#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for TexturePacker Unity format.

Generates semicolon-delimited text files compatible with TexturePacker's
Unity export format.

Output Format:
    ```
    :format=40300
    :texture=atlas.png
    :size=512x512
    sprite_01;0;0;64;64;0.5;0.5
    sprite_02;66;0;48;48;0.5;0.5
    ```

Each sprite line contains: name;x;y;width;height;pivotX;pivotY
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import (
    ExportOptions,
    GeneratorMetadata,
    PackedSprite,
)


@dataclass
class UnityExportOptions:
    """Unity format-specific export options.

    Attributes:
        format_version: Format version number (default 40300).
        include_pivot: Include pivot point values (last two columns).
    """

    format_version: int = 40300
    include_pivot: bool = True


@ExporterRegistry.register
class UnityExporter(BaseExporter):
    """Export sprites to TexturePacker Unity text format.

    Creates semicolon-delimited text files with header lines and
    sprite definitions.

    Usage:
        from exporters import UnityExporter, ExportOptions

        exporter = UnityExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".tpsheet"
    FORMAT_NAME = "unity"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Unity exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["unity"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> UnityExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            UnityExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("unity")

        if isinstance(opts, UnityExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return UnityExportOptions(**opts)
            except TypeError:
                return UnityExportOptions()
        else:
            return UnityExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Unity text metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for header comments.

        Returns:
            Text content with header and sprite definitions.
        """
        opts = self._format_options
        lines: List[str] = []

        # Add generator metadata as comments (lines starting with #)
        if generator_metadata:
            comment_lines = generator_metadata.format_comment_lines()
            for line in comment_lines:
                lines.append(f"# {line}")
            if comment_lines:
                lines.append("")

        # Header lines
        lines.append(f":format={opts.format_version}")
        lines.append(f":texture={image_name}")
        lines.append(f":size={atlas_width}x{atlas_height}")

        # Sprite lines
        for packed in packed_sprites:
            lines.append(self._build_sprite_line(packed, opts))

        return "\n".join(lines) + "\n"

    def _build_sprite_line(
        self,
        packed: PackedSprite,
        opts: UnityExportOptions,
    ) -> str:
        """Build a sprite definition line.

        Args:
            packed: Packed sprite with atlas position.
            opts: Format-specific options.

        Returns:
            Semicolon-delimited sprite line.

        Note:
            The Unity format doesn't have a rotation field, so if sprites
            are rotated in the atlas, the dimensions reflect the actual
            atlas space occupied (swapped width/height).
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]

        # Check if rotated - swap dimensions since Unity format has no rotation field
        is_rotated = packed.rotated or sprite.get("rotated", False)
        atlas_w, atlas_h = (height, width) if is_rotated else (width, height)

        parts = [
            sprite["name"],
            str(packed.atlas_x),
            str(packed.atlas_y),
            str(atlas_w),
            str(atlas_h),
        ]

        if opts.include_pivot:
            pivot_x = sprite.get("pivotX", 0.5)
            pivot_y = sprite.get("pivotY", 0.5)
            parts.append(str(pivot_x))
            parts.append(str(pivot_y))

        return ";".join(parts)


__all__ = ["UnityExporter", "UnityExportOptions"]
