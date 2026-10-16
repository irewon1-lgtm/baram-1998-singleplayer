#!/usr/bin/env python3
"""Record non-secret local P2 toolchain capabilities; never claim a game test."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--toolchain-root", default=Path("/workspace/p2-private/toolchain"), type=Path)
    parser.add_argument("--display", help="Optionally inspect an explicitly selected local X display")
    args = parser.parse_args()
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
    for relative in ("android-downloads/INSTALL_RECEIPT.json", "android-downloads/EMULATOR_INSTALL_RECEIPT.json", "apt/INSTALL_RECEIPT.json", "TOOLCHAIN_ADAPTATIONS.json"):
        path = args.toolchain_root / relative
        if path.is_file():
            setup_receipts.append({"path": str(path), "sha256": sha256(path), "receipt": json.loads(path.read_text())})
    devices = android_device_counts(sdk_adb or (Path(shutil.which("adb")) if shutil.which("adb") else None))
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
        "presence_only_environment": {name: bool(os.environ.get(name)) for name in ("DISPLAY", "WAYLAND_DISPLAY", "ANDROID_HOME", "ANDROID_SDK_ROOT", "JAVA_HOME", "PULSE_SERVER")},
        "device_paths": {path: Path(path).exists() for path in ("/dev/kvm", "/dev/dri", "/dev/snd", "/dev/bus/usb")},
        "android_devices": devices,
        "pinned_engine": {"required": PINNED_ENGINE, "observed_matches": tools["godot"].get("output", "").strip() == PINNED_ENGINE},
        "platform_execution": {"linux": "NOT_RUN_BY_PROBE", "windows_native": "NOT_RUN", "windows_wine": "NOT_RUN_BY_PROBE", "android_emulator": "NOT_RUN_BY_PROBE", "galaxy_tab_s10_fe": "NOT_RUN", "actual_ime": "NOT_RUN"},
        "constraints": ["No native Windows host was observed by this local probe.", "Wine execution, if later run, is compatibility-layer evidence and must be reported separately from native Windows.", "Android emulator absence or missing KVM does not establish that software emulation is impossible.", "No credential values, device identifiers, existing saves or signing-key contents are read or recorded."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output), "pinned_engine_matches": report["pinned_engine"]["observed_matches"], "observed_android_devices": devices["authorized_devices"]}))
    return 0 if report["pinned_engine"]["observed_matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
