#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for TexturePacker Unity format.

Generates semicolon-delimited text files compatible with TexturePacker's
Unity export format.

Output Format:
    ```
    :format=40300
    :texture=atlas.png
    :size=512x512
    sprite_01;0;0;64;64;0.5;0.5
    sprite_02;66;0;48;48;0.5;0.5
    ```

Each sprite line contains: name;x;y;width;height;pivotX;pivotY
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
class UnityExportOptions:
    """Unity format-specific export options.

    Attributes:
        format_version: Format version number written to the `:format`
            header. Defaults to 40300, matching the version emitted by
            modern TexturePacker releases.
        include_pivot: Legacy boolean. When `pivot_mode` is None this
            controls emission directly: True writes the trailing
            pivotX/pivotY columns (seven columns total), False writes
            five columns. Retained for backwards compatibility with
            existing callers.
        pivot_mode: Optional explicit override for the column count.
            `"always"` writes seven columns for every sprite, `"never"`
            writes five columns, and `"auto"` inspects the input and
            emits seven columns only when at least one sprite carries
            an explicit pivot. Use `"auto"` to round-trip a tpsheet
            faithfully when the source file did not declare pivots.
            When None (default), the exporter falls back to
            `include_pivot` for backwards compatibility.
    """

    format_version: int = 40300
    include_pivot: bool = True
    pivot_mode: Optional[str] = None


@ExporterRegistry.register
class UnityExporter(BaseExporter):
    """Export sprites to TexturePacker Unity text format.

    Creates semicolon-delimited text files with header lines and
    sprite definitions.

    Usage:
        from exporters import UnityExporter, ExportOptions

        exporter = UnityExporter()
        result = exporter.export_file(sprites, images, "/path/to/atlas")
    """

    FILE_EXTENSION = ".tpsheet"
    FORMAT_NAME = "unity"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Unity exporter.

        Args:
            options: Export options. Format-specific options should be
                     provided in options.custom_properties["unity"].
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> UnityExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            UnityExportOptions instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("unity")

        if isinstance(opts, UnityExportOptions):
            return opts
        elif isinstance(opts, dict):
            try:
                return UnityExportOptions(**opts)
            except TypeError:
                return UnityExportOptions()
        else:
            return UnityExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Unity text metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image.
            generator_metadata: Optional metadata for header comments.

        Returns:
            Text content with header and sprite definitions.
        """
        opts = self._format_options
        lines: List[str] = []

        # Decide once whether this file emits pivot columns. TexturePacker
        # tpsheet files use one consistent column count for the whole
        # file, so the decision is made up-front rather than per row.
        emit_pivot = self._resolve_emit_pivot(opts, packed_sprites)

        # Add generator metadata as comments (lines starting with #)
        if generator_metadata:
            comment_lines = generator_metadata.format_comment_lines()
            for line in comment_lines:
                lines.append(f"# {line}")
            if comment_lines:
                lines.append("")

        # Header lines
        lines.append(f":format={opts.format_version}")
        lines.append(f":texture={image_name}")
        lines.append(f":size={atlas_width}x{atlas_height}")

        # Sprite lines
        for packed in packed_sprites:
            lines.append(self._build_sprite_line(packed, emit_pivot))

        return "\n".join(lines) + "\n"

    @staticmethod
    def _resolve_emit_pivot(
        opts: UnityExportOptions,
        packed_sprites: List[PackedSprite],
    ) -> bool:
        """Resolve whether the output should include pivot columns.

        Args:
            opts: Format-specific export options.
            packed_sprites: Sprites whose source dicts may carry pivots.

        Returns:
            True when every emitted row should include pivot columns.
        """
        if opts.pivot_mode is None:
            # Backwards compatible default: the legacy boolean wins.
            return bool(opts.include_pivot)
        mode = opts.pivot_mode.lower()
        if mode == "always":
            return True
        if mode == "never":
            return False
        if mode == "auto":
            for packed in packed_sprites:
                sprite = packed.sprite
                if "pivotX" in sprite or "pivotY" in sprite:
                    return True
            return False
        # Unknown mode -> fall back to legacy include_pivot toggle.
        return bool(opts.include_pivot)

    def _build_sprite_line(
        self,
        packed: PackedSprite,
        emit_pivot: bool,
    ) -> str:
        """Build a sprite definition line.

        Args:
            packed: Packed sprite with atlas position.
            emit_pivot: Whether to append pivotX/pivotY columns.

        Returns:
            Semicolon-delimited sprite line.

        Note:
            The Unity format doesn't have a rotation field, so if sprites
            are rotated in the atlas, the dimensions reflect the actual
            atlas space occupied (swapped width/height).
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]

        # Check if rotated - swap dimensions since Unity format has no rotation field
        is_rotated = packed.rotated or sprite.get("rotated", False)
        atlas_w, atlas_h = (height, width) if is_rotated else (width, height)

        parts = [
            sprite["name"],
            str(packed.atlas_x),
            str(packed.atlas_y),
            str(atlas_w),
            str(atlas_h),
        ]

        if emit_pivot:
            pivot_x = sprite.get("pivotX", 0.5)
            pivot_y = sprite.get("pivotY", 0.5)
            parts.append(str(pivot_x))
            parts.append(str(pivot_y))

        return ";".join(parts)


__all__ = ["UnityExporter", "UnityExportOptions"]
