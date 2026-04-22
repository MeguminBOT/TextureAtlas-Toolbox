#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Egret2D JSON atlas format.

Generates JSON metadata using the simple Egret2D schema with direct
x, y, w, h keys (no nested frame object).

Output Format:
    ```json
    {
        "file": "atlas.png",
        "frames": {
            "sprite_01": {"x": 0, "y": 0, "w": 64, "h": 64},
            "sprite_02": {"x": 66, "y": 0, "w": 48, "h": 48}
        }
    }
    ```
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import (
    ExportOptions,
    GeneratorMetadata,
    PackedSprite,
)


@dataclass
class Egret2DExportOptions:
    """Egret2D-specific export options.

    Attributes:
        include_file_key: Include "file" key with image name.
        include_offset: Include offX/offY for trimmed sprites.
        include_source_size: Include sourceW/sourceH for trimmed sprites.
    """

    include_file_key: bool = True
    include_offset: bool = True
    include_source_size: bool = True


@ExporterRegistry.register
class Egret2DExporter(BaseExporter):
    """Export sprites to Egret2D JSON atlas format.

    The Egret2D format uses a simple frames hash with direct x/y/w/h
    properties, making it lightweight and easy to parse.

    Usage:
        from exporters import Egret2DExporter, ExportOptions

        exporter = Egret2DExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".json"
    FORMAT_NAME = "egret2d"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Egret2D exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["egret2d"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> Egret2DExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            Egret2DExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("egret2d")

        if isinstance(opts, Egret2DExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return Egret2DExportOptions(**opts)
            except TypeError:
                return Egret2DExportOptions()
        else:
            return Egret2DExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Egret2D JSON metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark info.

        Returns:
            JSON string with frames hash.

        Raises:
            FormatError: When `packed_sprites` contains a rotated
                sprite. The Egret2D schema has no rotation field and
                silently swapping `w`/`h` would produce metadata
                that no longer matches the atlas image.
        """
        self._reject_rotated_sprites(packed_sprites)
        opts = self._format_options

        # Build frames hash
        frames: Dict[str, Dict[str, int]] = {}
        for packed in packed_sprites:
            frames[packed.name] = self._build_frame_entry(packed, opts)

        # Build output
        output: Dict[str, Any] = {}
        if opts.include_file_key:
            output["file"] = image_name
        output["frames"] = frames

        # Add generator metadata if provided
        if generator_metadata:
            meta_block: Dict[str, Any] = {}
            if generator_metadata.app_version:
                meta_block["generator"] = (
                    f"TextureAtlas Toolbox ({generator_metadata.app_version})"
                )
            if generator_metadata.packer:
                meta_block["packer"] = generator_metadata.packer
            if generator_metadata.heuristic:
                meta_block["heuristic"] = generator_metadata.heuristic
            if generator_metadata.efficiency > 0:
                meta_block["efficiency"] = f"{generator_metadata.efficiency:.1f}%"
            if meta_block:
                output["meta"] = meta_block

        # Serialize
        indent = 4 if self.options.pretty_print else None
        return json.dumps(output, indent=indent, ensure_ascii=False)

    def _build_frame_entry(
        self,
        packed: PackedSprite,
        opts: Egret2DExportOptions,
    ) -> Dict[str, int]:
        """Build a frame entry for the frames hash.

        Args:
            packed: Packed sprite with atlas position.
            opts: Format-specific options.

        Returns:
            Frame data dict with x, y, w, h (and optional offset/source).

        Note:
            The Egret2D format has no rotation field. Rotated
            sprites are rejected upstream by
            `_reject_rotated_sprites`, so this method always emits
            the natural (unrotated) `w`/`h`.
        """
        sprite = packed.sprite
        w = sprite["width"]
        h = sprite["height"]

        entry: Dict[str, int] = {
            "x": packed.atlas_x,
            "y": packed.atlas_y,
            "w": w,
            "h": h,
        }

        # Optional trim offset
        if opts.include_offset:
            frame_x = sprite.get("frameX", 0)
            frame_y = sprite.get("frameY", 0)
            if frame_x != 0 or frame_y != 0:
                entry["offX"] = -frame_x
                entry["offY"] = -frame_y

        # Optional source size
        if opts.include_source_size:
            frame_w = sprite.get("frameWidth", w)
            frame_h = sprite.get("frameHeight", h)
            if frame_w != w or frame_h != h:
                entry["sourceW"] = frame_w
                entry["sourceH"] = frame_h

        return entry


__all__ = ["Egret2DExporter", "Egret2DExportOptions"]
