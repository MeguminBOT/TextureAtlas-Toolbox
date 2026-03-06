#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dithering algorithms for the image optimizer.

Provides ordered (Bayer 8×8) and Riemersma (Hilbert-curve) dithering
as standalone functions that accept a log callback.
"""

from __future__ import annotations

import io
from typing import Callable, Optional

import numpy as np
from PIL import Image

from core.optimizer.constants import BAYER_8x8, BLUE_NOISE_64, DitherMethod


LogFn = Callable[[str], None]


def apply_ordered_dither(
    rgb: Image.Image,
    palette_img: Image.Image,
    max_colors: int,
    log: Optional[LogFn] = None,
) -> Image.Image:
    """Apply Bayer 8×8 ordered dithering against a pre-computed palette.

    The Bayer threshold matrix introduces a position-dependent bias
    to each pixel before nearest-colour mapping.  This produces a
    regular halftone-like dot pattern that is visually distinct from
    error-diffusion dithering and compresses very well with PNG's
    deflate algorithm.

    Args:
        rgb: Source image in RGB mode.
        palette_img: Quantized palette image to map against.
        max_colors: Maximum number of palette entries.
        log: Optional logging callback.

    Returns:
        A quantized ``P``-mode image.
    """
    if log:
        log("[ImageOptimizer]   Applying ordered (Bayer 8\u00d78) dither")

    src = np.asarray(rgb).astype(np.float64)
    h, w = src.shape[:2]

    threshold = np.tile(BAYER_8x8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    spread = 255.0 / max(max_colors, 2) * 0.75

    adjusted = src + threshold[:, :, np.newaxis] * spread
    adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
    adjusted_img = Image.fromarray(adjusted, "RGB")

    # Map biased pixels to nearest palette colour (the bias already
    # provides the dithering effect)
    return adjusted_img.quantize(palette=palette_img, dither=Image.Dither.NONE)


def apply_riemersma_dither(
    rgb: Image.Image,
    palette_img: Image.Image,
    max_colors: int,
    log: Optional[LogFn] = None,
) -> Image.Image:
    """Apply Riemersma (Hilbert-curve) dithering via Wand/ImageMagick.

    Riemersma dithering distributes quantization error along a
    space-filling Hilbert curve, producing a more organic noise
    pattern than Floyd-Steinberg.  Requires ImageMagick 7+ via the
    Wand library.

    Falls back to Floyd-Steinberg when Wand is not available.

    Args:
        rgb: Source image in RGB mode.
        palette_img: Quantized palette image to map against.
        max_colors: Maximum number of palette entries.
        log: Optional logging callback.

    Returns:
        A quantized ``P``-mode image, or an RGBA image from Wand.
    """
    try:
        from wand.image import Image as WandImage
    except ImportError:
        if log:
            log(
                "[ImageOptimizer]   Riemersma requires Wand/ImageMagick; "
                "falling back to Floyd-Steinberg"
            )
        return rgb.quantize(
            palette=palette_img,
            dither=Image.Dither.FLOYDSTEINBERG,
        )

    if log:
        log("[ImageOptimizer]   Applying Riemersma dither via Wand")

    png_buf = io.BytesIO()
    rgb.save(png_buf, format="PNG")
    png_bytes = png_buf.getvalue()

    with WandImage(blob=png_bytes) as wand_img:
        wand_img.quantize(
            number_colors=max_colors,
            treedepth=0,
            dither="riemersma",
            measure_error=False,
        )
        result_blob = wand_img.make_blob(format="png")

    result = Image.open(io.BytesIO(result_blob))
    result.load()
    return result


def apply_blue_noise_dither(
    rgb: Image.Image,
    palette_img: Image.Image,
    max_colors: int,
    log: Optional[LogFn] = None,
) -> Image.Image:
    """Apply blue-noise threshold dithering against a pre-computed palette.

    Uses a spectrally-shaped 64×64 threshold matrix that tiles across
    the image.  The resulting noise pattern is visually uniform with no
    regular grid artefacts (unlike Bayer ordered dithering) while still
    compressing well with PNG's deflate algorithm.

    Args:
        rgb: Source image in RGB mode.
        palette_img: Quantized palette image to map against.
        max_colors: Maximum number of palette entries.
        log: Optional logging callback.

    Returns:
        A quantized ``P``-mode image.
    """
    if log:
        log("[ImageOptimizer]   Applying blue noise dither")

    src = np.asarray(rgb).astype(np.float64)
    h, w = src.shape[:2]

    size = BLUE_NOISE_64.shape[0]
    threshold = np.tile(BLUE_NOISE_64, (h // size + 1, w // size + 1))[:h, :w]
    spread = 255.0 / max(max_colors, 2) * 0.75

    adjusted = src + threshold[:, :, np.newaxis] * spread
    adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
    adjusted_img = Image.fromarray(adjusted, "RGB")

    return adjusted_img.quantize(palette=palette_img, dither=Image.Dither.NONE)


def apply_atkinson_dither(
    rgb: Image.Image,
    palette_img: Image.Image,
    max_colors: int,
    log: Optional[LogFn] = None,
) -> Image.Image:
    """Apply Atkinson error-diffusion dithering against a pre-computed palette.

    Atkinson dithering (Bill Atkinson, original Macintosh) diffuses only
    6/8 of the quantization error, producing a lighter and more open
    pattern with higher contrast than Floyd-Steinberg.  The "lost" 2/8
    of the error gives the result a characteristic crispness favoured by
    retro and pixel-art communities.

    Diffusion kernel (each coefficient is 1/8 of the error)::

            *   1   1
        1   1   1
            1

    Args:
        rgb: Source image in RGB mode.
        palette_img: Quantized palette image to map against.
        max_colors: Maximum number of palette entries.
        log: Optional logging callback.

    Returns:
        A quantized ``P``-mode image with the original palette.
    """
    if log:
        log("[ImageOptimizer]   Applying Atkinson dither")

    palette_data = palette_img.getpalette()
    if palette_data is None:
        return palette_img

    n_colors = min(max_colors, len(palette_data) // 3)
    palette_arr = np.array(palette_data[: n_colors * 3], dtype=np.float64).reshape(
        -1, 3
    )

    src = np.asarray(rgb).astype(np.float64).copy()
    h, w = src.shape[:2]
    output_indices = np.zeros((h, w), dtype=np.uint8)

    for y in range(h):
        for x in range(w):
            old = src[y, x, :3].copy()

            # Nearest palette colour
            diffs = palette_arr - old
            idx = int(np.argmin(np.sum(diffs * diffs, axis=1)))
            output_indices[y, x] = idx
            new_color = palette_arr[idx]

            # Only 6/8 of the error is diffused (1/8 per neighbour)
            err = (old - new_color) / 8.0

            if x + 1 < w:
                src[y, x + 1, :3] += err
            if x + 2 < w:
                src[y, x + 2, :3] += err
            if y + 1 < h:
                if x - 1 >= 0:
                    src[y + 1, x - 1, :3] += err
                src[y + 1, x, :3] += err
                if x + 1 < w:
                    src[y + 1, x + 1, :3] += err
            if y + 2 < h:
                src[y + 2, x, :3] += err

    result = Image.fromarray(output_indices, mode="P")
    result.putpalette(palette_data)
    return result


def wand_dither_string(dither: DitherMethod) -> str:
    """Map a ``DitherMethod`` to the Wand/IM7 dither string.

    ImageMagick 7 accepts ``'no'``, ``'riemersma'``, or
    ``'floyd_steinberg'`` as the *dither* argument to
    ``quantize()``.  Ordered (Bayer) is not natively supported by
    ImageMagick's quantize API, so it falls back to
    Floyd-Steinberg.

    Args:
        dither: The dither method to translate.

    Returns:
        A string accepted by ``wand.image.Image.quantize()``.
    """
    return {
        DitherMethod.NONE: "no",
        DitherMethod.FLOYD_STEINBERG: "floyd_steinberg",
        DitherMethod.RIEMERSMA: "riemersma",
        DitherMethod.ORDERED: "floyd_steinberg",
        DitherMethod.BLUE_NOISE: "floyd_steinberg",
        DitherMethod.ATKINSON: "floyd_steinberg",
    }.get(dither, "floyd_steinberg")
