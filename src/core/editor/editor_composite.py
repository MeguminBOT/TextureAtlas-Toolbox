"""Build composite animations from user-defined frame sequences.

This module lets the editor assemble new animations by referencing frames
from existing source animations and optionally overriding per-frame metadata
such as duration.

Type Aliases:
    FrameTuple: A 3-tuple of (frame_name, image, metadata_dict).
    AnimationMap: Mapping of animation names to lists of FrameTuples.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

FrameTuple = Tuple[str, Any, dict]
"""A single frame: (name, image object, metadata dict)."""

AnimationMap = Dict[str, List[FrameTuple]]
"""Mapping from animation name to its ordered list of frames."""


def clone_animation_map(
    animations: Optional[Dict[str, Sequence[FrameTuple]]],
) -> AnimationMap:
    """Clone an animation map, copying lists but sharing image objects.

    Args:
        animations: Source map to copy. May be ``None`` or empty.

    Returns:
        A new dict where each animation name maps to a fresh list of the
        same FrameTuple references.
    """
    cloned: AnimationMap = {}
    if not animations:
        return cloned
    for name, frames in animations.items():
        cloned[name] = list(frames or [])
    return cloned


def build_editor_composite_frames(
    definition: Optional[dict],
    source_frames: AnimationMap,
    *,
    log_warning: Optional[Callable[[str], None]] = None,
) -> List[FrameTuple]:
    """Assemble frames for an editor-defined composite animation.

    Each entry in ``definition["sequence"]`` references a source animation
    and frame index. Frames are copied so modifications do not mutate the
    originals.

    Args:
        definition: A dict with at least a ``"sequence"`` list. Each element
            should specify ``source_animation``, ``source_frame_index``, and
            optionally ``duration_ms`` or ``original_key``.
        source_frames: Available animations keyed by name.
        log_warning: Optional callback invoked with a message when a frame
            reference cannot be resolved.

    Returns:
        Ordered list of FrameTuples for the composite, or an empty list if
        ``definition`` is invalid or any frame reference fails.
    """

    def warn(message: str):
        if log_warning:
            try:
                log_warning(message)
            except Exception:
                logger.warning("%s", message)
        else:
            logger.warning("%s", message)

    if not isinstance(definition, dict):
        return []
    sequence = definition.get("sequence")
    if not isinstance(sequence, list):
        return []

    frames: List[FrameTuple] = []
    composite_name = definition.get("name") or "editor_composite"

    for index, frame_spec in enumerate(sequence):
        source_frame = _fetch_source_frame(frame_spec, source_frames)
        if source_frame is None:
            warn(
                f"[EditorComposite] Skipping composite '{composite_name}' because a referenced frame could not be resolved."
            )
            return []

        original_name, image, metadata = source_frame
        preferred_name = frame_spec.get("name")
        original_key = frame_spec.get("original_key") or original_name
        frame_name = preferred_name or original_key or original_name or f"frame_{index}"

        frame_metadata = _coerce_metadata(metadata)
        if "duration_ms" in frame_spec:
            frame_metadata["duration_ms"] = frame_spec.get("duration_ms")
        frame_metadata.setdefault("original_key", original_key or frame_name)
        frame_metadata["editor_source_animation"] = frame_spec.get("source_animation")
        frame_metadata["editor_source_frame_index"] = frame_spec.get(
            "source_frame_index"
        )
        frame_metadata["editor_sequence_index"] = index

        frame_image = image.copy() if hasattr(image, "copy") else image
        frames.append((frame_name, frame_image, frame_metadata))

    return frames


def _coerce_metadata(metadata: Any) -> dict:
    """Normalize arbitrary metadata into a mutable dict.

    Args:
        metadata: Original metadata; may be dict, tuple/list, None, or other.

    Returns:
        A new dict. List/tuple inputs become ``{"original_sprite_bounds": ...}``;
        unrecognised types become ``{"metadata": ...}``.
    """

    if isinstance(metadata, dict):
        return dict(metadata)
    if metadata is None:
        return {}
    if isinstance(metadata, (list, tuple)):
        return {"original_sprite_bounds": tuple(metadata)}
    return {"metadata": metadata}


def _fetch_source_frame(
    frame_spec: Optional[dict], source_frames: AnimationMap
) -> Optional[FrameTuple]:
    """Resolve a single frame reference from a composite sequence entry.

    Args:
        frame_spec: Dict containing ``source_animation``, ``source_frame_index``,
            and optionally ``original_key``.
        source_frames: Pool of available animations.

    Returns:
        The matching FrameTuple, or ``None`` if the reference is invalid or
        the frame does not exist.
    """

    if not isinstance(frame_spec, dict):
        return None
    source_animation = frame_spec.get("source_animation")
    source_index = frame_spec.get("source_frame_index")
    if source_animation is None or source_index is None:
        return None

    try:
        source_index = int(source_index)
    except (TypeError, ValueError):
        return None

    frames = source_frames.get(source_animation)
    if not frames or source_index < 0 or source_index >= len(frames):
        return None

    original_key = frame_spec.get("original_key")
    candidate = frames[source_index]
    if original_key and candidate and candidate[0] != original_key:
        for tuple_candidate in frames:
            if tuple_candidate and tuple_candidate[0] == original_key:
                return tuple_candidate
    return candidate
