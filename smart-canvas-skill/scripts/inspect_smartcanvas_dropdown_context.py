#!/usr/bin/env python3
"""Inspect SmartCanvas picture placement and image catalog categories."""

from __future__ import annotations

import argparse
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def read_package(path):
    with zipfile.ZipFile(path) as outer_zip:
        outer = {info.filename: outer_zip.read(info) for info in outer_zip.infolist()}
    inner_name = next(
        (
            name
            for name in outer
            if name.replace("\\", "/").lower().startswith("admin/")
            and name.lower().endswith(".zip")
        ),
        None,
    )
    inner_data = outer[inner_name] if inner_name else Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(inner_data)) as inner_zip:
        inner = {info.filename: inner_zip.read(info) for info in inner_zip.infolist()}
    return inner


def local_name(elem):
    return elem.tag.rsplit("}", 1)[-1]


def read_info_catalog(inner):
    catalog = {}
    blob = b"\n".join(
        data
        for name, data in inner.items()
        if name.replace("\\", "/").endswith("/info.bin") or name == "info.bin"
    )
    image = rb"([A-Za-z0-9_ .,'()&+\-\[\]/]+\.?(?:jpg|jpeg|png))"
    category = rb"\x12([\x01-\x60])([A-Za-z0-9_ .,'()&+\-/]+)"
    for match in re.finditer(image + category, blob, re.I):
        filename = match.group(1).decode("utf-8", errors="ignore").strip()
        length = match.group(2)[0]
        category_name = match.group(3)[:length].decode("utf-8", errors="ignore").strip()
        if filename and category_name:
            catalog[filename.rsplit("/", 1)[-1]] = category_name
    return catalog


def parse_target(raw):
    left, top = raw.split(",", 1)
    return float(left), float(top)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect SmartCanvas picture placements and catalog categories.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="LEFT,TOP",
        help="Target coordinate to inspect; repeat as needed",
    )
    parser.add_argument("--category", action="append", default=[], help="Catalog category to count/list")
    parser.add_argument("--units", choices=("points", "inches"), default="points")
    parser.add_argument("--nearest", type=int, default=6, help="Nearby Picture nodes to print for each target")
    args = parser.parse_args(argv)

    scale = 72.0 if args.units == "inches" else 1.0
    targets = [(left * scale, top * scale) for left, top in map(parse_target, args.target)]
    inner = read_package(Path(args.input))
    doc_name = next(
        name for name in inner if name.replace("\\", "/").endswith("/Document.xml") or name == "Document.xml"
    )
    root = ET.fromstring(inner[doc_name].decode("utf-8-sig"))
    catalog = read_info_catalog(inner)

    pictures = []
    for elem in root.iter():
        if local_name(elem) != "Picture":
            continue
        try:
            left = float(elem.get("Left", "nan"))
            top = float(elem.get("Top", "nan"))
        except ValueError:
            continue
        source = (elem.get("Source") or "").replace("\\", "/")
        filename = source.rsplit("/", 1)[-1]
        pictures.append((left, top, elem, filename, catalog.get(filename, "")))

    print(f"Document: {doc_name}")
    for target_left, target_top in targets:
        ranked = sorted(
            pictures,
            key=lambda item: abs(item[0] - target_left) + abs(item[1] - target_top),
        )[: args.nearest]
        print(f"\nTarget points left={target_left:.4f} top={target_top:.4f}")
        for left, top, elem, filename, category in ranked:
            print(
                f"  left={left} top={top} width={elem.get('Width')} height={elem.get('Height')} "
                f"source={elem.get('Source')} category={category}"
            )

    if args.category:
        print("\nCatalog matches:")
        for category in args.category:
            matches = sorted(fn for fn, cat in catalog.items() if cat == category)
            print(f"{category}: {len(matches)}")
            for filename in matches:
                print(f"  {filename}")


if __name__ == "__main__":
    raise SystemExit(main())
