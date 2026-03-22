"""Image helper utilities shared across extractor components.

Provides conversion functions between PIL Images and NumPy arrays, bounding
box calculations, scaling, padding, and alpha channel manipulation.

Type Aliases:
    FrameSource: ``Union[Image.Image, np.ndarray]`` — frame data may be
        either a PIL Image or a NumPy array throughout the pipeline.
    BBox: ``Tuple[int, int, int, int]`` — bounding box as ``(left, top, right, bottom)``.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

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


def pad_frames_to_canvas(images: Sequence[FrameSource]) -> List[np.ndarray]:
    """Pad frames so they share a common canvas size.

    Args:
        images: Sequence of PIL Images or NumPy arrays.

    Returns:
        List of RGBA NumPy arrays with identical dimensions.
    """
    if not images:
        return []

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
