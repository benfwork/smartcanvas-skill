#!/usr/bin/env python3
"""Export a machine-readable SmartCanvas catalog manifest as JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from inspect_smartcanvas_package import IMAGE_EXTENSIONS, summarize_info_bin, verify_image_records


def normalize_member_name(name: str) -> str:
    parts = [part for part in name.split("/") if part]
    if len(parts) > 1:
        return "/".join(parts[1:])
    return "/".join(parts)


def read_package(path: Path) -> tuple[str, dict[str, bytes]]:
    if path.is_dir() and (path / "info.json").exists():
        zips = sorted((path / "Admin").glob("*.zip"))
        if not zips:
            raise SystemExit(f"outer export has no Admin/*.zip: {path}")
        return f"outer:{path}", read_zip(zips[0])
    if path.is_file() and path.suffix.lower() == ".zip":
        return f"zip:{path}", read_zip(path)
    if path.is_dir():
        return f"folder:{path}", read_folder(path)
    raise SystemExit(f"unsupported path: {path}")


def read_zip(path: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            files[normalize_member_name(info.filename)] = archive.read(info.filename)
    return files


def read_folder(path: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for file_path in path.rglob("*"):
        if not file_path.is_file() or file_path.name.endswith(":Zone.Identifier"):
            continue
        files[str(file_path.relative_to(path))] = file_path.read_bytes()
    return files


def asset_stem(caption: str) -> str:
    path = Path(caption)
    suffix = path.suffix[1:]
    if not suffix:
        return path.name
    return f"{path.stem}_{suffix}"


def parse_image_info(path: str, data: bytes) -> dict[str, object]:
    root = ET.fromstring(data.decode("utf-8-sig", errors="replace"))
    resource = root.find("Resourceinfo")
    page = root.find("./Pages/Page")
    scalings = resource.find("./CustomProperties/Scalings") if resource is not None else None
    return {
        "path": path,
        "caption": root.attrib.get("Caption", ""),
        "group_name": root.attrib.get("GroupName", ""),
        "is_selected": root.attrib.get("IsSelected", ""),
        "image_width": int_or_none(root.attrib.get("ImageWidth")),
        "image_height": int_or_none(root.attrib.get("ImageHeight")),
        "filesize": int_or_none(root.attrib.get("Filesize")),
        "last_write_utc": root.attrib.get("LastWriteUtc", ""),
        "is_multi_image": root.attrib.get("IsMultiImage", ""),
        "page": dict(page.attrib) if page is not None else {},
        "dpi_x": int_or_none(resource.attrib.get("DPIx")) if resource is not None else None,
        "dpi_y": int_or_none(resource.attrib.get("DPIy")) if resource is not None else None,
        "bitmap_type": resource.attrib.get("BitmapType", "") if resource is not None else "",
        "has_mask": resource.attrib.get("HasMask", "") if resource is not None else "",
        "has_profile": resource.attrib.get("HasProfile", "") if resource is not None else "",
        "scalings": scalings.attrib.get("Value", "") if scalings is not None else "",
    }


def int_or_none(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def build_manifest(source_label: str, files: dict[str, bytes]) -> dict[str, object]:
    if "info.bin" not in files:
        raise SystemExit("package has no info.bin")

    info_summary = summarize_info_bin(files["info.bin"])
    if info_summary.get("parse_error"):
        raise SystemExit(f"info.bin parse error: {info_summary['parse_error']}")

    image_paths_by_basename: dict[str, list[str]] = defaultdict(list)
    image_bytes_by_basename: dict[str, bytes] = {}
    for path, data in files.items():
        if Path(path).suffix.lower() in IMAGE_EXTENSIONS:
            basename = Path(path).name
            image_paths_by_basename[basename].append(path)
            image_bytes_by_basename.setdefault(basename, data)

    sidecars_by_caption: dict[str, dict[str, object]] = {}
    for path, data in files.items():
        if path.endswith("_info.xml"):
            try:
                info = parse_image_info(path, data)
            except ET.ParseError:
                continue
            caption = str(info.get("caption", ""))
            if caption:
                sidecars_by_caption[caption] = info

    categories_by_caption = {record.get("caption"): record.get("category") for record in info_summary["image_categories"]}
    verification_by_caption = {record["caption"]: record for record in verify_image_records(info_summary, image_bytes_by_basename)}

    images = []
    for record in info_summary["image_records"]:
        caption = str(record.get("caption", ""))
        stem = asset_stem(caption)
        original_paths = sorted(image_paths_by_basename.get(caption, []))
        original_data = image_bytes_by_basename.get(caption)
        sidecar = sidecars_by_caption.get(caption)
        sidecar_filesize = sidecar.get("filesize") if sidecar else None
        actual_size = len(original_data) if original_data is not None else None
        thumbnail_inline = sorted(path for path in files if Path(path).name == f"{stem}_thumbi.png")
        thumbnail_normal = sorted(path for path in files if Path(path).name == f"{stem}_thumbn.png")
        scaled_assets = sorted(
            path
            for path in files
            if f"/{stem}/" in path and Path(path).suffix.lower() in IMAGE_EXTENSIONS
        )
        images.append(
            {
                "caption": caption,
                "category": categories_by_caption.get(caption, ""),
                "catalog_hash_sha1": record.get("hash", ""),
                "declared_size": record.get("declared_size"),
                "metadata_xml_bytes": record.get("metadata_xml_bytes"),
                "original_paths": original_paths,
                "actual_size": actual_size,
                "actual_sha1": sha1(original_data) if original_data is not None else "",
                "verification": verification_by_caption.get(caption, {}),
                "sidecar": sidecar,
                "sidecar_filesize_matches_actual": sidecar_filesize == actual_size if sidecar_filesize is not None else None,
                "thumbi_paths": thumbnail_inline,
                "thumbn_paths": thumbnail_normal,
                "scaled_asset_paths": scaled_assets,
            }
        )

    categories: dict[str, list[str]] = defaultdict(list)
    for image in images:
        category = str(image.get("category") or "[uncategorized]")
        categories[category].append(str(image["caption"]))

    sidecar_filesize_matches = sum(1 for image in images if image.get("sidecar_filesize_matches_actual") is True)
    sidecar_filesize_mismatches = sum(1 for image in images if image.get("sidecar_filesize_matches_actual") is False)

    resource_mime_counts: dict[str, int] = defaultdict(int)
    for resource in info_summary["resource_records"]:
        resource_mime_counts[str(resource.get("mime", ""))] += 1

    return {
        "source": source_label,
        "file_count": len(files),
        "image_file_count": sum(1 for path in files if Path(path).suffix.lower() in IMAGE_EXTENSIONS),
        "info_bin": {
            "size": info_summary["size"],
            "catalog_fields": info_summary["catalog_fields"],
            "database_column_count": len(info_summary["database_columns"]),
            "resource_blob_count": info_summary["resource_blob_count"],
            "resource_blob_bytes": info_summary["resource_blob_bytes"],
            "resource_mime_counts": dict(sorted(resource_mime_counts.items())),
        },
        "sidecar_filesize_matches_actual": sidecar_filesize_matches,
        "sidecar_filesize_mismatches_actual": sidecar_filesize_mismatches,
        "categories": {category: sorted(captions) for category, captions in sorted(categories.items())},
        "images": images,
        "resources": info_summary["resource_records"],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Outer export folder, inner campaign zip, or extracted inner campaign folder")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON to this file instead of stdout")
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")

    source_label, files = read_package(args.path)
    manifest = build_manifest(source_label, files)
    text = json.dumps(manifest, indent=2, sort_keys=True)

    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
