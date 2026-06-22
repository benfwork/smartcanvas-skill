#!/usr/bin/env python3
"""Dump grouped protobuf-wire summaries from SmartCanvas info.bin."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from export_smartcanvas_catalog import read_package
from inspect_smartcanvas_package import decode_text, scan_wire_message, summarize_info_bin


def read_info_bin(path: Path) -> tuple[str, bytes]:
    if path.is_file() and path.suffix.lower() != ".zip":
        return f"file:{path}", path.read_bytes()
    source_label, files = read_package(path)
    if "info.bin" not in files:
        raise SystemExit(f"no info.bin found in {path}")
    return source_label, files["info.bin"]


def field_key(field: int, wire_type: int) -> str:
    return f"field_{field}_wire_{wire_type}"


def summarize_wire(
    data: bytes,
    *,
    max_samples: int,
    max_inline_bytes: int,
    max_nested_bytes: int,
) -> dict[str, object]:
    groups: dict[str, dict[str, object]] = {}
    parse_error = None
    try:
        records = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        records = []
        parse_error = str(exc)

    for offset, field, wire_type, value in records:
        key = field_key(field, wire_type)
        group = groups.setdefault(
            key,
            {
                "field": field,
                "wire_type": wire_type,
                "count": 0,
                "first_offsets": [],
                "varint_samples": [],
                "varint_min": None,
                "varint_max": None,
                "length_samples": [],
                "length_total": 0,
                "text_samples": [],
                "hex_samples": [],
                "nested_field_counts": [],
                "nested_parse_errors": [],
            },
        )
        group["count"] += 1
        if len(group["first_offsets"]) < max_samples:
            group["first_offsets"].append(offset)

        if wire_type == 0 and isinstance(value, int):
            append_sample(group["varint_samples"], value, max_samples)
            group["varint_min"] = value if group["varint_min"] is None else min(group["varint_min"], value)
            group["varint_max"] = value if group["varint_max"] is None else max(group["varint_max"], value)
            continue

        if isinstance(value, bytes):
            length = len(value)
            append_sample(group["length_samples"], length, max_samples)
            group["length_total"] += length
            text = decode_text(value)
            if text is not None and length <= max_inline_bytes:
                append_sample(group["text_samples"], text, max_samples)
            elif length <= max_inline_bytes:
                append_sample(group["hex_samples"], value.hex(), max_samples)
            if length <= max_nested_bytes:
                nested = nested_field_counts(value)
                if "parse_error" in nested:
                    append_sample(group["nested_parse_errors"], nested["parse_error"], max_samples)
                else:
                    append_sample(group["nested_field_counts"], nested, max_samples)

    return {
        "size": len(data),
        "parse_error": parse_error,
        "field_groups": dict(sorted(groups.items(), key=lambda item: (item[1]["field"], item[1]["wire_type"]))),
    }


def append_sample(samples: list[object], value: object, max_samples: int) -> None:
    if len(samples) < max_samples and value not in samples:
        samples.append(value)


def nested_field_counts(data: bytes) -> dict[str, object]:
    try:
        records = list(scan_wire_message(data))
    except Exception as exc:  # noqa: BLE001
        return {"parse_error": str(exc)}
    counts = Counter(field_key(field, wire_type) for _, field, wire_type, _ in records)
    return dict(sorted(counts.items()))


def build_dump(args: argparse.Namespace) -> dict[str, object]:
    source_label, info_bin = read_info_bin(args.path)
    known = summarize_info_bin(info_bin)
    dump: dict[str, object] = {
        "source": source_label,
        "info_bin_size": len(info_bin),
        "known_summary": {
            "parse_error": known.get("parse_error"),
            "top_fields": known.get("top_fields"),
            "catalog_fields": known.get("catalog_fields"),
            "image_name_count": len(known.get("image_names", [])),
            "image_record_count": len(known.get("image_records", [])),
            "image_category_count": len(known.get("image_categories", [])),
            "database_column_count": len(known.get("database_columns", [])),
            "resource_blob_count": known.get("resource_blob_count"),
            "resource_blob_bytes": known.get("resource_blob_bytes"),
        },
        "top_level": summarize_wire(
            info_bin,
            max_samples=args.max_samples,
            max_inline_bytes=args.max_inline_bytes,
            max_nested_bytes=args.max_nested_bytes,
        ),
    }

    catalog = first_top_level_payload(info_bin, 1)
    if catalog is not None:
        dump["catalog_field_1"] = summarize_wire(
            catalog,
            max_samples=args.max_samples,
            max_inline_bytes=args.max_inline_bytes,
            max_nested_bytes=args.max_nested_bytes,
        )

    return dump


def first_top_level_payload(data: bytes, field_number: int) -> bytes | None:
    try:
        records = scan_wire_message(data)
        for _, field, wire_type, value in records:
            if field == field_number and wire_type == 2 and isinstance(value, bytes):
                return value
    except Exception:
        return None
    return None


def print_grouped_report(dump: dict[str, object], group_limit: int) -> None:
    print(f"Source: {dump['source']}")
    print(f"info.bin size: {dump['info_bin_size']}")
    known = dump["known_summary"]
    print("Known summary:")
    for key, value in known.items():
        if key == "top_fields":
            print(f"  {key}: {len(value or [])} records")
        else:
            print(f"  {key}: {value}")
    print_wire_report("Top-level fields", dump["top_level"], group_limit)
    if "catalog_field_1" in dump:
        print_wire_report("Catalog field 1 fields", dump["catalog_field_1"], group_limit)


def print_wire_report(title: str, summary: dict[str, object], group_limit: int) -> None:
    print("")
    print(title)
    if summary.get("parse_error"):
        print(f"  parse error: {summary['parse_error']}")
        return
    groups = summary["field_groups"]
    for key, group in list(groups.items())[:group_limit]:
        line = f"  {key}: count={group['count']}"
        if group["length_samples"]:
            line += f", length_samples={group['length_samples']}, length_total={group['length_total']}"
        if group["varint_samples"]:
            line += f", varint_samples={group['varint_samples']}, min={group['varint_min']}, max={group['varint_max']}"
        print(line)
        if group["text_samples"]:
            print(f"    text_samples={group['text_samples']}")
        if group["nested_field_counts"]:
            print(f"    nested_field_counts={group['nested_field_counts'][:3]}")
    if len(groups) > group_limit:
        print(f"  ... {len(groups) - group_limit} more field groups")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="info.bin, outer export folder, inner campaign zip, or extracted inner folder")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON dump to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--max-samples", type=int, default=5)
    parser.add_argument("--max-inline-bytes", type=int, default=200)
    parser.add_argument("--max-nested-bytes", type=int, default=100_000)
    parser.add_argument("--group-limit", type=int, default=80)
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")

    dump = build_dump(args)
    if args.output:
        args.output.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(dump, indent=2, sort_keys=True))
    elif args.format == "text":
        print_grouped_report(dump, args.group_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
