#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for Egret2D JSON spritesheet metadata."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class Egret2DParser(BaseParser):
    """Parse Egret2D atlas JSON files (simple x/y/w/h schema)."""

    FILE_EXTENSIONS = (".json",)

    def __init__(
        self,
        directory: str,
        json_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the Egret2D parser.

        Args:
            directory: Directory containing the JSON file.
            json_filename: Name of the JSON file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, json_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from the JSON file.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        data = self._load_json()
        frames: Dict[str, Dict[str, Any]] = data.get("frames", {})
        return {Utilities.strip_trailing_digits(name) for name in frames.keys()}

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
    def parse_from_frames(
        cls, frames: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert Egret2D frames dict to normalized sprite list.

        Args:
            frames: Dictionary mapping sprite names to {x, y, w, h} entries.

        Returns:
            List of normalized sprite dicts.
        """
        sprites: List[Dict[str, Any]] = []
        for sprite_name, entry in frames.items():
            x = int(entry.get("x", 0))
            y = int(entry.get("y", 0))
            width = int(entry.get("w", 0))
            height = int(entry.get("h", 0))

            sprite_data = {
                "name": sprite_name,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "frameX": 0,
                "frameY": 0,
                "frameWidth": width,
                "frameHeight": height,
                "rotated": False,
            }
            sprites.append(sprite_data)
        return sprites

    @staticmethod
    def parse_json_data(file_path: str) -> List[Dict[str, Any]]:
        """Parse an Egret2D JSON file and return sprite metadata.

        Args:
            file_path: Path to the JSON file.

        Returns:
            List of sprite dicts with position and dimension data.
        """
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        frames = data.get("frames", {})
        return Egret2DParser.parse_from_frames(frames)


__all__ = ["Egret2DParser"]
