#!/usr/bin/env python3
"""Execute the default C#/GDScript scene, real GUI fixtures and a cold process."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    for name in ['godot', 'experiment', 'previous', 'output', 'xvfb', 'display-library']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for key, value in vars(args).items(): setattr(args, key, value.resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    state = args.output / 'app-state/v1'; state.mkdir(parents=True)
    prior = args.previous / 'qa-host/v1'
    shutil.copyfile(prior / 'identity.json', state / 'identity.json')
    shutil.copyfile(prior / 'p3-v1.backup.db', state / 'p3-v1.backup.db')
    probe_backup_hash = hashlib.sha256((state / 'p3-v1.backup.db').read_bytes()).hexdigest()
    with sqlite3.connect(prior / 'project1998.db') as source, sqlite3.connect(state / 'project1998.db') as target:
        source.backup(target); target.execute('PRAGMA journal_mode=DELETE')
        original_probe = target.execute("SELECT json FROM characters WHERE username='p3probe'").fetchone()[0]
    env = os.environ | {'DISPLAY': '127.0.0.1:104', 'LD_LIBRARY_PATH': str(args.display_library),
        'P1998_P3_OUTPUT': str(state.parent), 'XDG_DATA_HOME': str(args.output / 'xdg-data'),
        'XDG_CONFIG_HOME': str(args.output / 'xdg-config'), 'GODOT_SILENCE_ROOT_WARNING': '1'}
    command = [str(args.godot), '--audio-driver', 'Dummy', '--path', str(args.experiment / 'runtime')]
    scripts = Path(__file__).parent

    def run(name, script, extra=None):
        with (args.output / (name + '.log')).open('w') as log:
            result = subprocess.run(command + ['--script', str(script), '--', '--p3-test-empty-base',
                '--qa-output=' + str(args.output)] + (extra or []), env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        if result.returncode:
            print((args.output / (name + '.log')).read_text()[-4500:])
        assert result.returncode == 0, name

    with (args.output / 'xvfb.log').open('w') as log:
        display = subprocess.Popen([str(args.xvfb), ':104', '-screen', '0', '1280x800x24', '-ac',
            '-nolisten', 'local', '-nolisten', 'unix', '-listen', 'tcp'], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1', 6104), timeout=.2): break
                except OSError: time.sleep(.1)
            run('gui', scripts / 'play_qa.gd')
            gui = json.loads((args.output / 'VIEW_QA.json').read_text()); assert gui['status'] == 'PASS'
            expected = args.output / 'expected-player.json'
            shutil.copyfile(state.parent / 'play-state.json', expected)
            env.update(P1998_P3_EXPECTED=str(expected), P1998_P3_COLD_OUTPUT=str(args.output))
            run('cold', scripts / 'cold_view_qa.gd')
            cold = json.loads((args.output / 'COLD_QA.json').read_text()); assert cold['status'] == 'PASS'
            with sqlite3.connect(state / 'project1998.db') as db:
                assert db.execute("SELECT json FROM characters WHERE username='p3probe'").fetchone()[0] == original_probe
            assert hashlib.sha256((state / 'p3-v1.backup.db').read_bytes()).hexdigest() == probe_backup_hash
            with sqlite3.connect(state / 'p3-player-v1.backup.db') as db:
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert db.execute("SELECT json FROM characters WHERE username='p3player'").fetchone()
            # Real default startup must refuse a future player without overwriting it.
            protected = args.output / 'future-player/v1'; protected.mkdir(parents=True)
            shutil.copyfile(state / 'identity.json', protected / 'identity.json')
            with sqlite3.connect(state / 'project1998.db') as source, sqlite3.connect(protected / 'project1998.db') as target:
                source.backup(target); target.execute('PRAGMA journal_mode=DELETE')
                unknown = json.loads(target.execute("SELECT json FROM characters WHERE username='p3player'").fetchone()[0])
                unknown['SchemaVersion'] = 999; unknown = json.dumps(unknown)
                target.execute("UPDATE characters SET json=?,unreadable_since=NULL WHERE username='p3player'", (unknown,))
            env.update(P1998_P3_OUTPUT=str(protected.parent), P1998_P3_CAPTURE=str(args.output / '04-protected.png'))
            run('future-player', scripts / 'capture.gd')
            failure = json.loads((protected.parent / 'failure.json').read_text())
            assert failure['stage'] == 'world-scene' and 'EXISTING_SAVE_PROTECTED' in failure['error']
            with sqlite3.connect(protected / 'project1998.db') as db:
                assert db.execute("SELECT json FROM characters WHERE username='p3player'").fetchone()[0] == unknown
            report = {'status': 'PASS_HOST_GUI_AND_COLD_SCOPE', 'gui_checks': len(gui['checks']),
                      'cold_process': 'PASS', 'prior_probe_json_preserved': True,
                      'prior_probe_backup_preserved': True, 'separate_player_backup_integrity': 'ok',
                      'future_player_refused_without_overwrite': True, 'android_map_runtime': 'NOT_RUN_DEVICE_MAP_LINK'}
            (args.output / 'SUMMARY.json').write_text(json.dumps(report, indent=2) + '\n'); print(json.dumps(report))
        finally:
            display.terminate()
            try: display.wait(timeout=5)
            except subprocess.TimeoutExpired: display.kill(); display.wait()


if __name__ == '__main__': main()
