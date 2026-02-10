#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parser utilities for Adobe Spritemap Animation.json files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional, Set

from parsers.base_parser import BaseParser
from parsers.parser_types import (
    FormatError,
    ParseResult,
    ParserErrorCode,
)
from utils.utilities import Utilities
from core.extractor.spritemap.metadata import (
    collect_referenced_symbols,
    compute_layers_length,
    compute_symbol_lengths,
    extract_label_ranges,
)
from core.extractor.spritemap.normalizer import normalize_animation_document


class SpritemapParser(BaseParser):
    """Extract animation names from Adobe Animate spritemap exports."""

    FILE_EXTENSIONS = (".json",)

    def __init__(
        self,
        directory: str,
        animation_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
        filter_single_frame: bool = True,
        filter_unused_symbols: bool = False,
        root_animation_only: bool = False,
    ) -> None:
        """Initialize the spritemap parser.

        Args:
            directory: Directory containing the Animation.json file.
            animation_filename: Name of the Animation.json file.
            name_callback: Optional callback invoked for each extracted name.
            filter_single_frame: If True, skip single-frame symbols.
            filter_unused_symbols: If True, skip symbols not referenced by
                the root animation timeline.
            root_animation_only: If True, only include the root animation
                name; skip individual symbols and timeline labels.
        """
        super().__init__(directory, animation_filename, name_callback)
        self.filter_single_frame = filter_single_frame
        self.filter_unused_symbols = filter_unused_symbols
        self.root_animation_only = root_animation_only

    def extract_names(self) -> Set[str]:
        """Extract animation and label names from the spritemap file.

        Returns:
            Set of animation names with trailing digits stripped.
        """
        names: Set[str] = set()
        animation_path = Path(self.directory) / self.filename
        try:
            with open(animation_path, "r", encoding="utf-8") as animation_file:
                animation_json = normalize_animation_document(json.load(animation_file))

            symbol_lengths = compute_symbol_lengths(animation_json)

            # Compute referenced symbols for filtering
            referenced_symbols = (
                collect_referenced_symbols(animation_json)
                if self.filter_unused_symbols
                else None
            )

            # Include the root animation (full AN timeline) name
            an = animation_json.get("AN", {})
            root_name = an.get("SN") or an.get("N")
            if root_name:
                root_layers = an.get("TL", {}).get("L", [])
                root_frame_count = compute_layers_length(root_layers)
                if not (self.filter_single_frame and root_frame_count <= 1):
                    names.add(root_name)

            if not self.root_animation_only:
                for symbol in animation_json.get("SD", {}).get("S", []):
                    raw_name = symbol.get("SN")
                    if raw_name:
                        if (
                            referenced_symbols is not None
                            and raw_name not in referenced_symbols
                        ):
                            continue
                        if (
                            self.filter_single_frame
                            and symbol_lengths.get(raw_name, 0) <= 1
                        ):
                            continue
                        names.add(Utilities.strip_trailing_digits(raw_name))

                for label in extract_label_ranges(animation_json, None):
                    frame_count = label["end"] - label["start"]
                    if self.filter_single_frame and frame_count <= 1:
                        continue
                    names.add(label["name"])
        except Exception as exc:
            print(f"Error parsing spritemap animation file {animation_path}: {exc}")
        return names

    @classmethod
    def parse_file(cls, file_path: str) -> ParseResult:
        """Parse an Adobe Spritemap Animation.json file.

        Note: This parser extracts animation metadata, not individual sprites.
        The actual sprite regions are in the accompanying spritemap.json file.

        Args:
            file_path: Path to the Animation.json file.

        Returns:
            ParseResult with animation data.
        """
        result = ParseResult(file_path=file_path, parser_name=cls.__name__)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = normalize_animation_document(json.load(f))

            # Validate this is a spritemap Animation.json
            if "SD" not in data and "ATLAS" not in data:
                raise FormatError(
                    ParserErrorCode.INVALID_FORMAT,
                    "Not a valid Adobe Spritemap Animation.json file",
                    file_path=file_path,
                )

            # For spritemap, we don't return traditional sprites
            # The extraction uses the full animation data structure
            result.add_warning(
                ParserErrorCode.UNSUPPORTED_FORMAT,
                "Spritemap format uses Animation.json + spritemap.json together",
            )

        except json.JSONDecodeError as e:
            result.add_error(
                ParserErrorCode.INVALID_FORMAT,
                f"Invalid JSON: {e}",
            )
        except FileNotFoundError:
            result.add_error(
                ParserErrorCode.FILE_NOT_FOUND,
                f"File not found: {file_path}",
            )
        except Exception as e:
            result.add_error(
                ParserErrorCode.UNKNOWN_ERROR,
                f"Unexpected error: {e}",
            )

        return result

    @staticmethod
    def is_spritemap_animation(file_path: str) -> bool:
        """Check if a JSON file is an Adobe Spritemap Animation.json.

        Args:
            file_path: Path to check.

        Returns:
            True if this is a spritemap Animation.json file.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = normalize_animation_document(json.load(f))
            return "SD" in data or ("ATLAS" in data and "AN" in data)
        except Exception:
            return False


__all__ = ["SpritemapParser"]
