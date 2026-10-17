#!/usr/bin/env python3
"""Export exact frozen source after a proven complete, byte-identical import.

Only ui/gameplay.gd may differ from the completed staging source. All runtime
bytes, import sidecars, generated destinations, settings and templates are
checked again. Godot's real export still validates and compiles the project.
This is resource-cache reuse, not a claim of native Windows/Android execution.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p2"))
import gameplay_platform as platform
from export_generation import PACKAGE, USER_DIR, RETAINED_CERT_SHA256, validate_retained_key

ENGINE_SHA256 = "f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3"
VERSION_NAME = "0.3.1-g2-r16-candidate"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def expected_presets(templates: Path) -> str:
    platform.PACKAGE, platform.USER_DIR = PACKAGE, USER_DIR
    return (platform.presets(templates)
        .replace("version/code=1", "version/code=8")
        .replace('version/name="0.1.0-p3"', 'version/name="' + VERSION_NAME + '"')
        .replace('package/name="바람의나라 P3"', 'package/name="바람의나라 자료 재구성"'))


def staged_settings(project: Path) -> str:
    value, count = re.subn(r'config/custom_user_dir_name="[^"\n]+"',
        'config/custom_user_dir_name="' + USER_DIR + '"', (project / "project.godot").read_text())
    if count != 1 or "config/use_custom_user_dir=true" not in value:
        raise ValueError("The retained custom user-directory setting is required")
    return value


def validate_runtime(stage: Path, expected: dict) -> dict:
    root = stage / "private_runtime"
    found = {p.relative_to(root).as_posix() for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".png", ".json", ".wav"}}
    if found != set(expected):
        raise ValueError("Staged raw runtime member set differs from frozen runtime")
    sidecars = 0
    destinations = set()
    for name, digest in expected.items():
        raw = root / name
        if raw.is_symlink() or platform.digest(raw) != digest:
            raise ValueError("Staged runtime bytes differ: " + name)
        if raw.suffix.lower() in {".png", ".wav"}:
            sidecar = raw.with_name(raw.name + ".import")
            if not sidecar.is_file() or sidecar.is_symlink():
                raise ValueError("Missing completed import sidecar: " + name)
            matched = re.search(r'^dest_files=(?:PackedStringArray\((.*?)\)|\[(.*?)\])', sidecar.read_text(), re.M)
            if not matched:
                raise ValueError("Missing completed import destinations: " + name)
            paths = re.findall(r'"(res://\.godot/imported/[^"\n]+)"', matched[1] or matched[2])
            if not paths:
                raise ValueError("No generated destination for: " + name)
            for path in paths:
                generated = stage / path.removeprefix("res://")
                if not generated.is_file() or generated.is_symlink() or generated.stat().st_size == 0:
                    raise ValueError("Missing generated import destination: " + path)
                destinations.add(path)
            sidecars += 1
    return {"verified_raw_members": len(expected), "verified_import_sidecars": sidecars,
            "verified_generated_destinations": len(destinations)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["Windows", "Android"], required=True)
    for name in ["project", "runtime", "godot", "templates", "output", "completed-export", "freeze"]:
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ["android-sdk", "java-home", "signing-root"]:
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.source_commit):
        raise ValueError("A published exact final source commit is required")
    project, runtime, output = args.project.resolve(), args.runtime.resolve(), args.output.resolve()
    prior_dir = args.completed_export.resolve()
    prior = read(prior_dir / "EXPORT_RECEIPT.json")
    freeze = read(args.freeze)
    if freeze.get("source_commit") != args.source_commit:
        raise ValueError("Freeze is not the requested final published source")
    source, raw = platform.snapshot(project), platform.snapshot(runtime)
    if source != freeze.get("source_snapshot") or raw != freeze.get("runtime_snapshot"):
        raise ValueError("Current source/runtime differs from final freeze")
    if raw != prior.get("runtime_snapshot") or prior.get("engine") != platform.ENGINE:
        raise ValueError("Completed import must have the identical frozen runtime and engine")
    delta = [name for name in sorted(set(source) | set(prior["source_snapshot"]))
             if source.get(name) != prior["source_snapshot"].get(name)]
    if set(delta) - {"ui/gameplay.gd"}:
        raise ValueError("Completed import reuse allows only the approved gameplay caption source delta")
    imported = next((r for r in prior.get("commands", [])
        if "--import" in r.get("command", []) and r.get("exit_code") == 0), None)
    inherited = prior.get("completed_import")
    if imported is None and not inherited:
        raise ValueError("Prior real Godot resource import must have completed with exit0")
    stage = Path(prior.get("staged_project", prior_dir / "project")).resolve()
    if not (stage / ".godot/imported").is_dir():
        raise ValueError("Completed import cache is missing")
    lock = (stage.parent / ".completed-import-export.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for proc in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            fields = proc.read_bytes().split(b"\0")
        except (OSError, PermissionError):
            continue
        if b"--path" in fields and str(stage).encode() in fields:
            raise ValueError("A Godot process is still using the completed staging project")
    if platform.digest(args.godot) != ENGINE_SHA256:
        raise ValueError("The verified official Godot ELF is required")
    version = subprocess.check_output([str(args.godot), "--version"], text=True).strip()
    if version != platform.ENGINE:
        raise ValueError("Pinned Godot engine mismatch")
    for name in (["windows_debug_x86_64.exe", "windows_release_x86_64.exe"] if args.target == "Windows"
                 else ["android_debug.apk", "android_release.apk"]):
        if not (args.templates / name).is_file():
            raise ValueError("Required export template missing: " + name)
    for name, expected in prior["source_snapshot"].items():
        if name in {"project.godot", "export_presets.cfg"}:
            continue
        if platform.digest(stage / name) != expected:
            raise ValueError("Prior staged source changed outside this transition: " + name)
    if (stage / "project.godot").read_text() != staged_settings(project):
        raise ValueError("Staged identity/settings differ")
    if (stage / "export_presets.cfg").read_text() != expected_presets(args.templates.resolve()):
        raise ValueError("Staged export presets differ")
    runtime_checks = validate_runtime(stage, raw)
    if not any((stage / ".godot/editor").glob("filesystem_cache*")):
        raise ValueError("Godot's completed resource filesystem cache is missing")
    platform.empty_output(output)
    for name in delta:
        archived = output / "superseded-source" / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage / name, archived)
        shutil.copy2(project / name, stage / name)
    for name, expected in source.items():
        if name not in {"project.godot", "export_presets.cfg"} and platform.digest(stage / name) != expected:
            raise ValueError("Final staged source mismatch: " + name)
    completed_import = inherited or {"receipt": str(prior_dir / "EXPORT_RECEIPT.json"),
        "receipt_sha256": platform.digest(prior_dir / "EXPORT_RECEIPT.json"), "command": imported,
        "source_commit_at_import": prior.get("source_commit"), "runtime_snapshot_identical": True}
    env = os.environ.copy()
    for name in ["BARAM_P2_RUNTIME", "BARAM_P2_REPORT", "BARAM_GAMEPLAY_RUNTIME", "BARAM_GAMEPLAY_REPORT"]:
        env.pop(name, None)
    env.update(XDG_CONFIG_HOME=str(output / "godot-config"), XDG_DATA_HOME=str(output / "godot-data"),
               GODOT_SILENCE_ROOT_WARNING="1")
    cert = None
    if args.target == "Android":
        if any(x is None for x in [args.android_sdk, args.java_home, args.signing_root]):
            raise ValueError("Explicit retained signing and Android/Java locations are required")
        cert = validate_retained_key(args.signing_root.resolve(), args.java_home.resolve())
        key = args.signing_root.resolve() / "new-gameplay-test.keystore"
        env.update(JAVA_HOME=str(args.java_home.resolve()), GODOT_ANDROID_KEYSTORE_DEBUG_PATH=str(key),
            GODOT_ANDROID_KEYSTORE_DEBUG_USER="gameplay",
            GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD=(args.signing_root / "password").read_text())
        settings = output / "godot-config/godot/editor_settings-4.6.tres"
        settings.parent.mkdir(parents=True)
        settings.write_text('[gd_resource type="EditorSettings" format=3]\n\n[resource]\n' +
            'export/android/java_sdk_path = ' + json.dumps(str(args.java_home.resolve())) + '\n' +
            'export/android/android_sdk_path = ' + json.dumps(str(args.android_sdk.resolve())) + '\n' +
            'export/android/debug_keystore = ' + json.dumps(str(key)) + '\n' +
            'export/android/shutdown_adb_on_exit = false\n')
        settings.chmod(0o600)
    receipt = {"schema": "baram.v2.candidate.export/1", "engine": version,
        "engine_binary_sha256": ENGINE_SHA256, "target": args.target, "source_commit": args.source_commit,
        "source_snapshot": source, "runtime_snapshot": raw, "staged_project": str(stage),
        "staged_options": prior["staged_options"], "result": "RUNNING", "commands": [],
        "completed_import": completed_import, "completed_import_raw_reverification": runtime_checks,
        "source_transition": {"prior_source_commit": prior.get("source_commit"), "changed_files": delta,
            "source_hash_changes": {name: {"before": prior["source_snapshot"].get(name), "after": source.get(name)} for name in delta},
            "prior_staged_source_backed_up_under": str(output / "superseded-source") if delta else None,
            "only_approved_caption_source_changed": True, "final_source_exactly_matches_freeze": True},
        "resource_validation_policy": "Completed real import plus full raw-hash equality, destination checks and real Godot export; no new --import command claimed",
        "version_code": 8, "version_name": VERSION_NAME, "installed_package": PACKAGE,
        "preserved_user_dir": USER_DIR, "retained_signer_sha256": cert,
        "new_signing_key_created": False, "retained_private_key_used": args.target == "Android",
        "existing_keys_saves_apps_used": args.target == "Android", "existing_saves_modified": False,
        "application_execution": "NOT_RUN_BY_EXPORTER", "private_only": True, "new_cost": 0,
        "runtime_manifest_sha256": platform.digest(runtime / "runtime.json"),
        "gameplay_content_sha256": platform.digest(runtime / "gameplay_content.json"),
        "runtime_generation": read(runtime / "runtime.json").get("generation")}
    receipt["source_content_fingerprint"] = hashlib.sha256(json.dumps({"engine": version,
        "source": source, "runtime": raw}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    report = output / "EXPORT_RECEIPT.json"
    platform.dump(report, receipt)
    binary = output / ("baram-p3-playable.exe" if args.target == "Windows" else "baram-p3-playable.apk")
    command = [str(args.godot), "--headless", "--path", str(stage), "--export-debug", "Gameplay " + args.target, str(binary)]
    exported = platform.run_logged(command, output / "export.log", env, args.timeout)
    receipt["commands"].append(exported)
    receipt["sources_unchanged"] = platform.snapshot(project) == source
    receipt["runtime_unchanged"] = platform.snapshot(runtime) == raw
    receipt["post_export_staged_runtime_checks"] = validate_runtime(stage, raw)
    receipt["result"] = "PASS_EXPORT_ONLY" if (exported["exit_code"] == 0 and binary.is_file()
        and receipt["sources_unchanged"] and receipt["runtime_unchanged"]) else "FAIL_EXPORT"
    if binary.is_file():
        receipt["artifact"] = {"path": str(binary), "bytes": binary.stat().st_size, "sha256": platform.digest(binary)}
    if receipt["result"] == "PASS_EXPORT_ONLY" and args.target == "Android":
        verified = platform.run_logged([str(args.android_sdk / "build-tools/35.0.1/apksigner"),
            "verify", "--print-certs", str(binary)], output / "signature.log", env, 45)
        receipt["commands"].append(verified)
        found = re.search(r"certificate SHA-256 digest: ([0-9a-f]+)", (output / "signature.log").read_text())
        receipt["final_apk_signer_matches_retained"] = bool(verified["exit_code"] == 0 and found and found[1] == RETAINED_CERT_SHA256)
        badge = platform.run_logged([str(args.android_sdk / "build-tools/35.0.1/aapt2"),
            "dump", "badging", str(binary)], output / "manifest.log", env, 45)
        receipt["commands"].append(badge)
        package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", (output / "manifest.log").read_text())
        receipt["final_apk_manifest"] = {"package": package[1], "version_code": int(package[2]), "version_name": package[3]} if package else None
        if not receipt["final_apk_signer_matches_retained"]:
            receipt["result"] = "FAIL_RETAINED_SIGNER_MISMATCH"
        elif badge["exit_code"] != 0 or receipt["final_apk_manifest"] != {"package": PACKAGE, "version_code": 8, "version_name": VERSION_NAME}:
            receipt["result"] = "FAIL_RETAINED_PACKAGE_VERSION"
    if receipt["result"] == "PASS_EXPORT_ONLY" and args.target == "Windows":
        archive = output / "baram-p3-playable-Windows.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            zipped.write(binary, "baram-p3-playable.exe")
            zipped.writestr("START.txt", "새 폴더에 전체 압축을 풀고 baram-p3-playable.exe를 실행하세요.\n기존 P3 보수본 저장 경로를 유지하는 설치 후보입니다. 실제 Windows 실행 검증은 별도입니다.\n")
        receipt["windows_zip"] = {"path": str(archive), "bytes": archive.stat().st_size, "sha256": platform.digest(archive)}
    platform.dump(report, receipt)
    print(json.dumps({k: receipt.get(k) for k in ["result", "artifact", "source_commit", "source_content_fingerprint", "final_apk_manifest", "final_apk_signer_matches_retained", "application_execution"]}, ensure_ascii=False))
    return 0 if receipt["result"] == "PASS_EXPORT_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
