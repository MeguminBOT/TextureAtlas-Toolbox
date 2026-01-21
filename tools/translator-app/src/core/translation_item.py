"""Data model for a single translation entry or group of identical source strings.

This module defines the TranslationItem class, the core data structure used
throughout the translator application to represent translatable strings loaded
from Qt .ts files.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple


class TranslationMarker(Enum):
    """Quality markers that translators can apply to translations.

    These markers help track the confidence level of translations and
    flag items that may need additional review or improvement.
    """

    NONE = ""  # No marker (default)
    UNSURE = "unsure"  # Translator is unsure about this translation
    MACHINE_TRANSLATED = "machine"  # Machine translated, needs human review
    COMPLETE = "complete"  # Fully verified and complete translation

    @classmethod
    def from_string(cls, value: Optional[str]) -> "TranslationMarker":
        """Convert a string to a TranslationMarker.

        Args:
            value: The marker string, or None.

        Returns:
            The corresponding TranslationMarker, or NONE if not found.
        """
        if not value:
            return cls.NONE
        for member in cls:
            if member.value == value:
                return member
        return cls.NONE


# Human-readable labels for markers
MARKER_LABELS: Dict[TranslationMarker, str] = {
    TranslationMarker.NONE: "None",
    TranslationMarker.UNSURE: "Unsure",
    TranslationMarker.MACHINE_TRANSLATED: "Machine Translated",
    TranslationMarker.COMPLETE: "Complete",
}


class TranslationItem:
    """A single translatable string or group of identical source strings.

    When multiple contexts share the same source text, this class aggregates
    them into a single logical entry. This reduces duplication and lets the
    translator provide one translation for all occurrences.

    Attributes:
        source: The original English (or source-language) text.
        translation: The translated text (empty until provided).
        contexts: Context names where this string appears.
        locations: List of (filename, line) tuples for each context.
        is_translated: True if translation is non-empty.
        is_machine_translated: True if translated by machine and not yet reviewed.
        marker: Quality marker for this translation (unsure, needs review, etc.).
    """

    def __init__(
        self,
        source: str,
        translation: str = "",
        context: str = "",
        filename: str = "",
        line: int = 0,
        marker: Optional[TranslationMarker] = None,
        is_machine_translated: bool = False,
        is_vanished: bool = False,
    ) -> None:
        """Initialize a translation entry.

        Args:
            source: The original source text to translate.
            translation: Existing translation, if any.
            context: Qt context name (e.g., class name) where the string appears.
            filename: Source file where the string is defined.
            line: Line number in the source file.
            marker: Quality marker for the translation.
            is_machine_translated: True if translated by machine translation.
            is_vanished: True if this string was marked vanished/obsolete by lupdate.
        """
        self.source = source
        self.translation = translation or ""
        self.contexts = [context] if context else []
        self.locations: List[Tuple[str, int]] = [(filename, line)] if filename else []
        self.is_translated = bool(self.translation.strip())
        self.is_machine_translated = is_machine_translated
        self.marker = marker if marker else TranslationMarker.NONE
        self.is_vanished = is_vanished

    def add_context(self, context: str, filename: str = "", line: int = 0) -> None:
        """Track another context that reuses this string.

        Args:
            context: Qt context name (e.g., class name) to add.
            filename: Source file where the string appears.
            line: Line number in the source file.
        """
        if context and context not in self.contexts:
            self.contexts.append(context)
        if filename and (filename, line) not in self.locations:
            self.locations.append((filename, line))

    def get_context_display(self) -> str:
        """Return a short label for list views.

        Returns:
            A single context name or a summary like "ContextA (+2 more)".
        """
        if len(self.contexts) == 1:
            return self.contexts[0]
        if len(self.contexts) > 1:
            return f"{self.contexts[0]} (+{len(self.contexts) - 1} more)"
        return "Unknown"

    def get_all_contexts_info(self) -> str:
        """Return an expanded list of contexts/locations grouped by context name.

        Groups locations by context so the same context isn't repeated.
        Each context is shown once with all its file locations listed below.

        Returns:
            A multi-line string with each context and its source locations.
        """
        # Group locations by context name
        context_to_locations: Dict[str, List[Tuple[str, int]]] = {}
        for i, context in enumerate(self.contexts):
            if context not in context_to_locations:
                context_to_locations[context] = []
            if i < len(self.locations):
                context_to_locations[context].append(self.locations[i])

        # Build output with each context shown once
        info_lines = []
        for context, locations in context_to_locations.items():
            if locations:
                files_info = "\n".join(
                    f"  • {filename}:{line}" for filename, line in locations
                )
                info_lines.append(f"Context: {context}\n{files_info}")
            else:
                info_lines.append(f"Context: {context}")
        return "\n\n".join(info_lines)

    @property
    def context(self) -> str:
        """The primary context name, or empty string if none."""
        return self.contexts[0] if self.contexts else ""

    @property
    def filename(self) -> str:
        """The primary source filename, or empty string if none."""
        return self.locations[0][0] if self.locations else ""

    @property
    def line(self) -> int:
        """The primary source line number, or 0 if unknown."""
        return self.locations[0][1] if self.locations else 0

    def has_placeholders(self) -> bool:
        """Check whether the source text contains brace-delimited placeholders.

        Returns:
            True if the source contains at least one ``{...}`` token.
        """
        return bool(re.search(r"\{[^}]*\}", self.source))

    def get_placeholders(self) -> List[str]:
        """Extract all brace-delimited placeholders from the source text.

        Returns:
            A list of placeholder tokens including braces (e.g., ['{name}', '{count}']).
        """
        return re.findall(r"\{[^}]*\}", self.source)

    def preview_with_placeholders(self, placeholder_values: Dict[str, str]) -> str:
        """Render the translation with placeholders replaced by sample values.

        Args:
            placeholder_values: Mapping from placeholder key (with or without braces)
                to the display value.

        Returns:
            The translation text with placeholders substituted, or empty string
            if no translation exists.
        """
        if not self.translation:
            return ""

        preview = self.translation
        placeholders = self.get_placeholders()

        for placeholder in placeholders:
            key = placeholder.strip("{}")
            if key in placeholder_values:
                preview = preview.replace(placeholder, placeholder_values[key])
            elif placeholder in placeholder_values:
                preview = preview.replace(placeholder, placeholder_values[placeholder])
            else:
                preview = preview.replace(placeholder, f"[{key}]")

        return preview

    def validate_translation(self) -> tuple[bool, str]:
        """Validate that the translation preserves all source placeholders.

        Returns:
            A tuple (is_valid, error_message). If valid, error_message is empty.
        """
        if not self.translation.strip():
            return True, ""

        source_placeholders = set(self.get_placeholders())
        translation_placeholders = set(re.findall(r"\{[^}]*\}", self.translation))

        missing_placeholders = source_placeholders - translation_placeholders
        extra_placeholders = translation_placeholders - source_placeholders

        errors = []
        if missing_placeholders:
            errors.append(f"Missing placeholders: {', '.join(missing_placeholders)}")
        if extra_placeholders:
            errors.append(f"Extra placeholders: {', '.join(extra_placeholders)}")

        if errors:
            return False, "; ".join(errors)
        return True, ""


__all__ = ["TranslationItem"]
