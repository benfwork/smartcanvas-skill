#!/usr/bin/env python3
"""Stage image files with SmartCanvas-style metadata sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
JPEG_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
BITMAP_TYPES = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png"}


def asset_stem(filename: str) -> str:
    path = Path(filename)
    suffix = path.suffix[1:]
    if not suffix:
        return path.name
    return f"{path.stem}_{suffix}"


def sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_dimensions(path: Path) -> tuple[int, int]:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return read_jpeg_dimensions(path)
    if suffix == ".png":
        return read_png_dimensions(path)
    raise ValueError(f"unsupported image extension: {path.suffix}")


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"not a readable PNG: {path}")
    return struct.unpack(">II", header[16:24])


def read_jpeg_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError(f"not a readable JPEG: {path}")
    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index : index + 2], "big")
        if length < 2:
            break
        if marker in JPEG_SOF_MARKERS:
            if index + 7 > len(data):
                break
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += length
    raise ValueError(f"could not find JPEG dimensions: {path}")


def dotnet_utc_now() -> str:
    # SmartCanvas demo sidecars use seven fractional digits. Python has six, so append one zero.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "0Z"


def build_info_xml(
    caption: str,
    width: int,
    height: int,
    filesize: int,
    bitmap_type: str,
    group_name: str,
    dpi: int,
    scaling: str,
    timestamp: str,
) -> bytes:
    root = ET.Element(
        "FileGroupInformation",
        {
            "Source": "_Template",
            "Resource": "_Image",
            "Caption": caption,
            "GroupName": group_name,
            "FileOrigin": "",
            "IsSelected": "false",
            "ImageWidth": str(width),
            "ImageHeight": str(height),
            "LastWriteUtc": timestamp,
            "IsMultiImage": "false",
            "LastImage": "1",
            "Filesize": str(filesize),
        },
    )
    pages = ET.SubElement(root, "Pages")
    ET.SubElement(pages, "Page", {"Top": "0", "Left": "0", "Width": str(width), "Height": str(height)})
    resource = ET.SubElement(
        root,
        "Resourceinfo",
        {
            "DPIx": str(dpi),
            "DPIy": str(dpi),
            "PixelBased": "True",
            "HasMask": "False",
            "HasProfile": "True",
            "CoordType": "Pixel",
            "Version": "",
            "BitmapType": bitmap_type,
            "BitsPerComponent": "8",
        },
    )
    custom = ET.SubElement(resource, "CustomProperties")
    ET.SubElement(custom, "Scalings", {"Value": scaling})
    indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False) + b"\n"


def indent(element: ET.Element, level: int = 0) -> None:
    padding = "\n" + level * "  "
    child_padding = "\n" + (level + 1) * "  "
    children = list(element)
    if children:
        if not element.text or not element.text.strip():
            element.text = child_padding
        for child in children:
            indent(child, level + 1)
        if not children[-1].tail or not children[-1].tail.strip():
            children[-1].tail = padding
    if level and (not element.tail or not element.tail.strip()):
        element.tail = padding


def iter_images(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and not path.name.endswith(":Zone.Identifier")
        and not is_known_derivative(path)
    )


def is_known_derivative(path: Path) -> bool:
    stem = path.stem
    return stem.endswith("_thumbi") or stem.endswith("_thumbn") or re_scaled_asset(path)


def re_scaled_asset(path: Path) -> bool:
    stem = path.stem
    parts = stem.rsplit("_", 1)
    return len(parts) == 2 and parts[1].isdigit() and path.parent.name == parts[0]


def scaling_value(width: int, height: int, mode: str) -> str:
    if mode == "none":
        return ""
    if mode == "auto":
        return "900" if max(width, height) > 1200 else ""
    return mode


def stage_images(args: argparse.Namespace) -> dict[str, object]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    images = iter_images(args.source_dir)
    if not images:
        raise SystemExit(f"no supported images found in {args.source_dir}")

    records = []
    timestamp = args.timestamp or dotnet_utc_now()
    for source_path in images:
        caption = source_path.name
        stem = asset_stem(caption)
        output_image = args.output_dir / caption
        output_info = args.output_dir / f"{stem}_info.xml"
        for output_path in (output_image, output_info):
            if output_path.exists() and not args.force:
                raise SystemExit(f"refusing to overwrite {output_path}; pass --force")

        width, height = read_dimensions(source_path)
        filesize = source_path.stat().st_size
        bitmap_type = BITMAP_TYPES[source_path.suffix.lower()]
        scaling = scaling_value(width, height, args.scaling)
        shutil.copy2(source_path, output_image)
        output_info.write_bytes(
            build_info_xml(
                caption=caption,
                width=width,
                height=height,
                filesize=filesize,
                bitmap_type=bitmap_type,
                group_name=args.group_name,
                dpi=args.dpi,
                scaling=scaling,
                timestamp=timestamp,
            )
        )
        records.append(
            {
                "caption": caption,
                "asset_stem": stem,
                "source_path": str(source_path),
                "output_image": str(output_image),
                "output_info_xml": str(output_info),
                "width": width,
                "height": height,
                "filesize": filesize,
                "sha1": sha1(source_path),
                "bitmap_type": bitmap_type,
                "group_name": args.group_name,
                "scaling": scaling,
                "thumbnail_inline": f"{stem}_thumbi.png",
                "thumbnail_normal": f"{stem}_thumbn.png",
                "scaled_asset": f"{stem}/{stem}_{scaling}.{source_path.suffix[1:].lower()}" if scaling else "",
            }
        )

    manifest = {
        "source_dir": str(args.source_dir),
        "output_dir": str(args.output_dir),
        "image_count": len(records),
        "generated": {
            "images_copied": True,
            "info_xml_sidecars": True,
            "thumbnails": False,
            "scaled_assets": False,
            "info_bin": False,
        },
        "notes": [
            "Generated sidecar XML follows the observed demo shape.",
            "SmartCanvas category mappings are stored in info.bin in the demo; sidecar GroupName is blank there.",
            "This script does not rebuild info.bin, thumbnails, or scaled image derivatives.",
        ],
        "images": records,
    }
    manifest_path = args.manifest or (args.output_dir / "smartcanvas-images-manifest.json")
    if manifest_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite {manifest_path}; pass --force")
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def print_text_report(manifest: dict[str, object]) -> None:
    print(f"Source: {manifest['source_dir']}")
    print(f"Output: {manifest['output_dir']}")
    print(f"Images staged: {manifest['image_count']}")
    print(f"Manifest: {manifest['manifest_path']}")
    print("Generated: images + _info.xml sidecars")
    print("Not generated: thumbnails, scaled assets, info.bin")
    for image in manifest["images"]:
        print(
            f"  - {image['caption']} | {image['width']}x{image['height']} | "
            f"{image['filesize']} bytes | scaling={image['scaling'] or '[none]'}"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing .jpg, .jpeg, or .png images to stage")
    parser.add_argument("output_dir", type=Path, help="Output directory for copied images and generated _info.xml files")
    parser.add_argument("--group-name", default="", help="Value for sidecar GroupName; demo sidecars use blank")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--scaling", default="auto", help="'auto', 'none', or a numeric scaling value such as 900")
    parser.add_argument("--timestamp", help="Explicit LastWriteUtc value; defaults to current UTC")
    parser.add_argument("--manifest", type=Path, help="Manifest path; defaults to output_dir/smartcanvas-images-manifest.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing staged files")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.source_dir.is_dir():
        parser.error(f"source_dir is not a directory: {args.source_dir}")
    if args.scaling not in ("auto", "none") and not args.scaling.isdigit():
        parser.error("--scaling must be 'auto', 'none', or a numeric value")

    manifest = stage_images(args)
    if args.format == "json":
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print_text_report(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
