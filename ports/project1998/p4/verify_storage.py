#!/usr/bin/env python3
"""Actual SIGKILL/restart, SQLite integrity, future/corrupt refusal, P3 isolation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import time
from tooling import environment, godot


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ['workspace', 'experiment', 'output']: p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); w = a.workspace.resolve(); exp = a.experiment.resolve(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    scripts = Path(__file__).resolve().parent
    legacy = out / 'user-data/p3'; shutil.copytree(w / 'p1998-private/p3/experiment-9/qa-host', legacy)
    legacy_hashes = {str(f.relative_to(legacy)): digest(f) for f in legacy.rglob('*') if f.is_file()}
    state = out / 'user-data/p4'; env = environment(w, exp) | {'DISPLAY': '127.0.0.1:108',
        'LD_LIBRARY_PATH': str(w / 'toolchain/display-root/usr/lib/x86_64-linux-gnu'), 'P1998_P4_OUTPUT': str(state)}
    base = [str(godot(w)), '--audio-driver', 'Dummy', '--path', str(exp / 'runtime')]
    def command(script, output, headless=False):
        return base + (['--headless'] if headless else []) + ['--script', str(scripts / script), '--', '--p4-test-empty-base', '--qa-output=' + str(output)]
    with (out / 'xvfb.log').open('w') as display_log:
        display = subprocess.Popen([str(w / 'toolchain/display-root/usr/bin/Xvfb'), ':108', '-screen', '0', '1280x800x24', '-ac', '-nolisten', 'local', '-nolisten', 'unix', '-listen', 'tcp'], env=env, stdout=display_log, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1', 6108), timeout=.2): break
                except OSError: time.sleep(.1)
            with (out / 'controls.log').open('w') as log:
                app = subprocess.Popen(command('controls_qa.gd', out), env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 220
                    while not (out / 'KILL_READY').exists():
                        if app.poll() is not None: raise RuntimeError('Controls failed: ' + (out / 'controls.log').read_text()[-3000:])
                        if time.monotonic() > deadline: raise TimeoutError('Controls did not reach the kill point')
                        time.sleep(.1)
                    time.sleep(.17); app.kill(); killed = app.wait(timeout=5); assert killed == -9
                finally:
                    if app.poll() is None: app.kill(); app.wait()
            controls = json.loads((out / 'CONTROLS.json').read_text()); assert controls['status'] == 'PASS'
            with sqlite3.connect(state / 'v1/progress.db') as db:
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                rows = db.execute('SELECT slot,json,sha256 FROM checkpoint ORDER BY slot').fetchall(); assert [r[0] for r in rows] == [1, 2]
                for _, value, checksum in rows: assert hashlib.sha256(value.encode()).hexdigest() == checksum
                checkpoint = json.loads(rows[0][1])
            current_map = checkpoint['character']['Map']; world = checkpoint['world']
            actors = sorted([{'id': m['data']['Id'], 'key': m['data']['Key'], 'x': m['data']['X'], 'y': m['data']['Y'], 'hp': m['data']['Hp'], 'max_hp': m['data']['MaxHp']}
                             for m in world['mobs'] if m['map'] == current_map], key=lambda x: x['id'])
            loot = sorted([{'id': m['item']['Id'], 'key': 'rabbit_meat', 'x': m['item']['X'], 'y': m['item']['Y'], 'amount': m['item']['Amount']}
                           for m in world['loot'] if m['map'] == current_map], key=lambda x: x['id'])
            assert loot and all(m['item']['ItemId'] == 10012 for m in world['loot'] if m['map'] == current_map), 'This natural control run only kills rabbits'
            (out / 'expected.json').write_text(json.dumps({'character': checkpoint['character'], 'revision': checkpoint['revision'], 'actors': actors, 'loot': loot}))
            with (out / 'cold.log').open('w') as log: cold = subprocess.run(command('cold_qa.gd', out), env=env, stdout=log, stderr=subprocess.STDOUT, timeout=35)
            assert cold.returncode == 0, (out / 'cold.log').read_text()[-2500:]
            guards = []
            for label in ['future_identity', 'future_checkpoint', 'future_character', 'future_world', 'bad_checksum', 'unknown_cache']:
                case = out / label; target = case / 'state'; (target / 'v1').mkdir(parents=True)
                shutil.copyfile(state / 'v1/identity.json', target / 'v1/identity.json')
                with sqlite3.connect(state / 'v1/progress.db') as original, sqlite3.connect(target / 'v1/progress.db') as copy:
                    original.backup(copy); copy.execute('PRAGMA journal_mode=DELETE')
                    value = json.loads(copy.execute('SELECT json FROM checkpoint WHERE slot=1').fetchone()[0])
                    if label == 'future_checkpoint': value['schema_version'] = 999
                    if label == 'future_character': value['character']['SchemaVersion'] = 999
                    if label == 'future_world': value['world']['schema_version'] = 999
                    text = json.dumps(value); checksum = hashlib.sha256(text.encode()).hexdigest()
                    if label == 'bad_checksum': checksum = '0' * 64
                    copy.execute('UPDATE checkpoint SET json=?,sha256=? WHERE slot=1', (text, checksum)); copy.commit()
                if label == 'future_identity':
                    identity = json.loads((target / 'v1/identity.json').read_text()); identity['schema_version'] = 999
                    (target / 'v1/identity.json').write_text(json.dumps(identity))
                if label == 'unknown_cache':
                    (target / 'cache').mkdir(); (target / 'cache/foreign.txt').write_text('must not be erased')
                before = digest(target / 'v1/progress.db')
                with (case / 'guard.log').open('w') as log:
                    r = subprocess.run(command('guard_qa.gd', case, True), env=env | {'P1998_P4_OUTPUT': str(target)}, stdout=log, stderr=subprocess.STDOUT, timeout=35)
                report = json.loads((case / 'GUARD.json').read_text())
                assert r.returncode == 0 and report['status'] == 'PASS' and digest(target / 'v1/progress.db') == before, label
                if label == 'unknown_cache': assert (target / 'cache/foreign.txt').read_text() == 'must not be erased'
                guards.append({'name': label, 'status': 'PASS', 'database_unchanged': True})
            assert legacy_hashes == {str(f.relative_to(legacy)): digest(f) for f in legacy.rglob('*') if f.is_file()}
            result = {'status': 'PASS_HOST_STORAGE_SCOPE', 'actual_sigkill_exit': killed, 'save_loop_active_before_kill': True,
                      'sqlite_integrity': 'ok', 'current_and_previous_checkpoint_checksums': 'PASS', 'cold': json.loads((out / 'COLD.json').read_text())['checks'],
                      'controls': len(controls['checks']), 'guards': guards, 'prior_p3_files_preserved': len(legacy_hashes), 'native_android': 'NOT_RUN_DEVICE_P4'}
            (out / 'STORAGE.json').write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result))
        finally:
            display.terminate()
            try: display.wait(timeout=5)
            except subprocess.TimeoutExpired: display.kill(); display.wait()


if __name__ == '__main__': main()
