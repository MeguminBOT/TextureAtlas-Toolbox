#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for UIKit-style plist atlas format.

Generates plist files using scalar keys (x, y, w, h, oX, oY, oW, oH)
rather than the string-based rect format. Used by some iOS tools.

Output Format (conceptual):
    ```xml
    <plist>
        <dict>
            <key>frames</key>
            <dict>
                <key>sprite_01</key>
                <dict>
                    <key>x</key><integer>0</integer>
                    <key>y</key><integer>0</integer>
                    <key>w</key><integer>64</integer>
                    <key>h</key><integer>64</integer>
                    <key>oX</key><integer>0</integer>
                    <key>oY</key><integer>0</integer>
                    <key>oW</key><integer>64</integer>
                    <key>oH</key><integer>64</integer>
                </dict>
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
class UIKitPlistExportOptions:
    """UIKit plist format-specific export options.

    Attributes:
        use_binary: Output binary plist (True) or XML plist (False).
        include_metadata: Include metadata dict with texture info.
    """

    use_binary: bool = True
    include_metadata: bool = True


@ExporterRegistry.register
class UIKitPlistExporter(BaseExporter):
    """Export sprites to UIKit-style plist atlas format.

    Uses scalar integer keys (x, y, w, h, oX, oY, oW, oH) for frame
    data rather than string-based rect encoding.

    Usage:
        from exporters import UIKitPlistExporter, ExportOptions

        exporter = UIKitPlistExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".plist"
    FORMAT_NAME = "uikit-plist"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the UIKit plist exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["uikit_plist"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> UIKitPlistExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            UIKitPlistExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("uikit_plist")

        if isinstance(opts, UIKitPlistExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return UIKitPlistExportOptions(**opts)
            except TypeError:
                return UIKitPlistExportOptions()
        else:
            return UIKitPlistExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> bytes:
        """Generate UIKit plist atlas content.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for plist metadata dict.

        Returns:
            Plist content as bytes.

        Raises:
            FormatError: When `packed_sprites` contains a rotated
                sprite. The UIKit plist schema has no rotation field
                and silently swapping `w`/`h` would produce metadata
                that no longer matches the atlas image.
        """
        self._reject_rotated_sprites(packed_sprites)
        opts = self._format_options

        # Build frames dict
        frames: Dict[str, Dict[str, Any]] = {}
        for packed in packed_sprites:
            frames[packed.name] = self._build_frame_entry(packed)

        # Build root dict
        root: Dict[str, Any] = {"frames": frames}

        # Add metadata
        if opts.include_metadata:
            metadata_dict: Dict[str, Any] = {
                "textureFileName": image_name,
                "width": atlas_width,
                "height": atlas_height,
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

    def _build_frame_entry(self, packed: PackedSprite) -> Dict[str, int]:
        """Build a frame entry for the frames dict.

        Args:
            packed: Packed sprite with atlas position.

        Returns:
            Frame data dict with scalar integer keys.

        Note:
            The UIKit plist format has no rotation field. Rotated
            sprites are rejected upstream by
            `_reject_rotated_sprites`, so this method always emits
            the natural (unrotated) `w`/`h`.
        """
        sprite = packed.sprite
        w = sprite["width"]
        h = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", w)
        frame_h = sprite.get("frameHeight", h)

        return {
            "x": packed.atlas_x,
            "y": packed.atlas_y,
            "w": w,
            "h": h,
            "oX": -frame_x,
            "oY": -frame_y,
            "oW": frame_w,
            "oH": frame_h,
        }


__all__ = ["UIKitPlistExporter", "UIKitPlistExportOptions"]
