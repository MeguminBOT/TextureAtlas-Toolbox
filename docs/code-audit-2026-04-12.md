# Source Code Audit — April 12, 2026

Full audit of `src/` covering bugs, missing error handling, inefficiencies, and progress display gaps.

---

## 1. Bugs

### Critical

| # | File | Issue |
|---|------|-------|
| B1 | `src/parsers/base_parser.py` ~L79-82 | `extract_raw_sprite_names()` catches **all** exceptions with `except Exception: return []`. File-not-found, encoding errors, JSON decode failures — all silently become an empty list. This masks real problems from users. |
| B2 | `src/core/extractor/animation_exporter.py` ~L165 | Signature cache corruption: when `_frame_signature()` returns `None`, `signature_cache` is set to `None` permanently, breaking deduplication for all remaining frames in that batch — even valid ones. |
| B3 | `src/core/extractor/sprite_processor.py` ~L170-180 | Canvas composition can produce **negative `copy_width`** if `sprite_array.shape[1] < src_x`. This would silently create an empty/corrupt frame rather than erroring out. |
| B4 | `src/utils/dependencies_checker.py` ~L133 | `configure_imagemagick()` doesn't guard against `find_root()` returning `None` before using the result as a path. |

### Medium

| # | File | Issue |
|---|------|-------|
| B5 | `src/core/extractor/frame_selector.py` ~L145 | Negative-range parsing (`"--1"`) can hit an off-by-one: `entry[1:].find("-") + 1` doesn't account for the leading-minus edge case properly. |
| B6 | `src/core/extractor/animation_exporter.py` ~L240 | GIF duration rounding truncates before clamping: `(19 // 10) * 10 = 10`, losing 9ms — accumulates over many frames. Should round, not floor. |
| B7 | `src/core/extractor/preview_generator.py` ~L118 | `tempfile.mkdtemp()` created but **never cleaned up** on exception paths — temp dir leak on every failed preview. |
| B8 | `src/core/extractor/extractor.py` ~L240-280 | TOCTOU race on `_psutil_process`: multiple workers can simultaneously check `is None` and re-create the `Process` object. |
| B9 | `src/utils/settings_manager.py` ~L37-48 | Logic creates an empty dict then immediately deletes it when `kwargs` is empty — should check first. |
| B10 | `src/utils/update_installer.py` ~L360-369 | `apply_pending_updates()` has TOCTOU: checks file exists then removes — another process could delete between check and removal. |
| B11 | `src/utils/translation_manager.py` ~L217-232 | Uses deprecated PySide6 `Territory`/`Country` enum — fragile across PySide6 versions. |

---

## 2. Missing Error Handling / Raises Not Using Proper Handlers

### Pattern: ~15 Parsers with Bare File I/O

All JSON parsers (`egret2d`, `godot_atlas`, `json_array`, `json_hash`, `paper2d`, `phaser3`) share the identical vulnerable pattern:

```python
def _load_json(self):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)  # ← No try/except, no ParserError
```

All XML parsers (`starling_xml`, `texture_packer_xml`, `xml_parser`) do the same:

```python
tree = ET.parse(file_path)  # ← Bare, no error wrapping
```

**Affected files** (should wrap with `FileError` / `FormatError` from `ParserError`):

| Parser | Bare I/O Location | Also Missing in `extract_names()` |
|--------|-------------------|-----------------------------------|
| `src/parsers/egret2d_parser.py` | ~L44-46 | Yes |
| `src/parsers/godot_atlas_parser.py` | ~L45-47 | Yes |
| `src/parsers/json_array_parser.py` | ~L40-42 | Yes |
| `src/parsers/json_hash_parser.py` | ~L43-45 | Yes |
| `src/parsers/paper2d_parser.py` | ~L43-45 | Yes |
| `src/parsers/phaser3_parser.py` | ~L43-45 | Yes |
| `src/parsers/uikit_plist_parser.py` | ~L51-53 | — |
| `src/parsers/starling_xml_parser.py` | ~L48-50, L207-209 | Yes |
| `src/parsers/texture_packer_xml_parser.py` | ~L45-47, L155-157 | Yes |

### Pattern: Bare `int()` Conversions Without Error Wrapping

| Parser | Location | Risk |
|--------|----------|------|
| `src/parsers/gdx_parser.py` ~L187-227 | `int(vals[0])` etc. in `_build_sprite()` | `ValueError` on non-numeric strings |
| `src/parsers/spine_parser.py` ~L79-82 | `_parse_pair()` returns `[0, 0]` silently | Silent data corruption |
| `src/parsers/aseprite_parser.py` ~L151-162 | `int(frame.get("x", 0))` | `ValueError` if value is non-numeric string |
| `src/parsers/texture_packer_unity_parser.py` ~L40-56 | `int(float(parts[1]))` | Silent skip, no warning count |

### Other Missing Handler Usage

| File | Issue |
|------|-------|
| `src/parsers/xml_parser.py` ~L94 | Raises `ValueError` instead of `FormatError(ParserErrorCode.INVALID_FORMAT)` — breaks unified error handling |
| `src/parsers/spritemap_parser.py` ~L83-85 | `print()` to stdout instead of proper error propagation |
| `src/gui/extract_tab_widget.py` ~L1330-1507 | Uses `print()` and `QMessageBox.warning()` directly instead of `ExceptionHandler` |
| `src/gui/editor_tab_widget.py` ~L1686 | Prints tracebacks to stderr instead of using structured error handling |
| `src/parsers/css_legacy_parser.py` ~L67-84 | Silently skips invalid CSS blocks — no warning/error count |
| `src/parsers/txt_parser.py` ~L95-125 | `parse_txt_packer()` silently skips invalid lines with `continue` — no tracking |
| All exporters `_get_format_options()` | `**opts` can raise `TypeError` on invalid dict keys — uncaught |

---

## 3. Highly Inefficient Code

### Critical Performance

| # | File | Issue | Impact |
|---|------|-------|--------|
| O1 | `src/core/generator/atlas_generator.py` ~L450-520 | **O(n²) flip-variant detection**: for every frame, iterates all entries in `hash_to_canonical` to check flip hashes. 1000 frames → ~500K comparisons. | Slug on large atlases |
| O2 | `src/core/optimizer/quantize.py` ~L210 | **512MB extra RAM** for 4096×4096 atlas: `np.float64` copy + `premul = arr.copy()`. Could use `float32` and in-place ops. | OOM on large images |
| O3 | `src/utils/translation_manager.py` ~L193-195 | `_calculate_completeness()` **parses entire .ts XML file** for every language in `get_available_languages()`. With 15 languages = 15 file reads. | Slow startup |

### Medium Performance

| # | File | Issue |
|---|------|-------|
| O4 | `src/core/extractor/animation_exporter.py` ~L105-130 | All frames converted to RGBA arrays upfront — could stream on-demand via generator to reduce peak memory. |
| O5 | `src/core/extractor/sprite_processor.py` ~L105 | `_atlas_array` (full contiguous copy of atlas) held in memory for entire session. Could release after all crops complete. |
| O6 | `src/core/extractor/frame_pipeline.py` / `src/core/extractor/animation_exporter.py` | Frame signature computed **twice** — once in dedup-check, again during GIF export. Cache should persist. |
| O7 | `src/core/extractor/spritemap/symbols.py` ~L340-380 | Union bounds computed twice: once in bounds pass, once implicitly in compact render. |
| O8 | `src/exporters/starling_xml_exporter.py` ~L267-296 | `minidom.parseString()` for pretty-printing never calls `dom.unlink()` — keeps entire DOM in memory until GC. |

---

## 4. Progress Display Gaps

### Architecture Context

Extraction **is** multi-threaded (QThread worker pool), and the `ProcessingWindow` shows file-level progress with a 100ms batched UI flush. However there are significant gaps:

### Critical Gaps

| # | Area | Problem | Suggested Fix |
|---|------|---------|---------------|
| P1 | **Per-file sub-progress** | When extracting a single large atlas (1000+ frames), the UI shows "Processing: atlas.png" with **no progress within that file**. Looks frozen for minutes. | Add a `frame_progress_callback(current, total)` to `FrameExporter.save_frames()` and `AnimationExporter.save_animations()`. Wire through to `ProcessingWindow`. |
| P2 | **Memory pressure pauses** | When workers pause due to memory budget, the UI shows nothing — extraction appears stuck. | Emit a "Paused: memory pressure" status when `_memory_within_budget()` returns False. Display in `ProcessingWindow` with a distinct color/icon. |
| P3 | **GIF/APNG compression phase** | After frame extraction, animation compression can take 30+ seconds with zero feedback. | Add progress callback into `AnimationExporter._save_with_wand()` and `_save_with_pillow()`. Even a simple indeterminate spinner. |

### Medium Gaps

| # | Area | Problem | Suggested Fix |
|---|------|---------|---------------|
| P4 | **Generator: initial frame setup** | `add_directory()` and `add_existing_atlas()` in `generate_tab_widget.py` scan/extract files synchronously on the main thread (~L385-655). Large directories freeze the UI. | Move to a lightweight QThread or use `QApplication.processEvents()` with a progress bar. |
| P5 | **Generator: duplicate detection** | The O(n²) flip detection loop emits no progress. With 500+ frames, multi-second stall with no feedback. | Add `progress_callback` to `_detect_duplicates()` that emits every N frames processed. |
| P6 | **Queue depth invisible** | Users see "3 of 10 processed" but can't tell if workers are idle vs. queued work is waiting. | Add "Queued: N files remaining" to `ProcessingWindow`. The queue size is available from `_file_queue.qsize()`. |
| P7 | **Worker display limit** | `_build_worker_status_snapshot(limit=4)` hides workers beyond 4. On 8+ core machines users miss activity. | Make the limit configurable or show a collapsed "...and N more workers" indicator. |
| P8 | **Editor: animation loading** | `add_animation_from_extractor()` loads frames synchronously with no progress — can block for large spritesheets. | Show indeterminate progress bar during load. |

---

## Suggested Implementation Plan

### Phase 1 — Bug Fixes (Quick Wins)
1. Fix `base_parser.py` silent swallow → catch specific exceptions, propagate errors
2. Fix `animation_exporter.py` signature cache corruption → don't null the cache on single failure
3. Fix `xml_parser.py` `ValueError` → `FormatError`
4. Fix `preview_generator.py` temp dir leak → use `tempfile.TemporaryDirectory()` context manager
5. Fix `sprite_processor.py` negative `copy_width` → add bounds check

### Phase 2 — Error Handling Consistency
6. Add `try/except` wrapping to all 9 JSON/XML parser `_load_*()` methods (template fix, very mechanical)
7. Add `try/except` around bare `int()` conversions in gdx, spine, aseprite, unity parsers
8. Replace `print()` error reporting with structured `ParserError` in `spritemap_parser.py`
9. Add `TypeError` guard to all exporter `_get_format_options()` methods

### Phase 3 — Progress Display
10. Add `frame_progress_callback` plumbing through `FrameExporter` → `AnimationExporter` → `ExtractorWorker` → `ProcessingWindow`
11. Add memory-pressure status emission in `Extractor._memory_within_budget()`
12. Add queue-depth display to `ProcessingWindow`
13. Move generator `add_directory()` / `add_existing_atlas()` off the main thread

### Phase 4 — Performance
14. Fix O(n²) flip detection → build reverse lookup set of all flip hashes
15. Fix `quantize.py` double-copy → use `float32` + in-place operations
16. Cache translation completeness calculations
17. Add `dom.unlink()` to starling XML exporter pretty-printing
