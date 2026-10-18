#!/usr/bin/env python3
"""Run path regressions in real Godot processes, including a prior-v1 save.

The empty-base fixture changes the real .NET AppContext value on Linux. It is
targeted regression evidence, not Android or physical-device execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess


def main():
    parser = argparse.ArgumentParser()
    for name in ['godot', 'experiment', 'previous', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for key, value in vars(args).items(): setattr(args, key, value.resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    previous = args.previous / 'qa-host/v1'
    expected = json.loads((previous / 'identity.json').read_text())
    capsule = (args.experiment / 'runtime/capsule.json').read_bytes()
    assert hashlib.sha256(capsule).hexdigest() == expected['content_sha256']
    results = []

    def run(name, override, existing=False, should_pass=True):
        root = args.output / name; root.mkdir()
        if existing:
            state = root / 'v1'; state.mkdir()
            shutil.copyfile(previous / 'identity.json', state / 'identity.json')
            with sqlite3.connect(previous / 'project1998.db') as source, sqlite3.connect(state / 'project1998.db') as target:
                source.backup(target); target.execute('PRAGMA journal_mode=DELETE')
        env = os.environ | {'P1998_P3_OUTPUT': str(root) if override is None else override,
            'GODOT_SILENCE_ROOT_WARNING': '1', 'XDG_DATA_HOME': str(root / 'xdg-data'),
            'XDG_CONFIG_HOME': str(root / 'xdg-config')}
        command = [str(args.godot), '--headless', '--audio-driver', 'Dummy', '--path',
                   str(args.experiment / 'runtime'), '--', '--p3-test-empty-base', '--p3-quit']
        receipts = []
        for attempt in range(2 if should_pass else 1):
            with (root / f'process-{attempt + 1}.log').open('w') as log:
                process = subprocess.run(command, env=env, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            matches = list(root.rglob('verification.json' if should_pass else 'failure.json'))
            assert len(matches) == 1, (name, matches)
            record = matches[0]; receipt = json.loads(record.read_text()); receipts.append(receipt)
            if should_pass:
                assert process.returncode == 0 and receipt['original_parity'] and receipt['steps'] == 40
                assert receipt['empty_base_directory'] and receipt['deployment_root_explicit']
                assert receipt['sqlite_round_trip'] and receipt['sqlite_online_backup'] and not receipt['world_started']
                if existing or attempt:
                    assert receipt['cold_existing_save'] == 'Ok' and receipt['cold_hp'] == 39
                actual_identity = json.loads((record.parent / 'v1/identity.json').read_text())
                assert actual_identity == expected, 'Save identity changed'
                if override is not None:
                    assert record.is_relative_to(root / 'xdg-data'), 'Fallback escaped sandbox'
            else:
                assert process.returncode == 1 and receipt['stage'] == 'paths'
                assert 'absolute, non-empty sandbox path' in receipt['error']
                assert not (root / override).exists(), 'Rejected relative root was created'
                assert not list(root.rglob('project1998.db')), 'Store initialized after rejected root'
        result = {'case': name, 'status': 'PASS', 'platform': 'Linux', 'empty_base_fixture': should_pass,
                  'processes': len(receipts), 'prior_v1_save': existing,
                  'last_receipt': receipts[-1], 'android_runtime': 'NOT_RUN_AFTER_FIX'}
        results.append(result); print(json.dumps(result), flush=True)

    run('empty-base-existing-v1', None, existing=True)
    run('blank-output-sandbox-fallback', '   ')
    run('relative-output-refused-with-diagnostic', 'relative-output', should_pass=False)
    (args.output / 'PATH_QA.json').write_text(json.dumps({'status': 'PASS_HOST_FIXTURES_ONLY',
        'unchanged_capsule_sha256': hashlib.sha256(capsule).hexdigest(), 'checks': results}, indent=2) + '\n')


if __name__ == '__main__': main()
