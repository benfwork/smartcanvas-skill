#!/usr/bin/env python3
"""Create an experimental SmartCanvas package with a candidate image dropdown control."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from make_smartcanvas_image_dropdown_blueprint import build_blueprint, slugify
from smartcanvas_package_workspace import pack, unpack
from validate_smartcanvas_image_assets import build_summary as build_readiness_summary


MANIFEST_VERSION = "smartcanvas-image-dropdown-experiment-v1"


def parse_xml(path: Path) -> ET.ElementTree:
    try:
        return ET.parse(path)
    except ET.ParseError as exc:
        raise SystemExit(f"failed to parse {path}: {exc}") from exc


def write_xml(path: Path, tree: ET.ElementTree) -> None:
    tree.write(path, encoding="utf-8", xml_declaration=False, short_empty_elements=True)


def choose_group(blueprint: dict[str, object], group_filter: str | None) -> dict[str, object]:
    groups = blueprint.get("groups", [])
    if group_filter:
        matches = [group for group in groups if group_filter.lower() in str(group.get("group_key", "")).lower()]
    else:
        matches = list(groups)
    if not matches:
        raise SystemExit(f"no candidate dropdown group matched: {group_filter or '(none)'}")
    if len(matches) > 1:
        names = ", ".join(str(group.get("group_key")) for group in matches)
        raise SystemExit(f"group is ambiguous; pass --group with one of: {names}")
    return matches[0]


def choose_option(group: dict[str, object], caption: str | None) -> dict[str, object]:
    options = list(group.get("options", []))
    if not options:
        raise SystemExit(f"group has no options: {group.get('group_key')}")
    if caption:
        for option in options:
            captions = [str(value) for value in option.get("all_captions", [])]
            if caption == option.get("representative_caption") or caption in captions:
                return option
        raise SystemExit(f"caption is not in group {group.get('group_key')}: {caption}")
    return options[0]


def choose_category(option: dict[str, object], explicit_category: str | None) -> str:
    if explicit_category is not None:
        return explicit_category
    categories = [str(value) for value in option.get("categories", []) if str(value) != "[uncategorized]"]
    return categories[0] if categories else ""


def select_docmodel(root: ET.Element, target: str, index: int) -> tuple[ET.Element, dict[str, object]]:
    candidates: list[tuple[ET.Element, ET.Element, str]] = []
    for doc in root.findall("./Doc"):
        doc_type = doc.attrib.get("DocType", "")
        doc_name = doc.attrib.get("Name", "")
        for model in doc.iter("DocModel"):
            candidates.append((doc, model, doc_type))

    if target == "dynamic":
        filtered = [(doc, model, doc_type) for doc, model, doc_type in candidates if doc_type == "DynamicDocument"]
    elif target == "storyboard":
        filtered = [(doc, model, doc_type) for doc, model, doc_type in candidates if doc_type == "Whiteboard"]
    else:
        filtered = candidates
    if not filtered:
        raise SystemExit(f"no DocModel candidates found for --target-doc {target}")
    if index < 1 or index > len(filtered):
        raise SystemExit(f"--docmodel-index {index} is out of range; {len(filtered)} candidate(s) found")
    doc, model, doc_type = filtered[index - 1]
    return model, {
        "target_doc": target,
        "docmodel_index": index,
        "doc_name": doc.attrib.get("Name", ""),
        "doc_type": doc_type,
        "before_attributes": dict(sorted(model.attrib.items())),
    }


def ensure_section(root: ET.Element, name: str) -> ET.Element:
    section = root.find(f"./{name}")
    if section is not None:
        return section
    section = ET.Element(name)
    root.insert(0, section)
    return section


def patch_template_xml(
    path: Path,
    selected_caption: str,
    category: str,
    css_class: str,
    target_doc: str,
    docmodel_index: int,
    show_browser: bool,
    enable_upload: bool,
) -> dict[str, object]:
    tree = parse_xml(path)
    root = tree.getroot()
    model, selection = select_docmodel(root, target_doc, docmodel_index)
    updates = {
        "Class": css_class,
        "ImageSelector": selected_caption,
        "ImageCategories": category,
        "ShowImageBrowser": bool_text(show_browser),
        "EnableImageUpload": bool_text(enable_upload),
    }
    for key, value in updates.items():
        model.set(key, value)
    selection["after_attributes"] = {key: model.attrib.get(key, "") for key in sorted(updates)}
    write_xml(path, tree)
    return selection


def patch_template_dhtt(
    path: Path,
    control_name: str,
    display_name: str,
    database_field: str,
    selected_caption: str,
    category: str,
) -> dict[str, object]:
    tree = parse_xml(path)
    root = tree.getroot()
    images = ensure_section(root, "Images")
    before_count = len(list(images))
    child = ET.Element(
        "Image",
        {
            "Name": control_name,
            "DisplayName": display_name,
            "JField": database_field,
            "Value": selected_caption,
            "ImageCategories": category,
        },
    )
    images.append(child)
    write_xml(path, tree)
    return {
        "section": "Images",
        "before_child_count": before_count,
        "after_child_count": before_count + 1,
        "added_child": {"tag": child.tag, "attributes": dict(sorted(child.attrib.items()))},
    }


def bool_text(value: bool) -> str:
    return "True" if value else "False"


def manifest_output_path(output: Path, explicit: Path | None) -> Path:
    if explicit:
        return explicit
    if output.suffix:
        return output.with_name(f"{output.name}.experiment-manifest.json")
    return output.parent / f"{output.name}-experiment-manifest.json"


def build_experiment(args: argparse.Namespace) -> dict[str, object]:
    readiness = build_readiness_summary(args.source, args.group)
    if readiness.get("error_count") and not args.allow_readiness_errors:
        raise SystemExit(
            f"image asset readiness has {readiness['error_count']} error(s); "
            "fix them or pass --allow-readiness-errors for a deliberately rough experiment"
        )

    source_blueprint = readiness_to_blueprint(args.source)
    group = choose_group(source_blueprint, args.group)
    option = choose_option(group, args.caption)
    selected_caption = str(option.get("representative_caption") or "")
    category = choose_category(option, args.category)
    control_name = args.control_name or str(group.get("suggested_control_name") or slugify(str(group.get("group_key", ""))))
    database_field = args.database_field or str(group.get("suggested_database_field") or slugify(f"{control_name}_Choice"))
    display_name = args.display_name or control_name.replace("_", " ")
    css_class = args.css_class

    with tempfile.TemporaryDirectory(prefix="smartcanvas-dropdown-experiment-") as tmp:
        workspace = Path(tmp) / "workspace"
        unpack(args.source, workspace, force=False)
        inner = workspace / "inner"
        template_xml = inner / "template.xml"
        template_dhtt = inner / "template.dhtt"
        if not template_xml.exists():
            raise SystemExit(f"workspace has no inner/template.xml: {workspace}")
        if not template_dhtt.exists():
            raise SystemExit(f"workspace has no inner/template.dhtt: {workspace}")

        template_patch = patch_template_xml(
            template_xml,
            selected_caption,
            category,
            css_class,
            args.target_doc,
            args.docmodel_index,
            args.show_browser,
            args.enable_upload,
        )
        dhtt_patch = patch_template_dhtt(template_dhtt, control_name, display_name, database_field, selected_caption, category)
        pack_result = pack(workspace, args.output, args.force)

    manifest = {
        "format": MANIFEST_VERSION,
        "source": str(args.source),
        "output": str(args.output),
        "packed": pack_result,
        "experimental": True,
        "schema_status": "unproven",
        "warning": (
            "This package is a controlled reverse-engineering probe. It patches observed XML surfaces only "
            "and does not rebuild info.bin or prove that SmartCanvas accepts the dropdown schema."
        ),
        "selected_group": {
            "group_key": group.get("group_key"),
            "control_name": control_name,
            "database_field": database_field,
            "display_name": display_name,
            "category": category,
            "selected_caption": selected_caption,
            "all_option_captions": [option.get("representative_caption") for option in group.get("options", [])],
        },
        "readiness": {
            "ready_for_dropdown_probe": readiness.get("ready_for_dropdown_probe"),
            "error_count": readiness.get("error_count"),
            "warning_count": readiness.get("warning_count"),
            "issue_code_counts": readiness.get("issue_code_counts"),
        },
        "template_xml_patch": template_patch,
        "template_dhtt_patch": dhtt_patch,
        "next_steps": [
            "Run compare_smartcanvas_dropdown_signals.py against the source and output to inspect the intended XML delta.",
            "Import the output into SmartCanvas only as a disposable experiment.",
            "Export the accepted/rejected result and compare it with the source to learn the real control schema.",
        ],
    }

    manifest_path = manifest_output_path(args.output, args.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def readiness_to_blueprint(source: Path) -> dict[str, object]:
    from analyze_smartcanvas_options import load_catalog

    return build_blueprint(load_catalog(source))


def print_result(manifest: dict[str, object]) -> None:
    print(f"Output: {manifest['output']}")
    print(f"Manifest: {manifest['manifest_path']}")
    selected = manifest["selected_group"]
    print(f"Group: {selected['group_key']}")
    print(f"Selected image: {selected['selected_caption']}")
    print(f"Category: {selected['category'] or '[empty]'}")
    print(f"Control: {selected['control_name']}")
    print(f"Database field: {selected['database_field']}")
    readiness = manifest["readiness"]
    print(
        f"Readiness: errors={readiness['error_count']}, "
        f"warnings={readiness['warning_count']}, ready={readiness['ready_for_dropdown_probe']}"
    )
    print("Schema status: unproven experimental patch")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Outer export folder or inner campaign zip")
    parser.add_argument("output", type=Path, help="Output outer export folder or inner zip, matching the source type")
    parser.add_argument("--group", help="Candidate dropdown group name filter; required when more than one group exists")
    parser.add_argument("--caption", help="Representative image caption to select initially")
    parser.add_argument("--category", help="Image category to write into control attributes")
    parser.add_argument("--control-name", help="Control Name attribute; defaults from dropdown blueprint")
    parser.add_argument("--display-name", help="Control DisplayName attribute")
    parser.add_argument("--database-field", help="JField value; defaults from dropdown blueprint")
    parser.add_argument("--css-class", default="DynamicImage1", help="DocModel Class value")
    parser.add_argument("--target-doc", choices=("dynamic", "storyboard", "any"), default="dynamic")
    parser.add_argument("--docmodel-index", type=int, default=1, help="1-based DocModel index within the chosen target doc set")
    parser.add_argument("--show-browser", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-upload", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--allow-readiness-errors", action="store_true")
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.source.exists():
        parser.error(f"source does not exist: {args.source}")
    if args.output.exists() and not args.force:
        parser.error(f"output exists: {args.output}; pass --force")

    manifest = build_experiment(args)
    if args.format == "json":
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print_result(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
