#!/usr/bin/env python3
"""Detection of FNF engine type from character data file structure."""
from __future__ import annotations

import json
from typing import Any, Mapping, Tuple
import xml.etree.ElementTree as ET

EngineDetectionResult = Tuple[str, Any]


def detect_engine(file_path: str) -> EngineDetectionResult:
    """Identify the FNF engine variant from a character data file.

    Args:
        file_path: Path to a JSON or XML character file.

    Returns:
        Tuple of (engine_name, parsed_data). Engine name is one of
        'Psych Engine', 'Kade Engine', 'Codename Engine', or 'Unknown'.
        Parsed data is the loaded JSON dict, XML root element, or None.
    """
    if file_path.endswith(".json"):
        return _detect_from_json(file_path)
    if file_path.endswith(".xml"):
        return _detect_from_xml(file_path)
    return "Unknown", None


def _detect_from_json(file_path: str) -> EngineDetectionResult:
    """Attempt to detect engine type from a JSON character file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Tuple of (engine_name, parsed_dict) or ('Unknown', None).
    """
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return "Unknown", None

    if _is_psych_engine(data):
        return "Psych Engine", data
    # V-Slice must be checked before Kade because both use per-animation
    # `prefix` / `offsets` / `looped` / `frameIndices`. They are disambiguated
    # by top-level keys: V-Slice uses `assetPath` + `version`, Kade uses
    # `asset` + `startingAnim`.
    if _is_vslice_engine(data):
        return "V-Slice Engine", data
    if _is_kade_engine(data):
        return "Kade Engine", data
    return "Unknown", None


def _detect_from_xml(file_path: str) -> EngineDetectionResult:
    """Attempt to detect engine type from an XML character file.

    Args:
        file_path: Path to the XML file.

    Returns:
        Tuple of (engine_name, xml_root) or ('Unknown', None).
    """
    try:
        tree = ET.parse(file_path)
    except (OSError, ET.ParseError):
        return "Unknown", None

    root = tree.getroot()
    if _is_codename_engine(root):
        return "Codename Engine", root
    return "Unknown", None


def _is_psych_engine(data: Any) -> bool:
    """Check if the parsed JSON matches Psych Engine structure.

    Args:
        data: Parsed JSON data.

    Returns:
        True if the structure matches Psych Engine format.
    """
    animations = data.get("animations") if isinstance(data, Mapping) else None
    if not isinstance(animations, list):
        return False

    required_keys = {"name", "fps", "anim", "loop", "indices"}
    for anim in animations:
        if not isinstance(anim, Mapping):
            return False
        if not required_keys.issubset(anim.keys()):
            return False
        if not isinstance(anim.get("indices"), list):
            return False

    required_top_level = {"image", "scale", "flip_x", "no_antialiasing"}
    return required_top_level.issubset(data.keys())


def _is_vslice_engine(data: Any) -> bool:
    """Check if the parsed JSON matches the official V-Slice Funkin' format.

    V-Slice (the official rewrite by Funkin' Crew) uses character JSON with a
    top-level ``version``, ``assetPath``, and an ``animations`` array whose
    entries carry a per-animation ``frameRate``. This is distinct from Kade
    (which has top-level ``asset`` + ``startingAnim`` and a single global
    ``frameRate``) and from Psych (which uses ``image`` + ``flip_x`` and
    per-animation ``fps`` / ``anim`` / ``indices``).

    Args:
        data: Parsed JSON data.

    Returns:
        True if the structure matches the V-Slice character data format.
    """
    if not isinstance(data, Mapping):
        return False

    # Required top-level keys that uniquely identify V-Slice.
    if not {"version", "name", "assetPath", "animations"}.issubset(data.keys()):
        return False

    if not isinstance(data.get("assetPath"), str):
        return False

    animations = data["animations"]
    if not isinstance(animations, list) or not animations:
        return False

    for anim in animations:
        if not isinstance(anim, Mapping):
            return False
        if not {"name", "prefix"}.issubset(anim.keys()):
            return False
        offsets = anim.get("offsets")
        if offsets is not None and (not isinstance(offsets, list) or len(offsets) != 2):
            return False
        frame_indices = anim.get("frameIndices")
        if frame_indices is not None and not isinstance(frame_indices, list):
            return False
        for bool_field in ("looped", "flipX", "flipY"):
            value = anim.get(bool_field)
            if value is not None and not isinstance(value, bool):
                return False
    return True


def _is_kade_engine(data: Any) -> bool:
    """Check if the parsed JSON matches Kade Engine structure.

    Args:
        data: Parsed JSON data.

    Returns:
        True if the structure matches Kade Engine format.
    """
    if not isinstance(data, Mapping):
        return False
    required_keys = {"name", "asset", "startingAnim", "animations"}
    if not required_keys.issubset(data.keys()):
        return False

    animations = data["animations"]
    if not isinstance(animations, list):
        return False

    for anim in animations:
        if not isinstance(anim, Mapping):
            return False
        if not {"name", "prefix", "offsets"}.issubset(anim.keys()):
            return False
        offsets = anim.get("offsets")
        if not isinstance(offsets, list) or len(offsets) != 2:
            return False
        frame_indices = anim.get("frameIndices")
        if frame_indices is not None and not isinstance(frame_indices, list):
            return False
        looped = anim.get("looped")
        if looped is not None and not isinstance(looped, bool):
            return False
    return True


def _is_codename_engine(root: ET.Element) -> bool:
    """Check if the XML root matches Codename Engine structure.

    Args:
        root: Root element of the parsed XML.

    Returns:
        True if the structure matches Codename Engine format.
    """
    if root.tag != "character":
        return False

    for anim in root.findall("anim"):
        attrib = anim.attrib
        if not {"name", "anim", "fps", "loop"}.issubset(attrib):
            return False
        indices = attrib.get("indices")
        if indices is not None and ".." not in indices:
            return False
    return True
