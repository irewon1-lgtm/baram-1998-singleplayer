#!/usr/bin/env python3
"""Exercise save refusal in real Godot processes against isolated SQLite backups."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess


def main():
    p = argparse.ArgumentParser()
    for name in ['godot', 'experiment', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for k, v in vars(a).items(): setattr(a, k, v.resolve())
    a.output.mkdir(parents=True, exist_ok=False)
    source = a.experiment / 'qa-host/v1'
    results = []
    for kind in ['future-envelope', 'wrong-content', 'database-without-identity', 'future-character']:
        root = a.output / kind; state = root / 'v1'; state.mkdir(parents=True)
        # SQLite's backup API includes committed WAL pages. Never file-copy a DB.
        with sqlite3.connect(source / 'project1998.db') as src, sqlite3.connect(state / 'project1998.db') as dest:
            src.backup(dest); dest.execute('PRAGMA journal_mode=DELETE')
        identity = json.loads((source / 'identity.json').read_text())
        if kind == 'future-envelope': identity['schema_version'] += 1
        if kind == 'wrong-content': identity['content_sha256'] = '0' * 64
        if kind != 'database-without-identity':
            (state / 'identity.json').write_text(json.dumps(identity))
        original_json = None
        if kind == 'future-character':
            with sqlite3.connect(state / 'project1998.db') as db:
                original_json = json.loads(db.execute("SELECT json FROM characters WHERE username='p3probe'").fetchone()[0])
                original_json['SchemaVersion'] = 999
                original_json = json.dumps(original_json)
                db.execute("UPDATE characters SET json=?,unreadable_since=NULL WHERE username='p3probe'", (original_json,))
        before = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in state.iterdir() if f.is_file()}
        env = os.environ | {'P1998_P3_OUTPUT': str(root), 'GODOT_SILENCE_ROOT_WARNING': '1',
            'DOTNET_ROOT': str(Path(os.environ.get('DOTNET_ROOT', a.godot.parent)).resolve()),
            'XDG_DATA_HOME': str(root / 'xdg-data'), 'XDG_CONFIG_HOME': str(root / 'xdg-config')}
        with (root / 'process.log').open('w') as log:
            proc = subprocess.run([str(a.godot), '--headless', '--audio-driver', 'Dummy', '--path', str(a.experiment / 'runtime'),
                '--', '--p3-quit'], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        failure = json.loads((root / 'failure.json').read_text())
        protected = proc.returncode == 1 and 'EXISTING_SAVE_PROTECTED' in failure['error']
        if kind == 'future-character':
            with sqlite3.connect(state / 'project1998.db') as db:
                intact = db.execute("SELECT json FROM characters WHERE username='p3probe'").fetchone()[0] == original_json
        else:
            after = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in state.iterdir() if f.is_file()}
            intact = before == after
        result = {'case': kind, 'status': 'PASS' if protected and intact else 'FAIL',
                  'exit': proc.returncode, 'existing_state_preserved': intact, 'refused_before_replacement': protected}
        results.append(result); print(json.dumps(result), flush=True)
    report = {'status': 'PASS_HOST_OBSERVED_SCOPE' if all(x['status'] == 'PASS' for x in results) else 'FAIL', 'checks': results}
    (a.output / 'SAVE_GUARD_QA.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['status'] == 'PASS_HOST_OBSERVED_SCOPE'


if __name__ == '__main__': main()
