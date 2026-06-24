#!/usr/bin/env python3
"""Verify SmartCanvas image dropdown fields and picture placements."""

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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify SmartCanvas image dropdown fields.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("--field-name", action="append", required=True, help="Dropdown field to verify")
    args = parser.parse_args(argv)

    inner = read_package(Path(args.input))
    doc_name = next(
        name for name in inner if name.replace("\\", "/").endswith("/Document.xml") or name == "Document.xml"
    )
    root = ET.fromstring(inner[doc_name].decode("utf-8-sig"))
    catalog = read_info_catalog(inner)
    wanted_fields = set(args.field_name)
    wanted_sources = set()

    print("Form fields:")
    for item in root.iter():
        if local_name(item) != "DataInterfaceItem" or item.get("Name") not in wanted_fields:
            continue
        keys = [key.get("KeyValue") for key in item.iter() if local_name(key) == "DataInterfaceKey"]
        categories = sorted({catalog.get(key, "") for key in keys})
        print(f"  {item.get('Name')}: {len(keys)} options; categories={categories}")
        for key in keys:
            wanted_sources.add("template/" + key)

    print("\nPicture placement:")
    for pic in root.iter():
        if local_name(pic) != "Picture" or pic.get("Source") not in wanted_sources:
            continue
        filename = pic.get("Source").rsplit("/", 1)[-1]
        print(
            f"  {catalog.get(filename, '')}: {filename}: "
            f"L={pic.get('Left')} T={pic.get('Top')} W={pic.get('Width')} H={pic.get('Height')}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
