# Friday Night Funkin' Guide

Specialized guide for extracting and processing Friday Night Funkin' (FNF) character sprites and animations.

## Table of Contents

- [What is Friday Night Funkin'?](#what-is-friday-night-funkin)
- [FNF Engine Support](#fnf-engine-support)
- [FNF File Structure](#fnf-file-structure)
    - [Example: Psych Engine JSON Structure](#example-psych-engine-json-structure)
    - [Example: V-Slice Engine JSON Structure](#example-v-slice-engine-json-structure)
- [Automatically loading FNF characters settings](#automatically-loading-fnf-characters-settings)
- [FNF Animation Naming Conventions](#fnf-animation-naming-conventions)
    - [Standard Animation Names](#standard-animation-names)
    - [Prefix Patterns](#prefix-patterns)
    - [Custom Naming](#custom-naming)
- [Known Bugs and Limitations](#known-bugs--limitations)

## What is Friday Night Funkin'?

Friday Night Funkin' (FNF) is a popular rhythm game with a vibrant modding community. Characters are typically stored as Starling spritesheets or Adobe Spritemaps with accompanying "Character data files" usually in JSON or XML format. These files define animation properties like scale, fps and more.

## FNF Engine Support

This tool supports character data from multiple FNF engines:

- **Kade Engine**: .json
- **Psych Engine**: .json
- **Codename Engine**: .xml
- **V-Slice (official Funkin')**: .json

## FNF File Structure

**Most engines are structured similarly to this**

```
assets (or mod folder)
└── characters
    └── character.json
└── images/characters
    ├── character1.png
    └── character1.xml
```

### Example: Psych Engine JSON Structure

```json
{
	"animations": [
		{
			"name": "idle",
			"prefix": "BF idle dance",
			"fps": 24,
			"loop": false,
			"indices": [],
			"offsets": [0, 0]
		},
		{
			"name": "singLEFT",
			"prefix": "BF NOTE LEFT",
			"fps": 24,
			"loop": false,
			"indices": [],
			"offsets": [-5, -6]
		}
	],
	"image": "character1",
	"scale": 1,
	"sing_duration": 6.1,
	"healthicon": "bf"
}
```

Please note that the following data is not used by this tool:

```json
{
    "healthicon"
    "sing_duration"
}
```

`offsets` are loaded and stored as alignment overrides on each animation, so they are available in the alignment editor (useful when combining multiple animations into a single output).

In the editor, the **Combine All** button next to **Combine Selected** stitches every loaded animation into a single composite entry named "All Poses" — handy for verifying alignment across every imported FNF pose at once without having to multi-select them by hand.

### Example: V-Slice Engine JSON Structure

The official [Funkin' Crew engine](https://github.com/FunkinCrew/Funkin/) ("V-Slice") uses a different schema. Frame rate is per-animation (not global like Kade), and the spritesheet is referenced via `assetPath` instead of `image`/`asset`.

```json
{
    "version": "1.0.1",
    "name": "Boyfriend",
    "renderType": "sparrow",
    "assetPath": "characters/BOYFRIEND",
    "scale": 1.0,
    "isPixel": false,
    "flipX": true,
    "danceEvery": 1,
    "singTime": 8.0,
    "startingAnimation": "idle",
    "animations": [
        {
            "name": "idle",
            "prefix": "BF idle dance",
            "frameRate": 24,
            "looped": false,
            "flipX": false,
            "flipY": false,
            "offsets": [0, 0]
        },
        {
            "name": "singLEFT",
            "prefix": "BF NOTE LEFT",
            "frameRate": 24,
            "looped": false,
            "offsets": [12, -6],
            "frameIndices": [0, 1, 2, 3]
        }
    ]
}
```

Fields not used by this tool: `version`, `renderType`, `isPixel`, `danceEvery`, `singTime`, `startingAnimation`, `healthIcon`, `death`, `cameraOffsets`, and `animType`. Per-animation `offsets` are loaded as alignment overrides for use in the alignment editor. Per-animation `flipX` overrides the character-level `flipX` when present.

## Automatically loading FNF characters settings

1. **Select directory with spritesheets** or **Menubar: Select files**
2. **Menubar: Import** → **FNF: Import settings from character data files**
3. **Show user settings** to confirm settings or double click an animation entry in the listbox to preview the output.

## FNF Animation Naming Conventions

### Standard Animation Names

- `idle` - Default standing/dancing animation
- `singLEFT`, `singDOWN`, `singUP`, `singRIGHT` - Note singing poses
- `singLEFTmiss`, `singDOWNmiss`, etc. - Missing note reactions
- `hey` - Special cheer/wave animation
- `scared` - Fear reaction (for GF characters)

### Prefix Patterns

Common prefixes found in XML metadata:

- `BF idle dance` → `idle`
- `BF NOTE LEFT` → `singLEFT`
- `GF Dancing Beat` → `idle`
- `spooky dance idle` → `idle`

### Custom Naming

Use **Find/Replace Rules** to standardize naming:

- Find: `BF NOTE (LEFT|RIGHT|UP|DOWN)`
- Replace: `sing$1`
- Enable regex for pattern matching

## Known Bugs & Limitations

### Indices, Loop problems or missing animations:

In cases where character data files containing several animations using the same **.xml**/**.txt** animation names but with different indices defined, only recognizes whatever the first entry is.

As an example, let's say you're trying to export `GF_assets` from Psych Engine and you're importing the `gf.json` file to get automated settings.

The JSON file contains `danceLEFT` and `danceRIGHT` which uses `GF Idle Dance` from the **.xml** file. The tool will in this case only export `danceLeft`.

So you will need to manually remove the indices from that animation in the override settings window.

---

_For general usage instructions, see the [User Manual](user-manual.md). For technical issues, check the [FAQ](faq.md)._
