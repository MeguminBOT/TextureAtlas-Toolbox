#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Spine .atlas text format.

Generates the text-based atlas format used by Spine and libGDX.
Each sprite is defined with indented key-value pairs under its name.

Output Format:
    ```
    atlas.png
    size: 512, 512
    format: RGBA8888
    filter: Linear, Linear
    repeat: none
    sprite_01
      rotate: false
      xy: 0, 0
      size: 64, 64
      orig: 64, 64
      offset: 0, 0
      index: -1
    sprite_02
      rotate: false
      xy: 66, 0
      size: 48, 48
      orig: 48, 48
      offset: 0, 0
      index: -1
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
class SpineExportOptions:
    """Spine atlas-specific export options.

    Attributes:
        format: Pixel format string (e.g., "RGBA8888", "RGB888").
        filter_min: Minification filter (e.g., "Linear", "Nearest").
        filter_mag: Magnification filter (e.g., "Linear", "Nearest").
        repeat: Repeat mode ("none", "x", "y", "xy").
        pma: Premultiplied alpha flag.
    """

    format: str = "RGBA8888"
    filter_min: str = "Linear"
    filter_mag: str = "Linear"
    repeat: str = "none"
    pma: bool = False


@ExporterRegistry.register
class SpineExporter(BaseExporter):
    """Export sprites to Spine/libGDX .atlas text format.

    The Spine atlas format is a simple text format used by the Spine
    animation tool and libGDX game framework. Each page (texture) is
    listed with its properties, followed by indented region definitions.

    Usage:
        from exporters import SpineExporter, ExportOptions

        exporter = SpineExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".atlas"
    FORMAT_NAME = "spine"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Spine exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["spine"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> SpineExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            SpineExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("spine")

        if isinstance(opts, SpineExportOptions):
            return opts
        elif isinstance(opts, dict):
            return SpineExportOptions(**opts)
        else:
            return SpineExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Spine atlas text metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for header info.

        Returns:
            Text content for the .atlas file.
        """
        opts = self._format_options
        lines: List[str] = []

        # Page header (texture file)
        lines.append(image_name)
        lines.append(f"size: {atlas_width}, {atlas_height}")
        lines.append(f"format: {opts.format}")
        lines.append(f"filter: {opts.filter_min}, {opts.filter_mag}")
        lines.append(f"repeat: {opts.repeat}")
        if opts.pma:
            lines.append("pma: true")

        # Add generator metadata as comments (Spine format doesn't have official comments,
        # but we can add them as custom properties that parsers will ignore)
        if generator_metadata:
            if generator_metadata.app_version:
                lines.append(
                    f"generator: TextureAtlas Toolbox ({generator_metadata.app_version})"
                )
            if generator_metadata.packer:
                lines.append(f"packer: {generator_metadata.packer}")
            if generator_metadata.heuristic:
                lines.append(f"heuristic: {generator_metadata.heuristic}")
            if generator_metadata.efficiency > 0:
                lines.append(f"efficiency: {generator_metadata.efficiency:.1f}%")

        # Regions (sprites)
        for packed in packed_sprites:
            lines.extend(self._build_region(packed))

        return "\n".join(lines) + "\n"

    def _build_region(self, packed: PackedSprite) -> List[str]:
        """Build lines for a single region/sprite.

        Args:
            packed: Packed sprite with atlas position.

        Returns:
            List of lines for this region (name + indented properties).
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]
        frame_w = sprite.get("frameWidth", width)
        frame_h = sprite.get("frameHeight", height)
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap width/height when rotated (standard TexturePacker convention)
        atlas_w, atlas_h = (height, width) if rotated else (width, height)

        # Use the animation frame index if available; -1 means not indexed
        frame_index = sprite.get("index", -1)
        if frame_index is None:
            frame_index = -1

        lines = [
            sprite["name"],
            f"  rotate: {'true' if rotated else 'false'}",
            f"  xy: {packed.atlas_x}, {packed.atlas_y}",
            f"  size: {atlas_w}, {atlas_h}",
            f"  orig: {frame_w}, {frame_h}",
            f"  offset: {-frame_x}, {-frame_y}",
            f"  index: {frame_index}",
        ]

        return lines


__all__ = ["SpineExporter", "SpineExportOptions"]
