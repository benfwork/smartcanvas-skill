#!/usr/bin/env python3
"""Create SmartCanvas shapes, lines, form fields, and variables in an export."""

from __future__ import annotations

import argparse
import copy
import io
import json
import random
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


POINTS_PER_INCH = 72.0


@dataclass(frozen=True)
class VariableFunctionExample:
    key: str
    name: str
    function: str
    args: tuple[object, ...] = ()
    variable_type: str = "0"


RAW_PREFIX = "__raw__:"
VARIABLE_FUNCTION_EXAMPLES = [
    VariableFunctionExample("replace", "replace", "replace", ("jimmy", "jim", "tim")),
    VariableFunctionExample("remove", "remove", "removechars", ("jimmy", "jim")),
    VariableFunctionExample("hmacsha256password", "HMACSHA256Password", "hmacsha256password", ("password", "salt")),
    VariableFunctionExample("hmacsha256", "HMACSHA256", "hmacsha256", ("password", "salt")),
    VariableFunctionExample("last-part", "LastPart", "lastPart", ("string", "r")),
    VariableFunctionExample("first-part", "FirstPart", "firstPart", ("string", "r")),
    VariableFunctionExample("trim-right", "TrimRightSide", "trimRight", ("string", "3")),
    VariableFunctionExample("trim-left", "TrimLeftSide", "trimLeft", ("string", "3")),
    VariableFunctionExample("trim-to-length", "TrimToLength", "trimToLength", ("string", "3")),
    VariableFunctionExample("right", "Right", "right", ("string", "3")),
    VariableFunctionExample("left", "Left", "left", ("string", "3")),
    VariableFunctionExample("substr", "Substr", "substr", ("string", "2", "5")),
    VariableFunctionExample("sha256", "SHA256", "sha256", ("string",)),
    VariableFunctionExample("sha1", "SHA1", "sha1", ("string",)),
    VariableFunctionExample("reverse-dns", "ReverseDNSLookup", "reverseDNS", ("1.1.1.1",)),
    VariableFunctionExample("replace-curly-brackets", "ReplaceCurlyBrackets", "replaceCurlyBrackets", ("{string}",)),
    VariableFunctionExample("md5", "MD5", "md5", ("string",)),
    VariableFunctionExample("upper-case", "UpperCase", "upperCase", ("string",)),
    VariableFunctionExample("lower-case", "LowerCase", "lowerCase", ("STRING",)),
    VariableFunctionExample("capitalize", "Capitalize", "capitalize", ("string",)),
    VariableFunctionExample("url-encode", "urlEncode", "urlEncode", ("https://example.com",)),
    VariableFunctionExample("url-decode", "urlDecode", "urlDecode", ("https://example.com",)),
    VariableFunctionExample("html-encode", "HtmlEncode", "htmlEncode", ("<strong>Hi</strong>",)),
    VariableFunctionExample("html-decode", "HtmlDecode", "htmlDecode", ("&lt;strong&gt;Hi&lt;/strong&gt;",)),
    VariableFunctionExample("password", "CreatePassword", "password", ("10",)),
    VariableFunctionExample("date-format-culture", "DateFormat1", "dateFormat", ("12-31-2021", "yyyy-MM-dd", "Chinese")),
    VariableFunctionExample("date-format", "DateFormat2", "dateFormat", ("12-31-2021", "yyyy-MM-dd")),
    VariableFunctionExample("date-utc-format", "DateFormat3", "dateUtc", ("yyyy-dd-MM",)),
    VariableFunctionExample("date-format-current", "DateFormat4", "date", ("yyyy-MM-dd",)),
    VariableFunctionExample("parse-int", "ParseInt", "parseInt", ("1234",)),
    VariableFunctionExample("add", "Add", r"\+I", ("1234", "6789")),
    VariableFunctionExample("subtract", "Subtract", "-I", ("1234", "6789")),
    VariableFunctionExample("divide-whole", "DivideWhole", "/I", ("1234", "6789")),
    VariableFunctionExample("multiply-whole", "MultiplyWhole", "*I", ("1234", "6789")),
    VariableFunctionExample("multiply-float", "MultiplyFloat", "*S", ("1234.56789", "6789.12345")),
    VariableFunctionExample("divide-float", "DivideFloat", "/S", ("1234.56789", "6789.12345")),
    VariableFunctionExample("random", "Random", "random", ("1", "9999")),
    VariableFunctionExample("age", "Age", "age", ("09-18-2004",)),
    VariableFunctionExample("month", "MonthPart", "month", ("09-18-2004",)),
    VariableFunctionExample("year", "YearPart", "year", ("09-18-2004",)),
    VariableFunctionExample("length", "Length", "length", ("string",)),
    VariableFunctionExample("current-date-utc", "CurrentDateUTC", "dateUtc"),
    VariableFunctionExample("current-date", "CurrentDate", "date"),
    VariableFunctionExample("add-days", "AddDaysToDate", "dateAddDays", ("09-18-2004", "20005")),
    VariableFunctionExample("add-hours", "AddHoursToDate", "dateAddHours", ("09-18-2004", "20005")),
    VariableFunctionExample("add-minutes", "AddMinutesToDate", "dateAddMinutes", ("09-18-2004", "20005")),
    VariableFunctionExample("has-birthday", "HasBirthDayToday", "hasBirthday", ("09-18-2004",)),
    VariableFunctionExample("has-birthday-format", "HasBirthdayToday2", "hasBirthday", ("09-18-2004", "MM-dd-yyyy")),
    VariableFunctionExample("is-date-in-next-month", "IsDateInNextMonth", "isDateInNextMonth", ("09-18-2004", "MM-dd-yyyy")),
    VariableFunctionExample("has-birthday-on-date", "HasBirthdayOnDate", "hasBirthdayOnDay", ("09-18-2004", "MM-dd-yyyy")),
    VariableFunctionExample("is-date-in-month", "IsDateInMonth", "isDateInMonthN", ("09-18-2004", "MM-dd-yyyy", "9")),
    VariableFunctionExample("calendar-days", "CreateCalendarDaysText", "createCalendarDays", ("2026", "09", "1", "full")),
    VariableFunctionExample("month-name", "ReturnMonthName", "getMonthNameByMonthIndex", ("2", "09")),
]
VARIABLE_FUNCTION_INDEX: dict[str, VariableFunctionExample] = {}
for example in VARIABLE_FUNCTION_EXAMPLES:
    for alias in {example.key, example.name, example.function}:
        VARIABLE_FUNCTION_INDEX[alias.lower().replace("_", "-")] = example


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


def format_num(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    text = f"{float(value):.10f}".rstrip("0").rstrip(".")
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


def convert_value(value: float | int | str, units: str) -> float | int | str:
    if isinstance(value, str):
        return value
    return value if units == "points" else float(value) * POINTS_PER_INCH


def convert_box(spec: dict[str, object], units: str) -> None:
    for key in ("left", "top", "width", "height"):
        if key in spec:
            spec[key] = convert_value(spec[key], units)  # type: ignore[arg-type]


def parse_json_specs(values: list[str]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for value in values:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("JSON specs must be objects")
        specs.append(parsed)
    return specs


def parse_variable_specs(values: list[str]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for value in values:
        if "=" not in value:
            raise ValueError("--variable values must use Name=Expression")
        name, expression = value.split("=", 1)
        specs.append({"name": name, "expression": expression})
    return specs


def quote_function_arg(value: object) -> str:
    if isinstance(value, dict):
        if "raw" in value:
            return str(value["raw"])
        if "value" in value:
            value = value["value"]
    text = str(value)
    if text.startswith(RAW_PREFIX):
        return text[len(RAW_PREFIX) :]
    return r"\'" + text.replace("\\", "\\\\").replace("'", r"\'") + r"\'"


def variable_function_expression(function_name: str, args: tuple[object, ...] | list[object]) -> str:
    joined_args = ", ".join(quote_function_arg(arg) for arg in args)
    return f"[[{{{{{function_name}({joined_args})}}}}]]"


def variable_function_spec(example: VariableFunctionExample, prefix: str = "") -> dict[str, object]:
    return {
        "name": prefix + example.name,
        "expression": variable_function_expression(example.function, example.args),
        "type": example.variable_type,
    }


def normalize_variable_function_key(value: str) -> str:
    return value.lower().replace("_", "-")


def parse_function_variable_specs(values: list[str]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for value in values:
        spec = json.loads(value)
        if not isinstance(spec, dict):
            raise ValueError("--function-variable-json values must be JSON objects")
        name = str(spec.get("name", ""))
        function_name = str(spec.get("function", ""))
        if not name or not function_name:
            raise ValueError("--function-variable-json requires name and function")
        args = spec.get("args", [])
        if not isinstance(args, list):
            raise ValueError("--function-variable-json args must be a JSON array")
        specs.append(
            {
                "name": name,
                "expression": variable_function_expression(function_name, args),
                "type": str(spec.get("type", "0")),
            }
        )
    return specs


def select_variable_function_specs(keys: list[str], prefix: str) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for key in keys:
        example = VARIABLE_FUNCTION_INDEX.get(normalize_variable_function_key(key))
        if example is None:
            raise ValueError(f"unknown variable function {key!r}; run --list-variable-functions")
        specs.append(variable_function_spec(example, prefix))
    return specs


def list_variable_functions() -> None:
    for example in VARIABLE_FUNCTION_EXAMPLES:
        print(f"{example.key}\t{example.name}\t{example.function}\t{variable_function_expression(example.function, example.args)}")


def ensure_layer(document: ET.Element, layer_name: str, locked: bool = False) -> str:
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


def ensure_composition(document: ET.Element) -> ET.Element:
    composition = find_first(document, "Composition")
    if composition is None:
        raise ValueError("Document.xml does not contain a Composition to receive new objects")
    return composition


def ensure_shape_templates(document: ET.Element) -> None:
    extended = ensure_child(document, "ExtendedProperties")
    templates = ensure_child(extended, "ShapeTemplates")
    if not any(local_name(child) == "Shape" and child.get("ID") == "rectangleTemplate" for child in templates):
        ET.SubElement(
            templates,
            "Shape",
            {
                "ShapeType": "rectangle",
                "ID": "rectangleTemplate",
                "Left": "-100",
                "Top": "-100",
                "Width": "200",
                "Height": "200",
                "Background": "",
                "Opacity": "1",
                "Layer": "none",
            },
        )
    if not any(local_name(child) == "Shape" and child.get("ID") == "ellipseTemplate" for child in templates):
        ET.SubElement(
            templates,
            "Shape",
            {
                "ShapeType": "ellipse",
                "ID": "ellipseTemplate",
                "Left": "-100",
                "Top": "-100",
                "Width": "200",
                "Height": "200",
                "Background": "",
                "Opacity": "1",
                "Layer": "none",
            },
        )
    if not any(local_name(child) == "Line" and child.get("ID") == "lineTemplate" for child in templates):
        ET.SubElement(
            templates,
            "Line",
            {
                "ID": "lineTemplate",
                "Left": "-100",
                "Top": "-100",
                "Width": "200",
                "Height": "200",
                "Background": "",
                "Opacity": "1",
                "Layer": "none",
                "LineThickness": "1",
            },
        )


def add_shapes(document: ET.Element, specs: list[dict[str, object]], default_layer: str, units: str) -> int:
    if not specs:
        return 0
    ensure_shape_templates(document)
    composition = ensure_composition(document)
    for spec in specs:
        convert_box(spec, units)
        kind = str(spec.get("type", "rectangle")).lower()
        if kind not in {"rectangle", "square", "ellipse", "oval", "circle"}:
            raise ValueError(f"unsupported shape type: {kind}")
        shape_type = "ellipse" if kind in {"ellipse", "oval", "circle"} else "rectangle"
        if kind in {"square", "circle"}:
            spec["height"] = spec.get("height", spec.get("width", 72.0))
            spec["width"] = spec.get("width", spec["height"])
        layer_id = ensure_layer(document, str(spec.get("layer", default_layer)), bool(spec.get("lock_layer", False)))
        ET.SubElement(
            composition,
            "Shape",
            {
                "ShapeType": shape_type,
                "ID": str(spec.get("id", uuid.uuid4())),
                "Left": format_num(spec.get("left", 0.0)),  # type: ignore[arg-type]
                "Top": format_num(spec.get("top", 0.0)),  # type: ignore[arg-type]
                "Width": format_num(spec.get("width", 72.0)),  # type: ignore[arg-type]
                "Height": format_num(spec.get("height", 72.0)),  # type: ignore[arg-type]
                "Background": str(spec.get("color", spec.get("background", ""))),
                "Opacity": format_num(spec.get("opacity", 1.0)),  # type: ignore[arg-type]
                "Layer": layer_id,
            },
        )
    return len(specs)


def add_lines(document: ET.Element, specs: list[dict[str, object]], default_layer: str, units: str) -> int:
    if not specs:
        return 0
    ensure_shape_templates(document)
    composition = ensure_composition(document)
    for spec in specs:
        convert_box(spec, units)
        if units == "inches" and "thickness" in spec and not isinstance(spec["thickness"], str):
            spec["thickness"] = float(spec["thickness"]) * POINTS_PER_INCH
        layer_id = ensure_layer(document, str(spec.get("layer", default_layer)), bool(spec.get("lock_layer", False)))
        attrs = {
            "ID": str(spec.get("id", uuid.uuid4())),
            "Left": format_num(spec.get("left", 0.0)),  # type: ignore[arg-type]
            "Top": format_num(spec.get("top", 0.0)),  # type: ignore[arg-type]
            "Width": format_num(spec.get("width", 72.0)),  # type: ignore[arg-type]
            "Height": format_num(spec.get("height", 0.0)),  # type: ignore[arg-type]
            "Background": str(spec.get("background", "")),
            "Opacity": format_num(spec.get("opacity", 1.0)),  # type: ignore[arg-type]
            "Layer": layer_id,
            "LineThickness": format_num(spec.get("thickness", 1.0)),  # type: ignore[arg-type]
            "LineColor": str(spec.get("color", spec.get("line_color", "#000000"))),
        }
        if spec.get("blend_mode"):
            attrs["BlendMode"] = str(spec["blend_mode"])
        ET.SubElement(composition, "Line", attrs)
    return len(specs)


def ensure_data_interface(document: ET.Element) -> ET.Element:
    resources = ensure_child(document, "Resources")
    data_interface = ensure_child(resources, "DataInterface2")
    ensure_child(data_interface, "Properties", PageCount="1", PageWidth="", PageHeight="", LocalDocumentFileName="")
    return ensure_child(data_interface, "DataInterfaceGroup", Name="FormFields", DisplayName="Form fields", AssociatedPageNo="1")


def upsert_form_field(group: ET.Element, spec: dict[str, object]) -> None:
    name = str(spec["name"])
    for child in list(group):
        if local_name(child) == "DataInterfaceItem" and child.get("Name") == name:
            group.remove(child)
    display_type = str(spec.get("display_type", "text")).lower()
    if display_type in {"radio", "radio buttons"}:
        display_id, display_name = "2", "Radio Buttons"
    elif display_type in {"dropdown", "select"}:
        display_id, display_name = "1", "DropDown"
    else:
        display_id, display_name = "0", "Text"
    item = ET.SubElement(
        group,
        "DataInterfaceItem",
        {
            "Name": name,
            "Value": str(spec.get("value", "")),
            "Guid": str(spec.get("guid", uuid.uuid4())),
            "ItemType": str(spec.get("item_type", "0")),
            "ItemTypeName": str(spec.get("item_type_name", "Text")),
            "FormatterReplacement": str(spec.get("formatter_replacement", "")),
        },
    )
    if spec.get("formatter_id"):
        item.set("FormatterID", str(spec["formatter_id"]))
    if spec.get("formatter_pattern"):
        item.set("FormatterPattern", str(spec["formatter_pattern"]))
    ET.SubElement(item, "Display", {"DisplayType": display_id, "DisplayTypeName": display_name})
    ET.SubElement(item, "TextProperties", {"TxtMaxSize": "0", "TxtValidationType": "0", "TxtFieldCategory": "0"})
    ET.SubElement(
        item,
        "Behaviour",
        {
            "isExpandable": "0",
            "isExpanded": "0",
            "OnChangeBehaviour": str(spec.get("on_change", "1")),
            "OnChangeBehaviourName": str(spec.get("on_change_name", "NoRefresh")),
            "isRequired": "1" if spec.get("required") else "0",
            "RemoveIfEmpty": "1" if spec.get("remove_if_empty") else "0",
            "isElementDBField": "0",
        },
    )
    options = spec.get("options", [])
    keys_attrs = {"ListType": "1", "ListTypeName": "UserDefined"} if options else {}
    keys = ET.SubElement(item, "DataInterfaceKeys", keys_attrs)
    if isinstance(options, str):
        options = [part for part in options.split("|") if part]
    for option in options:
        ET.SubElement(keys, "DataInterfaceKey", {"PageNr": "0", "KeyValue": str(option), "DisplayValue": str(option)})


def add_form_fields(document: ET.Element, specs: list[dict[str, object]]) -> int:
    if not specs:
        return 0
    group = ensure_data_interface(document)
    for spec in specs:
        if "name" not in spec:
            raise ValueError("form-field JSON requires a name")
        upsert_form_field(group, spec)
    return len(specs)


def upsert_variable(document: ET.Element, name: str, expression: str, variable_type: str = "0") -> None:
    resources = ensure_child(document, "Resources")
    variables = ensure_child(resources, "Variables")
    for child in list(variables):
        if local_name(child) == "Variable" and child.get("Name") == name:
            variables.remove(child)
    ET.SubElement(variables, "Variable", {"Name": name, "X": expression, "Type": variable_type})


def add_variables(document: ET.Element, specs: list[dict[str, object]]) -> int:
    for spec in specs:
        name = str(spec.get("name", ""))
        expression = str(spec.get("expression", spec.get("x", "")))
        if not name or not expression:
            raise ValueError("variable specs require name and expression")
        upsert_variable(document, name, expression, str(spec.get("type", "0")))
    return len(specs)


def add_birthday_example(document: ET.Element, args: argparse.Namespace) -> tuple[int, int]:
    field_specs = [
        {"name": args.age_field, "value": args.age_value, "display_type": "text"},
        {
            "name": args.had_birthday_field,
            "value": args.had_birthday_value,
            "display_type": "radio",
            "options": ["Yes", "No"],
        },
    ]
    variable_specs = [
        {"name": args.current_year_variable, "expression": r"[[{{date(\'yyyy\')}}]]"},
        {
            "name": args.age_plus_one_variable,
            "expression": rf"[[{{{{\+I([[{args.age_field}\]\], \'1\')}}}}]]",
        },
        {
            "name": args.birthyear_variable,
            "expression": (
                f"If ([[{args.had_birthday_field}]] == 'Yes') "
                f"Then [[{{{{-I([[{args.current_year_variable}\\]\\], [[{args.age_field}\\]\\])}}}}]] "
                f"Else [[{{{{-I([[{args.current_year_variable}\\]\\], [[{args.age_plus_one_variable}\\]\\])}}}}]]"
            ),
        },
    ]
    return add_form_fields(document, field_specs), add_variables(document, variable_specs)


def sync_smartcampaign(document: ET.Element, smartcampaign_data: bytes | None) -> bytes:
    root = parse_xml(smartcampaign_data) if smartcampaign_data else ET.Element("Campaign")
    resources = find_child(document, "Resources")
    if resources is not None:
        existing = find_child(root, "Resources")
        if existing is not None:
            root.remove(existing)
        root.insert(0, copy.deepcopy(resources))
    return xml_bytes(root)


def patch_package(args: argparse.Namespace) -> tuple[int, int, int, int]:
    outer, inner_name, inner = read_package(Path(args.input))
    document_name = find_inner_file(inner, "Document.xml")
    smartcampaign_name = next((name for name in inner if name.replace("\\", "/").endswith("/smartcampaign.xml")), None)
    prefix = campaign_prefix(document_name)

    document_root = parse_xml(inner[document_name].data)
    document = editable_document(document_root)

    shape_specs = parse_json_specs(args.shape_json)
    line_specs = parse_json_specs(args.line_json)
    form_specs = parse_json_specs(args.form_field_json)
    variable_specs = (
        parse_json_specs(args.variable_json)
        + parse_variable_specs(args.variable)
        + parse_function_variable_specs(args.function_variable_json)
    )
    if args.all_variable_functions:
        variable_specs += [variable_function_spec(example, args.variable_function_prefix) for example in VARIABLE_FUNCTION_EXAMPLES]
    variable_specs += select_variable_function_specs(args.variable_function, args.variable_function_prefix)

    shapes = add_shapes(document, shape_specs, args.layer_name, args.units)
    lines = add_lines(document, line_specs, args.layer_name, args.units)
    fields = add_form_fields(document, form_specs)
    variables = add_variables(document, variable_specs)
    if args.birthday_example:
        added_fields, added_variables = add_birthday_example(document, args)
        fields += added_fields
        variables += added_variables

    replacements = {document_name: xml_bytes(document_root)}
    additions: dict[str, bytes] = {}
    smartcampaign_output = sync_smartcampaign(document, inner[smartcampaign_name].data if smartcampaign_name else None)
    if smartcampaign_name:
        replacements[smartcampaign_name] = smartcampaign_output
    elif fields or variables:
        additions[prefix + "smartcampaign.xml"] = smartcampaign_output

    inner_bytes = create_inner_zip(inner, replacements, additions)
    output_path = Path(args.output)
    if inner_name:
        outer[inner_name].data = inner_bytes
        write_zip(output_path, outer)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(inner_bytes)
    return shapes, lines, fields, variables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create SmartCanvas shapes, lines, form fields, and variables.")
    parser.add_argument("input", nargs="?", help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", nargs="?", help="Output ZIP path")
    parser.add_argument("--units", choices=("points", "inches"), default="points", help="Coordinate units for boxes")
    parser.add_argument("--layer-name", default="Shapes and Variables", help="Default layer to create or reuse")
    parser.add_argument("--shape-json", action="append", default=[], help="Shape JSON object: type,left,top,width,height,color,opacity,layer")
    parser.add_argument("--line-json", action="append", default=[], help="Line JSON object: left,top,width,height,color,thickness,opacity,layer")
    parser.add_argument("--form-field-json", action="append", default=[], help="Form field JSON object: name,value,display_type,options")
    parser.add_argument("--variable-json", action="append", default=[], help="Variable JSON object: name,expression,type")
    parser.add_argument("--variable", action="append", default=[], help="Variable as Name=Expression")
    parser.add_argument("--function-variable-json", action="append", default=[], help="Function variable JSON: name,function,args,type")
    parser.add_argument("--variable-function", action="append", default=[], help="Add one built-in variable function example by key, name, or function")
    parser.add_argument("--all-variable-functions", action="store_true", help="Add built-in examples for all documented SmartCanvas variable functions")
    parser.add_argument("--variable-function-prefix", default="", help="Prefix for variables created by --variable-function or --all-variable-functions")
    parser.add_argument("--list-variable-functions", action="store_true", help="List built-in variable function keys and expressions")
    parser.add_argument("--birthday-example", action="store_true", help="Add the observed birthday-year form fields and variables")
    parser.add_argument("--age-field", default="Age", help="Birthday example age form field")
    parser.add_argument("--age-value", default="21", help="Birthday example default age value")
    parser.add_argument("--had-birthday-field", default="HadBirthdayThisYearSoFar", help="Birthday example yes/no form field")
    parser.add_argument("--had-birthday-value", choices=("Yes", "No"), default="No", help="Birthday example yes/no default")
    parser.add_argument("--current-year-variable", default="CurrentYear", help="Birthday example current-year variable name")
    parser.add_argument("--age-plus-one-variable", default="AgePlusOne", help="Birthday example age-plus-one variable name")
    parser.add_argument("--birthyear-variable", default="Birthyear", help="Birthday example birthyear variable name")
    args = parser.parse_args(argv)
    if args.list_variable_functions:
        list_variable_functions()
        return 0
    if not args.input or not args.output:
        parser.error("input and output are required unless --list-variable-functions is used")

    try:
        shapes, lines, fields, variables = patch_package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    print(f"Shapes: {shapes}; lines: {lines}; form fields: {fields}; variables: {variables}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
