# SmartCanvas ZIP Package Structure

This reference is based on `example-zip/1. blank design.zip`. SmartCanvas exports are ZIP packages with an outer import/export wrapper and an inner campaign ZIP that contains the editable design payload.

## High-Level Shape

The blank export has this outer structure:

```text
SmartCanvas export.zip
├── info.json
├── Admin/
│   └── <campaign-name>.zip
├── Impositions/
│   └── <uuid>.xml
└── PdfPresets/
    └── <uuid>.xml
```

Notes:

- The ZIP entries in the observed export use Windows-style backslashes, for example `Admin\<campaign>.zip`.
- `Admin/<campaign-name>.zip` is the nested archive containing the actual SmartCanvas design.
- `Impositions/` and `PdfPresets/` each contain 34 UUID-named XML files in the blank export.
- The `Impositions/` and `PdfPresets/` filename sets are identical in the blank export, and matching files are byte-for-byte identical.

## Outer Wrapper Files

### `info.json`

`info.json` is wrapper-level import/export metadata. It is not the page layout.

Observed fields include:

- `SourceAccountId`
- `NewAccountId`
- `StatusId`
- `Admin.Campaigns[]`
- `SourceCampaignId`
- `SourceCampaignName`
- `SourceCampaignDisplayName`
- `SourceDesignName`
- import status fields such as `Imported`, `ErrorReport`, and `ImportProgress`

In the blank export, the campaign name in `info.json` matches the nested campaign ZIP and the design XML campaign name.

### `Impositions/*.xml`

Each imposition XML uses an `Imposition` root:

```xml
<Imposition Version="2.0"
  ImpositionType="PageSequence"
  ImpositionDisplayName="Test Imposition"
  ImpositionFileName="075d4cf4-4125-460b-a8ff-a9087b3a01b2.xml">
  ...
</Imposition>
```

These files describe output/page imposition presets, not canvas controls. `ImpositionFileName` matches the UUID filename.

### `PdfPresets/*.xml`

In the blank export, these are duplicates of the matching `Impositions/*.xml` files. Preserve them unless deliberately changing output presets.

## Inner Campaign ZIP

The nested `Admin/<campaign-name>.zip` contains:

```text
<campaign-name>/
├── css.css
├── description.xml
├── Document.xml
├── fonts/
│   └── xap/
├── lasthash.txt
├── Storyboard_Thumb.png
├── template.dhtt
└── template.xml
databases.bin
info.bin
scriptsnippets.xml
```

The observed blank campaign is named `962_Test_Template__ZIP_manipulations_`, but tooling should treat this as variable.

Important details:

- The campaign-named directory contains the design XML and design-adjacent assets.
- `databases.bin`, `info.bin`, and `scriptsnippets.xml` are top-level entries inside the inner ZIP, not inside the campaign directory.
- The blank export does not contain `smartcampaign.xml`. Do not assume that file exists for all SmartCanvas exports.

## Design XML Files

### `<campaign-name>/template.xml`

`template.xml` is the main PURL/SmartCanvas design XML.

The blank export root is:

```xml
<Purl Version="4" DesignVersion="5" CampaignName="962_Test_Template__ZIP_manipulations_" ...>
  ...
</Purl>
```

Observed direct child sections:

- `Description`
- `TextStyles`
- `Doc`
- `Doc`
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

The two `Doc` nodes represent:

- `Storyboard` / `Whiteboard`
- `Document` / `DynamicDocument`

The blank export has an empty `Switches` section and 168 `DatabaseColumn` entries. For image dropdown work, `template.xml` is expected to be one of the primary files where new switches, form fields, image references, and database bindings may appear in before/after comparisons.

### `<campaign-name>/Document.xml`

`Document.xml` describes the production document/page/frame/layer shell.

The blank export root is:

```xml
<Documents SourceJobTemplate="" OriginAccountID="2" OriginCampaign="EmptyDocument" OriginDesign="Document" Version="3">
  ...
</Documents>
```

Observed hierarchy:

```text
Documents
└── Document
    └── Page
        └── Frame
            └── Composition
                └── Layers
                    └── Layer
```

The blank export contains one page, one frame, one composition, and one default layer:

```xml
<Layer DisplayName="Default Layer" SwitchMode="Always" Switch="" IsDefault="true" ... />
```

For image dropdown work, `Document.xml` is expected to be the primary place where new visible image layers and their switch bindings are represented.

### `<campaign-name>/template.dhtt`

`template.dhtt` stores DirectSmile PURL/template settings.

The blank export root is:

```xml
<DirectSmilePUrlTemplate Version="5" NeededLicenses="XMedia_VDP" RenderMode="1" DesignerAccountId="2" ...>
  ...
</DirectSmilePUrlTemplate>
```

Observed direct child sections:

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
- `Smss`
- `ErrorMessages`
- `Languages`
- `Cookies`
- `Scores`
- `WebApiSettings`

In the blank export, most sections are empty. `Templates` contains four default template entries and `Languages` contains one entry.

### `<campaign-name>/description.xml`

Small metadata file:

```xml
<Description Name="" Description="">
  <Categories />
  <TargetAudiences />
  <OutboundChannels />
</Description>
```

### `scriptsnippets.xml`

The blank export contains an empty script snippet document:

```xml
<ScriptSnippets />
```

## Asset and Generated Files

### `<campaign-name>/css.css`

Generated stylesheet for SmartCanvas/PURL dynamic components. In a blank design this file can still contain many default component class blocks. Do not infer that a control exists solely because a CSS class exists.

### `<campaign-name>/fonts/`

Font staging directory. The blank export contains `fonts/` and `fonts/xap/` directory entries, with no font files listed there.

### `<campaign-name>/Storyboard_Thumb.png`

Thumbnail image for the storyboard/design preview.

### `<campaign-name>/lasthash.txt`

Small generated hash/checksum file. Preserve it unless a controlled before/after export shows how SmartCanvas expects it to change.

### `<campaign-name>/images/`

The blank export does not include an `images/` directory entry. Other SmartCanvas exports may contain:

- original image assets
- preview/thumbnail derivatives
- sidecar metadata such as `_info.xml`

For image dropdown generation, new images should be staged in the inner campaign payload according to the patterns proven by before/after exports.

## Binary Files

### `databases.bin`

Opaque database payload.

Blank export fingerprint:

```text
size: 781 bytes
sha256: 68a2762d05ca5dd8bf890b230a2f66b26420be917d63a1061b24d5787d0c9059
```

Treat this as generated/opaque unless before/after testing proves a safe writer.

### `info.bin`

Large opaque catalog/resource payload.

Blank export fingerprint:

```text
size: 40869407 bytes
sha256: cddbb7549072611988e174979369624af46f9df4688ed045b55dc8a65f022d5b
```

This file likely stores catalog/resource metadata and embedded binary resource data. It should be inspected by diffing known exports, but not hand-edited without a verified encoder.

## Generic Editing Guidance

When building tools for SmartCanvas ZIPs:

- Detect whether input is an outer export ZIP or a direct inner campaign ZIP.
- Preserve the outer wrapper when the input has `info.json`, `Admin/`, `Impositions/`, and `PdfPresets/`.
- Treat `Admin/<campaign-name>.zip` as the canonical editable payload in outer exports.
- Preserve ZIP member names, path separators, timestamps, compression style, and ordering where practical.
- Do not assume a fixed campaign name; derive it from the inner campaign directory or `template.xml`.
- Do not assume `smartcampaign.xml` exists.
- Treat `.bin` files as opaque unless a specific workflow has proven how to update them.
- Prefer before/after diffs from SmartCanvas-authored exports before mutating controls, switches, image metadata, or dropdowns.

## Expected Mutation Areas for Image Dropdowns

Based on the blank package structure, an image dropdown workflow will likely need to modify or add:

- image asset files under the campaign payload
- image metadata sidecars, if required by the target export format
- `Document.xml` layers and switch bindings
- `template.xml` switches, field/control definitions, image references, and database bindings
- possibly `template.dhtt` if the UI control is represented there
- possibly `info.bin` if SmartCanvas requires catalog metadata for new assets

Use the blank design as a baseline and compare it against SmartCanvas-authored exports that add images, switches, and dropdown controls.
