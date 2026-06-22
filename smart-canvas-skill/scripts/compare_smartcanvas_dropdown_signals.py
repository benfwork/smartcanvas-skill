#!/usr/bin/env python3
"""Compare SmartCanvas exports for image-dropdown reverse-engineering signals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analyze_smartcanvas_options import build_option_analysis
from export_smartcanvas_catalog import build_manifest, read_package
from inspect_smartcanvas_controls import build_summary as build_control_summary


def load_signals(path: Path) -> dict[str, object]:
    source_label, files = read_package(path)
    catalog = build_manifest(source_label, files)
    return {
        "source": source_label,
        "catalog": catalog,
        "options": build_option_analysis(catalog),
        "controls": build_control_summary(path),
    }


def image_key(image: dict[str, object]) -> tuple[object, ...]:
    sidecar = image.get("sidecar") or {}
    return (
        image.get("category") or "",
        image.get("catalog_hash_sha1") or "",
        image.get("declared_size"),
        image.get("actual_size"),
        sidecar.get("image_width"),
        sidecar.get("image_height"),
        tuple(image.get("original_paths") or []),
        tuple(image.get("thumbi_paths") or []),
        tuple(image.get("thumbn_paths") or []),
        tuple(image.get("scaled_asset_paths") or []),
    )


def option_group_key(group: dict[str, object]) -> tuple[object, ...]:
    unique_options = []
    for option in group.get("unique_options", []):
        unique_options.append(
            (
                option.get("option_number"),
                option.get("option_label"),
                option.get("sha1"),
                tuple(option.get("categories") or []),
                tuple(option.get("captions") or []),
            )
        )
    return (
        group.get("image_count"),
        tuple(group.get("option_numbers") or []),
        tuple(sorted((group.get("categories") or {}).items())),
        tuple(sorted((item.get("width"), item.get("height"), item.get("count")) for item in group.get("dimensions", []))),
        tuple(unique_options),
    )


def docmodel_rows(controls: dict[str, object]) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    template = controls.get("template_xml") or {}
    for doc in template.get("docs", []):
        doc_name = doc.get("name") or doc.get("id") or "[unnamed-doc]"
        for index, model in enumerate(doc.get("doc_models", []), start=1):
            rows[f"{doc_name}#{index}"] = model
    return rows


def dhtt_section_rows(controls: dict[str, object]) -> dict[str, dict[str, object]]:
    dhtt = controls.get("template_dhtt") or {}
    return dhtt.get("sections", {}) or {}


def interesting_attribute_rows(controls: dict[str, object], section_name: str) -> dict[str, dict[str, object]]:
    section = controls.get(section_name) or {}
    rows = {}
    for item in section.get("interesting_attributes", []):
        key = f"{item.get('path', '')}|{item.get('tag', '')}"
        rows[key] = item.get("attributes", {})
    return rows


def css_classes(controls: dict[str, object]) -> set[str]:
    css = controls.get("css") or {}
    return set(css.get("dynamic_classes") or [])


def set_delta(before: set[object], after: set[object]) -> dict[str, list[object]]:
    return {
        "added": sorted(after - before),
        "removed": sorted(before - after),
    }


def map_delta(before: dict[object, object], after: dict[object, object]) -> dict[str, object]:
    before_keys = set(before)
    after_keys = set(after)
    common = sorted(before_keys & after_keys)
    changed = []
    for key in common:
        if before[key] != after[key]:
            changed.append({"key": key, "before": before[key], "after": after[key]})
    return {
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "changed": changed,
    }


def build_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_catalog = before["catalog"]
    after_catalog = after["catalog"]
    before_images = {image["caption"]: image_key(image) for image in before_catalog.get("images", [])}
    after_images = {image["caption"]: image_key(image) for image in after_catalog.get("images", [])}
    before_categories = {
        (image.get("caption"), image.get("category") or "[uncategorized]") for image in before_catalog.get("images", [])
    }
    after_categories = {
        (image.get("caption"), image.get("category") or "[uncategorized]") for image in after_catalog.get("images", [])
    }

    before_groups = {group["group_key"]: option_group_key(group) for group in before["options"].get("option_groups", [])}
    after_groups = {group["group_key"]: option_group_key(group) for group in after["options"].get("option_groups", [])}

    before_controls = before["controls"]
    after_controls = after["controls"]
    before_refs = {
        (caption, path)
        for caption, paths in (before_controls.get("catalog_image_xml_references") or {}).items()
        for path in paths
    }
    after_refs = {
        (caption, path)
        for caption, paths in (after_controls.get("catalog_image_xml_references") or {}).items()
        for path in paths
    }

    return {
        "before": before["source"],
        "after": after["source"],
        "catalog": {
            "image_count": [len(before_catalog.get("images", [])), len(after_catalog.get("images", []))],
            "image_records": map_delta(before_images, after_images),
            "image_category_records": set_delta(before_categories, after_categories),
            "sidecar_filesize_matches_actual": [
                before_catalog.get("sidecar_filesize_matches_actual"),
                after_catalog.get("sidecar_filesize_matches_actual"),
            ],
            "sidecar_filesize_mismatches_actual": [
                before_catalog.get("sidecar_filesize_mismatches_actual"),
                after_catalog.get("sidecar_filesize_mismatches_actual"),
            ],
        },
        "options": {
            "option_group_count": [
                before["options"].get("option_group_count"),
                after["options"].get("option_group_count"),
            ],
            "option_groups": map_delta(before_groups, after_groups),
        },
        "controls": {
            "catalog_image_xml_references": set_delta(before_refs, after_refs),
            "docmodels": map_delta(docmodel_rows(before_controls), docmodel_rows(after_controls)),
            "template_xml_interesting_attributes": map_delta(
                interesting_attribute_rows(before_controls, "template_xml"),
                interesting_attribute_rows(after_controls, "template_xml"),
            ),
            "template_dhtt_sections": map_delta(dhtt_section_rows(before_controls), dhtt_section_rows(after_controls)),
            "template_dhtt_interesting_attributes": map_delta(
                interesting_attribute_rows(before_controls, "template_dhtt"),
                interesting_attribute_rows(after_controls, "template_dhtt"),
            ),
            "document_xml_interesting_attributes": map_delta(
                interesting_attribute_rows(before_controls, "document_xml"),
                interesting_attribute_rows(after_controls, "document_xml"),
            ),
            "css_dynamic_classes": set_delta(css_classes(before_controls), css_classes(after_controls)),
        },
    }


def print_items(prefix: str, items: list[object], limit: int) -> None:
    for item in items[:limit]:
        print(f"  {prefix} {item}")
    if len(items) > limit:
        print(f"  ... {len(items) - limit} more")


def print_map_delta(title: str, delta: dict[str, object], limit: int) -> None:
    print(f"\n{title}")
    added = delta["added"]
    removed = delta["removed"]
    changed = delta["changed"]
    print(f"  added: {len(added)}")
    print_items("+", added, limit)
    print(f"  removed: {len(removed)}")
    print_items("-", removed, limit)
    print(f"  changed: {len(changed)}")
    for entry in changed[:limit]:
        print(f"  * {entry['key']}")
        print(f"    before: {entry['before']}")
        print(f"    after:  {entry['after']}")
    if len(changed) > limit:
        print(f"  ... {len(changed) - limit} more changed")


def print_set_delta_report(title: str, delta: dict[str, list[object]], limit: int) -> None:
    print(f"\n{title}")
    print(f"  added: {len(delta['added'])}")
    print_items("+", delta["added"], limit)
    print(f"  removed: {len(delta['removed'])}")
    print_items("-", delta["removed"], limit)


def print_text_report(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")

    catalog = delta["catalog"]
    print("\nCatalog Summary")
    print(f"  image count: {catalog['image_count'][0]} -> {catalog['image_count'][1]}")
    print(
        "  sidecar filesize matches actual: "
        f"{catalog['sidecar_filesize_matches_actual'][0]} -> {catalog['sidecar_filesize_matches_actual'][1]}"
    )
    print(
        "  sidecar filesize mismatches actual: "
        f"{catalog['sidecar_filesize_mismatches_actual'][0]} -> {catalog['sidecar_filesize_mismatches_actual'][1]}"
    )
    print_map_delta("Image Records", catalog["image_records"], limit)
    print_set_delta_report("Image Category Records", catalog["image_category_records"], limit)

    options = delta["options"]
    print("\nOption Summary")
    print(f"  option groups: {options['option_group_count'][0]} -> {options['option_group_count'][1]}")
    print_map_delta("Option Groups", options["option_groups"], limit)

    controls = delta["controls"]
    print_set_delta_report("Catalog Image References In Key XML", controls["catalog_image_xml_references"], limit)
    print_map_delta("DocModel Image/Control Attributes", controls["docmodels"], limit)
    print_map_delta("template.xml Interesting Attributes", controls["template_xml_interesting_attributes"], limit)
    print_map_delta("template.dhtt Sections", controls["template_dhtt_sections"], limit)
    print_map_delta("template.dhtt Interesting Attributes", controls["template_dhtt_interesting_attributes"], limit)
    print_map_delta("Document.xml Interesting Attributes", controls["document_xml_interesting_attributes"], limit)
    print_set_delta_report("CSS Dynamic Classes", controls["css_dynamic_classes"], limit)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Write JSON delta to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args(argv)

    if not args.before.exists():
        parser.error(f"before path does not exist: {args.before}")
    if not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    delta = build_delta(load_signals(args.before), load_signals(args.after))
    if args.output:
        args.output.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(delta, indent=2, sort_keys=True))
    elif args.format == "text":
        print_text_report(delta, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
