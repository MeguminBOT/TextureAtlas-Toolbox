#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Unified types and error handling for all texture atlas packers.

This module defines:
    - Rect: Basic rectangle with position and size, using NumPy for efficiency.
    - FrameInput: Input frame data for the packer.
    - PackedFrame: Result of packing a single frame with atlas position.
    - PackerOptions: Configuration options for packer algorithms.
    - PackerResult: Container for packing outcomes with diagnostics.
    - PackerError hierarchy: Typed exceptions for packing failures.

The packer system works with the exporter system:
    - Packers: List[FrameInput] → PackerResult (positions, atlas dimensions)
    - Exporters: PackerResult + images → atlas image + metadata file
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


# =============================================================================
# Error Types
# =============================================================================


class PackerErrorCode(Enum):
    """Categorized error codes for packer failures."""

    # Size constraint errors
    FRAME_TOO_LARGE = auto()
    ATLAS_OVERFLOW = auto()
    CANNOT_FIT_ALL = auto()

    # Input validation errors
    NO_FRAMES_PROVIDED = auto()
    INVALID_FRAME_SIZE = auto()
    DUPLICATE_FRAME_ID = auto()

    # Algorithm errors
    PACKING_FAILED = auto()
    HEURISTIC_NOT_FOUND = auto()
    INVALID_OPTIONS = auto()

    # Unknown/fallback
    UNKNOWN_ERROR = auto()


class PackerError(Exception):
    """Base exception for all packer errors.

    Attributes:
        code: Categorized error code for programmatic handling.
        message: Human-readable error description.
        details: Optional dict with additional context.
    """

    def __init__(
        self,
        code: PackerErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"Details: {detail_str}")
        return " | ".join(parts)


class FrameTooLargeError(PackerError):
    """A frame exceeds the maximum atlas dimensions."""

    pass


class AtlasOverflowError(PackerError):
    """Cannot fit all frames within maximum atlas size."""

    pass


class InvalidOptionsError(PackerError):
    """Invalid packer options provided."""

    pass


# =============================================================================
# Heuristic Enums
# =============================================================================


class MaxRectsHeuristic(Enum):
    """Heuristics for MaxRects rectangle placement.

    BSSF: Best Short Side Fit - Minimize short side remainder.
    BLSF: Best Long Side Fit - Minimize long side remainder.
    BAF: Best Area Fit - Minimize total wasted area.
    BL: Bottom-Left - Place as low and left as possible.
    CP: Contact Point - Maximize contact with edges and other rects.
    """

    BSSF = auto()  # Best Short Side Fit
    BLSF = auto()  # Best Long Side Fit
    BAF = auto()  # Best Area Fit
    BL = auto()  # Bottom-Left
    CP = auto()  # Contact Point


class GuillotinePlacement(Enum):
    """Heuristics for Guillotine placement selection.

    BSSF: Best Short Side Fit.
    BLSF: Best Long Side Fit.
    BAF: Best Area Fit - Minimize leftover area.
    WAF: Worst Area Fit - For uniform distribution.
    """

    BSSF = auto()
    BLSF = auto()
    BAF = auto()
    WAF = auto()


class GuillotineSplit(Enum):
    """Heuristics for Guillotine split direction.

    SHORTER_LEFTOVER_AXIS: Split along shorter leftover side.
    LONGER_LEFTOVER_AXIS: Split along longer leftover side.
    SHORTER_AXIS: Split along shorter frame side.
    LONGER_AXIS: Split along longer frame side.
    MIN_AREA: Minimize area of smallest resulting rect.
    MAX_AREA: Maximize area of smallest resulting rect.
    """

    SHORTER_LEFTOVER_AXIS = auto()
    LONGER_LEFTOVER_AXIS = auto()
    SHORTER_AXIS = auto()
    LONGER_AXIS = auto()
    MIN_AREA = auto()
    MAX_AREA = auto()


class ShelfHeuristic(Enum):
    """Heuristics for Shelf packer placement.

    NEXT_FIT: Always use the current (last) shelf.
    FIRST_FIT: Use first shelf where frame fits.
    BEST_WIDTH_FIT: Use shelf with least remaining width.
    BEST_HEIGHT_FIT: Use shelf matching frame height best.
    BEST_AREA_FIT: Minimize wasted area (height_diff * remaining_width).
    WORST_WIDTH_FIT: Use shelf with most remaining width.
    WORST_AREA_FIT: Maximize wasted area (load balancing).
    """

    NEXT_FIT = auto()
    FIRST_FIT = auto()
    BEST_WIDTH_FIT = auto()
    BEST_HEIGHT_FIT = auto()
    BEST_AREA_FIT = auto()
    WORST_WIDTH_FIT = auto()
    WORST_AREA_FIT = auto()


class SkylineHeuristic(Enum):
    """Heuristics for Skyline packer placement.

    BOTTOM_LEFT: Place at lowest Y, tie-break by leftmost X.
    MIN_WASTE: Place where least space is wasted below.
    BEST_FIT: Find position matching skyline contour best.
    """

    BOTTOM_LEFT = auto()
    MIN_WASTE = auto()
    BEST_FIT = auto()


class ExpandStrategy(Enum):
    """Strategy for growing the atlas when frames don't fit.

    DISABLED: Never expand; fail if frames don't fit.
    WIDTH_FIRST: Expand width before height.
    HEIGHT_FIRST: Expand height before width.
    SHORT_SIDE: Expand the shorter dimension.
    LONG_SIDE: Expand the longer dimension.
    BOTH: Double both dimensions together.
    """

    DISABLED = auto()
    WIDTH_FIRST = auto()
    HEIGHT_FIRST = auto()
    SHORT_SIDE = auto()
    LONG_SIDE = auto()
    BOTH = auto()


# =============================================================================
# Core Data Types
# =============================================================================


class Rect:
    """Axis-aligned rectangle with position and size.

    Uses NumPy-backed storage for efficient batch operations.
    Coordinate system: (0,0) is top-left, +Y goes down.

    Attributes:
        x: Left edge X coordinate.
        y: Top edge Y coordinate.
        width: Rectangle width in pixels.
        height: Rectangle height in pixels.
    """

    __slots__ = ("_data",)

    def __init__(self, x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> None:
        # Store as NumPy array: [x, y, width, height]
        object.__setattr__(
            self, "_data", np.array([x, y, width, height], dtype=np.int32)
        )

    @property
    def x(self) -> int:
        """Left edge X coordinate."""
        return int(self._data[0])

    @x.setter
    def x(self, value: int) -> None:
        self._data[0] = value

    @property
    def y(self) -> int:
        """Top edge Y coordinate."""
        return int(self._data[1])

    @y.setter
    def y(self, value: int) -> None:
        self._data[1] = value

    @property
    def width(self) -> int:
        """Rectangle width in pixels."""
        return int(self._data[2])

    @width.setter
    def width(self, value: int) -> None:
        self._data[2] = value

    @property
    def height(self) -> int:
        """Rectangle height in pixels."""
        return int(self._data[3])

    @height.setter
    def height(self, value: int) -> None:
        self._data[3] = value

    @property
    def left(self) -> int:
        """Left edge X coordinate."""
        return int(self._data[0])

    @left.setter
    def left(self, value: int) -> None:
        delta = self._data[0] - value
        self._data[2] += delta
        self._data[0] = value

    @property
    def top(self) -> int:
        """Top edge Y coordinate."""
        return int(self._data[1])

    @top.setter
    def top(self, value: int) -> None:
        delta = self._data[1] - value
        self._data[3] += delta
        self._data[1] = value

    @property
    def right(self) -> int:
        """Right edge X coordinate (exclusive)."""
        return int(self._data[0] + self._data[2])

    @right.setter
    def right(self, value: int) -> None:
        self._data[2] = value - self._data[0]

    @property
    def bottom(self) -> int:
        """Bottom edge Y coordinate (exclusive)."""
        return int(self._data[1] + self._data[3])

    @bottom.setter
    def bottom(self, value: int) -> None:
        self._data[3] = value - self._data[1]

    @property
    def area(self) -> int:
        """Rectangle area in pixels."""
        return int(self._data[2] * self._data[3])

    @property
    def short_side(self) -> int:
        """Shorter dimension."""
        return int(min(self._data[2], self._data[3]))

    @property
    def long_side(self) -> int:
        """Longer dimension."""
        return int(max(self._data[2], self._data[3]))

    @property
    def center(self) -> Tuple[float, float]:
        """Center point (x, y)."""
        return (
            float(self._data[0]) + float(self._data[2]) / 2,
            float(self._data[1]) + float(self._data[3]) / 2,
        )

    def clone(self) -> "Rect":
        """Create a copy of this rectangle."""
        return Rect(
            int(self._data[0]),
            int(self._data[1]),
            int(self._data[2]),
            int(self._data[3]),
        )

    def contains(self, other: "Rect") -> bool:
        """Check if this rectangle fully contains another."""
        return bool(
            self._data[0] <= other._data[0]
            and self._data[1] <= other._data[1]
            and self._data[0] + self._data[2] >= other._data[0] + other._data[2]
            and self._data[1] + self._data[3] >= other._data[1] + other._data[3]
        )

    def intersects(self, other: "Rect") -> bool:
        """Check if this rectangle overlaps with another."""
        return not (
            self._data[0] >= other._data[0] + other._data[2]
            or self._data[0] + self._data[2] <= other._data[0]
            or self._data[1] >= other._data[1] + other._data[3]
            or self._data[1] + self._data[3] <= other._data[1]
        )

    def to_tuple(self) -> Tuple[int, int, int, int]:
        """Return (x, y, width, height) tuple."""
        return (
            int(self._data[0]),
            int(self._data[1]),
            int(self._data[2]),
            int(self._data[3]),
        )

    def to_numpy(self) -> np.ndarray:
        """Return [x, y, width, height] as numpy array (copy)."""
        return self._data.copy()

    @classmethod
    def from_numpy(cls, arr: np.ndarray) -> "Rect":
        """Create from numpy array [x, y, width, height]."""
        return cls(int(arr[0]), int(arr[1]), int(arr[2]), int(arr[3]))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Rect):
            return NotImplemented
        return bool(np.array_equal(self._data, other._data))

    def __hash__(self) -> int:
        return hash(tuple(self._data))

    def __repr__(self) -> str:
        return f"Rect(x={self._data[0]}, y={self._data[1]}, w={self._data[2]}, h={self._data[3]})"


@dataclass
class FrameInput:
    """Input frame data for the packer.

    Attributes:
        id: Unique identifier for the frame.
        width: Frame width in pixels.
        height: Frame height in pixels.
        user_data: Optional arbitrary data passed through to output.
    """

    id: str
    width: int
    height: int
    user_data: Optional[Any] = None

    def clone(self) -> "FrameInput":
        """Create a copy of this frame input."""
        return FrameInput(self.id, self.width, self.height, self.user_data)


@dataclass
class PackedFrame:
    """Result of packing a single frame.

    Contains the original frame data plus its assigned position in the atlas.

    Attributes:
        frame: Original FrameInput.
        x: X position in the atlas.
        y: Y position in the atlas.
        rotated: True if frame was rotated 90° clockwise during packing.
        flipped_x: True if frame was flipped horizontally.
        flipped_y: True if frame was flipped vertically.
    """

    frame: FrameInput
    x: int = 0
    y: int = 0
    rotated: bool = False
    flipped_x: bool = False
    flipped_y: bool = False

    @property
    def id(self) -> str:
        """Frame identifier."""
        return self.frame.id

    @property
    def width(self) -> int:
        """Effective width in atlas (swapped if rotated)."""
        if self.rotated:
            return self.frame.height
        return self.frame.width

    @property
    def height(self) -> int:
        """Effective height in atlas (swapped if rotated)."""
        if self.rotated:
            return self.frame.width
        return self.frame.height

    @property
    def source_width(self) -> int:
        """Original frame width before rotation."""
        return self.frame.width

    @property
    def source_height(self) -> int:
        """Original frame height before rotation."""
        return self.frame.height

    @property
    def rect(self) -> Rect:
        """Get the placement rectangle in atlas coordinates."""
        return Rect(self.x, self.y, self.width, self.height)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "rotated": self.rotated,
            "flipped_x": self.flipped_x,
            "flipped_y": self.flipped_y,
            "user_data": self.frame.user_data,
        }


@dataclass
class PackerOptions:
    """Configuration options for packer algorithms.

    Attributes:
        max_width: Maximum atlas width in pixels.
        max_height: Maximum atlas height in pixels.
        padding: Pixels of padding between frames.
        border_padding: Pixels of padding around atlas edges.
        power_of_two: Force atlas dimensions to be powers of 2.
        force_square: Force atlas to be square.
        allow_rotation: Allow 90° rotation for better packing.
        allow_flip: Allow horizontal/vertical flipping (limited format support).
        expand_strategy: How to grow the atlas when frames don't fit.
        sort_by_area: Pre-sort frames by area descending before packing.
        sort_by_max_side: Pre-sort frames by max(width, height) descending.
    """

    max_width: int = 8192
    max_height: int = 8192
    padding: int = 2
    border_padding: int = 0
    power_of_two: bool = False
    force_square: bool = False
    allow_rotation: bool = False
    allow_flip: bool = False
    expand_strategy: ExpandStrategy = ExpandStrategy.SHORT_SIDE
    sort_by_area: bool = False
    sort_by_max_side: bool = True

    def validate(self) -> None:
        """Validate options and raise InvalidOptionsError if invalid."""
        if self.max_width < 1:
            raise InvalidOptionsError(
                PackerErrorCode.INVALID_OPTIONS,
                f"max_width must be positive, got {self.max_width}",
            )
        if self.max_height < 1:
            raise InvalidOptionsError(
                PackerErrorCode.INVALID_OPTIONS,
                f"max_height must be positive, got {self.max_height}",
            )
        if self.padding < 0:
            raise InvalidOptionsError(
                PackerErrorCode.INVALID_OPTIONS,
                f"padding must be non-negative, got {self.padding}",
            )
        if self.border_padding < 0:
            raise InvalidOptionsError(
                PackerErrorCode.INVALID_OPTIONS,
                f"border_padding must be non-negative, got {self.border_padding}",
            )


@dataclass
class PackerWarning:
    """Non-fatal issue detected during packing.

    Attributes:
        code: Categorized warning code.
        message: Human-readable description.
        frame_id: ID of affected frame, if applicable.
        details: Additional context.
    """

    code: PackerErrorCode
    message: str
    frame_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class PackerResult:
    """Container for packing outcomes with full diagnostics.

    Attributes:
        success: True if packing completed successfully.
        packed_frames: List of frames with their atlas positions.
        atlas_width: Final atlas width in pixels.
        atlas_height: Final atlas height in pixels.
        efficiency: Ratio of used area to total atlas area (0.0-1.0).
        warnings: Non-fatal issues encountered during packing.
        errors: List of errors that occurred.
        algorithm_name: Name of the packer algorithm used.
        heuristic_name: Name of the heuristic used, if applicable.
    """

    success: bool = False
    packed_frames: List[PackedFrame] = field(default_factory=list)
    atlas_width: int = 0
    atlas_height: int = 0
    efficiency: float = 0.0
    warnings: List[PackerWarning] = field(default_factory=list)
    errors: List[PackerError] = field(default_factory=list)
    algorithm_name: Optional[str] = None
    heuristic_name: Optional[str] = None

    @property
    def frame_count(self) -> int:
        """Number of successfully packed frames."""
        return len(self.packed_frames)

    @property
    def is_valid(self) -> bool:
        """Return True if packing produced valid output."""
        return self.success and self.frame_count > 0

    @property
    def total_area(self) -> int:
        """Total atlas area in pixels."""
        return self.atlas_width * self.atlas_height

    @property
    def used_area(self) -> int:
        """Total area used by packed frames."""
        return sum(f.width * f.height for f in self.packed_frames)

    def calculate_efficiency(self) -> float:
        """Calculate and store efficiency ratio."""
        if self.total_area > 0:
            self.efficiency = self.used_area / self.total_area
        else:
            self.efficiency = 0.0
        return self.efficiency

    def add_warning(
        self,
        code: PackerErrorCode,
        message: str,
        frame_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a warning to the result."""
        self.warnings.append(PackerWarning(code, message, frame_id, details))

    def add_error(
        self,
        code: PackerErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an error to the result."""
        self.errors.append(PackerError(code, message, details))

    def get_frame_by_id(self, frame_id: str) -> Optional[PackedFrame]:
        """Find a packed frame by its ID."""
        for frame in self.packed_frames:
            if frame.id == frame_id:
                return frame
        return None

    def get_summary(self) -> str:
        """Return a human-readable summary of the packing result."""
        status = "success" if self.success else "failed"
        parts = [
            f"Packing {status}: {self.frame_count} frames",
            f"Atlas: {self.atlas_width}x{self.atlas_height}",
            f"Efficiency: {self.efficiency:.1%}",
            f"{len(self.warnings)} warnings",
            f"{len(self.errors)} errors",
        ]
        if self.algorithm_name:
            parts.insert(0, f"Algorithm: {self.algorithm_name}")
        return " | ".join(parts)


# =============================================================================
# NumPy Batch Utilities
# =============================================================================


class RectBatch:
    """Efficient batch storage for multiple rectangles using NumPy.

    Stores rectangle data in a contiguous NumPy array for fast batch operations.
    Format: Each row is [x, y, width, height].

    Attributes:
        data: NumPy array of shape (n, 4) with dtype int32.
    """

    def __init__(self, capacity: int = 64) -> None:
        """Initialize with preallocated capacity.

        Args:
            capacity: Initial number of rectangles to allocate space for.
        """
        self.data = np.zeros((capacity, 4), dtype=np.int32)
        self._count = 0

    @property
    def count(self) -> int:
        """Number of rectangles currently stored."""
        return self._count

    def clear(self) -> None:
        """Remove all rectangles."""
        self._count = 0

    def add(self, rect: Rect) -> int:
        """Add a rectangle and return its index."""
        if self._count >= len(self.data):
            # Double capacity
            new_data = np.zeros((len(self.data) * 2, 4), dtype=np.int32)
            new_data[: len(self.data)] = self.data
            self.data = new_data

        self.data[self._count] = [rect.x, rect.y, rect.width, rect.height]
        idx = self._count
        self._count += 1
        return idx

    def remove(self, index: int) -> None:
        """Remove rectangle at index by swapping with last element."""
        if index < 0 or index >= self._count:
            return
        if index < self._count - 1:
            self.data[index] = self.data[self._count - 1]
        self._count -= 1

    def get(self, index: int) -> Rect:
        """Get rectangle at index."""
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")
        return Rect.from_numpy(self.data[index])

    def set(self, index: int, rect: Rect) -> None:
        """Set rectangle at index."""
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")
        self.data[index] = [rect.x, rect.y, rect.width, rect.height]

    def areas(self) -> np.ndarray:
        """Return array of areas for all rectangles."""
        return self.data[: self._count, 2] * self.data[: self._count, 3]

    def intersects_any(self, rect: Rect) -> bool:
        """Check if rect intersects any rectangle in the batch."""
        if self._count == 0:
            return False

        # Vectorized intersection test
        d = self.data[: self._count]
        rx, ry, rw, rh = rect.x, rect.y, rect.width, rect.height

        # Not intersecting if:
        #   self.x >= other.right OR self.right <= other.x OR
        #   self.y >= other.bottom OR self.bottom <= other.y
        not_intersecting = (
            (d[:, 0] >= rx + rw)
            | (d[:, 0] + d[:, 2] <= rx)
            | (d[:, 1] >= ry + rh)
            | (d[:, 1] + d[:, 3] <= ry)
        )
        return not np.all(not_intersecting)

    def to_list(self) -> List[Rect]:
        """Convert to list of Rect objects."""
        return [Rect.from_numpy(self.data[i]) for i in range(self._count)]


__all__ = [
    # Error types
    "PackerErrorCode",
    "PackerError",
    "FrameTooLargeError",
    "AtlasOverflowError",
    "InvalidOptionsError",
    # Heuristic enums
    "MaxRectsHeuristic",
    "GuillotinePlacement",
    "GuillotineSplit",
    "ShelfHeuristic",
    "SkylineHeuristic",
    "ExpandStrategy",
    # Core types
    "Rect",
    "FrameInput",
    "PackedFrame",
    "PackerOptions",
    "PackerWarning",
    "PackerResult",
    # NumPy utilities
    "RectBatch",
]
