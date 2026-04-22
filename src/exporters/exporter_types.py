#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Unified types and error handling for all spritesheet/atlas exporters.

This module defines:
    - ExportOptions: Dataclass for controlling export behavior.
    - ExportResult: Dataclass holding export outcomes and diagnostics.
    - ExporterErrorCode: Enum of error categories for programmatic handling.
    - ExporterError hierarchy: Typed exceptions for export failures.

The exporter system mirrors the parser architecture, providing symmetric
operations: parsers read metadata → SpriteData, exporters write SpriteData → metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

# Re-export SpriteData from parser_types for consistency
from parsers.parser_types import SpriteData


class ExporterErrorCode(Enum):
    """Categorized error codes for exporter failures."""

    # File-level errors
    FILE_WRITE_ERROR = auto()
    DIRECTORY_NOT_FOUND = auto()
    PERMISSION_DENIED = auto()

    # Image-level errors
    IMAGE_NOT_FOUND = auto()
    IMAGE_READ_ERROR = auto()
    IMAGE_WRITE_ERROR = auto()
    INVALID_IMAGE_FORMAT = auto()

    # Sprite-level errors
    SPRITE_MISSING_DATA = auto()
    SPRITE_INVALID_BOUNDS = auto()
    SPRITE_OUT_OF_BOUNDS = auto()
    DUPLICATE_SPRITE_NAME = auto()

    # Packing errors
    PACKING_FAILED = auto()
    ATLAS_TOO_LARGE = auto()
    NO_SPRITES_PROVIDED = auto()

    # Format errors
    UNSUPPORTED_FORMAT = auto()
    SERIALIZATION_ERROR = auto()

    # Unknown/fallback
    UNKNOWN_ERROR = auto()


class ExporterError(Exception):
    """Base exception for all exporter errors.

    Attributes:
        code: Categorized error code for programmatic handling.
        message: Human-readable error description.
        file_path: Path to the file that caused the error.
        details: Optional dict with additional context.
    """

    def __init__(
        self,
        code: ExporterErrorCode,
        message: str,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize an exporter error.

        Args:
            code: Error category code.
            message: Human-readable description.
            file_path: Path to the problematic file.
            details: Additional context dict.
        """
        self.code = code
        self.message = message
        self.file_path = file_path
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with context."""
        parts = [self.message]
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"Details: {detail_str}")
        return " | ".join(parts)


class FileWriteError(ExporterError):
    """Error writing to a file."""

    pass


class ImageError(ExporterError):
    """Error processing images."""

    pass


class PackingError(ExporterError):
    """Error during sprite packing."""

    pass


class FormatError(ExporterError):
    """Error in metadata format or serialization."""

    pass


@dataclass
class ExporterWarning:
    """Non-fatal issue detected during export.

    Attributes:
        code: Categorized warning code.
        message: Human-readable description.
        sprite_name: Name of affected sprite, if applicable.
        details: Additional context.
    """

    code: ExporterErrorCode
    message: str
    sprite_name: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ExportOptions:
    """Configuration options for atlas export.

    Controls how sprites are packed and metadata is formatted.

    Attributes:
        image_format: Output image format (PNG, WEBP, etc.).
        padding: Pixels of padding between sprites.
        power_of_two: Force atlas dimensions to power of 2.
        max_width: Maximum atlas width in pixels.
        max_height: Maximum atlas height in pixels.
        allow_rotation: Allow 90-degree rotation for better packing.
        trim_sprites: Trim transparent edges from sprites.
        pretty_print: Format metadata with indentation.
        include_metadata: Include atlas metadata (size, image name).
        custom_properties: Format-specific additional properties.
    """

    image_format: str = "PNG"
    padding: int = 2
    power_of_two: bool = False
    max_width: int = 4096
    max_height: int = 4096
    allow_rotation: bool = False
    trim_sprites: bool = False
    pretty_print: bool = True
    include_metadata: bool = True
    custom_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportResult:
    """Container for exporter output with full diagnostics.

    Attributes:
        success: True if export completed successfully.
        atlas_path: Path to the generated atlas image.
        metadata_path: Path to the generated metadata file.
        atlas_width: Final atlas width in pixels.
        atlas_height: Final atlas height in pixels.
        sprite_count: Number of sprites exported.
        warnings: Non-fatal issues encountered during export.
        errors: List of errors that occurred.
        exporter_name: Name of the exporter class used.
    """

    success: bool = False
    atlas_path: Optional[str] = None
    metadata_path: Optional[str] = None
    atlas_width: int = 0
    atlas_height: int = 0
    sprite_count: int = 0
    warnings: List[ExporterWarning] = field(default_factory=list)
    errors: List[ExporterError] = field(default_factory=list)
    exporter_name: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Return True if export produced valid output."""
        return self.success and self.sprite_count > 0

    @property
    def warning_count(self) -> int:
        """Return count of warnings."""
        return len(self.warnings)

    @property
    def error_count(self) -> int:
        """Return count of errors."""
        return len(self.errors)

    def add_warning(
        self,
        code: ExporterErrorCode,
        message: str,
        sprite_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a warning to the result.

        Args:
            code: Warning category code.
            message: Human-readable description.
            sprite_name: Name of affected sprite.
            details: Additional context.
        """
        self.warnings.append(ExporterWarning(code, message, sprite_name, details))

    def add_error(
        self,
        code: ExporterErrorCode,
        message: str,
        file_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an error to the result.

        Args:
            code: Error category code.
            message: Human-readable description.
            file_path: Path to problematic file.
            details: Additional context.
        """
        self.errors.append(ExporterError(code, message, file_path, details))

    def get_summary(self) -> str:
        """Return a human-readable summary of the export result.

        Returns:
            Formatted summary string.
        """
        status = "success" if self.success else "failed"
        parts = [
            f"Export {status}: {self.sprite_count} sprites",
            f"Atlas: {self.atlas_width}x{self.atlas_height}",
            f"{self.warning_count} warnings",
            f"{self.error_count} errors",
        ]
        if self.atlas_path:
            parts.insert(0, f"Output: {Path(self.atlas_path).name}")
        return " | ".join(parts)


@dataclass
class PackedSprite:
    """A sprite with its assigned position in the atlas.

    Holds both the original sprite data and its packed coordinates.

    Attributes:
        sprite: Original SpriteData from input.
        atlas_x: X position in the packed atlas.
        atlas_y: Y position in the packed atlas.
        rotated: True if sprite was rotated during packing.
    """

    sprite: SpriteData
    atlas_x: int = 0
    atlas_y: int = 0
    rotated: bool = False

    @property
    def name(self) -> str:
        """Return the sprite name."""
        return self.sprite["name"]

    @property
    def width(self) -> int:
        """Return effective width (swapped if rotated)."""
        w = self.sprite["width"]
        h = self.sprite["height"]
        return h if self.rotated else w

    @property
    def height(self) -> int:
        """Return effective height (swapped if rotated)."""
        w = self.sprite["width"]
        h = self.sprite["height"]
        return w if self.rotated else h


@dataclass
class GeneratorMetadata:
    """Metadata about the generation process for watermarking.

    This information can be included as comments in formats that support them.

    Attributes:
        app_version: Application version string (e.g., "1.9.5").
        packer: Name of the packing algorithm used (e.g., "MaxRects").
        heuristic: Heuristic used for packing (e.g., "BestShortSideFit").
        efficiency: Packing efficiency percentage (0-100).
    """

    app_version: str = ""
    packer: str = ""
    heuristic: str = ""
    efficiency: float = 0.0

    def format_comment_lines(self) -> List[str]:
        """Format metadata as comment lines.

        Returns:
            List of strings suitable for inclusion in metadata files.
        """
        lines = []
        if self.app_version:
            lines.append(f"Generated by TextureAtlas Toolbox ({self.app_version})")
        else:
            lines.append("Generated by TextureAtlas Toolbox")
        if self.packer:
            lines.append(f"Packer: {self.packer}")
        if self.heuristic:
            lines.append(f"Heuristic: {self.heuristic}")
        if self.efficiency > 0:
            lines.append(f"Efficiency: {self.efficiency:.1f}%")
        return lines


FORMATS_SUPPORTING_ROTATION = frozenset(
    {
        "starling-xml",
        "json-hash",
        "json-array",
        "aseprite",
        "texture-packer-xml",
        "spine",
        "phaser3",
        "plist",
        "paper2d",
        "gdx",
        "css",
    }
)
"""Format keys whose schemas can losslessly represent a 90 degree rotated sprite.

CSS encodes rotation via `transform: rotate(-90deg)`. The other listed
formats carry an explicit `rotated` / `rotate` field. Formats not in
this set (UIKit plist, Godot tpsheet, Egret2D, TXT) have no rotation
representation; emitting a rotated sprite to one of them would
silently swap dimensions and produce metadata that no longer matches
the atlas image. Both the GUI (which disables the rotation checkbox)
and the affected exporters (which raise `FormatError(UNSUPPORTED_FORMAT,
...)` when a rotated sprite arrives) consult this set.
"""


FORMATS_SUPPORTING_FLIP = frozenset({"starling-xml"})
"""Format keys whose schemas carry per-frame `flipX` / `flipY` attributes."""


__all__ = [
    "ExporterErrorCode",
    "ExporterError",
    "FileWriteError",
    "ImageError",
    "PackingError",
    "FormatError",
    "ExporterWarning",
    "ExportOptions",
    "ExportResult",
    "PackedSprite",
    "GeneratorMetadata",
    "SpriteData",
    "FORMATS_SUPPORTING_ROTATION",
    "FORMATS_SUPPORTING_FLIP",
]
