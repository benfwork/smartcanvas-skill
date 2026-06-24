#!/usr/bin/env python3
"""Locate SmartCanvas picture nodes by page and coordinates."""

from __future__ import annotations

import argparse
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
SIDECAR_RE = re.compile(r"_(jpg|jpeg|png)_(info\.xml|thumbi\.png|thumbn\.png)$", re.I)
THUMB_NAME_RE = re.compile(r"_(thumbi|thumbn)\.png$", re.I)


def local_name(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1]


def read_package(path: Path) -> dict[str, bytes]:
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
    inner_data = outer[inner_name] if inner_name else path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(inner_data)) as inner_zip:
        return {info.filename: inner_zip.read(info) for info in inner_zip.infolist()}


def parse_target(raw: str) -> tuple[float, float]:
    left, top = raw.split(",", 1)
    return float(left), float(top)


def read_info_catalog(inner: dict[str, bytes]) -> dict[str, str]:
    catalog: dict[str, str] = {}
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


def catalog_category_for(catalog: dict[str, str], filename: str) -> str:
    if filename in catalog:
        return catalog[filename]
    for raw_filename, category in catalog.items():
        if raw_filename.endswith(filename) or raw_filename[1:] == filename:
            return category
    return ""


def list_category(inner: dict[str, bytes], catalog: dict[str, str], category: str) -> list[str]:
    selected = []
    for name in inner:
        normalized = name.replace("\\", "/")
        filename = normalized.rsplit("/", 1)[-1]
        if Path(filename).suffix.lower() not in IMAGE_EXTS:
            continue
        if SIDECAR_RE.search(filename) or THUMB_NAME_RE.search(filename):
            continue
        if catalog_category_for(catalog, filename) == category:
            selected.append(filename)
    return sorted(set(selected))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Locate SmartCanvas images by page and X/Y coordinates.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("--target", action="append", default=[], metavar="LEFT,TOP", help="Coordinate to inspect; repeat as needed")
    parser.add_argument("--page", type=int, action="append", help="Limit matching to page number(s), 1-based")
    parser.add_argument("--category", action="append", default=[], help="Catalog category to count/list")
    parser.add_argument("--units", choices=("points", "inches"), default="points")
    parser.add_argument("--nearest", type=int, default=6, help="Nearby Picture nodes to print for each target")
    args = parser.parse_args(argv)

    scale = 72.0 if args.units == "inches" else 1.0
    targets = [(left * scale, top * scale) for left, top in map(parse_target, args.target)]
    page_filter = set(args.page or [])

    inner = read_package(Path(args.input))
    document_name = next(
        name for name in inner if name.replace("\\", "/").endswith("/Document.xml") or name == "Document.xml"
    )
    root = ET.fromstring(inner[document_name].decode("utf-8-sig"))
    catalog = read_info_catalog(inner)
    layers = {
        layer.get("Name"): layer.get("DisplayName")
        for layer in root.iter()
        if local_name(layer) == "Layer"
    }

    pictures = []
    pages = [child for child in root if local_name(child) == "Page"]
    for page_index, page in enumerate(pages, 1):
        if page_filter and page_index not in page_filter:
            continue
        composition = next((elem for elem in page.iter() if local_name(elem) == "Composition"), None)
        if composition is None:
            continue
        for order, elem in enumerate(list(composition)):
            if local_name(elem) != "Picture":
                continue
            try:
                left = float(elem.get("Left", "nan"))
                top = float(elem.get("Top", "nan"))
            except ValueError:
                continue
            source = (elem.get("Source") or "").replace("\\", "/")
            filename = source.rsplit("/", 1)[-1]
            pictures.append(
                {
                    "page": page_index,
                    "order": order,
                    "left": left,
                    "top": top,
                    "elem": elem,
                    "filename": filename,
                    "category": catalog_category_for(catalog, filename),
                    "layer_display": layers.get(elem.get("Layer"), ""),
                }
            )

    print(f"Document: {document_name}")
    for target_left, target_top in targets:
        ranked = sorted(
            pictures,
            key=lambda item: abs(item["left"] - target_left) + abs(item["top"] - target_top),
        )[: args.nearest]
        print(f"\nTarget points left={target_left:.4f} top={target_top:.4f}")
        for item in ranked:
            elem = item["elem"]
            print(
                f"  page={item['page']} order={item['order']} "
                f"left={elem.get('Left')} top={elem.get('Top')} width={elem.get('Width')} height={elem.get('Height')} "
                f"layer={item['layer_display']!r} source={elem.get('Source')} category={item['category']}"
            )

    if args.category:
        print("\nCatalog matches:")
        for category in args.category:
            matches = list_category(inner, catalog, category)
            print(f"{category}: {len(matches)}")
            for filename in matches:
                print(f"  {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
