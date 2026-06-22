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

When the user asks for an image dropdown and does not provide placement, ask for the X/Y coordinates if it is natural to clarify before running. If they do not provide coordinates, use `--left 0 --top 0`. All images in the dropdown should be placed at the same X/Y position and share the same size/margins.

The script patches `Document.xml` and `smartcampaign.xml`, adds/updates the Image List form field, switches, switched layers, picture nodes, image categories, and image files/sidecars. It preserves the outer SmartCanvas export ZIP shape when the input has nested `Admin/<campaign>.zip`. The image input may be a nested directory or ZIP; non-image files are ignored, subfolders become category names such as `level2/levelA`, and duplicate image basenames are made unique for SmartCanvas's flat `images/` folder.
