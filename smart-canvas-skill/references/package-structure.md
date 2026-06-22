# SmartCanvas Package Structure

This reference is based on the extracted demo export at `demo smartcanvas template/` and its inner archive `Admin/962_TestTemplate.zip`.

## Contents

- Outer Export Folder
- Package Edit Workspace
- Inner Campaign Zip
- Control Surface Inspector
- XML Inventory Inspector
- `databases.bin`
- Binary Fingerprints
- `info.bin`
- Raw `info.bin` Wire Dump
- Embedded Image Metadata
- Database Columns and Bindings
- `info.bin` Resource Blobs
- `info.bin` Image Categories
- Image Asset Pattern
- Image Asset Readiness
- Staging New Image Assets
- Image Dropdown Clues
- Recommended Next Reverse-Engineering Test
- Experimental Image Dropdown Workflow

## Outer Export Folder

The extracted export wrapper has this shape:

```text
demo smartcanvas template/
├── info.json
├── Admin/
│   └── 962_TestTemplate.zip
├── Impositions/
│   └── <uuid>.xml
└── PdfPresets/
    └── <uuid>.xml
```

### `info.json`

`info.json` is JSON import metadata for the account/campaign wrapper. In the demo it contains:

- `SourceAccountId`
- `NewAccountId`
- `StatusId`
- `Admin.Campaigns[]`
- source campaign/template/design names
- import status fields

This appears to describe the exported/imported campaign, not the canvas layout itself.

### `Admin/<campaign>.zip`

The `Admin` zip is the real SmartCanvas design payload. In the demo it is `962_TestTemplate.zip`.

## Package Edit Workspace

Use the workspace helper before attempting manual XML/image/dropdown edits:

```bash
python3 smart-canvas-skill/scripts/smartcanvas_package_workspace.py roundtrip-check "demo smartcanvas template" /tmp/smartcanvas-roundtrip-demo --force
python3 smart-canvas-skill/scripts/smartcanvas_package_workspace.py unpack "demo smartcanvas template" smartcanvas-edit-workspace/
python3 smart-canvas-skill/scripts/smartcanvas_package_workspace.py pack smartcanvas-edit-workspace/ smartcanvas-edited-export/
```

The helper creates:

```text
workspace/
├── smartcanvas-package-manifest.json
├── outer/
│   ├── info.json
│   ├── Impositions/
│   └── PdfPresets/
└── inner/
    ├── template.xml
    ├── template.dhtt
    ├── Document.xml
    ├── images/
    ├── databases.bin
    ├── info.bin
    └── scriptsnippets.xml
```

The manifest records original inner zip member names, normalized edit paths, compression type, timestamps, external attributes, and comments. `pack` rebuilds an outer export folder when the source was an outer export, or an inner zip when the source was an inner zip.

For outer exports, `Admin/<campaign>.zip` is treated as canonical. Extracted helper folders such as `Admin/962_TestTemplate/` and Windows `:Zone.Identifier` files are skipped. On the demo export, `roundtrip-check` produced:

```text
Payload match: True
Added/removed/changed: 0/0/0
```

`compare_smartcanvas_packages.py "demo smartcanvas template" /tmp/smartcanvas-packed-demo` also reported zero added, removed, or changed inner payload files and no decoded `info.bin` changes. This proves the workspace can be used for controlled no-op package edits before dropdown-specific mutations are attempted.

### `Impositions/` and `PdfPresets/`

Both directories contain UUID-named XML files. In the demo:

- `Impositions/` count: 34 XML files
- `PdfPresets/` count: 34 XML files
- filename sets are identical
- file contents are byte-for-byte identical

Each imposition XML has a root like:

```xml
<Imposition Version="2.0" Duplex="True" ImpositionType="PageSequence"
  ImpositionDisplayName="Business Card"
  ImpositionFileName="2d0f4e53-be68-4c52-b66e-86da5799b656.xml">
  <ImpositionList>
    <Signature ContentType="DOCPAGE" PageNr="1" SheetNr="1" ...>
      <Overlay />
    </Signature>
  </ImpositionList>
  <Sheetmarks />
  <Sheet DisplayName="" Width="21 cm" Height="29.7 cm" ... />
</Imposition>
```

`ImpositionFileName` matches the UUID filename. `ImpositionDisplayName` is the human-facing name.

Some impositions are empty/default presets with:

- `DocPageCount="0"`
- empty `ImpositionList`
- no `DocWidth` or `DocHeight`

## Inner Campaign Zip

The demo inner zip contains these top-level entries:

```text
962_TestTemplate/
databases.bin
info.bin
scriptsnippets.xml
```

Inside `962_TestTemplate/`:

```text
962_TestTemplate/
├── css.css
├── description.xml
├── Document.xml
├── fonts/
├── images/
├── lasthash.txt
├── Storyboard_Thumb.png
├── template.dhtt
└── template.xml
```

### `template.xml`

Main SmartCanvas/PURL design XML. The demo root is:

```xml
<Purl Version="4" DesignVersion="5" CampaignName="962_TestTemplate" ...>
```

Direct children in the demo:

- `Description`
- `TextStyles`
- `Doc` for the storyboard
- `Doc` for the dynamic document
- `TextVariables`
- `CPColors`
- `Switches`
- `SystemSets`
- `FavoriteSetCategories`
- `Languages`
- `ErrorMessages`
- `Campaigns`
- `FileUploadCampaignSettings`
- `TemplateSettings`
- `DatabaseColumns`

The demo `template.xml` appears to be mostly a shell:

- document/page/layer structure
- text style definitions
- switches such as `IsAdmin` and `IsLoggedIn`
- database column declarations
- no obvious image dropdown/control option nodes

### `Document.xml`

Document/page/frame shell. The demo root is:

```xml
<Documents SourceJobTemplate="" OriginAccountID="2" OriginCampaign="EmptyDocument"
  OriginDesign="Document" Version="3">
```

It defines `Document`, `Page`, `Frame`, `Composition`, and `Layers`.

### `template.dhtt`

DirectSmile PURL template settings. The demo root is:

```xml
<DirectSmilePUrlTemplate Version="5" NeededLicenses="XMedia_VDP" ...>
```

The demo contains sections such as:

- `Sites`
- `Variables`
- `ActionButtons`
- `Images`
- `IFrames`
- `TextInputs`
- `Templates`
- `Resources`
- `Payments`
- `FileUploads`
- `Languages`

In the demo, `Images` is empty and `Templates` contains condition templates for `IsAdmin` and `IsLoggedIn`.

### `css.css`

Generated CSS for dynamic component classes. The demo includes empty/default class blocks for many possible component types, including:

- `DynamicDocument1`
- `DynamicDirectSmileSet1`
- `DynamicCheckBox1`
- `DynamicTextField1`
- `DynamicImage1`
- `DynamicSelection1`
- `DynamicRadioButtons1`

The presence of these CSS classes alone does not prove the corresponding controls exist on the canvas.

### Control Surface Inspector

Run this to summarize the XML/control layer without reading the full XML by hand:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_controls.py before.zip
python3 smart-canvas-skill/scripts/inspect_smartcanvas_controls.py after.zip -o after-controls.json --format json
```

The inspector reports:

- `template.xml` docs, pages, layers, `DocModel` counts, and image-related `DocModel` attributes
- `template.dhtt` component sections such as `Variables`, `Images`, `TextInputs`, `Templates`, and `Resources`
- `Document.xml` document/page/frame shell
- generated CSS dynamic classes
- whether any catalog image captions from `info.bin` appear in key XML files

On the demo package:

```text
Catalog images: 24
Catalog image names referenced in key XML: 0

template.xml docs:
  Storyboard / Whiteboard: 1 page, 1 layer, 2 DocModel nodes
  Document / DynamicDocument: 1 page, 1 layer, 1 DocModel node

template.dhtt sections:
  Variables: 0 children
  ActionButtons: 0 children
  Images: 0 children
  IFrames: 0 children
  TextInputs: 0 children
  Templates: 4 Template children
  Resources: 0 children
  FileUploads: 0 children
```

Every demo `DocModel` includes these image/control attributes, all empty or default:

```text
Class=""
ImageSelector=""
ImageCategories=""
ShowImageBrowser="False"
EnableImageUpload="False"
LockImageReplace="False"
EnableCropping="True"
EnableKeepRatio="False"
SelectedTextStyleVariations=""
LayerID=""
```

This makes `DocModel` attributes a high-value diff target for a real image dropdown export, especially `ImageSelector`, `ImageCategories`, `Class`, `ShowImageBrowser`, and `EnableImageUpload`.

### `description.xml`

Small metadata file:

```xml
<Description Name="" Description="">
  <Categories />
  <TargetAudiences />
  <OutboundChannels />
</Description>
```

### `scriptsnippets.xml`

Empty in the demo:

```xml
<ScriptSnippets />
```

### `databases.bin`

Opaque binary in the demo. Current fingerprint:

```text
size: 781 bytes
sha256: 68a2762d05ca5dd8bf890b230a2f66b26420be917d63a1061b24d5787d0c9059
magic: unknown
entropy: 7.729045
printable ratio: 0.384123
protobuf-wire records before error: 2
protobuf-wire parse error: unsupported protobuf wire type 3 at offset 9
```

A string scan found no useful readable structure. Treat this as opaque unless a before/after export proves how it changes.

### Binary Fingerprints

Run this to fingerprint package `.bin` files and compare opaque binary changes:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_binaries.py before.zip -o before-binaries.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_binaries.py after.zip -o after-binaries.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_binaries.py before.zip after.zip -o binaries-delta.json
```

The inspector reports size, SHA-256, simple magic detection, entropy, printable-byte ratio, ASCII string samples, and a best-effort protobuf-wire probe. On the demo:

```text
Binary files: 2
databases.bin: 781 bytes, entropy 7.729045, wire parse error at offset 9
info.bin: 40892155 bytes, entropy 7.211109, 35 top-level wire records, no top-level parse error
```

Use this in real dropdown before/after exports to quickly detect whether `databases.bin`, `info.bin`, or any new binary file changed.

### `info.bin`

Large binary asset/catalog payload. The demo `info.bin` uses protobuf-style wire encoding. It is not plain UTF-8, but the outer and catalog layers can be parsed enough for inspection.

Top-level fields observed in the demo:

- field `1` wire `2`: main catalog payload, 40,890,401 bytes
- field `2` wire `2`: empty
- field `3` wire `0`: numeric account/campaign-like value
- field `4` wire `2`: `962_TestTemplate`
- field `6` wire `0`: numeric flag
- field `9` wire `2`: campaign metadata payload
- field `16` wire `2`: `DSMXContactsDatabase`
- field `20` wire `0`: numeric value `962` in the demo, matching the campaign/template number
- field `21` wire `2`: 64-character uppercase hex-like value, likely a generated hash/id; meaning not confirmed
- repeated field `26` wire `2`: image-to-category records near the end
- fields `28`, `39`, and `40` wire `0`: numeric flags/ids

The nested field `1` catalog payload has these field counts in the demo:

```text
field_1_wire_2: 24
field_11_wire_2: 1
field_18_wire_2: 1
field_19_wire_2: 1
field_21_wire_2: 24
field_48_wire_2: 167
field_49_wire_2: 75
```

Likely meanings from evidence:

- catalog field `1`: image captions/names
- catalog field `11`: document resource metadata
- catalog field `21`: one image asset record per caption
- catalog field `48`: database column names
- catalog field `49`: large embedded resource blobs; in the demo these are font resources

Each catalog field `21` image record contains:

- nested field `1`: image caption
- nested field `2`: image detail payload

The nested image detail payload contains:

- field `1`: filename/caption again
- field `2`: 40-character uppercase SHA-1 hash of the archived original image bytes
- field `3`: declared file size matching the archived original image size
- field `4`: embedded `FileGroupInformation` XML metadata

Example decoded image record:

```text
caption='Intro 1-3 Size_Option 1.jpg'
hash='EFFC3F56A17C0A11008B0DDDF859978F822BAB50'
declared_size=610038
metadata_xml_bytes=638
```

The repeated image names and image records match the 24 `_info.xml` sidecars in the demo.

#### Embedded Image Metadata

Run this to compare image metadata XML embedded in `info.bin` field `21` records against extracted `_info.xml` sidecars:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_metadata.py before.zip -o before-image-metadata.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_metadata.py after.zip -o after-image-metadata.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_metadata.py before.zip after.zip -o image-metadata-delta.json
```

On the demo package:

```text
Embedded image metadata records: 24
Sidecars: 24
Exact embedded/sidecar matches: 24
Exact embedded/sidecar mismatches: 0
Missing sidecars: 0
Parsed metadata mismatches: 0
```

This proves that, in the demo, each catalog image record's embedded `FileGroupInformation` XML is byte-for-byte identical to its extracted `_info.xml` sidecar. For asset creation, sidecars are not merely adjacent files; their exact XML also appears duplicated inside `info.bin`. `info.bin` is still treated as generated until a SmartCanvas round-trip proves a safe writer.

All 24 demo image records were verified against files in `962_TestTemplate/images/`:

- every catalog caption had a matching archived original image filename
- every field `3` declared size matched the original image byte count
- every field `2` hash matched `SHA1(original image bytes).hexdigest().upper()`

Duplicate image files with different captions share the same SHA-1 hash. For example the base, `_Demo Gallery`, and `_test` copies of `Messages of Help 2-3 Size_Green Fill_Option 1` all hash to `1C58256503DA51C5655EB179E5B03F6A8E5F5C72`.

Treat `info.bin` as generated until decoded further or round-tripped. It is useful for diffing, but not yet safe to hand-edit.

#### Raw `info.bin` Wire Dump

Run this when unknown binary fields need inspection or before/after diffing:

```bash
python3 smart-canvas-skill/scripts/dump_smartcanvas_info_bin.py before.zip -o before-info-bin-dump.json
python3 smart-canvas-skill/scripts/dump_smartcanvas_info_bin.py after.zip -o after-info-bin-dump.json
python3 smart-canvas-skill/scripts/compare_smartcanvas_info_bin_dumps.py before-info-bin-dump.json after-info-bin-dump.json
```

The dump script accepts an outer export folder, inner campaign zip, extracted inner folder, or a direct `info.bin` path. It reports:

- known decoded counts from `summarize_info_bin`
- grouped top-level protobuf-wire fields
- grouped nested catalog field `1` records
- field counts, total byte lengths, sample lengths, text samples, varint samples, and nested field-count samples

On the demo package, the dump reports:

```text
info.bin size: 40892155
top-level records: 35
image_name_count: 24
image_record_count: 24
image_category_count: 23
database_column_count: 167
resource_blob_count: 75
resource_blob_bytes: 40866671

top field_1_wire_2: count=1, length=40890401
top field_21_wire_2: count=1, length=64
top field_26_wire_2: count=23, total_length=1492

catalog field_1_wire_2: 24 image-name strings
catalog field_21_wire_2: 24 image records
catalog field_48_wire_2: 167 database column strings
catalog field_49_wire_2: 75 large font resource records
```

Nested parsing in the dump is heuristic. Treat it as a map for comparison and investigation, not as proof that every sampled byte field is a real nested message.

To compare two dumps or packages directly, run:

```bash
python3 smart-canvas-skill/scripts/compare_smartcanvas_info_bin_dumps.py before.zip after.zip
python3 smart-canvas-skill/scripts/compare_smartcanvas_info_bin_dumps.py before-info-bin-dump.json after-info-bin-dump.json
```

The comparator reports added, removed, and changed groups for:

- known decoded summary values
- top-level wire fields
- nested catalog field `1` groups

As a smoke test, changing only the top-level template-name string from `962_TestTemplate` to `963_TestTemplate` in a copied `/tmp` binary made the comparator report exactly one changed top-level group, `field_4_wire_2`, and no catalog field changes.

#### Database Columns and Bindings

Run this when a dropdown/control may have added a database field, changed a binding, or introduced a new `[[Field]]` expression:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_database.py before.zip -o before-database-bindings.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_database.py after.zip -o after-database-bindings.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_database.py before.zip after.zip -o database-bindings-delta.json
```

The inspector reports:

- `template.xml` `DatabaseColumns/DatabaseColumn` entries and attributes
- `info.bin` catalog field `48` database column strings
- whether named `template.xml` columns match `info.bin` columns in order
- binding-looking XML attributes such as `JField`, `DBField`, `IdFieldName`, `ConditionX`, `RelationType`, and `Value`
- `[[Field]]` references found in key XML files
- whether each `[[Field]]` reference matches a known database column

On the demo package:

```text
template columns: 168
template named columns: 167
info.bin columns: 167
named order matches info.bin: True
included columns: 1 (#1 has Name="" and IsIncluded="true")
field references: CampaignRights x4, HasUser x4
unknown referenced fields: HasUser
```

This means `template.xml` carries one empty included placeholder column before the real named columns. The real named columns exactly match `info.bin` field `48`. `HasUser` appears to be a condition/runtime variable rather than a database column.

#### `info.bin` Resource Blobs

Catalog field `49` contains embedded resource records. In the demo these are fonts, not images:

```text
75 total resources
25 application/vnd.ms-fontobject
25 application/font-sfnt
25 application/font-woff
```

The 75 records appear to be 25 font faces, each stored in EOT, TTF, and WOFF variants. Each resource record includes:

- field `1`: PostScript/internal font name, such as `ArialMT`
- field `2`: font family, such as `Arial`
- field `4`: style, such as `normal` or `italic`
- field `5`: kind, such as `TrueType (CID)`
- field `8`: source format, observed as `TTF`
- field `10`: embedded resource filename, such as `ArialMT.ttf`
- field `11`: MIME type
- field `12`: resource variant/type number
- field `14`: weight, such as `400`
- field `19`: embedded resource bytes

No field `49` resource bytes matched archived image files in this demo. Image originals remain regular files under `images/`, while catalog field `21` stores their metadata, size, and SHA-1.

#### `info.bin` Image Categories

Top-level repeated field `26` is confirmed as an image-to-category mapping in the demo. Each record has:

- nested field `1`: image caption/name
- nested field `2`: category name

Observed categories:

- `Front folder logo`
- `test`
- `Demo Gallery`

The demo has 23 category records for 24 cataloged images. The uncategorized image is:

```text
Messages of Help 2-3 Size_Green Fill_Option 1.jpg
```

This is important because all extracted `_info.xml` sidecars have `GroupName=""`, while the actual gallery/category assignment is preserved in `info.bin` field `26`.

## Image Asset Pattern

Images live under the inner campaign folder's `images/` directory.

Common original image:

```text
images/Intro 1-3 Size_Option 1.jpg
```

Sidecars:

```text
images/Intro 1-3 Size_Option 1_jpg_info.xml
images/Intro 1-3 Size_Option 1_jpg_thumbi.png
images/Intro 1-3 Size_Option 1_jpg_thumbn.png
```

For images with a generated scaling:

```text
images/Messages of Help 2-3 Size_Green Fill_Option 1.jpg
images/Messages of Help 2-3 Size_Green Fill_Option 1_jpg/
└── Messages of Help 2-3 Size_Green Fill_Option 1_jpg_900.jpg
```

The `_info.xml` sidecar has this structure:

```xml
<FileGroupInformation Source="_Template" Resource="_Image"
  Caption="Messages of Help 2-3 Size_Green Fill_Option 1.jpg"
  GroupName=""
  IsSelected="false"
  ImageWidth="1101"
  ImageHeight="1700"
  IsMultiImage="false"
  LastImage="1"
  Filesize="1937619">
  <Pages>
    <Page Top="0" Left="0" Width="1101" Height="1700" />
  </Pages>
  <Resourceinfo DPIx="300" DPIy="300" PixelBased="True"
    HasMask="False" HasProfile="True" CoordType="Pixel"
    BitmapType="jpeg" BitsPerComponent="8">
    <CustomProperties>
      <Scalings Value="900" />
    </CustomProperties>
  </Resourceinfo>
</FileGroupInformation>
```

Observed sidecar fields likely relevant to image dropdowns:

- `Caption`: visible/logical image filename
- `GroupName`: blank in the extracted XML sidecars, despite `info.bin` containing confirmed image-to-category mappings
- `IsSelected`: default selection flag, always `false` in the demo
- `ImageWidth` / `ImageHeight`
- `BitmapType`
- `Scalings Value`

Important size note: in the demo, all 24 `_info.xml` `Filesize` values differ from the archived image byte sizes. The `info.bin` image record size and SHA-1 are the values that match the archived original image bytes. Treat sidecar `Filesize` as a separate, not-yet-explained value rather than as the authoritative file byte count.

The sidecar XML is also embedded exactly in `info.bin` catalog image records. Use `inspect_smartcanvas_image_metadata.py` to verify this on other exports before assuming parity.

Observed derived image sizing:

- `_thumbi.png`: present for 24/24 catalog images; max dimension is 50 px for 3 images and 51 px for 21 images
- `_thumbn.png`: present for 23/24 catalog images; max dimension is 198 px for 2 images and 202 px for 21 images. `SampleImage.png` has no `_thumbn.png` in the demo.
- `*_900.jpg`: present for 21/24 catalog images, all measured at 727x1122 px
- `Scalings Value="900"` appears on the tall 1101x1700 images; the 1101x850 intro images have an empty scaling value
- the two intro images and `SampleImage.png` do not have scaled derivatives

Run this to measure original images, sidecars, thumbnails, scaled assets, and sidecar `Filesize` differences:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_derivatives.py before.zip -o before-image-derivatives.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_derivatives.py after.zip -o after-image-derivatives.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_derivatives.py before.zip after.zip -o image-derivatives-delta.json
```

On the demo package:

```text
images_with_originals: 24
images_with_thumbi: 24
images_with_thumbn: 23
images_with_scaled_assets: 21
original_dimensions_match_sidecar: 24
thumbi_max_dimension_counts: 50 => 3, 51 => 21
thumbn_max_dimension_counts: 198 => 2, 202 => 21
scaled_dimension_counts: 727x1122 => 21
```

### Image Asset Readiness

Run this before treating cataloged images as dropdown options:

```bash
python3 smart-canvas-skill/scripts/validate_smartcanvas_image_assets.py before.zip
python3 smart-canvas-skill/scripts/validate_smartcanvas_image_assets.py before.zip -o asset-readiness.json --format json
python3 smart-canvas-skill/scripts/validate_smartcanvas_image_assets.py before.zip after.zip -o asset-readiness-delta.json
python3 smart-canvas-skill/scripts/validate_smartcanvas_image_assets.py before.zip --group "Green Fill"
```

The readiness validator combines the catalog exporter, embedded metadata inspector, derivative inspector, and option analyzer. It classifies:

- **errors**: missing originals, missing sidecars, `info.bin` size/hash mismatches, embedded metadata/sidecar mismatches, parsed metadata mismatches, and image dimension mismatches.
- **warnings**: demo-observed sidecar `Filesize` drift, missing thumbnails, missing scaled derivatives when `Scalings` is set, uncategorized images, multiple original paths, and duplicate SHA-1 caption/category copies.

On the demo package:

```text
Images checked: 24 of 24
Status: ready
Errors: 0
Warnings: 47
Issue codes:
  sidecar_filesize_differs: 24
  duplicate_sha1_caption_copy: 21
  missing_thumbn: 1
  uncategorized_image: 1
Candidate dropdowns: 3
```

This means the demo image catalog is internally consistent enough for dropdown probing, while still carrying generated-asset quirks that should be watched in before/after diffs. The validator does not prove the control XML schema; it only answers whether the image assets and catalog records are coherent enough to use as candidate dropdown options.

### Staging New Image Assets

Use this helper to stage a folder of original images with SmartCanvas-style `_info.xml` sidecars and a manifest:

```bash
python3 smart-canvas-skill/scripts/prepare_smartcanvas_images.py source-images/ staged-images/
```

The script:

- copies `.jpg`, `.jpeg`, and `.png` source images
- skips known SmartCanvas derivatives such as `_thumbi.png`, `_thumbn.png`, and `*_900.jpg`
- reads JPEG/PNG dimensions with the Python standard library
- writes `_info.xml` files using the observed `FileGroupInformation` shape
- writes `smartcanvas-images-manifest.json` with dimensions, byte size, SHA-1, derived-file names, and staging notes

The script intentionally does not rebuild:

- `info.bin`
- image category records in `info.bin`
- `_thumbi.png` / `_thumbn.png`
- scaled derivative files such as `*_900.jpg`

Use it as an asset-prep aid, not as a complete SmartCanvas package writer. A round-trip import/export is still needed before treating generated sidecars as fully accepted by SmartCanvas.

## Image Dropdown Clues

The demo asset names strongly suggest option sets:

```text
Intro 1-3 Size_Option 1.jpg
Intro 1-3 Size_Option 2.jpg
Messages of Help 2-3 Size_Green Fill_Option 1.jpg
Messages of Help 2-3 Size_Orange Fill_Option 1.jpg
...
```

However, the demo does not expose an obvious dropdown definition in `template.xml` or `template.dhtt`.

Working hypothesis:

1. Image files and sidecars define available template image resources.
2. `info.bin` stores a generated image catalog, including hashes and category/gallery metadata.
3. A real image dropdown/control likely adds explicit nodes to `template.xml`, `template.dhtt`, or both.
4. The fastest path to decode dropdowns is to diff two exports that differ only by one image dropdown.

## Recommended Next Reverse-Engineering Test

Create or obtain two SmartCanvas exports:

1. Minimal template with two or three image assets and no dropdown.
2. Same template after adding one image dropdown that selects those assets.

To generate a small, distinctive image set for this test, run:

```bash
python3 smart-canvas-skill/scripts/make_smartcanvas_dropdown_probe_images.py smartcanvas-dropdown-probe-images/ --count 3 --stage-sidecars
```

This creates:

```text
smartcanvas-dropdown-probe-images/
├── probe-images-manifest.json
├── source-images/
│   ├── DropdownProbe_Option_1_Red.png
│   ├── DropdownProbe_Option_2_Green.png
│   └── DropdownProbe_Option_3_Blue.png
└── staged-images/
    ├── DropdownProbe_Option_1_Red.png
    ├── DropdownProbe_Option_1_Red_png_info.xml
    ├── DropdownProbe_Option_2_Green.png
    ├── DropdownProbe_Option_2_Green_png_info.xml
    ├── DropdownProbe_Option_3_Blue.png
    ├── DropdownProbe_Option_3_Blue_png_info.xml
    └── smartcanvas-images-manifest.json
```

Use the generated source images or staged images as convenient for the SmartCanvas UI. The filenames are intentionally distinctive so XML string scans, `info.bin` dumps, and catalog comparisons have stable probe terms. The generated PNGs are simple 480x320 RGB images; the staged sidecars follow the observed `_info.xml` pattern but still do not rebuild `info.bin`, thumbnails, or scaled derivatives.

Then compare:

- `template.xml`
- `template.dhtt`
- `Document.xml`
- `css.css`
- image sidecar XML
- image thumbnails and scaled derivative assets
- `.bin` file fingerprints, especially `databases.bin` and `info.bin`
- decoded `info.bin` catalog fields
- database columns, binding attributes, and `[[Field]]` references
- broad XML schema inventory paths, attribute names, exact elements, and exact attribute values
- archive file list and file sizes

Run:

```bash
python3 smart-canvas-skill/scripts/make_smartcanvas_dropdown_probe_bundle.py before.zip after.zip smartcanvas-probe/
python3 smart-canvas-skill/scripts/compare_smartcanvas_dropdown_signals.py before.zip after.zip
python3 smart-canvas-skill/scripts/compare_smartcanvas_packages.py before.zip after.zip
python3 smart-canvas-skill/scripts/inspect_smartcanvas_binaries.py before.zip after.zip -o binaries-delta.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_image_derivatives.py before.zip after.zip -o image-derivatives-delta.json
python3 smart-canvas-skill/scripts/dump_smartcanvas_info_bin.py before.zip -o before-info-bin-dump.json
python3 smart-canvas-skill/scripts/dump_smartcanvas_info_bin.py after.zip -o after-info-bin-dump.json
python3 smart-canvas-skill/scripts/compare_smartcanvas_info_bin_dumps.py before-info-bin-dump.json after-info-bin-dump.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_controls.py before.zip -o before-controls.json --format json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_controls.py after.zip -o after-controls.json --format json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_database.py before.zip after.zip -o database-bindings-delta.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_xml_inventory.py before.zip after.zip -o xml-inventory-delta.json
```

The bundle command is the preferred first pass once a real dropdown before/after export exists. It writes:

```text
smartcanvas-probe/
├── before/
│   ├── binaries.json
│   ├── asset-readiness.json
│   ├── catalog.json
│   ├── controls.json
│   ├── database-bindings.json
│   ├── dropdown-blueprint.json
│   ├── dropdown-blueprint.csv
│   ├── image-derivatives.json
│   ├── image-metadata.json
│   ├── info-bin-dump.json
│   ├── options.json
│   └── xml-inventory.json
├── after/
│   ├── binaries.json
│   ├── asset-readiness.json
│   ├── catalog.json
│   ├── controls.json
│   ├── database-bindings.json
│   ├── dropdown-blueprint.json
│   ├── dropdown-blueprint.csv
│   ├── image-derivatives.json
│   ├── image-metadata.json
│   ├── info-bin-dump.json
│   ├── options.json
│   └── xml-inventory.json
├── binaries-delta.json
├── asset-readiness-delta.json
├── image-derivatives-delta.json
├── dropdown-signals-delta.json
├── database-bindings-delta.json
├── image-metadata-delta.json
├── info-bin-delta.json
├── xml-inventory-delta.json
└── summary.txt
```

The summary is meant to answer "where should I look first?" without opening the JSON files. On the synthetic control probe it reported:

```text
binary files added/removed/changed: 0/0/0
catalog image XML refs added/removed: 2/0
DocModel changes: 1
template.xml interesting attr changes: 1
template.dhtt section changes: 1
template.dhtt interesting attrs added/removed/changed: 1/0/0
XML binding attrs added/removed/changed: 1/0/0
field refs added/removed/changed: 0/0/0
embedded/sidecar exact matches: 24 -> 24
image metadata records added/removed/changed: 0/0/0
schema paths added/removed/changed: 0/0/0
attribute names added/removed/changed: 0/0/0
exact elements added/removed/changed: 0/0/0
info.bin top-level groups added/removed/changed: 0/0/0
info.bin catalog groups added/removed/changed: 0/0/0
```

The dropdown signal comparator combines the catalog exporter, option analyzer, and control inspector into one report. Use it first when looking for image dropdown behavior. It compares:

- catalog image records, hashes, sizes, sidecar metadata, thumbnails, and scaled asset paths
- image category records decoded from `info.bin`
- inferred option/dropdown groups
- `DocModel` image/control attributes
- `template.xml` interesting image/selection/control attributes
- `template.dhtt` component sections, including direct child tags and child attributes
- `template.dhtt` interesting image/selection/control attributes
- `Document.xml` interesting image/selection/control attributes
- CSS dynamic classes
- catalog image filename references in key XML files

As a sanity check, comparing the demo zip to itself reports zero changes:

```text
image count: 24 -> 24
sidecar filesize matches actual: 0 -> 0
sidecar filesize mismatches actual: 24 -> 24
option groups: 3 -> 3
Image Records changed: 0
Image Category Records added/removed: 0/0
Option Groups changed: 0
DocModel Image/Control Attributes changed: 0
template.dhtt Sections changed: 0
CSS Dynamic Classes added/removed: 0/0
```

A synthetic control-surface probe was also run by modifying a temporary copy of the demo zip in `/tmp` only. The probe changed one existing `DocModel` to set:

```text
Class="DynamicImage1"
ImageSelector="Intro 1-3 Size_Option 1.jpg"
ImageCategories="Front folder logo"
ShowImageBrowser="True"
EnableImageUpload="True"
```

It also added one placeholder child under `template.dhtt` `<Images>`. This is not evidence of a valid SmartCanvas dropdown schema; it is only a tool validation probe. The dropdown signal comparator correctly reported:

```text
Catalog image references in key XML added: 2
DocModel Image/Control Attributes changed: 1
template.dhtt Sections changed: 1
Image Records changed: 0
Option Groups changed: 0
```

That means a real before/after export with a dropdown should make this comparator point at the likely control-layer changes quickly.

The control inspector also exposes direct child attributes for `template.dhtt` component sections. In the synthetic probe, the changed `Images` section includes:

```text
children: [{
  tag: "Image",
  attributes: {
    DisplayName: "Dropdown Probe Control",
    ImageCategories: "Front folder logo",
    JField: "DropdownProbe_Control",
    Name: "DropdownProbe_Control",
    Value: "Intro 1-3 Size_Option 1.jpg"
  }
}]
```

This richer section summary is intended to surface the real dropdown node attributes once a genuine SmartCanvas after-export is available.

### Experimental Image Dropdown Workflow

Use this only for disposable import probes after asset readiness and dropdown blueprint generation:

```bash
python3 smart-canvas-skill/scripts/make_smartcanvas_image_dropdown_experiment.py \
  "demo smartcanvas template" /tmp/smartcanvas-dropdown-experiment-demo \
  --group "Intro 1-3 Size" --force
```

The writer:

- unpacks the source with `smartcanvas_package_workspace.py`
- chooses one candidate dropdown group from the blueprint
- refuses ambiguous groups unless `--group` narrows the match
- checks asset readiness and refuses readiness errors unless `--allow-readiness-errors` is set
- patches one existing `DocModel` in the DynamicDocument by default
- appends one `<Image>` child under `template.dhtt` `<Images>`
- repacks the package and writes a sibling `*.experiment-manifest.json`

For the demo Intro group, the output manifest records:

```text
selected image: Intro 1-3 Size_Option 1.jpg
category: Front folder logo
control: Intro_1_3_Size
database field: Intro_1_3_Size_Choice
readiness: errors=0, warnings=2
schema status: unproven experimental patch
```

The focused dropdown comparator reports this intended delta:

```text
Image Records changed: 0
Image Category Records added/removed: 0/0
Option Groups changed: 0
Catalog image XML refs added: 2
DocModel changes: 1
template.dhtt section changes: 1
```

The raw package comparator reports only two changed inner files:

```text
template.xml
template.dhtt
```

The `template.xml` patch sets one DynamicDocument `DocModel`:

```text
Class="DynamicImage1"
ImageSelector="Intro 1-3 Size_Option 1.jpg"
ImageCategories="Front folder logo"
ShowImageBrowser="True"
EnableImageUpload="False"
```

The `template.dhtt` patch changes:

```xml
<Images>
  <Image Name="Intro_1_3_Size"
    DisplayName="Intro 1 3 Size"
    JField="Intro_1_3_Size_Choice"
    Value="Intro 1-3 Size_Option 1.jpg"
    ImageCategories="Front folder logo" />
</Images>
```

Binary comparison of the demo source against this experiment reports zero changed `.bin` files. `info.bin` size, catalog fields, image names, database columns, image records, image categories, and resource blobs remain unchanged.

This is not confirmed SmartCanvas Standard schema. Treat it as a controlled way to ask SmartCanvas what it accepts: import the package only into a disposable environment, export the result, then compare the export against the source and the experiment package.

After importing the experiment into SmartCanvas and exporting it back out, run the three-way analyzer:

```bash
python3 smart-canvas-skill/scripts/analyze_smartcanvas_dropdown_experiment_result.py \
  "demo smartcanvas template" \
  /tmp/smartcanvas-dropdown-experiment-demo \
  returned-from-smartcanvas/
```

The analyzer compares:

- source -> experiment: the intended candidate dropdown patch
- source -> returned export: what SmartCanvas actually emitted
- experiment -> returned export: any normalization, generated changes, or dropped fields

It classifies the returned export as:

- `preserved_exactly`: expected dropdown control signals remain and no focused signal changed between experiment and returned export
- `normalized`: expected control keys remain, but SmartCanvas rewrote one or more expected values
- `preserved_with_other_changes`: expected controls remain, with additional focused dropdown signal changes
- `partially_preserved`: some expected signals remain and some are missing
- `dropped_or_rejected`: expected dropdown control signals are absent
- `no_expected_dropdown_signal`: the experiment did not contain recognizable expected dropdown signals

Synthetic validation on the demo:

```text
source + experiment + experiment => preserved_exactly
source + experiment + source     => dropped_or_rejected
```

For the preserved case, the analyzer reports:

```text
Expected controls preserved/normalized/missing: 6/0/0
source_to_experiment: DocModel changes=1, template.dhtt section changes=1, XML refs added=2
experiment_to_returned: all focused dropdown signal counts are 0
binary summaries: added=0, removed=0, changed=0 for all three comparisons
```

For the dropped case, it reports:

```text
Expected controls preserved/normalized/missing: 0/0/6
Classification: dropped_or_rejected
```

This still does not prove the SmartCanvas Standard by itself. It is the evidence reducer for the real import/export loop: once a returned export exists, its classification and normalized values become the next schema clue.

### XML Inventory Inspector

Run this when a before/after export may add unknown XML tags or attributes that are not caught by the targeted control/database inspectors:

```bash
python3 smart-canvas-skill/scripts/inspect_smartcanvas_xml_inventory.py before.zip -o before-xml-inventory.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_xml_inventory.py after.zip -o after-xml-inventory.json
python3 smart-canvas-skill/scripts/inspect_smartcanvas_xml_inventory.py before.zip after.zip -o xml-inventory-delta.json
```

By default it inventories only key XML files: `template.xml`, `template.dhtt`, `Document.xml`, `description.xml`, and `scriptsnippets.xml`. Pass `--all-xml` to include sidecar XML files too. The report includes:

- per-file root tag, element counts, tag counts, and attribute value samples
- schema paths without sibling indexes, such as `Purl/Doc/DocumentPage/DocModel`
- exact indexed element paths with attributes, child counts, and text hashes
- diff sections for tag counts, schema paths, attribute names, exact elements, and exact attributes

On the demo key XML:

```text
XML files: 5
Document.xml: 7 elements, 7 schema paths
description.xml: 4 elements, 4 schema paths
scriptsnippets.xml: 1 element, 1 schema path
template.dhtt: 42 elements, 24 schema paths
template.xml: 220 elements, 37 schema paths
```

A self-compare of the demo reports zero added, removed, or changed tag counts, schema paths, attribute names, exact elements, and exact attributes. This makes it a broad safety net for real dropdown exports whose control schema uses unexpected naming.

For a dropdown-oriented image manifest, run:

```bash
python3 smart-canvas-skill/scripts/export_smartcanvas_catalog.py before.zip -o before-catalog.json
python3 smart-canvas-skill/scripts/export_smartcanvas_catalog.py after.zip -o after-catalog.json
```

The catalog JSON includes:

- each cataloged image caption
- image category from `info.bin` field `26`
- catalog SHA-1 and declared size from `info.bin` field `21`
- matching archived original image paths
- verification of file presence, byte size, and SHA-1
- sidecar `_info.xml` metadata
- whether sidecar `Filesize` matches the actual archived image byte count
- thumbnail paths
- scaled asset paths such as `*_900.jpg`
- embedded font resource summaries

On the demo package this manifest reports:

```text
24 catalog images
24/24 files found
24/24 sizes match
24/24 SHA-1 hashes match
0 sidecar filesize matches
24 sidecar filesize mismatches
Demo Gallery: 11 images
Front folder logo: 2 images
test: 10 images
[uncategorized]: 1 image
```

To infer likely image option/dropdown groups from a catalog or package, run:

```bash
python3 smart-canvas-skill/scripts/analyze_smartcanvas_options.py before-catalog.json
python3 smart-canvas-skill/scripts/analyze_smartcanvas_options.py before.zip -o before-options.json
```

The analyzer is heuristic. It looks for filename patterns such as `Option 1`, removes demo category-copy suffixes like `_Demo Gallery` and `_test`, then groups images by normalized base name. It also reports category distribution, dimensions, image hashes, and unique options collapsed by option number plus SHA-1.

On the demo package the option analysis reports:

```text
24 images
3 candidate option groups
1 single image

Intro 1-3 Size
  2 images
  options 1-2
  category: Front folder logo

Messages of Help 2-3 Size Green Fill
  11 images
  options 1-5
  unique hashes: 5
  categories: Demo Gallery, test, [uncategorized]

Messages of Help 2-3 Size Orange Fill
  10 images
  options 1-5
  unique hashes: 5
  categories: Demo Gallery, test
```

For the duplicated `Messages of Help` assets, the unique-options list collapses gallery/category copies when the option number and SHA-1 hash match.

To turn these inferred groups into a practical dropdown planning artifact, run:

```bash
python3 smart-canvas-skill/scripts/make_smartcanvas_image_dropdown_blueprint.py before.zip -o dropdown-blueprint.json --csv-output dropdown-blueprint.csv
python3 smart-canvas-skill/scripts/make_smartcanvas_image_dropdown_blueprint.py before.zip --group "Green Fill"
```

The blueprint includes:

- suggested control names and database field names
- unique options collapsed by option number plus SHA-1
- representative captions to try as image values
- all caption/category copies for each option
- dimensions, bitmap type, original paths, thumbnail paths, scaled asset paths, and SHA-1
- warnings for category-copy duplicates, uncategorized copies, missing files, hash mismatches, sidecar size mismatches, and mixed dimensions

The optional CSV output is a flat table with one row per unique dropdown option. Columns include `group_key`, suggested control/database names, option label, representative caption, all caption copies, categories, SHA-1, dimensions, asset paths, and warnings.

On the demo package, the blueprint reports three candidate dropdowns:

```text
Intro 1-3 Size: 2 unique options
Messages of Help 2-3 Size Green Fill: 5 unique options
Messages of Help 2-3 Size Orange Fill: 5 unique options
```

The demo CSV contains 12 rows: 2 intro options, 5 green-fill options, and 5 orange-fill options.

For `Messages of Help 2-3 Size Green Fill`, the suggested control name is:

```text
Messages_of_Help_2_3_Size_Green_Fill
```

and the suggested database field is:

```text
Messages_of_Help_2_3_Size_Green_Fill_Choice
```

Treat the blueprint as a planning aid. It does not prove the final SmartCanvas control XML schema; it identifies the image values, option grouping, and risk flags to use once the control schema is confirmed by a real before/after export.

Use stable, distinctive names such as:

```text
DropdownProbe_Option_A.jpg
DropdownProbe_Option_B.jpg
DropdownProbe_Control
DropdownProbe_Category
```

Distinctive names make binary/string scans much easier.
