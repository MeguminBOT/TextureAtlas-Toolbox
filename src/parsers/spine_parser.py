#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for Spine atlas text format."""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, ParserErrorCode
from utils.utilities import Utilities


class SpineAtlasParser(BaseParser):
    """Parse Spine ``.atlas`` text files."""

    FILE_EXTENSIONS = (".atlas",)

    def __init__(
        self,
        directory: str,
        atlas_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the Spine atlas parser.

        Args:
            directory: Directory containing the atlas file.
            atlas_filename: Name of the atlas file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, atlas_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from the atlas file.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        sprites = self.parse_atlas_file(os.path.join(self.directory, self.filename))
        return {Utilities.strip_trailing_digits(sprite["name"]) for sprite in sprites}

    @staticmethod
    def parse_atlas_file(file_path: str) -> List[Dict[str, int]]:
        """Parse a Spine .atlas text file and return sprite metadata.

        Args:
            file_path: Path to the .atlas file.

        Returns:
            List of sprite dicts with position, dimension, and rotation data.
        """
        sprites: List[Dict[str, int]] = []
        try:
            with open(file_path, "r", encoding="utf-8") as atlas_file:
                lines = [line.strip() for line in atlas_file if line.strip()]
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

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if ":" in line or "," in line or line.lower().startswith("size"):
                idx += 1
                continue

            name = line
            if idx + 4 >= len(lines):
                break

            rotate_line = lines[idx + 1]
            xy_line = lines[idx + 2]
            size_line = lines[idx + 3]
            orig_line = lines[idx + 4]

            rotate = "true" in rotate_line.split(":", 1)[-1].strip().lower()
            xy_values = SpineAtlasParser._parse_pair(xy_line)
            size_values = SpineAtlasParser._parse_pair(size_line)
            orig_values = SpineAtlasParser._parse_pair(orig_line)

            x, y = xy_values
            width, height = size_values
            orig_w, orig_h = orig_values

            sprite_data = {
                "name": name,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "frameX": 0,
                "frameY": 0,
                "frameWidth": orig_w or width,
                "frameHeight": orig_h or height,
                "rotated": rotate,
            }
            sprites.append(sprite_data)
            idx += 5

        return sprites

    @staticmethod
    def _parse_pair(line: str) -> List[int]:
        """Parse a colon-separated line with two comma-delimited integers.

        Args:
            line: A line like ``xy: 10, 20`` or ``10, 20``.

        Returns:
            A two-element list of integers, or [0, 0] on failure.
        """
        if ":" in line:
            _, values = line.split(":", 1)
        else:
            values = line
        parts = values.split(",")
        if len(parts) >= 2:
            try:
                return [int(part.strip()) for part in parts[:2]]
            except ValueError:
                return [0, 0]
        return [0, 0]


__all__ = ["SpineAtlasParser"]
