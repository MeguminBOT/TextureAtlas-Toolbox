# API Reference

General but comprehensive technical reference for the TextureAtlas Toolbox codebase. This document is
intended for any users or developers who want to:

- **Understand how the app works** — Explore the back-end architecture.

-  **Extend or implement new features** — Build custom parsers, packers, exporters, or UI
   components. See [developer-docs.md](developer-docs.md) for contribution guidelines and
   detailed implementation patterns.

-  **Script and automate** — Use the extraction, generation, or editor pipelines programmatically
   without the GUI.

-  **Integrate functionality into other applications** — Embed TextureAtlas Toolbox capabilities
   (parsing, packing, exporting) into your own tools or build companion utilities that work
   alongside this codebase.

---

# Table of Contents

- Extractor Tool
  - [Extraction Pipeline](#extraction-pipeline)
    - [Extractor](#extractor)
    - [AtlasProcessor](#atlasprocessor)
    - [SpriteProcessor](#spriteprocessor)
    - [AnimationProcessor](#animationprocessor)
    - [FramePipeline](#framepipeline)
    - [FrameSelector](#frameselector)
    - [FrameExporter](#frameexporter)
    - [AnimationExporter](#animationexporter)
  - [Parsers](#parsers)
    - [ParserRegistry](#parserregistry)
    - [BaseParser](#baseparser)
    - [Parser Types](#parser-types)
    - [Supported Formats](#supported-formats)
    - [ParserErrorCode](#parsererrorcode)
    - [ParserError](#parsererror)
    - [ParseResult](#parseresult)
    - [ParserWarning](#parserwarning)
  - [Spritemap Module](#spritemap-module)
    - [AdobeSpritemapRenderer](#adobespritemaprenderer)
    - [SpriteAtlas](#spriteatlas)
  - [Unknown Spritesheet Handling](#unknown-spritesheet-handling)
    - [UnknownParser](#unknownparser)
    - [UnknownSpritesheetHandler](#unknownspritesheethandler)
  - [Extraction Utilities](#extraction-utilities)
    - [SettingsManager](#settingsmanager)
    - [Image Utilities](#image-utilities)
    - [Frame Duration Utilities](#frame-duration-utilities)
  - [UI Bindings](#ui-bindings)
    - [Signal-Based Progress Reporting](#signal-based-progress-reporting)
    - [Integrating with Custom UI Frameworks](#integrating-with-custom-ui-frameworks)
- Generator Tool
  - [Generation Pipeline](#generation-pipeline)
    - [AtlasGenerator](#atlasgenerator)
    - [GeneratorOptions](#generatoroptions)
    - [GeneratorResult](#generatorresult)
  - [GPU Texture Compression](#gpu-texture-compression)
    - [TextureFormat Enum](#textureformat-enum)
    - [TextureContainer Enum](#texturecontainer-enum)
    - [TextureCompressor Methods](#texturecompressor-methods)
  - [Packers](#packers)
    - [PackerRegistry](#packerregistry)
    - [BasePacker](#basepacker)
    - [Packer Types](#packer-types)
    - [Available Algorithms](#available-algorithms)
    - [PackerErrorCode](#packererrorcode)
    - [PackerError](#packererror)
    - [PackerResult](#packerresult)
    - [PackerWarning](#packerwarning)
  - [Exporters](#exporters)
    - [ExporterRegistry](#exporterregistry)
    - [BaseExporter](#baseexporter)
    - [Exporter Types](#exporter-types)
    - [Supported Export Formats](#supported-export-formats)
    - [ExporterErrorCode](#exportererrorcode)
    - [ExporterError](#exportererror)
    - [ExportResult](#exportresult)
    - [ExporterWarning](#exporterwarning)
- Editor Tool
  - [Editor Composite](#editor-composite)
    - [build_editor_composite_frames](#build_editor_composite_frames)
    - [clone_animation_map](#clone_animation_map)
    - [Type Aliases](#type-aliases)
- General
  - [Utility Classes](#utility-classes)
    - [Utilities](#utilities)
  - [Application Configuration](#application-configuration)
    - [AppConfig](#appconfig)
  - [Version & Updates](#version--updates)
    - [Version Constants](#version-constants)
    - [UpdateChecker](#updatechecker)
  - [Resampling](#resampling)
    - [ResamplingMethod](#resamplingmethod)
  - [Error Handling](#error-handling)
    - [ExceptionHandler](#exceptionhandler)
    - [Common Exception Types](#common-exception-types)
- QT-Dependent (PySide6)
  - [Localization](#localization)
    - [TranslationManager](#translationmanager)
    - [tr (Translator)](#tr-translator)

---

# Extraction Pipeline

The extraction pipeline converts texture atlases into individual frames and animations. The main
entry point is `Extractor`, which coordinates multiple worker threads to process batches of
spritesheets in parallel.

## Extractor

Orchestrates parallel spritesheet parsing and animation export. Manages worker threads, dispatches
files from a queue, aggregates statistics, and supports pause/cancel semantics.

```python
from core.extractor.extractor import Extractor

extractor = Extractor(
    progress_callback,      # Callable[[int, int, str], None]
    current_version,        # str - version string for metadata
    settings_manager,       # SettingsManager instance
    app_config=None,        # Optional AppConfig for resource limits
    statistics_callback=None,
    cancel_event=None,
    error_prompt_callback=None,
)
```

### Key Methods

| Method | Description |
|--------|-------------|
| `process_directory(input_dir, output_dir, ...)` | Process a batch of spritesheets using a worker pool. |
| `cancel()` | Signal cancellation to all workers. |
| `pause()` / `resume()` | Pause or resume processing. |

#### Callbacks

- **progress_callback**: Receives `(current_file_index, total_files, status_message)`.
- **statistics_callback**: Receives `(frames_generated, anims_generated, sprites_failed)`.
- **error_prompt_callback**: Receives `(error_message, exception)`, returns `True` to continue.

---
<br>

## AtlasProcessor

Loads a texture atlas image and parses its metadata. Uses the unified `ParserRegistry` for format
detection, falling back to `UnknownParser` for images without metadata.

```python
from core.extractor.atlas_processor import AtlasProcessor

processor = AtlasProcessor(
    atlas_path,             # str - path to atlas image
    metadata_path,          # Optional[str] - path to metadata file
    parent_window=None,     # Optional widget for dialogs
)
atlas_image = processor.atlas       # PIL.Image or None
sprites = processor.sprites         # List[dict] - sprite metadata
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `atlas` | `PIL.Image` | Loaded atlas image, or `None` on error. |
| `sprites` | `List[dict]` | Parsed sprite metadata dicts. |
| `parse_result` | `ParseResult` | Full parse result with warnings/errors. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `open_atlas_and_parse_metadata()` | `(Image, List[dict])` | Load atlas and parse metadata. |
| `has_parse_errors()` | `bool` | Check if parsing produced errors. |

---
<br>

## SpriteProcessor

Extracts individual sprites from an atlas image and groups them into animation sequences.

```python
from core.extractor.sprite_processor import SpriteProcessor

processor = SpriteProcessor(atlas_image, sprites_list)
animations = processor.process_sprites()
# animations: Dict[str, List[Tuple[str, np.ndarray, dict]]]
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `process_sprites()` | `Dict[str, List[FrameTuple]]` | Group all sprites into animations. |
| `process_specific_animation(name)` | `Dict[str, List[FrameTuple]]` | Extract a single animation by name. |

**FrameTuple**: `Tuple[name: str, image: np.ndarray, metadata: dict]`

---
<br>

## AnimationProcessor

Coordinates frame and animation export. Applies alignment overrides, injects editor-defined
composite animations, and delegates to `FrameExporter` and `AnimationExporter`.

```python
from core.extractor.animation_processor import AnimationProcessor

processor = AnimationProcessor(
    animations,             # Dict[str, List[FrameTuple]]
    atlas_path,             # str
    output_dir,             # str
    settings_manager,       # SettingsManager
    current_version,        # str
    spritesheet_label=None, # Optional display name
)
frames, anims = processor.process_animations()
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `process_animations(is_unknown=False)` | `(int, int)` | Export all animations; returns counts. |
| `scale_image(image, factor)` | `PIL.Image` | Scale image (negative flips horizontally). |

---
<br>

## FramePipeline

Normalizes input frames (sorting, RGBA conversion) and builds export-ready context objects.

```python
from core.extractor.frame_pipeline import FramePipeline, AnimationContext

pipeline = FramePipeline()
context = pipeline.build_context(
    spritesheet_name,
    animation_name,
    image_tuples,
    settings,
)
```

### AnimationContext (dataclass)

Immutable container describing a prepared set of frames for export.

| Attribute | Type | Description |
|-----------|------|-------------|
| `spritesheet_name` | `str` | Source spritesheet identifier. |
| `animation_name` | `str` | Animation sequence name. |
| `settings` | `dict` | Export settings. |
| `frames` | `List[FrameTuple]` | Normalized frame tuples. |
| `kept_indices` | `List[int]` | Indices of frames to export. |
| `single_frame` | `bool` | `True` if all frames are identical. |

| Method | Description |
|--------|-------------|
| `with_frames(frames)` | Return copy with replaced frame list. |
| `iter_selected_frames()` | Yield frames at `kept_indices`. |
| `selected_frames` | Property returning list of selected frames. |

---
<br>

## FrameSelector

Static utilities for selecting which frames to export based on selection strategies.

```python
from core.extractor.frame_selector import FrameSelector

is_single = FrameSelector.is_single_frame(image_tuples)
kept = FrameSelector.get_kept_frames(settings, is_single, image_tuples)
indices = FrameSelector.get_kept_frame_indices(kept, image_tuples)
```

### Selection Strategies

| Value | Behavior |
|-------|----------|
| `"all"` | Keep every frame. |
| `"first"` | Keep only the first frame. |
| `"last"` | Keep only the last frame. |
| `"first_last"` | Keep first and last frames. |
| `"no_duplicates"` | Remove visually identical consecutive frames. |
| `"0,2,4"` / `"0-5"` | Explicit indices or ranges. |

---
<br>

## FrameExporter

Exports individual animation frames as image files (PNG, WebP, AVIF, etc.).

```python
from core.extractor.frame_exporter import FrameExporter

exporter = FrameExporter(output_dir, current_version, scale_image_func)
count = exporter.save_frames(
    image_tuples,
    kept_frame_indices,
    spritesheet_name,
    animation_name,
    scale,
    settings,
)
```

### Supported Frame Formats

`PNG`, `WebP`, `AVIF`, `BMP`, `DDS`, `TGA`, `TIFF`

---
<br>

## AnimationExporter

Exports frame sequences to animated image formats (GIF, WebP, APNG).

```python
from core.extractor.animation_exporter import AnimationExporter

exporter = AnimationExporter(output_dir, current_version, scale_image_func)
count = exporter.save_animations(image_tuples, spritesheet_name, animation_name, settings)
```

### Key Methods

| Method | Description |
|--------|-------------|
| `save_animations(...)` | Dispatch to format-specific exporter. |
| `save_gif(images, filename, fps, ...)` | Export optimized GIF. |
| `save_webp(images, filename, fps, ...)` | Export lossless animated WebP. |
| `save_apng(images, filename, fps, ...)` | Export animated PNG. |
| `remove_dups(animation)` | Merge duplicate frames in a Wand animation. |

---
<br>
<br>


# Parsers

The parser system provides unified metadata parsing across multiple spritesheet formats.

## ParserRegistry

Central registry for all available parsers. Provides format auto-detection and a single entry
point for parsing any supported format.

```python
from parsers.parser_registry import ParserRegistry

# Initialize (called automatically on first use)
ParserRegistry.initialize()

# Parse a file with auto-detection
result = ParserRegistry.parse_file("/path/to/atlas.json")
if result.is_valid:
    for sprite in result.sprites:
        process(sprite)
```

### Class Methods

| Method | Description |
|--------|-------------|
| `register(parser_cls)` | Register a parser class (can be used as decorator). |
| `get_parsers_for_extension(ext)` | Get parsers supporting an extension. |
| `detect_parser(file_path)` | Auto-detect best parser for a file. |
| `parse_file(file_path)` | Parse a file and return `ParseResult`. |

---
<br>

## BaseParser

Abstract base class all parsers must inherit from.

```python
from parsers.base_parser import BaseParser

class MyParser(BaseParser):
    FILE_EXTENSIONS = (".myext",)

    def extract_names(self) -> Set[str]:
        # Return animation/sprite names for UI
        ...

    @classmethod
    def parse_file(cls, file_path: str) -> ParseResult:
        # Parse and return structured result
        ...
```

---
<br>

## Parser Types

Core types defined in `parsers.parser_types`:

| Type | Description |
|------|-------------|
| `SpriteData` | TypedDict with canonical sprite structure. |
| `ParseResult` | Dataclass holding sprites, warnings, errors. |
| `ParserError` | Base exception for parser failures. |
| `ParserErrorCode` | Enum of error categories. |

#### SpriteData Keys

| Key | Required | Description |
|-----|----------|-------------|
| `name` | ✓ | Sprite identifier. |
| `x`, `y` | ✓ | Position in atlas (pixels). |
| `width`, `height` | ✓ | Sprite dimensions (pixels). |
| `frameX`, `frameY` | | Offset for trimmed sprites. |
| `frameWidth`, `frameHeight` | | Original dimensions before trim. |
| `rotated` | | `True` if rotated 90° in atlas. |

---
<br>

## Supported Formats

| Format | Parser | Extension(s) |
|--------|--------|--------------|
| Starling/Sparrow XML | `StarlingXmlParser` | `.xml` |
| TexturePacker JSON (Hash) | `JsonHashParser` | `.json` |
| TexturePacker JSON (Array) | `JsonArrayParser` | `.json` |
| Aseprite | `AsepriteParser` | `.json` |
| Spine | `SpineParser` | `.atlas` |
| Phaser 3 | `Phaser3Parser` | `.json` |
| Godot | `GodotAtlasParser` | `.tpsheet` |
| Unity | `TexturePackerUnityParser` | `.tpsheet` |
| CSS Spritesheet | `CssSpritesheetParser` | `.css` |
| Plist (Cocos2d) | `PlistXmlParser` | `.plist` |
| Adobe Animate Spritemap | `SpritemapParser` | `.json` |
| Plain text | `TxtParser` | `.txt` |

---
<br>

## ParserErrorCode

Enum categorizing all possible parser failure types for programmatic handling.

```python
from parsers.parser_types import ParserErrorCode

if error.code == ParserErrorCode.FILE_NOT_FOUND:
    # Handle missing file
    ...
elif error.code in (ParserErrorCode.INVALID_FORMAT, ParserErrorCode.MALFORMED_STRUCTURE):
    # Handle format issues
    ...
```

### Error Code Categories

| Category | Codes | Description |
|----------|-------|-------------|
| **File-level** | `FILE_NOT_FOUND`, `FILE_READ_ERROR`, `FILE_ENCODING_ERROR` | Problems accessing or reading the file. |
| **Format-level** | `INVALID_FORMAT`, `UNSUPPORTED_FORMAT`, `MALFORMED_STRUCTURE` | Structural issues with file format. |
| **Content-level** | `MISSING_REQUIRED_KEY`, `INVALID_VALUE_TYPE`, `INVALID_COORDINATE`, `NEGATIVE_DIMENSION`, `ZERO_DIMENSION` | Invalid data within the file. |
| **Sprite-level** | `SPRITE_PARSE_FAILED`, `SPRITE_OUT_OF_BOUNDS`, `DUPLICATE_SPRITE_NAME` | Issues with individual sprites. |
| **Metadata** | `MISSING_FRAMES_KEY`, `MISSING_TEXTURES_KEY`, `EMPTY_SPRITE_LIST` | Missing required metadata sections. |
| **Fallback** | `UNKNOWN_ERROR` | Catch-all for unexpected errors. |

---
<br>

## ParserError

Base exception class for all parser errors with structured error information.

```python
from parsers.parser_types import ParserError, ParserErrorCode

try:
    result = parser.parse_file(path)
except ParserError as e:
    print(f"Error code: {e.code}")
    print(f"Message: {e.message}")
    print(f"File: {e.file_path}")
    print(f"Details: {e.details}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `ParserErrorCode` | Categorized error code for programmatic handling. |
| `message` | `str` | Human-readable error description. |
| `file_path` | `str \| None` | Path to the file that caused the error. |
| `details` | `dict` | Additional context (line number, key name, etc.). |

### Subclasses

| Class | Use Case |
|-------|----------|
| `FileError` | Error reading or accessing a file. |
| `FormatError` | Error in file structure or format. |
| `ContentError` | Error in file content (missing keys, invalid values). |
| `SpriteError` | Error parsing a specific sprite entry (includes `sprite_name` attribute). |

---
<br>

## ParseResult

Dataclass container for parser output with full diagnostics including sprites, warnings, and errors.

```python
from parsers.parser_types import ParseResult

result = parser.parse_file("/path/to/atlas.json")

if result.is_valid:
    print(f"Parsed {result.sprite_count} sprites")
    for sprite in result.sprites:
        process(sprite)

if result.warnings:
    print(f"{result.warning_count} warnings:")
    for warning in result.warnings:
        print(f"  - {warning.message}")

if result.errors:
    print(f"{result.error_count} errors:")
    for error in result.errors:
        print(f"  - [{error.sprite_name}] {error.message}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `sprites` | `List[SpriteData]` | Successfully parsed sprite dicts. |
| `warnings` | `List[ParserWarning]` | Non-fatal issues encountered during parsing. |
| `errors` | `List[SpriteError]` | Fatal errors for specific sprites. |
| `file_path` | `str \| None` | Path to the parsed file. |
| `parser_name` | `str \| None` | Name of the parser class used. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_valid` | `bool` | `True` if at least one sprite was successfully parsed. |
| `sprite_count` | `int` | Count of successfully parsed sprites. |
| `warning_count` | `int` | Count of warnings. |
| `error_count` | `int` | Count of sprite-level errors. |

### Methods

| Method | Description |
|--------|-------------|
| `add_warning(code, message, sprite_name, details)` | Add a warning to the result. |
| `add_error(code, message, sprite_name, details)` | Add a sprite-level error to the result. |
| `get_summary()` | Return a human-readable summary of the parse result. |

---
<br>

## ParserWarning

Dataclass for non-fatal issues detected during parsing.

```python
from parsers.parser_types import ParserWarning, ParserErrorCode

warning = ParserWarning(
    code=ParserErrorCode.DUPLICATE_SPRITE_NAME,
    message="Duplicate sprite 'frame_01' found, using last occurrence",
    sprite_name="frame_01",
)
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `ParserErrorCode` | Categorized warning code. |
| `message` | `str` | Human-readable description. |
| `sprite_name` | `str \| None` | Name of affected sprite, if applicable. |
| `details` | `dict \| None` | Additional context. |

<br>
<br>

---

# Spritemap Module

Handles Adobe Animate spritemap exports (`Animation.json` + atlas image).

## AdobeSpritemapRenderer

High-level renderer for extracting symbol animations from Adobe Animate exports.

```python
from core.extractor.spritemap import AdobeSpritemapRenderer

renderer = AdobeSpritemapRenderer(
    animation_path,         # Path to Animation.json
    spritemap_json_path,    # Path to spritemap JSON
    atlas_image_path,       # Path to atlas PNG
)
symbols = renderer.list_symbol_names()
frames = renderer.render_symbol(symbol_name)  # List of PIL Images
```

### Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `list_symbol_names()` | `List[str]` | All symbols in the document. |
| `render_symbol(name)` | `List[Image]` | Render all frames of a symbol. |
| `get_symbol_frame_count(name)` | `int` | Number of frames in a symbol. |

---
<br>

## SpriteAtlas

Low-level sprite slicing and transformation for spritemap JSON.

```python
from core.extractor.spritemap.sprite_atlas import SpriteAtlas

atlas = SpriteAtlas(spritemap_json, atlas_image, canvas_size, resample)
image, offset = atlas.get_sprite(name, transform_matrix, color_effect)
```

<br>
<br>

---

# Unknown Spritesheet Handling

For images without metadata, the toolbox uses computer vision to detect sprite regions.

## UnknownParser

Fallback parser using flood-fill algorithms to detect sprite boundaries.

```python
from parsers.unknown_parser import UnknownParser

image, sprites = UnknownParser.parse_unknown_image(file_path, parent_window)
# sprites: List[dict] with detected regions
```

---
<br>

## UnknownSpritesheetHandler

Orchestrates background color detection and user prompts for unknown spritesheets.

```python
from core.extractor.unknown_spritesheet_handler import UnknownSpritesheetHandler

handler = UnknownSpritesheetHandler(logger=print)
cancelled = handler.handle_background_detection(input_dir, spritesheet_list, parent)
```

<br>
<br>

---

# Extraction Utilities

## SettingsManager

Manages layered settings with a three-tier hierarchy: global defaults → spritesheet overrides →
animation overrides. When retrieving settings, values merge with later tiers taking precedence.

```python
from utils.settings_manager import SettingsManager

manager = SettingsManager()

# Set global defaults
manager.set_global_settings(fps=24, scale=1.0, animation_format="GIF")

# Override for a specific spritesheet
manager.set_spritesheet_settings("player.png", fps=30, scale=2.0)

# Override for a specific animation
manager.set_animation_settings("player.png/idle", fps=12)

# Retrieve merged settings (global + spritesheet + animation)
settings = manager.get_settings("player.png", "player.png/idle")
# settings["fps"] == 12, settings["scale"] == 2.0, settings["animation_format"] == "GIF"
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `global_settings` | `dict` | Default settings applied to all exports. |
| `spritesheet_settings` | `dict` | Per-spritesheet overrides keyed by filename. |
| `animation_settings` | `dict` | Per-animation overrides keyed by animation name. |

### Methods

| Method | Description |
|--------|-------------|
| `set_global_settings(**kwargs)` | Update global defaults with key-value pairs. |
| `set_spritesheet_settings(name, **kwargs)` | Set overrides for a specific spritesheet. |
| `set_animation_settings(name, **kwargs)` | Set overrides for a specific animation. |
| `delete_spritesheet_settings(name)` | Remove stored settings for a spritesheet. |
| `delete_animation_settings(name)` | Remove stored settings for an animation. |
| `get_settings(filename, animation_name=None)` | Retrieve merged settings with all overrides applied. |

---
<br>

## Image Utilities

Helper functions in `core.extractor.image_utils`:

| Function | Description |
|----------|-------------|
| `scale_image(image, size, method)` | Scale with configurable resampling. |
| `pad_frames_to_canvas(images)` | Pad frames to common canvas size. |
| `ensure_rgba_array(source)` | Convert PIL Image or array to RGBA array. |
| `array_to_rgba_image(array)` | Convert RGBA array to PIL Image. |
| `frame_bbox(source)` | Get non-transparent bounding box. |
| `crop_to_bbox(array, bbox)` | Crop array to bounding box. |

---
<br>

## Frame Duration Utilities

Functions in `core.extractor.frame_pipeline`:

| Function | Description |
|----------|-------------|
| `build_frame_durations(count, fps, delay, period, var_delay)` | Compute per-frame durations in ms. |
| `compute_shared_bbox(images)` | Union bounding box across all frames. |
| `prepare_scaled_sequence(images, scale_func, scale, crop)` | Crop and scale a frame sequence. |

<br>
<br>

---

# UI Bindings

The extraction pipeline is designed for easy integration with any UI framework.

## Signal-Based Progress Reporting

The `Extractor` class accepts callbacks rather than binding directly to Qt signals, allowing
integration with any framework.

```python
def my_progress_handler(current: int, total: int, status: str):
    # Update your progress bar or status label
    ...

extractor = Extractor(
    progress_callback=my_progress_handler,
    ...
)
```

## Integrating with Custom UI Frameworks

1. **Create callback functions** matching the expected signatures.
2. **Pass callbacks** to `Extractor` on construction.
3. **Call `process_directory()`** from a background thread if needed.
4. **Use the cancel_event** (`threading.Event`) to signal abort.

```python
import threading

cancel_event = threading.Event()
extractor = Extractor(
    progress_callback=lambda c, t, s: update_ui(c, t, s),
    cancel_event=cancel_event,
    ...
)

# Run extraction in background
thread = threading.Thread(target=extractor.process_directory, args=(in_dir, out_dir))
thread.start()

# Cancel from UI
cancel_event.set()
```

<br>
<br>

---
---

# Generation Pipeline

The generation pipeline creates texture atlases from individual images. It combines the packer
system (for layout) with the exporter system (for output) into a unified workflow.

## AtlasGenerator

Main entry point for atlas generation. Orchestrates image loading, packing, compositing, and
metadata export.

```python
from core.generator.atlas_generator import AtlasGenerator, GeneratorOptions

generator = AtlasGenerator()
generator.set_progress_callback(lambda cur, total, msg: print(f"{cur}/{total}: {msg}"))

result = generator.generate(
    frames={"walk": ["walk_01.png", "walk_02.png"], "idle": ["idle_01.png"]},
    output_path="/path/to/atlas",
    options=GeneratorOptions(
        algorithm="maxrects",
        heuristic="bssf",
        export_format="json-hash",
        padding=2,
    ),
)

if result.success:
    print(f"Atlas: {result.atlas_path}")
    print(f"Metadata: {result.metadata_path}")
    print(f"Efficiency: {result.efficiency:.1%}")
```

### Methods

| Method | Description |
|--------|-------------|
| `generate(frames, output_path, options)` | Generate atlas from frame paths. Returns `GeneratorResult`. |
| `set_progress_callback(callback)` | Set callback for progress updates: `(current, total, message)`. |

---
<br>

## GeneratorOptions

Dataclass for configuring atlas generation.

```python
from core.generator.atlas_generator import GeneratorOptions

options = GeneratorOptions(
    algorithm="maxrects",           # Packing algorithm
    heuristic="bssf",               # Algorithm-specific heuristic
    max_width=4096,                 # Maximum atlas width
    max_height=4096,                # Maximum atlas height
    padding=2,                      # Pixels between sprites
    border_padding=0,               # Pixels around atlas edge
    power_of_two=False,             # Force power-of-2 dimensions
    force_square=False,             # Force square atlas
    allow_rotation=False,           # Allow 90° rotation
    trim_sprites=False,             # Trim transparent edges
    export_format="starling-xml",   # Metadata format
    image_format="png",             # Atlas image format
    texture_format=None,            # GPU compression format (TextureFormat enum or None)
    texture_container=None,         # Container format (TextureContainer enum or None)
    generate_mipmaps=False,         # Generate mipmap chain for GPU textures
)
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `algorithm` | `str` | `"maxrects"` | Packing algorithm name. |
| `heuristic` | `str \| None` | `None` | Algorithm-specific heuristic key. |
| `max_width` | `int` | `4096` | Maximum atlas width in pixels. |
| `max_height` | `int` | `4096` | Maximum atlas height in pixels. |
| `padding` | `int` | `2` | Pixels of padding between sprites. |
| `border_padding` | `int` | `0` | Pixels of padding around atlas edges. |
| `power_of_two` | `bool` | `False` | Force power-of-two dimensions. |
| `force_square` | `bool` | `False` | Force square atlas. |
| `allow_rotation` | `bool` | `False` | Allow 90° rotation for tighter packing. |
| `allow_flip` | `bool` | `False` | Allow sprite flipping (limited format support). |
| `trim_sprites` | `bool` | `False` | Trim transparent edges before packing. |
| `expand_strategy` | `str` | `"short_side"` | How to grow atlas: `disabled`, `width_first`, `height_first`, `short_side`, `long_side`, `both`. |
| `image_format` | `str` | `"png"` | Output image format. |
| `export_format` | `str` | `"starling-xml"` | Metadata format key. |
| `texture_format` | `TextureFormat \| None` | `None` | GPU compression format (e.g., `TextureFormat.BC3`). `None` disables GPU compression. |
| `texture_container` | `TextureContainer \| None` | `None` | Container for GPU data (`TextureContainer.DDS` or `TextureContainer.KTX2`). |
| `generate_mipmaps` | `bool` | `False` | Generate full mipmap chain when GPU compression is active. |

---
<br>

## GeneratorResult

Dataclass containing the outcome of atlas generation.

```python
result = generator.generate(frames, output_path, options)

if result.success:
    print(f"Generated {result.frame_count} frames")
    print(f"Atlas size: {result.atlas_width}x{result.atlas_height}")
    print(f"Efficiency: {result.efficiency:.1%}")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `success` | `bool` | Whether generation completed successfully. |
| `atlas_path` | `str` | Path to the generated atlas image. |
| `metadata_path` | `str` | Path to the generated metadata file. |
| `atlas_width` | `int` | Final atlas width in pixels. |
| `atlas_height` | `int` | Final atlas height in pixels. |
| `frame_count` | `int` | Number of packed frames. |
| `efficiency` | `float` | Packing efficiency (0.0–1.0). |
| `errors` | `List[str]` | Error messages if generation failed. |
| `warnings` | `List[str]` | Non-fatal warning messages. |

---
<br>

## GPU Texture Compression

The `TextureCompressor` class handles GPU texture compression for both the generator and
optimizer pipelines. It lives in `core/optimizer/texture_compress.py`.

```python
from core.optimizer.constants import TextureFormat, TextureContainer
from core.optimizer.texture_compress import TextureCompressor

compressor = TextureCompressor(
    fmt=TextureFormat.BC3,
    container=TextureContainer.DDS,
    generate_mipmaps=True,
)

# Check if the backend is available
if compressor.is_available():
    compressor.compress_to_file(pil_image, "/path/to/output.dds")
```

### TextureFormat Enum

Defined in `core/optimizer/constants.py`. Each member exposes:

| Property | Type | Description |
|----------|------|-------------|
| `block_size` | `int` | Side length of one compressed block in texels. |
| `block_bytes` | `int` | Byte size of one compressed block. |
| `has_alpha` | `bool` | Whether the format stores alpha channel data. |

Members: `BC1`, `BC3`, `BC7`, `ETC1`, `ETC2_RGB`, `ETC2_RGBA`, `ASTC_4x4`, `ASTC_6x6`,
`ASTC_8x8`, `PVRTC_4BPP`, `PVRTC_2BPP`.

### TextureContainer Enum

Members: `DDS`, `KTX2`.

### TextureCompressor Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `compress_to_file(image, output_path)` | `Path` | Compress a PIL Image and write to a DDS/KTX2 file. |
| `compress_bytes(image)` | `bytes` | Compress a PIL Image and return raw container bytes. |
| `is_available()` | `bool` | Whether the compression backend for the format is installed. |
| `available_formats` | `List[TextureFormat]` | Class method listing all formats with available backends. |

### Utility Functions

| Function | Description |
|----------|-------------|
| `check_format_available(fmt)` | Check if a specific format's backend is installed. |
| `check_container_supports_format(container, fmt)` | Validate that a container supports a given format. |

<br>
<br>

---

# Packers

The packer system provides layout algorithms for arranging sprites in a texture atlas.

## PackerRegistry

Central registry for all packing algorithms. Provides algorithm lookup and instantiation.

```python
from packers.packer_registry import PackerRegistry

# List available algorithms
algorithms = PackerRegistry.get_all_algorithms()
# [{"name": "maxrects", "display_name": "MaxRects", "heuristics": [...]}, ...]

# Get and use a packer
packer = PackerRegistry.get_packer("maxrects", options)
packer.set_heuristic("bssf")
result = packer.pack(frames)

# Convenience method
result = PackerRegistry.pack("guillotine", frames, options, heuristic="baf")
```

### Class Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `register(packer_class)` | `Type` | Register a packer class (can be used as decorator). |
| `get_packer(algorithm_name, options)` | `BasePacker` | Get an instantiated packer by name. |
| `get_packer_class(algorithm_name)` | `Type \| None` | Get packer class without instantiating. |
| `get_all_algorithms()` | `List[dict]` | Get info about all registered packers. |
| `get_algorithm_names()` | `List[str]` | Get sorted list of algorithm names. |
| `pack(algorithm_name, frames, options, heuristic)` | `PackerResult` | Convenience method to pack frames. |
| `is_registered(algorithm_name)` | `bool` | Check if an algorithm is registered. |

---
<br>

## BasePacker

Abstract base class all packers must inherit from.

```python
from packers.base_packer import BasePacker
from packers.packer_types import FrameInput, PackerOptions, PackedFrame

class MyPacker(BasePacker):
    ALGORITHM_NAME = "my-packer"
    DISPLAY_NAME = "My Custom Packer"
    SUPPORTED_HEURISTICS = [("fast", "Fast"), ("quality", "High Quality")]

    def _pack_internal(
        self,
        frames: List[FrameInput],
        width: int,
        height: int,
    ) -> List[PackedFrame]:
        # Implement packing logic
        ...
```

### Abstract Methods

| Method | Description |
|--------|-------------|
| `_pack_internal(frames, width, height)` | Core packing algorithm implementation. |

### Provided Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `pack(frames)` | `PackerResult` | Main entry point with preprocessing and postprocessing. |
| `set_heuristic(heuristic_key)` | `bool` | Set the heuristic to use for packing. |

---
<br>

## Packer Types

Core types defined in `packers.packer_types`:

| Type | Description |
|------|-------------|
| `FrameInput` | Input frame with id, width, height, and optional user_data. |
| `PackedFrame` | Result with frame reference and atlas position (x, y, rotated, flipped). |
| `PackerOptions` | Configuration for packing (max size, padding, rotation, etc.). |
| `PackerResult` | Container with packed frames, dimensions, efficiency, and diagnostics. |
| `Rect` | Basic rectangle with x, y, width, height. |

### FrameInput

```python
from packers.packer_types import FrameInput

frame = FrameInput(
    id="player_walk_01",
    width=64,
    height=64,
    user_data={"animation": "walk"},  # Optional
)
```

### PackerOptions

```python
from packers.packer_types import PackerOptions, ExpandStrategy

options = PackerOptions(
    max_width=4096,
    max_height=4096,
    padding=2,
    border_padding=0,
    power_of_two=False,
    force_square=False,
    allow_rotation=False,
    allow_flip=False,
    expand_strategy=ExpandStrategy.SHORT_SIDE,
)
```

---
<br>

## Available Algorithms

| Algorithm | Key | Description | Heuristics |
|-----------|-----|-------------|------------|
| MaxRects | `maxrects` | High-quality bin packing using free rectangle tracking. | BSSF, BLSF, BAF, BL, CP |
| Guillotine | `guillotine` | Split-based packing with configurable split rules. | BSSF, BLSF, BAF, WAF |
| Skyline | `skyline` | Fast skyline-based algorithm for real-time packing. | BL, MinWaste |
| Shelf | `shelf` | Simple row-based packing for uniform heights. | NextFit, FirstFit, BestFit |
| Shelf FFDH | `shelf-ffdh` | First Fit Decreasing Height shelf variant. | — |

### Heuristic Keys

| Key | Name | Description |
|-----|------|-------------|
| `bssf` | Best Short Side Fit | Minimize short side remainder. |
| `blsf` | Best Long Side Fit | Minimize long side remainder. |
| `baf` | Best Area Fit | Minimize total wasted area. |
| `bl` | Bottom-Left | Place as low and left as possible. |
| `cp` | Contact Point | Maximize contact with edges and other rects. |
| `waf` | Worst Area Fit | For uniform distribution. |

---
<br>

## PackerErrorCode

Enum categorizing packer failure types.

```python
from packers.packer_types import PackerErrorCode

if error.code == PackerErrorCode.FRAME_TOO_LARGE:
    # Handle oversized frame
    ...
elif error.code == PackerErrorCode.CANNOT_FIT_ALL:
    # Handle packing failure
    ...
```

### Error Code Categories

| Category | Codes | Description |
|----------|-------|-------------|
| **Size constraints** | `FRAME_TOO_LARGE`, `ATLAS_OVERFLOW`, `CANNOT_FIT_ALL` | Frame or atlas size issues. |
| **Input validation** | `NO_FRAMES_PROVIDED`, `INVALID_FRAME_SIZE`, `DUPLICATE_FRAME_ID` | Invalid input data. |
| **Algorithm errors** | `PACKING_FAILED`, `HEURISTIC_NOT_FOUND`, `INVALID_OPTIONS` | Runtime packing failures. |
| **Fallback** | `UNKNOWN_ERROR` | Catch-all for unexpected errors. |

---
<br>

## PackerError

Base exception class for packer errors.

```python
from packers.packer_types import PackerError, PackerErrorCode

try:
    result = packer.pack(frames)
except PackerError as e:
    print(f"Error code: {e.code}")
    print(f"Message: {e.message}")
    print(f"Details: {e.details}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `PackerErrorCode` | Categorized error code. |
| `message` | `str` | Human-readable description. |
| `details` | `dict` | Additional context. |

### Subclasses

| Class | Use Case |
|-------|----------|
| `FrameTooLargeError` | A frame exceeds maximum atlas dimensions. |
| `AtlasOverflowError` | Cannot fit all frames within size constraints. |
| `InvalidOptionsError` | Invalid packer configuration. |

---
<br>

## PackerResult

Dataclass container for packing output with diagnostics.

```python
from packers.packer_types import PackerResult

result = packer.pack(frames)

if result.is_valid:
    print(f"Packed {result.frame_count} frames")
    print(f"Atlas: {result.atlas_width}x{result.atlas_height}")
    print(f"Efficiency: {result.efficiency:.1%}")

    for frame in result.packed_frames:
        print(f"  {frame.id}: ({frame.x}, {frame.y})")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `success` | `bool` | Whether packing completed successfully. |
| `packed_frames` | `List[PackedFrame]` | Frames with atlas positions. |
| `atlas_width` | `int` | Final atlas width. |
| `atlas_height` | `int` | Final atlas height. |
| `efficiency` | `float` | Ratio of used area to total area (0.0–1.0). |
| `warnings` | `List[PackerWarning]` | Non-fatal issues. |
| `errors` | `List[PackerError]` | Errors that occurred. |
| `algorithm_name` | `str \| None` | Packing algorithm used. |
| `heuristic_name` | `str \| None` | Heuristic used, if applicable. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_valid` | `bool` | `True` if at least one frame was packed. |
| `frame_count` | `int` | Number of packed frames. |
| `total_area` | `int` | Total atlas area in pixels. |
| `used_area` | `int` | Area occupied by frames. |

---
<br>

## PackerWarning

Dataclass for non-fatal packing issues.

```python
from packers.packer_types import PackerWarning, PackerErrorCode

warning = PackerWarning(
    code=PackerErrorCode.DUPLICATE_FRAME_ID,
    message="Duplicate frame 'frame_01', using first occurrence",
    frame_id="frame_01",
)
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `PackerErrorCode` | Categorized warning code. |
| `message` | `str` | Human-readable description. |
| `frame_id` | `str \| None` | ID of affected frame. |
| `details` | `dict \| None` | Additional context. |

<br>
<br>

---

# Exporters

The exporter system generates atlas images and metadata files from packed sprite layouts.

## ExporterRegistry

Central registry for all metadata format exporters.

```python
from exporters.exporter_registry import ExporterRegistry

# List available formats
formats = ExporterRegistry.get_all_formats()
# ["json-array", "json-hash", "phaser3", "spine", "starling-xml", ...]

# Export using a specific format
result = ExporterRegistry.export_file(
    sprites=sprite_list,
    sprite_images=image_dict,
    output_path="/path/to/output",
    format_name="json-hash",
)
```

### Class Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `register(exporter_class)` | `Type` | Register an exporter (can be used as decorator). |
| `get_exporter(format_name)` | `Type \| None` | Get exporter class by format name or extension. |
| `get_all_formats()` | `List[str]` | Get sorted list of format names. |
| `get_supported_extensions()` | `List[str]` | Get list of supported file extensions. |
| `export_file(sprites, sprite_images, output_path, format_name, options)` | `ExportResult` | Unified export entry point. |
| `initialize()` | `None` | Initialize registry with all available exporters. |

---
<br>

## BaseExporter

Abstract base class all exporters must inherit from.

```python
from exporters.base_exporter import BaseExporter
from exporters.exporter_types import PackedSprite, ExportResult

class MyExporter(BaseExporter):
    FILE_EXTENSION = ".myformat"
    FORMAT_NAME = "my-format"

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata=None,
    ) -> str:
        # Generate format-specific metadata
        ...
```

### Abstract Methods

| Method | Description |
|--------|-------------|
| `build_metadata(packed_sprites, atlas_width, atlas_height, image_name, generator_metadata)` | Generate format-specific metadata string/bytes. |

### Provided Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `export_file(sprites, sprite_images, output_path)` | `ExportResult` | Main export entry point. |
| `pack_sprites(sprites, sprite_images)` | `Tuple[List[PackedSprite], int, int]` | Pack sprites into atlas layout. |
| `composite_atlas(packed_sprites, sprite_images, width, height)` | `Image` | Render sprites onto atlas image. |

---
<br>

## Exporter Types

Core types defined in `exporters.exporter_types`:

| Type | Description |
|------|-------------|
| `ExportOptions` | Configuration for export (image format, padding, etc.). |
| `ExportResult` | Container with paths, dimensions, and diagnostics. |
| `PackedSprite` | Sprite with atlas position (atlas_x, atlas_y, rotated). |
| `ExporterWarning` | Non-fatal issue during export. |
| `GeneratorMetadata` | Metadata for watermarking (app version, packer, efficiency). |

### ExportOptions

```python
from exporters.exporter_types import ExportOptions

options = ExportOptions(
    image_format="PNG",
    padding=2,
    power_of_two=False,
    max_width=4096,
    max_height=4096,
    allow_rotation=False,
    trim_sprites=False,
    pretty_print=True,
)
```

---
<br>

## Supported Export Formats

| Format | Key | Extension | Description |
|--------|-----|-----------|-------------|
| Starling/Sparrow XML | `starling-xml` | `.xml` | Adobe AIR/Starling framework format. |
| TexturePacker JSON (Hash) | `json-hash` | `.json` | Sprites keyed by name. |
| TexturePacker JSON (Array) | `json-array` | `.json` | Sprites in array format. |
| TexturePacker XML | `texturepacker-xml` | `.xml` | Legacy TexturePacker XML. |
| Spine | `spine` | `.atlas` | Esoteric Spine runtime format. |
| Phaser 3 | `phaser3` | `.json` | Phaser 3 game framework. |
| Godot | `godot` | `.tpsheet` | Godot engine import format. |
| Unity | `unity` | `.tpsheet` | Unity TexturePacker importer. |
| Cocos2d Plist | `plist` | `.plist` | Cocos2d-x property list. |
| UIKit Plist | `uikit-plist` | `.plist` | iOS UIKit format. |
| CSS Spritesheet | `css` | `.css` | CSS background-position rules. |
| Plain Text | `txt` | `.txt` | Simple text format. |
| Egret2D | `egret2d` | `.json` | Egret 2D engine. |
| Paper2D | `paper2d` | `.paper2dsprites` | Unreal Engine Paper2D. |

---
<br>

## ExporterErrorCode

Enum categorizing exporter failure types.

```python
from exporters.exporter_types import ExporterErrorCode

if error.code == ExporterErrorCode.IMAGE_NOT_FOUND:
    # Handle missing image
    ...
elif error.code == ExporterErrorCode.ATLAS_TOO_LARGE:
    # Handle size constraint
    ...
```

### Error Code Categories

| Category | Codes | Description |
|----------|-------|-------------|
| **File-level** | `FILE_WRITE_ERROR`, `DIRECTORY_NOT_FOUND`, `PERMISSION_DENIED` | File I/O issues. |
| **Image-level** | `IMAGE_NOT_FOUND`, `IMAGE_READ_ERROR`, `IMAGE_WRITE_ERROR`, `INVALID_IMAGE_FORMAT` | Image processing issues. |
| **Sprite-level** | `SPRITE_MISSING_DATA`, `SPRITE_INVALID_BOUNDS`, `SPRITE_OUT_OF_BOUNDS`, `DUPLICATE_SPRITE_NAME` | Sprite data issues. |
| **Packing** | `PACKING_FAILED`, `ATLAS_TOO_LARGE`, `NO_SPRITES_PROVIDED` | Layout failures. |
| **Format** | `UNSUPPORTED_FORMAT`, `SERIALIZATION_ERROR` | Metadata format issues. |
| **Fallback** | `UNKNOWN_ERROR` | Catch-all for unexpected errors. |

---
<br>

## ExporterError

Base exception class for exporter errors.

```python
from exporters.exporter_types import ExporterError, ExporterErrorCode

try:
    result = exporter.export_file(sprites, images, output_path)
except ExporterError as e:
    print(f"Error code: {e.code}")
    print(f"Message: {e.message}")
    print(f"File: {e.file_path}")
    print(f"Details: {e.details}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `ExporterErrorCode` | Categorized error code. |
| `message` | `str` | Human-readable description. |
| `file_path` | `str \| None` | Path to the problematic file. |
| `details` | `dict` | Additional context. |

### Subclasses

| Class | Use Case |
|-------|----------|
| `FileWriteError` | Error writing to a file. |
| `ImageError` | Error processing images. |
| `PackingError` | Error during sprite packing. |
| `FormatError` | Error in metadata format or serialization. |

---
<br>

## ExportResult

Dataclass container for export output with diagnostics.

```python
from exporters.exporter_types import ExportResult

result = exporter.export_file(sprites, images, output_path)

if result.is_valid:
    print(f"Exported {result.sprite_count} sprites")
    print(f"Atlas: {result.atlas_path}")
    print(f"Metadata: {result.metadata_path}")

if result.warnings:
    for warning in result.warnings:
        print(f"Warning: {warning.message}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `success` | `bool` | Whether export completed successfully. |
| `atlas_path` | `str \| None` | Path to generated atlas image. |
| `metadata_path` | `str \| None` | Path to generated metadata file. |
| `atlas_width` | `int` | Final atlas width. |
| `atlas_height` | `int` | Final atlas height. |
| `sprite_count` | `int` | Number of exported sprites. |
| `warnings` | `List[ExporterWarning]` | Non-fatal issues. |
| `errors` | `List[ExporterError]` | Errors that occurred. |
| `exporter_name` | `str \| None` | Name of exporter class used. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_valid` | `bool` | `True` if export produced valid output. |
| `warning_count` | `int` | Count of warnings. |
| `error_count` | `int` | Count of errors. |

### Methods

| Method | Description |
|--------|-------------|
| `add_warning(code, message, sprite_name, details)` | Add a warning to the result. |
| `add_error(code, message, file_path, details)` | Add an error to the result. |
| `get_summary()` | Return a human-readable summary. |

---
<br>

## ExporterWarning

Dataclass for non-fatal export issues.

```python
from exporters.exporter_types import ExporterWarning, ExporterErrorCode

warning = ExporterWarning(
    code=ExporterErrorCode.DUPLICATE_SPRITE_NAME,
    message="Duplicate sprite 'frame_01', using last occurrence",
    sprite_name="frame_01",
)
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `ExporterErrorCode` | Categorized warning code. |
| `message` | `str` | Human-readable description. |
| `sprite_name` | `str \| None` | Name of affected sprite. |
| `details` | `dict \| None` | Additional context. |

<br>
<br>

---

# Utility Classes

General-purpose utilities for path resolution, filename sanitization, and common operations.

## Utilities

Static utility methods for common application tasks including path resolution, filename
formatting, and spritesheet list management.

```python
from utils.utilities import Utilities

# Find the application root directory
root = Utilities.find_root("assets")

# Sanitize a filename
safe_name = Utilities.replace_invalid_chars("my:file*name.png")
# Returns: "my_file_name.png"

# Format a standardized filename
filename = Utilities.format_filename(
    prefix="export",
    sprite_name="player.png",
    animation_name="idle",
    filename_format="standardized",
    replace_rules=[],
)
# Returns: "export - player - idle"
```

### Static Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `find_root(target_name)` | `str \| None` | Walk up the directory tree to find a folder containing `target_name`. |
| `is_compiled()` | `bool` | Check if running as a Nuitka-compiled executable. |
| `count_spritesheets(spritesheet_list)` | `int` | Return the number of spritesheets in a list. |
| `replace_invalid_chars(name)` | `str` | Replace filesystem-invalid characters (`\\ / : * ? " < > \|`) with underscores. |
| `strip_trailing_digits(name)` | `str` | Remove trailing frame numbers and `.file` extension. |
| `format_filename(prefix, sprite_name, animation_name, filename_format, replace_rules, suffix)` | `str` | Build a sanitized filename from components and format rules. |

#### Filename Format Presets

| Preset | Example Output |
|--------|----------------|
| `standardized` | `prefix - sprite - animation - suffix` |
| `no_spaces` | `prefix-sprite-animation-suffix` |
| `no_special` | `prefixspriteanimationsuffix` |
| Custom template | Uses `$sprite` and `$anim` placeholders. |

<br>
<br>

---

# Application Configuration

## AppConfig

Manages persistent application settings stored in a JSON configuration file. Provides typed
access to extraction defaults, compression settings, interface preferences, and more.

```python
from utils.app_config import AppConfig

config = AppConfig()  # Loads from default path or creates new config

# Get/set simple values
language = config.get("language", "auto")
config.set("language", "en")

# Work with extraction defaults
defaults = config.get_extraction_defaults()
config.set_extraction_defaults(fps=30, scale=2.0)

# Get format-specific compression settings
png_settings = config.get_compression_defaults("png")
config.set_compression_defaults("webp", lossless=True, quality=95)
```

### Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `DEFAULTS` | `dict` | Default values for all configuration keys. |
| `TYPE_MAP` | `dict` | Expected Python types for each setting key. |
| `config_path` | `str` | Filesystem path to the configuration file. |
| `settings` | `dict` | Current settings dictionary. |

### Core Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `load()` | `None` | Load settings from the config file, merging with current values. |
| `save()` | `None` | Write the current settings to the config file. |
| `migrate()` | `None` | Add missing defaults and remove obsolete keys. |
| `get(key, default=None)` | `Any` | Retrieve a setting value by key. |
| `set(key, value)` | `None` | Store a setting value and persist to disk. |

### Extraction Defaults

| Method | Returns | Description |
|--------|---------|-------------|
| `get_extraction_defaults()` | `dict` | Return a copy of the extraction default settings. |
| `set_extraction_defaults(**kwargs)` | `None` | Update extraction defaults and persist to disk. |

### Compression Settings

| Method | Returns | Description |
|--------|---------|-------------|
| `get_compression_defaults(format_name=None)` | `dict` | Return compression defaults for one or all formats. |
| `set_compression_defaults(format_name, **kwargs)` | `None` | Update compression defaults for a format. |
| `get_format_compression_settings(format_name)` | `dict` | Return compression settings keyed for the frame exporter. |

### Generator & Editor Settings

| Method | Returns | Description |
|--------|---------|-------------|
| `get_generator_defaults()` | `dict` | Return a copy of the generator default settings. |
| `set_generator_defaults(**kwargs)` | `None` | Update generator defaults and persist to disk. |
| `get_editor_settings()` | `dict` | Return a copy of the editor settings. |
| `set_editor_settings(**kwargs)` | `None` | Update editor settings and persist to disk. |

### Interface Settings

| Method | Returns | Description |
|--------|---------|-------------|
| `get_last_input_directory()` | `str` | Return the last input directory if remembering is enabled. |
| `set_last_input_directory(path)` | `None` | Store the last input directory. |
| `get_last_output_directory()` | `str` | Return the last output directory if remembering is enabled. |
| `set_last_output_directory(path)` | `None` | Store the last output directory. |

### Default Configuration Structure

```python
{
    "first_run_completed": False,
    "language": "auto",
    "resource_limits": {
        "cpu_cores": "auto",
        "memory_limit_mb": 0,
    },
    "extraction_defaults": {
        "animation_format": "GIF",
        "animation_export": False,
        "duration": 42,
        "scale": 1.0,
        "threshold": 0.5,
        "resampling_method": "Nearest",
        "frame_selection": "all",
        "crop_option": "animation",
        "filename_format": "standardized",
        # ... additional settings
    },
    "compression_defaults": {
        "png": {"compress_level": 9, "optimize": True},
        "webp": {"lossless": True, "quality": 90, "method": 3},
        "avif": {"lossless": True, "quality": 90, "speed": 5},
        "tiff": {"compression_type": "lzw", "quality": 90},
    },
    "generator_defaults": {
        "algorithm": "auto",
        "max_size": 4096,
        "padding": 2,
        "export_format": "starling-xml",
    },
    "interface": {
        "last_input_directory": "",
        "last_output_directory": "",
        "remember_input_directory": True,
        "use_native_file_dialog": False,
    },
}
```

<br>
<br>

---

# Version & Updates

## Version Constants

Centralized application version constants and GitHub API URLs for update checking.

```python
from utils.version import APP_NAME, APP_VERSION, version_to_tuple

print(f"{APP_NAME} v{APP_VERSION}")

# Compare versions
current = version_to_tuple("1.2.3")
latest = version_to_tuple("2.0.0-beta")
if latest > current:
    print("Update available!")
```

### Constants

| Constant | Type | Description |
|----------|------|-------------|
| `APP_NAME` | `str` | Application display name (`"TextureAtlas Toolbox"`). |
| `APP_VERSION` | `str` | Current version string (e.g., `"2.0.0"`). |
| `REPO_OWNER` | `str` | GitHub repository owner. |
| `REPO_NAME` | `str` | GitHub repository name. |
| `GITHUB_TAGS_URL` | `str` | API URL for fetching tags. |
| `GITHUB_RELEASES_URL` | `str` | API URL for fetching releases. |
| `GITHUB_LATEST_RELEASE_URL` | `str` | API URL for fetching the latest release. |

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `version_to_tuple(version)` | `tuple[int, ...]` | Parse a semantic version string into a comparable tuple. |

---
<br>

## UpdateChecker

Background version checking against GitHub releases with user-facing update dialogs.

```python
from utils.update_checker import UpdateChecker

checker = UpdateChecker(current_version="1.0.0")

# Check for updates (async, emits signals)
checker.check_for_updates()

# Connect to signals
checker.update_available.connect(on_update_available)
checker.error.connect(on_check_error)
```

### Signals

| Signal | Parameters | Description |
|--------|------------|-------------|
| `update_available` | `(bool, str, dict)` | Emitted when check completes: (available, version, metadata). |
| `error` | `(str,)` | Emitted when a network or parsing error occurs. |

<br>
<br>

---

# Resampling

Utilities for image scaling operations with support for both Pillow and Wand (ImageMagick).

## Resampling Methods

Enum of available resampling methods with trade-offs between quality and performance.

```python
from utils.resampling import (
    get_pil_resampling_filter,
    get_wand_resampling_filter,
    RESAMPLING_DISPLAY_NAMES,
)

# Get PIL filter for resize operations
pil_filter = get_pil_resampling_filter("Lanczos")
scaled = image.resize((new_w, new_h), pil_filter)

# Get Wand filter for ImageMagick operations
wand_filter = get_wand_resampling_filter("Bicubic")
wand_image.resize(new_w, new_h, filter=wand_filter)
```

### Available Methods

| Method | PIL Constant | Wand Filter | Best For |
|--------|--------------|-------------|----------|
| `Nearest` | `NEAREST` | `point` | Pixel art, retro graphics, preserving hard edges. |
| `Bilinear` | `BILINEAR` | `triangle` | Quick previews, when speed matters more than quality. |
| `Bicubic` | `BICUBIC` | `catrom` | General-purpose scaling with good quality/speed balance. |
| `Lanczos` | `LANCZOS` | `lanczos` | High-resolution artwork, photos, maximum detail. |
| `Box` | `BOX` | `box` | Fast downscaling, thumbnail generation. |
| `Hamming` | `HAMMING` | `hamming` | Lanczos-like quality with fewer edge artifacts. |

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `get_pil_resampling_filter(method_name, scale)` | `int` | Get the PIL resampling filter constant. |
| `get_wand_resampling_filter(method_name, scale)` | `str` | Get the Wand/ImageMagick filter name. |
| `get_resampling_index(method_name)` | `int` | Get the combobox index for a method name. |
| `get_resampling_name(index)` | `str` | Get the method name for a combobox index. |
| `get_resampling_tooltip(method_name)` | `str` | Get a descriptive tooltip for a method. |

<br>
<br>

---

# Error Handling

Utilities for mapping low-level errors to user-friendly messages.

## ExceptionHandler

Utility namespace for mapping low-level errors to readable user messages. Integrates with the
unified parser error system.

```python
from core.exception_handler import ExceptionHandler

# Handle an exception during extraction
sprites_failed, user_error = ExceptionHandler.handle_exception(
    e=caught_exception,
    metadata_path="/path/to/atlas.json",
    sprites_failed=current_count,
)

# Format a ParserError for display
message = ExceptionHandler.format_parser_error(parser_error, fallback_path)

# Format a ParseResult summary
summary = ExceptionHandler.format_parse_result(result, include_warnings=True)
```

### Static Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `handle_exception(e, metadata_path, sprites_failed)` | `tuple[int, Exception]` | Convert an exception to a user-friendly error message. |
| `format_parser_error(error, fallback_path)` | `str` | Format a `ParserError` into a user-friendly message. |
| `format_parse_result(result, include_warnings)` | `str` | Format a `ParseResult` into a summary message. |
| `handle_validation_error(key, expected_type)` | `str` | Return a readable validation error message. |
| `should_show_error_dialog(result)` | `bool` | Determine if a `ParseResult` warrants showing an error dialog. |
| `should_prompt_removal(result)` | `bool` | Determine if user should be prompted to remove file from list. |

### Error Code Mapping

The `ERROR_MESSAGES` class attribute maps `ParserErrorCode` values to user-friendly message
templates with placeholders for `{message}` and `{file_path}`.

---
<br>

## Common Exception Types

| Category | Examples |
|----------|----------|
| **File I/O Errors** | Missing files, permission issues, encoding problems. |
| **Format Errors** | Invalid XML/JSON/TXT format, unsupported format. |
| **Validation Errors** | Invalid setting values, type mismatches. |
| **Coordinate Errors** | Sprite out of bounds, negative dimensions. |
| **Memory Errors** | Insufficient memory for large atlases. |
| **ImageMagick Errors** | Missing or misconfigured ImageMagick installation. |

<br>
<br>

---
---

# Qt-Dependent APIs

The following APIs require PySide6 (Qt for Python) and are only available when running the full
GUI application.

<br>

---

# Localization

> **Requires:** PySide6 (`QApplication`, `QTranslator`)

The translation system provides dynamic language switching, quality metadata for each supported
language, and utilities for translating UI strings.

## TranslationManager

Manages application translations and language switching. Handles discovery of available
translation files, loading translations, and providing metadata about translation quality.

```python
from utils.translation_manager import TranslationManager, get_translation_manager

# Get the global instance
manager = get_translation_manager()

# List available languages
languages = manager.get_available_languages()
# {"en": {"name": "English", "english_name": "English", "quality": "native"}, ...}

# Load a translation
manager.load_translation("de_de")

# Check translation quality
if manager.is_machine_translated("de_de"):
    title, message = manager.get_machine_translation_disclaimer()
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `app_instance` | `QApplication` | The QApplication instance for translator installation. |
| `current_translator` | `QTranslator \| None` | Currently installed QTranslator, if any. |
| `current_locale` | `str \| None` | Language code of the active translation. |
| `translations_dir` | `Path` | Path to the translations directory. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_available_languages()` | `dict[str, dict]` | Return languages that have translation files available. |
| `get_system_locale()` | `str` | Get the system's default locale as a language code. |
| `load_translation(language_code)` | `bool` | Load translation for the specified language code. |
| `get_current_language()` | `str` | Return the currently active language code. |
| `refresh_ui(main_window)` | `None` | Refresh the UI to apply the current translation. |
| `is_machine_translated(language_code)` | `bool` | Check if a language uses machine translation. |
| `get_quality_level(language_code)` | `str` | Get the quality level of a translation. |
| `get_english_name(language_code)` | `str` | Get the English name of a language. |
| `get_display_name(language_code, show_english)` | `str` | Get the display name for a language. |
| `get_machine_translation_disclaimer()` | `tuple[str, str]` | Get the machine translation disclaimer (title, message). |

### Translation Quality Levels

| Level | Description |
|-------|-----------|
| `native` | Approved by multiple native speakers. |
| `reviewed` | Checked by at least one reviewer. |
| `unreviewed` | Human translated but not yet reviewed. |
| `machine` | Auto-generated machine translation. |
| `unknown` | Fallback when quality is not specified. |

---
<br>

## tr (Translator)

Callable helper for translating UI strings with automatic context detection.

```python
from utils.translation_manager import tr

# Simple translation
label = tr("Save")

# With explicit context
message = tr("File saved successfully", context="FileDialog")

# As a class attribute (auto-detects class name as context)
class MyWidget:
    tr = tr

    def show_message(self):
        return self.tr("Hello, World!")
```

---