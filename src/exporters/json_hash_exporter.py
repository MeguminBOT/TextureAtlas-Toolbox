#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for TexturePacker JSON Hash format.

Generates JSON metadata with frames as an object/hash where sprite names
are keys mapping to frame data. This is the most common TexturePacker format.

Output Format:
    ```json
    {
        "frames": {
            "sprite_01": {
                "frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                "rotated": false,
                "trimmed": true,
                "spriteSourceSize": {"x": 2, "y": 2, "w": 60, "h": 60},
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
class JsonHashExportOptions:
    """JSON Hash-specific export options.

    Attributes:
        include_pivot: Include pivot point data (default center 0.5, 0.5).
        include_meta: Include meta block with image/size/format info.
        format_string: Pixel format string for meta block (e.g., "RGBA8888").
        scale_string: Scale string for meta block (e.g., "1").
        app_name: Application name for meta.app field.
        app_version: Application version for meta.version field.
    """

    include_pivot: bool = True
    include_meta: bool = True
    format_string: str = "RGBA8888"
    scale_string: str = "1"
    app_name: str = "TextureAtlas Toolbox"
    app_version: str = "2.0.5"


@ExporterRegistry.register
class JsonHashExporter(BaseExporter):
    """Export sprites to TexturePacker JSON Hash format.

    The JSON Hash format uses sprite names as keys in a frames object,
    making it easy to look up sprites by name at runtime.

    Usage:
        from exporters import JsonHashExporter, ExportOptions

        exporter = JsonHashExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".json"
    FORMAT_NAME = "json-hash"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the JSON Hash exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["json_hash"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> JsonHashExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            JsonHashExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("json_hash")

        if isinstance(opts, JsonHashExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return JsonHashExportOptions(**opts)
            except TypeError:
                return JsonHashExportOptions()
        else:
            return JsonHashExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate JSON Hash metadata.

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

        # Build output structure
        output: Dict[str, Any] = {"frames": frames}

        # Add meta block if requested
        if opts.include_meta:
            meta_block: Dict[str, Any] = {
                "app": opts.app_name,
                "version": opts.app_version,
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
        opts: JsonHashExportOptions,
    ) -> Dict[str, Any]:
        """Build a single frame entry for the frames hash.

        Args:
            packed: Packed sprite with atlas position.
            opts: Format-specific options.

        Returns:
            Frame data dict with frame, rotated, trimmed, sourceSize, etc.
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

        # Determine if trimmed
        trimmed = frame_x != 0 or frame_y != 0 or frame_w != width or frame_h != height

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
                "w": width,
                "h": height,
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


__all__ = ["JsonHashExporter", "JsonHashExportOptions"]
