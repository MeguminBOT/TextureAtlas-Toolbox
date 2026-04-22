#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for CSS spritesheet format.

Generates CSS class definitions for each sprite with `background-position`
and dimension properties. Supports three trim-handling strategies and
three rotation-handling strategies.

Background:
    Earlier versions of this exporter emitted ``margin-left`` /
    ``margin-top`` to encode trim, and pre-swapped ``width`` / ``height``
    when emitting ``transform: rotate(-90deg)``. Both were sources of
    real-world bugs:

    * CSS margins push the *box* around in flow layout. They do **not**
      shift the background image within the box, so the visible sprite
      ended up at the wrong on-screen position relative to the layout
      slot.
    * The rotation transform was emitted without an explicit
      ``transform-origin``, so it pivoted around the box centre. With
      ``width`` / ``height`` pre-swapped to displayed dimensions the
      result depended on the consumer's CSS environment and could
      double-rotate the sprite.

    The new defaults match SpriteSmith / sprity / Glue conventions
    (background-position carries the trim offset, container is sized to
    the original frame) and use ``transform-origin: 0 0`` plus a
    compensating ``translateY`` so a rotated sprite occupies its
    layout slot at the displayed (post-rotation) size. The legacy
    behaviours are still reachable through ``trim_mode="margin"`` and
    ``rotation_mode="legacy-center"``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

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
        trim_mode: How to encode trim offsets. One of:

            * ``"background-position"`` (default, spec-correct):
              container sized to ``frameWidth`` / ``frameHeight`` and
              ``background-position`` is shifted by the trim offset so
              the trimmed atlas region appears at the correct location
              inside the box. Matches SpriteSmith / sprity / Glue.
            * ``"margin"`` (legacy): emit ``margin-left`` /
              ``margin-top`` equal to ``-frameX`` / ``-frameY``. Box at
              the trimmed atlas region. Retained for compatibility with
              consumers that read this exporter's pre-3.0.0 output.
            * ``"none"``: ignore trim entirely. Box at the trimmed
              atlas region; ``background-position`` points directly at
              the atlas position. Use when the consumer does not need
              original-frame footprint.
        rotation_mode: How to encode 90 degree rotation. One of:

            * ``"transform"`` (default, layout-correct): emit
              ``transform-origin: 0 0`` plus a compensating
              ``translateY(<atlas_w>px)`` so the rotated content stays
              in its layout slot at the displayed (post-rotation) size.
              Container sized to the atlas region (rotated) dimensions.
            * ``"legacy-center"``: emit a bare ``transform:
              rotate(-90deg)`` with width / height pre-swapped to the
              displayed size. Pivots around the box centre. Retained
              for compatibility with this exporter's pre-3.0.0 output.
            * ``"none"``: do not emit a transform. The atlas region is
              shown as-is (still rotated 90 degrees clockwise as packed
              by TexturePacker convention). Use when the consumer
              handles rotation in JavaScript or shaders.
        class_prefix: Prefix for CSS class names (e.g. ``"sprite-"``).
        use_background_shorthand: ``True`` to combine ``background-image``
            and ``background-position`` into the ``background:``
            shorthand. ``False`` emits the long form.
        emit_round_trip_comment: ``True`` to emit a small
            ``/* tat: ... */`` comment alongside each rule that records
            the raw atlas position, atlas-region size, trim offsets,
            and rotation flag. The legacy CSS parser reads these
            markers to perform a lossless round-trip when
            ``trim_mode != "margin"`` or
            ``rotation_mode != "legacy-center"``. Cosmetic only;
            consumers that ignore CSS comments are unaffected.
    """

    trim_mode: str = "background-position"
    rotation_mode: str = "transform"
    class_prefix: str = ""
    use_background_shorthand: bool = True
    emit_round_trip_comment: bool = True


_VALID_TRIM_MODES = frozenset({"background-position", "margin", "none"})
_VALID_ROTATION_MODES = frozenset({"transform", "legacy-center", "none"})


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
                provided in ``options.custom_properties["css"]`` either
                as a `CssExportOptions` instance or a dict.
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> CssExportOptions:
        """Extract format-specific options from custom_properties.

        Returns:
            `CssExportOptions` instance, with unknown ``trim_mode`` /
            ``rotation_mode`` values silently coerced to the default.
        """
        custom = self.options.custom_properties
        opts = custom.get("css")

        if isinstance(opts, CssExportOptions):
            resolved = opts
        elif isinstance(opts, dict):
            try:
                resolved = CssExportOptions(**opts)
            except TypeError:
                resolved = CssExportOptions()
        else:
            resolved = CssExportOptions()

        if resolved.trim_mode not in _VALID_TRIM_MODES:
            resolved.trim_mode = "background-position"
        if resolved.rotation_mode not in _VALID_ROTATION_MODES:
            resolved.rotation_mode = "transform"
        return resolved

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
        rotated = bool(packed.rotated or sprite.get("rotated", False))
        atlas_w = int(sprite["width"])
        atlas_h = int(sprite["height"])
        frame_x = int(sprite.get("frameX", 0) or 0)
        frame_y = int(sprite.get("frameY", 0) or 0)
        frame_w_raw = sprite.get("frameWidth")
        frame_h_raw = sprite.get("frameHeight")
        frame_w = int(frame_w_raw) if frame_w_raw is not None else atlas_w
        frame_h = int(frame_h_raw) if frame_h_raw is not None else atlas_h

        class_name = opts.class_prefix + self._sanitize_class_name(packed.name)

        bg_x, bg_y, box_w, box_h = self._resolve_layout(
            packed.atlas_x,
            packed.atlas_y,
            atlas_w,
            atlas_h,
            frame_x,
            frame_y,
            frame_w,
            frame_h,
            rotated,
            opts,
        )

        props: List[str] = []
        if opts.use_background_shorthand:
            props.append(f"background: url('{image_name}') {bg_x}px {bg_y}px;")
        else:
            props.append(f"background-image: url('{image_name}');")
            props.append(f"background-position: {bg_x}px {bg_y}px;")
        props.append(f"width: {box_w}px;")
        props.append(f"height: {box_h}px;")

        if rotated and opts.rotation_mode == "transform":
            props.append("transform-origin: 0 0;")
            props.append(f"transform: translateY({atlas_w}px) rotate(-90deg);")
        elif rotated and opts.rotation_mode == "legacy-center":
            props.append("transform: rotate(-90deg);")

        if opts.trim_mode == "margin" and (frame_x or frame_y):
            if frame_x:
                props.append(f"margin-left: {-frame_x}px;")
            if frame_y:
                props.append(f"margin-top: {-frame_y}px;")

        comment = self._build_round_trip_comment(
            packed.atlas_x,
            packed.atlas_y,
            atlas_w,
            atlas_h,
            frame_x,
            frame_y,
            frame_w,
            frame_h,
            rotated,
            opts,
        )

        if self.options.pretty_print:
            body_lines: List[str] = []
            if comment:
                body_lines.append(f"    {comment}")
            for prop in props:
                body_lines.append(f"    {prop}")
            body = "\n".join(body_lines)
            return f".{class_name} {{\n{body}\n}}"

        flat_parts: List[str] = []
        if comment:
            flat_parts.append(comment)
        flat_parts.extend(props)
        return f".{class_name} {{ {' '.join(flat_parts)} }}"

    @staticmethod
    def _resolve_layout(
        atlas_x: int,
        atlas_y: int,
        atlas_w: int,
        atlas_h: int,
        frame_x: int,
        frame_y: int,
        frame_w: int,
        frame_h: int,
        rotated: bool,
        opts: CssExportOptions,
    ) -> Tuple[int, int, int, int]:
        """Compute the background offset and box size for a sprite.

        Args:
            atlas_x: Sprite's left edge in the atlas image.
            atlas_y: Sprite's top edge in the atlas image.
            atlas_w: Atlas-region width (rotated, as packed).
            atlas_h: Atlas-region height (rotated, as packed).
            frame_x: Negative offset of the original frame's origin
                relative to the trimmed atlas region (Starling
                convention; typically zero or negative).
            frame_y: Vertical counterpart to ``frame_x``.
            frame_w: Original (untrimmed) frame width.
            frame_h: Original (untrimmed) frame height.
            rotated: ``True`` when the sprite is stored rotated 90
                degrees clockwise in the atlas.
            opts: Format-specific options driving the layout choice.

        Returns:
            Tuple of ``(bg_x, bg_y, box_w, box_h)`` where ``bg_x`` /
            ``bg_y`` are the values to feed to ``background-position``
            (already negated where needed) and ``box_w`` / ``box_h``
            are the values for the ``width`` / ``height`` properties.
        """
        bg_x = -atlas_x
        bg_y = -atlas_y

        if rotated and opts.rotation_mode == "legacy-center":
            box_w = atlas_h
            box_h = atlas_w
        else:
            box_w = atlas_w
            box_h = atlas_h

        if opts.trim_mode == "background-position" and (
            frame_x or frame_y or frame_w != atlas_w or frame_h != atlas_h
        ):
            if not rotated or opts.rotation_mode == "none":
                box_w = frame_w
                box_h = frame_h
                bg_x -= frame_x
                bg_y -= frame_y

        return bg_x, bg_y, box_w, box_h

    @staticmethod
    def _build_round_trip_comment(
        atlas_x: int,
        atlas_y: int,
        atlas_w: int,
        atlas_h: int,
        frame_x: int,
        frame_y: int,
        frame_w: int,
        frame_h: int,
        rotated: bool,
        opts: CssExportOptions,
    ) -> Optional[str]:
        """Emit a parser-friendly comment describing the raw geometry.

        The comment is required for lossless round-trips whenever the
        active mode hides information that the legacy CSS parser would
        otherwise need to recover from raw CSS properties (atlas-region
        size when ``trim_mode == "background-position"``, the rotation
        flag when ``rotation_mode == "none"``).

        Args:
            atlas_x: Sprite's left edge in the atlas image.
            atlas_y: Sprite's top edge in the atlas image.
            atlas_w: Atlas-region width.
            atlas_h: Atlas-region height.
            frame_x: Trim X offset (Starling convention).
            frame_y: Trim Y offset.
            frame_w: Original frame width.
            frame_h: Original frame height.
            rotated: Whether the sprite is rotated in the atlas.
            opts: Format-specific options.

        Returns:
            A ``/* tat: ... */`` comment string, or ``None`` when the
            comment is disabled.
        """
        if not opts.emit_round_trip_comment:
            return None

        parts = [
            f"x={atlas_x}",
            f"y={atlas_y}",
            f"w={atlas_w}",
            f"h={atlas_h}",
        ]
        if frame_x or frame_y or frame_w != atlas_w or frame_h != atlas_h:
            parts.append(f"frameX={frame_x}")
            parts.append(f"frameY={frame_y}")
            parts.append(f"frameW={frame_w}")
            parts.append(f"frameH={frame_h}")
        if rotated:
            parts.append("rotated=1")
        return f"/* tat: {' '.join(parts)} */"

    @staticmethod
    def _sanitize_class_name(name: str) -> str:
        """Sanitize a sprite name for use as a CSS class.

        Args:
            name: Original sprite name.

        Returns:
            Sanitized name safe for CSS class selectors.
        """
        result = []
        for char in name:
            if char.isalnum() or char in "-_":
                result.append(char)
            else:
                result.append("-")

        sanitized = "".join(result)

        if sanitized and sanitized[0].isdigit():
            sanitized = "s" + sanitized

        return sanitized or "sprite"


__all__ = ["CssExporter", "CssExportOptions"]
