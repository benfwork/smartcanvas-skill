#!/usr/bin/env python3
"""Set SmartCanvas QR/barcode content in a template export ZIP."""

from __future__ import annotations

import argparse
import copy
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


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
            data = replacements.get(name, member.data)
            info = copy.copy(member.info) if member.info else zipfile.ZipInfo(name)
            if member.info is None:
                info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return buffer.getvalue()


def find_inner_file(inner: dict[str, ZipMember], basename: str) -> str:
    matches = [name for name in inner if name.replace("\\", "/").endswith("/" + basename) or name == basename]
    if not matches:
        raise ValueError(f"inner campaign zip does not contain {basename}")
    return sorted(matches, key=len)[0]


def iter_qr_barcodes(root: ET.Element) -> list[ET.Element]:
    barcodes: list[ET.Element] = []
    for element in root.iter():
        if local_name(element) != "Barcode":
            continue
        if (element.get("ID") or "").lower().endswith("template"):
            continue
        if element.get("Layer") == "none" and element.get("Left") == "-100" and element.get("Top") == "-100":
            continue
        barcode_type = (element.get("BarCodeType") or "").lower()
        ui_type = (element.get("UI-BarCodeType") or "").lower()
        if barcode_type == "qrcode" or "qr" in ui_type:
            barcodes.append(element)
    return barcodes


def format_placeholder(field_name: str) -> str:
    if field_name.startswith("[[") and field_name.endswith("]]"):
        return field_name
    return f"[[{field_name}]]"


def matches_selector(element: ET.Element, args: argparse.Namespace) -> bool:
    if args.id and element.get("ID") != args.id:
        return False
    if args.layer and element.get("Layer") != args.layer:
        return False
    return True


def patch_document(args: argparse.Namespace, data: bytes) -> tuple[bytes, int, int]:
    root = parse_xml(data)
    candidates = iter_qr_barcodes(root)
    selected = [element for element in candidates if matches_selector(element, args)]
    if not selected:
        raise ValueError("no matching QR Barcode nodes found in Document.xml")
    if len(selected) > 1 and not args.all:
        ids = ", ".join(element.get("ID", "<no ID>") for element in selected)
        raise ValueError(f"matched {len(selected)} QR Barcode nodes; pass --all or select one with --id/--layer: {ids}")

    content = format_placeholder(args.field_name) if args.field_name else args.content
    for element in selected:
        element.set("Content", content)
    return xml_bytes(root), len(candidates), len(selected)


def patch_package(args: argparse.Namespace) -> tuple[int, int]:
    outer, inner_name, inner = read_package(Path(args.input))
    document_name = find_inner_file(inner, "Document.xml")
    patched_document, total, changed = patch_document(args, inner[document_name].data)

    inner_bytes = create_inner_zip(inner, {document_name: patched_document})
    output_path = Path(args.output)
    if inner_name:
        outer[inner_name].data = inner_bytes
        write_zip(output_path, outer)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(inner_bytes)
    return total, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set QR-code Content attributes in a SmartCanvas export ZIP.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", help="Output ZIP path")
    content = parser.add_mutually_exclusive_group(required=True)
    content.add_argument("--content", help="Literal QR content to write")
    content.add_argument("--field-name", help="Form field name to write as a SmartCanvas placeholder, e.g. MyWebsite")
    parser.add_argument("--id", help="Only update the QR Barcode node with this ID")
    parser.add_argument("--layer", help="Only update QR Barcode nodes on this layer ID")
    parser.add_argument("--all", action="store_true", help="Update all matched QR Barcode nodes")
    args = parser.parse_args(argv)

    try:
        total, changed = patch_package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    print(f"QR Barcode nodes: {total}; changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
