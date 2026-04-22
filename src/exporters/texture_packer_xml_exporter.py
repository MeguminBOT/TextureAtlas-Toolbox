#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for TexturePacker XML format (sprite elements).

Generates XML metadata using <sprite> elements with shorthand attributes.
This is the TexturePacker generic XML format (distinct from Starling XML).

Output Format:
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <TextureAtlas imagePath="atlas.png" width="512" height="512">
        <sprite n="sprite_01" x="0" y="0" w="64" h="64"/>
        <sprite n="sprite_02" x="66" y="0" w="48" h="48" r="y"/>
    </TextureAtlas>
    ```

Attributes:
    n: Sprite name
    x, y: Position in atlas
    w, h: Sprite dimensions
    oX, oY: Original offset (trim offset)
    oW, oH: Original width/height (before trim)
    r: Rotated ("y" if true)
    pX, pY: Pivot point (0.0-1.0)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
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
class TexturePackerXmlExportOptions:
    """TexturePacker XML-specific export options.

    Attributes:
        include_pivot: Include pX/pY pivot attributes when the sprite
            carries a non-default pivot.
        include_atlas_size: Include ``width`` / ``height`` on the
            ``<TextureAtlas>`` element.
        use_short_rotation: Use ``"y"`` / ``"n"`` for rotation instead
            of ``"true"`` / ``"false"``. The TexturePacker generic XML
            template uses the short form.
        name_attribute: Which attribute carries the sprite name.
            ``"n"`` matches TexturePacker's own template (default);
            ``"name"`` matches the long form used by some homebrew
            tools. Unknown values fall back to ``"n"``.
        include_xml_declaration: Emit the leading
            ``<?xml version="1.0" encoding="UTF-8"?>`` declaration.
            Some downstream consumers concatenate fragments and require
            it absent.
    """

    include_pivot: bool = True
    include_atlas_size: bool = True
    use_short_rotation: bool = True
    name_attribute: str = "n"
    include_xml_declaration: bool = True


_VALID_NAME_ATTRIBUTES = frozenset({"n", "name"})


@ExporterRegistry.register
class TexturePackerXmlExporter(BaseExporter):
    """Export sprites to TexturePacker generic XML format.

    This format uses <sprite> elements with shorthand attribute names
    (n, x, y, w, h, r, oX, oY, oW, oH, pX, pY).

    Usage:
        from exporters import TexturePackerXmlExporter, ExportOptions

        exporter = TexturePackerXmlExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".xml"
    FORMAT_NAME = "texturepacker-xml"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the TexturePacker XML exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["texturepacker_xml"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> TexturePackerXmlExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            TexturePackerXmlExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("texturepacker_xml")

        if isinstance(opts, TexturePackerXmlExportOptions):
            resolved = opts
        elif isinstance(opts, dict):
            try:
                resolved = TexturePackerXmlExportOptions(**opts)
            except TypeError:
                resolved = TexturePackerXmlExportOptions()
        else:
            resolved = TexturePackerXmlExportOptions()

        if resolved.name_attribute not in _VALID_NAME_ATTRIBUTES:
            resolved.name_attribute = "n"
        return resolved

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate TexturePacker XML metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark comments.

        Returns:
            XML string with TextureAtlas and sprite elements.
        """
        self._generator_metadata = generator_metadata
        opts = self._format_options

        # Create root element
        root = ET.Element("TextureAtlas")
        root.set("imagePath", image_name)

        if opts.include_atlas_size:
            root.set("width", str(atlas_width))
            root.set("height", str(atlas_height))

        # Add sprite elements
        for packed in packed_sprites:
            self._add_sprite(root, packed, opts)

        # Format and return XML
        return self._format_xml(root)

    def _add_sprite(
        self,
        root: ET.Element,
        packed: PackedSprite,
        opts: TexturePackerXmlExportOptions,
    ) -> None:
        """Add a sprite element for a packed sprite.

        Args:
            root: Parent TextureAtlas element.
            packed: Packed sprite with atlas position.
            opts: Format-specific options.
        """
        sprite = packed.sprite
        elem = ET.SubElement(root, "sprite")

        # Check if rotated
        rotated = packed.rotated or sprite.get("rotated", False)

        # Atlas dimensions: swap width/height when rotated (standard TexturePacker convention)
        sprite_w = sprite["width"]
        sprite_h = sprite["height"]
        atlas_w, atlas_h = (sprite_h, sprite_w) if rotated else (sprite_w, sprite_h)

        # Required attributes (shorthand names)
        elem.set(opts.name_attribute, sprite["name"])
        elem.set("x", str(packed.atlas_x))
        elem.set("y", str(packed.atlas_y))
        elem.set("w", str(atlas_w))
        elem.set("h", str(atlas_h))

        # Rotation
        if rotated:
            if opts.use_short_rotation:
                elem.set("r", "y")
            else:
                elem.set("r", "true")

        # Trim/offset data
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", sprite_w)
        frame_h = sprite.get("frameHeight", sprite_h)

        has_offset = frame_x != 0 or frame_y != 0
        has_orig_size = frame_w != sprite_w or frame_h != sprite_h

        if has_offset:
            elem.set("oX", str(-frame_x))
            elem.set("oY", str(-frame_y))

        if has_orig_size:
            elem.set("oW", str(frame_w))
            elem.set("oH", str(frame_h))

        # Pivot
        if opts.include_pivot:
            pivot_x = sprite.get("pivotX", 0.5)
            pivot_y = sprite.get("pivotY", 0.5)
            # Only include if not default center
            if pivot_x != 0.5 or pivot_y != 0.5:
                elem.set("pX", str(pivot_x))
                elem.set("pY", str(pivot_y))

    def _format_xml(self, root: ET.Element) -> str:
        """Format XML with proper declaration and indentation.

        Args:
            root: Root XML element to format.

        Returns:
            Pretty-printed XML string. The leading
            ``<?xml ... ?>`` declaration is included unless
            :py:attr:`TexturePackerXmlExportOptions.include_xml_declaration`
            is ``False``.
        """
        opts = self._format_options
        rough_string = ET.tostring(root, encoding="unicode")

        # Build generator metadata comment
        comment_block = ""
        if hasattr(self, "_generator_metadata") and self._generator_metadata:
            comment_lines = self._generator_metadata.format_comment_lines()
            if comment_lines:
                comment_block = "<!--\n    " + "\n    ".join(comment_lines) + "\n-->\n"

        declaration = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            if opts.include_xml_declaration
            else ""
        )

        if self.options.pretty_print:
            dom = minidom.parseString(rough_string)
            try:
                pretty = dom.toprettyxml(indent="    ", encoding=None)
                lines = pretty.split("\n")
                if lines and lines[0].startswith("<?xml"):
                    lines = lines[1:]
                content = "\n".join(line for line in lines if line.strip())
            finally:
                dom.unlink()
            return declaration + comment_block + content
        else:
            return declaration + comment_block + rough_string


__all__ = ["TexturePackerXmlExporter", "TexturePackerXmlExportOptions"]
