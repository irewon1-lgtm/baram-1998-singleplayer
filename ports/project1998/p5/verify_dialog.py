#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import time
from tooling import environment, godot


def main():
    p = argparse.ArgumentParser()
    for key in ['workspace', 'experiment', 'output']: p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--display', type=int, default=125)
    a = p.parse_args(); w = a.workspace.resolve(); exp = a.experiment.resolve(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    env = environment(w, exp) | {'P1998_P4_OUTPUT': str(out / 'app-state'), 'DISPLAY': '127.0.0.1:' + str(a.display), 'LD_LIBRARY_PATH': str(w / 'toolchain/display-root/usr/lib/x86_64-linux-gnu')}
    cmd = [str(godot(w)), '--audio-driver', 'Dummy', '--path', str(exp / 'runtime'), '--script', str(Path(__file__).with_name('dialog_save_qa.gd').resolve()), '--', '--p4-test-empty-base', '--qa-output=' + str(out)]
    with (out / 'xvfb.log').open('w') as log:
        display = subprocess.Popen([str(w / 'toolchain/display-root/usr/bin/Xvfb'), ':' + str(a.display), '-screen', '0', '1280x800x24', '-ac', '-nolisten', 'local', '-nolisten', 'unix', '-listen', 'tcp'], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1', 6000 + a.display), timeout=.2): break
                except OSError: time.sleep(.1)
            with (out / 'partial.log').open('w') as stream:
                app = subprocess.Popen(cmd, env=env, stdout=stream, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 55
                    while not (out / 'KILL_READY').exists():
                        if app.poll() is not None: raise RuntimeError((out / 'partial.log').read_text()[-2500:])
                        if time.monotonic() > deadline: raise TimeoutError('No partial dialog checkpoint')
                        time.sleep(.1)
                    app.kill(); killed = app.wait(timeout=5)
                finally:
                    if app.poll() is None: app.kill(); app.wait()
            with sqlite3.connect(out / 'app-state/v2/progress.db') as db:
                text, checksum = db.execute('SELECT json,sha256 FROM checkpoint WHERE slot=1').fetchone(); assert hashlib.sha256(text.encode()).hexdigest() == checksum
                c = json.loads(text)['character']; count = sum(i['Amount'] for i in c['Inventory'] if i['ItemId'] == 102)
            result = {'status': 'PASS' if count == 0 else 'FAIL', 'actual_sigkill_exit': killed,
                      'pending_source_reward_in_ui': 1, 'canonical_sabers_before_dialog_commit': count,
                      'criterion': 'Pending dialogue changes must not commit an item before its quest stage'}
            (out / 'DIALOG_SAVE.json').write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result), flush=True)
            if count != 0: raise SystemExit(1)
            with (out / 'cold.log').open('w') as stream: cold = subprocess.run(cmd + ['--dialog-cold'], env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=30)
            assert cold.returncode == 0, (out / 'cold.log').read_text()[-2500:]
        finally:
            display.terminate()
            try: display.wait(timeout=5)
            except subprocess.TimeoutExpired: display.kill(); display.wait()


if __name__ == '__main__': main()
