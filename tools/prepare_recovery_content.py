#!/usr/bin/env python3
"""Reconstructed recovery helper; the lost original Python was not recovered.

This implementation is based on the retained conversation patches and pinned
Work packages. Its tests and receipts must be executed afresh. Data activation
does not assert gameplay or device validation.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from baram_content import PackageStore, atomic_write, decode, encode, git_bytes, snapshot_package, sha, HEX64
from import_work_content import ROOT, baseline, execute

WORK_COMMIT = 'c919cf1bdffe0e318d4058dc3fc17be4a2844203'
BASELINE_RELEASE = '9e30ec651489a4f5bdbf5c4e727a41a3c7a2b2825a373262056c1e896a82fb7c'
CANDIDATE_RELEASE = 'cd0c680ab5fc8fb223ef2d14ff0b991b18e3e100fecba693bd608040f8a66e57'


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def release_pointer(runtime, ident):
    if not isinstance(ident, str) or not HEX64.fullmatch(ident):
        raise ValueError('Expected a full immutable release hash')
    raw = (Path(runtime)/'private_content/releases'/ident/'release.json').read_bytes()
    if sha(raw) != ident:
        raise ValueError('Release bytes disagree with their immutable hash')
    release = decode(raw)
    return dict(format='BARAM_ACTIVE_CONTENT', version=1, release_id=ident,
                sha256=ident, bytes=len(raw), generation=release['generation'])


def input_fingerprint(root):
    return {p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=file_sha(p))
            for p in sorted(Path(root).rglob('*')) if p.is_file()}


def verify_ledger(repo, release, work_commit):
    index_raw = git_bytes(repo, work_commit, 'content-work/HANDOFF_INDEX.json')
    index = decode(index_raw)
    expected = {p['batch_id']:p for p in index['packages']}
    checks = []
    for batch in [f'WK-CONTENT-{n:03d}' for n in range(1,11)]+['WK-ASSETS-001','WK-ASSETS-002','WK-ASSETS-003']:
        actual = release['imports'].get(batch, {})
        pinned = expected[batch]
        allowed = ('IMPORTED','PARTIALLY_IMPORTED') if batch=='WK-ASSETS-001' else ('IMPORTED',)
        ok = (actual.get('status') in allowed
              and actual.get('manifest_sha256') == pinned['manifest_sha256']
              and actual.get('source_commit') == pinned.get('source_commit', pinned.get('package_commit')))
        checks.append(dict(batch_id=batch, status='PASS' if ok else 'FAIL',
                           import_status=actual.get('status', 'NOT_IMPORTED')))
    return checks, sha(index_raw)


def semantic_content(release):
    """Only the consumer code commit is expected to change on reproduction."""
    result = json.loads(encode(release))
    for imported in result['imports'].values():
        imported.pop('applied_before_game_commit', None)
    return result


def run_import(repo, runtime, evidence, work_commit, private_assets=None):
    private_assets = private_assets or runtime/'private_assets'
    original = PackageStore(runtime/'private_content', baseline(repo, private_assets)).load()
    selections = []
    for batch, imported in original['imports'].items():
        if imported.get('status') != 'PARTIALLY_IMPORTED':
            continue
        # Preserve only the established asset gap. A partial content package
        # must be completed by this import and cannot silently pass as old.
        if batch != 'WK-ASSETS-001':
            continue
        path = evidence/(batch+'-preserved-selection.json')
        atomic_write(path, encode(imported['applied_ids']))
        selections.append(batch+'='+str(path))
    report_path = evidence/'work-import.json'
    execute(SimpleNamespace(repo=str(repo), work_commit=work_commit,
            runtime_root=str(runtime/'private_content'), private_assets=str(private_assets),
            bundle=[], members=[], selection=selections, reconcile_npc=True,
            staging_root=str(runtime.parent), receipts=str(evidence/'receipts'), report=str(report_path)))
    return json.loads(report_path.read_text(encoding='utf-8'))


def verify_existing(args):
    """Read-only candidate inspection. No importer or runtime file is written."""
    repo, runtime = Path(args.repo).resolve(), Path(args.runtime).resolve()
    before = input_fingerprint(runtime)
    from windows_ci import validate_runtime
    validate_runtime(runtime)
    store = PackageStore(runtime/'private_content', baseline(repo, runtime/'private_assets'))
    release = store.load()
    checks, index_hash = verify_ledger(repo, release, args.work_commit)
    pinned_candidate = store.pointer()['release_id'] == args.expected_release
    package_receipts=[]
    if all(c['status']=='PASS' for c in checks):
        index=decode(git_bytes(repo,args.work_commit,'content-work/HANDOFF_INDEX.json'))
        store.selection={'WK-ASSETS-001':release['imports']['WK-ASSETS-001']['applied_ids']}
        report_parent=Path(args.report).resolve().parent
        report_parent.mkdir(parents=True,exist_ok=True)
        game_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        with tempfile.TemporaryDirectory(prefix='verify-work-',dir=report_parent) as staging:
            for entry in index['packages']:
                batch=entry['batch_id']
                if batch not in release['imports']:continue
                source_commit=entry.get('source_commit',entry.get('package_commit'))
                package,schema_root=snapshot_package(repo,source_commit,entry['manifest_path'],Path(staging)/batch)
                if sha((package/'manifest.json').read_bytes())!=entry['manifest_sha256']:
                    raise ValueError('Work index manifest pin mismatch')
                receipt=store.import_package(package,source_commit,game_commit,schema_root=schema_root)
                if receipt['import_status']!='ALREADY_IMPORTED':
                    raise ValueError('Read-only candidate verification must not activate data')
                package_receipts.append(receipt)
    unchanged = before == input_fingerprint(runtime)
    result = dict(status='PASS' if all(c['status']=='PASS' for c in checks) and pinned_candidate and unchanged else 'FAIL',
                  scope='READ_ONLY_CANDIDATE_HASH_AND_LEDGER_NOT_REBUILD_OR_GAMEPLAY',
                  implementation_origin='RECONSTRUCTED_PYTHON_ORIGINAL_RAW_SOURCE_NOT_RECOVERED',
                  work_commit=args.work_commit, handoff_index_sha256=index_hash,
                  active=store.pointer(), expected_release=args.expected_release,
                  exact_candidate_release=pinned_candidate, source_files_unchanged=unchanged,
                  source_file_count=len(before), checks=checks, package_receipts=package_receipts,
                  gameplay='NOT_RUN', rebuild='NOT_RUN')
    atomic_write(args.report, encode(result))
    return 0 if result['status']=='PASS' else 2


def prepare(args):
    repo, source, output = Path(args.repo).resolve(), Path(args.runtime).resolve(), Path(args.output).resolve()
    if source == output or source in output.parents:
        raise ValueError('Use an independent destination; the source seed is read only')
    if output.exists():
        raise ValueError('Existing output is preserved; choose a fresh destination')
    from windows_ci import validate_runtime
    validate_runtime(source)
    source_files = input_fingerprint(source)
    original_manifest = json.loads((source/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    original_releases = {p.name for p in (source/'private_content/releases').iterdir() if p.is_dir()}
    seed_pointer = release_pointer(source, args.seed_release) if args.seed_release else json.loads((source/'private_content/ACTIVE.json').read_text(encoding='utf-8'))
    if (source/'recovery-evidence').exists():
        raise ValueError('Use an unprepared source runtime; recovery evidence already exists')
    # Import generations live only in a separate staging tree. The final
    # output receives the source files plus the last release, never transient
    # generations that would need to be deleted from the distribution later.
    with tempfile.TemporaryDirectory(prefix='recovery-import-',dir=output.parent) as temporary:
        staging=Path(temporary)
        shutil.copytree(source/'private_content',staging/'private_content')
        atomic_write(staging/'private_content/ACTIVE.json',encode(seed_pointer))
        evidence=staging/'recovery-evidence';evidence.mkdir()
        original=PackageStore(staging/'private_content',baseline(repo,source/'private_assets')).load()
        imported_report=run_import(repo,staging,evidence,args.work_commit,source/'private_assets')
        store=PackageStore(staging/'private_content',baseline(repo,source/'private_assets'))
        release=store.load();active=store.pointer()
        not_copied=[p.name for p in (staging/'private_content/releases').iterdir()
                    if p.is_dir() and p.name not in original_releases and p.name!=active['release_id']]
        shutil.copytree(source,output)
        shutil.copytree(evidence,output/'recovery-evidence')
        if active['release_id'] not in original_releases:
            shutil.copytree(staging/'private_content/releases'/active['release_id'],
                            output/'private_content/releases'/active['release_id'])
    evidence=output/'recovery-evidence'
    atomic_write(evidence/'original-PACKAGE_MANIFEST.json',encode(original_manifest))
    preserved_assets = all(release['assets'].get(k) == v for k,v in original['assets'].items())
    unchanged = source_files == input_fingerprint(source)
    copied_inputs = all((output/name).is_file() and file_sha(output/name)==row['sha256']
                        for name,row in source_files.items() if name!='private_content/ACTIVE.json')
    if not unchanged or not copied_inputs or not preserved_assets:
        raise ValueError('Original private inputs changed during preparation')
    if active['release_id'] != seed_pointer['release_id']:
        active['previous'] = {key:value for key,value in seed_pointer.items() if key!='previous'}
    atomic_write(output/'private_content/ACTIVE.json', encode(active))
    PackageStore(output/'private_content',baseline(repo,output/'private_assets')).load()
    if (output/'runtime_cache').exists():
        (output/'runtime_cache').rename(evidence/'original-runtime_cache')
    rows = [dict(path=p.relative_to(output).as_posix(), bytes=p.stat().st_size, sha256=file_sha(p))
            for directory in ('private_assets','private_content','licenses')
            for p in sorted((output/directory).rglob('*')) if p.is_file()]
    manifest = dict(original_manifest)
    manifest.update(private_only=True, contains_user_saves=False, files=rows,
                    recovery_work_commit=args.work_commit, recovery_content_version=active['release_id'])
    atomic_write(output/'PACKAGE_MANIFEST.json', encode(manifest))
    validate_runtime(output)
    checks, index_hash = verify_ledger(repo, release, args.work_commit)
    incomplete = [dict(batch_id=r.get('batch_id'), status=r['import_status'], errors=r.get('errors', []))
                  for r in imported_report['receipts'] if r['import_status'] not in ('IMPORTED','ALREADY_IMPORTED')]
    reference = source/'private_content/releases'/CANDIDATE_RELEASE/'release.json'
    comparison = dict(status='NOT_RUN', reason='Exact candidate release not included in this seed')
    if reference.is_file():
        expected = decode(reference.read_bytes())
        if sha(reference.read_bytes())!=CANDIDATE_RELEASE:
            raise ValueError('Pinned candidate comparison bytes changed')
        same = semantic_content(release)==semantic_content(expected)
        comparison = dict(status='PASS' if same else 'FAIL', reference_release=CANDIDATE_RELEASE,
                          ignored_fields=['imports.*.applied_before_game_commit'],
                          actual_semantic_sha256=sha(encode(semantic_content(release))),
                          expected_semantic_sha256=sha(encode(semantic_content(expected))))
    ok = not incomplete and all(c['status']=='PASS' for c in checks) and comparison['status']!='FAIL'
    result = dict(status='PASS' if ok else 'BLOCKED', scope='PINNED_DATA_ACTIVATION_NOT_GAMEPLAY',
                  implementation_origin='RECONSTRUCTED_PYTHON_ORIGINAL_RAW_SOURCE_NOT_RECOVERED',
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
                  work_commit=args.work_commit, handoff_index_sha256=index_hash, seed_release=seed_pointer['release_id'],
                  active=active, original_asset_bindings_preserved=preserved_assets,
                  source_files_unchanged=unchanged, original_copied_inputs_verified=copied_inputs,
                  source_file_count=len(source_files), preserved_baseline_releases=sorted(original_releases),
                  transient_releases_removed=[], transient_releases_not_copied=not_copied,
                  runtime_manifest_validation='PASS',
                  preserved_baseline_asset_gaps=[dict(batch_id=k,status=v['status'],applied_count=len(v['applied_ids']),held_ids=v.get('held_ids',[]))
                    for k,v in original['imports'].items() if v.get('status')=='PARTIALLY_IMPORTED'],
                  cache_handling='ORIGINAL_CACHE_PRESERVED_AS_EVIDENCE_REBUILD_REQUIRED',
                  candidate_semantic_comparison=comparison, checks=checks, incomplete=incomplete,
                  receipts=imported_report['receipts'], gameplay='NOT_RUN')
    atomic_write(args.report, encode(result))
    print('RECOVERY_CONTENT', result['status'], active['release_id'])
    return 0 if ok else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=str(ROOT));parser.add_argument('--runtime', required=True)
    parser.add_argument('--output');parser.add_argument('--report', required=True)
    parser.add_argument('--work-commit', default=WORK_COMMIT)
    parser.add_argument('--seed-release', help='Select an existing immutable seed only in the copied output')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--expected-release', default=CANDIDATE_RELEASE)
    args=parser.parse_args()
    if not args.verify_only and not args.output:parser.error('--output is required for rebuilding')
    return verify_existing(args) if args.verify_only else prepare(args)


if __name__=='__main__':
    raise SystemExit(main())
