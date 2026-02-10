"""Lightweight helpers for inspecting Adobe Spritemap timelines without rendering.

These utilities extract timing and label information directly from the
Animation.json structure, avoiding the overhead of full frame rendering.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set


def _collect_symbol_refs_from_layers(layers: Optional[List[dict]]) -> Set[str]:
    """Collect symbol names directly referenced by ``SI`` elements in layers.

    Args:
        layers: List of layer dicts from a timeline.

    Returns:
        Set of symbol names found in ``SI.SN`` entries.
    """
    refs: Set[str] = set()
    if not layers:
        return refs
    for layer in layers:
        for frame in layer.get("FR", []):
            for element in frame.get("E", []):
                si = element.get("SI")
                if si:
                    name = si.get("SN")
                    if name:
                        refs.add(name)
    return refs


def collect_referenced_symbols(animation_json: dict) -> Set[str]:
    """Return all symbol names reachable from the root ``AN`` timeline.

    Performs a depth-first traversal starting from the root animation,
    following ``SI.SN`` references through nested symbol timelines.
    This identifies every symbol that participates in the main animation,
    as opposed to standalone component symbols that are never composed
    into the root timeline.

    Args:
        animation_json: Parsed and normalized Animation.json structure.

    Returns:
        Set of symbol names transitively referenced by the root timeline.
    """
    root_layers = animation_json.get("AN", {}).get("TL", {}).get("L", [])
    symbols_by_name: Dict[str, List[dict]] = {}
    for symbol in animation_json.get("SD", {}).get("S", []):
        name = symbol.get("SN")
        if name:
            symbols_by_name[name] = symbol.get("TL", {}).get("L", [])

    referenced: Set[str] = set()
    stack = list(_collect_symbol_refs_from_layers(root_layers))
    while stack:
        name = stack.pop()
        if name in referenced:
            continue
        referenced.add(name)
        child_layers = symbols_by_name.get(name)
        if child_layers:
            for child in _collect_symbol_refs_from_layers(child_layers):
                if child not in referenced:
                    stack.append(child)
    return referenced


def _frame_duration(frame: dict) -> int:
    """Return clamped duration for a single frame entry.

    Args:
        frame: A frame dict from the timeline, expected to have a ``"DU"`` key.

    Returns:
        The duration as an int, minimum 1.
    """

    duration = frame.get("DU", 1)
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 1
    return max(1, duration)


def compute_layers_length(layers: Optional[List[dict]]) -> int:
    """Compute the total frame count spanned by a set of timeline layers.

    Args:
        layers: List of layer dicts, each containing a ``"FR"`` (frames) list.

    Returns:
        The highest end-frame index across all layers, or 0 if empty.
    """

    if not layers:
        return 0

    total = 0
    for layer in layers:
        frames = layer.get("FR", []) or []
        if not frames:
            continue
        last_frame = frames[-1]
        start_index = int(last_frame.get("I", 0))
        total = max(total, start_index + _frame_duration(last_frame))
    return total


def compute_symbol_lengths(animation_json: dict) -> Dict[str, int]:
    """Build a mapping of symbol name to total frame count.

    Args:
        animation_json: Parsed Animation.json structure.

    Returns:
        Dict keyed by symbol name with integer frame counts.
    """

    lengths: Dict[str, int] = {}
    for symbol in animation_json.get("SD", {}).get("S", []):
        name = symbol.get("SN")
        if not name:
            continue
        layers = symbol.get("TL", {}).get("L", [])
        lengths[name] = compute_layers_length(layers)
    return lengths


def _extract_label_ranges_from_layers(
    layers: Optional[List[dict]],
) -> List[Dict[str, int]]:
    """Extract labelled frame ranges from timeline layers.

    Only the first layer containing labels is used; duplicates are dropped.

    Args:
        layers: List of layer dicts from a timeline.

    Returns:
        Sorted list of dicts with ``name``, ``start``, and ``end`` keys.
    """

    labels: List[Dict[str, int]] = []
    if not layers:
        return labels

    for layer in layers:
        frames = layer.get("FR", [])
        for frame in frames:
            label_name = frame.get("N")
            if not label_name:
                continue
            start = int(frame.get("I", 0))
            duration = _frame_duration(frame)
            labels.append({"name": label_name, "start": start, "end": start + duration})
        if labels:
            break

    labels.sort(key=lambda item: item["start"])
    unique: List[Dict[str, int]] = []
    seen = set()
    for entry in labels:
        if entry["name"] in seen:
            continue
        seen.add(entry["name"])
        unique.append(entry)
    return unique


def extract_label_ranges(
    animation_json: dict, symbol_name: Optional[str] = None
) -> List[Dict[str, int]]:
    """Get labelled frame ranges for the root timeline or a nested symbol.

    Args:
        animation_json: Parsed Animation.json structure.
        symbol_name: If provided, look up this symbol; otherwise use root.

    Returns:
        List of dicts with ``name``, ``start``, and ``end`` keys.
    """

    if symbol_name is None:
        layers = animation_json.get("AN", {}).get("TL", {}).get("L", [])
    else:
        for symbol in animation_json.get("SD", {}).get("S", []):
            if symbol.get("SN") == symbol_name:
                layers = symbol.get("TL", {}).get("L", [])
                break
        else:
            layers = []
    return _extract_label_ranges_from_layers(layers)


def extract_label_ranges_from_layers(
    layers: Optional[List[dict]],
) -> List[Dict[str, int]]:
    """Wrapper for extracting label ranges from raw layer data.

    Args:
        layers: List of layer dicts from a timeline.

    Returns:
        Sorted list of dicts with ``name``, ``start``, and ``end`` keys.
    """
    return _extract_label_ranges_from_layers(layers)
