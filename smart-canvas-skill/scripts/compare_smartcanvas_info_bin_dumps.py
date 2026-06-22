#!/usr/bin/env python3
"""Compare SmartCanvas info.bin wire-dump summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dump_smartcanvas_info_bin import build_dump


def load_dump(path: Path, args: argparse.Namespace) -> dict[str, object]:
    if path.is_file() and path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    dump_args = argparse.Namespace(
        path=path,
        max_samples=args.max_samples,
        max_inline_bytes=args.max_inline_bytes,
        max_nested_bytes=args.max_nested_bytes,
    )
    return build_dump(dump_args)


def comparable_group(group: dict[str, object]) -> dict[str, object]:
    return {
        "field": group.get("field"),
        "wire_type": group.get("wire_type"),
        "count": group.get("count"),
        "varint_samples": group.get("varint_samples") or [],
        "varint_min": group.get("varint_min"),
        "varint_max": group.get("varint_max"),
        "length_samples": group.get("length_samples") or [],
        "length_total": group.get("length_total"),
        "text_samples": group.get("text_samples") or [],
        "hex_samples": group.get("hex_samples") or [],
        "nested_field_counts": group.get("nested_field_counts") or [],
        "nested_parse_errors": group.get("nested_parse_errors") or [],
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


def field_group_delta(before_section: dict[str, object], after_section: dict[str, object]) -> dict[str, object]:
    before_groups = {
        key: comparable_group(value)
        for key, value in (before_section.get("field_groups") or {}).items()
    }
    after_groups = {
        key: comparable_group(value)
        for key, value in (after_section.get("field_groups") or {}).items()
    }
    return map_delta(before_groups, after_groups)


def known_summary_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_known = dict(before.get("known_summary") or {})
    after_known = dict(after.get("known_summary") or {})
    before_known.pop("top_fields", None)
    after_known.pop("top_fields", None)
    return map_delta(before_known, after_known)


def build_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    return {
        "before": before.get("source"),
        "after": after.get("source"),
        "info_bin_size": [before.get("info_bin_size"), after.get("info_bin_size")],
        "known_summary": known_summary_delta(before, after),
        "top_level": field_group_delta(before.get("top_level") or {}, after.get("top_level") or {}),
        "catalog_field_1": field_group_delta(before.get("catalog_field_1") or {}, after.get("catalog_field_1") or {}),
    }


def print_items(prefix: str, items: list[object], limit: int) -> None:
    for item in items[:limit]:
        print(f"  {prefix} {item}")
    if len(items) > limit:
        print(f"  ... {len(items) - limit} more")


def print_map_delta(title: str, delta: dict[str, object], limit: int) -> None:
    print("")
    print(title)
    print(f"  added: {len(delta['added'])}")
    print_items("+", delta["added"], limit)
    print(f"  removed: {len(delta['removed'])}")
    print_items("-", delta["removed"], limit)
    print(f"  changed: {len(delta['changed'])}")
    for entry in delta["changed"][:limit]:
        print(f"  * {entry['key']}")
        print(f"    before: {entry['before']}")
        print(f"    after:  {entry['after']}")
    if len(delta["changed"]) > limit:
        print(f"  ... {len(delta['changed']) - limit} more changed")


def print_text_report(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    print(f"info.bin size: {delta['info_bin_size'][0]} -> {delta['info_bin_size'][1]}")
    print_map_delta("Known Summary", delta["known_summary"], limit)
    print_map_delta("Top-Level Field Groups", delta["top_level"], limit)
    print_map_delta("Catalog Field 1 Groups", delta["catalog_field_1"], limit)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="Dump JSON, info.bin, outer folder, inner zip, or extracted inner folder")
    parser.add_argument("after", type=Path, help="Dump JSON, info.bin, outer folder, inner zip, or extracted inner folder")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON delta to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--max-samples", type=int, default=5)
    parser.add_argument("--max-inline-bytes", type=int, default=200)
    parser.add_argument("--max-nested-bytes", type=int, default=100_000)
    args = parser.parse_args(argv)

    if not args.before.exists():
        parser.error(f"before path does not exist: {args.before}")
    if not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    delta = build_delta(load_dump(args.before, args), load_dump(args.after, args))
    if args.output:
        args.output.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(delta, indent=2, sort_keys=True))
    elif args.format == "text":
        print_text_report(delta, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
