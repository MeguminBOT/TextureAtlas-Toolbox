#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for Paper2D/Unreal atlas JSON metadata."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class Paper2DParser(BaseParser):
    """Parse Paper2D (Unreal) JSON atlases (hash-style frames)."""

    FILE_EXTENSIONS = (".paper2dsprites",)

    def __init__(
        self,
        directory: str,
        json_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the Paper2D parser.

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
        """Convert a frames hash to normalized sprite list.

        Args:
            frames: Dictionary mapping sprite names to frame metadata.

        Returns:
            List of normalized sprite dicts with pivot information.
        """
        sprites: List[Dict[str, Any]] = []
        for filename, entry in frames.items():
            frame = entry.get("frame", {})
            frame_x = int(frame.get("x", 0))
            frame_y = int(frame.get("y", 0))
            frame_w = int(frame.get("w", 0))
            frame_h = int(frame.get("h", 0))

            sprite_source = entry.get("spriteSourceSize", {})
            source_size = entry.get("sourceSize", {})
            rotated = bool(entry.get("rotated", False))

            sprite_data = {
                "name": filename,
                "x": frame_x,
                "y": frame_y,
                "width": frame_w,
                "height": frame_h,
                "frameX": -int(sprite_source.get("x", 0)),
                "frameY": -int(sprite_source.get("y", 0)),
                "frameWidth": int(source_size.get("w", frame_w)),
                "frameHeight": int(source_size.get("h", frame_h)),
                "rotated": rotated,
                "pivotX": float(entry.get("pivot", {}).get("x", 0.5)),
                "pivotY": float(entry.get("pivot", {}).get("y", 0.5)),
            }
            sprites.append(sprite_data)
        return sprites

    @staticmethod
    def parse_json_data(file_path: str) -> List[Dict[str, Any]]:
        """Parse a Paper2D atlas file and return sprite metadata.

        Args:
            file_path: Path to the JSON file.

        Returns:
            List of sprite dicts with position, dimension, and pivot data.
        """
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        frames = data.get("frames", {})
        return Paper2DParser.parse_from_frames(frames)


__all__ = ["Paper2DParser"]
