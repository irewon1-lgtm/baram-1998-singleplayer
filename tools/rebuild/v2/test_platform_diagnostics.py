"""Prevent initialization logs/blank screenshots from becoming Android UI PASS.

These are simulated ADB integration tests, not Android or renderer execution.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p2"))
import gameplay_platform as platform


BLANK_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class RunningLogcat:
    def poll(self):
        return 0


class AndroidPresentationGate(unittest.TestCase):
    def run_android_fixture(self, stage, *, live=True, screenshot=True, request_input=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apk = root / "synthetic.apk"
            apk.write_bytes(b"explicit-synthetic-apk-not-installable")
            args = argparse.Namespace(output=root / "evidence", apk=apk,
                apk_sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
                android_sdk=root / "sdk", adb_port=5043, serial="emulator-synthetic",
                reuse_installed=False, startup_timeout=90, smoke=request_input,
                ui_probe=request_input, timeout=180)
            calls = []

            def logged(command, path, env, timeout):
                calls.append(command)
                text = b""
                code = 0
                if "badging" in command:
                    text = ("package: name='" + platform.PACKAGE + "'\n").encode()
                elif "start" in command:
                    text = b"Starting: Intent { cmp=synthetic }\nStatus: ok\n"
                elif "pidof" in command:
                    text, code = (b"1234\n", 0) if live else (b"", 1)
                elif "screencap" in command:
                    text, code = (BLANK_PNG, 0) if screenshot else (b"capture failed", 1)
                Path(path).write_bytes(text)
                return {"exit_code":code, "log":str(path), "command":command}

            def execute(command, **kwargs):
                if "cat" in command:
                    data = (json.dumps({"stage":stage}) + "\n").encode() if stage else b""
                    return subprocess.CompletedProcess(command, 0, data, b"")
                raise AssertionError("Unexpected external execution: " + str(command))

            clock = iter(range(0, 5000, 10))
            with patch.object(platform, "run_logged", side_effect=logged), \
                 patch.object(platform.subprocess, "Popen", return_value=RunningLogcat()), \
                 patch.object(platform.subprocess, "run", side_effect=execute), \
                 patch.object(platform.time, "monotonic", side_effect=lambda: next(clock)), \
                 patch.object(platform.time, "sleep"):
                result = platform.android_gameplay(args)
            receipt = json.loads((args.output / "RUN_RECEIPT.json").read_text())
            return result, receipt, calls

    def test_historical_first_frame_and_blank_png_are_not_visible_ui_pass(self):
        code, receipt, calls = self.run_android_fixture("first_frame")
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "PARTIAL_DEFAULT_PRESENTATION_UNVERIFIED")
        self.assertEqual(receipt["default_mode"], "LOG_ONLY_PROCESS_READY_STAYS_RUNNING")
        self.assertEqual(receipt["presentation"]["status"], "NOT_VERIFIED")
        self.assertTrue(receipt["presentation"]["screenshot_captured"])
        self.assertEqual(receipt["presentation"]["screenshot_sha256"], hashlib.sha256(BLANK_PNG).hexdigest())
        self.assertEqual(receipt["ordinary_input_probe"]["status"], "NOT_RUN")
        self.assertFalse(any("input" in command for command in calls))

    def test_new_process_ready_is_recognized_without_claiming_presentation(self):
        code, receipt, _ = self.run_android_fixture("process_ready")
        self.assertEqual(code, 1)
        self.assertEqual(receipt["default_stages"], ["process_ready"])
        self.assertFalse(receipt["presentation"]["process_checkpoint_is_visible_frame"])
        self.assertEqual(receipt["smoke"], "NOT_RUN")

    def test_failed_screencap_does_not_allow_input_or_boot_pass(self):
        code, receipt, _ = self.run_android_fixture("process_ready", screenshot=False, request_input=False)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "PARTIAL_DEFAULT_PRESENTATION_UNVERIFIED")
        self.assertFalse(receipt["presentation"]["screenshot_captured"])

    def test_dead_process_is_a_failure_even_with_checkpoint(self):
        code, receipt, _ = self.run_android_fixture("first_frame", live=False)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "FAIL_DEFAULT_PROCESS_ABSENT")

    def test_missing_checkpoint_is_not_replaced_by_successful_screencap(self):
        code, receipt, _ = self.run_android_fixture(None)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "FAIL_DEFAULT_PROCESS_READY_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
