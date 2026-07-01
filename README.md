# SmartCanvas Skill

The SmartCanvas skill helps Codex create or update SmartCanvas template exports. Give Codex a SmartCanvas export ZIP, or ask it to start from a blank template, describe the change you want, and Codex can create a new ZIP that you can import back into SmartCanvas.

When you ask to start from scratch, the skill downloads an approved blank SmartCanvas export from GitHub and uses that as the starting point.

## Install

Automatic Installation

In Codex, ask:

```codex
Using $skill-installer, please install this skill:
https://github.com/benfwork/smartcanvas-skill/tree/main/smart-canvas-skill
```

Or you can manually install by:

Copying the `smart-canvas-skill` folder into your Codex skills folder:

```text
~/.codex/skills/smart-canvas-skill
```

## Use

Prepare the files Codex needs, usually:

- Any images or details needed for the requested change.
- The output ZIP name you want.

If you already have a SmartCanvas template export ZIP, include it. If you want to start from a blank template, just say that in your request.

To export your SmartCanvas template

Then ask Codex in plain language. For example:

```text
Use the SmartCanvas skill to add these images as an image dropdown to my blank SmartCanvas export.

Template ZIP: example-zip/blank-design.zip
Images: example-images/
Output name: blank-design-with-dropdown.zip
Dropdown field name: image_dropdown_1
Image position: X 0, Y 0
```

You can also keep the request simple:

```text
Use the SmartCanvas skill on my template ZIP and image folder. Make an image dropdown and save a new SmartCanvas ZIP.
```

Or start from a blank template:

```text
Use the SmartCanvas skill to create a new SmartCanvas product from scratch.
Add a text field and an image dropdown.
Images: example-images/
Output name: new-product.zip
```

## Features

### Image Dropdowns

Create SmartCanvas image-list dropdowns from a folder, ZIP, or existing SmartCanvas image library. Nested image folders can become dropdown categories. Codex creates the field, switches, layers, image placement, and selection logic.

### Existing Image Placement

Find placed images in an export and reuse their page, position, size, and layer details. This is useful when a new dropdown needs to line up with an existing design.

### Layout manipulation

Adjust existing elements to exact positions and sizes. Make sure elements are perfectly aligned.

### Text Fields

Add SmartCanvas text objects with placement, font, size, line height, tracking, style name, and layer name. If you do not provide coordinates, Codex can use a simple default placement or ask for exact measurements.

### Shapes and Lines

Add rectangles, squares, ovals, circles, and lines. Colors can be hex values or SmartCanvas swatch strings, and measurements can be in points or inches.

### Form Fields and Variables

Add form fields, radio options, computed variables, and SmartCanvas variable functions. The skill has documentation for all 52 SmartCanvas functions. This can support personalization logic such as greetings, calculations, conditional values, and birthday-year examples.

### QR Codes

Update QR code content so it points to a SmartCanvas field, variable, or fixed value.

### Locks

Lock or unlock layers and objects in a template. Codex can target everything, a named layer, or content that contains specific text or filenames.

### Inspection and Verification

Inspect exported packages, locate images, and verify dropdown fields and placements after changes are made.

### Blank Templates

Start from an approved blank SmartCanvas export when you do not already have a template ZIP. If Codex cannot access GitHub, it will ask you to allow the download or provide a blank export manually.

## Image Folders

You may import images em masse using a folder

It can be flat:

```text
images/
  photo1.jpg
  photo2.jpg
  photo3.png
```

Or nested:

```text
images/
  level1/photo1.jpg
  level1/photo2.jpg
  level2/photo1.jpg
  level2/levelA/photo2.jpg
```

For nested folders, each subfolder can become an image category in SmartCanvas:

```text
level1
level2
level2/levelA
```

Non-image files are ignored.

## What You Get Back

Codex creates a new SmartCanvas ZIP and leaves the original export unchanged. Import the new ZIP into SmartCanvas to review it.

For brand-new images, SmartCanvas may need to rebuild its internal image catalog after import. If that happens, import the new ZIP into SmartCanvas and re-export it once.
