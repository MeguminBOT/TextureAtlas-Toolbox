#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Utilities.group_names_by_animation batch-aware grouping."""

from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from utils.utilities import Utilities


class TestGroupNamesByAnimation(unittest.TestCase):
    """Test batch-aware animation name grouping."""

    # ------------------------------------------------------------------
    # Simple / short-suffix cases (< 5 digits) – no sub-index splitting
    # ------------------------------------------------------------------

    def test_simple_trailing_digits(self):
        """idle0001, idle0002 → single group 'idle'."""
        names = ["idle0001", "idle0002", "idle0003"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("idle", result)
        self.assertEqual(len(result["idle"]), 3)

    def test_simple_underscore_separator(self):
        """run_001, run_002 → single group 'run'."""
        names = ["run_001", "run_002", "run_003"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("run", result)
        self.assertEqual(len(result["run"]), 3)

    def test_simple_space_separator(self):
        """walk 0, walk 1, walk 2 → single group 'walk'."""
        names = ["walk 0", "walk 1", "walk 2"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("walk", result)
        self.assertEqual(len(result["walk"]), 3)

    def test_simple_dot_separator(self):
        """anim.001, anim.002 → single group 'anim'."""
        names = ["anim.001", "anim.002"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("anim", result)
        self.assertEqual(len(result["anim"]), 2)

    def test_simple_dash_separator(self):
        """sprite-01, sprite-02 → single group 'sprite'."""
        names = ["sprite-01", "sprite-02"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("sprite", result)
        self.assertEqual(len(result["sprite"]), 2)

    def test_multiple_simple_animations(self):
        """Different text prefixes → separate groups."""
        names = ["idle0001", "idle0002", "run0001", "run0002"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("idle", result)
        self.assertIn("run", result)
        self.assertEqual(len(result["idle"]), 2)
        self.assertEqual(len(result["run"]), 2)

    def test_no_digits(self):
        """Names without trailing digits → each is its own group."""
        names = ["background", "logo"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("background", result)
        self.assertIn("logo", result)

    # ------------------------------------------------------------------
    # Sub-indexed sequences: RESET → separate animations
    # ------------------------------------------------------------------

    def test_reset_separate_animations(self):
        """Anim10001..10002, Anim20001..20002 → Anim1 and Anim2."""
        names = ["Anim10001", "Anim10002", "Anim20001", "Anim20002"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim1", result)
        self.assertIn("Anim2", result)
        self.assertEqual(result["Anim1"], ["Anim10001", "Anim10002"])
        self.assertEqual(result["Anim2"], ["Anim20001", "Anim20002"])

    def test_reset_three_animations(self):
        """Anim10001, Anim20001, Anim30001 → three separate animations."""
        names = ["Anim10001", "Anim20001", "Anim30001"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim1", result)
        self.assertIn("Anim2", result)
        self.assertIn("Anim3", result)
        self.assertEqual(len(result), 3)

    def test_reset_with_zero_start(self):
        """banban10007..10008, banban20000 → separate (banban1, banban2)."""
        names = ["banban10007", "banban10008", "banban20000"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("banban1", result)
        self.assertIn("banban2", result)
        self.assertEqual(result["banban1"], ["banban10007", "banban10008"])
        self.assertEqual(result["banban2"], ["banban20000"])

    def test_banban_xml_full(self):
        """Full banban.xml: banban10000-10008, banban20009-20016 → two groups."""
        names = [
            "banban10000", "banban10001", "banban10002", "banban10003",
            "banban10004", "banban10005", "banban10006", "banban10007",
            "banban10008",
            "banban20009", "banban20010", "banban20011", "banban20012",
            "banban20013", "banban20014", "banban20015", "banban20016",
        ]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("banban1", result)
        self.assertIn("banban2", result)
        self.assertEqual(len(result["banban1"]), 9)
        self.assertEqual(len(result["banban2"]), 8)
        self.assertNotIn("banban", result)

    def test_reset_with_separator(self):
        """Pico shoot 10000..10001, Pico shoot 20000..20001 → separate."""
        names = [
            "Pico shoot 10000",
            "Pico shoot 10001",
            "Pico shoot 20000",
            "Pico shoot 20001",
        ]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Pico shoot 1", result)
        self.assertIn("Pico shoot 2", result)
        self.assertEqual(len(result["Pico shoot 1"]), 2)
        self.assertEqual(len(result["Pico shoot 2"]), 2)

    def test_reset_with_underscore(self):
        """char_10001..10003, char_20001..20003 → separate."""
        names = [
            "char_10001",
            "char_10002",
            "char_10003",
            "char_20001",
            "char_20002",
            "char_20003",
        ]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("char_1", result)
        self.assertIn("char_2", result)
        self.assertEqual(len(result["char_1"]), 3)
        self.assertEqual(len(result["char_2"]), 3)

    # ------------------------------------------------------------------
    # Sub-indexed sequences: always split by sub-index
    # ------------------------------------------------------------------

    def test_subindex_split_continuous_frames(self):
        """Anim10001..10002, Anim20003..20004 → separate (Anim1, Anim2)."""
        names = ["Anim10001", "Anim10002", "Anim20003", "Anim20004"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim1", result)
        self.assertIn("Anim2", result)
        self.assertEqual(result["Anim1"], ["Anim10001", "Anim10002"])
        self.assertEqual(result["Anim2"], ["Anim20003", "Anim20004"])

    def test_subindex_split_three_subgroups(self):
        """Anim10001..10002, Anim20003..20004, Anim30005 → three groups."""
        names = [
            "Anim10001",
            "Anim10002",
            "Anim20003",
            "Anim20004",
            "Anim30005",
        ]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim1", result)
        self.assertIn("Anim2", result)
        self.assertIn("Anim3", result)
        self.assertEqual(len(result), 3)

    def test_subindex_split_banban_continuous(self):
        """banban10007, banban10008, banban20009 → separate (banban1, banban2)."""
        names = ["banban10007", "banban10008", "banban20009"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("banban1", result)
        self.assertIn("banban2", result)
        self.assertEqual(result["banban1"], ["banban10007", "banban10008"])
        self.assertEqual(result["banban2"], ["banban20009"])

    def test_subindex_split_with_separator_continuous(self):
        """Pico shoot 10000..10002, Pico shoot 20003 → separate groups."""
        names = [
            "Pico shoot 10000",
            "Pico shoot 10001",
            "Pico shoot 10002",
            "Pico shoot 20003",
        ]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Pico shoot 1", result)
        self.assertIn("Pico shoot 2", result)
        self.assertEqual(len(result["Pico shoot 1"]), 3)
        self.assertEqual(len(result["Pico shoot 2"]), 1)

    # ------------------------------------------------------------------
    # Single sub-group (only one leading digit value)
    # ------------------------------------------------------------------

    def test_single_subgroup_no_split(self):
        """All in same sub-group → one animation, no split."""
        names = ["Anim10000", "Anim10001", "Anim10002"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim", result)
        self.assertEqual(len(result["Anim"]), 3)

    # ------------------------------------------------------------------
    # Mixed animations with sub-indexing
    # ------------------------------------------------------------------

    def test_mixed_prefixes_with_subindex(self):
        """Different text prefixes, each with sub-indexed sequences."""
        names = [
            "idle10001",
            "idle10002",
            "idle20001",
            "idle20002",
            "run10001",
            "run10002",
            "run20001",
        ]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("idle1", result)
        self.assertIn("idle2", result)
        self.assertIn("run1", result)
        self.assertIn("run2", result)

    # ------------------------------------------------------------------
    # File extensions should be stripped before analysis
    # ------------------------------------------------------------------

    def test_with_png_extension(self):
        """Names with .png extension are handled correctly."""
        names = ["idle0001.png", "idle0002.png"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("idle", result)
        self.assertEqual(len(result["idle"]), 2)

    def test_subindex_with_extension(self):
        """Sub-indexed names with extensions."""
        names = ["Anim10001.png", "Anim10002.png", "Anim20001.png"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim1", result)
        self.assertIn("Anim2", result)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_input(self):
        result = Utilities.group_names_by_animation([])
        self.assertEqual(result, {})

    def test_single_name(self):
        result = Utilities.group_names_by_animation(["sprite0001"])
        self.assertIn("sprite", result)
        self.assertEqual(len(result["sprite"]), 1)

    def test_single_subindexed_name(self):
        """Single 5-digit suffix → no split (only one sub-group)."""
        result = Utilities.group_names_by_animation(["Anim10001"])
        self.assertIn("Anim", result)
        self.assertEqual(len(result["Anim"]), 1)

    def test_four_digit_suffix_not_split(self):
        """4-digit suffixes should never trigger sub-index splitting."""
        names = ["char0001", "char0002", "char0003"]
        result = Utilities.group_names_by_animation(names)
        self.assertEqual(len(result), 1)
        self.assertIn("char", result)

    def test_preserves_original_names(self):
        """Original name strings are preserved in the output lists."""
        names = ["Anim10001", "Anim10002", "Anim20001"]
        result = Utilities.group_names_by_animation(names)
        all_names = []
        for group_names in result.values():
            all_names.extend(group_names)
        self.assertEqual(sorted(all_names), sorted(names))

    def test_order_preserved_within_groups(self):
        """Names within each group are sorted by numeric suffix."""
        names = ["Anim10003", "Anim10001", "Anim10002"]
        result = Utilities.group_names_by_animation(names)
        self.assertIn("Anim", result)
        self.assertEqual(result["Anim"], ["Anim10001", "Anim10002", "Anim10003"])


if __name__ == "__main__":
    unittest.main()
