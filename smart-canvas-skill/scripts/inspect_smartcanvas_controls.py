#!/usr/bin/env python3
"""Inspect SmartCanvas XML/control surfaces for dropdown reverse-engineering."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from export_smartcanvas_catalog import read_package
from inspect_smartcanvas_package import summarize_info_bin


KEY_XML_FILENAMES = ("template.xml", "template.dhtt", "Document.xml", "description.xml", "scriptsnippets.xml")
COMPONENT_SECTIONS = ("Variables", "ActionButtons", "Images", "IFrames", "TextInputs", "Templates", "Resources", "FileUploads")
DOCMODEL_ATTRS = (
    "Class",
    "ImageSelector",
    "ImageCategories",
    "ShowImageBrowser",
    "EnableImageUpload",
    "LockImageReplace",
    "EnableCropping",
    "EnableKeepRatio",
    "SelectedTextStyleVariations",
    "LayerID",
)
INTERESTING_ATTR_RE = re.compile(
    r"image|select|selection|option|drop|combo|category|class|upload|variable|field|caption|source",
    re.IGNORECASE,
)
CSS_DYNAMIC_CLASS_RE = re.compile(r"\.Dynamic[A-Za-z0-9_-]+")
CSS_BLOCK_COMMENT_RE = re.compile(r"/\*\s*Start\s+([^*]+?)\s*\*/")


def find_by_basename(files: dict[str, bytes], basename: str) -> tuple[str, bytes] | None:
    matches = sorted((path, data) for path, data in files.items() if Path(path).name == basename)
    return matches[0] if matches else None


def parse_xml(data: bytes, label: str) -> ET.Element | None:
    try:
        return ET.fromstring(data.decode("utf-8-sig", errors="replace"))
    except ET.ParseError as exc:
        raise SystemExit(f"failed to parse {label}: {exc}") from exc


def short_attrs(element: ET.Element, keys: tuple[str, ...]) -> dict[str, str]:
    return {key: element.attrib.get(key, "") for key in keys if key in element.attrib}


def summarize_template_xml(files: dict[str, bytes]) -> dict[str, object]:
    found = find_by_basename(files, "template.xml")
    if not found:
        return {"present": False}
    path, data = found
    root = parse_xml(data, path)
    assert root is not None

    docs = []
    for doc in root.findall("./Doc"):
        pages = doc.findall("./DocumentPage")
        docmodels = list(doc.iter("DocModel"))
        docs.append(
            {
                "id": doc.attrib.get("ID", ""),
                "name": doc.attrib.get("Name", ""),
                "doc_type": doc.attrib.get("DocType", ""),
                "width": doc.attrib.get("Width", ""),
                "height": doc.attrib.get("Height", ""),
                "page_count": len(pages),
                "layer_count": len(doc.findall("./DocLayers/DocLayer")),
                "doc_model_count": len(docmodels),
                "doc_models": [short_attrs(model, DOCMODEL_ATTRS) for model in docmodels],
            }
        )

    template_settings = []
    for settings in root.iter("TemplateSettings"):
        template_settings.append(
            short_attrs(settings, ("DisplayName", "ImageName", "ImageSource", "PlaceholderName", "ShowExportAsTemplate"))
        )

    return {
        "present": True,
        "path": path,
        "root": root.tag,
        "root_attributes": short_attrs(root, ("Version", "DesignVersion", "CampaignName", "Name", "ID")),
        "tag_counts": tag_counts(root),
        "docs": docs,
        "template_settings": template_settings,
        "interesting_attributes": interesting_attributes(root),
    }


def summarize_dhtt(files: dict[str, bytes]) -> dict[str, object]:
    found = find_by_basename(files, "template.dhtt")
    if not found:
        return {"present": False}
    path, data = found
    root = parse_xml(data, path)
    assert root is not None

    sections = {}
    for section_name in COMPONENT_SECTIONS:
        section = root.find(f"./{section_name}")
        if section is None:
            sections[section_name] = {"present": False, "child_count": 0, "child_tags": {}, "children": []}
            continue
        child_tags = Counter(child.tag for child in list(section))
        sections[section_name] = {
            "present": True,
            "attributes": dict(sorted(section.attrib.items())),
            "child_count": len(list(section)),
            "child_tags": dict(sorted(child_tags.items())),
            "children": section_children(section),
        }

    templates = []
    for template in root.findall("./Templates/Template"):
        templates.append(
            short_attrs(
                template,
                ("Name", "DisplayName", "JField", "Value", "Behaviour", "TemplateModus", "ConditionX", "ShowHiddenObjects"),
            )
        )

    return {
        "present": True,
        "path": path,
        "root": root.tag,
        "root_attributes": short_attrs(root, ("Version", "TimeStamp", "NeededLicenses", "RenderMode", "DesignerAccountId")),
        "tag_counts": tag_counts(root),
        "sections": sections,
        "templates": templates,
        "interesting_attributes": interesting_attributes(root),
    }


def summarize_document_xml(files: dict[str, bytes]) -> dict[str, object]:
    found = find_by_basename(files, "Document.xml")
    if not found:
        return {"present": False}
    path, data = found
    root = parse_xml(data, path)
    assert root is not None

    documents = []
    for document in root.findall("./Document"):
        pages = []
        for page in document.findall("./Page"):
            frames = []
            for frame in page.findall("./Frame"):
                frames.append(short_attrs(frame, ("ID", "Caption", "Width", "Height")))
            pages.append(
                {
                    "name": page.attrib.get("Name", ""),
                    "width": page.attrib.get("Width", ""),
                    "height": page.attrib.get("Height", ""),
                    "frames": frames,
                }
            )
        documents.append({"name": document.attrib.get("Name", ""), "pages": pages})

    return {
        "present": True,
        "path": path,
        "root": root.tag,
        "root_attributes": short_attrs(root, ("OriginAccountID", "OriginCampaign", "OriginDesign", "Version")),
        "tag_counts": tag_counts(root),
        "documents": documents,
        "interesting_attributes": interesting_attributes(root),
    }


def summarize_css(files: dict[str, bytes]) -> dict[str, object]:
    found = find_by_basename(files, "css.css")
    if not found:
        return {"present": False}
    path, data = found
    text = data.decode("utf-8-sig", errors="replace")
    dynamic_classes = sorted(set(match.group(0)[1:] for match in CSS_DYNAMIC_CLASS_RE.finditer(text)))
    block_names = [match.group(1).strip() for match in CSS_BLOCK_COMMENT_RE.finditer(text)]
    return {
        "present": True,
        "path": path,
        "dynamic_class_count": len(dynamic_classes),
        "dynamic_classes": dynamic_classes,
        "block_names": block_names,
    }


def tag_counts(root: ET.Element) -> dict[str, int]:
    counts = Counter(element.tag for element in root.iter())
    return dict(sorted(counts.items()))


def section_children(section: ET.Element) -> list[dict[str, object]]:
    children = []
    for index, child in enumerate(list(section), start=1):
        children.append(
            {
                "index": index,
                "tag": child.tag,
                "attributes": dict(sorted(child.attrib.items())),
                "child_count": len(list(child)),
            }
        )
    return children


def interesting_attributes(root: ET.Element) -> list[dict[str, object]]:
    matches = []
    for path, element in walk(root):
        attrs = {
            key: value
            for key, value in sorted(element.attrib.items())
            if INTERESTING_ATTR_RE.search(key) or (value and INTERESTING_ATTR_RE.search(value))
        }
        if attrs:
            matches.append({"path": path, "tag": element.tag, "attributes": attrs})
    return matches


def walk(element: ET.Element, path: str = "") -> list[tuple[str, ET.Element]]:
    current = path or element.tag
    result = [(current, element)]
    tag_seen: Counter[str] = Counter()
    for child in list(element):
        tag_seen[child.tag] += 1
        child_path = f"{current}/{child.tag}[{tag_seen[child.tag]}]"
        result.extend(walk(child, child_path))
    return result


def xml_catalog_references(files: dict[str, bytes], catalog_names: list[str]) -> dict[str, list[str]]:
    key_texts = {}
    for basename in KEY_XML_FILENAMES:
        found = find_by_basename(files, basename)
        if found:
            key_texts[found[0]] = found[1].decode("utf-8-sig", errors="replace")
    references: dict[str, list[str]] = {}
    for caption in catalog_names:
        paths = sorted(path for path, text in key_texts.items() if caption and caption in text)
        if paths:
            references[caption] = paths
    return references


def build_summary(path: Path) -> dict[str, object]:
    source_label, files = read_package(path)
    catalog_names: list[str] = []
    if "info.bin" in files:
        info_summary = summarize_info_bin(files["info.bin"])
        if not info_summary.get("parse_error"):
            catalog_names = [str(name) for name in info_summary.get("image_names", [])]

    return {
        "source": source_label,
        "file_count": len(files),
        "template_xml": summarize_template_xml(files),
        "template_dhtt": summarize_dhtt(files),
        "document_xml": summarize_document_xml(files),
        "css": summarize_css(files),
        "catalog_image_count": len(catalog_names),
        "catalog_image_xml_references": xml_catalog_references(files, catalog_names),
    }


def print_text_report(summary: dict[str, object]) -> None:
    print(f"Source: {summary['source']}")
    print(f"Files: {summary['file_count']}")
    print(f"Catalog images: {summary['catalog_image_count']}")
    refs = summary["catalog_image_xml_references"]
    print(f"Catalog image names referenced in key XML: {len(refs)}")

    template = summary["template_xml"]
    print("\ntemplate.xml")
    if not template["present"]:
        print("  missing")
    else:
        print(f"  root: {template['root']} {template['root_attributes']}")
        print(f"  docs: {len(template['docs'])}")
        for doc in template["docs"]:
            print(
                f"    - {doc['name']} ({doc['doc_type']}): pages={doc['page_count']} "
                f"layers={doc['layer_count']} docmodels={doc['doc_model_count']}"
            )
            for index, model in enumerate(doc["doc_models"], start=1):
                print(f"      DocModel {index}: {model}")
        print(f"  interesting attrs: {len(template['interesting_attributes'])}")

    dhtt = summary["template_dhtt"]
    print("\ntemplate.dhtt")
    if not dhtt["present"]:
        print("  missing")
    else:
        print(f"  root: {dhtt['root']} {dhtt['root_attributes']}")
        for name, section in dhtt["sections"].items():
            if section["present"]:
                print(f"  {name}: children={section['child_count']} tags={section['child_tags']}")
                for child in section.get("children", [])[:5]:
                    print(f"    child {child['index']}: {child['tag']} {child['attributes']}")
                if len(section.get("children", [])) > 5:
                    print(f"    ... {len(section['children']) - 5} more children")
            else:
                print(f"  {name}: missing")
        print(f"  templates: {len(dhtt['templates'])}")

    document = summary["document_xml"]
    print("\nDocument.xml")
    if not document["present"]:
        print("  missing")
    else:
        for document_entry in document["documents"]:
            print(f"  document: {document_entry['name']} pages={len(document_entry['pages'])}")
            for page in document_entry["pages"]:
                print(f"    page {page['name']}: {page['width']} x {page['height']} frames={len(page['frames'])}")

    css = summary["css"]
    print("\ncss.css")
    if not css["present"]:
        print("  missing")
    else:
        print(f"  dynamic classes: {css['dynamic_class_count']}")
        for class_name in css["dynamic_classes"]:
            print(f"    - {class_name}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Outer export folder, inner campaign zip, or extracted inner folder")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON summary to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")

    summary = build_summary(args.path)
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif args.format == "text":
        print_text_report(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
