#!/usr/bin/env python3
"""Validate real P0/P1 deliverables; never reports a gameplay PASS."""
import argparse,csv,hashlib,json,re,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/rebuild/step01'
def j(n):return json.loads((OUT/n).read_text())
def jl(n):return [json.loads(x) for x in (OUT/n).read_text().splitlines() if x.strip()]
def csvread(n):return list(csv.DictReader((OUT/n).open(encoding='utf-8-sig',newline='')))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

checks=[]
def check(name,condition,detail):
    checks.append({'check_id':name,'result':'PASS' if condition else 'FAIL','scope':'STATIC_ARTIFACT_INTEGRITY_ONLY','observed':detail})

required=['REPORT.md','requirements.csv','sources.jsonl','issues.csv','NEXT_P2.md']
check('required_deliverables',all((OUT/n).is_file() for n in required),required)
reqs=csvread('requirements.csv');sources=jl('sources.jsonl');issues=csvread('issues.csv');bindings=jl('field_bindings.jsonl');members=jl('archive_members.jsonl')
R={r['requirement_id']:r for r in reqs};S={s['source_id']:s for s in sources};M={m['member_id']:m for m in members}
check('unique_requirement_ids',len(R)==len(reqs),{'rows':len(reqs),'unique':len(R)})
check('unique_source_ids',len(S)==len(sources),{'rows':len(sources),'unique':len(S)})
check('unique_issue_and_binding_member_ids',len({x['issue_id'] for x in issues})==len(issues) and len({b['binding_id'] for b in bindings})==len(bindings) and len(M)==len(members),{'issues':len(issues),'bindings':len(bindings),'members':len(members)})
needed=['requirement_id','category','canonical_requirement','expected_behavior','evidence_needed','source_ids','source_locator','confirmed_information','missing_information','implementation_feature','normal_test_id','normal_test','failure_test_id','failure_test','cancel_test_id','cancel_test','priority','planned_phase','fact_status','use_status','test_status']
blank=[(r['requirement_id'],k) for r in reqs for k in needed if not r.get(k,'').strip()]
check('requirement_cells_complete',not blank,{'empty_cells':blank})
refs=[(r['requirement_id'],sid) for r in reqs for sid in r['source_ids'].split('|') if sid not in S]
refs += [(i['issue_id'],sid) for i in issues for sid in i['source_ids'].split('|') if sid not in S]
refs += [(i['issue_id'],qid) for i in issues for qid in i['requirement_ids'].split('|') if qid not in R]
refs += [(b['binding_id'],sid) for b in bindings for sid in b['source_ids'] if sid not in S]
refs += [(b['binding_id'],qid) for b in bindings for qid in b['requirement_ids'] if qid not in R]
refs += [(m['member_id'],m['source_id']) for m in members if m['source_id'] not in S]
refs += [(b['binding_id'],m.get('member_id')) for b in bindings for m in b.get('original_member_candidates',[]) if m.get('member_id') not in M]
check('all_source_requirement_member_refs',not refs,{'broken_refs':refs})
testids=[r[k] for r in reqs for k in ['normal_test_id','failure_test_id','cancel_test_id']]
check('unique_normal_failure_cancel_tests',len(testids)==len(set(testids)) and len(testids)==3*len(reqs),{'designed':len(testids),'unique':len(set(testids))})
check('unexecuted_game_tests_not_pass',all(r['test_status']=='NOT_RUN' for r in reqs) and all(i['new_game_test_status']=='NOT_RUN' for i in issues) and all(b['test_status']=='NOT_RUN' for b in bindings),{'runtime_tests_executed':0,'requirement_test_status_counts':dict(Counter(r['test_status'] for r in reqs))})
check('no_new_runtime_bound_claim',all(r['use_status'] not in ['BOUND','EXERCISED'] for r in reqs) and all(not s.get('new_runtime_bound') for s in sources),{'bound_or_exercised':0})
check('canonical_provenance_axes',all(s['fact_status'] in ['ORIGINAL_VERIFIED','CORROBORATED_RECONSTRUCTION','INFERRED','UNKNOWN'] and s['use_status'] in ['DISCOVERED','ACQUIRED','DECODED','IDENTIFIED','BOUND','EXERCISED'] for s in sources),{'source_specific_notes_preserved':sum('source_specific_fact_status' in s for s in sources)})

hasherrors=[]
for s in sources:
    h=s.get('sha256')
    if h and not re.fullmatch('[a-f0-9]{64}',h):hasherrors.append((s['source_id'],'bad source sha'))
    if not h and not s.get('missing_hash_reason'):hasherrors.append((s['source_id'],'hash and explicit missing reason both absent'))
    for f in s.get('files',[]):
        if not re.fullmatch('[a-f0-9]{64}',str(f.get('sha256',''))):hasherrors.append((s['source_id'],f.get('path'),'missing member sha'))
for m in members:
    if not re.fullmatch('[a-f0-9]{64}',str(m.get('sha256',''))):hasherrors.append((m['member_id'],'missing byte member sha'))
check('source_and_member_hashes_or_explicit_gap',not hasherrors,{'hash_errors':hasherrors,'sources_with_explicit_missing_hash':sum(not s.get('sha256') for s in sources)})
bytefails=[];bytechecked=0
for s in sources:
    p=s.get('local_materialization_path') or s.get('private_local_path')
    if p and Path(p).is_file() and s.get('sha256'):
        bytechecked+=1
        if digest(Path(p))!=s['sha256']:bytefails.append((s['source_id'],'current bytes differ'))
    for f in s.get('files',[]):
        fp=f.get('local_path')
        if fp and Path(fp).is_file():
            bytechecked+=1
            if digest(Path(fp))!=f['sha256']:bytefails.append((s['source_id'],f.get('path'),'current nested source bytes differ'))
check('available_acquired_files_match_ledger',not bytefails,{'files_checked':bytechecked,'failures':bytefails,'note':'Other remote/snapshot bytes have agent hash evidence; unavailable private paths are not invented.'})

coverage=j('coverage_matrix.json')
covrefs=[(k,x) for kind in ['required_categories','inherited_regressions'] for k,v in coverage[kind].items() for x in v if x not in R]
check('required_categories_and_inherited_failures',not covrefs and len(coverage['required_categories'])==9 and len(coverage['inherited_regressions'])==10 and set(r['category'] for r in reqs)=={'START','UI','WORLD','GROWTH','COMBAT','LIFE','AV','SAVE','OPS'}, {'categories':{k:len(v) for k,v in coverage['required_categories'].items()},'regression_groups':len(coverage['inherited_regressions']),'broken_refs':covrefs})
reasonset={i['unused_reason'] for i in issues}
expected={'접근 불가','해독 실패','ID 미식별','버전 불일치','지원 코드 없음','패키징·캐시 결함','의도적 미사용'}
check('seven_unused_reasons_have_actions',expected<=reasonset and all(i['resolution_and_next_action'] and i['blocking_for'] and i['next_phase'] for i in issues),{'reason_categories':sorted(reasonset),'issue_states':dict(Counter(i['status'] for i in issues))})
profile=j('RESTORATION_PROFILE.json');state=json.loads((ROOT/'docs/rebuild/STATE.json').read_text())
check('stage_and_approval_boundary',state.get('implementation_status')=='NOT_STARTED' and state.get('p2_execution_authorized') is False and profile['runtime_binding']=='NOT_STARTED',{'implementation_status':state.get('implementation_status'),'p2_execution_authorized':state.get('p2_execution_authorized'),'profile_status':profile['status']})

patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{40,}',r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}',r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}']
allowed=[]
for base in [OUT,ROOT/'tools/rebuild/step01']:
    allowed.extend(p for p in base.rglob('*') if p.is_file() and p.name!='VALIDATION.json' and not p.name.endswith('.draft.csv') and '__pycache__' not in p.parts)
allowed.extend([ROOT/'AGENTS.md',ROOT/'docs/rebuild/STATE.json'])
badtypes=[str(p.relative_to(ROOT)) for p in allowed if p.suffix not in ['.md','.json','.jsonl','.csv','.py']]
secrets=[]
for p in allowed:
    if p.suffix=='.py':continue # detector source literals are not secrets
    t=p.read_text(encoding='utf-8-sig')
    if any(re.search(pat,t) for pat in patterns):secrets.append(str(p.relative_to(ROOT)))
check('public_metadata_only_no_secret_patterns',not badtypes and not secrets,{'unexpected_file_types':badtypes,'secret_pattern_files':secrets,'note':'No original binaries, graphics/audio, real save, credential or signing-key bytes in deliverables.'})

fingerprints={str(p.relative_to(ROOT)):digest(p) for p in sorted(allowed)}
result={'task_id':'BARAM_REBUILD_P0P1_001','executed_at_utc':datetime.now(timezone.utc).isoformat(),
 'command':'python3 tools/rebuild/step01/validate_step01.py','result':'PASS' if all(c['result']=='PASS' for c in checks) else 'FAIL',
 'scope':'STATIC P0/P1 ARTIFACT/REFERENCE/BYTE VALIDATION ONLY; NOT GAMEPLAY OR HISTORICAL ACCURACY',
 'checks':checks,'input_fingerprints':fingerprints,'runtime_tests_executed':0,'p2_executed':False,
 'limitations':['Container byte inventory is not all asset semantic decoding','Original historical values and audiovisual identity remain provisional','No native Windows/Android, reference server or real account roundtrip tests']}
(OUT/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'result':result['result'],'checks':len(checks),'failures':[x for x in checks if x['result']=='FAIL'],'requirements':len(reqs),'sources':len(sources),'members':len(members),'issues':len(issues),'runtime_tests_executed':0},ensure_ascii=False))
sys.exit(0 if result['result']=='PASS' else 1)
