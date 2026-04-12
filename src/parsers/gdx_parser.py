#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for libGDX TexturePacker atlas format.

Handles both the modern format (using ``bounds`` and ``offsets`` fields)
and the legacy format (using separate ``xy``, ``size``, ``orig``,
``offset`` fields).

Modern format example::

    atlas.png
    size: 512, 512
    format: RGBA8888
    filter: Linear, Linear
    repeat: none
    sprite
      bounds: 0, 0, 64, 64
      offsets: 0, 0, 64, 64
      rotate: false
      index: -1

Legacy format example::

    atlas.png
    size: 512, 512
    format: RGBA8888
    filter: Linear, Linear
    repeat: none
    sprite
      rotate: false
      xy: 0, 0
      size: 64, 64
      orig: 64, 64
      offset: 0, 0
      index: -1
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Set, Tuple

from parsers.base_parser import BaseParser
from parsers.parser_types import ContentError, FileError, ParserErrorCode
from utils.utilities import Utilities


class GdxAtlasParser(BaseParser):
    """Parse libGDX TexturePacker ``.atlas`` files.

    Supports both the modern (``bounds``/``offsets``) and legacy
    (``xy``/``size``/``orig``/``offset``) field layouts produced by
    the libGDX TexturePacker tool.
    """

    FILE_EXTENSIONS = (".atlas",)

    def __init__(
        self,
        directory: str,
        atlas_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(directory, atlas_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique sprite base names from the atlas file.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        sprites = self.parse_atlas_file(os.path.join(self.directory, self.filename))
        return {Utilities.strip_trailing_digits(sprite["name"]) for sprite in sprites}

    @staticmethod
    def parse_atlas_file(file_path: str) -> List[Dict[str, int]]:
        """Parse a libGDX TexturePacker .atlas file.

        Args:
            file_path: Path to the .atlas file.

        Returns:
            List of sprite dicts with position, dimension, and rotation data.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise FileError(
                ParserErrorCode.FILE_NOT_FOUND,
                f"File not found: {file_path}",
                file_path=file_path,
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise FileError(
                ParserErrorCode.FILE_READ_ERROR,
                str(exc),
                file_path=file_path,
            )

        sprites: List[Dict[str, int]] = []
        idx = 0
        page_active = False

        while idx < len(lines):
            line = lines[idx].rstrip("\n\r")

            # Blank line signals end of a page block
            if not line.strip():
                page_active = False
                idx += 1
                continue

            # If no page is active, this line is a page filename
            if not page_active:
                page_active = True
                idx += 1
                # Read page header fields (all have colons)
                while idx < len(lines):
                    header_line = lines[idx].rstrip("\n\r")
                    if not header_line.strip():
                        break
                    # Page header fields are NOT indented in modern format,
                    # but have a colon. Region names don't have colons.
                    entry = GdxAtlasParser._read_entry(header_line)
                    if entry is None:
                        # This line has no colon → first region name
                        break
                    idx += 1
                continue

            # Region name: not indented (or trimmed), no colon
            entry = GdxAtlasParser._read_entry(line)
            if entry is not None:
                # This is a key:value line at page level, skip it
                idx += 1
                continue

            region_name = line.strip()
            idx += 1

            # Collect region fields (indented key:value pairs)
            fields: Dict[str, List[str]] = {}
            while idx < len(lines):
                field_line = lines[idx].rstrip("\n\r")
                if not field_line.strip():
                    break
                entry = GdxAtlasParser._read_entry(field_line)
                if entry is None:
                    # Next region name
                    break
                key, values = entry
                fields[key] = values
                idx += 1

            sprite = GdxAtlasParser._build_sprite(region_name, fields)
            sprites.append(sprite)

        return sprites

    @staticmethod
    def _read_entry(line: str) -> Optional[Tuple[str, List[str]]]:
        """Parse a key: value1, value2, ... line.

        Args:
            line: A line from the atlas file.

        Returns:
            Tuple of (key, [values]) or None if no colon found.
        """
        stripped = line.strip()
        colon = stripped.find(":")
        if colon == -1:
            return None
        key = stripped[:colon].strip()
        rest = stripped[colon + 1 :].strip()
        values = [v.strip() for v in rest.split(",")]
        return (key, values)

    @staticmethod
    def _build_sprite(
        name: str,
        fields: Dict[str, List[str]],
    ) -> Dict[str, int]:
        """Build a sprite data dict from parsed fields.

        Handles both modern (bounds/offsets) and legacy
        (xy/size/orig/offset) field layouts.

        Args:
            name: Region name.
            fields: Parsed key-value fields for this region.

        Returns:
            Sprite data dict.
        """
        x = y = 0
        width = height = 0
        offset_x = offset_y = 0
        orig_w = orig_h = 0
        rotated = False
        index = -1

        try:
            # Modern combined fields
            if "bounds" in fields:
                vals = fields["bounds"]
                x = int(vals[0])
                y = int(vals[1])
                width = int(vals[2]) if len(vals) > 2 else 0
                height = int(vals[3]) if len(vals) > 3 else 0

            # Legacy separate fields
            if "xy" in fields:
                vals = fields["xy"]
                x = int(vals[0])
                y = int(vals[1]) if len(vals) > 1 else 0
            if "size" in fields:
                vals = fields["size"]
                width = int(vals[0])
                height = int(vals[1]) if len(vals) > 1 else 0

            # Modern combined offsets
            if "offsets" in fields:
                vals = fields["offsets"]
                offset_x = int(vals[0])
                offset_y = int(vals[1]) if len(vals) > 1 else 0
                orig_w = int(vals[2]) if len(vals) > 2 else width
                orig_h = int(vals[3]) if len(vals) > 3 else height

            # Legacy separate fields
            if "offset" in fields:
                vals = fields["offset"]
                offset_x = int(vals[0])
                offset_y = int(vals[1]) if len(vals) > 1 else 0
            if "orig" in fields:
                vals = fields["orig"]
                orig_w = int(vals[0])
                orig_h = int(vals[1]) if len(vals) > 1 else 0
        except (ValueError, IndexError) as exc:
            raise ContentError(
                ParserErrorCode.INVALID_SPRITE_DATA,
                f"Non-numeric coordinate in sprite '{name}': {exc}",
            )

        # Rotation
        if "rotate" in fields:
            val = fields["rotate"][0].lower()
            if val == "true":
                rotated = True
            elif val != "false":
                # Degrees value; 90 means rotated
                try:
                    rotated = int(val) == 90
                except ValueError:
                    rotated = False

        # Index
        if "index" in fields:
            try:
                index = int(fields["index"][0])
            except ValueError:
                index = -1

        # When rotated, the stored width/height are swapped in the atlas
        if rotated:
            width, height = height, width

        # If orig not set, default to packed dimensions
        if orig_w == 0:
            orig_w = width
        if orig_h == 0:
            orig_h = height

        return {
            "name": name,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "frameX": -offset_x,
            "frameY": -offset_y,
            "frameWidth": orig_w,
            "frameHeight": orig_h,
            "rotated": rotated,
            "index": index,
        }

    @staticmethod
    def is_modern_format(file_path: str) -> bool:
        """Check whether an atlas file uses the modern GDX format.

        The modern format uses ``bounds:`` and/or ``offsets:`` fields.

        Args:
            file_path: Path to the .atlas file.

        Returns:
            True if modern format markers are found.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("bounds:") or stripped.startswith(
                        "offsets:"
                    ):
                        return True
        except (OSError, UnicodeDecodeError):
            pass
        return False


__all__ = ["GdxAtlasParser"]
