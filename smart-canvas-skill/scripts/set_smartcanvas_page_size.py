#!/usr/bin/env python3
"""Set the page/canvas size in a SmartCanvas export."""

from __future__ import annotations

import argparse
import copy
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


POINTS_PER_INCH = 72.0


@dataclass
class ZipMember:
    name: str
    data: bytes
    info: zipfile.ZipInfo | None = None


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data.decode("utf-8-sig"))


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True)


def format_num(value: float) -> str:
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def convert(value: float, units: str) -> float:
    return value if units == "points" else value * POINTS_PER_INCH


def read_package(path: Path) -> tuple[dict[str, ZipMember], str | None, dict[str, ZipMember]]:
    with zipfile.ZipFile(path) as outer_zip:
        outer = {info.filename: ZipMember(info.filename, outer_zip.read(info), info) for info in outer_zip.infolist()}
    inner_name = next(
        (name for name in outer if name.replace("\\", "/").lower().startswith("admin/") and name.lower().endswith(".zip")),
        None,
    )
    inner_data = outer[inner_name].data if inner_name else path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(inner_data)) as inner_zip:
        inner = {info.filename: ZipMember(info.filename, inner_zip.read(info), info) for info in inner_zip.infolist()}
    return outer, inner_name, inner


def write_zip(path: Path, members: dict[str, ZipMember]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, member in members.items():
            info = copy.copy(member.info) if member.info else zipfile.ZipInfo(name)
            if member.info is None:
                info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, member.data)


def create_inner_zip(inner: dict[str, ZipMember], replacements: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, member in inner.items():
            info = copy.copy(member.info) if member.info else zipfile.ZipInfo(name)
            zf.writestr(info, replacements.get(name, member.data))
    return buffer.getvalue()


def find_inner_file(inner: dict[str, ZipMember], basename: str) -> str:
    matches = [name for name in inner if name.replace("\\", "/").endswith("/" + basename) or name == basename]
    if not matches:
        raise ValueError(f"inner campaign zip does not contain {basename}")
    return sorted(matches, key=len)[0]


def editable_document(root: ET.Element) -> ET.Element:
    if local_name(root) == "Document":
        return root
    if local_name(root) == "Documents":
        for child in root:
            if local_name(child) == "Document":
                return child
    raise ValueError("Document.xml must have a Document root or contain a Document child")


def set_page_size(document: ET.Element, width: float, height: float) -> tuple[int, int]:
    width_text = format_num(width)
    height_text = format_num(height)
    document.set("InsertPageWidth", width_text)
    document.set("InsertPageHeight", height_text)
    pages = 0
    compositions = 0
    for element in document.iter():
        if local_name(element) == "Page":
            element.set("Width", width_text)
            element.set("Height", height_text)
            pages += 1
        elif local_name(element) == "Composition":
            element.set("Width", width_text)
            element.set("Height", height_text)
            compositions += 1
    return pages, compositions


def patch_package(input_path: Path, output_path: Path, width: float, height: float) -> tuple[int, int]:
    outer, inner_name, inner = read_package(input_path)
    document_name = find_inner_file(inner, "Document.xml")
    document_root = parse_xml(inner[document_name].data)
    document = editable_document(document_root)
    counts = set_page_size(document, width, height)
    inner_bytes = create_inner_zip(inner, {document_name: xml_bytes(document_root)})
    if inner_name:
        outer[inner_name].data = inner_bytes
        write_zip(output_path, outer)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(inner_bytes)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set SmartCanvas Document, Page, and Composition size.")
    parser.add_argument("input", type=Path, help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", type=Path, help="Output ZIP path")
    parser.add_argument("--width", type=float, required=True, help="Page width")
    parser.add_argument("--height", type=float, required=True, help="Page height")
    parser.add_argument("--units", choices=("points", "inches"), default="points", help="Units for width/height")
    args = parser.parse_args(argv)

    width = convert(args.width, args.units)
    height = convert(args.height, args.units)
    try:
        pages, compositions = patch_package(args.input, args.output, width, height)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output}")
    print(f"Page size: {format_num(width)} x {format_num(height)} points; pages: {pages}; compositions: {compositions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
