#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Godot atlas JSON format.

Generates JSON metadata compatible with Godot's TexturePacker importer,
using the textures/sprites structure.

Output Format:
    ```json
    {
        "textures": [
            {
                "image": "atlas.png",
                "size": {"w": 512, "h": 512},
                "sprites": [
                    {
                        "filename": "sprite_01",
                        "region": {"x": 0, "y": 0, "w": 64, "h": 64}
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
class GodotExportOptions:
    """Godot atlas-specific export options.

    Attributes:
        include_size: Include size in texture entry.
    """

    include_size: bool = True


@ExporterRegistry.register
class GodotExporter(BaseExporter):
    """Export sprites to Godot atlas JSON format.

    Creates JSON files compatible with Godot's TexturePacker import
    plugin using the textures[].sprites[] structure.

    Usage:
        from exporters import GodotExporter, ExportOptions

        exporter = GodotExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".tpsheet"
    FORMAT_NAME = "godot"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Godot exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["godot"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> GodotExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            GodotExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("godot")

        if isinstance(opts, GodotExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return GodotExportOptions(**opts)
            except TypeError:
                return GodotExportOptions()
        else:
            return GodotExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Godot atlas JSON metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark info.

        Returns:
            JSON string with textures array containing sprites.

        Raises:
            FormatError: When `packed_sprites` contains a rotated
                sprite. The Godot tpsheet schema has no rotation
                field and silently swapping `w`/`h` would produce
                metadata that no longer matches the atlas image.
        """
        self._reject_rotated_sprites(packed_sprites)
        opts = self._format_options

        # Build sprites list
        sprites: List[Dict[str, Any]] = []
        for packed in packed_sprites:
            sprites.append(self._build_sprite_entry(packed))

        # Build texture entry
        texture: Dict[str, Any] = {
            "image": image_name,
            "sprites": sprites,
        }

        if opts.include_size:
            texture["size"] = {"w": atlas_width, "h": atlas_height}

        # Build output
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

    def _build_sprite_entry(self, packed: PackedSprite) -> Dict[str, Any]:
        """Build a sprite entry for the sprites array.

        Args:
            packed: Packed sprite with atlas position.

        Returns:
            Sprite data dict with filename and region.

        Note:
            The Godot tpsheet format has no rotation field. Rotated
            sprites are rejected upstream by
            `_reject_rotated_sprites`, so this method always emits
            the natural (unrotated) `w`/`h`.
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]

        return {
            "filename": packed.name,
            "region": {
                "x": packed.atlas_x,
                "y": packed.atlas_y,
                "w": width,
                "h": height,
            },
        }


__all__ = ["GodotExporter", "GodotExportOptions"]
