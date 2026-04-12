#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for generic JSON array atlas metadata."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class JsonArrayAtlasParser(BaseParser):
    """Parse atlas JSON where ``frames`` is a list of entries with frame metadata."""

    FILE_EXTENSIONS = (".json",)

    def __init__(
        self,
        directory: str,
        json_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the JSON array parser.

        Args:
            directory: Directory containing the JSON file.
            json_filename: Name of the JSON file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, json_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from the JSON file.

        Returns:
            Set of filenames with trailing digits stripped.
        """
        data = self._load_json()
        frames: List[Dict[str, Any]] = data.get("frames", [])
        names: Set[str] = set()
        for entry in frames:
            filename = entry.get("filename")
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
    def parse_from_frames(cls, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert a frames array to normalized sprite list.

        Handles rotated sprites by swapping width/height so consumers always
        see the original (un-rotated) dimensions.

        Args:
            frames: List of frame entries with nested frame/sourceSize dicts.

        Returns:
            List of normalized sprite dicts with pivot information.
        """
        sprites: List[Dict[str, Any]] = []
        for entry in frames:
            filename = entry.get("filename", "")
            frame = entry.get("frame", {})
            frame_x = int(frame.get("x", 0))
            frame_y = int(frame.get("y", 0))
            frame_w = int(frame.get("w", 0))
            frame_h = int(frame.get("h", 0))

            sprite_source = entry.get("spriteSourceSize", {})
            source_size = entry.get("sourceSize", {})
            rotated = bool(entry.get("rotated", False))

            # When rotated, atlas stores swapped dimensions — restore originals
            if rotated:
                frame_w, frame_h = frame_h, frame_w

            sprite_data: Dict[str, Any] = {
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

            duration = entry.get("duration")
            if duration is not None:
                sprite_data["duration"] = int(duration)

            sprites.append(sprite_data)
        return sprites

    @classmethod
    def parse_frame_tags(cls, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract frameTags from the meta block.

        Supports ``forward``, ``reverse``, and ``pingpong`` directions.

        Args:
            data: Full parsed JSON document (with ``meta`` key).

        Returns:
            List of tag dicts with ``name``, ``from``, ``to``, ``direction``.
        """
        meta = data.get("meta", {})
        raw_tags = meta.get("frameTags", [])
        tags: List[Dict[str, Any]] = []
        for tag in raw_tags:
            tags.append(
                {
                    "name": tag.get("name", ""),
                    "from": int(tag.get("from", 0)),
                    "to": int(tag.get("to", 0)),
                    "direction": tag.get("direction", "forward"),
                }
            )
        return tags

    @staticmethod
    def parse_json_data(file_path: str) -> List[Dict[str, Any]]:
        """Parse a JSON array atlas file and return sprite metadata.

        Also parses ``meta.frameTags`` when present, attaching an
        ``animation`` key to each sprite that falls within a tag range.

        Args:
            file_path: Path to the JSON file.

        Returns:
            List of sprite dicts with position, dimension, and pivot data.
        """
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        frames = data.get("frames", [])
        sprites = JsonArrayAtlasParser.parse_from_frames(frames)

        # Apply frameTags as animation names
        tags = JsonArrayAtlasParser.parse_frame_tags(data)
        if tags:
            for tag in tags:
                for i, sprite in enumerate(sprites):
                    if tag["from"] <= i <= tag["to"]:
                        sprite["animation"] = tag["name"]
                        sprite["direction"] = tag["direction"]

        return sprites


__all__ = ["JsonArrayAtlasParser"]
