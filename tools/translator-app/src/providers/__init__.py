"""Machine translation provider implementations.

Each provider wraps a third-party translation API (DeepL, Google Cloud,
LibreTranslate) and implements the TranslationProvider interface.
"""

from .deepl import DeepLTranslationProvider
from .google import GoogleTranslationProvider
from .libretranslate import LibreTranslationProvider

__all__ = [
    "DeepLTranslationProvider",
    "GoogleTranslationProvider",
    "LibreTranslationProvider",
]
