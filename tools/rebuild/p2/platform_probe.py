#!/usr/bin/env python3
"""Record non-secret local P2 toolchain capabilities; never claim a game test."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time


PINNED_ENGINE = "4.6.3.stable.official.7d41c59c4"
VERSION_COMMANDS = {
    "godot": ["godot", "--version"],
    "java": ["java", "-version"],
    "javac": ["javac", "-version"],
    "gradle": ["gradle", "--version"],
    "adb": ["adb", "version"],
    "emulator": ["emulator", "-version"],
    "sdkmanager": ["sdkmanager", "--version"],
    "wine": ["wine", "--version"],
    "dotnet": ["dotnet", "--info"],
    "docker": ["docker", "version", "--format", "{{.Client.Version}} {{if .Server}}{{.Server.Version}}{{end}}"],
    "ffmpeg": ["ffmpeg", "-version"],
    "apksigner": ["apksigner", "--version"],
}
PRESENCE_ONLY = ["Xvfb", "xvfb-run", "pulseaudio", "pactl", "keytool", "jarsigner", "zipalign", "aapt2"]
INSPECTION_PACKAGE = "org.baram.rebuild.p2.codex001"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_receipt(command: list[str], max_chars: int = 4000) -> dict:
    resolved = shutil.which(command[0])
    if not resolved:
        return {"command": command, "status": "UNAVAILABLE", "exit_code": None}
    started = time.monotonic()
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        output = (run.stdout + run.stderr).strip()
        return {
            "command": command, "resolved_path": resolved,
            "status": "AVAILABLE" if run.returncode == 0 else "COMMAND_FAILED",
            "exit_code": run.returncode, "duration_ms": round((time.monotonic() - started) * 1000),
            "output": output[:max_chars], "output_truncated": len(output) > max_chars,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "resolved_path": resolved, "status": "COMMAND_FAILED", "exit_code": None, "failure_type": type(exc).__name__}


def android_device_counts(adb: Path | None) -> dict:
    if adb is None:
        return {"status": "UNAVAILABLE", "authorized_devices": 0, "device_identifiers_recorded": False}
    try:
        # This may start the local ADB server, but does not install or contact a device.
        run = subprocess.run([str(adb), "devices"], capture_output=True, text=True, timeout=15, check=False)
        counts: dict[str, int] = {}
        for line in run.stdout.splitlines()[1:]:
            columns = line.split()
            if len(columns) >= 2:
                counts[columns[1]] = counts.get(columns[1], 0) + 1
        return {"command": [str(adb), "devices"], "status": "OBSERVED" if run.returncode == 0 else "COMMAND_FAILED", "exit_code": run.returncode, "state_counts": counts, "authorized_devices": counts.get("device", 0), "device_identifiers_recorded": False}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "COMMAND_FAILED", "failure_type": type(exc).__name__, "authorized_devices": 0, "device_identifiers_recorded": False}


def exercise_android(args: argparse.Namespace) -> Path:
    """Run only the separately installed synthetic inspection app, twice."""
    if not re.fullmatch(r"[0-9a-f]{64}", args.apk_sha256 or ""):
        raise ValueError("--apk-sha256 must pin the exact APK")
    if not re.fullmatch(r"[0-9a-f]{40}", args.app_code_sha or ""):
        raise ValueError("--app-code-sha must identify its frozen source commit")
    if not args.android_serial or not args.run_output_dir:
        raise ValueError("APK execution requires --android-serial and --run-output-dir")
    if sha256(args.exercise_apk) != args.apk_sha256:
        raise ValueError("APK SHA256 differs; nothing was installed")
    output = args.run_output_dir
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Preserve old evidence: --run-output-dir must be empty")
    apk = output / "inspection.apk"
    shutil.copyfile(args.exercise_apk, apk)
    adb = args.toolchain_root / "android-sdk/platform-tools/adb"
    build_tools = args.toolchain_root / "android-sdk/build-tools/35.0.1"
    base = [str(adb), "-P", str(args.adb_server_port), "-s", args.android_serial]
    receipt = {
        "schema": "baram.p2.android_execution/1", "code_sha": args.app_code_sha,
        "apk_sha256": sha256(apk), "apk_bytes": apk.stat().st_size,
        "platform": "EXPLICIT_ANDROID_TARGET_SEE_DEVICE_METADATA",
        "native_galaxy": "NOT_ESTABLISHED_BY_RUNNER", "package": INSPECTION_PACKAGE,
        "original_assets_consumed": "NOT_ESTABLISHED_BY_RUNNER", "commands": [], "trials": [],
        "physical_input": "NOT_RUN", "IME": "NOT_RUN", "authentication": "NOT_RUN",
        "result": "RUNNING",
    }
    receipt_path = output / "RUN_RECEIPT.json"

    def save() -> None:
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

    def run(command: list[str], label: str, timeout: int = 40) -> subprocess.CompletedProcess:
        started = time.monotonic()
        path = output / (label + ".log")
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
            path.write_bytes(result.stdout + result.stderr)
            receipt["commands"].append({"command": command, "exit_code": result.returncode,
                                        "elapsed_seconds": round(time.monotonic() - started, 3), "log": str(path)})
            save()
            return result
        except subprocess.TimeoutExpired as exc:
            path.write_bytes((exc.stdout or b"") + (exc.stderr or b""))
            receipt["commands"].append({"command": command, "exit_code": None,
                                        "result": "TIMEOUT", "timeout_seconds": timeout, "log": str(path)})
            save()
            raise

    save()
    try:
        badging = run([str(build_tools / "aapt"), "dump", "badging", str(apk)], "apk-package")
        match = re.search(rb"^package: name='([^']+)'", badging.stdout)
        if badging.returncode or match is None or match.group(1).decode() != INSPECTION_PACKAGE:
            raise ValueError("APK package is not the independent P2 package; nothing was installed")
        verified = run([str(build_tools / "apksigner"), "verify", str(apk)], "apk-signature")
        if verified.returncode:
            raise ValueError("APK signature validation failed; nothing was installed")
        for prop in ("ro.build.version.release", "ro.build.version.sdk", "ro.product.cpu.abi", "ro.kernel.qemu"):
            run(base + ["shell", "getprop", prop], "device-" + prop)
        install = run(base + ["install", "-r", "--no-incremental", "--no-streaming", str(apk)], "install", 300)
        if install.returncode:
            raise RuntimeError("Inspection APK install failed")
        for trial_number in (1, 2):
            label = "trial" + str(trial_number)
            run(base + ["shell", "am", "force-stop", INSPECTION_PACKAGE], label + "-force-stop")
            # Only this runner's synthetic report files; saves and old evidence remain.
            run(base + ["shell", "run-as", INSPECTION_PACKAGE, "rm", "-f", "files/ui-smoke.json", "files/ui-smoke.json.png"], label + "-remove-stale-report")
            launch = run(base + ["shell", "am", "start", "-n", INSPECTION_PACKAGE + "/com.godot.game.GodotAppLauncher"], label + "-launch")
            if launch.returncode:
                raise RuntimeError("Android inspection Activity launch failed")
            deadline = time.monotonic() + 180
            report = None
            while time.monotonic() < deadline:
                try:
                    result = subprocess.run(base + ["exec-out", "run-as", INSPECTION_PACKAGE, "cat", "files/ui-smoke.json"], capture_output=True, timeout=min(15, max(1, deadline - time.monotonic())), check=False)
                    parsed = json.loads(result.stdout)
                    if parsed.get("schema") == "baram.p2.ui_smoke/1":
                        report = parsed
                        break
                except (subprocess.TimeoutExpired, json.JSONDecodeError, UnicodeDecodeError):
                    pass
                time.sleep(2)
            run(base + ["logcat", "-d", "-t", "4000", "-s", "godot:V", "AndroidRuntime:V", "ActivityTaskManager:V"], label + "-logcat")
            if report is None:
                receipt["trials"].append({"trial": trial_number, "result": "FAIL_NO_REPORT_180S", "ui_tests": "NOT_RUN", "storage_tests": "NOT_RUN"})
                receipt["result"] = "FAIL"
                save()
                break
            report_path = output / (label + "-ui-smoke.json")
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            storage = report.get("save_tests", {})
            receipt["original_assets_consumed"] = report.get("original_assets_consumed", "UNKNOWN")
            item = {"trial": trial_number, "report": str(report_path), "report_sha256": sha256(report_path),
                    "ui_checks": len(report.get("checks", [])), "ui_failures": sum(not value.get("pass") for value in report.get("checks", [])),
                    "save_checks": storage.get("checks"), "save_failures": storage.get("failures"),
                    "save_not_run": sum(value.get("status") == "NOT_RUN" for value in storage.get("tests", []))}
            item["result"] = "PASS" if item["ui_failures"] == 0 and item["save_failures"] == 0 else "FAIL"
            # The app writes PNG after its report. Allow the final draw to finish.
            time.sleep(1)
            picture = run(base + ["exec-out", "run-as", INSPECTION_PACKAGE, "cat", "files/ui-smoke.json.png"], label + "-screenshot")
            if picture.returncode == 0 and picture.stdout.startswith(b"\x89PNG\r\n"):
                picture_path = output / (label + "-ui-smoke.png")
                picture_path.write_bytes(picture.stdout)
                item["screenshot"] = str(picture_path)
                item["screenshot_sha256"] = sha256(picture_path)
            fixture_root = report.get("fixture_root", report.get("save_fixture_root", ""))
            allowed = ("/data/data/" + INSPECTION_PACKAGE + "/files/", "/data/user/0/" + INSPECTION_PACKAGE + "/files/")
            if fixture_root.startswith(allowed) and ".." not in Path(fixture_root).parts:
                fixture = run(base + ["exec-out", "run-as", INSPECTION_PACKAGE, "cat", fixture_root.rstrip("/") + "/roundtrip/character.json"], label + "-fixture")
                if fixture.returncode == 0:
                    fixture_path = output / (label + "-character.json")
                    fixture_path.write_bytes(fixture.stdout)
                    item["fixture"] = str(fixture_path)
                    item["fixture_sha256"] = sha256(fixture_path)
                    if args.linux_fixture:
                        item["linux_fixture_comparison"] = {"source": str(args.linux_fixture), "linux_sha256": sha256(args.linux_fixture), "byte_equal": fixture.stdout == args.linux_fixture.read_bytes(), "json_equal": json.loads(fixture.stdout) == json.loads(args.linux_fixture.read_text()), "scope": "Synthetic save format only; no authentication or original-save migration"}
            receipt["trials"].append(item)
            save()
            print(json.dumps(item), flush=True)
        receipt["result"] = "PASS" if len(receipt["trials"]) == 2 and all(value["result"] == "PASS" for value in receipt["trials"]) else "FAIL"
        save()
    except Exception as exc:
        receipt["result"] = "FAIL"
        receipt["failure_type"] = type(exc).__name__
        receipt["failure"] = str(exc)
        save()
        print(json.dumps({"result": "FAIL", "receipt": str(receipt_path), "failure_type": type(exc).__name__}), flush=True)
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--toolchain-root", default=Path("/workspace/p2-private/toolchain"), type=Path)
    parser.add_argument("--display", help="Optionally inspect an explicitly selected local X display")
    parser.add_argument("--run-receipt", action="append", default=[], type=Path,
                        help="Include an explicitly selected non-secret synthetic platform run receipt")
    parser.add_argument("--historical-run-receipt", action="append", default=[], type=Path,
                        help="Reference preserved past failures separately from the current run result")
    parser.add_argument("--exercise-apk", type=Path, help="Optionally install and launch only the independent synthetic P2 app twice")
    parser.add_argument("--apk-sha256")
    parser.add_argument("--app-code-sha")
    parser.add_argument("--android-serial")
    parser.add_argument("--adb-server-port", type=int, default=5038)
    parser.add_argument("--run-output-dir", type=Path)
    parser.add_argument("--linux-fixture", type=Path)
    args = parser.parse_args()
    if args.exercise_apk:
        args.run_receipt.append(exercise_android(args))
    root = Path(__file__).resolve().parents[3]
    tools = {name: command_receipt(command) for name, command in VERSION_COMMANDS.items()}
    tools.update({name: {"resolved_path": shutil.which(name), "status": "AVAILABLE" if shutil.which(name) else "UNAVAILABLE"} for name in PRESENCE_ONLY})
    private_versions = {
        "private_wine": (args.toolchain_root / "debian-root/usr/lib/wine/wine64", "--version"),
        "private_emulator": (args.toolchain_root / "android-sdk/emulator/emulator", "-version"),
    }
    for name, (binary, flag) in private_versions.items():
        if binary.is_file():
            tools[name] = command_receipt([str(binary), flag])
    xvfb = args.toolchain_root / "debian-root/usr/bin/Xvfb"
    tools["private_Xvfb"] = {"path": str(xvfb), "status": "AVAILABLE" if xvfb.is_file() else "UNAVAILABLE"}
    if args.display:
        # An X server observation still does not establish rendered game output.
        tools["selected_display"] = command_receipt(["env", "DISPLAY=" + args.display, "xdpyinfo"])
    sdk_roots = [args.toolchain_root / "android-sdk"]
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(name):
            sdk_roots.append(Path(os.environ[name]))
    sdk_roots = list(dict.fromkeys(sdk_roots))
    sdk_adb = next((path / "platform-tools/adb" for path in sdk_roots if (path / "platform-tools/adb").is_file()), None)
    sdk_signers = [path for sdk in sdk_roots for path in (sdk / "build-tools").glob("*/apksigner")]
    for binary in [sdk_adb, *sdk_signers]:
        if binary:
            tools[str(binary)] = command_receipt([str(binary), "version" if binary.name == "adb" else "--version"])
    git = command_receipt(["git", "-C", str(root), "rev-parse", "HEAD"])
    artifacts = []
    # Only fixed toolchain artifacts are hashed: never inspect credential files.
    for pattern in ("godot-4.6.3/SHA512-SUMS.txt", "godot-4.6.3/*export_templates.tpz", "android-downloads/repository2-1.xml", "android-downloads/*.zip", "godot-4.6.3/templates/version.txt"):
        for path in sorted(args.toolchain_root.glob(pattern)):
            if path.is_file():
                artifacts.append({"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    setup_receipts = []
    for relative in ("godot-4.6.3/INSTALL_RECEIPT.json", "android-downloads/INSTALL_RECEIPT.json", "android-downloads/EMULATOR_INSTALL_RECEIPT.json", "apt/INSTALL_RECEIPT.json", "TOOLCHAIN_ADAPTATIONS.json"):
        path = args.toolchain_root / relative
        if path.is_file():
            setup_receipts.append({"path": str(path), "sha256": sha256(path), "receipt": json.loads(path.read_text())})
    devices = android_device_counts(sdk_adb or (Path(shutil.which("adb")) if shutil.which("adb") else None))
    run_receipts = []
    for path in args.run_receipt:
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("Run receipt must be an existing JSON file of at most 1 MiB")
        run_receipts.append({"path": str(path), "sha256": sha256(path), "receipt": json.loads(path.read_text())})
    historical_receipts = []
    for path in args.historical_run_receipt:
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("Historical receipt must be an existing JSON file of at most 1 MiB")
        receipt = json.loads(path.read_text())
        historical_receipts.append({"path": str(path), "sha256": sha256(path),
                                    "code_sha": receipt.get("code_sha"), "apk_sha256": receipt.get("apk_sha256"),
                                    "result": receipt.get("result"), "trials": receipt.get("trials"),
                                    "scope": "Preserved past result; does not change the latest artifact's test result"})
    has_android_execution_receipt = any(
        receipt["receipt"].get("schema") == "baram.p2.android_execution/1"
        for receipt in run_receipts
    )
    disk = shutil.disk_usage("/workspace")
    mem = {}
    if Path("/proc/meminfo").exists():
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:")):
                key, value, _ = line.split()
                mem[key.rstrip(":")] = int(value) * 1024
    report = {
        "schema": "baram.p2.platform_capabilities/1", "task_id": "BARAM_REBUILD_CODEX_P2_001",
        "observed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "Capability observations only; installation, export, native execution, IME and Galaxy gameplay require separate run evidence.",
        "probe_sha256": sha256(Path(__file__)), "code_sha_receipt": git,
        "system": {"os": platform.system(), "machine": platform.machine(), "release": platform.release(), "cpus": os.cpu_count(), "memory_bytes": mem, "workspace_free_bytes": disk.free},
        "tools": tools, "toolchain_artifacts": artifacts, "toolchain_installation_receipts": setup_receipts,
        "explicit_run_receipts": run_receipts,
        "historical_run_receipts": historical_receipts,
        "presence_only_environment": {name: bool(os.environ.get(name)) for name in ("DISPLAY", "WAYLAND_DISPLAY", "ANDROID_HOME", "ANDROID_SDK_ROOT", "JAVA_HOME", "PULSE_SERVER")},
        "device_paths": {path: Path(path).exists() for path in ("/dev/kvm", "/dev/dri", "/dev/snd", "/dev/bus/usb")},
        "android_devices": devices,
        "pinned_engine": {"required": PINNED_ENGINE, "observed_matches": tools["godot"].get("output", "").strip() == PINNED_ENGINE},
        "platform_execution": {"linux": "NOT_RUN_BY_PROBE", "windows_native": "NOT_RUN", "windows_wine": "NOT_RUN_BY_PROBE", "android_emulator": "SEE_EXPLICIT_RUN_RECEIPTS" if has_android_execution_receipt else "NOT_RUN_BY_PROBE", "galaxy_tab_s10_fe": "NOT_RUN", "actual_ime": "NOT_RUN"},
        "constraints": ["No native Windows host was observed by this local probe.", "Wine execution, if later run, is compatibility-layer evidence and must be reported separately from native Windows.", "Android emulator absence or missing KVM does not establish that software emulation is impossible.", "No credential values, device identifiers, existing saves or signing-key contents are read or recorded."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output), "pinned_engine_matches": report["pinned_engine"]["observed_matches"], "observed_android_devices": devices["authorized_devices"]}))
    run_failed = any(value["receipt"].get("result") == "FAIL" for value in run_receipts)
    return 0 if report["pinned_engine"]["observed_matches"] and not run_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
