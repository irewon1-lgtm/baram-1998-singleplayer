#!/usr/bin/env python3
"""Private, free local P3 exports and explicit smoke execution.

Normal artifacts start in play mode. Smoke is a command-line opt-in using the
same code/assets, new package, new user data directory and synthetic signing key.
This module never edits P2 exports, production settings, keys or user saves.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET

from work_platform import (ENGINE, android_engine_signal, android_launch_problem,
                           android_process_live, digest, dump, empty_output,
                           run_logged, snapshot)

PACKAGE = "com.irewon.baram.gameplay20261016"
USER_DIR = "baram_rebuild_gameplay_001"
REPORT = "gameplay-smoke.json"
CHECKPOINTS = "gameplay-checkpoints.jsonl"


def presets(templates: Path) -> str:
    quoted = lambda name: json.dumps(str(templates / name))
    return f'''[preset.0]
name="Gameplay Windows"
platform="Windows Desktop"
runnable=true
custom_features=""
export_filter="all_resources"
include_filter="*.json,*.jsonl,*.png,*.wav"
exclude_filter="README.md,*.ttf,*.otf,*.woff,*.woff2"
script_export_mode=2

[preset.0.options]
custom_template/debug={quoted("windows_debug_x86_64.exe")}
custom_template/release={quoted("windows_release_x86_64.exe")}
binary_format/architecture="x86_64"
binary_format/embed_pck=true
codesign/enable=false
application/modify_resources=false

[preset.1]
name="Gameplay Android"
platform="Android"
runnable=true
custom_features=""
export_filter="all_resources"
include_filter="*.json,*.jsonl,*.png,*.wav"
exclude_filter="README.md,*.ttf,*.otf,*.woff,*.woff2"
script_export_mode=2

[preset.1.options]
custom_template/debug={quoted("android_debug.apk")}
custom_template/release={quoted("android_release.apk")}
gradle_build/use_gradle_build=false
architectures/armeabi-v7a=false
architectures/arm64-v8a=true
architectures/x86=false
architectures/x86_64=true
package/unique_name="{PACKAGE}"
package/name="바람의나라 P3"
package/signed=true
version/code=1
version/name="0.1.0-p3"
screen/immersive_mode=false
screen/orientation=0
permissions/internet=false
'''


def stage_project(project: Path, runtime: Path, stage: Path, templates: Path) -> dict:
    if stage.exists():
        raise ValueError("Staging must use a new private path")
    if not (runtime / "runtime.json").is_file():
        raise ValueError("Explicit gameplay runtime.json required")
    for path in runtime.rglob("*"):
        if path.is_symlink():
            raise ValueError("No symlink in frozen gameplay runtime")
        if path.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2", ".keystore", ".jks", ".pem", ".sql"}:
            raise ValueError("Forbidden font/key/database input in runtime: " + path.name)
    shutil.copytree(project, stage, ignore=shutil.ignore_patterns(".godot", "private_runtime", ".git"))
    shutil.copytree(runtime, stage / "private_runtime")
    text = (stage / "project.godot").read_text()
    if "config/use_custom_user_dir=true" not in text:
        raise ValueError("Gameplay source must explicitly select a custom user directory")
    text, count = re.subn(r'config/custom_user_dir_name="[^"\n]+"', f'config/custom_user_dir_name="{USER_DIR}"', text)
    if count != 1:
        raise ValueError("Exactly one isolated gameplay user data setting required")
    (stage / "project.godot").write_text(text)
    (stage / "export_presets.cfg").write_text(presets(templates))
    if snapshot(runtime) != snapshot(stage / "private_runtime"):
        raise ValueError("Staged runtime bytes changed")
    return {"package": PACKAGE, "custom_user_dir": USER_DIR,
            "runtime_location": "res://private_runtime", "default_mode": "PLAY_CONFIGURED_NOT_YET_EXECUTED",
            "smoke": "Explicit --gameplay-smoke only; no automatic-smoke export feature"}


def export_gameplay(args: argparse.Namespace) -> int:
    args.output = args.output.resolve()
    project, runtime = args.project.resolve(), args.runtime.resolve()
    if project in args.output.resolve().parents or args.output.resolve() == project:
        raise ValueError("Private output must be outside the source project")
    version = subprocess.check_output([str(args.godot), "--version"], text=True).strip()
    if version != ENGINE:
        raise ValueError("Pinned Godot4.6.3 required")
    for name in (["windows_debug_x86_64.exe", "windows_release_x86_64.exe"] if args.target == "Windows"
                 else ["android_debug.apk", "android_release.apk"]):
        if not (args.templates / name).is_file():
            raise ValueError("Missing pinned template: " + name)
    source_before, runtime_before = snapshot(project), snapshot(runtime)
    empty_output(args.output)
    options = stage_project(project, runtime, args.output / "project", args.templates.resolve())
    env = os.environ.copy()
    for name in ("BARAM_P2_RUNTIME", "BARAM_P2_REPORT", "BARAM_GAMEPLAY_RUNTIME", "BARAM_GAMEPLAY_REPORT"):
        env.pop(name, None)
    env.update(XDG_CONFIG_HOME=str(args.output / "godot-config"), XDG_DATA_HOME=str(args.output / "godot-data"),
               GODOT_SILENCE_ROOT_WARNING="1")
    if args.target == "Android":
        if args.android_sdk is None or args.java_home is None:
            raise ValueError("Explicit AndroidSDK and Java locations required")
        sdk, java = args.android_sdk.resolve(), args.java_home.resolve()
        for path in [sdk / "platform-tools/adb", sdk / "build-tools/35.0.1/apksigner", java / "bin/keytool"]:
            if not path.is_file():
                raise ValueError("Missing Android export dependency: " + str(path))
        signing = args.signing_root.resolve() if args.signing_root else args.output / "private-signing"
        key = signing / "new-gameplay-test.keystore"
        if signing.exists():
            marker = signing / "SYNTHETIC_KEY.json"
            if not marker.is_file() or json.loads(marker.read_text()).get("owner") != "BARAM_REBUILD_WORK_P3_PLAYABLE_001" or not key.is_file() or not (signing / "password").is_file():
                raise ValueError("Refuse any key not created for this isolated P3 task")
            password = (signing / "password").read_text()
        else:
            signing.mkdir(parents=True, mode=0o700)
            password = secrets.token_hex(24)
            env["BARAM_GAMEPLAY_KEY_PASSWORD"] = password
            keytool = subprocess.run([str(java / "bin/keytool"), "-genkeypair", "-keystore", str(key),
                "-storepass:env", "BARAM_GAMEPLAY_KEY_PASSWORD", "-keypass:env", "BARAM_GAMEPLAY_KEY_PASSWORD",
                "-alias", "gameplay", "-dname", "CN=Isolated P3 Synthetic Test", "-keyalg", "RSA", "-validity", "3650", "-noprompt"],
                env=env, capture_output=True, timeout=60)
            if keytool.returncode:
                raise ValueError("Synthetic signing key generation failed")
            key.chmod(0o600)
            (signing / "password").write_text(password)
            (signing / "password").chmod(0o600)
            dump(signing / "SYNTHETIC_KEY.json", {"schema":"baram.gameplay.synthetic-key/1", "owner":"BARAM_REBUILD_WORK_P3_PLAYABLE_001",
                "existing_game_key":False, "private_key_never_in_artifact":True})
        env.update(JAVA_HOME=str(java), GODOT_ANDROID_KEYSTORE_DEBUG_PATH=str(key),
                   GODOT_ANDROID_KEYSTORE_DEBUG_USER="gameplay", GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD=password)
        settings = args.output / "godot-config/godot/editor_settings-4.6.tres"
        settings.parent.mkdir(parents=True)
        settings.write_text('[gd_resource type="EditorSettings" format=3]\n\n[resource]\n' +
            'export/android/java_sdk_path = ' + json.dumps(str(java)) + '\n' +
            'export/android/android_sdk_path = ' + json.dumps(str(sdk)) + '\n' +
            'export/android/shutdown_adb_on_exit = false\n')
    receipt = {"schema": "baram.gameplay.export/1", "engine": version, "target": args.target,
        "source_snapshot": source_before, "runtime_snapshot": runtime_before, "staged_options": options,
        "result": "RUNNING", "application_execution": "NOT_RUN_BY_EXPORTER", "private_only": True,
        "existing_keys_saves_apps_used": False, "new_cost": 0, "commands": []}
    git_head = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
    receipt["git_head_at_export"] = git_head.stdout.strip() if git_head.returncode == 0 else None
    receipt["runtime_manifest_sha256"] = digest(runtime / "runtime.json")
    receipt["runtime_generation"] = json.loads((runtime / "runtime.json").read_text()).get("generation")
    if (runtime / "gameplay_content.json").is_file():
        receipt["gameplay_content_sha256"] = digest(runtime / "gameplay_content.json")
    report = args.output / "EXPORT_RECEIPT.json"
    dump(report, receipt)
    copy = args.output / "project"
    imported = run_logged([str(args.godot), "--headless", "--path", str(copy), "--editor", "--import"], args.output / "import.log", env, 180)
    receipt["commands"].append(imported)
    if imported["exit_code"] != 0:
        receipt["result"] = "FAIL_IMPORT"
        dump(report, receipt)
        return 1
    binary = args.output / ("baram-p3-playable.exe" if args.target == "Windows" else "baram-p3-playable.apk")
    command = [str(args.godot), "--headless", "--path", str(copy), "--export-debug", "Gameplay " + args.target, str(binary)]
    exported = run_logged(command, args.output / "export.log", env, 240)
    receipt["commands"].append(exported)
    receipt["sources_unchanged"] = source_before == snapshot(project)
    receipt["runtime_unchanged"] = runtime_before == snapshot(runtime)
    receipt["result"] = "PASS_EXPORT_ONLY" if exported["exit_code"] == 0 and binary.is_file() and receipt["sources_unchanged"] and receipt["runtime_unchanged"] else "FAIL_EXPORT"
    if binary.is_file():
        receipt["artifact"] = {"path": str(binary), "bytes": binary.stat().st_size, "sha256": digest(binary)}
        if args.target == "Android":
            verified = run_logged([str(args.android_sdk.resolve() / "build-tools/35.0.1/apksigner"), "verify", str(binary)], args.output / "signature.log", env, 30)
            receipt["commands"].append(verified)
            if verified["exit_code"] != 0:
                receipt["result"] = "FAIL_SIGNATURE"
        else:
            archive = args.output / "baram-p3-playable-Windows.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
                zipped.write(binary, "baram-p3-playable.exe")
                zipped.writestr("START.txt", "새 폴더에 전체 압축을 풀고 baram-p3-playable.exe를 실행하세요.\n기존 게임·세이브와 분리된 P3 시험본입니다.\n자동 시험은 --gameplay-smoke 옵션이며 일반 실행은 플레이 모드입니다.\n")
            receipt["windows_zip"] = {"path": str(archive), "bytes": archive.stat().st_size, "sha256": digest(archive)}
    dump(report, receipt)
    print(json.dumps({k: receipt.get(k) for k in ("result", "artifact", "windows_zip", "application_execution")}, ensure_ascii=False))
    return 0 if receipt["result"] == "PASS_EXPORT_ONLY" else 1


def checkpoint_names(raw: bytes) -> list[str]:
    names = []
    for line in raw.decode(errors="replace").splitlines():
        try:
            value = json.loads(line.removeprefix("GAMEPLAY_STAGE "))
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("stage"), str):
            names.append(value["stage"])
    return names


def android_gameplay(args: argparse.Namespace) -> int:
    args.output = args.output.resolve()
    """Observe normal launch, then explicit debug-only one-shot smoke in same APK."""
    if digest(args.apk) != args.apk_sha256 or not re.fullmatch(r"[0-9a-f]{64}", args.apk_sha256):
        raise ValueError("Exact final APK SHA256 required")
    empty_output(args.output)
    sdk = args.android_sdk.resolve()
    base = [str(sdk / "platform-tools/adb"), "-P", str(args.adb_port), "-s", args.serial]
    env = os.environ.copy()
    commands = []
    receipt = {"schema": "baram.gameplay.android-run/1", "package": PACKAGE, "apk_sha256": args.apk_sha256,
        "result": "RUNNING", "platform": "ANDROID_EMULATOR" if args.serial.startswith("emulator-") else "ANDROID_EXPLICIT_DEVICE",
        "default_mode": "NOT_RUN", "smoke": "NOT_RUN", "actual_IME": "NOT_RUN", "real_Galaxy": "NOT_RUN",
        "hardware_listening": "NOT_RUN", "authentication_roundtrip": "NOT_RUN", "commands": commands,
        "historical_GEN003": "FAIL_NO_REPORT_PRESERVED", "new_cost": 0}
    report_path = args.output / "RUN_RECEIPT.json"
    def save(): dump(report_path, receipt)
    def run(command, name, timeout=20):
        entry = run_logged(command, args.output / (name + ".log"), env, timeout)
        commands.append(entry)
        save()
        return entry
    def capture(label):
        run(base + ["shell", "pidof", PACKAGE], "pid-" + label)
        run(base + ["shell", "dumpsys", "activity", "activities"], "activity-" + label)
        run(base + ["shell", "dumpsys", "window", "windows"], "window-" + label)
        run(base + ["shell", "run-as", PACKAGE, "find", "files", "-maxdepth", "4", "-type", "f"], "files-" + label)
        screen = run(base + ["exec-out", "screencap", "-p"], "screen-" + label, 30)
        path = Path(screen["log"])
        if screen["exit_code"] == 0 and path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            png = args.output / ("screen-" + label + ".png")
            path.rename(png)
            screen["log"] = str(png)
            save()
    def handle_observed_systemui_dialog():
        window = args.output / "window-default-first-frame.log"
        if not window.is_file() or "Application Not Responding: com.android.systemui" not in window.read_text(errors="replace"):
            return
        receipt["environment_dialog"] = "OBSERVED_SYSTEM_UI_ANR_NOT_GAMEPLAY_APP_ANR"
        # Choose the ordinary visible Wait button of this specific emulator
        # dialog. Never disable ANR/security settings or suppress app failures.
        run(base + ["shell", "uiautomator", "dump", "/data/local/tmp/gameplay-system-dialog.xml"], "systemui-dialog-dump", 30)
        ui = run(base + ["exec-out", "cat", "/data/local/tmp/gameplay-system-dialog.xml"], "systemui-dialog-xml", 20)
        try: xml = ET.fromstring(Path(ui["log"]).read_text(errors="replace"))
        except ET.ParseError: xml = None
        if xml is not None:
            texts = [node.attrib.get("text", "") for node in xml.iter("node")]
            if any("System UI isn't responding" in text for text in texts):
                for node in xml.iter("node"):
                    bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
                    if node.attrib.get("text") == "Wait" and bounds:
                        x = (int(bounds[1]) + int(bounds[3])) // 2
                        y = (int(bounds[2]) + int(bounds[4])) // 2
                        run(base + ["shell", "input", "tap", str(x), str(y)], "systemui-visible-wait-tap")
                        time.sleep(2)
                        capture("after-systemui-wait")
                        after = (args.output / "window-after-systemui-wait.log").read_text(errors="replace")
                        receipt["environment_dialog"] = "SYSTEM_UI_ANR_WAIT_SELECTED_DIALOG_CLOSED" if "Application Not Responding: com.android.systemui" not in after else "SYSTEM_UI_ANR_STILL_OVERLAYING_APP"
                        return
        receipt["environment_dialog"] = "SYSTEM_UI_ANR_WAIT_NOT_RESOLVED_NO_BLIND_TAP"
    def read_private(relative):
        if not re.fullmatch(r"files(?:/[A-Za-z0-9_.-]+)+", relative) or ".." in Path(relative).parts:
            raise ValueError("Unsafe private diagnostic path")
        try:
            result = subprocess.run(base + ["exec-out", "run-as", PACKAGE, "cat", relative], capture_output=True, timeout=15)
        except subprocess.TimeoutExpired:
            return b"", {"result": "TIMEOUT", "path": relative}
        return result.stdout if result.returncode == 0 else b"", {"path": relative, "returncode": result.returncode,
            "stderr": result.stderr.decode(errors="replace")[:2048], "stdout_bytes": len(result.stdout)}
    def launch(label):
        entry = run(base + ["shell", "am", "start", "-W", "-n", PACKAGE + "/com.godot.game.GodotAppLauncher"], "launch-" + label, 60)
        problem = android_launch_problem(entry["exit_code"], Path(entry["log"]).read_text(errors="replace"))
        if problem:
            receipt["result"] = "FAIL_LAUNCH_" + label.upper()
            receipt["failure_reason"] = problem
            return False
        return True
    save()
    # Capture full main/system/crash/graphics logs before any app launch.
    log_stream = (args.output / "logcat-all.log").open("wb")
    log_err = (args.output / "logcat-stream-stderr.log").open("wb")
    logcat = subprocess.Popen(base + ["logcat", "-b", "all", "-v", "threadtime"], stdout=log_stream, stderr=log_err, env=env)
    userdata = "files"
    polls = []
    try:
        badge = run([str(sdk / "build-tools/35.0.1/aapt"), "dump", "badging", str(args.apk)], "package")
        if badge["exit_code"] != 0 or ("package: name='" + PACKAGE + "'") not in Path(badge["log"]).read_text():
            receipt["result"] = "FAIL_PACKAGE_ID"
            return 1
        verified = run([str(sdk / "build-tools/35.0.1/apksigner"), "verify", str(args.apk)], "signature")
        if verified["exit_code"] != 0:
            receipt["result"] = "FAIL_SIGNATURE"
            return 1
        if args.reuse_installed:
            located=run(base+["shell","pm","path",PACKAGE],"installed-apk-path",30)
            remote=Path(located["log"]).read_text().strip().removeprefix("package:")
            if not re.fullmatch(r"/data/app/[A-Za-z0-9_./=+-]+/base\.apk",remote):
                receipt["result"]="FAIL_INSTALLED_APK_LOCATION";return 1
            observed=run(base+["shell","sha256sum",remote],"installed-apk-sha256",30)
            if not Path(observed["log"]).read_text().startswith(args.apk_sha256+" "):
                receipt["result"]="FAIL_INSTALLED_APK_HASH";return 1
            receipt["installation"]="REUSED_EXACT_INSTALLED_APK_SHA256"
        else:
            installed = run(base + ["install", "-r", "--no-incremental", "--no-streaming", str(args.apk)], "install", 180)
            if installed["exit_code"] != 0:
                receipt["result"] = "FAIL_INSTALL"
                return 1
        run(base + ["shell", "am", "force-stop", PACKAGE], "stop-before-default")
        old_checkpoints, _ = read_private(userdata + "/" + CHECKPOINTS)
        if old_checkpoints:
            (args.output / "previous-run-checkpoints.jsonl").write_bytes(old_checkpoints)
        removed = run(base + ["shell", "run-as", PACKAGE, "rm", "-f", userdata + "/" + CHECKPOINTS], "remove-stale-diagnostic-checkpoints")
        if removed["exit_code"] != 0:
            receipt["result"] = "FAIL_CHECKPOINT_RESET"
            return 1
        if not launch("default"):
            return 1
        started = time.monotonic()
        missing = 0
        stages = []
        while time.monotonic() - started < args.startup_timeout:
            raw, poll = read_private(userdata + "/" + CHECKPOINTS)
            polls.append(poll)
            stages = checkpoint_names(raw)
            (args.output / "default-checkpoints.jsonl").write_bytes(raw)
            proc = run(base + ["shell", "pidof", PACKAGE], "default-pid-%03d" % len(polls))
            live = android_process_live(proc["exit_code"], Path(proc["log"]).read_text(errors="replace"))
            missing = 0 if live else missing + 1
            if missing >= 2:
                receipt["result"] = "FAIL_DEFAULT_PROCESS_ABSENT"
                return 1
            normalized = [re.sub(r"[^a-z]", "", s.lower()) for s in stages]
            if "firstframe" in normalized and time.monotonic() - started >= 5:
                receipt["default_mode"] = "PASS_NORMAL_LAUNCH_FIRST_FRAME_STAYS_RUNNING"
                receipt["default_stages"] = stages
                break
            if len(polls) == 2:
                # If Android places user:// beneath files, use the actual own-
                # package checkpoint path. Never probe other apps or saves.
                found = run(base + ["shell", "run-as", PACKAGE, "find", "files", "-maxdepth", "4", "-name", CHECKPOINTS], "find-checkpoint")
                for relative in Path(found["log"]).read_text(errors="replace").splitlines():
                    if re.fullmatch(r"files(?:/[A-Za-z0-9_.-]+)+", relative) and relative.endswith("/" + CHECKPOINTS):
                        userdata = str(Path(relative).parent)
                        break
            time.sleep(2)
        else:
            receipt["result"] = "FAIL_DEFAULT_FIRST_FRAME_TIMEOUT"
            receipt["default_stages"] = stages
            return 1
        capture("default-first-frame")
        handle_observed_systemui_dialog()
        overlay = receipt.get("environment_dialog", "")
        if overlay and overlay != "SYSTEM_UI_ANR_WAIT_SELECTED_DIALOG_CLOSED":
            receipt["default_mode"] = "APP_FIRST_FRAME_BEHIND_UNRESOLVED_ENVIRONMENT_DIALOG"
        if not args.smoke and not args.ui_probe:
            receipt["result"] = "PASS_DEFAULT_BOOT_ONLY" if receipt["default_mode"].startswith("PASS_") else "PARTIAL_DEFAULT_ENVIRONMENT_OVERLAY"
            return 0 if receipt["default_mode"].startswith("PASS_") else 1
        if args.ui_probe:
            from gameplay_android_input import probe
            receipt["ordinary_input_probe"] = probe(base, PACKAGE, userdata, args.output, run, read_private, launch, capture)
            save()
        if not args.smoke:
            receipt['result']='PASS_SAME_APK_DEFAULT_AND_ORDINARY_INPUT' if receipt.get('ordinary_input_probe',{}).get('status')=='PASS' else 'PARTIAL_ANDROID_ORDINARY_INPUT'
            return 0 if receipt['result'].startswith('PASS_') else 1
        run(base + ["shell", "am", "force-stop", PACKAGE], "stop-before-explicit-smoke")
        removed = run(base + ["shell", "run-as", PACKAGE, "rm", "-f", userdata + "/" + REPORT, userdata + "/" + CHECKPOINTS], "remove-stale-test-diagnostics")
        if removed["exit_code"] != 0:
            receipt["result"] = "FAIL_STALE_TEST_REPORT_RESET"
            return 1
        request = {"mode": "smoke", "run_id": "platform-" + secrets.token_hex(8)}
        # Official Godot4.6.3 strips command-line extras on exported activities.
        # Use a root-UI-validated debug-only one-shot request, not a security bypass.
        relative = userdata + "/gameplay-test-request.json"
        shell = "run-as " + PACKAGE + " sh -c 'cat > " + relative + "'"
        wrote = subprocess.run(base + ["shell", shell], input=json.dumps(request).encode(), capture_output=True, timeout=20)
        (args.output / "test-request-write.log").write_bytes(wrote.stdout + wrote.stderr)
        if wrote.returncode != 0:
            receipt["result"] = "FAIL_DEBUG_SMOKE_OPTIN_WRITE"
            return 1
        if not launch("explicit-smoke"):
            return 1
        start = last_progress = time.monotonic()
        seen = []
        missing = 0
        while time.monotonic() - start < args.timeout:
            raw, poll = read_private(userdata + "/" + REPORT)
            polls.append(poll)
            try: parsed = json.loads(raw)
            except ValueError: parsed = None
            if isinstance(parsed, dict) and parsed.get("schema"):
                (args.output / REPORT).write_bytes(raw)
                checks = parsed.get("checks", [])
                if parsed.get("schema") == "baram.gameplay-gui-evidence/1":
                    character = parsed.get("final", {}).get("character", {})
                    checks = [
                        {"id":"production_gui_report_pass", "pass":parsed.get("status")=="PASS"},
                        {"id":"four_production_moves", "pass":len(parsed.get("moves",[]))==4 and all(r.get("status")=="OK" for r in parsed.get("moves",[]))},
                        {"id":"new_commoner_level1", "pass":character.get("job")=="commoner" and character.get("level")==1 and not parsed.get("final",{}).get("skills")},
                        {"id":"actual_save_readback_equal", "pass":parsed.get("restored_equal") is True},
                        {"id":"asset_and_draw_references_valid", "pass":parsed.get("asset_errors")==[] and parsed.get("draw_errors")==[] and bool(parsed.get("rendered_paths"))},
                    ]
                    receipt["derived_production_checks"] = checks
                failures = sum(c.get("status") != "PASS" and not c.get("pass", False) for c in checks)
                receipt.update(smoke="PASS" if checks and failures == 0 else "FAIL", checks=len(checks), failures=failures,
                    report_sha256=digest(args.output / REPORT), result="PASS_SAME_APK_DEFAULT_AND_SMOKE" if checks and failures == 0 else "FAIL_SMOKE_ASSERTIONS")
                if receipt["default_mode"] != "PASS_NORMAL_LAUNCH_FIRST_FRAME_STAYS_RUNNING":
                    receipt["result"] = "PARTIAL_SMOKE_ENVIRONMENT_OVERLAY"
                    return 1
                if args.ui_probe and receipt.get("ordinary_input_probe",{}).get("status") != "PASS":
                    receipt["result"] = "PARTIAL_ANDROID_ORDINARY_INPUT"
                    return 1
                return 0 if checks and failures == 0 else 1
            raw_stages, _ = read_private(userdata + "/" + CHECKPOINTS)
            (args.output / "smoke-checkpoints.jsonl").write_bytes(raw_stages)
            current = checkpoint_names(raw_stages)
            if current != seen:
                seen, last_progress = current, time.monotonic()
                receipt["smoke_stages"] = seen
                save()
            proc = run(base + ["shell", "pidof", PACKAGE], "smoke-pid-%03d" % len(polls))
            live = android_process_live(proc["exit_code"], Path(proc["log"]).read_text(errors="replace"))
            missing = 0 if live else missing + 1
            if missing >= 2:
                receipt["result"] = "FAIL_SMOKE_PROCESS_ABSENT_NO_REPORT"
                return 1
            if time.monotonic() - last_progress > 60:
                receipt["result"] = "FAIL_SMOKE_STAGE_STALLED"
                return 1
            time.sleep(2)
        receipt["result"] = "FAIL_SMOKE_TIMEOUT_WITH_CHECKPOINTS"
        return 1
    finally:
        receipt["userdata_relative_root"] = userdata
        dump(args.output / "POLL_RECEIPTS.json", {"polls": polls})
        capture("final")
        run(base + ["logcat", "-d", "-b", "all", "-v", "threadtime", "-t", "16000"], "logcat-final")
        if logcat.poll() is None:
            logcat.terminate()
            try: logcat.wait(timeout=5)
            except subprocess.TimeoutExpired: logcat.kill(); logcat.wait(timeout=5)
        log_stream.close()
        log_err.close()
        save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    export = sub.add_parser("export")
    for name in ["project", "runtime", "godot", "templates", "output"]:
        export.add_argument("--" + name, type=Path, required=True)
    export.add_argument("--target", choices=["Windows", "Android"], required=True)
    export.add_argument("--android-sdk", type=Path)
    export.add_argument("--java-home", type=Path)
    export.add_argument("--signing-root", type=Path)
    android = sub.add_parser("android-run")
    for name in ["android-sdk", "apk", "output"]:
        android.add_argument("--" + name, type=Path, required=True)
    android.add_argument("--apk-sha256", required=True)
    android.add_argument("--serial", required=True)
    android.add_argument("--adb-port", type=int, default=5043)
    android.add_argument("--startup-timeout", type=int, default=90)
    android.add_argument("--timeout", type=int, default=180)
    android.add_argument("--smoke", action="store_true")
    android.add_argument("--ui-probe", action="store_true")
    android.add_argument("--reuse-installed", action="store_true")
    args = parser.parse_args()
    return export_gameplay(args) if args.mode == "export" else android_gameplay(args)


if __name__ == "__main__":
    raise SystemExit(main())
