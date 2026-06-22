#!/usr/bin/env python3
"""Analyze a SmartCanvas import/export result for an experimental image dropdown patch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from compare_smartcanvas_dropdown_signals import build_delta as build_dropdown_delta
from compare_smartcanvas_dropdown_signals import load_signals
from inspect_smartcanvas_binaries import build_delta as build_binary_delta
from inspect_smartcanvas_binaries import build_summary as build_binary_summary


def default_manifest_path(experiment: Path) -> Path:
    if experiment.suffix:
        return experiment.with_name(f"{experiment.name}.experiment-manifest.json")
    return experiment.parent / f"{experiment.name}-experiment-manifest.json"


def load_manifest(path: Path | None, experiment: Path) -> dict[str, object] | None:
    manifest_path = path or default_manifest_path(experiment)
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def changed_after_map(delta: dict[str, object]) -> dict[str, object]:
    return {str(item.get("key")): item.get("after") for item in delta.get("changed", [])}


def changed_before_map(delta: dict[str, object]) -> dict[str, object]:
    return {str(item.get("key")): item.get("before") for item in delta.get("changed", [])}


def added_set(delta: dict[str, object]) -> set[str]:
    return {repr(item) for item in delta.get("added", [])}


def removed_set(delta: dict[str, object]) -> set[str]:
    return {repr(item) for item in delta.get("removed", [])}


def compare_expected_changed(expected: dict[str, object], actual: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    preserved = {}
    normalized = {}
    missing = {}
    for key, expected_after in expected.items():
        if key in actual:
            if actual[key] == expected_after:
                preserved[key] = expected_after
            else:
                normalized[key] = {"expected": expected_after, "actual": actual[key]}
        elif key in baseline:
            missing[key] = {"expected": expected_after, "actual": baseline[key]}
        else:
            missing[key] = {"expected": expected_after, "actual": None}
    return {"preserved": preserved, "normalized": normalized, "missing": missing}


def compare_expected_added(expected: set[str], actual: set[str], removed: set[str]) -> dict[str, object]:
    preserved = sorted(expected & actual)
    missing = sorted(expected - actual)
    explicitly_removed = sorted(expected & removed)
    return {"preserved": preserved, "missing": missing, "explicitly_removed": explicitly_removed}


def control_expectation_report(intended: dict[str, object], result: dict[str, object]) -> dict[str, object]:
    intended_controls = intended["controls"]
    result_controls = result["controls"]
    report = {
        "docmodels": compare_expected_changed(
            changed_after_map(intended_controls["docmodels"]),
            changed_after_map(result_controls["docmodels"]),
            changed_before_map(result_controls["docmodels"]),
        ),
        "template_xml_interesting_attributes": compare_expected_changed(
            changed_after_map(intended_controls["template_xml_interesting_attributes"]),
            changed_after_map(result_controls["template_xml_interesting_attributes"]),
            changed_before_map(result_controls["template_xml_interesting_attributes"]),
        ),
        "template_dhtt_sections": compare_expected_changed(
            changed_after_map(intended_controls["template_dhtt_sections"]),
            changed_after_map(result_controls["template_dhtt_sections"]),
            changed_before_map(result_controls["template_dhtt_sections"]),
        ),
        "template_dhtt_interesting_attributes": compare_expected_added(
            added_set(intended_controls["template_dhtt_interesting_attributes"]),
            added_set(result_controls["template_dhtt_interesting_attributes"]),
            removed_set(result_controls["template_dhtt_interesting_attributes"]),
        ),
        "catalog_image_xml_references": compare_expected_added(
            added_set(intended_controls["catalog_image_xml_references"]),
            added_set(result_controls["catalog_image_xml_references"]),
            removed_set(result_controls["catalog_image_xml_references"]),
        ),
    }
    return report


def count_nested_items(value: object, key: str) -> int:
    if isinstance(value, dict):
        item = value.get(key)
        if isinstance(item, dict):
            return len(item)
        if isinstance(item, list):
            return len(item)
    return 0


def summarize_expectations(report: dict[str, object]) -> dict[str, int]:
    preserved = 0
    normalized = 0
    missing = 0
    for value in report.values():
        preserved += count_nested_items(value, "preserved")
        normalized += count_nested_items(value, "normalized")
        missing += count_nested_items(value, "missing")
        missing += count_nested_items(value, "explicitly_removed")
    return {"preserved": preserved, "normalized": normalized, "missing": missing}


def delta_count_summary(delta: dict[str, object]) -> dict[str, object]:
    controls = delta["controls"]
    catalog = delta["catalog"]
    options = delta["options"]
    return {
        "image_records_changed": len(catalog["image_records"]["changed"]),
        "image_records_added": len(catalog["image_records"]["added"]),
        "image_records_removed": len(catalog["image_records"]["removed"]),
        "image_categories_added": len(catalog["image_category_records"]["added"]),
        "image_categories_removed": len(catalog["image_category_records"]["removed"]),
        "option_groups_changed": len(options["option_groups"]["changed"]),
        "docmodels_changed": len(controls["docmodels"]["changed"]),
        "template_xml_interesting_attributes_changed": len(controls["template_xml_interesting_attributes"]["changed"]),
        "template_dhtt_sections_changed": len(controls["template_dhtt_sections"]["changed"]),
        "template_dhtt_interesting_attributes_added": len(controls["template_dhtt_interesting_attributes"]["added"]),
        "catalog_image_xml_references_added": len(controls["catalog_image_xml_references"]["added"]),
        "css_dynamic_classes_added": len(controls["css_dynamic_classes"]["added"]),
        "css_dynamic_classes_removed": len(controls["css_dynamic_classes"]["removed"]),
    }


def binary_count_summary(delta: dict[str, object]) -> dict[str, int]:
    return {
        "added": len(delta["binaries"]["added"]),
        "removed": len(delta["binaries"]["removed"]),
        "changed": len(delta["binaries"]["changed"]),
    }


def classify(expectation_counts: dict[str, int], normalization_delta: dict[str, object]) -> str:
    if expectation_counts["missing"]:
        if expectation_counts["preserved"] or expectation_counts["normalized"]:
            return "partially_preserved"
        return "dropped_or_rejected"
    if expectation_counts["normalized"]:
        return "normalized"
    if expectation_counts["preserved"] and not normalization_has_changes(normalization_delta):
        return "preserved_exactly"
    if expectation_counts["preserved"]:
        return "preserved_with_other_changes"
    return "no_expected_dropdown_signal"


def normalization_has_changes(delta: dict[str, object]) -> bool:
    summary = delta_count_summary(delta)
    return any(value for value in summary.values())


def build_analysis(source: Path, experiment: Path, returned: Path, manifest_path: Path | None) -> dict[str, object]:
    manifest = load_manifest(manifest_path, experiment)
    source_signals = load_signals(source)
    experiment_signals = load_signals(experiment)
    returned_signals = load_signals(returned)

    intended_delta = build_dropdown_delta(source_signals, experiment_signals)
    result_delta = build_dropdown_delta(source_signals, returned_signals)
    normalization_delta = build_dropdown_delta(experiment_signals, returned_signals)
    expectations = control_expectation_report(intended_delta, result_delta)
    expectation_counts = summarize_expectations(expectations)

    source_binaries = build_binary_summary(source)
    experiment_binaries = build_binary_summary(experiment)
    returned_binaries = build_binary_summary(returned)
    binary_deltas = {
        "source_to_experiment": build_binary_delta(source_binaries, experiment_binaries),
        "source_to_returned": build_binary_delta(source_binaries, returned_binaries),
        "experiment_to_returned": build_binary_delta(experiment_binaries, returned_binaries),
    }

    return {
        "source": str(source),
        "experiment": str(experiment),
        "returned": str(returned),
        "manifest": manifest,
        "classification": classify(expectation_counts, normalization_delta),
        "expectation_counts": expectation_counts,
        "expectations": expectations,
        "delta_summaries": {
            "source_to_experiment": delta_count_summary(intended_delta),
            "source_to_returned": delta_count_summary(result_delta),
            "experiment_to_returned": delta_count_summary(normalization_delta),
        },
        "binary_summaries": {
            "source_to_experiment": binary_count_summary(binary_deltas["source_to_experiment"]),
            "source_to_returned": binary_count_summary(binary_deltas["source_to_returned"]),
            "experiment_to_returned": binary_count_summary(binary_deltas["experiment_to_returned"]),
        },
        "deltas": {
            "source_to_experiment": intended_delta,
            "source_to_returned": result_delta,
            "experiment_to_returned": normalization_delta,
        },
        "binary_deltas": binary_deltas,
        "notes": [
            "preserved_exactly means the returned export kept the expected control-surface changes and no focused dropdown signal changed between experiment and returned.",
            "normalized means SmartCanvas kept the expected control keys but rewrote one or more expected values.",
            "dropped_or_rejected means the returned export does not contain the expected dropdown control signals.",
            "This analyzer still needs a real SmartCanvas returned export to prove the actual Standard schema.",
        ],
    }


def print_summary(analysis: dict[str, object], limit: int) -> None:
    print("SmartCanvas Dropdown Experiment Result")
    print(f"Source:     {analysis['source']}")
    print(f"Experiment: {analysis['experiment']}")
    print(f"Returned:   {analysis['returned']}")
    print(f"Classification: {analysis['classification']}")
    if analysis.get("manifest"):
        selected = (analysis["manifest"] or {}).get("selected_group", {})
        print(f"Manifest group: {selected.get('group_key', '')}")
        print(f"Manifest image: {selected.get('selected_caption', '')}")
    counts = analysis["expectation_counts"]
    print(f"Expected controls preserved/normalized/missing: {counts['preserved']}/{counts['normalized']}/{counts['missing']}")

    print("\nDelta Summaries")
    for name, summary in analysis["delta_summaries"].items():
        print(f"  {name}: {summary}")

    print("\nBinary Summaries")
    for name, summary in analysis["binary_summaries"].items():
        print(f"  {name}: {summary}")

    print("\nExpectation Details")
    for section, detail in analysis["expectations"].items():
        print(f"  {section}")
        for key in ("preserved", "normalized", "missing", "explicitly_removed"):
            value = detail.get(key) if isinstance(detail, dict) else None
            count = len(value) if isinstance(value, (dict, list)) else 0
            print(f"    {key}: {count}")
            if isinstance(value, dict):
                for item_key, item_value in list(value.items())[:limit]:
                    print(f"      * {item_key}: {item_value}")
            elif isinstance(value, list):
                for item in value[:limit]:
                    print(f"      * {item}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Original source package before the experiment")
    parser.add_argument("experiment", type=Path, help="Experimental package generated by make_smartcanvas_image_dropdown_experiment.py")
    parser.add_argument("returned", type=Path, help="Package exported back from SmartCanvas after importing the experiment")
    parser.add_argument("--manifest", type=Path, help="Experiment manifest JSON; defaults to sibling manifest next to experiment")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON analysis to this file")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args(argv)

    for label, path in (("source", args.source), ("experiment", args.experiment), ("returned", args.returned)):
        if not path.exists():
            parser.error(f"{label} path does not exist: {path}")
    if args.manifest and not args.manifest.exists():
        parser.error(f"manifest path does not exist: {args.manifest}")

    analysis = build_analysis(args.source, args.experiment, args.returned, args.manifest)
    if args.output:
        args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.format == "json" and not args.output:
        print(json.dumps(analysis, indent=2, sort_keys=True))
    elif args.format == "text":
        print_summary(analysis, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
