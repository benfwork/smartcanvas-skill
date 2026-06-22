#!/usr/bin/env python3
"""Inspect embedded SmartCanvas image metadata XML and sidecar parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from export_smartcanvas_catalog import parse_image_info, read_package
from inspect_smartcanvas_package import decode_text, scan_wire_message


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_top_level_payload(data: bytes, field_number: int) -> bytes | None:
    for _, field, wire_type, value in scan_wire_message(data):
        if field == field_number and wire_type == 2 and isinstance(value, bytes):
            return value
    return None


def extract_embedded_records(info_bin: bytes) -> list[dict[str, object]]:
    catalog = first_top_level_payload(info_bin, 1)
    if catalog is None:
        raise SystemExit("info.bin has no field 1 catalog payload")

    records: list[dict[str, object]] = []
    for _, field, wire_type, value in scan_wire_message(catalog):
        if field == 21 and wire_type == 2 and isinstance(value, bytes):
            records.append(extract_image_record(value))
    return records


def extract_image_record(data: bytes) -> dict[str, object]:
    record: dict[str, object] = {
        "caption": "",
        "filename": "",
        "hash": "",
        "declared_size": None,
        "embedded_metadata_xml_bytes": 0,
        "embedded_metadata_xml_sha256": "",
        "embedded_metadata": None,
    }
    for _, field, wire_type, value in scan_wire_message(data):
        if field == 1 and wire_type == 2 and isinstance(value, bytes):
            record["caption"] = decode_text(value) or ""
        elif field == 2 and wire_type == 2 and isinstance(value, bytes):
            populate_record_details(record, value)
    return record


def populate_record_details(record: dict[str, object], data: bytes) -> None:
    for _, field, wire_type, value in scan_wire_message(data):
        if field == 1 and wire_type == 2 and isinstance(value, bytes):
            record["filename"] = decode_text(value) or ""
        elif field == 2 and wire_type == 2 and isinstance(value, bytes):
            record["hash"] = decode_text(value) or ""
        elif field == 3 and wire_type == 0:
            record["declared_size"] = value
        elif field == 4 and wire_type == 2 and isinstance(value, bytes):
            record["embedded_metadata_xml_bytes"] = len(value)
            record["embedded_metadata_xml_sha256"] = sha256(value)
            record["embedded_metadata"] = parse_metadata_xml(f"info.bin:{record.get('caption', '')}", value)


def parse_metadata_xml(label: str, data: bytes) -> dict[str, object]:
    try:
        return parse_image_info(label, data)
    except ET.ParseError as exc:
        return {"path": label, "parse_error": str(exc)}


def sidecars_by_caption(files: dict[str, bytes]) -> dict[str, dict[str, object]]:
    sidecars: dict[str, dict[str, object]] = {}
    for path, data in files.items():
        if not path.endswith("_info.xml"):
            continue
        parsed = parse_metadata_xml(path, data)
        caption = str(parsed.get("caption", ""))
        if not caption:
            continue
        sidecars[caption] = {
            "path": path,
            "xml_bytes": len(data),
            "xml_sha256": sha256(data),
            "metadata": parsed,
            "raw": data,
        }
    return sidecars


def compare_metadata_fields(embedded: dict[str, object] | None, sidecar: dict[str, object] | None) -> list[str]:
    if not embedded or not sidecar:
        return []
    fields = (
        "caption",
        "group_name",
        "is_selected",
        "image_width",
        "image_height",
        "filesize",
        "last_write_utc",
        "is_multi_image",
        "dpi_x",
        "dpi_y",
        "bitmap_type",
        "has_mask",
        "has_profile",
        "scalings",
        "page",
    )
    mismatches = []
    for field in fields:
        if embedded.get(field) != sidecar.get(field):
            mismatches.append(field)
    return mismatches


def build_summary(path: Path) -> dict[str, object]:
    source_label, files = read_package(path)
    if "info.bin" not in files:
        raise SystemExit(f"package has no info.bin: {path}")

    sidecars = sidecars_by_caption(files)
    records = []
    for embedded in extract_embedded_records(files["info.bin"]):
        caption = str(embedded.get("caption", ""))
        sidecar = sidecars.get(caption)
        sidecar_metadata = sidecar.get("metadata") if sidecar else None
        embedded_metadata = embedded.get("embedded_metadata") if isinstance(embedded.get("embedded_metadata"), dict) else None
        records.append(
            {
                "caption": caption,
                "filename": embedded.get("filename", ""),
                "hash": embedded.get("hash", ""),
                "declared_size": embedded.get("declared_size"),
                "embedded_metadata_xml_bytes": embedded.get("embedded_metadata_xml_bytes"),
                "embedded_metadata_xml_sha256": embedded.get("embedded_metadata_xml_sha256"),
                "sidecar_path": sidecar.get("path", "") if sidecar else "",
                "sidecar_xml_bytes": sidecar.get("xml_bytes") if sidecar else None,
                "sidecar_xml_sha256": sidecar.get("xml_sha256", "") if sidecar else "",
                "sidecar_found": sidecar is not None,
                "embedded_matches_sidecar_exactly": bool(
                    sidecar and embedded.get("embedded_metadata_xml_sha256") == sidecar.get("xml_sha256")
                ),
                "parsed_metadata_mismatches": compare_metadata_fields(embedded_metadata, sidecar_metadata),
                "embedded_metadata": embedded_metadata,
                "sidecar_metadata": sidecar_metadata,
            }
        )

    captions = {str(record["caption"]) for record in records}
    sidecar_only = sorted(caption for caption in sidecars if caption not in captions)
    exact_matches = sum(1 for record in records if record["embedded_matches_sidecar_exactly"])
    missing_sidecars = sum(1 for record in records if not record["sidecar_found"])
    parsed_mismatches = sum(1 for record in records if record["parsed_metadata_mismatches"])

    return {
        "source": source_label,
        "embedded_record_count": len(records),
        "sidecar_count": len(sidecars),
        "embedded_sidecar_exact_match_count": exact_matches,
        "embedded_sidecar_exact_mismatch_count": len(records) - exact_matches,
        "missing_sidecar_count": missing_sidecars,
        "parsed_metadata_mismatch_count": parsed_mismatches,
        "sidecar_only_captions": sidecar_only,
        "records": records,
    }


def record_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for record in summary.get("records", []):
        rows[str(record.get("caption", ""))] = {
            key: value
            for key, value in record.items()
            if key not in {"embedded_metadata", "sidecar_metadata"}
        }
    return rows


def map_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_keys = set(before)
    after_keys = set(after)
    changed = []
    for key in sorted(before_keys & after_keys):
        if before[key] != after[key]:
            changed.append({"key": key, "before": before[key], "after": after[key]})
    return {
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "changed": changed,
    }


def build_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    return {
        "before": before["source"],
        "after": after["source"],
        "counts": {
            "embedded_record_count": [before["embedded_record_count"], after["embedded_record_count"]],
            "sidecar_count": [before["sidecar_count"], after["sidecar_count"]],
            "embedded_sidecar_exact_match_count": [
                before["embedded_sidecar_exact_match_count"],
                after["embedded_sidecar_exact_match_count"],
            ],
            "embedded_sidecar_exact_mismatch_count": [
                before["embedded_sidecar_exact_mismatch_count"],
                after["embedded_sidecar_exact_mismatch_count"],
            ],
            "parsed_metadata_mismatch_count": [
                before["parsed_metadata_mismatch_count"],
                after["parsed_metadata_mismatch_count"],
            ],
        },
        "records": map_delta(record_rows(before), record_rows(after)),
        "sidecar_only_captions": map_delta(
            {caption: True for caption in before.get("sidecar_only_captions", [])},
            {caption: True for caption in after.get("sidecar_only_captions", [])},
        ),
    }


def print_summary(summary: dict[str, object], limit: int) -> None:
    print(f"Source: {summary['source']}")
    print(f"Embedded image metadata records: {summary['embedded_record_count']}")
    print(f"Sidecars: {summary['sidecar_count']}")
    print(f"Exact embedded/sidecar matches: {summary['embedded_sidecar_exact_match_count']}")
    print(f"Exact embedded/sidecar mismatches: {summary['embedded_sidecar_exact_mismatch_count']}")
    print(f"Missing sidecars: {summary['missing_sidecar_count']}")
    print(f"Parsed metadata mismatches: {summary['parsed_metadata_mismatch_count']}")
    if summary["sidecar_only_captions"]:
        print(f"Sidecar-only captions: {len(summary['sidecar_only_captions'])}")
        for caption in summary["sidecar_only_captions"][:limit]:
            print(f"  - {caption}")
    print("\nRecords")
    for record in summary["records"][:limit]:
        print(
            f"  - {record['caption']}: embedded={record['embedded_metadata_xml_bytes']} bytes, "
            f"sidecar={record['sidecar_xml_bytes']} bytes, exact={record['embedded_matches_sidecar_exactly']}"
        )


def print_delta(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    counts = delta["counts"]
    print("\nCounts")
    for key, value in counts.items():
        print(f"  {key}: {value[0]} -> {value[1]}")
    print_map_delta("Image Metadata Records", delta["records"], limit)
    print_map_delta("Sidecar-Only Captions", delta["sidecar_only_captions"], limit)


def print_map_delta(title: str, delta: dict[str, object], limit: int) -> None:
    print(f"\n{title}")
    print(f"  added: {len(delta['added'])}")
    for item in delta["added"][:limit]:
        print(f"  + {item}")
    print(f"  removed: {len(delta['removed'])}")
    for item in delta["removed"][:limit]:
        print(f"  - {item}")
    print(f"  changed: {len(delta['changed'])}")
    for item in delta["changed"][:limit]:
        print(f"  * {item['key']}")
        print(f"    before: {item['before']}")
        print(f"    after:  {item['after']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Outer export folder, inner campaign zip, or extracted inner folder")
    parser.add_argument("after", nargs="?", type=Path, help="Optional after package to compare with path")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON summary or delta to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")
    if args.after and not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    before = build_summary(args.path)
    result = build_delta(before, build_summary(args.after)) if args.after else before

    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.format == "text":
        if args.after:
            print_delta(result, args.limit)
        else:
            print_summary(result, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
