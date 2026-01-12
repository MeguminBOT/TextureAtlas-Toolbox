#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MaxRects bin packing algorithm with multiple placement heuristics.

Maintains maximal free rectangles and splits/prunes them as frames are placed.

Based on Jukka Jylänki's paper "A Thousand Ways to Pack the Bin" and
reference implementation: https://github.com/juj/RectangleBinPack
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from packers.base_packer import BasePacker
from packers.packer_types import (
    FrameInput,
    MaxRectsHeuristic,
    PackedFrame,
    PackerOptions,
    Rect,
)


class MaxRectsPacker(BasePacker):
    """MaxRects bin packing implementation.

    Maintains a list of maximal free rectangles. When a frame is placed, any
    overlapping free rectangle is split into up to four new rectangles, and
    rectangles fully contained in others are pruned.

    Attributes:
        options: Packer configuration inherited from BasePacker.
        free_rects: Available free rectangles in the current bin.
        used_rects: Rectangles already placed in the bin.
        heuristic: Active placement heuristic (default BSSF).
    """

    ALGORITHM_NAME = "maxrects"
    DISPLAY_NAME = "MaxRects Packer"
    SUPPORTED_HEURISTICS = [
        ("bssf", "Best Short Side Fit (BSSF)"),
        ("blsf", "Best Long Side Fit (BLSF)"),
        ("baf", "Best Area Fit (BAF)"),
        ("bl", "Bottom-Left (BL)"),
        ("cp", "Contact Point (CP)"),
    ]

    def __init__(self, options: Optional[PackerOptions] = None) -> None:
        super().__init__(options)
        self.free_rects: List[Rect] = []
        self.used_rects: List[Rect] = []
        self.heuristic: MaxRectsHeuristic = MaxRectsHeuristic.BSSF
        self._bin_width: int = 0
        self._bin_height: int = 0

    def set_heuristic(self, heuristic_key: str) -> bool:
        """Set the placement heuristic.

        Args:
            heuristic_key: One of 'bssf', 'blsf', 'baf', 'bl', 'cp'.

        Returns:
            True if heuristic was set, False if invalid key.
        """
        heuristic_map = {
            "bssf": MaxRectsHeuristic.BSSF,
            "blsf": MaxRectsHeuristic.BLSF,
            "baf": MaxRectsHeuristic.BAF,
            "bl": MaxRectsHeuristic.BL,
            "cp": MaxRectsHeuristic.CP,
        }
        if heuristic_key.lower() in heuristic_map:
            self.heuristic = heuristic_map[heuristic_key.lower()]
            self._current_heuristic = heuristic_key.lower()
            return True
        return False

    def _pack_internal(
        self,
        frames: List[FrameInput],
        width: int,
        height: int,
    ) -> List[PackedFrame]:
        """Pack frames using the MaxRects algorithm.

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
            best_score = (float("inf"), float("inf"))
            best_frame_idx: Optional[int] = None
            best_result: Optional[Tuple[int, int, int, int, bool]] = None

            for i, (frame, frame_w, frame_h) in enumerate(remaining):
                result = self._find_best_position(frame_w, frame_h)
                if result is not None:
                    _, _, placed_w, placed_h, _ = result
                    score = self._score_frame_placement(result, frame_w, frame_h)
                    if score < best_score:
                        best_score = score
                        best_frame_idx = i
                        best_result = result

            if best_frame_idx is None:
                return packed

            frame, frame_w, frame_h = remaining[best_frame_idx]
            best_x, best_y, best_w, best_h, rotated = best_result

            packed_frame = PackedFrame(
                frame=frame,
                x=best_x,
                y=best_y,
                rotated=rotated,
            )
            packed.append(packed_frame)

            placed_rect = Rect(best_x, best_y, best_w, best_h)
            self._place_rect(placed_rect)

            remaining[best_frame_idx] = remaining[-1]
            remaining.pop()

        return packed

    def _score_frame_placement(
        self,
        result: Tuple[int, int, int, int, bool],
        frame_w: int,
        frame_h: int,
    ) -> Tuple[float, float]:
        """Score a frame placement for global best-fit selection.

        Args:
            result: Placement tuple (x, y, placed_w, placed_h, rotated).
            frame_w: Original frame width including padding.
            frame_h: Original frame height including padding.

        Returns:
            A (primary, secondary) score tuple; lower is better.
        """
        best_x, best_y, placed_w, placed_h, rotated = result

        for rect in self.free_rects:
            if rect.x == best_x and rect.y == best_y:
                if placed_w <= rect.width and placed_h <= rect.height:
                    return self._score_position(rect, placed_w, placed_h)

        return (float("inf"), float("inf"))

    def _init_bin(self, width: int, height: int) -> None:
        """Initialize the bin with the given dimensions.

        Clears existing state and creates a single free rectangle spanning
        the usable area (respecting border padding).

        Args:
            width: Total bin width in pixels.
            height: Total bin height in pixels.
        """
        self._bin_width = width
        self._bin_height = height
        self.free_rects = []
        self.used_rects = []

        border = self.options.border_padding
        self.free_rects.append(
            Rect(border, border, width - 2 * border, height - 2 * border)
        )

    def _find_best_position(
        self,
        width: int,
        height: int,
    ) -> Optional[Tuple[int, int, int, int, bool]]:
        """Find the best position for a rectangle of the given size.

        Tries both orientations (if rotation allowed) and picks the best score.

        Args:
            width: Rectangle width (including padding).
            height: Rectangle height (including padding).

        Returns:
            (x, y, width, height, rotated) or None if no position found.
        """
        best_score = (float("inf"), float("inf"))
        best_result: Optional[Tuple[int, int, int, int, bool]] = None

        for rect in self.free_rects:
            if width <= rect.width and height <= rect.height:
                score = self._score_position(rect, width, height)
                if score < best_score:
                    best_score = score
                    best_result = (rect.x, rect.y, width, height, False)

            if self.options.allow_rotation:
                if height <= rect.width and width <= rect.height:
                    score = self._score_position(rect, height, width)
                    if score < best_score:
                        best_score = score
                        best_result = (rect.x, rect.y, height, width, True)

        return best_result

    def _score_position(
        self,
        rect: Rect,
        width: int,
        height: int,
    ) -> Tuple[float, float]:
        """Score a potential placement position using the active heuristic.

        Args:
            rect: Free rectangle being considered.
            width: Width of the rectangle to place (including padding).
            height: Height of the rectangle to place (including padding).

        Returns:
            A (primary, secondary) score tuple; lower values are better.
        """
        leftover_w = rect.width - width
        leftover_h = rect.height - height

        if self.heuristic == MaxRectsHeuristic.BSSF:
            short_side = min(leftover_w, leftover_h)
            long_side = max(leftover_w, leftover_h)
            return (float(short_side), float(long_side))

        elif self.heuristic == MaxRectsHeuristic.BLSF:
            short_side = min(leftover_w, leftover_h)
            long_side = max(leftover_w, leftover_h)
            return (float(long_side), float(short_side))

        elif self.heuristic == MaxRectsHeuristic.BAF:
            leftover_area = rect.width * rect.height - width * height
            short_side = min(leftover_w, leftover_h)
            return (float(leftover_area), float(short_side))

        elif self.heuristic == MaxRectsHeuristic.BL:
            top_side_y = rect.y + height
            return (float(top_side_y), float(rect.x))

        elif self.heuristic == MaxRectsHeuristic.CP:
            contact = self._calculate_contact_score(rect.x, rect.y, width, height)
            return (-float(contact), float(rect.y))

        # Default to BSSF
        short_side = min(leftover_w, leftover_h)
        long_side = max(leftover_w, leftover_h)
        return (float(short_side), float(long_side))

    def _calculate_contact_score(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> int:
        """Calculate total edge contact for a rectangle placement.

        Contact is the sum of pixels where the rectangle touches bin
        boundaries and already-placed rectangles.

        Args:
            x: Left edge of the placement.
            y: Top edge of the placement.
            width: Rectangle width.
            height: Rectangle height.

        Returns:
            Total contact length in pixels (higher means tighter packing).
        """
        border = self.options.border_padding
        contact = 0

        if x == border:
            contact += height
        if y == border:
            contact += width
        if x + width == self._bin_width - border:
            contact += height
        if y + height == self._bin_height - border:
            contact += width

        for used in self.used_rects:
            if x == used.right or x + width == used.x:
                y_start = max(y, used.y)
                y_end = min(y + height, used.bottom)
                if y_end > y_start:
                    contact += y_end - y_start

            if y == used.bottom or y + height == used.y:
                x_start = max(x, used.x)
                x_end = min(x + width, used.right)
                if x_end > x_start:
                    contact += x_end - x_start

        return contact

    def _place_rect(self, rect: Rect) -> None:
        """Place a rectangle and update the free rectangle list.

        Splits any free rectangle that intersects with `rect` and prunes
        rectangles that become fully contained in others.

        Args:
            rect: The rectangle being placed.
        """
        self.used_rects.append(rect)
        new_free: List[Rect] = []

        for free_rect in self.free_rects:
            if not free_rect.intersects(rect):
                new_free.append(free_rect)
                continue

            splits = self._split_rect(free_rect, rect)
            new_free.extend(splits)

        self.free_rects = new_free
        self._prune_free_rects()

    def _split_rect(self, free_rect: Rect, placed: Rect) -> List[Rect]:
        """Split a free rectangle around a placed rectangle.

        Creates up to four new rectangles from the portions of `free_rect`
        that do not overlap with `placed`. Zero-area results are discarded.

        Args:
            free_rect: The free rectangle to split.
            placed: The newly placed rectangle causing the split.

        Returns:
            Non-empty rectangles remaining after the split.
        """
        result: List[Rect] = []

        if placed.x > free_rect.x:
            result.append(
                Rect(
                    free_rect.x,
                    free_rect.y,
                    placed.x - free_rect.x,
                    free_rect.height,
                )
            )

        if placed.right < free_rect.right:
            result.append(
                Rect(
                    placed.right,
                    free_rect.y,
                    free_rect.right - placed.right,
                    free_rect.height,
                )
            )

        if placed.y > free_rect.y:
            result.append(
                Rect(
                    free_rect.x,
                    free_rect.y,
                    free_rect.width,
                    placed.y - free_rect.y,
                )
            )

        if placed.bottom < free_rect.bottom:
            result.append(
                Rect(
                    free_rect.x,
                    placed.bottom,
                    free_rect.width,
                    free_rect.bottom - placed.bottom,
                )
            )

        return [r for r in result if r.area > 0]

    def _prune_free_rects(self) -> None:
        """Remove free rectangles fully contained in others.

        Delegates to a simple O(n²) loop for small lists or a NumPy-based
        batch check for lists exceeding 20 rectangles.
        """
        if len(self.free_rects) <= 1:
            return

        n = len(self.free_rects)
        if n > 20:
            self._prune_free_rects_numpy()
        else:
            self._prune_free_rects_simple()

    def _prune_free_rects_simple(self) -> None:
        """Prune contained rectangles using a simple O(n²) loop."""
        i = 0
        while i < len(self.free_rects):
            j = i + 1
            remove_i = False
            while j < len(self.free_rects):
                ri = self.free_rects[i]
                rj = self.free_rects[j]

                if rj.contains(ri):
                    remove_i = True
                    break
                elif ri.contains(rj):
                    del self.free_rects[j]
                    continue
                j += 1

            if remove_i:
                del self.free_rects[i]
            else:
                i += 1

    def _prune_free_rects_numpy(self) -> None:
        """Prune contained rectangles using NumPy vectorized checks."""
        n = len(self.free_rects)
        if n == 0:
            return

        rects = np.array(
            [(r.x, r.y, r.right, r.bottom) for r in self.free_rects],
            dtype=np.int32,
        )
        remove = np.zeros(n, dtype=bool)

        for i in range(n):
            if remove[i]:
                continue

            contains_i = (
                (rects[:, 0] <= rects[i, 0])
                & (rects[:, 1] <= rects[i, 1])
                & (rects[:, 2] >= rects[i, 2])
                & (rects[:, 3] >= rects[i, 3])
            )
            contains_i[i] = False

            if np.any(contains_i):
                remove[i] = True

        self.free_rects = [self.free_rects[i] for i in range(n) if not remove[i]]

    def occupancy(self) -> float:
        """Return the ratio of used area to total bin area."""

        used_area = sum(r.area for r in self.used_rects)
        total_area = self._bin_width * self._bin_height
        return used_area / total_area if total_area > 0 else 0.0


__all__ = ["MaxRectsPacker"]
