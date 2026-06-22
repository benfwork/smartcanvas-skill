#!/usr/bin/env python3
"""Infer candidate image option groups from a SmartCanvas catalog manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from export_smartcanvas_catalog import build_manifest, read_package


OPTION_RE = re.compile(r"(?:^|[_\s-])Option[_\s-]*(\d+)\b", re.IGNORECASE)
CATEGORY_COPY_RE = re.compile(r"[_\s-]+(?:Demo\s+Gallery|test)$", re.IGNORECASE)


def load_catalog(path: Path) -> dict[str, object]:
    if path.is_file() and path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    source_label, files = read_package(path)
    return build_manifest(source_label, files)


def clean_name(caption: str) -> str:
    return Path(caption).stem.replace("_", " ").strip()


def infer_image_parts(caption: str) -> dict[str, object]:
    stem = Path(caption).stem
    stem = CATEGORY_COPY_RE.sub("", stem)
    option_match = OPTION_RE.search(stem)
    option_number = int(option_match.group(1)) if option_match else None
    if option_match:
        base = (stem[: option_match.start()] + stem[option_match.end() :]).strip(" _-")
    else:
        base = stem
    return {
        "base_key": re.sub(r"[_\s]+", " ", base).strip(),
        "option_number": option_number,
        "option_label": f"Option {option_number}" if option_number is not None else "",
    }


def build_option_analysis(catalog: dict[str, object]) -> dict[str, object]:
    images = catalog.get("images", [])
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)

    for image in images:
        caption = str(image.get("caption", ""))
        parts = infer_image_parts(caption)
        group_key = str(parts["base_key"] or clean_name(caption))
        groups[group_key].append({**image, **parts})

    option_groups = []
    singles = []
    for group_key, group_images in sorted(groups.items()):
        option_numbers = sorted({image.get("option_number") for image in group_images if image.get("option_number") is not None})
        categories = Counter(str(image.get("category") or "[uncategorized]") for image in group_images)
        hashes = Counter(str(image.get("catalog_hash_sha1") or "") for image in group_images)
        dimensions = Counter(
            (
                (image.get("sidecar") or {}).get("image_width"),
                (image.get("sidecar") or {}).get("image_height"),
            )
            for image in group_images
        )
        unique_options = summarize_unique_options(group_images)
        entry = {
            "group_key": group_key,
            "image_count": len(group_images),
            "option_numbers": option_numbers,
            "categories": dict(sorted(categories.items())),
            "unique_hash_count": len([value for value in hashes if value]),
            "unique_options": unique_options,
            "dimensions": [{"width": key[0], "height": key[1], "count": count} for key, count in dimensions.items()],
            "images": [
                {
                    "caption": image.get("caption"),
                    "category": image.get("category") or "[uncategorized]",
                    "option_number": image.get("option_number"),
                    "option_label": image.get("option_label"),
                    "sha1": image.get("catalog_hash_sha1"),
                    "original_paths": image.get("original_paths"),
                    "thumbi_paths": image.get("thumbi_paths"),
                    "thumbn_paths": image.get("thumbn_paths"),
                    "scaled_asset_paths": image.get("scaled_asset_paths"),
                }
                for image in sorted(group_images, key=image_sort_key)
            ],
        }
        if len(group_images) > 1 or option_numbers:
            option_groups.append(entry)
        else:
            singles.append(entry)

    return {
        "source": catalog.get("source"),
        "image_count": len(images),
        "option_group_count": len(option_groups),
        "single_image_count": len(singles),
        "option_groups": option_groups,
        "single_images": singles,
    }


def summarize_unique_options(images: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: dict[tuple[object, str], list[dict[str, object]]] = defaultdict(list)
    for image in images:
        key = (image.get("option_number"), str(image.get("catalog_hash_sha1") or ""))
        buckets[key].append(image)

    options = []
    for (option_number, digest), bucket in sorted(buckets.items(), key=lambda item: unique_option_sort_key(item[0])):
        captions = sorted(str(image.get("caption") or "") for image in bucket)
        categories = sorted({str(image.get("category") or "[uncategorized]") for image in bucket})
        labels = [str(image.get("option_label") or "") for image in bucket if image.get("option_label")]
        options.append(
            {
                "option_number": option_number,
                "option_label": labels[0] if labels else "",
                "sha1": digest,
                "categories": categories,
                "captions": captions,
            }
        )
    return options


def unique_option_sort_key(key: tuple[object, str]) -> tuple[object, str]:
    option_number, digest = key
    return (option_number if option_number is not None else 10**9, digest)


def image_sort_key(image: dict[str, object]) -> tuple[object, str, str]:
    option_number = image.get("option_number")
    return (
        option_number if option_number is not None else 10**9,
        str(image.get("category") or ""),
        str(image.get("caption") or ""),
    )


def print_text_report(analysis: dict[str, object]) -> None:
    print(f"Source: {analysis.get('source')}")
    print(f"Images: {analysis['image_count']}")
    print(f"Candidate option groups: {analysis['option_group_count']}")
    print(f"Single images: {analysis['single_image_count']}")
    for group in analysis["option_groups"]:
        print("")
        print(f"{group['group_key']}")
        print(f"  images: {group['image_count']}")
        print(f"  options: {group['option_numbers']}")
        print(f"  categories: {group['categories']}")
        print(f"  unique hashes: {group['unique_hash_count']}")
        print(f"  dimensions: {group['dimensions']}")
        print("  unique options:")
        for option in group["unique_options"]:
            label = option["option_label"] or "no option label"
            print(f"    * {label} | {option['sha1']} | categories={option['categories']}")
        for image in group["images"]:
            option = image["option_label"] or "no option label"
            category = image["category"]
            print(f"    - {option} | {category} | {image['caption']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Catalog JSON, outer export folder, inner campaign zip, or extracted inner folder")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON analysis to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")

    analysis = build_option_analysis(load_catalog(args.path))
    if args.output:
        args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(analysis, indent=2, sort_keys=True))
    elif args.format == "text":
        print_text_report(analysis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
