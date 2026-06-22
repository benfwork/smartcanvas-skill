#!/usr/bin/env python3
"""Create and rebuild controlled SmartCanvas package edit workspaces."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from export_smartcanvas_catalog import normalize_member_name, read_package


MANIFEST_NAME = "smartcanvas-package-manifest.json"


def safe_relpath(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"unsafe archive/member path: {value}")
    return path


def ensure_empty_dir(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            if path.is_dir() and not any(path.iterdir()):
                return
            raise SystemExit(f"refusing to overwrite non-empty path: {path}; pass --force")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.mkdir(parents=True, exist_ok=True)


def ensure_output_path(path: Path, force: bool, *, directory: bool) -> None:
    if path.exists():
        if not force:
            raise SystemExit(f"refusing to overwrite {path}; pass --force")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    if directory:
        path.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)


def source_info(source: Path) -> dict[str, object]:
    if source.is_dir() and (source / "info.json").exists():
        admin_zips = sorted((source / "Admin").glob("*.zip"))
        if not admin_zips:
            raise SystemExit(f"outer export has no Admin/*.zip: {source}")
        return {"mode": "outer", "outer_path": source, "inner_zip": admin_zips[0]}
    if source.is_file() and source.suffix.lower() == ".zip":
        return {"mode": "inner_zip", "inner_zip": source}
    raise SystemExit(f"unsupported source; use an outer export folder or inner campaign zip: {source}")


def unpack(source: Path, workspace: Path, force: bool) -> dict[str, object]:
    info = source_info(source)
    ensure_empty_dir(workspace, force)
    inner_dir = workspace / "inner"
    inner_dir.mkdir()

    outer_files: list[dict[str, object]] = []
    if info["mode"] == "outer":
        outer_dir = workspace / "outer"
        outer_dir.mkdir()
        outer_path = Path(info["outer_path"])
        for file_path in sorted(path for path in outer_path.rglob("*") if path.is_file()):
            rel = file_path.relative_to(outer_path)
            if file_path.name.endswith(":Zone.Identifier"):
                continue
            if rel.parts and rel.parts[0] == "Admin":
                continue
            dest = outer_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest)
            outer_files.append({"path": rel.as_posix()})

    inner_entries = extract_inner_zip(Path(info["inner_zip"]), inner_dir)
    manifest = {
        "format": "smartcanvas-package-workspace-v1",
        "source": str(source),
        "mode": info["mode"],
        "admin_zip_name": Path(info["inner_zip"]).name,
        "outer_files": outer_files,
        "inner_entries": inner_entries,
    }
    write_manifest(workspace, manifest)
    return manifest


def extract_inner_zip(zip_path: Path, inner_dir: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    seen_normalized: set[str] = set()
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            normalized = normalize_member_name(info.filename)
            if not normalized:
                entries.append(zip_info_record(info, normalized, is_dir=True))
                continue
            if normalized in seen_normalized:
                raise SystemExit(f"duplicate normalized member path in {zip_path}: {normalized}")
            seen_normalized.add(normalized)
            record = zip_info_record(info, normalized, is_dir=info.is_dir())
            entries.append(record)
            if info.is_dir():
                (inner_dir / safe_relpath(normalized)).mkdir(parents=True, exist_ok=True)
                continue
            dest = inner_dir / safe_relpath(normalized)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(info.filename))
    return entries


def zip_info_record(info: zipfile.ZipInfo, normalized: str, *, is_dir: bool) -> dict[str, object]:
    return {
        "original_name": info.filename,
        "normalized_name": normalized,
        "is_dir": is_dir,
        "date_time": list(info.date_time),
        "compress_type": info.compress_type,
        "external_attr": info.external_attr,
        "comment_hex": info.comment.hex(),
    }


def read_manifest(workspace: Path) -> dict[str, object]:
    manifest_path = workspace / MANIFEST_NAME
    if not manifest_path.exists():
        raise SystemExit(f"workspace has no {MANIFEST_NAME}: {workspace}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_manifest(workspace: Path, manifest: dict[str, object]) -> None:
    (workspace / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pack(workspace: Path, output: Path, force: bool) -> dict[str, object]:
    manifest = read_manifest(workspace)
    mode = manifest.get("mode")
    if mode == "outer":
        ensure_output_path(output, force, directory=True)
        copy_outer_files(workspace, output, manifest)
        admin_dir = output / "Admin"
        admin_dir.mkdir(parents=True, exist_ok=True)
        inner_zip_path = admin_dir / str(manifest["admin_zip_name"])
        write_inner_zip(workspace, inner_zip_path, manifest)
        output_path = output
    elif mode == "inner_zip":
        ensure_output_path(output, force, directory=False)
        write_inner_zip(workspace, output, manifest)
        output_path = output
    else:
        raise SystemExit(f"unsupported workspace mode: {mode}")
    return {"mode": mode, "output": str(output_path)}


def copy_outer_files(workspace: Path, output: Path, manifest: dict[str, object]) -> None:
    outer_dir = workspace / "outer"
    for file_record in manifest.get("outer_files", []):
        rel = safe_relpath(str(file_record["path"]))
        source = outer_dir / rel
        if not source.exists():
            raise SystemExit(f"outer workspace file missing: {source}")
        dest = output / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def write_inner_zip(workspace: Path, output_zip: Path, manifest: dict[str, object]) -> None:
    inner_dir = workspace / "inner"
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w") as archive:
        for record in manifest.get("inner_entries", []):
            original_name = str(record["original_name"])
            normalized_name = str(record.get("normalized_name") or "")
            info = zipfile.ZipInfo(original_name)
            info.date_time = tuple(record.get("date_time") or (1980, 1, 1, 0, 0, 0))
            info.compress_type = int(record.get("compress_type", zipfile.ZIP_DEFLATED))
            info.external_attr = int(record.get("external_attr", 0))
            info.comment = bytes.fromhex(str(record.get("comment_hex", "")))
            if record.get("is_dir"):
                archive.writestr(info, b"")
                continue
            source = inner_dir / safe_relpath(normalized_name)
            if not source.exists():
                raise SystemExit(f"inner workspace file missing: {source}")
            archive.writestr(info, source.read_bytes())


def compare_payloads(before: Path, after: Path) -> dict[str, object]:
    before_label, before_files = read_package(before)
    after_label, after_files = read_package(after)
    before_keys = set(before_files)
    after_keys = set(after_files)
    changed = sorted(
        name for name in before_keys & after_keys if before_files[name] != after_files[name]
    )
    return {
        "before": before_label,
        "after": after_label,
        "added": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "changed": changed,
        "match": not (after_keys - before_keys or before_keys - after_keys or changed),
    }


def roundtrip_check(source: Path, work_dir: Path, force: bool) -> dict[str, object]:
    ensure_empty_dir(work_dir, force)
    workspace = work_dir / "workspace"
    manifest = unpack(source, workspace, force=False)
    output = work_dir / ("roundtrip-export" if manifest["mode"] == "outer" else "roundtrip.zip")
    pack_result = pack(workspace, output, force=False)
    delta = compare_payloads(source, output)
    return {"workspace": str(workspace), "packed": pack_result, "payload_delta": delta}


def print_unpack_result(manifest: dict[str, object], workspace: Path) -> None:
    file_entries = [entry for entry in manifest.get("inner_entries", []) if not entry.get("is_dir")]
    print(f"Workspace: {workspace}")
    print(f"Mode: {manifest['mode']}")
    print(f"Admin zip: {manifest['admin_zip_name']}")
    print(f"Outer files: {len(manifest.get('outer_files', []))}")
    print(f"Inner files: {len(file_entries)}")
    print(f"Manifest: {workspace / MANIFEST_NAME}")


def print_pack_result(result: dict[str, object]) -> None:
    print(f"Packed {result['mode']} package: {result['output']}")


def print_roundtrip_result(result: dict[str, object]) -> None:
    delta = result["payload_delta"]
    print(f"Workspace: {result['workspace']}")
    print(f"Packed: {result['packed']['output']}")
    print(f"Payload match: {delta['match']}")
    print(f"Added/removed/changed: {len(delta['added'])}/{len(delta['removed'])}/{len(delta['changed'])}")
    for label in ("added", "removed", "changed"):
        for item in delta[label][:40]:
            print(f"  {label}: {item}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    unpack_parser = subparsers.add_parser("unpack", help="Unpack an outer export or inner zip into an edit workspace")
    unpack_parser.add_argument("source", type=Path)
    unpack_parser.add_argument("workspace", type=Path)
    unpack_parser.add_argument("--force", action="store_true")
    unpack_parser.add_argument("--format", choices=("text", "json"), default="text")

    pack_parser = subparsers.add_parser("pack", help="Pack an edit workspace back into an outer export or inner zip")
    pack_parser.add_argument("workspace", type=Path)
    pack_parser.add_argument("output", type=Path)
    pack_parser.add_argument("--force", action="store_true")
    pack_parser.add_argument("--format", choices=("text", "json"), default="text")

    roundtrip_parser = subparsers.add_parser("roundtrip-check", help="Unpack, repack, and compare package payloads")
    roundtrip_parser.add_argument("source", type=Path)
    roundtrip_parser.add_argument("work_dir", type=Path)
    roundtrip_parser.add_argument("--force", action="store_true")
    roundtrip_parser.add_argument("--format", choices=("text", "json"), default="text")

    args = parser.parse_args(argv)

    if args.command == "unpack":
        if not args.source.exists():
            parser.error(f"source does not exist: {args.source}")
        result = unpack(args.source, args.workspace, args.force)
        if args.format == "json":
            print(json.dumps({"workspace": str(args.workspace), "manifest": result}, indent=2, sort_keys=True))
        else:
            print_unpack_result(result, args.workspace)
        return 0

    if args.command == "pack":
        result = pack(args.workspace, args.output, args.force)
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print_pack_result(result)
        return 0

    if args.command == "roundtrip-check":
        if not args.source.exists():
            parser.error(f"source does not exist: {args.source}")
        result = roundtrip_check(args.source, args.work_dir, args.force)
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print_roundtrip_result(result)
        return 0 if result["payload_delta"]["match"] else 1

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
