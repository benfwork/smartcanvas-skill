#!/usr/bin/env python3
"""Set SmartCanvas picture geometry by layer/crop rules and optionally lock layers."""

from __future__ import annotations

import argparse
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

POINTS_PER_INCH = 72.0


@dataclass(frozen=True)
class GeometryRule:
    layer_contains: str
    crop_contains: str
    left: float
    top: float
    width: float
    height: float

    @classmethod
    def parse(cls, value: str, units: str) -> "GeometryRule":
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 6:
            raise argparse.ArgumentTypeError(
                "rules must be 'layer contains,crop contains,left,top,width,height'"
            )
        factor = POINTS_PER_INCH if units == "inches" else 1.0
        return cls(
            layer_contains=parts[0],
            crop_contains=parts[1],
            left=float(parts[2]) * factor,
            top=float(parts[3]) * factor,
            width=float(parts[4]) * factor,
            height=float(parts[5]) * factor,
        )


def local_name(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1]


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True)


def format_num(value: float) -> str:
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def clone_info(info: zipfile.ZipInfo, filename: str | None = None) -> zipfile.ZipInfo:
    clone = zipfile.ZipInfo(filename or info.filename, date_time=info.date_time)
    clone.compress_type = info.compress_type
    clone.comment = info.comment
    clone.extra = info.extra
    clone.internal_attr = info.internal_attr
    clone.external_attr = info.external_attr
    clone.create_system = info.create_system
    return clone


def find_inner_zip(outer_names: list[str]) -> str | None:
    for name in outer_names:
        normalized = name.replace("\\", "/").lower()
        if normalized.startswith("admin/") and normalized.endswith(".zip"):
            return name
    return None


def patch_document(data: bytes, rules: list[GeometryRule], lock_layers: bool) -> tuple[bytes, dict[str, int]]:
    root = ET.fromstring(data.decode("utf-8-sig"))
    stats = {"layers_locked": 0, "pictures_updated": 0}
    layer_by_id: dict[str, ET.Element] = {}

    for elem in root.iter():
        if local_name(elem) != "Layer":
            continue
        layer_id = elem.get("Name")
        if layer_id:
            layer_by_id[layer_id] = elem
        if lock_layers and elem.get("Locked") != "True":
            elem.set("Locked", "True")
            stats["layers_locked"] += 1

    sorted_rules = sorted(
        rules,
        key=lambda rule: (len(rule.layer_contains), len(rule.crop_contains)),
        reverse=True,
    )

    for pic in root.iter():
        if local_name(pic) != "Picture":
            continue
        layer = layer_by_id.get(pic.get("Layer", ""))
        if layer is None:
            continue
        haystack = " ".join(
            value
            for value in (
                layer.get("DisplayName", ""),
                layer.get("SwitchName", ""),
                pic.get("Source", ""),
                pic.get("OrgSource", ""),
            )
            if value
        ).lower()
        for rule in sorted_rules:
            if rule.layer_contains.lower() in haystack and rule.crop_contains.lower() in haystack:
                pic.set("Left", format_num(rule.left))
                pic.set("Top", format_num(rule.top))
                pic.set("Width", format_num(rule.width))
                pic.set("Height", format_num(rule.height))
                stats["pictures_updated"] += 1
                break

    return xml_bytes(root), stats


def read_package(path: Path) -> tuple[list[zipfile.ZipInfo], dict[str, bytes], str | None]:
    with zipfile.ZipFile(path, "r") as outer:
        infos = outer.infolist()
        data = {info.filename: outer.read(info.filename) for info in infos}
    return infos, data, find_inner_zip([info.filename for info in infos])


def write_package(output: Path, infos: list[zipfile.ZipInfo], data: dict[str, bytes]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as zout:
        for info in infos:
            zout.writestr(clone_info(info), data[info.filename])


def patch_inner_zip(inner_data: bytes, rules: list[GeometryRule], lock_layers: bool) -> tuple[bytes, dict[str, int]]:
    with zipfile.ZipFile(io.BytesIO(inner_data), "r") as zin:
        infos = zin.infolist()
        data = {info.filename: zin.read(info.filename) for info in infos}

    totals = {"layers_locked": 0, "pictures_updated": 0}
    for name in list(data):
        normalized = name.replace("\\", "/")
        if normalized.endswith("/Document.xml") or normalized == "Document.xml":
            data[name], stats = patch_document(data[name], rules, lock_layers)
            for key, value in stats.items():
                totals[key] += value

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zout:
        for info in infos:
            zout.writestr(clone_info(info), data[info.filename])
    return out.getvalue(), totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set SmartCanvas Picture Left/Top/Width/Height by layer/crop rules."
    )
    parser.add_argument("input", type=Path, help="SmartCanvas export ZIP or inner campaign ZIP")
    parser.add_argument("output", type=Path, help="Output ZIP path")
    parser.add_argument(
        "--units",
        choices=["points", "inches"],
        default="points",
        help="Units used by --rule geometry values",
    )
    parser.add_argument(
        "--rule",
        action="append",
        default=[],
        help="Rule: 'layer contains,crop contains,left,top,width,height'",
    )
    parser.add_argument("--lock-layers", action="store_true", help="Set Locked=True on every Layer in Document.xml")
    args = parser.parse_args(argv)

    rules = [GeometryRule.parse(value, args.units) for value in args.rule]
    if not rules and not args.lock_layers:
        parser.error("provide at least one --rule or --lock-layers")

    infos, data, inner_name = read_package(args.input)
    if inner_name:
        data[inner_name], totals = patch_inner_zip(data[inner_name], rules, args.lock_layers)
        write_package(args.output, infos, data)
    else:
        doc_name = next(
            (
                name
                for name in data
                if name.replace("\\", "/").endswith("/Document.xml") or name == "Document.xml"
            ),
            None,
        )
        if doc_name is None:
            raise SystemExit("Could not find Document.xml")
        data[doc_name], totals = patch_document(data[doc_name], rules, args.lock_layers)
        write_package(args.output, infos, data)

    print(f"Wrote {args.output}")
    print(f"Pictures updated: {totals['pictures_updated']}")
    print(f"Layers locked: {totals['layers_locked']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
