#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Quantization algorithms for the image optimizer.

Provides Pillow-based quantization (Median Cut, Max Coverage, Fast
Octree, libimagequant) and a native pngquant-style premultiplied-alpha
quantizer, all as standalone functions that accept a log callback.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from PIL import Image

from core.optimizer.constants import DitherMethod, OptimizeOptions, QuantizeMethod
from core.optimizer.dither import (
    apply_atkinson_dither,
    apply_blue_noise_dither,
    apply_ordered_dither,
    apply_riemersma_dither,
)


LogFn = Callable[[str], None]


def quantize_pillow(
    img: Image.Image,
    options: OptimizeOptions,
    log: Optional[LogFn] = None,
    src_path: str = "",
) -> Image.Image:
    """Reduce the image to an indexed palette using Pillow.

    Median Cut and Max Coverage only support RGB images.  When the
    source is RGBA we separate the alpha channel, quantize the RGB
    portion, then re-apply the original alpha so transparency is
    preserved.  Fast Octree handles RGBA natively.

    Args:
        img: Source image (RGB or RGBA).
        options: Quantization settings (method, max colours, dither).
        log: Optional logging callback.
        src_path: Path to the source file, used only for log messages.

    Returns:
        A quantized image (``P`` mode, or RGBA when alpha was restored).
    """
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    if options.quantize_method is QuantizeMethod.PNGQUANT:
        return quantize_pngquant(img, options, log=log)

    # LIBIMAGEQUANT falls back to MEDIANCUT when the C extension was
    # not compiled with libimagequant support.
    pillow_method = {
        QuantizeMethod.MEDIANCUT: Image.Quantize.MEDIANCUT,
        QuantizeMethod.MAXCOVERAGE: Image.Quantize.MAXCOVERAGE,
        QuantizeMethod.FASTOCTREE: Image.Quantize.FASTOCTREE,
        QuantizeMethod.LIBIMAGEQUANT: Image.Quantize.LIBIMAGEQUANT,
    }.get(options.quantize_method, Image.Quantize.MEDIANCUT)

    method_name = options.quantize_method.value

    if pillow_method is Image.Quantize.LIBIMAGEQUANT:
        try:
            # Quick probe — will raise if the C dependency is missing
            probe = Image.new("RGB", (1, 1))
            probe.quantize(colors=2, method=Image.Quantize.LIBIMAGEQUANT)
        except Exception:
            if log:
                log(
                    "[ImageOptimizer]   libimagequant not available, "
                    "falling back to Median Cut"
                )
            pillow_method = Image.Quantize.MEDIANCUT
            method_name = "mediancut"

    return quantize_with_method(img, pillow_method, method_name, options, log=log)


def quantize_with_method(
    img: Image.Image,
    pillow_method: Image.Quantize,
    method_name: str,
    options: OptimizeOptions,
    log: Optional[LogFn] = None,
) -> Image.Image:
    """Run a single Pillow quantize method, handling the RGBA workaround.

    Pillow's ``quantize()`` silently ignores the ``dither``
    parameter when generating the palette in the same call.  To
    make dithering actually work we use a two-step approach:

    1. Quantize with ``dither=NONE`` to compute the palette.
    2. Apply the selected dither algorithm against that palette.

    Args:
        img: Source image (RGB or RGBA).
        pillow_method: The Pillow ``Image.Quantize`` enum value.
        method_name: Human-readable name for log messages.
        options: Quantization settings (max colours, dither, etc.).
        log: Optional logging callback.

    Returns:
        A quantized image (``P`` mode, or RGBA when alpha was restored).
    """
    dither = options.dither
    has_alpha = img.mode == "RGBA"
    needs_alpha_workaround = has_alpha and pillow_method in (
        Image.Quantize.MEDIANCUT,
        Image.Quantize.MAXCOVERAGE,
        Image.Quantize.LIBIMAGEQUANT,
    )

    # --- Step 1: generate palette (always without dither) ---
    if needs_alpha_workaround:
        alpha = img.getchannel("A")
        rgb = img.convert("RGB")
        if log:
            log(
                "[ImageOptimizer]   RGBA workaround: separating alpha for "
                f"{method_name} quantization"
            )
        palette_img = rgb.quantize(
            colors=options.max_colors,
            method=pillow_method,
            dither=Image.Dither.NONE,
        )
    else:
        alpha = img.getchannel("A") if has_alpha else None
        rgb = img.convert("RGB") if has_alpha else img
        palette_img = img.quantize(
            colors=options.max_colors,
            method=pillow_method,
            dither=Image.Dither.NONE,
        )

    # --- Step 2: apply dither ---
    if dither is DitherMethod.NONE:
        quantized = palette_img

    elif dither is DitherMethod.FLOYD_STEINBERG:
        # Pillow needs an RGB source and an RGB palette image
        # for the re-quantize step.
        palette_rgb = (
            palette_img
            if not needs_alpha_workaround
            else rgb.quantize(
                colors=options.max_colors,
                method=pillow_method,
                dither=Image.Dither.NONE,
            )
        )
        src_rgb = (
            rgb
            if needs_alpha_workaround
            else (img.convert("RGB") if has_alpha else img)
        )
        quantized = src_rgb.quantize(
            palette=palette_rgb,
            dither=Image.Dither.FLOYDSTEINBERG,
        )

    elif dither is DitherMethod.ORDERED:
        quantized = apply_ordered_dither(
            (
                rgb
                if needs_alpha_workaround
                else (img.convert("RGB") if has_alpha else img)
            ),
            palette_img,
            options.max_colors,
            log=log,
        )

    elif dither is DitherMethod.BLUE_NOISE:
        quantized = apply_blue_noise_dither(
            (
                rgb
                if needs_alpha_workaround
                else (img.convert("RGB") if has_alpha else img)
            ),
            palette_img,
            options.max_colors,
            log=log,
        )

    elif dither is DitherMethod.ATKINSON:
        quantized = apply_atkinson_dither(
            (
                rgb
                if needs_alpha_workaround
                else (img.convert("RGB") if has_alpha else img)
            ),
            palette_img,
            options.max_colors,
            log=log,
        )

    elif dither is DitherMethod.RIEMERSMA:
        quantized = apply_riemersma_dither(
            (
                rgb
                if needs_alpha_workaround
                else (img.convert("RGB") if has_alpha else img)
            ),
            palette_img,
            options.max_colors,
            log=log,
        )

    else:
        quantized = palette_img

    # --- Step 3: restore alpha ---
    if alpha is not None:
        result = quantized.convert("RGBA")
        result.putalpha(alpha)
        return result

    return quantized


def quantize_pngquant(
    img: Image.Image,
    options: OptimizeOptions,
    log: Optional[LogFn] = None,
) -> Image.Image:
    """Native pngquant-style quantization with premultiplied alpha.

    Replicates pngquant's core technique:

    1. Premultiply RGB by alpha so the quantizer sees colours
       weighted by their visibility.
    2. Generate a palette from the premultiplied RGBA pixels.
    3. Map every pixel to its nearest palette entry (with optional
       dithering).
    4. Un-premultiply the result palette so the final PNG stores
       straight (non-premultiplied) alpha.

    This produces significantly better results for sprites with
    semi-transparent edges than quantizing straight-alpha images,
    because the palette entries naturally de-prioritise colours
    that are mostly invisible.

    Args:
        img: Source image (preferably RGBA).
        options: Quantization settings (max colours, dither, etc.).
        log: Optional logging callback.

    Returns:
        A quantized RGBA image with straight alpha.
    """
    has_alpha = img.mode == "RGBA"
    if not has_alpha:
        if log:
            log(
                "[ImageOptimizer]   pngquant: no alpha channel, "
                "delegating to Median Cut"
            )
        return quantize_with_method(
            img,
            Image.Quantize.MEDIANCUT,
            "mediancut",
            options,
            log=log,
        )

    if log:
        log("[ImageOptimizer]   pngquant: premultiplying alpha")

    arr = np.asarray(img).astype(np.float64)
    alpha = arr[:, :, 3:4] / 255.0

    premul = arr.copy()
    premul[:, :, :3] *= alpha
    premul = np.clip(premul, 0, 255).astype(np.uint8)
    try:
        premul_img = Image.fromarray(premul, "RGBA")
    except TypeError:
        h, w = premul.shape[:2]
        premul_img = Image.frombytes(
            "RGBA", (w, h), np.ascontiguousarray(premul).tobytes()
        )

    # Prefer libimagequant, else fall back to Median Cut.
    try:
        probe = Image.new("RGB", (1, 1))
        probe.quantize(colors=2, method=Image.Quantize.LIBIMAGEQUANT)
        quant_method = Image.Quantize.LIBIMAGEQUANT
        method_name = "libimagequant"
    except Exception:
        quant_method = Image.Quantize.MEDIANCUT
        method_name = "mediancut"

    if log:
        log(
            f"[ImageOptimizer]   pngquant: palette via {method_name}, "
            f"colors={options.max_colors}"
        )

    # Generate palette from premultiplied pixels.
    # Separate alpha for methods that require RGB-only input.
    orig_alpha = img.getchannel("A")
    premul_rgb = premul_img.convert("RGB")
    palette_img = premul_rgb.quantize(
        colors=options.max_colors,
        method=quant_method,
        dither=Image.Dither.NONE,
    )

    # Apply dithering against the premultiplied palette
    dither = options.dither
    if dither is DitherMethod.NONE:
        quantized = palette_img
    elif dither is DitherMethod.FLOYD_STEINBERG:
        quantized = premul_rgb.quantize(
            palette=palette_img,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
    elif dither is DitherMethod.ORDERED:
        quantized = apply_ordered_dither(
            premul_rgb, palette_img, options.max_colors, log=log
        )
    elif dither is DitherMethod.BLUE_NOISE:
        quantized = apply_blue_noise_dither(
            premul_rgb, palette_img, options.max_colors, log=log
        )
    elif dither is DitherMethod.ATKINSON:
        quantized = apply_atkinson_dither(
            premul_rgb, palette_img, options.max_colors, log=log
        )
    elif dither is DitherMethod.RIEMERSMA:
        quantized = apply_riemersma_dither(
            premul_rgb, palette_img, options.max_colors, log=log
        )
    else:
        quantized = palette_img

    # Un-premultiply the palette colours
    result_rgba = quantized.convert("RGBA")
    res_arr = np.asarray(result_rgba).astype(np.float64).copy()

    # Use the original alpha so edges stay crisp.
    orig_alpha_arr = np.asarray(orig_alpha).astype(np.float64)
    safe_alpha = np.maximum(orig_alpha_arr / 255.0, 1.0 / 255.0)
    res_arr[:, :, :3] /= safe_alpha[:, :, np.newaxis]
    res_arr[:, :, :3] = np.clip(res_arr[:, :, :3], 0, 255)
    res_arr[:, :, 3] = orig_alpha_arr
    result_arr = res_arr.astype(np.uint8)
    try:
        result = Image.fromarray(result_arr, "RGBA")
    except TypeError:
        h, w = result_arr.shape[:2]
        result = Image.frombytes(
            "RGBA", (w, h), np.ascontiguousarray(result_arr).tobytes()
        )

    if log:
        log("[ImageOptimizer]   pngquant: un-premultiplied, done")
    return result
