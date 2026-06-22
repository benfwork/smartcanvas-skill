#!/usr/bin/env python3
"""Inventory and diff SmartCanvas XML structure for schema reverse-engineering."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from export_smartcanvas_catalog import read_package


KEY_XML_FILENAMES = ("template.xml", "template.dhtt", "Document.xml", "description.xml", "scriptsnippets.xml")


def find_xml_files(files: dict[str, bytes], *, all_xml: bool) -> dict[str, bytes]:
    result = {}
    for path, data in files.items():
        basename = Path(path).name
        if all_xml:
            if Path(path).suffix.lower() == ".xml" or basename.endswith(".dhtt"):
                result[path] = data
        elif basename in KEY_XML_FILENAMES:
            result[path] = data
    return dict(sorted(result.items()))


def parse_xml(data: bytes, label: str) -> ET.Element | None:
    try:
        return ET.fromstring(data.decode("utf-8-sig", errors="replace"))
    except ET.ParseError as exc:
        raise SystemExit(f"failed to parse {label}: {exc}") from exc


def walk(element: ET.Element, indexed_path: str = "", schema_path: str = "") -> list[tuple[str, str, ET.Element]]:
    current_indexed = indexed_path or element.tag
    current_schema = schema_path or element.tag
    result = [(current_indexed, current_schema, element)]
    tag_seen: Counter[str] = Counter()
    for child in list(element):
        tag_seen[child.tag] += 1
        child_indexed = f"{current_indexed}/{child.tag}[{tag_seen[child.tag]}]"
        child_schema = f"{current_schema}/{child.tag}"
        result.extend(walk(child, child_indexed, child_schema))
    return result


def text_summary(text: str | None, max_text: int) -> dict[str, object]:
    value = (text or "").strip()
    if not value:
        return {"present": False, "length": 0, "sha256": "", "sample": ""}
    return {
        "present": True,
        "length": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "sample": value[:max_text],
    }


def build_summary(path: Path, *, all_xml: bool = False, max_text: int = 160) -> dict[str, object]:
    source_label, files = read_package(path)
    xml_files = find_xml_files(files, all_xml=all_xml)
    documents: dict[str, object] = {}

    for file_path, data in xml_files.items():
        root = parse_xml(data, file_path)
        assert root is not None
        elements = []
        schema_paths: dict[str, dict[str, object]] = {}
        tag_counts: Counter[str] = Counter()
        attribute_counts: Counter[str] = Counter()
        attribute_values: dict[str, set[str]] = defaultdict(set)

        for indexed_path, schema_path, element in walk(root):
            tag_counts[element.tag] += 1
            attrs = dict(sorted(element.attrib.items()))
            for name, value in attrs.items():
                attribute_counts[name] += 1
                if len(attribute_values[name]) < 12:
                    attribute_values[name].add(value)

            schema = schema_paths.setdefault(
                schema_path,
                {
                    "tag": element.tag,
                    "count": 0,
                    "attribute_names": set(),
                    "child_tags": set(),
                },
            )
            schema["count"] += 1
            schema["attribute_names"].update(attrs)
            schema["child_tags"].update(child.tag for child in list(element))

            elements.append(
                {
                    "path": indexed_path,
                    "schema_path": schema_path,
                    "tag": element.tag,
                    "attributes": attrs,
                    "child_count": len(list(element)),
                    "text": text_summary(element.text, max_text),
                }
            )

        documents[file_path] = {
            "root": root.tag,
            "element_count": len(elements),
            "tag_counts": dict(sorted(tag_counts.items())),
            "attribute_counts": dict(sorted(attribute_counts.items())),
            "attribute_value_samples": {
                name: sorted(values) for name, values in sorted(attribute_values.items())
            },
            "schema_paths": {
                schema_path: {
                    "tag": value["tag"],
                    "count": value["count"],
                    "attribute_names": sorted(value["attribute_names"]),
                    "child_tags": sorted(value["child_tags"]),
                }
                for schema_path, value in sorted(schema_paths.items())
            },
            "elements": elements,
        }

    return {
        "source": source_label,
        "mode": "all_xml" if all_xml else "key_xml",
        "xml_file_count": len(xml_files),
        "documents": documents,
    }


def tag_count_rows(summary: dict[str, object]) -> dict[str, int]:
    rows = {}
    for file_path, document in summary.get("documents", {}).items():
        for tag, count in document.get("tag_counts", {}).items():
            rows[f"{file_path}|{tag}"] = count
    return rows


def schema_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for file_path, document in summary.get("documents", {}).items():
        for schema_path, value in document.get("schema_paths", {}).items():
            rows[f"{file_path}|{schema_path}"] = value
    return rows


def attribute_name_rows(summary: dict[str, object]) -> dict[str, object]:
    rows: dict[str, object] = {}
    for file_path, document in summary.get("documents", {}).items():
        for schema_path, schema in document.get("schema_paths", {}).items():
            for attribute_name in schema.get("attribute_names", []):
                rows[f"{file_path}|{schema_path}|@{attribute_name}"] = True
    return rows


def exact_element_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for file_path, document in summary.get("documents", {}).items():
        for element in document.get("elements", []):
            key = f"{file_path}|{element['path']}"
            rows[key] = {
                "schema_path": element["schema_path"],
                "tag": element["tag"],
                "attributes": element["attributes"],
                "child_count": element["child_count"],
                "text": element["text"],
            }
    return rows


def exact_attribute_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for file_path, document in summary.get("documents", {}).items():
        for element in document.get("elements", []):
            for name, value in element.get("attributes", {}).items():
                rows[f"{file_path}|{element['path']}|@{name}"] = value
    return rows


def map_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_keys = set(before)
    after_keys = set(after)
    changed = []
    for key in sorted(before_keys & after_keys):
        if before[key] != after[key]:
            changed.append({"key": key, "before": before[key], "after": after[key]})
    return {
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "changed": changed,
    }


def build_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    return {
        "before": before["source"],
        "after": after["source"],
        "mode": [before.get("mode"), after.get("mode")],
        "xml_file_count": [before.get("xml_file_count"), after.get("xml_file_count")],
        "tag_counts": map_delta(tag_count_rows(before), tag_count_rows(after)),
        "schema_paths": map_delta(schema_rows(before), schema_rows(after)),
        "attribute_names": map_delta(attribute_name_rows(before), attribute_name_rows(after)),
        "exact_elements": map_delta(exact_element_rows(before), exact_element_rows(after)),
        "exact_attributes": map_delta(exact_attribute_rows(before), exact_attribute_rows(after)),
    }


def print_summary(summary: dict[str, object], limit: int) -> None:
    print(f"Source: {summary['source']}")
    print(f"Mode: {summary['mode']}")
    print(f"XML files: {summary['xml_file_count']}")
    for file_path, document in summary.get("documents", {}).items():
        print(f"\n{file_path}")
        print(f"  root: {document['root']}")
        print(f"  elements: {document['element_count']}")
        print(f"  schema paths: {len(document['schema_paths'])}")
        print(f"  unique tags: {len(document['tag_counts'])}")
        for tag, count in list(document["tag_counts"].items())[:limit]:
            print(f"    {tag}: {count}")


def print_delta(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    print(f"XML files: {delta['xml_file_count'][0]} -> {delta['xml_file_count'][1]}")
    print_map_delta("Tag Counts", delta["tag_counts"], limit)
    print_map_delta("Schema Paths", delta["schema_paths"], limit)
    print_map_delta("Attribute Names", delta["attribute_names"], limit)
    print_map_delta("Exact Elements", delta["exact_elements"], limit)
    print_map_delta("Exact Attributes", delta["exact_attributes"], limit)


def print_map_delta(title: str, delta: dict[str, object], limit: int) -> None:
    print(f"\n{title}")
    print(f"  added: {len(delta['added'])}")
    for item in delta["added"][:limit]:
        print(f"  + {item}")
    print(f"  removed: {len(delta['removed'])}")
    for item in delta["removed"][:limit]:
        print(f"  - {item}")
    print(f"  changed: {len(delta['changed'])}")
    for item in delta["changed"][:limit]:
        print(f"  * {item['key']}")
        print(f"    before: {item['before']}")
        print(f"    after:  {item['after']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Outer export folder, inner campaign zip, or extracted inner folder")
    parser.add_argument("after", nargs="?", type=Path, help="Optional after package to compare with path")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON summary or delta to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--all-xml", action="store_true", help="Inventory all XML files instead of only key SmartCanvas XML")
    parser.add_argument("--max-text", type=int, default=160)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")
    if args.after and not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    before = build_summary(args.path, all_xml=args.all_xml, max_text=args.max_text)
    result = build_delta(before, build_summary(args.after, all_xml=args.all_xml, max_text=args.max_text)) if args.after else before

    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.format == "text":
        if args.after:
            print_delta(result, args.limit)
        else:
            print_summary(result, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
