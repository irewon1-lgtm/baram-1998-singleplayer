#!/usr/bin/env python3
"""Recipient acquisition from pinned local originals using reviewed Work tools.

The upstream package is read only. A separate private sandbox receives copies
of fixed converter inputs. No regenerated definition is used as a new package.
Only bytes matching the *published* member pins are eligible for intake.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from baram_content import sha, encode, atomic_write

BASE = 'dea6574c9a69ebb04432d10fc32951aacd8b66cb'
BASE_FILES = ['tools/legacy_assets.py', 'tools/legacy_maps.py',
              'game/data/runtime_bindings.json']

def run(args):
    repo, package, sandbox = Path(args.repo), Path(args.package), Path(args.sandbox)
    acquisition = json.loads((package / 'acquisition.json').read_text())
    converter_name = 'build_content.py' if args.na_maps else 'build_assets.py'
    converter = package / 'toolchain' / converter_name
    if sha(converter.read_bytes()) != acquisition['rebuild']['sha256']:
        raise ValueError('Fixed converter hash mismatch')
    if sandbox.exists() and not args.verify_existing:
        raise ValueError('Use an empty recipient sandbox; upstream is never overwritten')
    sandbox.mkdir(parents=True,exist_ok=args.verify_existing)
    base_files = BASE_FILES + (['game/data/numeric.json','game/data/skill_effects.json',
                  'research/restoration-integrated-20261013/CONTENT_CATALOG.jsonl',
                  'research/restoration-integrated-20261013/NUMERIC_MASTER.jsonl',
                  'research/restoration-integrated-20261013/DROP_RULES.jsonl',
                  'docs/development/runs/20261014-assets/original-world-build.json'] if args.na_maps else [])
    for name in base_files:
        target = sandbox / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','show',BASE+':'+name], cwd=repo))
    for name in [converter_name, 'common.py']:
        target = sandbox / 'content-work/tools' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((package / 'toolchain' / name).read_bytes())
    target = sandbox / 'content-work/schemas/content-v1.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((package / 'schema/content-v1.json').read_bytes())
    output = sandbox / 'recipient-bytes'
    command = [sys.executable, str(sandbox / 'content-work/tools' / converter_name),
               '--inputs', str(Path(args.inputs).resolve()), '--private-out', str(output),
               '--batch', 'RECIPIENT_REBUILD',
               '--bundle-id', acquisition['bundle_id'], '--bundle', str(sandbox/'recipient.zip')]
    if args.na_maps:
        command += ['--na-maps', str(Path(args.na_maps).resolve())]
        destination=sandbox/'content-work/packages/WK-ASSETS-001';destination.mkdir(parents=True,exist_ok=args.verify_existing)
        for source in Path(args.assets_package).glob('content-*.jsonl'):(destination/source.name).write_bytes(source.read_bytes())
    else:command += ['--v125', str(Path(args.v125).resolve())]
    exit_code=0
    if not args.verify_existing:
        with (sandbox / 'converter.log').open('w') as log:
            exit_code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    records = [json.loads(line) for file in sorted(package.glob('content-*.jsonl'))
               for line in file.read_text().splitlines() if line.strip()]
    verified, blocked = [], []
    checked = {}
    for record in records:
        data = record['data']; pin = data.get('acquisition',data.get('layout_acquisition'))
        if not isinstance(pin,dict) or not pin.get('member'):continue
        member = pin['member']
        checks = [(member, pin['sha256'])]
        checks += [(p['path'], p['sha256']) for p in data.get('metadata',{}).get('pages', [])]
        if data.get('metadata',{}).get('atlas_member'):
            checks.append((data['metadata']['atlas_member'], data['metadata']['sha256']))
        errors = []
        for name, expected in checks:
            if name not in checked:
                file = output / name
                checked[name] = sha(file.read_bytes()) if file.is_file() else None
            if checked[name] != expected:
                errors.append(dict(member=name, expected=expected, actual=checked[name]))
        (blocked if errors else verified).append(dict(id=record['id'], errors=errors) if errors else record['id'])
    report = dict(protocol_id='BARAM_PARALLEL_V1', batch_id=acquisition['bundle_id'],
                  acquisition_method='REVIEWED_PINNED_WORK_CONVERTER_ON_EXISTING_ORIGINALS',
                  converter_sha256=sha(converter.read_bytes()), converter_exit=exit_code,
                  converter_log=str(sandbox/'converter.log'), directory=str(output),
                  verified_ids=verified, blocked=blocked,
                  verified_member_sha256={k:v for k,v in checked.items() if v is not None},
                  note='Partial member acquisition; neither complete Library ZIP acquisition nor gameplay verification.')
    archive=sandbox/'recipient.zip'
    report['bundle_hash_matches']=archive.is_file() and sha(archive.read_bytes())==acquisition['sha256'] and archive.stat().st_size==acquisition['size_bytes']
    atomic_write(args.report, encode(report))
    print('Verified member definitions', len(verified), 'blocked', len(blocked), 'converter exit', exit_code, 'whole bundle matches',report['bundle_hash_matches'])

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['repo','package','sandbox','inputs','report']:
        p.add_argument('--'+key, required=True)
    p.add_argument('--v125',default='/tmp/baram-v125-not-received.zip');p.add_argument('--na-maps');p.add_argument('--assets-package')
    p.add_argument('--verify-existing',action='store_true')
    run(p.parse_args())
