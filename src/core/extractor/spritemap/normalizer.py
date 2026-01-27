#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Normalize Adobe Animate spritemap JSON into a consistent abbreviated format.

Adobe Animate exports spritemap data in two forms:
  - **Optimized**: Compact keys (``AN``, ``SD``, ``TL``, ``FR``, etc.)
  - **Verbose**: Descriptive keys (``ANIMATION``, ``TIMELINE``, ``LAYERS``, etc.)

This module ensures all Animation.json documents use the optimized schema
regardless of export settings. The :func: `normalize_animation_document`
function detects verbose structures and transforms them into the abbreviated
layout, allowing the rest of the extraction pipeline to work with a single
predictable format.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

IDENTITY_M3D: List[float] = [
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1.0,
]

LOOP_MAP = {
    "loop": "LP",
    "play once": "PO",
    "single frame": "SF",
    "singleframe": "SF",
}

SYMBOL_TYPE_MAP = {
    "graphic": "G",
    "graphics": "G",
    "movie clip": "MC",
    "movieclip": "MC",
    "button": "BTN",
}


def normalize_animation_document(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *data* with optimized spritemap keys.

    Args:
        data: Parsed Animation.json payload.

    Returns:
        Dict guaranteed to expose the abbreviated ``AN`` / ``SD`` layout.
    """

    if not isinstance(data, dict):
        return data

    if "AN" in data and "SD" in data:
        # Already abbreviated format, but may still need MX→M3D conversion
        return _convert_mx_to_m3d_recursive(data)

    verbose_key_candidates = {
        key.lower(): key for key in data.keys() if isinstance(key, str)
    }
    has_verbose_keys = (
        "animation" in verbose_key_candidates
        or "symbol_dictionary" in verbose_key_candidates
    )
    if not has_verbose_keys:
        return _convert_mx_to_m3d_recursive(data)

    normalized = dict(data)

    animation_section = _normalize_animation_section(
        _get_first(data, "ANIMATION", "animation")
    )
    if animation_section:
        normalized["AN"] = animation_section

    symbol_dictionary = _normalize_symbol_dictionary(
        _get_first(data, "SYMBOL_DICTIONARY", "symbolDictionary")
    )
    if symbol_dictionary:
        normalized["SD"] = symbol_dictionary

    metadata_section = _normalize_metadata(_get_first(data, "metadata", "MD"))
    if metadata_section:
        merged = dict(normalized.get("MD", {}))
        merged.update(metadata_section)
        normalized["MD"] = merged

    return normalized


def _convert_mx_to_m3d_recursive(data: Any) -> Any:
    """Recursively convert MX (6-element) matrices to M3D (16-element) format.

    Walks through the entire document structure and converts any MX keys
    to M3D format in-place for SI (symbol instance) and ASI (atlas sprite
    instance) elements.

    Args:
        data: Any JSON-compatible structure (dict, list, or primitive).

    Returns:
        The same structure with MX matrices converted to M3D.
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "MX" and isinstance(value, list) and len(value) == 6:
                result["M3D"] = _mx_to_m3d(value)
            elif key == "M3D":
                result[key] = value
            else:
                result[key] = _convert_mx_to_m3d_recursive(value)
        return result
    elif isinstance(data, list):
        return [_convert_mx_to_m3d_recursive(item) for item in data]
    else:
        return data


def _mx_to_m3d(mx: List[float]) -> List[float]:
    """Convert a 6-element MX matrix to 16-element M3D format.

    MX format is [a, b, c, d, tx, ty] representing the 2D affine matrix:
        | a  c  tx |
        | b  d  ty |
        | 0  0  1  |

    M3D is a 16-element column-major 4x4 matrix.

    Args:
        mx: 6-element list [a, b, c, d, tx, ty].

    Returns:
        16-element M3D list.
    """
    a, b, c, d, tx, ty = mx
    return [
        float(a),
        float(b),
        0.0,
        0.0,
        float(c),
        float(d),
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        float(tx),
        float(ty),
        0.0,
        1.0,
    ]


def _normalize_animation_section(section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize the root ``ANIMATION`` section into the abbreviated shape.

    Args:
        section: Verbose ``ANIMATION`` dict from the raw export.

    Returns:
        Abbreviated dict with ``N``, ``SN``, and ``TL`` keys as applicable.
    """

    if not isinstance(section, dict):
        return {}

    timeline = _normalize_timeline(_get_first(section, "TIMELINE", "timeline"))
    normalized: Dict[str, Any] = {}
    name = _get_first(section, "name", "NAME")
    if name:
        normalized["N"] = name
    symbol_name = _get_first(
        section,
        "SYMBOL_name",
        "symbol_name",
        "SYMBOLName",
        "symbolName",
    )
    if symbol_name:
        normalized["SN"] = symbol_name
    if timeline:
        normalized["TL"] = timeline
    return normalized


def _normalize_symbol_dictionary(section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert ``symbolDictionary`` entries into the compact ``SD`` layout.

    Args:
        section: Verbose ``SYMBOL_DICTIONARY`` dict containing a ``Symbols`` list.

    Returns:
        Dict with an ``S`` key holding a list of abbreviated symbol dicts.
    """

    if not isinstance(section, dict):
        return {}

    symbols: List[Dict[str, Any]] = []
    symbols_source = _get_first(section, "Symbols", "symbols") or []
    for symbol in symbols_source:
        if not isinstance(symbol, dict):
            continue
        normalized_symbol: Dict[str, Any] = {}
        symbol_name = _get_first(
            symbol,
            "SYMBOL_name",
            "symbol_name",
            "SYMBOLName",
            "symbolName",
        )
        if symbol_name:
            normalized_symbol["SN"] = symbol_name
        timeline = _normalize_timeline(_get_first(symbol, "TIMELINE", "timeline"))
        if timeline:
            normalized_symbol["TL"] = timeline
        if normalized_symbol:
            symbols.append(normalized_symbol)
    if symbols:
        return {"S": symbols}
    return {}


def _normalize_timeline(section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize timeline layers from verbose ``LAYERS`` definitions.

    Args:
        section: Verbose ``TIMELINE`` dict containing a ``LAYERS`` list.

    Returns:
        Dict with an ``L`` key holding a list of abbreviated layer dicts.
    """

    if not isinstance(section, dict):
        return {}

    layers_source = _get_first(section, "LAYERS", "layers") or []
    layers = [
        layer for layer in (_normalize_layer(entry) for entry in layers_source) if layer
    ]
    if layers:
        return {"L": layers}
    return {}


def _normalize_layer(layer: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a single layer definition and its frames into ``FR`` blocks.

    Args:
        layer: Verbose layer dict with ``Frames`` and optional clipping flags.

    Returns:
        Abbreviated layer dict with ``LN``, ``FR``, and clipping keys.
    """

    if not isinstance(layer, dict):
        return {}

    frames_source = _get_first(layer, "Frames", "frames", "FRAMES") or []
    frames = [
        frame for frame in (_normalize_frame(entry) for entry in frames_source) if frame
    ]
    normalized: Dict[str, Any] = {}
    name = _get_first(layer, "Layer_name", "layerName", "name")
    if name:
        normalized["LN"] = name
    if frames:
        normalized["FR"] = frames
    layer_type = (_get_first(layer, "layerType", "Layer_type") or "").lower()
    if _truthy(layer.get("isClippingLayer")) or layer_type == "clipping":
        normalized["LT"] = "Clp"
    if _truthy(layer.get("hasClippingMask")):
        normalized["Clpb"] = True
    return normalized


def _normalize_frame(frame: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Translate a frame record plus its elements into the shorthand form.

    Args:
        frame: Verbose frame dict with ``index``, ``duration``, and ``elements``.

    Returns:
        Abbreviated frame dict with ``I``, ``DU``, ``E``, and optional ``N``.
    """

    if not isinstance(frame, dict):
        return {}

    elements_source = _get_first(frame, "E", "elements", "Elements") or []
    elements = [
        element
        for element in (_normalize_element(entry) for entry in elements_source)
        if element
    ]
    normalized: Dict[str, Any] = {
        "I": _safe_int(_get_first(frame, "I", "index"), default=0),
        "DU": max(1, _safe_int(_get_first(frame, "DU", "duration"), default=1)),
        "E": elements,
    }
    label = _get_first(frame, "N", "name", "label")
    if label:
        normalized["N"] = label
    return normalized


def _normalize_element(element: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize symbol or atlas instances embedded inside a frame.

    Args:
        element: Verbose element dict potentially containing ``SYMBOL_Instance``
            or ``ATLAS_SPRITE_instance``.

    Returns:
        Dict with either ``SI`` or ``ASI`` key in abbreviated form.
    """

    if not isinstance(element, dict):
        return {}

    if "ASI" in element:
        return element
    if "SI" in element:
        bitmap_instance = _normalize_symbol_bitmap(element.get("SI"))
        if bitmap_instance:
            return {"ASI": bitmap_instance}
        return element

    symbol_instance = _get_first(
        element,
        "SI",
        "SYMBOL_Instance",
        "symbol_instance",
        "symbolInstance",
    )
    if symbol_instance is not None:
        bitmap_instance = _normalize_symbol_bitmap(symbol_instance)
        if bitmap_instance:
            return {"ASI": bitmap_instance}
        symbol = _normalize_symbol_instance(symbol_instance)
        if symbol:
            return {"SI": symbol}
    atlas_instance = _get_first(
        element,
        "ASI",
        "ATLAS_SPRITE_instance",
        "atlas_sprite_instance",
        "atlasSpriteInstance",
    )
    if atlas_instance is not None:
        atlas = _normalize_atlas_instance(atlas_instance)
        if atlas:
            return {"ASI": atlas}
    return {}


def _normalize_symbol_instance(instance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert verbose symbol instance dictionaries into ``SI`` payloads.

    Args:
        instance: Verbose ``SYMBOL_Instance`` dict with symbol name, loop mode,
            transform data, etc.

    Returns:
        Abbreviated ``SI`` dict ready for the rendering pipeline.
    """

    if not isinstance(instance, dict):
        return {}

    normalized: Dict[str, Any] = {}
    symbol_name = _get_first(
        instance,
        "SN",
        "SYMBOL_name",
        "symbol_name",
        "SYMBOLName",
        "symbolName",
    )
    if symbol_name:
        normalized["SN"] = symbol_name
    instance_name = _get_first(instance, "IN", "Instance_Name", "instanceName")
    if instance_name is not None:
        normalized["IN"] = instance_name
    symbol_type = (
        _get_first(instance, "ST", "symbolType", "symbol_type") or ""
    ).lower()
    normalized["ST"] = SYMBOL_TYPE_MAP.get(symbol_type, symbol_type.upper() or "G")
    normalized["FF"] = _safe_int(_get_first(instance, "FF", "firstFrame"), default=0)
    loop_mode = _get_first(instance, "LP", "loop", "Loop")
    if isinstance(loop_mode, str):
        normalized["LP"] = LOOP_MAP.get(loop_mode.lower(), loop_mode)
    elif loop_mode is not None:
        normalized["LP"] = loop_mode
    transform_point = _get_first(
        instance,
        "TRP",
        "transformationPoint",
        "transformPoint",
    )
    if isinstance(transform_point, dict):
        normalized["TRP"] = {
            "x": float(transform_point.get("x", 0.0)),
            "y": float(transform_point.get("y", 0.0)),
        }
    matrix_source = _get_first(instance, "M3D", "Matrix3D")
    if matrix_source is None:
        matrix_source = _get_first(instance, "MX")
    if matrix_source is None:
        matrix_source = _matrix_from_decomposed(instance)
    normalized["M3D"] = _normalize_matrix(matrix_source)
    color_effect = _get_first(instance, "C", "colorEffect", "colourEffect")
    if color_effect is not None:
        normalized["C"] = color_effect
    return normalized


def _normalize_symbol_bitmap(instance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a symbol instance that only references a bitmap into ``ASI``.

    Args:
        instance: Verbose symbol instance dict that may contain a ``bitmap`` key.

    Returns:
        Abbreviated ``ASI`` dict if a bitmap reference exists, else empty dict.
    """

    if not isinstance(instance, dict):
        return {}
    bitmap = instance.get("bitmap")
    if not isinstance(bitmap, dict):
        return {}
    name = bitmap.get("name")
    if not name:
        return {}
    normalized: Dict[str, Any] = {"N": name}
    matrix_source = _get_first(instance, "M3D", "Matrix3D")
    if matrix_source is None:
        matrix_source = _get_first(instance, "MX")
    if matrix_source is None:
        matrix_source = _matrix_from_decomposed(instance)
    normalized["M3D"] = _normalize_matrix(matrix_source)
    return normalized


def _normalize_atlas_instance(instance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize atlas sprite instances into ``ASI`` structures.

    Args:
        instance: Verbose ``ATLAS_SPRITE_instance`` dict with name and matrix.

    Returns:
        Abbreviated ``ASI`` dict with ``N`` and ``M3D`` keys.
    """

    if not isinstance(instance, dict):
        return {}

    normalized: Dict[str, Any] = {}
    name = _get_first(instance, "N", "name", "Name")
    if name:
        normalized["N"] = name
    matrix_source = _get_first(instance, "M3D", "Matrix3D", "matrix3D")
    if matrix_source is None:
        matrix_source = _get_first(instance, "MX")
    if matrix_source is None:
        matrix_source = _matrix_from_decomposed(instance)
    normalized["M3D"] = _normalize_matrix(matrix_source)
    return normalized


def _matrix_from_decomposed(
    instance: Optional[Dict[str, Any]],
) -> Optional[List[float]]:
    """Build an ``M3D`` list from separate position/rotation/scale data.

    Args:
        instance: Dict that may contain ``DecomposedMatrix``, ``Position``,
            ``Rotation``, or ``Scaling`` keys.

    Returns:
        A 16-element column-major matrix list, or ``None`` if no decomposed
        data is present.
    """

    if not isinstance(instance, dict):
        return None

    containers = []
    decomposed = _get_first(instance, "DecomposedMatrix", "decomposedMatrix")
    if isinstance(decomposed, dict):
        containers.append(decomposed)
    containers.append(instance)

    position = None
    rotation = None
    scaling = None

    for container in containers:
        if position is None:
            position = _get_first(container, "Position", "position")
        if rotation is None:
            rotation = _get_first(container, "Rotation", "rotation")
        if scaling is None:
            scaling = _get_first(container, "Scaling", "scaling", "Scale", "scale")

    if position is None and rotation is None and scaling is None:
        return None

    translate_x = _safe_float(position.get("x"), default=0.0) if position else 0.0
    translate_y = _safe_float(position.get("y"), default=0.0) if position else 0.0

    angle_z = 0.0
    if rotation:
        angle_z = math.radians(_safe_float(rotation.get("z"), default=0.0))
    scale_x = _safe_float(scaling.get("x"), default=1.0) if scaling else 1.0
    scale_y = _safe_float(scaling.get("y"), default=1.0) if scaling else 1.0

    cos_z = math.cos(angle_z)
    sin_z = math.sin(angle_z)

    matrix = list(IDENTITY_M3D)
    matrix[0] = scale_x * cos_z
    matrix[4] = -scale_y * sin_z
    matrix[1] = scale_x * sin_z
    matrix[5] = scale_y * cos_z
    matrix[12] = translate_x
    matrix[13] = translate_y
    return matrix


def _normalize_matrix(matrix: Optional[Any]) -> List[float]:
    """Return a 16-value matrix list no matter the incoming representation.

    Args:
        matrix: A 16-element list (M3D), a 6-element list (MX 2D affine),
            a dict with ``m00``–``m33`` keys, or ``None``.

    Returns:
        A 16-element column-major matrix list; identity if input is invalid.
    """

    if isinstance(matrix, list) and len(matrix) == 16:
        return matrix
    if isinstance(matrix, list) and len(matrix) == 6:
        # MX format: [a, b, c, d, tx, ty] representing 2D affine transform
        # | a  c  tx |    Maps to M3D column-major 4x4:
        # | b  d  ty |    [a, b, 0, 0, c, d, 0, 0, 0, 0, 1, 0, tx, ty, 0, 1]
        # | 0  0  1  |
        a, b, c, d, tx, ty = matrix
        return [
            float(a),
            float(b),
            0.0,
            0.0,
            float(c),
            float(d),
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            float(tx),
            float(ty),
            0.0,
            1.0,
        ]
    if isinstance(matrix, dict):
        return [
            _get_first(matrix, "m00", "M00") or 1.0,
            _get_first(matrix, "m01", "M01") or 0.0,
            _get_first(matrix, "m02", "M02") or 0.0,
            _get_first(matrix, "m03", "M03") or 0.0,
            _get_first(matrix, "m10", "M10") or 0.0,
            _get_first(matrix, "m11", "M11") or 1.0,
            _get_first(matrix, "m12", "M12") or 0.0,
            _get_first(matrix, "m13", "M13") or 0.0,
            _get_first(matrix, "m20", "M20") or 0.0,
            _get_first(matrix, "m21", "M21") or 0.0,
            _get_first(matrix, "m22", "M22") or 1.0,
            _get_first(matrix, "m23", "M23") or 0.0,
            _get_first(matrix, "m30", "M30") or 0.0,
            _get_first(matrix, "m31", "M31") or 0.0,
            _get_first(matrix, "m32", "M32") or 0.0,
            _get_first(matrix, "m33", "M33") or 1.0,
        ]
    return list(IDENTITY_M3D)


def _safe_float(value: Optional[Any], default: float = 0.0) -> float:
    """Return ``value`` coerced to ``float`` or the provided default."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_metadata(section: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract frame-rate metadata from verbose ``metadata`` blocks.

    Args:
        section: Verbose ``metadata`` dict potentially containing ``framerate``.

    Returns:
        Dict with ``FRT`` key if a valid frame rate is found, else empty.
    """

    if not isinstance(section, dict):
        return {}
    framerate = section.get("framerate") or section.get("frameRate")
    if framerate is None:
        return {}
    try:
        framerate_value = float(framerate)
    except (TypeError, ValueError):
        return {}
    return {"FRT": framerate_value}


def _safe_int(value: Optional[Any], default: int = 0) -> int:
    """Return ``value`` coerced to ``int`` or the provided default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_first(container: Optional[Dict[str, Any]], *keys: str) -> Any:
    """Fetch the first key present in ``container`` (case insensitive).

    Args:
        container: Dict to search.
        *keys: Keys to try in order; first match wins.

    Returns:
        The value for the first matching key, or ``None`` if none match.
    """

    if not isinstance(container, dict):
        return None
    for key in keys:
        if key in container:
            return container[key]
    lowercase_map = None
    for key in keys:
        if not isinstance(key, str):
            continue
        if lowercase_map is None:
            lowercase_map = {
                existing_key.lower(): existing_key
                for existing_key in container.keys()
                if isinstance(existing_key, str)
            }
        match = lowercase_map.get(key.lower())
        if match is not None:
            return container[match]
    return None


def _truthy(value: Any) -> bool:
    """Return ``True`` if the provided value is truthy or affirmative text.

    Args:
        value: Any value; strings ``"true"``, ``"1"``, and ``"yes"`` are
            considered truthy regardless of case.

    Returns:
        Boolean interpretation of the value.
    """

    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


__all__ = ["normalize_animation_document"]
