"""Receiver guards use synthetic data; they do not validate historical assets."""
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from cache_fingerprint import COMPONENTS, fingerprint
from receive_work_batch import Limits, identity, review, safe_name, Rejected


def encoded(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = "a" * 40
        self.old_hash = "c" * 64
        self.dependency = {"kind": "frozen_P1_5", "sha": self.base, "core_version": 1,
                           "core_library_id": "libfile_1234", "core_sha256": "d" * 64}
        self.candidate = {
            "schema": "baram-work-field-candidate-v1", "task_id": "BARAM_REBUILD_WORK_SOURCE_DELTA_001",
            "candidate_id": "WD-MS-001", "base_p1_5_sha": self.base,
            "binding_ids": ["BND-023"], "requirement_ids": ["RQ-088"],
            "existing_record_ids": ["KR491:effect_sequence:56"], "field": "delay_raw_unit",
            "profile_id": "EXPLICIT_KR_PROFILE", "selected_for_build": False,
            "codex_tests": ["Observe original timing; unknown unit stays unknown"],
            "old_value_or_hash": {"old_value": "UNKNOWN", "prior_sha256": self.old_hash},
            "payload_refs": ["motion_sound/timing.json"],
            "source_locator": {"private_file": {"relative_private_path": "motion_sound/timing.json",
                                                 **identity(encoded({"unit": "UNKNOWN"}))}}}
        self.source = {"source_id": "synthetic", "private_file": self.candidate["source_locator"]["private_file"],
                       "input_source_sha256": {"synthetic_original": self.old_hash}}
        self.payload = {"FIELD_CANDIDATES.jsonl": encoded(self.candidate), "SOURCES.jsonl": encoded(self.source),
                        "README.md": b"Synthetic fixture only.\n", "motion_sound/timing.json": encoded({"unit": "UNKNOWN"})}
        self.manifest = {
            "schema": "baram.work_source_delta.batch/1", "task_id": "BARAM_REBUILD_WORK_SOURCE_DELTA_001",
            "batch_id": "B001", "base_p1_5_sha": self.base, "input_manifest_sha256": "b" * 64,
            "profile_dispatch_required": True, "default_build_profile_id": None,
            "profiles": ["EXPLICIT_KR_PROFILE"], "dependencies": [self.dependency], "supersedes": [],
            "candidate_ids": ["WD-MS-001"], "valid_binding_ids": ["BND-023"], "affected_bindings": ["BND-023"]}
        self.policy = {
            "work_commit": "e" * 40, "batch_id": "B001", "base_p1_5_sha": self.base,
            "input_manifest_sha256": "b" * 64, "profiles": ["EXPLICIT_KR_PROFILE"],
            "dependencies": [self.dependency], "supersedes": [], "valid_binding_ids": ["BND-023"],
            "valid_requirement_ids": ["RQ-088"], "declared_prior_hashes": [self.old_hash],
            "verified_prior_hashes": [self.old_hash], "verified_record_ids": ["KR491:effect_sequence:56"],
            "verified_dependencies": [self.dependency]}
        self.refresh()

    def refresh(self, members=None):
        self.payload["FIELD_CANDIDATES.jsonl"] = encoded(self.candidate)
        self.manifest["files"] = [{"path": name, **identity(data)} for name, data in self.payload.items()]
        manifest = encoded(self.manifest)
        validation = encoded({"schema": "baram.work_source_delta.validation/1", "result": "PASS", "errors": [],
                              "files_checked": len(self.payload)})
        content = {**self.payload, "MANIFEST.json": manifest, "VALIDATION.json": validation}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in (content.items() if members is None else members(content)):
                archive.writestr(name, data)
        self.archive = self.root / "B001.zip"
        self.archive.write_bytes(zip_buffer.getvalue())
        self.policy["zip"] = {**identity(zip_buffer.getvalue()), "library_file_id": "libfile_1234",
                              "file_id": "file_5678", "version": 0}
        ready = ("길이: {bytes}\nSHA256: {sha256}\n지속 파일 ID: {library_file_id}\n파일 ID: {file_id}\n버전: {version}\n".format(**self.policy["zip"])).encode()
        raw = {"manifest": manifest, "validation": validation, "candidates": self.payload["FIELD_CANDIDATES.jsonl"], "ready": ready}
        self.paths = {}
        self.policy["snapshot_files"] = {}
        for name, data in raw.items():
            path = self.root / (name + ".json")
            path.write_bytes(data)
            self.paths[name + "_path"] = path
            self.policy["snapshot_files"][name] = identity(data)

    def run_review(self, with_zip=True, limits=Limits()):
        return review(**self.paths, policy=self.policy, zip_path=self.archive if with_zip else None, limits=limits)

    def assertRejected(self, expected):
        result = self.run_review()
        self.assertEqual(result["status"], "REJECTED", result)
        self.assertTrue(any(expected in error for error in result["errors"]), result)

    def test_missing_private_zip_is_deferred_even_matching_public_candidates(self):
        result = self.run_review(with_zip=False)
        self.assertEqual(result["metadata_result"], "PASS")
        self.assertEqual(result["status"], "DEFERRED")
        self.assertEqual(result["private_payload_result"], "NOT_RUN_MISSING_BYTES")
        self.assertEqual(result["adopted_fields"], [])

    def test_exact_batch_is_received_but_never_adopted_or_exercised(self):
        before = set(self.root.iterdir())
        result = self.run_review()
        self.assertEqual(result["status"], "RECEIVED", result)
        self.assertEqual(result["adoption"], "NOT_STARTED")
        self.assertEqual(result["runtime"], "NOT_RUN")
        self.assertEqual(set(self.root.iterdir()), before)

    def test_missing_original_records_remains_deferred_with_zip(self):
        self.policy["verified_record_ids"] = []
        result = self.run_review()
        self.assertEqual(result["status"], "DEFERRED")
        self.assertEqual(result["private_payload_result"], "PASS_BYTES_AND_FORMATS")

    def test_missing_prior_bytes_remains_deferred(self):
        self.policy["verified_prior_hashes"] = []
        self.assertEqual(self.run_review()["status"], "DEFERRED")

    def test_missing_dependency_bytes_remains_deferred(self):
        self.policy["verified_dependencies"] = []
        self.assertEqual(self.run_review()["status"], "DEFERRED")

    def test_metadata_hash_tampering(self):
        self.paths["manifest_path"].write_bytes(b"{}\n")
        self.assertRejected("metadata length/hash")

    def test_missing_public_metadata_is_rejected(self):
        self.paths["ready_path"].unlink()
        self.assertRejected("No such file")

    def test_unknown_profile(self):
        self.candidate["profile_id"] = "DIFFERENT_ERA"
        self.refresh()
        self.assertRejected("candidate profile")

    def test_dependency_pin_conflict(self):
        self.manifest["dependencies"] = []
        self.refresh()
        self.assertRejected("dependency conflict")

    def test_existing_hash_conflict(self):
        self.candidate["old_value_or_hash"]["prior_sha256"] = "f" * 64
        self.refresh()
        self.assertRejected("prior input hash conflict")

    def test_unknown_requirement(self):
        self.candidate["requirement_ids"] = ["RQ-999"]
        self.refresh()
        self.assertRejected("unknown requirement")

    def test_unknown_binding(self):
        self.candidate["binding_ids"] = ["BND-999"]
        self.refresh()
        self.assertRejected("unknown binding")

    def test_missing_private_payload_reference(self):
        self.candidate["payload_refs"] = ["absent.json"]
        self.refresh()
        self.assertRejected("missing payload reference")

    def test_private_locator_hash_conflict(self):
        self.candidate["source_locator"]["private_file"]["sha256"] = "0" * 64
        self.refresh()
        self.assertRejected("source identity conflict")

    def test_outer_zip_hash_tampering(self):
        with self.archive.open("ab") as stream:
            stream.write(b"changed")
        self.assertRejected("ZIP length/hash")

    def test_inner_hash_tampering_with_updated_outer_pin(self):
        def change(content):
            content["README.md"] = b"X" * len(content["README.md"])
            return content.items()
        self.refresh(change)
        self.assertRejected("ZIP member hash")

    def test_prefix_wrapping_is_not_silently_stripped(self):
        self.refresh(lambda content: [("B001/" + key, data) for key, data in content.items()])
        self.assertRejected("unexpected ZIP member")

    def test_zip_path_traversal(self):
        self.refresh(lambda content: [("../README.md" if key == "README.md" else key, data) for key, data in content.items()])
        self.assertRejected("unsafe path component")

    def test_zip_symlink(self):
        def symlink(content):
            info = zipfile.ZipInfo("README.md")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            return [(info if key == "README.md" else key, data) for key, data in content.items()]
        self.refresh(symlink)
        self.assertRejected("nonregular/symlink")

    def test_input_symlink_parent_is_rejected(self):
        linked = self.root / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        self.paths["ready_path"] = linked / self.paths["ready_path"].name
        self.assertRejected("symlink")

    def test_missing_zip_member(self):
        self.refresh(lambda content: [(key, value) for key, value in content.items() if key != "README.md"])
        self.assertRejected("exact file-set")

    def test_extra_zip_member(self):
        self.refresh(lambda content: [*content.items(), ("injected.py", b"raise Exception('must not run')")])
        self.assertRejected("exact file-set")

    def test_case_alias_manifest_paths(self):
        self.payload["readme.md"] = b"alias"
        self.refresh()
        self.assertRejected("case-alias manifest")

    def test_manifest_file_directory_collision(self):
        self.payload["README.md/child"] = b"collision"
        self.refresh()
        self.assertRejected("prefix collision")

    def test_depth_and_windows_path_rejection(self):
        for path in ["a:b", "C:/file", "CON.txt", "a/../b", "/root", "a\\b", "a/", "a. ", "a/" * 9 + "b"]:
            with self.subTest(path=path), self.assertRaises(Rejected):
                safe_name(path, Limits())

    def test_declared_oversize_rejected_before_decompression(self):
        result = self.run_review(limits=Limits(total_bytes=100))
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("total size limit", result["errors"])

    def test_empty_payload_set_cannot_pass(self):
        self.payload = {}
        self.refresh()
        self.manifest["files"] = []
        data = encoded(self.manifest)
        self.paths["manifest_path"].write_bytes(data)
        self.policy["snapshot_files"]["manifest"] = identity(data)
        self.assertRejected("empty/oversize")

    def test_font_or_sensitive_database_is_not_accepted(self):
        for name in ["private.ttf", "accounts.sql", "signing.jks"]:
            with self.subTest(path=name):
                self.payload[name] = b"forbidden fixture"
                self.refresh()
                self.assertRejected("excluded sensitive/font/database")
                del self.payload[name]

    def test_source_payload_reference_conflict(self):
        self.source["private_file"] = {**self.source["private_file"], "sha256": "9" * 64}
        self.payload["SOURCES.jsonl"] = encoded(self.source)
        self.refresh()
        self.assertRejected("source payload locator conflict")

    def test_source_prior_input_identity_conflict(self):
        self.source["input_source_sha256"] = {"synthetic_original": "f" * 64}
        self.payload["SOURCES.jsonl"] = encoded(self.source)
        self.refresh()
        self.assertRejected("source prior input hash conflict")

    def test_zero_time_budget_cannot_pass(self):
        result = self.run_review(limits=Limits(seconds=0))
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("ZIP time limit", result["errors"])

    def test_decompression_ratio_limit(self):
        result = self.run_review(limits=Limits(ratio=1))
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("ZIP ratio limit", result["errors"])

    def test_batch_document_strings_are_never_executed(self):
        marker = self.root / "executed"
        self.payload["README.md"] = ("$(touch " + str(marker) + ")\n").encode()
        self.refresh()
        self.assertEqual(self.run_review()["status"], "RECEIVED")
        self.assertFalse(marker.exists())


class CacheFingerprintTests(unittest.TestCase):
    def test_converter_only_change_invalidates_cache(self):
        components = {name: hashlib.sha256(name.encode()).hexdigest() for name in COMPONENTS}
        first = fingerprint(components)
        second = {**components, "converter": hashlib.sha256(b"converter v2").hexdigest()}
        self.assertNotEqual(first, fingerprint(second))
        self.assertEqual(first, fingerprint(dict(reversed(list(components.items())))))

    def test_each_required_component_invalidates_cache(self):
        components = {name: "0" * 64 for name in COMPONENTS}
        for name in COMPONENTS:
            with self.subTest(component=name):
                self.assertNotEqual(fingerprint(components), fingerprint({**components, name: "1" * 64}))

    def test_missing_or_noncontent_components_rejected(self):
        with self.assertRaises(ValueError):
            fingerprint({name: "0" * 64 for name in COMPONENTS - {"converter"}})
        with self.assertRaises(ValueError):
            fingerprint({name: "some/path" for name in COMPONENTS})


if __name__ == "__main__":
    unittest.main()
