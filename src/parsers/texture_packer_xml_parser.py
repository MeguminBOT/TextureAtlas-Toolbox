#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""TexturePacker XML parser (``<sprite>`` nodes with shorthand attributes)."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class TexturePackerXmlParser(BaseParser):
    """Parse TexturePacker XML exports that use ``<sprite>`` elements."""

    FILE_EXTENSIONS = (".xml",)

    SPRITE_TAG = "sprite"

    def __init__(
        self,
        directory: str,
        xml_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the TexturePacker XML parser.

        Args:
            directory: Directory containing the XML file.
            xml_filename: Name of the XML file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, xml_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Extract unique animation/sprite base names from the XML file.

        Returns:
            Set of sprite names with trailing digits stripped.

        Raises:
            FileError: If the file cannot be found or read.
            FormatError: If the file contains invalid XML.
        """
        file_path = os.path.join(self.directory, self.filename)
        try:
            tree = ET.parse(file_path)
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
        except ET.ParseError as exc:
            raise FormatError(
                ParserErrorCode.INVALID_FORMAT,
                f"Invalid XML: {exc}",
                file_path=file_path,
            )
        xml_root = tree.getroot()
        return self.extract_names_from_root(xml_root)

    @classmethod
    def matches_root(cls, xml_root) -> bool:
        """Check if the XML root matches TexturePacker sprite format.

        Args:
            xml_root: The root element of the parsed XML tree.

        Returns:
            True if root is TextureAtlas with sprite children but no SubTexture.
        """
        return (
            xml_root.tag == "TextureAtlas"
            and xml_root.find(cls.SPRITE_TAG) is not None
            and xml_root.find("SubTexture") is None
        )

    @staticmethod
    def extract_names_from_root(xml_root) -> Set[str]:
        """Extract sprite names from an already-parsed XML root.

        Args:
            xml_root: The root element containing sprite children.

        Returns:
            Set of sprite names with trailing digits stripped.
        """
        names: Set[str] = set()
        for sprite in xml_root.findall(".//sprite"):
            name = sprite.get("n") or sprite.get("name")
            if name:
                names.add(Utilities.strip_trailing_digits(name))
        return names

    @classmethod
    def parse_from_root(cls, xml_root) -> List[Dict[str, Any]]:
        """Parse sprite metadata from an already-parsed XML root.

        Args:
            xml_root: The root element containing sprite children.

        Returns:
            List of sprite dicts with position, dimension, and pivot data.
        """
        sprites: List[Dict[str, Any]] = []
        for sprite in xml_root.findall("sprite"):
            sprite_data = {
                "name": sprite.get("n") or sprite.get("name"),
                "x": cls._parse_int(sprite.get("x"), default=0),
                "y": cls._parse_int(sprite.get("y"), default=0),
                "width": cls._parse_int(sprite.get("w"), default=0),
                "height": cls._parse_int(sprite.get("h"), default=0),
                "frameX": cls._parse_int(sprite.get("oX"), default=0),
                "frameY": cls._parse_int(sprite.get("oY"), default=0),
                "frameWidth": cls._parse_int(sprite.get("oW"), default=None),
                "frameHeight": cls._parse_int(sprite.get("oH"), default=None),
                "rotated": cls._parse_bool(sprite.get("r")),
                "pivotX": cls._parse_float(sprite.get("pX"), 0.5),
                "pivotY": cls._parse_float(sprite.get("pY"), 0.5),
            }
            if sprite_data["frameWidth"] is None:
                sprite_data["frameWidth"] = sprite_data["width"]
            if sprite_data["frameHeight"] is None:
                sprite_data["frameHeight"] = sprite_data["height"]
            sprites.append(sprite_data)
        return sprites

    @staticmethod
    def _parse_int(value, default: Optional[int] = 0) -> Optional[int]:
        """Parse an integer from a string value.

        Args:
            value: The string value to parse.
            default: Value returned on failure.

        Returns:
            The parsed integer or default.
        """
        if value is None:
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_float(value, default: float = 0.0) -> float:
        """Parse a float from a string value.

        Args:
            value: The string value to parse.
            default: Value returned on failure.

        Returns:
            The parsed float or default.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_bool(value) -> bool:
        """Parse a boolean from a string value.

        Args:
            value: The string value (e.g., ``'y'``, ``'true'``, ``'1'``).

        Returns:
            True if the value indicates a truthy string.
        """
        if value is None:
            return False
        return str(value).lower() in {"y", "yes", "true", "1"}

    @staticmethod
    def parse_xml_data(file_path: str) -> List[Dict[str, Any]]:
        """Parse a TexturePacker XML file and return sprite metadata.

        Args:
            file_path: Path to the XML file.

        Returns:
            List of sprite dicts with position, dimension, and pivot data.
        """
        try:
            tree = ET.parse(file_path)
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
        except ET.ParseError as exc:
            raise FormatError(
                ParserErrorCode.INVALID_FORMAT,
                f"Invalid XML: {exc}",
                file_path=file_path,
            )
        xml_root = tree.getroot()
        return TexturePackerXmlParser.parse_from_root(xml_root)
