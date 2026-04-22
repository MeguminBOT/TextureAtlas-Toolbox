#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Exporter for Aseprite-compatible JSON metadata.

This exporter emits the same JSON structure that Aseprite's
``--data`` flag produces, allowing users to round-trip atlases between
TextureAtlas Toolbox and Aseprite. The schema mirrored here is taken
directly from :file:`src/app/doc_exporter.cpp`
(``DocExporter::createDataFile``) on the upstream Aseprite project.

Format reference:
    https://www.aseprite.org/docs/cli/
    https://github.com/aseprite/aseprite/blob/main/src/app/doc_exporter.cpp
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from exporters.base_exporter import BaseExporter
from exporters.exporter_registry import ExporterRegistry
from exporters.exporter_types import ExportOptions, GeneratorMetadata, PackedSprite
from utils.version import APP_VERSION

logger = logging.getLogger(__name__)

# Canonical animation directions emitted by Aseprite via
# ``convert_anidir_to_string``. Keep in sync with
# :data:`parsers.aseprite_parser.VALID_DIRECTIONS`.
_VALID_DIRECTIONS = frozenset({"forward", "reverse", "pingpong", "pingpong_reverse"})


def _normalize_direction(value: Any) -> str:
    """Coerce a direction value to one of Aseprite's four canonical names."""
    if not isinstance(value, str):
        return "forward"
    canonical = value.replace("-", "_").strip().lower()
    if canonical in _VALID_DIRECTIONS:
        return canonical
    logger.warning(
        "[AsepriteExporter] Unknown direction %r; emitting 'forward'.", value
    )
    return "forward"


def _emit_user_data(
    target: Dict[str, Any],
    color: Any = None,
    data: Any = None,
    properties: Any = None,
) -> None:
    """Append Aseprite ``userData`` fields to a JSON-bound dict.

    Mirrors ``operator<<(std::ostream&, const doc::UserData&)`` from
    :file:`doc_exporter.cpp`: only emit ``color``, ``data``, and
    ``properties`` when they have meaningful values.
    """
    if isinstance(color, str) and color:
        target["color"] = color
    if isinstance(data, str) and data:
        target["data"] = data
    if isinstance(properties, dict) and properties:
        target["properties"] = properties


@dataclass
class AsepriteExportOptions:
    """Options specific to the Aseprite JSON exporter.

    Attributes:
        format_string: ``meta.format`` value (``"RGBA8888"`` or ``"I8"``
            in upstream Aseprite).
        scale_string: ``meta.scale`` value. Aseprite emits this as a
            JSON string literal ``"1"`` (see ``createDataFile`` in
            ``doc_exporter.cpp``); we preserve that convention by
            default.
        default_duration: Per-frame duration in milliseconds, used when
            a sprite does not carry its own ``duration`` field.
        json_array: When ``True``, emit ``frames`` as a JSON array with
            a ``filename`` attribute on each entry (Aseprite's
            ``--format json-array``); otherwise emit a ``filename`` to
            ``frame`` mapping (``--format json-hash``, the default).
        app_string: Override for ``meta.app``. When empty,
            ``"TextureAtlas Toolbox (<version>)"`` is used.
        version_string: Override for ``meta.version``. Defaults to
            :data:`APP_VERSION`.
        strict_aseprite: When ``True``, always emit ``rotated: false``
            (matching Aseprite, whose own packer never rotates samples).
            Defaults to ``False`` so our rotation extension survives the
            round-trip when the consumer supports it.
        frame_tags: Optional explicit ``meta.frameTags`` list. When
            provided, this overrides the auto-derived tag list and is
            emitted verbatim after key normalization. Each entry should
            mirror the parser output: ``name``, ``from``, ``to``,
            ``direction``, optional ``repeat`` (int), ``color``,
            ``data``, ``properties``.
        layers: Optional ``meta.layers`` list. Pass-through; entries
            should follow the structure produced by
            :class:`parsers.aseprite_parser.AsepriteParser`.
        slices: Optional ``meta.slices`` list. Pass-through; entries
            should follow the structure produced by
            :class:`parsers.aseprite_parser.AsepriteParser`.
    """

    format_string: str = "RGBA8888"
    scale_string: str = "1"
    default_duration: int = 0  # milliseconds
    json_array: bool = False
    app_string: str = ""
    version_string: str = ""
    strict_aseprite: bool = False
    frame_tags: List[Dict[str, Any]] = field(default_factory=list)
    layers: List[Dict[str, Any]] = field(default_factory=list)
    slices: List[Dict[str, Any]] = field(default_factory=list)


@ExporterRegistry.register
class AsepriteExporter(BaseExporter):
    """Export packed sprites to the Aseprite JSON schema.

    The output is byte-compatible with the document Aseprite emits when
    invoked as ``aseprite -b sprite.aseprite --sheet sheet.png --data
    sheet.json --list-tags --list-layers --list-slices``.
    """

    FILE_EXTENSION = ".json"
    FORMAT_NAME = "aseprite"
    DISPLAY_NAME = "Aseprite JSON"

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        super().__init__(options)
        self._format_options = self._get_format_options()

    def _get_format_options(self) -> AsepriteExportOptions:
        """Extract format-specific options from :class:`ExportOptions`."""
        custom = self.options.custom_properties
        opts = custom.get("aseprite")
        if isinstance(opts, AsepriteExportOptions):
            return opts
        if isinstance(opts, dict):
            try:
                return AsepriteExportOptions(**opts)
            except TypeError:
                logger.warning(
                    "[AsepriteExporter] Unrecognized keys in 'aseprite' "
                    "custom_properties dict; using defaults."
                )
                return AsepriteExportOptions()
        return AsepriteExportOptions()

    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> str:
        """Generate an Aseprite JSON document.

        Args:
            packed_sprites: Sprites with their atlas placements.
            atlas_width: Width of the rendered atlas image.
            atlas_height: Height of the rendered atlas image.
            image_name: Filename of the matching atlas image.
            generator_metadata: Optional packer/heuristic metadata to
                stash under ``meta.textureAtlasToolbox``.

        Returns:
            The serialized JSON document.
        """
        opts = self._format_options
        if opts.json_array:
            frames: Any = [
                self._build_array_frame_entry(packed) for packed in packed_sprites
            ]
        else:
            frames = {
                packed.name: self._build_frame_entry(packed)
                for packed in packed_sprites
            }

        meta = self._build_meta_block(
            packed_sprites,
            atlas_width,
            atlas_height,
            image_name,
            generator_metadata,
        )

        data = {"frames": frames, "meta": meta}
        indent = 4 if self.options.pretty_print else None
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def _build_frame_entry(self, packed: PackedSprite) -> Dict[str, Any]:
        """Create the frame dictionary for a single sprite (hash form).

        Aseprite always emits ``rotated: false`` because its packer
        never rotates samples (see ``createDataFile`` in
        :file:`doc_exporter.cpp`). When ``strict_aseprite`` is ``True``
        we honour that exactly; otherwise we faithfully report the
        rotation our own packer applied.

        **Rotation direction.** When ``rotated`` is ``True`` the sample
        in the atlas image has been rotated **90° clockwise** relative
        to the source frame (the TexturePacker convention that Aseprite
        inherits, and the same convention used everywhere else in this
        toolbox — see ``FORMATS_SUPPORTING_ROTATION`` in
        :mod:`exporters.exporter_types`). The atlas ``frame.w`` /
        ``frame.h`` are therefore the *post-rotation* dimensions:
        ``atlas_w == sprite_height`` and ``atlas_h == sprite_width``.
        Consumers must rotate the sample 90° **counter-clockwise** when
        blitting it back to its source orientation.
        """
        sprite = packed.sprite
        opts = self._format_options
        width = sprite["width"]
        height = sprite["height"]
        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_w = sprite.get("frameWidth", width)
        frame_h = sprite.get("frameHeight", height)

        trimmed = frame_x != 0 or frame_y != 0 or frame_w != width or frame_h != height
        actual_rotated = packed.rotated or sprite.get("rotated", False)
        emit_rotated = False if opts.strict_aseprite else actual_rotated

        atlas_w, atlas_h = (height, width) if actual_rotated else (width, height)

        # Per-sprite duration takes precedence over the default.
        try:
            duration = int(sprite.get("duration", opts.default_duration))
        except (TypeError, ValueError):
            duration = opts.default_duration

        return {
            "frame": {
                "x": packed.atlas_x,
                "y": packed.atlas_y,
                "w": atlas_w,
                "h": atlas_h,
            },
            "rotated": emit_rotated,
            "trimmed": trimmed,
            "spriteSourceSize": {
                "x": frame_x,
                "y": frame_y,
                "w": width,
                "h": height,
            },
            "sourceSize": {
                "w": frame_w,
                "h": frame_h,
            },
            "duration": duration,
        }

    def _build_array_frame_entry(self, packed: PackedSprite) -> Dict[str, Any]:
        """Build a frame entry for ``--format json-array`` output.

        Mirrors Aseprite's ``filename_as_attr`` branch: each entry is a
        dict with ``filename`` plus the standard frame fields.
        """
        entry: Dict[str, Any] = {"filename": packed.name}
        entry.update(self._build_frame_entry(packed))
        return entry

    def _build_meta_block(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata],
    ) -> Dict[str, Any]:
        """Build the ``meta`` section of the JSON output.

        Field order matches the upstream emit
        (``app, version, image, format, size, scale, frameTags,
        layers, slices``) so a textual diff against an Aseprite-produced
        file is meaningful.
        """
        opts = self._format_options
        meta: Dict[str, Any] = {
            "app": opts.app_string or f"TextureAtlas Toolbox ({APP_VERSION})",
            "version": opts.version_string or APP_VERSION,
            "image": image_name,
            "format": opts.format_string,
            "size": {"w": atlas_width, "h": atlas_height},
            "scale": opts.scale_string,
            "frameTags": self._build_frame_tags(packed_sprites),
            "layers": self._build_layers(),
            "slices": self._build_slices(),
        }

        if generator_metadata:
            tatt_meta: Dict[str, Any] = {}
            if generator_metadata.packer:
                tatt_meta["packer"] = generator_metadata.packer
            if generator_metadata.heuristic:
                tatt_meta["heuristic"] = generator_metadata.heuristic
            if generator_metadata.efficiency > 0:
                tatt_meta["efficiency"] = generator_metadata.efficiency
            if tatt_meta:
                meta["textureAtlasToolbox"] = tatt_meta

        return meta

    def _build_frame_tags(
        self, packed_sprites: List[PackedSprite]
    ) -> List[Dict[str, Any]]:
        """Build the ``meta.frameTags`` array.

        If :attr:`AsepriteExportOptions.frame_tags` was supplied, those
        entries are emitted verbatim (after key normalization).
        Otherwise, frame tags are derived by scanning the packed sprite
        list for runs of identical animation names.
        """
        opts = self._format_options
        if opts.frame_tags:
            return [self._format_frame_tag(tag) for tag in opts.frame_tags]
        return self._derive_frame_tags(packed_sprites)

    @staticmethod
    def _format_frame_tag(tag: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a frame-tag dict to Aseprite's emit conventions.

        ``repeat`` is rendered as a JSON string when greater than zero,
        matching the upstream emit (``"\"repeat\": \"3\""``); a value
        of ``0`` is omitted (Aseprite uses ``0`` to mean infinite).
        """
        out: Dict[str, Any] = {
            "name": str(tag.get("name", "")),
            "from": int(tag.get("from", 0)),
            "to": int(tag.get("to", 0)),
            "direction": _normalize_direction(tag.get("direction", "forward")),
        }
        repeat_val = tag.get("repeat")
        if repeat_val is not None:
            try:
                repeat_int = int(repeat_val)
                if repeat_int > 0:
                    out["repeat"] = str(repeat_int)
            except (TypeError, ValueError):
                pass
        _emit_user_data(
            out,
            color=tag.get("color"),
            data=tag.get("data"),
            properties=tag.get("properties"),
        )
        return out

    def _derive_frame_tags(
        self, packed_sprites: List[PackedSprite]
    ) -> List[Dict[str, Any]]:
        """Auto-derive frame tags from the packed sprite stream.

        Each contiguous run of sprites sharing the same animation name
        becomes one tag. Optional ``animation_repeat``,
        ``animation_color``, ``animation_data``, ``animation_properties``
        fields on the *first* sprite of each run feed into the
        emitted tag's user-data fields.
        """
        tags: List[Dict[str, Any]] = []
        current_anim: Optional[str] = None
        current_direction: str = "forward"
        current_extras: Dict[str, Any] = {}
        start_idx = 0

        def _read_tag_extras(sprite: Dict[str, Any]) -> Dict[str, Any]:
            extras: Dict[str, Any] = {}
            if "animation_repeat" in sprite:
                extras["repeat"] = sprite["animation_repeat"]
            for src, dst in (
                ("animation_color", "color"),
                ("animation_data", "data"),
                ("animation_properties", "properties"),
            ):
                if src in sprite:
                    extras[dst] = sprite[src]
            return extras

        def _read_anim_name(sprite: Dict[str, Any]) -> str:
            # Prefer the unambiguous parser-side name; fall back to the
            # legacy "animation" key for callers that build sprites by
            # hand.
            return str(sprite.get("animation_tag", sprite.get("animation", "")))

        def _read_direction(sprite: Dict[str, Any]) -> str:
            return _normalize_direction(
                sprite.get(
                    "animation_direction",
                    sprite.get("direction", "forward"),
                )
            )

        for i, packed in enumerate(packed_sprites):
            anim = _read_anim_name(packed.sprite)
            if anim != current_anim:
                if current_anim:
                    tags.append(
                        self._format_frame_tag(
                            {
                                "name": current_anim,
                                "from": start_idx,
                                "to": i - 1,
                                "direction": current_direction,
                                **current_extras,
                            }
                        )
                    )
                current_anim = anim
                current_direction = _read_direction(packed.sprite)
                current_extras = _read_tag_extras(packed.sprite)
                start_idx = i

        # Close the last group
        if current_anim and packed_sprites:
            tags.append(
                self._format_frame_tag(
                    {
                        "name": current_anim,
                        "from": start_idx,
                        "to": len(packed_sprites) - 1,
                        "direction": current_direction,
                        **current_extras,
                    }
                )
            )

        return tags

    def _build_layers(self) -> List[Dict[str, Any]]:
        """Build ``meta.layers`` from explicit overrides only.

        Layer information cannot be reconstructed from packed sprites
        alone, so this exporter only emits it when the caller has
        threaded data through :attr:`AsepriteExportOptions.layers`
        (for example, from a previous parse).
        """
        return [self._format_layer(layer) for layer in self._format_options.layers]

    @staticmethod
    def _format_layer(layer: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single layer entry."""
        out: Dict[str, Any] = {"name": str(layer.get("name", ""))}
        if "group" in layer:
            out["group"] = str(layer["group"])
        if "opacity" in layer:
            try:
                out["opacity"] = int(layer["opacity"])
            except (TypeError, ValueError):
                pass
        if "blendMode" in layer:
            out["blendMode"] = str(layer["blendMode"])
        _emit_user_data(
            out,
            color=layer.get("color"),
            data=layer.get("data"),
            properties=layer.get("properties"),
        )
        cels = layer.get("cels")
        if isinstance(cels, list) and cels:
            formatted_cels: List[Dict[str, Any]] = []
            for cel in cels:
                if not isinstance(cel, dict):
                    continue
                cel_out: Dict[str, Any] = {"frame": int(cel.get("frame", 0))}
                if "opacity" in cel:
                    try:
                        cel_out["opacity"] = int(cel["opacity"])
                    except (TypeError, ValueError):
                        pass
                if "zIndex" in cel:
                    try:
                        cel_out["zIndex"] = int(cel["zIndex"])
                    except (TypeError, ValueError):
                        pass
                _emit_user_data(
                    cel_out,
                    color=cel.get("color"),
                    data=cel.get("data"),
                    properties=cel.get("properties"),
                )
                formatted_cels.append(cel_out)
            if formatted_cels:
                out["cels"] = formatted_cels
        return out

    def _build_slices(self) -> List[Dict[str, Any]]:
        """Build ``meta.slices`` from explicit overrides only."""
        return [self._format_slice(slc) for slc in self._format_options.slices]

    @staticmethod
    def _format_slice(slc: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single slice entry to the upstream emit shape."""
        out: Dict[str, Any] = {"name": str(slc.get("name", ""))}
        _emit_user_data(
            out,
            color=slc.get("color"),
            data=slc.get("data"),
            properties=slc.get("properties"),
        )
        keys: List[Dict[str, Any]] = []
        for key in slc.get("keys", []) or []:
            if not isinstance(key, dict):
                continue
            bounds = key.get("bounds")
            if not isinstance(bounds, dict):
                continue
            try:
                key_out: Dict[str, Any] = {
                    "frame": int(key.get("frame", 0)),
                    "bounds": {
                        "x": int(bounds.get("x", 0)),
                        "y": int(bounds.get("y", 0)),
                        "w": int(bounds.get("w", 0)),
                        "h": int(bounds.get("h", 0)),
                    },
                }
            except (TypeError, ValueError):
                continue
            center = key.get("center")
            if isinstance(center, dict):
                try:
                    key_out["center"] = {
                        "x": int(center.get("x", 0)),
                        "y": int(center.get("y", 0)),
                        "w": int(center.get("w", 0)),
                        "h": int(center.get("h", 0)),
                    }
                except (TypeError, ValueError):
                    pass
            pivot = key.get("pivot")
            if isinstance(pivot, dict):
                try:
                    key_out["pivot"] = {
                        "x": int(pivot.get("x", 0)),
                        "y": int(pivot.get("y", 0)),
                    }
                except (TypeError, ValueError):
                    pass
            keys.append(key_out)
        out["keys"] = keys
        return out


__all__ = ["AsepriteExporter", "AsepriteExportOptions"]
