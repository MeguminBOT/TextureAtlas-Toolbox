"""Bounded-memory storage for a single animation's rendered frames.

Frame selection, duplicate detection and animation encoding all need random
access to every frame of an animation, so frames cannot simply be streamed to
disk as they are produced.  ``FrameBuffer`` keeps that random access while
capping how much stays resident: frames accumulate in RAM up to a byte budget,
after which each new frame is appended to a temporary file and handed back as
a read-only ``numpy.memmap``.

Spilled pages are backed by the page cache, so the OS can reclaim them under
pressure instead of the process growing without bound.  A long full-scene
timeline that would otherwise pin several gigabytes of heap costs the budget
plus whatever the OS chooses to keep cached.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Iterator, List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

#: Resident frame bytes tolerated before spilling to disk (512 MB).
DEFAULT_RAM_BUDGET = 512 * 1024 * 1024


class FrameBuffer:
    """Sequence of ``(name, array, metadata)`` frames with a RAM ceiling.

    Behaves like a list to consumers.  Frames stored past the budget live in
    a temp file and are returned as memmap views, which are valid until
    :meth:`close` runs.

    Attributes:
        spilled: Number of frames written to the backing file.
    """

    def __init__(self, ram_budget: int = DEFAULT_RAM_BUDGET) -> None:
        """Create an empty buffer.

        Args:
            ram_budget: Bytes of frame data to hold in memory before
                spilling. Non-positive values spill from the first frame.
        """
        self._ram_budget = int(ram_budget)
        self._entries: List[Tuple[str, Any, Any]] = []
        self._resident_bytes = 0
        self._handle = None
        self._path: Optional[str] = None
        self._offset = 0
        self.spilled = 0

    def append(self, name: str, array: np.ndarray, metadata: Any) -> None:
        """Store one frame, spilling to disk once the budget is exceeded.

        Args:
            name: Frame name.
            array: RGBA frame data.
            metadata: The frame's metadata/placement value.
        """
        nbytes = int(getattr(array, "nbytes", 0))

        if self._resident_bytes + nbytes <= self._ram_budget:
            self._entries.append((name, array, metadata))
            self._resident_bytes += nbytes
            return

        spilled = self._spill(array)
        if spilled is None:
            # Spilling failed (no temp space, permissions); keeping the frame
            # resident is worse than losing it, but losing it is worse still.
            self._entries.append((name, array, metadata))
            self._resident_bytes += nbytes
            return
        self._entries.append((name, spilled, metadata))
        self.spilled += 1

    def _spill(self, array: np.ndarray) -> Optional[np.memmap]:
        """Append *array* to the backing file and return a memmap view."""
        try:
            contiguous = np.ascontiguousarray(array)
            if self._handle is None:
                descriptor, path = tempfile.mkstemp(
                    prefix="tatgf_frames_", suffix=".bin"
                )
                os.close(descriptor)
                self._path = path
                self._handle = open(path, "r+b")

            self._handle.seek(self._offset)
            self._handle.write(contiguous.tobytes())
            self._handle.flush()

            view = np.memmap(
                self._path,
                dtype=contiguous.dtype,
                mode="r",
                offset=self._offset,
                shape=contiguous.shape,
            )
            self._offset += contiguous.nbytes
            return view
        except Exception:
            logger.warning(
                "Could not spill frame to disk; keeping it in memory",
                exc_info=True,
            )
            return None

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[Tuple[str, Any, Any]]:
        return iter(self._entries)

    def __getitem__(self, index):
        return self._entries[index]

    def as_list(self) -> List[Tuple[str, Any, Any]]:
        """Return the frames as a plain list of tuples."""
        return list(self._entries)

    def close(self) -> None:
        """Drop all frames and remove the backing file.

        Any memmap views handed out become invalid, so callers must be done
        with the frames before calling this.
        """
        self._entries.clear()
        self._resident_bytes = 0
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None
        if self._path:
            try:
                os.unlink(self._path)
            except OSError:
                pass
            self._path = None
        self._offset = 0

    def __enter__(self) -> "FrameBuffer":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


__all__ = ["FrameBuffer", "DEFAULT_RAM_BUDGET"]
