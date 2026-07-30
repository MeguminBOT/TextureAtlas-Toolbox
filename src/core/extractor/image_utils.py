"""Image helper utilities shared across extractor components.

Provides conversion functions between PIL Images and NumPy arrays, bounding
box calculations, scaling, padding, and alpha channel manipulation.

Type Aliases:
    FrameSource: ``Union[Image.Image, np.ndarray]`` — frame data may be
        either a PIL Image or a NumPy array throughout the pipeline.
    BBox: ``Tuple[int, int, int, int]`` — bounding box as ``(left, top, right, bottom)``.
"""

from __future__ import annotations

from collections.abc import Sequence as _SequenceABC
from typing import List, NamedTuple, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

from utils.resampling import get_pil_resampling_filter


FrameSource = Union[Image.Image, np.ndarray]
BBox = Tuple[int, int, int, int]


def scale_image(
    image: Image.Image,
    size: float,
    resampling_method: str = "Nearest",
) -> Image.Image:
    """Scale an image using a configurable resampling method.

    Negative scale flips the source horizontally before resizing. Size is
    interpreted as a multiplier (1.0 keeps the original dimensions).

    Args:
        image: Source PIL image.
        size: Scale multiplier; negative values flip horizontally.
        resampling_method: One of "Nearest", "Bilinear", "Bicubic",
            "Lanczos", "Box", or "Hamming".

    Returns:
        Resized PIL image, or the original if dimensions are unchanged.
    """
    working = image
    if size < 0:
        working = working.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    abs_size = abs(size)
    new_width = max(1, round(working.width * abs_size))
    new_height = max(1, round(working.height * abs_size))
    if new_width == working.width and new_height == working.height:
        return working

    pil_filter = get_pil_resampling_filter(resampling_method, abs_size)
    return working.resize((new_width, new_height), pil_filter)


def scale_image_nearest(image: Image.Image, size: float) -> Image.Image:
    """Scale an image using nearest-neighbor sampling.

    Negative scale flips the source horizontally before resizing. Size is
    interpreted as a multiplier (1.0 keeps the original dimensions).

    Args:
        image: Source PIL image.
        size: Scale multiplier; negative values flip horizontally.

    Returns:
        Resized PIL image, or the original if dimensions are unchanged.

    Note:
        This function is deprecated; prefer ``scale_image`` with the
        ``resampling_method`` parameter set to ``"Nearest"``.
    """
    return scale_image(image, size, resampling_method="Nearest")


#: Where a tight frame sits on the shared canvas:
#: ``(offset_x, offset_y, canvas_width, canvas_height)``.
Placement = Tuple[int, int, int, int]


class FramePlacement(NamedTuple):
    """Frame metadata marking a tight crop's spot on a shared canvas.

    Emitted as a frame tuple's third element by the spritemap renderer.
    It is a distinct type rather than a plain tuple on purpose: atlas-based
    frames put ``(x, y, width, height, frameX, frameY)`` in that same slot,
    where ``(x, y)`` is a position *in the source atlas*. Reading one as the
    other would silently mis-place every frame, so consumers must test
    ``isinstance(metadata, FramePlacement)`` rather than sniff the shape.

    The six fields keep it interchangeable with the legacy bounds tuple for
    code that only cares about the frame's width and height.
    """

    offset_x: int
    offset_y: int
    canvas_width: int
    canvas_height: int
    pad_x: int = 0
    pad_y: int = 0

    def placement(self) -> Placement:
        """Return the ``(offset_x, offset_y, canvas_w, canvas_h)`` tuple."""
        return (
            self.offset_x,
            self.offset_y,
            self.canvas_width,
            self.canvas_height,
        )


def place_on_canvas(array: np.ndarray, placement: Placement) -> np.ndarray:
    """Blit a tight frame onto a transparent canvas at its recorded offset.

    Args:
        array: Tight RGBA frame.
        placement: ``(offset_x, offset_y, canvas_width, canvas_height)``.

    Returns:
        RGBA array of canvas size with *array* composited at its offset.
    """
    offset_x, offset_y, canvas_width, canvas_height = placement
    channels = array.shape[2] if array.ndim >= 3 else 1
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))

    if (
        int(offset_x) == 0
        and int(offset_y) == 0
        and array.shape[1] == canvas_width
        and array.shape[0] == canvas_height
    ):
        return array

    canvas = np.zeros((canvas_height, canvas_width, channels), dtype=np.uint8)

    src_left = max(0, -int(offset_x))
    src_top = max(0, -int(offset_y))
    dst_left = max(0, int(offset_x))
    dst_top = max(0, int(offset_y))
    width = min(array.shape[1] - src_left, canvas_width - dst_left)
    height = min(array.shape[0] - src_top, canvas_height - dst_top)
    if width > 0 and height > 0:
        canvas[dst_top : dst_top + height, dst_left : dst_left + width] = array[
            src_top : src_top + height, src_left : src_left + width
        ]
    return canvas


#: A frame must exceed this multiple of the p90 frame area to count as an
#: oversized outlier rather than ordinary animation content.
OUTLIER_AREA_RATIO = 4.0

#: Outlier exclusion needs enough frames for the percentile to mean anything.
OUTLIER_MIN_FRAMES = 8

#: Refuse to treat outliers as such once they stop being a rare exception.
OUTLIER_MAX_FRACTION = 0.1


def union_excluding_outliers(
    boxes: Sequence[Tuple[int, int, int, int]],
) -> Optional[Tuple[int, int, int, int]]:
    """Union *boxes*, ignoring the rare frame that dwarfs all the others.

    Adobe/BTA exports often end on a packing frame that parks every symbol
    on the stage at once purely so the exporter includes them in the atlas.
    That single frame is 10x the size of real content, and letting it into
    the union forces every other frame onto an enormous shared canvas.

    Only frames that are *individually* oversized are dropped. An animation
    whose content travels across the stage has a large union but no outlier
    frame, so it correctly keeps its full canvas — otherwise its frames
    would no longer line up.

    Args:
        boxes: ``(left, top, right, bottom)`` for each non-empty frame.

    Returns:
        The union box, or ``None`` when *boxes* is empty.
    """
    if not boxes:
        return None

    def union_of(selection: Sequence[Tuple[int, int, int, int]]):
        return (
            min(box[0] for box in selection),
            min(box[1] for box in selection),
            max(box[2] for box in selection),
            max(box[3] for box in selection),
        )

    if len(boxes) < OUTLIER_MIN_FRAMES:
        return union_of(boxes)

    areas = sorted((box[2] - box[0]) * (box[3] - box[1]) for box in boxes)
    reference = areas[int(0.9 * (len(areas) - 1))]
    if reference <= 0:
        return union_of(boxes)

    limit = reference * OUTLIER_AREA_RATIO
    kept = [box for box in boxes if (box[2] - box[0]) * (box[3] - box[1]) <= limit]

    dropped = len(boxes) - len(kept)
    if not kept or dropped > len(boxes) * OUTLIER_MAX_FRACTION:
        return union_of(boxes)
    return union_of(kept)


def resolve_frame_placements(frames: List[Tuple[str, FrameSource, object]]) -> bool:
    """Give an animation's frames a canvas sized to their real content.

    The spritemap renderer emits each frame trimmed to the pixels that
    actually drew, tagged with its absolute canvas-space origin and an
    unresolved (zero-sized) canvas. Only once every frame exists is the true
    extent known — so this walks the finished list, takes the union of the
    trimmed boxes, and rewrites each placement relative to it.

    Sizing from drawn pixels rather than from the geometric bounds means
    sprites that are referenced but never visible (placed off-canvas, fully
    masked, alpha'd to nothing) no longer inflate the output.

    Args:
        frames: List of ``(name, image, metadata)`` tuples, modified in
            place. Entries whose metadata is not an unresolved
            ``FramePlacement`` are left alone.

    Returns:
        ``True`` if any frame contained visible pixels. ``False`` means the
        animation rendered empty and should be skipped rather than exported
        as a run of blank frames.
    """
    indices = [
        index
        for index, frame in enumerate(frames)
        if isinstance(frame[2], FramePlacement) and frame[2].canvas_width == 0
    ]
    if not indices:
        return True

    boxes: List[Tuple[int, int, int, int]] = []
    for index in indices:
        _, image, placement = frames[index]
        width, height = frame_dimensions(image)
        # Frames that never drew are 1x1 placeholders at the origin; they
        # must not drag the canvas towards (0, 0).
        if width <= 1 and height <= 1:
            continue
        left, top = placement.offset_x, placement.offset_y
        boxes.append((left, top, left + width, top + height))

    extent = union_excluding_outliers(boxes)
    if extent is None:
        return False

    min_x, min_y, max_x, max_y = extent
    canvas_width = max(1, int(max_x - min_x))
    canvas_height = max(1, int(max_y - min_y))

    for index in indices:
        name, image, placement = frames[index]
        width, height = frame_dimensions(image)
        if width <= 1 and height <= 1:
            resolved = FramePlacement(0, 0, canvas_width, canvas_height)
        else:
            resolved = FramePlacement(
                int(placement.offset_x - min_x),
                int(placement.offset_y - min_y),
                canvas_width,
                canvas_height,
            )
        frames[index] = (name, image, resolved)

    return True


def materialize_frame(frame: FrameSource, metadata) -> np.ndarray:
    """Return a frame at its full canvas size, expanding a tight crop.

    Spritemap frames are stored cropped to their own content. Anything that
    needs frames in a shared coordinate space — cross-frame bounding boxes,
    uniform file output — must expand them first. Frames without a
    ``FramePlacement`` are returned unchanged.

    Args:
        frame: PIL Image or NumPy array.
        metadata: The frame tuple's third element.

    Returns:
        RGBA NumPy array at canvas size when a placement applies.
    """
    array = ensure_rgba_array(frame)
    if not isinstance(metadata, FramePlacement):
        return array
    if metadata.canvas_width <= 0 or metadata.canvas_height <= 0:
        return array
    return place_on_canvas(array, metadata.placement())


class LazyPaddedFrames(_SequenceABC):
    """Sequence of tight frames that expands to full canvas size on access.

    Rendered spritemap frames are stored cropped to their own content, which
    is typically a small fraction of the animation's union canvas. Exporters
    need uniformly sized frames, but they consume them one at a time — so the
    full-size array is built on ``__getitem__`` and dropped as soon as the
    caller releases it. Peak memory becomes ``sum(tight frames) + 1 canvas``
    instead of ``count * canvas``.

    Assigning ``None`` to an index releases that frame's stored pixels, which
    is how the animation exporter frees as it encodes.
    """

    __slots__ = ("_frames", "_placements")

    def __init__(
        self,
        frames: Sequence[FrameSource],
        placements: Sequence[Optional[Placement]],
    ) -> None:
        self._frames: List[Optional[FrameSource]] = list(frames)
        self._placements: List[Optional[Placement]] = list(placements)
        while len(self._placements) < len(self._frames):
            self._placements.append(None)

    def __len__(self) -> int:
        return len(self._frames)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self._frames)))]
        frame = self._frames[index]
        if frame is None:
            return None
        placement = self._placements[index]
        array = ensure_rgba_array(frame)
        if placement is None:
            return array
        return place_on_canvas(array, placement)

    def __setitem__(self, index, value) -> None:
        self._frames[index] = value
        if value is None:
            self._placements[index] = None

    def tight_frame(self, index: int) -> Optional[FrameSource]:
        """Return the stored frame without expanding it to canvas size."""
        return self._frames[index]

    def placement(self, index: int) -> Optional[Placement]:
        """Return the canvas placement recorded for *index*."""
        return self._placements[index]


def pad_frames_to_canvas(
    images: Sequence[FrameSource],
    placements: Optional[Sequence[Optional[Placement]]] = None,
) -> Sequence[np.ndarray]:
    """Pad frames so they share a common canvas size.

    Args:
        images: Sequence of PIL Images or NumPy arrays.
        placements: Optional per-frame ``(offset_x, offset_y, canvas_w,
            canvas_h)``. When supplied, frames are treated as tight crops
            and expanded lazily, so the full sequence is never resident at
            once.

    Returns:
        Sequence of RGBA NumPy arrays with identical dimensions.
    """
    if not images:
        return []

    if placements is not None and any(
        placement is not None for placement in placements
    ):
        return LazyPaddedFrames(images, placements)

    arrays = [ensure_rgba_array(frame) for frame in images]
    heights = [array.shape[0] for array in arrays]
    widths = [array.shape[1] for array in arrays]

    max_width = max(widths)
    max_height = max(heights)
    min_width = min(widths)
    min_height = min(heights)

    if max_width == min_width and max_height == min_height:
        return arrays

    padded: List[np.ndarray] = []
    for array in arrays:
        if array.shape[1] == max_width and array.shape[0] == max_height:
            padded.append(array)
            continue
        canvas = np.zeros((max_height, max_width, array.shape[2]), dtype=np.uint8)
        canvas[: array.shape[0], : array.shape[1]] = array
        padded.append(canvas)
    return padded


def image_to_rgba_array(image: Image.Image) -> np.ndarray:
    """Convert a PIL image to a contiguous RGBA NumPy array.

    Args:
        image: Source PIL image (any mode).

    Returns:
        Contiguous uint8 RGBA array.
    """

    rgba_image = image if image.mode == "RGBA" else image.convert("RGBA")
    array = np.asarray(rgba_image)
    if not array.flags["C_CONTIGUOUS"]:
        array = np.ascontiguousarray(array)
    return array


def array_to_rgba_image(array: np.ndarray) -> Image.Image:
    """Convert an RGBA NumPy array to a PIL image.

    Args:
        array: Source RGBA array (H x W x 4, uint8).

    Returns:
        PIL Image in RGBA mode.
    """

    if array.dtype != np.uint8:
        array = array.astype(np.uint8)
    if not array.flags["C_CONTIGUOUS"]:
        array = np.ascontiguousarray(array)
    try:
        return Image.fromarray(array, mode="RGBA")
    except TypeError:
        h, w = array.shape[:2]
        return Image.frombytes("RGBA", (w, h), array.tobytes())


def ensure_rgba_array(source: FrameSource) -> np.ndarray:
    """Return a contiguous uint8 RGBA array from any frame source.

    Args:
        source: PIL Image or NumPy array.

    Returns:
        Contiguous RGBA NumPy array.
    """

    if isinstance(source, np.ndarray):
        array = source
    else:
        array = image_to_rgba_array(source)
    if array.dtype != np.uint8:
        array = array.astype(np.uint8, copy=False)
    if array.ndim == 2:
        array = np.expand_dims(array, axis=-1)
    if not array.flags["C_CONTIGUOUS"]:
        array = np.ascontiguousarray(array)
    return array


def ensure_pil_image(source: FrameSource) -> Image.Image:
    """Return a PIL RGBA image from any frame source.

    Args:
        source: PIL Image or NumPy array.

    Returns:
        PIL Image in RGBA mode.
    """

    if isinstance(source, Image.Image):
        return source if source.mode == "RGBA" else source.convert("RGBA")
    return array_to_rgba_image(source)


def frame_dimensions(source: FrameSource) -> Tuple[int, int]:
    """Return the width and height of a frame.

    Args:
        source: PIL Image or NumPy array.

    Returns:
        Tuple ``(width, height)``.
    """

    if isinstance(source, np.ndarray):
        if source.ndim == 2:
            return source.shape[1], source.shape[0]
        return source.shape[1], source.shape[0]
    return source.width, source.height


def alpha_mask(array: np.ndarray, *, threshold: int = 0) -> Optional[np.ndarray]:
    """Return a boolean mask of pixels exceeding the alpha threshold.

    Falls back to luminance if the array lacks an alpha channel.

    Args:
        array: Source RGBA (or grayscale) NumPy array.
        threshold: Minimum alpha value to be considered visible.

    Returns:
        2-D boolean array, or ``None`` if the input is empty or invalid.
    """

    if array.size == 0:
        return None

    if array.ndim == 2:
        return array > threshold

    if array.ndim >= 3:
        channels = array.shape[2]
        if channels == 0:
            return None
        if channels >= 4:
            return array[..., 3] > threshold
        return np.any(array[..., :channels] > threshold, axis=2)

    return None


def bbox_from_mask(mask: Optional[np.ndarray]) -> Optional[BBox]:
    """Compute a tight bounding box from a boolean mask.

    Args:
        mask: 2-D boolean array indicating visible pixels.

    Returns:
        Tuple ``(left, top, right, bottom)``, or ``None`` if empty.
    """

    if mask is None or mask.ndim != 2:
        return None

    row_hits = np.flatnonzero(mask.any(axis=1))
    if row_hits.size == 0:
        return None
    col_hits = np.flatnonzero(mask.any(axis=0))
    if col_hits.size == 0:
        return None

    top = int(row_hits[0])
    bottom = int(row_hits[-1] + 1)
    left = int(col_hits[0])
    right = int(col_hits[-1] + 1)
    return left, top, right, bottom


def bbox_from_array(array: np.ndarray, *, threshold: int = 0) -> Optional[BBox]:
    """Return the bounding box of visible pixels in an array.

    Args:
        array: Source RGBA NumPy array.
        threshold: Minimum alpha to be considered visible.

    Returns:
        Tuple ``(left, top, right, bottom)``, or ``None`` if empty.
    """

    mask = alpha_mask(array, threshold=threshold)
    if mask is None:
        return None
    return bbox_from_mask(mask)


def frame_bbox(frame: FrameSource, *, threshold: int = 0) -> Optional[BBox]:
    """Compute the bounding box for a PIL Image or NumPy array.

    Args:
        frame: PIL Image or NumPy array.
        threshold: Minimum alpha to be considered visible.

    Returns:
        Tuple ``(left, top, right, bottom)``, or ``None`` on error or empty.
    """

    try:
        array = ensure_rgba_array(frame)
    except Exception:
        return None
    return bbox_from_array(array, threshold=threshold)


def crop_to_bbox(array: np.ndarray, bbox: BBox) -> np.ndarray:
    """Return a view of the array cropped to the bounding box.

    Args:
        array: Source NumPy array (at least 2-D).
        bbox: Tuple ``(left, top, right, bottom)``.

    Returns:
        Cropped array view; may share memory with the original.
    """

    if array.ndim < 2:
        return array

    height, width = array.shape[0], array.shape[1]
    left, top, right, bottom = bbox

    left = max(0, min(width, int(left)))
    top = max(0, min(height, int(top)))
    right = max(left, min(width, int(right)))
    bottom = max(top, min(height, int(bottom)))

    if left == 0 and top == 0 and right == width and bottom == height:
        return array

    return array[top:bottom, left:right]


def apply_alpha_threshold(array: np.ndarray, threshold: float) -> np.ndarray:
    """Clamp the alpha channel to fully transparent or fully opaque.

    Pixels with alpha above the normalized threshold become 255; others become 0.

    Args:
        array: RGBA NumPy array.
        threshold: Normalized cutoff in ``[0.0, 1.0]``.

    Returns:
        Array with binary alpha; may be a copy if the input was read-only.
    """

    if array.ndim < 3 or array.shape[2] < 4:
        return array

    try:
        value = float(threshold)
    except (TypeError, ValueError):
        return array

    value = min(max(value, 0.0), 1.0)
    working = array if array.flags.writeable else array.copy()
    alpha_view = working[..., 3]

    mask = np.empty(alpha_view.shape, dtype=bool)
    if value >= 1.0:
        np.greater_equal(alpha_view, 255, out=mask)
    elif value <= 0.0:
        np.greater(alpha_view, 0, out=mask)
    else:
        cutoff = int(round(value * 255))
        np.greater(alpha_view, cutoff, out=mask)

    np.multiply(mask, 255, out=alpha_view, casting="unsafe")
    return working
