#!/usr/bin/env python3
"""Validate SmartCanvas image catalog assets for dropdown probe readiness."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analyze_smartcanvas_options import build_option_analysis
from export_smartcanvas_catalog import build_manifest, read_package
from inspect_smartcanvas_image_derivatives import build_summary as build_derivative_summary
from inspect_smartcanvas_image_metadata import build_summary as build_metadata_summary


def issue(severity: str, code: str, message: str, caption: str = "", details: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "severity": severity,
        "code": code,
        "caption": caption,
        "message": message,
        "details": details or {},
    }


def records_by_caption(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(record.get("caption", "")): record for record in records}


def selected_group_captions(option_analysis: dict[str, object], group_filter: str | None) -> set[str] | None:
    if not group_filter:
        return None
    captions: set[str] = set()
    needle = group_filter.lower()
    for group in option_analysis.get("option_groups", []):
        if needle not in str(group.get("group_key", "")).lower():
            continue
        for image in group.get("images", []):
            caption = str(image.get("caption", ""))
            if caption:
                captions.add(caption)
    return captions


def build_summary(path: Path, group_filter: str | None = None) -> dict[str, object]:
    source_label, files = read_package(path)
    catalog = build_manifest(source_label, files)
    options = build_option_analysis(catalog)
    derivatives = build_derivative_summary(path)
    metadata = build_metadata_summary(path)

    allowed_captions = selected_group_captions(options, group_filter)
    derivative_records = records_by_caption(derivatives.get("records", []))
    metadata_records = records_by_caption(metadata.get("records", []))
    image_records = [
        image
        for image in catalog.get("images", [])
        if allowed_captions is None or str(image.get("caption", "")) in allowed_captions
    ]

    duplicate_hashes = duplicate_digest_map(image_records)
    image_readiness = []
    all_issues: list[dict[str, object]] = []
    for image in image_records:
        caption = str(image.get("caption", ""))
        image_issues = validate_image_record(
            image,
            derivative_records.get(caption, {}),
            metadata_records.get(caption, {}),
            duplicate_hashes.get(str(image.get("catalog_hash_sha1") or ""), []),
        )
        all_issues.extend(image_issues)
        image_readiness.append(
            {
                "caption": caption,
                "category": image.get("category") or "",
                "original_paths": image.get("original_paths") or [],
                "thumbi_paths": image.get("thumbi_paths") or [],
                "thumbn_paths": image.get("thumbn_paths") or [],
                "scaled_asset_paths": image.get("scaled_asset_paths") or [],
                "error_count": sum(1 for item in image_issues if item["severity"] == "error"),
                "warning_count": sum(1 for item in image_issues if item["severity"] == "warning"),
                "issues": image_issues,
            }
        )

    group_readiness = build_group_readiness(options, image_readiness, group_filter)
    issue_counts = Counter(item["severity"] for item in all_issues)
    summary = {
        "source": catalog.get("source"),
        "group_filter": group_filter or "",
        "image_count": len(image_records),
        "catalog_image_count": len(catalog.get("images", [])),
        "ready_for_dropdown_probe": issue_counts.get("error", 0) == 0,
        "error_count": issue_counts.get("error", 0),
        "warning_count": issue_counts.get("warning", 0),
        "issue_code_counts": dict(sorted(Counter(str(item["code"]) for item in all_issues).items())),
        "catalog_counts": {
            "sidecar_filesize_matches_actual": catalog.get("sidecar_filesize_matches_actual"),
            "sidecar_filesize_mismatches_actual": catalog.get("sidecar_filesize_mismatches_actual"),
            "categories": {key: len(value) for key, value in sorted((catalog.get("categories") or {}).items())},
        },
        "metadata_counts": {
            "embedded_record_count": metadata.get("embedded_record_count"),
            "sidecar_count": metadata.get("sidecar_count"),
            "embedded_sidecar_exact_match_count": metadata.get("embedded_sidecar_exact_match_count"),
            "embedded_sidecar_exact_mismatch_count": metadata.get("embedded_sidecar_exact_mismatch_count"),
            "missing_sidecar_count": metadata.get("missing_sidecar_count"),
            "parsed_metadata_mismatch_count": metadata.get("parsed_metadata_mismatch_count"),
        },
        "derivative_counts": derivatives.get("counts", {}),
        "candidate_dropdown_count": len(group_readiness),
        "candidate_dropdowns": group_readiness,
        "images": image_readiness,
        "issues": all_issues,
        "notes": [
            "Errors mean the catalog, original file, hash, size, or embedded metadata is internally inconsistent.",
            "Warnings identify dropdown-planning risks or demo-observed generated assets that may need SmartCanvas to regenerate.",
            "This validates image asset readiness only; it does not prove the SmartCanvas dropdown control XML schema.",
        ],
    }
    return summary


def duplicate_digest_map(images: list[dict[str, object]]) -> dict[str, list[str]]:
    captions_by_hash: dict[str, list[str]] = defaultdict(list)
    for image in images:
        digest = str(image.get("catalog_hash_sha1") or "")
        caption = str(image.get("caption") or "")
        if digest and caption:
            captions_by_hash[digest].append(caption)
    return {digest: sorted(captions) for digest, captions in captions_by_hash.items() if len(captions) > 1}


def validate_image_record(
    image: dict[str, object],
    derivatives: dict[str, object],
    metadata: dict[str, object],
    duplicate_captions: list[str],
) -> list[dict[str, object]]:
    caption = str(image.get("caption", ""))
    issues: list[dict[str, object]] = []
    verification = image.get("verification") if isinstance(image.get("verification"), dict) else {}
    sidecar = image.get("sidecar") if isinstance(image.get("sidecar"), dict) else None
    originals = image.get("original_paths") or []
    thumbi = image.get("thumbi_paths") or []
    thumbn = image.get("thumbn_paths") or []
    scaled_assets = image.get("scaled_asset_paths") or []

    if not caption:
        issues.append(issue("error", "missing_caption", "catalog image record has no caption"))
    if not image.get("catalog_hash_sha1"):
        issues.append(issue("error", "missing_catalog_hash", "catalog image record has no SHA-1 hash", caption))
    if image.get("declared_size") is None:
        issues.append(issue("error", "missing_declared_size", "catalog image record has no declared file size", caption))
    if not originals:
        issues.append(issue("error", "missing_original", "catalog image has no matching archived original image", caption))
    elif len(originals) > 1:
        issues.append(issue("warning", "multiple_original_paths", "caption resolves to multiple archived image paths", caption, {"paths": originals}))

    if verification:
        if not verification.get("file_found", True):
            issues.append(issue("error", "verification_file_missing", "info.bin image record points to a missing original", caption))
        if verification.get("size_match") is False:
            issues.append(issue("error", "declared_size_mismatch", "info.bin declared size does not match original file bytes", caption))
        if verification.get("sha1_match") is False:
            issues.append(issue("error", "catalog_sha1_mismatch", "info.bin SHA-1 does not match original file bytes", caption))

    if sidecar is None:
        issues.append(issue("error", "missing_sidecar", "catalog image has no matching _info.xml sidecar", caption))
    else:
        if image.get("sidecar_filesize_matches_actual") is False:
            issues.append(
                issue(
                    "warning",
                    "sidecar_filesize_differs",
                    "sidecar Filesize differs from archived original byte size; this is expected in the demo but should be tracked",
                    caption,
                    {"sidecar_filesize": sidecar.get("filesize"), "actual_size": image.get("actual_size")},
                )
            )
        if sidecar.get("caption") and sidecar.get("caption") != caption:
            issues.append(issue("error", "sidecar_caption_mismatch", "sidecar Caption does not match catalog caption", caption))
        if sidecar.get("group_name"):
            issues.append(issue("warning", "sidecar_group_name_set", "sidecar GroupName is set; demo categories live in info.bin instead", caption))

    if not metadata:
        issues.append(issue("error", "missing_embedded_metadata_record", "no embedded image metadata record found in info.bin", caption))
    else:
        if not metadata.get("sidecar_found", True):
            issues.append(issue("error", "metadata_sidecar_missing", "embedded metadata has no matching sidecar", caption))
        if metadata.get("embedded_matches_sidecar_exactly") is False:
            issues.append(issue("error", "embedded_sidecar_mismatch", "embedded metadata XML differs from the _info.xml sidecar", caption))
        if metadata.get("parsed_metadata_mismatches"):
            issues.append(
                issue(
                    "error",
                    "parsed_metadata_mismatch",
                    "parsed embedded metadata fields differ from sidecar fields",
                    caption,
                    {"fields": metadata.get("parsed_metadata_mismatches")},
                )
            )

    if derivatives:
        if derivatives.get("original_dimensions_match_sidecar") is False:
            issues.append(issue("error", "dimension_mismatch", "original image dimensions do not match sidecar ImageWidth/ImageHeight", caption))
        for asset_kind in ("originals", "thumbi", "thumbn", "scaled"):
            for asset in derivatives.get(asset_kind, []) or []:
                if asset.get("parse_error"):
                    issues.append(
                        issue(
                            "error",
                            f"{asset_kind}_parse_error",
                            f"{asset_kind} image asset could not be parsed",
                            caption,
                            {"path": asset.get("path"), "parse_error": asset.get("parse_error")},
                        )
                    )

    if not thumbi:
        issues.append(issue("warning", "missing_thumbi", "missing _thumbi.png thumbnail asset", caption))
    if not thumbn:
        issues.append(issue("warning", "missing_thumbn", "missing _thumbn.png thumbnail asset", caption))
    if sidecar and sidecar.get("scalings") and not scaled_assets:
        issues.append(issue("warning", "missing_scaled_derivative", "sidecar Scalings value is set but no scaled derivative asset was found", caption))
    if not image.get("category"):
        issues.append(issue("warning", "uncategorized_image", "image has no category record in info.bin field 26", caption))
    if duplicate_captions:
        issues.append(
            issue(
                "warning",
                "duplicate_sha1_caption_copy",
                "same original image hash is used by multiple captions; likely category/gallery copies",
                caption,
                {"captions": duplicate_captions},
            )
        )
    return issues


def build_group_readiness(
    option_analysis: dict[str, object],
    image_readiness: list[dict[str, object]],
    group_filter: str | None,
) -> list[dict[str, object]]:
    readiness_by_caption = {str(image.get("caption", "")): image for image in image_readiness}
    groups = []
    needle = group_filter.lower() if group_filter else ""
    for group in option_analysis.get("option_groups", []):
        group_key = str(group.get("group_key", ""))
        if needle and needle not in group_key.lower():
            continue
        captions = [str(image.get("caption", "")) for image in group.get("images", [])]
        selected = [readiness_by_caption[caption] for caption in captions if caption in readiness_by_caption]
        if not selected:
            continue
        errors = sum(int(image.get("error_count", 0)) for image in selected)
        warnings = sum(int(image.get("warning_count", 0)) for image in selected)
        groups.append(
            {
                "group_key": group_key,
                "image_count": len(selected),
                "unique_option_count": len(group.get("unique_options", [])),
                "option_numbers": group.get("option_numbers", []),
                "ready_for_dropdown_probe": errors == 0,
                "error_count": errors,
                "warning_count": warnings,
                "categories": group.get("categories", {}),
            }
        )
    return groups


def image_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for image in summary.get("images", []):
        rows[str(image.get("caption", ""))] = {
            "category": image.get("category"),
            "error_count": image.get("error_count"),
            "warning_count": image.get("warning_count"),
            "issue_codes": [item.get("code") for item in image.get("issues", [])],
            "original_paths": image.get("original_paths"),
            "thumbi_paths": image.get("thumbi_paths"),
            "thumbn_paths": image.get("thumbn_paths"),
            "scaled_asset_paths": image.get("scaled_asset_paths"),
        }
    return rows


def group_rows(summary: dict[str, object]) -> dict[str, object]:
    rows = {}
    for group in summary.get("candidate_dropdowns", []):
        rows[str(group.get("group_key", ""))] = group
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
        "ready_for_dropdown_probe": [before["ready_for_dropdown_probe"], after["ready_for_dropdown_probe"]],
        "image_count": [before["image_count"], after["image_count"]],
        "error_count": [before["error_count"], after["error_count"]],
        "warning_count": [before["warning_count"], after["warning_count"]],
        "issue_code_counts": map_delta(before.get("issue_code_counts", {}), after.get("issue_code_counts", {})),
        "candidate_dropdowns": map_delta(group_rows(before), group_rows(after)),
        "images": map_delta(image_rows(before), image_rows(after)),
    }


def print_summary(summary: dict[str, object], limit: int) -> None:
    status = "ready" if summary["ready_for_dropdown_probe"] else "not ready"
    print(f"Source: {summary['source']}")
    if summary.get("group_filter"):
        print(f"Group filter: {summary['group_filter']}")
    print(f"Images checked: {summary['image_count']} of {summary['catalog_image_count']}")
    print(f"Status: {status}")
    print(f"Errors: {summary['error_count']}")
    print(f"Warnings: {summary['warning_count']}")
    print(f"Candidate dropdowns: {summary['candidate_dropdown_count']}")
    if summary["issue_code_counts"]:
        print("Issue codes")
        for code, count in summary["issue_code_counts"].items():
            print(f"  {code}: {count}")
    print("\nImages")
    for image in summary["images"][:limit]:
        print(
            f"  - {image['caption']}: errors={image['error_count']}, "
            f"warnings={image['warning_count']}, category={image['category'] or '[uncategorized]'}"
        )
        for item in image["issues"][:limit]:
            print(f"      {item['severity']}: {item['code']} - {item['message']}")


def print_delta(delta: dict[str, object], limit: int) -> None:
    print(f"Before: {delta['before']}")
    print(f"After:  {delta['after']}")
    print(f"Ready: {delta['ready_for_dropdown_probe'][0]} -> {delta['ready_for_dropdown_probe'][1]}")
    print(f"Images: {delta['image_count'][0]} -> {delta['image_count'][1]}")
    print(f"Errors: {delta['error_count'][0]} -> {delta['error_count'][1]}")
    print(f"Warnings: {delta['warning_count'][0]} -> {delta['warning_count'][1]}")
    print_map_delta("Issue Codes", delta["issue_code_counts"], limit)
    print_map_delta("Candidate Dropdowns", delta["candidate_dropdowns"], limit)
    print_map_delta("Images", delta["images"], limit)


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
    parser.add_argument("--group", help="Only validate images in option groups whose name contains this text")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")
    if args.after and not args.after.exists():
        parser.error(f"after path does not exist: {args.after}")

    before = build_summary(args.path, args.group)
    result = build_delta(before, build_summary(args.after, args.group)) if args.after else before
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
