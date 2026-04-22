#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Phaser 3 atlas JSON format.

Supports all three documented Phaser 3 schema variants:

    multiatlas (default)
        Root contains `textures: [{...}]`, each texture carries its
        own `image`/`format`/`size`/`scale`/`frames`. Top-level
        `meta` may carry `app`/`version`/`smartupdate` and a
        `related_multi_packs` list referencing sibling pack files.
        This is what `Phaser.Loader.FileTypes.MultiAtlasFile`
        consumes.

    JSONArray (single-atlas, frames as list)
        Root has `frames: [...]` and a single `meta` block carrying
        page metadata.

    JSONHash (single-atlas, frames as object)
        Same as JSONArray except `frames` is keyed by filename.

Format reference:
    https://github.com/phaserjs/phaser/blob/master/src/textures/parsers/JSONArray.js
    https://github.com/phaserjs/phaser/blob/master/src/textures/parsers/JSONHash.js
    https://github.com/phaserjs/phaser/blob/master/src/loader/filetypes/MultiAtlasFile.js
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import (
    ExportOptions,
    GeneratorMetadata,
    PackedSprite,
)


@dataclass
class Phaser3ExportOptions:
    """Phaser 3 specific export options.

    Attributes:
        format_string: Pixel format string emitted on each page
            (e.g. `"RGBA8888"`).
        scale: Atlas scale factor written to each page (1 for
            standard, 2 for `@2x`).
        multiatlas: When True, emit the multi-atlas form with a
            top-level `textures[]` array. When False, emit the
            single-atlas form with `frames` directly under the root
            and a single page-metadata block on `meta`.
        frames_as_array: When True, `frames` is emitted as a JSON
            array (JSONArray form). When False, as an object keyed
            by filename (JSONHash form).
        related_multi_packs: Sibling pack filenames to advertise on
            `meta.related_multi_packs`. Phaser's `MultiAtlasFile`
            loader follows these references automatically.
        smartupdate_hash: Optional smartupdate hash recorded on
            `meta.smartupdate` for tooling round-trips.
        include_pivot: When True, sprites carrying `pivotX` /
            `pivotY` produce a per-frame `pivot: {x, y}` block.
        strict_spec: When True, suppress non-spec generator fields
            (`generator`, `packer`, `heuristic`, `efficiency`).
    """

    format_string: str = "RGBA8888"
    scale: float = 1.0
    multiatlas: bool = True
    frames_as_array: bool = True
    related_multi_packs: List[str] = field(default_factory=list)
    smartupdate_hash: Optional[str] = None
    include_pivot: bool = True
    strict_spec: bool = False


@ExporterRegistry.register
class Phaser3Exporter(BaseExporter):
    """Export packed sprites to Phaser 3 atlas JSON.

    Defaults to the multi-atlas (`textures[]`) form because that is
    the variant Phaser's `MultiAtlasFile` loader consumes and the one
    most modern projects use. Both single-atlas variants are
    available via `Phaser3ExportOptions`.

    Usage:
        from exporters import Phaser3Exporter, ExportOptions
        from exporters.phaser3_exporter import Phaser3ExportOptions

        options = ExportOptions(
            custom_properties={"phaser3": Phaser3ExportOptions()}
        )
        exporter = Phaser3Exporter(options)
    """

    FILE_EXTENSION = ".json"
    FORMAT_NAME = "phaser3"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the Phaser 3 exporter.

        Args:
            options: Export options. Format-specific options should
                be supplied via
                `options.custom_properties["phaser3"]`.

        Returns:
            None.
        """
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> Phaser3ExportOptions:
        """Resolve the Phaser3ExportOptions instance to use.

        Returns:
            A `Phaser3ExportOptions` built from
            `options.custom_properties["phaser3"]`, or a default
            instance when none was supplied.
        """
        custom = self.options.custom_properties
        opts = custom.get("phaser3")

        if isinstance(opts, Phaser3ExportOptions):
            return opts
        if isinstance(opts, dict):
            try:
                return Phaser3ExportOptions(**opts)
            except TypeError:
                return Phaser3ExportOptions()
        return Phaser3ExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate Phaser 3 atlas JSON metadata.

        Args:
            packed_sprites: Sprites with their atlas positions
                assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image, written to
                `meta.image` (single-atlas) or each texture's
                `image` (multi-atlas).
            generator_metadata: Optional generator info written into
                the top-level `meta` block when `strict_spec` is
                False.

        Returns:
            The atlas JSON as a string. Pretty-printed with
            four-space indent when `options.pretty_print` is set.
        """
        opts = self._format_options
        frames_payload = self._build_frames_payload(packed_sprites, opts)

        page_block: Dict[str, Any] = {
            "image": image_name,
            "format": opts.format_string,
            "size": {"w": atlas_width, "h": atlas_height},
            "scale": opts.scale,
        }

        meta_block = self._build_meta_block(
            opts, generator_metadata, page_block, multiatlas=opts.multiatlas
        )

        if opts.multiatlas:
            texture: Dict[str, Any] = dict(page_block)
            texture["frames"] = frames_payload
            output: Dict[str, Any] = {"textures": [texture]}
            if meta_block:
                output["meta"] = meta_block
        else:
            output = {"frames": frames_payload}
            if meta_block:
                output["meta"] = meta_block

        indent = 4 if self.options.pretty_print else None
        return json.dumps(output, indent=indent, ensure_ascii=False)

    def _build_frames_payload(
        self,
        packed_sprites: List[PackedSprite],
        opts: Phaser3ExportOptions,
    ) -> Any:
        """Build the `frames` payload in array or hash form.

        Args:
            packed_sprites: Packed sprite list to emit.
            opts: Resolved Phaser 3 export options.

        Returns:
            Either a list of frame dicts (JSONArray / multi-atlas
            form) or a dict keyed by filename (JSONHash form).
        """
        if opts.frames_as_array:
            return [
                self._build_frame_entry(p, opts, include_filename=True)
                for p in packed_sprites
            ]

        result: Dict[str, Any] = {}
        for packed in packed_sprites:
            entry = self._build_frame_entry(packed, opts, include_filename=False)
            result[packed.name] = entry
        return result

    def _build_frame_entry(
        self,
        packed: PackedSprite,
        opts: Phaser3ExportOptions,
        include_filename: bool,
    ) -> Dict[str, Any]:
        """Build one frame entry for the `frames` payload.

        Args:
            packed: Packed sprite with atlas position.
            opts: Resolved Phaser 3 export options.
            include_filename: Whether to embed the filename inside
                the entry. Array form sets True; hash form False
                (the filename is the key).

        Returns:
            Frame dict matching Phaser 3's per-frame schema.
        """
        sprite = packed.sprite
        width = sprite["width"]
        height = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", width)
        frame_h = sprite.get("frameHeight", height)

        is_rotated = bool(packed.rotated or sprite.get("rotated", False))
        atlas_w, atlas_h = (height, width) if is_rotated else (width, height)

        if "trimmed" in sprite:
            trimmed = bool(sprite["trimmed"])
        else:
            trimmed = (
                frame_x != 0 or frame_y != 0 or frame_w != width or frame_h != height
            )

        entry: Dict[str, Any] = {}
        if include_filename:
            entry["filename"] = packed.name
        entry["frame"] = {
            "x": packed.atlas_x,
            "y": packed.atlas_y,
            "w": atlas_w,
            "h": atlas_h,
        }
        entry["rotated"] = is_rotated
        entry["trimmed"] = trimmed
        entry["spriteSourceSize"] = {
            "x": -frame_x,
            "y": -frame_y,
            "w": width,
            "h": height,
        }
        entry["sourceSize"] = {"w": frame_w, "h": frame_h}

        if opts.include_pivot and ("pivotX" in sprite or "pivotY" in sprite):
            entry["pivot"] = {
                "x": float(sprite.get("pivotX", 0.0)),
                "y": float(sprite.get("pivotY", 0.0)),
            }

        return entry

    def _build_meta_block(
        self,
        opts: Phaser3ExportOptions,
        generator_metadata: Optional[GeneratorMetadata],
        page_block: Dict[str, Any],
        multiatlas: bool,
    ) -> Dict[str, Any]:
        """Build the top-level `meta` block.

        Args:
            opts: Resolved Phaser 3 export options.
            generator_metadata: Optional generator info for the
                non-strict watermark fields.
            page_block: The page metadata (image / format / size /
                scale). For single-atlas output this is merged into
                `meta`. For multi-atlas it is omitted (each
                `textures[]` entry already carries it).
            multiatlas: True when the parent output is using the
                multi-atlas wrapper.

        Returns:
            A dict that is empty when nothing needs to be emitted.
            Always emitted at the top level when non-empty.
        """
        meta: Dict[str, Any] = {}

        if not multiatlas:
            meta.update(page_block)

        if opts.smartupdate_hash:
            meta["smartupdate"] = opts.smartupdate_hash

        if opts.related_multi_packs:
            meta["related_multi_packs"] = list(opts.related_multi_packs)

        if not opts.strict_spec and generator_metadata:
            if generator_metadata.app_version:
                meta["app"] = "TextureAtlas Toolbox"
                meta["version"] = generator_metadata.app_version
            if generator_metadata.packer:
                meta["packer"] = generator_metadata.packer
            if generator_metadata.heuristic:
                meta["heuristic"] = generator_metadata.heuristic
            if generator_metadata.efficiency > 0:
                meta["efficiency"] = int(round(generator_metadata.efficiency))

        return meta


__all__ = ["Phaser3Exporter", "Phaser3ExportOptions"]
