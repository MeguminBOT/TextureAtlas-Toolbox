#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Phaser 3 atlas JSON format.

Generates JSON metadata using the Phaser 3 multi-texture atlas structure
with textures array containing frames arrays.

Output Format:
    ```json
    {
        "textures": [
            {
                "image": "atlas.png",
                "format": "RGBA8888",
                "size": {"w": 512, "h": 512},
                "scale": 1,
                "frames": [
                    {
                        "filename": "sprite_01",
                        "frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                        "rotated": false,
                        "trimmed": false,
                        "spriteSourceSize": {"x": 0, "y": 0, "w": 64, "h": 64},
                        "sourceSize": {"w": 64, "h": 64}
                    }
                ]
            }
        ]
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
class Phaser3ExportOptions:
    """Phaser 3-specific export options.

    Attributes:
        format_string: Pixel format string (e.g., "RGBA8888").
        scale: Atlas scale factor (1 for standard, 2 for @2x).
    """

    format_string: str = "RGBA8888"
    scale: float = 1.0


@ExporterRegistry.register
class Phaser3Exporter(BaseExporter):
    """Export sprites to Phaser 3 multi-atlas JSON format.

    Phaser 3 uses a textures array that can contain multiple texture
    pages, each with its own frames array. This exporter creates a
    single-page atlas.

    Usage:
        from exporters import Phaser3Exporter, ExportOptions

        exporter = Phaser3Exporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".json"
    FORMAT_NAME = "phaser3"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Phaser 3 exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["phaser3"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> Phaser3ExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            Phaser3ExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("phaser3")

        if isinstance(opts, Phaser3ExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return Phaser3ExportOptions(**opts)
            except TypeError:
                return Phaser3ExportOptions()
        else:
            return Phaser3ExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Phaser 3 atlas JSON metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark info.

        Returns:
            JSON string with textures array containing frames.
        """
        opts = self._format_options

        # Build frames list
        frames: List[Dict[str, Any]] = []
        for packed in packed_sprites:
            frames.append(self._build_frame_entry(packed))

        # Build texture entry
        texture: Dict[str, Any] = {
            "image": image_name,
            "format": opts.format_string,
            "size": {"w": atlas_width, "h": atlas_height},
            "scale": opts.scale,
            "frames": frames,
        }

        # Build output structure
        output: Dict[str, Any] = {"textures": [texture]}

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

    def _build_frame_entry(self, packed: PackedSprite) -> Dict[str, Any]:
        """Build a single frame entry for the frames array.

        Args:
            packed: Packed sprite with atlas position.

        Returns:
            Frame data dict for Phaser 3 format.
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", width)
        frame_h = sprite.get("frameHeight", height)

        # Check if rotated
        is_rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap width/height when rotated (standard TexturePacker convention)
        atlas_w, atlas_h = (height, width) if is_rotated else (width, height)

        trimmed = frame_x != 0 or frame_y != 0 or frame_w != width or frame_h != height

        return {
            "filename": packed.name,
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
                "w": width,
                "h": height,
            },
            "sourceSize": {
                "w": frame_w,
                "h": frame_h,
            },
        }


__all__ = ["Phaser3Exporter", "Phaser3ExportOptions"]
