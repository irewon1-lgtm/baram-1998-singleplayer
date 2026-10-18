#!/usr/bin/env python3
"""Real Android P3 process test. API 28 software guest, never a Galaxy claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import signal
import time

PACKAGE = 'com.irewon.baram.project1998.p3'


def main():
    p = argparse.ArgumentParser()
    for name in ['sdk', 'avd-root', 'android-user', 'apk', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--adb-port', type=int, default=5037)
    a = p.parse_args()
    for k, v in vars(a).items():
        if isinstance(v, Path): setattr(a, k, v.resolve())
    a.output.mkdir(parents=True, exist_ok=True)
    a.avd_root.mkdir(parents=True, exist_ok=True)
    avd = a.avd_root / 'p1998-p3-28.avd'; avd.mkdir(exist_ok=True)
    (a.avd_root / 'p1998-p3-28.ini').write_text('avd.ini.encoding=UTF-8\npath=' + str(avd) + '\ntarget=android-28\n')
    (avd / 'config.ini').write_text('''AvdId=p1998-p3-28
avd.ini.displayname=P1998 P3 API28
abi.type=x86_64
hw.cpu.arch=x86_64
hw.cpu.ncore=1
hw.ramSize=2048
hw.lcd.width=800
hw.lcd.height=480
hw.lcd.density=160
hw.keyboard=yes
hw.gpu.enabled=yes
hw.gpu.mode=swiftshader_indirect
disk.dataPartition.size=1G
image.sysdir.1=system-images/android-28/default/x86_64/
tag.id=default
tag.display=Default
PlayStore.enabled=false
''')
    env = os.environ | {'ANDROID_SDK_ROOT': str(a.sdk), 'ANDROID_AVD_HOME': str(a.avd_root),
                        'ANDROID_USER_HOME': str(a.android_user), 'ADB_SERVER_PORT': str(a.adb_port),
                        'ANDROID_ADB_SERVER_PORT': str(a.adb_port)}
    adb = str(a.sdk / 'platform-tools/adb'); serial = 'emulator-5564'
    def ad(*args, timeout=20, binary=False):
        return subprocess.run([adb, '-P', str(a.adb_port), '-s', serial, *args], env=env, capture_output=True,
                              text=not binary, timeout=timeout)
    record = {'status': 'BLOCKED_ENVIRONMENT', 'galaxy': 'NOT_RUN_DEVICE', 'checks': [],
              'changed_hypothesis': 'Explicit 2048MB system/data partition avoids emulator auto-inflating userdata to 6GB; fresh AVD; 2GiB RAM; package readiness; non-streaming install'}
    def check(name, ok, detail=None):
        record['checks'].append({'name': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})
        print(json.dumps(record['checks'][-1]), flush=True)
        if not ok: raise AssertionError(name)
    def receipt(timeout=150, cold=None):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            r = ad('shell', 'run-as', PACKAGE, 'cat', 'files/p3/verification.json')
            try:
                d = json.loads(r.stdout)
                if cold is None or d.get('cold_existing_save') == cold: return d
            except ValueError: pass
            fail = ad('shell', 'run-as', PACKAGE, 'cat', 'files/p3/failure.json')
            if fail.returncode == 0 and fail.stdout.strip(): raise RuntimeError('App failure: ' + fail.stdout)
            time.sleep(2)
        raise TimeoutError('P3 app receipt not observed')
    emu = None
    logcat = None
    logcat_file = None
    try:
        subprocess.run([adb, '-P', str(a.adb_port), 'start-server'], env=env, capture_output=True, timeout=20, check=True)
        with (a.output / 'emulator.log').open('w') as log:
            emu = subprocess.Popen([str(a.sdk / 'emulator/emulator'), '-avd', 'p1998-p3-28', '-port', '5564',
                '-no-window', '-no-audio', '-no-snapshot', '-no-boot-anim', '-accel', 'off',
                '-gpu', 'swiftshader_indirect', '-memory', '2048', '-partition-size', '2048', '-cores', '1', '-show-kernel'], env=env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            start = time.monotonic(); booted = False; progress = 0
            while time.monotonic() - start < 600:
                if emu.poll() is not None: raise RuntimeError('Emulator exited ' + str(emu.returncode))
                try:
                    query = ad('shell', 'getprop', 'sys.boot_completed', timeout=8)
                    booted = query.stdout.strip() == '1'
                except subprocess.TimeoutExpired: pass
                if booted: break
                if time.monotonic() - start >= progress:
                    print('P3 API28 boot pending', round(time.monotonic() - start),
                          (query.stdout + query.stderr).strip() if 'query' in locals() else 'query timeout', flush=True)
                    progress += 30
                time.sleep(2)
            if not booted: raise TimeoutError('Changed API28 guest not booted within 600 seconds')
            check('Android API28 guest boots', True, round(time.monotonic() - start, 1))
            logcat_file = (a.output / 'logcat-live.txt').open('w')
            logcat = subprocess.Popen([adb, '-P', str(a.adb_port), '-s', serial, 'logcat', '-b', 'all', '-v', 'threadtime'],
                env=env, stdout=logcat_file, stderr=subprocess.STDOUT)
            # boot_completed can precede a stable package service in slow TCG
            # guests. Verify it answers before copying the large .NET candidate.
            package_ready = False
            for attempt in range(12):
                try:
                    ready = ad('shell', 'cmd', 'package', 'list', 'packages', timeout=20)
                    package_ready = ready.returncode == 0 and 'package:android' in ready.stdout
                except subprocess.TimeoutExpired: package_ready = False
                if package_ready: break
                print('Package service pending', attempt, flush=True); time.sleep(2)
            if not package_ready: raise TimeoutError('Android package service never stabilized')
            # The guest can boot while the C# candidate builds.
            deadline = time.monotonic() + 900
            while not a.apk.exists():
                if time.monotonic() > deadline: raise TimeoutError('Candidate APK not ready')
                time.sleep(2)
            record['apk_sha256'] = hashlib.sha256(a.apk.read_bytes()).hexdigest()
            installed = ad('install', '--no-streaming', '-r', '-t', str(a.apk), timeout=240)
            check('Exact P3 APK installs', installed.returncode == 0 and 'Success' in installed.stdout, installed.stdout + installed.stderr)
            ad('shell', 'input', 'keyevent', '82')
            ad('shell', 'svc', 'wifi', 'disable'); ad('shell', 'svc', 'data', 'disable')
            ad('shell', 'settings', 'put', 'global', 'airplane_mode_on', '1')
            ad('shell', 'am', 'broadcast', '-a', 'android.intent.action.AIRPLANE_MODE', '--ez', 'state', 'true')
            ad('logcat', '-c')
            launched = ad('shell', 'am', 'start', '-n', PACKAGE + '/com.godot.game.GodotApp', timeout=60)
            (a.output / 'launch.txt').write_text(launched.stdout + launched.stderr)
            first = receipt()
            check('C# original rules run offline inside Android app', first['platform'] == 'Android' and first['original_parity'] and not first['world_started'], first)
            check('Original MoonSharp and native SQLite execute', first['moonsharp_heal_and_drink'] and first['sqlite_round_trip'] and first['sqlite_online_backup'])
            (a.output / 'first.json').write_text(json.dumps(first, indent=2))
            trace = ad('shell', 'run-as', PACKAGE, 'cat', 'files/p3/trace.json')
            (a.output / 'trace.json').write_text(trace.stdout)
            screenshot = ad('exec-out', 'screencap', '-p', binary=True)
            check('Android screenshot captured', screenshot.stdout.startswith(b'\x89PNG'))
            (a.output / 'android-p3.png').write_bytes(screenshot.stdout)
            ad('shell', 'am', 'force-stop', PACKAGE)
            ad('shell', 'run-as', PACKAGE, 'rm', 'files/p3/verification.json')
            ad('shell', 'am', 'start', '-n', PACKAGE + '/com.godot.game.GodotApp', timeout=60)
            second = receipt(cold='Ok')
            check('Android cold process reads previous SQLite save', second['cold_existing_save'] == 'Ok' and second['cold_hp'] == 39, second)
            (a.output / 'second.json').write_text(json.dumps(second, indent=2))
            record['status'] = 'PASS_ANDROID_EMULATOR_OBSERVED_SCOPE'
    except (TimeoutError, subprocess.TimeoutExpired) as e:
        record['error'] = str(e)
    except Exception as e:
        record.update(status='FAIL_OBSERVED_ANDROID', error=str(e))
    finally:
        if logcat is not None:
            logcat.terminate()
            try: logcat.wait(timeout=5)
            except subprocess.TimeoutExpired: logcat.kill(); logcat.wait()
        if logcat_file is not None: logcat_file.close()
        try: (a.output / 'logcat.txt').write_text(ad('logcat', '-d', timeout=20).stdout)
        except Exception: pass
        (a.output / 'ANDROID_P3.json').write_text(json.dumps(record, indent=2) + '\n')
        try: ad('emu', 'kill', timeout=8)
        except Exception: pass
        if emu is not None:
            # The launcher can leave its QEMU child alive. This session was
            # created exclusively for this task, so clean its entire group.
            try: os.killpg(emu.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: emu.wait(timeout=8)
            except subprocess.TimeoutExpired: pass
            try: os.killpg(emu.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            if emu.poll() is None: emu.wait(timeout=5)
        print(json.dumps(record), flush=True)


if __name__ == '__main__': main()
