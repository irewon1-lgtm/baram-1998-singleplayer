"""Reproduce semantic-reference guard cases against the current supplemental tool."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent
WORK=HERE.parent.parent
BATCH=Path('/workspace/scratch/3624c67f59e8/batch_staging/B001')
BASE=Path('/workspace/scratch/68a0f3ea5a03/receiver/package/docs/rebuild/p1_5')


def main():
    tool=WORK/'verify_evidence_refs.py'
    code=tool.read_bytes()
    ns={'__name__':'audit_evidence_guard_snapshot'}
    exec(compile(code,str(tool),'exec'),ns)
    verify=ns['verify']
    cases=[]
    def edit(p,fn):
        rows=[json.loads(l) for l in (p/'FIELD_CANDIDATES.jsonl').read_text().splitlines()]
        fn(rows[0])
        (p/'FIELD_CANDIDATES.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    def run(name,fn=None,expected='FAIL'):
        with tempfile.TemporaryDirectory(prefix='disposable_refs_',dir=HERE) as tmp:
            p=Path(tmp)/'B001';shutil.copytree(BATCH,p)
            if fn:fn(p)
            result=verify(p,BASE,BASE/'selected_content')
            cases.append({'case':name,'expected':expected,'actual':result['result'],'guard_satisfied':result['result']==expected,'errors':result['errors'],'checks':result['checks']})
    run('unchanged_complete_batch',expected='PASS')
    run('nonexistent_stable_existing_record',lambda p:edit(p,lambda r:r.update(existing_record_ids=['KR491:effect_sequence:999999'])))
    run('nonexistent_requirement',lambda p:edit(p,lambda r:r.update(requirement_ids=['RQ-999999'])))
    run('nonexistent_private_record',lambda p:edit(p,lambda r:r['source_locator'].update(records=['DOES_NOT_EXIST'])))
    run('wrong_private_file_hash',lambda p:edit(p,lambda r:r['source_locator']['private_file'].update(sha256='0'*64)))
    def bad_binding(p):
        edit(p,lambda r:r.update(binding_ids=['BND-999999']))
        path=p/'MANIFEST.json';m=json.loads(path.read_text());m['valid_binding_ids'].append('BND-999999');path.write_text(json.dumps(m))
    run('self_allowlisted_nonexistent_binding',bad_binding)
    def bad_fingerprint(p):
        path=p/'MANIFEST.json';m=json.loads(path.read_text());m['input_manifest_sha256']='WRONG';path.write_text(json.dumps(m))
    run('wrong_baseline_manifest_fingerprint',bad_fingerprint)
    result={'schema':'baram.work_delta.supplemental_guard_independent_regression/1','checker_sha256':hashlib.sha256(code).hexdigest(),'cases':cases,'all_expected':all(c['guard_satisfied'] for c in cases),'scope':'Six previously missed semantic references; no B001 modifications or gameplay execution','runtime':'NOT_RUN'}
    (HERE/'EVIDENCE_GUARD_REGRESSION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
