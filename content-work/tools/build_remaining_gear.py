#!/usr/bin/env python3
"""Use the remaining compatible original weapons, then optional fans/shields."""
import argparse,collections,copy,shutil,sys
sys.dont_write_bytecode=True
from common import WORK,IDs,load,lines,write,record,shard,ratio,round_int
from build_expansion_links import patch_record,data_refs

WEAPONS=[
 ('sword',40,'가시줄기 곤봉','warrior',35,'forest','hp'),
 ('sword',41,'광맥 쪼개기 도끼','warrior',55,'cave','strength'),
 ('sword',42,'나무결 지팡이','poet',35,'forest','mp'),
 ('sword',43,'구름결 법장','mage',75,'water','intelligence'),
 ('sword',62,'굽은 사구 칼','rogue',55,'dry','dexterity'),
 ('sword',76,'황혼 수호검','warrior',75,'dry','hp'),
 ('sword',79,'설맥 곡도','rogue',95,'snow','dexterity'),
 ('sword',80,'푸른 침날','rogue',75,'water','damage'),
 ('sword',83,'은결 단검','rogue',55,'water','damage'),
 ('sword',84,'넓은 달날','warrior',95,'snow','damage'),
 ('sword',85,'초행 사냥칼','rogue',15,'forest','dexterity'),
 ('sword',86,'길목 세검','warrior',35,'cave','damage'),
 ('sword',89,'나무결 몽둥이','warrior',15,'forest','hp'),
 ('spear',20,'등불 수호창','warrior',35,'cave','hp'),
 ('spear',21,'설깃 창','poet',55,'snow','mp'),
 ('spear',22,'쌍월 긴창','warrior',55,'water','damage'),
 ('spear',23,'사구 불꽃봉','mage',75,'dry','intelligence'),
 ('spear',24,'푸른 광맥봉','mage',55,'cave','mp'),
 ('spear',25,'마른가지 창','rogue',35,'dry','dexterity'),
 ('spear',26,'백송 수호봉','poet',75,'snow','mp'),
 ('spear',27,'달갈퀴 봉','poet',95,'water','intelligence'),
 ('spear',28,'푸른갈래 창','warrior',95,'fire','strength')]

def build(batch,optional,bows=False):
    idx=load(WORK/'HANDOFF_INDEX.json');assets={};defs={}
    for entry in idx['packages']:
        if bows and entry['batch_id'] in ('WK-ASSETS-002','WK-ASSETS-003','WK-CONTENT-006','WK-CONTENT-008'):continue
        for p in sorted((WORK/'packages'/entry['batch_id']).glob('content-*.jsonl')):
            for r in lines(p):(assets if r['kind']=='asset' else defs)[r.get('target_id',r['id'])]=r
    ids=IDs();rs=[];updates={};summary=[]
    regions=load(WORK/'packages/WK-CONTENT-003/region-summary.json')['regions']
    specs=WEAPONS if not optional else [
       ('fan',0,'흰잎 여행선','poet',35,'forest','mp'),('fan',1,'푸른숲 보호선','poet',75,'water','hp'),('fan',2,'설빛 정화선','mage',95,'snow','intelligence')]
    if bows:specs=[('sword',14,'초행 사냥활','warrior',15,'forest','dexterity'),('sword',15,'굽은 사구활','rogue',55,'dry','damage'),('sword',59,'푸른 귀환활','rogue',95,'water','dexterity')]
    if optional:
        names=['나무결 방패','작은 가죽방패','세칸 강철방패','나무살 원방패','뿔결 방패','청석 방패','설철 방패','보랏결 방패','석벽 방패','곡목 방패','격자 강철방패','풀결 방패','백철 방패']
        themes=['forest','forest','cave','dry','dry','water','snow','snow','cave','forest','fire','forest','snow']
        for model,name in enumerate(names):
            lv=[10,20,35,45,55,65,75,85,55,45,95,35,99][model]
            specs.append(('shield',model,name,'warrior' if model%3==0 else 'poet' if model%3==1 else 'rogue',lv,themes[model],'hp' if model%2==0 else 'mp'))
    for family,model,name,job,level,theme,focus in specs:
        aid=f'wk.asset.kr491.{family}.{model:03d}';assert aid in assets
        source_key=f'exp3.source-bow.{model}' if bows else f'exp3.source-{family}.{model}'
        iid=ids.get('item',source_key);rid=ids.get('recipe',source_key)
        reg=min((r for r in regions if r['theme']==theme),key=lambda r:abs(sum(r['levels'])/2-level));npc=reg['smith_id'];cid='wk.class.'+job
        candidates=[r['data'] for r in defs.values() if r['kind']=='item' and r['data']['slot']=='weapon' and cid in r['data']['requirements']['class_ids'] and not r['data']['requirements'].get('advancement_rank')]
        base=min(candidates,key=lambda d:(abs(d['requirements']['level']-level),d['name']));d=copy.deepcopy(base)
        d.update(name=name,item_type='armor' if family=='shield' else 'weapon',slot='offhand' if family=='shield' else 'weapon',extension=True,historical_status='AUTHORED_SOURCE_MODEL_EQUIPMENT_NOT_ORIGINAL_ITEM_NAME')
        d['requirements']={'level':level,'strength':0,'class_ids':[cid],'gender':'any'}
        stats={k:0 for k in base['stats']};stats['durability']=10000+level*80
        scale=max(1,level)/max(1,base['requirements']['level'])
        if family=='shield':stats['armor_class']=-max(1,level//5);stats['hp_bonus']=level*15;stats['mp_bonus']=level*4
        else:
            for k in ['damage_min','damage_max']:stats[k]=max(1,round_int(base['stats'][k]*scale*(1.2 if focus=='damage' else .9)))
            stats[{'hp':'hp_bonus','mp':'mp_bonus','strength':'strength_bonus','dexterity':'dexterity_bonus','intelligence':'intelligence_bonus','damage':'damage_max'}[focus]]+=level*(8 if focus in ('hp','mp') else 1 if focus=='damage' else .1)
            stats={k:round_int(v) for k,v in stats.items()}
        d['stats']=stats;d['stack_limit']=1;d['prices']={'buy':level*level*14+100,'sell':level*level*4+20,'unit':'gold'}
        d['flags']={'obtainable':True,'usable':False,'buyable':False,'sellable':True,'droppable':True,'quest_bound':False};d['use_effects']=[]
        d['visual']={'icon_id':'wk.asset.kr491.sheet.item','icon_frame':12 if family=='shield' else 37 if family=='fan' else 6 if family=='spear' else 18 if model in [40,89] else 34 if job in ('mage','poet') else 0,
                     'equipment_asset_id':aid,'attachment':'ORIGINAL_FOOT_OVERLAY','motion':'spear' if family=='spear' else 'sword','identity':'REVIEWED_SOURCE_SHAPE_AUTHORED_ITEM_IDENTITY'}
        d['acquisition']=[{'kind':'recipe','recipe_id':rid,'source_mode':'INFERRED'}]
        if bows:d['visual']['weapon_family']='bow'
        rec=record(iid,'item',d,['rule.exp3.remaining-gear']);rec['references']=data_refs(d,assets);rs.append(rec)
        material='wk.item.exp2.material.'+theme;cost=d['prices']['sell']+level*10+50
        rd={'name':name+' 제작','npc_id':npc,'consume':[{'item_id':material,'quantity':2+level//12}], 'outputs':[{'item_id':iid,'quantity':1}],'gold_cost':cost,'success_ratio':ratio(1),'extension':True}
        rec=record(rid,'recipe',rd,['rule.exp3.remaining-gear']);rec['references']=data_refs(rd,assets);rs.append(rec)
        if npc not in updates:updates[npc]=[defs[npc],copy.deepcopy(defs[npc]['data'])]
        nd=updates[npc][1];nd['services'].append({'type':'recipe_book','recipe_id':rid});nd['dialogue'][0]['choices'].append({'label':name+' 제작','service_index':len(nd['services'])-1})
        summary.append({'item_id':iid,'source_model':aid,'class_id':cid,'level':level,'region':reg['key'],'focus':focus,'recipe_id':rid})
    for target,(old,d) in updates.items():
        r=patch_record(ids,old,d,['services','dialogue'],'rule.exp3.remaining-gear','remaining-gear-'+batch.lower());r['references']=data_refs(d,assets);rs.append(r)
    bow_repairs=[]
    if not optional and not bows:
        for target,old in defs.items():
            if old['kind']!='item' or old['data']['visual'].get('equipment_asset_id') not in ['wk.asset.kr491.sword.014','wk.asset.kr491.sword.015','wk.asset.kr491.sword.059']:continue
            d=copy.deepcopy(old['data']);d['visual']['equipment_asset_id']='wk.asset.kr491.sword.057' if 'wk.class.poet' in d['requirements']['class_ids'] else 'wk.asset.kr491.sword.073'
            r=patch_record(ids,old,d,['visual.equipment_asset_id'],'rule.exp3.remaining-gear','bow-repair');r['references']=data_refs(d,assets);rs.append(r);bow_repairs.append(target)
    p=WORK/'packages'/batch
    if p.exists():raise ValueError('Use a new immutable package')
    (p/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',p/'schema/content-v1.json');shard(p,rs);ids.save()
    write(p/'provenance.json',[{'id':'rule.exp3.remaining-gear','source_mode':'INFERRED','basis':['remaining reviewed original sword/spear/fan/shield silhouettes','nearest level compatible-class non-advancement weapon definitions and existing regional crafters/materials'],
      'rules':{'identity':'authored distinct weapons/shields, not historical item-name proof','role':'class/level/region/focus/acquisition purpose retained; source variants not counted as new graphics','stats':'nearest compatible template scaled to authored level; distinct HP/MP/primary-stat or damage focus','craft':'existing material consumption and NPC recipe_book; fee exceeds output resale value','bow_reserve':'sword models14/15/59 are bows; existing model59 mismatch repaired with compatible caster staff, no numeric changes','optional':'fan and shield models require declared family attachment/offhand capabilities; optional packet does not block ordinary sword/spear packet'}}])
    if bows:
        write(p/'bow-consumer-requirements.json',{'scope':'RECEIVER_CAPABILITY_REQUIREMENTS_NOT_IMPLEMENTED_HERE','source_family':'Original Sword TBL models14/15/59 are bow silhouettes; retain their source frame/foot offset selections.',
            'item_ids':[x['item_id'] for x in summary],'attack_purpose':'physical ranged weapon attack; do not activate as an ordinary melee weapon merely because its source table is named Sword',
            'authored_range_tiles':6,'requirements':['verify source bow firing pose attachment in four directions','use existing physical damage/hostile target checks, range and source directional collision checks','one damage application per attack; no remote damage through a blocking wall','persist item ownership/equipment and reject unsupported optional packet'],
            'projectile_graphic':'UNRESOLVED: original bow.epf contains zero frames. No new arrow pixels or claimed source arrow animation.',
            'game_import':'NOT_RUN','gameplay':'NOT_RUN'})
    write(p/'gear-summary.json',{'scope':'DATA_ONLY','new_items':len(specs),'new_recipes':len(specs),'existing_npc_proposals':len(updates),'bow_repairs':bow_repairs,'optional_new_capabilities':optional or bows,'bow_packet':bows,'definitions':summary,'game_import':'NOT_RUN','gameplay':'NOT_RUN'})
    print(batch,dict(collections.Counter(r['kind'] for r in rs)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);m=p.add_mutually_exclusive_group();m.add_argument('--optional',action='store_true');m.add_argument('--bows',action='store_true');a=p.parse_args();build(a.batch,a.optional,a.bows)
