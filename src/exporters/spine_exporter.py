#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for libGDX TexturePacker / Spine ``.atlas`` text format.

Emits the same on-disk schema that libGDX's ``TextureAtlasData.load``
parses (see
:file:`gdx/src/com/badlogic/gdx/graphics/g2d/TextureAtlas.java`),
which is also the format used by Spine's runtime atlas readers.

Format reference:
    http://esotericsoftware.com/spine-atlas-format
    https://github.com/libgdx/libgdx/blob/master/gdx/src/com/badlogic/gdx/graphics/g2d/TextureAtlas.java

Two output dialects are supported:

* **Modern** (default, ``modern_format=True``): one ``bounds:`` and
  one ``offsets:`` line per region. Preferred since libGDX 1.10 and
  required for tightly packed regions where width/height differ from
  the original.
* **Legacy** (``modern_format=False``): the deprecated
  ``xy``/``size``/``orig``/``offset`` quadruple. Use this for older
  Spine runtimes (≤ 4.0) and for tooling pinned to the historical
  layout.

Output example (modern)::

    atlas.png
    size: 512, 512
    format: RGBA8888
    filter: Linear, Linear
    repeat: none
    sprite_01
      bounds: 0, 0, 64, 64
      offsets: 0, 0, 64, 64
      rotate: false
      index: -1
"""

from __future__ import annotations

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
class SpineExportOptions:
    """libGDX/Spine atlas-specific export options.

    Attributes:
        format: Pixel format string. Must be a libGDX ``Pixmap.Format``
            enum name (``Alpha``, ``Intensity``, ``LuminanceAlpha``,
            ``RGB565``, ``RGBA4444``, ``RGB888``, ``RGBA8888``).
        filter_min: Minification filter. Must be a libGDX
            ``Texture.TextureFilter`` enum name (``Nearest``,
            ``Linear``, ``MipMap``, ``MipMapNearestNearest``,
            ``MipMapLinearNearest``, ``MipMapNearestLinear``,
            ``MipMapLinearLinear``).
        filter_mag: Magnification filter (same enum as ``filter_min``).
        repeat: Repeat / wrap mode. ``"none"``, ``"x"``, ``"y"``, or
            ``"xy"``.
        pma: Premultiplied-alpha flag.
        modern_format: When ``True`` (default), emit the modern
            ``bounds:``/``offsets:`` two-line layout. When ``False``,
            emit the legacy ``xy``/``size``/``orig``/``offset``
            quadruple for compatibility with old Spine runtimes.
        strict_spec: When ``True``, suppress the non-spec
            ``generator:``/``packer:``/``heuristic:``/``efficiency:``
            comment-style lines that some downstream tools treat as
            unknown page fields.
    """

    format: str = "RGBA8888"
    filter_min: str = "Linear"
    filter_mag: str = "Linear"
    repeat: str = "none"
    pma: bool = False
    modern_format: bool = True
    strict_spec: bool = False


@ExporterRegistry.register
class SpineExporter(BaseExporter):
    """Export sprites to libGDX / Spine ``.atlas`` text format.

    Each page begins with the texture filename followed by indented
    page fields (``size``, ``format``, ``filter``, ``repeat``, ``pma``);
    region entries follow with their own indented field lines. The
    output is byte-compatible with what libGDX's TexturePacker writes.
    """

    FILE_EXTENSION = ".atlas"
    FORMAT_NAME = "spine"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> SpineExportOptions:
        """Extract format-specific options from :class:`ExportOptions`."""
        custom = self.options.custom_properties
        opts = custom.get("spine")
        if isinstance(opts, SpineExportOptions):
            return opts
        if isinstance(opts, dict):
            try:
                return SpineExportOptions(**opts)
            except TypeError:
                return SpineExportOptions()
        return SpineExportOptions()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate libGDX/Spine atlas text metadata.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image (becomes the page
                name).
            generator_metadata: Optional metadata. Emitted as
                non-standard ``generator:``/``packer:``/``heuristic:``
                page lines unless ``strict_spec=True``.

        Returns:
            Text content for the ``.atlas`` file (always ends with a
            single trailing newline).
        """
        opts = self._format_options
        lines: List[str] = []

        # Page header
        lines.append(image_name)
        lines.append(f"size: {atlas_width}, {atlas_height}")
        lines.append(f"format: {opts.format}")
        lines.append(f"filter: {opts.filter_min}, {opts.filter_mag}")
        lines.append(f"repeat: {opts.repeat}")
        if opts.pma:
            lines.append("pma: true")

        # Optional generator metadata. libGDX silently ignores unknown
        # page fields (``// Silently ignore all header fields.``), so
        # these are safe to include but easy to suppress when targeting
        # strictly spec-conformant output.
        if generator_metadata and not opts.strict_spec:
            if generator_metadata.app_version:
                lines.append(
                    f"generator: TextureAtlas Toolbox ({generator_metadata.app_version})"
                )
            if generator_metadata.packer:
                lines.append(f"packer: {generator_metadata.packer}")
            if generator_metadata.heuristic:
                lines.append(f"heuristic: {generator_metadata.heuristic}")
            if generator_metadata.efficiency > 0:
                # Use an int so unknown-field parsers that try to coerce
                # the value via ``Integer.parseInt`` succeed instead of
                # silently dropping it.
                lines.append(f"efficiency: {int(round(generator_metadata.efficiency))}")

        for packed in packed_sprites:
            lines.extend(self._build_region(packed))

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Region emit
    # ------------------------------------------------------------------

    def _build_region(self, packed: PackedSprite) -> List[str]:
        """Build the lines for a single region/sprite entry."""
        sprite = packed.sprite
        opts = self._format_options

        width = int(sprite["width"])
        height = int(sprite["height"])
        frame_w = int(sprite.get("frameWidth", width))
        frame_h = int(sprite.get("frameHeight", height))
        frame_x = int(sprite.get("frameX", 0))
        frame_y = int(sprite.get("frameY", 0))
        rotated = bool(packed.rotated or sprite.get("rotated", False))

        # libGDX swaps width/height in the file when ``rotate: true``;
        # match that convention so the atlas is round-trip correct.
        atlas_w, atlas_h = (height, width) if rotated else (width, height)

        # Emit ``rotate: <degrees>`` when an explicit non-90/0 angle is
        # carried on the sprite (libGDX accepts any int 0–359). Falls
        # back to ``true``/``false`` otherwise.
        degrees_val = sprite.get("degrees")
        rotate_token = self._format_rotate(rotated, degrees_val)

        index_val = sprite.get("index", -1)
        if index_val is None:
            index_val = -1

        lines: List[str] = [sprite["name"]]

        if opts.modern_format:
            # ``bounds: x, y, w, h`` and ``offsets: ox, oy, ow, oh``.
            # libGDX stores ``offset`` as the negative of our
            # ``frameX``/``frameY``.
            lines.append(
                f"  bounds: {packed.atlas_x}, {packed.atlas_y}, {atlas_w}, {atlas_h}"
            )
            lines.append(f"  offsets: {-frame_x}, {-frame_y}, {frame_w}, {frame_h}")
            lines.append(f"  rotate: {rotate_token}")
            lines.append(f"  index: {int(index_val)}")
        else:
            lines.append(f"  rotate: {rotate_token}")
            lines.append(f"  xy: {packed.atlas_x}, {packed.atlas_y}")
            lines.append(f"  size: {atlas_w}, {atlas_h}")
            lines.append(f"  orig: {frame_w}, {frame_h}")
            lines.append(f"  offset: {-frame_x}, {-frame_y}")
            lines.append(f"  index: {int(index_val)}")

        # Ninepatch metadata. libGDX expects exactly four ints for each
        # of ``split`` (left, right, top, bottom) and ``pad`` (same
        # order); silently skip malformed payloads.
        split = sprite.get("split")
        if isinstance(split, (list, tuple)) and len(split) == 4:
            lines.append("  split: " + ", ".join(str(int(v)) for v in split))
        pad = sprite.get("pad")
        if isinstance(pad, (list, tuple)) and len(pad) == 4:
            lines.append("  pad: " + ", ".join(str(int(v)) for v in pad))

        # Arbitrary int-array custom values, mirroring libGDX's
        # ``names[]`` / ``values[]`` extension point.
        custom = sprite.get("custom_values")
        if isinstance(custom, dict):
            for key, values in custom.items():
                if not isinstance(values, (list, tuple)) or not values:
                    continue
                try:
                    formatted = ", ".join(str(int(v)) for v in values)
                except (TypeError, ValueError):
                    continue
                lines.append(f"  {key}: {formatted}")

        return lines

    @staticmethod
    def _format_rotate(rotated: bool, degrees: Any) -> str:
        """Render the value for the ``rotate:`` field.

        ``rotate: 90`` and ``rotate: true`` are equivalent in libGDX;
        we prefer the boolean form for the common case so existing
        readers stay happy. Numeric degrees are emitted only when an
        explicit non-trivial angle is provided.
        """
        if degrees is None:
            return "true" if rotated else "false"
        try:
            deg_int = int(degrees) % 360
        except (TypeError, ValueError):
            return "true" if rotated else "false"
        if deg_int == 0:
            return "false"
        if deg_int == 90:
            return "true"
        return str(deg_int)


__all__ = ["SpineExporter", "SpineExportOptions"]
