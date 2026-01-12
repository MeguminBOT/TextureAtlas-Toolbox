#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Skyline bin packing algorithm with multiple placement heuristics.

Maintains a "skyline" representing the top edge of placed rectangles. Each
segment has a position (x) and height (y). New rectangles are placed by
finding the best position along the skyline.

One of the most efficient packing algorithms, offering near-optimal results
with O(n²) worst-case complexity.

Based on Jukka Jylänki's paper "A Thousand Ways to Pack the Bin" and
reference implementation: https://github.com/juj/RectangleBinPack
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from packers.base_packer import BasePacker
from packers.packer_types import (
    FrameInput,
    PackedFrame,
    PackerOptions,
    SkylineHeuristic,
)


@dataclass
class SkylineNode:
    """A segment of the skyline.

    Attributes:
        x: Starting X position of this segment.
        y: Height (top edge Y coordinate).
        width: Horizontal extent of this segment.
    """

    x: int
    y: int
    width: int


class SkylinePacker(BasePacker):
    """Skyline bin packing implementation.

    The skyline is a horizontal contour representing the top edge of all
    placed rectangles. Placing a rectangle raises the appropriate segments.

    Attributes:
        options: Packer configuration inherited from BasePacker.
        skyline: Active skyline segments in the current bin.
        heuristic: Strategy for selecting placement positions.
    """

    ALGORITHM_NAME = "skyline"
    DISPLAY_NAME = "Skyline Packer"
    SUPPORTED_HEURISTICS = [
        ("bottom_left", "Bottom-Left (BL)"),
        ("min_waste", "Minimum Waste"),
        ("best_fit", "Best Fit"),
    ]

    def __init__(self, options: Optional[PackerOptions] = None) -> None:
        super().__init__(options)
        self.skyline: List[SkylineNode] = []
        self.heuristic: SkylineHeuristic = SkylineHeuristic.MIN_WASTE
        self._bin_width: int = 0
        self._bin_height: int = 0
        self._placed: List[Tuple[int, int, int, int]] = []  # (x, y, w, h)

    def set_heuristic(self, heuristic_key: str) -> bool:
        """Set the placement heuristic.

        Args:
            heuristic_key: One of 'bottom_left', 'min_waste', 'best_fit'.

        Returns:
            True if heuristic was set, False if invalid key.
        """
        heuristic_map = {
            "bottom_left": SkylineHeuristic.BOTTOM_LEFT,
            "min_waste": SkylineHeuristic.MIN_WASTE,
            "best_fit": SkylineHeuristic.BEST_FIT,
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
        """Pack frames using the Skyline algorithm.

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

        for frame in frames:
            frame_w = frame.width + padding
            frame_h = frame.height + padding

            result = self._find_best_position(frame_w, frame_h)
            if result is None:
                return packed

            best_x, best_y, placed_w, placed_h, rotated = result

            if best_y + placed_h > self._bin_height - self.options.border_padding:
                return packed

            packed_frame = PackedFrame(
                frame=frame,
                x=best_x,
                y=best_y,
                rotated=rotated,
            )
            packed.append(packed_frame)

            self._add_skyline_level(best_x, best_y, placed_w, placed_h)
            self._placed.append((best_x, best_y, placed_w, placed_h))

        return packed

    def _init_bin(self, width: int, height: int) -> None:
        """Initialize the bin with the given dimensions.

        Args:
            width: Total bin width in pixels.
            height: Total bin height in pixels.
        """
        self._bin_width = width
        self._bin_height = height
        self._placed = []

        border = self.options.border_padding
        self.skyline = [SkylineNode(x=border, y=border, width=width - 2 * border)]

    def _find_best_position(
        self,
        width: int,
        height: int,
    ) -> Optional[Tuple[int, int, int, int, bool]]:
        """Find the best position for a rectangle.

        Args:
            width: Rectangle width including padding.
            height: Rectangle height including padding.

        Returns:
            Tuple (x, y, width, height, rotated) or None if no fit.
        """
        best_x = -1
        best_y = -1
        best_width = width
        best_height = height
        best_rotated = False
        best_score = float("inf")

        result = self._find_position_for_size(width, height)
        if result is not None:
            idx, x, y, score = result
            if score < best_score:
                best_score = score
                best_x = x
                best_y = y
                best_width = width
                best_height = height
                best_rotated = False

        if self.options.allow_rotation and width != height:
            result = self._find_position_for_size(height, width)
            if result is not None:
                idx, x, y, score = result
                if score < best_score:
                    best_score = score
                    best_x = x
                    best_y = y
                    best_width = height
                    best_height = width
                    best_rotated = True

        if best_x == -1:
            return None

        return (best_x, best_y, best_width, best_height, best_rotated)

    def _find_position_for_size(
        self,
        width: int,
        height: int,
    ) -> Optional[Tuple[int, int, int, float]]:
        """Find the best position for a rectangle of given size.

        Args:
            width: Rectangle width.
            height: Rectangle height.

        Returns:
            Tuple (skyline_index, x, y, score) or None if no fit.
        """
        best_idx = -1
        best_x = -1
        best_y = -1
        best_score = float("inf")
        border = self.options.border_padding

        for i in range(len(self.skyline)):
            result = self._fit_at_skyline_index(i, width, height)
            if result is None:
                continue

            x, y, waste = result

            if y + height > self._bin_height - border:
                continue

            if self.heuristic == SkylineHeuristic.BOTTOM_LEFT:
                score = float(y * self._bin_width + x)
            elif self.heuristic == SkylineHeuristic.MIN_WASTE:
                score = float(waste)
            elif self.heuristic == SkylineHeuristic.BEST_FIT:
                fit_score = abs(width - self.skyline[i].width)
                score = float(y * 1000 + fit_score)
            else:
                score = float(y * self._bin_width + x)

            if score < best_score:
                best_score = score
                best_x = x
                best_y = y
                best_idx = i

        if best_idx == -1:
            return None

        return (best_idx, best_x, best_y, best_score)

    def _fit_at_skyline_index(
        self,
        idx: int,
        width: int,
        height: int,
    ) -> Optional[Tuple[int, int, int]]:
        """Try to fit a rectangle starting at the given skyline index.

        Args:
            idx: Skyline segment index to start from.
            width: Rectangle width.
            height: Rectangle height.

        Returns:
            Tuple (x, y, waste) if it fits, None otherwise.
        """
        x = self.skyline[idx].x
        border = self.options.border_padding

        if x + width > self._bin_width - border:
            return None

        width_left = width
        i = idx
        y = 0
        waste = 0

        while width_left > 0 and i < len(self.skyline):
            node = self.skyline[i]

            if node.y > y:
                waste += (node.y - y) * (width - width_left)
                y = node.y
            else:
                waste += (y - node.y) * min(width_left, node.width)

            if node.x + node.width >= x + width:
                width_left = 0
            else:
                width_left -= node.width - max(0, x - node.x)

            i += 1

        if width_left > 0:
            return None

        return (x, y, waste)

    def _add_skyline_level(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        """Update the skyline after placing a rectangle.

        Args:
            x: Placement X coordinate.
            y: Placement Y coordinate.
            width: Placed rectangle width.
            height: Placed rectangle height.
        """
        new_node = SkylineNode(x=x, y=y + height, width=width)

        new_skyline: List[SkylineNode] = []
        i = 0

        while i < len(self.skyline) and self.skyline[i].x + self.skyline[i].width <= x:
            new_skyline.append(self.skyline[i])
            i += 1

        if i < len(self.skyline) and self.skyline[i].x < x:
            node = self.skyline[i]
            trimmed = SkylineNode(x=node.x, y=node.y, width=x - node.x)
            new_skyline.append(trimmed)

        new_skyline.append(new_node)

        while (
            i < len(self.skyline)
            and self.skyline[i].x + self.skyline[i].width <= x + width
        ):
            i += 1

        if i < len(self.skyline) and self.skyline[i].x < x + width:
            node = self.skyline[i]
            overlap = x + width - node.x
            adjusted = SkylineNode(x=x + width, y=node.y, width=node.width - overlap)
            if adjusted.width > 0:
                new_skyline.append(adjusted)
            i += 1

        while i < len(self.skyline):
            new_skyline.append(self.skyline[i])
            i += 1

        self.skyline = new_skyline
        self._merge_skyline()

    def _merge_skyline(self) -> None:
        """Merge adjacent skyline nodes with the same height."""
        if len(self.skyline) <= 1:
            return

        merged: List[SkylineNode] = [self.skyline[0]]

        for i in range(1, len(self.skyline)):
            node = self.skyline[i]
            last = merged[-1]

            if last.y == node.y:
                merged[-1] = SkylineNode(
                    x=last.x,
                    y=last.y,
                    width=last.width + node.width,
                )
            else:
                merged.append(node)

        self.skyline = merged

    def get_skyline_height(self) -> int:
        """Return the maximum height of the current skyline."""
        if not self.skyline:
            return 0
        return max(node.y for node in self.skyline)


__all__ = ["SkylinePacker", "SkylineNode"]
