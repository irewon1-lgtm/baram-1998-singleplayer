#!/usr/bin/env python3
"""Package static evidence only; never execute acquired reference code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--research-root', type=Path, required=True)
    ap.add_argument('--asset-evidence', type=Path, required=True)
    ap.add_argument('--reference-package', type=Path, required=True)
    ap.add_argument('--source-commit', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    repo = args.repo.resolve()
    files = {}

    def add(path, name):
        if path.is_symlink():
            raise ValueError('Linked package input')
        path = path.resolve()
        parts = PurePosixPath(name).parts
        if name.startswith('/') or '..' in parts or any(x in parts for x in ['.git', '__pycache__', 'private-intake']):
            raise ValueError('Unsafe package path')
        if path.is_symlink() or not path.is_file() or name in files:
            raise ValueError('Missing, duplicate or linked input: ' + name)
        files[name] = path

    add(repo / 'AGENTS.md', 'AGENTS.md')
    for directory in ['docs/rebuild', 'tools/rebuild']:
        for p in sorted((repo / directory).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.name in ['DELIVERY_RECEIPT.json', 'DELIVERY_RECHECK_RECEIPT.json']:
                continue
            if p.suffix in ['.pyc', '.pyo']:
                continue
            add(p, p.relative_to(repo).as_posix())
    manifest = json.loads((repo / 'docs/rebuild/p1_5/INPUT_MANIFEST.json').read_text())
    reference_bytes = args.reference_package.read_bytes()
    if digest(reference_bytes) != manifest['reference_package']['sha256'] or len(reference_bytes) != manifest['reference_package']['bytes']:
        raise ValueError('Reference package does not match pinned manifest')
    add(args.reference_package, 'inputs/reference_sources.zip')

    # Original article HTML is restored separately by registered URL/hash.
    source_index = []
    # Historical visual-tool versions differ from the current reference snapshot.
    for line in (repo / 'docs/rebuild/step01/sources.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row.get('source_id') not in ['EXT-VIS-002', 'EXT-VIS-004', 'EXT-VIS-007']:
            continue
        for item in row.get('files', []):
            p = Path(item['local_path'])
            if p.is_symlink() or not p.is_file():
                raise ValueError('Missing historical visual source: ' + row['source_id'])
            raw = p.read_bytes()
            if digest(raw) != item['sha256']:
                raise ValueError('Historical visual source hash mismatch: ' + row['source_id'])
            name = 'evidence/source_bytes/' + item['sha256'] + '.bin'
            if name not in files:
                add(p, name)
            source_index.append({'source_id': row['source_id'], 'original_relative_path': item['path'], 'path': name, 'sha256': item['sha256'], 'bytes': len(raw)})
    # Only verified images are copied; failed responses stay metadata.
    from PIL import Image
    image_index = []
    for base, prefix in [(args.research_root / 'korean', 'evidence/images'), (args.asset_evidence / 'previews', 'evidence/previews')]:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in ['.gif', '.png', '.jpg', '.jpeg', '.bmp', '.pcx', '.img']:
                continue
            try:
                with Image.open(p) as im:
                    im.verify()
                raw = p.read_bytes()
            except Exception:
                continue
            sha = digest(raw)
            name = prefix + '/' + sha + p.suffix.lower()
            if name not in files:
                add(p, name)
            image_index.append({'source_cache_relative_path': p.relative_to(base).as_posix(), 'path': name, 'sha256': sha, 'bytes': len(raw)})

    for name in ['guide_effect_comparison.json', 'npc_frame_comparison.json']:
        add(args.asset_evidence / name, 'evidence/' + name)
    for name in ['Project1998-files.json', 'Project1998-tree.json', 'RTK-Server-files.json', 'RTK-Server-tree.json', 'discovery.json', 'discovery-followup.json', 'na_static_validation.json', 'reuse_check.json', 'server_failure_receipts.json', 'validation-summary-final.json', 'official-cross-era-conflicts.json', 'official-review-completeness.json', 'effect-review-final-summary.json', 'effect-review-structural-result.json', 'independent_effect_review.py', 'independent_official_check.py', 'official_completeness_check.py']:
        add(args.research_root / 'server' / name, 'evidence/server/' + name)
    for name in ['acquisition.json', 'creation_alternate_attempt.json']:
        add(args.research_root / 'korean/official' / name, 'evidence/acquisition/' + name)
    for name in ['web-acquisition.json', 'image-acquisition.json', 'target-image-acquisition.json', 'wayback-attempts.json']:
        add(args.research_root / 'korean' / name, 'evidence/acquisition/' + name)
    entries = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        def put(name, data, method=zipfile.ZIP_DEFLATED):
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.compress_type = method
            z.writestr(info, data)
            entries.append({'path': name, 'bytes': len(data), 'sha256': digest(data)})
        for name, path in sorted(files.items()):
            put(name, path.read_bytes(), zipfile.ZIP_STORED if name == 'inputs/reference_sources.zip' else zipfile.ZIP_DEFLATED)
        put('PRIVATE_IMAGE_INDEX.json', (json.dumps(image_index, ensure_ascii=False, indent=2) + '\n').encode())
        put('PRIVATE_SOURCE_INDEX.json', (json.dumps(source_index, ensure_ascii=False, indent=2) + '\n').encode())
        note = ('# P1.5 static handoff\n\nSource commit: ' + args.source_commit + '\n\n'
                'Read AGENTS.md, STATE.json, REPORT.md and NEXT_P2_DELTA.md. This package does not authorize P2 execution.\n'
                'Source values are private. Do not publish selected_content JSONL or images.\n'
                'Original 42 client/user archives remain at INPUT_MANIFEST Library IDs. Materialize exact hashes separately.\n'
                'Use tools/rebuild/p1_5/prepare_handoff_inputs.py to restore current paths. Archived article HTML is not bundled; retrieve its recorded public URL and verify its registered hash. PRIVATE_SOURCE_INDEX contains only historical visual tool source files.\n'
                'RTK raw database and credential-bearing settings, transfer receipts, .git and caches are intentionally excluded.\n'
                'The source graph contains documented NA dangling references: importer overall FAIL must remain visible.\n'
                'Runtime, devices, authentication and Codex receiver G0 are NOT_RUN.\n'
                'ZIP file ID/hash and publication checks are in the external DELIVERY_RECHECK_RECEIPT.json to avoid self-reference.\n')
        put('READ_FIRST.md', note.encode())
        wrapper = {'schema': 'baram.p1_5.package_manifest/1', 'source_commit': args.source_commit, 'files': entries,
                   'manifest_self_excluded': True, 'runtime_tests': 'NOT_RUN', 'codex_receiver': 'NOT_RUN'}
        info = zipfile.ZipInfo('PACKAGE_MANIFEST.json')
        info.external_attr = (stat.S_IFREG | 0o600) << 16
        z.writestr(info, json.dumps(wrapper, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'files': len(entries), 'images': len(image_index), 'bytes': args.output.stat().st_size,
                      'sha256': digest(args.output.read_bytes()), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
