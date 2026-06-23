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

When the user asks for an image dropdown and does not provide placement, ask for the X/Y coordinates if it is natural to clarify before running. If they do not provide coordinates, use `--left 0 --top 0`. All images in the dropdown should be placed at the same X/Y position and share the same size/margins.

The script patches `Document.xml` and `smartcampaign.xml`, adds/updates the Image List form field, switches, switched layers, picture nodes, image categories, and image files/sidecars. It preserves the outer SmartCanvas export ZIP shape when the input has nested `Admin/<campaign>.zip`. The image input may be a nested directory or ZIP; non-image files are ignored, subfolders become category names such as `level2/levelA`, and duplicate image basenames are made unique for SmartCanvas's flat `images/` folder. Existing-library mode reuses images already under the campaign `images/` folder and does not duplicate their binary files.
