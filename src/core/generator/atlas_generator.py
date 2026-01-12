#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Atlas generator that combines packing and exporting.

Provides the main generation pipeline: load images, pack them using
the selected algorithm, composite the atlas image, and export metadata.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from packers import (
    ExpandStrategy,
    FrameInput,
    PackedFrame,
    PackerOptions,
    PackerResult,
    get_packer,
    list_algorithms,
)
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import GeneratorMetadata
from utils.version import APP_VERSION


@dataclass
class GeneratorOptions:
    """Options for atlas generation.

    Attributes:
        algorithm: Packing algorithm name (e.g., 'maxrects', 'guillotine').
        heuristic: Algorithm-specific heuristic key.
        max_width: Maximum atlas width.
        max_height: Maximum atlas height.
        padding: Pixels between sprites.
        border_padding: Pixels around atlas edge.
        power_of_two: Force power-of-two dimensions.
        force_square: Force square atlas.
        allow_rotation: Allow 90° rotation for tighter packing.
        allow_flip: Allow sprite flipping (limited format support).
        trim_sprites: Trim transparent edges from sprites for tighter packing.
        expand_strategy: How to grow atlas when sprites don't fit.
        image_format: Output image format (png, webp, etc.).
        export_format: Metadata format key (e.g., 'starling-xml', 'json-hash').
        compression_settings: Format-specific compression options dict.
    """

    algorithm: str = "maxrects"
    heuristic: Optional[str] = None
    max_width: int = 4096
    max_height: int = 4096
    padding: int = 2
    border_padding: int = 0
    power_of_two: bool = False
    force_square: bool = False
    allow_rotation: bool = False
    allow_flip: bool = False
    trim_sprites: bool = False
    expand_strategy: str = "short_side"
    image_format: str = "png"
    export_format: str = "starling-xml"
    compression_settings: Optional[Dict[str, Any]] = None

    def to_packer_options(self) -> PackerOptions:
        """Convert to PackerOptions for the packer system."""
        strategy_map = {
            "disabled": ExpandStrategy.DISABLED,
            "width_first": ExpandStrategy.WIDTH_FIRST,
            "height_first": ExpandStrategy.HEIGHT_FIRST,
            "short_side": ExpandStrategy.SHORT_SIDE,
            "long_side": ExpandStrategy.LONG_SIDE,
            "both": ExpandStrategy.BOTH,
        }
        expand = strategy_map.get(self.expand_strategy, ExpandStrategy.SHORT_SIDE)

        return PackerOptions(
            max_width=self.max_width,
            max_height=self.max_height,
            padding=self.padding,
            border_padding=self.border_padding,
            power_of_two=self.power_of_two,
            force_square=self.force_square,
            allow_rotation=self.allow_rotation,
            allow_flip=self.allow_flip,
            expand_strategy=expand,
            sort_by_max_side=True,
        )


@dataclass
class GeneratorResult:
    """Result of atlas generation.

    Attributes:
        success: Whether generation succeeded.
        atlas_path: Path to the generated atlas image.
        metadata_path: Path to the generated metadata file.
        atlas_width: Final atlas width.
        atlas_height: Final atlas height.
        frame_count: Number of packed frames.
        efficiency: Packing efficiency (0.0-1.0).
        errors: List of error messages.
        warnings: List of warning messages.
    """

    success: bool = False
    atlas_path: str = ""
    metadata_path: str = ""
    atlas_width: int = 0
    atlas_height: int = 0
    frame_count: int = 0
    efficiency: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing UI."""
        return {
            "success": self.success,
            "atlas_path": self.atlas_path,
            "metadata_files": [self.metadata_path] if self.metadata_path else [],
            "atlas_size": (self.atlas_width, self.atlas_height),
            "frames_count": self.frame_count,
            "efficiency": self.efficiency * 100,  # Convert to percentage
            "errors": self.errors,
            "warnings": self.warnings,
        }


class AtlasGenerator:
    """Main atlas generation pipeline."""

    def __init__(self) -> None:
        self._progress_callback: Optional[Callable[[int, int, str], None]] = None

    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Set callback for progress updates.

        Args:
            callback: Function(current, total, message) called during generation.
        """
        self._progress_callback = callback

    def _emit_progress(self, current: int, total: int, message: str) -> None:
        """Emit progress update if callback is set."""

        if self._progress_callback:
            self._progress_callback(current, total, message)

    @staticmethod
    def _trim_image(img: Image.Image) -> Tuple[Image.Image, int, int, int, int]:
        """Trim transparent edges from an image.

        Finds the bounding box of non-transparent pixels and crops to it.
        Uses NumPy for efficient bounding box calculation.

        Args:
            img: PIL Image to trim (must be RGBA mode).

        Returns:
            Tuple of (trimmed_image, trim_left, trim_top, original_width, original_height).
            If the image is fully transparent, returns a 1x1 crop with zero offsets.
        """
        original_width, original_height = img.width, img.height

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        arr = np.asarray(img)
        alpha = arr[:, :, 3]

        rows_with_content = np.any(alpha > 0, axis=1)
        cols_with_content = np.any(alpha > 0, axis=0)

        if not np.any(rows_with_content):
            # Fully transparent image - return 1x1 to avoid zero-size issues
            return img.crop((0, 0, 1, 1)), 0, 0, original_width, original_height

        row_indices = np.where(rows_with_content)[0]
        col_indices = np.where(cols_with_content)[0]

        top = int(row_indices[0])
        bottom = int(row_indices[-1]) + 1
        left = int(col_indices[0])
        right = int(col_indices[-1]) + 1

        trimmed = img.crop((left, top, right, bottom))

        return trimmed, left, top, original_width, original_height

    @staticmethod
    def _compute_image_hash(img: Image.Image) -> str:
        """Compute a hash for image content comparison.

        Uses a fast hash of raw pixel data. Images that are 100% identical
        (same dimensions, mode, and pixels) will produce the same hash.

        Args:
            img: PIL Image to hash.

        Returns:
            Hex digest string uniquely identifying the image content.
        """
        # Ensure consistent mode for comparison
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Get raw pixel data as bytes
        pixel_bytes = img.tobytes()

        # Include dimensions in hash to avoid collisions from resized images
        header = f"{img.width}x{img.height}:{img.mode}:".encode("utf-8")

        # Use SHA-256 for a good balance of speed and collision resistance
        hasher = hashlib.sha256()
        hasher.update(header)
        hasher.update(pixel_bytes)

        return hasher.hexdigest()

    @staticmethod
    def _compute_flip_hashes(
        img: Image.Image,
    ) -> Dict[str, Tuple[str, bool, bool]]:
        """Compute hashes for all flipped variants of an image.

        Args:
            img: PIL Image to compute flip hashes for.

        Returns:
            Dict mapping hash -> (variant_name, flip_x, flip_y) for each variant:
            - "original": (hash, False, False)
            - "flip_x": (hash, True, False) - horizontal flip
            - "flip_y": (hash, False, True) - vertical flip
            - "flip_xy": (hash, True, True) - both flips
        """
        from PIL import ImageOps

        result = {}

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        original_hash = AtlasGenerator._compute_image_hash(img)
        result[original_hash] = ("original", False, False)

        flip_x_img = ImageOps.mirror(img)
        flip_x_hash = AtlasGenerator._compute_image_hash(flip_x_img)
        if flip_x_hash not in result:
            result[flip_x_hash] = ("flip_x", True, False)

        flip_y_img = ImageOps.flip(img)
        flip_y_hash = AtlasGenerator._compute_image_hash(flip_y_img)
        if flip_y_hash not in result:
            result[flip_y_hash] = ("flip_y", False, True)

        flip_xy_img = ImageOps.mirror(ImageOps.flip(img))
        flip_xy_hash = AtlasGenerator._compute_image_hash(flip_xy_img)
        if flip_xy_hash not in result:
            result[flip_xy_hash] = ("flip_xy", True, True)

        return result

    def generate(
        self,
        animation_groups: Dict[str, List[str]],
        output_path: str,
        options: Optional[GeneratorOptions] = None,
    ) -> GeneratorResult:
        """Generate an atlas from animation groups.

        Args:
            animation_groups: Dict mapping animation names to lists of frame paths.
            output_path: Base output path (without extension).
            options: Generation options.

        Returns:
            GeneratorResult with paths, dimensions, and status.
        """
        options = options or GeneratorOptions()
        result = GeneratorResult()

        try:
            self._emit_progress(0, 4, "Loading images...")
            load_result = self._load_images_with_dedup(
                animation_groups,
                trim_sprites=options.trim_sprites,
                allow_flip=options.allow_flip,
            )
            unique_frames = load_result["unique_frames"]
            images = load_result["images"]
            duplicate_map = load_result["duplicate_map"]
            all_frame_data = load_result["all_frame_data"]

            if not unique_frames:
                result.errors.append("No valid images found to pack")
                return result

            duplicate_count = len(all_frame_data) - len(unique_frames)
            if duplicate_count > 0:
                result.warnings.append(
                    f"Detected {duplicate_count} duplicate frame(s), "
                    f"packing {len(unique_frames)} unique frames"
                )

            self._emit_progress(1, 4, f"Packing with {options.algorithm}...")
            pack_result = self._pack_frames(unique_frames, options)

            if not pack_result.success:
                for err in pack_result.errors:
                    result.errors.append(err.message)
                return result

            self._emit_progress(2, 4, "Compositing atlas...")
            atlas_image = self._composite_atlas(
                pack_result.packed_frames,
                images,
                pack_result.atlas_width,
                pack_result.atlas_height,
                options.padding,
            )

            expanded_packed_frames = self._expand_packed_frames_with_duplicates(
                pack_result.packed_frames,
                duplicate_map,
                all_frame_data,
            )

            self._emit_progress(3, 4, "Saving files...")
            atlas_path, metadata_path = self._save_output(
                atlas_image,
                pack_result,
                output_path,
                options,
                expanded_packed_frames,
            )

            result.success = True
            result.atlas_path = atlas_path
            result.metadata_path = metadata_path
            result.atlas_width = pack_result.atlas_width
            result.atlas_height = pack_result.atlas_height
            result.frame_count = len(all_frame_data)
            result.efficiency = pack_result.efficiency

            self._emit_progress(4, 4, "Complete!")

        except Exception as e:
            result.errors.append(f"Generation failed: {e}")

        return result

    def _load_images_with_dedup(
        self,
        animation_groups: Dict[str, List[str]],
        trim_sprites: bool = False,
        allow_flip: bool = False,
    ) -> Dict[str, Any]:
        """Load images with duplicate and flip-variant detection.

        Args:
            animation_groups: Dict mapping animation names to frame path lists.
            trim_sprites: If True, trim transparent edges from sprites.
            allow_flip: If True, detect flipped variants as duplicates.

        Returns:
            Dict with keys: unique_frames, images, duplicate_map, all_frame_data.
        """
        all_frame_data: List[FrameInput] = []
        unique_frames: List[FrameInput] = []
        images: Dict[str, Image.Image] = {}
        hash_to_canonical: Dict[str, str] = {}
        duplicate_map: Dict[str, str] = {}

        for anim_name, frame_paths in animation_groups.items():
            for idx, path in enumerate(frame_paths):
                try:
                    img = Image.open(path)
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")

                    original_width, original_height = img.width, img.height
                    trim_offset_x, trim_offset_y = 0, 0

                    if trim_sprites:
                        (
                            img,
                            trim_offset_x,
                            trim_offset_y,
                            original_width,
                            original_height,
                        ) = self._trim_image(img)

                    frame_id = f"{anim_name}_{idx:04d}"
                    path_obj = Path(path)

                    frame_input = FrameInput(
                        id=frame_id,
                        width=img.width,
                        height=img.height,
                        user_data={
                            "path": path,
                            "name": path_obj.stem,
                            "animation": anim_name,
                            "index": idx,
                            "trim_offset_x": trim_offset_x,
                            "trim_offset_y": trim_offset_y,
                            "original_width": original_width,
                            "original_height": original_height,
                            "trimmed": trim_sprites
                            and (
                                trim_offset_x != 0
                                or trim_offset_y != 0
                                or img.width != original_width
                                or img.height != original_height
                            ),
                        },
                    )
                    all_frame_data.append(frame_input)

                    img_hash = self._compute_image_hash(img)

                    if img_hash in hash_to_canonical:
                        canonical_id, _, _ = hash_to_canonical[img_hash]
                        duplicate_map[frame_id] = (canonical_id, False, False)
                    elif allow_flip:
                        found_flip_match = False
                        flip_hashes = self._compute_flip_hashes(img)

                        for existing_hash, (
                            canonical_id,
                            canonical_flip_x,
                            canonical_flip_y,
                        ) in hash_to_canonical.items():
                            if existing_hash in flip_hashes:
                                _, flip_x, flip_y = flip_hashes[existing_hash]
                                final_flip_x = flip_x ^ canonical_flip_x
                                final_flip_y = flip_y ^ canonical_flip_y
                                duplicate_map[frame_id] = (
                                    canonical_id,
                                    final_flip_x,
                                    final_flip_y,
                                )
                                found_flip_match = True
                                break

                        if not found_flip_match:
                            hash_to_canonical[img_hash] = (frame_id, False, False)
                            unique_frames.append(frame_input)
                            images[frame_id] = img
                    else:
                        hash_to_canonical[img_hash] = (frame_id, False, False)
                        unique_frames.append(frame_input)
                        images[frame_id] = img

                except Exception as e:
                    print(f"Warning: Failed to load {path}: {e}")

        return {
            "unique_frames": unique_frames,
            "images": images,
            "duplicate_map": duplicate_map,
            "all_frame_data": all_frame_data,
        }

    def _expand_packed_frames_with_duplicates(
        self,
        packed_frames: List[PackedFrame],
        duplicate_map: Dict[str, Tuple[str, bool, bool]],
        all_frame_data: List[FrameInput],
    ) -> List[PackedFrame]:
        """Expand packed frames to include duplicate entries.

        Args:
            packed_frames: Packed frames for unique images only.
            duplicate_map: Maps duplicate IDs to (canonical_id, flip_x, flip_y).
            all_frame_data: All frame inputs including duplicates.

        Returns:
            PackedFrame list for all frames, with duplicates sharing positions.
        """
        if not duplicate_map:
            return packed_frames

        packed_lookup: Dict[str, PackedFrame] = {pf.id: pf for pf in packed_frames}

        expanded: List[PackedFrame] = []

        for frame in all_frame_data:
            if frame.id in duplicate_map:
                canonical_id, flip_x, flip_y = duplicate_map[frame.id]
                canonical_packed = packed_lookup.get(canonical_id)
                if canonical_packed:
                    final_flip_x = flip_x ^ canonical_packed.flipped_x
                    final_flip_y = flip_y ^ canonical_packed.flipped_y
                    duplicate_packed = PackedFrame(
                        frame=frame,
                        x=canonical_packed.x,
                        y=canonical_packed.y,
                        rotated=canonical_packed.rotated,
                        flipped_x=final_flip_x,
                        flipped_y=final_flip_y,
                    )
                    expanded.append(duplicate_packed)
            else:
                packed = packed_lookup.get(frame.id)
                if packed:
                    expanded.append(packed)

        return expanded

    def _load_images(
        self,
        animation_groups: Dict[str, List[str]],
    ) -> Tuple[List[FrameInput], Dict[str, Image.Image]]:
        """Load images from animation groups without deduplication.

        Args:
            animation_groups: Dict mapping animation names to frame path lists.

        Returns:
            Tuple of (frame inputs, dict mapping frame IDs to images).
        """
        frame_data: List[FrameInput] = []
        images: Dict[str, Image.Image] = {}

        for anim_name, frame_paths in animation_groups.items():
            for idx, path in enumerate(frame_paths):
                try:
                    img = Image.open(path)
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")

                    frame_id = f"{anim_name}_{idx:04d}"
                    path_obj = Path(path)

                    frame_input = FrameInput(
                        id=frame_id,
                        width=img.width,
                        height=img.height,
                        user_data={
                            "path": path,
                            "name": path_obj.stem,
                            "animation": anim_name,
                            "index": idx,
                        },
                    )
                    frame_data.append(frame_input)
                    images[frame_id] = img

                except Exception as e:
                    print(f"Warning: Failed to load {path}: {e}")

        return frame_data, images

    def _pack_frames(
        self,
        frames: List[FrameInput],
        options: GeneratorOptions,
    ) -> PackerResult:
        """Pack frames using the selected algorithm.

        Handles "auto" algorithm/heuristic selection and automatic retry
        with larger dimensions on size-constraint failures.

        Args:
            frames: Frames to pack.
            options: Generator options.

        Returns:
            PackerResult with packed frames and dimensions.
        """
        ABSOLUTE_MAX = 16384
        current_max_width = options.max_width
        current_max_height = options.max_height

        while current_max_width <= ABSOLUTE_MAX and current_max_height <= ABSOLUTE_MAX:
            packer_options = options.to_packer_options()
            packer_options.max_width = current_max_width
            packer_options.max_height = current_max_height
            algorithm = options.algorithm

            if algorithm == "auto":
                result = self._pack_with_best_algorithm(
                    frames, packer_options, options.heuristic
                )
            elif options.heuristic == "auto" or options.heuristic is None:
                result = self._pack_with_best_heuristic(
                    frames, algorithm, packer_options
                )
            else:
                packer = get_packer(algorithm, packer_options)
                packer.set_heuristic(options.heuristic)
                result = packer.pack(frames)

            if result.success:
                return result

            size_error = any(
                e.code.name in ("CANNOT_FIT_ALL", "FRAME_TOO_LARGE")
                for e in result.errors
            )

            if not size_error:
                return result

            if current_max_width >= ABSOLUTE_MAX and current_max_height >= ABSOLUTE_MAX:
                return result

            old_width, old_height = current_max_width, current_max_height
            current_max_width = min(current_max_width + 1024, ABSOLUTE_MAX)
            current_max_height = min(current_max_height + 1024, ABSOLUTE_MAX)

            if current_max_width == old_width and current_max_height == old_height:
                return result

            self._emit_progress(
                1,
                4,
                f"Retrying with larger atlas ({current_max_width}x{current_max_height})...",
            )

        return result

    def _calculate_packing_score(
        self, result: PackerResult, options: PackerOptions
    ) -> float:
        """Calculate a score for comparing packing results (lower is better).

        Primary metric is atlas area. When power_of_two is enabled, applies
        bonuses for exact POT dimensions and penalties for near-POT sizes.

        Args:
            result: The packing result to score.
            options: Packer options.

        Returns:
            Float score where lower is better.
        """
        width = result.atlas_width
        height = result.atlas_height
        area = width * height

        score = float(area)

        if options.power_of_two:

            def is_power_of_two(n: int) -> bool:
                return n > 0 and (n & (n - 1)) == 0

            def next_power_of_two(n: int) -> int:
                if n <= 0:
                    return 1
                p = 1
                while p < n:
                    p <<= 1
                return p

            def prev_power_of_two(n: int) -> int:
                if n <= 0:
                    return 1
                p = 1
                while p * 2 <= n:
                    p <<= 1
                return p

            pot_bonus = 0.0
            if is_power_of_two(width):
                pot_bonus += 0.02 * area
            if is_power_of_two(height):
                pot_bonus += 0.02 * area
            score -= pot_bonus

            for dim in (width, height):
                if not is_power_of_two(dim):
                    next_pot = next_power_of_two(dim)
                    prev_pot = prev_power_of_two(dim)
                    if next_pot > prev_pot:
                        overshoot = (dim - prev_pot) / (next_pot - prev_pot)
                        if overshoot < 0.1:
                            near_pot_penalty = (0.1 - overshoot) * area * 0.05
                            score += near_pot_penalty

        return score

    def _pack_with_best_algorithm(
        self,
        frames: List[FrameInput],
        options: PackerOptions,
        heuristic_hint: Optional[str] = None,
    ) -> PackerResult:
        """Try all algorithms and return the result with best score.

        Args:
            frames: Frames to pack.
            options: Packer options.
            heuristic_hint: Heuristic to use, or "auto"/None to try all.

        Returns:
            PackerResult with the best (smallest) score.
        """
        algorithms = list_algorithms()

        best_result: Optional[PackerResult] = None
        best_score: float = float("inf")
        auto_heuristic = heuristic_hint == "auto" or heuristic_hint is None

        for algo_info in algorithms:
            algo_name = algo_info.get("name", "")
            if not algo_name or algo_name == "auto":
                continue

            try:
                if auto_heuristic:
                    result = self._pack_with_best_heuristic(frames, algo_name, options)
                else:
                    packer = get_packer(algo_name, options)
                    packer.set_heuristic(heuristic_hint)
                    result = packer.pack(frames)

                if not result.success:
                    continue

                # Use comprehensive scoring
                score = self._calculate_packing_score(result, options)

                if best_result is None or score < best_score:
                    best_result = result
                    best_score = score

            except Exception as e:
                print(f"Warning: Algorithm '{algo_name}' failed: {e}")
                continue

        if best_result is None:
            packer = get_packer("maxrects", options)
            return packer.pack(frames)

        return best_result

    def _pack_with_best_heuristic(
        self,
        frames: List[FrameInput],
        algorithm: str,
        options: PackerOptions,
    ) -> PackerResult:
        """Try all heuristics for an algorithm and return the best result.

        Args:
            frames: Frames to pack.
            algorithm: Algorithm name.
            options: Packer options.

        Returns:
            PackerResult with the best (smallest) score.
        """
        from packers import get_heuristics_for_algorithm

        heuristics = get_heuristics_for_algorithm(algorithm)

        if not heuristics:
            packer = get_packer(algorithm, options)
            return packer.pack(frames)

        best_result: Optional[PackerResult] = None
        best_score: float = float("inf")

        for heuristic_key, _ in heuristics:
            try:
                packer = get_packer(algorithm, options)
                packer.set_heuristic(heuristic_key)
                result = packer.pack(frames)

                if not result.success:
                    continue

                score = self._calculate_packing_score(result, options)

                if best_result is None or score < best_score:
                    best_result = result
                    best_score = score

            except Exception as e:
                print(f"Warning: Heuristic '{heuristic_key}' failed: {e}")
                continue

        if best_result is None:
            packer = get_packer(algorithm, options)
            return packer.pack(frames)

        return best_result

    def _composite_atlas(
        self,
        packed_frames: List[PackedFrame],
        images: Dict[str, Image.Image],
        width: int,
        height: int,
        padding: int,
    ) -> Image.Image:
        """Composite packed frames onto a transparent atlas image.

        Args:
            packed_frames: Frames with assigned positions.
            images: Dict mapping frame IDs to images.
            width: Atlas width.
            height: Atlas height.
            padding: Padding between sprites (unused, positions already include it).

        Returns:
            Composited RGBA atlas image.
        """
        atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        for packed in packed_frames:
            img = images.get(packed.id)
            if img is None:
                continue

            if img.mode != "RGBA":
                img = img.convert("RGBA")

            if packed.rotated:
                img = img.transpose(Image.Transpose.ROTATE_270)

            atlas.alpha_composite(img, (packed.x, packed.y))

        return atlas

    def _build_save_kwargs(self, options: GeneratorOptions) -> Dict[str, Any]:
        """Build PIL save kwargs from format and compression settings.

        Args:
            options: Generator options with format and compression settings.

        Returns:
            Dict of kwargs for PIL's Image.save().
        """
        fmt = options.image_format.lower()
        user_settings = options.compression_settings or {}
        save_kwargs: Dict[str, Any] = {}

        if fmt == "png":
            save_kwargs["compress_level"] = user_settings.get("compress_level", 9)
            save_kwargs["optimize"] = user_settings.get("optimize", True)

        elif fmt == "webp":
            lossless = user_settings.get("lossless", True)
            save_kwargs["lossless"] = lossless
            if lossless:
                save_kwargs["quality"] = user_settings.get("quality", 90)
            else:
                save_kwargs["quality"] = user_settings.get("quality", 85)
            if "method" in user_settings:
                save_kwargs["method"] = user_settings["method"]

        elif fmt in ("jpg", "jpeg"):
            save_kwargs["quality"] = user_settings.get("quality", 95)
            save_kwargs["optimize"] = user_settings.get("optimize", True)
            if "progressive" in user_settings:
                save_kwargs["progressive"] = user_settings["progressive"]
            if "subsampling" in user_settings:
                save_kwargs["subsampling"] = user_settings["subsampling"]

        elif fmt == "tiff":
            compression = user_settings.get("compression", "tiff_lzw")
            save_kwargs["compression"] = compression

        elif fmt == "avif":
            save_kwargs["quality"] = user_settings.get("quality", 80)
            if "speed" in user_settings:
                save_kwargs["speed"] = user_settings["speed"]

        elif fmt == "bmp":
            pass

        elif fmt == "tga":
            if user_settings.get("rle", False):
                save_kwargs["rle"] = True

        elif fmt == "dds":
            pass

        return save_kwargs

    def _save_output(
        self,
        atlas_image: Image.Image,
        pack_result: PackerResult,
        output_path: str,
        options: GeneratorOptions,
        expanded_packed_frames: Optional[List[PackedFrame]] = None,
    ) -> Tuple[str, str]:
        """Save atlas image and metadata.

        Args:
            atlas_image: Composited atlas image.
            pack_result: Result from packer.
            output_path: Base output path without extension.
            options: Generator options.
            expanded_packed_frames: Optional list of all frames including duplicates.
                                    If None, uses pack_result.packed_frames.

        Returns:
            Tuple of (atlas_path, metadata_path).
        """
        output_base = Path(output_path)
        output_base.parent.mkdir(parents=True, exist_ok=True)

        image_ext = f".{options.image_format.lower()}"
        atlas_path = output_base.with_suffix(image_ext)
        save_kwargs = self._build_save_kwargs(options)
        atlas_image.save(str(atlas_path), **save_kwargs)

        frames_for_metadata = expanded_packed_frames or pack_result.packed_frames

        algorithm_name = pack_result.algorithm_name or options.algorithm or "Unknown"
        heuristic_name = pack_result.heuristic_name or options.heuristic or "Unknown"
        algorithm_name = algorithm_name.replace("_", " ").title()
        heuristic_name = heuristic_name.replace("_", " ").title()

        generator_metadata = GeneratorMetadata(
            app_version=APP_VERSION,
            packer=algorithm_name,
            heuristic=heuristic_name,
            efficiency=pack_result.efficiency * 100,
        )

        metadata_path = self._save_metadata(
            frames_for_metadata,
            pack_result.atlas_width,
            pack_result.atlas_height,
            output_base,
            atlas_path.name,
            options.export_format,
            generator_metadata,
            include_flip_attributes=options.allow_flip,
        )

        return str(atlas_path), metadata_path

    def _save_metadata(
        self,
        packed_frames: List[PackedFrame],
        atlas_width: int,
        atlas_height: int,
        output_base: Path,
        image_name: str,
        export_format: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
        include_flip_attributes: bool = False,
    ) -> str:
        """Generate and save metadata file.

        Args:
            packed_frames: All packed frames including duplicates.
            atlas_width: Width of the atlas image.
            atlas_height: Height of the atlas image.
            output_base: Base path for output files.
            image_name: Name of the atlas image file.
            export_format: Format key for the exporter.
            generator_metadata: Optional metadata for watermarking.
            include_flip_attributes: If True, include flipX/flipY in output.

        Returns:
            Path to the saved metadata file, or empty string on failure.
        """
        animation_max_sizes: Dict[str, Tuple[int, int]] = {}
        for packed in packed_frames:
            user_data = packed.frame.user_data or {}
            animation_name = user_data.get("animation") or ""
            original_w = user_data.get("original_width", packed.source_width)
            original_h = user_data.get("original_height", packed.source_height)
            max_w, max_h = animation_max_sizes.get(animation_name, (0, 0))
            animation_max_sizes[animation_name] = (
                max(max_w, original_w),
                max(max_h, original_h),
            )

        sprites_data = []
        for packed in packed_frames:
            user_data = packed.frame.user_data or {}
            animation_name = user_data.get("animation") or ""
            original_w = user_data.get("original_width", packed.source_width)
            original_h = user_data.get("original_height", packed.source_height)
            trim_offset_x = user_data.get("trim_offset_x", 0)
            trim_offset_y = user_data.get("trim_offset_y", 0)
            was_trimmed = user_data.get("trimmed", False)
            sprite_width = packed.source_width
            sprite_height = packed.source_height
            max_w, max_h = animation_max_sizes.get(
                animation_name, (original_w, original_h)
            )

            if was_trimmed:
                frame_x = -trim_offset_x
                frame_y = -trim_offset_y
                frame_w = original_w
                frame_h = original_h
            else:
                frame_x = -((max_w - sprite_width) // 2)
                frame_y = -((max_h - sprite_height) // 2)
                frame_w = max_w
                frame_h = max_h

            sprite = {
                "name": user_data.get("name", packed.id),
                "x": packed.x,
                "y": packed.y,
                "width": sprite_width,
                "height": sprite_height,
                "frameX": frame_x,
                "frameY": frame_y,
                "frameWidth": frame_w,
                "frameHeight": frame_h,
                "source_width": original_w,
                "source_height": original_h,
                "rotated": packed.rotated,
                "flipX": packed.flipped_x,
                "flipY": packed.flipped_y,
                "animation": animation_name,
                "index": user_data.get("index", 0),
            }
            sprites_data.append(sprite)

        try:
            ExporterRegistry.initialize()

            exporter_cls = ExporterRegistry.get_exporter(export_format)
            if not exporter_cls:
                print(f"Warning: No exporter found for format: {export_format}")
                return ""

            from exporters.exporter_types import ExportOptions

            export_options = ExportOptions(pretty_print=True)

            if include_flip_attributes and export_format == "starling-xml":
                from exporters.starling_xml_exporter import StarlingExportOptions

                export_options.custom_properties["starling"] = StarlingExportOptions(
                    include_flip_attributes=True,
                )

            exporter = exporter_cls(export_options)
            metadata_ext = exporter.FILE_EXTENSION
            metadata_path = output_base.with_suffix(metadata_ext)

            from exporters.exporter_types import PackedSprite

            packed_sprites = []
            for sprite in sprites_data:
                packed_sprite = PackedSprite(
                    sprite=sprite,
                    atlas_x=sprite["x"],
                    atlas_y=sprite["y"],
                    rotated=sprite["rotated"],
                )
                packed_sprites.append(packed_sprite)

            metadata = exporter.build_metadata(
                packed_sprites,
                atlas_width,
                atlas_height,
                image_name,
                generator_metadata,
            )

            if isinstance(metadata, bytes):
                with open(metadata_path, "wb") as f:
                    f.write(metadata)
            else:
                with open(metadata_path, "w", encoding="utf-8") as f:
                    f.write(metadata)

            return str(metadata_path)

        except Exception as e:
            print(f"Warning: Failed to save metadata: {e}")
            return ""


def get_available_algorithms() -> List[Dict[str, Any]]:
    """Get list of available packing algorithms for UI.

    Returns:
        List of dicts with 'name', 'display_name', 'heuristics' keys.
    """
    return list_algorithms()


__all__ = [
    "AtlasGenerator",
    "GeneratorOptions",
    "GeneratorResult",
    "get_available_algorithms",
]
