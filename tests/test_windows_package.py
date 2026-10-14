"""Packaging safety and byte equivalence; these are not Windows play tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("package_windows", Path(__file__).resolve().parents[1]/"tools/package_windows.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class WindowsPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.payloads = {
            "game/main.gd":b"verified game",
            "private_assets/tiles/atlas.png":b"private bytes",
            "private_content/ACTIVE.json":b'{"release_id":"fixed"}',
            "licenses/GODOT-LICENSE.txt":b"MIT",
            "intake_inputs/not-needed.bin":b"not a runtime asset",
        }

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, change=None, extra=None):
        manifest = dict(contains_user_saves=False, private_only=True,
                        files=[dict(path=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
                               for p,b in self.payloads.items()])
        if change:
            change(manifest)
        path = self.root/"input.zip"
        with zipfile.ZipFile(path,"w") as z:
            for name, raw in self.payloads.items():
                z.writestr("fixed/"+name,raw)
            z.writestr("fixed/PACKAGE_MANIFEST.json", json.dumps(manifest))
            if extra:
                z.writestr(*extra)
        return path, package.sha256(path)

    def test_exact_private_bytes_and_no_development_or_saves(self):
        path, digest = self.archive()
        stage = self.root/"out"
        source = package.extract_source(path,digest,stage)
        result = package.verify_private_equivalence(source,stage)
        self.assertEqual(result["files"],2)
        self.assertEqual((stage/"private_assets/tiles/atlas.png").read_bytes(),b"private bytes")
        self.assertFalse((stage/"intake_inputs").exists())
        self.assertFalse((stage/"saves").exists())

    def test_wrong_source_hash_does_not_create_destination(self):
        path, _ = self.archive()
        with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
            package.extract_source(path,"0"*64,self.root/"out")
        self.assertFalse((self.root/"out").exists())

    def test_path_escape_is_rejected_before_writing_assets(self):
        path, digest = self.archive(extra=("fixed/../../escape",b"bad"))
        with self.assertRaisesRegex(ValueError,"Unsafe"):
            package.extract_source(path,digest,self.root/"out")
        self.assertFalse((self.root/"escape").exists())
        self.assertFalse((self.root/"out/private_assets").exists())

    def test_symlink_is_rejected(self):
        link = zipfile.ZipInfo("fixed/private_assets/link")
        link.create_system = 3
        link.external_attr = (0o120777 << 16)
        path, digest = self.archive(extra=(link,b"/etc/passwd"))
        with self.assertRaisesRegex(ValueError,"symlink"):
            package.extract_source(path,digest,self.root/"out")

    def test_source_manifest_mismatch_is_rejected(self):
        path, digest = self.archive(change=lambda m:m["files"][1].update(sha256="0"*64))
        with self.assertRaisesRegex(ValueError,"Source member SHA mismatch"):
            package.extract_source(path,digest,self.root/"out")

    def test_extra_or_missing_private_asset_is_not_equivalent(self):
        path,digest = self.archive()
        stage = self.root/"out"
        source = package.extract_source(path,digest,stage)
        (stage/"private_assets/extra.png").write_bytes(b"new")
        with self.assertRaisesRegex(ValueError,"membership"):
            package.verify_private_equivalence(source,stage)
        (stage/"private_assets/extra.png").unlink()
        (stage/"private_assets/tiles/atlas.png").unlink()
        with self.assertRaisesRegex(ValueError,"membership"):
            package.verify_private_equivalence(source,stage)

    def test_private_bytes_cannot_be_silently_changed(self):
        path,digest = self.archive()
        stage = self.root/"out"
        source = package.extract_source(path,digest,stage)
        (stage/"private_assets/tiles/atlas.png").write_bytes(b"altered bytes")
        with self.assertRaisesRegex(ValueError,"Private content changed"):
            package.verify_private_equivalence(source,stage)

    def test_pe_requires_64_bit_gui_not_32_bit_editor_shell(self):
        raw = bytearray(512)
        raw[:2] = b"MZ"
        struct.pack_into("<I",raw,0x3c,128)
        raw[128:132] = b"PE\0\0"
        struct.pack_into("<H",raw,132,0x8664)
        struct.pack_into("<H",raw,152,0x20b)
        struct.pack_into("<H",raw,220,2)
        path = self.root/"engine.exe"
        path.write_bytes(raw)
        self.assertEqual(package.pe_info(path)["machine"],"AMD64")
        struct.pack_into("<H",raw,132,0x14c)
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,"AMD64"):
            package.pe_info(path)

    def finalization_fixture(self, report_status, game_build="fixed-code"):
        source=self.root/"initial"
        source.mkdir()
        (source/"payload").write_bytes(b"immutable")
        manifest=dict(build=dict(commit="fixed-code",content_version="fixed-content"),
                      files=[dict(path="payload",bytes=9,sha256=package.sha256(source/"payload"))])
        package.json_write(source/"PACKAGE_MANIFEST.json",manifest)
        initial=self.root/"initial.zip"
        with zipfile.ZipFile(initial,"w") as z:
            z.write(source/"payload","payload")
        package.json_write(self.root/"build.json",dict(stage=str(source),archive=str(initial),sha256=package.sha256(initial)))
        package.json_write(self.root/"game.json",dict(status="PASS_EXECUTED_SCREEN_INPUT",game_build=game_build,
                                                     content_version="fixed-content",checks=[dict(status="PASS",name="input")]))
        run=dict(exit_code=0,game_report=str(self.root/"game.json"),mode="work-core",x11_captures=[dict(status="PASS")],audio_mix=dict(status="PASS_PCM_SIGNAL"))
        package.json_write(self.root/"evidence.json",dict(status=report_status,runs=[run]))
        return SimpleNamespace(build_report=str(self.root/"build.json"),evidence_report=[str(self.root/"evidence.json")],
                               out=str(self.root/"final"),report=str(self.root/"final-report.json"))

    def test_finalization_refuses_unexecuted_or_generic_pass(self):
        args=self.finalization_fixture("PASS")
        with self.assertRaisesRegex(ValueError,"actually executed"):
            package.finalize(args)
        self.assertFalse((self.root/"final").exists())

    def test_finalization_refuses_evidence_from_other_game_build(self):
        args=self.finalization_fixture("PASS_EXECUTED_SCREEN_INPUT_AND_RESTART",game_build="other-code")
        with self.assertRaisesRegex(ValueError,"does not match frozen game"):
            package.finalize(args)
        self.assertFalse((self.root/"final").exists())

    def test_finalization_requires_actual_pickup_and_restart_modes(self):
        args=self.finalization_fixture("PASS_EXECUTED_SCREEN_INPUT_AND_RESTART")
        with self.assertRaisesRegex(ValueError,"actual pickup"):
            package.finalize(args)
        self.assertFalse((self.root/"final").exists())


if __name__ == "__main__":
    unittest.main()
