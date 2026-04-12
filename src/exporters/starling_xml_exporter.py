#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Starling and Sparrow XML texture atlas formats.

Generates XML metadata compatible with:
    - Starling (Flash/AIR Stage3D framework)
    - Sparrow (iOS/Objective-C framework)
    - HaxeFlixel (with flipX/flipY extension)

Output Format:
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <TextureAtlas imagePath="atlas.png">
        <SubTexture name="sprite_01" x="0" y="0" width="64" height="64"
                    frameX="0" frameY="0" frameWidth="64" frameHeight="64"/>
        ...
    </TextureAtlas>
    ```

Sparrow Compatibility Mode:
    When enabled, omits Starling-specific attributes (rotated, pivotX, pivotY)
    and optionally includes the legacy ``format`` attribute on TextureAtlas.

FlipX/FlipY Extension:
    When enabled, includes ``flipX`` and ``flipY`` attributes on SubTextures
    for engines like HaxeFlixel that support sprite mirroring metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from xml.dom import minidom
import xml.etree.ElementTree as ET

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import (
    ExportOptions,
    GeneratorMetadata,
    PackedSprite,
)


@dataclass
class StarlingExportOptions:
    """Starling/Sparrow-specific export options.

    Attributes:
        sparrow_compatible: If True, omit Starling-specific attributes
            (rotated, pivotX, pivotY) for maximum Sparrow compatibility.
        include_flip_attributes: If True, include flipX/flipY attributes
            on SubTextures (non-standard, used by HaxeFlixel).
        include_frame_data: If True, include frameX/Y/Width/Height attributes
            even when they match the sprite bounds (no trimming).
        include_pivot: If True, include pivotX/pivotY if present in sprite data.
            Ignored when sparrow_compatible is True.
        legacy_format_attribute: If set, include format="value" on TextureAtlas.
            Only relevant for Sparrow v1 compatibility (e.g., "RGBA8888").
        scale: Atlas scale factor for high-DPI (e.g., 2.0 for @2x).
            Ignored when sparrow_compatible is True.
        flip_data: Optional dict mapping sprite names to flip state.
            Format: {"sprite_name": {"flipX": True, "flipY": False}, ...}
    """

    sparrow_compatible: bool = False
    include_flip_attributes: bool = False
    include_frame_data: bool = True
    include_pivot: bool = True
    legacy_format_attribute: Optional[str] = None
    scale: Optional[float] = None
    flip_data: Dict[str, Dict[str, bool]] = field(default_factory=dict)


@ExporterRegistry.register
class StarlingXmlExporter(BaseExporter):
    """Export sprites to Starling/Sparrow XML texture atlas format.

    Supports both standard Starling output and Sparrow-compatible mode.
    Can optionally include flipX/flipY attributes for HaxeFlixel compatibility.

    Usage:
        from exporters import StarlingXmlExporter, ExportOptions
        from exporters.starling_xml_exporter import StarlingExportOptions

        # Standard Starling export
        exporter = StarlingXmlExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")

        # Sparrow-compatible export
        options = ExportOptions(
            custom_properties={"starling": StarlingExportOptions(
                sparrow_compatible=True,
                legacy_format_attribute="RGBA8888",
            )}
        )
        exporter = StarlingXmlExporter(options)
        result = exporter.export_file(sprites, images, "/path/to/atlas")

        # With flip attributes
        flip_data = {"walk_01": {"flipX": True, "flipY": False}}
        options = ExportOptions(
            custom_properties={"starling": StarlingExportOptions(
                include_flip_attributes=True,
                flip_data=flip_data,
            )}
        )
    """

    FILE_EXTENSION = ".xml"
    FORMAT_NAME = "starling-xml"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Starling XML exporter.

        Args:
            options: Export options. Starling-specific options should be
                     provided in options.custom_properties["starling"].
        """
        super().__init__(options)
        self._starling_options = self._get_starling_options()

    def _get_starling_options(self) -> StarlingExportOptions:
        """Extract Starling-specific options from custom_properties.

        Returns:
            StarlingExportOptions instance with format-specific settings.
        """
        custom = self.options.custom_properties
        starling_opts = custom.get("starling")

        if isinstance(starling_opts, StarlingExportOptions):
            return starling_opts
        elif isinstance(starling_opts, dict):
            return StarlingExportOptions(**starling_opts)
        else:
            return StarlingExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Starling/Sparrow XML metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark comments.

        Returns:
            XML string with TextureAtlas and SubTexture elements.
        """
        self._generator_metadata = generator_metadata
        opts = self._starling_options

        # Create root element
        root = ET.Element("TextureAtlas")
        root.set("imagePath", image_name)

        # Add Sparrow legacy format attribute if specified
        if opts.legacy_format_attribute:
            root.set("format", opts.legacy_format_attribute)

        # Add Starling scale attribute (not in Sparrow-compatible mode)
        if opts.scale is not None and not opts.sparrow_compatible:
            root.set("scale", str(opts.scale))

        # Add SubTexture elements for each sprite
        for packed in packed_sprites:
            self._add_subtexture(root, packed, opts)

        # Format and return XML string
        return self._format_xml(root)

    def _add_subtexture(
        self,
        root: ET.Element,
        packed: PackedSprite,
        opts: StarlingExportOptions,
    ) -> None:
        """Add a SubTexture element for a packed sprite.

        Args:
            root: Parent TextureAtlas element.
            packed: Packed sprite with atlas position.
            opts: Starling-specific export options.
        """
        sprite = packed.sprite
        sub = ET.SubElement(root, "SubTexture")

        # Check if sprite is rotated
        is_rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap width/height when rotated (standard TexturePacker convention)
        # When a sprite is rotated 90° in the atlas, the atlas region has swapped dimensions
        sprite_w = sprite["width"]
        sprite_h = sprite["height"]
        atlas_w, atlas_h = (sprite_h, sprite_w) if is_rotated else (sprite_w, sprite_h)

        # Required attributes
        sub.set("name", sprite["name"])
        sub.set("x", str(packed.atlas_x))
        sub.set("y", str(packed.atlas_y))
        sub.set("width", str(atlas_w))
        sub.set("height", str(atlas_h))

        # Frame data (trimming offset and original size)
        if opts.include_frame_data:
            frame_x = sprite.get("frameX", 0)
            frame_y = sprite.get("frameY", 0)
            frame_w = sprite.get("frameWidth", sprite["width"])
            frame_h = sprite.get("frameHeight", sprite["height"])

            # Only include if there's actual trimming or always include is set
            has_trimming = (
                frame_x != 0
                or frame_y != 0
                or frame_w != sprite["width"]
                or frame_h != sprite["height"]
            )

            if has_trimming:
                sub.set("frameX", str(frame_x))
                sub.set("frameY", str(frame_y))
                sub.set("frameWidth", str(frame_w))
                sub.set("frameHeight", str(frame_h))

        # Rotation (Starling-only, skip in Sparrow mode)
        if not opts.sparrow_compatible:
            if packed.rotated or sprite.get("rotated", False):
                sub.set("rotated", "true")

        # Pivot points (Starling 2.x only, skip in Sparrow mode)
        if opts.include_pivot and not opts.sparrow_compatible:
            if "pivotX" in sprite:
                sub.set("pivotX", str(sprite["pivotX"]))
            if "pivotY" in sprite:
                sub.set("pivotY", str(sprite["pivotY"]))

        # Flip attributes (non-standard extension)
        if opts.include_flip_attributes:
            flip_info = opts.flip_data.get(sprite["name"], {})
            sprite_flip_x = flip_info.get("flipX", sprite.get("flipX", False))
            sprite_flip_y = flip_info.get("flipY", sprite.get("flipY", False))

            if sprite_flip_x:
                sub.set("flipX", "true")
            if sprite_flip_y:
                sub.set("flipY", "true")

    def _format_xml(self, root: ET.Element) -> str:
        """Format XML with proper declaration and indentation.

        Args:
            root: Root XML element to format.

        Returns:
            Pretty-printed XML string with declaration.
        """
        # Convert to string
        rough_string = ET.tostring(root, encoding="unicode")

        # Build generator metadata comment
        comment_block = ""
        if hasattr(self, "_generator_metadata") and self._generator_metadata:
            comment_lines = self._generator_metadata.format_comment_lines()
            if comment_lines:
                comment_block = "<!--\n    " + "\n    ".join(comment_lines) + "\n-->\n"

        # Parse with minidom for pretty printing
        if self.options.pretty_print:
            dom = minidom.parseString(rough_string)
            try:
                # Get pretty XML, skip the minidom XML declaration (we add our own)
                pretty = dom.toprettyxml(indent="    ", encoding=None)
                # Remove minidom's declaration and clean up
                lines = pretty.split("\n")
                # Skip empty first line if present
                if lines and lines[0].startswith("<?xml"):
                    lines = lines[1:]
                # Remove extra blank lines
                content = "\n".join(line for line in lines if line.strip())
            finally:
                dom.unlink()
            # Add our own declaration and comment
            return '<?xml version="1.0" encoding="UTF-8"?>\n' + comment_block + content
        else:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                + comment_block
                + rough_string
            )


__all__ = ["StarlingXmlExporter", "StarlingExportOptions"]
