#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regression tests for atlas generator alignment metadata."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.generator.atlas_generator import AtlasGenerator, GeneratorOptions


def _make_rgba(path: Path, size: tuple[int, int], color: tuple[int, int, int, int]):
    image = Image.new("RGBA", size, color)
    image.save(path)


def test_generator_emits_frame_offsets_for_alignment(tmp_path: Path):
    atlas_base = tmp_path / "walk_atlas"

    large_frame = tmp_path / "walk_large.png"
    small_frame = tmp_path / "walk_small.png"

    _make_rgba(large_frame, (32, 24), (200, 50, 50, 255))
    _make_rgba(small_frame, (16, 12), (50, 200, 50, 255))

    generator = AtlasGenerator()
    options = GeneratorOptions(
        max_width=128,
        max_height=128,
        padding=0,
        allow_rotation=False,
        export_format="json-hash",
        image_format="png",
    )

    result = generator.generate(
        {"walk": [str(large_frame), str(small_frame)]},
        str(atlas_base),
        options,
    )

    assert result.success, f"Generation failed: {result.errors}"
    metadata_path = Path(result.metadata_path)
    assert metadata_path.exists(), "Metadata file was not created"

    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    frames = metadata["frames"]
    large = frames["walk_01"]
    small = frames["walk_02"]

    # Largest frame stays untrimmed.
    assert large["trimmed"] is False
    assert large["sourceSize"] == {"w": 32, "h": 24}

    # Smaller frame carries frame offsets so playback aligns to the 32x24 canvas.
    assert small["trimmed"] is True
    assert small["sourceSize"] == {"w": 32, "h": 24}
    assert small["spriteSourceSize"]["x"] == 8
    assert small["spriteSourceSize"]["y"] == 6
