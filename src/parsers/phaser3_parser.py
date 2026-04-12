#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for Phaser 3 atlas JSON metadata."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class Phaser3Parser(BaseParser):
    """Parse Phaser 3 texture atlas JSON (``textures[*].frames[]`` schema)."""

    FILE_EXTENSIONS = (".json",)

    def __init__(
        self,
        directory: str,
        json_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the Phaser 3 parser.

        Args:
            directory: Directory containing the JSON file.
            json_filename: Name of the JSON file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, json_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from textures.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        data = self._load_json()
        names: Set[str] = set()
        for texture in data.get("textures", []):
            for frame_entry in texture.get("frames", []):
                filename = frame_entry.get("filename")
                if filename:
                    names.add(Utilities.strip_trailing_digits(filename))
        return names

    def _load_json(self) -> Dict[str, Any]:
        """Load and parse the JSON file.

        Returns:
            Parsed JSON data as a dictionary.

        Raises:
            FileError: If the file cannot be found or read.
            FormatError: If the file contains invalid JSON.
        """
        file_path = os.path.join(self.directory, self.filename)
        try:
            with open(file_path, "r", encoding="utf-8") as json_file:
                return json.load(json_file)
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
        except json.JSONDecodeError as exc:
            raise FormatError(
                ParserErrorCode.INVALID_FORMAT,
                f"Invalid JSON: {exc}",
                file_path=file_path,
            )

    @classmethod
    def parse_from_textures(
        cls, textures: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert a textures list to normalized sprite list.

        Args:
            textures: List of texture dicts containing frames arrays.

        Returns:
            List of normalized sprite dicts with position/trim data.
        """
        sprites: List[Dict[str, Any]] = []
        for texture in textures:
            for frame_entry in texture.get("frames", []):
                frame = frame_entry.get("frame", {})
                frame_x = int(frame.get("x", 0))
                frame_y = int(frame.get("y", 0))
                frame_w = int(frame.get("w", 0))
                frame_h = int(frame.get("h", 0))

                source_size = frame_entry.get("sourceSize", {})
                sprite_source = frame_entry.get("spriteSourceSize", {})
                rotated = bool(frame_entry.get("rotated", False))

                sprite_data = {
                    "name": frame_entry.get("filename", ""),
                    "x": frame_x,
                    "y": frame_y,
                    "width": frame_w,
                    "height": frame_h,
                    "frameX": -int(sprite_source.get("x", 0)),
                    "frameY": -int(sprite_source.get("y", 0)),
                    "frameWidth": int(source_size.get("w", frame_w)),
                    "frameHeight": int(source_size.get("h", frame_h)),
                    "rotated": rotated,
                }
                sprites.append(sprite_data)
        return sprites

    @staticmethod
    def parse_json_data(file_path: str) -> List[Dict[str, Any]]:
        """Parse a Phaser 3 atlas file and return sprite metadata.

        Args:
            file_path: Path to the JSON file.

        Returns:
            List of sprite dicts with position, dimension, and rotation data.
        """
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        textures = data.get("textures", [])
        return Phaser3Parser.parse_from_textures(textures)


__all__ = ["Phaser3Parser"]
