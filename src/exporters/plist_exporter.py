#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Apple plist (property list) atlas format.

Generates binary or XML plist files compatible with iOS/macOS sprite
frameworks and TexturePacker's Cocos2d export.

Output Format (conceptual, actual output is binary plist):
    ```xml
    <plist>
        <dict>
            <key>frames</key>
            <dict>
                <key>sprite_01</key>
                <dict>
                    <key>frame</key>
                    <string>{{0,0},{64,64}}</string>
                    <key>sourceColorRect</key>
                    <string>{{0,0},{64,64}}</string>
                    <key>sourceSize</key>
                    <string>{64,64}</string>
                    <key>rotated</key>
                    <false/>
                </dict>
            </dict>
            <key>metadata</key>
            <dict>
                <key>textureFileName</key>
                <string>atlas.png</string>
                <key>size</key>
                <string>{512,512}</string>
            </dict>
        </dict>
    </plist>
    ```
"""

from __future__ import annotations

import plistlib
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
class PlistExportOptions:
    """Plist format-specific export options.

    Attributes:
        use_binary: Output binary plist (True) or XML plist (False).
        format_version: Plist format version (2 or 3).
        include_metadata: Include metadata dict with texture info.
    """

    use_binary: bool = True
    format_version: int = 2
    include_metadata: bool = True


@ExporterRegistry.register
class PlistExporter(BaseExporter):
    """Export sprites to Apple plist atlas format.

    Creates plist files compatible with iOS/macOS sprite frameworks
    like SpriteKit and Cocos2d.

    Usage:
        from exporters import PlistExporter, ExportOptions

        exporter = PlistExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".plist"
    FORMAT_NAME = "plist"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the plist exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["plist"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> PlistExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            PlistExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("plist")

        if isinstance(opts, PlistExportOptions):
            return opts
        elif isinstance(opts, dict):
            return PlistExportOptions(**opts)
        else:
            return PlistExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> bytes:
        """Generate plist atlas content.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for plist metadata dict.

        Returns:
            Plist content as bytes (binary or XML format).
        """
        opts = self._format_options

        # Build frames dict
        # Cocos2d plist convention: frame keys include .png extension
        frames: Dict[str, Dict[str, Any]] = {}
        for packed in packed_sprites:
            frame_key = packed.name
            if not frame_key.lower().endswith(
                (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tga")
            ):
                frame_key = f"{frame_key}.png"
            frames[frame_key] = self._build_frame_entry(packed)

        # Build root dict
        root: Dict[str, Any] = {"frames": frames}

        # Add metadata
        if opts.include_metadata:
            metadata_dict: Dict[str, Any] = {
                "format": opts.format_version,
                "textureFileName": image_name,
                "size": f"{{{atlas_width},{atlas_height}}}",
                "realTextureFileName": image_name,
            }
            # Add generator metadata if provided
            if generator_metadata:
                if generator_metadata.app_version:
                    metadata_dict["generator"] = (
                        f"TextureAtlas Toolbox ({generator_metadata.app_version})"
                    )
                if generator_metadata.packer:
                    metadata_dict["packer"] = generator_metadata.packer
                if generator_metadata.heuristic:
                    metadata_dict["heuristic"] = generator_metadata.heuristic
                if generator_metadata.efficiency > 0:
                    metadata_dict["efficiency"] = (
                        f"{generator_metadata.efficiency:.1f}%"
                    )
            root["metadata"] = metadata_dict

        # Serialize
        if opts.use_binary:
            return plistlib.dumps(root, fmt=plistlib.FMT_BINARY)
        else:
            return plistlib.dumps(root, fmt=plistlib.FMT_XML)

    def _build_frame_entry(self, packed: PackedSprite) -> Dict[str, Any]:
        """Build a frame entry for the frames dict.

        Args:
            packed: Packed sprite with atlas position.

        Returns:
            Frame data dict in plist format.
        """
        sprite = packed.sprite
        x = packed.atlas_x
        y = packed.atlas_y
        w = sprite["width"]
        h = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", w)
        frame_h = sprite.get("frameHeight", h)
        rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap width/height when rotated (standard TexturePacker convention)
        atlas_w, atlas_h = (h, w) if rotated else (w, h)

        # Use TexturePacker plist format (string rects)
        return {
            "frame": f"{{{{{x},{y}}},{{{atlas_w},{atlas_h}}}}}",
            "offset": f"{{{-frame_x},{-frame_y}}}",
            "rotated": rotated,
            "sourceColorRect": f"{{{{{-frame_x},{-frame_y}}},{{{w},{h}}}}}",
            "sourceSize": f"{{{frame_w},{frame_h}}}",
        }


__all__ = ["PlistExporter", "PlistExportOptions"]
