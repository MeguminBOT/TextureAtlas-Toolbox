#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Apple/TexturePacker `.plist` (Cocos2d-x) atlas format.

Emits any of the four documented Cocos2d-x format versions (0-3) so
output is byte-compatible with the readers in
`CCSpriteFrameCache::addSpriteFramesWithDictionary`. Format 3 is the
modern TexturePacker default and supports rotation, aliases, and
polygon-mesh data; older versions are provided for compatibility with
Zwoptex-era pipelines.

Format reference:
    https://www.codeandweb.com/texturepacker/documentation/cocos2d-x
    https://github.com/cocos2d/cocos2d-x/blob/master/cocos/2d/CCSpriteFrameCache.cpp
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


_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tga")


@dataclass
class PlistExportOptions:
    """Cocos2d-x plist exporter options.

    Attributes:
        use_binary: Emit binary plist when True, XML plist otherwise.
        format_version: Cocos2d-x format version. Must be one of
            0, 1, 2, or 3. Defaults to 3 (TexturePacker's modern
            default). Versions 0 and 1 cannot represent rotation;
            version 2 is the legacy string-rect layout; version 3 is
            the modern `textureRect`/`textureRotated` layout that also
            carries aliases and polygon-mesh data.
        include_metadata: Include the top-level `metadata` dict.
        pixel_format: Value of `metadata.pixelFormat` for v3 output.
        premultiply_alpha: Value of `metadata.premultiplyAlpha` for v3
            output.
        smartupdate_hash: Optional value for `metadata.smartupdate`
            (TexturePacker writes a content-hash string here).
        target_name: Value of `metadata.target` for v3 output. Common
            values are `"cocos2d"` and `"default"`.
        strict_spec: When True, suppress the non-spec
            `generator:`/`packer:`/`heuristic:`/`efficiency:` metadata
            fields some downstream tools reject.
        append_png_extension: When True (the v2 default for legacy
            Cocos2d compatibility), append `.png` to frame keys that
            do not already carry a known image extension. v3 leaves
            keys untouched by default since aliases handle naming.
    """

    use_binary: bool = True
    format_version: int = 3
    include_metadata: bool = True
    pixel_format: str = "RGBA8888"
    premultiply_alpha: bool = False
    smartupdate_hash: Optional[str] = None
    target_name: str = "cocos2d"
    strict_spec: bool = False
    append_png_extension: Optional[bool] = None


@ExporterRegistry.register
class PlistExporter(BaseExporter):
    """Export sprites to Apple/TexturePacker (Cocos2d-x) `.plist`.

    The on-disk schema depends on `PlistExportOptions.format_version`;
    see the dataclass for the per-version differences.
    """

    FILE_EXTENSION = ".plist"
    FORMAT_NAME = "plist"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the plist exporter.

        Args:
            options: Generic export options. Format-specific options
                live in `options.custom_properties["plist"]` and may
                be either a `PlistExportOptions` instance or a dict
                of the same fields.

        Returns:
            None.
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> PlistExportOptions:
        """Pull format-specific options out of `custom_properties`.

        Returns:
            A `PlistExportOptions` instance, falling back to
            defaults when no usable value is provided.
        """
        custom = self.options.custom_properties
        opts = custom.get("plist")

        if isinstance(opts, PlistExportOptions):
            return opts
        if isinstance(opts, dict):
            try:
                return PlistExportOptions(**opts)
            except TypeError:
                return PlistExportOptions()
        return PlistExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> bytes:
        """Build the plist atlas content as a byte string.

        Args:
            packed_sprites: Sprites with their assigned atlas
                positions.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image (used for the
                `textureFileName` / `realTextureFileName` page fields).
            generator_metadata: Optional generator info embedded in the
                page metadata. Suppressed entirely when
                `strict_spec=True`.

        Returns:
            The serialized plist bytes (XML or binary depending on
            `use_binary`).
        """
        opts = self._format_options
        version = opts.format_version
        if version not in (0, 1, 2, 3):
            version = 3

        append_ext = opts.append_png_extension
        if append_ext is None:
            append_ext = version == 2

        frames: Dict[str, Dict[str, Any]] = {}
        for packed in packed_sprites:
            frame_key = self._frame_key(packed, append_ext)
            frames[frame_key] = self._build_frame_entry(packed, version)

        root: Dict[str, Any] = {"frames": frames}

        if opts.include_metadata:
            root["metadata"] = self._build_page_metadata(
                version, atlas_width, atlas_height, image_name, generator_metadata
            )

        fmt = plistlib.FMT_BINARY if opts.use_binary else plistlib.FMT_XML
        return plistlib.dumps(root, fmt=fmt)

    def _frame_key(self, packed: PackedSprite, append_ext: bool) -> str:
        """Produce the dictionary key used for a packed sprite.

        Args:
            packed: The packed sprite.
            append_ext: When True, append `.png` to keys that do not
                already end in a known image extension.

        Returns:
            The frame key string.
        """
        key = packed.name
        if append_ext and not key.lower().endswith(_IMAGE_EXTENSIONS):
            key = f"{key}.png"
        return key

    def _build_page_metadata(
        self,
        version: int,
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata],
    ) -> Dict[str, Any]:
        """Assemble the top-level `metadata` dict.

        Args:
            version: Cocos2d-x format version (0-3).
            atlas_width: Atlas width in pixels.
            atlas_height: Atlas height in pixels.
            image_name: Atlas image filename.
            generator_metadata: Optional generator info to embed.

        Returns:
            The metadata dict, ready to be inserted at the plist root.
        """
        opts = self._format_options
        meta: Dict[str, Any] = {
            "format": version,
            "textureFileName": image_name,
            "realTextureFileName": image_name,
            "size": f"{{{atlas_width},{atlas_height}}}",
        }

        if version >= 3:
            meta["pixelFormat"] = opts.pixel_format
            meta["premultiplyAlpha"] = bool(opts.premultiply_alpha)
            meta["target"] = opts.target_name
            if opts.smartupdate_hash:
                meta["smartupdate"] = opts.smartupdate_hash

        if generator_metadata and not opts.strict_spec:
            if generator_metadata.app_version:
                meta["generator"] = (
                    f"TextureAtlas Toolbox ({generator_metadata.app_version})"
                )
            if generator_metadata.packer:
                meta["packer"] = generator_metadata.packer
            if generator_metadata.heuristic:
                meta["heuristic"] = generator_metadata.heuristic
            if generator_metadata.efficiency > 0:
                meta["efficiency"] = int(round(generator_metadata.efficiency))

        return meta

    def _build_frame_entry(self, packed: PackedSprite, version: int) -> Dict[str, Any]:
        """Build the per-frame dict for a single sprite.

        Args:
            packed: The packed sprite.
            version: Cocos2d-x format version (0-3); selects the
                key naming convention.

        Returns:
            The frame dict in the layout expected by the chosen
            version, including any aliases and polygon-mesh data
            that were carried on the source sprite.
        """
        sprite = packed.sprite
        x = packed.atlas_x
        y = packed.atlas_y
        width = int(sprite["width"])
        height = int(sprite["height"])
        frame_x = int(sprite.get("frameX", 0))
        frame_y = int(sprite.get("frameY", 0))
        frame_w = int(sprite.get("frameWidth", width))
        frame_h = int(sprite.get("frameHeight", height))
        rotated = bool(packed.rotated or sprite.get("rotated", False))

        atlas_w, atlas_h = (height, width) if rotated else (width, height)

        if version >= 3:
            entry = self._build_v3_entry(
                x, y, atlas_w, atlas_h, frame_w, frame_h, frame_x, frame_y, rotated
            )
        elif version == 2:
            entry = self._build_v2_entry(
                x,
                y,
                atlas_w,
                atlas_h,
                frame_w,
                frame_h,
                frame_x,
                frame_y,
                width,
                height,
                rotated,
            )
        else:
            entry = self._build_v0_entry(
                x, y, atlas_w, atlas_h, frame_w, frame_h, frame_x, frame_y
            )

        aliases = sprite.get("aliases")
        if isinstance(aliases, list) and aliases:
            entry["aliases"] = list(aliases)
        elif version >= 3:
            entry.setdefault("aliases", [])

        if version >= 3:
            mesh = sprite.get("mesh")
            if isinstance(mesh, dict):
                for key in ("triangles", "vertices", "verticesUV", "anchor"):
                    if key in mesh:
                        entry[key] = mesh[key]

        return entry

    @staticmethod
    def _build_v0_entry(
        x: int,
        y: int,
        atlas_w: int,
        atlas_h: int,
        frame_w: int,
        frame_h: int,
        frame_x: int,
        frame_y: int,
    ) -> Dict[str, Any]:
        """Build a Zwoptex-style scalar frame entry (format 0 / 1).

        Args:
            x: Atlas x position.
            y: Atlas y position.
            atlas_w: Width in atlas (after any rotation swap).
            atlas_h: Height in atlas (after any rotation swap).
            frame_w: Original (untrimmed) sprite width.
            frame_h: Original (untrimmed) sprite height.
            frame_x: Trim x offset.
            frame_y: Trim y offset.

        Returns:
            Dict with the v0/v1 scalar field layout.
        """
        return {
            "x": x,
            "y": y,
            "width": atlas_w,
            "height": atlas_h,
            "offsetX": -frame_x,
            "offsetY": -frame_y,
            "originalWidth": frame_w,
            "originalHeight": frame_h,
        }

    @staticmethod
    def _build_v2_entry(
        x: int,
        y: int,
        atlas_w: int,
        atlas_h: int,
        frame_w: int,
        frame_h: int,
        frame_x: int,
        frame_y: int,
        sprite_w: int,
        sprite_h: int,
        rotated: bool,
    ) -> Dict[str, Any]:
        """Build a TexturePacker classic string-rect entry (format 2).

        Args:
            x: Atlas x position.
            y: Atlas y position.
            atlas_w: Width in atlas (after rotation swap).
            atlas_h: Height in atlas (after rotation swap).
            frame_w: Original (untrimmed) sprite width.
            frame_h: Original (untrimmed) sprite height.
            frame_x: Trim x offset.
            frame_y: Trim y offset.
            sprite_w: Trimmed sprite width (pre-swap).
            sprite_h: Trimmed sprite height (pre-swap).
            rotated: Whether the sprite is rotated 90 degrees.

        Returns:
            Dict with the v2 string-rect layout.
        """
        return {
            "frame": _format_rect(x, y, atlas_w, atlas_h),
            "offset": _format_size(-frame_x, -frame_y),
            "rotated": rotated,
            "sourceColorRect": _format_rect(-frame_x, -frame_y, sprite_w, sprite_h),
            "sourceSize": _format_size(frame_w, frame_h),
        }

    @staticmethod
    def _build_v3_entry(
        x: int,
        y: int,
        atlas_w: int,
        atlas_h: int,
        frame_w: int,
        frame_h: int,
        frame_x: int,
        frame_y: int,
        rotated: bool,
    ) -> Dict[str, Any]:
        """Build a TexturePacker modern entry (format 3).

        Args:
            x: Atlas x position.
            y: Atlas y position.
            atlas_w: Width in atlas (after rotation swap, matching the
                Cocos2d-x `textureRect` convention).
            atlas_h: Height in atlas (after rotation swap).
            frame_w: Original (untrimmed) sprite width.
            frame_h: Original (untrimmed) sprite height.
            frame_x: Trim x offset.
            frame_y: Trim y offset.
            rotated: Whether the sprite is rotated 90 degrees.

        Returns:
            Dict with the v3 layout (`textureRect`,
            `textureRotated`, `spriteOffset`, `spriteSize`,
            `spriteSourceSize`).
        """
        return {
            "textureRect": _format_rect(x, y, atlas_w, atlas_h),
            "textureRotated": rotated,
            "spriteOffset": _format_size(-frame_x, -frame_y),
            "spriteSize": _format_size(atlas_w, atlas_h),
            "spriteSourceSize": _format_size(frame_w, frame_h),
        }


def _format_rect(x: int, y: int, w: int, h: int) -> str:
    """Render a `(x, y, w, h)` rectangle in Cocos2d-x string form.

    Args:
        x: Origin x.
        y: Origin y.
        w: Width.
        h: Height.

    Returns:
        A string of the form `{{x,y},{w,h}}`.
    """
    return f"{{{{{x},{y}}},{{{w},{h}}}}}"


def _format_size(w: int, h: int) -> str:
    """Render a `(w, h)` size in Cocos2d-x string form.

    Args:
        w: Width or x component.
        h: Height or y component.

    Returns:
        A string of the form `{w,h}`.
    """
    return f"{{{w},{h}}}"


__all__ = ["PlistExporter", "PlistExportOptions"]
