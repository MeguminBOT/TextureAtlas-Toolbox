"""Symbol timeline renderer for Adobe Spritemap support.

Provides the ``Symbols`` class which manages nested symbol timelines parsed
from Animation.json and renders individual frames by compositing sprites and
recursively evaluating symbol instances.
"""

from __future__ import annotations

import hashlib
import math
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageChops

from .transform_matrix import TransformMatrix
from .color_effect import ColorEffect
from .metadata import compute_layers_length, extract_label_ranges_from_layers

#: Absolute ceiling on a single rendered frame, in pixels (~1 GB as RGBA).
#: Viewports are already clipped to the canvas, so this only trips on a
#: genuinely degenerate transform — it is a crash guard, not a size policy.
MAX_RENDER_PIXELS = 256 * 1024 * 1024

IDENTITY_M3D = [
    1,
    0,
    0,
    0,
    0,
    1,
    0,
    0,
    0,
    0,
    1,
    0,
    0,
    0,
    0,
    1,
]


def _union_bounds(
    a: Optional[Tuple[int, int, int, int]],
    b: Optional[Tuple[int, int, int, int]],
) -> Optional[Tuple[int, int, int, int]]:
    """Return the axis-aligned union of two bounding boxes.

    Either argument may be ``None``; ``None`` values are treated as empty.
    """
    if a is None:
        return b
    if b is None:
        return a
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    )


class Symbols:
    """Manage and render nested symbol timelines from Adobe Animate exports.

    Parses symbol definitions from Animation.json and provides methods to
    query frame counts, render individual frames, and retrieve timeline label
    metadata.

    Attributes:
        background_color: RGBA tuple used when creating new canvases.
        canvas_size: ``(width, height)`` for rendered frames.
        sprite_atlas: ``SpriteAtlas`` instance for sprite lookup.
        timelines: Dict mapping symbol names (or ``None`` for root) to layer
            lists.
        label_map: Dict mapping symbol names to extracted label ranges.
        center_in_canvas: Pre-built translation centering content on canvas.
    """

    def __init__(self, animation_json, sprite_atlas, canvas_size):
        """Parse symbol timelines and prepare lookup tables for rendering.

        Args:
            animation_json: Parsed Animation.json dict.
            sprite_atlas: ``SpriteAtlas`` for sprite lookup.
            canvas_size: ``(width, height)`` for rendered frames.

        Raises:
            ValueError: If a duplicate symbol name is encountered.
        """

        self.background_color = (0, 0, 0, 0)
        self.canvas_size = canvas_size
        self.sprite_atlas = sprite_atlas
        self.timelines = {}

        for symbol in animation_json.get("SD", {}).get("S", []):
            name = symbol.get("SN")
            if name in self.timelines:
                raise ValueError(f"Symbol `{name}` is not unique")
            self.timelines[name] = symbol.get("TL", {}).get("L", [])

        self.timelines[None] = animation_json.get("AN", {}).get("TL", {}).get("L", [])
        self.label_map: Dict[Optional[str], List[Dict[str, int]]] = {
            name: extract_label_ranges_from_layers(layers)
            for name, layers in self.timelines.items()
        }
        self.center_in_canvas = TransformMatrix(
            c=canvas_size[0] // 2, f=canvas_size[1] // 2
        )
        self._length_cache: Dict[Optional[str], int] = {}

    def length(self, symbol_name):
        """Return the total frame count for the specified symbol.

        Memoized: ``_resolve_instance_frame`` asks for this once per element
        per frame, and recomputing it walks every layer of the timeline.

        Args:
            symbol_name: Symbol name, or ``None`` for the root timeline.

        Returns:
            Number of frames, or 0 if the symbol does not exist.
        """
        cached = self._length_cache.get(symbol_name, -1)
        if cached >= 0:
            return cached
        value = compute_layers_length(self.timelines.get(symbol_name))
        self._length_cache[symbol_name] = value
        return value

    def render_symbol(self, name, frame_index):
        """Render a single frame of a symbol into a new RGBA image.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            frame_index: Zero-based frame index to render.

        Returns:
            An RGBA PIL ``Image`` of ``canvas_size`` dimensions.
        """

        canvas = Image.new("RGBA", self.canvas_size, color=self.background_color)
        self._render_symbol(
            canvas, name, frame_index, self.center_in_canvas, ColorEffect()
        )
        return canvas

    def compute_frame_bounds(
        self, name: Optional[str], frame_index: int
    ) -> Optional[Tuple[int, int, int, int]]:
        """Compute the pixel bounding box for a single frame without rendering.

        Walks the symbol tree and applies transform math to each sprite to
        determine where it would land on the full canvas.  No images are
        created, making this very cheap compared to ``render_symbol``.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            frame_index: Zero-based frame index.

        Returns:
            ``(min_x, min_y, max_x, max_y)`` in full-canvas coordinates,
            or ``None`` if the frame contains no visible sprites.
        """
        return self._compute_bounds(name, frame_index, self.center_in_canvas)

    def compute_union_bounds(
        self,
        name: Optional[str],
        start_frame: int,
        end_frame: int,
        padding: int = 2,
    ) -> Optional[Tuple[int, int, int, int]]:
        """Compute the union bounding box across a contiguous range of frames.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            start_frame: First frame index (inclusive).
            end_frame: Last frame index (exclusive).
            padding: Extra pixels around the result for anti-alias safety.

        Returns:
            ``(min_x, min_y, max_x, max_y)`` encompassing all frames,
            or ``None`` if every frame is empty.
        """
        union: Optional[Tuple[int, int, int, int]] = None
        for frame_index in range(start_frame, end_frame):
            frame_bounds = self._compute_bounds(
                name, frame_index, self.center_in_canvas
            )
            union = _union_bounds(union, frame_bounds)

        if union is None:
            return None

        return self._clip_to_canvas(union, padding)

    def _clip_to_canvas(
        self,
        bounds: Tuple[int, int, int, int],
        padding: int,
    ) -> Tuple[int, int, int, int]:
        """Pad *bounds* then clip them to the canvas rectangle.

        Sprites are already dropped by ``SpriteAtlas.get_sprite`` once they
        fall outside the canvas, so clipping here loses nothing that could
        have been drawn. It does stop an extreme transform from producing a
        viewport far larger than any renderable area.
        """
        min_x = max(0, bounds[0] - padding)
        min_y = max(0, bounds[1] - padding)
        max_x = min(self.canvas_size[0], bounds[2] + padding)
        max_y = min(self.canvas_size[1], bounds[3] + padding)
        return (min_x, min_y, max(min_x + 1, max_x), max(min_y + 1, max_y))

    def iter_frame_bounds(
        self,
        name: Optional[str],
        start_frame: int,
        end_frame: int,
        padding: int = 2,
    ) -> List[Optional[Tuple[int, int, int, int]]]:
        """Return per-frame bounds for a range, in one traversal.

        ``compute_union_bounds`` discards the individual frame boxes it
        computes.  Callers that render each frame at its own tight size need
        them, and recomputing would double the (recursive) bounds work.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            start_frame: First frame index (inclusive).
            end_frame: Last frame index (exclusive).
            padding: Extra pixels around each box for anti-alias safety.

        Returns:
            List aligned with ``range(start_frame, end_frame)``; entries are
            ``None`` where the frame has no visible content.
        """
        per_frame: List[Optional[Tuple[int, int, int, int]]] = []
        for frame_index in range(start_frame, end_frame):
            bounds = self._compute_bounds(name, frame_index, self.center_in_canvas)
            if bounds is None:
                per_frame.append(None)
                continue
            per_frame.append(self._clip_to_canvas(bounds, padding))
        return per_frame

    def render_symbol_compact(
        self,
        name: Optional[str],
        frame_index: int,
        viewport: Tuple[int, int, int, int],
    ) -> Image.Image:
        """Render a frame onto a compact canvas covering only *viewport*.

        Instead of allocating a full-size canvas (e.g. 4096x4096) this
        creates a canvas sized to ``viewport`` and adjusts transforms so
        sprites land at the correct compact-canvas positions.  Clipping
        layers also use the compact size, dramatically reducing peak memory.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            frame_index: Zero-based frame index.
            viewport: ``(min_x, min_y, max_x, max_y)`` in full-canvas
                coordinates defining the region to render.

        Returns:
            An RGBA ``Image`` sized to the viewport.
        """
        vp_x, vp_y, vp_x2, vp_y2 = viewport
        compact_w = max(1, vp_x2 - vp_x)
        compact_h = max(1, vp_y2 - vp_y)

        # Hard allocation guard. A degenerate transform can produce a
        # viewport of essentially unbounded size; without this the render
        # below turns into a multi-gigabyte request that takes the process
        # down instead of producing a (clipped) frame.
        if compact_w * compact_h > MAX_RENDER_PIXELS:
            warnings.warn(
                f"Symbol `{name}` frame {frame_index} wants a "
                f"{compact_w}x{compact_h} canvas; clipping to fit "
                f"{MAX_RENDER_PIXELS} pixels"
            )
            ratio = math.sqrt(MAX_RENDER_PIXELS / float(compact_w * compact_h))
            compact_w = max(1, int(compact_w * ratio))
            compact_h = max(1, int(compact_h * ratio))

        # The compact size travels down the call chain as an argument rather
        # than being written onto self/sprite_atlas. Mutate-and-restore
        # worked only while one frame rendered at a time; passing it makes
        # concurrent frame renders independent.
        clip = (compact_w, compact_h)

        # Shift the center transform so full-canvas coords map to compact coords
        compact_center = TransformMatrix(
            c=self.canvas_size[0] // 2 - vp_x,
            f=self.canvas_size[1] // 2 - vp_y,
        )

        canvas = Image.new("RGBA", clip, color=self.background_color)
        self._render_symbol(
            canvas, name, frame_index, compact_center, ColorEffect(), clip
        )
        return canvas

    def frame_signature(self, name: Optional[str], frame_index: int) -> bytes:
        """Return a digest of everything that affects how a frame renders.

        Animate holds a keyframe for its whole ``DU`` span, so a timeline
        routinely resolves to the same picture for many consecutive frame
        indices. Two frames with the same signature composite the identical
        element tree and therefore produce identical pixels, so the second
        one need not be rendered or stored at all.

        The walk mirrors :meth:`_render_symbol` exactly — same layer order,
        same keyframe lookup, same clip handling, same recursion — and folds
        in every input that reaches the compositor: symbol identity, resolved
        child frame, transform, colour effect, and sprite name.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            frame_index: Zero-based frame index.

        Returns:
            A digest that is equal exactly when the render would be equal.
        """
        digest = hashlib.blake2b(digest_size=16)
        self._collect_signature(name, frame_index, digest, 0)
        return digest.digest()

    def _collect_signature(
        self,
        name: Optional[str],
        frame_index: int,
        digest: "hashlib._Hash",
        depth: int,
    ) -> None:
        """Fold one symbol's resolved state at *frame_index* into *digest*."""
        if depth > 64:
            # Matches the recursion guard elsewhere; a cycle would otherwise
            # spin here. Feeding a marker keeps distinct states distinct.
            digest.update(b"|cycle")
            return

        digest.update(b"|S")
        digest.update(str(name).encode("utf-8", "replace"))

        for layer_index, layer in enumerate(reversed(self.timelines.get(name, []))):
            frames = layer.get("FR", [])
            if not frames:
                continue

            low = 0
            high = len(frames) - 1
            while low != high:
                mid = (low + high + 1) // 2
                if frame_index < frames[mid]["I"]:
                    high = mid - 1
                else:
                    low = mid
            frame = frames[low]
            if not (frame["I"] <= frame_index < frame["I"] + frame["DU"]):
                continue

            # Layer identity and clip role change how the canvas stack is
            # built, so they belong in the signature even though they are
            # not per-element data.
            digest.update(b"|L")
            digest.update(str(layer_index).encode())
            digest.update(str(layer.get("LT")).encode())
            digest.update(str(layer.get("Clpb")).encode())
            digest.update(str(layer.get("LN")).encode())

            for element in frame.get("E", []):
                if "SI" in element:
                    instance = element["SI"]
                    element_name = instance.get("SN")
                    if not element_name:
                        continue
                    instance_frame = self._resolve_instance_frame(
                        element_name, instance, frame["I"], frame_index
                    )
                    digest.update(b"|I")
                    digest.update(repr(instance.get("M3D", IDENTITY_M3D)).encode())
                    digest.update(repr(instance.get("C")).encode())
                    self._collect_signature(
                        element_name, instance_frame, digest, depth + 1
                    )
                else:
                    atlas_instance = element.get("ASI", {})
                    digest.update(b"|A")
                    digest.update(str(atlas_instance.get("N")).encode())
                    digest.update(
                        repr(atlas_instance.get("M3D", IDENTITY_M3D)).encode()
                    )

    def _compute_bounds(
        self,
        name: Optional[str],
        frame_index: int,
        matrix: TransformMatrix,
    ) -> Optional[Tuple[int, int, int, int]]:
        """Recursively compute the bounding box for a symbol frame.

        Mirrors the traversal of :meth:`_render_symbol` but only performs
        coordinate math — no images are allocated or composited.
        Clipping-layer restrictions are intentionally ignored to keep
        things simple; the result may slightly overestimate the visible area.

        Args:
            name: Symbol name, or ``None`` for the root timeline.
            frame_index: Zero-based frame index.
            matrix: Accumulated affine transform from parent instances.

        Returns:
            ``(min_x, min_y, max_x, max_y)`` in canvas coordinates,
            or ``None`` if the frame contains no visible sprites.
        """
        combined: Optional[Tuple[int, int, int, int]] = None

        for layer in reversed(self.timelines.get(name, [])):
            frames = layer.get("FR", [])
            if not frames:
                continue

            # Binary search — identical to _render_symbol
            low = 0
            high = len(frames) - 1
            while low != high:
                mid = (low + high + 1) // 2
                if frame_index < frames[mid]["I"]:
                    high = mid - 1
                else:
                    low = mid
            frame = frames[low]
            if not (frame["I"] <= frame_index < frame["I"] + frame["DU"]):
                continue

            for element in frame.get("E", []):
                if "SI" in element:
                    instance = element["SI"]
                    element_name = instance.get("SN")
                    if not element_name:
                        continue
                    instance_frame = self._resolve_instance_frame(
                        element_name, instance, frame["I"], frame_index
                    )
                    transform = TransformMatrix.parse(instance.get("M3D", IDENTITY_M3D))
                    child_bounds = self._compute_bounds(
                        element_name, instance_frame, matrix @ transform
                    )
                    combined = _union_bounds(combined, child_bounds)
                elif "ASI" in element:
                    atlas_instance = element["ASI"]
                    sprite_name = atlas_instance.get("N")
                    if not sprite_name:
                        continue
                    transform = TransformMatrix.parse(
                        atlas_instance.get("M3D", IDENTITY_M3D)
                    )
                    sprite_bounds = self._compute_sprite_bounds(
                        sprite_name, matrix @ transform
                    )
                    combined = _union_bounds(combined, sprite_bounds)

        return combined

    def _compute_sprite_bounds(
        self,
        sprite_name: str,
        matrix: TransformMatrix,
    ) -> Optional[Tuple[int, int, int, int]]:
        """Compute a sprite's transformed bounding box from atlas metadata.

        Uses the same corner-transform math as ``SpriteAtlas.get_sprite``
        but without loading or cropping any pixel data.
        """
        info = self.sprite_atlas.sprite_info.get(sprite_name)
        if not info:
            return None

        box = info["box"]
        width = box[2] - box[0]
        height = box[3] - box[1]
        if info.get("rotated"):
            width, height = height, width

        corners = matrix.m @ np.array(
            [[0, width, 0, width], [0, 0, height, height], [1, 1, 1, 1]]
        )
        return (
            math.floor(float(min(corners[0]))),
            math.floor(float(min(corners[1]))),
            math.ceil(float(max(corners[0]))),
            math.ceil(float(max(corners[1]))),
        )

    def _render_symbol(self, canvas, name, frame_index, matrix, color, clip=None):
        """Recursively composite symbol layers onto an existing canvas.

        Handles nested symbol instances and clipping mask layers.

        Args:
            canvas: Target PIL ``Image`` to draw into.
            name: Symbol name, or ``None`` for root.
            frame_index: Frame index within the symbol's timeline.
            matrix: Accumulated affine transform.
            color: Accumulated colour effect.
            clip: ``(width, height)`` of the target canvas. Threaded through
                the recursion instead of read from shared state so parallel
                frame renders cannot clobber each other; defaults to the
                symbol-wide canvas size.
        """
        if clip is None:
            clip = self.canvas_size

        canvas_stack = []
        for layer in reversed(self.timelines.get(name, [])):
            frames = layer.get("FR", [])
            if not frames:
                continue

            low = 0
            high = len(frames) - 1
            while low != high:
                mid = (low + high + 1) // 2
                if frame_index < frames[mid]["I"]:
                    high = mid - 1
                else:
                    low = mid
            frame = frames[low]
            if not (frame["I"] <= frame_index < frame["I"] + frame["DU"]):
                continue

            if (layer.get("Clpb") and not canvas_stack) or layer.get("LT") == "Clp":
                canvas_stack.append(canvas)
                canvas = Image.new("RGBA", clip, color=(0, 0, 0, 0))

            for element in frame.get("E", []):
                if "SI" in element:
                    instance = element["SI"]
                    element_name = instance.get("SN")
                    if not element_name:
                        continue
                    instance_frame = self._resolve_instance_frame(
                        element_name,
                        instance,
                        frame["I"],
                        frame_index,
                    )
                    element_color = (
                        color @ ColorEffect.parse(instance["C"])
                        if "C" in instance
                        else color
                    )
                    transform = TransformMatrix.parse(instance.get("M3D", IDENTITY_M3D))
                    self._render_symbol(
                        canvas,
                        element_name,
                        instance_frame,
                        matrix @ transform,
                        element_color,
                        clip,
                    )
                else:
                    atlas_instance = element.get("ASI", {})
                    sprite_name = atlas_instance.get("N")
                    transform = TransformMatrix.parse(
                        atlas_instance.get("M3D", IDENTITY_M3D)
                    )
                    sprite, dest = self.sprite_atlas.get_sprite(
                        sprite_name, matrix @ transform, color, clip
                    )
                    if sprite is not None:
                        canvas.alpha_composite(sprite, dest=dest)

            if layer.get("LT") == "Clp":
                mask_canvas = canvas
                masked_canvas = canvas_stack.pop()
                base_canvas = canvas_stack.pop()

                mask_bbox = mask_canvas.getbbox()
                if mask_bbox is None:
                    warnings.warn(
                        f"Mask `{layer.get('LN')}` in symbol `{name}` is fully transparent"
                    )
                    base_canvas.alpha_composite(masked_canvas)
                else:
                    mask_canvas = mask_canvas.crop(mask_bbox)
                    masked_canvas = masked_canvas.crop(mask_bbox)
                    masked_alpha = masked_canvas.getchannel("A")

                    mask_alpha = np.array(mask_canvas.getchannel("A"))
                    mask_alpha = (
                        mask_alpha
                        if np.max(mask_alpha) == 0
                        else mask_alpha / np.max(mask_alpha) * 255
                    )
                    mask_alpha_arr = mask_alpha.clip(0, 255).astype("uint8")
                    try:
                        mask_alpha = Image.fromarray(mask_alpha_arr, "L")
                    except TypeError:
                        h, w = mask_alpha_arr.shape[:2]
                        mask_alpha = Image.frombytes(
                            "L", (w, h), np.ascontiguousarray(mask_alpha_arr).tobytes()
                        )
                    masked_canvas.putalpha(
                        ImageChops.multiply(masked_alpha, mask_alpha)
                    )
                    base_canvas.alpha_composite(masked_canvas, dest=mask_bbox[:2])

                canvas = base_canvas

    def _resolve_instance_frame(
        self,
        symbol_name: str,
        instance: dict,
        frame_start: int,
        parent_frame_index: int,
    ) -> int:
        """Return which frame of a nested symbol should render on a parent frame.

        Args:
            symbol_name: Name of the child symbol timeline.
            instance: Raw ``SI`` payload describing loop mode and offsets.
            frame_start: Parent key-frame index where the instance begins.
            parent_frame_index: Absolute frame index currently being rendered.

        Returns:
            Integer index within the child symbol timeline.
        """

        symbol_length = self.length(symbol_name)
        if symbol_length <= 0:
            return 0

        try:
            first_frame = int(instance.get("FF", 0))
        except (TypeError, ValueError):
            first_frame = 0
        first_frame = max(0, min(first_frame, symbol_length - 1))

        # MovieClip symbols are frozen at *first_frame* during extraction.
        # In non-swfRender mode (the standard game-engine convention) the
        # MC playhead is externally controlled and defaults to frame 0.
        # Graphic symbols use the parent-keyframe-relative offset together
        # with the loop mode (LP) to determine the child frame.
        symbol_type = (instance.get("ST") or "G").upper()
        if symbol_type == "MC":
            return first_frame

        offset = max(0, parent_frame_index - frame_start)

        loop_mode = instance.get("LP") or "LP"
        if isinstance(loop_mode, str):
            loop_mode = loop_mode.upper()
        else:
            loop_mode = "LP"

        if loop_mode == "SF":
            return first_frame

        target = first_frame + offset
        if loop_mode == "PO":
            return min(target, symbol_length - 1)

        if symbol_length == 0:
            return first_frame

        return target % symbol_length

    def get_label_ranges(self, symbol_name: Optional[str]):
        """Return all timeline labels for the requested symbol.

        Args:
            symbol_name: Symbol name, or ``None`` for the root timeline.

        Returns:
            List of dicts with ``name``, ``start``, and ``end`` keys.
        """
        return self.label_map.get(symbol_name, [])

    def get_label_range(self, symbol_name: Optional[str], label_name: str):
        """Return metadata for a specific timeline label.

        Args:
            symbol_name: Symbol name, or ``None`` for the root timeline.
            label_name: The label to look up.

        Returns:
            A dict with ``name``, ``start``, and ``end`` keys, or ``None`` if
            the label does not exist.
        """
        for entry in self.label_map.get(symbol_name, []):
            if entry["name"] == label_name:
                return entry
        return None

    def close(self) -> None:
        """Release atlas and timeline data.

        Drops the sprite atlas reference and clears timeline and label
        structures so associated memory can be reclaimed.
        """

        self.sprite_atlas = None
        self.timelines.clear()
        self.label_map.clear()
