#!/usr/bin/env python3
"""Use retained native fire/lightning pixels for explicitly reconstructed bindings.

Only unmatched fallback and explicitly reconstructed G2 associations change. Exact RGB guide matches remain.
This is an art-direction reconstruction, not historical spell-ID evidence.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def repair(runtime):
    runtime=Path(runtime);p=runtime/'gameplay_content.json';d=json.loads(p.read_text());before=sha(p)
    visual_fields={'effect_id','effect_asset_binding','visual_repair'}
    executable_before={sid:{k:v for k,v in skill.items()if k not in visual_fields}for sid,skill in d['skills'].items()}
    compatibility_before=json.dumps(d['compatibility'],sort_keys=True);accepted_before=json.dumps(d.get('accepted_compatibility',[]),sort_keys=True)
    effects={int(e['id']) for e in json.loads((runtime/'kr491/kr491_runtime.json').read_text())['effects']};changed=[]
    for sid,s in d['skills'].items():
        binding=s.get('effect_asset_binding',{})
        g2_reconstruction=s.get('generation')=='G2' and not binding
        if not g2_reconstruction and ('FALLBACK' not in binding.get('method','') or s.get('kind') not in ['damage','debuff','status']):continue
        name=''.join(s['name'].split());eid=None;family=None
        if s.get('kind') in ['debuff','status'] and s.get('status')=='poison':eid=19;family='poison_green_native_outline'
        elif any(x in name for x in ['화염','화열','화계','화안']):eid=7;family='fire_red_orange_native_swirl'
        elif any(x in name for x in ['뢰격','뇌전','번개']):eid=68;family='lightning_bright_blue_native_burst'
        if eid is None and g2_reconstruction:
            kind=s.get('kind');job=s.get('job')
            if kind=='damage':eid=5 if job=='전사' else 6 if job=='도적' else 0;family='melee_native_slash' if job in ['전사','도적'] else 'native_magic_spark'
            elif kind in ['heal','cleanse','revive']:eid=4;family='native_healing_crescent'
            elif kind=='restore_mp':eid=64;family='native_golden_restoration'
            elif kind in ['buff','debuff','status']:eid=20 if s.get('status')=='stealth' else 19 if s.get('status')=='poison' else 2;family='native_status_outline_or_ring'
            elif kind in ['blink','return','shrine']:eid=9;family='native_mobility_ring'
            else:eid=0;family='native_magic_spark'
        if eid is None or int(s['effect_id'])==eid:continue
        if eid not in effects:raise ValueError(f'Required retained effect absent: {eid}')
        old=s['effect_id'];s['effect_id']=eid
        if not binding:
            binding={'content_id':sid,'field':'effect_id','source_tier':'LEGACY_RECONSTRUCTED','runtime_ref':'skills.'+sid+'.effect_id','source_ref':'G2_APPROVED_RECONSTRUCTION'}
            s['effect_asset_binding']=binding
        binding.update(selected_value=eid,previous_reconstructed_effect_id=old,
          method='VISUALLY_SELECTED_NATIVE_FAMILY_RECONSTRUCTION',status='RECONSTRUCTED_FAMILY_RUNTIME_TEST_NOT_RUN',
          rationale='Existing native pixels selected after contact-sheet and production-frame visual review for explicit spell-name semantics. Exact skill-to-Effect.tbl ID/timing/audio is not historically established.')
        binding['dependencies']=['KR491:effect_sequence:'+str(eid)]
        s['visual_repair']={'source_tier':'LEGACY_RECONSTRUCTED','family':family,'exact_historical_binding':False,
         'rationale':'Fire and lightning names previously shared dark cyan circles; native retained red fire and blue burst improve visible differentiation.'}
        changed.append({'skill_id':sid,'name':s['name'],'job':s['job'],'old_effect_id':old,'new_effect_id':eid,'family':family})
    assert executable_before=={sid:{k:v for k,v in skill.items()if k not in visual_fields}for sid,skill in d['skills'].items()}
    assert compatibility_before==json.dumps(d['compatibility'],sort_keys=True) and accepted_before==json.dumps(d.get('accepted_compatibility',[]),sort_keys=True)
    if changed:
        d['visual_effect_repair']={'version':'B5-r16-native-effect-semantics','tool_sha256':sha(Path(__file__)),'changes':changed,'exact_guide_matches_preserved':True,'gameplay_actions_stats_and_save_contracts_preserved':True}
        d['manifest_sha256']=hashlib.sha256(json.dumps({'parent_manifest_sha256':d['manifest_sha256'],'visual_effect_repair':d['visual_effect_repair']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    write(p,d)
    manifest_path=runtime/'runtime.json';manifest=json.loads(manifest_path.read_text())
    for f in manifest['files']:
        if f['path']=='gameplay_content.json':f['sha256']=sha(p);f['bytes']=p.stat().st_size
    manifest['input_definitions_sha256']=sha(p)
    manifest['fingerprint']=hashlib.sha256(json.dumps(sorted(manifest['files'],key=lambda f:f['path']),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest['files']=sorted(manifest['files'],key=lambda f:f['path'])
    write(manifest_path,manifest)
    report={'schema':'baram.repair.native-effect-semantics/1','status':'RECONSTRUCTED_BINDINGS_UPDATED_RUNTIME_TEST_NOT_RUN',
      'before_content_sha256':before,'after_content_sha256':sha(p),'changes':changed,
      'exact_guide_matches_preserved':True,'original_pngs_changed':False,'historical_match_claim':False}
    write(runtime/'EFFECT_VISUAL_REPAIR.json',report)
    manifest['files']=[{'path':str(f.relative_to(runtime)),'bytes':f.stat().st_size,'sha256':sha(f)}for f in sorted(runtime.rglob('*'))if f.is_file() and f.name!='runtime.json']
    manifest['fingerprint']=hashlib.sha256(json.dumps(manifest['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    write(manifest_path,manifest)
    print(json.dumps({'changes':len(changed),'by_family':{k:sum(r['family']==k for r in changed)for k in set(r['family']for r in changed)}},ensure_ascii=False));return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args();repair(a.runtime)
