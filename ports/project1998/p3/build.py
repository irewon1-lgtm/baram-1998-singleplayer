#!/usr/bin/env python3
"""Build the reference, verify the in-process host, export a private C# APK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import zipfile


def main():
    p = argparse.ArgumentParser()
    for key in ['experiment', 'dotnet', 'godot', 'sdk', 'templates', 'signing', 'output']:
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--direct-msbuild', type=Path, help='Optional exact SDK MSBuild.dll for restricted /proc build hosts')
    p.add_argument('--resume', choices=['oracle-build', 'app-build', 'import', 'android-export'], default='oracle-build')
    a = p.parse_args()
    for k, v in vars(a).items():
        if isinstance(v, Path): setattr(a, k, v.resolve())
    exp = a.experiment; runtime = exp / 'runtime'; logs = exp / 'build'; logs.mkdir(exist_ok=True)
    env = os.environ | {'DOTNET_ROOT': str(a.dotnet.parent), 'DOTNET_CLI_HOME': str(exp.parent / 'dotnet-home'),
        'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'MSBUILDDISABLENODEREUSE': '1',
        'PATH': str(a.dotnet.parent) + ':' + os.environ['PATH'], 'GODOT_SILENCE_ROOT_WARNING': '1',
        'XDG_DATA_HOME': str(exp / 'editor-data'), 'XDG_CONFIG_HOME': str(exp / 'editor-config'),
        'JAVA_HOME': '/usr/lib/jvm/java-17-openjdk-amd64'}
    if a.direct_msbuild:
        wrapper = exp / 'dotnet-wrapper'; wrapper.mkdir(exist_ok=True)
        shutil.copyfile(Path(__file__).with_name('dotnet_msbuild.py'), wrapper / 'dotnet')
        (wrapper / 'dotnet').chmod(0o755)
        env.update(P3_REAL_DOTNET=str(a.dotnet), P3_MSBUILD_DLL=str(a.direct_msbuild),
                   MSBUILD_EXE_PATH=str(a.direct_msbuild), MSBuildSDKsPath=str(a.direct_msbuild.parent / 'Sdks'),
                   DOTNET_MSBUILD_SDK_RESOLVER_CLI_DIR=str(a.dotnet.parent),
                   PATH=str(wrapper) + ':' + env['PATH'])
    stages = ['oracle-build', 'app-build', 'import', 'android-export']
    def run(name, cmd, cwd=None, timeout=240):
        path = logs / (name + '.log')
        if path.exists(): raise ValueError('Preserve previous evidence; choose a new experiment: ' + str(path))
        with path.open('w') as log:
            result = subprocess.run([str(x) for x in cmd], env=env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        print(name, 'exit', result.returncode, flush=True)
        if result.returncode:
            print(path.read_text()[-5000:]); raise RuntimeError(name + ' failed')
        return path
    common = ['-m:1', '-nr:false', '-p:BuildInParallel=false', '-p:UseSharedCompilation=false', '--nologo', '-v', 'minimal']
    compiler = exp / 'dotnet-wrapper/dotnet' if a.direct_msbuild else a.dotnet
    if a.resume == 'oracle-build':
        run('oracle-build', [compiler, 'build', exp / 'oracle/Oracle.csproj', *common])
        run('oracle-run', [a.dotnet, exp / 'oracle/bin/Debug/net8.0/Oracle.dll', exp / 'content', runtime / 'fixtures.json',
                           exp / 'oracle-state', runtime / 'oracle.expected.json'])
    assert (runtime / 'P3Probe.sln').exists(), 'Run prepare.py first'
    if stages.index(a.resume) <= 1: run('app-build', [compiler, 'build', runtime / 'P3Probe.csproj', *common])
    if stages.index(a.resume) <= 2:
        imported = run('import', [a.godot, '--headless', '--editor', '--path', runtime, '--import', '--quit'])
        if 'ERROR:' in imported.read_text(): raise RuntimeError('Godot import errors require inspection')
    env['P1998_P3_OUTPUT'] = str(exp / 'qa-host')
    if a.resume != 'android-export':
        run('host-first', [a.godot, '--headless', '--audio-driver', 'Dummy', '--path', runtime, '--', '--p3-quit'])
        first = json.loads((exp / 'qa-host/verification.json').read_text())
        (logs / 'host-first.json').write_text(json.dumps(first, indent=2) + '\n')
        run('host-cold', [a.godot, '--headless', '--audio-driver', 'Dummy', '--path', runtime, '--', '--p3-quit'])
    first = json.loads((logs / 'host-first.json').read_text())
    cold = json.loads((exp / 'qa-host/verification.json').read_text())
    assert first['original_parity'] and first['steps'] == 40 and not first['world_started']
    assert cold['cold_existing_save'] == 'Ok' and cold['cold_hp'] == 39
    del env['P1998_P3_OUTPUT']
    config = exp / 'editor-config/godot'; config.mkdir(parents=True, exist_ok=True)
    (config / 'editor_settings-4.6.tres').write_text('[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
        + 'export/android/android_sdk_path=' + json.dumps(str(a.sdk)) + '\n'
        + 'export/android/java_sdk_path="/usr/lib/jvm/java-17-openjdk-amd64"\n')
    password = (a.signing / 'password').read_text()
    env.update(GODOT_ANDROID_KEYSTORE_DEBUG_PATH=str(a.signing / 'p1998-dev.keystore'),
               GODOT_ANDROID_KEYSTORE_DEBUG_USER='p1998dev', GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD=password)
    (runtime / 'export_presets.cfg').write_text('''[preset.0]
name="P1998 P3 Android"
platform="Android"
runnable=true
export_filter="all_resources"
include_filter="capsule.json,capsule.zip,fixtures.json,oracle.expected.json,fonts/OFL.txt,PRIVATE_INPUT_NOTICE.txt"
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
package/name="Project1998 P3 Core"
package/signed=true
version/code=1
version/name="0.0.1-p3"
screen/immersive_mode=true
screen/orientation=0
user_data_backup/allow=false
permissions/internet=false
permissions/access_network_state=false
dotnet/include_scripts_content=false
dotnet/include_debug_symbols=false
dotnet/embed_build_outputs=true
dotnet/android_use_linux_bionic=false
''' % (a.templates / 'android_debug.apk', a.templates / 'android_release.apk'))
    (runtime / 'PRIVATE_INPUT_NOTICE.txt').write_text('''Private, user-requested compatibility experiment.
Original Project1998 supplied source: https://github.com/project1998/Project1998
Pinned commit: 65cb3ef28f289ee35d19abfb6829d6120b9ec0cd
No original project redistribution license was found. No public binary deployment is authorized.
Godot: MIT. .NET runtime: MIT. MoonSharp 2.0.0: BSD-3-Clause.
Microsoft.Data.Sqlite 8.0.10: MIT. SQLitePCLRaw 2.1.6: Apache-2.0. SQLite: public domain.
BCrypt.Net-Next 4.0.3: MIT. Noto Sans KR: SIL Open Font License (fonts/OFL.txt).
''')
    frozen = {'files': [{'path': str(f.relative_to(runtime)), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
              for f in sorted(runtime.rglob('*')) if f.is_file() and '.godot' not in f.parts and not f.name.endswith(('.import', '.uid'))],
              'capsule_sha256': first['capsule_sha256']}
    (exp / 'APP_FREEZE.json').write_text(json.dumps(frozen, indent=2) + '\n')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    pending = a.output.with_name(a.output.stem + '.pending.apk')
    run('android-export', [a.godot, '--headless', '--path', runtime, '--export-debug', 'P1998 P3 Android', pending], timeout=600)
    tools = a.sdk / 'build-tools/35.0.1'
    run('signature', [tools / 'apksigner', 'verify', '--verbose', '--print-certs', pending])
    permission = run('permissions', [tools / 'aapt2', 'dump', 'permissions', pending])
    badging = run('badging', [tools / 'aapt2', 'dump', 'badging', pending])
    assert 'android.permission.INTERNET' not in permission.read_text()
    assert "package: name='com.irewon.baram.project1998.p3'" in badging.read_text()
    with zipfile.ZipFile(pending) as archive:
        names = archive.namelist(); native = []
        for abi in ['arm64-v8a', 'x86_64']:
            matches = [n for n in names if n.startswith('lib/' + abi + '/') and n.endswith('/libe_sqlite3.so')]
            assert len(matches) == 1, matches
            native.append({'abi': abi, 'entry': matches[0], 'sha256': hashlib.sha256(archive.read(matches[0])).hexdigest()})
        assert not any(n.endswith('/LoginServer.dll') for n in names)
    pending.rename(a.output)
    receipt = {'status': 'BUILD_PASS', 'package': 'com.irewon.baram.project1998.p3', 'versionCode': 1,
               'apk': a.output.name, 'bytes': a.output.stat().st_size, 'sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
               'network_permission': False, 'sqlite_native': native, 'host': cold, 'galaxy': 'NOT_RUN_DEVICE'}
    (exp / 'BUILD_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__': main()
