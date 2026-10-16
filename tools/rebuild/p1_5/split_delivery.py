#!/usr/bin/env python3
"""Make a small handoff ZIP plus exact reference ZIP parts; execute no sources."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--full-package', required=True, type=Path)
    ap.add_argument('--output-dir', required=True, type=Path)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    with zipfile.ZipFile(args.full_package) as src:
        if len(src.infolist()) > 20000 or sum(i.file_size for i in src.infolist()) > 2 * 1024**3:
            raise ValueError('Package bounds exceeded')
        for info in src.infolist():
            p = PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Unsafe package member')
        old = json.loads(src.read('PACKAGE_MANIFEST.json'))
        ref_name = 'inputs/reference_sources.zip'
        expected = next(x for x in old['files'] if x['path'] == ref_name)
        combined = hashlib.sha256()
        with src.open(ref_name) as stream:
            number = 1
            while True:
                raw = stream.read(40 * 1024**2)
                if not raw:
                    break
                name = 'BARAM_P1_5_reference_sources.zip.part' + str(number).zfill(3)
                path = args.output_dir / name
                path.write_bytes(raw)
                combined.update(raw)
                parts.append({'file_name': name, 'bytes': len(raw), 'sha256': sha(raw)})
                number += 1
        if combined.hexdigest() != expected['sha256'] or sum(x['bytes'] for x in parts) != expected['bytes']:
            raise ValueError('Reference archive identity mismatch')
        note = src.read('READ_FIRST.md').decode()
        note += ('\n## Delivery in four files\n\n'
                 'This ZIP contains all35 normalized files, code, reports and visual evidence. The large reference archive is an external exact-byte input.\n'
                 'Download the three BARAM_P1_5_reference_sources.zip.part001..003 files by IDs in the repository DELIVERY_RECEIPT.json.\n'
                 'Join them in numeric order as inputs/reference_sources.zip. Compare every part SHA and the full SHA below before opening.\n'
                 'The full original reference archive SHA256 is ' + expected['sha256'] + '.\n'
                 'Its expected byte length is ' + str(expected['bytes']) + '.\n'
                 'The original acquired source files, normalized data and their hashes were not changed by splitting.\n'
                 'PACKAGE_MANIFEST.external_inputs records every part. Missing parts remain BLOCKED, never synthesized.\n'
                 'No original client archive, raw RTK account database or transfer receipt is in these files.\n')
        target = args.output_dir / 'BARAM_P1_5_handoff_20261016.zip'
        entries = []
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
            for info in src.infolist():
                if info.filename in [ref_name, 'PACKAGE_MANIFEST.json']:
                    continue
                raw = note.encode() if info.filename == 'READ_FIRST.md' else src.read(info)
                dst.writestr(info, raw)
                entries.append({'path': info.filename, 'bytes': len(raw), 'sha256': sha(raw)})
            old.update(files=entries, external_inputs=[dict(expected, delivery='JOIN_ORDERED_PARTS', parts=parts)],
                       original_full_package_sha256=sha(args.full_package.read_bytes()),
                       delivery_scope='Core payload plus exact external reference parts; full source content and normalized data unchanged')
            dst.writestr('PACKAGE_MANIFEST.json', json.dumps(old, ensure_ascii=False, indent=2) + '\n')
    result = {'core': {'file_name': target.name, 'bytes': target.stat().st_size, 'sha256': sha(target.read_bytes())},
              'external_reference': dict(expected, parts=parts), 'reconstruction_hash_check': 'PASS',
              'source_commit': old['source_commit'], 'runtime': 'NOT_RUN'}
    (args.output_dir / 'split_delivery_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
