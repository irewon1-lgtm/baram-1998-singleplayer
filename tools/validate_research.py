#!/usr/bin/env python3
"""원장 내부 참조/미확인 수치 격리 검사. 1998 원본 정확도 검증 아님."""
from pathlib import Path
import json, sys, hashlib
BASE = Path(__file__).resolve().parents[1]
LEDGER = BASE / 'research' / 'v1' / '1998_4.0_source_ledger.json'

def checks():
    errors = []
    data=json.loads(LEDGER.read_text(encoding='utf-8'))
    sources=data.get('sources',[])
    facts=data.get('facts',[])
    sids=[s.get('id') for s in sources]
    fids=[f.get('id') for f in facts]
    if len(set(sids)) != len(sids): errors.append('duplicate source ID')
    if len(set(fids)) != len(fids): errors.append('duplicate fact ID')
    allowed=set(data.get('status_legend',{}))
    for f in facts:
        if f.get('status') not in allowed: errors.append(f"{f.get('id')} unknown status")
        for id_ in f.get('source_ids',[]):
            if id_ not in sids: errors.append(f"{f.get('id')}: dangling {id_}")
        if f.get('status')=='CONFIRMED_OFFICIAL' and not any(
            id_ in {s['id'] for s in sources if s['origin'].startswith('NEXON')} for id_ in f.get('source_ids',[])
        ): errors.append(f"{f.get('id')}: official not backed by official source")
    def no_unverified_numbers(o,path='numeric_original_values'):
        if isinstance(o,dict):
            for k,v in o.items():
                if k in {'max_hp','max_mp','attack_min','attack_max','defense','experience','attack_interval_ms','respawn_sec',
                         'experience_table','total_exp','hp_requirement_by_job','mp_requirement_by_job',
                         'mana_costs','damage_formulas','equipment_stats','drop_chances','drop_rates',
                         'vendor_prices'} and v is not None:
                    errors.append(f'{path}/{k} nonnull original numeric field without new audit')
                if isinstance(v,(dict,list)): no_unverified_numbers(v,path+'/'+k)
        elif isinstance(o,list):
            for i,v in enumerate(o): no_unverified_numbers(v,path+'/'+str(i))
    no_unverified_numbers(data.get('numeric_original_values',{}))
    strict=json.loads((BASE/'data'/'strict_1998_rules.json').read_text(encoding='utf-8'))
    assumed=json.loads((BASE/'data'/'assumed_dev_rules.json').read_text(encoding='utf-8'))
    if strict.get('numeric_rules_status')!='BLOCKED_UNVERIFIED': errors.append('strict numeric verified without evidence')
    if strict.get('monsters') or strict.get('experience_levels_1_to_99') is not None: errors.append('strict original data populated')
    if assumed.get('classification')!='ASSUMED_GAMEPLAY': errors.append('assumed rules mislabeled')
    expected=(BASE/'research'/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    for line in expected:
        if not line.strip() or line.startswith('#'): continue
        h,rel=line.split('  ',1)
        p=BASE/rel
        if not p.is_file():
            if rel.startswith('research/archive/'):
                print('NOTE: original ZIP is stored separately; source files are verified in this checkout')
                continue
            errors.append(f'archive missing: {rel}'); continue
        got=hashlib.sha256(p.read_bytes()).hexdigest()
        if got!=h: errors.append(f'archive SHA mismatch: {rel}')
    return errors,len(sources),len(facts)

if __name__=='__main__':
    errors,ns,nf=checks()
    if errors:
        print('FAIL: internal research integrity:',*errors,sep='\n- ')
        sys.exit(1)
    print(f'PASS: research ledger structure and archive hashes | sources={ns} facts={nf} | 1998 original numeric verified=0')
    print('NOTE: gameplay/build/1998 numerical reproduction: NOT TESTED / BLOCKED')
