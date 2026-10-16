"""P3 export staging safety. These fixtures do not claim platform execution."""
import json
from pathlib import Path
import tempfile
import unittest

from gameplay_platform import PACKAGE, USER_DIR, checkpoint_names, presets, stage_project
from work_platform import snapshot


class GameplayPlatformSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project, self.runtime = self.root / "source", self.root / "runtime"
        self.project.mkdir()
        self.runtime.mkdir()
        (self.project / "project.godot").write_text('config_version=5\n[application]\nconfig/use_custom_user_dir=true\nconfig/custom_user_dir_name="preserved-old-test"\n')
        (self.runtime / "runtime.json").write_text('{"generation":"SYNTHETIC-NOT-A-GAME"}')
        (self.runtime / "gameplay_content.json").write_text('{}')

    def tearDown(self):
        self.temp.cleanup()

    def test_staging_preserves_source_runtime_and_isolates_userdata(self):
        old_source, old_runtime = snapshot(self.project), snapshot(self.runtime)
        stage = self.root / "fresh-private-stage"
        status = stage_project(self.project, self.runtime, stage, self.root / "templates")
        self.assertEqual(snapshot(self.project), old_source)
        self.assertEqual(snapshot(self.runtime), old_runtime)
        self.assertEqual(snapshot(stage / "private_runtime"), old_runtime)
        self.assertIn(USER_DIR, (stage / "project.godot").read_text())
        self.assertEqual(status["package"], PACKAGE)
        self.assertNotIn("preserved-old-test", (stage / "project.godot").read_text())

    def test_private_font_key_database_never_enters_runtime(self):
        for extension in [".ttf", ".keystore", ".sql"]:
            file = self.runtime / ("forbidden" + extension)
            file.write_bytes(b"synthetic")
            with self.assertRaisesRegex(ValueError, "Forbidden"):
                stage_project(self.project, self.runtime, self.root / "never-created", self.root / "templates")
            file.unlink()

    def test_symlink_runtime_rejected(self):
        (self.runtime / "escape").symlink_to(self.project / "project.godot")
        with self.assertRaisesRegex(ValueError, "symlink"):
            stage_project(self.project, self.runtime, self.root / "never-created", self.root / "templates")

    def test_existing_stage_is_not_overwritten(self):
        stage = self.root / "existing"
        stage.mkdir()
        (stage / "original").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "new private path"):
            stage_project(self.project, self.runtime, stage, self.root / "templates")
        self.assertEqual((stage / "original").read_text(), "preserve")

    def test_default_exports_have_no_automatic_smoke_feature_or_args(self):
        text = presets(self.root / "templates")
        self.assertNotIn("p2_smoke", text)
        self.assertNotIn("gameplay-smoke", text)
        self.assertNotIn("command_line/extra_args", text)
        self.assertEqual(text.count('custom_features=""'), 2)
        self.assertIn('package/unique_name="' + PACKAGE + '"', text)

    def test_checkpoint_parser_keeps_stage_sequence_and_skips_nonrecords(self):
        raw = b'engine log\nGAMEPLAY_STAGE {"stage":"engine"}\n{"stage":"first_frame"}\nnull\n'
        self.assertEqual(checkpoint_names(raw), ["engine", "first_frame"])


if __name__ == "__main__":
    unittest.main()
