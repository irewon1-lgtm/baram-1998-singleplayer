#!/usr/bin/env python3
"""Validate data contracts and immutable evidence. Never executes a game test."""
import collections, datetime, hashlib, json, math, re, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/restoration-integrated-20261013'
def readl(name):return [json.loads(l) for l in (OUT/name).read_text().splitlines() if l.strip()]
def readj(name):return json.loads((OUT/name).read_text())
def main():
    checks=[]
    def check(name,ok,observed,expected):checks.append(dict(name=name,result='PASS' if ok else 'FAIL',expected=expected,observed=observed,scope='RESEARCH_DATA_CONTRACT_ONLY'))
    catalog=readl('CONTENT_CATALOG.jsonl');master=readl('NUMERIC_MASTER.jsonl');sources=readl('NUMERIC_SOURCES.jsonl');gaps=readl('NUMERIC_GAPS.jsonl');review=readl('CANDIDATE_REVIEW.jsonl');original=[json.loads(l) for l in (ROOT/'research/korean-history-20261013/extracted-candidates.jsonl').read_text().splitlines()]
    cs={r['content_id']:r for r in catalog};ms={r['field_id']:r for r in master};ss={r['observation_id']:r for r in sources};registry={r['id']:r for r in readj('SOURCE_VERSION_RIGHTS_LEDGER.json')['sources']}
    check('Unique content ids',len(cs)==len(catalog),len(cs),len(catalog))
    check('Unique field ids and content-field pairs',len(ms)==len(master)==len({(r['content_id'],r['field']) for r in master}),len(ms),len(master))
    check('Unique source observation ids',len(ss)==len(sources),len(ss),len(sources))
    ids={r['candidate_id'] for r in review};expected={r['id'] for r in original}
    check('All 1674 candidates reconciled exactly once',ids==expected and len(review)==1674,dict(rows=len(review),missing=list(expected-ids),extra=list(ids-expected)),dict(rows=1674,missing=[],extra=[]))
    outcomes=collections.Counter(r['outcome'] for r in review)
    check('Candidate outcome partition',set(outcomes)<=set(['VERIFIED','DUPLICATE','ERROR','INSUFFICIENT_DATA','DEFERRED']) and sum(outcomes.values())==1674,dict(outcomes),readj('CANDIDATE_REVIEW_SUMMARY.json')['outcomes'])
    check('Source HTML byte verification for every candidate',all(r['source_bytes_check']['status']=='PASS' for r in review),dict(verified=sum(r['source_bytes_check']['status']=='PASS' for r in review),source_count=len({r['source_id'] for r in review})),dict(verified=1674,source_count=58))
    links=[r['field_id'] for r in master if r['content_id'] not in cs or any(sid not in ss for sid in r['source_observation_ids'])]
    check('Master content and observation links resolve',not links,links,[])
    missing=[r['observation_id'] for r in sources if r['content_id'] not in cs or r['source_id'] not in registry or not r.get('position')]
    check('Observations have content/source/position',not missing,missing,[])
    unlinked=[r['field_id'] for r in master if r['value'] is not None and not r['source_observation_ids']]
    check('Every applied value has linked evidence or assumption',not unlinked,unlinked,[])
    no_url=[r['observation_id'] for r in sources if r['kind']!='DEV_ESTIMATE' and not r.get('source_url')]
    check('Original and external values retain URLs',not no_url,no_url,[])
    valid_units={'HP','MP','AC','XP','ms','tile','level','rank','damage','stat','count','durability_point','ratio','probability','전'}
    invalid=[(r['field_id'],r['unit']) for r in master if r['unit'] not in valid_units]
    check('No unknown numeric units',not invalid,invalid,[])
    invalid=[r['field_id'] for r in master if r['value'] is not None and (type(r['value']) not in [int,float] or not math.isfinite(r['value']))]
    check('Applied values are finite numeric scalars',not invalid,invalid,[])
    invalid=[r['field_id'] for r in master if r['unit']=='probability' and r['value'] is not None and not 0<=r['value']<=1]
    check('Probabilities use 0..1',not invalid,invalid,[])
    invalid=[r['field_id'] for r in master if r['unit'] in ['level','count','rank','tile','durability_point','ms','stat','HP','MP','damage','전'] and r['value'] is not None and r['value']!=int(r['value'])]
    check('Integer domains have explicit integer values',not invalid,invalid,[])
    invalid=[r['field_id'] for r in master if r['unit']!='AC' and r['value'] is not None and r['value']<0]
    check('Nonnegative resource domains; signed AC separate',not invalid,invalid,[])
    bad=[]
    for r in master:
        if r['classification']=='KR_CONFIRMED' and any(ss[sid]['kind']!='KR_CONFIRMED' for sid in r['source_observation_ids']):bad.append(r['field_id'])
        if r['classification']=='DEV_ESTIMATE' and any(ss[sid]['kind']!='DEV_ESTIMATE' for sid in r['source_observation_ids']):bad.append(r['field_id'])
    check('Historical, replacement and assumed values stay separate',not bad,bad,[])
    bad=[]
    for r in readj('IMPLEMENTATION_MEANS.json'):
        values=r['distinct_values'];linked=[ss[oid] for oid in r['observation_ids']]
        if abs(sum(values)/len(values)-r['raw_arithmetic_mean'])>1e-9 or len(values)!=len(set(values)) or any(o['kind']!='KR_CONFIRMED' for o in linked):bad.append((r['content_id'],r['field']))
    check('Means reproduce distinct Korean observations only',not bad,dict(mean_fields=len(readj('IMPLEMENTATION_MEANS.json')),bad=bad),dict(bad=[]))
    early=[r for r in master if r['required'] and r['early_scope']];required=[r for r in master if r['required']]
    check('Every declared early scalar input populated',all(r['value'] is not None for r in early),dict(filled=sum(r['value'] is not None for r in early),total=len(early)),dict(filled=len(early),total=len(early)))
    miss={(r['content_id'],r['field']) for r in required if r['value'] is None};gapkeys={(r['content_id'],r['field']) for r in gaps}
    check('Every missing required scalar has one gap row',miss==gapkeys and len(gapkeys)==len(gaps),dict(required_missing=len(miss),gap_rows=len(gaps)),dict(equal=True))
    number_summary=readj('NUMERIC_SUMMARY.json')
    check('Numeric headline reconciles to data',number_summary['required_fields']==len(required) and number_summary['remaining_scalar_gaps']==len(gaps) and number_summary['early_required_fields']==len(early),dict(required=len(required),gaps=len(gaps),early=len(early)),dict(required=number_summary['required_fields'],gaps=number_summary['remaining_scalar_gaps'],early=number_summary['early_required_fields']))
    drops=readl('DROP_RULES.jsonl');bad=[r['drop_rule_id'] for r in drops if r['monster_content_id'] not in cs or r['item_content_id'] not in cs or r['source_id'] not in registry or r['probability'] is not None and not 0<=r['probability']<=1]
    check('Drop monster/item/source links and ranges',not bad,bad,[])
    tests=readj('BALANCE_TESTS.json');bad=[r['test_id'] for r in tests['tests'] if r['execution_status']!='NOT_RUN' or any(fid not in ms for fid in r['field_refs'])]
    check('Prepared tests are not represented as executed',not bad and tests['actual_simulations_executed']==0,dict(test_definitions=tests['test_count'],actual_runs=tests['actual_simulations_executed'],bad=bad),dict(actual_runs=0,bad=[]))
    features=readj('FEATURE_MATRIX.json')['features']
    check('Gameplay implementation and screen checks remain unverified',all(f['game_implementation']==f['automatic_game_test']==f['actual_screen_operation']=='NOT_RUN' for f in features),len(features),'All independent statuses NOT_RUN')
    assets=readl('ASSET_CATALOG.jsonl');bad=[r['asset_id'] for r in assets if r['decoded_render_status']!='NOT_RUN' or r['public_bytes_included'] or len(r['sha256'])!=64]
    check('Asset catalogue has hashes but no render/public-byte claim',not bad and len({r['sha256'] for r in assets})==len(assets),dict(unique_payloads=len(assets),bad=bad),dict(bad=[]))
    preserved=[];inherit=readj('INHERITED_FILES.json')
    for r in inherit['files']:
        if r['action'] in ['reviewed_new_research_file_import','same_blob_preserved']:
            path=ROOT/r['path']
            if not path.exists():preserved.append(r['path']);continue
            value=subprocess.check_output(['git','hash-object',str(path)],cwd=ROOT,text=True).strip()
            if value!=r['blob_sha']:preserved.append(r['path'])
    check('Inherited research file bytes preserved',not preserved,preserved,[])
    public_files=list(OUT.glob('*'));bad=[str(p.relative_to(ROOT)) for p in public_files if p.is_file() and p.suffix.lower() not in ['.json','.jsonl','.md','.log','.txt']]
    check('Public new research contains no raw client/resource binaries',not bad,bad,[])
    # Specific guard against the source meaning errors exposed by this audit.
    find=lambda name,field,scope=None:next(r for r in master if r['content_name']==name and r['field']==field and (scope is None or r['class_scope']==scope))
    check('Squirrel blended XP remains 7.5',find('다람쥐','experience')['value']==7.5,find('다람쥐','experience')['value'],7.5)
    check('Gungon cast MP40 differs from learn gold3250',find('건곤대나이','cast_mp','전사')['value']==40 and find('건곤대나이','learn_money','전사')['value']==3250,dict(cast_mp=find('건곤대나이','cast_mp','전사')['value'],learn_gold=find('건곤대나이','learn_money','전사')['value']),dict(cast_mp=40,learn_gold=3250))
    bad=[]
    for r in master:
        if r['category']=='growth' and r['level']<99:
            row=next((s for s in sources if s['observation_id'] in r['source_observation_ids']),None)
            if r['field'].endswith('max_inclusive') and row and row.get('literal_source_numeric_value')!=r['value']+1:bad.append(r['field_id'])
    check('Exclusive external growth maxima converted explicitly',not bad,bad,[])
    result=dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command='python tools/validate_restoration_data.py',base_sha=inherit['base_sha'],checks=checks,pass_checks=sum(c['result']=='PASS' for c in checks),fail_checks=sum(c['result']=='FAIL' for c in checks),
                data_contract_status='PASS' if all(c['result']=='PASS' for c in checks) else 'FAIL',original_fidelity='UNVERIFIED',actual_game_simulation='NOT_RUN',actual_game_screen='NOT_RUN',full_later_numeric_completion='BLOCKED_GAPS_RETAINED',main_merge=False,paid_work=False)
    (OUT/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2));return int(result['fail_checks']>0)

if __name__=='__main__':raise SystemExit(main())
