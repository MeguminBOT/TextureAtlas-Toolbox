"""Core data models and base abstractions for the translator app.

Exports:
    TranslationItem: Data class representing a translatable string.
    TranslationMarker: Enum for quality markers (unsure, machine, complete).
    MARKER_LABELS: Human-readable labels for each marker.
    TranslationError: Exception raised on translation failures.
    TranslationProvider: Abstract base for machine translation backends.
"""

from .translation_item import TranslationItem, TranslationMarker, MARKER_LABELS
from .translation_provider_base import TranslationError, TranslationProvider

__all__ = [
    "MARKER_LABELS",
    "TranslationError",
    "TranslationItem",
    "TranslationMarker",
    "TranslationProvider",
]
