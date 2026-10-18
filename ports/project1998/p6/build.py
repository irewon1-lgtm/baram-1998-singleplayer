#!/usr/bin/env python3
"""Export the private P6 repair, retaining the existing package/signing identity."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from tooling import environment, godot


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ['workspace', 'experiment', 'output']: p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); w = a.workspace.resolve(); exp = a.experiment.resolve(); runtime = exp / 'runtime'; output = a.output.resolve()
    if output.exists(): raise ValueError('Preserve existing APK; choose a new output')
    logs = exp / 'android-build'; logs.mkdir(exist_ok=False); env = environment(w, exp)
    signing = w / 'p1998-private/build/signing'; templates = w / 'toolchain/templates-mono/templates'
    env.update(GODOT_ANDROID_KEYSTORE_DEBUG_PATH=str(signing / 'p1998-dev.keystore'), GODOT_ANDROID_KEYSTORE_DEBUG_USER='p1998dev',
               GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD=(signing / 'password').read_text())
    config = exp / 'editor-config/godot'; config.mkdir(parents=True, exist_ok=True)
    (config / 'editor_settings-4.6.tres').write_text('[gd_resource type="EditorSettings" format=3]\n[resource]\nexport/android/android_sdk_path=' + json.dumps(str(w / 'toolchain/android-sdk')) + '\nexport/android/java_sdk_path="/usr/lib/jvm/java-17-openjdk-amd64"\n')
    (runtime / 'export_presets.cfg').write_text('''[preset.0]
name="P1998 P6 Fix2 Android"
platform="Android"
runnable=true
export_filter="all_resources"
include_filter="capsule.json,capsule.zip,migration.json,fonts/OFL.txt,PRIVATE_INPUT_NOTICE.txt,assets/assets.json,assets/maps/*.map,p6/locale.json,p6/art/assets.json,p6/art/npc-placements.json"
exclude_filter="*.csproj,*.sln"
export_path=""
script_export_mode=2
[preset.0.options]
custom_template/debug="%s"
custom_template/release="%s"
gradle_build/use_gradle_build=false
architectures/armeabi-v7a=false
architectures/arm64-v8a=true
architectures/x86=false
architectures/x86_64=true
package/unique_name="com.irewon.baram.project1998.p3"
package/name="Project1998 P6 수정"
package/signed=true
version/code=8
version/name="0.0.6-p6-fix2"
screen/immersive_mode=true
screen/orientation=6
user_data_backup/allow=false
permissions/internet=false
permissions/access_network_state=false
dotnet/include_scripts_content=false
dotnet/include_debug_symbols=false
dotnet/embed_build_outputs=true
dotnet/android_use_linux_bionic=false
''' % (templates / 'android_debug.apk', templates / 'android_release.apk'))
    (runtime / 'PRIVATE_INPUT_NOTICE.txt').write_text('''Private user-requested Project1998 compatibility build.
Original source: https://github.com/project1998/Project1998 commit 65cb3ef28f289ee35d19abfb6829d6120b9ec0cd
Original source/client assets remain private supplied inputs; no public binary deployment.
Godot MIT; .NET MIT; MoonSharp BSD-3-Clause; Microsoft.Data.Sqlite MIT;
SQLitePCLRaw Apache-2.0; SQLite public domain; BCrypt.Net-Next MIT;
Noto Sans KR SIL OFL (fonts/OFL.txt).
''')
    frozen = [{'path': str(f.relative_to(runtime)), 'sha256': sha(f)} for f in sorted(runtime.rglob('*'))
              if f.is_file() and '.godot' not in f.parts and not f.name.endswith(('.import', '.uid'))]
    (exp / 'APP_FREEZE.json').write_text(json.dumps({'files': frozen, 'capsule_sha256': sha(runtime / 'capsule.json')}, indent=2) + '\n')
    def run(label, command, timeout=600):
        log = logs / (label + '.log')
        with log.open('w') as stream: result = subprocess.run([str(x) for x in command], env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        print(label, result.returncode, flush=True)
        if result.returncode: print(log.read_text()[-5000:]); raise RuntimeError(label)
        return log.read_text()
    output.parent.mkdir(parents=True, exist_ok=True); pending = output.with_suffix('.pending.apk')
    run('export', [godot(w), '--headless', '--path', runtime, '--export-debug', 'P1998 P6 Fix2 Android', pending])
    android = w / 'toolchain/android-sdk/build-tools/35.0.1'
    cert = run('signature', [android / 'apksigner', 'verify', '--verbose', '--print-certs', pending])
    expected = '5fb380f895f3a98d90e9688e1d7769db7f3c16ae821f3ae9f47a8c348c0a921e'
    assert expected in cert, 'Update signing identity changed'
    permissions = run('permissions', [android / 'aapt2', 'dump', 'permissions', pending])
    badging = run('badging', [android / 'aapt2', 'dump', 'badging', pending])
    assert 'android.permission.INTERNET' not in permissions
    assert "name='com.irewon.baram.project1998.p3'" in badging and "versionCode='8'" in badging
    native = []
    with zipfile.ZipFile(pending) as z:
        for abi in ['arm64-v8a', 'x86_64']:
            entry = 'lib/' + abi + '/libe_sqlite3.so'; assert entry in z.namelist()
            native.append({'abi': abi, 'sqlite_sha256': hashlib.sha256(z.read(entry)).hexdigest()})
        assert not any(n.endswith('/LoginServer.dll') for n in z.namelist())
    pending.rename(output)
    receipt = {'status': 'BUILD_PASS', 'package': 'com.irewon.baram.project1998.p3', 'versionCode': 8, 'versionName': '0.0.6-p6-fix2',
               'apk': output.name, 'bytes': output.stat().st_size, 'sha256': sha(output), 'signer_sha256': expected,
               'internet_permission': False, 'abis': native, 'native_android': 'NOT_RUN_DEVICE_P6_FIX2'}
    (exp / 'BUILD_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n'); print(json.dumps(receipt))


if __name__ == '__main__': main()
