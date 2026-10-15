#!/usr/bin/env python3
"""Relocate verified P1.5 source bytes into a current flat input map.

Static local work only. No game, reference server, installer or network execution.
Registry absolute paths are names/hints only; files are read solely from explicit
--input-map, --originals-dir, --cache-root, and --reference-root arguments.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
VERSION = 'baram-p15-portable-inputs/1.1'
SHA = re.compile(r'^[0-9a-f]{64}$')
MAX_FILE = 768 * 1024 * 1024

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def load_json(p): return json.loads(p.read_text(encoding='utf-8-sig'))

def load_registry(repo, registry):
    rows, registered, fingerprints = {}, set(), {}
    for p in [repo/'docs/rebuild/step01/sources.jsonl', registry/'sources_delta.jsonl']:
        if not p.is_file(): continue
        fingerprints[str(p.relative_to(repo))] = digest(p)
        for line in p.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip(): continue
            r = json.loads(line); sid = r.get('source_id')
            if sid: rows[sid] = dict(rows.get(sid, {}), **r)
    for p in sorted(registry.glob('research_*.json')):
        fingerprints[str(p.relative_to(repo))] = digest(p)
        for key in ('sources','web_pages','web_images'):
            for r in load_json(p).get(key, []):
                if not isinstance(r, dict) or not r.get('source_id'): continue
                sid = r['source_id']; old = rows.get(sid, {})
                if old.get('sha256') and r.get('sha256') and old['sha256'] != r['sha256']:
                    raise ValueError('Registry hash disagreement for '+sid)
                rows[sid] = dict(old, **r); registered.add(sid)
    return rows, registered, fingerprints

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n'); temp = Path(f.name)
    os.replace(temp, path)

def declared_step01_inputs(repo):
    """Use exactly the legacy validator declaration, including sourceID::file."""
    base = repo/'docs/rebuild/step01'
    expected = {}
    for line in (base/'sources.jsonl').read_text(encoding='utf-8-sig').splitlines():
        if not line.strip(): continue
        row=json.loads(line);sid=row['source_id'];files=row.get('files',[])
        if row.get('sha256') and not files:
            expected[sid]={'sha256':row['sha256'],'bytes':row.get('size_bytes')}
        for entry in files:
            expected[sid+'::'+entry['path']]={'sha256':entry.get('sha256'),'bytes':entry.get('actual_size',entry.get('size'))}
    # archive_sources cross-consistency is still checked by validate_step01.
    # It does not add a second copy of source IDs to the byte declaration.
    for line in (base/'archive_members.jsonl').read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            row=json.loads(line);expected[row['member_id']]={'sha256':row.get('sha256'),'bytes':row.get('size_bytes')}
    if not expected: raise ValueError('No declared step01 required input IDs')
    return expected

def project_step01_map(repo, current_map, output, report_path):
    """Project current verified object bytes into the legacy2489-ID namespace.

    Never send P1.5 IDs to the strict legacy validator. Composite source-file
    IDs are restored by their declared byte hash, without trusting old paths.
    """
    mapping=load_json(current_map);expected=declared_step01_inputs(repo)
    wanted={e['sha256'] for e in expected.values()};by_hash={};checked=set()
    for value in mapping.values():
        path=Path(value)
        if str(path) in checked:continue
        checked.add(str(path))
        if path.name not in wanted or path.is_symlink() or not path.is_file():continue
        actual=digest(path)
        if actual==path.name:by_hash.setdefault(actual,path.resolve())
    projected={};missing=[]
    for ident,e in sorted(expected.items()):
        path=by_hash.get(e['sha256'])
        if path is None or e['bytes'] is not None and path.stat().st_size!=e['bytes']:
            missing.append(ident)
        else:projected[ident]=str(path)
    result='BLOCKED' if missing else 'PASS'
    atomic_json(output,projected)
    command=[sys.executable,str(repo/'tools/rebuild/step01/validate_step01.py'),'--root',str(repo),'--input-map',str(output),'--output',str(output.parent/'whole_byte_validation_current.json')]
    receipt={'schema':'baram.p1_5.step01_map_projection/1','result':result,'scope':'Exact step01 declared ID set only; fullP1.5 importer map unchanged','main_import_map':str(current_map),'main_import_map_sha256':digest(current_map),'step01_map':str(output),'step01_map_sha256':digest(output),'declared_ids':len(expected),'mapped_ids':len(projected),'missing_ids':missing,'unknown_ids':sorted(set(projected)-set(expected)),'byte_hashes_verified':len(by_hash),'whole_byte_gate_command':shlex.join(command),'source_objects_modified':False,'runtime_tests':'NOT_RUN'}
    atomic_json(report_path,receipt)
    print(json.dumps({k:receipt[k] for k in ['result','declared_ids','mapped_ids','unknown_ids']},ensure_ascii=False))
    print('STEP01_MAP='+str(output));print('WHOLE_BYTE_GATE='+shlex.join(command))
    return receipt

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, default=ROOT)
    ap.add_argument('--registry-dir', type=Path)
    ap.add_argument('--input-map', type=Path, help='Existing explicit current flat ID:path map')
    ap.add_argument('--originals-dir', type=Path, help='User-materialized42Library files; never fetched automatically')
    ap.add_argument('--cache-root', type=Path, action='append', default=[])
    ap.add_argument('--reference-root', type=Path, help='Already statically extracted reference_sources.zip root; searched by byte hash')
    ap.add_argument('--copy-inputs-to', type=Path, help='Independent read-only SHA256 object copies below this clean directory')
    ap.add_argument('--output', type=Path, required=True, help='Flat current map; with --split-existing-map this is the step01-specific output')
    ap.add_argument('--split-existing-map', type=Path, help='Only project existing SHAobject map into exact legacy step01 ID set; no recopy')
    ap.add_argument('--report', type=Path, help='Defaults to <output-stem>.report.json')
    ap.add_argument('--content-dir', type=Path, help='Actual35normalized payload directory, for printed importer command')
    a = ap.parse_args(); repo = a.repo.resolve(); registry = (a.registry_dir or repo/'docs/rebuild/p1_5').resolve()
    report_path = a.report or a.output.with_name(a.output.stem+'.report.json')
    if a.split_existing_map:
        if a.output.resolve()==a.split_existing_map.resolve():ap.error('Split output must differ from main importer map')
        receipt=project_step01_map(repo,a.split_existing_map.resolve(),a.output.resolve(),report_path.resolve())
        return 0 if receipt['result']=='PASS' else 2
    if a.copy_inputs_to is None:ap.error('--copy-inputs-to is required unless --split-existing-map is used')
    rows, registered, fingerprints = load_registry(repo, registry)
    manifest_path = registry/'INPUT_MANIFEST.json'; manifest = load_json(manifest_path)
    expected = {}; required = set(); hints = collections.defaultdict(set)
    def add(sid, row, need):
        h = row.get('sha256')
        if not sid or not isinstance(h, str) or not SHA.fullmatch(h): return
        old = expected.get(sid)
        if old and old['sha256'] != h: raise ValueError('Expected hash disagreement for '+sid)
        size = row.get('size_bytes', row.get('bytes', row.get('byte_length')))
        expected[sid] = {'sha256':h, 'bytes':size if isinstance(size,int) else None}
        if need: required.add(sid)
        for key in ('local_private_path','local_path','local_materialization_path','private_local_path','library_path','file_path','path'):
            if row.get(key): hints[h].add(Path(str(row[key])).name)
        hints[h].update([sid,h])
    for sid, r in rows.items(): add(sid,r,sid in registered)
    for r in manifest.get('originals', []): add(r.get('source_id'),r,True)
    # Include exactly the legacy byte declaration, especially source.files
    # composite IDs. A parent source record has no hash for these files.
    # Omitting them would let the legacy validator fall back to stale paths.
    for sid, r in declared_step01_inputs(repo).items():
        add(sid,dict(r,path=sid.split('::',1)[-1]),True)
    member_path = repo/'docs/rebuild/step01/archive_members.jsonl'
    if member_path.is_file():
        fingerprints[str(member_path.relative_to(repo))] = digest(member_path)
        for line in member_path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip():
                r=json.loads(line);add(r.get('member_id'),r,True)
    explicit = load_json(a.input_map) if a.input_map else {}
    if not isinstance(explicit,dict) or not all(isinstance(v,str) for v in explicit.values()): raise ValueError('input-map must be a flat ID:path object')
    # Additional explicit object-map entries may be later nested-member IDs.
    # Their source filename itself must declare a SHA256; keep their identity.
    for sid, val in explicit.items():
        if sid not in expected and SHA.fullmatch(Path(val).name): add(sid,{'sha256':Path(val).name},True)
    by_hash = {}; failures = []; hashed = {}; explicit_checked=0
    def accept(path, wanted=None, declared_size=None):
        nonlocal explicit_checked
        try:
            if path.is_symlink() or not path.is_file(): return False
            st=path.stat()
            if st.st_size>MAX_FILE or declared_size is not None and st.st_size!=declared_size:return False
            key=(str(path.resolve()),st.st_size,st.st_mtime_ns)
            h=hashed.get(key)
            if h is None:h=digest(path);hashed[key]=h
            if wanted and h!=wanted:return False
            by_hash.setdefault(h,path.resolve());return True
        except OSError:return False
    for sid,val in explicit.items():
        e=expected.get(sid)
        if not e:continue
        p=Path(val);explicit_checked+=1
        if p.is_file() and not accept(p,e['sha256'],e['bytes']):failures.append({'id':sid,'status':'FAIL','reason':'Explicit input-map byte/size/symlink mismatch'})
    roots = [p.resolve() for p in ([a.originals_dir,a.reference_root]+a.cache_root) if p]
    sizes = {e['bytes'] for e in expected.values() if e['bytes'] is not None}
    wanted_hashes = {e['sha256'] for e in expected.values()}; names={n for ns in hints.values() for n in ns}
    scanned=0
    for root in roots:
        if not root.is_dir():continue
        for p in root.rglob('*'):
            try:
                if p.is_symlink() or not p.is_file():continue
                scanned+=1
                # Skip unrelated large/cache files; hash plausible names or exact sizes.
                if p.name not in names and p.stat().st_size not in sizes:continue
                if len(by_hash.keys() & wanted_hashes)==len(wanted_hashes):break
                accept(p)
            except OSError:continue
    pool=a.copy_inputs_to.resolve();pool.mkdir(parents=True,exist_ok=True);copies={};mapped={};results=[]
    for sid,e in sorted(expected.items()):
        h=e['sha256'];source=by_hash.get(h)
        if source is None:
            results.append({'id':sid,'required':sid in required,'status':'BLOCKED','sha256':h,'reason':'No explicit current exact-hash source; use materialized originals/cache or known URL/hash reacquisition contract'})
            continue
        if h not in copies:
            dest=pool/h
            if dest.exists():
                if dest.is_symlink() or digest(dest)!=h:raise ValueError('Clean object-pool hash mismatch; existing bytes preserved')
            else:
                # Copy, never chmod a hardlink to an original inode.
                with tempfile.NamedTemporaryFile(dir=pool,delete=False) as f:
                    temp=Path(f.name)
                    with source.open('rb') as src:
                        for b in iter(lambda:src.read(1024*1024),b''):f.write(b)
                    f.flush();os.fsync(f.fileno())
                if digest(temp)!=h:temp.unlink();raise ValueError('Source changed while copying; original preserved')
                os.replace(temp,dest);dest.chmod(0o444)
            copies[h]=str(dest)
        mapped[sid]=copies[h];results.append({'id':sid,'required':sid in required,'status':'PASS','sha256':h,'current_path':copies[h]})
    missing=[r for r in results if r['required'] and r['status']=='BLOCKED']
    status='FAIL' if failures else 'BLOCKED' if missing else 'PASS'
    atomic_json(a.output.resolve(),dict(sorted(mapped.items())))
    cmd=[sys.executable,str(repo/'tools/rebuild/p1_5/import_dry_run.py'),'--repo',str(repo),'--registry-dir',str(registry),'--input-map',str(a.output.resolve()),'--catalog-manifest',str(manifest_path),'--output',str(a.output.resolve().parent/'import_validation_current.json')]
    if a.content_dir:cmd+=['--content-dir',str(a.content_dir.resolve())]
    report={'schema':'baram.p1_5.portable_inputs/1','tool_version':VERSION,'result':status,'scope':'Exact-byte path relocation/copy only; not original accuracy, game execution or CodexG0','source_registry_rows':len(rows),'registered_source_ids':len(registered),'expected_id_count':len(expected),'required_ids':len(required),'required_mapped':sum(sid in mapped for sid in required),'required_missing':len(missing),'mapped_ids':len(mapped),'unique_object_copies':len(copies),'explicit_map_entries_checked':explicit_checked,'cache_files_scanned':scanned,'all_mapped_paths_within_copy_pool':all(Path(v).is_relative_to(pool) for v in mapped.values()),'copy_method':'Independent SHA256verified byte copy; original permissions/content untouched; new objects read-only','registry_fingerprints':fingerprints,'input_manifest_sha256':digest(manifest_path),'input_map_sha256':digest(a.output.resolve()),'failures':failures,'inputs':results,'network_requests':0,'download_feature':'NOT_IMPLEMENTED; current source cache only. Known URL+hash re-acquisition contract in handoff_input_contract.json.','installer_game_server_execution':'NOT_RUN','next_import_command':shlex.join(cmd),'content_dir_status':'SUPPLIED' if a.content_dir else 'NOT_SUPPLIED; add --content-dir with35actual normalized payloads before import','native_runtime_tests':'NOT_RUN'}
    step01_output=a.output.with_name(a.output.stem+'.step01.json').resolve()
    step01_receipt=project_step01_map(repo,a.output.resolve(),step01_output,step01_output.with_name(step01_output.stem+'.report.json'))
    report['step01_map']=str(step01_output);report['step01_map_result']=step01_receipt['result'];report['whole_byte_gate_command']=step01_receipt['whole_byte_gate_command']
    if report['result']=='PASS' and step01_receipt['result']!='PASS':report['result']='BLOCKED';status='BLOCKED'
    atomic_json(report_path.resolve(),report)
    print(json.dumps({k:report[k] for k in ['result','source_registry_rows','required_ids','required_mapped','required_missing','mapped_ids','unique_object_copies','all_mapped_paths_within_copy_pool','network_requests']},ensure_ascii=False))
    print('INPUT_MAP='+str(a.output.resolve()));print('REPORT='+str(report_path.resolve()));print('NEXT_IMPORT='+shlex.join(cmd))
    return 1 if status=='FAIL' else 2 if status=='BLOCKED' else 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as e:
        print('FAIL: '+type(e).__name__+': '+str(e)[:240],file=sys.stderr);raise SystemExit(1)
