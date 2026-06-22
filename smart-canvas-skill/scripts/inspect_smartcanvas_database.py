#!/usr/bin/env python3
"""Inspect SmartCanvas database columns, bindings, and field references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from export_smartcanvas_catalog import read_package
from inspect_smartcanvas_package import summarize_info_bin


KEY_XML_FILENAMES = ("template.xml", "template.dhtt", "Document.xml", "description.xml", "scriptsnippets.xml")
FIELD_REF_RE = re.compile(r"\[\[([^\]]+)\]\]")
BINDING_ATTR_RE = re.compile(
    r"(field|column|condition|relation|key|value|script|data|template|record)",
    re.IGNORECASE,
)


def find_by_basename(files: dict[str, bytes], basename: str) -> tuple[str, bytes] | None:
    matches = sorted((path, data) for path, data in files.items() if Path(path).name == basename)
    return matches[0] if matches else None


def parse_xml(data: bytes, label: str) -> ET.Element | None:
    try:
        return ET.fromstring(data.decode("utf-8-sig", errors="replace"))
    except ET.ParseError as exc:
        raise SystemExit(f"failed to parse {label}: {exc}") from exc


def walk(element: ET.Element, path: str = "") -> list[tuple[str, ET.Element]]:
    current = path or element.tag
    result = [(current, element)]
    tag_seen: Counter[str] = Counter()
    for child in list(element):
        tag_seen[child.tag] += 1
        child_path = f"{current}/{child.tag}[{tag_seen[child.tag]}]"
        result.extend(walk(child, child_path))
    return result


def extract_template_columns(files: dict[str, bytes]) -> dict[str, object]:
    found = find_by_basename(files, "template.xml")
    if not found:
        return {"present": False, "columns": []}
    path, data = found
    root = parse_xml(data, path)
    assert root is not None

    columns = []
    for index, column in enumerate(root.findall("./DatabaseColumns/DatabaseColumn"), start=1):
        columns.append(
            {
                "index": index,
                "name": column.attrib.get("Name", ""),
                "is_included": column.attrib.get("IsIncluded", ""),
                "attributes": dict(sorted(column.attrib.items())),
            }
        )
    return {"present": True, "path": path, "columns": columns}


def extract_xml_binding_signals(files: dict[str, bytes], known_fields: set[str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    bindings: list[dict[str, object]] = []
    field_refs: list[dict[str, object]] = []

    for basename in KEY_XML_FILENAMES:
        found = find_by_basename(files, basename)
        if not found:
            continue
        file_path, data = found
        text = data.decode("utf-8-sig", errors="replace")
        root = parse_xml(data, file_path)
        assert root is not None

        for path, element in walk(root):
            for attr_name, attr_value in sorted(element.attrib.items()):
                if BINDING_ATTR_RE.search(attr_name) or FIELD_REF_RE.search(attr_value):
                    bindings.append(
                        {
                            "file": file_path,
                            "path": path,
                            "tag": element.tag,
                            "attribute": attr_name,
                            "value": attr_value,
                            "references": extract_refs(attr_value, known_fields),
                        }
                    )
                for ref in extract_refs(attr_value, known_fields):
                    field_refs.append(
                        {
                            "file": file_path,
                            "path": path,
                            "tag": element.tag,
                            "source": f"@{attr_name}",
                            **ref,
                        }
                    )
            if element.text and FIELD_REF_RE.search(element.text):
                for ref in extract_refs(element.text, known_fields):
                    field_refs.append(
                        {
                            "file": file_path,
                            "path": path,
                            "tag": element.tag,
                            "source": "text",
                            **ref,
                        }
                    )

        # Keep a cheap file-level count for raw strings that might sit outside parsed XML nodes.
        for raw_ref in FIELD_REF_RE.findall(text):
            raw_ref = raw_ref.strip()
            if not raw_ref:
                continue
            if not any(item["file"] == file_path and item["raw"] == raw_ref for item in field_refs):
                field_refs.append(
                    {
                        "file": file_path,
                        "path": "[raw-text]",
                        "tag": "",
                        "source": "raw",
                        "raw": raw_ref,
                        "field": normalize_ref(raw_ref),
                        "known_column": normalize_ref(raw_ref) in known_fields,
                    }
                )

    return bindings, field_refs


def extract_refs(value: str, known_fields: set[str]) -> list[dict[str, object]]:
    refs = []
    for raw_ref in FIELD_REF_RE.findall(value):
        raw_ref = raw_ref.strip()
        if not raw_ref:
            continue
        field = normalize_ref(raw_ref)
        refs.append({"raw": raw_ref, "field": field, "known_column": field in known_fields})
    return refs


def normalize_ref(raw_ref: str) -> str:
    # Most observed references are plain [[FieldName]]. Leave complex formulas visible in raw.
    return raw_ref.strip()


def build_summary(path: Path) -> dict[str, object]:
    source_label, files = read_package(path)
    template_columns = extract_template_columns(files)
    xml_column_names = [column["name"] for column in template_columns.get("columns", []) if column.get("name")]

    info_columns: list[str] = []
    info_parse_error = None
    if "info.bin" in files:
        info_summary = summarize_info_bin(files["info.bin"])
        info_parse_error = info_summary.get("parse_error")
        if not info_parse_error:
            info_columns = [str(name) for name in info_summary.get("database_columns", [])]

    known_fields = set(xml_column_names) | set(info_columns)
    bindings, field_refs = extract_xml_binding_signals(files, known_fields)
    ref_counts: dict[str, int] = defaultdict(int)
    unknown_ref_counts: dict[str, int] = defaultdict(int)
    for ref in field_refs:
        field = str(ref.get("field", ""))
        if field:
            ref_counts[field] += 1
            if not ref.get("known_column"):
                unknown_ref_counts[field] += 1

    xml_set = set(xml_column_names)
    info_set = set(info_columns)
    aligned_xml_names = [name for name in xml_column_names if name]
    first_order_mismatch = first_mismatch(aligned_xml_names, info_columns)

    return {
        "source": source_label,
        "file_count": len(files),
        "template_columns": template_columns,
        "info_bin_columns": {
            "present": "info.bin" in files,
            "parse_error": info_parse_error,
            "columns": info_columns,
        },
        "alignment": {
            "template_column_count": len(template_columns.get("columns", [])),
            "template_named_column_count": len(xml_column_names),
            "template_empty_name_count": len(template_columns.get("columns", [])) - len(xml_column_names),
            "info_bin_column_count": len(info_columns),
            "template_names_missing_from_info_bin": sorted(xml_set - info_set),
            "info_bin_names_missing_from_template": sorted(info_set - xml_set),
            "named_column_order_matches_info_bin": aligned_xml_names == info_columns,
            "first_order_mismatch": first_order_mismatch,
            "included_columns": [
                column
                for column in template_columns.get("columns", [])
                if str(column.get("is_included", "")).lower() == "true"
            ],
        },
        "xml_binding_attributes": bindings,
        "field_references": field_refs,
        "field_reference_counts": dict(sorted(ref_counts.items())),
        "unknown_field_reference_counts": dict(sorted(unknown_ref_counts.items())),
    }


def first_mismatch(left: list[str], right: list[str]) -> dict[str, object] | None:
    for index, (left_value, right_value) in enumerate(zip(left, right), start=1):
        if left_value != right_value:
            return {"index": index, "template": left_value, "info_bin": right_value}
    if len(left) != len(right):
        return {"index": min(len(left), len(right)) + 1, "template": len(left), "info_bin": len(right)}
    return None


def column_rows(summary: dict[str, object], source: str) -> dict[str, object]:
    if source == "template":
        rows = {}
        for column in (summary.get("template_columns") or {}).get("columns", []):
            name = column.get("name") or f"[empty]#{column.get('index')}"
            rows[str(name)] = {key: value for key, value in column.items() if key != "index"}
        return rows
    return {name: index for index, name in enumerate((summary.get("info_bin_columns") or {}).get("columns", []), start=1)}


def binding_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for item in summary.get("xml_binding_attributes", []):
        key = f"{item.get('file')}|{item.get('path')}|{item.get('attribute')}"
        rows[key] = item.get("value")
    return rows


def reference_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for item in summary.get("field_references", []):
        key = f"{item.get('file')}|{item.get('path')}|{item.get('source')}|{item.get('raw')}"
        rows[key] = {"field": item.get("field"), "known_column": item.get("known_column")}
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
        "alignment": {
            "template_column_count": [
                before["alignment"]["template_column_count"],
                after["alignment"]["template_column_count"],
            ],
            "info_bin_column_count": [
                before["alignment"]["info_bin_column_count"],
                after["alignment"]["info_bin_column_count"],
            ],
            "named_column_order_matches_info_bin": [
                before["alignment"]["named_column_order_matches_info_bin"],
                after["alignment"]["named_column_order_matches_info_bin"],
            ],
        },
        "template_columns": map_delta(column_rows(before, "template"), column_rows(after, "template")),
        "info_bin_columns": map_delta(column_rows(before, "info_bin"), column_rows(after, "info_bin")),
        "xml_binding_attributes": map_delta(binding_rows(before), binding_rows(after)),
        "field_references": map_delta(reference_rows(before), reference_rows(after)),
        "field_reference_counts": map_delta(
            before.get("field_reference_counts", {}),
            after.get("field_reference_counts", {}),
        ),
        "unknown_field_reference_counts": map_delta(
            before.get("unknown_field_reference_counts", {}),
            after.get("unknown_field_reference_counts", {}),
        ),
    }


def print_summary(summary: dict[str, object]) -> None:
    alignment = summary["alignment"]
    print(f"Source: {summary['source']}")
    print(f"Files: {summary['file_count']}")
    print("\nDatabase Columns")
    print(f"  template columns: {alignment['template_column_count']}")
    print(f"  template named columns: {alignment['template_named_column_count']}")
    print(f"  info.bin columns: {alignment['info_bin_column_count']}")
    print(f"  named order matches info.bin: {alignment['named_column_order_matches_info_bin']}")
    print(f"  template names missing from info.bin: {len(alignment['template_names_missing_from_info_bin'])}")
    print(f"  info.bin names missing from template: {len(alignment['info_bin_names_missing_from_template'])}")
    print(f"  included columns: {len(alignment['included_columns'])}")
    for column in alignment["included_columns"][:20]:
        print(f"    - #{column.get('index')} {column.get('name')!r} {column.get('attributes')}")

    print("\nBindings")
    print(f"  binding-looking XML attributes: {len(summary['xml_binding_attributes'])}")
    print(f"  field references: {len(summary['field_references'])}")
    print(f"  unique referenced fields: {len(summary['field_reference_counts'])}")
    print(f"  unknown referenced fields: {len(summary['unknown_field_reference_counts'])}")
    for field, count in list(summary["field_reference_counts"].items())[:40]:
        known = "known" if field not in summary["unknown_field_reference_counts"] else "unknown"
        print(f"    - {field}: {count} ({known})")


def print_delta(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    alignment = delta["alignment"]
    print("\nDatabase Columns")
    print(f"  template columns: {alignment['template_column_count'][0]} -> {alignment['template_column_count'][1]}")
    print(f"  info.bin columns: {alignment['info_bin_column_count'][0]} -> {alignment['info_bin_column_count'][1]}")
    print(
        "  named order matches info.bin: "
        f"{alignment['named_column_order_matches_info_bin'][0]} -> {alignment['named_column_order_matches_info_bin'][1]}"
    )
    print_map_delta("Template Columns", delta["template_columns"], limit)
    print_map_delta("info.bin Columns", delta["info_bin_columns"], limit)
    print_map_delta("XML Binding Attributes", delta["xml_binding_attributes"], limit)
    print_map_delta("Field References", delta["field_references"], limit)
    print_map_delta("Field Reference Counts", delta["field_reference_counts"], limit)
    print_map_delta("Unknown Field Reference Counts", delta["unknown_field_reference_counts"], limit)


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
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")
    if args.after and not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    if args.after:
        result = build_delta(build_summary(args.path), build_summary(args.after))
    else:
        result = build_summary(args.path)

    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.format == "text":
        if args.after:
            print_delta(result, args.limit)
        else:
            print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
