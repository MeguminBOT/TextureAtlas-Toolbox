#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser for Starling and Sparrow XML texture atlas formats.

Sparrow (iOS/Objective-C) and Starling (Flash/AIR Stage3D) share nearly
identical XML schemas. Both use ``<TextureAtlas>`` with ``<SubTexture>``
children. Most exporters label output as "Sparrow/Starling" interchangeably.
Starling is an extension of Sparrow with additional features.

Sparrow-only keys (legacy):
        - ``format`` on TextureAtlas: Pixel format hint (e.g., "RGBA8888", "RGBA4444").
                Only used in Sparrow v1; Sparrow v2 and Starling ignores it.

Starling-only keys:
        - ``scale`` on TextureAtlas: High-DPI support (@2x, @4x).
        - ``pivotX``/``pivotY`` on SubTexture: Custom anchor points (Starling 2.x).

Non-standard keys (not part of official framework specifications):
        - ``flipX``/``flipY``: Some engines (e.g., HaxeFlixel) add these to indicate
                mirrored sprites. Neither Sparrow nor Starling officially support them.
                But there were instances where negative ``width``/``height`` values were used to indicate flipped sprites.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import FileError, FormatError, ParserErrorCode
from utils.utilities import Utilities


class StarlingXmlParser(BaseParser):
    """Parse Starling/Sparrow XML texture atlas metadata.

    Both formats share the same ``<TextureAtlas>`` root with ``<SubTexture>``
    children. Starling extends Sparrow with optional ``rotated`` and pivot
    attributes, but the core structure remains identical.
    """

    FILE_EXTENSIONS = (".xml",)

    def __init__(
        self,
        directory: str,
        xml_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the Starling/Sparrow XML parser.

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

    @staticmethod
    def matches_root(xml_root) -> bool:
        """Check if the XML root matches Starling/Sparrow format.

        Args:
                xml_root: The root element of the parsed XML tree.

        Returns:
                True if the root is a TextureAtlas with SubTexture children.
        """
        return (
            xml_root.tag == "TextureAtlas" and xml_root.find("SubTexture") is not None
        )

    @staticmethod
    def extract_names_from_root(xml_root) -> Set[str]:
        """Extract sprite names from an already-parsed XML root.

        Args:
                xml_root: The root element containing SubTexture children.

        Returns:
                Set of sprite names with trailing digits stripped.
        """
        names = set()
        for subtexture in xml_root.findall(".//SubTexture"):
            name = subtexture.get("name")
            if name:
                name = Utilities.strip_trailing_digits(name)
                names.add(name)
        return names

    @staticmethod
    def parse_from_root(xml_root) -> List[Dict[str, Any]]:
        """Parse sprite metadata from an already-parsed XML root.

        Args:
                xml_root: The root element containing SubTexture children.

        Returns:
                List of sprite dicts with position, dimension, and rotation data.
        """
        sprites = []
        for sprite in xml_root.findall("SubTexture"):
            sprite_data = {
                "name": sprite.get("name"),
                "x": int(sprite.get("x", 0)),
                "y": int(sprite.get("y", 0)),
                "width": int(sprite.get("width", 0)),
                "height": int(sprite.get("height", 0)),
                "frameX": int(sprite.get("frameX", 0)),
                "frameY": int(sprite.get("frameY", 0)),
                "frameWidth": int(sprite.get("frameWidth", sprite.get("width", 0))),
                "frameHeight": int(sprite.get("frameHeight", sprite.get("height", 0))),
                "rotated": sprite.get("rotated", "false") == "true",
            }
            sprites.append(sprite_data)
        return sprites

    @staticmethod
    def parse_xml_data(
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """Parse a Starling/Sparrow XML file and return sprite metadata.

        Args:
                file_path: Path to the XML file.

        Returns:
                List of sprite dicts with position, dimension, and rotation data.
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
        return StarlingXmlParser.parse_from_root(xml_root)
