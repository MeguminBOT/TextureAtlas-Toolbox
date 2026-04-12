#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Unreal Engine Paper2D atlas format.

Generates JSON metadata compatible with Unreal Engine's Paper2D
sprite system using the TexturePacker hash structure.

Output Format:
    ```json
    {
        "frames": {
            "sprite_01": {
                "frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                "rotated": false,
                "trimmed": false,
                "spriteSourceSize": {"x": 0, "y": 0, "w": 64, "h": 64},
                "sourceSize": {"w": 64, "h": 64},
                "pivot": {"x": 0.5, "y": 0.5}
            }
        },
        "meta": {
            "image": "atlas.png",
            "size": {"w": 512, "h": 512},
            "format": "RGBA8888",
            "scale": "1"
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
class Paper2DExportOptions:
    """Paper2D-specific export options.

    Attributes:
        include_pivot: Include pivot point data.
        include_meta: Include meta block with image/size info.
        format_string: Pixel format string for meta block.
        scale_string: Scale string for meta block.
    """

    include_pivot: bool = True
    include_meta: bool = True
    format_string: str = "RGBA8888"
    scale_string: str = "1"


@ExporterRegistry.register
class Paper2DExporter(BaseExporter):
    """Export sprites to Unreal Engine Paper2D atlas format.

    Uses the standard TexturePacker hash format which is compatible
    with Paper2D's sprite importer.

    Usage:
        from exporters import Paper2DExporter, ExportOptions

        exporter = Paper2DExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".paper2dsprites"
    FORMAT_NAME = "paper2d"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Paper2D exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["paper2d"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> Paper2DExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            Paper2DExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("paper2d")

        if isinstance(opts, Paper2DExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return Paper2DExportOptions(**opts)
            except TypeError:
                return Paper2DExportOptions()
        else:
            return Paper2DExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Paper2D JSON metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark info.

        Returns:
            JSON string with frames hash and optional meta block.
        """
        opts = self._format_options

        # Build frames hash
        frames: Dict[str, Dict[str, Any]] = {}
        for packed in packed_sprites:
            frames[packed.name] = self._build_frame_entry(packed, opts)

        # Build output
        output: Dict[str, Any] = {"frames": frames}

        # Add meta block
        if opts.include_meta:
            meta_block: Dict[str, Any] = {
                "image": image_name,
                "format": opts.format_string,
                "size": {"w": atlas_width, "h": atlas_height},
                "scale": opts.scale_string,
            }
            # Add generator metadata if provided
            if generator_metadata:
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
            output["meta"] = meta_block

        # Serialize
        indent = 4 if self.options.pretty_print else None
        return json.dumps(output, indent=indent, ensure_ascii=False)

    def _build_frame_entry(
        self,
        packed: PackedSprite,
        opts: Paper2DExportOptions,
    ) -> Dict[str, Any]:
        """Build a frame entry for the frames hash.

        Args:
            packed: Packed sprite with atlas position.
            opts: Format-specific options.

        Returns:
            Frame data dict in Paper2D format.
        """
        sprite = packed.sprite
        w = sprite["width"]
        h = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", w)
        frame_h = sprite.get("frameHeight", h)

        # Check if rotated
        is_rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap width/height when rotated (standard TexturePacker convention)
        atlas_w, atlas_h = (h, w) if is_rotated else (w, h)

        trimmed = frame_x != 0 or frame_y != 0 or frame_w != w or frame_h != h

        entry: Dict[str, Any] = {
            "frame": {
                "x": packed.atlas_x,
                "y": packed.atlas_y,
                "w": atlas_w,
                "h": atlas_h,
            },
            "rotated": is_rotated,
            "trimmed": trimmed,
            "spriteSourceSize": {
                "x": -frame_x,
                "y": -frame_y,
                "w": w,
                "h": h,
            },
            "sourceSize": {
                "w": frame_w,
                "h": frame_h,
            },
        }

        if opts.include_pivot:
            entry["pivot"] = {
                "x": sprite.get("pivotX", 0.5),
                "y": sprite.get("pivotY", 0.5),
            }

        return entry


__all__ = ["Paper2DExporter", "Paper2DExportOptions"]
