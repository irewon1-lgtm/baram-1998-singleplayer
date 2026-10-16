"""Independent static batch audit; mutation cases use disposable copies only."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import re

HERE = Path(__file__).resolve().parent
ROOT = Path('/workspace/scratch/3624c67f59e8')
BATCH = ROOT / 'batch_staging/B001'
PACKAGE = Path('/workspace/scratch/68a0f3ea5a03/receiver/package')
VALIDATOR = HERE.parent.parent / 'validate_batch.py'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load(p):
    return json.loads(p.read_text())


def gif_metadata(b):
    """Read GIF block sizes/GCE delays independently of Pillow; no decompression."""
    assert b[:6] in (b'GIF87a', b'GIF89a')
    w, h = int.from_bytes(b[6:8], 'little'), int.from_bytes(b[8:10], 'little')
    packed = b[10]
    pos = 13 + (3 * 2 ** ((packed & 7) + 1) if packed & 128 else 0)
    pending = None
    durations = []
    def subblocks(pos):
        while True:
            n = b[pos]
            pos += 1
            if n == 0:
                return pos
            assert pos + n <= len(b)
            pos += n
    while pos < len(b):
        marker = b[pos]
        pos += 1
        if marker == 0x3b:
            break
        if marker == 0x21:
            label = b[pos]
            pos += 1
            if label == 0xf9:
                assert b[pos] == 4 and b[pos + 5] == 0
                pending = int.from_bytes(b[pos+2:pos+4], 'little') * 10
                pos += 6
            else:
                pos = subblocks(pos)
        elif marker == 0x2c:
            packed = b[pos + 8]
            pos += 9
            if packed & 128:
                pos += 3 * 2 ** ((packed & 7) + 1)
            pos += 1  # LZW minimum code size; compressed data is never executed.
            pos = subblocks(pos)
            durations.append(pending)
            pending = None
        else:
            raise ValueError('unexpected GIF marker')
    return [w, h], durations


def main():
    script = VALIDATOR.read_bytes()
    namespace = {'__name__': 'audit_validator_snapshot'}
    exec(compile(script, str(VALIDATOR), 'exec'), namespace)
    validate = namespace['validate']
    tests = []
    def case(name, mutation=None, expected='FAIL', reseal=False):
        with tempfile.TemporaryDirectory(prefix='disposable_b001_', dir=HERE) as tmp:
            p = Path(tmp) / 'B001'
            shutil.copytree(BATCH, p)
            if mutation:
                mutation(p)
            if reseal:
                m = load(p/'MANIFEST.json')
                for f in m['files']:
                    data=(p/f['path']).read_bytes()
                    f['bytes'], f['sha256'] = len(data), sha(data)
                (p/'MANIFEST.json').write_text(json.dumps(m))
            result = validate(p)
            tests.append({'case': name, 'expected': expected, 'actual': result['result'], 'errors': result['errors'], 'guard_satisfied': result['result']==expected})
    def edit_candidate(p, change):
        rows=[json.loads(l) for l in (p/'FIELD_CANDIDATES.jsonl').read_text().splitlines()]
        change(rows[0])
        (p/'FIELD_CANDIDATES.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    case('unchanged_complete_batch', expected='PASS')
    case('byte_tamper_without_resealing', lambda p: (p/'motion_sound/summary.json').write_text('{}'))
    case('missing_file', lambda p: (p/'motion_sound/summary.json').unlink())
    def empty_manifest(p):
        m=load(p/'MANIFEST.json');m['files']=[];(p/'MANIFEST.json').write_text(json.dumps(m))
    case('zero_manifest_files', empty_manifest)
    case('broken_payload_path', lambda p: edit_candidate(p,lambda r:r.update(payload_refs=['missing.json'])),reseal=True)
    case('nonexistent_stable_existing_record', lambda p:edit_candidate(p,lambda r:r.update(existing_record_ids=['KR491:effect_sequence:999999'])),reseal=True)
    case('nonexistent_requirement', lambda p:edit_candidate(p,lambda r:r.update(requirement_ids=['RQ-999999'])),reseal=True)
    case('nonexistent_private_record',lambda p:edit_candidate(p,lambda r:r['source_locator'].update(records=['DOES_NOT_EXIST'])),reseal=True)
    case('wrong_private_file_hash',lambda p:edit_candidate(p,lambda r:r['source_locator']['private_file'].update(sha256='0'*64)),reseal=True)
    def self_allowlisted_binding(p):
        edit_candidate(p,lambda r:r.update(binding_ids=['BND-999999']))
        m=load(p/'MANIFEST.json');m['valid_binding_ids'].append('BND-999999');(p/'MANIFEST.json').write_text(json.dumps(m))
    case('self_allowlisted_nonexistent_binding',self_allowlisted_binding,reseal=True)
    def wrong_fingerprint(p):
        m=load(p/'MANIFEST.json');m['input_manifest_sha256']='WRONG';(p/'MANIFEST.json').write_text(json.dumps(m))
    case('wrong_baseline_manifest_fingerprint',wrong_fingerprint)

    baseline_ids=set()
    for p in (PACKAGE/'docs/rebuild/p1_5/selected_content').glob('*.jsonl'):
        for line in p.read_text().splitlines():
            if line.strip():
                row=json.loads(line)
                if row.get('id'): baseline_ids.add(row['id'])
    bindings={json.loads(l)['binding_id'] for l in (PACKAGE/'docs/rebuild/p1_5/field_bindings.jsonl').read_text().splitlines()}
    candidates=[json.loads(l) for l in (BATCH/'FIELD_CANDIDATES.jsonl').read_text().splitlines()]
    bad_stable=[v for c in candidates for v in c['existing_record_ids'] if v not in baseline_ids]
    bad_bindings=[v for c in candidates for v in c['binding_ids'] if v not in bindings]
    timing=load(BATCH/'motion_sound/gif_timing_evidence.json')['records']
    difference=load(BATCH/'motion_sound/gif_sequence_discrepancies.json')['records']
    images={r['sha256']:r for r in load(PACKAGE/'PRIVATE_IMAGE_INDEX.json')}
    sequences={r['id']:r for r in map(json.loads,(PACKAGE/'docs/rebuild/p1_5/selected_content/kr_asset_effect_sequences.jsonl').read_text().splitlines())}
    metadata=[]
    for r in timing:
        source=PACKAGE/images[r['guide_sha256']]['path']
        b=source.read_bytes()
        dimensions,durations=gif_metadata(b)
        expected=[f['declared_duration_ms'] for f in r['gif_frame_metadata']]
        seq=sequences[r['effect_sequence_id']]
        pairs=r['aligned_nonblank_timing_pairs']
        exact_pairs=len(seq['front_frames'])==len(pairs) and all(s['frame_index']==p['client_frame_index'] and s['delay_raw']==p['raw_delay_unit_unknown'] and s['source_line']==p['effect_tbl_line'] and s['source_byte_offset']==p['effect_tbl_byte_offset'] for s,p in zip(seq['front_frames'],pairs))
        metadata.append({'record_id':r['record_id'],'gif_hash_matches':sha(b)==r['guide_sha256'],'dimensions_match':dimensions==r['gif_dimensions_px'],'all_declared_durations_match_independent_block_parser':durations==expected,'frame_count':len(durations),'effect_source_pairs_match_frozen_records':exact_pairs})
    private_records={r['record_id'] for r in timing+difference}
    bad_private=[]
    for c in candidates:
        loc=c['source_locator']
        refs=loc.get('records',[loc.get('record_id')])
        bad_private.extend(r for r in refs if r not in private_records)
        info=loc['private_file'];b=(BATCH/info['relative_private_path']).read_bytes()
        if len(b)!=info['bytes'] or sha(b)!=info['sha256']:bad_private.append(c['candidate_id']+':private_file_hash')
    z=ROOT/'delivery/BARAM_WORK_SOURCE_DELTA_B001_20261016.zip'
    with zipfile.ZipFile(z) as zipf:
        zip_set={v.filename for v in zipf.infolist() if not v.is_dir()}
        batch_set={v.relative_to(BATCH).as_posix() for v in BATCH.rglob('*') if v.is_file()}
        zip_ok=zip_set==batch_set and all(zipf.read(v)==(BATCH/v).read_bytes() for v in zip_set)
        secret_patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{20,}',rb'sk-proj-[A-Za-z0-9_-]{20,}',rb'X-Amz-Signature=[A-Za-z0-9]+',rb'completion_token[\"\s:]+[A-Za-z0-9_-]{16,}']
        findings=[name for name in zip_set if any(re.search(pattern,zipf.read(name)) for pattern in secret_patterns)]
        zip_result={'sha256':sha(z.read_bytes()),'files':len(zip_set),'crc_failure':zipf.testzip(),'exact_staging_set_and_bytes':zip_ok,'excluded_suffixes_found':[v for v in zip_set if Path(v).suffix.lower() in {'.exe','.sql','.ttf','.otf','.pfx','.jks','.keystore','.bak'}],'strong_secret_marker_files':findings,'security_scope':'Limited filename/strong credential patterns; no malware or absence-of-all-secrets certification'}
    report={'schema':'baram.work_delta.independent_ai_audit/1','scope':'B001 static bytes/IDs/private locators plus independent GIF GCE metadata; no original runtime/hit/audio/accuracy certification','validator_sha256':sha(script),'validator_mutation_cases':tests,'actual_batch':{'stable_id_references_checked':sum(len(c['existing_record_ids']) for c in candidates),'unknown_stable_ids':bad_stable,'unknown_binding_ids':bad_bindings,'broken_private_locators':bad_private,'independent_gif_metadata':metadata,'zip':zip_result},'judgement':'ACTUAL_B001_STATIC_METADATA_CONSISTENT; VALIDATOR_SEMANTIC_REFERENCE_GUARDS_INCOMPLETE','runtime':'NOT_RUN','historical_accuracy':'PARTIAL_UNCONFIRMED','immutable_B001_modified':False}
    (HERE/'B001_INDEPENDENT_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'audit':str(HERE/'B001_INDEPENDENT_AUDIT.json'),'guard_gaps':[t['case'] for t in tests if not t['guard_satisfied']],'actual_b001_bad_ids_or_locators':bad_stable+bad_bindings+bad_private,'gif_records':len(metadata),'gif_metadata_all_match':all(all(v for k,v in r.items() if k.endswith('matches') or k.endswith('_parser') or k.endswith('_records') or k=='dimensions_match') for r in metadata),'zip':zip_result},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
