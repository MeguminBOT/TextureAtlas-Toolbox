#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Guillotine bin packing algorithm with configurable split heuristics.

Subdivides the atlas into rectangular regions using guillotine cuts. When a
frame is placed, remaining space is split horizontally or vertically based on
the chosen split heuristic.

Based on Jukka Jylänki's paper "A Thousand Ways to Pack the Bin" and
reference implementation: https://github.com/juj/RectangleBinPack
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from packers.base_packer import BasePacker
from packers.packer_types import (
    FrameInput,
    GuillotinePlacement,
    GuillotineSplit,
    PackedFrame,
    PackerOptions,
    Rect,
)


class GuillotinePacker(BasePacker):
    """Guillotine bin packing implementation.

    Unlike MaxRects, each free rectangle is split exactly once when used,
    so no overlap tracking or pruning is needed.

    Attributes:
        options: Packer configuration inherited from BasePacker.
        free_rects: Available free rectangles in the current bin.
        placement_heuristic: Strategy for choosing where to place frames.
        split_heuristic: Strategy for dividing leftover space after placement.
    """

    ALGORITHM_NAME = "guillotine"
    DISPLAY_NAME = "Guillotine Packer"
    SUPPORTED_HEURISTICS = [
        ("bssf", "Best Short Side Fit (BSSF)"),
        ("blsf", "Best Long Side Fit (BLSF)"),
        ("baf", "Best Area Fit (BAF)"),
        ("waf", "Worst Area Fit (WAF)"),
    ]

    def __init__(self, options: Optional[PackerOptions] = None) -> None:
        super().__init__(options)
        self.free_rects: List[Rect] = []
        self.placement_heuristic: GuillotinePlacement = GuillotinePlacement.BAF
        self.split_heuristic: GuillotineSplit = GuillotineSplit.SHORTER_LEFTOVER_AXIS
        self._bin_width: int = 0
        self._bin_height: int = 0

    def set_heuristic(self, heuristic_key: str) -> bool:
        """Set the placement heuristic.

        Args:
            heuristic_key: One of 'bssf', 'blsf', 'baf', 'waf'.

        Returns:
            True if heuristic was set, False if invalid key.
        """
        heuristic_map = {
            "bssf": GuillotinePlacement.BSSF,
            "blsf": GuillotinePlacement.BLSF,
            "baf": GuillotinePlacement.BAF,
            "waf": GuillotinePlacement.WAF,
        }
        if heuristic_key.lower() in heuristic_map:
            self.placement_heuristic = heuristic_map[heuristic_key.lower()]
            self._current_heuristic = heuristic_key.lower()
            return True
        return False

    def set_split_heuristic(self, split_key: str) -> bool:
        """Set the split heuristic.

        Args:
            split_key: One of 'shorter_leftover', 'longer_leftover',
                       'shorter_axis', 'longer_axis', 'min_area', 'max_area'.

        Returns:
            True if heuristic was set, False if invalid key.
        """
        split_map = {
            "shorter_leftover": GuillotineSplit.SHORTER_LEFTOVER_AXIS,
            "longer_leftover": GuillotineSplit.LONGER_LEFTOVER_AXIS,
            "shorter_axis": GuillotineSplit.SHORTER_AXIS,
            "longer_axis": GuillotineSplit.LONGER_AXIS,
            "min_area": GuillotineSplit.MIN_AREA,
            "max_area": GuillotineSplit.MAX_AREA,
        }
        if split_key.lower() in split_map:
            self.split_heuristic = split_map[split_key.lower()]
            return True
        return False

    def _pack_internal(
        self,
        frames: List[FrameInput],
        width: int,
        height: int,
    ) -> List[PackedFrame]:
        """Pack frames using the Guillotine algorithm.

        At each step, selects the remaining frame that best fits the current
        free-rectangle state (global best-fit).

        Args:
            frames: Frames to pack.
            width: Atlas width in pixels.
            height: Atlas height in pixels.

        Returns:
            Successfully placed frames with their positions.
        """
        self._init_bin(width, height)
        packed: List[PackedFrame] = []
        padding = self.options.padding

        remaining = [
            (frame, frame.width + padding, frame.height + padding) for frame in frames
        ]

        while remaining:
            best_score = float("inf")
            best_frame_idx: Optional[int] = None
            best_result: Optional[Tuple[int, int, int, int, int, bool]] = None

            for i, (frame, frame_w, frame_h) in enumerate(remaining):
                result = self._find_best_position(frame_w, frame_h)
                if result is not None:
                    rect_idx, x, y, placed_w, placed_h, rotated = result
                    if rect_idx < len(self.free_rects):
                        rect = self.free_rects[rect_idx]
                        score = self._score_placement(placed_w, placed_h, rect)
                        if score < best_score:
                            best_score = score
                            best_frame_idx = i
                            best_result = result

            if best_frame_idx is None:
                return packed

            frame, frame_w, frame_h = remaining[best_frame_idx]
            rect_idx, best_x, best_y, placed_w, placed_h, rotated = best_result

            packed_frame = PackedFrame(
                frame=frame,
                x=best_x,
                y=best_y,
                rotated=rotated,
            )
            packed.append(packed_frame)

            self._split_free_rect(rect_idx, best_x, best_y, placed_w, placed_h)

            remaining[best_frame_idx] = remaining[-1]
            remaining.pop()

        return packed

    def _init_bin(self, width: int, height: int) -> None:
        """Initialize the bin with the given dimensions.

        Args:
            width: Total bin width in pixels.
            height: Total bin height in pixels.
        """
        self._bin_width = width
        self._bin_height = height
        self.free_rects = []

        border = self.options.border_padding
        self.free_rects.append(
            Rect(border, border, width - 2 * border, height - 2 * border)
        )

    def _find_best_position(
        self,
        width: int,
        height: int,
    ) -> Optional[Tuple[int, int, int, int, int, bool]]:
        """Find the best position for a rectangle.

        Args:
            width: Rectangle width including padding.
            height: Rectangle height including padding.

        Returns:
            Tuple (rect_index, x, y, width, height, rotated) or None.
        """
        best_score = float("inf")
        best_result: Optional[Tuple[int, int, int, int, int, bool]] = None

        for i, rect in enumerate(self.free_rects):
            if width <= rect.width and height <= rect.height:
                score = self._score_placement(width, height, rect)
                if score < best_score:
                    best_score = score
                    best_result = (i, rect.x, rect.y, width, height, False)

            if self.options.allow_rotation:
                if height <= rect.width and width <= rect.height:
                    score = self._score_placement(height, width, rect)
                    if score < best_score:
                        best_score = score
                        best_result = (i, rect.x, rect.y, height, width, True)

        return best_result

    def _score_placement(self, width: int, height: int, rect: Rect) -> float:
        """Score a potential placement using the active heuristic.

        Args:
            width: Placed rectangle width.
            height: Placed rectangle height.
            rect: Free rectangle being considered.

        Returns:
            Placement score; lower values are better.
        """
        leftover_w = rect.width - width
        leftover_h = rect.height - height

        if self.placement_heuristic == GuillotinePlacement.BSSF:
            return float(min(leftover_w, leftover_h))

        elif self.placement_heuristic == GuillotinePlacement.BLSF:
            return float(max(leftover_w, leftover_h))

        elif self.placement_heuristic == GuillotinePlacement.BAF:
            return float(rect.width * rect.height - width * height)

        elif self.placement_heuristic == GuillotinePlacement.WAF:
            return -float(rect.width * rect.height - width * height)

        return 0.0

    def _split_free_rect(
        self,
        rect_idx: int,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        """Split a free rectangle after placing a frame.

        Creates two new rectangles from the leftover space; split direction
        is determined by the active split heuristic.

        Args:
            rect_idx: Index of the free rectangle being consumed.
            x: Placement x-coordinate.
            y: Placement y-coordinate.
            width: Placed width.
            height: Placed height.
        """
        rect = self.free_rects[rect_idx]
        leftover_w = rect.width - width
        leftover_h = rect.height - height

        split_horizontal = self._should_split_horizontal(
            width, height, leftover_w, leftover_h
        )

        new_rects: List[Rect] = []

        if split_horizontal:
            if leftover_w > 0:
                new_rects.append(Rect(x + width, rect.y, leftover_w, rect.height))
            if leftover_h > 0:
                new_rects.append(Rect(x, y + height, width, leftover_h))
        else:
            if leftover_h > 0:
                new_rects.append(Rect(rect.x, y + height, rect.width, leftover_h))
            if leftover_w > 0:
                new_rects.append(Rect(x + width, y, leftover_w, height))

        del self.free_rects[rect_idx]
        self.free_rects.extend(new_rects)

    def _should_split_horizontal(
        self,
        width: int,
        height: int,
        leftover_w: int,
        leftover_h: int,
    ) -> bool:
        """Determine split direction based on the active split heuristic.

        Args:
            width: Placed rectangle width.
            height: Placed rectangle height.
            leftover_w: Remaining width in the free rectangle.
            leftover_h: Remaining height in the free rectangle.

        Returns:
            True for horizontal split, False for vertical.
        """
        heuristic = self.split_heuristic

        if heuristic == GuillotineSplit.SHORTER_LEFTOVER_AXIS:
            return leftover_w < leftover_h

        elif heuristic == GuillotineSplit.LONGER_LEFTOVER_AXIS:
            return leftover_w >= leftover_h

        elif heuristic == GuillotineSplit.SHORTER_AXIS:
            return width < height

        elif heuristic == GuillotineSplit.LONGER_AXIS:
            return width >= height

        elif heuristic == GuillotineSplit.MIN_AREA:
            h_area1 = leftover_w * (height + leftover_h) if leftover_w > 0 else 0
            h_area2 = width * leftover_h if leftover_h > 0 else 0
            h_min = (
                min(h_area1, h_area2)
                if h_area1 > 0 and h_area2 > 0
                else max(h_area1, h_area2)
            )

            v_area1 = leftover_w * height if leftover_w > 0 else 0
            v_area2 = (width + leftover_w) * leftover_h if leftover_h > 0 else 0
            v_min = (
                min(v_area1, v_area2)
                if v_area1 > 0 and v_area2 > 0
                else max(v_area1, v_area2)
            )

            return h_min < v_min

        elif heuristic == GuillotineSplit.MAX_AREA:
            h_area1 = leftover_w * (height + leftover_h) if leftover_w > 0 else 0
            h_area2 = width * leftover_h if leftover_h > 0 else 0
            h_min = (
                min(h_area1, h_area2)
                if h_area1 > 0 and h_area2 > 0
                else max(h_area1, h_area2)
            )

            v_area1 = leftover_w * height if leftover_w > 0 else 0
            v_area2 = (width + leftover_w) * leftover_h if leftover_h > 0 else 0
            v_min = (
                min(v_area1, v_area2)
                if v_area1 > 0 and v_area2 > 0
                else max(v_area1, v_area2)
            )

            return h_min >= v_min

        return True  # Default to horizontal

    def merge_free_rects(self) -> None:
        """Merge adjacent free rectangles to reduce fragmentation.

        This is O(n²); call periodically during packing if needed.
        """
        i = 0
        while i < len(self.free_rects):
            j = i + 1
            merged = False
            while j < len(self.free_rects):
                r1 = self.free_rects[i]
                r2 = self.free_rects[j]

                if r1.y == r2.y and r1.height == r2.height:
                    if r1.right == r2.x:
                        self.free_rects[i] = Rect(
                            r1.x, r1.y, r1.width + r2.width, r1.height
                        )
                        del self.free_rects[j]
                        merged = True
                        continue
                    elif r2.right == r1.x:
                        self.free_rects[i] = Rect(
                            r2.x, r1.y, r1.width + r2.width, r1.height
                        )
                        del self.free_rects[j]
                        merged = True
                        continue

                if r1.x == r2.x and r1.width == r2.width:
                    if r1.bottom == r2.y:
                        self.free_rects[i] = Rect(
                            r1.x, r1.y, r1.width, r1.height + r2.height
                        )
                        del self.free_rects[j]
                        merged = True
                        continue
                    elif r2.bottom == r1.y:
                        self.free_rects[i] = Rect(
                            r1.x, r2.y, r1.width, r1.height + r2.height
                        )
                        del self.free_rects[j]
                        merged = True
                        continue

                j += 1

            if not merged:
                i += 1


__all__ = ["GuillotinePacker"]
