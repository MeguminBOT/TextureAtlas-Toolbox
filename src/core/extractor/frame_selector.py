"""Frame selection strategies for filtering animation frames.

Provides ``FrameSelector`` with static methods for detecting single-frame
animations, applying selection rules (All, First, Last, No duplicates, etc.),
and resolving index ranges.
"""

import numpy as np

from core.extractor.image_utils import ensure_rgba_array


class FrameSelector:
    """Static utilities for selecting which frames to export.

    Supports strategies like keeping all frames, first/last only, removing
    duplicates, or explicit index/range notation.
    """

    @staticmethod
    def is_single_frame(image_tuples):
        """Return ``True`` when all frames are visually identical.

        Compares metadata and pixel data across frames. Returns ``True`` for
        empty or single-element sequences.

        Args:
            image_tuples: Sequence of ``(name, image, metadata)`` tuples where
                image is a PIL Image or NumPy array.

        Returns:
            ``True`` if every frame matches the first, ``False`` otherwise.
        """
        if not image_tuples or len(image_tuples) == 1:
            return True

        _, first_image, first_meta = image_tuples[0]
        first_array = ensure_rgba_array(first_image)

        try:
            first_bytes = first_array.tobytes()
        except Exception:
            first_bytes = None

        first_shape = first_array.shape

        for _, image, metadata in image_tuples[1:]:
            if metadata != first_meta:
                return False

            candidate = ensure_rgba_array(image)
            if candidate.shape != first_shape:
                return False

            if first_bytes is not None:
                try:
                    if candidate.tobytes() != first_bytes:
                        return False
                    continue
                except Exception:
                    first_bytes = None

            if not np.array_equal(candidate, first_array):
                return False

        return True

    @staticmethod
    def get_kept_frames(settings, single_frame, image_tuples):
        """Determine which frame indices to keep based on selection settings.

        Args:
            settings: Dict with optional ``frame_selection`` key.
            single_frame: When ``True``, forces selection to ``["0"]``.
            image_tuples: Sequence of ``(name, image, metadata)`` tuples.

        Returns:
            List of string indices or ranges (e.g., ``["0", "2-5", "-1"]``).
        """
        if single_frame:
            return ["0"]

        kept_frames = settings.get("frame_selection")
        if kept_frames is None:
            kept_frames = "all"

        # Support both new internal values and legacy display text values
        kept_frames_lower = kept_frames.lower() if isinstance(kept_frames, str) else ""

        if kept_frames_lower in ("all", "", "custom"):
            return [str(i) for i in range(len(image_tuples))]
        elif kept_frames_lower == "first":
            return ["0"]
        elif kept_frames_lower == "last":
            return ["-1"]
        elif kept_frames_lower in ("first_last", "first, last"):
            return ["0", "-1"]
        elif kept_frames_lower in ("no_duplicates", "no duplicates"):
            unique_indices = []
            seen_signatures = set()
            for i, frame in enumerate(image_tuples):
                signature = FrameSelector._frame_signature(frame[1])
                if signature is None or signature not in seen_signatures:
                    if signature is not None:
                        seen_signatures.add(signature)
                    unique_indices.append(str(i))
            return unique_indices
        else:
            return kept_frames.split(",")

    @staticmethod
    def get_kept_frame_indices(kept_frames, image_tuples):
        """Convert string specifiers into a sorted list of unique indices.

        Handles single indices, negative indices, and range notation
        (e.g., ``"0-3"``, ``"-1--4"``).

        Args:
            kept_frames: List or comma-separated string of specifiers.
            image_tuples: Frame sequence used for length and bounds checking.

        Returns:
            Sorted list of valid integer indices.
        """
        kept_frame_indices = set()

        if isinstance(kept_frames, str):
            kept_frames = kept_frames.split(",")

        for entry in kept_frames:
            entry = entry.strip()

            if "--" in entry:  # Detect ranges like "-1--4"
                try:
                    split_index = entry[1:].find("-") + 1
                    start = int(entry[:split_index])
                    end = int(entry[split_index + 1 :])

                    if start < 0:
                        start += len(image_tuples)
                    if end < 0:
                        end += len(image_tuples)

                    if start <= end:
                        kept_frame_indices.update(
                            range(max(0, start), min(len(image_tuples), end + 1))
                        )
                    else:
                        kept_frame_indices.update(
                            range(max(0, end), min(len(image_tuples), start + 1))[::-1]
                        )
                except ValueError:
                    continue

            elif (
                "-" in entry and not entry.lstrip("-").isdigit()
            ):  # Detect ranges like "0-3"
                try:
                    start, end = map(int, entry.split("-"))
                    if start < 0:
                        start += len(image_tuples)
                    if end < 0:
                        end += len(image_tuples)

                    if start <= end:
                        kept_frame_indices.update(
                            range(max(0, start), min(len(image_tuples), end + 1))
                        )
                    else:
                        kept_frame_indices.update(
                            range(max(0, end), min(len(image_tuples), start + 1))[::-1]
                        )
                except ValueError:
                    continue

            else:
                try:
                    frame_index = int(entry)
                    if frame_index < 0:
                        frame_index += len(image_tuples)
                    if 0 <= frame_index < len(image_tuples):
                        kept_frame_indices.add(frame_index)
                except ValueError:
                    continue
        return sorted(kept_frame_indices)

    @staticmethod
    def _frame_signature(frame_source):
        """Compute a hash signature for duplicate detection.

        Samples a sparse grid of pixels to produce a fast, approximate
        fingerprint of the image data.

        Args:
            frame_source: PIL Image or NumPy array.

        Returns:
            Integer hash, or ``None`` if the frame cannot be processed.
        """
        try:
            array = ensure_rgba_array(frame_source)
        except Exception:
            return None

        if array.ndim < 2:
            return None

        step_y = max(1, array.shape[0] // 32)
        step_x = max(1, array.shape[1] // 32)
        sample = array[::step_y, ::step_x]
        if sample.ndim == 3 and sample.shape[2] > 4:
            sample = sample[..., :4]

        try:
            sample = np.ascontiguousarray(sample)
            prefix = sample.tobytes()
        except Exception:
            return None

        return hash((array.shape, array.dtype.str, prefix))
