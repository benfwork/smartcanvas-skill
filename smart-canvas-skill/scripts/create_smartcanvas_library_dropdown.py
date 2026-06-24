#!/usr/bin/env python3
"""Create a SmartCanvas image dropdown from exact existing library categories.

Use this when the stock dropdown helper's substring matching would select too
much, or when one dropdown should contain images from multiple catalog
categories.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load_base_helper():
    helper_path = Path(__file__).with_name("create_smartcanvas_image_dropdown.py")
    spec = importlib.util.spec_from_file_location("smartcanvas_dropdown", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smartcanvas = load_base_helper()


def collect_by_exact_categories(inner, image_prefix, categories):
    catalog = smartcanvas.read_info_catalog(inner)
    selected = {smartcanvas.normalized_lookup(category) for category in categories}
    image_members = {
        name.replace("\\", "/").rsplit("/", 1)[-1]: member
        for name, member in inner.items()
        if name.replace("\\", "/").startswith(image_prefix)
        and Path(name.replace("\\", "/").rsplit("/", 1)[-1]).suffix.lower() in smartcanvas.IMAGE_EXTS
        and not smartcanvas.SIDECAR_RE.search(name.replace("\\", "/").rsplit("/", 1)[-1])
        and not smartcanvas.THUMB_NAME_RE.search(name.replace("\\", "/").rsplit("/", 1)[-1])
    }
    sidecar_members = {
        name.replace("\\", "/").rsplit("/", 1)[-1]: member.data
        for name, member in inner.items()
        if name.replace("\\", "/").startswith(image_prefix)
        and smartcanvas.SIDECAR_RE.search(name.replace("\\", "/").rsplit("/", 1)[-1])
    }

    assets = []
    for filename, member in sorted(image_members.items()):
        category = smartcanvas.catalog_category_for(catalog, filename)
        if smartcanvas.normalized_lookup(category) not in selected:
            continue
        width, height = smartcanvas.get_image_size(member.data, filename)
        asset = smartcanvas.ImageAsset(
            source_path=image_prefix + filename,
            filename=filename,
            category=category,
            data=member.data,
            width=width,
            height=height,
            sidecars={},
        )
        prefix = smartcanvas.sidecar_prefix(filename)
        for suffix in ("info.xml", "thumbi.png", "thumbn.png"):
            sidecar_name = f"{prefix}_{suffix}"
            if sidecar_name in sidecar_members:
                asset.sidecars[sidecar_name] = sidecar_members[sidecar_name]
        assets.append(asset)
    if not assets:
        raise ValueError(f"no images matched exact categories: {', '.join(categories)}")
    return assets


def patch_dropdown(input_path, output_path, field_name, categories, left, top, width, height):
    outer, inner_name, inner = smartcanvas.read_package(Path(input_path))
    document_name = smartcanvas.find_inner_file(inner, "Document.xml")
    smartcampaign_name = next(
        (name for name in inner if name.replace("\\", "/").endswith("/smartcampaign.xml")),
        None,
    )
    prefix = smartcanvas.campaign_prefix(document_name)
    image_prefix = prefix + "images/"
    assets = collect_by_exact_categories(inner, image_prefix, categories)
    field_name = smartcanvas.safe_field_name(field_name)

    document_root = smartcanvas.parse_xml(inner[document_name].data)
    document = smartcanvas.editable_document(document_root)
    smartcanvas.ensure_form_dropdown(document, field_name, assets)
    smartcanvas.ensure_switches(document, field_name, assets)
    smartcanvas.ensure_layers_and_pictures(document, field_name, assets, left, top, width, height)

    replacements = {document_name: smartcanvas.xml_bytes(document_root)}
    smartcampaign_data = inner[smartcampaign_name].data if smartcampaign_name else None
    smartcampaign_output = smartcanvas.sync_smartcampaign(
        document,
        smartcampaign_data,
        sorted({asset.category for asset in assets if asset.category}),
    )
    additions = {}
    if smartcampaign_name:
        replacements[smartcampaign_name] = smartcampaign_output
    else:
        additions[prefix + "smartcampaign.xml"] = smartcampaign_output

    inner_bytes = smartcanvas.create_inner_zip(inner, replacements, additions)
    if inner_name:
        outer[inner_name].data = inner_bytes
        smartcanvas.write_zip(Path(output_path), outer)
    else:
        Path(output_path).write_bytes(inner_bytes)
    return len(assets)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a SmartCanvas image-list dropdown from exact existing catalog categories."
    )
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", help="Output ZIP path")
    parser.add_argument("--field-name", required=True, help="Form field/dropdown name")
    parser.add_argument(
        "--category",
        action="append",
        required=True,
        help="Exact catalog category to include; repeat to combine categories in one dropdown",
    )
    parser.add_argument("--left", type=float, required=True, help="Picture left/X coordinate")
    parser.add_argument("--top", type=float, required=True, help="Picture top/Y coordinate")
    parser.add_argument("--width", type=float, required=True, help="Picture width")
    parser.add_argument("--height", type=float, required=True, help="Picture height")
    parser.add_argument(
        "--units",
        choices=("points", "inches"),
        default="points",
        help="Coordinate units for left/top/width/height",
    )
    args = parser.parse_args(argv)
    scale = 72.0 if args.units == "inches" else 1.0
    requested_field_name = args.field_name
    safe_field_name = smartcanvas.safe_field_name(args.field_name)
    count = patch_dropdown(
        args.input,
        args.output,
        safe_field_name,
        args.category,
        args.left * scale,
        args.top * scale,
        args.width * scale,
        args.height * scale,
    )
    print(f"Wrote {args.output} with {count} images")
    if safe_field_name != requested_field_name:
        print(f"warning: field name sanitized from {requested_field_name!r} to {safe_field_name!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
