"""Safety regression tests for selecting source-backed effect previews."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from priority_effects import apply_overlay, frame_problem, select_effect


class EffectSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        data = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 3, 3)
        (self.root / "frame.png").write_bytes(data)
        self.frame = {"source_line": 3, "raw_fields": {"Frame#": 5, "Delay": 100, "Alpha": 0.0, "Light": -1},
                      "sentinel": False, "image": {"frame": 5, "size": [3, 3], "offset": [0, 0],
                      "source_empty_rectangle": False, "path": "frame.png", "sha256": hashlib.sha256(data).hexdigest()}}
        self.effect = {"id": 0, "source_id": "KR491:effect_sequence:0", "preview_supported": True,
                       "raw_fields": {"NumFrontFrames": 1, "NumBackFrames": 0,
                       "RepeatFrontFrom": -1, "RepeatFrontTo": -1, "RepeatBackFrom": -1, "RepeatBackTo": -1},
                       "front_frames": [self.frame], "back_frames": []}

    def tearDown(self):
        self.temp.cleanup()

    def test_negative_never_indexes_last_or_frame_zero(self):
        self.frame["raw_fields"]["Frame#"] = -1
        self.frame["sentinel"] = True
        chosen, report = select_effect(self.effect, self.root)
        self.assertFalse(chosen["priority_preview"]["available"])
        self.assertEqual(report["blocked_frames"][0]["reason"], "SENTINEL_OR_NEGATIVE_FRAME")

    def test_missing_and_corrupt_frames_are_distinct(self):
        self.frame["image"]["path"] = "missing.png"
        self.assertEqual(frame_problem(self.frame, self.root), "MISSING_FRAME_FILE")
        self.frame["image"]["path"] = "frame.png"
        self.frame["image"]["sha256"] = "0" * 64
        self.assertEqual(frame_problem(self.frame, self.root), "FRAME_DIGEST_MISMATCH")

    def test_empty_rectangle_is_not_blank_fallback(self):
        self.frame["image"]["source_empty_rectangle"] = True
        self.assertEqual(frame_problem(self.frame, self.root), "EMPTY_SOURCE_RECTANGLE")

    def test_path_escape_rejected(self):
        self.frame["image"]["path"] = "../outside.png"
        self.assertEqual(frame_problem(self.frame, self.root), "UNSAFE_IMAGE_PATH")

    def test_invalid_delay_and_infinite_control_rejected(self):
        self.frame["raw_fields"]["Delay"] = 0
        self.assertEqual(frame_problem(self.frame, self.root), "INVALID_DELAY")
        self.frame["raw_fields"]["Delay"] = 100
        self.frame["raw_fields"]["Light"] = float("inf")
        self.assertEqual(frame_problem(self.frame, self.root), "INVALID_LIGHT")

    def test_sentinel_splits_explicit_fragments_not_whole(self):
        bad = copy.deepcopy(self.frame)
        bad["raw_fields"]["Frame#"] = -1
        bad["sentinel"] = True
        bad["image"] = None
        self.effect["front_frames"] = [self.frame, bad, copy.deepcopy(self.frame)]
        self.effect["raw_fields"]["NumFrontFrames"] = 3
        chosen, report = select_effect(self.effect, self.root)
        preview = chosen["priority_preview"]
        self.assertFalse(preview["whole_sequence_available"])
        self.assertEqual(len(preview["fragments"]), 2)
        self.assertEqual([f["start"] for f in preview["fragments"]], [0, 2])
        self.assertEqual(report["valid_frame_count"], 2)

    def test_light_alpha_repeat_remain_reconstructed(self):
        self.frame["raw_fields"].update(Alpha=0.5, Light=41)
        self.effect["raw_fields"].update(RepeatFrontFrom=0, RepeatFrontTo=0)
        chosen, report = select_effect(self.effect, self.root)
        preview = chosen["priority_preview"]
        self.assertTrue(preview["whole_sequence_available"])
        self.assertEqual(preview["renderer"]["light"], "DISABLED")
        self.assertEqual(preview["renderer"]["opacity"], 1.0)
        self.assertEqual(preview["limits"]["repeat_count"], 0)
        self.assertEqual(preview["fact_status"], "RECONSTRUCTED")
        self.assertEqual(len(report["command_flags"]), 3)

    def test_overlay_is_fresh_and_bound_to_source_graph(self):
        chosen, _ = select_effect(self.effect, self.root)
        original = copy.deepcopy(self.effect)
        new = apply_overlay({"effects": [self.effect]}, {"effects": [chosen]})
        self.assertEqual(self.effect, original)
        self.assertIn("priority_preview", new["effects"][0])
        self.effect["front_frames"][0]["raw_fields"]["Light"] = 3
        with self.assertRaisesRegex(ValueError, "changed after selection"):
            apply_overlay({"effects": [self.effect]}, {"effects": [chosen]})


if __name__ == "__main__":
    unittest.main()
