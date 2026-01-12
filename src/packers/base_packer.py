#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Base class for texture atlas packing algorithms.

Provides the abstract interface that packers must implement, plus shared
utilities for frame preprocessing, atlas sizing, and result building.

Subclasses implement `_pack_internal` with their layout algorithm; the
base class handles validation, sorting, sizing strategies, and result
construction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from packers.packer_types import (
    ExpandStrategy,
    FrameInput,
    FrameTooLargeError,
    PackedFrame,
    PackerError,
    PackerErrorCode,
    PackerOptions,
    PackerResult,
)


class BasePacker(ABC):
    """Abstract base for texture atlas packing algorithms.

    Subclasses must define `ALGORITHM_NAME`, `DISPLAY_NAME`, and implement
    `_pack_internal`. The base class handles validation, sorting, atlas
    sizing, expansion, and result building.

    Attributes:
        options: Packer configuration options.
    """

    ALGORITHM_NAME: str = ""
    DISPLAY_NAME: str = ""
    SUPPORTED_HEURISTICS: List[Tuple[str, str]] = []

    def __init__(self, options: Optional[PackerOptions] = None) -> None:
        """Initialize the packer with configuration options.

        Args:
            options: Packer options controlling sizing and layout behavior.
                     Defaults to PackerOptions() if not provided.
        """

        self.options = options or PackerOptions()
        self._current_heuristic: Optional[str] = None

    @abstractmethod
    def _pack_internal(
        self,
        frames: List[FrameInput],
        width: int,
        height: int,
    ) -> List[PackedFrame]:
        """Core packing algorithm implementation.

        Subclasses implement their layout logic here. Frames are already
        sorted and validated.

        Args:
            frames: Preprocessed frames to pack.
            width: Available atlas width in pixels.
            height: Available atlas height in pixels.

        Returns:
            Packed frames with positions, or empty list if they cannot fit.
        """
        pass

    def pack(self, frames: List[FrameInput]) -> PackerResult:
        """Pack frames into an atlas layout.

        Main entry point. Validates input, preprocesses frames, selects
        sizing strategy (POT-aware or aspect-ratio optimization), and
        builds the result with efficiency metrics.

        Args:
            frames: Frames to pack.

        Returns:
            Result containing packed frames, dimensions, and diagnostics.
        """
        result = PackerResult(algorithm_name=self.ALGORITHM_NAME)

        if not frames:
            result.add_error(
                PackerErrorCode.NO_FRAMES_PROVIDED,
                "No frames provided for packing",
            )
            return result

        try:
            self.options.validate()
            work_frames = [f.clone() for f in frames]
            self._validate_frames(work_frames)
            work_frames = self._sort_frames(work_frames)

            padding = self.options.padding
            border = self.options.border_padding
            max_frame_w = max(f.width for f in work_frames) + padding + 2 * border
            max_frame_h = max(f.height for f in work_frames) + padding + 2 * border
            total_frame_area = sum(
                (f.width + padding) * (f.height + padding) for f in work_frames
            )

            if self.options.power_of_two:
                candidates = self._generate_pot_candidates(
                    max_frame_w, max_frame_h, total_frame_area
                )

                if candidates:
                    packed, final_width, final_height = self._pack_with_pot_sizes(
                        work_frames, candidates
                    )

                    if packed:
                        if self.options.force_square:
                            final_width = final_height = max(final_width, final_height)

                        result.success = True
                        result.packed_frames = packed
                        result.atlas_width = final_width
                        result.atlas_height = final_height
                        result.heuristic_name = self._current_heuristic
                        result.calculate_efficiency()
                        return result

            best_result = self._pack_with_best_aspect_ratio(
                work_frames, total_frame_area, max_frame_w, max_frame_h
            )

            if best_result:
                packed, final_width, final_height = best_result

                if self.options.force_square:
                    final_width = final_height = max(final_width, final_height)

                result.success = True
                result.packed_frames = packed
                result.atlas_width = final_width
                result.atlas_height = final_height
                result.heuristic_name = self._current_heuristic
                result.calculate_efficiency()
                return result

            init_width, init_height = self._calculate_initial_size(work_frames)

            packed, final_width, final_height = self._pack_with_expansion(
                work_frames, init_width, init_height
            )

            if not packed:
                result.add_error(
                    PackerErrorCode.CANNOT_FIT_ALL,
                    f"Cannot fit all {len(frames)} frames within "
                    f"{self.options.max_width}x{self.options.max_height}",
                )
                return result

            if self.options.power_of_two:
                final_width = self._next_power_of_two(final_width)
                final_height = self._next_power_of_two(final_height)

            if self.options.force_square:
                final_width = final_height = max(final_width, final_height)

            result.success = True
            result.packed_frames = packed
            result.atlas_width = final_width
            result.atlas_height = final_height
            result.heuristic_name = self._current_heuristic
            result.calculate_efficiency()

        except PackerError as e:
            result.add_error(e.code, e.message, e.details)
        except Exception as e:
            result.add_error(
                PackerErrorCode.UNKNOWN_ERROR,
                f"Unexpected error during packing: {e}",
                details={"exception_type": type(e).__name__},
            )

        return result

    def set_heuristic(self, heuristic_key: str) -> bool:
        """Set the heuristic for packing.

        Args:
            heuristic_key: Key identifying the heuristic to use.

        Returns:
            True if set successfully, False if the key is not supported.
        """
        valid_keys = [h[0] for h in self.SUPPORTED_HEURISTICS]
        if heuristic_key in valid_keys:
            self._current_heuristic = heuristic_key
            return True
        elif not self.SUPPORTED_HEURISTICS:
            return True
        return False

    def _validate_frames(self, frames: List[FrameInput]) -> None:
        """Validate that all frames fit within maximum dimensions.

        Args:
            frames: Frames to validate.

        Raises:
            FrameTooLargeError: If any frame exceeds the configured maximum.
        """
        padding = self.options.padding
        border = self.options.border_padding
        max_w = self.options.max_width - 2 * border
        max_h = self.options.max_height - 2 * border

        for frame in frames:
            effective_w = frame.width + padding
            effective_h = frame.height + padding

            if self.options.allow_rotation:
                fits_normal = effective_w <= max_w and effective_h <= max_h
                fits_rotated = effective_h <= max_w and effective_w <= max_h
                if not (fits_normal or fits_rotated):
                    raise FrameTooLargeError(
                        PackerErrorCode.FRAME_TOO_LARGE,
                        f"Frame '{frame.id}' ({frame.width}x{frame.height}) "
                        f"exceeds maximum dimensions even when rotated",
                        details={"frame_id": frame.id, "max_size": (max_w, max_h)},
                    )
            else:
                if effective_w > max_w or effective_h > max_h:
                    raise FrameTooLargeError(
                        PackerErrorCode.FRAME_TOO_LARGE,
                        f"Frame '{frame.id}' ({frame.width}x{frame.height}) "
                        f"exceeds maximum dimensions ({max_w}x{max_h})",
                        details={"frame_id": frame.id, "max_size": (max_w, max_h)},
                    )

    def _sort_frames(self, frames: List[FrameInput]) -> List[FrameInput]:
        """Sort frames for better packing efficiency.

        Args:
            frames: Frames to sort.

        Returns:
            Sorted list of frames based on configured sort strategy.
        """

        if self.options.sort_by_area:
            return sorted(frames, key=lambda f: f.width * f.height, reverse=True)
        elif self.options.sort_by_max_side:
            return sorted(
                frames,
                key=lambda f: (max(f.width, f.height), min(f.width, f.height)),
                reverse=True,
            )
        return frames

    def _calculate_initial_size(self, frames: List[FrameInput]) -> Tuple[int, int]:
        """Calculate minimum atlas size that can fit the largest frame.

        Args:
            frames: Frames to measure.

        Returns:
            Tuple of (width, height) for the minimum initial atlas size.
        """
        padding = self.options.padding
        border = self.options.border_padding
        max_frame_w = max(f.width for f in frames) + padding
        max_frame_h = max(f.height for f in frames) + padding
        min_width = max_frame_w + 2 * border
        min_height = max_frame_h + 2 * border
        return (
            min(min_width, self.options.max_width),
            min(min_height, self.options.max_height),
        )

    def _pack_with_best_aspect_ratio(
        self,
        frames: List[FrameInput],
        total_frame_area: int,
        min_width: int,
        min_height: int,
    ) -> Optional[Tuple[List[PackedFrame], int, int]]:
        """Try multiple aspect ratios and return the result with best efficiency.

        Generates candidate canvas sizes at various aspect ratios, packs into
        each, and selects the layout with highest efficiency. Tries progressively
        looser efficiency estimates (95% -> 90% -> 85%) to find the tightest fit.

        Args:
            frames: Frames to pack.
            total_frame_area: Sum of frame bounding box areas including padding.
            min_width: Minimum width for the largest frame plus borders.
            min_height: Minimum height for the largest frame plus borders.

        Returns:
            Tuple of (packed_frames, width, height), or None if all failed.
        """
        import math

        max_w = self.options.max_width
        max_h = self.options.max_height
        border = self.options.border_padding

        aspect_ratios = [
            (1, 1),
            (4, 3),
            (3, 4),
            (3, 2),
            (2, 3),
            (16, 9),
            (9, 16),
            (2, 1),
            (1, 2),
        ]

        efficiency_targets = [1.0, 0.95, 0.90, 0.85, 0.80]

        for target_efficiency in efficiency_targets:
            estimated_area = int(total_frame_area / target_efficiency)
            candidates: List[Tuple[int, int]] = []

            for w_ratio, h_ratio in aspect_ratios:
                ratio = w_ratio / h_ratio
                width = int(math.sqrt(estimated_area * ratio))
                height = (
                    int(estimated_area / width)
                    if width > 0
                    else int(math.sqrt(estimated_area))
                )

                width = max(width, min_width)
                height = max(height, min_height)

                if width <= max_w and height <= max_h:
                    candidates.append((width, height))

            seen = set()
            unique_candidates = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    unique_candidates.append(c)

            best_packed: Optional[List[PackedFrame]] = None
            best_width = 0
            best_height = 0
            best_efficiency = 0.0

            for canvas_w, canvas_h in unique_candidates:
                packed = self._pack_internal(frames, canvas_w, canvas_h)

                if len(packed) == len(frames):
                    if packed:
                        tight_w = max(p.x + p.width for p in packed) + border
                        tight_h = max(p.y + p.height for p in packed) + border
                    else:
                        tight_w, tight_h = 0, 0

                    atlas_area = tight_w * tight_h
                    efficiency = (
                        total_frame_area / atlas_area if atlas_area > 0 else 0.0
                    )

                    if efficiency > best_efficiency:
                        best_efficiency = efficiency
                        best_packed = packed
                        best_width = tight_w
                        best_height = tight_h

            if best_packed:
                return best_packed, best_width, best_height

        return None

    def _pack_with_expansion(
        self,
        frames: List[FrameInput],
        init_width: int,
        init_height: int,
    ) -> Tuple[List[PackedFrame], int, int]:
        """Pack with automatic atlas expansion until frames fit or max is reached.

        Args:
            frames: Frames to pack.
            init_width: Starting atlas width.
            init_height: Starting atlas height.

        Returns:
            Tuple of (packed_frames, width, height), or ([], 0, 0) on failure.
        """
        width, height = init_width, init_height
        max_w, max_h = self.options.max_width, self.options.max_height
        strategy = self.options.expand_strategy

        while width <= max_w and height <= max_h:
            packed = self._pack_internal(frames, width, height)

            if len(packed) == len(frames):
                if packed:
                    final_w = max(p.x + p.width for p in packed)
                    final_h = max(p.y + p.height for p in packed)
                else:
                    final_w, final_h = 0, 0

                final_w += self.options.border_padding
                final_h += self.options.border_padding
                return packed, final_w, final_h

            if strategy == ExpandStrategy.DISABLED:
                break

            new_width, new_height = self._expand_atlas(width, height, strategy)
            if new_width == width and new_height == height:
                break

            width, height = new_width, new_height

        return [], 0, 0

    def _expand_atlas(
        self,
        width: int,
        height: int,
        strategy: ExpandStrategy,
    ) -> Tuple[int, int]:
        """Expand atlas dimensions according to the given strategy.

        Args:
            width: Current atlas width.
            height: Current atlas height.
            strategy: Expansion strategy determining which dimension grows.

        Returns:
            New (width, height) tuple after expansion.
        """
        max_w, max_h = self.options.max_width, self.options.max_height

        if strategy == ExpandStrategy.WIDTH_FIRST:
            if width < max_w:
                return min(width * 2, max_w), height
            else:
                return width, min(height * 2, max_h)

        elif strategy == ExpandStrategy.HEIGHT_FIRST:
            if height < max_h:
                return width, min(height * 2, max_h)
            else:
                return min(width * 2, max_w), height

        elif strategy == ExpandStrategy.SHORT_SIDE:
            if width <= height and width < max_w:
                return min(width * 2, max_w), height
            elif height < max_h:
                return width, min(height * 2, max_h)
            else:
                return min(width * 2, max_w), height

        elif strategy == ExpandStrategy.LONG_SIDE:
            if width >= height and width < max_w:
                return min(width * 2, max_w), height
            elif height < max_h:
                return width, min(height * 2, max_h)
            else:
                return min(width * 2, max_w), height

        elif strategy == ExpandStrategy.BOTH:
            return min(width * 2, max_w), min(height * 2, max_h)

        return width, height

    @staticmethod
    def _next_power_of_two(value: int) -> int:
        """Return the smallest power of two greater than or equal to value.

        Args:
            value: Input value to round up.

        Returns:
            Smallest power of two >= value, or 1 if value <= 0.
        """
        if value <= 0:
            return 1
        power = 1
        while power < value:
            power *= 2
        return power

    def _generate_pot_candidates(
        self,
        min_width: int,
        min_height: int,
        total_area: int,
    ) -> List[Tuple[int, int]]:
        """Generate power-of-two size candidates sorted by area ascending.

        Args:
            min_width: Minimum width for the largest frame.
            min_height: Minimum height for the largest frame.
            total_area: Total area of all frames for lower-bound filtering.

        Returns:
            List of (width, height) POT pairs, smallest area first.
        """
        max_w = self.options.max_width
        max_h = self.options.max_height
        min_pot_w = self._next_power_of_two(min_width)
        min_pot_h = self._next_power_of_two(min_height)
        max_pot_w = self._next_power_of_two(max_w) // 2
        max_pot_h = self._next_power_of_two(max_h) // 2
        if max_pot_w < min_pot_w:
            max_pot_w = min_pot_w
        if max_pot_h < min_pot_h:
            max_pot_h = min_pot_h

        candidates = []
        w = min_pot_w
        while w <= max_w:
            h = min_pot_h
            while h <= max_h:
                if w * h >= total_area * 0.8:
                    candidates.append((w, h))
                h *= 2
            w *= 2

        candidates.sort(key=lambda x: x[0] * x[1])

        return candidates

    def _pack_with_pot_sizes(
        self,
        frames: List[FrameInput],
        candidates: List[Tuple[int, int]],
    ) -> Tuple[List[PackedFrame], int, int]:
        """Try packing into POT candidate sizes, smallest first.

        Args:
            frames: Frames to pack.
            candidates: List of (width, height) POT sizes to try.

        Returns:
            Tuple of (packed_frames, width, height), or ([], 0, 0) on failure.
        """
        for width, height in candidates:
            packed = self._pack_internal(frames, width, height)

            if len(packed) == len(frames):
                return packed, width, height

        return [], 0, 0

    @classmethod
    def get_supported_heuristics(cls) -> List[Tuple[str, str]]:
        """Return a copy of the supported heuristics list.

        Returns:
            List of (key, display_name) tuples for each supported heuristic.
        """

        return cls.SUPPORTED_HEURISTICS.copy()

    @classmethod
    def can_pack(cls, algorithm_name: str) -> bool:
        """Check if this packer handles the given algorithm name.

        Args:
            algorithm_name: Algorithm name to check (case-insensitive).

        Returns:
            True if this packer handles the algorithm.
        """

        return algorithm_name.lower() == cls.ALGORITHM_NAME.lower()


class SimplePacker(BasePacker):
    """Row-based packer that places frames left-to-right, top-to-bottom.

    Fast but not space-efficient. Useful for ordered layouts where
    predictable frame positioning matters more than minimal atlas size.
    """

    ALGORITHM_NAME = "simple"
    DISPLAY_NAME = "Simple Row Packer"

    def _pack_internal(
        self,
        frames: List[FrameInput],
        width: int,
        height: int,
    ) -> List[PackedFrame]:
        packed: List[PackedFrame] = []
        padding = self.options.padding
        border = self.options.border_padding

        x = border
        y = border
        row_height = 0
        available_width = width - 2 * border
        available_height = height - 2 * border

        for frame in frames:
            frame_w = frame.width + padding
            frame_h = frame.height + padding

            if x + frame_w > border + available_width:
                x = border
                y += row_height
                row_height = 0

            if y + frame_h > border + available_height:
                return packed

            packed.append(PackedFrame(frame=frame, x=x, y=y))

            x += frame_w
            row_height = max(row_height, frame_h)

        return packed


__all__ = ["BasePacker", "SimplePacker"]
