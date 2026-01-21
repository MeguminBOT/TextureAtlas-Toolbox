"""Custom filter proxy model for translation list filtering.

Provides efficient, stable filtering of translation items without
destroying/recreating Qt widgets on each keystroke.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import (
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)


# Role constants for the model
class TranslationRoles:
    """Custom data roles for translation items in the model."""

    ItemRole = Qt.UserRole  # Stores the TranslationItem object
    SourceRole = Qt.UserRole + 1  # Source text (lowercase for filtering)
    TranslationRole = Qt.UserRole + 2  # Translation text (lowercase for filtering)
    HasPlaceholdersRole = Qt.UserRole + 3  # bool
    IsMachineTranslatedRole = Qt.UserRole + 4  # bool
    IsTranslatedRole = Qt.UserRole + 5  # bool
    MarkerRole = Qt.UserRole + 6  # TranslationMarker enum
    IsVanishedRole = Qt.UserRole + 7  # bool
    ContextsRole = Qt.UserRole + 8  # List of context strings (lowercase)


class TranslationFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy model with support for keyword-based translation filtering.

    Supports structured filter syntax with prefixes:
    - is:translated, is:missing, is:mt, is:unsure, is:vanished
    - has:placeholder
    - ctx:<name> or context:<name>
    - Plain text: Searches in source and translation text

    Examples:
        "is:missing"           - Show only untranslated items
        "is:mt has:placeholder" - Machine translated items with placeholders
        "ctx:main_window"      - Items in main_window context
        "hello world"          - Items containing "hello world"
    """

    IS_TRANSLATED = frozenset({"translated", "done"})
    IS_MISSING = frozenset({"missing", "untranslated"})
    IS_MT = frozenset({"mt", "machine"})
    IS_UNSURE = frozenset({"unsure"})
    IS_VANISHED = frozenset({"vanished", "obsolete"})
    HAS_PLACEHOLDER = frozenset({"placeholder", "placeholders", "ph"})

    def __init__(self, parent=None) -> None:
        """Initialize the filter proxy model.

        Args:
            parent: Parent Qt object, typically the view using this proxy.
        """
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._filter_text: str = ""
        self._require_placeholders: bool = False
        self._require_machine: bool = False
        self._require_translated: bool = False
        self._require_untranslated: bool = False
        self._require_unsure: bool = False
        self._require_vanished: bool = False
        self._context_terms: List[str] = []
        self._search_text: str = ""

    def set_filter_text(self, text: str) -> None:
        """Set the filter text and re-parse keywords.

        Args:
            text: The raw filter string from the search input.
        """
        if text == self._filter_text:
            return

        self._filter_text = text
        self._parse_filter(text)
        self.invalidateFilter()

    def _parse_filter(self, raw_filter: str) -> None:
        """Parse the filter string into keyword flags and search text.

        Syntax:
            is:<status>  - Filter by status (translated, missing, mt, unsure, vanished)
            has:<feature> - Filter by feature (placeholder)
            ctx:<name>   - Filter by context name
            <text>       - Plain text search in source/translation
        """
        self._require_placeholders = False
        self._require_machine = False
        self._require_translated = False
        self._require_untranslated = False
        self._require_unsure = False
        self._require_vanished = False
        self._context_terms = []
        self._search_text = ""

        if not raw_filter.strip():
            return

        tokens = [tok for tok in raw_filter.strip().lower().split() if tok]
        remaining_parts: List[str] = []

        for token in tokens:
            # Handle "is:" prefix for status filters
            if token.startswith("is:"):
                value = token[3:]  # Remove "is:" prefix
                if value in self.IS_TRANSLATED:
                    self._require_translated = True
                elif value in self.IS_MISSING:
                    self._require_untranslated = True
                elif value in self.IS_MT:
                    self._require_machine = True
                elif value in self.IS_UNSURE:
                    self._require_unsure = True
                elif value in self.IS_VANISHED:
                    self._require_vanished = True
                # Unknown is: value - ignore silently

            # Handle "has:" prefix for feature filters
            elif token.startswith("has:"):
                value = token[4:]  # Remove "has:" prefix
                if value in self.HAS_PLACEHOLDER:
                    self._require_placeholders = True
            elif token.startswith("ctx:") or token.startswith("context:"):
                term = token.split(":", 1)[1].strip()
                if term:
                    self._context_terms.append(term)
            else:
                remaining_parts.append(token)

        self._search_text = " ".join(remaining_parts).strip()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Determine if a row should be visible based on the current filter.

        Args:
            source_row: Row index in the source model.
            source_parent: Parent index (unused for flat lists).

        Returns:
            True if the row should be shown, False to hide it.
        """
        # No filter = show all
        if not self._filter_text.strip():
            return True

        # Contradictory filter - hide all
        if self._require_translated and self._require_untranslated:
            return False

        model = self.sourceModel()
        if model is None:
            return True

        index = model.index(source_row, 0, source_parent)

        # Check keyword filters
        if self._require_placeholders:
            has_ph = index.data(TranslationRoles.HasPlaceholdersRole)
            if not has_ph:
                return False

        if self._require_machine:
            is_machine = index.data(TranslationRoles.IsMachineTranslatedRole)
            if not is_machine:
                return False

        if self._require_translated:
            is_translated = index.data(TranslationRoles.IsTranslatedRole)
            if not is_translated:
                return False

        if self._require_untranslated:
            is_translated = index.data(TranslationRoles.IsTranslatedRole)
            if is_translated:
                return False

        if self._require_unsure:
            from core import TranslationMarker

            marker = index.data(TranslationRoles.MarkerRole)
            if marker != TranslationMarker.UNSURE:
                return False

        if self._require_vanished:
            is_vanished = index.data(TranslationRoles.IsVanishedRole)
            if not is_vanished:
                return False

        if self._context_terms:
            contexts = index.data(TranslationRoles.ContextsRole) or []
            if not any(
                any(term in ctx for term in self._context_terms) for ctx in contexts
            ):
                return False

        if self._search_text:
            source_text = index.data(TranslationRoles.SourceRole) or ""
            translation_text = index.data(TranslationRoles.TranslationRole) or ""
            if (
                self._search_text not in source_text
                and self._search_text not in translation_text
            ):
                return False

        return True


__all__ = ["TranslationFilterProxyModel", "TranslationRoles"]
