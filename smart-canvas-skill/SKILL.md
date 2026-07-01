---
name: smart-canvas
description: Work with SmartCanvas template exports, including preparing and arranging image assets/dropdowns; creating/arranging shapes, lines, form fields, variables, text fields, text styles, QR codes/barcodes; setting page/canvas size and layout geometry; creating a new product from an approved blank seed export; and programmatically locking or unlocking template layers/objects.
---

For complex product creation, translate the user's visual constraints into the document geometry before adding objects. If the user says the design/product/page/layout is a square, make the SmartCanvas page square by setting the `Document` insert size, every `Page`, and every `Composition`, not just by drawing square artwork inside a non-square page. Use inches when the user gives print-like sizes; SmartCanvas stores the values as points.

```bash
python3 smart-canvas-skill/scripts/set_smartcanvas_page_size.py \
  "template-export.zip" \
  "template-export-square.zip" \
  --width 5 \
  --height 5 \
  --units inches
```

When composing several helper outputs, build background and structural layers first, then add foreground image/text/dropdown content. SmartCanvas layer order is visual order: lower layer indexes render above later layers. Dropdown image layers should be foreground by default so selected images remain visible on top of shape layers. The dropdown helper enforces this for its switch layers; if you manually edit layers, keep dropdown/text/content layers before decorative/background layers.

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

To create rectangles/squares, ovals/circles, lines, form fields, or computed variables, use the shapes/variables helper:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_shapes_variables.py \
  "template-export.zip" \
  "template-export-with-shapes.zip" \
  --shape-json '{"type":"rectangle","left":10,"top":30.5,"width":75.8,"height":84.2,"color":"swatch,R=237 G=247 B=163","opacity":1}' \
  --shape-json '{"type":"circle","left":120.5,"top":30.5,"width":84.2,"color":"#9bb7a7"}' \
  --line-json '{"left":17,"top":37.5,"width":236.8,"height":71.9,"color":"swatch,R=122 G=148 B=196","thickness":11.072,"opacity":0.53,"blend_mode":"Multiply"}'
```

Use `type` values `rectangle`, `square`, `ellipse`, `oval`, or `circle`. Shape colors are written to `Background`; line colors are written to `LineColor`. SmartCanvas accepts hex colors such as `#9bb7a7` and swatch strings such as `swatch,R=237 G=247 B=163`. `opacity` uses SmartCanvas decimal opacity, where `1` is fully opaque and `0.5` is 50%. Pass `--units inches` when using inch coordinates; line thickness is also converted from inches in that mode. The helper creates/reuses a layer named by `--layer-name` unless an individual JSON spec includes `"layer":"Layer Name"`.

To add form fields and variables, pass JSON specs or simple `Name=Expression` variables:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_shapes_variables.py \
  "template-export.zip" \
  "template-export-with-variables.zip" \
  --form-field-json '{"name":"FavoriteColor","value":"Red","display_type":"radio","options":["Red","Blue"]}' \
  --variable 'Greeting=[[FavoriteColor]]'
```

For SmartCanvas variable functions, use the built-in function catalog. It is based on `example-zip/variable-examples.zip` plus `references/variable-functions.md`; read that reference when choosing exact function names, arguments, or behavior.

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_shapes_variables.py --list-variable-functions

python3 smart-canvas-skill/scripts/create_smartcanvas_shapes_variables.py \
  "template-export.zip" \
  "template-export-with-all-function-vars.zip" \
  --all-variable-functions

python3 smart-canvas-skill/scripts/create_smartcanvas_shapes_variables.py \
  "template-export.zip" \
  "template-export-with-function-vars.zip" \
  --variable-function html-encode \
  --variable-function add \
  --function-variable-json '{"name":"CustomReplace","function":"replace","args":["abc","a","z"]}'
```

Use `--variable-function` for one of the built-in examples by key, variable name, or function name. Use `--variable-function-prefix` when adding examples to a template that may already contain same-named variables. Use `--function-variable-json` for custom function-backed variables; string args are written with SmartCanvas escaped single quotes, and an arg object such as `{"raw":"[[FieldName]]"}` is written without quotes for field/variable references or nested expressions.

For the birthday-year pattern from `example-zip/shapes_and_variables.zip`, use the built-in preset:

```bash
python3 smart-canvas-skill/scripts/create_smartcanvas_shapes_variables.py \
  "template-export.zip" \
  "template-export-with-birthday-vars.zip" \
  --birthday-example \
  --age-field Age \
  --had-birthday-field HadBirthdayThisYearSoFar \
  --birthyear-variable Birthyear
```

The birthday preset creates text form field `Age`, radio form field `HadBirthdayThisYearSoFar` with `Yes`/`No`, and variables `CurrentYear`, `AgePlusOne`, and `Birthyear`. The helper writes visible objects to `Document.xml` `Composition`, creates shape templates under `ExtendedProperties/ShapeTemplates` when missing, writes form fields to `Resources/DataInterface2`, writes computed variables to `Resources/Variables`, and syncs `Resources` into `smartcampaign.xml` when present or creates it when needed.

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

When the dropdown sits inside a frame, circle, or other visible container, place the picture box inside that container with an intentional inset margin. If SmartCanvas clipping is not being created, do not imply that rectangular images are clipped by a circle; use a picture box that fits within the circle and keep the circle/frame below the dropdown layers.

The dropdown helpers sanitize `--field-name` to SmartCanvas-safe identifiers containing only letters, numbers, `_`, and `-`; for example `Inside - Msgs of Help 1/3` becomes `Inside-Msgs-of-Help-1-3`. Use the sanitized field names for verification. Switches/layers are scoped by sanitized field name and option index, so separate dropdowns can safely reuse the same image filenames/categories.

The dropdown scripts patch `Document.xml` and `smartcampaign.xml`, add/update the Image List form field, switches, switched layers, picture nodes, image categories, and image files/sidecars. They preserve the outer SmartCanvas export ZIP shape when the input has nested `Admin/<campaign>.zip`. External image input may be a nested directory or ZIP; non-image files are ignored, subfolders become category names such as `level2/levelA`, and duplicate image basenames are made unique for SmartCanvas's flat `images/` folder. Existing-library mode reuses images already under the campaign `images/` folder and does not duplicate their binary files.

When the user asks to create a SmartCanvas product/template "from scratch" and does not provide a template export ZIP, first prepare a blank seed export:

```bash
python3 smart-canvas-skill/scripts/prepare_smartcanvas_blank_template.py \
  "blank-template.zip"
```

This downloads the approved blank SmartCanvas seed export from the pinned GitHub URL, verifies its SHA256, caches it under `~/.cache/smart-canvas-skill`, validates that it has the expected outer SmartCanvas wrapper, and copies it to the requested output path. If network access is blocked, ask the user to allow the download or provide a blank SmartCanvas export ZIP manually. Treat the prepared ZIP as the input `template-export.zip` for the other helpers below.
