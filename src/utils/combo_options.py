#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized definitions for translatable combo box options.

This module provides index-mapped option definitions for combo boxes that
need translatable display text while maintaining stable internal values
for settings persistence and logic.

Usage:
    from utils.combo_options import (
        FRAME_SELECTION_OPTIONS,
        CROPPING_METHOD_OPTIONS,
        FILENAME_FORMAT_OPTIONS,
        ANIMATION_FORMAT_OPTIONS,
        ANIMATION_FORMAT_OPTIONS_WITH_NONE,
        FRAME_FORMAT_OPTIONS,
        GENERATOR_IMAGE_FORMAT_OPTIONS,
        TIFF_COMPRESSION_OPTIONS,
        get_display_text,
        get_internal_value,
        populate_combobox,
    )

    # Populate a combobox with translated options
    populate_combobox(combo, FRAME_SELECTION_OPTIONS, tr_func)

    # Get display text for an internal value
    display = get_display_text(FRAME_SELECTION_OPTIONS, "no_duplicates", tr_func)

    # Get internal value from a display text
    value = get_internal_value(FRAME_SELECTION_OPTIONS, "Sem duplicatas", tr_func)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import QT_TRANSLATE_NOOP


# =============================================================================
# Translation markers for pyside6-lupdate
# =============================================================================
# QT_TRANSLATE_NOOP marks strings for extraction without translating them.
# The actual translation happens at runtime via the tr_func passed to helpers.
# fmt: off
_FRAME_SELECTION_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "All"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No duplicates"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "First"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Last"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "First, Last"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Custom"),
)
_CROPPING_METHOD_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "None"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation based"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame based"),
)
_FILENAME_FORMAT_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Standardized"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No spaces"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No special characters"),
)
# Note: Animation/frame formats use technical names that typically stay in English
# fmt: on


@dataclass(frozen=True)
class ComboOption:
    """Represents a single combo box option.

    Attributes:
        internal: The stable internal value used for settings/logic.
        display_key: The English display string (also used as translation key).
    """

    internal: str
    display_key: str


# Frame selection options (All, No duplicates, First, Last, First/Last, Custom)
FRAME_SELECTION_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("all", "All"),
    ComboOption("no_duplicates", "No duplicates"),
    ComboOption("first", "First"),
    ComboOption("last", "Last"),
    ComboOption("first_last", "First, Last"),
    ComboOption("custom", "Custom"),
)

# Cropping method options (None, Animation based, Frame based)
CROPPING_METHOD_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("none", "None"),
    ComboOption("animation", "Animation based"),
    ComboOption("frame", "Frame based"),
)

# Filename format options
FILENAME_FORMAT_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("standardized", "Standardized"),
    ComboOption("no_spaces", "No spaces"),
    ComboOption("no_special", "No special characters"),
)

# =============================================================================
# Animation & Frame Format Options
# =============================================================================
# Note: Format names (GIF, WebP, PNG, etc.) are technical terms that typically
# remain in English across all languages. They use the format extension as
# their internal value for direct file extension mapping.

# Animation format options - used in extract tab, app config, etc.
ANIMATION_FORMAT_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("gif", "GIF"),
    ComboOption("webp", "WebP"),
    ComboOption("apng", "APNG"),
)

# Animation format options WITH "None" - used in override settings
# where "None" means "use default/don't override"
ANIMATION_FORMAT_OPTIONS_WITH_NONE: Tuple[ComboOption, ...] = (
    ComboOption("none", "None"),
    ComboOption("gif", "GIF"),
    ComboOption("webp", "WebP"),
    ComboOption("apng", "APNG"),
)

# Frame/image format options - used in extract tab, app config, override settings, etc.
# Alphabetically ordered for consistent UI presentation
FRAME_FORMAT_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("avif", "AVIF"),
    ComboOption("bmp", "BMP"),
    ComboOption("dds", "DDS"),
    ComboOption("png", "PNG"),
    ComboOption("tga", "TGA"),
    ComboOption("tiff", "TIFF"),
    ComboOption("webp", "WebP"),
)

# Generator image format options - used in texture atlas generator
# Different from frame formats: includes JPEG, excludes AVIF/DDS
GENERATOR_IMAGE_FORMAT_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("bmp", "BMP"),
    ComboOption("jpeg", "JPEG"),
    ComboOption("png", "PNG"),
    ComboOption("tga", "TGA"),
    ComboOption("tiff", "TIFF"),
    ComboOption("webp", "WebP"),
)

# TIFF compression options - used across compression settings
TIFF_COMPRESSION_OPTIONS: Tuple[ComboOption, ...] = (
    ComboOption("none", "None"),
    ComboOption("lzw", "LZW"),
    ComboOption("deflate", "Deflate"),
    ComboOption("packbits", "PackBits"),
    ComboOption("jpeg", "JPEG"),
)


def get_display_texts(
    options: Tuple[ComboOption, ...],
    tr_func: Optional[Callable[[str], str]] = None,
) -> List[str]:
    """Get a list of display texts for populating a combobox.

    Args:
        options: Tuple of ComboOption definitions.
        tr_func: Optional translation function. If None, returns English keys.

    Returns:
        List of display strings (translated if tr_func provided).
    """
    if tr_func is None:
        return [opt.display_key for opt in options]
    return [tr_func(opt.display_key) for opt in options]


def get_display_text(
    options: Tuple[ComboOption, ...],
    internal_value: str,
    tr_func: Optional[Callable[[str], str]] = None,
) -> str:
    """Get the display text for a given internal value.

    Args:
        options: Tuple of ComboOption definitions.
        internal_value: The internal value to look up.
        tr_func: Optional translation function.

    Returns:
        The (optionally translated) display text, or the internal value if not found.
    """
    for opt in options:
        if opt.internal == internal_value:
            return tr_func(opt.display_key) if tr_func else opt.display_key
    return internal_value


def get_internal_value(
    options: Tuple[ComboOption, ...],
    display_text: str,
    tr_func: Optional[Callable[[str], str]] = None,
) -> str:
    """Get the internal value for a given display text.

    Matches against both the English key and translated text.

    Args:
        options: Tuple of ComboOption definitions.
        display_text: The display text to look up.
        tr_func: Optional translation function for matching translated text.

    Returns:
        The internal value, or the display_text if not found.
    """
    for opt in options:
        if opt.display_key == display_text:
            return opt.internal
        if tr_func and tr_func(opt.display_key) == display_text:
            return opt.internal
    return display_text


def get_internal_by_index(
    options: Tuple[ComboOption, ...],
    index: int,
) -> str:
    """Get the internal value at a specific index.

    Args:
        options: Tuple of ComboOption definitions.
        index: Zero-based index into the options.

    Returns:
        The internal value at that index, or empty string if out of range.
    """
    if 0 <= index < len(options):
        return options[index].internal
    return ""


def get_index_by_internal(
    options: Tuple[ComboOption, ...],
    internal_value: str,
) -> int:
    """Get the index for a given internal value.

    Args:
        options: Tuple of ComboOption definitions.
        internal_value: The internal value to find.

    Returns:
        The zero-based index, or 0 if not found.
    """
    for i, opt in enumerate(options):
        if opt.internal == internal_value:
            return i
    return 0


def get_index_by_display(
    options: Tuple[ComboOption, ...],
    display_text: str,
    tr_func: Optional[Callable[[str], str]] = None,
) -> int:
    """Get the index for a given display text.

    Matches against both the English display_key and translated text.

    Args:
        options: Tuple of ComboOption definitions.
        display_text: The display text to look up.
        tr_func: Optional translation function for matching translated text.

    Returns:
        The zero-based index, or 0 if not found.
    """
    for i, opt in enumerate(options):
        if opt.display_key == display_text:
            return i
        if tr_func and tr_func(opt.display_key) == display_text:
            return i
    return 0


def populate_combobox(
    combobox: QComboBox,
    options: Tuple[ComboOption, ...],
    tr_func: Optional[Callable[[str], str]] = None,
    set_data: bool = True,
) -> None:
    """Populate a QComboBox with translated options.

    Args:
        combobox: The QComboBox to populate.
        options: Tuple of ComboOption definitions.
        tr_func: Optional translation function.
        set_data: If True, sets the internal value as item data.
    """
    combobox.clear()
    for opt in options:
        display = tr_func(opt.display_key) if tr_func else opt.display_key
        if set_data:
            combobox.addItem(display, opt.internal)
        else:
            combobox.addItem(display)


def update_combobox_texts(
    combobox: QComboBox,
    options: Tuple[ComboOption, ...],
    tr_func: Optional[Callable[[str], str]] = None,
) -> None:
    """Update existing combobox items with translated text and item data.

    Preserves selection by index. Use this when retranslating the UI
    without rebuilding the combobox.

    Args:
        combobox: The QComboBox to update.
        options: Tuple of ComboOption definitions.
        tr_func: Optional translation function.
    """
    current_index = combobox.currentIndex()
    for i, opt in enumerate(options):
        if i < combobox.count():
            display = tr_func(opt.display_key) if tr_func else opt.display_key
            combobox.setItemText(i, display)
            combobox.setItemData(i, opt.internal)
    if current_index >= 0:
        combobox.setCurrentIndex(current_index)


# Legacy compatibility: Mapping from old internal values to new ones.
# These mappings support settings files that used the display text as the value.
LEGACY_FRAME_SELECTION_MAP = {
    "All": "all",
    "No duplicates": "no_duplicates",
    "First": "first",
    "Last": "last",
    "First, Last": "first_last",
    "Custom": "custom",
}

LEGACY_CROPPING_METHOD_MAP = {
    "None": "none",
    "Animation based": "animation",
    "Frame based": "frame",
}

LEGACY_FILENAME_FORMAT_MAP = {
    "Standardized": "standardized",
    "No spaces": "no_spaces",
    "No special characters": "no_special",
}


def normalize_legacy_value(
    legacy_map: dict,
    value: str,
) -> str:
    """Convert a legacy display-text value to the new internal format.

    Args:
        legacy_map: Dictionary mapping old values to new internal values.
        value: The value to normalize (may be old or new format).

    Returns:
        The normalized internal value.
    """
    return legacy_map.get(value, value)
