---
name: smart-canvas
description: Work with EFI/DirectSmile SmartCanvas template exports, especially reverse-engineering package structure, inspecting template XML and image resources, comparing exported templates, preparing image assets/dropdowns for SmartCanvas imports, creating/manipulating text fields, text styles, QR codes/barcodes, and programmatically locking or unlocking template layers/objects.
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

When the user wants new dropdown images to match existing placed images, inspect the original export first. Prefer the page-aware locator when the same X/Y may exist on multiple pages or when the original layer must be removed:

```bash
python3 smart-canvas-skill/scripts/locate_smartcanvas_images.py \
  "template-export.zip" \
  --target 7.33,-0.125 \
  --target 3.6667,2.83 \
  --category "Front Panel" \
  --category "Back Panel - Contact Us" \
  --units inches
```

Use the matching `Picture` node's `page`, `Left`, `Top`, `Width`, `Height`, source, and layer details for placement/removal. SmartCanvas stores coordinates in points; pass `--units inches` when using user-facing inch measurements. If the locator is not needed, `inspect_smartcanvas_dropdown_context.py` remains available for quick nearest-picture/category checks.


To correct existing dropdown picture placement/size by crop and optionally lock layers, use the geometry helper. Rules are matched against layer display/switch names and picture sources, then written as SmartCanvas point values; pass `--units inches` for user-facing measurements:

```bash
python3 smart-canvas-skill/scripts/set_smartcanvas_picture_geometry.py \
  "template-export.zip" \
  "template-export-fixed.zip" \
  --units inches \
  --rule "Inside Middle Panel,Crop 2,3.6667,-0.125,3.6667,2.91" \
  --rule "Inside Middle Panel,Crop 1,3.6667,-0.125,3.6667,4.41" \
  --rule "Inside Middle Panel,Crop 3,3.6667,-0.125,3.6667,2.38" \
  --rule "Inside Middle Panel Secondary,Crop 3,3.6667,3.29,3.6667,2.37" \
  --lock-layers
```

Use this when existing image dropdown layers need exact bleed-aware dimensions without rebuilding the dropdown. Keep shared vertical edges numerically identical across related crop rules, such as using the same left and width for primary and secondary Crop 3 layers; tiny differences like 3.666 vs 3.6667 inches can rasterize as visible seams. Put more specific rules, such as secondary crop layers, alongside broader rules; the helper applies the most specific layer/crop match first.

To create a text field in a template export, run:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_text_field.py \
  "template-export.zip" \
  "template-export-with-text.zip" \
  --text "Customer Name" \
  --left 10 \
  --top 10 \
  --width 279 \
  --height 20.5 \
  --font "Arial Bold Italic" \
  --font-size 9 \
  --line-height 12 \
  --tracking 200 \
  --style-name "customer name style" \
  --layer-name "Text Layer"
```

When the user asks to add text and does not provide placement, ask for X/Y coordinates if it is natural to clarify before running. If they do not provide coordinates, use `--left 0 --top 0 --width 200 --height 40`. Use `--units inches` when the user gives measurements in inches; otherwise coordinates are points.

The text helper patches `Document.xml` by creating/reusing the named layer, creating/updating a `Resources/TextStyles/ParagraphStyle`, and adding a `Text` node inside the page `Composition`. It syncs `smartcampaign.xml` resources when present, or creates a minimal `smartcampaign.xml` when missing. It preserves the outer SmartCanvas export ZIP shape when the input has nested `Admin/<campaign>.zip`.

Supported `--font` values are: Arial, Arial Bold Italic, Arial Bold, Arial Italic, Calibri, Calibri Bold, Calibri Bold Italic, Calibri Italic, Century Gothic, Century Gothic Bold, Century Gothic Bold Italic, Century Gothic Italic, Comic Sans MS, Comic Sans MS Bold, Garamond, Garamond Bold, Garamond Italic, Times New Roman, Times New Roman Bold Italic, Times New Roman Bold, Times New Roman Italic, Trebuchet MS, Trebuchet MS Bold Italic, Trebuchet MS Bold, Trebuchet MS Italic.

To set a QR code to use a SmartCanvas form field, write the field placeholder into the QR `Barcode` node's `Content` attribute:

```bash
python3 smart-canvas-skill/scripts/set_smartcanvas_qr_content.py \
  "template-export.zip" \
  "template-export-with-qr-field.zip" \
  --field-name MyWebsite
```

The QR helper patches QR `Barcode` nodes in `Document.xml` where `BarCodeType="QRCode"` or `UI-BarCodeType` contains `QR`. `--field-name MyWebsite` writes `[[MyWebsite]]`; use `--content "literal value"` for a fixed QR payload. If more than one QR code matches, pass `--id <Barcode-ID>`, `--layer <Layer-ID>`, or `--all`.

To lock or unlock template layers/objects, use the lock helper. SmartCanvas layer locks are stored as `IsLocked="true"` on `Layer` entries in `Document.xml`; object-level locks are stored on `DocModel` entries in `template.xml`. To lock every layer/object:

```bash
python3 smart-canvas-skill/scripts/set_smartcanvas_locks.py \
  "template-export.zip" \
  "template-export-locked.zip" \
  --state locked \
  --all
```

To unlock everything, pass `--state unlocked --all`. Unlocking removes `IsLocked` from `Document.xml` layers, matching observed SmartCanvas exports for unlocked layers. To target specific content, use `--layer-name "Layer Display Name"` for that layer and objects assigned to it, or `--contains "text or filename"` for layers/objects whose XML attributes/text include a value. Repeat selectors as needed. The helper preserves the nested `Admin/<campaign>.zip` package shape and reports matched/changed layer and `DocModel` counts.

After writing a dropdown export, verify the fields and placements:

```bash
python3 smart-canvas-skill/scripts/verify_smartcanvas_dropdowns.py \
  "template-export-with-dropdown.zip" \
  --field-name Front-Panel \
  --field-name Back-Panel-Testimony-OFA
```

When the user asks for an image dropdown and does not provide placement, ask for the X/Y coordinates if it is natural to clarify before running. If they do not provide coordinates, use `--left 0 --top 0`. All images in the dropdown should be placed at the same X/Y position and share the same size/margins.

The dropdown helpers sanitize `--field-name` to SmartCanvas-safe identifiers containing only letters, numbers, `_`, and `-`; for example `Inside - Msgs of Help 1/3` becomes `Inside-Msgs-of-Help-1-3`. Use the sanitized field names for verification. Switches/layers are scoped by sanitized field name and option index, so separate dropdowns can safely reuse the same image filenames/categories.

The dropdown scripts patch `Document.xml` and `smartcampaign.xml`, add/update the Image List form field, switches, switched layers, picture nodes, image categories, and image files/sidecars. They preserve the outer SmartCanvas export ZIP shape when the input has nested `Admin/<campaign>.zip`. External image input may be a nested directory or ZIP; non-image files are ignored, subfolders become category names such as `level2/levelA`, and duplicate image basenames are made unique for SmartCanvas's flat `images/` folder. Existing-library mode reuses images already under the campaign `images/` folder and does not duplicate their binary files.


