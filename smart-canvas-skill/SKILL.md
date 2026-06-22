---
name: smart-canvas
description: Work with EFI/DirectSmile SmartCanvas template exports, especially reverse-engineering package structure, inspecting template XML and image resources, comparing exported templates, and preparing image assets/dropdowns for SmartCanvas imports.
---

# SmartCanvas

Use this skill when inspecting or modifying SmartCanvas template exports.

## Workflow

1. Identify whether the input is an outer import/export folder, an inner campaign zip, or an already-extracted inner campaign folder.
2. For a new export, run `scripts/inspect_smartcanvas_package.py <path>` to summarize package contents, XML roots, image sidecars, and imposition duplication.
3. Before editing packages, run `scripts/smartcanvas_package_workspace.py roundtrip-check <path> work-dir/ --force` to prove unpack/repack produces zero payload changes.
4. Use `scripts/smartcanvas_package_workspace.py unpack <path> workspace/` and `pack workspace/ output/` for controlled edit experiments.
5. Run `scripts/inspect_smartcanvas_binaries.py <path>` to fingerprint `.bin` files, including opaque files such as `databases.bin`.
6. Run `scripts/dump_smartcanvas_info_bin.py <path> -o info-bin-dump.json` when you need grouped protobuf-wire field counts and samples from `info.bin`.
7. Run `scripts/compare_smartcanvas_info_bin_dumps.py <before> <after>` to compare two `info.bin` dumps or packages by known summary, top-level fields, and catalog field groups.
8. Run `scripts/export_smartcanvas_catalog.py <path> -o catalog.json` when you need a machine-readable image catalog for dropdown planning or generation.
9. Run `scripts/inspect_smartcanvas_image_metadata.py <path>` to verify `info.bin` embedded image metadata XML against `_info.xml` sidecars.
10. Run `scripts/inspect_smartcanvas_image_derivatives.py <path>` to measure original images, sidecars, thumbnails, and scaled derivative assets.
11. Run `scripts/validate_smartcanvas_image_assets.py <path>` to classify image catalog readiness errors versus warnings before using images as dropdown options.
12. Run `scripts/analyze_smartcanvas_options.py catalog.json` or pass a package path directly to infer candidate image option/dropdown groups from filenames, categories, hashes, and dimensions.
13. Run `scripts/make_smartcanvas_image_dropdown_blueprint.py <path> -o dropdown-blueprint.json --csv-output dropdown-blueprint.csv` to turn candidate option groups into practical dropdown planning records and a flat option table.
14. Run `scripts/make_smartcanvas_image_dropdown_experiment.py <source> <output> --group "<group>"` only for disposable import probes; it patches observed XML surfaces but does not prove the SmartCanvas dropdown schema.
15. After importing/exporting a disposable experiment, run `scripts/analyze_smartcanvas_dropdown_experiment_result.py <source> <experiment> <returned-export>` to classify whether SmartCanvas preserved, normalized, or dropped the candidate dropdown schema.
16. Run `scripts/inspect_smartcanvas_controls.py <path>` to summarize `template.xml`, `template.dhtt`, `Document.xml`, CSS dynamic classes, and catalog image references in key XML files.
17. Run `scripts/inspect_smartcanvas_database.py <path>` to summarize `template.xml` database columns, `info.bin` column strings, binding-looking XML attributes, and `[[Field]]` references.
18. Run `scripts/inspect_smartcanvas_xml_inventory.py <path>` or `<before> <after>` when a dropdown/control may use unanticipated XML tags or attributes.
19. Run `scripts/make_smartcanvas_dropdown_probe_images.py out-dir/ --stage-sidecars` to create distinctive probe option images for a clean dropdown before/after test.
20. Run `scripts/prepare_smartcanvas_images.py <source-images> <output-dir>` to stage original images with SmartCanvas-style `_info.xml` sidecars and a manifest. This does not rebuild `info.bin`, thumbnails, or scaled derivatives.
21. For image-dropdown before/after reverse-engineering, run `scripts/make_smartcanvas_dropdown_probe_bundle.py <before> <after> out-dir/` to generate catalogs, binary fingerprints, asset readiness reports, option analyses, dropdown blueprints, image derivative summaries, image metadata summaries, control summaries, database/binding summaries, XML inventory summaries, `info.bin` dumps, deltas, and a summary in one folder.
22. Run `scripts/compare_smartcanvas_dropdown_signals.py <before> <after>` when you only need the focused dropdown/control delta.
23. For raw package-level before/after reverse-engineering, run `scripts/compare_smartcanvas_packages.py <before> <after>`.
24. Read `references/package-structure.md` when you need the current reverse-engineered structure, naming patterns, binary fingerprint notes, image asset conventions, image readiness notes, image derivative notes, experimental dropdown writer/result notes, package workspace notes, control-surface notes, image metadata notes, XML inventory notes, database/binding notes, or `info.bin` catalog notes.
25. For image dropdown work, prefer comparing two exports:
   - a minimal template before adding the dropdown
   - the same template after adding one image dropdown with known options
26. Treat `.bin` files as generated unless a round-trip test proves a hand edit is accepted by SmartCanvas. `info.bin` is partly decoded for inspection, but not yet safe to rewrite.

## Current Findings

- The outer export can contain `info.json`, `Admin/<campaign>.zip`, `Impositions/*.xml`, and `PdfPresets/*.xml`.
- The workspace unpacker treats `Admin/<campaign>.zip` as canonical, skips extracted `Admin/<campaign>/` helper folders and `:Zone.Identifier` files, and roundtrips the demo with zero payload changes.
- The inner campaign zip contains `template.xml`, `template.dhtt`, `Document.xml`, `css.css`, image resources, generated thumbnails/metadata, and binary catalog files.
- In the demo export, `Impositions/` and `PdfPresets/` contain identical UUID-named XML files.
- Image sidecars use names like `Image_jpg_info.xml`, `Image_jpg_thumbi.png`, `Image_jpg_thumbn.png`, and optionally `Image_jpg/Image_jpg_900.jpg`.
- `info.bin` uses protobuf-style wire encoding. In the demo it lists 24 image names, 24 image records, 23 image category mappings, 167 database columns, and 75 resource blobs. Image record hashes are uppercase SHA-1 hashes of the original archived image bytes.
- In the demo, `template.xml` has 168 `DatabaseColumn` nodes: one empty included placeholder plus 167 named columns that exactly match the 167 `info.bin` column strings in order.
- In the demo, all 24 `info.bin` embedded image metadata XML blobs match their `_info.xml` sidecars byte-for-byte.
- In the demo, every sidecar `_info.xml` `Filesize` differs from the actual archived image byte size; the `info.bin` image record size and SHA-1 match the archived image bytes.
- In the demo, all 24 originals and `_thumbi.png` files exist, 23 `_thumbn.png` files exist, and 21 tall images have `727x1122` scaled derivatives.
- In the demo, `validate_smartcanvas_image_assets.py` reports zero readiness errors and 47 warnings: 24 sidecar `Filesize` differences, 21 duplicate-hash category copies, one missing `_thumbn.png`, and one uncategorized image.
- A disposable experiment package for the demo Intro group changes only `template.xml` and `template.dhtt`: one DynamicDocument `DocModel` receives `Class="DynamicImage1"`, `ImageSelector`, `ImageCategories`, and `ShowImageBrowser="True"`, and `template.dhtt` gets one `Images/Image` child. Binaries and `info.bin` catalog records remain unchanged. This is a probe, not confirmed SmartCanvas Standard schema.
- The experiment result analyzer classifies an unchanged experiment-as-returned package as `preserved_exactly` and the original source-as-returned package as `dropped_or_rejected`; use it on a real returned export to evaluate whether SmartCanvas accepted or rewrote the candidate schema.
- In the demo, `databases.bin` is 781 bytes, high entropy, unknown magic, and fails protobuf-wire parsing at offset 9; treat it as opaque but fingerprint it in before/after exports.
- The demo's `info.bin` resource blobs are embedded font resources, not image resources.
- The demo's `template.xml` has the document shell and style/settings data, but no obvious image dropdown control node.
- The demo key XML inventory has 5 files; `template.xml` has 220 elements and 37 schema paths, while `template.dhtt` has 42 elements and 24 schema paths.
- The demo's key XML files do not reference any of the 24 catalog image filenames; image availability appears to come from the image files/sidecars plus `info.bin`, while actual dropdown controls likely add separate XML nodes or attributes.
