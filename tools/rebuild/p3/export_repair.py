#!/usr/bin/env python3
"""Free local P3 remediation exports; reuse the preserved P3 exporter.

Use a separate package because the former private test key is not included in
handoffs. Original apps, user data, signing keys and P3 input bytes stay intact.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p2'))
import gameplay_platform as platform

platform.PACKAGE = 'com.irewon.baram.p3repair20261016'
platform.USER_DIR = 'baram_rebuild_p3repair_001'
_base_presets = platform.presets

def presets(templates):
    return (_base_presets(templates)
            .replace('version/code=1', 'version/code=2')
            .replace('0.1.0-p3', '0.1.1-p3-repair')
            .replace('package/name="바람의나라 P3"', 'package/name="바람의나라 P3 보수"'))

platform.presets = presets

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=['Windows', 'Android'], required=True)
    for name in ['project', 'runtime', 'godot', 'templates', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ['android-sdk', 'java-home', 'signing-root']:
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = platform.export_gameplay(args)
    path = args.output / 'EXPORT_RECEIPT.json'
    if path.exists():
        receipt = json.loads(path.read_text())
        receipt['source_equivalent_remote_commit'] = args.source_commit
        receipt['source_equivalence_evidence'] = 'source_snapshot contains actual per-file SHA256; materialized local git SHA may differ'
        receipt['install_policy'] = 'Parallel package; previous game and saves preserved; no unverified same-key update claim'
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return result

if __name__ == '__main__':
    raise SystemExit(main())
