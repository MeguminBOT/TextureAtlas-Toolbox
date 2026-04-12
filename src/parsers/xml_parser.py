#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dispatcher that selects the proper XML spritesheet parser by content."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Set, Type

from parsers.base_parser import BaseParser
from parsers.parser_types import FormatError, ParserErrorCode
from parsers.starling_xml_parser import StarlingXmlParser
from parsers.texture_packer_xml_parser import TexturePackerXmlParser


FormatParser = Type[BaseParser]


class XmlParser(BaseParser):
    """Entry point for XML spritesheet parsing.

    Loads the XML once, inspects its structure, and delegates to the first
    format-specific parser that reports compatibility (currently
    :class:`StarlingXmlParser`). This keeps external imports stable while
    allowing new XML dialects to plug in later.
    """

    FILE_EXTENSIONS = (".xml",)
    FORMAT_PARSERS: List[FormatParser] = [TexturePackerXmlParser, StarlingXmlParser]

    def __init__(
        self,
        directory: str,
        xml_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the XML parser dispatcher.

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
        """
        file_path, xml_root = self._load_xml()
        parser_cls = self._detect_parser(xml_root, file_path)
        extractor = getattr(parser_cls, "extract_names_from_root", None)
        if callable(extractor):
            return extractor(xml_root)

        parser = parser_cls(self.directory, self.filename, self.name_callback)
        return parser.extract_names()

    @classmethod
    def _detect_parser(
        cls,
        xml_root,
        file_path: Optional[str] = None,
    ) -> FormatParser:
        """Detect the correct parser class for an XML root element.

        Args:
            xml_root: The parsed XML root element.
            file_path: Optional path for error messages.

        Returns:
            The matching parser class.

        Raises:
            ValueError: If no parser matches the XML structure.
        """
        for parser_cls in cls.FORMAT_PARSERS:
            matcher = getattr(parser_cls, "matches_root", None)
            if matcher and matcher(xml_root):
                return parser_cls

        raise FormatError(
            ParserErrorCode.UNSUPPORTED_FORMAT,
            f"Unsupported XML spritesheet format in file: {file_path or cls.__name__}",
            file_path=file_path,
        )

    def _load_xml(self):
        """Load and parse the XML file.

        Returns:
            A tuple (file_path, xml_root).
        """
        file_path = os.path.join(self.directory, self.filename)
        tree = ET.parse(file_path)
        return file_path, tree.getroot()

    @staticmethod
    def parse_xml_data(
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """Parse an XML file and return sprite metadata.

        Detects the XML dialect and delegates to the appropriate parser.

        Args:
            file_path: Path to the XML file.

        Returns:
            List of sprite dicts with position, dimension, and rotation data.
        """
        tree = ET.parse(file_path)
        xml_root = tree.getroot()
        parser_cls = XmlParser._detect_parser(xml_root, file_path)
        parse_from_root = getattr(parser_cls, "parse_from_root", None)
        if callable(parse_from_root):
            return parse_from_root(xml_root)
        return parser_cls.parse_xml_data(file_path)


__all__ = ["XmlParser", "StarlingXmlParser", "TexturePackerXmlParser"]
