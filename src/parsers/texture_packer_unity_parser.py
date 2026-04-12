#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for TexturePacker Unity text format."""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import ContentError, FileError, ParserErrorCode
from utils.utilities import Utilities


class TexturePackerUnityParser(BaseParser):
    """Parse TexturePacker's Unity export (semicolon-delimited rows)."""

    FILE_EXTENSIONS = (".tpsheet",)

    def __init__(
        self,
        directory: str,
        txt_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the TexturePacker Unity parser.

        Args:
            directory: Directory containing the text file.
            txt_filename: Name of the text file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, txt_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from the text file.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        sprites = self.parse_text_file(os.path.join(self.directory, self.filename))
        return {Utilities.strip_trailing_digits(sprite["name"]) for sprite in sprites}

    @staticmethod
    def parse_text_file(file_path: str) -> List[Dict[str, int]]:
        """Parse a TexturePacker Unity export file.

        Args:
            file_path: Path to the text file.

        Returns:
            List of sprite dicts with position and dimension data.
        """
        sprites: List[Dict[str, int]] = []
        try:
            data_file = open(file_path, "r", encoding="utf-8")
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
        with data_file:
            for line in data_file:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(":"):
                    continue
                parts = [token.strip() for token in line.split(";") if token.strip()]
                if len(parts) < 5:
                    continue
                name = parts[0]
                try:
                    x = int(float(parts[1]))
                    y = int(float(parts[2]))
                    width = int(float(parts[3]))
                    height = int(float(parts[4]))
                except (ValueError, IndexError) as exc:
                    raise ContentError(
                        ParserErrorCode.INVALID_SPRITE_DATA,
                        f"Non-numeric coordinate in sprite '{name}': {exc}",
                        file_path=file_path,
                    )

                sprite_data = {
                    "name": name,
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


__all__ = ["TexturePackerUnityParser"]
