# Developer Guide

Technical reference for contributors building or extending TextureAtlas Toolbox.
This document covers architecture, real code patterns, and copy-pasteable examples
for parsers, exporters, packers, and animation formats.

> **Note:** This doc is kept in sync with the source. If something looks outdated,
> open an issue or PR.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Layout](#project-layout)
- [Architecture Overview](#architecture-overview)
- [Core Contracts](#core-contracts)
  - [BaseParser (extraction)](#baseparser-extraction)
  - [ParserRegistry](#parserregistry)
  - [BaseExporter (generation)](#baseexporter-generation)
  - [ExporterRegistry](#exporterregistry)
  - [BasePacker](#basepacker)
  - [PackerRegistry](#packerregistry)
  - [AnimationExporter](#animationexporter-extraction)
  - [SettingsManager](#settingsmanager)
  - [AppConfig](#appconfig)
- [Extension Guides](#extension-guides)
- [Debug and Testing](#debug-and-testing)
- [Contribution Checklist](#contribution-checklist)

---

## Prerequisites

| Requirement           | Notes                                                              |
|-----------------------|--------------------------------------------------------------------|
| Python 3.14+          | Required; earlier versions may work but are unsupported.           |
| Git                   | For version control.                                               |
| Pillow                | Core image handling; installed via requirements.                   |
| Wand + ImageMagick    | GIF export with advanced features (quantization, duplicate removal).|
| PySide6               | Qt 6 bindings for GUI; runtime included.                           |
| etcpak                | GPU texture compression (BC1/BC3/ETC); installed via requirements. |

### Local setup

```bash
git clone https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames.git
cd TextureAtlas-to-GIF-and-Frames

python -m venv .venv
# Windows (bash): source .venv/Scripts/activate
# macOS/Linux:    source .venv/bin/activate

pip install -r setup/requirements.txt
# Optional bleeding-edge stack:
# pip install -r setup/requirements-experimental.txt
```

Run the test suite:

```bash
pytest tests/
```

We don't enforce linting globally yet, but prefer `black` and `ruff` locally.

---

## Project Layout

```
src/
├── Main.py                 # Application entry point and GUI wiring
├── version.py              # APP_VERSION constant
├── core/
│   ├── extractor/          # Extraction pipeline classes
│   │   ├── extractor.py           # Multi-threaded batch orchestrator
│   │   ├── atlas_processor.py     # Atlas image loading
│   │   ├── sprite_processor.py    # Sprite grouping
│   │   ├── animation_processor.py # Animation dispatch
│   │   ├── animation_exporter.py  # GIF/WebP/APNG export
│   │   ├── frame_pipeline.py      # Frame normalization & selection
│   │   ├── frame_selector.py      # Duplicate detection
│   │   ├── frame_exporter.py      # Static frame export
│   │   ├── preview_generator.py   # Animation preview helper
│   │   └── image_utils.py         # Low-level NumPy/Pillow helpers
│   ├── generator/
│   │   └── atlas_generator.py     # Full generation pipeline
│   ├── optimizer/          # Image optimization and GPU compression
│   │   ├── constants.py           # Enums, labels, OptimizeOptions
│   │   ├── optimizer.py           # PNG optimization pipeline
│   │   └── texture_compress.py    # GPU texture compression engine
│   └── editor/             # Visual editor components
├── parsers/
│   ├── base_parser.py      # Abstract base parser
│   ├── parser_registry.py  # Auto-detection registry
│   ├── parser_types.py     # SpriteData, ParseResult, ParserError
│   └── *_parser.py         # Concrete format parsers
├── exporters/
│   ├── base_exporter.py    # Abstract base exporter
│   ├── exporter_registry.py# Format registry
│   ├── exporter_types.py   # ExportOptions, ExportResult, errors
│   └── *_exporter.py       # Concrete format exporters
├── packers/
│   ├── base_packer.py      # Abstract base packer
│   ├── packer_registry.py  # Algorithm registry
│   ├── packer_types.py     # FrameInput, PackedFrame, PackerOptions
│   ├── maxrects_packer.py  # MaxRects bin-packing
│   ├── guillotine_packer.py# Guillotine packing
│   ├── shelf_packer.py     # Shelf packing
│   └── skyline_packer.py   # Skyline packing
├── gui/                    # PySide6 widgets and windows
├── utils/
│   ├── app_config.py       # Persistent JSON config
│   ├── settings_manager.py # Hierarchical settings
│   ├── utilities.py        # General helpers
│   ├── resampling.py       # Resize filter utilities
│   └── FNF/                # Friday Night Funkin' engine support
└── translations/           # Localization files
```

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            GUI Layer (PySide6)                             │
│   Main.py  ·  extract_tab_widget  ·  generate_tab_widget  ·  editor_tab    │
│                              optimize_tab_widget                            │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
      ┌─────────────────────────┼─────────────────────────┐
      ▼                         ▼                         ▼
┌────────────────┐    ┌────────────────────┐    ┌────────────────────┐
│   Extraction   │    │     Generation     │    │       Editor       │
│    Pipeline    │    │      Pipeline      │    │     (optional)     │
└───────┬────────┘    └─────────┬──────────┘    └────────────────────┘
        │                       │
        ▼                       ▼
┌────────────────┐    ┌────────────────────┐
│    Parsers     │    │      Packers       │
│ (read metadata)│    │ (layout algorithm) │
└───────┬────────┘    └─────────┬──────────┘
        │                       │
        │                       ▼
        │             ┌────────────────────┐
        │             │     Exporters      │
        │             │ (write metadata)   │
        │             └─────────┬──────────┘
        │                       │
        │                       ▼
        │             ┌────────────────────┐
        │             │  TextureCompressor │
        │             │ (GPU compression)  │
        │             └────────────────────┘
        ▼
┌────────────────┐
│AnimationExporter│
│ (GIF/WebP/APNG) │
└────────────────┘
```

**Extraction** reads an existing atlas image + metadata file, groups frames
into animations, and writes GIF/WebP/APNG (and optionally static frames).

**Generation** takes individual images, packs them using a bin-packing
algorithm, composites an atlas image, and writes metadata in any supported
format.

Keep these pipelines separate: parsers are input-only; exporters are output-only.

---

## Core Contracts

### BaseParser (extraction)

**Location:** `src/parsers/base_parser.py`

All extraction-side parsers inherit from `BaseParser`. The base class handles
file loading boilerplate and delegates format-specific logic to subclasses.

**Contract:**

| Member                  | Description                                                                  |
|-------------------------|------------------------------------------------------------------------------|
| `FILE_EXTENSIONS`       | Tuple of supported extensions, e.g. `(".json",)`.                            |
| `extract_names()`       | Return `Set[str]` of animation/sprite names for UI population.               |
| `parse_file(cls, path)` | Class method returning `ParseResult` with sprites, warnings, errors.         |
| `can_parse(cls, path)`  | Optional override for content-based detection beyond extension.              |

**SpriteData dict (canonical format):**

```python
{
    "name": str,        # Required: sprite/frame identifier
    "x": int,           # Required: X position in atlas
    "y": int,           # Required: Y position in atlas
    "width": int,       # Required: sprite width
    "height": int,      # Required: sprite height
    "frameX": int,      # Optional: offset for trimmed sprites (default 0)
    "frameY": int,      # Optional: offset for trimmed sprites (default 0)
    "frameWidth": int,  # Optional: original width before trim (default = width)
    "frameHeight": int, # Optional: original height before trim (default = height)
    "rotated": bool,    # Optional: 90° clockwise rotation (default False)
}
```

**Minimal parser example:**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser for a custom JSON spritesheet format."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Set

from parsers.base_parser import BaseParser
from parsers.parser_registry import ParserRegistry
from parsers.parser_types import ParseResult
from utils.utilities import Utilities


@ParserRegistry.register
class MyFormatParser(BaseParser):
    """Parse my custom JSON spritesheet format."""

    FILE_EXTENSIONS = (".myjson",)

    def extract_names(self) -> Set[str]:
        """Extract unique animation base names (for UI lists)."""
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            Utilities.strip_trailing_digits(frame.get("name", ""))
            for frame in data.get("frames", [])
            if frame.get("name")
        }

    @classmethod
    def parse_file(cls, file_path: str) -> ParseResult:
        """Parse file and return sprites with error handling."""
        raw_sprites = cls.parse_json_data(file_path)
        return cls.validate_sprites(raw_sprites, file_path)

    @staticmethod
    def parse_json_data(file_path: str) -> List[Dict[str, Any]]:
        """Load JSON and convert to canonical sprite dicts."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sprites = []
        for frame in data.get("frames", []):
            sprites.append({
                "name": frame["name"],
                "x": int(frame["x"]),
                "y": int(frame["y"]),
                "width": int(frame["w"]),
                "height": int(frame["h"]),
                "frameX": int(frame.get("fx", 0)),
                "frameY": int(frame.get("fy", 0)),
                "frameWidth": int(frame.get("fw", frame["w"])),
                "frameHeight": int(frame.get("fh", frame["h"])),
                "rotated": bool(frame.get("rotated", False)),
            })
        return sprites
```

The `@ParserRegistry.register` decorator automatically adds the parser to the
registry. Auto-detection in `ParserRegistry.detect_parser()` uses extension
matching and content sniffing for ambiguous formats like `.json` and `.xml`.

---

### ParserRegistry

**Location:** `src/parsers/parser_registry.py`

Central hub for parser discovery and auto-detection.

| Method                          | Description                                                 |
|---------------------------------|-------------------------------------------------------------|
| `@register`                     | Decorator to register a parser class.                       |
| `detect_parser(file_path)`      | Return the best parser for a file (extension + content).    |
| `parse_file(file_path)`         | Detect parser and parse in one call; returns `ParseResult`. |
| `get_parsers_for_extension(ext)`| List all parsers handling a given extension.                |

**Auto-detection for `.json` files:**

The registry inspects JSON structure to distinguish Aseprite, JSON-Hash,
JSON-Array, Phaser3, Egret2D, Godot Atlas, and Adobe Animate spritemap formats.

---

### BaseExporter (generation)

**Location:** `src/exporters/base_exporter.py`

All generator-side exporters inherit from `BaseExporter`. The base class
provides packing (basic shelf algorithm), atlas compositing, and file writing.
Subclasses only need to implement metadata serialization.

**Contract:**

| Member                           | Description                                                        |
|----------------------------------|--------------------------------------------------------------------|
| `FILE_EXTENSION`                 | Output extension, e.g. `".json"`.                                  |
| `FORMAT_NAME`                    | Display name, e.g. `"json-hash"`.                                  |
| `build_metadata(...)`            | Return metadata as `str` or `bytes`.                               |
| `export_file(sprites, images, path)` | Main entry point; returns `ExportResult`.                      |

**Minimal exporter example:**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exporter for a custom atlas metadata format."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import ExportOptions, GeneratorMetadata, PackedSprite


@ExporterRegistry.register
class MyFormatExporter(BaseExporter):
    """Export sprites to my custom metadata format."""

    FILE_EXTENSION = ".myfmt"
    FORMAT_NAME = "my-format"

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> Union[str, bytes]:
        frames: Dict[str, Any] = {}
        for packed in packed_sprites:
            frames[packed.name] = {
                "x": packed.atlas_x,
                "y": packed.atlas_y,
                "w": packed.sprite["width"],
                "h": packed.sprite["height"],
                "rotated": packed.rotated,
            }
        output = {
            "image": image_name,
            "size": {"w": atlas_width, "h": atlas_height},
            "frames": frames,
        }
        indent = 4 if self.options.pretty_print else None
        return json.dumps(output, indent=indent, ensure_ascii=False)
```

After creating a new exporter, import it in `ExporterRegistry.initialize()` so
registration runs at startup.

---

### ExporterRegistry

**Location:** `src/exporters/exporter_registry.py`

| Method                            | Description                                              |
|-----------------------------------|----------------------------------------------------------|
| `@register`                       | Decorator to register an exporter class.                 |
| `get_exporter(format_name)`       | Lookup by `FORMAT_NAME` or extension.                    |
| `export_file(..., format_name)`   | One-call export using the matched exporter.              |
| `get_all_formats()`               | List registered format names.                            |
| `initialize()`                    | Import all exporter modules; call once at startup.       |

---

### BasePacker

**Location:** `src/packers/base_packer.py`

All packing algorithms inherit from `BasePacker`. The base class handles
preprocessing (sorting, validation), atlas sizing, and result building.
Subclasses implement the core layout logic.

**Contract:**

| Member                         | Description                                                    |
|--------------------------------|----------------------------------------------------------------|
| `ALGORITHM_NAME`               | Unique key, e.g. `"maxrects"`.                                 |
| `DISPLAY_NAME`                 | Human-readable name for UI.                                    |
| `SUPPORTED_HEURISTICS`         | List of `(key, display_name)` tuples.                          |
| `_pack_internal(frames, w, h)` | Core algorithm; return `List[PackedFrame]`.                    |
| `pack(frames)`                 | Entry point; handles expansion and returns `PackerResult`.     |

**Available packers:**

| Algorithm    | Heuristics                                    |
|--------------|-----------------------------------------------|
| `maxrects`   | BSSF, BLSF, BAF, BL, CP                       |
| `guillotine` | BSSF/BLSF/BAF/WAF × split strategies          |
| `shelf`      | NEXT_FIT, FIRST_FIT, BEST_WIDTH/HEIGHT_FIT    |
| `skyline`    | BOTTOM_LEFT, MIN_WASTE, BEST_FIT              |

**PackerOptions** controls padding, max size, power-of-two, rotation, etc.

---

### PackerRegistry

**Location:** `src/packers/packer_registry.py`

| Method                      | Description                                               |
|-----------------------------|-----------------------------------------------------------|
| `@register`                 | Decorator to register a packer class.                     |
| `get_packer(algorithm)`     | Return instantiated packer.                               |
| `pack(algorithm, frames)`   | Convenience wrapper.                                      |
| `get_all_algorithms()`      | List registered algorithm names.                          |

---

### AnimationExporter (extraction)

**Location:** `src/core/extractor/animation_exporter.py`

Handles GIF, WebP, and APNG export from extracted frame sequences.

**Key methods:**

| Method              | Description                                                  |
|---------------------|--------------------------------------------------------------|
| `save_animations()` | Dispatcher based on `settings["animation_format"]`.          |
| `save_gif()`        | Uses Wand/ImageMagick for quantization and duplicate removal.|
| `save_webp()`       | Pillow lossless animated WebP.                               |
| `save_apng()`       | Pillow APNG with metadata.                                   |

**Helper utilities in `frame_pipeline.py`:**

- `prepare_scaled_sequence()` – scale and crop frames.
- `build_frame_durations()` – compute per-frame timing from fps/delay/period.
- `compute_shared_bbox()` – union bounding box for cropping.

**Adding a new animation format:**

1. Add a branch in `save_animations()` and implement `save_<format>()`.
2. Update UI combo boxes in `extract_tab_widget.py` and `animation_format_map`
   in `Main.py`.
3. Map the format to a file extension in
   `preview_generator.py::_preview_extension_for_format`.

Example skeleton:

```python
def save_myformat(self, images, filename, fps, delay, period, scale, settings):
    final_images = prepare_scaled_sequence(
        images, self.scale_image, scale, settings.get("crop_option")
    )
    if not final_images:
        return

    durations = build_frame_durations(
        len(final_images), fps, delay, period, settings.get("var_delay", False)
    )
    if not durations:
        return

    out_path = os.path.join(self.output_dir, f"{filename}.myfmt")
    # Encode final_images with durations using your library
    print(f"Saved MyFormat animation: {out_path}")
```

---

### SettingsManager

**Location:** `src/utils/settings_manager.py`

Three-tier hierarchy: global → spritesheet → animation. When retrieving
settings, values merge with later tiers taking precedence.

| Method                                    | Description                                |
|-------------------------------------------|--------------------------------------------|
| `set_global_settings(**kwargs)`           | Update global defaults.                    |
| `set_spritesheet_settings(name, **kw)`    | Override for a specific spritesheet.       |
| `set_animation_settings(name, **kw)`      | Override for a specific animation.         |
| `get_settings(filename, animation_name)`  | Return merged dict with all overrides.     |

---

### AppConfig

**Location:** `src/utils/app_config.py`

Persistent JSON-backed configuration. Settings are validated against
`TYPE_MAP` on load/save.

| Attribute     | Description                                                       |
|---------------|-------------------------------------------------------------------|
| `DEFAULTS`    | Nested dict of default values.                                    |
| `TYPE_MAP`    | Flat dict mapping setting keys to Python types.                   |

To add a new persistent setting:

1. Add default value to `DEFAULTS` (usually under `extraction_defaults`).
2. Add type to `TYPE_MAP`, e.g. `"my_flag": bool`.
3. Access via `app_config.get("extraction_defaults")["my_flag"]`.

---

## Extension Guides

### Add a new parser (extraction)

1. Create a file in `src/parsers/`, e.g. `my_format_parser.py`.
2. Subclass `BaseParser`, define `FILE_EXTENSIONS`, implement `extract_names()`.
3. Implement `parse_file()` (or a legacy `parse_<type>_data()` static method).
4. Decorate with `@ParserRegistry.register`.
5. If the extension is ambiguous (e.g. `.json`), add content-detection logic in
   `ParserRegistry._detect_json_parser()`.

### Add a new generator exporter

1. Create a file in `src/exporters/`, e.g. `my_format_exporter.py`.
2. Subclass `BaseExporter`, define `FILE_EXTENSION` and `FORMAT_NAME`.
3. Implement `build_metadata()`.
4. Decorate with `@ExporterRegistry.register`.
5. Import your module in `ExporterRegistry.initialize()`.
6. If the UI lists formats explicitly (e.g. combo boxes), add the display name.

### Add a new packer algorithm

1. Create a file in `src/packers/`, e.g. `my_packer.py`.
2. Subclass `BasePacker`, define `ALGORITHM_NAME`, `DISPLAY_NAME`,
   optionally `SUPPORTED_HEURISTICS`.
3. Implement `_pack_internal(frames, width, height)` returning `List[PackedFrame]`.
4. Decorate with `@PackerRegistry.register` (via `register_packer` convenience).
5. Import in `packers/__init__.py` if needed.

### Add a new animation format (extraction)

1. Add a branch in `AnimationExporter.save_animations()`.
2. Implement `save_<format>()` following the existing patterns.
3. Update `animation_format_combobox.addItems` in `extract_tab_widget.py`.
4. Extend `animation_format_map` in `Main.py`.
5. Map the format extension in `preview_generator.py`.

### Add support for a new FNF engine

1. Extend `utils/FNF/engine_detector.py` with `_is_<engine>()`.
2. Add a branch in `CharacterData._process_character_file()` to parse
   the format and call `_update_animation_settings()`.
3. Handle any offset or index quirks in `utils/FNF/alignment.py`.

### Add a new persistent setting

1. Add the default in `AppConfig.DEFAULTS` (typically under
   `extraction_defaults` or a new section).
2. Add the type to `AppConfig.TYPE_MAP`, e.g. `"my_flag": bool`.
3. Access via `app_config.get_extraction_defaults()["my_flag"]`.

---

---

## Contribution Checklist

- [ ] Follow naming conventions: `snake_case` functions, `PascalCase` classes,
      `UPPER_SNAKE_CASE` constants.
- [ ] Add docstrings to public classes and methods.
- [ ] Update docs when adding formats or settings.
- [ ] Don't touch `latestVersion.txt` (triggers premature update prompts).

---

*For usage instructions, see the [User Manual](user-manual.md).  
For installation help, see the [Installation Guide](installation-guide.md).  
For an AI-generated overview, see [DeepWiki](https://deepwiki.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames).*

---

*Last updated: December 6, 2025 — TextureAtlas Toolbox v2.0.0*