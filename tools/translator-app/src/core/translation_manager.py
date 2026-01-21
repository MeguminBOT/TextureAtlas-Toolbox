"""Coordinate machine translation providers and placeholder preservation.

The TranslationManager class acts as the central hub for interacting with
translation providers (DeepL, Google, LibreTranslate). It also provides
helpers to protect brace-wrapped placeholders during API round-trips.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from localization import QT_LANGUAGE_CHOICES
from .translation_provider_base import TranslationError, TranslationProvider
from providers import (
    DeepLTranslationProvider,
    GoogleTranslationProvider,
    LibreTranslationProvider,
)


class TranslationManager:
    """Coordinate translation providers and protect placeholders during translation.

    This class manages registered translation providers, checks their availability,
    and offers static helpers to shield brace-delimited placeholders from being
    corrupted by external machine translation APIs.

    Attributes:
        providers: Mapping of provider keys ("deepl", "google", "libretranslate")
            to their corresponding TranslationProvider instances.
    """

    def __init__(self) -> None:
        self.providers: Dict[str, TranslationProvider] = {
            "deepl": DeepLTranslationProvider(),
            "google": GoogleTranslationProvider(),
            "libretranslate": LibreTranslationProvider(),
        }

    def get_provider_language_choices(
        self, provider_key: Optional[str]
    ) -> List[Tuple[str, str]]:
        """Return Qt language tuples limited to what the provider reports.

        Args:
            provider_key: Key identifying the provider (e.g., "deepl"), or None
                to return all Qt language choices.

        Returns:
            A list of (code, display_name) tuples for the provider's languages.
        """

        choices = QT_LANGUAGE_CHOICES
        if not provider_key:
            return choices

        provider = self.providers.get(provider_key)
        if not provider:
            return choices

        supported = provider.supported_codes()
        if not supported:
            return choices

        allowed = {code.upper() for code in supported}
        filtered = [entry for entry in choices if entry[0] in allowed]
        return filtered or choices

    def get_provider_name(self, key: Optional[str]) -> str:
        """Return a human-friendly name for a provider key.

        Args:
            key: Provider key such as "deepl" or "google", or None.

        Returns:
            The provider's display name, "Manual" if key is None, or "Unknown".
        """
        if not key:
            return "Manual"
        provider = self.providers.get(key)
        return provider.name if provider else "Unknown"

    def is_provider_available(self, key: Optional[str]) -> tuple[bool, str]:
        """Report whether the requested provider can be used right now.

        Args:
            key: Provider key such as "deepl" or "google", or None.

        Returns:
            A tuple (available, message) indicating readiness and reason.
        """
        if not key:
            return False, "Machine translation disabled."
        provider = self.providers.get(key)
        if not provider:
            return False, "Selected provider is not available."
        return provider.is_available()

    def translate(
        self,
        provider_key: str,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        """Translate text using the specified provider.

        Args:
            provider_key: Key identifying the provider ("deepl", "google", etc.).
            text: Source text to translate.
            target_lang: Target language code.
            source_lang: Optional source language code; auto-detected if omitted.

        Returns:
            The translated text.

        Raises:
            TranslationError: If the provider is unavailable or the request fails.
        """
        provider = self.providers.get(provider_key)
        if not provider:
            raise TranslationError("Selected translation provider is not supported.")
        available, reason = provider.is_available()
        if not available:
            raise TranslationError(reason)
        return provider.translate(text, target_lang, source_lang)

    # Regex patterns for different placeholder types
    # Order matters - more specific patterns should come first
    PLACEHOLDER_PATTERNS = [
        # Qt numbered arguments: %1, %2, %L1, %Ln, etc.
        r"%L?n?\d+",
        # printf-style: %s, %d, %f, %x, %.2f, %03d, etc.
        r"%[-+0 #]*\d*\.?\d*[hlL]?[diouxXeEfFgGaAcspn%]",
        # Brace placeholders: {value}, {0}, {name_here}
        r"\{[^}]*\}",
        # HTML/XML tags: <b>, </b>, <br/>, <a href="...">, etc.
        r"<[^>]+>",
        # Keyboard accelerators: &File, &Save (but not &&)
        r"(?<!&)&(?!&)(?=[a-zA-Z])",
    ]

    # Regex to find our placeholder tokens in translated text (case-insensitive)
    # Token formats we accept (MT engines sometimes drop a bracket or add spaces):
    #   [[PH0]], [[PH 0]], [[ ph0 ]], [PH0]], [[PH], PH0, ph0
    _TOKEN_PATTERN = re.compile(
        r"\[\[?\s*PH\s*(\d+)\s*\]?\]?|PH\s*(\d+)", re.IGNORECASE
    )

    @staticmethod
    def protect_placeholders(text: str) -> tuple[str, Dict[int, str]]:
        """Replace placeholders with unique tokens to survive translation.

        Machine translation APIs may corrupt placeholders like ``{value}``,
        ``%1``, ``%s``, or HTML tags. This method replaces them with
        neutral tokens ([[PH0]], [[PH1]]...) that engines generally leave alone,
        returning a mapping to restore them afterward.

        Supported placeholder types:
            - Qt numbered arguments: %1, %2, %L1, %Ln
            - printf-style: %s, %d, %f, %.2f, %03d
            - Brace placeholders: {value}, {0}, {name}
            - HTML/XML tags: <b>, </b>, <br/>, <a href="...">
            - Qt keyboard accelerators: &F in "&File"

        Args:
            text: The source string containing placeholders.

        Returns:
            A tuple of (protected_text, mapping) where mapping maps tokens
            back to their original placeholder strings.
        """
        mapping: Dict[int, str] = {}
        protected_text = text

        # Build combined pattern from all placeholder types
        combined_pattern = "|".join(
            f"({pattern})" for pattern in TranslationManager.PLACEHOLDER_PATTERNS
        )

        def repl(match: re.Match) -> str:
            original = match.group(0)
            token_id = len(mapping)
            token = f"[[PH{token_id}]]"
            mapping[token_id] = original
            return token

        protected_text = re.sub(combined_pattern, repl, text)
        return protected_text, mapping

    @classmethod
    def restore_placeholders(cls, text: str, mapping: Dict[int, str]) -> str:
        """Replace tokens back to their original placeholders.

        Uses regex matching to handle variations in how translation APIs
        return the placeholder tokens (whitespace changes, quote changes, etc.).

        Args:
            text: Translated text containing placeholder tokens.
            mapping: ID-to-placeholder mapping produced by protect_placeholders.

        Returns:
            The text with tokens replaced by their original placeholders
            (Qt arguments, printf specifiers, braces, HTML tags, etc.).
        """

        def repl(match: re.Match) -> str:
            # group(1) for bracketed/partial bracket tokens, group(2) for bare PHn
            token_group = match.group(1) or match.group(2)
            token_id = int(token_group)
            return mapping.get(token_id, match.group(0))

        restored = cls._TOKEN_PATTERN.sub(repl, text)
        return restored


__all__ = ["TranslationManager"]
