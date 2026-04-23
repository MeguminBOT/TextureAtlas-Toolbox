#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for libGDX TexturePacker ``.atlas`` text format.

Format-wise this is identical to Spine's ``.atlas`` (Spine's runtime
loader is a direct port of libGDX's ``TextureAtlasData``), so the
heavy lifting is delegated to :class:`exporters.spine_exporter.SpineExporter`.
This thin wrapper keeps the ``gdx`` registry key and its own
``GdxExportOptions`` dataclass so existing callers continue to work.

Format reference:
    https://github.com/libgdx/libgdx/blob/master/gdx/src/com/badlogic/gdx/graphics/g2d/TextureAtlas.java
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import (
    ExportOptions,
    GeneratorMetadata,
    PackedSprite,
)
from exporters.spine_exporter import SpineExporter, SpineExportOptions


@dataclass
class GdxExportOptions:
    """libGDX atlas-specific export options.

    Attributes:
        format: Pixel format (``Pixmap.Format`` enum name).
        filter_min: Minification filter (``Texture.TextureFilter``).
        filter_mag: Magnification filter (``Texture.TextureFilter``).
        repeat: Repeat / wrap mode (``"none"``, ``"x"``, ``"y"``, ``"xy"``).
        pma: Premultiplied-alpha flag.
        modern_format: Emit modern ``bounds:``/``offsets:`` layout
            (default) or legacy ``xy``/``size``/``orig``/``offset``
            quadruple when ``False``.
        strict_spec: Suppress non-spec generator/packer/heuristic page
            lines.
        strip_index_suffix: Strip the trailing ``_<digits>`` suffix
            from region names whose ``index`` field matches, so an
            animation strip shares a single base name (libGDX's
            ``findRegions(name)`` convention). Defaults to True.
    """

    format: str = "RGBA8888"
    filter_min: str = "Linear"
    filter_mag: str = "Linear"
    repeat: str = "none"
    pma: bool = False
    modern_format: bool = True
    strict_spec: bool = False
    strip_index_suffix: bool = True


@ExporterRegistry.register
class GdxExporter(SpineExporter):
    """Export sprites to libGDX TexturePacker ``.atlas`` format.

    Same on-disk schema as :class:`SpineExporter`; subclassed only to
    expose a distinct ``gdx`` registry key and the
    :class:`GdxExportOptions` dataclass so that callers carrying
    ``custom_properties["gdx"]`` keep working.
    """

    FILE_EXTENSION = ".atlas"
    FORMAT_NAME = "gdx"

    def _get_format_options(self) -> SpineExportOptions:
        """Translate ``custom_properties["gdx"]`` into a ``SpineExportOptions``.

        Returns:
            The equivalent :class:`SpineExportOptions` instance.
        """
        custom = self.options.custom_properties
        opts = custom.get("gdx")

        if isinstance(opts, GdxExportOptions):
            return SpineExportOptions(
                format=opts.format,
                filter_min=opts.filter_min,
                filter_mag=opts.filter_mag,
                repeat=opts.repeat,
                pma=opts.pma,
                modern_format=opts.modern_format,
                strict_spec=opts.strict_spec,
                strip_index_suffix=opts.strip_index_suffix,
            )
        if isinstance(opts, SpineExportOptions):
            return opts
        if isinstance(opts, dict):
            try:
                return SpineExportOptions(**opts)
            except TypeError:
                return SpineExportOptions()
        return SpineExportOptions()


__all__ = ["GdxExporter", "GdxExportOptions"]
