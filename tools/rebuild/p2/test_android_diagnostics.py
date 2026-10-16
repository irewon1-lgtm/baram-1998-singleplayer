"""Synthetic Android command/receipt regression. Never launches adb or an APK."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import work_platform


class AndroidDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.apk = self.root / "synthetic-not-an-apk"
        self.apk.write_bytes(b"synthetic command test; no Android execution")
        self.args = argparse.Namespace(apk=self.apk, apk_sha256=hashlib.sha256(self.apk.read_bytes()).hexdigest(),
                                       output=self.root / "output", android_sdk=self.root / "absent-sdk",
                                       serial="synthetic-only", adb_port=5041, emulator=True, timeout=60, startup_timeout=3)
        self.commands = []
        self.launch_text = "Starting: Intent { cmp=com.irewon.baram.p2work20261016/com.godot.game.GodotAppLauncher }\nStatus: ok\nComplete\n"
        self.process_text = ""
        self.now = 0.0

    def tearDown(self):
        self.temp.cleanup()

    def fake_run_logged(self, cmd, output, env, timeout=300):
        self.commands.append(cmd)
        text, code = "", 0
        if "aapt" in Path(cmd[0]).name:
            text = "package: name='" + work_platform.PACKAGE + "'"
        elif "start" in cmd and "am" in cmd:
            text = self.launch_text
        elif "pidof" in cmd:
            text, code = self.process_text, (0 if self.process_text else 1)
        elif "logcat" in cmd:
            text = "10-16 05:40:43.369 1 1 I ActivityManager: launch com.godot.game.GodotAppLauncher\n"
        output.write_text(text)
        return {"command":cmd, "exit_code":code, "seconds":0, "log":str(output), "log_sha256":work_platform.digest(output)}

    def sleep(self, seconds):
        self.now += seconds

    def execute(self, poll):
        with patch("work_platform.run_logged", self.fake_run_logged), patch("work_platform.subprocess.run", side_effect=poll), \
             patch("work_platform.time.monotonic", side_effect=lambda:self.now), patch("work_platform.time.sleep", side_effect=self.sleep):
            code = work_platform.android_run(self.args)
        return code, json.loads((self.args.output / "RUN_RECEIPT.json").read_text())

    def test_shell_zero_launch_error_stops_without_report_poll(self):
        self.launch_text = "Error type 3\nError: Activity class does not exist\n"
        code, receipt = self.execute(AssertionError("report poll after known launch failure"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "FAIL_LAUNCH")
        self.assertTrue(any("start" in c and "-W" in c for c in self.commands))
        # adb's device selector uses -s before logcat; only a logcat -s tag
        # filter would discard the process/graphics evidence we require.
        self.assertTrue(any("logcat" in c and "all" in c and "-s" not in c[c.index("logcat") + 1:] for c in self.commands))

    def test_process_exit_stops_after_two_failed_polls_and_keeps_stderr(self):
        polls = []
        def poll(*args, **kwargs):
            polls.append(args[0])
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"cat: no report file")
        code, receipt = self.execute(poll)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "FAIL_NO_PACKAGE_PROCESS")
        self.assertEqual(len(polls), 2)
        evidence = json.loads((self.args.output / "REPORT_POLLS.json").read_text())
        self.assertEqual(evidence["polls"][0]["stderr"], "cat: no report file")
        self.assertTrue(any("dumpsys" in c and "activity" in c for c in self.commands))
        self.assertTrue(any("screencap" in c for c in self.commands))

    def test_live_process_without_engine_progress_stops_at_startup_checkpoint(self):
        self.process_text = "445\n"
        code, receipt = self.execute(lambda *a, **k:SimpleNamespace(returncode=1, stdout=b"", stderr=b"no file"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "FAIL_STARTUP_NO_ENGINE_SIGNAL")
        self.assertLess(self.now, self.args.timeout)
        self.assertFalse(receipt["engine_log_signal_seen"])

    def test_poll_timeout_is_recorded_and_final_diagnostics_still_written(self):
        code, receipt = self.execute(subprocess.TimeoutExpired(["synthetic-poll"], 15, output=b"", stderr=b"adb stalled"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["result"], "FAIL_REPORT_POLL_TIMEOUT")
        self.assertTrue((self.args.output / "logcat-final.log").exists())

    def test_engine_progress_requires_current_pid_and_engine_tag(self):
        self.assertTrue(work_platform.android_engine_signal("10-16 05:40:43.369 445 446 I godot: Godot Engine v4.6.3\n", "445"))
        self.assertFalse(work_platform.android_engine_signal("10-16 05:40:43.369 555 446 I godot: old process\n", "445"))
        self.assertFalse(work_platform.android_engine_signal("10-16 05:40:43.369 445 446 I ActivityManager: launch com.godot.game\n", "445"))

    def test_launch_and_pid_parse_fail_closed(self):
        self.assertEqual(work_platform.android_launch_problem(None, ""), "AM_START_FAILED_OR_TIMED_OUT")
        self.assertEqual(work_platform.android_launch_problem(0, ""), "AM_START_EMPTY_RESPONSE")
        self.assertIsNone(work_platform.android_launch_problem(0, "Status: ok\nComplete"))
        self.assertTrue(work_platform.android_process_live(0, "445 446\n"))
        self.assertFalse(work_platform.android_process_live(0, "error: device offline"))


if __name__ == "__main__":
    unittest.main()
