#!/usr/bin/env python3
"""Incremental semantic/visual repairs; never rebuild fixed Work001 packages."""
import argparse
import collections
import copy
import shutil
import sys
from pathlib import Path
sys.dont_write_bytecode=True
from common import ROOT, WORK, BASE, IDs, lines, load, write, record, ref, shard, file_sha

def dependency_records():
    return [r for batch in ['WK-ASSETS-001','WK-CONTENT-001'] for p in sorted((WORK/'packages'/batch).glob('content-*.jsonl')) for r in lines(p)]

def selected_frames(asset,motions):
    md=asset['data']['metadata'];out=set()
    for name in motions:
        a=md.get('animations',{}).get(name)
        if a:out.update(range(a['offset'],a['offset']+a['directions']*a['frames_per_direction']))
    return sorted(out)

def data_refs(data, assets):
    out=[];seen=set()
    def walk(v,k='definition'):
        if isinstance(v,dict):
            for name,x in v.items():
                if name.endswith('_id') and isinstance(x,str) and x.startswith(('kr.','wk.')):
                    key=(name,x)
                    if key not in seen:out.append(ref(name,x));seen.add(key)
                elif name.endswith('_ids') and isinstance(x,list):
                    for iid in x:
                        if isinstance(iid,str) and iid.startswith(('kr.','wk.')) and (name,iid) not in seen:
                            out.append(ref(name,iid));seen.add((name,iid))
                walk(x,name)
        elif isinstance(v,list):
            for x in v:walk(x,k)
    walk(data)
    vis=data.get('visual',{})
    if vis.get('icon_id') in assets:out.append(ref('icon',vis['icon_id'],{'frame':vis['icon_frame']}))
    aid=vis.get('equipment_asset_id') or vis.get('asset_id')
    if aid in assets:
        family=aid.split('.')[3]
        motions=['walk_unarmed','walk_sword','attack_sword','walk_spear','attack_spear','cast','pickup'] if family=='body' else ['walk','attack']
        if 'motion' in vis and vis['motion']=='walk':motions=['walk']
        fs=selected_frames(assets[aid],motions)
        if fs:out.append(ref('selected_animation_frames',aid,{'frames':fs,'motions':motions,'scope':'DECLARED_SELECTION_NOT_PLAYED'}))
    return out

def patch_record(ids,old,after,fields,rule,label='links'):
    target=old.get('target_id',old['id']);kind=old['kind']
    r=record(ids.get(kind,'exp2.'+label+'.'+target),kind,after,[rule])
    r.update(operation='propose_patch',target_id=target,base_game_commit=BASE,changes=[])
    prefix='runtime_definition.' if old.get('target_id','').startswith('kr.') else ''
    for field in fields:
        b=old['data'];a=after;parts=field.split('.')
        for part in parts[:-1]:b=b[part];a=a[part]
        name=parts[-1]
        before={'exists':name in b}
        if name in b:before['value']=copy.deepcopy(b[name])
        if name in b and b[name]==a[name]:continue
        r['changes'].append({'path':prefix+field,'before':before,'after':copy.deepcopy(a[name]),
           'reason':'Purpose-compatible reviewed source model or semantic repair; only this field changes',
           'provenance_ref':rule})
    return r

def build(batch):
    rs=dependency_records();assets={r['id']:r for r in rs if r['kind']=='asset'}
    eff={r.get('target_id',r['id']):r for r in rs if r['kind']!='asset'};ids=IDs();records=[];rows=[]
    bindings=load(ROOT/'game/data/runtime_bindings.json');known_icons=bindings['icons']
    # Reviewed weapon silhouettes. Bows and bare shadows are intentionally excluded.
    blades=[0,1,2,3,5,6,7,8,9,10,11,16,17,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,44,45,46,47,48,49,52,53,54,55,61,63,64,65,66,67,68,69,70,76,77,78,79,80,81,82,83,84,85,86,87,88]
    clubs=[22,60,89];axes=[18,19,41,58];staff=[12,13,50,51,56,57,73,74,75]
    robes=[6,18,20,24,27,29,35,38,40,41,42,48,49,50,52,54,55,56,65]
    garments=[0,1,2,3,4,5,7,8,9,10,11,12,13,14,15,16,17,19,21,22,23,25,26,28,30,31,32,33,34,36,37,39,43,44,45,46,47,51,53,57,58,59,60,61,62,63,64]
    counter=collections.Counter();reclassified=[];aggregates=[]
    for iid,old in sorted(eff.items(),key=lambda t:(t[1]['data'].get('requirements',{}).get('level',0),t[1]['data'].get('name',''),t[0])):
        if old['kind']!='item':continue
        d=copy.deepcopy(old['data']);name=d['name'];slot=d['slot'];fields=[];reason=[]
        if '~' in name and any(x in name for x in ['드레스','망또']):
            d['flags'].update(obtainable=False,buyable=False,sellable=False,droppable=False)
            d['historical_status']='SOURCE_RANGE_LABEL_RETAINED_AS_INACTIVE_AGGREGATE_INDIVIDUAL_IDS_PRESERVED'
            fields+=['flags','historical_status'];aggregates.append(iid)
        elif slot=='none' and any(x in name for x in ['망또','드레스','산타클로스옷']):
            d.update(slot='body',item_type='armor',stack_limit=1)
            d['stats']['durability']=max(1000,d['stats']['durability']);slot='body';fields+=['slot','item_type','stack_limit','stats'];reclassified.append(iid)
        elif slot=='none' and name.endswith('제삼검'):
            d.update(slot='weapon',item_type='weapon',stack_limit=1)
            lv=d['requirements']['level'];d['stats'].update(damage_min=max(1,2+int(lv*.6)),damage_max=max(1,4+int(lv*.9)),durability=10000)
            slot='weapon';fields+=['slot','item_type','stack_limit','stats'];reclassified.append(iid)
        if slot in ('body','weapon'):
            lv=d['requirements']['level']
            if slot=='body':
                cat='robe' if any(x in name for x in ['포','삼','망또','드레스','천의']) else 'garment';pool=robes if cat=='robe' else garments;family='body'
                model=17 if '산타' in name else 15 if '드레스' in name else pool[counter[cat]%len(pool)]
            else:
                cat='spear' if any(x in name for x in ['창','봉']) else 'fan' if any(x in name for x in ['선류','부채']) else 'staff' if any(x in name for x in ['지팡이','장','술사']) else 'club' if any(x in name for x in ['목도','곤봉','철퇴']) else 'axe' if '도끼' in name else 'blade'
                pool=list(range(29)) if cat=='spear' else [0,1,2] if cat=='fan' else staff if cat=='staff' else clubs if cat=='club' else axes if cat=='axe' else blades
                model=pool[counter[cat]%len(pool)];family='spear' if cat=='spear' else 'fan' if cat=='fan' else 'sword'
            counter[cat]+=1;aid=f'wk.asset.kr491.{family}.{model:03d}'
            vis=d['visual'];vis.update(equipment_asset_id=aid,attachment='BODY_REPLACEMENT' if slot=='body' else 'ORIGINAL_FOOT_OVERLAY',identity='REVIEWED_PURPOSE_COMPATIBLE_ORIGINAL_PIXELS_INFERRED_NAME')
            if slot=='weapon':vis['motion']='spear' if family=='spear' else 'sword'
            if name not in known_icons:
                # Original sheet representatives reviewed: blade0, staff34, club18,
                # clothes12; no icon17 (empty box) as an inferred sword any more.
                vis['icon_frame']=12 if slot=='body' else 34 if cat=='staff' else 18 if cat=='club' else 6 if cat=='spear' else 37 if cat=='fan' else 0
            fields.append('visual');reason.append('clothing/weapon model role')
        elif slot in ('head','accessory') and 'equipment_asset_id' in d['visual']:
            # Head models contain faces/hair; shields cannot represent rings/gloves.
            # Retain actual icons and stats while requiring verified gear overlays.
            vis=d['visual'];vis.pop('equipment_asset_id',None);vis.pop('attachment',None)
            vis['identity']='ICON_AND_STATS_AVAILABLE_HEADWEAR_OR_ACCESSORY_OVERLAY_NOT_IDENTIFIED'
            fields.append('visual');reason.append('remove incompatible whole-head/shield overlay')
        if not fields:continue
        r=patch_record(ids,old,d,list(dict.fromkeys(fields)),'rule.exp2.item-role')
        if not r['changes']:continue
        r['references']=data_refs(d,assets);records.append(r)
        rows.append({'target_id':iid,'kind':'item','fields':[c['path'] for c in r['changes']],'role':d['item_type'],'name':name,'frame_selection':'references[].selector','reason':reason})
    replacements={'bat':105,'bear':293,'pig':170,'tiger':166,'scorpion':168,'spider':243,'monkey':136,'deer':181,'chicken':28,'bull':99}
    for iid,old in sorted(eff.items()):
        if old['kind']!='monster':continue
        d=copy.deepcopy(old['data']);fam=d.get('family');model=replacements.get(fam)
        if model is None:continue
        if '가재' in d['name']:model=286
        if fam=='deer':
            # Source181 is a horned round beast, not a verified deer. Do not
            # silently label the earlier goat-skull representative as a deer.
            continue
        d['visual'].update(asset_id=f'wk.asset.kr491.monster.{model:03d}',semantic_match='VISUALLY_REVIEWED_FAMILY_REPLACEMENT_NAME_UNVERIFIED')
        r=patch_record(ids,old,d,['visual'],'rule.exp2.monster-role')
        if r['changes']:r['references']=data_refs(d,assets);records.append(r);rows.append({'target_id':iid,'kind':'monster','name':d['name'],'family':fam,'asset_id':d['visual']['asset_id']})
    # Occupation-compatible human models, never rocks/totems or bare shadows.
    npc_models={'smith':[38,194,302,304],'cloth':[5,7,13,80,82,200,201,204],
       'inn':[14,85,206,294,321],'grocer':[4,15,53,54,79,180,273],'trainer':[63,64,65,66,300],
       'revive':[9,205,211,238],'craft':[8,51,67,68,69,202,203,207,209,270,271,272]}
    counts=collections.Counter()
    for iid,old in sorted(eff.items()):
        if old['kind']!='npc' or not old['data'].get('placements'):continue
        d=copy.deepcopy(old['data']);role=d.get('role','craft');pool=npc_models[role];model=pool[counts[role]%len(pool)];counts[role]+=1
        d['visual'].update(asset_id=f'wk.asset.kr491.monster.{model:03d}',identity='REVIEWED_HUMAN_OCCUPATION_REPLACEMENT_NOT_SOURCE_PERSON_ID')
        r=patch_record(ids,old,d,['visual'],'rule.exp2.npc-role')
        if r['changes']:r['references']=data_refs(d,assets);records.append(r);rows.append({'target_id':iid,'kind':'npc','name':d['name'],'role':role,'asset_id':d['visual']['asset_id']})
    # Remove disabled range-label aggregate offers; each real variation stays.
    for iid,old in sorted(eff.items()):
        if old['kind']!='shop':continue
        d=copy.deepcopy(old['data']);d['offers']=[o for o in d['offers'] if o['item_id'] not in aggregates]
        if d['offers']==old['data']['offers']:continue
        r=patch_record(ids,old,d,['offers'],'rule.exp2.item-role');r['references']=data_refs(d,assets);records.append(r)
    package=WORK/'packages'/batch
    if package.exists():raise ValueError('New batch required; frozen outputs are immutable')
    (package/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',package/'schema/content-v1.json')
    rules=[{'id':'rule.exp2.item-role','source_mode':'INFERRED','basis':['preserved Korean item names and slot patterns','reviewed original KR491 model silhouettes','existing source numeric fields left unchanged'],
      'rules':{'garments':'cloak/dress/Santa clothes equip as body, no invented combat bonus','swords':'name ending 제삼검 is a weapon; missing stats reuse rule.item.complete','visuals':'source pixels reused; shape-compatible association only, names unverified','overlays':'faces/hair do not become helmets; shields do not become gloves/rings','aggregate':'range labels inactive; individual identities preserved','frames':'actual selected motion ranges only; no whole sheet utilization claim'}},
      {'id':'rule.exp2.monster-role','source_mode':'INFERRED','basis':['KR491 full327 model contact sheet','earlier mismatched family replacements'],
       'rules':{'correction':'bat105, bear293, boar170, spotted feline166, scorpion168, crab286, spider243, monkey136, bird28, bovine99','limit':'representative silhouette reviewed, full-animation visual and historical name identity NOT_RUN'}},
      {'id':'rule.exp2.npc-role','source_mode':'INFERRED','basis':['reviewed human source model representatives','existing NPC service occupation'],
       'rules':{'identity':'occupation-compatible visual; no original person-name attribution','frames':'walk only for NPC, all source walk directions selected; attack frames not counted'}}]
    write(package/'provenance.json',rules);shard(package,records)
    write(package/'changes-summary.json',{'scope':'DATA_ONLY','existing_definition_patches':len(records),'new_definitions':0,
        'misclassified_items_repaired':reclassified,'inactive_source_range_labels':aggregates,'counts':dict(collections.Counter(r['kind'] for r in records)),
        'work_review':'300 equipment and327 actor representatives; not all frame animations','rows':rows,
        'imported':'NOT_RUN','play_verified':'NOT_RUN'})
    ids.save();print(batch,len(records),dict(collections.Counter(r['kind'] for r in records)),len(reclassified),'semantic corrections')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);build(p.parse_args().batch)
