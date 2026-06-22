#!/usr/bin/env python3
"""Fingerprint and diff SmartCanvas binary files such as info.bin and databases.bin."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from export_smartcanvas_catalog import read_package
from inspect_smartcanvas_package import decode_text, scan_wire_message


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    printable = sum(1 for byte in data if byte in (9, 10, 13) or 32 <= byte <= 126)
    return printable / len(data)


def magic_type(data: bytes) -> str:
    if data.startswith(b"PK\x03\x04"):
        return "zip"
    if data.startswith(b"\x1f\x8b"):
        return "gzip"
    if data.startswith(b"SQLite format 3\x00"):
        return "sqlite"
    if data.startswith(b"\x78\x01") or data.startswith(b"\x78\x9c") or data.startswith(b"\x78\xda"):
        return "zlib"
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf8-bom"
    return "unknown"


def ascii_strings(data: bytes, *, min_length: int, limit: int) -> list[str]:
    values = []
    for match in re.finditer(rb"[\x20-\x7e]{" + str(min_length).encode("ascii") + rb",}", data):
        values.append(match.group(0).decode("ascii", errors="replace"))
        if len(values) >= limit:
            break
    return values


def field_key(field: int, wire_type: int) -> str:
    return f"field_{field}_wire_{wire_type}"


def wire_probe(data: bytes, *, max_samples: int, max_inline_bytes: int) -> dict[str, object]:
    records = []
    parse_error = None
    try:
        for record in scan_wire_message(data):
            records.append(record)
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)

    groups: dict[str, dict[str, object]] = {}
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
                "length_samples": [],
                "text_samples": [],
                "hex_samples": [],
            },
        )
        group["count"] += 1
        append_sample(group["first_offsets"], offset, max_samples)
        if wire_type == 0 and isinstance(value, int):
            append_sample(group["varint_samples"], value, max_samples)
        elif isinstance(value, bytes):
            append_sample(group["length_samples"], len(value), max_samples)
            if len(value) <= max_inline_bytes:
                text = decode_text(value)
                if text is not None:
                    append_sample(group["text_samples"], text, max_samples)
                else:
                    append_sample(group["hex_samples"], value.hex(), max_samples)

    return {
        "record_count_before_error": len(records),
        "parse_error": parse_error,
        "field_groups": dict(sorted(groups.items(), key=lambda item: (item[1]["field"], item[1]["wire_type"]))),
    }


def append_sample(values: list[object], value: object, max_samples: int) -> None:
    if len(values) < max_samples and value not in values:
        values.append(value)


def binary_files(path: Path) -> tuple[str, dict[str, bytes]]:
    if path.is_file() and path.suffix.lower() != ".zip":
        return f"file:{path}", {path.name: path.read_bytes()}
    source_label, files = read_package(path)
    return source_label, {name: data for name, data in files.items() if Path(name).suffix.lower() == ".bin"}


def build_summary(path: Path, *, min_string: int = 4, string_limit: int = 40) -> dict[str, object]:
    source_label, bins = binary_files(path)
    records = {}
    for name, data in sorted(bins.items()):
        records[name] = {
            "size": len(data),
            "sha256": sha256(data),
            "magic": magic_type(data),
            "entropy": round(entropy(data), 6),
            "printable_ratio": round(printable_ratio(data), 6),
            "ascii_strings": ascii_strings(data, min_length=min_string, limit=string_limit),
            "wire_probe": wire_probe(data, max_samples=5, max_inline_bytes=160),
        }
    return {
        "source": source_label,
        "binary_count": len(records),
        "binaries": records,
    }


def binary_rows(summary: dict[str, object]) -> dict[str, object]:
    return {
        name: {
            "size": record.get("size"),
            "sha256": record.get("sha256"),
            "magic": record.get("magic"),
            "entropy": record.get("entropy"),
            "printable_ratio": record.get("printable_ratio"),
            "wire_parse_error": (record.get("wire_probe") or {}).get("parse_error"),
            "wire_record_count_before_error": (record.get("wire_probe") or {}).get("record_count_before_error"),
            "wire_field_groups": sorted(((record.get("wire_probe") or {}).get("field_groups") or {}).keys()),
        }
        for name, record in summary.get("binaries", {}).items()
    }


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
        "binary_count": [before["binary_count"], after["binary_count"]],
        "binaries": map_delta(binary_rows(before), binary_rows(after)),
    }


def print_summary(summary: dict[str, object], limit: int) -> None:
    print(f"Source: {summary['source']}")
    print(f"Binary files: {summary['binary_count']}")
    for name, record in summary.get("binaries", {}).items():
        wire = record["wire_probe"]
        print(f"\n{name}")
        print(f"  size: {record['size']}")
        print(f"  sha256: {record['sha256']}")
        print(f"  magic: {record['magic']}")
        print(f"  entropy: {record['entropy']}")
        print(f"  printable ratio: {record['printable_ratio']}")
        print(f"  wire records before error: {wire['record_count_before_error']}")
        print(f"  wire parse error: {wire['parse_error']}")
        if record["ascii_strings"]:
            print("  ascii strings:")
            for value in record["ascii_strings"][:limit]:
                print(f"    - {value}")


def print_delta(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    print(f"Binary files: {delta['binary_count'][0]} -> {delta['binary_count'][1]}")
    print_map_delta("Binaries", delta["binaries"], limit)


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
    parser.add_argument("path", type=Path, help="Outer export folder, inner zip, extracted folder, or direct binary file")
    parser.add_argument("after", nargs="?", type=Path, help="Optional after package/binary to compare with path")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON summary or delta to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--min-string", type=int, default=4)
    parser.add_argument("--string-limit", type=int, default=40)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")
    if args.after and not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    before = build_summary(args.path, min_string=args.min_string, string_limit=args.string_limit)
    result = build_delta(
        before,
        build_summary(args.after, min_string=args.min_string, string_limit=args.string_limit),
    ) if args.after else before

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
