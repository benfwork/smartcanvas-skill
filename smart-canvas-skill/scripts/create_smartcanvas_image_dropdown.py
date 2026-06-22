#!/usr/bin/env python3
"""Create a SmartCanvas image-list dropdown from image assets.

This script patches the XML surfaces observed in SmartCanvas exports:
Document.xml and smartcampaign.xml. It also copies images into the inner
campaign's images/ folder and can copy complete SmartCanvas image sidecars
from an existing export. It does not rewrite info.bin.
"""

from __future__ import annotations

import argparse
import copy
import io
import os
import posixpath
import random
import re
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
SIDECAR_RE = re.compile(r"_(jpg|jpeg|png)_(info\.xml|thumbi\.png|thumbn\.png)$", re.I)


@dataclass
class ZipMember:
    name: str
    data: bytes
    info: zipfile.ZipInfo | None = None


@dataclass
class ImageAsset:
    filename: str
    data: bytes
    width: int
    height: int
    sidecars: dict[str, bytes]

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def xml_source(self) -> str:
        return f"template/{self.filename}"

    @property
    def switch_name(self) -> str:
        return safe_name(self.stem)

    @property
    def display_value(self) -> str:
        return display_name(self.stem)


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not cleaned:
        cleaned = "image"
    if cleaned[0].isdigit():
        cleaned = f"image_{cleaned}"
    return cleaned


def display_name(value: str) -> str:
    words = re.sub(r"[_-]+", " ", value).strip().split()
    return " ".join(w[:1].upper() + w[1:] for w in words) or value


def qname(parent: ET.Element, tag: str) -> str:
    if parent.tag.startswith("{"):
        return parent.tag.split("}", 1)[0] + "}" + tag
    return tag


def find_child(parent: ET.Element, tag: str) -> ET.Element | None:
    for child in parent:
        if child.tag == qname(parent, tag) or child.tag.rsplit("}", 1)[-1] == tag:
            return child
    return None


def ensure_child(parent: ET.Element, tag: str, **attrs: str) -> ET.Element:
    child = find_child(parent, tag)
    if child is None:
        child = ET.SubElement(parent, qname(parent, tag))
    for key, value in attrs.items():
        child.set(key, value)
    return child


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data.decode("utf-8-sig"))


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True)


def get_image_size(data: bytes, filename: str) -> tuple[int, int]:
    ext = Path(filename).suffix.lower()
    if ext == ".png":
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{filename}: invalid PNG signature")
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if ext in {".jpg", ".jpeg"}:
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in {0xD8, 0xD9}:
                continue
            if i + 2 > len(data):
                break
            size = int.from_bytes(data[i : i + 2], "big")
            if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                if i + 7 > len(data):
                    break
                return int.from_bytes(data[i + 5 : i + 7], "big"), int.from_bytes(data[i + 3 : i + 5], "big")
            i += size
    raise ValueError(f"{filename}: unsupported or unreadable image dimensions")


def sidecar_prefix(filename: str) -> str:
    path = Path(filename)
    ext = path.suffix.lower().lstrip(".")
    return f"{path.stem}_{ext}"


def make_info_sidecar(asset: ImageAsset) -> bytes:
    bitmap_type = "jpeg" if Path(asset.filename).suffix.lower() in {".jpg", ".jpeg"} else "png"
    root = ET.Element(
        "FileGroupInformation",
        {
            "Source": "_Template",
            "Resource": "_Image",
            "Caption": asset.filename,
            "GroupName": "",
            "FileOrigin": "",
            "IsSelected": "false",
            "ImageWidth": str(asset.width),
            "ImageHeight": str(asset.height),
            "LastWriteUtc": "1970-01-01T00:00:00Z",
            "IsMultiImage": "false",
            "LastImage": "1",
            "Filesize": str(len(asset.data)),
        },
    )
    pages = ET.SubElement(root, "Pages")
    ET.SubElement(pages, "Page", {"Top": "0", "Left": "0", "Width": str(asset.width), "Height": str(asset.height)})
    resource = ET.SubElement(
        root,
        "Resourceinfo",
        {
            "DPIx": "72",
            "DPIy": "72",
            "PixelBased": "True",
            "HasMask": "False",
            "HasProfile": "False",
            "CoordType": "Pixel",
            "Version": "",
            "BitmapType": bitmap_type,
            "BitsPerComponent": "8",
        },
    )
    custom = ET.SubElement(resource, "CustomProperties")
    ET.SubElement(custom, "Scalings", {"Value": ""})
    return xml_bytes(root)


def collect_images(source: Path) -> tuple[list[ImageAsset], list[str]]:
    warnings: list[str] = []
    if source.is_dir():
        items: list[tuple[str, bytes, dict[str, bytes]]] = []
        for path in sorted(source.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                items.append((path.name, path.read_bytes(), {}))
        return build_assets(items, warnings)

    if not zipfile.is_zipfile(source):
        raise ValueError(f"image source must be a directory or zip: {source}")

    with zipfile.ZipFile(source) as zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        grouped_sidecars: dict[str, dict[str, bytes]] = {}
        originals: list[tuple[str, bytes, dict[str, bytes]]] = []
        for info in infos:
            name = info.filename.replace("\\", "/")
            base = posixpath.basename(name)
            if not base:
                continue
            match = SIDECAR_RE.search(base)
            if match:
                prefix = base[: match.start()]
                grouped_sidecars.setdefault(prefix, {})[base] = zf.read(info)
                continue
            if Path(base).suffix.lower() in IMAGE_EXTS:
                originals.append((base, zf.read(info), grouped_sidecars.setdefault(sidecar_prefix(base), {})))
        return build_assets(originals, warnings)


def build_assets(items: Iterable[tuple[str, bytes, dict[str, bytes]]], warnings: list[str]) -> tuple[list[ImageAsset], list[str]]:
    assets: list[ImageAsset] = []
    seen: set[str] = set()
    for filename, data, sidecars in items:
        if filename in seen:
            raise ValueError(f"duplicate image filename: {filename}")
        seen.add(filename)
        width, height = get_image_size(data, filename)
        asset = ImageAsset(filename=filename, data=data, width=width, height=height, sidecars=dict(sidecars))
        if not any(name.endswith("_info.xml") for name in asset.sidecars):
            asset.sidecars[f"{sidecar_prefix(filename)}_info.xml"] = make_info_sidecar(asset)
            warnings.append(f"{filename}: generated minimal _info.xml sidecar")
        if not any(name.endswith("_thumbi.png") for name in asset.sidecars):
            warnings.append(f"{filename}: no _thumbi.png sidecar available")
        if not any(name.endswith("_thumbn.png") for name in asset.sidecars):
            warnings.append(f"{filename}: no _thumbn.png sidecar available")
        assets.append(asset)
    if not assets:
        raise ValueError("no images found in source")
    return assets, warnings


def read_package(path: Path) -> tuple[dict[str, ZipMember], str | None, dict[str, ZipMember]]:
    with zipfile.ZipFile(path) as outer_zip:
        outer = {info.filename: ZipMember(info.filename, outer_zip.read(info), info) for info in outer_zip.infolist()}
    inner_name = next((name for name in outer if name.replace("\\", "/").lower().startswith("admin/") and name.lower().endswith(".zip")), None)
    inner_data = outer[inner_name].data if inner_name else path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(inner_data)) as inner_zip:
        inner = {info.filename: ZipMember(info.filename, inner_zip.read(info), info) for info in inner_zip.infolist()}
    return outer, inner_name, inner


def find_inner_file(inner: dict[str, ZipMember], basename: str) -> str:
    matches = [name for name in inner if name.replace("\\", "/").endswith("/" + basename) or name == basename]
    if not matches:
        raise ValueError(f"inner campaign zip does not contain {basename}")
    return sorted(matches, key=len)[0]


def campaign_prefix(document_name: str) -> str:
    normalized = document_name.replace("\\", "/")
    return normalized.rsplit("/", 1)[0] + "/" if "/" in normalized else ""


def ensure_form_dropdown(root: ET.Element, field_name: str, assets: list[ImageAsset]) -> None:
    resources = ensure_child(root, "Resources")
    data_interface = ensure_child(resources, "DataInterface2")
    if find_child(data_interface, "Properties") is None:
        ET.SubElement(
            data_interface,
            "Properties",
            {"PageCount": "1", "PageWidth": "30.0", "PageHeight": "10.5", "LocalDocumentFileName": ""},
        )
    group = find_child(data_interface, "DataInterfaceGroup")
    if group is None:
        group = ET.SubElement(data_interface, "DataInterfaceGroup")
    group.set("Name", "FormFields")
    group.set("DisplayName", "Form fields")
    group.set("AssociatedPageNo", "1")

    for child in list(group):
        if child.tag.rsplit("}", 1)[-1] == "DataInterfaceItem" and child.get("Name") == field_name:
            group.remove(child)

    item = ET.SubElement(
        group,
        "DataInterfaceItem",
        {
            "Name": field_name,
            "Value": assets[0].xml_source,
            "Guid": str(uuid.uuid4()),
            "ItemType": "0",
            "ItemTypeName": "Text",
            "FormatterReplacement": "",
        },
    )
    ET.SubElement(item, "Display", {"DisplayType": "7", "DisplayTypeName": "Image List"})
    ET.SubElement(item, "TextProperties", {"TxtMaxSize": "0", "TxtValidationType": "0", "TxtFieldCategory": "0"})
    ET.SubElement(
        item,
        "Behaviour",
        {
            "isExpandable": "0",
            "isExpanded": "0",
            "OnChangeBehaviour": "1",
            "OnChangeBehaviourName": "NoRefresh",
            "isRequired": "0",
            "RemoveIfEmpty": "0",
            "isElementDBField": "0",
        },
    )
    keys = ET.SubElement(item, "DataInterfaceKeys")
    for asset in assets:
        ET.SubElement(
            keys,
            "DataInterfaceKey",
            {
                "PageNr": "0",
                "KeyValue": asset.xml_source,
                "DisplayValue": asset.display_value,
                "ImageFilename": f"{asset.filename}|{asset.width}|{asset.height}",
            },
        )


def ensure_switches(root: ET.Element, field_name: str, assets: list[ImageAsset]) -> None:
    resources = ensure_child(root, "Resources")
    switches = ensure_child(resources, "Switches")
    wanted = {asset.switch_name for asset in assets}
    for child in list(switches):
        if child.tag.rsplit("}", 1)[-1] == "Switch" and child.get("Name") in wanted:
            switches.remove(child)
    for asset in assets:
        ET.SubElement(
            switches,
            "Switch",
            {
                "Name": asset.switch_name,
                "X": f"([[{field_name}]] == '{asset.xml_source}')",
            },
        )


def ensure_layers_and_pictures(root: ET.Element, assets: list[ImageAsset], left: float, top: float, height: float) -> None:
    layers = ensure_child(root, "Layers")
    existing_layers = {layer.get("DisplayName"): layer for layer in layers if layer.tag.rsplit("}", 1)[-1] == "Layer"}
    default_layer = next((layer for layer in layers if layer.get("IsDefault") == "true"), None)
    insert_at = list(layers).index(default_layer) if default_layer is not None else len(layers)

    for asset in assets:
        layer = existing_layers.get(asset.switch_name)
        if layer is None:
            layer = ET.Element(
                "Layer",
                {
                    "Name": str(uuid.uuid4()),
                    "DisplayName": asset.switch_name,
                    "Color": random_color(asset.switch_name),
                },
            )
            layers.insert(insert_at, layer)
            insert_at += 1
        layer.set("SwitchMode", "Switch")
        layer.set("SwitchName", asset.switch_name)

    composition = find_first(root, "Composition")
    if composition is None:
        raise ValueError("Document.xml does not contain a Composition to receive Picture nodes")
    existing_pictures = {
        picture.get("Source"): picture
        for picture in composition
        if picture.tag.rsplit("}", 1)[-1] == "Picture" and picture.get("Source")
    }
    for asset in assets:
        picture = existing_pictures.get(asset.xml_source)
        width = height * asset.width / asset.height
        if picture is None:
            picture = ET.SubElement(
                composition,
                "Picture",
                {
                    "ID": str(uuid.uuid4()),
                    "Left": str(left),
                    "Top": str(top),
                    "Width": str(width),
                    "Height": str(height),
                    "Background": "",
                    "Opacity": "1",
                    "Layer": find_layer_id(layers, asset.switch_name),
                    "CustomStretch": "UniformToFill",
                    "Stretch": "Fill",
                    "Source": asset.xml_source,
                    "OrgSource": asset.xml_source,
                    "OrigWidth": str(asset.width),
                    "OrigHeight": str(asset.height),
                },
            )
        picture.set("Layer", find_layer_id(layers, asset.switch_name))
        picture.set("SwitchMode", "Switch")
        picture.set("Source", asset.xml_source)
        picture.set("OrgSource", asset.xml_source)
        picture.set("OrigWidth", str(asset.width))
        picture.set("OrigHeight", str(asset.height))


def find_first(root: ET.Element, tag: str) -> ET.Element | None:
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1] == tag:
            return elem
    return None


def find_layer_id(layers: ET.Element, display_name: str) -> str:
    for layer in layers:
        if layer.tag.rsplit("}", 1)[-1] == "Layer" and layer.get("DisplayName") == display_name:
            return layer.get("Name", "")
    raise ValueError(f"missing layer for {display_name}")


def random_color(seed: str) -> str:
    rng = random.Random(seed)
    return f"#{rng.randrange(32, 224):02x}{rng.randrange(32, 224):02x}{rng.randrange(32, 224):02x}"


def sync_smartcampaign(document_root: ET.Element, smartcampaign_data: bytes | None, category: str) -> bytes:
    if smartcampaign_data:
        root = parse_xml(smartcampaign_data)
    else:
        root = ET.Element("Campaign")
    resources = ensure_child(root, "Resources")
    document_resources = find_child(document_root, "Resources")
    if document_resources is not None:
        root.remove(resources)
        resources = copy.deepcopy(document_resources)
        root.insert(0, resources)
    campaign_resources = ensure_child(root, "CampaignResources")
    image_categories = ensure_child(campaign_resources, "ImageCategories")
    if not any(child.tag.rsplit("}", 1)[-1] == "Category" and child.get("Name") == category for child in image_categories):
        ET.SubElement(image_categories, "Category", {"Name": category, "Type": "image"})
    return xml_bytes(root)


def write_zip(path: Path, members: dict[str, ZipMember]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, member in members.items():
            if member.info is None:
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
            else:
                info = copy.copy(member.info)
            zf.writestr(info, member.data)


def create_inner_zip(inner: dict[str, ZipMember], output_replacements: dict[str, bytes], additions: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        written: set[str] = set()
        for name, member in inner.items():
            if name in additions:
                continue
            data = output_replacements.get(name, member.data)
            info = copy.copy(member.info) if member.info else zipfile.ZipInfo(name)
            zf.writestr(info, data)
            written.add(name)
        for name, data in additions.items():
            if name not in written:
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
    return buffer.getvalue()


def patch_package(args: argparse.Namespace) -> list[str]:
    input_path = Path(args.input)
    output_path = Path(args.output)
    assets, warnings = collect_images(Path(args.images))
    outer, inner_name, inner = read_package(input_path)
    document_name = find_inner_file(inner, "Document.xml")
    smartcampaign_name = next((name for name in inner if name.replace("\\", "/").endswith("/smartcampaign.xml")), None)
    prefix = campaign_prefix(document_name)
    image_prefix = prefix + "images/"

    document_root = parse_xml(inner[document_name].data)
    ensure_form_dropdown(document_root, args.field_name, assets)
    ensure_switches(document_root, args.field_name, assets)
    ensure_layers_and_pictures(document_root, assets, args.left, args.top, args.height)

    replacements = {document_name: xml_bytes(document_root)}
    smartcampaign_data = inner[smartcampaign_name].data if smartcampaign_name else None
    smartcampaign_output = sync_smartcampaign(document_root, smartcampaign_data, args.category)
    additions: dict[str, bytes] = {}
    if smartcampaign_name:
        replacements[smartcampaign_name] = smartcampaign_output
    else:
        additions[prefix + "smartcampaign.xml"] = smartcampaign_output

    for asset in assets:
        additions[image_prefix + asset.filename] = asset.data
        for sidecar_name, sidecar_data in asset.sidecars.items():
            additions[image_prefix + sidecar_name] = sidecar_data

    info_member = next((member for name, member in inner.items() if name.replace("\\", "/").endswith("/info.bin") or name == "info.bin"), None)
    if info_member is not None:
        missing_catalog = [asset.filename for asset in assets if asset.filename.encode("utf-8") not in info_member.data]
        if missing_catalog:
            warnings.append(
                "info.bin was not rewritten and does not catalog: "
                + ", ".join(missing_catalog)
                + "; import into SmartCanvas may need an image-catalog rebuild/re-export"
            )

    inner_bytes = create_inner_zip(inner, replacements, additions)
    if inner_name:
        outer[inner_name].data = inner_bytes
        write_zip(output_path, outer)
    else:
        output_path.write_bytes(inner_bytes)
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a SmartCanvas image-list dropdown in a template export ZIP.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("images", help="Directory or ZIP of image files/assets")
    parser.add_argument("output", help="Output ZIP path")
    parser.add_argument("--field-name", default="image_dropdown_1", help="Form field/dropdown name")
    parser.add_argument("--category", default="Image_dropdown", help="Image category name for smartcampaign.xml")
    parser.add_argument("--left", type=float, default=17.0, help="Inserted picture left coordinate")
    parser.add_argument("--top", type=float, default=22.0, help="Inserted picture top coordinate")
    parser.add_argument("--height", type=float, default=104.0, help="Inserted picture height")
    args = parser.parse_args(argv)

    try:
        warnings = patch_package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
