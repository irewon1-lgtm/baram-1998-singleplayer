#!/usr/bin/env python3
"""Actual Work-only checks: persisted IDs, rational precision, original means."""
import collections
import sys
from decimal import Decimal
sys.dont_write_bytecode=True
from common import ROOT,WORK,IDs,round_int,ratio,average,lines,load,write,file_sha,canonical

def main():
    checks=[]
    def check(name,condition,details):
        checks.append({'name':name,'result':'PASS' if condition else 'FAIL','details':details})
    check('positive_half_tie',round_int('137.5')==138,{'input':'137.5','observed':round_int('137.5')})
    check('negative_half_tie',round_int('-26.5')==-27,{'input':'-26.5','observed':round_int('-26.5')})
    rare=ratio('0.0000001');check('rare_ratio_not_zero',rare['numerator']>0 and Decimal(rare['numerator'])/rare['denominator']==Decimal('0.0000001'),rare)
    observations=[{'origin_key':'source-a','unit':'gold','condition':'same item','value':120},{'origin_key':'source-a','unit':'gold','condition':'same item','value':120},{'origin_key':'source-b','unit':'gold','condition':'same item','value':155}]
    mean=average(observations);check('duplicate_source_excluded_from_mean',mean['value']==138 and len(mean['observations'])==2,mean)
    rejected=False
    try:average([dict(observations[0],unit='XP'),observations[2]])
    except ValueError:rejected=True
    check('mixed_units_rejected',rejected,{})
    before=load(WORK/'catalog/permanent_ids.json');registry=IDs()
    for k,ident in before.items():
        kind,origin=k.split(':',1)
        if registry.get(kind,origin)!=ident:raise AssertionError(k)
    check('same_origins_preserve_all_IDs',registry.entries==before,{'IDs':len(before),'new_IDs':len(registry.entries)-len(before)})
    allrs=[r for p in (WORK/'packages/WK-CONTENT-001').glob('content-*.jsonl') for r in lines(p)]
    reversedrs=list(reversed(allrs));canonical_order=lambda rs:canonical(sorted(rs,key=lambda r:r['id']))
    check('record_order_independent',canonical_order(allrs)==canonical_order(reversedrs),{'records':len(allrs)})
    base=load(ROOT/'game/data/numeric.json')['contents'];original={v['id']:v for v in base};known_fields=0;violations=[]
    for r in allrs:
        if r['operation']!='propose_patch':continue
        for c in r['changes'][1:]:
            key=c['path'].removeprefix('values.')
            if original[r['target_id']]['values'].get(key) is not None and c['provenance_ref']!='rule.numeric.mean.rounding':violations.append([r['target_id'],key])
        known_fields+=sum(x is not None for x in original[r['target_id']]['values'].values())
    check('existing_non_null_fields_only_authorized_mean_repair',not violations,{'retained_fields':known_fields,'allowed_exception':'Explicit guarded KR_MEAN integer rounding','violations':violations})
    mean_rows=[x for x in lines(ROOT/'research/restoration-integrated-20261013/NUMERIC_MASTER.jsonl') if x['classification']=='KR_MEAN']
    proposed={r['target_id']:{c['path'].removeprefix('values.'):c['after'] for c in r['changes'][1:]} for r in allrs if r['operation']=='propose_patch'}
    bad=[x['field_id'] for x in mean_rows if round_int(x['raw_average'])!=proposed[x['content_id']].get(x['field'],x['value'])]
    check('inherited_means_half_away_after_guarded_proposal',not bad,{'source_rows':len(mean_rows),'mismatches':bad,'source_sha256':file_sha(ROOT/'research/restoration-integrated-20261013/NUMERIC_MASTER.jsonl')})
    report={'result':'PASS' if all(c['result']=='PASS' for c in checks) else 'FAIL','scope':'ACTUAL_WORK_GENERATION_RULES_AND_CURRENT_DATA_NOT_GAMEPLAY','command':'python3 content-work/tools/check_reproducibility.py','checks':checks}
    write(WORK/'catalog/reproducibility.json',report);print(report['result'],len(checks),'checks')
    return report['result']!='PASS'
if __name__=='__main__':raise SystemExit(main())
