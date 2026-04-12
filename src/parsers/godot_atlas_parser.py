#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for Godot Atlas JSON metadata."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class GodotAtlasParser(BaseParser):
    """Parse Godot atlas JSON files that describe textures and sprite regions."""

    FILE_EXTENSIONS = (".tpsheet", ".tpset")

    def __init__(
        self,
        directory: str,
        json_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the Godot atlas parser.

        Args:
            directory: Directory containing the JSON file.
            json_filename: Name of the JSON file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, json_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique sprite base names from all textures.

        Returns:
            Set of sprite filenames with trailing digits stripped.
        """
        data = self._load_json()
        sprites = self._iter_sprites(data)
        return {
            Utilities.strip_trailing_digits(sprite["filename"]) for sprite in sprites
        }

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
        """Convert Godot textures list to normalized sprite list.

        Args:
            textures: List of texture dicts, each containing a ``sprites`` list.

        Returns:
            List of normalized sprite dicts from all textures.
        """
        sprites: List[Dict[str, Any]] = []
        for texture in textures:
            for sprite in texture.get("sprites", []):
                region = sprite.get("region", {})
                x = int(region.get("x", 0))
                y = int(region.get("y", 0))
                width = int(region.get("w", 0))
                height = int(region.get("h", 0))

                sprite_data = {
                    "name": sprite.get("filename", ""),
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
        """Parse a Godot atlas JSON file and return sprite metadata.

        Args:
            file_path: Path to the JSON file.

        Returns:
            List of sprite dicts with position and dimension data.
        """
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        textures = data.get("textures", [])
        return GodotAtlasParser.parse_from_textures(textures)

    @staticmethod
    def _iter_sprites(data: Dict[str, Any]):
        """Yield all sprites from all textures in the data.

        Args:
            data: Parsed JSON data containing ``textures`` list.

        Yields:
            Each sprite dict from each texture.
        """
        for texture in data.get("textures", []):
            for sprite in texture.get("sprites", []):
                yield sprite


__all__ = ["GodotAtlasParser"]
