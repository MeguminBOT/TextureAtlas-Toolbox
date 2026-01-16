"""GUI helper components for the translator app."""

from .add_language_dialog import AddLanguageDialog
from .batch_unused_dialog import BatchUnusedStringsDialog
from .icon_provider import (
    IconProvider,
    IconStyle,
    IconType,
    get_icon_provider,
    get_status_icon,
    get_status_text,
)
from .placeholder_highlighter import PlaceholderHighlighter
from .shortcuts_dialog import ShortcutsDialog, DEFAULT_SHORTCUTS, SHORTCUT_LABELS
from .theme_options_dialog import ThemeOptionsDialog
from .themes import apply_app_theme, theme_stylesheet
from .translation_filter_model import TranslationFilterProxyModel, TranslationRoles
from .unused_strings_dialog import UnusedStringsDialog

__all__ = [
    "AddLanguageDialog",
    "BatchUnusedStringsDialog",
    "DEFAULT_SHORTCUTS",
    "IconProvider",
    "IconStyle",
    "IconType",
    "PlaceholderHighlighter",
    "SHORTCUT_LABELS",
    "ShortcutsDialog",
    "ThemeOptionsDialog",
    "TranslationFilterProxyModel",
    "TranslationRoles",
    "UnusedStringsDialog",
    "apply_app_theme",
    "get_icon_provider",
    "get_status_icon",
    "get_status_text",
    "theme_stylesheet",
]
