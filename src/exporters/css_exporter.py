#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for CSS spritesheet format.

Generates CSS class definitions for each sprite with background-position
and dimension properties. Supports optional rotation via CSS transforms.

Output Format:
    ```css
    .sprite_01 {
        background: url('atlas.png') -0px -0px;
        width: 64px;
        height: 64px;
    }
    .sprite_02 {
        background: url('atlas.png') -66px -0px;
        width: 48px;
        height: 48px;
        transform: rotate(-90deg);
        margin-left: 2px;
        margin-top: 2px;
    }
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import (
    ExportOptions,
    GeneratorMetadata,
    PackedSprite,
)


@dataclass
class CssExportOptions:
    """CSS spritesheet-specific export options.

    Attributes:
        include_rotation: Include transform: rotate(-90deg) for rotated sprites.
        include_trim_margins: Include margin-left/margin-top for trimmed sprites.
        class_prefix: Prefix for CSS class names (e.g., "sprite-").
        use_background_shorthand: Use background shorthand vs background-position.
    """

    include_rotation: bool = True
    include_trim_margins: bool = True
    class_prefix: str = ""
    use_background_shorthand: bool = True


@ExporterRegistry.register
class CssExporter(BaseExporter):
    """Export sprites to CSS spritesheet format.

    Generates CSS class definitions that can be used to display sprites
    from the atlas image as background images.

    Usage:
        from exporters import CssExporter, ExportOptions

        exporter = CssExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".css"
    FORMAT_NAME = "css"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the CSS exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["css"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> CssExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            CssExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("css")

        if isinstance(opts, CssExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return CssExportOptions(**opts)
            except TypeError:
                return CssExportOptions()
        else:
            return CssExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate CSS spritesheet content.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels (unused in CSS).
            atlas_height: Final atlas height in pixels (unused in CSS).
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for watermark comments.

        Returns:
            CSS content with class definitions for each sprite.
        """
        opts = self._format_options
        rules: List[str] = []

        # Add generator metadata as CSS comment block
        if generator_metadata:
            comment_lines = generator_metadata.format_comment_lines()
            if comment_lines:
                rules.append("/*")
                for line in comment_lines:
                    rules.append(f" * {line}")
                rules.append(" */")
                rules.append("")

        for packed in packed_sprites:
            rules.append(self._build_css_rule(packed, image_name, opts))

        separator = "\n\n" if self.options.pretty_print else "\n"
        return separator.join(rules) + "\n"

    def _build_css_rule(
        self,
        packed: PackedSprite,
        image_name: str,
        opts: CssExportOptions,
    ) -> str:
        """Build a CSS rule for a single sprite.

        Args:
            packed: Packed sprite with atlas position.
            image_name: Atlas image filename.
            opts: Format-specific options.

        Returns:
            CSS rule string for this sprite.
        """
        sprite = packed.sprite
        rotated = packed.rotated or sprite.get("rotated", False)

        # For rotated sprites, width/height are swapped in display
        if rotated:
            display_w = sprite["height"]
            display_h = sprite["width"]
        else:
            display_w = sprite["width"]
            display_h = sprite["height"]

        # Build class name (sanitize for CSS)
        class_name = opts.class_prefix + self._sanitize_class_name(packed.name)

        # Build properties
        props: List[str] = []

        # Background
        bg_x = -packed.atlas_x
        bg_y = -packed.atlas_y
        if opts.use_background_shorthand:
            props.append(f"background: url('{image_name}') {bg_x}px {bg_y}px;")
        else:
            props.append(f"background-image: url('{image_name}');")
            props.append(f"background-position: {bg_x}px {bg_y}px;")

        # Dimensions
        props.append(f"width: {display_w}px;")
        props.append(f"height: {display_h}px;")

        # Rotation
        if rotated and opts.include_rotation:
            props.append("transform: rotate(-90deg);")

        # Trim margins
        if opts.include_trim_margins:
            frame_x = sprite.get("frameX", 0)
            frame_y = sprite.get("frameY", 0)
            if frame_x != 0:
                props.append(f"margin-left: {-frame_x}px;")
            if frame_y != 0:
                props.append(f"margin-top: {-frame_y}px;")

        # Format rule
        if self.options.pretty_print:
            props_str = "\n    ".join(props)
            return f".{class_name} {{\n    {props_str}\n}}"
        else:
            props_str = " ".join(props)
            return f".{class_name} {{ {props_str} }}"

    @staticmethod
    def _sanitize_class_name(name: str) -> str:
        """Sanitize a sprite name for use as a CSS class.

        Args:
            name: Original sprite name.

        Returns:
            Sanitized name safe for CSS class selectors.
        """
        # Replace invalid characters with hyphens
        result = []
        for char in name:
            if char.isalnum() or char in "-_":
                result.append(char)
            else:
                result.append("-")

        sanitized = "".join(result)

        # Ensure doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = "s" + sanitized

        return sanitized or "sprite"


__all__ = ["CssExporter", "CssExportOptions"]
