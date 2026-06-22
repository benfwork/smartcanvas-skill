#!/usr/bin/env python3
"""Create an image-dropdown planning blueprint from a SmartCanvas catalog."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from analyze_smartcanvas_options import build_option_analysis, load_catalog


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value or "ImageDropdown"


def first_nonempty(values: list[object]) -> object:
    for value in values:
        if value not in ("", None, [], {}):
            return value
    return ""


def build_option(option: dict[str, object], images_by_caption: dict[str, dict[str, object]]) -> dict[str, object]:
    captions = [str(caption) for caption in option.get("captions", [])]
    images = [images_by_caption[caption] for caption in captions if caption in images_by_caption]
    categories = sorted({str(image.get("category") or "[uncategorized]") for image in images})
    representative = images[0] if images else {}
    sidecar = representative.get("sidecar") or {}
    verification = representative.get("verification") or {}
    warnings = []
    if len(captions) > 1:
        warnings.append("multiple captions share this option/hash; likely category/gallery copies")
    if "[uncategorized]" in categories:
        warnings.append("one or more copies are uncategorized in info.bin")
    if verification and not verification.get("file_found"):
        warnings.append("representative file missing")
    if verification and not verification.get("sha1_match"):
        warnings.append("representative SHA-1 does not match info.bin")
    if representative.get("sidecar_filesize_matches_actual") is False:
        warnings.append("sidecar Filesize differs from archived file size, as observed in demo")

    return {
        "option_number": option.get("option_number"),
        "label": option.get("option_label") or f"Option {option.get('option_number')}",
        "representative_caption": representative.get("caption") or first_nonempty(captions),
        "all_captions": captions,
        "categories": categories,
        "sha1": option.get("sha1"),
        "width": sidecar.get("image_width"),
        "height": sidecar.get("image_height"),
        "bitmap_type": sidecar.get("bitmap_type"),
        "original_paths": representative.get("original_paths") or [],
        "thumbi_paths": representative.get("thumbi_paths") or [],
        "thumbn_paths": representative.get("thumbn_paths") or [],
        "scaled_asset_paths": representative.get("scaled_asset_paths") or [],
        "warnings": warnings,
    }


def build_blueprint(catalog: dict[str, object], group_filter: str | None = None) -> dict[str, object]:
    analysis = build_option_analysis(catalog)
    images_by_caption = {str(image.get("caption")): image for image in catalog.get("images", [])}
    groups = []
    for group in analysis.get("option_groups", []):
        group_key = str(group.get("group_key"))
        if group_filter and group_filter.lower() not in group_key.lower():
            continue
        options = [build_option(option, images_by_caption) for option in group.get("unique_options", [])]
        categories = Counter()
        warnings = []
        for option in options:
            categories.update(option["categories"])
            warnings.extend(option["warnings"])
        dimensions = {(option.get("width"), option.get("height")) for option in options}
        if len(dimensions) > 1:
            warnings.append("options have mixed dimensions")
        if len(options) != len(group.get("option_numbers") or []):
            warnings.append("unique option count differs from parsed option number count")
        groups.append(
            {
                "group_key": group_key,
                "suggested_control_name": slugify(group_key),
                "suggested_database_field": slugify(f"{group_key}_Choice"),
                "image_count": group.get("image_count"),
                "unique_option_count": len(options),
                "option_numbers": group.get("option_numbers"),
                "categories": dict(sorted(categories.items())),
                "dimensions": group.get("dimensions"),
                "options": options,
                "warnings": sorted(set(warnings)),
            }
        )

    return {
        "source": catalog.get("source"),
        "image_count": len(catalog.get("images", [])),
        "candidate_dropdown_count": len(groups),
        "groups": groups,
        "notes": [
            "This is a planning blueprint, not a proven SmartCanvas dropdown writer.",
            "A real before/after export is still required to confirm the control XML schema.",
            "Use representative_caption as the likely image value to test first; category copies may map to gallery organization instead of distinct dropdown options.",
        ],
    }


def print_text_report(blueprint: dict[str, object]) -> None:
    print(f"Source: {blueprint['source']}")
    print(f"Images: {blueprint['image_count']}")
    print(f"Candidate dropdowns: {blueprint['candidate_dropdown_count']}")
    for group in blueprint["groups"]:
        print("")
        print(group["group_key"])
        print(f"  suggested_control_name: {group['suggested_control_name']}")
        print(f"  suggested_database_field: {group['suggested_database_field']}")
        print(f"  unique options: {group['unique_option_count']}")
        print(f"  categories: {group['categories']}")
        if group["warnings"]:
            print(f"  warnings: {group['warnings']}")
        for option in group["options"]:
            print(
                f"    - {option['label']}: {option['representative_caption']} "
                f"{option['width']}x{option['height']} categories={option['categories']}"
            )


def blueprint_csv_rows(blueprint: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for group in blueprint["groups"]:
        for option in group["options"]:
            rows.append(
                {
                    "group_key": group["group_key"],
                    "suggested_control_name": group["suggested_control_name"],
                    "suggested_database_field": group["suggested_database_field"],
                    "option_number": option["option_number"],
                    "option_label": option["label"],
                    "representative_caption": option["representative_caption"],
                    "all_captions": " | ".join(option["all_captions"]),
                    "categories": " | ".join(option["categories"]),
                    "sha1": option["sha1"],
                    "width": option["width"],
                    "height": option["height"],
                    "bitmap_type": option["bitmap_type"],
                    "original_paths": " | ".join(option["original_paths"]),
                    "thumbi_paths": " | ".join(option["thumbi_paths"]),
                    "thumbn_paths": " | ".join(option["thumbn_paths"]),
                    "scaled_asset_paths": " | ".join(option["scaled_asset_paths"]),
                    "warnings": " | ".join(option["warnings"]),
                }
            )
    return rows


def write_blueprint_csv(path: Path, blueprint: dict[str, object]) -> None:
    rows = blueprint_csv_rows(blueprint)
    fieldnames = [
        "group_key",
        "suggested_control_name",
        "suggested_database_field",
        "option_number",
        "option_label",
        "representative_caption",
        "all_captions",
        "categories",
        "sha1",
        "width",
        "height",
        "bitmap_type",
        "original_paths",
        "thumbi_paths",
        "thumbn_paths",
        "scaled_asset_paths",
        "warnings",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Catalog JSON, outer export folder, inner campaign zip, or extracted inner folder")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON blueprint to this file")
    parser.add_argument("--csv-output", type=Path, help="Write a flat option table CSV to this file")
    parser.add_argument("--group", help="Only include option groups whose name contains this text")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")

    blueprint = build_blueprint(load_catalog(args.path), args.group)
    if args.output:
        args.output.write_text(json.dumps(blueprint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.csv_output:
        write_blueprint_csv(args.csv_output, blueprint)
    if args.format == "json" and not args.output:
        print(json.dumps(blueprint, indent=2, sort_keys=True))
    elif args.format == "text":
        print_text_report(blueprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
