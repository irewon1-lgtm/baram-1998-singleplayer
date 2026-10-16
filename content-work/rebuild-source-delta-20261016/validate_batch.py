"""Validate only a Work delta batch, never frozen G0/P2 data."""
import argparse, hashlib, json, stat
from pathlib import Path, PurePosixPath


def validate(root):
    root = Path(root)
    errors, checked, parsed = [], 0, 0
    def check(ok, message):
        if not ok:
            errors.append(message)
    try:
        m = json.loads((root / 'MANIFEST.json').read_text())
    except Exception as e:
        return {'result': 'FAIL', 'errors': ['manifest: ' + str(e)], 'files_checked': 0}
    check(m.get('schema') == 'baram.work_source_delta.batch/1', 'schema')
    check(m.get('base_p1_5_sha') == '590bd626b63cebf6d858c8e9c1c9ce822ea0ec94', 'P1.5 baseline')
    check(bool(m.get('input_manifest_sha256')), 'input fingerprint missing')
    check(m.get('profile_dispatch_required') is True and m.get('default_build_profile_id') is None, 'profile')
    files = m.get('files', [])
    check(bool(files), 'empty file set')
    names = [f.get('path') for f in files]
    check(len(names) == len(set(names)), 'duplicate paths')
    required = {'FIELD_CANDIDATES.jsonl', 'SOURCES.jsonl', 'README.md'}
    check(required.issubset(set(names)), 'required content missing')
    expected = set(names) | {'MANIFEST.json', 'VALIDATION.json'}
    actual = set()
    for p in root.rglob('*'):
        if p.is_symlink():
            errors.append('symlink: ' + str(p))
        elif p.is_file():
            actual.add(p.relative_to(root).as_posix())
    check(actual == expected, 'file-set mismatch: missing=' + str(sorted(expected-actual)) + ' extra=' + str(sorted(actual-expected)))
    for f in files:
        name = f.get('path', '')
        rel = PurePosixPath(name)
        check(bool(name) and not rel.is_absolute() and '..' not in rel.parts and '\\' not in name, 'unsafe path: ' + name)
        if not name or rel.is_absolute() or '..' in rel.parts or '\\' in name:
            continue
        p = root.joinpath(*rel.parts)
        if not p.is_file() or p.is_symlink():
            errors.append('missing regular file: ' + name)
            continue
        check(p.stat().st_size <= 64 * 1024 * 1024, 'oversize: ' + name)
        b = p.read_bytes()
        checked += 1
        check(len(b) == f.get('bytes'), 'length mismatch: ' + name)
        check(hashlib.sha256(b).hexdigest() == f.get('sha256'), 'hash mismatch: ' + name)
        if p.suffix in {'.json', '.jsonl'}:
            try:
                if p.suffix == '.json':
                    json.loads(b)
                    parsed += 1
                else:
                    for line in b.decode('utf8').splitlines():
                        if line.strip():
                            json.loads(line)
                            parsed += 1
            except Exception as e:
                errors.append('format: ' + name + ': ' + str(e))
        if p.suffix.lower() in {'.exe', '.ttf', '.otf', '.pfx', '.jks', '.keystore', '.sql', '.bak'}:
            errors.append('excluded type: ' + name)
        for marker in [b'-----BEGIN PRIVATE KEY-----', b'-----BEGIN RSA PRIVATE KEY-----', b'ghp_', b'sk-proj-', b'X-Amz-Signature=', b'completion_token']:
            if marker in b:
                errors.append('secret/transfer marker: ' + name)
    try:
        candidates = [json.loads(l) for l in (root / 'FIELD_CANDIDATES.jsonl').read_text().splitlines() if l.strip()]
        sources = [json.loads(l) for l in (root / 'SOURCES.jsonl').read_text().splitlines() if l.strip()]
        check(bool(candidates) and bool(sources), 'empty candidate/source records')
        ids = [r['candidate_id'] for r in candidates]
        check(len(ids) == len(set(ids)), 'duplicate candidate IDs')
        check(set(ids) == set(m.get('candidate_ids', [])), 'manifest candidate set mismatch')
        for r in candidates:
            check(bool(r.get('binding_ids')), 'binding missing: ' + r['candidate_id'])
            for b in r.get('binding_ids', []):
                check(b in m.get('valid_binding_ids', []), 'unknown binding: ' + b)
            check(r.get('selected_for_build') is False, 'unapproved adoption: ' + r['candidate_id'])
            check(bool(r.get('codex_tests')), 'observation missing: ' + r['candidate_id'])
            for ref in r.get('payload_refs', []):
                check(ref in names, 'broken payload ref: ' + ref)
        json.loads((root / 'VALIDATION.json').read_text())
    except Exception as e:
        errors.append('record references: ' + str(e))
    return {'schema': 'baram.work_source_delta.validation/1', 'result': 'FAIL' if errors else 'PASS',
        'scope': 'Work batch required set/bytes/SHA256/JSON/declared binding and payload references only',
        'files_checked': checked, 'records_parsed': parsed, 'errors': errors,
        'historical_accuracy': 'PARTIAL_NOT_A_GLOBAL_PASS', 'runtime': 'NOT_RUN', 'Codex_G0_P2': 'NOT_RUN'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--content', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = validate(a.root)
    from verify_evidence_refs import verify
    evidence = verify(a.root, a.baseline, a.content)
    result['evidence_references'] = evidence
    result['result'] = 'PASS' if result['result'] == 'PASS' and evidence['result'] == 'PASS' else 'FAIL'
    result['scope'] += '; fixed external baseline IDs and declared private evidence references'
    s = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if a.output:
        a.output.write_text(s)
    print(s, end='')
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
