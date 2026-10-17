#!/usr/bin/env python3
"""Hash every actual signed APK member using indexed ZIP reads for pack parity."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['android-export', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--comparison-blob', type=Path,
        help='Optional exact decompressed private-runtime/compiled-script byte stream for indexed direct equality')
    args = parser.parse_args()
    receipt = json.loads((args.android_export / 'EXPORT_RECEIPT.json').read_text())
    artifact = receipt['artifact']
    apk = Path(artifact['path']).resolve()
    if (receipt['result'] != 'PASS_EXPORT_ONLY' or receipt['target'] != 'Android'
            or apk.parent != args.android_export.resolve() or apk.stat().st_size != artifact['bytes']
            or digest(apk) != artifact['sha256'] or not receipt['final_apk_signer_matches_retained']):
        raise ValueError('Exact successful signed APK receipt required')
    files = {}
    blob = args.comparison_blob.open('xb') if args.comparison_blob else None
    try:
        with zipfile.ZipFile(apk) as zipped:
            for row in zipped.infolist():
                name = row.filename
                if name in files or name.startswith('/') or '..' in PurePosixPath(name).parts or '\\' in name:
                    raise ValueError('Duplicate or unsafe APK member')
                data = zipped.read(row)
                files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                if blob and name.startswith('assets/') and (name.startswith('assets/private_runtime/') or name.endswith('.gdc')) and not name.endswith('/'):
                    files[name]['comparison_blob_offset'] = blob.tell()
                    blob.write(data)
    finally:
        if blob:
            blob.close()
    if digest(apk) != artifact['sha256']:
        raise ValueError('Signed APK changed during manifest generation')
    result = {'schema': 'baram.g2.r16.actual-apk-members/1', 'status': 'PASS_MANIFEST_ONLY',
        'source_commit': receipt['source_commit'], 'artifact': artifact, 'files': files,
        'member_count': len(files), 'native_execution': 'NOT_RUN',
        'scope': 'Every exact signed APK member decompressed and hashed with indexed ZIP access; actual PCK equality is separately checked by Godot'}
    if args.comparison_blob:
        result['comparison_blob'] = {'path': str(args.comparison_blob.resolve()),
            'bytes': args.comparison_blob.stat().st_size, 'sha256': digest(args.comparison_blob),
            'scope': 'Exact decompressed signed-APK private-runtime and compiled-script bytes, indexed per actual member; never a game artifact'}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'members': len(files), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
