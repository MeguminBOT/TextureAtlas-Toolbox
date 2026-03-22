#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Set, Optional, Callable, List, Dict, Any, Tuple
from PIL import Image
import numpy as np

# Import our own modules
from parsers.base_parser import BaseParser
from parsers.parser_types import (
    ParseResult,
    ParserErrorCode,
    FileError,
    FormatError,
    validate_sprites,
)

# Qt imports
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox, QApplication


class UnknownParser(BaseParser):
    """Fallback parser for images without metadata files.

    Uses computer vision (flood fill) to detect sprite regions from the image's
    alpha channel. Can optionally detect and remove solid background colors.

    Note: This parser handles image files directly, not metadata files.
    FILE_EXTENSIONS is empty because it's used as a fallback for any image type.
    """

    FILE_EXTENSIONS = ()  # Used as fallback for any image, not extension-based

    @classmethod
    def parse_file(cls, file_path: str, parent_window=None) -> ParseResult:
        """Parse an image file using computer vision sprite detection.

        Args:
            file_path: Path to the image file.
            parent_window: Optional parent for dialogs.

        Returns:
            ParseResult with detected sprite regions.
        """
        result = ParseResult(file_path=file_path, parser_name=cls.__name__)

        if not os.path.exists(file_path):
            raise FileError(
                ParserErrorCode.FILE_NOT_FOUND,
                f"Image file not found: {file_path}",
                file_path=file_path,
            )

        try:
            _, sprites = cls.parse_unknown_image(file_path, parent_window)
            result = validate_sprites(sprites, file_path)
            result.parser_name = cls.__name__
            return result
        except Exception as e:
            raise FormatError(
                ParserErrorCode.UNKNOWN_ERROR,
                f"Error analyzing image for sprites: {e}",
                file_path=file_path,
                details={"exception_type": type(e).__name__},
            )

    def __init__(
        self,
        directory: str,
        image_filename: str,
        name_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the unknown image parser.

        Args:
            directory: Directory containing the image file.
            image_filename: Name of the image file.
            name_callback: Optional callback invoked for each extracted name.
        """
        super().__init__(directory, image_filename, name_callback)

    def extract_names(self) -> Set[str]:
        """Generate sequential sprite names based on detected regions.

        Returns:
            Set of names like ``sprite_001``, ``sprite_002``, etc.
        """
        try:
            file_path = os.path.join(self.directory, self.filename)
            _, sprites = self.parse_unknown_image(file_path)

            names = set()
            for i, sprite in enumerate(sprites):
                # Generate names like "sprite_001", "sprite_002", etc.
                name = f"sprite_{i + 1:03d}"
                names.add(name)

            return names
        except Exception as e:
            print(f"Error extracting names from image {self.filename}: {e}")
            return set()

    @staticmethod
    def parse_unknown_image(
        file_path: str, parent_window=None
    ) -> Tuple[Image.Image, List[Dict[str, Any]]]:
        """Detect sprite regions in an image using alpha transparency.

        Args:
            file_path: Path to the image file.
            parent_window: Optional parent widget for background-removal dialogs.

        Returns:
            A tuple (processed_image, sprites) where sprites is a list of dicts.
        """
        try:
            from PIL import Image

            Image.MAX_IMAGE_PIXELS = None
            image = Image.open(file_path)

            if image.mode != "RGBA":
                image = image.convert("RGBA")

            background_color = UnknownParser._detect_background_color(image)

            if background_color and UnknownParser._should_apply_color_keying(
                background_color, parent_window
            ):
                processed_image = UnknownParser._apply_color_keying(
                    image, background_color
                )
            else:
                processed_image = image

            sprites = UnknownParser._find_sprites_in_image(processed_image)

            return processed_image, sprites

        except Exception as e:
            print(f"Error parsing unknown image {file_path}: {e}")
            from PIL import Image

            return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), []

    @staticmethod
    def _detect_background_color(image: Image.Image) -> Optional[Tuple[int, int, int]]:
        """Detect the most common edge color as a potential background.

        Args:
            image: The PIL Image to analyze.

        Returns:
            RGB tuple of the background color, or None if not detected.
        """
        try:
            rgb_image = image.convert("RGB")

            width, height = image.size
            edge_pixels = []

            for x in range(width):
                edge_pixels.append(rgb_image.getpixel((x, 0)))  # Top edge
                edge_pixels.append(rgb_image.getpixel((x, height - 1)))  # Bottom edge

            for y in range(height):
                edge_pixels.append(rgb_image.getpixel((0, y)))  # Left edge
                edge_pixels.append(rgb_image.getpixel((width - 1, y)))  # Right edge

            from collections import Counter

            color_counts = Counter(edge_pixels)
            most_common = color_counts.most_common(1)

            if most_common and most_common[0][1] > len(edge_pixels) * 0.1:
                return most_common[0][0]

            return None
        except Exception:
            return None

    @staticmethod
    def _should_apply_color_keying(
        background_color: Tuple[int, int, int], parent_window=None
    ) -> bool:
        """Prompt user to confirm background color removal.

        Args:
            background_color: The detected background RGB tuple.
            parent_window: Optional parent widget for the dialog.

        Returns:
            True if the user confirms removal.
        """
        try:
            if parent_window is None:
                app = QApplication.instance()
                if app:
                    for widget in app.topLevelWidgets():
                        if widget.isMainWindow():
                            parent_window = widget
                            break

            msg_box = QMessageBox(parent_window)
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setWindowTitle(
                QCoreApplication.translate("UnknownParser", "Background Color Detected")
            )
            msg_box.setText(
                QCoreApplication.translate(
                    "UnknownParser",
                    (
                        "Detected background color: RGB{color}\n\n"
                        "Would you like to remove this background color and make it transparent?"
                    ),
                ).format(color=background_color)
            )
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            result = msg_box.exec()
            return result == QMessageBox.StandardButton.Yes
        except Exception:
            return False

    @staticmethod
    def _apply_color_keying(
        image: Image.Image, background_color: Tuple[int, int, int], tolerance: int = 10
    ) -> Image.Image:
        """Make pixels matching the background color transparent.

        Args:
            image: The source RGBA image.
            background_color: RGB tuple of the color to remove.
            tolerance: Maximum per-channel deviation allowed.

        Returns:
            A new image with matching pixels set to alpha 0.
        """
        try:
            img_array = np.array(image)

            r, g, b = background_color
            mask = (
                (np.abs(img_array[:, :, 0] - r) <= tolerance)
                & (np.abs(img_array[:, :, 1] - g) <= tolerance)
                & (np.abs(img_array[:, :, 2] - b) <= tolerance)
            )

            img_array[mask, 3] = 0

            try:
                return Image.fromarray(img_array, "RGBA")
            except TypeError:
                h, w = img_array.shape[:2]
                return Image.frombytes(
                    "RGBA", (w, h), np.ascontiguousarray(img_array).tobytes()
                )
        except Exception as e:
            print(f"Error applying color keying: {e}")
            return image

    @staticmethod
    def _find_sprites_in_image(image: Image.Image) -> List[Dict[str, Any]]:
        """Find connected non-transparent regions in the image.

        Args:
            image: The RGBA image to analyze.

        Returns:
            List of sprite dicts with name, x, y, width, height.
        """
        try:
            img_array = np.array(image)

            alpha_mask = img_array[:, :, 3] > 0

            regions = UnknownParser._find_connected_regions(alpha_mask)

            sprites = []
            for i, region in enumerate(regions):
                if len(region) > 10:  # Filter out very small regions (noise)
                    bbox = UnknownParser._get_bounding_box(region)
                    sprite_data = {
                        "name": f"sprite_{i + 1:03d}",
                        "x": bbox[0],
                        "y": bbox[1],
                        "width": bbox[2] - bbox[0],
                        "height": bbox[3] - bbox[1],
                    }
                    sprites.append(sprite_data)

            return sprites
        except Exception as e:
            print(f"Error finding sprites in image: {e}")
            return []

    @staticmethod
    def _find_connected_regions(alpha_mask: np.ndarray) -> List[List[Tuple[int, int]]]:
        """Flood-fill the alpha mask to find connected regions.

        Args:
            alpha_mask: Boolean 2D array where True indicates non-transparent pixels.

        Returns:
            List of regions, each a list of (x, y) coordinate tuples.
        """
        try:
            height, width = alpha_mask.shape
            visited = np.zeros_like(alpha_mask, dtype=bool)
            regions = []

            def flood_fill(start_x, start_y):
                stack = [(start_x, start_y)]
                region = []

                while stack:
                    x, y = stack.pop()
                    if (
                        x < 0
                        or x >= width
                        or y < 0
                        or y >= height
                        or visited[y, x]
                        or not alpha_mask[y, x]
                    ):
                        continue

                    visited[y, x] = True
                    region.append((x, y))

                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx != 0 or dy != 0:
                                stack.append((x + dx, y + dy))

                return region

            for y in range(height):
                for x in range(width):
                    if alpha_mask[y, x] and not visited[y, x]:
                        region = flood_fill(x, y)
                        if region:
                            regions.append(region)

            return regions
        except Exception as e:
            print(f"Error finding connected regions: {e}")
            return []

    @staticmethod
    def _get_bounding_box(
        region_coords: List[Tuple[int, int]],
    ) -> Tuple[int, int, int, int]:
        """Compute the bounding box of a region.

        Args:
            region_coords: List of (x, y) coordinate tuples.

        Returns:
            A tuple (min_x, min_y, max_x + 1, max_y + 1).
        """
        if not region_coords:
            return (0, 0, 0, 0)

        x_coords = [coord[0] for coord in region_coords]
        y_coords = [coord[1] for coord in region_coords]

        return (min(x_coords), min(y_coords), max(x_coords) + 1, max(y_coords) + 1)

    @staticmethod
    def _has_transparency(image: Image.Image) -> bool:
        """Check if the image has any transparent pixels.

        Args:
            image: The image to check.

        Returns:
            True if any pixel has alpha < 255.
        """
        try:
            if image.mode != "RGBA":
                return False

            img_array = np.array(image)

            return np.any(img_array[:, :, 3] < 255)
        except Exception as e:
            print(f"Error checking transparency: {e}")
            return False

    @staticmethod
    def _detect_background_colors(
        image: Image.Image, max_colors: int = 3
    ) -> List[Tuple[int, int, int]]:
        """Detect up to N candidate background colors from edge sampling.

        Args:
            image: The image to analyze.
            max_colors: Maximum number of background colors to return.

        Returns:
            List of RGB tuples sorted by frequency.
        """
        try:
            rgb_image = image.convert("RGB")

            width, height = image.size
            edge_pixels = []

            for x in range(0, width, max(1, width // 50)):  # Sample every ~2% of width
                edge_pixels.append(rgb_image.getpixel((x, 0)))
                if height > 1:
                    edge_pixels.append(rgb_image.getpixel((x, height - 1)))

            for y in range(0, height, max(1, height // 50)):
                edge_pixels.append(rgb_image.getpixel((0, y)))
                if width > 1:
                    edge_pixels.append(rgb_image.getpixel((width - 1, y)))

            corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
            for corner in corners:
                for _ in range(5):
                    edge_pixels.append(rgb_image.getpixel(corner))

            from collections import Counter

            color_counts = Counter(edge_pixels)

            min_occurrences = max(1, len(edge_pixels) * 0.05)
            background_colors = []

            for color, count in color_counts.most_common(max_colors * 2):
                if count >= min_occurrences and len(background_colors) < max_colors:
                    background_colors.append(color)

            return background_colors

        except Exception as e:
            print(f"Error detecting background colors: {e}")
            return []
