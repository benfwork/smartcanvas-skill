#!/usr/bin/env python3
"""Create a before/after evidence bundle for SmartCanvas image-dropdown probes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analyze_smartcanvas_options import build_option_analysis
from compare_smartcanvas_dropdown_signals import build_delta as build_dropdown_delta
from compare_smartcanvas_dropdown_signals import load_signals as load_dropdown_signals
from compare_smartcanvas_info_bin_dumps import build_delta as build_info_delta
from dump_smartcanvas_info_bin import build_dump
from export_smartcanvas_catalog import build_manifest, read_package
from inspect_smartcanvas_binaries import build_delta as build_binary_delta
from inspect_smartcanvas_binaries import build_summary as build_binary_summary
from inspect_smartcanvas_controls import build_summary as build_control_summary
from inspect_smartcanvas_database import build_delta as build_database_delta
from inspect_smartcanvas_database import build_summary as build_database_summary
from inspect_smartcanvas_image_derivatives import build_delta as build_image_derivative_delta
from inspect_smartcanvas_image_derivatives import build_summary as build_image_derivative_summary
from inspect_smartcanvas_image_metadata import build_delta as build_image_metadata_delta
from inspect_smartcanvas_image_metadata import build_summary as build_image_metadata_summary
from inspect_smartcanvas_xml_inventory import build_delta as build_xml_inventory_delta
from inspect_smartcanvas_xml_inventory import build_summary as build_xml_inventory_summary
from make_smartcanvas_image_dropdown_blueprint import build_blueprint
from make_smartcanvas_image_dropdown_blueprint import write_blueprint_csv
from validate_smartcanvas_image_assets import build_delta as build_asset_readiness_delta
from validate_smartcanvas_image_assets import build_summary as build_asset_readiness_summary


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_info_dump(path: Path) -> dict[str, object]:
    args = argparse.Namespace(path=path, max_samples=5, max_inline_bytes=200, max_nested_bytes=100_000)
    return build_dump(args)


def build_single_side(path: Path) -> dict[str, object]:
    source_label, files = read_package(path)
    catalog = build_manifest(source_label, files)
    return {
        "catalog": catalog,
        "binaries": build_binary_summary(path),
        "asset_readiness": build_asset_readiness_summary(path),
        "image_derivatives": build_image_derivative_summary(path),
        "options": build_option_analysis(catalog),
        "blueprint": build_blueprint(catalog),
        "controls": build_control_summary(path),
        "database": build_database_summary(path),
        "image_metadata": build_image_metadata_summary(path),
        "xml_inventory": build_xml_inventory_summary(path),
        "info_bin_dump": build_info_dump(path),
    }


def ensure_output_dir(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()) and not force:
        raise SystemExit(f"output directory is not empty: {path}; pass --force")
    path.mkdir(parents=True, exist_ok=True)
    for side in ("before", "after"):
        (path / side).mkdir(exist_ok=True)


def summarize_bundle(
    before: dict[str, object],
    after: dict[str, object],
    dropdown_delta: dict[str, object],
    info_delta: dict[str, object],
    database_delta: dict[str, object],
    binary_delta: dict[str, object],
    asset_readiness_delta: dict[str, object],
    image_derivative_delta: dict[str, object],
    image_metadata_delta: dict[str, object],
    xml_inventory_delta: dict[str, object],
) -> str:
    before_catalog = before["catalog"]
    after_catalog = after["catalog"]
    before_options = before["options"]
    after_options = after["options"]
    controls = dropdown_delta["controls"]
    catalog = dropdown_delta["catalog"]
    database_alignment = database_delta["alignment"]
    lines = [
        "SmartCanvas Dropdown Probe Bundle",
        "",
        f"Before: {before_catalog.get('source')}",
        f"After:  {after_catalog.get('source')}",
        "",
        "Catalog",
        f"  images: {len(before_catalog.get('images', []))} -> {len(after_catalog.get('images', []))}",
        f"  image records added/removed/changed: {len(catalog['image_records']['added'])}/"
        f"{len(catalog['image_records']['removed'])}/{len(catalog['image_records']['changed'])}",
        f"  image category records added/removed: {len(catalog['image_category_records']['added'])}/"
        f"{len(catalog['image_category_records']['removed'])}",
        "",
        "Binaries",
        f"  binary files: {binary_delta['binary_count'][0]} -> {binary_delta['binary_count'][1]}",
        f"  binaries added/removed/changed: "
        f"{len(binary_delta['binaries']['added'])}/"
        f"{len(binary_delta['binaries']['removed'])}/"
        f"{len(binary_delta['binaries']['changed'])}",
        "",
        "Image Derivatives",
        f"  images: {image_derivative_delta['image_count'][0]} -> {image_derivative_delta['image_count'][1]}",
        f"  derivative records added/removed/changed: "
        f"{len(image_derivative_delta['records']['added'])}/"
        f"{len(image_derivative_delta['records']['removed'])}/"
        f"{len(image_derivative_delta['records']['changed'])}",
        "",
        "Asset Readiness",
        f"  ready: {asset_readiness_delta['ready_for_dropdown_probe'][0]} -> "
        f"{asset_readiness_delta['ready_for_dropdown_probe'][1]}",
        f"  errors: {asset_readiness_delta['error_count'][0]} -> {asset_readiness_delta['error_count'][1]}",
        f"  warnings: {asset_readiness_delta['warning_count'][0]} -> {asset_readiness_delta['warning_count'][1]}",
        f"  images added/removed/changed: "
        f"{len(asset_readiness_delta['images']['added'])}/"
        f"{len(asset_readiness_delta['images']['removed'])}/"
        f"{len(asset_readiness_delta['images']['changed'])}",
        "",
        "Options",
        f"  option groups: {before_options.get('option_group_count')} -> {after_options.get('option_group_count')}",
        f"  option groups added/removed/changed: {len(dropdown_delta['options']['option_groups']['added'])}/"
        f"{len(dropdown_delta['options']['option_groups']['removed'])}/{len(dropdown_delta['options']['option_groups']['changed'])}",
        "",
        "Controls",
        f"  catalog image XML refs added/removed: {len(controls['catalog_image_xml_references']['added'])}/"
        f"{len(controls['catalog_image_xml_references']['removed'])}",
        f"  DocModel changes: {len(controls['docmodels']['changed'])}",
        f"  template.xml interesting attr changes: {len(controls['template_xml_interesting_attributes']['changed'])}",
        f"  template.dhtt section changes: {len(controls['template_dhtt_sections']['changed'])}",
        f"  template.dhtt interesting attrs added/removed/changed: "
        f"{len(controls['template_dhtt_interesting_attributes']['added'])}/"
        f"{len(controls['template_dhtt_interesting_attributes']['removed'])}/"
        f"{len(controls['template_dhtt_interesting_attributes']['changed'])}",
        "",
        "Database/Bindings",
        f"  template columns: {database_alignment['template_column_count'][0]} -> "
        f"{database_alignment['template_column_count'][1]}",
        f"  info.bin columns: {database_alignment['info_bin_column_count'][0]} -> "
        f"{database_alignment['info_bin_column_count'][1]}",
        f"  XML binding attrs added/removed/changed: "
        f"{len(database_delta['xml_binding_attributes']['added'])}/"
        f"{len(database_delta['xml_binding_attributes']['removed'])}/"
        f"{len(database_delta['xml_binding_attributes']['changed'])}",
        f"  field refs added/removed/changed: "
        f"{len(database_delta['field_references']['added'])}/"
        f"{len(database_delta['field_references']['removed'])}/"
        f"{len(database_delta['field_references']['changed'])}",
        "",
        "Image Metadata",
        f"  embedded records: {image_metadata_delta['counts']['embedded_record_count'][0]} -> "
        f"{image_metadata_delta['counts']['embedded_record_count'][1]}",
        f"  embedded/sidecar exact matches: "
        f"{image_metadata_delta['counts']['embedded_sidecar_exact_match_count'][0]} -> "
        f"{image_metadata_delta['counts']['embedded_sidecar_exact_match_count'][1]}",
        f"  records added/removed/changed: "
        f"{len(image_metadata_delta['records']['added'])}/"
        f"{len(image_metadata_delta['records']['removed'])}/"
        f"{len(image_metadata_delta['records']['changed'])}",
        "",
        "XML Inventory",
        f"  schema paths added/removed/changed: "
        f"{len(xml_inventory_delta['schema_paths']['added'])}/"
        f"{len(xml_inventory_delta['schema_paths']['removed'])}/"
        f"{len(xml_inventory_delta['schema_paths']['changed'])}",
        f"  attribute names added/removed/changed: "
        f"{len(xml_inventory_delta['attribute_names']['added'])}/"
        f"{len(xml_inventory_delta['attribute_names']['removed'])}/"
        f"{len(xml_inventory_delta['attribute_names']['changed'])}",
        f"  exact elements added/removed/changed: "
        f"{len(xml_inventory_delta['exact_elements']['added'])}/"
        f"{len(xml_inventory_delta['exact_elements']['removed'])}/"
        f"{len(xml_inventory_delta['exact_elements']['changed'])}",
        "",
        "info.bin",
        f"  size: {info_delta['info_bin_size'][0]} -> {info_delta['info_bin_size'][1]}",
        f"  known summary changed: {len(info_delta['known_summary']['changed'])}",
        f"  top-level groups added/removed/changed: {len(info_delta['top_level']['added'])}/"
        f"{len(info_delta['top_level']['removed'])}/{len(info_delta['top_level']['changed'])}",
        f"  catalog groups added/removed/changed: {len(info_delta['catalog_field_1']['added'])}/"
        f"{len(info_delta['catalog_field_1']['removed'])}/{len(info_delta['catalog_field_1']['changed'])}",
        "",
        "Key files",
        "  before/catalog.json",
        "  before/binaries.json",
        "  before/asset-readiness.json",
        "  before/image-derivatives.json",
        "  before/options.json",
        "  before/dropdown-blueprint.json",
        "  before/dropdown-blueprint.csv",
        "  before/controls.json",
        "  before/database-bindings.json",
        "  before/image-metadata.json",
        "  before/xml-inventory.json",
        "  before/info-bin-dump.json",
        "  after/catalog.json",
        "  after/binaries.json",
        "  after/asset-readiness.json",
        "  after/image-derivatives.json",
        "  after/options.json",
        "  after/dropdown-blueprint.json",
        "  after/dropdown-blueprint.csv",
        "  after/controls.json",
        "  after/database-bindings.json",
        "  after/image-metadata.json",
        "  after/xml-inventory.json",
        "  after/info-bin-dump.json",
        "  binaries-delta.json",
        "  asset-readiness-delta.json",
        "  image-derivatives-delta.json",
        "  dropdown-signals-delta.json",
        "  database-bindings-delta.json",
        "  image-metadata-delta.json",
        "  xml-inventory-delta.json",
        "  info-bin-delta.json",
    ]
    return "\n".join(lines) + "\n"


def build_bundle(before_path: Path, after_path: Path, output_dir: Path, force: bool) -> dict[str, object]:
    ensure_output_dir(output_dir, force)
    before = build_single_side(before_path)
    after = build_single_side(after_path)
    dropdown_delta = build_dropdown_delta(load_dropdown_signals(before_path), load_dropdown_signals(after_path))
    binary_delta = build_binary_delta(before["binaries"], after["binaries"])
    asset_readiness_delta = build_asset_readiness_delta(before["asset_readiness"], after["asset_readiness"])
    image_derivative_delta = build_image_derivative_delta(before["image_derivatives"], after["image_derivatives"])
    info_delta = build_info_delta(before["info_bin_dump"], after["info_bin_dump"])
    database_delta = build_database_delta(before["database"], after["database"])
    image_metadata_delta = build_image_metadata_delta(before["image_metadata"], after["image_metadata"])
    xml_inventory_delta = build_xml_inventory_delta(before["xml_inventory"], after["xml_inventory"])

    for side_name, side in (("before", before), ("after", after)):
        side_dir = output_dir / side_name
        write_json(side_dir / "catalog.json", side["catalog"])
        write_json(side_dir / "binaries.json", side["binaries"])
        write_json(side_dir / "asset-readiness.json", side["asset_readiness"])
        write_json(side_dir / "image-derivatives.json", side["image_derivatives"])
        write_json(side_dir / "options.json", side["options"])
        write_json(side_dir / "dropdown-blueprint.json", side["blueprint"])
        write_blueprint_csv(side_dir / "dropdown-blueprint.csv", side["blueprint"])
        write_json(side_dir / "controls.json", side["controls"])
        write_json(side_dir / "database-bindings.json", side["database"])
        write_json(side_dir / "image-metadata.json", side["image_metadata"])
        write_json(side_dir / "xml-inventory.json", side["xml_inventory"])
        write_json(side_dir / "info-bin-dump.json", side["info_bin_dump"])

    write_json(output_dir / "binaries-delta.json", binary_delta)
    write_json(output_dir / "asset-readiness-delta.json", asset_readiness_delta)
    write_json(output_dir / "image-derivatives-delta.json", image_derivative_delta)
    write_json(output_dir / "dropdown-signals-delta.json", dropdown_delta)
    write_json(output_dir / "database-bindings-delta.json", database_delta)
    write_json(output_dir / "image-metadata-delta.json", image_metadata_delta)
    write_json(output_dir / "xml-inventory-delta.json", xml_inventory_delta)
    write_json(output_dir / "info-bin-delta.json", info_delta)
    summary = summarize_bundle(
        before,
        after,
        dropdown_delta,
        info_delta,
        database_delta,
        binary_delta,
        asset_readiness_delta,
        image_derivative_delta,
        image_metadata_delta,
        xml_inventory_delta,
    )
    (output_dir / "summary.txt").write_text(summary, encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "summary": summary,
        "dropdown_delta": dropdown_delta,
        "binary_delta": binary_delta,
        "asset_readiness_delta": asset_readiness_delta,
        "image_derivative_delta": image_derivative_delta,
        "database_delta": database_delta,
        "image_metadata_delta": image_metadata_delta,
        "xml_inventory_delta": xml_inventory_delta,
        "info_delta": info_delta,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="Before outer folder, inner zip, or extracted inner folder")
    parser.add_argument("after", type=Path, help="After outer folder, inner zip, or extracted inner folder")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.before.exists():
        parser.error(f"before path does not exist: {args.before}")
    if not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    result = build_bundle(args.before, args.after, args.output_dir, args.force)
    if args.format == "json":
        print(json.dumps({"output_dir": result["output_dir"]}, indent=2, sort_keys=True))
    else:
        print(result["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
