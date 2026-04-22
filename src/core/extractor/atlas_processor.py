"""Load texture atlases and parse their accompanying metadata.

Provides ``AtlasProcessor`` which opens atlas images and delegates to the
unified parser registry for metadata parsing with full error handling.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from utils.logger import get_logger

logger = get_logger(__name__)


class AtlasProcessor:
    """Open a texture atlas and parse sprite metadata.

    Uses the unified ParserRegistry for format detection and parsing.
    For unknown spritesheets (no metadata or image-only paths),
    falls back to heuristic sprite detection.

    Attributes:
        atlas_path: Filesystem path to the atlas image.
        metadata_path: Filesystem path to the metadata file, or ``None``.
        parent_window: Optional parent widget for progress dialogs.
        atlas: The opened PIL ``Image``, or ``None`` on failure.
        sprites: List of parsed sprite dicts.
        parse_result: Full ParseResult with warnings and errors.
    """

    def __init__(
        self,
        atlas_path: str,
        metadata_path: Optional[str],
        parent_window: Optional[Any] = None,
    ) -> None:
        """Load the atlas and parse metadata on construction.

        Args:
            atlas_path: Path to the texture atlas image.
            metadata_path: Path to the metadata file, or ``None`` for
                unknown spritesheets.
            parent_window: Optional parent widget for dialogs.
        """
        self.atlas_path = atlas_path
        self.metadata_path = metadata_path
        self.parent_window = parent_window
        self.parse_result: Optional[Any] = None  # Will be ParseResult
        self.atlas, self.sprites = self.open_atlas_and_parse_metadata()

    def open_atlas_and_parse_metadata(
        self,
    ) -> Tuple[Optional[Image.Image], List[Dict[str, Any]]]:
        """Open the atlas image and parse sprite metadata.

        Uses ParserRegistry for format detection and unified parsing.
        Falls back to ``UnknownParser`` when metadata is missing or points to
        an image file.

        Returns:
            A tuple ``(atlas, sprites)`` where ``atlas`` is a PIL ``Image``
            (or ``None`` on error) and ``sprites`` is a list of sprite dicts.

        Raises:
            ParserError: If the metadata file cannot be parsed.
        """
        from parsers.parser_registry import ParserRegistry
        from parsers.parser_types import ParseResult, ParserError, ParserErrorCode
        from parsers.unknown_parser import UnknownParser

        atlas: Optional[Image.Image] = None
        sprites: List[Dict[str, Any]] = []

        try:
            Image.MAX_IMAGE_PIXELS = None
            ext = (
                self.atlas_path.rsplit(".", 1)[-1].lower()
                if "." in self.atlas_path
                else ""
            )
            if ext in ("dds", "ktx2"):
                from core.optimizer.texture_compress import load_gpu_texture

                atlas = load_gpu_texture(self.atlas_path)
            else:
                atlas = Image.open(self.atlas_path)
        except Exception as e:
            logger.exception("Error opening atlas %s", self.atlas_path)
            return None, []

        if self._is_unknown_spritesheet():
            processed_atlas, sprites = UnknownParser.parse_unknown_image(
                self.atlas_path, self.parent_window
            )
            if processed_atlas is not None:
                atlas = processed_atlas
            return atlas, sprites

        try:
            if not ParserRegistry._all_parsers:
                ParserRegistry.initialize()

            self.parse_result = ParserRegistry.parse_file(self.metadata_path)

            if self.parse_result.is_valid:
                sprites = list(self.parse_result.sprites)

                # Log any warnings
                for warning in self.parse_result.warnings:
                    sprite_suffix = (
                        f" (sprite: {warning.sprite_name})"
                        if warning.sprite_name
                        else ""
                    )
                    logger.warning(
                        "Parser warning: %s%s", warning.message, sprite_suffix
                    )
            else:
                # Log errors but don't raise - allow partial results
                for error in self.parse_result.errors:
                    logger.error("Parser error: %s", error.message)

        except ParserError as e:
            logger.error("Parser error for %s: %s", self.metadata_path, e)
            self.parse_result = ParseResult(
                file_path=self.metadata_path,
                parser_name="AtlasProcessor",
            )
            self.parse_result.add_error(e.code, e.message, details=e.details)
        except Exception as e:
            logger.exception("Unexpected error parsing %s", self.metadata_path)
            self.parse_result = ParseResult(
                file_path=self.metadata_path,
                parser_name="AtlasProcessor",
            )
            self.parse_result.add_error(
                ParserErrorCode.UNKNOWN_ERROR,
                f"Unexpected error: {e}",
            )

        return atlas, sprites

    def _is_unknown_spritesheet(self) -> bool:
        """Check if this is an unknown spritesheet (no metadata or image-only).

        Returns:
            True if we should use UnknownParser for sprite detection.
        """
        if self.metadata_path is None:
            return True

        image_extensions = (
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tiff",
            ".webp",
            ".dds",
            ".ktx2",
        )
        return self.metadata_path.lower().endswith(image_extensions)

    def has_parse_errors(self) -> bool:
        """Check if parsing produced any errors.

        Returns:
            True if there were parse errors.
        """
        return self.parse_result is not None and self.parse_result.error_count > 0

    def has_parse_warnings(self) -> bool:
        """Check if parsing produced any warnings.

        Returns:
            True if there were parse warnings.
        """
        return self.parse_result is not None and self.parse_result.warning_count > 0

    def get_parse_summary(self) -> str:
        """Get a human-readable summary of the parse result.

        Returns:
            Summary string or empty if no parse result.
        """
        if self.parse_result is None:
            return ""
        return self.parse_result.get_summary()

    def parse_for_preview(self, animation_name: str) -> List[Dict[str, Any]]:
        """Parse metadata for a single animation's sprites.

        Filters sprites to only those matching the animation name.
        Uses the appropriate method based on metadata file type.

        Args:
            animation_name: Animation prefix to filter by.

        Returns:
            List of sprite dicts matching the animation.
        """
        if not self.metadata_path:
            return []

        if self.metadata_path.endswith(".xml"):
            return self.parse_xml_for_preview(animation_name)
        elif self.metadata_path.endswith(".txt"):
            return self.parse_txt_for_preview(animation_name)
        else:
            return self._filter_sprites_for_animation(animation_name, self.sprites)

    def _filter_sprites_for_animation(
        self,
        animation_name: str,
        sprites: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter sprites to only those matching an animation name.

        Supports two matching modes:
        1. Animation tag matching (Aseprite format) - sprites with 'animation_tag' field
        2. Name prefix matching (traditional) - sprite names starting with animation name

        Args:
            animation_name: Animation name or prefix to filter by.
            sprites: List of all sprites.

        Returns:
            Filtered list of matching sprites.
        """

        tag_matched_sprites = [
            sprite
            for sprite in sprites
            if sprite.get("animation_tag") == animation_name
        ]
        if tag_matched_sprites:
            return tag_matched_sprites

        anim_patterns = self._get_animation_patterns(animation_name)

        animation_sprites = []
        for sprite in sprites:
            sprite_name = sprite.get("name", "")
            for pattern in anim_patterns:
                if sprite_name == pattern or sprite_name.startswith(pattern):
                    animation_sprites.append(sprite)
                    break

        return animation_sprites

    @staticmethod
    def _get_animation_patterns(animation_name: str) -> List[str]:
        """Generate pattern variations for matching animation sprites.

        Args:
            animation_name: Base animation name.

        Returns:
            List of patterns to match against sprite names.
        """
        patterns = [
            animation_name,
            re.sub(r"\d+$", "", animation_name),
            re.sub(r"_?\d+$", "", animation_name),
            re.sub(r"[-_]?\d+$", "", animation_name),
        ]
        return list(dict.fromkeys(patterns))

    def parse_xml_for_preview(self, animation_name: str) -> List[Dict[str, Any]]:
        """Parse XML metadata for a single animation's sprites.

        Only extracts sprites whose names match ``animation_name``, reducing
        memory and processing time for preview generation.

        Args:
            animation_name: Animation prefix to filter by.

        Returns:
            List of sprite dicts matching the animation.
        """
        if not self.metadata_path or not self.metadata_path.endswith(".xml"):
            return []

        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(self.metadata_path)
            xml_root = tree.getroot()

            anim_patterns = self._get_animation_patterns(animation_name)

            animation_sprites = []
            for sprite in xml_root.findall("SubTexture"):
                sprite_name = sprite.get("name", "")
                is_match = False
                for pattern in anim_patterns:
                    if sprite_name == pattern or sprite_name.startswith(pattern):
                        is_match = True
                        break

                if is_match:
                    sprite_data = {
                        "name": sprite_name,
                        "x": int(sprite.get("x", 0)),
                        "y": int(sprite.get("y", 0)),
                        "width": int(sprite.get("width", 0)),
                        "height": int(sprite.get("height", 0)),
                        "frameX": int(sprite.get("frameX", 0)),
                        "frameY": int(sprite.get("frameY", 0)),
                        "frameWidth": int(
                            sprite.get("frameWidth", sprite.get("width", 0))
                        ),
                        "frameHeight": int(
                            sprite.get("frameHeight", sprite.get("height", 0))
                        ),
                        "rotated": sprite.get("rotated", "false") == "true",
                    }
                    animation_sprites.append(sprite_data)

            return animation_sprites

        except Exception as e:
            logger.exception("Error parsing XML for animation %s", animation_name)
            return []

    def parse_txt_for_preview(self, animation_name: str) -> List[Dict[str, Any]]:
        """Parse TXT metadata for a single animation's sprites.

        Only extracts sprites whose names match ``animation_name``, reducing
        memory and processing time for preview generation.

        Args:
            animation_name: Animation prefix to filter by.

        Returns:
            List of sprite dicts matching the animation.
        """
        if not self.metadata_path or not self.metadata_path.endswith(".txt"):
            return []

        try:
            from parsers.txt_parser import TxtParser

            all_sprites = TxtParser.parse_txt_packer(self.metadata_path)
            return self._filter_sprites_for_animation(animation_name, all_sprites)
        except Exception as e:
            logger.exception("Error parsing TXT for animation %s", animation_name)
            return []

    def close(self) -> None:
        """Release resources held by this processor.

        Closes the atlas PIL image and clears the sprite list and parse
        result so memory can be reclaimed.
        """

        if getattr(self, "atlas", None) is not None:
            try:
                self.atlas.close()
            except Exception:
                pass
            finally:
                self.atlas = None

        self.sprites = []
        self.parse_result = None


__all__ = ["AtlasProcessor"]
