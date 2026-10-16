#!/usr/bin/env python3
"""Isolated Work P2 exports and Android execution; no existing app/save/key use.

All package-bearing output belongs in an explicitly selected private work folder.
The checked-out project and historical Codex records are never rewritten here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parents[3]
ENGINE = "4.6.3.stable.official.7d41c59c4"
PACKAGE = "com.irewon.baram.p2work20261016"
USER_DIR = "baram_rebuild_work_p2_001"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink in frozen export input")
        if path.is_file() and ".godot" not in path.relative_to(root).parts:
            result[path.relative_to(root).as_posix()] = digest(path)
    if not result:
        raise ValueError("Empty export input")
    return result


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def empty_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValueError("Output must be a new empty private directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)


def run_logged(cmd: list[str], output: Path, env: dict, timeout: int = 300) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=timeout)
        raw = proc.stdout + proc.stderr
        for key in ("GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD", "BARAM_WORK_KEY_PASSWORD"):
            if env.get(key):
                raw = raw.replace(env[key].encode(), b"[REDACTED]")
        output.write_bytes(raw)
        return {"command": cmd, "exit_code": proc.returncode,
                "seconds": round(time.monotonic() - started, 3),
                "log": str(output), "log_sha256": digest(output)}
    except subprocess.TimeoutExpired as exc:
        raw = (exc.stdout or b"") + (exc.stderr or b"")
        for key in ("GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD", "BARAM_WORK_KEY_PASSWORD"):
            if env.get(key):
                raw = raw.replace(env[key].encode(), b"[REDACTED]")
        output.write_bytes(raw)
        return {"command": cmd, "exit_code": None, "result": "TIMEOUT",
                "seconds": round(time.monotonic() - started, 3),
                "log": str(output), "log_sha256": digest(output)}


def export(args: argparse.Namespace) -> int:
    source = args.project.resolve()
    runtime = args.runtime.resolve()
    if not (runtime / "runtime.json").is_file():
        raise ValueError("Explicit original-runtime generation lacks runtime.json")
    if source in args.output.resolve().parents or args.output.resolve() == source:
        raise ValueError("Output must be outside the checked-out project")
    observed = subprocess.check_output([str(args.godot), "--version"], text=True).strip()
    if observed != ENGINE:
        raise ValueError("Pinned Godot version mismatch")
    project_text = (source / "project.godot").read_text()
    if 'config/custom_user_dir_name="' + USER_DIR + '"' not in project_text:
        raise ValueError("Work-only user data path must be set by the integrator")
    inputs = snapshot(runtime)
    sources = snapshot(source)
    empty_output(args.output)
    copy = args.output / "project"
    shutil.copytree(source, copy, ignore=shutil.ignore_patterns(".godot", "private_runtime"))
    shutil.copytree(runtime, copy / "private_runtime")
    if snapshot(copy / "private_runtime") != inputs:
        raise ValueError("Runtime copy differs from the frozen generation")
    templates = args.templates.resolve()
    for filename in (["windows_debug_x86_64.exe", "windows_release_x86_64.exe"] if args.target == "Windows" else ["android_debug.apk", "android_release.apk"]):
        if not (templates / filename).is_file():
            raise ValueError("Required pinned export template missing: " + filename)
    presets = (copy / "export_presets.cfg").read_text()
    presets = re.sub(r'custom_template/(debug|release)="[^"\n]*/([^/"\n]+)"',
                     lambda m: 'custom_template/' + m[1] + '=' + json.dumps(str(templates / m[2])), presets)
    presets = presets.replace('include_filter=""', 'include_filter="*.json,*.png,*.wav"')
    presets = presets.replace('custom_features="p2_smoke"', 'custom_features="p2_original_smoke"')
    presets = re.sub(r'package/unique_name="[^"\n]+"', 'package/unique_name="' + PACKAGE + '"', presets)
    presets = re.sub(r'package/name="[^"\n]+"', 'package/name="Baram P2 Work Inspection"', presets)
    (copy / "export_presets.cfg").write_text(presets)
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(args.output / "godot-config")
    env["XDG_DATA_HOME"] = str(args.output / "godot-data")
    env.pop("BARAM_P2_RUNTIME", None)
    env.pop("BARAM_P2_REPORT", None)
    env["GODOT_SILENCE_ROOT_WARNING"] = "1"
    if args.target == "Android":
        if not args.android_sdk or not args.java_home:
            raise ValueError("Android export requires explicit SDK and Java locations")
        key_dir = args.output / "private-signing"
        key_dir.mkdir(mode=0o700)
        key = key_dir / "work-inspection.keystore"
        password = secrets.token_hex(24)
        env["BARAM_WORK_KEY_PASSWORD"] = password
        subprocess.run([str(args.java_home / "bin/keytool"), "-genkeypair", "-keystore", str(key),
                        "-storepass:env", "BARAM_WORK_KEY_PASSWORD", "-keypass:env", "BARAM_WORK_KEY_PASSWORD",
                        "-alias", "p2work", "-dname", "CN=Work P2 Isolated Test", "-keyalg", "RSA",
                        "-validity", "3650", "-noprompt"], env=env, capture_output=True, check=True)
        key.chmod(0o600)
        # Secret is retained locally for a repeated build only; never in a report.
        password_file = key_dir / "password"
        password_file.write_text(password)
        password_file.chmod(0o600)
        env["JAVA_HOME"] = str(args.java_home.resolve())
        env["GODOT_ANDROID_KEYSTORE_DEBUG_PATH"] = str(key)
        env["GODOT_ANDROID_KEYSTORE_DEBUG_USER"] = "p2work"
        env["GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD"] = password
        settings = args.output / "godot-config/godot/editor_settings-4.6.tres"
        settings.parent.mkdir(parents=True)
        settings.write_text('[gd_resource type="EditorSettings" format=3]\n\n[resource]\n' +
                            'export/android/java_sdk_path = ' + json.dumps(str(args.java_home.resolve())) + '\n' +
                            'export/android/android_sdk_path = ' + json.dumps(str(args.android_sdk.resolve())) + '\n' +
                            'export/android/shutdown_adb_on_exit = false\n')
    receipt = {"schema": "baram.work.p2.export/1", "target": args.target, "engine": observed,
               "package": PACKAGE if args.target == "Android" else None, "custom_user_dir": USER_DIR,
               "result": "RUNNING", "execution": "NOT_RUN_BY_EXPORTER", "original_assets_included": True,
               "private_distribution_required": True, "signing_key_in_build": False,
               "source_sha256": sources, "runtime_sha256": inputs, "commands": []}
    receipt_path = args.output / "EXPORT_RECEIPT.json"
    dump(receipt_path, receipt)
    imported = run_logged([str(args.godot), "--headless", "--path", str(copy), "--editor", "--import"], args.output / "import.log", env, 600)
    receipt["commands"].append(imported)
    if imported["exit_code"] != 0:
        receipt["result"] = "FAIL_IMPORT"
        dump(receipt_path, receipt)
        return 1
    artifact = args.output / ("baram-p2-work-inspection" + (".exe" if args.target == "Windows" else ".apk"))
    exported = run_logged([str(args.godot), "--headless", "--path", str(copy), "--export-debug", "P2 " + args.target, str(artifact)], args.output / "export.log", env, 600)
    receipt["commands"].append(exported)
    receipt["sources_unchanged"] = sources == snapshot(source)
    receipt["runtime_unchanged"] = inputs == snapshot(runtime)
    receipt["result"] = "PASS_EXPORT_ONLY" if exported["exit_code"] == 0 and artifact.is_file() and receipt["sources_unchanged"] and receipt["runtime_unchanged"] else "FAIL"
    if artifact.is_file():
        receipt["artifact"] = {"path": str(artifact), "bytes": artifact.stat().st_size, "sha256": digest(artifact)}
    dump(receipt_path, receipt)
    print(json.dumps({"result": receipt["result"], "receipt": str(receipt_path), "artifact": receipt.get("artifact")}))
    return 0 if receipt["result"] == "PASS_EXPORT_ONLY" else 1


def android_run(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9a-f]{64}", args.apk_sha256) or digest(args.apk) != args.apk_sha256:
        raise ValueError("Exact APK SHA256 pin required")
    empty_output(args.output)
    adb = args.android_sdk / "platform-tools/adb"
    tools = args.android_sdk / "build-tools/35.0.1"
    env = os.environ.copy()
    commands = []
    receipt = {"schema": "baram.work.p2.android_run/1", "package": PACKAGE,
               "apk_sha256": args.apk_sha256, "result": "RUNNING", "commands": commands,
               "platform": "ANDROID_EMULATOR" if args.emulator else "ANDROID_EXPLICIT_DEVICE",
               "Galaxy": "NOT_RUN", "actual_IME": "NOT_RUN", "physical_audio_listening": "NOT_RUN"}
    def save() -> None:
        dump(args.output / "RUN_RECEIPT.json", receipt)
    def run(command: list[str], name: str, timeout: int = 60) -> dict:
        value = run_logged(command, args.output / (name + ".log"), env, timeout)
        commands.append(value)
        save()
        return value
    def snapshot_state(label: str, screenshot: bool = False) -> None:
        # The result remains private. Do not filter away ActivityManager, native
        # loader, graphics, ANR or low-memory-killer evidence as GEN003 did.
        run(base + ["logcat", "-d", "-b", "all", "-v", "threadtime", "-t", "12000"], "logcat-" + label, 20)
        run(base + ["shell", "dumpsys", "activity", "activities"], "activity-" + label, 20)
        run(base + ["shell", "dumpsys", "window", "windows"], "window-" + label, 20)
        run(base + ["shell", "run-as", PACKAGE, "pwd"], "userdata-root-" + label, 20)
        run(base + ["shell", "run-as", PACKAGE, "find", "files", "-maxdepth", "3", "-type", "f"], "isolated-files-" + label, 20)
        if screenshot:
            entry = run(base + ["exec-out", "screencap", "-p"], "screen-" + label, 20)
            path = Path(entry["log"])
            if entry["exit_code"] == 0 and path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                png = args.output / ("screen-" + label + ".png")
                path.rename(png)
                entry["log"] = str(png)
                receipt.setdefault("diagnostic_screenshots", []).append({"path": str(png), "sha256": digest(png),
                    "scope": "Device screen at diagnostic checkpoint; Godot first-frame correctness NOT_ASSESSED"})
                save()
    save()
    badge = run([str(tools / "aapt"), "dump", "badging", str(args.apk)], "package")
    if badge["exit_code"] or ("package: name='" + PACKAGE + "'") not in Path(badge["log"]).read_text():
        raise ValueError("APK package identity differs; install refused")
    if run([str(tools / "apksigner"), "verify", str(args.apk)], "signature")["exit_code"]:
        raise ValueError("APK signature invalid; install refused")
    base = [str(adb), "-P", str(args.adb_port), "-s", args.serial]
    for prop in ("ro.build.version.release", "ro.build.version.sdk", "ro.product.cpu.abi", "ro.kernel.qemu"):
        run(base + ["shell", "getprop", prop], "device-" + prop)
    installed = run(base + ["install", "-r", "--no-incremental", "--no-streaming", str(args.apk)], "install", 300)
    if installed["exit_code"]:
        receipt["result"] = "FAIL_INSTALL"
        save()
        return 1
    # The app is the new Work-only package, with its own synthetic test state.
    run(base + ["shell", "am", "force-stop", PACKAGE], "force-stop")
    run(base + ["shell", "run-as", PACKAGE, "rm", "-f", "files/work-original-smoke.json"], "remove-stale-report")
    snapshot_state("before-launch")
    launch = run(base + ["shell", "am", "start", "-W", "-n", PACKAGE + "/com.godot.game.GodotAppLauncher"], "launch", 90)
    launch_text = Path(launch["log"]).read_text(errors="replace")
    launch_problem = android_launch_problem(launch["exit_code"], launch_text)
    if launch_problem:
        receipt["result"] = "FAIL_LAUNCH"
        receipt["failure_reason"] = launch_problem
        snapshot_state("launch-failure", screenshot=True)
        save()
        return 1
    receipt["launch_wait_status"] = "AM_START_WAIT_RETURNED_WITHOUT_REPORTED_ERROR"
    deadline = time.monotonic() + args.timeout
    startup_deadline = time.monotonic() + args.startup_timeout
    report = None
    poll_receipts = []
    receipt["report_poll_evidence"] = "REPORT_POLLS.json"
    missing_process_polls = 0
    package_process_seen = False
    next_checkpoint = time.monotonic()
    first_engine_signal = False
    while time.monotonic() < deadline:
        try:
            attempt = subprocess.run(base + ["exec-out", "run-as", PACKAGE, "cat", "files/work-original-smoke.json"], capture_output=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            poll_receipts.append({"poll": len(poll_receipts), "returncode": None, "result": "TIMEOUT",
                                  "stdout_bytes": len(exc.stdout or b""), "stderr": (exc.stderr or b"").decode(errors="replace")[:4096]})
            dump(args.output / "REPORT_POLLS.json", {"schema": "baram.work.p2.android-report-polls/1", "polls": poll_receipts})
            receipt["result"] = "FAIL_REPORT_POLL_TIMEOUT"
            receipt["failure_reason"] = "ADB report poll timed out; inspect final process/activity/device diagnostics before retry."
            break
        poll_receipts.append({"poll": len(poll_receipts), "returncode": attempt.returncode,
                              "stdout_bytes": len(attempt.stdout), "stderr": attempt.stderr.decode(errors="replace")[:4096]})
        dump(args.output / "REPORT_POLLS.json", {"schema": "baram.work.p2.android-report-polls/1", "polls": poll_receipts})
        try:
            parsed = json.loads(attempt.stdout)
            if isinstance(parsed, dict) and parsed.get("schema"):
                report = parsed
                (args.output / "work-original-smoke.json").write_bytes(attempt.stdout)
                break
        except (ValueError, UnicodeError):
            pass
        process = run(base + ["shell", "pidof", PACKAGE], "process-%03d" % len(poll_receipts), 15)
        process_text = Path(process["log"]).read_text(errors="replace")
        if android_process_live(process["exit_code"], process_text):
            missing_process_polls = 0
            package_process_seen = True
        else:
            missing_process_polls += 1
        if missing_process_polls >= 2:
            receipt["result"] = "FAIL_PROCESS_EXIT_NO_REPORT" if package_process_seen else "FAIL_NO_PACKAGE_PROCESS"
            receipt["failure_reason"] = "No package PID on two consecutive report polls; no app result was received."
            break
        if time.monotonic() >= next_checkpoint:
            label = "checkpoint-%03d" % len(poll_receipts)
            snapshot_state(label, screenshot=True)
            text = (args.output / ("logcat-" + label + ".log")).read_text(errors="replace")
            # This is only a startup progress signal, not a render/test PASS.
            first_engine_signal = first_engine_signal or android_engine_signal(text, process_text)
            receipt["engine_log_signal_seen"] = first_engine_signal
            next_checkpoint = time.monotonic() + 20
        if not first_engine_signal and time.monotonic() >= startup_deadline:
            receipt["result"] = "FAIL_STARTUP_NO_ENGINE_SIGNAL"
            receipt["failure_reason"] = "Package process exists but no Godot startup log/report was observed within the diagnostic startup limit; inspect full logs/screens before retry."
            break
        time.sleep(2)
    snapshot_state("final", screenshot=report is None)
    if report is None:
        if receipt["result"] == "RUNNING":
            receipt["result"] = "FAIL_NO_REPORT_WITH_DIAGNOSTICS"
    else:
        receipt["app_report_sha256"] = digest(args.output / "work-original-smoke.json")
        receipt["app_result"] = report.get("result", "UNKNOWN")
        checks = report.get("checks", [])
        receipt["checks"] = len(checks)
        receipt["failures"] = sum(not (item.get("pass", False) or item.get("status") == "PASS") for item in checks)
        receipt["result"] = "REPORT_RECEIVED_REVIEW_REQUIRED"
        listing = subprocess.run(base + ["shell", "run-as", PACKAGE, "find", "files", "-maxdepth", "1", "-type", "f"], capture_output=True, text=True, timeout=20)
        captures = []
        for filename in listing.stdout.splitlines():
            name = Path(filename).name
            if not re.fullmatch(r"work-original-smoke\.json[-A-Za-z0-9_.]*\.(?:png|wav)", name):
                continue
            value = subprocess.run(base + ["exec-out", "run-as", PACKAGE, "cat", filename], capture_output=True, timeout=30)
            if value.returncode == 0:
                path = args.output / name
                path.write_bytes(value.stdout)
                captures.append({"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)})
        receipt["captures"] = captures
    save()
    print(json.dumps({"result": receipt["result"], "receipt": str(args.output / "RUN_RECEIPT.json")}))
    return 0 if report is not None else 1


def android_launch_problem(exit_code: int | None, text: str) -> str | None:
    """am can return shell0 while reporting a launch error; never call that PASS."""
    if exit_code != 0:
        return "AM_START_FAILED_OR_TIMED_OUT"
    if re.search(r"(?im)^\s*(?:error(?:\s+type\s+\d+)?\s*:|exception\b|status:\s*(?:timeout|error)|.*(?:permission denial|activity class .* does not exist))", text):
        return "AM_START_REPORTED_ERROR"
    if not text.strip():
        return "AM_START_EMPTY_RESPONSE"
    return None


def android_process_live(exit_code: int | None, text: str) -> bool:
    return exit_code == 0 and bool(re.fullmatch(r"\s*\d+(?:\s+\d+)*\s*", text))


def android_engine_signal(logcat: str, process_text: str) -> bool:
    """Require the current package PID and an engine tag/banner, not launcher text."""
    pids = set(process_text.split())
    for line in logcat.splitlines():
        parsed = re.match(r"^\S+\s+\S+\s+(\d+)\s+\d+\s+[VDIWEF]\s+([^:]+):\s*(.*)$", line)
        if parsed and parsed[1] in pids and (parsed[2].strip().lower() == "godot" or parsed[3].startswith("Godot Engine")):
            return True
    return False


def linux_run(args: argparse.Namespace) -> int:
    """Keep TCP-only X/audio servers and Godot within the same execution session."""
    empty_output(args.output)
    sources = snapshot(args.project)
    inputs = snapshot(args.runtime)
    system = args.system_root.resolve()
    modules = system / "usr/lib/pulse-16.1+dfsg1/modules"
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ":".join(str(path) for path in (
        system / "usr/lib/x86_64-linux-gnu", system / "usr/lib/x86_64-linux-gnu/pulseaudio", modules))
    env["PATH"] = str(system / "usr/bin") + os.pathsep + env["PATH"]
    env["DISPLAY"] = "127.0.0.1:" + str(args.display_number)
    env["PULSE_SERVER"] = "tcp:127.0.0.1:" + str(args.pulse_port)
    env["XAUTHORITY"] = str(args.output / "x11.auth")
    env["PULSE_RUNTIME_PATH"] = str(args.output / "pulse-runtime")
    env["PULSE_STATE_PATH"] = str(args.output / "pulse-state")
    env["PULSE_CONFIG_PATH"] = str(args.output)
    env["BARAM_P2_RUNTIME"] = str(args.runtime.resolve())
    env["BARAM_P2_REPORT"] = str(args.output.resolve() / "work-original-smoke.json")
    env["GODOT_SILENCE_ROOT_WARNING"] = "1"
    Path(env["PULSE_RUNTIME_PATH"]).mkdir(mode=0o700)
    subprocess.run([str(system / "usr/bin/xauth"), "-f", env["XAUTHORITY"], "add", env["DISPLAY"],
                    "MIT-MAGIC-COOKIE-1", secrets.token_hex(16)], env=env, capture_output=True, check=True)
    Path(env["XAUTHORITY"]).chmod(0o600)
    conf = args.output / "pulse.conf"
    conf.write_text("load-module module-native-protocol-tcp listen=127.0.0.1 port=" + str(args.pulse_port) + " auth-anonymous=1\n"
                    "load-module module-null-sink sink_name=p2_capture rate=48000 channels=2\nset-default-sink p2_capture\n")
    processes = []
    receipt = {"schema": "baram.work.p2.linux_run/1", "platform": "Linux", "result": "RUNNING",
               "virtual_display": "Xvfb TCP loopback/client-auth", "audio_output": "PulseAudio virtual sink",
               "physical_audio_listening": "NOT_RUN", "IME": "NOT_RUN", "original_accuracy": "NOT_ESTABLISHED_BY_RUNNER",
               "source_sha256": sources, "runtime_sha256": inputs}
    try:
        for name, command in [
            ("xvfb", [str(system / "usr/bin/Xvfb"), ":" + str(args.display_number), "-screen", "0", "1280x800x24", "-nolisten", "unix", "-nolisten", "local", "-listen", "tcp", "-auth", env["XAUTHORITY"]]),
            ("pulse", [str(system / "usr/bin/pulseaudio"), "--daemonize=no", "--exit-idle-time=-1", "--use-pid-file=no", "--disable-shm=yes", "--disallow-exit=yes", "--dl-search-path=" + str(modules), "-n", "-F", str(conf)])]:
            log = (args.output / (name + ".log")).open("wb")
            processes.append(subprocess.Popen(command, env=env, stdout=log, stderr=log))
        time.sleep(2)
        receipt["display_probe"] = run_logged([str(system / "usr/bin/xdpyinfo")], args.output / "display.log", env, 20)
        receipt["audio_probe"] = run_logged([str(system / "usr/bin/pactl"), "info"], args.output / "audio-server.log", env, 20)
        if receipt["display_probe"]["exit_code"] != 0 or receipt["audio_probe"]["exit_code"] != 0:
            receipt["result"] = "FAIL_VIRTUAL_DEVICE_INITIALIZATION"
        else:
            if args.record_video:
                video = args.output / "original-runtime.mp4"
                video_command = ["ffmpeg", "-nostdin", "-y", "-f", "x11grab", "-video_size", "1100x720", "-framerate", "12",
                                 "-i", env["DISPLAY"] + ".0", "-f", "pulse", "-i", "p2_capture.monitor",
                                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                                 "-c:a", "aac", "-b:a", "128k", str(video)]
                log = (args.output / "video-capture.log").open("wb")
                processes.append(subprocess.Popen(video_command, env=env, stdout=log, stderr=log))
                receipt["video_command"] = video_command
                time.sleep(0.5)
            command = [str(args.godot), "--path", str(args.project), "--rendering-method", "gl_compatibility", "--", "--p2-original-smoke"]
            receipt["application"] = run_logged(command, args.output / "application.log", env, args.timeout)
            receipt["result"] = "APPLICATION_EXIT_" + str(receipt["application"]["exit_code"])
            path = Path(env["BARAM_P2_REPORT"])
            if path.is_file():
                receipt["app_report_sha256"] = digest(path)
        dump(args.output / "RUN_RECEIPT.json", receipt)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    receipt["sources_unchanged"] = sources == snapshot(args.project)
    receipt["runtime_unchanged"] = inputs == snapshot(args.runtime)
    if not receipt["sources_unchanged"] or not receipt["runtime_unchanged"]:
        receipt["result"] = "FAIL_INPUT_CHANGED_DURING_RUN"
    video = args.output / "original-runtime.mp4"
    if video.is_file():
        receipt["video"] = {"path": str(video), "bytes": video.stat().st_size, "sha256": digest(video),
                            "scope": "Actual Xvfb GUI and Pulse virtual-output capture; no hardware listening"}
    dump(args.output / "RUN_RECEIPT.json", receipt)
    print(json.dumps({"result": receipt["result"], "receipt": str(args.output / "RUN_RECEIPT.json")}))
    return 0 if receipt.get("application", {}).get("exit_code") == 0 and receipt["sources_unchanged"] and receipt["runtime_unchanged"] else 1


def native_run(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise ValueError("native-run requires actual Windows; Wine/Linux refused")
    if digest(args.exe) != args.exe_sha256:
        raise ValueError("Exact EXE SHA256 pin required")
    empty_output(args.output)
    env = os.environ.copy()
    env["BARAM_P2_REPORT"] = str(args.output.resolve() / "work-original-smoke.json")
    env.pop("BARAM_P2_RUNTIME", None)
    env["GODOT_SILENCE_ROOT_WARNING"] = "1"
    receipt = {"schema": "baram.work.p2.windows_native/1", "platform": "Windows native",
               "exe_sha256": args.exe_sha256, "result": "RUNNING", "IME": "NOT_RUN",
               "physical_audio_listening": "NOT_RUN", "historical_wine_failure": "PRESERVED docs/rebuild/p2/WINE_STORAGE_DIAGNOSIS.json",
               "commands": []}
    for name, options in [("windowed", []), ("headless", ["--headless"])]:
        report = args.output.resolve() / (name + "-original-smoke.json")
        env["BARAM_P2_REPORT"] = str(report)
        command = [str(args.exe.resolve()), *options, "--", "--p2-original-smoke"]
        entry = run_logged(command, args.output / (name + ".log"), env, args.timeout)
        receipt["commands"].append(entry)
        if report.is_file():
            entry["report_sha256"] = digest(report)
            parsed = json.loads(report.read_text())
            entry["app_result"] = parsed.get("result", "UNKNOWN")
            entry["checks"] = len(parsed.get("checks", []))
            entry["failures"] = sum(not (item.get("pass", False) or item.get("status") == "PASS") for item in parsed.get("checks", []))
            entry["save_tests"] = {key: parsed.get("save_tests", {}).get(key) for key in ("checks", "failures")}
        dump(args.output / "RUN_RECEIPT.json", receipt)
        # Headless retry only supplies native OS/storage evidence when renderer fails.
        if entry["exit_code"] == 0 and report.is_file():
            receipt["result"] = "PASS_NATIVE_APPLICATION" if name == "windowed" else "PASS_NATIVE_HEADLESS_ONLY"
            break
    if receipt["result"] == "RUNNING":
        receipt["result"] = "FAIL"
    dump(args.output / "RUN_RECEIPT.json", receipt)
    print(json.dumps({"result": receipt["result"], "receipt": str(args.output / "RUN_RECEIPT.json")}))
    return 0 if receipt["result"].startswith("PASS_") else 1


def seal(args: argparse.Namespace) -> int:
    """Encrypt all original-bearing binary evidence to a new session public key."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    import io
    public = serialization.load_pem_public_key(args.public_key.read_bytes())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(args.source).as_posix())
    key = AESGCM.generate_key(bit_length=256)
    nonce = secrets.token_bytes(12)
    associated = b"BARAM_REBUILD_WORK_P2_TAKEOVER_001/native-evidence-v1"
    encrypted = AESGCM(key).encrypt(nonce, buffer.getvalue(), associated)
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=associated))
    header = {"schema": "baram.work.p2.sealed/1", "algorithm": "RSA-OAEP-SHA256/AES256-GCM",
              "public_key_sha256": digest(args.public_key), "wrapped_key": base64.b64encode(wrapped).decode(),
              "nonce": base64.b64encode(nonce).decode(), "associated_data": associated.decode()}
    args.output.write_bytes(json.dumps(header).encode() + b"\n" + encrypted)
    print(json.dumps({"encrypted_file": str(args.output), "bytes": args.output.stat().st_size, "sha256": digest(args.output)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--project", type=Path, default=ROOT / "rebuild/p2")
    exp.add_argument("--godot", type=Path, required=True)
    exp.add_argument("--templates", type=Path, required=True)
    exp.add_argument("--runtime", type=Path, required=True)
    exp.add_argument("--target", choices=["Windows", "Android"], required=True)
    exp.add_argument("--output", type=Path, required=True)
    exp.add_argument("--android-sdk", type=Path)
    exp.add_argument("--java-home", type=Path)
    android = sub.add_parser("android-run")
    android.add_argument("--android-sdk", type=Path, required=True)
    android.add_argument("--apk", type=Path, required=True)
    android.add_argument("--apk-sha256", required=True)
    android.add_argument("--serial", required=True)
    android.add_argument("--adb-port", type=int, default=5041)
    android.add_argument("--emulator", action="store_true")
    android.add_argument("--output", type=Path, required=True)
    android.add_argument("--timeout", type=int, default=120)
    android.add_argument("--startup-timeout", type=int, default=45)
    linux = sub.add_parser("linux-run")
    linux.add_argument("--project", type=Path, default=ROOT / "rebuild/p2")
    linux.add_argument("--godot", type=Path, required=True)
    linux.add_argument("--runtime", type=Path, required=True)
    linux.add_argument("--system-root", type=Path, required=True)
    linux.add_argument("--output", type=Path, required=True)
    linux.add_argument("--display-number", type=int, default=195)
    linux.add_argument("--pulse-port", type=int, default=4718)
    linux.add_argument("--timeout", type=int, default=600)
    linux.add_argument("--record-video", action="store_true")
    native = sub.add_parser("native-run")
    native.add_argument("--exe", type=Path, required=True)
    native.add_argument("--exe-sha256", required=True)
    native.add_argument("--output", type=Path, required=True)
    native.add_argument("--timeout", type=int, default=600)
    sealing = sub.add_parser("seal")
    sealing.add_argument("--source", type=Path, required=True)
    sealing.add_argument("--public-key", type=Path, required=True)
    sealing.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return {"export": export, "android-run": android_run, "linux-run": linux_run,
            "native-run": native_run, "seal": seal}[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())
