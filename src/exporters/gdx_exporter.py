#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for libGDX TexturePacker .atlas format.

Generates the modern text-based atlas format used by the libGDX framework.
Uses the combined ``bounds`` and ``offsets`` fields introduced when
``legacyOutput`` is set to ``false`` in the TexturePacker settings.

Output Format::

    atlas.png
    size: 512, 512
    format: RGBA8888
    filter: Linear, Linear
    repeat: none
    sprite_01
      bounds: 0, 0, 64, 64
      offsets: 0, 0, 64, 64
      rotate: false
      index: 0
    sprite_02
      bounds: 66, 0, 48, 48
      offsets: 0, 0, 48, 48
      rotate: false
      index: 1
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
class GdxExportOptions:
    """libGDX atlas-specific export options.

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
class GdxExporter(BaseExporter):
    """Export sprites to libGDX TexturePacker .atlas format.

    The libGDX atlas format is a simple text format used by the libGDX
    game framework and its TexturePacker tool.  This exporter emits the
    **modern** field layout (``bounds``/``offsets``).

    Usage:
        from exporters import GdxExporter, ExportOptions

        exporter = GdxExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".atlas"
    FORMAT_NAME = "gdx"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> GdxExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            GdxExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("gdx")

        if isinstance(opts, GdxExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return GdxExportOptions(**opts)
            except TypeError:
                return GdxExportOptions()
        else:
            return GdxExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate libGDX atlas text metadata.

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

        # Page header
        lines.append(image_name)
        lines.append(f"size: {atlas_width}, {atlas_height}")
        lines.append(f"format: {opts.format}")
        lines.append(f"filter: {opts.filter_min}, {opts.filter_mag}")
        lines.append(f"repeat: {opts.repeat}")
        if opts.pma:
            lines.append("pma: true")

        # Generator metadata as custom page-level fields (parsers ignore unknown keys)
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

        # Regions
        for packed in packed_sprites:
            lines.extend(self._build_region(packed))

        return "\n".join(lines) + "\n"

    def _build_region(self, packed: PackedSprite) -> List[str]:
        """Build lines for a single region using modern field layout.

        Args:
            packed: Packed sprite with atlas position.

        Returns:
            List of lines for this region.
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]
        frame_w = sprite.get("frameWidth", width)
        frame_h = sprite.get("frameHeight", height)
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap when rotated
        atlas_w, atlas_h = (height, width) if rotated else (width, height)

        # Offset from frame coordinates
        offset_x = -frame_x if frame_x else 0
        offset_y = -frame_y if frame_y else 0

        # Frame index
        frame_index = sprite.get("index", -1)
        if frame_index is None:
            frame_index = -1

        lines = [
            sprite["name"],
            f"  bounds: {packed.atlas_x}, {packed.atlas_y}, {atlas_w}, {atlas_h}",
            f"  offsets: {offset_x}, {offset_y}, {frame_w}, {frame_h}",
        ]

        if rotated:
            lines.append("  rotate: 90")
        lines.append(f"  index: {frame_index}")

        return lines


__all__ = ["GdxExporter", "GdxExportOptions"]
