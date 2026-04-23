#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regenerate every supported atlas format from ``TEST/starling.xml``.

This is a smoke / round-trip script for confirming spec-conformant
output across all registered exporters. It:

  1. Parses ``TEST/starling.xml`` + ``TEST/starling.png`` with the
     existing :class:`StarlingXmlParser`.
  2. Restores each ``<SubTexture>`` to its untrimmed source size using
     ``frameX``/``frameY``/``frameWidth``/``frameHeight`` so the
     re-packed atlases see logical full-size frames just like a fresh
     import would.
  3. Writes the unpacked frames to a temp directory grouped by
     animation name (trailing digits stripped).
  4. Iterates every format registered with
     :class:`ExporterRegistry` and runs the full
     :class:`AtlasGenerator` pipeline once per format, dropping each
     atlas+metadata pair into ``TEST/_regen/<format>/``.

Usage::

    python tools/regen_all_formats_from_starling.py
    python tools/regen_all_formats_from_starling.py --source TEST/starling.xml
    python tools/regen_all_formats_from_starling.py --formats json-hash spine
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from PIL import Image

# Make ``src/`` importable when run from the repository root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core.generator.atlas_generator import (  # noqa: E402
    AtlasGenerator,
    GeneratorOptions,
)
from exporters.exporter_registry import ExporterRegistry  # noqa: E402
from parsers.starling_xml_parser import StarlingXmlParser  # noqa: E402
from utils.utilities import Utilities  # noqa: E402

# Ensure every exporter module is imported so the registry is populated.
import exporters  # noqa: E402,F401


# Formats that are atypical end-points (not driven by the standard
# generate() path or no longer in the public registry). The script will
# skip these and report them.
_SKIP_FORMATS: frozenset[str] = frozenset()


def _restore_source_frame(
    atlas: Image.Image, sprite: Dict[str, object]
) -> Image.Image:
    """Return the sprite restored to its untrimmed source-frame size.

    Starling/Sparrow sprites store the trimmed sub-texture rect in
    ``x/y/width/height`` plus the offsets back into the original
    untrimmed art via ``frameX/frameY/frameWidth/frameHeight``. To
    re-pack as if the artist had supplied the original frames, we paste
    the trimmed crop back onto a transparent canvas at the recorded
    offset so each generator input matches the source dimensions.
    """
    sx = int(sprite["x"])
    sy = int(sprite["y"])
    sw = int(sprite["width"])
    sh = int(sprite["height"])
    crop = atlas.crop((sx, sy, sx + sw, sy + sh))

    frame_w = int(sprite.get("frameWidth", sw) or sw)
    frame_h = int(sprite.get("frameHeight", sh) or sh)
    # frameX/frameY are negative offsets that say where the trimmed
    # crop sits inside the original frame. Paste position is the
    # absolute value so transparent padding surrounds the crop.
    paste_x = -int(sprite.get("frameX", 0) or 0)
    paste_y = -int(sprite.get("frameY", 0) or 0)

    # Fall back to the crop itself if the recorded source frame is
    # degenerate (which would otherwise hide the sprite entirely).
    if frame_w <= 0 or frame_h <= 0:
        return crop

    canvas = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    canvas.paste(crop, (paste_x, paste_y))
    return canvas


def _extract_animation_groups(
    xml_path: Path, image_path: Path, work_dir: Path
) -> Dict[str, List[str]]:
    """Extract every sub-texture as a PNG and group them by animation.

    Returns a mapping of ``animation_name -> [frame_path, ...]`` ready
    to feed into :meth:`AtlasGenerator.generate`.
    """
    sprites = StarlingXmlParser.parse_xml_data(str(xml_path))
    if not sprites:
        raise SystemExit(f"No <SubTexture> entries found in {xml_path}")

    with Image.open(image_path) as raw_atlas:
        atlas = raw_atlas.convert("RGBA")

    # Group by stripped name while preserving the original frame order
    # from the XML. We index frames per group so collisions across
    # different animations can never overwrite each other on disk.
    groups: Dict[str, List[str]] = {}
    counters: Dict[str, int] = {}

    for sprite in sprites:
        name = str(sprite.get("name") or "").strip()
        if not name:
            continue
        anim = Utilities.strip_trailing_digits(name) or name
        idx = counters.get(anim, 0)
        counters[anim] = idx + 1

        frame_image = _restore_source_frame(atlas, sprite)
        anim_dir = work_dir / _safe_dir_name(anim)
        anim_dir.mkdir(parents=True, exist_ok=True)
        frame_path = anim_dir / f"{idx:04d}.png"
        frame_image.save(frame_path, format="PNG")
        groups.setdefault(anim, []).append(str(frame_path))

    return groups


def _safe_dir_name(name: str) -> str:
    """Return a filesystem-safe directory name for an animation group."""
    return "".join(ch if ch.isalnum() or ch in (" ", "_", "-") else "_" for ch in name)


def _registered_formats() -> List[str]:
    """Return all exporter format keys registered with the registry."""
    formats = sorted(set(ExporterRegistry._exporters_by_name.keys()))
    return [fmt for fmt in formats if fmt not in _SKIP_FORMATS]


def _run_format(
    fmt: str,
    animation_groups: Dict[str, List[str]],
    out_root: Path,
) -> Tuple[bool, str]:
    """Run the generator for *fmt* and return (success, message)."""
    fmt_dir = out_root / fmt
    if fmt_dir.exists():
        shutil.rmtree(fmt_dir)
    fmt_dir.mkdir(parents=True, exist_ok=True)
    output_base = fmt_dir / "atlas"

    options = GeneratorOptions(
        max_width=4096,
        max_height=4096,
        padding=2,
        allow_rotation=False,
        trim_sprites=True,
        export_format=fmt,
        image_format="png",
    )

    generator = AtlasGenerator()
    result = generator.generate(animation_groups, str(output_base), options)
    if not result.success:
        return False, "; ".join(result.errors) or "unknown failure"
    bits: List[str] = [
        f"{result.frame_count} frames",
        f"{result.atlas_width}x{result.atlas_height}",
        f"eff={result.efficiency * 100:.1f}%",
    ]
    if result.warnings:
        bits.append(f"warnings={len(result.warnings)}")
    return True, ", ".join(bits)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=_REPO_ROOT / "TEST" / "starling.xml",
        help="Starling/Sparrow XML file to regenerate from.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Override path to the atlas image (defaults to <source>.png).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_REPO_ROOT / "TEST" / "_regen",
        help="Directory where per-format outputs are written.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=None,
        help="Optional subset of format keys to regenerate.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary frame directory for inspection.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    xml_path: Path = args.source
    image_path: Path = args.image or xml_path.with_suffix(".png")
    if not xml_path.is_file():
        raise SystemExit(f"Starling XML not found: {xml_path}")
    if not image_path.is_file():
        raise SystemExit(f"Atlas image not found: {image_path}")

    formats = args.formats or _registered_formats()
    if not formats:
        raise SystemExit("No exporter formats are registered.")

    out_root: Path = args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="regen_starling_"))
    print(f"Extracting frames -> {temp_dir}")
    try:
        animation_groups = _extract_animation_groups(xml_path, image_path, temp_dir)
        print(
            f"  parsed {sum(len(v) for v in animation_groups.values())} frames "
            f"across {len(animation_groups)} animations"
        )

        print(f"Writing per-format outputs -> {out_root}")
        results: List[Tuple[str, bool, str]] = []
        for fmt in formats:
            ok, msg = _run_format(fmt, animation_groups, out_root)
            status = "OK  " if ok else "FAIL"
            print(f"  [{status}] {fmt:<20} {msg}")
            results.append((fmt, ok, msg))

        failures = [r for r in results if not r[1]]
        print(
            f"\nSummary: {len(results) - len(failures)} ok, {len(failures)} failed"
        )
        if failures:
            for fmt, _, msg in failures:
                print(f"  - {fmt}: {msg}")
        return 0 if not failures else 1
    finally:
        if not args.keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
