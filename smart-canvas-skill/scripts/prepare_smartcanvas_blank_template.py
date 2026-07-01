#!/usr/bin/env python3
"""Prepare a blank SmartCanvas template export from the approved seed ZIP."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


DEFAULT_SEED_URL = (
    "https://github.com/benfwork/smartcanvas-skill/raw/"
    "2e60ac023740a49ac24805bc11414f89bed8bc28/"
    "blank%20design/blank%20design.zip"
)
DEFAULT_CACHE_NAME = "smartcanvas-blank-design-2e60ac023740a49ac24805bc11414f89bed8bc28.zip"
DEFAULT_SEED_SHA256 = "b8124240bda07d15654e9b9968e6826f00d32559a9fd50ba9d889b0f41c1e48f"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_smartcanvas_export(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"seed is not a ZIP file: {path}")

    with zipfile.ZipFile(path) as outer:
        names = outer.namelist()
        inner_name = next(
            (
                name
                for name in names
                if name.replace("\\", "/").lower().startswith("admin/")
                and name.lower().endswith(".zip")
            ),
            None,
        )
        if not inner_name:
            raise ValueError("seed ZIP does not contain Admin/<campaign>.zip")
        if "info.json" not in names:
            raise ValueError("seed ZIP does not contain info.json")


def download_seed(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            with tmp.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        tmp.replace(destination)
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download/cache the approved blank SmartCanvas seed export and copy it to an output ZIP."
    )
    parser.add_argument("output_zip", type=Path, help="Path for the prepared blank SmartCanvas export ZIP.")
    parser.add_argument("--seed-url", default=DEFAULT_SEED_URL, help="Blank SmartCanvas seed ZIP URL.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "smart-canvas-skill",
        help="Directory used to cache the downloaded seed ZIP.",
    )
    parser.add_argument(
        "--sha256",
        default=DEFAULT_SEED_SHA256,
        help="Expected SHA256 for the seed ZIP. Pass an empty string to skip hash verification.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Download the seed even if a cached copy already exists.",
    )
    args = parser.parse_args(argv)

    cache_path = args.cache_dir / DEFAULT_CACHE_NAME
    if args.force_download or not cache_path.exists():
        download_seed(args.seed_url, cache_path)

    if args.sha256:
        actual = sha256_file(cache_path)
        if actual.lower() != args.sha256.lower():
            raise ValueError(f"seed SHA256 mismatch: expected {args.sha256}, got {actual}")

    validate_smartcanvas_export(cache_path)
    args.output_zip.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cache_path, args.output_zip)
    print(f"Prepared blank SmartCanvas export: {args.output_zip}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
