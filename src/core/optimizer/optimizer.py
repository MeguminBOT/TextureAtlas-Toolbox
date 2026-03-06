#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Core image optimization engine.

Thin orchestration layer that delegates quantization, dithering,
and quality measurement to sibling modules.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
from PIL import Image

from core.optimizer.constants import (
    SUPPORTED_EXTENSIONS,
    ColorMode,
    OptimizeOptions,
    OptimizeResult,
    QuantizeMethod,
)
from core.optimizer.dither import wand_dither_string
from core.optimizer.quality import ssim_from_arrays
from core.optimizer.quantize import quantize_pillow

# Spritesheets can exceed Pillow's 89-megapixel decompression bomb
# threshold, so raise the limit to 512 megapixels.
Image.MAX_IMAGE_PIXELS = 512_000_000


class ImageOptimizer:
    """Batch image optimization engine.

    Processes images using Pillow's PNG optimisation with optional
    lossy quantization via Pillow or Wand (ImageMagick).
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self._progress = progress_callback
        self._log_callback = log_callback

    def _log(self, message: str) -> None:
        """Write *message* to stdout and to the UI log callback."""
        print(message)
        if self._log_callback:
            self._log_callback(message)

    def optimize_batch(
        self,
        file_paths: List[str],
        options: OptimizeOptions,
    ) -> List[OptimizeResult]:
        """Optimize a list of image files.

        Args:
            file_paths: Absolute paths to image files.
            options: Compression / quantization settings.

        Returns:
            A list of ``OptimizeResult``, one per input file.
        """
        results: List[OptimizeResult] = []
        total = len(file_paths)

        for idx, src in enumerate(file_paths, start=1):
            if self._progress:
                self._progress(idx, total, os.path.basename(src))
            results.append(self._optimize_single(src, options))

        return results

    def _optimize_single(
        self, src_path: str, options: OptimizeOptions
    ) -> OptimizeResult:
        """Optimize a single image file.

        Pipeline:
            1. Choose processing path (Pillow or Wand).
            2. Apply colour-mode conversion.
            3. Optionally quantize to indexed palette.
            4. Save as optimised PNG to a temporary file.
            5. Compare sizes; skip if larger when requested.
            6. Move result to destination.

        Args:
            src_path: Absolute path to the source image.
            options: Compression / quantization settings.

        Returns:
            An ``OptimizeResult`` describing the outcome.
        """
        result = OptimizeResult(source_path=src_path)
        basename = os.path.basename(src_path)
        self._log(f"[ImageOptimizer] Processing: {basename}")

        try:
            original_size = os.path.getsize(src_path)
            result.original_size = original_size
            dest_path = self._resolve_dest(src_path, options)
            self._log(
                f"[ImageOptimizer]   Source size: {self.format_size(original_size)}"
            )
            self._log(f"[ImageOptimizer]   Destination: {dest_path}")
            self._log(
                f"[ImageOptimizer]   Quantize={options.quantize}, "
                f"Method={options.quantize_method.value}, "
                f"Colors={options.max_colors}, "
                f"ColorMode={options.color_mode.value}"
            )

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(tmp_fd)

            try:
                if (
                    options.quantize
                    and options.quantize_method is QuantizeMethod.IMAGEMAGICK
                ):
                    self._log("[ImageOptimizer]   Using Wand/ImageMagick pipeline")
                    self._process_with_wand(src_path, tmp_path, options)
                else:
                    self._log("[ImageOptimizer]   Using Pillow pipeline")
                    self._process_with_pillow(src_path, tmp_path, options)

                optimized_size = os.path.getsize(tmp_path)
                self._log(
                    f"[ImageOptimizer]   Optimized size: "
                    f"{self.format_size(optimized_size)} "
                    f"(was {self.format_size(original_size)})"
                )

                if options.quantize:
                    try:
                        orig_img = Image.open(src_path).convert("RGBA")
                        opt_img = Image.open(tmp_path).convert("RGBA")
                        orig_arr = np.asarray(orig_img, dtype=np.float64)
                        opt_arr = np.asarray(opt_img, dtype=np.float64)
                        ssim_val = ssim_from_arrays(orig_arr, opt_arr)
                        result.ssim = ssim_val
                        self._log(f"[ImageOptimizer]   SSIM: {ssim_val:.4f}")
                        orig_img.close()
                        opt_img.close()
                    except Exception:
                        pass

                if options.skip_if_larger and optimized_size >= original_size:
                    os.remove(tmp_path)
                    result.optimized_size = original_size
                    result.output_path = src_path
                    result.skipped = True
                    self._log("[ImageOptimizer]   SKIPPED (result not smaller)")
                else:
                    shutil.move(tmp_path, dest_path)
                    result.optimized_size = optimized_size
                    result.output_path = dest_path
                    savings_pct = (
                        (original_size - optimized_size) / original_size * 100
                        if original_size > 0
                        else 0
                    )
                    self._log(f"[ImageOptimizer]   OK  saved {savings_pct:.1f}%")

            except Exception as inner_exc:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise RuntimeError(
                    f"Processing failed for {basename}: "
                    f"{type(inner_exc).__name__}: {inner_exc}"
                ) from inner_exc

        except Exception as exc:
            error_msg = str(exc) or repr(exc)
            tb_str = traceback.format_exc()
            self._log(f"[ImageOptimizer] ERROR on {basename}: {error_msg}")
            self._log(f"[ImageOptimizer] Traceback:\n{tb_str}")
            result.success = False
            result.error = error_msg

        return result

    def _resolve_dest(self, src_path: str, options: OptimizeOptions) -> str:
        """Determine the output path for an optimized file.

        Args:
            src_path: Absolute path to the source image.
            options: Settings that control overwrite behaviour and output directory.

        Returns:
            Absolute path for the optimized file.
        """
        if options.overwrite:
            return src_path
        dest_dir = options.output_dir or os.path.dirname(src_path)
        os.makedirs(dest_dir, exist_ok=True)
        return str(
            Path(os.path.join(dest_dir, os.path.basename(src_path))).with_suffix(".png")
        )

    def _process_with_pillow(
        self, src_path: str, tmp_path: str, options: OptimizeOptions
    ) -> None:
        """Run the Pillow-only pipeline: colour-mode -> quantize -> save PNG.

        Args:
            src_path: Absolute path to the source image.
            tmp_path: Temporary file to write the optimized PNG to.
            options: Compression / quantization settings.
        """
        img = Image.open(src_path)
        self._log(f"[ImageOptimizer]   Opened image: mode={img.mode}, size={img.size}")

        img = self._apply_color_mode(img, options)
        self._log(f"[ImageOptimizer]   After color mode: mode={img.mode}")

        if options.quantize:
            self._log(
                f"[ImageOptimizer]   Quantizing: method={options.quantize_method.value}, "
                f"colors={options.max_colors}, dither={options.dither.value}"
            )
            img = quantize_pillow(img, options, log=self._log, src_path=src_path)
            self._log(f"[ImageOptimizer]   After quantize: mode={img.mode}")

        save_kwargs = self._build_save_kwargs(img, options)
        self._log(f"[ImageOptimizer]   Saving PNG with kwargs: {save_kwargs}")
        img.save(tmp_path, **save_kwargs)
        img.close()

    def _process_with_wand(
        self, src_path: str, tmp_path: str, options: OptimizeOptions
    ) -> None:
        """Wand/ImageMagick quantization followed by Pillow PNG save.

        ImageMagick provides superior RGBA-aware quantization with
        configurable dithering.  The result is re-saved by Pillow for
        optimal PNG deflate compression.

        Args:
            src_path: Absolute path to the source image.
            tmp_path: Temporary file to write the optimized PNG to.
            options: Compression / quantization settings.

        Raises:
            RuntimeError: If the Wand library is not installed.
        """
        try:
            from wand.image import Image as WandImage
        except ImportError as exc:
            raise RuntimeError(
                "ImageMagick quantization requires the Wand library. "
                "Install it with: pip install Wand"
            ) from exc

        with WandImage(filename=src_path) as wand_img:
            self._log(
                f"[ImageOptimizer]   Wand opened: "
                f"{wand_img.width}x{wand_img.height}, "
                f"depth={wand_img.depth}, type={wand_img.type}"
            )

            if options.color_mode is ColorMode.RGB:
                wand_img.alpha_channel = "remove"
                self._log("[ImageOptimizer]   Wand: removed alpha")
            elif options.color_mode is ColorMode.GRAYSCALE:
                wand_img.transform_colorspace("gray")
                wand_img.alpha_channel = "remove"
                self._log("[ImageOptimizer]   Wand: grayscale, no alpha")
            elif options.color_mode is ColorMode.GRAYSCALE_ALPHA:
                wand_img.transform_colorspace("gray")
                self._log("[ImageOptimizer]   Wand: grayscale + alpha")

            dither_str = wand_dither_string(options.dither)
            self._log(
                f"[ImageOptimizer]   Wand quantize: "
                f"colors={options.max_colors}, dither={dither_str}"
            )
            wand_img.quantize(
                number_colors=options.max_colors,
                treedepth=0,
                dither=dither_str,
                measure_error=False,
            )

            if options.strip_metadata:
                wand_img.strip()

            wand_img.save(filename=tmp_path)
            self._log("[ImageOptimizer]   Wand saved temp file")

        pil_img = Image.open(tmp_path)
        pil_img.load()  # read into memory so we can overwrite the file
        self._log(
            f"[ImageOptimizer]   Re-saving through Pillow: "
            f"mode={pil_img.mode}, compress_level={options.compress_level}"
        )
        pil_img.save(
            tmp_path,
            format="PNG",
            optimize=options.optimize,
            compress_level=options.compress_level,
        )
        pil_img.close()

    @staticmethod
    def _apply_color_mode(img: Image.Image, options: OptimizeOptions) -> Image.Image:
        """Convert *img* to the colour mode specified in *options*.

        Args:
            img: Source image.
            options: Settings whose ``color_mode`` field controls conversion.

        Returns:
            The converted image, or the original if no conversion is needed.
        """
        mode = options.color_mode

        if mode is ColorMode.KEEP:
            return img

        target = mode.value  # "RGBA", "RGB", "LA", "L"
        if img.mode != target:
            img = img.convert(target)
        return img

    @staticmethod
    def _build_save_kwargs(img: Image.Image, options: OptimizeOptions) -> dict:
        """Build keyword arguments for ``Image.save()``.

        Args:
            img: The image about to be saved.
            options: Settings controlling PNG compression and metadata stripping.

        Returns:
            A dict suitable for unpacking into ``Image.save()``.
        """
        kwargs: dict = {
            "format": "PNG",
            "optimize": options.optimize,
            "compress_level": options.compress_level,
        }

        if not options.strip_metadata and hasattr(img, "info"):
            kwargs["pnginfo"] = img.info.get("pnginfo")

        return kwargs

    @staticmethod
    def collect_images(directory: str) -> List[str]:
        """Recursively collect all supported image files from a directory.

        Args:
            directory: Root directory to scan.

        Returns:
            Sorted list of absolute paths.
        """
        found: List[str] = []
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                    found.append(os.path.join(root, fname))
        found.sort()
        return found

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Human-readable file size string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
