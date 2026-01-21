"""Icon provider for consistent iconography throughout the application.

Supports three display styles: emoji characters, colored shape indicators
(simplified), or user-provided custom assets. Used for translation status,
quality markers, and file state indicators.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


class IconStyle(Enum):
    """Available icon display styles."""

    EMOJI = "emoji"  # Original emoji characters (✅, ❌, etc.)
    SIMPLIFIED = "simplified"  # Colored circles/indicators
    CUSTOM = "custom"  # User-provided icon assets


class IconType(Enum):
    """Types of icons used in the application."""

    # Status indicators
    SUCCESS = "success"  # Translated, file exists, etc.
    ERROR = "error"  # Not translated, file missing, etc.
    WARNING = "warning"  # Needs attention

    # Language quality indicators (translation source/review status)
    QUALITY_MACHINE = "quality_machine"  # Machine-translated, no human review
    QUALITY_UNREVIEWED = "quality_unreviewed"  # Human translated, not yet reviewed
    QUALITY_REVIEWED = "quality_reviewed"  # Reviewed by at least one person
    QUALITY_NATIVE = "quality_native"  # Approved by multiple native speakers
    QUALITY_UNKNOWN = "quality_unknown"  # Unknown quality

    # Translation status markers
    MARKER_UNSURE = "marker_unsure"  # Translator is unsure
    MACHINE_TRANSLATED = "machine_translated"  # Machine translated, not reviewed

    # Misc
    GROUP = "group"  # Multiple contexts indicator


# Color definitions for simplified mode
SIMPLIFIED_COLORS: Dict[IconType, Tuple[int, int, int]] = {
    IconType.SUCCESS: (76, 175, 80),  # Green
    IconType.ERROR: (244, 67, 54),  # Red
    IconType.WARNING: (255, 193, 7),  # Amber/Yellow
    IconType.QUALITY_MACHINE: (156, 39, 176),  # Purple
    IconType.QUALITY_UNREVIEWED: (255, 152, 0),  # Orange
    IconType.QUALITY_REVIEWED: (0, 188, 212),  # Cyan
    IconType.QUALITY_NATIVE: (33, 150, 243),  # Blue
    IconType.QUALITY_UNKNOWN: (158, 158, 158),  # Gray
    IconType.MARKER_UNSURE: (255, 193, 7),  # Amber
    IconType.MACHINE_TRANSLATED: (156, 39, 176),  # Purple (same as quality_machine)
    IconType.GROUP: (96, 125, 139),  # Blue Gray
}

# Emoji mappings for emoji mode
EMOJI_CHARS: Dict[IconType, str] = {
    IconType.SUCCESS: "✅",
    IconType.ERROR: "❌",
    IconType.WARNING: "⚠️",
    IconType.QUALITY_MACHINE: "🤖",
    IconType.QUALITY_UNREVIEWED: "✍️",
    IconType.QUALITY_REVIEWED: "👍",
    IconType.QUALITY_NATIVE: "✅",
    IconType.QUALITY_UNKNOWN: "❓",
    IconType.MARKER_UNSURE: "❔",
    IconType.MACHINE_TRANSLATED: "🤖",
    IconType.GROUP: "📎",
}

# Asset filename mappings for custom mode
ASSET_FILENAMES: Dict[IconType, str] = {
    IconType.SUCCESS: "icon_success.png",
    IconType.ERROR: "icon_error.png",
    IconType.WARNING: "icon_warning.png",
    IconType.QUALITY_MACHINE: "icon_machine.png",
    IconType.QUALITY_UNREVIEWED: "icon_unreviewed.png",
    IconType.QUALITY_REVIEWED: "icon_reviewed.png",
    IconType.QUALITY_NATIVE: "icon_native.png",
    IconType.QUALITY_UNKNOWN: "icon_unknown.png",
    IconType.MARKER_UNSURE: "icon_unsure.png",
    IconType.MACHINE_TRANSLATED: "icon_machine.png",
    IconType.GROUP: "icon_group.png",
}


class IconProvider:
    """Provides icons based on the configured style.

    Supports three styles:
    - Emoji: Uses Unicode emoji characters (original behavior)
    - Simplified: Generates colored circle indicators
    - Custom: Uses user-provided PNG assets from an assets folder

    Attributes:
        style: The current icon style.
        custom_assets_path: Path to custom icon assets folder.
    """

    _instance: Optional["IconProvider"] = None

    def __init__(
        self,
        style: IconStyle = IconStyle.SIMPLIFIED,
        custom_assets_path: Optional[Path] = None,
    ) -> None:
        """Initialize the icon provider.

        Args:
            style: The icon style to use.
            custom_assets_path: Path to folder containing custom icon assets.
        """
        self._style = style
        self._custom_assets_path = custom_assets_path
        self._icon_cache: Dict[Tuple[IconType, int], QIcon] = {}
        self._pixmap_cache: Dict[Tuple[IconType, int], QPixmap] = {}

    @classmethod
    def instance(cls) -> "IconProvider":
        """Get or create the singleton instance.

        Returns:
            The global IconProvider instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, provider: "IconProvider") -> None:
        """Set the global icon provider instance.

        Args:
            provider: The IconProvider to use globally.
        """
        cls._instance = provider

    @property
    def style(self) -> IconStyle:
        """Get the current icon style."""
        return self._style

    @style.setter
    def style(self, value: IconStyle) -> None:
        """Set the icon style and clear caches.

        Args:
            value: The new icon style.
        """
        if value != self._style:
            self._style = value
            self._clear_caches()

    @property
    def custom_assets_path(self) -> Optional[Path]:
        """Get the custom assets path."""
        return self._custom_assets_path

    @custom_assets_path.setter
    def custom_assets_path(self, value: Optional[Path]) -> None:
        """Set the custom assets path and clear caches.

        Args:
            value: Path to the custom assets folder.
        """
        if value != self._custom_assets_path:
            self._custom_assets_path = value
            self._clear_caches()

    def _clear_caches(self) -> None:
        """Clear cached icons and pixmaps.

        Called when the style or custom assets path changes to ensure icons
        are regenerated with the new settings.
        """
        self._icon_cache.clear()
        self._pixmap_cache.clear()

    def get_text(self, icon_type: IconType) -> str:
        """Get the text representation for an icon type.

        In emoji mode, returns the emoji character.
        In simplified/custom modes, returns an empty string (use icons instead).

        Args:
            icon_type: The type of icon.

        Returns:
            The text representation, or empty string for non-emoji modes.
        """
        if self._style == IconStyle.EMOJI:
            return EMOJI_CHARS.get(icon_type, "")
        return ""

    def get_icon(self, icon_type: IconType, size: int = 16) -> QIcon:
        """Get a QIcon for the specified type.

        Args:
            icon_type: The type of icon to retrieve.
            size: The desired icon size in pixels.

        Returns:
            A QIcon instance for the requested icon type.
        """
        cache_key = (icon_type, size)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        pixmap = self.get_pixmap(icon_type, size)
        icon = QIcon(pixmap)
        self._icon_cache[cache_key] = icon
        return icon

    def get_pixmap(self, icon_type: IconType, size: int = 16) -> QPixmap:
        """Get a QPixmap for the specified type.

        Args:
            icon_type: The type of icon to retrieve.
            size: The desired pixmap size in pixels.

        Returns:
            A QPixmap instance for the requested icon type.
        """
        cache_key = (icon_type, size)
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        if self._style == IconStyle.CUSTOM and self._custom_assets_path:
            pixmap = self._load_custom_asset(icon_type, size)
            if not pixmap.isNull():
                self._pixmap_cache[cache_key] = pixmap
                return pixmap
            # Fall back to simplified if custom asset not found

        # Generate simplified colored circle
        pixmap = self._generate_circle(icon_type, size)
        self._pixmap_cache[cache_key] = pixmap
        return pixmap

    def _load_custom_asset(self, icon_type: IconType, size: int) -> QPixmap:
        """Attempt to load a custom asset for the icon type.

        Args:
            icon_type: The type of icon.
            size: The desired size.

        Returns:
            The loaded pixmap, or a null pixmap if not found.
        """
        if not self._custom_assets_path:
            return QPixmap()

        filename = ASSET_FILENAMES.get(icon_type)
        if not filename:
            return QPixmap()

        asset_path = self._custom_assets_path / filename
        if not asset_path.exists():
            return QPixmap()

        pixmap = QPixmap(str(asset_path))
        if pixmap.isNull():
            return QPixmap()

        return pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _generate_circle(self, icon_type: IconType, size: int) -> QPixmap:
        """Generate a colored circle pixmap for the icon type.

        Args:
            icon_type: The type of icon.
            size: The circle diameter in pixels.

        Returns:
            A QPixmap with a colored circle.
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        color_tuple = SIMPLIFIED_COLORS.get(icon_type, (128, 128, 128))
        color = QColor(*color_tuple)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

        margin = 1
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
        painter.end()

        return pixmap

    def format_status_text(
        self,
        is_positive: bool,
        text: str = "",
        icon_size: int = 14,
    ) -> Tuple[str, Optional[QIcon]]:
        """Format a status indicator with optional text.

        Args:
            is_positive: True for success/positive, False for error/negative.
            text: Optional text to append after the icon.
            icon_size: Size for the icon if applicable.

        Returns:
            A tuple of (display_text, optional_icon).
            In emoji mode, the icon is embedded in display_text.
            In other modes, display_text is the plain text and icon is provided.
        """
        icon_type = IconType.SUCCESS if is_positive else IconType.ERROR

        if self._style == IconStyle.EMOJI:
            emoji = EMOJI_CHARS.get(icon_type, "")
            return (f"{emoji} {text}".strip(), None)

        icon = self.get_icon(icon_type, icon_size)
        return (text.strip(), icon)

    def get_quality_indicator(
        self, quality: str, icon_size: int = 14
    ) -> Tuple[str, Optional[QIcon]]:
        """Get the quality indicator for a language.

        Args:
            quality: Quality string ('machine', 'unreviewed', 'reviewed', 'native', etc.).
            icon_size: Size for the icon.

        Returns:
            A tuple of (display_text_suffix, optional_icon).
        """
        quality_map = {
            "machine": IconType.QUALITY_MACHINE,
            "unreviewed": IconType.QUALITY_UNREVIEWED,
            "reviewed": IconType.QUALITY_REVIEWED,
            "native": IconType.QUALITY_NATIVE,
            "unknown": IconType.QUALITY_UNKNOWN,
        }
        icon_type = quality_map.get(quality)
        if not icon_type:
            return ("", None)

        if self._style == IconStyle.EMOJI:
            emoji = EMOJI_CHARS.get(icon_type, "")
            return (f" {emoji}" if emoji else "", None)

        icon = self.get_icon(icon_type, icon_size)
        return ("", icon)


# Convenience functions for common use cases
def get_icon_provider() -> IconProvider:
    """Get the global icon provider instance.

    Returns:
        The global IconProvider singleton.
    """
    return IconProvider.instance()


def get_status_text(is_positive: bool) -> str:
    """Get status indicator text (emoji or empty for icon mode).

    Args:
        is_positive: True for success, False for error.

    Returns:
        The emoji character or empty string.
    """
    provider = get_icon_provider()
    icon_type = IconType.SUCCESS if is_positive else IconType.ERROR
    return provider.get_text(icon_type)


def get_status_icon(is_positive: bool, size: int = 16) -> QIcon:
    """Get a status indicator icon.

    Args:
        is_positive: True for success (green), False for error (red).
        size: Icon size in pixels.

    Returns:
        A QIcon for the status.
    """
    provider = get_icon_provider()
    icon_type = IconType.SUCCESS if is_positive else IconType.ERROR
    return provider.get_icon(icon_type, size)


__all__ = [
    "IconProvider",
    "IconStyle",
    "IconType",
    "EMOJI_CHARS",
    "SIMPLIFIED_COLORS",
    "get_icon_provider",
    "get_status_text",
    "get_status_icon",
]
