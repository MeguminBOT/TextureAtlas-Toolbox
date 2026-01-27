# Texture Atlas Format Reference

This document provides in-depth technical details for every texture atlas and spritesheet
format supported by TextureAtlas Toolbox. Use this reference when choosing an output format
for your project or troubleshooting import issues in game engines.

---

## Table of Contents

1. [Format Comparison Matrix](#format-comparison-matrix)
2. [XML Formats](#xml-formats)
    - [Starling/Sparrow XML](#starlingsparrow-xml)
    - [TexturePacker XML](#texturepacker-xml)
3. [JSON Formats](#json-formats)
    - [JSON Hash](#json-hash)
    - [JSON Array](#json-array)
    - [Phaser 3](#phaser-3)
    - [Aseprite JSON](#aseprite-json)
    - [Egret2D](#egret2d)
    - [Godot Atlas](#godot-atlas)
4. [Text-Based Formats](#text-based-formats)
    - [Spine Atlas](#spine-atlas)
    - [Simple TXT](#simple-txt)
    - [TexturePacker Unity](#texturepacker-unity)
5. [Property List Formats](#property-list-formats)
    - [Cocos2d Plist](#cocos2d-plist)
    - [UIKit Plist](#uikit-plist)
6. [Web Formats](#web-formats)
    - [CSS Spritesheet](#css-spritesheet)
7. [Engine-Specific Formats](#engine-specific-formats)
    - [Paper2D (Unreal)](#paper2d-unreal)
8. [Special Formats](#special-formats)
    - [Adobe Animate Spritemap](#adobe-animate-spritemap)
9. [Common Concepts](#common-concepts)
    - [Rotation](#rotation)
    - [Trimming and Source Size](#trimming-and-source-size)
    - [Pivot Points](#pivot-points)
10. [Format Selection Guide](#format-selection-guide)

---

## Format Comparison Matrix

| Format            | Extension            | Rotation | Trimming | Pivot | Animation | Engine/Framework                  |
| ----------------- | -------------------- | :------: | :------: | :---: | :-------: | --------------------------------- |
| Starling XML      | `.xml`               |    ✅    |    ✅    |  ✅   |    ❌     | Starling, HaxeFlixel, OpenFL      |
| Sparrow XML       | `.xml`               |    ❌    |    ✅    |  ❌   |    ❌     | Sparrow (iOS), legacy Flash       |
| TexturePacker XML | `.xml`               |    ✅    |    ✅    |  ✅   |    ❌     | Generic, custom engines           |
| JSON Hash         | `.json`              |    ✅    |    ✅    |  ✅   |    ❌     | Phaser 2, PixiJS, many frameworks |
| JSON Array        | `.json`              |    ✅    |    ✅    |  ✅   |    ❌     | Phaser 2, PixiJS, CreateJS        |
| Phaser 3          | `.json`              |    ✅    |    ✅    |  ❌   |    ❌     | Phaser 3                          |
| Aseprite JSON     | `.json`              |    ✅    |    ✅    |  ❌   |    ✅     | Aseprite, Phaser, Godot           |
| Egret2D           | `.json`              |    ❌    |    ❌    |  ❌   |    ❌     | Egret2D Engine                    |
| Godot             | `.tpsheet`, `.tpset` |    ❌    |    ❌    |  ❌   |    ❌     | Godot Engine                      |
| Spine             | `.atlas`             |    ✅    |    ✅    |  ❌   |    ✅     | Spine, libGDX                     |
| Simple TXT        | `.txt`               |    ❌    |    ❌    |  ❌   |    ❌     | Custom parsers                    |
| Unity (TP)        | `.tpsheet`           |    ❌    |    ❌    |  ❌   |    ❌     | Unity (via plugin)                |
| Cocos2d Plist     | `.plist`             |    ✅    |    ✅    |  ❌   |    ❌     | Cocos2d, SpriteKit                |
| UIKit Plist       | `.plist`             |    ❌    |    ✅    |  ❌   |    ❌     | iOS UIKit, SpriteKit              |
| CSS Spritesheet   | `.css`               |    ✅    |    ✅    |  ❌   |    ❌     | Web browsers                      |
| Paper2D           | `.paper2dsprites`    |    ✅    |    ✅    |  ✅   |    ❌     | Unreal Engine                     |

-   ✅ Supported natively in format
-   ❌ Not supported or ignored

_Information may be inaccurate on some of these_

---

## XML Formats

### Starling/Sparrow XML

The most widely used XML atlas format, originating from the Sparrow framework (iOS) and later
adopted by Starling (Flash/AIR). Many 2D frameworks support this format.

**File Extension:** `.xml`

**Compatible Engines:**

-   Starling (Flash/AIR Stage3D)
-   Sparrow (iOS/Objective-C)
-   HaxeFlixel / OpenFL
-   Many custom engines

**Structure:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<TextureAtlas imagePath="atlas.png">
    <SubTexture name="walk_01"
                x="0" y="0" width="64" height="64"
                frameX="0" frameY="0" frameWidth="64" frameHeight="64"
                rotated="false"
                pivotX="0.5" pivotY="0.5"/>
    <SubTexture name="walk_02"
                x="66" y="0" width="64" height="64"
                frameX="-2" frameY="-2" frameWidth="68" frameHeight="68"/>
</TextureAtlas>
```

**Attributes:**

| Attribute     | Type    | Required | Description                                              |
| ------------- | ------- | :------: | -------------------------------------------------------- |
| `imagePath`   | string  |    ✅    | Filename of the atlas image (on root element)            |
| `name`        | string  |    ✅    | Unique sprite identifier                                 |
| `x`           | int     |    ✅    | X position in atlas (pixels)                             |
| `y`           | int     |    ✅    | Y position in atlas (pixels)                             |
| `width`       | int     |    ✅    | Sprite width in atlas (pixels)                           |
| `height`      | int     |    ✅    | Sprite height in atlas (pixels)                          |
| `frameX`      | int     |    ❌    | Trim offset X (negative = padding was removed from left) |
| `frameY`      | int     |    ❌    | Trim offset Y (negative = padding was removed from top)  |
| `frameWidth`  | int     |    ❌    | Original untrimmed width                                 |
| `frameHeight` | int     |    ❌    | Original untrimmed height                                |
| `rotated`     | boolean |    ❌    | True if sprite is rotated 90° clockwise (Starling only)  |
| `pivotX`      | float   |    ❌    | Anchor point X (0.0–1.0, default 0.5) (Starling only)    |
| `pivotY`      | float   |    ❌    | Anchor point Y (0.0–1.0, default 0.5) (Starling only)    |

**Starling-Only Extensions:**

| Attribute | Type  | Description                                      |
| --------- | ----- | ------------------------------------------------ |
| `scale`   | float | High-DPI scale factor (e.g., 2.0 for @2x assets) |
| `rotated` | bool  | 90° clockwise rotation flag                      |
| `pivotX`  | float | Horizontal anchor (0.0 = left, 1.0 = right)      |
| `pivotY`  | float | Vertical anchor (0.0 = top, 1.0 = bottom)        |

**Sparrow-Only Attributes:**

| Attribute | Type   | Description                                        |
| --------- | ------ | -------------------------------------------------- |
| `format`  | string | Pixel format hint (e.g., "RGBA8888") — rarely used |

**HaxeFlixel Extension (Non-Standard):**

| Attribute | Type | Description          |
| --------- | ---- | -------------------- |
| `flipX`   | bool | Horizontal flip flag |
| `flipY`   | bool | Vertical flip flag   |

> **Note:** The `flipX`/`flipY` attributes are a HaxeFlixel-specific extension. Most Starling
> and Sparrow implementations ignore these attributes.

**When to Use:**

-   Flash/AIR games with Starling
-   HaxeFlixel / OpenFL projects
-   Frameworks that list "Sparrow" or "Starling" format support
-   When you need rotation and trimming support in XML

---

### TexturePacker XML

An alternative XML format using `<sprite>` elements with shorthand attribute names.
Less common than Starling XML but supported by some tools.

**File Extension:** `.xml`

**Structure:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<TextureAtlas imagePath="atlas.png" width="512" height="512">
    <sprite n="walk_01" x="0" y="0" w="64" h="64"
            oX="0" oY="0" oW="64" oH="64"
            r="n" pX="0.5" pY="0.5"/>
    <sprite n="walk_02" x="66" y="0" w="64" h="64"
            oX="-2" oY="-2" oW="68" oH="68"
            r="y"/>
</TextureAtlas>
```

**Attributes:**

| Attribute | Full Name      | Type   | Description                        |
| --------- | -------------- | ------ | ---------------------------------- |
| `n`       | name           | string | Sprite identifier                  |
| `x`       | x              | int    | X position in atlas                |
| `y`       | y              | int    | Y position in atlas                |
| `w`       | width          | int    | Width in atlas                     |
| `h`       | height         | int    | Height in atlas                    |
| `oX`      | offsetX        | int    | Trim offset X                      |
| `oY`      | offsetY        | int    | Trim offset Y                      |
| `oW`      | originalWidth  | int    | Original untrimmed width           |
| `oH`      | originalHeight | int    | Original untrimmed height          |
| `r`       | rotated        | string | `"y"` or `"true"` = rotated 90° CW |
| `pX`      | pivotX         | float  | Anchor point X (0.0–1.0)           |
| `pY`      | pivotY         | float  | Anchor point Y (0.0–1.0)           |

**When to Use:**

-   Projects requiring compact XML with short attribute names
-   Custom engines that parse this specific format

---

## JSON Formats

### JSON Hash

The most popular JSON atlas format. Frames are stored as an object (hash/dictionary) where
sprite names are keys. This makes runtime lookups O(1) by name.

**File Extension:** `.json`

**Compatible Engines:**

-   Phaser 2.x
-   PixiJS
-   CreateJS
-   Cocos2d-x
-   Most JavaScript game frameworks

**Structure:**

```json
{
	"frames": {
		"walk_01": {
			"frame": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"rotated": false,
			"trimmed": true,
			"spriteSourceSize": { "x": 2, "y": 2, "w": 60, "h": 60 },
			"sourceSize": { "w": 64, "h": 64 },
			"pivot": { "x": 0.5, "y": 0.5 }
		},
		"walk_02": {
			"frame": { "x": 66, "y": 0, "w": 64, "h": 64 },
			"rotated": false,
			"trimmed": false,
			"spriteSourceSize": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"sourceSize": { "w": 64, "h": 64 },
			"pivot": { "x": 0.5, "y": 0.5 }
		}
	},
	"meta": {
		"app": "TextureAtlas Toolbox",
		"version": "1.0",
		"image": "atlas.png",
		"format": "RGBA8888",
		"size": { "w": 512, "h": 512 },
		"scale": "1"
	}
}
```

**Frame Fields:**

| Field              | Type    | Description                                    |
| ------------------ | ------- | ---------------------------------------------- |
| `frame`            | object  | Position and size in atlas: `{x, y, w, h}`     |
| `rotated`          | boolean | True if rotated 90° clockwise in atlas         |
| `trimmed`          | boolean | True if transparent pixels were trimmed        |
| `spriteSourceSize` | object  | Trimmed region within original: `{x, y, w, h}` |
| `sourceSize`       | object  | Original untrimmed dimensions: `{w, h}`        |
| `pivot`            | object  | Anchor point (0.0–1.0): `{x, y}`               |

**Meta Fields:**

| Field     | Type   | Description                     |
| --------- | ------ | ------------------------------- |
| `app`     | string | Generator application name      |
| `version` | string | Generator version               |
| `image`   | string | Atlas image filename            |
| `format`  | string | Pixel format (e.g., "RGBA8888") |
| `size`    | object | Atlas dimensions: `{w, h}`      |
| `scale`   | string | Scale factor (e.g., "1", "2")   |

**When to Use:**

-   Web games with Phaser, PixiJS, or CreateJS
-   When you need fast sprite lookup by name
-   General-purpose JSON atlas needs

---

### JSON Array

Similar to JSON Hash, but frames are stored as an array. Each entry includes a `filename`
field for identification. Some frameworks prefer this format for ordered iteration.

**File Extension:** `.json`

**Structure:**

```json
{
	"frames": [
		{
			"filename": "walk_01",
			"frame": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"rotated": false,
			"trimmed": false,
			"spriteSourceSize": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"sourceSize": { "w": 64, "h": 64 },
			"pivot": { "x": 0.5, "y": 0.5 }
		},
		{
			"filename": "walk_02",
			"frame": { "x": 66, "y": 0, "w": 64, "h": 64 },
			"rotated": false,
			"trimmed": false,
			"spriteSourceSize": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"sourceSize": { "w": 64, "h": 64 },
			"pivot": { "x": 0.5, "y": 0.5 }
		}
	],
	"meta": {
		"image": "atlas.png",
		"size": { "w": 512, "h": 512 }
	}
}
```

**Differences from JSON Hash:**

-   `frames` is an array, not an object
-   Each entry has a `filename` field
-   Preserves sprite ordering (useful for animations)

**When to Use:**

-   When sprite order matters (animation sequences)
-   Frameworks that expect array-based frame lists

---

### Phaser 3

Phaser 3 introduced a new multi-atlas format supporting multiple texture pages.
Each page is a texture entry containing its own frames array.

**File Extension:** `.json`

**Compatible Engines:**

-   Phaser 3.x exclusively

**Structure:**

```json
{
	"textures": [
		{
			"image": "atlas.png",
			"format": "RGBA8888",
			"size": { "w": 512, "h": 512 },
			"scale": 1,
			"frames": [
				{
					"filename": "walk_01",
					"frame": { "x": 0, "y": 0, "w": 64, "h": 64 },
					"rotated": false,
					"trimmed": false,
					"spriteSourceSize": { "x": 0, "y": 0, "w": 64, "h": 64 },
					"sourceSize": { "w": 64, "h": 64 }
				}
			]
		}
	],
	"meta": {
		"generator": "TextureAtlas Toolbox"
	}
}
```

**Key Differences from JSON Hash/Array:**

-   Top-level `textures` array (supports multi-page atlases)
-   Each texture has its own `image`, `size`, and `frames`
-   `scale` is a number, not a string
-   No `pivot` field in standard Phaser 3 format

**When to Use:**

-   Phaser 3 projects exclusively
-   Multi-page atlas requirements

---

### Aseprite JSON

Aseprite's native export format with built-in animation support via frame tags.
Includes per-frame duration for variable-speed animations.

**File Extension:** `.json`

**Compatible Engines:**

-   Aseprite (native)
-   Phaser (with loader plugins)
-   Godot (with importers)
-   Any engine with Aseprite JSON support

**Structure:**

```json
{
	"frames": {
		"character_0": {
			"frame": { "x": 0, "y": 0, "w": 32, "h": 32 },
			"rotated": false,
			"trimmed": false,
			"spriteSourceSize": { "x": 0, "y": 0, "w": 32, "h": 32 },
			"sourceSize": { "w": 32, "h": 32 },
			"duration": 100
		},
		"character_1": {
			"frame": { "x": 32, "y": 0, "w": 32, "h": 32 },
			"duration": 100
		}
	},
	"meta": {
		"app": "https://www.aseprite.org/",
		"version": "1.3",
		"image": "character.png",
		"format": "RGBA8888",
		"size": { "w": 128, "h": 32 },
		"scale": "1",
		"frameTags": [
			{ "name": "idle", "from": 0, "to": 3, "direction": "forward" },
			{ "name": "walk", "from": 4, "to": 7, "direction": "forward" }
		],
		"layers": [
			{ "name": "Layer 1", "opacity": 255, "blendMode": "normal" }
		],
		"slices": []
	}
}
```

**Unique Fields:**

| Field       | Location    | Description                              |
| ----------- | ----------- | ---------------------------------------- |
| `duration`  | frame entry | Frame display time in milliseconds       |
| `frameTags` | meta        | Animation definitions with frame ranges  |
| `layers`    | meta        | Layer information from the Aseprite file |
| `slices`    | meta        | 9-slice data for UI elements             |

**Frame Tag Fields:**

| Field       | Type   | Description                               |
| ----------- | ------ | ----------------------------------------- |
| `name`      | string | Animation name                            |
| `from`      | int    | Starting frame index                      |
| `to`        | int    | Ending frame index                        |
| `direction` | string | `"forward"`, `"reverse"`, or `"pingpong"` |

**When to Use:**

-   Aseprite workflow (direct export)
-   Variable frame timing animations
-   When you need animation metadata embedded in the atlas

---

### Egret2D

A minimal JSON format used by the Egret2D game engine. Contains only essential
position and dimension data without trimming or rotation support.

**File Extension:** `.json`

**Compatible Engines:**

-   Egret2D Engine

**Structure:**

```json
{
	"file": "atlas.png",
	"frames": {
		"sprite_01": { "x": 0, "y": 0, "w": 64, "h": 64 },
		"sprite_02": { "x": 66, "y": 0, "w": 48, "h": 48 }
	}
}
```

**Fields:**

| Field  | Type   | Description          |
| ------ | ------ | -------------------- |
| `file` | string | Atlas image filename |
| `x`    | int    | X position in atlas  |
| `y`    | int    | Y position in atlas  |
| `w`    | int    | Sprite width         |
| `h`    | int    | Sprite height        |

**Limitations:**

-   No rotation support
-   No trimming/source size
-   No pivot points

**When to Use:**

-   Egret2D engine projects
-   Simple use cases not requiring trimming or rotation

---

### Godot Atlas

JSON format for Godot Engine's TexturePacker importer. Uses a `textures`/`sprites`
structure with region-based coordinates.

**File Extension:** `.tpsheet` or `.tpset`

**Compatible Engines:**

-   Godot Engine (3.x and 4.x with importer)

**Structure:**

```json
{
	"textures": [
		{
			"image": "atlas.png",
			"size": { "w": 512, "h": 512 },
			"sprites": [
				{
					"filename": "walk_01",
					"region": { "x": 0, "y": 0, "w": 64, "h": 64 }
				},
				{
					"filename": "walk_02",
					"region": { "x": 66, "y": 0, "w": 64, "h": 64 }
				}
			]
		}
	]
}
```

**Sprite Fields:**

| Field      | Type   | Description                       |
| ---------- | ------ | --------------------------------- |
| `filename` | string | Sprite identifier                 |
| `region`   | object | Position and size: `{x, y, w, h}` |

**When to Use:**

-   Godot Engine projects
-   When using the TexturePacker Godot importer

---

## Text-Based Formats

### Spine Atlas

The official atlas format for Spine animation software and libGDX framework.
A plain-text format with indented key-value pairs for each sprite.

**File Extension:** `.atlas`

**Compatible Engines:**

-   Spine (Esoteric Software)
-   libGDX
-   Spine runtimes for Unity, Unreal, Cocos2d-x, etc.

**Structure:**

```
atlas.png
size: 512, 512
format: RGBA8888
filter: Linear, Linear
repeat: none
walk_01
  rotate: false
  xy: 0, 0
  size: 64, 64
  orig: 64, 64
  offset: 0, 0
  index: -1
walk_02
  rotate: true
  xy: 66, 0
  size: 64, 64
  orig: 64, 64
  offset: 0, 0
  index: -1
```

**Page Header (First Lines):**

| Line      | Description                                |
| --------- | ------------------------------------------ |
| Line 1    | Image filename                             |
| `size:`   | Atlas dimensions (width, height)           |
| `format:` | Pixel format (RGBA8888, RGB888, etc.)      |
| `filter:` | Min/mag texture filters (Linear, Nearest)  |
| `repeat:` | Texture repeat mode (none, x, y, xy)       |
| `pma:`    | Premultiplied alpha (optional, true/false) |

**Region Fields (Indented):**

| Field    | Description                                   |
| -------- | --------------------------------------------- |
| `rotate` | `true` = rotated 90° clockwise                |
| `xy`     | Position in atlas (x, y)                      |
| `size`   | Size in atlas (may be swapped if rotated)     |
| `orig`   | Original untrimmed size                       |
| `offset` | Trim offset (x, y)                            |
| `index`  | Frame index for animations (-1 = not indexed) |

**When to Use:**

-   Spine animation projects
-   libGDX game development
-   Any project using Spine runtimes

---

### Simple TXT

A minimal human-readable format with one sprite per line. Easy to parse
with basic string operations, suitable for custom engines or prototyping.

**File Extension:** `.txt`

**Structure:**

```
# Atlas: atlas.png
sprite_01 = 0 0 64 64
sprite_02 = 66 0 48 48
sprite_03 = 0 66 32 32
```

**Format:** `name = x y width height`

**Limitations:**

-   No rotation support
-   No trimming information
-   No pivot points
-   No metadata block

**When to Use:**

-   Quick prototyping
-   Custom engines with simple parsers
-   Human-editable atlas definitions

---

### TexturePacker Unity

A semicolon-delimited text format for Unity projects using TexturePacker.
Requires the TexturePacker Unity importer.

**File Extension:** `.tpsheet`

**Structure:**

```
:format=40300
:texture=atlas.png
:size=512x512
sprite_01;0;0;64;64;0.5;0.5
sprite_02;66;0;48;48;0.5;0.5
```

**Header Lines:**

-   `:format=40300` — Format version
-   `:texture=atlas.png` — Atlas image filename
-   `:size=512x512` — Atlas dimensions

**Sprite Line Format:** `name;x;y;width;height;pivotX;pivotY`

**When to Use:**

-   Unity projects with TexturePacker workflow
-   When the Unity importer plugin is installed

---

## Property List Formats

### Cocos2d Plist

Apple property list format used by Cocos2d, SpriteKit, and iOS/macOS frameworks.
Stores frame data using Cocoa-style string representations.

**File Extension:** `.plist`

**Compatible Engines:**

-   Cocos2d / Cocos2d-x
-   SpriteKit
-   iOS/macOS native apps

**Structure (Conceptual XML):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>frames</key>
    <dict>
        <key>walk_01.png</key>
        <dict>
            <key>frame</key>
            <string>{{0,0},{64,64}}</string>
            <key>offset</key>
            <string>{0,0}</string>
            <key>rotated</key>
            <false/>
            <key>sourceColorRect</key>
            <string>{{0,0},{64,64}}</string>
            <key>sourceSize</key>
            <string>{64,64}</string>
        </dict>
    </dict>
    <key>metadata</key>
    <dict>
        <key>format</key>
        <integer>2</integer>
        <key>textureFileName</key>
        <string>atlas.png</string>
        <key>size</key>
        <string>{512,512}</string>
    </dict>
</dict>
</plist>
```

**Frame Fields:**

| Key               | Format          | Description                    |
| ----------------- | --------------- | ------------------------------ |
| `frame`           | `{{x,y},{w,h}}` | Position and size in atlas     |
| `offset`          | `{x,y}`         | Trim offset                    |
| `rotated`         | boolean         | 90° clockwise rotation         |
| `sourceColorRect` | `{{x,y},{w,h}}` | Trimmed region within original |
| `sourceSize`      | `{w,h}`         | Original untrimmed dimensions  |

**Format Versions:**

-   Format 2: Standard Cocos2d format
-   Format 3: Extended format with additional fields

**When to Use:**

-   Cocos2d / Cocos2d-x projects
-   iOS/macOS native SpriteKit apps
-   Apple platform development

---

### UIKit Plist

A simplified plist format with scalar values instead of Cocoa-style strings.
Easier to parse in non-Apple environments.

**File Extension:** `.plist`

**Frame Fields:**

| Key  | Type | Description         |
| ---- | ---- | ------------------- |
| `x`  | int  | X position in atlas |
| `y`  | int  | Y position in atlas |
| `w`  | int  | Width in atlas      |
| `h`  | int  | Height in atlas     |
| `oX` | int  | Offset X (trim)     |
| `oY` | int  | Offset Y (trim)     |
| `oW` | int  | Original width      |
| `oH` | int  | Original height     |

**Differences from Cocos2d Plist:**

-   Uses scalar integer values
-   No Cocoa-style `{{x,y},{w,h}}` strings
-   No rotation support

**When to Use:**

-   Simpler iOS/macOS projects
-   When you need easier plist parsing

---

## Web Formats

### CSS Spritesheet

Generates CSS class definitions for displaying sprites as background images.
Supports rotation via CSS transforms and trim offsets via margins.

**File Extension:** `.css`

**Structure:**

```css
/*
 * Generated by TextureAtlas Toolbox
 * Atlas: atlas.png
 */

.walk_01 {
	background: url("atlas.png") -0px -0px;
	width: 64px;
	height: 64px;
}

.walk_02 {
	background: url("atlas.png") -66px -0px;
	width: 48px;
	height: 48px;
}

.rotated_sprite {
	background: url("atlas.png") -120px -0px;
	width: 64px;
	height: 64px;
	transform: rotate(-90deg);
	margin-left: 2px;
	margin-top: 2px;
}
```

**CSS Properties Used:**

| Property      | Purpose                              |
| ------------- | ------------------------------------ |
| `background`  | Atlas image URL and sprite position  |
| `width`       | Sprite display width                 |
| `height`      | Sprite display height                |
| `transform`   | `rotate(-90deg)` for rotated sprites |
| `margin-left` | Trim offset X adjustment             |
| `margin-top`  | Trim offset Y adjustment             |

**Usage in HTML:**

```html
<div class="walk_01"></div>
<div class="walk_02"></div>
```

**When to Use:**

-   Web development (HTML/CSS)
-   CSS-only sprite implementations
-   When JavaScript sprite libraries aren't needed

---

## Engine-Specific Formats

### Paper2D (Unreal)

JSON format for Unreal Engine's Paper2D plugin. Follows the JSON Hash structure
with additional pivot point support.

**File Extension:** `.paper2dsprites`

**Compatible Engines:**

-   Unreal Engine 4/5 (Paper2D plugin)

**Structure:**

```json
{
	"frames": {
		"walk_01": {
			"frame": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"rotated": false,
			"trimmed": false,
			"spriteSourceSize": { "x": 0, "y": 0, "w": 64, "h": 64 },
			"sourceSize": { "w": 64, "h": 64 },
			"pivot": { "x": 0.5, "y": 0.5 }
		}
	},
	"meta": {
		"image": "atlas.png",
		"size": { "w": 512, "h": 512 }
	}
}
```

**When to Use:**

-   Unreal Engine 2D projects with Paper2D
-   When importing atlases into UE4/UE5

---

## Special Formats

These formats require specialized handling and are **extraction-only** in TextureAtlas Toolbox.
They cannot be generated as output formats.

---

### Adobe Animate Spritemap

> ⚠️ **EXTRACTION ONLY**  
> TextureAtlas Toolbox can only extract this format. It cannot be used as an output format.
> Most other tools do not support this format at all for extraction.

A proprietary three-file format exported by Adobe Animate (formerly Flash) for HTML5 Canvas
and WebGL animations. Contains sprite atlas data, sprite metadata, and full animation timeline information.

While it’s technically a proprietary format, it’s not a protected or a closed format.

You can parse it freely, reverse-engineer it, or convert it into another atlas format.

It’s not restricted, because JSON itself is open.

**File Extension:** Three files required:

-   `spritemap1.png` (or `spritemap.png`) — The packed sprite atlas image
-   `spritemap1.json` (or `spritemap.json`) — Sprite positions and dimensions in the atlas
-   `Animation.json` — Timeline, symbol definitions, and animation data

**Compatible Engines:**

-   Adobe Animate runtime (CreateJS-based)
-   TextureAtlas Toolbox (extraction only)
-   Custom parsers with timeline support

**Why This Format is Special:**

Unlike standard atlas formats that only store sprite positions, Adobe Animate spritemaps
include full animation timeline data:

-   **Symbol hierarchies** — Nested movieclips and graphics
-   **Transform matrices** — Per-frame position, rotation, scale, skew
-   **Layer structure** — Multiple layers with depth ordering
-   **Frame labels** — Named keyframes for animation control
-   **Easing data** — Tween interpolation curves

This makes extraction significantly more complex than standard atlas formats.

**spritemap.json Structure:**

```json
{
	"ATLAS": {
		"SPRITES": [
			{
				"SPRITE": {
					"name": "symbol_0",
					"x": 0,
					"y": 0,
					"w": 64,
					"h": 64,
					"rotated": false
				}
			},
			{
				"SPRITE": {
					"name": "symbol_1",
					"x": 66,
					"y": 0,
					"w": 48,
					"h": 48,
					"rotated": false
				}
			}
		]
	},
	"meta": {
		"app": "Adobe Animate",
		"version": "24.0",
		"image": "spritemap1.png",
		"format": "RGBA8888",
		"size": { "w": 4096, "h": 2430 },
		"resolution": "1"
	}
}
```

**spritemap.json Fields:**

| Key               | Description                                   |
| ----------------- | --------------------------------------------- |
| `ATLAS`           | Container for sprite definitions              |
| `SPRITES`         | Array of sprite entries                       |
| `SPRITE`          | Individual sprite definition object           |
| `name`            | Symbol instance name (matches Animation.json) |
| `x`, `y`          | Position in spritemap image                   |
| `w`, `h`          | Dimensions in spritemap                       |
| `rotated`         | Whether sprite is rotated 90° in atlas        |
| `meta`            | Metadata about the atlas                      |
| `meta.app`        | Application name ("Adobe Animate")            |
| `meta.version`    | Application version                           |
| `meta.image`      | Filename of the spritemap PNG                 |
| `meta.format`     | Pixel format (e.g., "RGBA8888")               |
| `meta.size`       | Atlas dimensions (`w`, `h`)                   |
| `meta.resolution` | Scale factor (usually "1")                    |

**Animation.json Structure:**

The Animation.json file contains timeline and animation data only. Sprite positions are
stored separately in spritemap.json.

```json
{
	"AN": {
		"N": "MyAnimation",
		"STI": {
			"SI": {
				"SN": "MainSymbol",
				"IN": "",
				"ST": "G",
				"M3D": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 858, 770, 0, 1]
			}
		},
		"SN": "MainSymbol",
		"TL": {
			"L": [
				{
					"LN": "Layer_1",
					"FR": [
						{
							"N": "Idle",
							"I": 0,
							"DU": 14,
							"E": []
						},
						{
							"N": "Walk",
							"I": 14,
							"DU": 8,
							"E": []
						}
					]
				}
			]
		}
	},
	"SD": {
		"S": [
			{
				"SN": "idle_animation",
				"TL": {
					"L": [
						{
							"LN": "Layer_1",
							"FR": [
								{
									"I": 0,
									"DU": 3,
									"E": [
										{
											"ASI": 0,
											"M3D": [
												1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1,
												0, 0, 0, 0, 1
											]
										}
									]
								}
							]
						}
					]
				}
			}
		]
	},
	"MD": {
		"FRT": 24.0
	}
}
```

**Animation.json Top-Level Keys:**

| Key  | Description                                                   |
| ---- | ------------------------------------------------------------- |
| `AN` | Main animation with timeline, stage instance, and symbol name |
| `SD` | Symbol definitions (reusable movieclips/graphics)             |
| `MD` | Metadata including frame rate (`FRT`)                         |

**AN (Animation) Keys:**

| Key   | Description                             |
| ----- | --------------------------------------- |
| `N`   | Animation name                          |
| `SN`  | Symbol name                             |
| `STI` | Stage instance — root element placement |
| `TL`  | Timeline with layers and frames         |

**Timeline Keys:**

| Key  | Full Name  | Description                            |
| ---- | ---------- | -------------------------------------- |
| `TL` | Timeline   | Timeline object containing layers      |
| `L`  | Layers     | Array of layer objects                 |
| `LN` | Layer Name | Name of the layer                      |
| `FR` | Frames     | Array of keyframe objects              |
| `N`  | Name       | Frame label (e.g., "Idle", "Walk")     |
| `I`  | Index      | Frame index (0-based)                  |
| `DU` | Duration   | Number of frames this keyframe spans   |
| `E`  | Elements   | Array of display objects on this frame |

**Element Keys:**

| Key   | Full Name          | Description                                              |
| ----- | ------------------ | -------------------------------------------------------- |
| `ASI` | Atlas Sprite Index | Reference to sprite index in spritemap.json              |
| `SI`  | Symbol Instance    | Reference to a symbol in SD                              |
| `ST`  | Symbol Type        | "G" (graphic), "MC" (movieclip), etc.                    |

**Transform keys:**

| Key   | Full Name          | Description                                              |
| ----- | ------------------ | -------------------------------------------------------- |
| `M3D` | Matrix 3D          | 4x4 3D transformation matrix (16 values)                 |
| `MX`  | Matrix 2D          | 3x2 2D transformation matrix (6 values)                  |

**Extraction Behavior:**

TextureAtlas Toolbox reconstructs Adobe Animate spritemap animations through a multi-stage
rendering pipeline:

1. **Normalization** — The Animation.json is normalized to a consistent format. This includes
converting verbose key names to abbreviated forms and transforming `MX` (6-value 2D) matrices
to `M3D` (16-value 3D) format for unified processing.

2. **Atlas Loading** — The spritemap PNG is loaded and the `ATLAS.SPRITES` array is parsed to
create a lookup table mapping sprite names to their atlas regions (position, dimensions,
rotation state).

3. **Timeline Walking** — The renderer walks through both root timeline (`AN.TL`) and symbol
definitions (`SD.S`). Each symbol's layers are processed in reverse order (back-to-front)
to respect Flash's layer stacking.

4. **Frame Resolution** — For each frame index, a binary search locates the active keyframe
based on `I` (index) and `DU` (duration) values. Nested symbol instances resolve their
internal frame using loop mode (`LP`):
- `LP` (Loop) — Cycles through frames continuously
- `PO` (Play Once) — Plays once, then holds the last frame
- `SF` (Single Frame) — Displays only the specified `FF` (first frame)

5. **Transform Composition** — Each element's `M3D` or `MX` matrix is parsed into a 3×3 affine
transform. Parent transforms accumulate via matrix multiplication (`@`) as the renderer
descends into nested symbols, preserving the full transform hierarchy.

6. **Sprite Compositing** — Individual sprites are extracted from the atlas. NumPy computes the
transformed bounding box from corner positions, then PIL's `Image.transform()` applies the
affine transformation. Sprites are alpha-composited onto the canvas in layer order. Color
effects (`C` key) are applied when present.

7. **Clipping Masks** — Layers marked as clipping masks (`LT: "Clp"`) use a canvas stack
approach: the mask and masked content render to temporary canvases, then combine using
alpha multiplication before compositing onto the base canvas.

8. **Bounding Box Calculation** — After rendering all frames for a symbol or label range, the
combined bounding box is calculated and frames are cropped to minimize output size while
preserving registration (offset data for proper playback alignment).

**Memory Considerations:**

Adobe Animate spritemaps can be memory-intensive to reconstruct for export:
-   Large spritemap images (often 4096×4096 or larger)
-   Complex nested symbol hierarchies requiring recursive rendering
-   Many unique frames when transforms vary per-frame

Consider processing these files individually rather than in large batches.

When used properly in a game engine, unlike our extractor, it’s a memory efficient format.
If you have any ideas on improvements to the spritemap processing, you can open a PR with your changes.

**When to Use:**
-   Extracting animations from Adobe Animate HTML5 Canvas exports
-   Converting Flash/Animate assets to standard sprite sheets
-   Recovering individual frames from Animate projects
-   Game engines with support for Adobe Spritemaps

---

## Common Concepts

### Rotation

**90° Clockwise Rotation** is the standard convention used across formats.
When a sprite is marked as rotated:

1. The sprite is stored rotated 90° clockwise in the atlas
2. The `width` and `height` in the atlas are swapped
3. The runtime must rotate the sprite -90° (counter-clockwise) when rendering

**Formats Supporting Rotation:**

-   Starling XML ✅
-   TexturePacker XML ✅
-   JSON Hash/Array ✅
-   Phaser 3 ✅
-   Aseprite JSON ✅
-   Spine ✅
-   Cocos2d Plist ✅
-   Paper2D ✅
-   CSS (via `transform`) ✅

**Formats Without Rotation:**

-   Sparrow XML ❌
-   Egret2D ❌
-   Godot ❌
-   Simple TXT ❌
-   UIKit Plist ❌
-   Unity (TP) ❌

---

### Trimming and Source Size

Trimming removes transparent pixels from sprite edges to save atlas space.
The format must store enough data to reconstruct the original dimensions.

**Key Fields:**

| Concept        | JSON Field         | XML Attribute       | Description                  |
| -------------- | ------------------ | ------------------- | ---------------------------- |
| Atlas position | `frame.x/y`        | `x`, `y`            | Where sprite is in atlas     |
| Atlas size     | `frame.w/h`        | `width`, `height`   | Trimmed size in atlas        |
| Trim offset    | `spriteSourceSize` | `frameX/Y`          | Where trimmed region starts  |
| Original size  | `sourceSize`       | `frameWidth/Height` | Full untrimmed dimensions    |
| Trimmed flag   | `trimmed`          | (implicit)          | Whether trimming was applied |

**Example:**

-   Original sprite: 64×64 pixels
-   After trimming: 48×48 pixels (8px transparent border removed)
-   `spriteSourceSize`: `{x: 8, y: 8, w: 48, h: 48}`
-   `sourceSize`: `{w: 64, h: 64}`

---

### Pivot Points

Pivot (anchor) points define the sprite's center of rotation and scaling.
Expressed as normalized coordinates (0.0 to 1.0).

**Common Values:**

| Position      | pivotX | pivotY |
| ------------- | ------ | ------ |
| Center        | 0.5    | 0.5    |
| Top-left      | 0.0    | 0.0    |
| Bottom-center | 0.5    | 1.0    |
| Top-center    | 0.5    | 0.0    |

**Formats Supporting Pivot:**

-   Starling XML ✅
-   TexturePacker XML ✅
-   JSON Hash/Array ✅
-   Paper2D ✅

---

## Format Selection Guide

### By Engine/Framework

| Engine/Framework | Recommended Format      | Alternative   |
| ---------------- | ----------------------- | ------------- |
| Phaser 3         | Phaser 3                | JSON Hash     |
| Phaser 2         | JSON Hash               | JSON Array    |
| PixiJS           | JSON Hash               | JSON Array    |
| HaxeFlixel       | Starling XML            | —             |
| OpenFL           | Starling XML            | —             |
| Starling         | Starling XML            | —             |
| libGDX           | Spine Atlas             | JSON Hash     |
| Spine            | Spine Atlas             | —             |
| Cocos2d          | Cocos2d Plist           | JSON Hash     |
| Godot            | Godot Atlas             | Aseprite JSON |
| Unity            | TexturePacker Unity     | JSON Hash     |
| Unreal (Paper2D) | Paper2D                 | —             |
| Web (CSS)        | CSS Spritesheet         | —             |
| Custom Engine    | JSON Hash or Simple TXT | —             |

### By Feature Requirements

| Requirement           | Recommended Formats                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------- |
| Rotation support      | Starling XML, TexturePacker XML, JSON Hash/Array, Phaser 3, Aseprite, Spine, Plist, Paper2D |
| Animation metadata    | Aseprite JSON, Spine Atlas                                                                  |
| Variable frame timing | Aseprite JSON                                                                               |
| Pivot/anchor points   | JSON Hash, Starling XML, Paper2D                                                            |
| Minimal file size     | Simple TXT, Egret2D                                                                         |
| Maximum compatibility | JSON Hash                                                                                   |

### Extraction-Only Formats

The following formats can only be **read/extracted** by TextureAtlas Toolbox and cannot
be used as output formats:

| Format                  | Why Extraction Only                                      |
| ----------------------- | -------------------------------------------------------- |
| Adobe Animate Spritemap | Complex timeline data; requires proprietary Adobe export |

To convert assets from these formats, extract with TextureAtlas Toolbox and re-export
to a standard format like JSON Hash or Starling XML.

---

_Last updated: December 6, 2025 — TextureAtlas Toolbox v2.0.0_
