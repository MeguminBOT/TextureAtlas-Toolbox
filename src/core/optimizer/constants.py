#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Enums, labels, dataclasses, and preset definitions for the optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import numpy as np


# Standard 8×8 Bayer threshold matrix for ordered dithering.
# Normalised to the [-0.5, +0.484375] range so the threshold can be
# multiplied by a colour-dependent spread and added to pixel values.
BAYER_8x8: np.ndarray = (
    np.array(
        [
            [0, 48, 12, 60, 3, 51, 15, 63],
            [32, 16, 44, 28, 35, 19, 47, 31],
            [8, 56, 4, 52, 11, 59, 7, 55],
            [40, 24, 36, 20, 43, 27, 39, 23],
            [2, 50, 14, 62, 1, 49, 13, 61],
            [34, 18, 46, 30, 33, 17, 45, 29],
            [10, 58, 6, 54, 9, 57, 5, 53],
            [42, 26, 38, 22, 41, 25, 37, 21],
        ],
        dtype=np.float64,
    )
    / 64.0
    - 0.5
)


class ColorMode(Enum):
    """Target colour mode for channel / bit-depth conversion."""

    KEEP = "keep"
    RGBA = "RGBA"
    RGB = "RGB"
    GRAYSCALE_ALPHA = "LA"
    GRAYSCALE = "L"


class QuantizeMethod(Enum):
    """Algorithm used for palette quantization."""

    MEDIANCUT = "mediancut"
    MAXCOVERAGE = "maxcoverage"
    FASTOCTREE = "fastoctree"
    LIBIMAGEQUANT = "libimagequant"
    PNGQUANT = "pngquant"
    IMAGEMAGICK = "imagemagick"


class DitherMethod(Enum):
    """Dithering algorithm applied during quantization."""

    NONE = "none"
    FLOYD_STEINBERG = "floyd_steinberg"
    ORDERED = "ordered"
    BLUE_NOISE = "blue_noise"
    ATKINSON = "atkinson"
    RIEMERSMA = "riemersma"


class OptimizePreset(Enum):
    """Pre-configured optimization profiles."""

    LOSSLESS = "lossless"
    ALL_AROUND = "all_around"
    PIXEL_ART = "pixel_art"
    HEAVY_TRANSPARENCY = "heavy_transparency"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


COLOR_MODE_LABELS: dict[str, ColorMode] = {
    "Keep original": ColorMode.KEEP,
    "RGBA (32-bit)": ColorMode.RGBA,
    "RGB (24-bit, no alpha)": ColorMode.RGB,
    "Grayscale + Alpha": ColorMode.GRAYSCALE_ALPHA,
    "Grayscale": ColorMode.GRAYSCALE,
}


QUANTIZE_METHOD_LABELS: dict[str, QuantizeMethod] = {
    "Median Cut": QuantizeMethod.MEDIANCUT,
    "Max Coverage": QuantizeMethod.MAXCOVERAGE,
    "Fast Octree": QuantizeMethod.FASTOCTREE,
    "libimagequant": QuantizeMethod.LIBIMAGEQUANT,
    "pngquant": QuantizeMethod.PNGQUANT,
    "ImageMagick": QuantizeMethod.IMAGEMAGICK,
}


DITHER_METHOD_LABELS: dict[str, DitherMethod] = {
    "None": DitherMethod.NONE,
    "Floyd-Steinberg": DitherMethod.FLOYD_STEINBERG,
    "Ordered (Bayer)": DitherMethod.ORDERED,
    "Blue Noise": DitherMethod.BLUE_NOISE,
    "Atkinson": DitherMethod.ATKINSON,
    "Riemersma": DitherMethod.RIEMERSMA,
}


PRESET_LABELS: dict[str, OptimizePreset] = {
    "Lossless (recompress only)": OptimizePreset.LOSSLESS,
    "All Around": OptimizePreset.ALL_AROUND,
    "Pixel Art": OptimizePreset.PIXEL_ART,
    "Heavy Transparency": OptimizePreset.HEAVY_TRANSPARENCY,
    "Aggressive": OptimizePreset.AGGRESSIVE,
    "Custom": OptimizePreset.CUSTOM,
}


@dataclass
class OptimizeOptions:
    """Configuration for an optimization run.

    Attributes:
        compress_level: PNG deflate compression (0-9, higher = smaller).
        optimize: Enable Pillow's extra PNG optimization pass.
        color_mode: Channel / bit-depth conversion before save.
        quantize: Whether to reduce to an indexed palette.
        quantize_method: Algorithm for palette quantization.
        max_colors: Maximum palette entries when quantizing (2-256).
        dither: Dithering algorithm applied during quantization.
        strip_metadata: Remove EXIF / text chunks.
        skip_if_larger: Do not write output if it would be larger.
        overwrite: Replace originals instead of writing to output_dir.
        output_dir: Destination directory when not overwriting.
    """

    compress_level: int = 9
    optimize: bool = True
    color_mode: ColorMode = ColorMode.KEEP
    quantize: bool = False
    quantize_method: QuantizeMethod = QuantizeMethod.PNGQUANT
    max_colors: int = 256
    dither: DitherMethod = DitherMethod.FLOYD_STEINBERG
    strip_metadata: bool = True
    skip_if_larger: bool = True
    overwrite: bool = False
    output_dir: str = ""


@dataclass
class OptimizeResult:
    """Outcome of optimizing a single image.

    Attributes:
        source_path: Original file path.
        output_path: Where the optimized file was written.
        original_size: File size in bytes before optimization.
        optimized_size: File size in bytes after optimization.
        success: Whether the operation completed without error.
        error: Error message if ``success`` is False.
        skipped: True if the file was skipped (result was larger).
        ssim: Structural similarity index (0–1) after quantization,
            or ``-1.0`` when not computed.
    """

    source_path: str
    output_path: str = ""
    original_size: int = 0
    optimized_size: int = 0
    success: bool = True
    error: str = ""
    skipped: bool = False
    ssim: float = -1.0

    @property
    def savings_bytes(self) -> int:
        """Byte difference (positive means smaller)."""
        return self.original_size - self.optimized_size

    @property
    def savings_percent(self) -> float:
        """Percent reduced (0-100). Returns 0 when original was empty."""
        if self.original_size <= 0:
            return 0.0
        return (self.savings_bytes / self.original_size) * 100.0


PRESET_OPTIONS: dict[OptimizePreset, OptimizeOptions] = {
    OptimizePreset.LOSSLESS: OptimizeOptions(
        compress_level=9,
        optimize=True,
        color_mode=ColorMode.KEEP,
        quantize=False,
        strip_metadata=True,
        skip_if_larger=True,
    ),
    OptimizePreset.ALL_AROUND: OptimizeOptions(
        compress_level=9,
        optimize=True,
        color_mode=ColorMode.KEEP,
        quantize=True,
        quantize_method=QuantizeMethod.MEDIANCUT,
        max_colors=256,
        dither=DitherMethod.FLOYD_STEINBERG,
        strip_metadata=True,
        skip_if_larger=True,
    ),
    OptimizePreset.PIXEL_ART: OptimizeOptions(
        compress_level=9,
        optimize=True,
        color_mode=ColorMode.KEEP,
        quantize=True,
        quantize_method=QuantizeMethod.FASTOCTREE,
        max_colors=256,
        dither=DitherMethod.NONE,
        strip_metadata=True,
        skip_if_larger=True,
    ),
    OptimizePreset.HEAVY_TRANSPARENCY: OptimizeOptions(
        compress_level=9,
        optimize=True,
        color_mode=ColorMode.KEEP,
        quantize=True,
        quantize_method=QuantizeMethod.PNGQUANT,
        max_colors=256,
        dither=DitherMethod.FLOYD_STEINBERG,
        strip_metadata=True,
        skip_if_larger=True,
    ),
    OptimizePreset.AGGRESSIVE: OptimizeOptions(
        compress_level=9,
        optimize=True,
        color_mode=ColorMode.KEEP,
        quantize=True,
        quantize_method=QuantizeMethod.PNGQUANT,
        max_colors=64,
        dither=DitherMethod.FLOYD_STEINBERG,
        strip_metadata=True,
        skip_if_larger=True,
    ),
}


SUPPORTED_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
)


def _generate_blue_noise(size: int = 64, seed: int = 42) -> np.ndarray:
    """Generate a blue-noise threshold matrix via spectral shaping.

    Applies a high-pass filter to white noise in the frequency domain,
    suppressing low frequencies to produce the characteristic blue-noise
    spectral profile.  The result tiles seamlessly and is normalised to
    the ``[-0.5, +0.5)`` range (same convention as :data:`BAYER_8x8`).

    Args:
        size: Side length of the square matrix.
        seed: RNG seed for reproducibility.

    Returns:
        A ``(size, size)`` float64 array normalised to ``[-0.5, +0.5)``.
    """
    rng = np.random.RandomState(seed)
    noise = rng.random((size, size))

    spectrum = np.fft.fft2(noise)
    freqs_y = np.fft.fftfreq(size)
    freqs_x = np.fft.fftfreq(size)
    fy, fx = np.meshgrid(freqs_y, freqs_x, indexing="ij")
    dist = np.sqrt(fx**2 + fy**2)

    # High-pass: attenuate low frequencies
    cutoff = 4.0 / size
    hp = 1.0 - np.exp(-(dist**2) / (2 * cutoff**2))

    filtered = np.fft.ifft2(spectrum * hp).real
    mn, mx = filtered.min(), filtered.max()
    if mx > mn:
        filtered = (filtered - mn) / (mx - mn) - 0.5
    return filtered


BLUE_NOISE_64: np.ndarray = _generate_blue_noise(64, seed=42)
