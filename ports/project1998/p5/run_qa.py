#!/usr/bin/env python3
"""Run real Godot windows and Xvfb within one executor namespace."""
import argparse
from pathlib import Path
import socket
import subprocess
import time
from tooling import environment, godot


def main():
    p = argparse.ArgumentParser()
    for key in ['workspace', 'experiment', 'output', 'script']: p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--state', type=Path); p.add_argument('--timeout', type=int, default=900)
    p.add_argument('--display', type=int, default=104)
    p.add_argument('--continue-journey', action='store_true')
    a = p.parse_args(); w = a.workspace.resolve(); exp = a.experiment.resolve(); out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = environment(w, exp) | {'DISPLAY': '127.0.0.1:' + str(a.display),
        'LD_LIBRARY_PATH': str(w / 'toolchain/display-root/usr/lib/x86_64-linux-gnu'),
        'P1998_P4_OUTPUT': str(a.state.resolve() if a.state else out / 'app-state')}
    with (out / 'xvfb.log').open('w') as log:
        display = subprocess.Popen([str(w / 'toolchain/display-root/usr/bin/Xvfb'), ':' + str(a.display), '-screen', '0', '1280x800x24', '-ac',
            '-nolisten', 'local', '-nolisten', 'unix', '-listen', 'tcp'], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1', 6000 + a.display), timeout=.2): break
                except OSError: time.sleep(.1)
            with (out / 'godot.log').open('w') as app_log:
                result = subprocess.run([str(godot(w)), '--audio-driver', 'Dummy', '--path', str(exp / 'runtime'), '--script', str(a.script.resolve()),
                    '--', '--p4-test-empty-base', '--qa-output=' + str(out)] + (['--continue-journey'] if a.continue_journey else []), env=env, stdout=app_log, stderr=subprocess.STDOUT, timeout=a.timeout)
            print('Godot exit', result.returncode)
            if result.returncode: print((out / 'godot.log').read_text()[-4500:])
            raise SystemExit(result.returncode)
        finally:
            display.terminate()
            try: display.wait(timeout=5)
            except subprocess.TimeoutExpired: display.kill(); display.wait()


if __name__ == '__main__': main()
