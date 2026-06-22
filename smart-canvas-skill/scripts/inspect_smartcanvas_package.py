#!/usr/bin/env python3
"""Summarize an extracted SmartCanvas export folder or inner campaign zip."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff"}


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
    raise EOFError("unterminated varint")


def scan_wire_message(data: bytes):
    pos = 0
    while pos < len(data):
        tag_pos = pos
        tag, pos = read_varint(data, pos)
        if tag == 0:
            raise ValueError(f"zero protobuf tag at offset {tag_pos}")
        field = tag >> 3
        wire_type = tag & 7
        if wire_type == 0:
            value, pos = read_varint(data, pos)
            yield tag_pos, field, wire_type, value
        elif wire_type == 1:
            value = data[pos : pos + 8]
            pos += 8
            yield tag_pos, field, wire_type, value
        elif wire_type == 2:
            length, pos = read_varint(data, pos)
            value = data[pos : pos + length]
            pos += length
            yield tag_pos, field, wire_type, value
        elif wire_type == 5:
            value = data[pos : pos + 4]
            pos += 4
            yield tag_pos, field, wire_type, value
        else:
            raise ValueError(f"unsupported protobuf wire type {wire_type} at offset {tag_pos}")


def decode_text(value: bytes) -> str | None:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        return None
    return text


def summarize_info_bin(data: bytes) -> dict[str, object]:
    summary: dict[str, object] = {
        "size": len(data),
        "top_fields": [],
        "catalog_fields": {},
        "image_names": [],
        "image_records": [],
        "image_categories": [],
        "database_columns": [],
        "resource_records": [],
        "resource_blob_count": 0,
        "resource_blob_bytes": 0,
        "parse_error": None,
    }

    try:
        top_records = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        summary["parse_error"] = f"top-level parse failed: {exc}"
        return summary

    summary["top_fields"] = [
        {"offset": offset, "field": field, "wire_type": wire_type, "length": len(value) if isinstance(value, bytes) else None}
        for offset, field, wire_type, value in top_records
    ]

    catalog = None
    for _, field, wire_type, value in top_records:
        if field == 1 and wire_type == 2 and isinstance(value, bytes):
            catalog = value
            break
    if catalog is None:
        summary["parse_error"] = "no field 1 catalog payload found"
        return summary

    try:
        catalog_records = list(scan_wire_message(catalog))
    except Exception as exc:  # noqa: BLE001
        summary["parse_error"] = f"catalog parse failed: {exc}"
        return summary

    field_counts = Counter((field, wire_type) for _, field, wire_type, _ in catalog_records)
    summary["catalog_fields"] = {f"field_{field}_wire_{wire_type}": count for (field, wire_type), count in sorted(field_counts.items())}

    image_names: list[str] = []
    image_categories: list[dict[str, str]] = []
    database_columns: list[str] = []
    image_records: list[dict[str, object]] = []
    resource_records: list[dict[str, object]] = []
    resource_blob_count = 0
    resource_blob_bytes = 0

    for _, field, wire_type, value in catalog_records:
        if wire_type != 2 or not isinstance(value, bytes):
            continue
        text = decode_text(value)
        if field == 1 and text:
            image_names.append(text)
        elif field == 48 and text:
            database_columns.append(text)
        elif field == 49:
            resource_blob_count += 1
            resource_blob_bytes += len(value)
            resource_records.append(summarize_resource_record(value))
        elif field == 21:
            image_records.append(summarize_image_record(value))

    for _, field, wire_type, value in top_records:
        if field == 26 and wire_type == 2 and isinstance(value, bytes):
            image_categories.append(summarize_category_record(value))

    summary["image_names"] = image_names
    summary["image_categories"] = image_categories
    summary["database_columns"] = database_columns
    summary["image_records"] = image_records
    summary["resource_records"] = resource_records
    summary["resource_blob_count"] = resource_blob_count
    summary["resource_blob_bytes"] = resource_blob_bytes
    return summary


def summarize_resource_record(data: bytes) -> dict[str, object]:
    record: dict[str, object] = {
        "name": "",
        "family": "",
        "style": "",
        "kind": "",
        "source_format": "",
        "filename": "",
        "mime": "",
        "variant": None,
        "weight": None,
        "data_len": 0,
    }
    try:
        fields = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        record["parse_error"] = str(exc)
        return record

    for _, field, wire_type, value in fields:
        text = decode_text(value) if isinstance(value, bytes) else None
        if field == 1 and text is not None:
            record["name"] = text
        elif field == 2 and text is not None:
            record["family"] = text
        elif field == 4 and text is not None:
            record["style"] = text
        elif field == 5 and text is not None:
            record["kind"] = text
        elif field == 8 and text is not None:
            record["source_format"] = text
        elif field == 10 and text is not None:
            record["filename"] = text
        elif field == 11 and text is not None:
            record["mime"] = text
        elif field == 12 and wire_type == 0:
            record["variant"] = value
        elif field == 14 and wire_type == 0:
            record["weight"] = value
        elif field == 19 and isinstance(value, bytes):
            record["data_len"] = len(value)
    return record


def verify_image_records(summary: dict[str, object], files_by_basename: dict[str, bytes]) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for record in summary.get("image_records", []):
        caption = str(record.get("caption", ""))
        data = files_by_basename.get(caption)
        if data is None:
            checks.append(
                {
                    "caption": caption,
                    "file_found": False,
                    "size_match": False,
                    "sha1_match": False,
                    "actual_size": None,
                    "actual_sha1": "",
                }
            )
            continue

        actual_sha1 = hashlib.sha1(data).hexdigest().upper()
        checks.append(
            {
                "caption": caption,
                "file_found": True,
                "size_match": len(data) == record.get("declared_size"),
                "sha1_match": actual_sha1 == record.get("hash"),
                "actual_size": len(data),
                "actual_sha1": actual_sha1,
            }
        )
    return checks


def summarize_category_record(data: bytes) -> dict[str, str]:
    record = {"caption": "", "category": ""}
    try:
        fields = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        record["parse_error"] = str(exc)
        return record

    for _, field, wire_type, value in fields:
        if wire_type == 2 and isinstance(value, bytes):
            if field == 1:
                record["caption"] = decode_text(value) or ""
            elif field == 2:
                record["category"] = decode_text(value) or ""
    return record


def summarize_image_record(data: bytes) -> dict[str, object]:
    record: dict[str, object] = {
        "caption": "",
        "filename": "",
        "hash": "",
        "declared_size": None,
        "metadata_xml_bytes": 0,
    }
    try:
        fields = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        record["parse_error"] = str(exc)
        return record

    for _, field, wire_type, value in fields:
        if field == 1 and wire_type == 2 and isinstance(value, bytes):
            record["caption"] = decode_text(value) or ""
        elif field == 2 and wire_type == 2 and isinstance(value, bytes):
            populate_image_record_details(record, value)
    return record


def populate_image_record_details(record: dict[str, object], data: bytes) -> None:
    try:
        fields = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        record["detail_parse_error"] = str(exc)
        return

    for _, field, wire_type, value in fields:
        if field == 1 and wire_type == 2 and isinstance(value, bytes):
            record["filename"] = decode_text(value) or ""
        elif field == 2 and wire_type == 2 and isinstance(value, bytes):
            record["hash"] = decode_text(value) or ""
        elif field == 3 and wire_type == 0:
            record["declared_size"] = value
        elif field == 4 and wire_type == 2 and isinstance(value, bytes):
            record["metadata_xml_bytes"] = len(value)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def xml_root_summary_from_bytes(data: bytes) -> str:
    root = ET.fromstring(data.decode("utf-8-sig", errors="replace"))
    attrs = " ".join(f'{key}="{value}"' for key, value in list(root.attrib.items())[:6])
    return f"<{root.tag} {attrs}>".strip()


def xml_root_summary(path: Path) -> str:
    return xml_root_summary_from_bytes(path.read_bytes())


def safe_print(label: str, value: object = "") -> None:
    if value == "":
        print(label)
    else:
        print(f"{label}: {value}")


def inspect_outer_folder(path: Path) -> None:
    safe_print("Mode", "outer/extracted folder")
    safe_print("Path", path)

    info_json = path / "info.json"
    if info_json.exists():
        try:
            info = json.loads(read_text(info_json))
            safe_print("info.json SourceAccountId", info.get("SourceAccountId"))
            campaigns = info.get("Admin", {}).get("Campaigns", [])
            if campaigns:
                campaign = campaigns[0]
                safe_print("info.json SourceCampaignName", campaign.get("SourceCampaignName"))
                safe_print("info.json SourceCampaignDisplayName", campaign.get("SourceCampaignDisplayName"))
        except json.JSONDecodeError as exc:
            safe_print("info.json parse error", exc)

    admin_zips = sorted((path / "Admin").glob("*.zip")) if (path / "Admin").exists() else []
    safe_print("Admin zip count", len(admin_zips))
    for zip_path in admin_zips:
        safe_print("Admin zip", f"{zip_path.name} ({zip_path.stat().st_size} bytes)")

    impositions = sorted((path / "Impositions").glob("*.xml")) if (path / "Impositions").exists() else []
    pdf_presets = sorted((path / "PdfPresets").glob("*.xml")) if (path / "PdfPresets").exists() else []
    safe_print("Imposition XML count", len(impositions))
    safe_print("PdfPreset XML count", len(pdf_presets))

    imp_names = {p.name for p in impositions}
    pdf_names = {p.name for p in pdf_presets}
    if impositions or pdf_presets:
        safe_print("Imposition/PdfPreset filename sets identical", imp_names == pdf_names)
        matching = sorted(imp_names & pdf_names)
        differing = [name for name in matching if (path / "Impositions" / name).read_bytes() != (path / "PdfPresets" / name).read_bytes()]
        safe_print("Imposition/PdfPreset differing content count", len(differing))

    if impositions:
        safe_print("")
        safe_print("Impositions")
        for imposition in impositions:
            root = ET.fromstring(imposition.read_bytes().decode("utf-8-sig", errors="replace"))
            signatures = len(root.findall("./ImpositionList/Signature"))
            display_name = root.attrib.get("ImpositionDisplayName", "")
            doc_size = f'{root.attrib.get("DocWidth", "?")} x {root.attrib.get("DocHeight", "?")}'
            print(f"- {imposition.name}: {display_name!r}, duplex={root.attrib.get('Duplex')}, pages={root.attrib.get('DocPageCount')}, signatures={signatures}, doc={doc_size}")

    for zip_path in admin_zips:
        safe_print("")
        inspect_zip(zip_path)


def inspect_zip(path: Path) -> None:
    safe_print("Mode", "inner campaign zip")
    safe_print("Zip", path)
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        files = [info for info in infos if not info.is_dir()]
        safe_print("Entry count", len(infos))
        safe_print("File count", len(files))

        top_level = Counter(info.filename.split("/")[0] for info in infos)
        safe_print("Top-level entries", dict(top_level.most_common()))

        extensions = Counter(Path(info.filename).suffix.lower() or "[no ext]" for info in files)
        safe_print("File extensions", dict(extensions.most_common()))

        safe_print("")
        safe_print("Key XML files")
        for info in files:
            name = info.filename
            if Path(name).name in {"template.xml", "Document.xml", "template.dhtt", "description.xml", "scriptsnippets.xml"}:
                try:
                    print(f"- {name}: {xml_root_summary_from_bytes(archive.read(name))}")
                except Exception as exc:  # noqa: BLE001
                    print(f"- {name}: parse error: {exc}")

        image_files = [info for info in files if Path(info.filename).suffix.lower() in IMAGE_EXTENSIONS]
        image_files_by_basename = {Path(info.filename).name: archive.read(info.filename) for info in image_files}
        image_info_files = [info for info in files if info.filename.endswith("_info.xml")]
        safe_print("")
        safe_print("Image file count", len(image_files))
        safe_print("Image metadata XML count", len(image_info_files))

        if image_info_files:
            safe_print("Image metadata")
            for info in image_info_files:
                root = ET.fromstring(archive.read(info.filename).decode("utf-8-sig", errors="replace"))
                resource = root.find("Resourceinfo")
                scaling = ""
                if resource is not None:
                    scalings = resource.find("./CustomProperties/Scalings")
                    if scalings is not None:
                        scaling = scalings.attrib.get("Value", "")
                print(
                    "- "
                    f"{info.filename}: caption={root.attrib.get('Caption')!r}, "
                    f"group={root.attrib.get('GroupName')!r}, "
                    f"selected={root.attrib.get('IsSelected')}, "
                    f"size={root.attrib.get('ImageWidth')}x{root.attrib.get('ImageHeight')}, "
                    f"type={resource.attrib.get('BitmapType') if resource is not None else ''}, "
                    f"scalings={scaling!r}"
                )

        for binary_name in ("info.bin", "databases.bin"):
            if any(info.filename == binary_name for info in files):
                data = archive.read(binary_name)
                safe_print("")
                if binary_name == "info.bin":
                    print_info_bin_summary(data, image_files_by_basename)
                else:
                    strings = re.findall(rb"[\x20-\x7e]{4,}", data[: min(len(data), 2_000_000)])
                    safe_print(binary_name, f"{len(data)} bytes; readable strings in first 2MB={len(strings)}")
                    for value in strings[:20]:
                        print(f"- {value.decode('ascii', errors='replace')}")


def print_info_bin_summary(data: bytes, image_files_by_basename: dict[str, bytes] | None = None) -> None:
    summary = summarize_info_bin(data)
    safe_print("info.bin", f"{summary['size']} bytes")
    if summary["parse_error"]:
        safe_print("info.bin parse error", summary["parse_error"])
        strings = re.findall(rb"[\x20-\x7e]{4,}", data[: min(len(data), 2_000_000)])
        safe_print("readable strings in first 2MB", len(strings))
        for value in strings[:20]:
            print(f"- {value.decode('ascii', errors='replace')}")
        return

    safe_print("info.bin top fields", summary["top_fields"])
    safe_print("info.bin catalog fields", summary["catalog_fields"])
    safe_print("info.bin image names", len(summary["image_names"]))
    for name in summary["image_names"][:30]:
        print(f"- {name}")
    if len(summary["image_names"]) > 30:
        print(f"- ... {len(summary['image_names']) - 30} more")

    safe_print("info.bin image records", len(summary["image_records"]))
    for record in summary["image_records"][:30]:
        print(
            "- "
            f"caption={record.get('caption')!r}, "
            f"hash={record.get('hash')!r}, "
            f"declared_size={record.get('declared_size')}, "
            f"metadata_xml_bytes={record.get('metadata_xml_bytes')}"
        )
    if len(summary["image_records"]) > 30:
        print(f"- ... {len(summary['image_records']) - 30} more")

    if image_files_by_basename is not None:
        checks = verify_image_records(summary, image_files_by_basename)
        missing = [check for check in checks if not check["file_found"]]
        size_mismatches = [check for check in checks if check["file_found"] and not check["size_match"]]
        sha1_mismatches = [check for check in checks if check["file_found"] and not check["sha1_match"]]
        safe_print(
            "info.bin image file verification",
            f"{len(checks) - len(missing)}/{len(checks)} files found, "
            f"{len(checks) - len(missing) - len(size_mismatches)}/{len(checks)} sizes match, "
            f"{len(checks) - len(missing) - len(sha1_mismatches)}/{len(checks)} SHA-1 hashes match",
        )
        for label, problems in (("missing", missing), ("size mismatch", size_mismatches), ("SHA-1 mismatch", sha1_mismatches)):
            for problem in problems[:20]:
                print(f"- {label}: {problem['caption']}")
            if len(problems) > 20:
                print(f"- ... {len(problems) - 20} more {label} records")

    safe_print("info.bin image categories", len(summary["image_categories"]))
    for record in summary["image_categories"][:40]:
        print(f"- caption={record.get('caption')!r}, category={record.get('category')!r}")
    if len(summary["image_categories"]) > 40:
        print(f"- ... {len(summary['image_categories']) - 40} more")

    image_names = set(summary["image_names"])
    categorized_names = {record.get("caption") for record in summary["image_categories"]}
    uncategorized = sorted(name for name in image_names - categorized_names if name)
    if uncategorized:
        safe_print("info.bin uncategorized images", len(uncategorized))
        for name in uncategorized[:40]:
            print(f"- {name}")

    safe_print("info.bin database columns", len(summary["database_columns"]))
    print(", ".join(summary["database_columns"][:40]))
    safe_print("info.bin resource blobs", f"{summary['resource_blob_count']} blobs / {summary['resource_blob_bytes']} bytes")
    resource_records = summary["resource_records"]
    if resource_records:
        safe_print("info.bin resource MIME counts", dict(Counter(record.get("mime", "") for record in resource_records)))
        safe_print("info.bin resource filenames", len(resource_records))
        for record in resource_records[:30]:
            print(
                "- "
                f"filename={record.get('filename')!r}, "
                f"family={record.get('family')!r}, "
                f"style={record.get('style')!r}, "
                f"mime={record.get('mime')!r}, "
                f"bytes={record.get('data_len')}"
            )
        if len(resource_records) > 30:
            print(f"- ... {len(resource_records) - 30} more")


def inspect_extracted_inner_folder(path: Path) -> None:
    safe_print("Mode", "extracted inner campaign folder")
    safe_print("Path", path)

    files = [p for p in path.rglob("*") if p.is_file() and not p.name.endswith(":Zone.Identifier")]
    safe_print("File count", len(files))
    extensions = Counter(p.suffix.lower() or "[no ext]" for p in files)
    safe_print("File extensions", dict(extensions.most_common()))

    safe_print("")
    safe_print("Key XML files")
    for filename in ("template.xml", "Document.xml", "template.dhtt", "description.xml"):
        matches = sorted(path.rglob(filename))
        for match in matches:
            try:
                print(f"- {match.relative_to(path)}: {xml_root_summary(match)}")
            except Exception as exc:  # noqa: BLE001
                print(f"- {match.relative_to(path)}: parse error: {exc}")

    image_info_files = sorted(path.rglob("*_info.xml"))
    image_files_by_basename = {
        file_path.name: file_path.read_bytes()
        for file_path in path.rglob("*")
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS and not file_path.name.endswith(":Zone.Identifier")
    }
    safe_print("")
    safe_print("Image metadata XML count", len(image_info_files))
    for info_file in image_info_files:
        root = ET.fromstring(read_text(info_file))
        resource = root.find("Resourceinfo")
        print(
            "- "
            f"{info_file.relative_to(path)}: caption={root.attrib.get('Caption')!r}, "
            f"group={root.attrib.get('GroupName')!r}, "
            f"selected={root.attrib.get('IsSelected')}, "
            f"size={root.attrib.get('ImageWidth')}x{root.attrib.get('ImageHeight')}, "
            f"type={resource.attrib.get('BitmapType') if resource is not None else ''}"
        )

    info_bins = sorted(path.rglob("info.bin"))
    for info_bin in info_bins:
        safe_print("")
        safe_print("Binary catalog", info_bin.relative_to(path))
        print_info_bin_summary(info_bin.read_bytes(), image_files_by_basename)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Outer export folder, inner campaign zip, or extracted inner campaign folder")
    args = parser.parse_args(argv)

    path = args.path
    if not path.exists():
        parser.error(f"path does not exist: {path}")

    if path.is_file() and path.suffix.lower() == ".zip":
        inspect_zip(path)
        return 0

    if path.is_dir() and (path / "info.json").exists():
        inspect_outer_folder(path)
        return 0

    if path.is_dir():
        inspect_extracted_inner_folder(path)
        return 0

    parser.error(f"unsupported path: {path}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
