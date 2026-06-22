# SmartCanvas Skill

This skill helps Codex update SmartCanvas product/template ZIPs. Its main job right now is creating image dropdowns from a folder or ZIP of photos.

## What To Give Codex

Prepare two things:

- A SmartCanvas template export ZIP.
- A folder or ZIP of images.

Then ask Codex to use this skill. For example:

```text
Use the SmartCanvas skill to add these images as an image dropdown to my blank SmartCanvas export.

Template ZIP: example-zip/1. blank design.zip
Images: example-images/
Output name: blank-design-with-image-dropdown.zip
Dropdown field name: image_dropdown_1
Category name: Test_category
Image position: X 0, Y 0
```

You can also keep it simpler:

```text
Use the SmartCanvas skill on my template ZIP and image folder. Make an image dropdown and save a new SmartCanvas ZIP.
```

## Image Folders

Your image folder can be flat:

```text
images/
  photo1.jpg
  photo2.jpg
  photo3.png
```

Or it can be nested:

```text
images/
  level1/photo1.jpg
  level1/photo2.jpg
  level2/photo1.jpg
  level2/levelA/photo2.jpg
```

For nested folders, each subfolder becomes an image category in SmartCanvas:

```text
level1
level2
level2/levelA
```

Non-image files are ignored.

## What You Get Back

Codex will create a new SmartCanvas ZIP that includes:

- the images
- an image dropdown field
- one switch per image
- one image layer per image
- the switch logic needed to show the selected image

All dropdown images are placed in the same spot on the canvas. If you know where they should go, include the X/Y position in your request. If you leave it out, Codex will use X 0, Y 0.

If your images are brand new to the template, SmartCanvas may still need to rebuild its internal image catalog after import. In that case, import the new ZIP into SmartCanvas and re-export it once.
