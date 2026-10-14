#!/usr/bin/env python3
"""Restore a private runtime seed with byte-level integrity and safe extraction."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

LIMIT = 512 * 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def restore(vault, output):
    vault, output = Path(vault).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Previous runtime must be preserved; choose a fresh destination')
    manifest = json.loads((vault / 'private-runtime-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'BARAM_PRIVATE_RUNTIME_CHUNKS_V1':
        raise ValueError('Unknown private input format')
    parts = manifest.get('parts', [])
    if not parts or len(parts) > 64 or not 0 < manifest['archive_bytes'] <= LIMIT:
        raise ValueError('Invalid private input size or part count')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='baram-input-', dir=output.parent) as temporary:
        root = Path(temporary)
        archive = root / 'input.zip'
        total = 0
        with archive.open('wb') as target:
            for index, part in enumerate(parts):
                if part['file'] != f'baram-private-runtime.part{index:03d}':
                    raise ValueError('Private input parts must be contiguous safe basenames')
                source = vault / part['file']
                if source.stat().st_size != part['bytes'] or digest(source) != part['sha256']:
                    raise ValueError('Private input part integrity failure')
                total += source.stat().st_size
                if total > LIMIT:
                    raise ValueError('Private input exceeds size limit')
                with source.open('rb') as stream:
                    shutil.copyfileobj(stream, target)
        if total != manifest['archive_bytes'] or digest(archive) != manifest['archive_sha256']:
            raise ValueError('Complete private input integrity failure')
        extracted = root / 'extracted'
        with zipfile.ZipFile(archive) as package:
            seen = set()
            expanded = 0
            for member in package.infolist():
                path = PurePosixPath(member.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in member.filename
                        or ':' in member.filename or member.filename in seen
                        or ((member.external_attr >> 16) & 0o170000) == 0o120000):
                    raise ValueError('Unsafe or duplicate private input member')
                seen.add(member.filename)
                expanded += member.file_size
                if expanded > LIMIT:
                    raise ValueError('Expanded private input exceeds size limit')
                if path.parts and path.parts[0] == 'runtime':
                    package.extract(member, extracted)
                elif member.filename not in ('README.txt', 'README.md', '.gitattributes'):
                    raise ValueError('Unexpected private input member')
            if package.testzip() is not None:
                raise ValueError('Private input ZIP CRC failure')
        runtime = extracted / 'runtime'
        if not (runtime / 'PACKAGE_MANIFEST.json').is_file() or not (runtime / 'template-win64.exe').is_file():
            raise ValueError('Required private runtime input is missing')
        runtime.rename(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--vault', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    restore(args.vault, args.out)
    print('PRIVATE_RUNTIME_RESTORED: all part/archive hashes and ZIP safety checks passed')
