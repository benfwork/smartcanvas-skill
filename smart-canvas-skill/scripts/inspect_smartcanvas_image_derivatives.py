#!/usr/bin/env python3
"""Inspect SmartCanvas image originals, sidecars, thumbnails, and scaled derivatives."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from export_smartcanvas_catalog import build_manifest, read_package


JPEG_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def image_dimensions(data: bytes, filename: str) -> dict[str, object]:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".png":
            width, height = read_png_dimensions(data)
            return {"width": width, "height": height, "format": "png", "parse_error": ""}
        if suffix in (".jpg", ".jpeg"):
            width, height = read_jpeg_dimensions(data)
            return {"width": width, "height": height, "format": "jpeg", "parse_error": ""}
    except ValueError as exc:
        return {"width": None, "height": None, "format": suffix.lstrip("."), "parse_error": str(exc)}
    return {"width": None, "height": None, "format": suffix.lstrip("."), "parse_error": "unsupported image format"}


def read_png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a readable PNG")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def read_jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("not a readable JPEG")
    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index : index + 2], "big")
        if length < 2:
            break
        if marker in JPEG_SOF_MARKERS:
            if index + 7 > len(data):
                break
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += length
    raise ValueError("could not find JPEG dimensions")


def asset_record(path: str, data: bytes) -> dict[str, object]:
    dimensions = image_dimensions(data, path)
    width = dimensions.get("width")
    height = dimensions.get("height")
    return {
        "path": path,
        "bytes": len(data),
        "sha1": sha1(data),
        "width": width,
        "height": height,
        "max_dimension": max(width, height) if isinstance(width, int) and isinstance(height, int) else None,
        "format": dimensions.get("format"),
        "parse_error": dimensions.get("parse_error", ""),
    }


def records_by_paths(files: dict[str, bytes], paths: list[str]) -> list[dict[str, object]]:
    records = []
    for path in sorted(paths):
        data = files.get(path)
        if data is None:
            records.append({"path": path, "missing": True})
        else:
            records.append(asset_record(path, data))
    return records


def build_summary(path: Path) -> dict[str, object]:
    source_label, files = read_package(path)
    catalog = build_manifest(source_label, files)

    records = []
    for image in catalog.get("images", []):
        sidecar = image.get("sidecar") or {}
        originals = records_by_paths(files, image.get("original_paths") or [])
        thumbi = records_by_paths(files, image.get("thumbi_paths") or [])
        thumbn = records_by_paths(files, image.get("thumbn_paths") or [])
        scaled = records_by_paths(files, image.get("scaled_asset_paths") or [])
        original = originals[0] if originals else {}
        sidecar_width = sidecar.get("image_width")
        sidecar_height = sidecar.get("image_height")
        original_width = original.get("width")
        original_height = original.get("height")
        sidecar_filesize = sidecar.get("filesize")
        actual_size = image.get("actual_size")
        records.append(
            {
                "caption": image.get("caption"),
                "category": image.get("category") or "",
                "catalog_hash_sha1": image.get("catalog_hash_sha1") or "",
                "declared_size": image.get("declared_size"),
                "actual_size": actual_size,
                "sidecar_filesize": sidecar_filesize,
                "sidecar_filesize_minus_actual": (
                    sidecar_filesize - actual_size if isinstance(sidecar_filesize, int) and isinstance(actual_size, int) else None
                ),
                "sidecar_scalings": sidecar.get("scalings", ""),
                "originals": originals,
                "thumbi": thumbi,
                "thumbn": thumbn,
                "scaled": scaled,
                "original_dimensions_match_sidecar": original_width == sidecar_width and original_height == sidecar_height,
                "thumbi_max_dimensions": sorted({item.get("max_dimension") for item in thumbi if item.get("max_dimension")}),
                "thumbn_max_dimensions": sorted({item.get("max_dimension") for item in thumbn if item.get("max_dimension")}),
                "scaled_dimensions": sorted(
                    {
                        (item.get("width"), item.get("height"))
                        for item in scaled
                        if item.get("width") and item.get("height")
                    }
                ),
            }
        )

    summary_counts = summarize_records(records)
    return {
        "source": source_label,
        "image_count": len(records),
        "counts": summary_counts,
        "records": records,
    }


def summarize_records(records: list[dict[str, object]]) -> dict[str, object]:
    sidecar_minus_actual = [record["sidecar_filesize_minus_actual"] for record in records if isinstance(record.get("sidecar_filesize_minus_actual"), int)]
    thumbi_max = Counter(
        value
        for record in records
        for value in record.get("thumbi_max_dimensions", [])
    )
    thumbn_max = Counter(
        value
        for record in records
        for value in record.get("thumbn_max_dimensions", [])
    )
    scaled_dimensions = Counter(
        tuple(value)
        for record in records
        for value in record.get("scaled_dimensions", [])
    )
    return {
        "images_with_originals": sum(1 for record in records if record.get("originals")),
        "images_with_thumbi": sum(1 for record in records if record.get("thumbi")),
        "images_with_thumbn": sum(1 for record in records if record.get("thumbn")),
        "images_with_scaled_assets": sum(1 for record in records if record.get("scaled")),
        "original_dimensions_match_sidecar": sum(1 for record in records if record.get("original_dimensions_match_sidecar")),
        "sidecar_filesize_minus_actual_min": min(sidecar_minus_actual) if sidecar_minus_actual else None,
        "sidecar_filesize_minus_actual_max": max(sidecar_minus_actual) if sidecar_minus_actual else None,
        "sidecar_filesize_minus_actual_values": sorted(set(sidecar_minus_actual)),
        "thumbi_max_dimension_counts": {str(key): value for key, value in sorted(thumbi_max.items())},
        "thumbn_max_dimension_counts": {str(key): value for key, value in sorted(thumbn_max.items())},
        "scaled_dimension_counts": {f"{key[0]}x{key[1]}": value for key, value in sorted(scaled_dimensions.items())},
    }


def record_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for record in summary.get("records", []):
        rows[str(record.get("caption", ""))] = {
            "category": record.get("category"),
            "declared_size": record.get("declared_size"),
            "actual_size": record.get("actual_size"),
            "sidecar_filesize": record.get("sidecar_filesize"),
            "sidecar_filesize_minus_actual": record.get("sidecar_filesize_minus_actual"),
            "sidecar_scalings": record.get("sidecar_scalings"),
            "originals": compact_assets(record.get("originals", [])),
            "thumbi": compact_assets(record.get("thumbi", [])),
            "thumbn": compact_assets(record.get("thumbn", [])),
            "scaled": compact_assets(record.get("scaled", [])),
            "original_dimensions_match_sidecar": record.get("original_dimensions_match_sidecar"),
        }
    return rows


def compact_assets(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "path": item.get("path"),
            "bytes": item.get("bytes"),
            "width": item.get("width"),
            "height": item.get("height"),
            "max_dimension": item.get("max_dimension"),
            "sha1": item.get("sha1"),
            "parse_error": item.get("parse_error"),
            "missing": item.get("missing", False),
        }
        for item in items
    ]


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
        "image_count": [before["image_count"], after["image_count"]],
        "counts": map_delta(before.get("counts", {}), after.get("counts", {})),
        "records": map_delta(record_rows(before), record_rows(after)),
    }


def print_summary(summary: dict[str, object], limit: int) -> None:
    print(f"Source: {summary['source']}")
    print(f"Images: {summary['image_count']}")
    print("Counts")
    for key, value in summary["counts"].items():
        print(f"  {key}: {value}")
    print("\nRecords")
    for record in summary["records"][:limit]:
        print(
            f"  - {record['caption']}: original={len(record['originals'])}, "
            f"thumbi={len(record['thumbi'])}, thumbn={len(record['thumbn'])}, "
            f"scaled={len(record['scaled'])}, scaling={record['sidecar_scalings']!r}"
        )


def print_delta(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    print(f"Images: {delta['image_count'][0]} -> {delta['image_count'][1]}")
    print_map_delta("Counts", delta["counts"], limit)
    print_map_delta("Image Derivative Records", delta["records"], limit)


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
    parser.add_argument("path", type=Path, help="Outer export folder, inner zip, or extracted inner folder")
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
