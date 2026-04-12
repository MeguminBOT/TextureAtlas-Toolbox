#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for UIKit-compatible plist sprite sheet metadata."""

from __future__ import annotations

import os
import plistlib
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class UIKitPlistParser(BaseParser):
    """Parse ``.plist`` atlases that store scalar frame keys (x/y/w/h/oX/oY/oW/oH)."""

    FILE_EXTENSIONS = (".plist",)

    def __init__(
        self,
        directory: str,
        plist_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the UIKit plist parser.

        Args:
            directory: Directory containing the plist file.
            plist_filename: Name of the plist file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, plist_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from the plist file.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        plist_data = self._load_plist()
        frames: Dict[str, Dict[str, Any]] = plist_data.get("frames", {})
        names: Set[str] = set()
        for sprite_name in frames.keys():
            names.add(Utilities.strip_trailing_digits(sprite_name))
        return names

    def _load_plist(self) -> Dict[str, Any]:
        """Load and parse the plist file.

        Returns:
            Parsed plist data as a dictionary.

        Raises:
            FileError: If the file cannot be found or read.
            FormatError: If the file contains invalid plist data.
        """
        file_path = os.path.join(self.directory, self.filename)
        try:
            with open(file_path, "rb") as plist_file:
                return plistlib.load(plist_file)
        except FileNotFoundError:
            raise FileError(
                ParserErrorCode.FILE_NOT_FOUND,
                f"File not found: {file_path}",
                file_path=file_path,
            )
        except OSError as exc:
            raise FileError(
                ParserErrorCode.FILE_READ_ERROR,
                str(exc),
                file_path=file_path,
            )
        except (plistlib.InvalidFileException, ValueError) as exc:
            raise FormatError(
                ParserErrorCode.INVALID_FORMAT,
                f"Invalid plist: {exc}",
                file_path=file_path,
            )

    @classmethod
    def parse_from_frames(
        cls, frames: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert a plist frames dict to normalized sprite list.

        Args:
            frames: Dictionary mapping sprite names to scalar frame keys.

        Returns:
            List of normalized sprite dicts with position and trim data.
        """
        sprites: List[Dict[str, Any]] = []
        for sprite_name, sprite_info in frames.items():
            x = cls._parse_number(sprite_info.get("x"))
            y = cls._parse_number(sprite_info.get("y"))
            width = cls._parse_number(sprite_info.get("w"))
            height = cls._parse_number(sprite_info.get("h"))
            offset_x = cls._parse_number(sprite_info.get("oX"))
            offset_y = cls._parse_number(sprite_info.get("oY"))
            original_w = cls._parse_number(sprite_info.get("oW")) or width
            original_h = cls._parse_number(sprite_info.get("oH")) or height

            sprite_data = {
                "name": sprite_name,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "frameX": -offset_x,
                "frameY": -offset_y,
                "frameWidth": original_w,
                "frameHeight": original_h,
                "rotated": False,
            }
            sprites.append(sprite_data)
        return sprites

    @staticmethod
    def parse_plist_data(file_path: str) -> List[Dict[str, Any]]:
        """Parse a UIKit plist atlas file and return sprite metadata.

        Args:
            file_path: Path to the plist file.

        Returns:
            List of sprite dicts with position and trim data.
        """
        with open(file_path, "rb") as plist_file:
            plist_data = plistlib.load(plist_file)
        frames = plist_data.get("frames", {})
        return UIKitPlistParser.parse_from_frames(frames)

    @staticmethod
    def _parse_number(value: Any) -> int:
        """Parse an integer from a plist value.

        Args:
            value: An int, float, or numeric string.

        Returns:
            The parsed integer, or 0 on failure.
        """
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


__all__ = ["UIKitPlistParser"]
