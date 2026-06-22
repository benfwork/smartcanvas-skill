#!/usr/bin/env python3
"""Generate distinctive PNG images for SmartCanvas dropdown reverse-engineering."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

from prepare_smartcanvas_images import stage_images


DEFAULT_COLORS = [
    ("Red", (218, 61, 49)),
    ("Green", (38, 145, 96)),
    ("Blue", (54, 101, 206)),
    ("Gold", (226, 169, 53)),
    ("Purple", (130, 81, 177)),
]


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, color: tuple[int, int, int], option_index: int) -> None:
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            r, g, b = color
            if (x // 24 + y // 24 + option_index) % 2 == 0:
                pixel = (r, g, b)
            elif x < width * option_index / 8:
                pixel = (min(255, r + 34), min(255, g + 34), min(255, b + 34))
            else:
                pixel = (max(0, r - 42), max(0, g - 42), max(0, b - 42))
            row.extend(pixel)
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + png_chunk(b"IEND", b"")
    )
    path.write_bytes(data)


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def generate_images(args: argparse.Namespace) -> dict[str, object]:
    source_dir = args.output_dir / "source-images"
    staged_dir = args.output_dir / "staged-images"
    source_dir.mkdir(parents=True, exist_ok=True)
    if args.stage_sidecars:
        staged_dir.mkdir(parents=True, exist_ok=True)

    colors = DEFAULT_COLORS[: args.count]
    records = []
    for index, (label, color) in enumerate(colors, start=1):
        filename = f"{args.prefix}_Option_{index}_{safe_name(label)}.png"
        path = source_dir / filename
        if path.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite {path}; pass --force")
        write_png(path, args.width, args.height, color, index)
        records.append(
            {
                "option_number": index,
                "label": label,
                "filename": filename,
                "path": str(path),
                "width": args.width,
                "height": args.height,
                "color_rgb": color,
            }
        )

    manifest = {
        "source_dir": str(source_dir),
        "staged_dir": str(staged_dir) if args.stage_sidecars else "",
        "prefix": args.prefix,
        "image_count": len(records),
        "images": records,
        "next_steps": [
            "Import or upload these images into a minimal SmartCanvas template.",
            "Create one image dropdown using these options.",
            "Export before and after packages, then run make_smartcanvas_dropdown_probe_bundle.py.",
        ],
    }
    if args.stage_sidecars:
        stage_args = argparse.Namespace(
            source_dir=source_dir,
            output_dir=staged_dir,
            group_name=args.group_name,
            dpi=300,
            scaling="none",
            timestamp=None,
            manifest=staged_dir / "smartcanvas-images-manifest.json",
            force=args.force,
            format="json",
        )
        staged_manifest = stage_images(stage_args)
        manifest["staged_manifest"] = staged_manifest.get("manifest_path")

    manifest_path = args.output_dir / "probe-images-manifest.json"
    if manifest_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite {manifest_path}; pass --force")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def print_report(manifest: dict[str, object]) -> None:
    print(f"Source images: {manifest['source_dir']}")
    if manifest.get("staged_dir"):
        print(f"Staged images: {manifest['staged_dir']}")
    print(f"Manifest: {manifest['manifest_path']}")
    print(f"Images: {manifest['image_count']}")
    for image in manifest["images"]:
        print(f"  - Option {image['option_number']}: {image['filename']} {image['width']}x{image['height']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--prefix", default="DropdownProbe")
    parser.add_argument("--count", type=int, default=3, choices=range(2, len(DEFAULT_COLORS) + 1))
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument("--stage-sidecars", action="store_true", help="Also create staged-images/ with _info.xml sidecars")
    parser.add_argument("--group-name", default="", help="Sidecar GroupName when --stage-sidecars is used")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if args.width <= 0 or args.height <= 0:
        parser.error("width and height must be positive")

    result = generate_images(args)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
