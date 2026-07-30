"""High-level Adobe Spritemap renderer for extracting symbol animations.

Provides ``AdobeSpritemapRenderer``, which loads an Adobe Animate export
(Animation.json + spritemap JSON + atlas PNG) and renders each symbol or
timeline label into cropped RGBA frames.

Two rendering strategies are available:

* **Batch** via ``AdobeSpritemapRenderer.build_animation_frames`` —
  renders every animation into memory at once.  Required when editor
  composites need cross-animation frame references.

* **Streaming** via ``AdobeSpritemapRenderer.iter_animations`` —
  yields one ``(name, lazy_frame_iterator)`` at a time so the caller can
  export and free frames before the next animation is rendered, keeping
  peak memory proportional to the largest single animation.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from PIL import Image

from core.extractor.image_utils import FramePlacement, union_excluding_outliers
from utils.utilities import Utilities
from .sprite_atlas import SpriteAtlas
from .symbols import Symbols
from .metadata import collect_direct_child_symbols, collect_referenced_symbols
from .normalizer import normalize_animation_document
from .transform_matrix import TransformMatrix

#: Matches ``spritemap.json`` / ``spritemap1.json`` ... ``spritemapN.json``.
_PAGE_FILE_RE = re.compile(r"^spritemap(\d*)\.json$", re.IGNORECASE)

#: Image extensions a spritemap page may point at, in preference order.
_PAGE_IMAGE_EXTENSIONS = (".png", ".webp", ".dds", ".ktx2", ".jpg", ".jpeg", ".bmp")

#: Hard ceiling on any single render canvas, in pixels. A malformed or
#: extreme transform can otherwise ask for a multi-gigabyte allocation.
MAX_CANVAS_PIXELS = 64 * 1024 * 1024

#: Frame bytes allowed in flight across render threads at once. Caps what
#: parallelism costs in memory, so speed cannot undo the memory savings.
INFLIGHT_FRAME_BUDGET = 512 * 1024 * 1024


def default_render_workers() -> int:
    """Return a sensible default thread count for frame rendering."""
    return max(1, min(8, (os.cpu_count() or 1)))


def discover_spritemap_pages(
    directory: Union[str, Path],
) -> List[Tuple[Path, Optional[Path]]]:
    """Find every ``spritemap*.json`` page in *directory* with its image.

    Stock Adobe Animate writes a single ``spritemap.json``; Better Texture
    Atlas splits overflow across ``spritemap1.json`` ... ``spritemapN.json``.
    All of them belong to one animation and must be rendered together.

    Args:
        directory: Folder holding ``Animation.json`` and its pages.

    Returns:
        List of ``(json_path, image_path_or_None)`` sorted by page index.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []

    found: List[Tuple[int, Path]] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        match = _PAGE_FILE_RE.match(entry.name)
        if match:
            digits = match.group(1)
            found.append((int(digits) if digits else 1, entry))
    found.sort(key=lambda item: item[0])

    pages: List[Tuple[Path, Optional[Path]]] = []
    for _, json_path in found:
        pages.append((json_path, _resolve_page_image(json_path)))
    return pages


def is_secondary_spritemap_page(image_path: Union[str, Path]) -> bool:
    """Return ``True`` when *image_path* is a follow-on page of a set.

    A multi-page export (``spritemap1.png`` ... ``spritemapN.png``) is one
    animation, not N of them. Rendering starts from the first page and pulls
    in the rest, so every later page must be filtered out of file listings —
    otherwise the same animation is extracted once per sheet, multiplying
    both runtime and peak memory by the page count.

    Args:
        image_path: Candidate spritesheet image.

    Returns:
        ``True`` if this page is covered by an earlier page in the same
        directory and should not be listed on its own.
    """
    path = Path(image_path)
    directory = path.parent
    if not (directory / "Animation.json").is_file():
        return False
    if not _PAGE_FILE_RE.match(f"{path.stem}.json"):
        return False

    pages = discover_spritemap_pages(directory)
    if len(pages) <= 1:
        return False

    for _, page_image in pages:
        if page_image is None:
            continue
        try:
            same = page_image.resolve() == path.resolve()
        except OSError:
            same = page_image.name == path.name
        # The first page in index order represents the whole set.
        return not same
    return False


def _resolve_page_image(json_path: Path) -> Optional[Path]:
    """Locate the bitmap belonging to a spritemap page.

    Prefers the ``meta.image`` filename declared inside the page, falling
    back to a sibling sharing the JSON's stem.
    """
    try:
        with open(json_path, "rb") as handle:
            page = json.loads(handle.read().decode("utf-8-sig"))
        declared = (page.get("meta") or {}).get("image")
    except Exception:
        declared = None

    if isinstance(declared, str) and declared:
        candidate = json_path.parent / declared
        if candidate.is_file():
            return candidate

    for extension in _PAGE_IMAGE_EXTENSIONS:
        candidate = json_path.with_suffix(extension)
        if candidate.is_file():
            return candidate
    return None


class AdobeSpritemapRenderer:
    """Render symbol animations from Adobe Animate spritemap exports.

    Loads the animation metadata, spritemap JSON, and atlas image on
    construction, then exposes methods to list symbols, render frames,
    and populate default FPS settings.

    Attributes:
        animation_path: Filesystem path to Animation.json.
        spritemap_json_path: Filesystem path to the spritemap JSON.
        atlas_image_path: Filesystem path to the atlas bitmap.
        animation_json: Parsed Animation.json dict.
        frame_rate: Frames-per-second from metadata (default 24).
        filter_single_frame: Whether to skip single-frame animations.
        filter_unused_symbols: Whether to hide symbols not used by the root
            animation timeline.
        sprite_atlas: ``SpriteAtlas`` instance for sprite lookup.
        symbols: ``Symbols`` instance for timeline/symbol management.
    """

    def __init__(
        self,
        animation_path: str,
        spritemap_json_path: str,
        atlas_image_path: str,
        canvas_size=None,
        resample=Image.BICUBIC,
        filter_single_frame: bool = True,
        filter_unused_symbols: bool = False,
        root_animation_only: bool = False,
        max_render_workers: Optional[int] = None,
    ):
        """Load animation metadata, spritemap JSON, and the atlas image.

        Args:
            animation_path: Path to Animation.json generated by Adobe Animate.
            spritemap_json_path: Path to the per-spritesheet JSON file.
            atlas_image_path: Path to the atlas bitmap.
            canvas_size: Optional ``(width, height)`` override for the render
                canvas; defaults to atlas dimensions.
            resample: Pillow resample filter for scaling operations.
            filter_single_frame: When ``True``, animations with only one frame
                are omitted from batch renders.
            filter_unused_symbols: When ``True``, symbols not referenced by the
                root animation timeline are excluded from batch operations.
            root_animation_only: When ``True``, only the root animation is
                included in batch operations; symbols and labels are excluded.
        """

        self.animation_path = animation_path
        self.max_render_workers = (
            default_render_workers()
            if max_render_workers is None
            else max(1, int(max_render_workers))
        )

        with open(animation_path, "r", encoding="utf-8") as animation_file:
            self.animation_json = normalize_animation_document(
                json.load(animation_file)
            )

        json_paths, image_paths = self._resolve_pages(
            animation_path, spritemap_json_path, atlas_image_path
        )
        # Kept as scalars for callers that still read these attributes.
        self.spritemap_json_path = str(json_paths[0]) if json_paths else None
        self.atlas_image_path = str(image_paths[0]) if image_paths else None
        self.spritemap_json_paths = [str(path) for path in json_paths]
        self.atlas_image_paths = [str(path) if path else None for path in image_paths]

        page_jsons: List[Dict[str, Any]] = []
        page_images: List[Optional[str]] = []
        for json_path, image_path in zip(json_paths, image_paths):
            if image_path is None:
                continue
            try:
                with open(json_path, "rb") as spritemap_file:
                    page_jsons.append(
                        json.loads(spritemap_file.read().decode("utf-8-sig"))
                    )
            except (OSError, ValueError):
                continue
            page_images.append(str(image_path))

        if canvas_size is None:
            canvas_size = _infer_canvas_size(
                self.animation_json,
                page_jsons,
                _largest_page_size(page_images),
            )
        self.frame_rate = self.animation_json.get("MD", {}).get("FRT", 24)
        self.filter_single_frame = filter_single_frame
        self.filter_unused_symbols = filter_unused_symbols
        self.root_animation_only = root_animation_only

        direct_children = collect_direct_child_symbols(self.animation_json)
        if direct_children:
            self._referenced_symbols = direct_children
        elif filter_unused_symbols:
            self._referenced_symbols = collect_referenced_symbols(self.animation_json)
        else:
            self._referenced_symbols = None
        self.sprite_atlas = SpriteAtlas(
            page_jsons, page_images, canvas_size, resample
        )
        self.symbols = Symbols(self.animation_json, self.sprite_atlas, canvas_size)

    @staticmethod
    def _resolve_pages(
        animation_path: str,
        spritemap_json_path: Union[str, Sequence[str], None],
        atlas_image_path: Union[str, Sequence[str], None],
    ) -> Tuple[List[Path], List[Optional[Path]]]:
        """Work out which spritemap pages this render should cover.

        An explicit sequence is honoured as-is.  A single page path is
        expanded to every sibling ``spritemap*.json`` so multi-sheet exports
        render as one animation instead of once per sheet with most sprites
        missing.  Passing nothing discovers pages beside ``Animation.json``.
        """

        def _listify(value: Any) -> List[Any]:
            if value is None:
                return []
            if isinstance(value, (str, Path)):
                return [value]
            if isinstance(value, Sequence):
                return list(value)
            return [value]

        json_values = _listify(spritemap_json_path)
        image_values = _listify(atlas_image_path)

        if len(json_values) > 1 or (json_values and len(image_values) > 1):
            paths = [Path(value) for value in json_values]
            images: List[Optional[Path]] = [
                Path(value) if value is not None else None for value in image_values
            ]
            while len(images) < len(paths):
                images.append(_resolve_page_image(paths[len(images)]))
            return paths, images[: len(paths)]

        directory = (
            Path(json_values[0]).parent
            if json_values
            else Path(animation_path).parent
        )
        discovered = discover_spritemap_pages(directory)

        if discovered:
            paths = [json_path for json_path, _ in discovered]
            images = [image_path for _, image_path in discovered]
            # Honour an explicitly supplied image for its own page, so a
            # caller pointing at a renamed/relocated sheet still wins.
            if json_values and image_values and image_values[0] is not None:
                target = Path(json_values[0]).resolve()
                for index, json_path in enumerate(paths):
                    if json_path.resolve() == target:
                        images[index] = Path(image_values[0])
                        break
            return paths, images

        if json_values:
            single = Path(json_values[0])
            image = (
                Path(image_values[0])
                if image_values and image_values[0] is not None
                else _resolve_page_image(single)
            )
            return [single], [image]
        return [], []

    def get_root_animation_name(self) -> Optional[str]:
        """Return the display name of the root animation, if available.

        The root animation is defined by the top-level ``AN`` section of
        the Animation.json document.  Its display name comes from ``AN.SN``
        (the symbol name) with a fallback to ``AN.N`` (the internal name).

        Returns:
            The root animation name, or ``None`` when the document has no
            ``AN`` section.
        """
        an = self.animation_json.get("AN", {})
        return an.get("SN") or an.get("N") or None

    def is_symbol_referenced(self, symbol_name: str) -> bool:
        """Check whether a symbol is used by the root animation timeline.

        Always returns ``True`` when ``filter_unused_symbols`` is disabled.

        Args:
            symbol_name: The symbol name to check.

        Returns:
            True if the symbol is transitively referenced by the root
            animation, or if filtering is disabled.
        """
        if self._referenced_symbols is None:
            return True
        return symbol_name in self._referenced_symbols

    def list_symbol_names(self, include_all: bool = False) -> List[str]:
        """Return symbol names defined in the animation document.

        Args:
            include_all: When ``True``, return every symbol regardless of
                the ``filter_unused_symbols`` setting.

        Returns:
            List of symbol name strings.
        """
        names = [
            symbol.get("SN")
            for symbol in self.animation_json.get("SD", {}).get("S", [])
            if symbol.get("SN")
        ]
        if include_all or self._referenced_symbols is None:
            return names
        return [n for n in names if n in self._referenced_symbols]

    def build_animation_frames(
        self,
    ) -> Dict[str, List[Tuple[str, Image.Image, Tuple[int, int, int, int, int, int]]]]:
        """Render frames for every symbol and timeline label at once.

        All rendered frames are held in memory simultaneously.  Prefer
        :meth:`iter_animations` for large spritesheets unless editor
        composites require cross-animation frame access.

        Symbols and labels that resolve to a single frame are skipped when
        ``filter_single_frame`` is enabled.

        Returns:
            Dict mapping folder/label names to lists of frame tuples. Each
            tuple contains ``(frame_name, image, bounds)`` where bounds is
            ``(x, y, width, height, offset_x, offset_y)``.
        """

        animations: Dict[
            str, List[Tuple[str, Image.Image, Tuple[int, int, int, int, int, int]]]
        ] = {}

        # Render the root animation (full AN timeline) if it exists
        root_name = self.get_root_animation_name()
        if root_name:
            root_frames = self._render_symbol_frames(None)
            if root_frames:
                if not self.filter_single_frame or len(root_frames) > 1:
                    animations.setdefault(root_name, []).extend(root_frames)

        if not self.root_animation_only:
            for symbol_name in self.list_symbol_names():
                frames = self._render_symbol_frames(symbol_name)
                if not frames:
                    continue
                if self.filter_single_frame and len(frames) <= 1:
                    continue
                folder_name = Utilities.strip_trailing_digits(symbol_name)
                animations.setdefault(folder_name, []).extend(frames)

            for label in self.symbols.get_label_ranges(None):
                frames = self._render_symbol_frames(
                    None,
                    start_frame=label["start"],
                    end_frame=label["end"],
                    frame_name_prefix=label["name"],
                )
                if not frames:
                    continue
                if self.filter_single_frame and len(frames) <= 1:
                    continue
                folder_name = label["name"]
                animations.setdefault(folder_name, []).extend(frames)

        return animations

    #: Shape of a single rendered frame: ``(name, PIL Image, bounds_6tuple)``.
    FrameTuple = Tuple[str, Image.Image, Tuple[int, int, int, int, int, int]]

    def iter_animations(
        self,
    ) -> Generator[
        Tuple[str, Iterator["AdobeSpritemapRenderer.FrameTuple"]],
        None,
        None,
    ]:
        """Yield ``(folder_name, frame_iterator)`` one animation at a time.

        Each ``frame_iterator`` is a lazy generator that renders frames
        one at a time via ``_iter_symbol_frames``.  Only one compact
        canvas is alive at any moment, keeping rendering memory at O(1)
        rather than O(N) frames.

        The caller **must fully consume** (or discard) the ``frame_iterator``
        before advancing this outer generator to the next animation.

        Yields:
            Tuples of ``(folder_name, frame_iterator)`` where
            ``frame_iterator`` yields ``(frame_name, image, bounds)``.
        """
        root_name = self.get_root_animation_name()
        if root_name:
            total = self.symbols.length(None)
            if not self.filter_single_frame or total > 1:
                yield root_name, self._iter_symbol_frames(None)

        if not self.root_animation_only:
            for symbol_name in self.list_symbol_names():
                total = self.symbols.length(symbol_name)
                if total == 0:
                    continue
                if self.filter_single_frame and total <= 1:
                    continue
                folder_name = Utilities.strip_trailing_digits(symbol_name)
                yield folder_name, self._iter_symbol_frames(symbol_name)

            for label in self.symbols.get_label_ranges(None):
                total = label["end"] - label["start"]
                if total <= 0:
                    continue
                if self.filter_single_frame and total <= 1:
                    continue
                yield label["name"], self._iter_symbol_frames(
                    None,
                    start_frame=label["start"],
                    end_frame=label["end"],
                    frame_name_prefix=label["name"],
                )

    def _render_symbol_frames(
        self,
        symbol_name: Optional[str],
        start_frame: int = 0,
        end_frame: Optional[int] = None,
        frame_name_prefix: Optional[str] = None,
    ):
        """Render a contiguous range of frames for a symbol or timeline label.

        Uses a three-phase strategy to minimise memory consumption:

        1. **Bounds pass** — walks the symbol tree with transform math only
           (no images allocated) to compute the tightest viewport that
           contains every frame in the range.
        2. **Compact render pass** — renders each frame onto a canvas sized
           to just the viewport instead of the full inferred canvas.
        3. **Pixel crop pass** — computes the pixel-content union bounding
           box across all rendered frames, then crops each frame to that
           box and closes the intermediate compact canvas.

        Used by ``build_animation_frames``.  For low-memory streaming,
        see ``_iter_symbol_frames`` which omits Phase 3.

        Args:
            symbol_name: Name of the symbol, or ``None`` for the root timeline.
            start_frame: First frame index to render (inclusive).
            end_frame: Last frame index (exclusive); defaults to total length.
            frame_name_prefix: Prefix for generated frame names.

        Returns:
            List of ``(name, image, bounds)`` tuples, or empty if no valid
            frames exist.
        """

        total_frames = self.symbols.length(symbol_name)
        if total_frames == 0:
            return []

        if end_frame is None or end_frame > total_frames:
            end_frame = total_frames

        if start_frame >= end_frame:
            return []

        # Phase 1 renders each frame at its own bounds rather than at the
        # animation-wide union, so the intermediate buffer costs the sum of
        # the frames' real content instead of frame_count * union_area.
        per_frame = self.symbols.iter_frame_bounds(symbol_name, start_frame, end_frame)

        # Empty frames are kept (as ``None`` content): they still occupy a
        # slot in the timeline, and dropping them would shorten the
        # animation and shift every later frame's timing.
        tight: List[Tuple[int, Optional[Image.Image], Tuple[int, int]]] = []
        boxes: List[Tuple[int, int, int, int]] = []

        for offset, frame_index in enumerate(range(start_frame, end_frame)):
            bounds = per_frame[offset]
            if bounds is None:
                tight.append((offset, None, (0, 0)))
                continue
            frame_image = self.symbols.render_symbol_compact(
                symbol_name, frame_index, bounds
            )
            if frame_image is None:
                continue
            bbox = frame_image.getbbox()
            if bbox is None:
                frame_image.close()
                tight.append((offset, None, (0, 0)))
                continue
            # Trim to actual pixels straight away, then track the union in
            # canvas coordinates so every frame can share a final crop.
            content = frame_image.crop(bbox)
            frame_image.close()
            origin = (bounds[0] + bbox[0], bounds[1] + bbox[1])
            tight.append((offset, content, origin))
            boxes.append(
                (
                    origin[0],
                    origin[1],
                    origin[0] + content.width,
                    origin[1] + content.height,
                )
            )

        extent = union_excluding_outliers(boxes)
        if not tight or extent is None:
            return []

        min_x, min_y, max_x, max_y = extent
        final_width = max(1, int(max_x - min_x))
        final_height = max(1, int(max_y - min_y))
        prefix = frame_name_prefix or (symbol_name if symbol_name else "timeline")

        rendered_frames: List[
            Tuple[str, Image.Image, Tuple[int, int, int, int, int, int]]
        ] = []
        for offset, content, origin in tight:
            canvas = Image.new("RGBA", (final_width, final_height), (0, 0, 0, 0))
            if content is not None:
                canvas.paste(
                    content,
                    (int(origin[0] - min_x), int(origin[1] - min_y)),
                )
                content.close()
            rendered_frames.append(
                (
                    f"{prefix}_{offset:04d}",
                    canvas,
                    (0, 0, final_width, final_height, 0, 0),
                )
            )

        return rendered_frames

    def _iter_symbol_frames(
        self,
        symbol_name: Optional[str],
        start_frame: int = 0,
        end_frame: Optional[int] = None,
        frame_name_prefix: Optional[str] = None,
    ) -> Generator[
        Tuple[str, Image.Image, Tuple[int, int, int, int, int, int]],
        None,
        None,
    ]:
        """Yield rendered frames one at a time for a symbol or label.

        Like ``_render_symbol_frames`` but renders lazily: only one
        compact canvas is alive at any moment.  The Phase 3 pixel-level
        union crop from ``_render_symbol_frames`` is omitted so frames can
        be yielded immediately.  Downstream callers (e.g.
        ``pad_frames_to_canvas`` and the GIF exporter ``crop_option``)
        handle size normalisation.

        Args:
            symbol_name: Name of the symbol, or ``None`` for the root timeline.
            start_frame: First frame index to render (inclusive).
            end_frame: Last frame index (exclusive); defaults to total length.
            frame_name_prefix: Prefix for generated frame names.

        Yields:
            ``(frame_name, pil_image, bounds_tuple)`` for each rendered frame.
        """
        total_frames = self.symbols.length(symbol_name)
        if total_frames == 0:
            return

        if end_frame is None or end_frame > total_frames:
            end_frame = total_frames

        if start_frame >= end_frame:
            return

        # The bounds pass is geometric: it covers every sprite the timeline
        # *references*, including ones that never draw (placed off-canvas,
        # fully masked, or alpha'd out). Sizing the shared canvas from that
        # lets a single stray sprite inflate an entire animation — on real
        # exports by 10x or more. So each frame is rendered at its geometric
        # box, then immediately trimmed to the pixels that actually landed,
        # and only those trimmed boxes decide the canvas.
        #
        # The true canvas is therefore not known until every frame has been
        # rendered. Frames are yielded with their absolute canvas-space
        # origin and an unresolved placement; ``resolve_frame_placements``
        # rewrites them once the real union is known.
        per_frame = self.symbols.iter_frame_bounds(symbol_name, start_frame, end_frame)
        prefix = frame_name_prefix or (symbol_name if symbol_name else "timeline")

        def render_one(offset: int):
            """Render frame *offset*, trimmed to the pixels that drew."""
            bounds = per_frame[offset]
            frame_name = f"{prefix}_{offset:04d}"
            if bounds is None:
                # An empty frame still occupies a slot in the timeline;
                # dropping it would shorten the animation and shift timing.
                return (
                    frame_name,
                    Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                    FramePlacement(0, 0, 0, 0),
                )
            frame_image = self.symbols.render_symbol_compact(
                symbol_name, start_frame + offset, bounds
            )
            if frame_image is None:
                return None
            bbox = frame_image.getbbox()
            if bbox is None:
                frame_image.close()
                return (
                    frame_name,
                    Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                    FramePlacement(0, 0, 0, 0),
                )
            content = frame_image.crop(bbox)
            frame_image.close()
            return (
                frame_name,
                content,
                FramePlacement(bounds[0] + bbox[0], bounds[1] + bbox[1], 0, 0),
            )

        total = end_frame - start_frame
        workers = self._render_workers(per_frame)

        if workers <= 1:
            for offset in range(total):
                result = render_one(offset)
                if result is not None:
                    yield result
            return

        # Bounded look-ahead: never more than `workers` frames in flight, so
        # concurrency costs a handful of canvases rather than the whole
        # animation, and results still come out in timeline order.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending: "deque" = deque()
            next_offset = 0
            while next_offset < total and len(pending) < workers:
                pending.append(pool.submit(render_one, next_offset))
                next_offset += 1
            while pending:
                result = pending.popleft().result()
                if next_offset < total:
                    pending.append(pool.submit(render_one, next_offset))
                    next_offset += 1
                if result is not None:
                    yield result

    def _render_workers(self, per_frame: Sequence[Optional[Tuple]]) -> int:
        """Choose a thread count for rendering *per_frame*.

        PIL releases the GIL inside its C imaging routines, so threads give
        real parallelism here. The count is capped by how much frame data may
        be in flight at once — concurrency must not undo the memory work by
        keeping many large canvases alive simultaneously.
        """
        if self.max_render_workers == 1:
            return 1

        sizes = [
            (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
            for bounds in per_frame
            if bounds is not None
        ]
        if len(sizes) < 2:
            return 1

        sizes.sort()
        typical = sizes[int(0.9 * (len(sizes) - 1))] * 4  # bytes as RGBA
        affordable = max(1, int(INFLIGHT_FRAME_BUDGET // max(1, typical)))
        return max(1, min(self.max_render_workers, affordable, len(sizes)))

    def ensure_animation_defaults(self, settings_manager, spritesheet_name):
        """Populate animation duration defaults in the settings manager if missing.

        Iterates over all symbols and timeline labels and ensures each has an
        entry in ``settings_manager.animation_settings`` with at least a
        ``duration`` key (in milliseconds).

        Args:
            settings_manager: A settings manager exposing ``animation_settings``.
            spritesheet_name: Base name used to construct full setting keys.
        """
        # Convert fps to milliseconds for default duration
        default_duration_ms = (
            max(1, round(1000 / self.frame_rate)) if self.frame_rate > 0 else 42
        )

        # Ensure defaults for the root animation
        root_name = self.get_root_animation_name()
        if root_name:
            full_name = f"{spritesheet_name}/{root_name}"
            sprite_settings = settings_manager.animation_settings.setdefault(
                full_name, {}
            )
            sprite_settings.setdefault("duration", default_duration_ms)

        if not self.root_animation_only:
            for animation_name in self.list_symbol_names():
                folder_name = Utilities.strip_trailing_digits(animation_name)
                full_name = f"{spritesheet_name}/{folder_name}"
                sprite_settings = settings_manager.animation_settings.setdefault(
                    full_name, {}
                )
                sprite_settings.setdefault("duration", default_duration_ms)

            for label in self.symbols.get_label_ranges(None):
                label_name = label["name"]
                full_name = f"{spritesheet_name}/{label_name}"
                sprite_settings = settings_manager.animation_settings.setdefault(
                    full_name, {}
                )
                sprite_settings.setdefault("duration", default_duration_ms)

    def render_animation(self, target):
        """Render frames for a symbol or timeline label.

        Args:
            target: Either a symbol name string, or a dict with ``type`` and
                ``value`` keys (type may be ``"symbol"`` or ``"timeline_label"``).

        Returns:
            List of ``(name, image, bounds)`` tuples for the requested target.
        """

        target_type, target_value = self._normalize_target(target)

        if target_type == "root_animation":
            root_name = self.get_root_animation_name()
            return self._render_symbol_frames(None, frame_name_prefix=root_name)

        if target_type == "timeline_label":
            label_range = self.symbols.get_label_range(None, target_value)
            if not label_range:
                return []
            return self._render_symbol_frames(
                None,
                start_frame=label_range["start"],
                end_frame=label_range["end"],
                frame_name_prefix=target_value,
            )

        return self._render_symbol_frames(target_value)

    def _normalize_target(self, target):
        """Normalize a render target to a ``(type, value)`` pair.

        Args:
            target: A string (treated as symbol name) or dict with ``type``
                and ``value`` keys.

        Returns:
            Tuple of ``(target_type, target_value)``.
        """

        if isinstance(target, dict):
            return target.get("type", "symbol"), target.get("value")
        return "symbol", target

    def close(self) -> None:
        """Release renderer resources.

        Closes the ``Symbols`` and ``SpriteAtlas`` instances, then drops the
        parsed animation JSON so memory can be reclaimed.
        """

        if getattr(self, "symbols", None):
            try:
                self.symbols.close()
            except Exception:
                pass
            finally:
                self.symbols = None

        if getattr(self, "sprite_atlas", None):
            try:
                self.sprite_atlas.close()
            except Exception:
                pass
            finally:
                self.sprite_atlas = None

        self.animation_json = None


def _infer_canvas_size(animation_json, spritemap_json, atlas_size):
    """Compute a canvas size large enough to contain all transformed sprites.

    Scans every symbol timeline and atlas sprite instance, applying their
    transforms to determine the maximum extent any sprite can reach. The
    returned dimensions ensure no sprite is clipped during rendering.

    Args:
        animation_json: Normalized Animation.json dict.
        spritemap_json: Parsed spritemap JSON with sprite regions.
        atlas_size: Default ``(width, height)`` from the atlas image.

    Returns:
        A ``(width, height)`` tuple at least as large as ``atlas_size`` and
        sufficient to hold all transformed sprite bounds.
    """

    sprite_sizes = _collect_sprite_sizes(spritemap_json)
    if not sprite_sizes:
        return _clamp_canvas(atlas_size)

    timelines = _collect_timelines(animation_json)
    if not timelines:
        return _clamp_canvas(atlas_size)

    bounds_cache: Dict[Optional[str], Optional[Tuple[float, float, float, float]]] = {}
    visiting: set[Optional[str]] = set()

    def symbol_bounds(
        symbol_name: Optional[str],
    ) -> Optional[Tuple[float, float, float, float]]:
        """Return the cumulative bounding box for all frames of a symbol.

        Recursively resolves nested symbol instances and caches results to
        avoid redundant traversals. Cyclic references are detected via the
        ``visiting`` set and return ``None`` to break infinite loops.

        Args:
            symbol_name: Name of the symbol, or ``None`` for the root timeline.

        Returns:
            A ``(min_x, min_y, max_x, max_y)`` tuple, or ``None`` if the
            symbol has no renderable content.
        """

        if symbol_name in bounds_cache:
            return bounds_cache[symbol_name]
        if symbol_name in visiting:
            return None
        visiting.add(symbol_name)

        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for layer in timelines.get(symbol_name, []):
            for frame in layer.get("FR", []):
                for element in frame.get("E", []):
                    bounds = _element_bounds(element, sprite_sizes, symbol_bounds)
                    if not bounds:
                        continue
                    min_x = min(min_x, bounds[0])
                    min_y = min(min_y, bounds[1])
                    max_x = max(max_x, bounds[2])
                    max_y = max(max_y, bounds[3])

        visiting.remove(symbol_name)

        if min_x == float("inf"):
            bounds_cache[symbol_name] = None
        else:
            bounds_cache[symbol_name] = (min_x, min_y, max_x, max_y)
        return bounds_cache[symbol_name]

    for symbol_name in timelines.keys():
        symbol_bounds(symbol_name)

    max_abs_x = 0.0
    max_abs_y = 0.0
    for bounds in bounds_cache.values():
        if not bounds:
            continue
        min_x, min_y, max_x, max_y = bounds
        max_abs_x = max(max_abs_x, abs(min_x), abs(max_x))
        max_abs_y = max(max_abs_y, abs(min_y), abs(max_y))

    if max_abs_x == 0 and max_abs_y == 0:
        return _clamp_canvas(atlas_size)

    padding = 32.0
    inferred_width = int(math.ceil(max_abs_x * 2.0 + padding))
    inferred_height = int(math.ceil(max_abs_y * 2.0 + padding))
    return _clamp_canvas(
        (
            max(atlas_size[0], inferred_width),
            max(atlas_size[1], inferred_height),
        )
    )


def _clamp_canvas(size: Tuple[int, int]) -> Tuple[int, int]:
    """Return *size* as a sane positive ``(width, height)``.

    The inferred canvas is a coordinate envelope, not an allocation: it sets
    where content is centred, and shrinking it would push content past the
    origin where viewport clamping silently crops it. The real allocation
    guard lives in ``Symbols.render_symbol_compact``, which caps the compact
    viewport that actually gets allocated.
    """
    return (max(1, int(size[0])), max(1, int(size[1])))


def _largest_page_size(page_images: Sequence[Optional[str]]) -> Tuple[int, int]:
    """Return the largest ``(width, height)`` across every page image.

    Reads headers only — ``Image.open`` does not decode pixel data.
    """
    width = height = 0
    for path in page_images:
        if not path:
            continue
        try:
            with Image.open(path) as handle:
                page_width, page_height = handle.size
        except Exception:
            continue
        width = max(width, page_width)
        height = max(height, page_height)
    return (width or 1, height or 1)


def _collect_sprite_sizes(
    spritemap_json: Union[Dict[str, Any], Sequence[Dict[str, Any]]],
) -> Dict[str, Tuple[int, int]]:
    """Build a mapping of sprite names to their pixel dimensions.

    Args:
        spritemap_json: One parsed spritemap dict, or a sequence of page
            dicts whose sprites are merged into a single namespace.

    Returns:
        Dict mapping each sprite name to its ``(width, height)`` in pixels.
    """

    pages: Sequence[Dict[str, Any]]
    if isinstance(spritemap_json, dict):
        pages = [spritemap_json]
    else:
        pages = list(spritemap_json or [])

    sizes: Dict[str, Tuple[int, int]] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        for sprite in page.get("ATLAS", {}).get("SPRITES", []):
            data = sprite.get("SPRITE", sprite)
            name = data.get("name")
            if not name or name in sizes:
                continue
            sizes[name] = (int(data.get("w", 0)), int(data.get("h", 0)))
    return sizes


def _collect_timelines(animation_json: Dict[str, Any]):
    """Extract all symbol timelines from a normalized animation document.

    Args:
        animation_json: Normalized Animation.json dict with ``SD`` (symbol
            dictionary) and ``AN`` (root animation) sections.

    Returns:
        Dict mapping symbol names (or ``None`` for the root timeline) to
        their layer lists.
    """

    timelines: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for symbol in animation_json.get("SD", {}).get("S", []):
        name = symbol.get("SN")
        if not name:
            continue
        layers = symbol.get("TL", {}).get("L", [])
        timelines[name] = layers
    timelines[None] = animation_json.get("AN", {}).get("TL", {}).get("L", [])
    return timelines


def _element_bounds(element, sprite_sizes, symbol_bounds_fn):
    """Compute the transformed bounding box for a single frame element.

    Handles both atlas sprite instances (``ASI``) and nested symbol instances
    (``SI``), recursively resolving child symbol bounds when necessary.

    Args:
        element: A frame element dict potentially containing ``ASI`` or ``SI``.
        sprite_sizes: Dict mapping sprite names to ``(width, height)``.
        symbol_bounds_fn: Callable accepting a symbol name and returning its
            cumulative bounds, used for recursive symbol resolution.

    Returns:
        A ``(min_x, min_y, max_x, max_y)`` tuple, or ``None`` if the element
        cannot be resolved.
    """

    if not isinstance(element, dict):
        return None
    if "ASI" in element:
        atlas = element["ASI"]
        sprite_name = atlas.get("N")
        if not sprite_name:
            return None
        sprite_size = sprite_sizes.get(sprite_name)
        if not sprite_size:
            return None
        matrix = TransformMatrix.parse(atlas.get("M3D"))
        return _transform_sprite(sprite_size, matrix)
    if "SI" in element:
        instance = element["SI"]
        child_name = instance.get("SN")
        if not child_name:
            return None
        child_bounds = symbol_bounds_fn(child_name)
        if not child_bounds:
            return None
        matrix = TransformMatrix.parse(instance.get("M3D"))
        return _transform_bounds(child_bounds, matrix)
    return None


def _transform_sprite(sprite_size: Tuple[int, int], matrix: TransformMatrix):
    """Apply a transform to an origin-anchored sprite and return its bounds.

    Args:
        sprite_size: ``(width, height)`` of the sprite in pixels.
        matrix: Affine transform to apply.

    Returns:
        Transformed ``(min_x, min_y, max_x, max_y)`` bounding box.
    """

    width, height = sprite_size
    return _transform_bounds((0.0, 0.0, float(width), float(height)), matrix)


def _transform_bounds(
    bounds: Tuple[float, float, float, float], matrix: TransformMatrix
) -> Tuple[float, float, float, float]:
    """Transform a bounding box and return its axis-aligned enclosure.

    Applies the affine transform to each corner of the input rectangle and
    computes the smallest axis-aligned rectangle containing the results.

    Args:
        bounds: ``(min_x, min_y, max_x, max_y)`` rectangle.
        matrix: Affine transform to apply.

    Returns:
        Transformed ``(min_x, min_y, max_x, max_y)`` bounding box.
    """

    min_x, min_y, max_x, max_y = bounds
    corners = (
        (min_x, min_y),
        (min_x, max_y),
        (max_x, min_y),
        (max_x, max_y),
    )
    a, b, c, d, e, f = matrix.m.reshape(-1)[:6]
    transformed = ((a * x + b * y + c, d * x + e * y + f) for (x, y) in corners)
    xs, ys = zip(*transformed)
    return (min(xs), min(ys), max(xs), max(ys))
