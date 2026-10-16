#!/usr/bin/env python3
"""Verify every core/part input and optionally restore the inert reference ZIP."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile


def identity(stream, sink=None):
    h, n = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024**2), b''):
        h.update(block)
        n += len(block)
        if sink:
            sink.write(block)
    return h.hexdigest(), n


def verify(core, parts_dir, restore=None):
    with zipfile.ZipFile(core) as z:
        infos = z.infolist()
        names = [x.filename for x in infos]
        if not names or len(names) != len(set(names)) or sum(x.file_size for x in infos) > 2 * 1024**3:
            raise ValueError('Invalid core set or bounds')
        for x in infos:
            p = PurePosixPath(x.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in x.filename or stat.S_ISLNK(x.external_attr >> 16):
                raise ValueError('Unsafe core path')
        manifest = json.loads(z.read('PACKAGE_MANIFEST.json'))
        expected = {x['path']: x for x in manifest['files']}
        if len(expected) != len(manifest['files']) or set(names) - {'PACKAGE_MANIFEST.json'} != set(expected):
            raise ValueError('Core manifest set mismatch')
        for name, item in expected.items():
            with z.open(name) as stream:
                h, n = identity(stream)
            if h != item['sha256'] or n != item['bytes']:
                raise ValueError('Core byte mismatch: ' + name)
        catalogs = json.loads(z.read('docs/rebuild/p1_5/INPUT_MANIFEST.json'))
        for item in catalogs['normalized_catalogs']:
            entry = expected['docs/rebuild/p1_5/' + item['path']]
            if entry['sha256'] != item['sha256'] or entry['bytes'] != item['bytes']:
                raise ValueError('Required normalized input mismatch')
        external = manifest.get('external_inputs', [])
        if len(external) != 1 or not external[0].get('parts'):
            raise ValueError('Exact external reference declaration required')
        ref = external[0]
        pin = catalogs['reference_package']
        if any(ref[k] != pin[k] for k in ['path', 'sha256', 'bytes']):
            raise ValueError('External reference pin mismatch')
        declared = ref['parts']
        wanted = [x['file_name'] for x in declared]
        if len(wanted) != len(set(wanted)) or any('/' in n or '\\' in n or not n.endswith('.part' + str(i).zfill(3)) for i, n in enumerate(wanted, 1)):
            raise ValueError('Invalid ordered part declarations')
        actual = {x.name for x in parts_dir.glob('BARAM_P1_5_reference_sources.zip.part*') if x.is_file()}
        if actual - set(wanted):
            raise ValueError('Unexpected reference part')
        missing = set(wanted) - actual
        if missing:
            raise FileNotFoundError('Required reference parts missing: ' + ','.join(sorted(missing)))
        combined, count = hashlib.sha256(), 0
        for item in declared:
            p = parts_dir / item['file_name']
            if p.is_symlink():
                raise ValueError('Linked part input')
            with p.open('rb') as f:
                h = hashlib.sha256()
                n = 0
                for block in iter(lambda: f.read(1024**2), b''):
                    h.update(block)
                    combined.update(block)
                    n += len(block)
            if h.hexdigest() != item['sha256'] or n != item['bytes']:
                raise ValueError('Reference part byte mismatch: ' + item['file_name'])
            count += n
        if combined.hexdigest() != ref['sha256'] or count != ref['bytes']:
            raise ValueError('Combined reference identity mismatch')
        restored = 'NOT_REQUESTED'
        if restore:
            if restore.exists():
                with restore.open('rb') as f:
                    h, n = identity(f)
                if h != ref['sha256'] or n != ref['bytes']:
                    raise ValueError('Existing output differs; preserved without overwrite')
                restored = 'REUSED_EXACT_HASH'
            else:
                restore.parent.mkdir(parents=True, exist_ok=True)
                temporary = restore.with_name(restore.name + '.p15-tmp')
                with temporary.open('xb') as out:
                    for item in declared:
                        with (parts_dir / item['file_name']).open('rb') as f:
                            identity(f, out)
                with temporary.open('rb') as f:
                    h, n = identity(f)
                if h != ref['sha256'] or n != ref['bytes']:
                    raise ValueError('Restored reference mismatch; original output untouched')
                temporary.rename(restore)
                restored = 'PASS_NEW_FILE'
        return {'result': 'PASS_DELIVERY_SET_SCOPE', 'core_files_checked': len(expected), 'normalized_files': len(catalogs['normalized_catalogs']), 'normalized_rows': sum(x['records'] for x in catalogs['normalized_catalogs']), 'required_parts': len(declared), 'parts_read': len(declared), 'reference_sha256': ref['sha256'], 'reference_bytes': count, 'restored_reference': restored, 'runtime': 'NOT_RUN', 'Codex_G0': 'NOT_RUN'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--core', type=Path, required=True)
    ap.add_argument('--parts-dir', type=Path, required=True)
    ap.add_argument('--restore-reference-to', type=Path)
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    code = 0
    try:
        result = verify(a.core, a.parts_dir, a.restore_reference_to)
    except (FileNotFoundError, ValueError, KeyError, OSError, zipfile.BadZipFile) as e:
        result = {'result': 'BLOCKED' if isinstance(e, FileNotFoundError) else 'FAIL', 'reason': str(e), 'runtime': 'NOT_RUN'}
        code = 1
    result['observed_exit_code'] = code
    if a.output:
        a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
