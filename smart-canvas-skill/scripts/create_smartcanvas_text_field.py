#!/usr/bin/env python3
"""Create a SmartCanvas text field in a template export."""

from __future__ import annotations

import argparse
import copy
import html
import io
import random
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


POINTS_PER_INCH = 72.0

FONTS = {
    "Arial": ("Arial", "400", "normal"),
    "Arial Bold Italic": ("Arial", "700", "italic"),
    "Arial Bold": ("Arial", "700", "normal"),
    "Arial Italic": ("Arial", "400", "italic"),
    "Calibri": ("Calibri", "400", "normal"),
    "Calibri Bold": ("Calibri", "700", "normal"),
    "Calibri Bold Italic": ("Calibri", "700", "italic"),
    "Calibri Italic": ("Calibri", "400", "italic"),
    "Century Gothic": ("Century Gothic", "400", "normal"),
    "Century Gothic Bold": ("Century Gothic", "700", "normal"),
    "Century Gothic Bold Italic": ("Century Gothic", "700", "italic"),
    "Century Gothic Italic": ("Century Gothic", "400", "italic"),
    "Comic Sans MS": ("Comic Sans MS", "400", "normal"),
    "Comic Sans MS Bold": ("Comic Sans MS", "700", "normal"),
    "Garamond": ("Garamond", "400", "normal"),
    "Garamond Bold": ("Garamond", "700", "normal"),
    "Garamond Italic": ("Garamond", "400", "italic"),
    "Times New Roman": ("Times New Roman", "400", "normal"),
    "Times New Roman Bold Italic": ("Times New Roman", "700", "italic"),
    "Times New Roman Bold": ("Times New Roman", "700", "normal"),
    "Times New Roman Italic": ("Times New Roman", "400", "italic"),
    "Trebuchet MS": ("Trebuchet MS", "400", "normal"),
    "Trebuchet MS Bold Italic": ("Trebuchet MS", "700", "italic"),
    "Trebuchet MS Bold": ("Trebuchet MS", "700", "normal"),
    "Trebuchet MS Italic": ("Trebuchet MS", "400", "italic"),
}


@dataclass
class ZipMember:
    name: str
    data: bytes
    info: zipfile.ZipInfo | None = None


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def qname(parent: ET.Element, tag: str) -> str:
    if parent.tag.startswith("{"):
        return parent.tag.split("}", 1)[0] + "}" + tag
    return tag


def find_child(parent: ET.Element, tag: str) -> ET.Element | None:
    for child in parent:
        if child.tag == qname(parent, tag) or local_name(child) == tag:
            return child
    return None


def ensure_child(parent: ET.Element, tag: str, **attrs: str) -> ET.Element:
    child = find_child(parent, tag)
    if child is None:
        child = ET.SubElement(parent, qname(parent, tag))
    for key, value in attrs.items():
        child.set(key, value)
    return child


def find_first(root: ET.Element, tag: str) -> ET.Element | None:
    for element in root.iter():
        if local_name(element) == tag:
            return element
    return None


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data.decode("utf-8-sig"))


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True)


def format_num(value: float) -> str:
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def random_color(seed: str) -> str:
    rng = random.Random(seed)
    return f"#{rng.randrange(32, 224):02x}{rng.randrange(32, 224):02x}{rng.randrange(32, 224):02x}"


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


def create_inner_zip(inner: dict[str, ZipMember], replacements: dict[str, bytes], additions: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        written: set[str] = set()
        for name, member in inner.items():
            if name in additions:
                continue
            data = replacements.get(name, member.data)
            info = copy.copy(member.info) if member.info else zipfile.ZipInfo(name)
            zf.writestr(info, data)
            written.add(name)
        for name, data in additions.items():
            if name not in written:
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
    return buffer.getvalue()


def find_inner_file(inner: dict[str, ZipMember], basename: str) -> str:
    matches = [name for name in inner if name.replace("\\", "/").endswith("/" + basename) or name == basename]
    if not matches:
        raise ValueError(f"inner campaign zip does not contain {basename}")
    return sorted(matches, key=len)[0]


def campaign_prefix(document_name: str) -> str:
    normalized = document_name.replace("\\", "/")
    return normalized.rsplit("/", 1)[0] + "/" if "/" in normalized else ""


def editable_document(root: ET.Element) -> ET.Element:
    if local_name(root) == "Document":
        return root
    if local_name(root) == "Documents":
        document = find_child(root, "Document")
        if document is not None:
            return document
    raise ValueError("Document.xml must have a Document root or contain a Document child")


def ensure_layer(document: ET.Element, layer_name: str, locked: bool) -> str:
    layers = ensure_child(document, "Layers")
    for layer in layers:
        if local_name(layer) == "Layer" and layer.get("DisplayName") == layer_name:
            if locked:
                layer.set("IsLocked", "true")
            return layer.get("Name", "")

    layer = ET.Element(
        "Layer",
        {
            "Name": str(uuid.uuid4()),
            "DisplayName": layer_name,
            "Color": random_color(layer_name),
        },
    )
    if locked:
        layer.set("IsLocked", "true")
    default_layer = next((child for child in layers if local_name(child) == "Layer" and child.get("IsDefault") == "true"), None)
    insert_at = list(layers).index(default_layer) if default_layer is not None else len(layers)
    layers.insert(insert_at, layer)
    return layer.get("Name", "")


def ensure_text_style(
    document: ET.Element,
    style_name: str,
    font: str,
    font_size: float,
    line_height: float,
    tracking: str,
    color: str,
    alignment: str,
    outline_thickness: str | None,
) -> None:
    family, weight, font_style = FONTS[font]
    resources = ensure_child(document, "Resources")
    styles = ensure_child(resources, "TextStyles")
    for child in list(styles):
        if local_name(child) == "ParagraphStyle" and child.get("Name") == style_name:
            styles.remove(child)
    attrs = {
        "Name": style_name,
        "BasedOn": "[Default]",
        "FontFamily": family,
        "FontSize": format_num(font_size),
        "FontStyle": font_style,
        "FontWeight": weight,
        "Tracking": tracking,
        "LineHeight": format_num(line_height),
        "TextAlignment": alignment,
        "RuleAboveMode": "column",
        "RuleAboveRef": "top",
        "RuleBelowRef": "bottom",
        "RuleBelowMode": "column",
    }
    if color:
        attrs["Foreground"] = color
    if outline_thickness is not None:
        attrs["OutlineThickness"] = outline_thickness
    ET.SubElement(styles, "ParagraphStyle", attrs)


def add_text(document: ET.Element, args: argparse.Namespace, layer_id: str) -> None:
    composition = find_first(document, "Composition")
    if composition is None:
        raise ValueError("Document.xml does not contain a Composition to receive Text nodes")

    escaped = html.escape(args.text, quote=False)
    text_attrs = {
        "ID": str(uuid.uuid4()),
        "Left": format_num(args.left),
        "Top": format_num(args.top),
        "Width": format_num(args.width),
        "Height": format_num(args.height),
        "Background": args.background,
        "Opacity": format_num(args.opacity),
        "Layer": layer_id,
        "Version": "3",
        "FitMode": args.fit_mode,
        "BasedOn": args.style_name,
        "LineSetter": args.line_setter,
        "html": f'<p class="">{escaped}</p>',
    }
    text_node = ET.SubElement(composition, "Text", text_attrs)
    paragraph = ET.SubElement(text_node, "Paragraph", {"BasedOn": args.style_name})
    run = ET.SubElement(paragraph, "Run")
    run.text = args.text


def sync_smartcampaign(document: ET.Element, smartcampaign_data: bytes | None) -> bytes:
    root = parse_xml(smartcampaign_data) if smartcampaign_data else ET.Element("Campaign")
    resources = ensure_child(root, "Resources")
    document_resources = find_child(document, "Resources")
    if document_resources is not None:
        root.remove(resources)
        root.insert(0, copy.deepcopy(document_resources))
    return xml_bytes(root)


def convert_measurements(args: argparse.Namespace) -> None:
    if args.units == "points":
        return
    for name in ("left", "top", "width", "height"):
        setattr(args, name, getattr(args, name) * POINTS_PER_INCH)


def patch_package(args: argparse.Namespace) -> None:
    outer, inner_name, inner = read_package(Path(args.input))
    document_name = find_inner_file(inner, "Document.xml")
    smartcampaign_name = next((name for name in inner if name.replace("\\", "/").endswith("/smartcampaign.xml")), None)
    prefix = campaign_prefix(document_name)

    document_root = parse_xml(inner[document_name].data)
    document = editable_document(document_root)
    layer_id = ensure_layer(document, args.layer_name, args.lock_layer)
    ensure_text_style(
        document,
        args.style_name,
        args.font,
        args.font_size,
        args.line_height,
        args.tracking,
        args.color,
        args.align,
        args.outline_thickness,
    )
    add_text(document, args, layer_id)

    replacements = {document_name: xml_bytes(document_root)}
    additions: dict[str, bytes] = {}
    smartcampaign_output = sync_smartcampaign(document, inner[smartcampaign_name].data if smartcampaign_name else None)
    if smartcampaign_name:
        replacements[smartcampaign_name] = smartcampaign_output
    else:
        additions[prefix + "smartcampaign.xml"] = smartcampaign_output

    inner_bytes = create_inner_zip(inner, replacements, additions)
    output_path = Path(args.output)
    if inner_name:
        outer[inner_name].data = inner_bytes
        write_zip(output_path, outer)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(inner_bytes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a SmartCanvas text field in a template export ZIP.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", help="Output ZIP path")
    parser.add_argument("--text", required=True, help="Text content to place in the field")
    parser.add_argument("--left", type=float, default=0.0, help="Text left/X coordinate")
    parser.add_argument("--top", type=float, default=0.0, help="Text top/Y coordinate")
    parser.add_argument("--width", type=float, default=200.0, help="Text field width")
    parser.add_argument("--height", type=float, default=40.0, help="Text field height")
    parser.add_argument("--units", choices=("points", "inches"), default="points", help="Coordinate units")
    parser.add_argument("--layer-name", default="Text Layer", help="Layer to create or reuse")
    parser.add_argument("--lock-layer", action="store_true", help="Set IsLocked=true on the target layer")
    parser.add_argument("--style-name", default="Codex text style", help="ParagraphStyle name to create/update")
    parser.add_argument("--font", choices=sorted(FONTS), default="Arial", help="Font face/style")
    parser.add_argument("--font-size", type=float, default=11.0, help="Font size in points")
    parser.add_argument("--line-height", type=float, default=0.0, help="Line height in points; 0 lets SmartCanvas default it")
    parser.add_argument("--tracking", default="normal", help="SmartCanvas tracking value, e.g. normal, 100, 200")
    parser.add_argument("--color", default="", help="Optional SmartCanvas Foreground value, e.g. '#000000' or 'swatch, [Black]'")
    parser.add_argument("--align", choices=("left", "center", "right", "justify"), default="left", help="Text alignment")
    parser.add_argument("--outline-thickness", help="Optional outline thickness, e.g. 0.5")
    parser.add_argument("--fit-mode", default="ShrinkOnly", help="Text FitMode attribute")
    parser.add_argument("--line-setter", default="HalfLeading", help="Text LineSetter attribute")
    parser.add_argument("--background", default="", help="Text Background attribute")
    parser.add_argument("--opacity", type=float, default=1.0, help="Text opacity")
    args = parser.parse_args(argv)

    convert_measurements(args)
    try:
        patch_package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
