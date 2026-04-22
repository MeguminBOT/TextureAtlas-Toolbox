#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Base class for all spritesheet/atlas exporters.

Provides the abstract interface that all exporters must implement, plus
shared utilities for image compositing and metadata serialization.

The exporter system mirrors the parser architecture:
    - Parsers: metadata file → List[SpriteData]
    - Exporters: List[SpriteData] + images → atlas image + metadata file
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image

from exporters.exporter_types import (
    ExporterError,
    ExporterErrorCode,
    ExportOptions,
    ExportResult,
    FileWriteError,
    FormatError,
    FORMATS_SUPPORTING_ROTATION,
    GeneratorMetadata,
    ImageError,
    PackedSprite,
    PackingError,
    SpriteData,
)


class BaseExporter(ABC):
    """Abstract base class for spritesheet/atlas metadata exporters.

    Subclasses must implement:
        - build_metadata(): Generate format-specific metadata string/bytes.
        - FILE_EXTENSION: The output file extension for this format.
        - FORMAT_NAME: Human-readable format name for UI display.

    The base class provides:
        - export_file(): Main entry point for creating atlas + metadata.
        - pack_sprites(): Sprite packing with configurable algorithms.
        - composite_atlas(): Render sprites onto atlas image.
    """

    # Subclasses must define these
    FILE_EXTENSION: str = ""
    FORMAT_NAME: str = ""

    def __init__(self, options: Optional[ExportOptions] = None) -> None:
        """Initialize the exporter with optional configuration.

        Args:
            options: Export options controlling packing and output.
                     Uses defaults if not provided.
        """
        self.options = options or ExportOptions()

    @classmethod
    def supports_rotation(cls) -> bool:
        """Return whether this format can represent rotated sprites.

        Formats whose schemas have no rotation field (UIKit plist,
        Godot tpsheet, Egret2D, TXT, CSS) return False; the GUI
        disables the rotation option for them and the exporter
        raises `FormatError(UNSUPPORTED_FORMAT, ...)` if a rotated
        sprite is passed in anyway.

        Returns:
            True when rotation can round-trip via this format.
        """
        return cls.FORMAT_NAME in FORMATS_SUPPORTING_ROTATION

    def _reject_rotated_sprites(self, packed_sprites: List[PackedSprite]) -> None:
        """Raise when a rotation-incapable format receives rotated input.

        Affected exporters (UIKit plist, Godot tpsheet, Egret2D, TXT,
        CSS) call this from `build_metadata` so the silent
        dimension-swap data-loss bug becomes a clear, recoverable
        error instead.

        Args:
            packed_sprites: Packed sprites about to be serialized.

        Raises:
            FormatError: When any sprite is marked rotated.
        """
        offenders = [
            p.name
            for p in packed_sprites
            if p.rotated or p.sprite.get("rotated", False)
        ]
        if offenders:
            sample = ", ".join(offenders[:3])
            extra = "" if len(offenders) <= 3 else f" (+{len(offenders) - 3} more)"
            raise FormatError(
                ExporterErrorCode.UNSUPPORTED_FORMAT,
                (
                    f"Format '{self.FORMAT_NAME}' has no rotation field; "
                    f"refusing to silently swap dimensions for rotated sprites. "
                    f"Disable rotation in the packer or pick a rotation-capable "
                    f"format. Offending sprites: {sample}{extra}."
                ),
                details={
                    "format": self.FORMAT_NAME,
                    "rotated_sprite_count": len(offenders),
                },
            )

    @abstractmethod
    def build_metadata(
        self,
        packed_sprites: List[PackedSprite],
        atlas_width: int,
        atlas_height: int,
        image_name: str,
        generator_metadata: Optional[GeneratorMetadata] = None,
    ) -> Union[str, bytes]:
        """Generate format-specific metadata for the packed atlas.

        Args:
            packed_sprites: Sprites with their atlas positions assigned.
            atlas_width: Final atlas width in pixels.
            atlas_height: Final atlas height in pixels.
            image_name: Filename of the atlas image (for references).
            generator_metadata: Optional metadata about the generation process
                               for watermarking/comments.

        Returns:
            Metadata content as string (text formats) or bytes (binary formats).
        """
        pass

    def export_file(
        self,
        sprites: List[SpriteData],
        sprite_images: Dict[str, Image.Image],
        output_path: str,
    ) -> ExportResult:
        """Export sprites to an atlas image and metadata file.

        This is the main entry point for the export pipeline.

        Args:
            sprites: List of sprite definitions to export.
            sprite_images: Mapping of sprite names to PIL Images.
            output_path: Base path for output (without extension).
                         Will create {output_path}.png and {output_path}.{ext}.

        Returns:
            ExportResult with paths, dimensions, and any errors.

        Raises:
            ExporterError: If a fatal error prevents export.
        """
        result = ExportResult(exporter_name=self.__class__.__name__)

        # Validate inputs
        if not sprites:
            result.add_error(
                ExporterErrorCode.NO_SPRITES_PROVIDED,
                "No sprites provided for export",
            )
            return result

        # Check for missing images
        missing = [s["name"] for s in sprites if s["name"] not in sprite_images]
        if missing:
            result.add_error(
                ExporterErrorCode.IMAGE_NOT_FOUND,
                f"Missing images for sprites: {', '.join(missing[:5])}",
                details={"count": len(missing)},
            )
            return result

        try:
            # Pack sprites into atlas layout
            packed_sprites, atlas_width, atlas_height = self.pack_sprites(
                sprites, sprite_images
            )

            # Composite the atlas image
            atlas_image = self.composite_atlas(
                packed_sprites, sprite_images, atlas_width, atlas_height
            )

            # Determine output paths
            output_base = Path(output_path)
            atlas_path = output_base.with_suffix(
                f".{self.options.image_format.lower()}"
            )
            metadata_path = output_base.with_suffix(self.FILE_EXTENSION)

            # Ensure output directory exists
            atlas_path.parent.mkdir(parents=True, exist_ok=True)

            # Save atlas image
            self._save_atlas_image(atlas_image, str(atlas_path))

            # Generate and save metadata
            image_name = atlas_path.name
            metadata = self.build_metadata(
                packed_sprites, atlas_width, atlas_height, image_name
            )
            self._save_metadata(metadata, str(metadata_path))

            # Populate successful result
            result.success = True
            result.atlas_path = str(atlas_path)
            result.metadata_path = str(metadata_path)
            result.atlas_width = atlas_width
            result.atlas_height = atlas_height
            result.sprite_count = len(packed_sprites)

        except ExporterError as e:
            result.add_error(e.code, e.message, e.file_path, e.details)
        except Exception as e:
            result.add_error(
                ExporterErrorCode.UNKNOWN_ERROR,
                f"Unexpected error during export: {e}",
                details={"exception_type": type(e).__name__},
            )

        return result

    def pack_sprites(
        self,
        sprites: List[SpriteData],
        sprite_images: Dict[str, Image.Image],
    ) -> Tuple[List[PackedSprite], int, int]:
        """Pack sprites into an atlas layout.

        Uses a simple shelf-packing algorithm by default.
        Subclasses or future versions can plug in more sophisticated packers.

        Args:
            sprites: Sprite definitions to pack.
            sprite_images: Mapping of sprite names to PIL Images.

        Returns:
            Tuple of (packed_sprites, atlas_width, atlas_height).

        Raises:
            PackingError: If sprites cannot fit in the maximum dimensions.
        """
        padding = self.options.padding
        max_width = self.options.max_width
        max_height = self.options.max_height

        # Sort sprites by height (descending) for better shelf packing
        sorted_sprites = sorted(
            sprites,
            key=lambda s: sprite_images[s["name"]].height,
            reverse=True,
        )

        packed: List[PackedSprite] = []
        current_x = padding
        current_y = padding
        row_height = 0
        atlas_width = 0
        atlas_height = 0

        for sprite in sorted_sprites:
            img = sprite_images[sprite["name"]]
            w, h = img.width, img.height

            # Check if sprite fits in current row
            if current_x + w + padding > max_width:
                # Move to next row
                current_x = padding
                current_y += row_height + padding
                row_height = 0

            # Check if sprite fits vertically
            if current_y + h + padding > max_height:
                raise PackingError(
                    ExporterErrorCode.ATLAS_TOO_LARGE,
                    f"Cannot fit all sprites in {max_width}x{max_height} atlas",
                    details={"sprite_count": len(sprites)},
                )

            # Place sprite
            packed.append(
                PackedSprite(
                    sprite=sprite,
                    atlas_x=current_x,
                    atlas_y=current_y,
                    rotated=False,
                )
            )

            # Update tracking
            current_x += w + padding
            row_height = max(row_height, h)
            atlas_width = max(atlas_width, current_x)
            atlas_height = max(atlas_height, current_y + h + padding)

        # Optionally round up to power of two
        if self.options.power_of_two:
            atlas_width = self._next_power_of_two(atlas_width)
            atlas_height = self._next_power_of_two(atlas_height)

        return packed, atlas_width, atlas_height

    def composite_atlas(
        self,
        packed_sprites: List[PackedSprite],
        sprite_images: Dict[str, Image.Image],
        atlas_width: int,
        atlas_height: int,
    ) -> Image.Image:
        """Composite packed sprites onto an atlas image.

        Args:
            packed_sprites: Sprites with assigned atlas positions.
            sprite_images: Mapping of sprite names to PIL Images.
            atlas_width: Target atlas width.
            atlas_height: Target atlas height.

        Returns:
            Composited atlas as a PIL Image.
        """
        # Create transparent atlas
        atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))

        for packed in packed_sprites:
            img = sprite_images[packed.name]

            # Handle rotation if needed
            if packed.rotated:
                img = img.transpose(Image.Transpose.ROTATE_90)

            # Ensure image is RGBA
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Paste onto atlas
            atlas.paste(img, (packed.atlas_x, packed.atlas_y), img)

        return atlas

    def _save_atlas_image(self, image: Image.Image, path: str) -> None:
        """Save the atlas image to disk.

        Args:
            image: Atlas image to save.
            path: Output file path.

        Raises:
            ImageError: If the image cannot be saved.
        """
        try:
            # Determine format from extension
            ext = Path(path).suffix.lower().lstrip(".")
            save_kwargs: Dict[str, Any] = {}

            if ext == "png":
                save_kwargs["compress_level"] = 9
                save_kwargs["optimize"] = True
            elif ext == "webp":
                save_kwargs["lossless"] = True
                save_kwargs["quality"] = 90

            image.save(path, **save_kwargs)

        except Exception as e:
            raise ImageError(
                ExporterErrorCode.IMAGE_WRITE_ERROR,
                f"Failed to save atlas image: {e}",
                file_path=path,
            )

    def _save_metadata(self, metadata: Union[str, bytes], path: str) -> None:
        """Save metadata content to disk.

        Args:
            metadata: Metadata content (string or bytes).
            path: Output file path.

        Raises:
            FileWriteError: If the file cannot be written.
        """
        try:
            if isinstance(metadata, bytes):
                with open(path, "wb") as f:
                    f.write(metadata)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(metadata)

        except Exception as e:
            raise FileWriteError(
                ExporterErrorCode.FILE_WRITE_ERROR,
                f"Failed to save metadata: {e}",
                file_path=path,
            )

    @staticmethod
    def _next_power_of_two(value: int) -> int:
        """Round up to the next power of two.

        Args:
            value: Input value.

        Returns:
            Smallest power of two >= value.
        """
        power = 1
        while power < value:
            power *= 2
        return power

    @classmethod
    def can_export(cls, format_name: str) -> bool:
        """Check if this exporter supports the given format.

        Args:
            format_name: Format name or extension to check.

        Returns:
            True if this exporter handles the format.
        """
        format_lower = format_name.lower().lstrip(".")
        return (
            format_lower == cls.FORMAT_NAME.lower()
            or format_lower == cls.FILE_EXTENSION.lower().lstrip(".")
        )


__all__ = ["BaseExporter"]
