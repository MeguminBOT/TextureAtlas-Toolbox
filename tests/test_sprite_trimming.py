#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for sprite trimming during atlas generation."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.generator.atlas_generator import AtlasGenerator, GeneratorOptions


def _make_sprite_with_padding(
    path: Path,
    content_size: tuple[int, int],
    padding: tuple[int, int, int, int],
    color: tuple[int, int, int, int],
):
    """Create a sprite with transparent padding around opaque content.
    
    Args:
        path: Where to save the image.
        content_size: (width, height) of the opaque region.
        padding: (left, top, right, bottom) transparent padding.
        color: RGBA color for the opaque region.
    """
    left, top, right, bottom = padding
    total_w = left + content_size[0] + right
    total_h = top + content_size[1] + bottom
    
    # Create fully transparent image
    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    
    # Draw opaque content box
    arr = np.array(img)
    arr[top:top + content_size[1], left:left + content_size[0]] = color
    
    result = Image.fromarray(arr)
    result.save(path)
    return total_w, total_h


def test_trimming_removes_transparent_edges(tmp_path: Path):
    """Test that trimming removes transparent edges and produces smaller atlas."""
    atlas_base = tmp_path / "trimmed_atlas"
    
    # Create a sprite with lots of transparent padding
    # 10x10 content with 20px padding on all sides = 50x50 total
    sprite_path = tmp_path / "padded_sprite.png"
    original_size = _make_sprite_with_padding(
        sprite_path,
        content_size=(10, 10),
        padding=(20, 20, 20, 20),
        color=(255, 0, 0, 255),
    )
    assert original_size == (50, 50)
    
    # Generate with trimming ENABLED
    generator = AtlasGenerator()
    options_trimmed = GeneratorOptions(
        max_width=128,
        max_height=128,
        padding=0,
        allow_rotation=False,
        trim_sprites=True,
        export_format="json-hash",
        image_format="png",
    )
    
    result_trimmed = generator.generate(
        {"test": [str(sprite_path)]},
        str(atlas_base) + "_trimmed",
        options_trimmed,
    )
    
    assert result_trimmed.success, f"Trimmed generation failed: {result_trimmed.errors}"
    
    # The trimmed atlas should only be 10x10 (the content size)
    assert result_trimmed.atlas_width == 10, f"Expected width 10, got {result_trimmed.atlas_width}"
    assert result_trimmed.atlas_height == 10, f"Expected height 10, got {result_trimmed.atlas_height}"
    
    # Check metadata has correct trim offsets
    with open(result_trimmed.metadata_path, "r") as f:
        metadata = json.load(f)
    
    frame = metadata["frames"]["test_01"]
    
    # Trimmed frame should be 10x10 in atlas
    assert frame["frame"]["w"] == 10
    assert frame["frame"]["h"] == 10
    
    # spriteSourceSize.x/y should indicate the trim offset (20px padding was removed)
    assert frame["spriteSourceSize"]["x"] == 20
    assert frame["spriteSourceSize"]["y"] == 20
    
    # sourceSize should be the original 50x50
    assert frame["sourceSize"]["w"] == 50
    assert frame["sourceSize"]["h"] == 50
    
    # Should be marked as trimmed
    assert frame["trimmed"] is True


def test_no_trimming_when_disabled(tmp_path: Path):
    """Test that disabling trimming preserves original dimensions."""
    atlas_base = tmp_path / "untrimmed_atlas"
    
    # Create same padded sprite
    sprite_path = tmp_path / "padded_sprite.png"
    _make_sprite_with_padding(
        sprite_path,
        content_size=(10, 10),
        padding=(20, 20, 20, 20),
        color=(255, 0, 0, 255),
    )
    
    # Generate with trimming DISABLED
    generator = AtlasGenerator()
    options_untrimmed = GeneratorOptions(
        max_width=128,
        max_height=128,
        padding=0,
        allow_rotation=False,
        trim_sprites=False,
        export_format="json-hash",
        image_format="png",
    )
    
    result_untrimmed = generator.generate(
        {"test": [str(sprite_path)]},
        str(atlas_base),
        options_untrimmed,
    )
    
    assert result_untrimmed.success, f"Untrimmed generation failed: {result_untrimmed.errors}"
    
    # Without trimming, atlas should be full 50x50
    assert result_untrimmed.atlas_width == 50
    assert result_untrimmed.atlas_height == 50


def test_trimming_efficiency_improvement(tmp_path: Path):
    """Test that trimming significantly reduces atlas size."""
    # Create multiple sprites with heavy padding
    sprites = []
    for i in range(4):
        sprite_path = tmp_path / f"sprite_{i}.png"
        _make_sprite_with_padding(
            sprite_path,
            content_size=(20, 20),
            padding=(30, 30, 30, 30),  # 80x80 total, 20x20 content
            color=(i * 60, 100, 200, 255),
        )
        sprites.append(str(sprite_path))
    
    generator = AtlasGenerator()
    
    # With trimming
    options_trimmed = GeneratorOptions(
        max_width=512,
        max_height=512,
        padding=2,
        trim_sprites=True,
        export_format="json-hash",
    )
    result_trimmed = generator.generate(
        {"anim": sprites},
        str(tmp_path / "atlas_trimmed"),
        options_trimmed,
    )
    
    # Without trimming
    options_untrimmed = GeneratorOptions(
        max_width=512,
        max_height=512,
        padding=2,
        trim_sprites=False,
        export_format="json-hash",
    )
    result_untrimmed = generator.generate(
        {"anim": sprites},
        str(tmp_path / "atlas_untrimmed"),
        options_untrimmed,
    )
    
    assert result_trimmed.success
    assert result_untrimmed.success
    
    # Calculate areas
    trimmed_area = result_trimmed.atlas_width * result_trimmed.atlas_height
    untrimmed_area = result_untrimmed.atlas_width * result_untrimmed.atlas_height
    
    # Trimmed should be significantly smaller
    # 4 sprites at 20x20 + padding vs 4 sprites at 80x80 + padding
    # At minimum, trimmed area should be less than 25% of untrimmed
    assert trimmed_area < untrimmed_area * 0.25, (
        f"Trimmed area {trimmed_area} should be much smaller than "
        f"untrimmed area {untrimmed_area}"
    )
