#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shelf bin packing algorithm with multiple heuristics.

Organizes frames into horizontal shelves (rows). Each shelf has a fixed height
determined by the first frame placed on it. Frames are placed left-to-right
until no more fit, then a new shelf is created below.

Simpler and faster than MaxRects/Guillotine but may waste vertical space.
Best suited for frames of similar heights.

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
    ShelfHeuristic,
)


@dataclass
class Shelf:
    """A horizontal shelf in the bin.

    Attributes:
        y: Top Y coordinate of the shelf.
        height: Shelf height (set by the first placed frame).
        used_width: Total width consumed by placed frames.
    """

    y: int
    height: int
    used_width: int = 0

    def remaining_width(self, bin_width: int, border: int = 0) -> int:
        """Return the remaining usable width on this shelf.

        Args:
            bin_width: Total bin width.
            border: Border padding on each side.

        Returns:
            Available width for additional frames.
        """
        return bin_width - 2 * border - self.used_width


class ShelfPacker(BasePacker):
    """Shelf bin packing implementation.

    Frames are placed on shelves left-to-right. When a frame does not fit on
    any existing shelf, a new shelf is created below.

    Attributes:
        options: Packer configuration inherited from BasePacker.
        shelves: Active shelf objects in the current bin.
        heuristic: Strategy for selecting which shelf to use.
    """

    ALGORITHM_NAME = "shelf"
    DISPLAY_NAME = "Shelf Packer"
    SUPPORTED_HEURISTICS = [
        ("next_fit", "Next Fit"),
        ("first_fit", "First Fit"),
        ("best_width", "Best Width Fit"),
        ("best_height", "Best Height Fit"),
        ("best_area", "Best Area Fit"),
        ("worst_width", "Worst Width Fit"),
        ("worst_area", "Worst Area Fit"),
    ]

    def __init__(self, options: Optional[PackerOptions] = None) -> None:
        super().__init__(options)
        self.shelves: List[Shelf] = []
        self.heuristic: ShelfHeuristic = ShelfHeuristic.BEST_HEIGHT_FIT
        self._bin_width: int = 0
        self._bin_height: int = 0
        self._current_y: int = 0
        self._placed: List[Tuple[int, int, int, int]] = []

    def set_heuristic(self, heuristic_key: str) -> bool:
        """Set the shelf selection heuristic.

        Args:
            heuristic_key: One of 'next_fit', 'first_fit', 'best_width',
                          'best_height', 'worst_width'.

        Returns:
            True if heuristic was set, False if invalid key.
        """
        heuristic_map = {
            "next_fit": ShelfHeuristic.NEXT_FIT,
            "first_fit": ShelfHeuristic.FIRST_FIT,
            "best_width": ShelfHeuristic.BEST_WIDTH_FIT,
            "best_height": ShelfHeuristic.BEST_HEIGHT_FIT,
            "best_area": ShelfHeuristic.BEST_AREA_FIT,
            "worst_width": ShelfHeuristic.WORST_WIDTH_FIT,
            "worst_area": ShelfHeuristic.WORST_AREA_FIT,
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
        """Pack frames using the Shelf algorithm.

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

            result = self._insert_frame(frame_w, frame_h)
            if result is None:
                return packed

            x, y, placed_w, placed_h, rotated = result

            packed_frame = PackedFrame(
                frame=frame,
                x=x,
                y=y,
                rotated=rotated,
            )
            packed.append(packed_frame)
            self._placed.append((x, y, placed_w, placed_h))

        return packed

    def _init_bin(self, width: int, height: int) -> None:
        """Initialize the bin with the given dimensions.

        Args:
            width: Total bin width in pixels.
            height: Total bin height in pixels.
        """
        self._bin_width = width
        self._bin_height = height
        self._current_y = self.options.border_padding
        self.shelves = []
        self._placed = []

    def _insert_frame(
        self,
        width: int,
        height: int,
    ) -> Optional[Tuple[int, int, int, int, bool]]:
        """Insert a frame into a shelf, creating one if necessary.

        Args:
            width: Frame width including padding.
            height: Frame height including padding.

        Returns:
            Tuple (x, y, width, height, rotated) or None if no fit.
        """
        result = self._find_shelf(width, height, False)

        if result is None and self.options.allow_rotation:
            result = self._find_shelf(height, width, True)

        if result is None:
            result = self._create_new_shelf(width, height, False)

        if result is None and self.options.allow_rotation:
            result = self._create_new_shelf(height, width, True)

        return result

    def _find_shelf(
        self,
        width: int,
        height: int,
        rotated: bool,
    ) -> Optional[Tuple[int, int, int, int, bool]]:
        """Find an existing shelf that can fit the frame.

        Args:
            width: Frame width.
            height: Frame height.
            rotated: Whether the frame is rotated 90°.

        Returns:
            Placement tuple or None if no shelf fits.
        """
        if not self.shelves:
            return None

        border = self.options.border_padding

        if self.heuristic == ShelfHeuristic.NEXT_FIT:
            shelf = self.shelves[-1]
            if self._fits_on_shelf(shelf, width, height):
                return self._place_on_shelf(shelf, width, height, rotated)
            return None

        best_shelf: Optional[Shelf] = None
        best_score = float("inf")

        for shelf in self.shelves:
            if not self._fits_on_shelf(shelf, width, height):
                continue

            if self.heuristic == ShelfHeuristic.FIRST_FIT:
                return self._place_on_shelf(shelf, width, height, rotated)

            elif self.heuristic == ShelfHeuristic.BEST_WIDTH_FIT:
                remaining = shelf.remaining_width(self._bin_width, border) - width
                if remaining < best_score:
                    best_score = remaining
                    best_shelf = shelf

            elif self.heuristic == ShelfHeuristic.BEST_HEIGHT_FIT:
                height_diff = shelf.height - height
                if height_diff >= 0 and height_diff < best_score:
                    best_score = height_diff
                    best_shelf = shelf

            elif self.heuristic == ShelfHeuristic.BEST_AREA_FIT:
                height_diff = shelf.height - height
                if height_diff >= 0:
                    remaining = shelf.remaining_width(self._bin_width, border) - width
                    waste = height_diff * (self._bin_width - 2 * border)
                    if waste < best_score:
                        best_score = waste
                        best_shelf = shelf

            elif self.heuristic == ShelfHeuristic.WORST_AREA_FIT:
                height_diff = shelf.height - height
                if height_diff >= 0:
                    waste = height_diff * (self._bin_width - 2 * border)
                    score = -waste
                    if score < best_score:
                        best_score = score
                        best_shelf = shelf

            elif self.heuristic == ShelfHeuristic.WORST_WIDTH_FIT:
                remaining = shelf.remaining_width(self._bin_width, border) - width
                score = -remaining
                if score < best_score:
                    best_score = score
                    best_shelf = shelf

        if best_shelf is not None:
            return self._place_on_shelf(best_shelf, width, height, rotated)

        return None

    def _fits_on_shelf(self, shelf: Shelf, width: int, height: int) -> bool:
        """Check if a frame fits on the given shelf.

        Args:
            shelf: Shelf to check.
            width: Frame width.
            height: Frame height.

        Returns:
            True if the frame fits, False otherwise.
        """
        border = self.options.border_padding

        if shelf.remaining_width(self._bin_width, border) < width:
            return False

        if height > shelf.height:
            return False

        return True

    def _place_on_shelf(
        self,
        shelf: Shelf,
        width: int,
        height: int,
        rotated: bool,
    ) -> Tuple[int, int, int, int, bool]:
        """Place a frame on a shelf and update its used width.

        Args:
            shelf: Target shelf.
            width: Frame width.
            height: Frame height.
            rotated: Whether the frame is rotated 90°.

        Returns:
            Placement tuple (x, y, width, height, rotated).
        """
        border = self.options.border_padding
        x = border + shelf.used_width
        y = shelf.y

        shelf.used_width += width

        return (x, y, width, height, rotated)

    def _create_new_shelf(
        self,
        width: int,
        height: int,
        rotated: bool,
    ) -> Optional[Tuple[int, int, int, int, bool]]:
        """Create a new shelf for the frame if space permits.

        Args:
            width: Frame width.
            height: Frame height.
            rotated: Whether the frame is rotated 90°.

        Returns:
            Placement tuple or None if bin height would be exceeded.
        """
        border = self.options.border_padding

        if self._current_y + height > self._bin_height - border:
            return None

        if width > self._bin_width - 2 * border:
            return None

        new_shelf = Shelf(y=self._current_y, height=height)
        self.shelves.append(new_shelf)
        self._current_y += height

        return self._place_on_shelf(new_shelf, width, height, rotated)

    def shelf_occupancy(self) -> float:
        """Return the ratio of used area to total shelf area."""
        if not self.shelves:
            return 0.0

        used_area = sum(w * h for x, y, w, h in self._placed)
        shelf_area = sum(
            shelf.height * (self._bin_width - 2 * self.options.border_padding)
            for shelf in self.shelves
        )
        return used_area / shelf_area if shelf_area > 0 else 0.0


class ShelfPackerDecreasingHeight(ShelfPacker):
    """Shelf packer that pre-sorts frames by decreasing height (FFDH).

    Sorting typically achieves better packing than unsorted shelf packing.
    Output order matches the original input order.
    """

    ALGORITHM_NAME = "shelf-ffdh"
    DISPLAY_NAME = "Shelf Packer (FFDH)"

    def _pack_internal(
        self,
        frames: List[FrameInput],
        width: int,
        height: int,
    ) -> List[PackedFrame]:
        """Pack frames sorted by decreasing height.

        Args:
            frames: Frames to pack.
            width: Atlas width in pixels.
            height: Atlas height in pixels.

        Returns:
            Successfully placed frames in original input order.
        """
        self._init_bin(width, height)
        padding = self.options.padding

        indexed_frames = [(f, i) for i, f in enumerate(frames)]

        sorted_frames = sorted(
            indexed_frames,
            key=lambda x: (x[0].height, x[0].width),
            reverse=True,
        )

        temp_results: List[Tuple[PackedFrame, int]] = []

        for frame, original_idx in sorted_frames:
            frame_w = frame.width + padding
            frame_h = frame.height + padding

            result = self._insert_frame(frame_w, frame_h)
            if result is None:
                temp_results.sort(key=lambda x: x[1])
                return [pf for pf, _ in temp_results]

            x, y, placed_w, placed_h, rotated = result

            packed_frame = PackedFrame(
                frame=frame,
                x=x,
                y=y,
                rotated=rotated,
            )
            temp_results.append((packed_frame, original_idx))
            self._placed.append((x, y, placed_w, placed_h))

        temp_results.sort(key=lambda x: x[1])
        return [pf for pf, _ in temp_results]


__all__ = ["ShelfPacker", "ShelfPackerDecreasingHeight", "Shelf"]
