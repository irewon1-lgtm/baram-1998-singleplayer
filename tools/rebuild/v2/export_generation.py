#!/usr/bin/env python3
"""Export a V2 candidate while preserving the installed P3 repair identity.

Reuses the existing exporter with explicit version, package and user-directory
policy. Android requires the retained private repair key; this tool never makes
a replacement key. Build success is separate from device execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p2"))
import gameplay_platform as platform

PACKAGE = "com.irewon.baram.p3repair20261016"
USER_DIR = "baram_rebuild_p3repair_001"
RETAINED_CERT_SHA256 = "c0bc3989d93d7b9443bbfa59281797a48e2b020e5da4b1dc91858768b35ccd05"


def validate_retained_key(signing: Path, java: Path) -> str:
    key = signing / "new-gameplay-test.keystore"
    marker, password_file = signing / "SYNTHETIC_KEY.json", signing / "password"
    if not key.is_file() or not marker.is_file() or not password_file.is_file():
        raise ValueError("Retained P3 repair signing material is required; no new key will be created")
    if json.loads(marker.read_text()).get("owner") != "BARAM_REBUILD_WORK_P3_PLAYABLE_001":
        raise ValueError("Signing marker does not belong to the retained test identity")
    key.chmod(0o600)
    password_file.chmod(0o600)
    env = os.environ.copy()
    env["BARAM_RETAINED_KEY_PASSWORD"] = password_file.read_text()
    cert = subprocess.run([str(java / "bin/keytool"), "-exportcert", "-keystore", str(key),
        "-storepass:env", "BARAM_RETAINED_KEY_PASSWORD", "-alias", "gameplay"],
        env=env, capture_output=True, timeout=30)
    if cert.returncode or hashlib.sha256(cert.stdout).hexdigest() != RETAINED_CERT_SHA256:
        raise ValueError("Private key certificate does not match the delivered P3 repair APK")
    return RETAINED_CERT_SHA256


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["Windows", "Android"], required=True)
    for name in ("project", "runtime", "godot", "templates", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("android-sdk", "java-home", "signing-root"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--version-code", type=int, default=3)
    parser.add_argument("--version-name", default="0.2.0-v2-candidate")
    parser.add_argument("--resume-import", action="store_true",
                        help="Resume a timed-out import only after exact frozen-input checks")
    parser.add_argument("--import-timeout", type=int, default=180)
    args = parser.parse_args()
    if args.version_code <= 2:
        parser.error("Version code must increase above the delivered P3 repair code 2")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.version_name):
        parser.error("Version name contains unsupported characters")
    cert = None
    if args.target == "Android":
        if args.signing_root is None or args.java_home is None:
            parser.error("Android requires the retained --signing-root and --java-home")
        cert = validate_retained_key(args.signing_root.resolve(), args.java_home.resolve())
    platform.PACKAGE, platform.USER_DIR = PACKAGE, USER_DIR
    base_presets = platform.presets
    def presets(templates):
        return (base_presets(templates)
            .replace("version/code=1", "version/code=" + str(args.version_code))
            .replace('version/name="0.1.0-p3"', 'version/name="' + args.version_name + '"')
            .replace('package/name="바람의나라 P3"', 'package/name="바람의나라 자료 재구성"'))
    platform.presets = presets
    if not 180 <= args.import_timeout <= 1800:
        parser.error("Import timeout must be between 180 and 1800 seconds")
    base_run = platform.run_logged
    def bounded_import(command, output, env, timeout=300):
        if "--import" in command:
            timeout = args.import_timeout
        return base_run(command, output, env, timeout)
    platform.run_logged = bounded_import
    if args.resume_import:
        prior_path = args.output.resolve() / "EXPORT_RECEIPT.json"
        prior = json.loads(prior_path.read_text())
        if (prior.get("result") != "FAIL_IMPORT" or prior.get("source_commit") != args.source_commit
                or prior.get("target") != args.target or prior.get("version_code") != args.version_code
                or prior.get("version_name") != args.version_name
                or prior.get("source_snapshot") != platform.snapshot(args.project.resolve())
                or prior.get("runtime_snapshot") != platform.snapshot(args.runtime.resolve())):
            raise ValueError("Resume requires the identical failed import and frozen inputs")
        stage = args.output.resolve() / "project"
        for name, expected in prior["source_snapshot"].items():
            staged = stage / name
            if name == "export_presets.cfg":
                continue
            if name == "project.godot":
                text = (args.project.resolve() / name).read_text()
                text = re.sub(r'config/custom_user_dir_name="[^"\\n]+"',
                              'config/custom_user_dir_name="' + USER_DIR + '"', text)
                if staged.read_text() != text:
                    raise ValueError("Staged project settings changed")
            elif platform.digest(staged) != expected:
                raise ValueError("Staged source changed: " + name)
        if (stage / "export_presets.cfg").read_text() != presets(args.templates.resolve()):
            raise ValueError("Staged export presets changed")
        for name, expected in prior["runtime_snapshot"].items():
            if platform.digest(stage / "private_runtime" / name) != expected:
                raise ValueError("Staged runtime changed: " + name)
        for name in ("EXPORT_RECEIPT.json", "import.log"):
            source = args.output.resolve() / name
            archived = source.with_name(source.name + ".attempt-1")
            if archived.exists():
                raise ValueError("Resume attempt archive already exists")
            source.rename(archived)
        platform.empty_output = lambda output: None
        platform.stage_project = lambda *unused: prior["staged_options"]
    if args.target == "Android":
        base_run_logged = platform.run_logged
        def retained_key_logged(command, output, env, timeout=300):
            # Godot normally creates an unrelated editor debug key on the
            # first import. Point its editor default at the retained key before
            # any Godot process, while actual signing credentials stay in env.
            settings = args.output.resolve() / "godot-config/godot/editor_settings-4.6.tres"
            if settings.is_file() and command[0] == str(args.godot):
                text = settings.read_text()
                if "export/android/debug_keystore = " not in text:
                    text += "export/android/debug_keystore = " + json.dumps(str(
                        args.signing_root.resolve() / "new-gameplay-test.keystore")) + "\n"
                    settings.write_text(text)
                    settings.chmod(0o600)
            return base_run_logged(command, output, env, timeout)
        platform.run_logged = retained_key_logged
    result = platform.export_gameplay(args)
    path = args.output / "EXPORT_RECEIPT.json"
    if path.exists():
        receipt = json.loads(path.read_text())
        receipt.update(schema="baram.v2.candidate.export/1", source_commit=args.source_commit,
            version_code=args.version_code, version_name=args.version_name,
            installed_package=PACKAGE, preserved_user_dir=USER_DIR,
            application_execution="NOT_RUN_BY_EXPORTER", new_signing_key_created=False,
            retained_signer_sha256=cert, private_only=True,
            existing_keys_saves_apps_used=args.target == "Android",
            retained_private_key_used=args.target == "Android", existing_saves_modified=False,
            install_policy="Update the retained P3 repair package without uninstalling; actual device update/save retention remains separately testable")
        receipt["source_content_fingerprint"] = hashlib.sha256(json.dumps({
            "engine": receipt.get("engine"), "source": receipt.get("source_snapshot"),
            "runtime": receipt.get("runtime_snapshot")}, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if result == 0 and args.target == "Android":
            apk = Path(receipt["artifact"]["path"])
            checked = subprocess.run([str(args.android_sdk / "build-tools/35.0.1/apksigner"),
                "verify", "--print-certs", str(apk)], capture_output=True, text=True, timeout=30)
            found = re.search(r"certificate SHA-256 digest: ([0-9a-f]+)", checked.stdout)
            receipt["final_apk_signer_matches_retained"] = bool(checked.returncode == 0 and found and found[1] == cert)
            if not receipt["final_apk_signer_matches_retained"]:
                receipt["result"], result = "FAIL_RETAINED_SIGNER_MISMATCH", 1
            badging = subprocess.run([str(args.android_sdk / "build-tools/35.0.1/aapt2"),
                "dump", "badging", str(apk)], capture_output=True, text=True, timeout=30)
            package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging.stdout)
            receipt["final_apk_manifest"] = {"package": package[1], "version_code": int(package[2]),
                "version_name": package[3]} if package else None
            if badging.returncode or not package or package[1] != PACKAGE or int(package[2]) != args.version_code:
                receipt["result"], result = "FAIL_RETAINED_PACKAGE_VERSION", 1
        if result == 0 and args.target == "Windows":
            archive = Path(receipt["windows_zip"]["path"])
            binary = Path(receipt["artifact"]["path"])
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
                zipped.write(binary, "baram-p3-playable.exe")
                zipped.writestr("START.txt", "새 폴더에 전체 압축을 풀고 baram-p3-playable.exe를 실행하세요.\n"
                    "기존 P3 보수본의 사용자 저장 경로를 유지하는 V2 후보입니다.\n"
                    "빌드 성공은 Windows 실제 실행·저장 이전 성공을 뜻하지 않습니다.\n")
            receipt["windows_zip"].update(bytes=archive.stat().st_size, sha256=platform.digest(archive))
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print("V2_FINAL_EXPORT " + json.dumps({k: receipt.get(k) for k in (
            "result", "artifact", "windows_zip", "source_content_fingerprint",
            "final_apk_manifest", "final_apk_signer_matches_retained", "application_execution")}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
