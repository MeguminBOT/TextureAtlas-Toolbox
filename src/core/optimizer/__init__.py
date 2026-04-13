#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Image optimizer / PNG compression module.

Provides lossless PNG recompression and lossy pngquant-style colour
quantization via Pillow or Wand (ImageMagick).
"""

from core.optimizer.constants import (
    COLOR_MODE_LABELS,
    DITHER_METHOD_LABELS,
    PRESET_LABELS,
    PRESET_OPTIONS,
    QUANTIZE_METHOD_LABELS,
    SUPPORTED_EXTENSIONS,
    TEXTURE_CONTAINER_LABELS,
    TEXTURE_FORMAT_LABELS,
    ColorMode,
    DitherMethod,
    OptimizeOptions,
    OptimizePreset,
    OptimizeResult,
    QuantizeMethod,
    TextureContainer,
    TextureFormat,
)
from core.optimizer.optimizer import ImageOptimizer
from core.optimizer.texture_compress import TextureCompressor

__all__ = [
    "COLOR_MODE_LABELS",
    "ColorMode",
    "DITHER_METHOD_LABELS",
    "DitherMethod",
    "ImageOptimizer",
    "OptimizeOptions",
    "OptimizePreset",
    "OptimizeResult",
    "PRESET_LABELS",
    "PRESET_OPTIONS",
    "QUANTIZE_METHOD_LABELS",
    "QuantizeMethod",
    "SUPPORTED_EXTENSIONS",
    "TEXTURE_CONTAINER_LABELS",
    "TEXTURE_FORMAT_LABELS",
    "TextureCompressor",
    "TextureContainer",
    "TextureFormat",
]
