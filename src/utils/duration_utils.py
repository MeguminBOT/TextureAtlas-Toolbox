#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Duration conversion utilities for animation timing.

Provides functions to convert between different duration units used in
animation export formats and user interfaces.

Duration Types:
    - native: Format-specific (GIF=centiseconds, WebP/APNG=milliseconds)
    - fps: Frames per second (converted to milliseconds via 1000/fps)
    - deciseconds: 1/10th of a second (100ms increments)
    - centiseconds: 1/100th of a second (10ms increments)
    - milliseconds: 1/1000th of a second

Usage:
    from utils.duration_utils import (
        duration_to_milliseconds,
        milliseconds_to_duration,
        get_duration_label,
        get_duration_range,
    )

    # Convert user input to milliseconds for export
    ms = duration_to_milliseconds(24, "fps")  # 41ms
    ms = duration_to_milliseconds(10, "centiseconds") # 100ms

    # Convert milliseconds to display unit
    display = milliseconds_to_duration(100, "centiseconds")  # 10
"""

from __future__ import annotations

from typing import NamedTuple, Tuple

from PySide6.QtCore import QT_TRANSLATE_NOOP


DURATION_FPS = "fps"
DURATION_NATIVE = "native"
DURATION_DECISECONDS = "deciseconds"
DURATION_CENTISECONDS = "centiseconds"
DURATION_MILLISECONDS = "milliseconds"

DURATION_TYPES = (
    DURATION_FPS,
    DURATION_NATIVE,
    DURATION_DECISECONDS,
    DURATION_CENTISECONDS,
    DURATION_MILLISECONDS,
)

DURATION_SUFFIXES = {
    DURATION_FPS: " fps",
    DURATION_DECISECONDS: " ds",
    DURATION_CENTISECONDS: " cs",
    DURATION_MILLISECONDS: " ms",
}

NATIVE_DURATION_MAP = {
    "GIF": DURATION_CENTISECONDS,
    "WEBP": DURATION_MILLISECONDS,
    "APNG": DURATION_MILLISECONDS,
}


def resolve_native_duration_type(animation_format: str) -> str:
    """Resolve 'native' duration type to the format-specific type.

    Args:
        animation_format: Animation format name (GIF, WebP, APNG).

    Returns:
        The format-native duration type (centiseconds for GIF,
        milliseconds for WebP/APNG).
    """
    return NATIVE_DURATION_MAP.get(animation_format.upper(), DURATION_MILLISECONDS)


def duration_to_milliseconds(
    value: int | float,
    duration_type: str,
    animation_format: str,
) -> int:
    """Convert a duration value to milliseconds.

    Args:
        value: The duration value in the specified unit.
        duration_type: One of 'fps', 'native', 'deciseconds',
            'centiseconds', or 'milliseconds'.
        animation_format: Animation format name, used when duration_type
            is 'native' to determine the native unit.

    Returns:
        The duration in milliseconds, minimum 1ms.

    Raises:
        ValueError: If duration_type is not recognized.
    """
    if duration_type == DURATION_NATIVE:
        duration_type = resolve_native_duration_type(animation_format)

    if duration_type == DURATION_FPS:
        fps = max(1, float(value))
        return max(1, round(1000 / fps))
    elif duration_type == DURATION_DECISECONDS:
        return max(1, int(value * 100))
    elif duration_type == DURATION_CENTISECONDS:
        return max(1, int(value * 10))
    elif duration_type == DURATION_MILLISECONDS:
        return max(1, int(value))
    else:
        raise ValueError(f"Unknown duration type: {duration_type}")


def milliseconds_to_duration(
    ms: int,
    duration_type: str,
    animation_format: str,
) -> int:
    """Convert milliseconds to the specified duration unit.

    Args:
        ms: The duration in milliseconds.
        duration_type: One of 'fps', 'native', 'deciseconds',
            'centiseconds', or 'milliseconds'.
        animation_format: Animation format name, used when duration_type
            is 'native' to determine the native unit.

    Returns:
        The duration in the specified unit.

    Raises:
        ValueError: If duration_type is not recognized.
    """
    ms = max(1, int(ms))

    if duration_type == DURATION_NATIVE:
        duration_type = resolve_native_duration_type(animation_format)

    if duration_type == DURATION_FPS:
        return max(1, round(1000 / ms))
    elif duration_type == DURATION_DECISECONDS:
        return max(1, round(ms / 100))
    elif duration_type == DURATION_CENTISECONDS:
        return max(1, round(ms / 10))
    elif duration_type == DURATION_MILLISECONDS:
        return ms
    else:
        raise ValueError(f"Unknown duration type: {duration_type}")


def convert_duration(
    value: int | float,
    from_type: str,
    to_type: str,
    animation_format: str,
) -> int:
    """Convert a duration value from one unit to another.

    This is a convenience function that combines duration_to_milliseconds
    and milliseconds_to_duration for direct type-to-type conversion.

    Args:
        value: The duration value in the source unit.
        from_type: Source duration type (fps, native, deciseconds, etc.).
        to_type: Target duration type (fps, native, deciseconds, etc.).
        animation_format: Animation format name, used to resolve 'native'.

    Returns:
        The duration value converted to the target unit.

    Example:
        >>> convert_duration(24, "fps", "milliseconds", "GIF")
        42
        >>> convert_duration(42, "milliseconds", "centiseconds", "GIF")
        4
    """
    ms = duration_to_milliseconds(value, from_type, animation_format)
    return milliseconds_to_duration(ms, to_type, animation_format)


def get_duration_label(duration_type: str, animation_format: str) -> str:
    """Get the display label for a duration type.

    Args:
        duration_type: The duration type identifier.
        animation_format: Animation format name, used when duration_type
            is 'native'.

    Returns:
        A human-readable label for the duration type.
    """
    if duration_type == DURATION_NATIVE:
        duration_type = resolve_native_duration_type(animation_format)

    labels = {
        DURATION_FPS: QT_TRANSLATE_NOOP("ExtractTabWidget", "Frame rate"),
        DURATION_DECISECONDS: QT_TRANSLATE_NOOP("ExtractTabWidget", "Frame delay (ds)"),
        DURATION_CENTISECONDS: QT_TRANSLATE_NOOP(
            "ExtractTabWidget", "Frame delay (cs)"
        ),
        DURATION_MILLISECONDS: QT_TRANSLATE_NOOP(
            "ExtractTabWidget", "Frame delay (ms)"
        ),
    }
    return labels.get(
        duration_type, QT_TRANSLATE_NOOP("ExtractTabWidget", "Frame rate")
    )


def get_duration_range(duration_type: str, animation_format: str) -> Tuple[int, int]:
    """Get the valid input range for a duration type.

    Args:
        duration_type: The duration type identifier.
        animation_format: Animation format name, used when duration_type
            is 'native'.

    Returns:
        A tuple of (min_value, max_value) for the spinbox.
    """
    if duration_type == DURATION_NATIVE:
        duration_type = resolve_native_duration_type(animation_format)

    ranges = {
        DURATION_FPS: (1, 1000),
        DURATION_DECISECONDS: (1, 1000),
        DURATION_CENTISECONDS: (1, 10000),
        DURATION_MILLISECONDS: (1, 100000),
    }
    return ranges.get(duration_type, (1, 1000))


def get_duration_tooltip(duration_type: str, animation_format: str) -> str:
    """Get a tooltip description for a duration type.

    Args:
        duration_type: The duration type identifier.
        animation_format: Animation format name, used when duration_type
            is 'native'.

    Returns:
        A tooltip string explaining the duration unit.
    """
    if duration_type == DURATION_NATIVE:
        duration_type = resolve_native_duration_type(animation_format)

    tooltips = {
        DURATION_FPS: QT_TRANSLATE_NOOP(
            "ExtractTabWidget", "Frames per second (1-1000)"
        ),
        DURATION_DECISECONDS: QT_TRANSLATE_NOOP(
            "ExtractTabWidget", "Frame delay in deciseconds (1 = 100ms, 10 = 1 second)"
        ),
        DURATION_CENTISECONDS: QT_TRANSLATE_NOOP(
            "ExtractTabWidget", "Frame delay in centiseconds (1 = 10ms, 100 = 1 second)"
        ),
        DURATION_MILLISECONDS: QT_TRANSLATE_NOOP(
            "ExtractTabWidget", "Frame delay in milliseconds (1000 = 1 second)"
        ),
    }
    return tooltips.get(
        duration_type,
        QT_TRANSLATE_NOOP("ExtractTabWidget", "Frames per second (1-1000)"),
    )


class DurationDisplayMeta(NamedTuple):
    """Metadata describing how to display a duration control."""

    resolved_type: str
    label: str
    tooltip: str
    suffix: str
    min_value: int
    max_value: int


class StoredDuration(NamedTuple):
    """Container for duration values that preserves FPS precision.

    When storing FPS values, integer milliseconds can't perfectly represent
    all frame rates. For example, 60 FPS = 16.67ms, which rounds to 17ms,
    and converting back gives 59 FPS.

    This class stores both the millisecond value (for formats that need it)
    and the original display value with its type, allowing perfect round-trips.
    """

    duration_ms: int
    display_value: int
    display_type: str


def store_duration(
    display_value: int,
    duration_type: str,
    animation_format: str,
) -> StoredDuration:
    """Create a StoredDuration that preserves the original display value.

    Args:
        display_value: The value as entered by the user (e.g., 60 for 60fps).
        duration_type: The duration type (fps, centiseconds, etc.).
        animation_format: Animation format for resolving 'native' type.

    Returns:
        A StoredDuration containing both ms and original display values.
    """
    resolved_type = duration_type
    if duration_type == DURATION_NATIVE:
        resolved_type = resolve_native_duration_type(animation_format)

    duration_ms = duration_to_milliseconds(
        display_value, resolved_type, animation_format
    )
    return StoredDuration(
        duration_ms=duration_ms,
        display_value=display_value,
        display_type=resolved_type,
    )


def load_duration_display_value(
    duration_ms: int,
    stored_display_value: int | None,
    stored_display_type: str | None,
    target_display_type: str,
    animation_format: str,
) -> int:
    """Load the display value, using stored value when types match.

    This function enables lossless FPS round-trips by returning the
    originally stored display value when the target type matches.

    Args:
        duration_ms: The duration in milliseconds (fallback source).
        stored_display_value: The originally stored display value, if any.
        stored_display_type: The type of the stored display value.
        target_display_type: The type to display (fps, centiseconds, etc.).
        animation_format: Animation format for resolving 'native' type.

    Returns:
        The display value to show in the UI.

    Example:
        >>> # User stored 60 FPS -> 17ms
        >>> load_duration_display_value(17, 60, "fps", "fps", "GIF")
        60  # Returns exact original, not round(1000/17)=59
        >>> load_duration_display_value(17, 60, "fps", "milliseconds", "GIF")
        17  # Different type, convert from ms
    """
    resolved_target = target_display_type
    if target_display_type == DURATION_NATIVE:
        resolved_target = resolve_native_duration_type(animation_format)

    resolved_stored = stored_display_type
    if stored_display_type == DURATION_NATIVE:
        resolved_stored = resolve_native_duration_type(animation_format)

    if (
        stored_display_value is not None
        and stored_display_type is not None
        and resolved_stored == resolved_target
    ):
        return stored_display_value

    return milliseconds_to_duration(duration_ms, resolved_target, animation_format)


def get_duration_display_meta(
    duration_type: str, animation_format: str
) -> DurationDisplayMeta:
    """Build display metadata for a duration control.

    Args:
        duration_type: Configured duration input type (fps, native, etc.).
        animation_format: Current animation format.

    Returns:
        DurationDisplayMeta describing label text, tooltip, suffix, and range.
    """

    if duration_type == DURATION_NATIVE:
        resolved_type = resolve_native_duration_type(animation_format)
    else:
        resolved_type = duration_type

    label = get_duration_label(resolved_type, animation_format)
    tooltip = get_duration_tooltip(resolved_type, animation_format)
    min_value, max_value = get_duration_range(resolved_type, animation_format)
    suffix = DURATION_SUFFIXES.get(resolved_type, " fps")

    return DurationDisplayMeta(
        resolved_type=resolved_type,
        label=label,
        tooltip=tooltip,
        suffix=suffix,
        min_value=min_value,
        max_value=max_value,
    )
