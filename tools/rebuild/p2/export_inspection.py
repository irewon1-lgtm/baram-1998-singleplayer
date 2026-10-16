#!/usr/bin/env python3
"""Export only the isolated P2 project; keys and output remain private."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = Path("/workspace/p2-private")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["Windows", "Android"], required=True)
    ap.add_argument("--output-dir", type=Path, default=PRIVATE / "builds")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(PRIVATE / "godot-config")
    env["XDG_DATA_HOME"] = str(PRIVATE / "godot-data")
    settings = Path(env["XDG_CONFIG_HOME"]) / "godot/editor_settings-4.6.tres"
    settings.parent.mkdir(parents=True, exist_ok=True)
    key = PRIVATE / "signing/p2-debug.keystore"
    if args.target == "Android":
        key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        pwfile = key.with_suffix(".password")
        if not key.exists():
            # Local synthetic signing key only; never copied into repo/artifact.
            if pwfile.exists():
                raise RuntimeError("Partial key state: preserve and inspect before retry")
            password = secrets.token_hex(24)
            pwfile.write_text(password)
            pwfile.chmod(0o600)
            env["BARAM_P2_KEY_PASSWORD"] = password
            subprocess.run(["keytool", "-genkeypair", "-keystore", str(key),
                            "-storepass:env", "BARAM_P2_KEY_PASSWORD",
                            "-keypass:env", "BARAM_P2_KEY_PASSWORD", "-alias", "p2inspection",
                            "-dname", "CN=P2 Synthetic Inspection", "-keyalg", "RSA",
                            "-validity", "3650", "-noprompt"], env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            key.chmod(0o600)
        env["GODOT_ANDROID_KEYSTORE_DEBUG_PATH"] = str(key)
        env["GODOT_ANDROID_KEYSTORE_DEBUG_USER"] = "p2inspection"
        env["GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD"] = pwfile.read_text()
        # Editor settings need only non-secret tool locations; key stays in env.
        settings.write_text('[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
                            'export/android/java_sdk_path = "/usr/lib/jvm/java-21-openjdk-amd64"\n'
                            'export/android/android_sdk_path = "/workspace/p2-private/toolchain/android-sdk"\n')
    suffix = ".exe" if args.target == "Windows" else ".apk"
    output = args.output_dir / ("baram-p2-inspection" + suffix)
    def source_snapshot():
        return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT/"rebuild/p2").rglob("*"))
                if p.is_file() and ".godot" not in p.parts}
    sources = source_snapshot()
    code_sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    input_manifest_sha = hashlib.sha256((ROOT/"docs/rebuild/p2/INPUT_MANIFEST.json").read_bytes()).hexdigest()
    cmd = [shutil.which("godot") or "godot", "--headless", "--path", str(ROOT/"rebuild/p2"),
           "--export-debug", "P2 " + args.target, str(output)]
    started = time.time()
    completed = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    log = args.output_dir / (args.target.lower()+"-export.log")
    # Engine does not print key env; refuse known secret if a new version does.
    stdout = completed.stdout+completed.stderr
    for name in ["GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD", "BARAM_P2_KEY_PASSWORD"]:
        if env.get(name):
            stdout = stdout.replace(env[name], "[REDACTED]")
    log.write_text(stdout)
    receipt = {"target":args.target,"command":cmd,"exit_code":completed.returncode,
               "elapsed_seconds":round(time.time()-started, 3),"log":str(log),
               "file":str(output),"result":"PASS" if completed.returncode == 0 and output.exists() else "FAIL",
               "original_assets":0,"application_execution":"NOT_RUN_BY_EXPORTER",
               "engine":"4.6.3.stable.official.7d41c59c4","signing_key_in_artifact":False}
    receipt.update(code_sha=code_sha, source_sha256=sources,
                   input_manifest_sha256=input_manifest_sha,
                   sources_unchanged_during_export=sources == source_snapshot())
    if not receipt["sources_unchanged_during_export"]:
        receipt["result"] = "FAIL_SOURCE_CHANGED_DURING_EXPORT"
    if output.exists():
        receipt.update(bytes=output.stat().st_size,sha256=hashlib.file_digest(output.open("rb"),"sha256").hexdigest())
    (args.output_dir/(args.target.lower()+"-export.json")).write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({k:v for k,v in receipt.items() if k != "source_sha256"}))
    if completed.returncode:
        print(stdout[-6000:])
    return completed.returncode or (0 if receipt["sources_unchanged_during_export"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
