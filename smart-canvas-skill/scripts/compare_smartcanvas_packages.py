#!/usr/bin/env python3
"""Compare two SmartCanvas exports, inner zips, or extracted inner folders."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import sys
import zipfile
from pathlib import Path

from inspect_smartcanvas_package import summarize_info_bin


KEY_FILENAMES = {"template.xml", "template.dhtt", "Document.xml", "css.css", "description.xml", "scriptsnippets.xml"}
IMAGE_INFO_SUFFIX = "_info.xml"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_member_name(name: str) -> str:
    parts = [part for part in name.split("/") if part]
    if len(parts) > 1:
        return "/".join(parts[1:])
    return "/".join(parts)


def read_package(path: Path) -> dict[str, object]:
    if path.is_dir() and (path / "info.json").exists():
        zips = sorted((path / "Admin").glob("*.zip"))
        if not zips:
            raise SystemExit(f"outer export has no Admin/*.zip: {path}")
        return read_zip(zips[0], label=str(path))
    if path.is_file() and path.suffix.lower() == ".zip":
        return read_zip(path, label=str(path))
    if path.is_dir():
        return read_folder(path, label=str(path))
    raise SystemExit(f"unsupported path: {path}")


def read_zip(path: Path, label: str) -> dict[str, object]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            files[normalize_member_name(info.filename)] = archive.read(info.filename)
    return build_summary(label, files)


def read_folder(path: Path, label: str) -> dict[str, object]:
    files: dict[str, bytes] = {}
    for file_path in path.rglob("*"):
        if not file_path.is_file() or file_path.name.endswith(":Zone.Identifier"):
            continue
        files[str(file_path.relative_to(path))] = file_path.read_bytes()
    return build_summary(label, files)


def build_summary(label: str, files: dict[str, bytes]) -> dict[str, object]:
    hashes = {name: sha256(data) for name, data in files.items()}
    key_texts = {
        name: data.decode("utf-8-sig", errors="replace")
        for name, data in files.items()
        if Path(name).name in KEY_FILENAMES
    }
    image_info = {
        name: data.decode("utf-8-sig", errors="replace")
        for name, data in files.items()
        if name.endswith(IMAGE_INFO_SUFFIX)
    }
    info_bin_summary = summarize_info_bin(files["info.bin"]) if "info.bin" in files else None
    return {
        "label": label,
        "files": files,
        "hashes": hashes,
        "key_texts": key_texts,
        "image_info": image_info,
        "info_bin_summary": info_bin_summary,
    }


def print_set_delta(title: str, before: set[str], after: set[str], limit: int = 80) -> None:
    added = sorted(after - before)
    removed = sorted(before - after)
    print(f"\n{title}")
    print(f"  added: {len(added)}")
    for item in added[:limit]:
        print(f"    + {item}")
    if len(added) > limit:
        print(f"    ... {len(added) - limit} more")
    print(f"  removed: {len(removed)}")
    for item in removed[:limit]:
        print(f"    - {item}")
    if len(removed) > limit:
        print(f"    ... {len(removed) - limit} more")


def print_changed_files(before: dict[str, object], after: dict[str, object]) -> None:
    before_hashes = before["hashes"]
    after_hashes = after["hashes"]
    common = sorted(set(before_hashes) & set(after_hashes))
    changed = [name for name in common if before_hashes[name] != after_hashes[name]]
    print("\nChanged Files")
    print(f"  changed: {len(changed)}")
    for name in changed[:120]:
        print(f"    * {name}")
    if len(changed) > 120:
        print(f"    ... {len(changed) - 120} more")


def print_key_diffs(before: dict[str, object], after: dict[str, object], max_lines: int) -> None:
    before_texts = before["key_texts"]
    after_texts = after["key_texts"]
    names = sorted(set(before_texts) | set(after_texts))
    print("\nKey Text Diffs")
    for name in names:
        before_text = before_texts.get(name)
        after_text = after_texts.get(name)
        if before_text == after_text:
            continue
        print(f"\n--- {name}")
        if before_text is None:
            print("  only present after")
            continue
        if after_text is None:
            print("  only present before")
            continue
        diff = list(
            difflib.unified_diff(
                before_text.splitlines(),
                after_text.splitlines(),
                fromfile=f"before/{name}",
                tofile=f"after/{name}",
                lineterm="",
                n=3,
            )
        )
        for line in diff[:max_lines]:
            print(line)
        if len(diff) > max_lines:
            print(f"... diff truncated, {len(diff) - max_lines} more lines")


def print_info_bin_delta(before: dict[str, object], after: dict[str, object]) -> None:
    before_info = before["info_bin_summary"]
    after_info = after["info_bin_summary"]
    print("\ninfo.bin Delta")
    if not before_info or not after_info:
        print("  info.bin missing from one side")
        return
    if before_info.get("parse_error") or after_info.get("parse_error"):
        print(f"  before parse error: {before_info.get('parse_error')}")
        print(f"  after parse error: {after_info.get('parse_error')}")
        return

    print(f"  size: {before_info['size']} -> {after_info['size']}")
    print(f"  catalog fields: {before_info['catalog_fields']} -> {after_info['catalog_fields']}")

    print_set_delta("  Image Names", set(before_info["image_names"]), set(after_info["image_names"]))
    print_set_delta("  Database Columns", set(before_info["database_columns"]), set(after_info["database_columns"]))

    before_records = {record.get("caption"): record for record in before_info["image_records"]}
    after_records = {record.get("caption"): record for record in after_info["image_records"]}
    print_set_delta("  Image Records", set(before_records), set(after_records))

    before_categories = {(record.get("caption"), record.get("category")) for record in before_info["image_categories"]}
    after_categories = {(record.get("caption"), record.get("category")) for record in after_info["image_categories"]}
    print_set_delta("  Image Categories", before_categories, after_categories)

    before_resources = {record.get("filename"): record for record in before_info["resource_records"]}
    after_resources = {record.get("filename"): record for record in after_info["resource_records"]}
    print_set_delta("  Resource Blobs", set(before_resources), set(after_resources))

    changed_resources = []
    for filename in sorted(set(before_resources) & set(after_resources)):
        if before_resources[filename] != after_resources[filename]:
            changed_resources.append(filename)
    print(f"\n  changed resource blobs: {len(changed_resources)}")
    for filename in changed_resources[:80]:
        print(f"    * {filename}")
        print(f"      before: {before_resources[filename]}")
        print(f"      after:  {after_resources[filename]}")

    changed = []
    for caption in sorted(set(before_records) & set(after_records)):
        if before_records[caption] != after_records[caption]:
            changed.append(caption)
    print(f"\n  changed image records: {len(changed)}")
    for caption in changed[:80]:
        print(f"    * {caption}")
        print(f"      before: {before_records[caption]}")
        print(f"      after:  {after_records[caption]}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--max-diff-lines", type=int, default=220)
    args = parser.parse_args(argv)

    before = read_package(args.before)
    after = read_package(args.after)

    print(f"Before: {before['label']}")
    print(f"After:  {after['label']}")
    print_set_delta("Files", set(before["hashes"]), set(after["hashes"]))
    print_changed_files(before, after)
    print_set_delta("Image Metadata Files", set(before["image_info"]), set(after["image_info"]))
    print_key_diffs(before, after, args.max_diff_lines)
    print_info_bin_delta(before, after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
