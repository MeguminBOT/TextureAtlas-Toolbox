#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Aseprite-compatible JSON metadata.

This exporter emits the same JSON structure that Aseprite's
"Sprite Sheet" export produces, allowing users to round-trip
atlases between TextureAtlas Toolbox and Aseprite.

Format reference:
    https://www.aseprite.org/docs/spritesheet/
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import ExportOptions, GeneratorMetadata, PackedSprite
from utils.version import APP_VERSION


@dataclass
class AsepriteExportOptions:
    """Options specific to the Aseprite JSON exporter."""

    format_string: str = "RGBA8888"
    scale_string: str = "1"
    default_duration: int = 0  # milliseconds


@ExporterRegistry.register
class AsepriteExporter(BaseExporter):
    """Export packed sprites to the Aseprite JSON schema."""

    FILE_EXTENSION = ".json"
    FORMAT_NAME = "aseprite"
    DISPLAY_NAME = "Aseprite JSON"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> AsepriteExportOptions:
        """Extract format-specific options from ExportOptions."""

        custom = self.options.custom_properties
        opts = custom.get("aseprite")
        if isinstance(opts, AsepriteExportOptions):
            return opts
        if isinstance(opts, dict):
            try:
                return AsepriteExportOptions(**opts)
            except TypeError:
                return AsepriteExportOptions()
        return AsepriteExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate an Aseprite JSON document."""

        frames = {
            packed.name: self._build_frame_entry(packed) for packed in packed_sprites
        }

        meta = self._build_meta_block(
            packed_sprites, atlas_width, atlas_height, image_name, generator_metadata
        )

        data = {"frames": frames, "meta": meta}
        indent = 4 if self.options.pretty_print else None
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def _build_frame_entry(self, packed: PackedSprite) -> Dict[str, Any]:
        """Create the frame dictionary for a single sprite."""

        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", width)
        frame_h = sprite.get("frameHeight", height)

        trimmed = frame_x != 0 or frame_y != 0 or frame_w != width or frame_h != height
        is_rotated = packed.rotated or sprite.get("rotated", False)

        atlas_w, atlas_h = (height, width) if is_rotated else (width, height)

        return {
            "frame": {
                "x": packed.atlas_x,
                "y": packed.atlas_y,
                "w": atlas_w,
                "h": atlas_h,
            },
            "rotated": is_rotated,
            "trimmed": trimmed,
            "spriteSourceSize": {
                "x": frame_x,
                "y": frame_y,
                "w": width,
                "h": height,
            },
            "sourceSize": {
                "w": frame_w,
                "h": frame_h,
            },
            "duration": self._format_options.default_duration,
        }

    def _build_meta_block(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata],
    ) -> Dict[str, Any]:
        """Build the meta section of the JSON output."""

        opts = self._format_options
        meta: Dict[str, Any] = {
            "app": f"TextureAtlas Toolbox ({APP_VERSION})",
            "version": APP_VERSION,
            "image": image_name,
            "format": opts.format_string,
            "size": {"w": atlas_width, "h": atlas_height},
            "scale": opts.scale_string,
            "frameTags": self._build_frame_tags(packed_sprites),
            "layers": [],
            "slices": [],
        }

        if generator_metadata:
            tatt_meta: Dict[str, Any] = {}
            if generator_metadata.packer:
                tatt_meta["packer"] = generator_metadata.packer
            if generator_metadata.heuristic:
                tatt_meta["heuristic"] = generator_metadata.heuristic
            if generator_metadata.efficiency > 0:
                tatt_meta["efficiency"] = generator_metadata.efficiency
            if tatt_meta:
                meta["textureAtlasToolbox"] = tatt_meta

        return meta

    def _build_frame_tags(
        self, packed_sprites: List[PackedSprite]
    ) -> List[Dict[str, Any]]:
        """Build frameTags array from animation groups in packed sprites.

        Groups consecutive sprites by their animation name and produces
        Aseprite-compatible frame tag entries.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.

        Returns:
            List of frameTag dicts with name, from, to, direction fields.
        """
        tags: List[Dict[str, Any]] = []
        current_anim: Optional[str] = None
        current_direction: str = "forward"
        start_idx = 0

        for i, packed in enumerate(packed_sprites):
            anim = packed.sprite.get("animation", "")
            if anim != current_anim:
                if current_anim is not None and current_anim:
                    tags.append(
                        {
                            "name": current_anim,
                            "from": start_idx,
                            "to": i - 1,
                            "direction": current_direction,
                        }
                    )
                current_anim = anim
                current_direction = packed.sprite.get("direction", "forward")
                start_idx = i

        # Close the last group
        if current_anim is not None and current_anim and packed_sprites:
            tags.append(
                {
                    "name": current_anim,
                    "from": start_idx,
                    "to": len(packed_sprites) - 1,
                    "direction": current_direction,
                }
            )

        return tags


__all__ = ["AsepriteExporter", "AsepriteExportOptions"]
