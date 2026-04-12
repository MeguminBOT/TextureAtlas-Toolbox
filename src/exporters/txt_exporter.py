#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for simple text-based spritesheet format.

Generates a plain text file with sprite definitions in the format:
    name = x y width height

Output Format:
    ```
    sprite_01 = 0 0 64 64
    sprite_02 = 66 0 48 48
    sprite_03 = 0 66 32 32
    ```
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
class TxtExportOptions:
    """TXT format-specific export options.

    Attributes:
        include_header: Add a comment header with image name.
        comment_prefix: Prefix for comment lines (e.g., "#", "//").
    """

    include_header: bool = True
    comment_prefix: str = "#"


@ExporterRegistry.register
class TxtExporter(BaseExporter):
    """Export sprites to simple text format.

    The TXT format is a minimal, human-readable format with one
    sprite per line: name = x y width height

    Usage:
        from exporters import TxtExporter, ExportOptions

        exporter = TxtExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".txt"
    FORMAT_NAME = "txt"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the TXT exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["txt"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> TxtExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            TxtExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("txt")

        if isinstance(opts, TxtExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return TxtExportOptions(**opts)
            except TypeError:
                return TxtExportOptions()
        else:
            return TxtExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate TXT spritesheet content.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark comments.

        Returns:
            Text content with sprite definitions.
        """
        opts = self._format_options
        lines: List[str] = []

        # Add generator metadata as comments
        if generator_metadata:
            comment_lines = generator_metadata.format_comment_lines()
            for line in comment_lines:
                lines.append(f"{opts.comment_prefix} {line}")
            if comment_lines:
                lines.append("")

        # Optional header
        if opts.include_header:
            lines.append(f"{opts.comment_prefix} Atlas: {image_name}")
            lines.append(f"{opts.comment_prefix} Size: {atlas_width} x {atlas_height}")
            lines.append(f"{opts.comment_prefix} Sprites: {len(packed_sprites)}")
            lines.append("")

        # Sprite definitions
        for packed in packed_sprites:
            sprite = packed.sprite
            width = sprite["width"]
            height = sprite["height"]

            # Check if rotated - swap dimensions since TXT format has no rotation field
            is_rotated = packed.rotated or sprite.get("rotated", False)
            atlas_w, atlas_h = (height, width) if is_rotated else (width, height)

            line = (
                f"{sprite['name']} = "
                f"{packed.atlas_x} {packed.atlas_y} "
                f"{atlas_w} {atlas_h}"
            )
            lines.append(line)

        return "\n".join(lines) + "\n"


__all__ = ["TxtExporter", "TxtExportOptions"]
