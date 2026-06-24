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
THUMB_NAME_RE = re.compile(r"_(thumbi|thumbn)\.png$", re.I)


@dataclass
class ZipMember:
    name: str
    data: bytes
    info: zipfile.ZipInfo | None = None


@dataclass
class ImageAsset:
    source_path: str
    filename: str
    category: str
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
    def key_value(self) -> str:
        return self.filename

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


def safe_field_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-_")
    if not cleaned:
        cleaned = "image-dropdown"
    if cleaned[0].isdigit():
        cleaned = f"field-{cleaned}"
    return cleaned


def switch_name_for(field_name: str, index: int) -> str:
    return f"{safe_name(field_name)}_{index:02d}"


def display_name(value: str) -> str:
    words = re.sub(r"[_-]+", " ", value).strip().split()
    return " ".join(w[:1].upper() + w[1:] for w in words) or value


def safe_file_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "image"


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


def normalized_lookup(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def normalize_info_sidecar(data: bytes, asset: ImageAsset) -> bytes:
    try:
        root = parse_xml(data)
    except ET.ParseError:
        return data
    root.set("Caption", asset.filename)
    root.set("GroupName", asset.category)
    root.set("ImageWidth", str(asset.width))
    root.set("ImageHeight", str(asset.height))
    return xml_bytes(root)


def make_info_sidecar(asset: ImageAsset) -> bytes:
    bitmap_type = "jpeg" if Path(asset.filename).suffix.lower() in {".jpg", ".jpeg"} else "png"
    root = ET.Element(
        "FileGroupInformation",
        {
            "Source": "_Template",
            "Resource": "_Image",
            "Caption": asset.filename,
            "GroupName": asset.category,
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
        for path in sorted(source.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                items.append((path.relative_to(source).as_posix(), path.read_bytes(), {}))
        return build_assets(items, warnings)

    if not zipfile.is_zipfile(source):
        raise ValueError(f"image source must be a directory or zip: {source}")

    with zipfile.ZipFile(source) as zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        names = [info.filename.replace("\\", "/").strip("/") for info in infos]
        image_names = [name for name in names if Path(posixpath.basename(name)).suffix.lower() in IMAGE_EXTS]
        strip_prefix = common_zip_root(image_names)
        grouped_sidecars: dict[str, dict[str, bytes]] = {}
        originals: list[tuple[str, bytes, dict[str, bytes]]] = []
        for info in infos:
            name = strip_zip_root(info.filename.replace("\\", "/").strip("/"), strip_prefix)
            base = posixpath.basename(name)
            if not base:
                continue
            match = SIDECAR_RE.search(base)
            if match:
                prefix = base[: match.start()]
                key = posixpath.join(posixpath.dirname(name), prefix)
                grouped_sidecars.setdefault(key, {})[base] = zf.read(info)
                continue
            if Path(base).suffix.lower() in IMAGE_EXTS:
                key = posixpath.join(posixpath.dirname(name), sidecar_prefix(base))
                originals.append((name, zf.read(info), grouped_sidecars.setdefault(key, {})))
        return build_assets(originals, warnings)


def collect_existing_library_images(
    inner: dict[str, ZipMember],
    image_prefix: str,
    selector: str,
    default_category: str,
) -> tuple[list[ImageAsset], list[str], dict[str, bytes]]:
    warnings: list[str] = []
    selected = normalized_lookup(selector)
    catalog = read_info_catalog(inner)
    image_members = {
        posixpath.basename(name.replace("\\", "/")): member
        for name, member in inner.items()
        if name.replace("\\", "/").startswith(image_prefix)
        and Path(posixpath.basename(name.replace("\\", "/"))).suffix.lower() in IMAGE_EXTS
        and not SIDECAR_RE.search(posixpath.basename(name.replace("\\", "/")))
        and not THUMB_NAME_RE.search(posixpath.basename(name.replace("\\", "/")))
    }
    sidecar_members = {
        posixpath.basename(name.replace("\\", "/")): member.data
        for name, member in inner.items()
        if name.replace("\\", "/").startswith(image_prefix)
        and SIDECAR_RE.search(posixpath.basename(name.replace("\\", "/")))
    }

    matched: list[tuple[str, ZipMember, str]] = []
    for filename, member in sorted(image_members.items()):
        category = catalog_category_for(catalog, filename)
        search_values = {
            normalized_lookup(category),
            normalized_lookup(filename),
            normalized_lookup(Path(filename).stem),
        }
        if selected in search_values or any(selected and selected in value for value in search_values):
            matched.append((filename, member, category))

    if not matched:
        raise ValueError(f"no existing library images matched {selector!r}")

    assets: list[ImageAsset] = []
    for filename, member, category in matched:
        data = member.data
        width, height = get_image_size(data, filename)
        asset = ImageAsset(
            source_path=image_prefix + filename,
            filename=filename,
            category=category or default_category,
            data=data,
            width=width,
            height=height,
            sidecars={},
        )
        prefix = sidecar_prefix(filename)
        for suffix in ("info.xml", "thumbi.png", "thumbn.png"):
            sidecar_name = f"{prefix}_{suffix}"
            if sidecar_name in sidecar_members:
                asset.sidecars[sidecar_name] = sidecar_members[sidecar_name]
        if not asset.sidecars:
            warnings.append(f"{filename}: selected from library but sidecars were not found")
        assets.append(asset)
    return assets, warnings, {asset.filename: asset.data for asset in assets}


def catalog_category_for(catalog: dict[str, str], filename: str) -> str:
    if filename in catalog:
        return catalog[filename]
    for raw_filename, category in catalog.items():
        if raw_filename.endswith(filename) or raw_filename[1:] == filename:
            return category
    return ""


def read_info_catalog(inner: dict[str, ZipMember]) -> dict[str, str]:
    catalog: dict[str, str] = {}
    info_members = [
        member.data
        for name, member in inner.items()
        if name.replace("\\", "/").endswith("/info.bin") or name == "info.bin"
    ]
    if not info_members:
        return catalog
    blob = b"\n".join(info_members)
    image = rb"([A-Za-z0-9_ .,'()&+\-\[\]]+\.(?:jpg|jpeg|png))"
    category = rb"\x12([\x01-\x40])([A-Za-z0-9_ .,'()&+\-/]+)"
    for match in re.finditer(image + category, blob, re.I):
        filename = match.group(1).decode("utf-8", errors="ignore")
        length = match.group(2)[0]
        raw_category = match.group(3)[:length]
        category_name = raw_category.decode("utf-8", errors="ignore").strip()
        if filename and category_name:
            catalog[filename] = category_name
    return catalog


def common_zip_root(image_names: list[str]) -> str:
    if not image_names:
        return ""
    first_segments = {name.split("/", 1)[0] for name in image_names if "/" in name}
    has_root_image = any("/" not in name for name in image_names)
    if has_root_image or len(first_segments) != 1:
        return ""
    return next(iter(first_segments))


def strip_zip_root(name: str, strip_prefix: str) -> str:
    if strip_prefix and (name == strip_prefix or name.startswith(strip_prefix + "/")):
        return name[len(strip_prefix) :].lstrip("/")
    return name


def build_assets(items: Iterable[tuple[str, bytes, dict[str, bytes]]], warnings: list[str]) -> tuple[list[ImageAsset], list[str]]:
    assets: list[ImageAsset] = []
    item_list = sorted(items, key=lambda item: item[0])
    basename_counts: dict[str, int] = {}
    for rel_path, _, _ in item_list:
        basename_counts[posixpath.basename(rel_path)] = basename_counts.get(posixpath.basename(rel_path), 0) + 1
    used_filenames: set[str] = set()
    for rel_path, data, sidecars in item_list:
        filename = output_filename(rel_path, basename_counts[posixpath.basename(rel_path)], used_filenames)
        category = posixpath.dirname(rel_path)
        width, height = get_image_size(data, filename)
        asset = ImageAsset(source_path=rel_path, filename=filename, category=category, data=data, width=width, height=height, sidecars={})
        copied_info = False
        for sidecar_name, sidecar_data in sidecars.items():
            suffix = sidecar_suffix(sidecar_name)
            if suffix is None:
                continue
            output_sidecar_name = f"{sidecar_prefix(filename)}_{suffix}"
            if suffix == "info.xml":
                sidecar_data = normalize_info_sidecar(sidecar_data, asset)
                copied_info = True
            asset.sidecars[output_sidecar_name] = sidecar_data
        if not copied_info:
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


def apply_default_category(assets: list[ImageAsset], default_category: str) -> None:
    for asset in assets:
        if not asset.category:
            asset.category = default_category
        for sidecar_name, sidecar_data in list(asset.sidecars.items()):
            if sidecar_name.endswith("_info.xml"):
                asset.sidecars[sidecar_name] = normalize_info_sidecar(sidecar_data, asset)


def output_filename(rel_path: str, basename_count: int, used_filenames: set[str]) -> str:
    base = posixpath.basename(rel_path)
    ext = Path(base).suffix
    stem = Path(base).stem
    if basename_count == 1:
        candidate = safe_file_segment(stem) + ext.lower()
    else:
        parent = posixpath.dirname(rel_path)
        path_stem = "__".join(safe_file_segment(part) for part in [*parent.split("/"), stem] if part)
        candidate = path_stem + ext.lower()
    original_candidate = candidate
    counter = 2
    while candidate in used_filenames:
        candidate = f"{Path(original_candidate).stem}_{counter}{Path(original_candidate).suffix}"
        counter += 1
    used_filenames.add(candidate)
    return candidate


def sidecar_suffix(filename: str) -> str | None:
    match = SIDECAR_RE.search(filename)
    if not match:
        return None
    return match.group(2).lower()


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


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def editable_document(root: ET.Element) -> ET.Element:
    if local_name(root) == "Document":
        return root
    if local_name(root) == "Documents":
        document = find_child(root, "Document")
        if document is not None:
            return document
    raise ValueError("Document.xml must have a Document root or contain a Document child")


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
        if local_name(child) == "DataInterfaceItem" and child.get("Name") == field_name:
            group.remove(child)

    item = ET.SubElement(
        group,
        "DataInterfaceItem",
        {
            "Name": field_name,
            "Value": assets[0].key_value,
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
                "KeyValue": asset.key_value,
                "DisplayValue": asset.display_value,
                "ImageFilename": f"{asset.filename}|{asset.width}|{asset.height}",
            },
        )


def ensure_switches(root: ET.Element, field_name: str, assets: list[ImageAsset]) -> None:
    resources = ensure_child(root, "Resources")
    switches = ensure_child(resources, "Switches")
    prefix = safe_name(field_name) + "_"
    wanted = {switch_name_for(field_name, index) for index, _ in enumerate(assets, 1)}
    legacy_wanted = {asset.switch_name for asset in assets}
    for child in list(switches):
        if local_name(child) != "Switch":
            continue
        name = child.get("Name") or ""
        if name in wanted or name in legacy_wanted or name.startswith(prefix):
            switches.remove(child)
    for index, asset in enumerate(assets, 1):
        ET.SubElement(
            switches,
            "Switch",
            {
                "Name": switch_name_for(field_name, index),
                "X": f"([[{field_name}]] == '{asset.key_value}')",
            },
        )


def ensure_layers_and_pictures(
    root: ET.Element,
    field_name: str,
    assets: list[ImageAsset],
    left: float,
    top: float,
    width: float | None,
    height: float | None,
) -> None:
    layers = ensure_child(root, "Layers")
    existing_layers = {layer.get("DisplayName"): layer for layer in layers if local_name(layer) == "Layer"}
    default_layer = next((layer for layer in layers if layer.get("IsDefault") == "true"), None)
    insert_at = list(layers).index(default_layer) if default_layer is not None else len(layers)

    switch_names = {asset.filename: switch_name_for(field_name, index) for index, asset in enumerate(assets, 1)}
    for asset in assets:
        switch_name = switch_names[asset.filename]
        layer = existing_layers.get(switch_name)
        if layer is None:
            layer = ET.Element(
                "Layer",
                {
                    "Name": str(uuid.uuid4()),
                    "DisplayName": switch_name,
                    "Color": random_color(switch_name),
                },
            )
            layers.insert(insert_at, layer)
            insert_at += 1
        layer.set("SwitchMode", "Switch")
        layer.set("SwitchName", switch_name)

    composition = find_first(root, "Composition")
    if composition is None:
        raise ValueError("Document.xml does not contain a Composition to receive Picture nodes")
    existing_pictures = {
        (picture.get("Source"), picture.get("Layer")): picture
        for picture in composition
        if local_name(picture) == "Picture" and picture.get("Source")
    }
    for asset in assets:
        switch_name = switch_names[asset.filename]
        layer_id = find_layer_id(layers, switch_name)
        picture = existing_pictures.get((asset.xml_source, layer_id))
        picture_width = width if width is not None else height * asset.width / asset.height
        picture_height = height if height is not None else picture_width * asset.height / asset.width
        if picture is None:
            picture = ET.SubElement(
                composition,
                "Picture",
                {
                    "ID": str(uuid.uuid4()),
                    "Left": str(left),
                    "Top": str(top),
                    "Width": str(picture_width),
                    "Height": str(picture_height),
                    "Background": "",
                    "Opacity": "1",
                    "Layer": layer_id,
                    "CustomStretch": "UniformToFill",
                    "Stretch": "Fill",
                    "Source": asset.xml_source,
                    "OrgSource": asset.xml_source,
                    "OrigWidth": str(asset.width),
                    "OrigHeight": str(asset.height),
                },
            )
        picture.set("Layer", layer_id)
        picture.set("SwitchMode", "Switch")
        picture.set("Source", asset.xml_source)
        picture.set("OrgSource", asset.xml_source)
        picture.set("OrigWidth", str(asset.width))
        picture.set("OrigHeight", str(asset.height))
        picture.set("Left", str(left))
        picture.set("Top", str(top))
        picture.set("Width", str(picture_width))
        picture.set("Height", str(picture_height))


def find_first(root: ET.Element, tag: str) -> ET.Element | None:
    for elem in root.iter():
        if local_name(elem) == tag:
            return elem
    return None


def find_layer_id(layers: ET.Element, display_name: str) -> str:
    for layer in layers:
        if local_name(layer) == "Layer" and layer.get("DisplayName") == display_name:
            return layer.get("Name", "")
    raise ValueError(f"missing layer for {display_name}")


def random_color(seed: str) -> str:
    rng = random.Random(seed)
    return f"#{rng.randrange(32, 224):02x}{rng.randrange(32, 224):02x}{rng.randrange(32, 224):02x}"


def convert_measurements(args: argparse.Namespace) -> None:
    if args.units == "points":
        return
    scale = 72.0
    args.left *= scale
    args.top *= scale
    if args.width is not None:
        args.width *= scale
    if args.height is not None:
        args.height *= scale


def sync_smartcampaign(document_root: ET.Element, smartcampaign_data: bytes | None, categories: Iterable[str]) -> bytes:
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
    existing_categories = {child.get("Name") for child in image_categories if local_name(child) == "Category"}
    for category in categories:
        if category and category not in existing_categories:
            ET.SubElement(image_categories, "Category", {"Name": category, "Type": "image"})
            existing_categories.add(category)
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
    outer, inner_name, inner = read_package(input_path)
    document_name = find_inner_file(inner, "Document.xml")
    smartcampaign_name = next((name for name in inner if name.replace("\\", "/").endswith("/smartcampaign.xml")), None)
    prefix = campaign_prefix(document_name)
    image_prefix = prefix + "images/"
    existing_library = bool(args.library_folder or args.library_filter)
    if existing_library:
        selector = args.library_folder or args.library_filter
        assets, warnings, existing_image_data = collect_existing_library_images(inner, image_prefix, selector, args.category)
    else:
        assets, warnings = collect_images(Path(args.images))
        apply_default_category(assets, args.category)
        existing_image_data = {}

    requested_field_name = args.field_name
    args.field_name = safe_field_name(args.field_name)
    if args.field_name != requested_field_name:
        warnings.append(f"field name sanitized from {requested_field_name!r} to {args.field_name!r} for SmartCanvas switch compatibility")

    document_root = parse_xml(inner[document_name].data)
    document = editable_document(document_root)
    ensure_form_dropdown(document, args.field_name, assets)
    ensure_switches(document, args.field_name, assets)
    ensure_layers_and_pictures(document, args.field_name, assets, args.left, args.top, args.width, args.height)

    replacements = {document_name: xml_bytes(document_root)}
    smartcampaign_data = inner[smartcampaign_name].data if smartcampaign_name else None
    categories = sorted({asset.category for asset in assets if asset.category})
    smartcampaign_output = sync_smartcampaign(document, smartcampaign_data, categories)
    additions: dict[str, bytes] = {}
    if smartcampaign_name:
        replacements[smartcampaign_name] = smartcampaign_output
    else:
        additions[prefix + "smartcampaign.xml"] = smartcampaign_output

    if not existing_library:
        for asset in assets:
            additions[image_prefix + asset.filename] = asset.data
            for sidecar_name, sidecar_data in asset.sidecars.items():
                additions[image_prefix + sidecar_name] = sidecar_data

    info_member = next((member for name, member in inner.items() if name.replace("\\", "/").endswith("/info.bin") or name == "info.bin"), None)
    if info_member is not None:
        missing_catalog = [
            asset.filename
            for asset in assets
            if asset.filename not in existing_image_data and asset.filename.encode("utf-8") not in info_member.data
        ]
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
    parser.add_argument("images_or_output", help="Image source for external mode, or output ZIP when using --library-folder")
    parser.add_argument("output", nargs="?", help="Output ZIP path")
    parser.add_argument("--field-name", default="image_dropdown_1", help="Form field/dropdown name")
    parser.add_argument("--category", default="Image_dropdown", help="Image category name for smartcampaign.xml")
    parser.add_argument("--library-folder", help="Select existing library images by SmartCanvas catalog folder/category")
    parser.add_argument("--library-filter", help="Select existing library images by filename/category substring")
    parser.add_argument("--left", type=float, default=0.0, help="Inserted picture left/X coordinate")
    parser.add_argument("--top", type=float, default=0.0, help="Inserted picture top/Y coordinate")
    parser.add_argument("--width", type=float, help="Inserted picture width")
    parser.add_argument("--height", type=float, help="Inserted picture height")
    parser.add_argument("--units", choices=("points", "inches"), default="points", help="Coordinate units for left/top/width/height")
    args = parser.parse_args(argv)
    if args.library_folder or args.library_filter:
        if args.output is None:
            args.output = args.images_or_output
        else:
            parser.error("when using --library-folder/--library-filter, provide only input and output positionals")
        args.images = None
    else:
        if args.output is None:
            parser.error("external image mode requires input, images, and output positionals")
        args.images = args.images_or_output
    has_explicit_size = args.width is not None or args.height is not None
    convert_measurements(args)
    if not has_explicit_size:
        args.height = 104.0

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
