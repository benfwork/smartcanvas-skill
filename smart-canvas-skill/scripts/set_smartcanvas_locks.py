#!/usr/bin/env python3
"""Lock or unlock SmartCanvas template layers and objects."""

from __future__ import annotations

import argparse
import copy
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


LOCK_ATTRS = (
    "LockPosition",
    "LockSize",
    "LockTextEdit",
    "LockImageReplace",
    "LockInFront",
)
ENABLE_ATTRS = (
    "EnableRemove",
    "EnableRotate",
    "EnableCropping",
)


@dataclass
class ZipMember:
    name: str
    data: bytes
    info: zipfile.ZipInfo | None = None


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data.decode("utf-8-sig"))


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True)


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def read_package(path: Path) -> tuple[dict[str, ZipMember], str | None, dict[str, ZipMember]]:
    with zipfile.ZipFile(path) as outer_zip:
        outer = {info.filename: ZipMember(info.filename, outer_zip.read(info), info) for info in outer_zip.infolist()}
    inner_name = next(
        (
            name
            for name in outer
            if name.replace("\\", "/").lower().startswith("admin/")
            and name.lower().endswith(".zip")
        ),
        None,
    )
    inner_data = outer[inner_name].data if inner_name else path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(inner_data)) as inner_zip:
        inner = {info.filename: ZipMember(info.filename, inner_zip.read(info), info) for info in inner_zip.infolist()}
    return outer, inner_name, inner


def find_inner_files(inner: dict[str, ZipMember], basename: str) -> list[str]:
    return sorted(
        name
        for name in inner
        if name.replace("\\", "/").endswith("/" + basename) or name == basename
    )


def write_zip(path: Path, members: dict[str, ZipMember]) -> None:
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


def normalize(value: str) -> str:
    return value.casefold()


def element_search_text(element: ET.Element) -> str:
    values: list[str] = []
    for elem in element.iter():
        values.extend(str(value) for value in elem.attrib.values())
        if elem.text:
            values.append(elem.text)
        if elem.tail:
            values.append(elem.tail)
    return "\n".join(values)


def collect_layer_ids(roots: list[ET.Element], layer_names: list[str]) -> set[str]:
    wanted_names = {normalize(name) for name in layer_names}
    ids: set[str] = set()
    for root in roots:
        for elem in root.iter():
            if local_name(elem) not in {"Layer", "DocLayer"}:
                continue
            display_name = elem.get("DisplayName") or elem.get("Name") or ""
            if normalize(display_name) in wanted_names:
                layer_id = elem.get("ID") or elem.get("Name")
                if layer_id:
                    ids.add(layer_id)
                if elem.get("IsDefault", "").casefold() == "true":
                    ids.add("")
    return ids


def docmodel_matches(
    docmodel: ET.Element,
    all_layers: bool,
    layer_ids: set[str],
    contains: list[str],
) -> bool:
    if all_layers:
        return True
    if layer_ids and docmodel.get("LayerID") in layer_ids:
        return True
    if contains:
        haystack = normalize(element_search_text(docmodel))
        return any(normalize(needle) in haystack for needle in contains)
    return False


def layer_matches(layer: ET.Element, all_layers: bool, layer_names: list[str], contains: list[str]) -> bool:
    if all_layers:
        return True
    display_name = layer.get("DisplayName") or layer.get("Name") or ""
    if layer_names and normalize(display_name) in {normalize(name) for name in layer_names}:
        return True
    if contains:
        haystack = normalize(element_search_text(layer))
        return any(normalize(needle) in haystack for needle in contains)
    return False


def set_layer_lock(layer: ET.Element, locked: bool) -> bool:
    if locked:
        if layer.get("IsLocked") == "true":
            return False
        layer.set("IsLocked", "true")
        return True
    if "IsLocked" in layer.attrib:
        del layer.attrib["IsLocked"]
        return True
    return False


def set_docmodel_lock(docmodel: ET.Element, locked: bool) -> bool:
    changed = False
    lock_value = "True" if locked else "False"
    enable_value = "False" if locked else "True"
    for attr in LOCK_ATTRS:
        if docmodel.get(attr) != lock_value:
            docmodel.set(attr, lock_value)
            changed = True
    for attr in ENABLE_ATTRS:
        if attr in docmodel.attrib and docmodel.get(attr) != enable_value:
            docmodel.set(attr, enable_value)
            changed = True
    return changed


def patch_document_xml(
    data: bytes,
    locked: bool,
    all_layers: bool,
    layer_names: list[str],
    contains: list[str],
) -> tuple[bytes, int, int]:
    root = parse_xml(data)
    matched = 0
    changed = 0
    for elem in root.iter():
        if local_name(elem) != "Layer":
            continue
        if not layer_matches(elem, all_layers, layer_names, contains):
            continue
        matched += 1
        if set_layer_lock(elem, locked):
            changed += 1
    return xml_bytes(root), matched, changed


def patch_template_xml(
    data: bytes,
    locked: bool,
    all_layers: bool,
    layer_ids: set[str],
    contains: list[str],
) -> tuple[bytes, int, int]:
    root = parse_xml(data)
    matched = 0
    changed = 0
    for elem in root.iter():
        if local_name(elem) != "DocModel":
            continue
        if not docmodel_matches(elem, all_layers, layer_ids, contains):
            continue
        matched += 1
        if set_docmodel_lock(elem, locked):
            changed += 1
    return xml_bytes(root), matched, changed


def patch_package(args: argparse.Namespace) -> tuple[int, int, int, int, list[str]]:
    outer, inner_name, inner = read_package(Path(args.input))
    template_names = find_inner_files(inner, "template.xml")
    if not template_names:
        raise ValueError("inner campaign zip does not contain template.xml")

    xml_roots = [parse_xml(inner[name].data) for name in template_names]
    for document_name in find_inner_files(inner, "Document.xml"):
        xml_roots.append(parse_xml(inner[document_name].data))

    layer_ids = collect_layer_ids(xml_roots, args.layer_name)
    warnings: list[str] = []
    if args.layer_name and not layer_ids:
        warnings.append("no matching layer names found: " + ", ".join(args.layer_name))

    replacements: dict[str, bytes] = {}
    total_docmodel_matched = 0
    total_docmodel_changed = 0
    for template_name in template_names:
        data, matched, changed = patch_template_xml(
            inner[template_name].data,
            args.state == "locked",
            args.all,
            layer_ids,
            args.contains,
        )
        total_docmodel_matched += matched
        total_docmodel_changed += changed
        if changed:
            replacements[template_name] = data

    total_layer_matched = 0
    total_layer_changed = 0
    for document_name in find_inner_files(inner, "Document.xml"):
        data, matched, changed = patch_document_xml(
            inner[document_name].data,
            args.state == "locked",
            args.all,
            args.layer_name,
            args.contains,
        )
        total_layer_matched += matched
        total_layer_changed += changed
        if changed:
            replacements[document_name] = data

    if total_docmodel_matched == 0:
        warnings.append("no DocModel objects matched the requested selectors")
    if total_layer_matched == 0:
        warnings.append("no Document.xml layers matched the requested selectors")

    inner_bytes = create_inner_zip(inner, replacements)
    output_path = Path(args.output)
    if inner_name:
        outer[inner_name].data = inner_bytes
        write_zip(output_path, outer)
    else:
        output_path.write_bytes(inner_bytes)
    return total_docmodel_matched, total_docmodel_changed, total_layer_matched, total_layer_changed, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lock or unlock SmartCanvas template layers and objects.")
    parser.add_argument("input", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", help="Output ZIP path")
    parser.add_argument("--state", choices=("locked", "unlocked"), required=True)
    parser.add_argument("--all", action="store_true", help="Apply to every layer in Document.xml and every DocModel object in template.xml")
    parser.add_argument("--layer-name", action="append", default=[], help="Apply to this layer display name and objects assigned to it; repeatable")
    parser.add_argument("--contains", action="append", default=[], help="Apply to layers/objects whose attributes/text contain this value; repeatable")
    args = parser.parse_args(argv)

    if not args.all and not args.layer_name and not args.contains:
        parser.error("provide --all, --layer-name, or --contains")

    try:
        docmodel_matched, docmodel_changed, layer_matched, layer_changed, warnings = patch_package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    print(f"Matched {layer_matched} Document.xml layer(s); changed {layer_changed}.")
    print(f"Matched {docmodel_matched} template.xml DocModel object(s); changed {docmodel_changed}.")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
