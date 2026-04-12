#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Base class for all spritesheet/atlas parsers.

Provides the abstract interface that all parsers must implement, plus
shared utilities for error handling and sprite normalization.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from parsers.parser_types import (
    ContentError,  # noqa: F401
    FileError,
    FormatError,
    ParseResult,
    ParserError,
    ParserErrorCode,
    SpriteData,
    normalize_sprite,
    validate_sprites,
)


class BaseParser(ABC):
    """Abstract base class for spritesheet/atlas metadata parsers.

    Subclasses must implement:
        - extract_names(): Return animation/sprite names for UI population.
        - parse_file() (class method): Parse file and return ParseResult.

    Class attributes that should be defined:
        - FILE_EXTENSIONS: Tuple of supported file extensions (e.g., (".json",)).
    """

    FILE_EXTENSIONS: Tuple[str, ...] = ()

    def __init__(
        self,
        directory: str,
        filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the parser with file location and optional callback.

        Args:
            directory: Directory containing the metadata file.
            filename: Name of the metadata file.
            name_callback: Optional callback invoked for each extracted name.
        """
        self.directory = directory
        self.filename = filename
        self.name_callback = name_callback

    @property
    def file_path(self) -> str:
        """Return the full path to the metadata file."""
        return os.path.join(self.directory, self.filename)

    @abstractmethod
    def extract_names(self) -> Set[str]:
        """Extract animation/sprite names for UI population.

        Returns:
            Set of unique animation or sprite base names.
        """
        pass

    def extract_raw_sprite_names(self) -> list[str]:
        """Return raw sprite names before any trailing-digit stripping.

        Used by :meth:`get_data` when *smart_grouping* is enabled so that
        ``group_names_by_animation`` can analyse the full numeric suffixes.

        The default implementation re-parses the file via :meth:`parse_file`
        and collects the ``name`` field from each sprite.  Subclasses may
        override this for a cheaper path.

        Returns:
            List of raw sprite name strings, or empty if unavailable.
        """
        try:
            result = self.__class__.parse_file(self.file_path)
            return [s["name"] for s in result.sprites if s.get("name")]
        except (FileNotFoundError, OSError) as exc:
            print(
                f"[{self.__class__.__name__}] Could not read file for "
                f"raw sprite names: {exc}"
            )
            return []
        except ParserError as exc:
            print(
                f"[{self.__class__.__name__}] Parser error extracting "
                f"raw sprite names: {exc}"
            )
            return []
        except NotImplementedError:
            return []

    def get_data(self, smart_grouping: bool = False) -> Set[str]:
        """Extract names and invoke callback for each.

        When *smart_grouping* is ``True``, raw sprite names are analysed
        with :func:`~utils.utilities.Utilities.group_names_by_animation`
        so that sub-indexed sequences produce distinct animation entries.

        Args:
            smart_grouping: Use batch-aware grouping instead of simple
                trailing-digit stripping.

        Returns:
            Set of extracted names.
        """
        if smart_grouping:
            raw_names = self.extract_raw_sprite_names()
            if raw_names:
                from utils.utilities import Utilities

                groups = Utilities.group_names_by_animation(raw_names)
                names = set(groups.keys())
                if self.name_callback:
                    for name in names:
                        self.name_callback(name)
                return names

        names = self.extract_names()
        if self.name_callback:
            for name in names:
                self.name_callback(name)
        return names

    @classmethod
    def parse_file(cls, file_path: str) -> ParseResult:
        """Parse a file and return structured results with error handling.

        This is the unified entry point for extraction pipelines.
        Subclasses should override this method to provide format-specific parsing.

        Args:
            file_path: Absolute path to the metadata file.

        Returns:
            ParseResult containing sprites, warnings, and errors.

        Raises:
            FileError: If the file cannot be read.
            FormatError: If the file structure is invalid.
        """
        # Default implementation calls the legacy static parse method
        # Subclasses should override for better error handling
        result = ParseResult(file_path=file_path, parser_name=cls.__name__)

        if not os.path.exists(file_path):
            raise FileError(
                ParserErrorCode.FILE_NOT_FOUND,
                f"File not found: {file_path}",
                file_path=file_path,
            )

        try:
            # Try to call the format-specific parse method
            parse_method = cls._get_legacy_parse_method()
            if parse_method:
                raw_sprites = parse_method(file_path)
                result = validate_sprites(raw_sprites, file_path)
                result.parser_name = cls.__name__
                return result
            else:
                raise NotImplementedError(
                    f"{cls.__name__} must implement parse_file() or a legacy parse method"
                )
        except ParserError:
            raise
        except Exception as e:
            raise FormatError(
                ParserErrorCode.UNKNOWN_ERROR,
                f"Unexpected error parsing file: {e}",
                file_path=file_path,
                details={"exception_type": type(e).__name__},
            )

    @classmethod
    def _get_legacy_parse_method(
        cls,
    ) -> Optional[Callable[[str], List[Dict[str, Any]]]]:
        """Find the legacy static parse method if it exists.

        Checks for common method names in order of preference.

        Returns:
            The parse method if found, None otherwise.
        """
        method_names = [
            "parse_json_data",
            "parse_xml_data",
            "parse_plist_data",
            "parse_css_data",
            "parse_atlas_file",
            "parse_text_file",
            "parse_txt_packer",
        ]
        for name in method_names:
            method = getattr(cls, name, None)
            if callable(method):
                return method
        return None

    @classmethod
    def can_parse(cls, file_path: str) -> bool:
        """Check if this parser can handle the given file.

        Default implementation checks file extension against FILE_EXTENSIONS.
        Subclasses may override for content-based detection.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if this parser can handle the file.
        """
        if not cls.FILE_EXTENSIONS:
            return False
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.FILE_EXTENSIONS

    @staticmethod
    def normalize_sprite(sprite: Dict[str, Any]) -> SpriteData:
        """Normalize a raw sprite dict to canonical SpriteData format.

        Convenience wrapper around parser_types.normalize_sprite().

        Args:
            sprite: Raw sprite dict from parsing.

        Returns:
            Normalized SpriteData dict.
        """
        return normalize_sprite(sprite)

    @staticmethod
    def validate_sprites(
        sprites: List[Dict[str, Any]],
        file_path: Optional[str] = None,
    ) -> ParseResult:
        """Validate and normalize a list of sprites.

        Convenience wrapper around parser_types.validate_sprites().

        Args:
            sprites: List of raw sprite dicts.
            file_path: Source file path for error context.

        Returns:
            ParseResult with validated sprites and any errors.
        """
        return validate_sprites(sprites, file_path)


__all__ = ["BaseParser"]
