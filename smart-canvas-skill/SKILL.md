---
name: smart-canvas
description: Work with EFI/DirectSmile SmartCanvas template exports, especially reverse-engineering package structure, inspecting template XML and image resources, comparing exported templates, and preparing image assets/dropdowns for SmartCanvas imports.
---

To create an image-list dropdown in a template export, run:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_image_dropdown.py \
  "template-export.zip" \
  "image-folder-or-assets.zip" \
  "template-export-with-dropdown.zip" \
  --field-name image_dropdown_1 \
  --category Test_category \
  --left 0 \
  --top 0
```

To create a dropdown from images that are already in the SmartCanvas image library, omit the external image source and select the existing catalog folder/category:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_image_dropdown.py \
  "template-export.zip" \
  "template-export-with-dropdown.zip" \
  --library-folder "European CRP 2" \
  --field-name European-CRP2 \
  --category "European CRP2" \
  --left 7.335 \
  --top 5.6838 \
  --width 3.79 \
  --units inches
```

Use `--library-folder` when the export's `info.bin` catalog contains labels such as `European CRP2`, even if the ZIP paths and `_info.xml` sidecars do not preserve that folder name. Folder matching normalizes punctuation and spaces, so `European CRP 2` can match `European CRP2`. Use `--library-filter` for a filename/category substring fallback such as `crp2`.

When a category name is a substring of another category, or when one dropdown must include multiple categories, use the exact-category helper:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_library_dropdown.py \
  "template-export.zip" \
  "template-export-with-dropdown.zip" \
  --field-name Back-Panel-Testimony-OFA \
  --category "Back Panel - Testimony" \
  --category "Back Panel - OF&A" \
  --left 3.6667 \
  --top -0.125 \
  --width 3.6667 \
  --height 2.9583 \
  --units inches
```

When the user wants new dropdown images to match existing placed images, inspect the original export first:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_dropdown_context.py \
  "template-export.zip" \
  --target 7.33,-0.125 \
  --target 3.6667,2.83 \
  --category "Front Panel" \
  --category "Back Panel - Contact Us" \
  --units inches
```

Use the nearest `Picture` node's `Left`, `Top`, `Width`, and `Height` values for the dropdown's placement unless the user gives an override. SmartCanvas stores coordinates in points; pass `--units inches` when using user-facing inch measurements.

After writing a dropdown export, verify the fields and placements:

```bash
python3 smart-canvas-skill/scripts/verify_smartcanvas_dropdowns.py \
  "template-export-with-dropdown.zip" \
  --field-name Front-Panel \
  --field-name Back-Panel-Testimony-OFA
```

When the user asks for an image dropdown and does not provide placement, ask for the X/Y coordinates if it is natural to clarify before running. If they do not provide coordinates, use `--left 0 --top 0`. All images in the dropdown should be placed at the same X/Y position and share the same size/margins.

The dropdown scripts patch `Document.xml` and `smartcampaign.xml`, add/update the Image List form field, switches, switched layers, picture nodes, image categories, and image files/sidecars. They preserve the outer SmartCanvas export ZIP shape when the input has nested `Admin/<campaign>.zip`. External image input may be a nested directory or ZIP; non-image files are ignored, subfolders become category names such as `level2/levelA`, and duplicate image basenames are made unique for SmartCanvas's flat `images/` folder. Existing-library mode reuses images already under the campaign `images/` folder and does not duplicate their binary files.
