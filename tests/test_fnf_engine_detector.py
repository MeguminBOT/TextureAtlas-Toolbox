#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for the FNF character data engine detector and importer.

Covers detection of Kade, Psych, Codename, and the new V-Slice engine
formats, and verifies the V-Slice import path wires animation settings
through to the settings manager correctly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from utils.FNF.character_data import CharacterData  # noqa: E402
from utils.FNF.engine_detector import detect_engine  # noqa: E402


# --------------------------------------------------------------------------- #
# Sample character payloads                                                   #
# --------------------------------------------------------------------------- #

VSLICE_BF = {
    "version": "1.0.1",
    "name": "Boyfriend",
    "renderType": "sparrow",
    "assetPath": "characters/BOYFRIEND",
    "scale": 1.0,
    "isPixel": False,
    "flipX": True,
    "danceEvery": 1,
    "singTime": 8.0,
    "startingAnimation": "idle",
    "offsets": [0, 0],
    "cameraOffsets": [0, 0],
    "animations": [
        {
            "name": "idle",
            "prefix": "BF idle dance",
            "frameRate": 24,
            "looped": False,
            "flipX": False,
            "flipY": False,
            "offsets": [0, 0],
        },
        {
            "name": "singLEFT",
            "prefix": "BF NOTE LEFT",
            "frameRate": 24,
            "looped": False,
            "offsets": [12, -6],
            "frameIndices": [0, 1, 2, 3],
        },
    ],
}

PSYCH_CHAR = {
    "image": "character1",
    "scale": 1,
    "flip_x": False,
    "no_antialiasing": False,
    "animations": [
        {
            "name": "idle",
            "anim": "BF idle dance",
            "fps": 24,
            "loop": False,
            "indices": [],
        }
    ],
}

KADE_CHAR = {
    "name": "Boyfriend",
    "asset": "BOYFRIEND",
    "startingAnim": "idle",
    "frameRate": 24,
    "scale": 1,
    "animations": [
        {
            "name": "idle",
            "prefix": "BF idle dance",
            "offsets": [0, 0],
            "looped": False,
            "frameIndices": [],
        }
    ],
}

CODENAME_XML = (
    '<character scale="1">'
    '<anim name="idle" anim="BF idle dance" fps="24" loop="false" '
    'indices="0..23" x="0" y="0"/>'
    "</character>"
)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _write_json(tmp_path: Path, name: str, data: dict) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


class RecordingSettingsManager:
    """Captures animation settings registered by ``CharacterData``."""

    def __init__(self) -> None:
        self.calls: dict[str, dict] = {}

    def set_animation_settings(self, name: str, **kwargs) -> None:
        self.calls[name] = kwargs


# --------------------------------------------------------------------------- #
# Detection tests                                                             #
# --------------------------------------------------------------------------- #


def test_detect_vslice_json(tmp_path: Path) -> None:
    path = _write_json(tmp_path, "bf.json", VSLICE_BF)
    engine, parsed = detect_engine(path)
    assert engine == "V-Slice Engine"
    assert parsed is not None and parsed["assetPath"] == "characters/BOYFRIEND"


def test_detect_psych_json(tmp_path: Path) -> None:
    path = _write_json(tmp_path, "psych.json", PSYCH_CHAR)
    engine, _ = detect_engine(path)
    assert engine == "Psych Engine"


def test_detect_kade_json(tmp_path: Path) -> None:
    path = _write_json(tmp_path, "kade.json", KADE_CHAR)
    engine, _ = detect_engine(path)
    assert engine == "Kade Engine"


def test_detect_codename_xml(tmp_path: Path) -> None:
    path = tmp_path / "codename.xml"
    path.write_text(CODENAME_XML, encoding="utf-8")
    engine, _ = detect_engine(str(path))
    assert engine == "Codename Engine"


def test_detect_unknown_for_garbage_json(tmp_path: Path) -> None:
    path = _write_json(tmp_path, "junk.json", {"foo": "bar"})
    engine, parsed = detect_engine(path)
    assert engine == "Unknown"
    assert parsed is None


def test_vslice_not_misdetected_as_kade(tmp_path: Path) -> None:
    """V-Slice payloads must take priority over the Kade matcher."""
    path = _write_json(tmp_path, "bf.json", VSLICE_BF)
    engine, _ = detect_engine(path)
    assert engine != "Kade Engine"


# --------------------------------------------------------------------------- #
# V-Slice import behavior                                                     #
# --------------------------------------------------------------------------- #


def test_vslice_import_registers_per_animation_settings(tmp_path: Path) -> None:
    path = _write_json(tmp_path, "bf.json", VSLICE_BF)
    manager = RecordingSettingsManager()

    CharacterData().import_character_settings(path, manager)

    # assetPath "characters/BOYFRIEND" should resolve to "BOYFRIEND.png".
    assert "BOYFRIEND.png/idle" in manager.calls
    assert "BOYFRIEND.png/singLEFT" in manager.calls

    idle = manager.calls["BOYFRIEND.png/idle"]
    # 24 fps -> ~42 ms duration.
    assert idle["duration"] == pytest.approx(42, abs=1)
    # Per-animation flipX False overrides character-level True.
    raw = idle["alignment_overrides"]["_fnf_raw_offsets"]
    assert raw.get("flip_x") in (None, False)

    sing = manager.calls["BOYFRIEND.png/singLEFT"]
    assert sing["indices"] == [0, 1, 2, 3]
    # No per-animation flipX -> inherits character-level True.
    sing_raw = sing["alignment_overrides"]["_fnf_raw_offsets"]
    assert sing_raw["flip_x"] is True
    # offsets [12, -6] become alignment defaults of (-12, 6).
    assert sing["alignment_overrides"]["default"] == {"x": -12, "y": 6}


def test_vslice_import_unsupported_file_raises(tmp_path: Path) -> None:
    path = _write_json(tmp_path, "junk.json", {"foo": "bar"})
    with pytest.raises(ValueError):
        CharacterData().import_character_settings(path, RecordingSettingsManager())
