#!/usr/bin/env python3
"""Add rank1 training paths, gear and visually matched original spell effects."""
import argparse,collections,copy,shutil,sys
sys.dont_write_bytecode=True
from common import ROOT,WORK,BASE,IDs,load,lines,write,record,ref,shard,ratio
from build_expansion_links import patch_record,data_refs

POOLS={'fire':[7,18,39,40,41,42,44,45,46,47,50,53,54,55,61,93,101,103,111],
 'lightning':[3,6,8,17,26,27,28,29,68,69,87,94,123],
 'heal':[57,107,109,120,122], 'ice':[22,23,24,25,43,51,75,98,112,119],
 'poison':[12,13,15,16,21,52,58,100],
 'buff':[2,4,9,10,11,19,20,56,60,62,63,64,65,74,76,78,83,84,88,90,108,114,115,117,118,121],
 'slash':[5,14,30,31,32,33,59,66,67,73,79,80,81,82,89,113], 'teleport':[34,35,36,37,38,95,97]}
SPECS=[
 ('warrior','석맥 베기','damage',5,'enemy',1,0,40000,7000,0,0),
 ('warrior','문지기 태세','armor',84,'self',0,0,15,3000,0,30000),
 ('warrior','강행 수련','strength',83,'self',0,0,8,4000,0,15000),
 ('rogue','그늘 갈무리','damage',59,'enemy',1,1,32000,6000,0,0),
 ('rogue','정적의 눈','attack_multiplier',60,'self',0,0,2,3000,0,10000),
 ('rogue','독기 씻기','remove_status',100,'self',0,0,0,1000,0,0),
 ('mage','설맥 냉광','damage',22,'enemy',6,2,36000,8000,0,0),
 ('mage','석류 뇌격','damage',68,'enemy',6,0,50000,10000,0,0),
 ('mage','마력 갈무리','restore_mp',74,'self',0,0,9000,0,10000,0),
 ('poet','여행자 기원','heal_hp',109,'self_or_ally',6,0,40000,6000,0,0),
 ('poet','서리막','damage_reduction',75,'self',0,0,20,4000,0,10000),
 ('poet','맑은 기운','remove_status',120,'self_or_ally',6,0,0,500,0,0)]

def build(batch):
    defs={};assets={}
    for b in ['WK-ASSETS-001','WK-CONTENT-001','WK-CONTENT-002','WK-CONTENT-003']:
        for p in sorted((WORK/'packages'/b).glob('content-*.jsonl')):
            for r in lines(p):(assets if r['kind']=='asset' else defs)[r.get('target_id',r['id'])]=r
    ids=IDs();records=[];updates={};used=collections.Counter();visual_patches=0
    def add(r):records.append(r);return r
    def edit(target,path,value,rule):
        if target not in updates:updates[target]=[defs[target],copy.deepcopy(defs[target]['data']),set(),rule]
        old,d,fields,rule=updates[target];parts=path.split('.');parent=d
        for part in parts[:-1]:parent=parent[part]
        parent[parts[-1]]=value;fields.add(path)
    for target,old in sorted(defs.items()):
        if old['kind']!='skill':continue
        d=old['data'];name=d['name'];ops={e['op'] for e in d['effects']};elements={e.get('element') for e in d['effects']}
        key='teleport' if 'teleport' in ops else 'heal' if 'heal_hp' in ops or 'revive' in ops else 'ice' if any(t in name for t in ['빙','설','냉','서리']) else 'fire' if 'fire' in elements else 'lightning' if 'lightning' in elements else 'poison' if any(t in name for t in ['중독','저주','혼마','혼돈','마비','절망']) else 'buff' if any(op in ops for op in ['apply_status','restore_mp','remove_status','local_message','inspect_item']) else 'slash'
        model=POOLS[key][used[key]%len(POOLS[key])];used[key]+=1;aid=f'wk.asset.kr491.effect.{model:03d}'
        if aid!=d['animation']['effect_asset_id']:edit(target,'animation.effect_asset_id',aid,'rule.exp2.effects');visual_patches+=1
    keys=['warrior','rogue','mage','poet'];titles=['전사','도적','주술사','도사'];mentors={};manuals={};newskills=collections.defaultdict(list);gear=collections.defaultdict(list)
    for job,title in zip(keys,titles):
        cid='wk.class.'+job
        mentors[job]=next(r['data']['learn']['teacher_npc_ids'][0] for r in defs.values() if r['kind']=='skill' and r['data']['class_ids']==[cid])
        qid=ids.get('quest','exp2.rank1.training.'+job);manual=ids.get('item','exp2.rank1.manual.'+job);manuals[job]=manual
        d={'name':title+' 수련 문서','item_type':'quest','slot':'none','requirements':{'level':99,'strength':0,'class_ids':[cid],'gender':'any'},
          'stats':{k:0 for k in ['damage_min','damage_max','armor_class','hp_bonus','mp_bonus','strength_bonus','dexterity_bonus','intelligence_bonus','durability']},
          'stack_limit':3,'prices':{'buy':0,'sell':0,'unit':'gold'},'flags':{'obtainable':True,'usable':False,'buyable':False,'sellable':False,'droppable':False,'quest_bound':True},'use_effects':[],
          'visual':{'icon_id':'wk.asset.kr491.sheet.item','icon_frame':20,'identity':'REVIEWED_SPELLBOOK_REPLACEMENT'},
          'acquisition':[{'kind':'quest_reward','quest_id':qid,'source_mode':'INFERRED'}],'extension':True,'historical_status':'AUTHORED_SINGLEPLAYER_RANK1_TRAINING_TOKEN'}
        add(record(manual,'item',d,['rule.exp2.rank1']))
        for slot,model in [('weapon',{'warrior':70,'rogue':81,'mage':73,'poet':74}[job]),('body',{'warrior':59,'rogue':60,'mage':64,'poet':65}[job])]:
            iid=ids.get('item','exp2.rank1.gear.'+job+'.'+slot);visual={'icon_id':'wk.asset.kr491.sheet.item','icon_frame':0 if slot=='weapon' else 12,
                'equipment_asset_id':f'wk.asset.kr491.'+('sword' if slot=='weapon' else 'body')+f'.{model:03d}',
                'attachment':'ORIGINAL_FOOT_OVERLAY' if slot=='weapon' else 'BODY_REPLACEMENT','motion':'sword' if slot=='weapon' else 'walk_unarmed','identity':'REVIEWED_PURPOSE_COMPATIBLE_ORIGINAL_MODEL'}
            stats={'damage_min':140 if slot=='weapon' else 0,'damage_max':210 if slot=='weapon' else 0,'armor_class':-40 if slot=='body' else 0,'durability':20000,
                   'hp_bonus':4000 if job in ('warrior','rogue') else 1500,'mp_bonus':5000 if job in ('mage','poet') else 1000,'strength_bonus':5 if job=='warrior' else 0,'dexterity_bonus':5 if job=='rogue' else 0,'intelligence_bonus':5 if job in ('mage','poet') else 0}
            d={'name':title+' 승급수련 '+('무기' if slot=='weapon' else '도복'),'item_type':'weapon' if slot=='weapon' else 'armor','slot':slot,
               'requirements':{'level':99,'strength':0,'class_ids':[cid],'gender':'any','advancement_rank':1},'stats':stats,'stack_limit':1,'prices':{'buy':0,'sell':0,'unit':'gold'},
               'flags':{'obtainable':True,'usable':False,'buyable':False,'sellable':False,'droppable':False,'quest_bound':True},'use_effects':[],'visual':visual,
               'acquisition':[{'kind':'quest_reward','quest_id':qid,'source_mode':'INFERRED'}],'extension':True,'historical_status':'AUTHORED_RANK1_REWARD_NOT_ORIGINAL_EQUIPMENT'}
            add(record(iid,'item',d,['rule.exp2.rank1']));gear[job].append(iid)
    for job,name,op,model,target,rng,aoe,amount,mp,hp,duration in SPECS:
        cid='wk.class.'+job;sid=ids.get('skill','exp2.rank1.'+job+'.'+str(len(newskills[job])+1));newskills[job].append(sid)
        effects=[{'op':op,'amount':amount,'scale':'flat','element':'lightning' if '뇌격' in name else 'damage'}] if op=='damage' else [{'op':op,'amount':amount,'target':'self' if target=='self' else 'selected'}] if op in ('heal_hp','restore_mp') else [{'op':'remove_status','status':'poison'}] if op=='remove_status' else [{'op':'apply_status','status':op,'magnitude':amount,'stack':'refresh_duration'}]
        d={'name':name,'class_ids':[cid],'learn':{'level':99,'money':0,'experience_cost':0,'consume':[{'item_id':manuals[job],'quantity':1}],'teacher_npc_ids':[mentors[job]],'rank':1,'once':True},
           'target':target,'range_tiles':rng,'aoe_radius_tiles':aoe,'effects':effects,'cost':{'mp':mp,'hp':hp,'hp_fraction':ratio(0),'prevent_suicide':True},
           'cooldown_ms':5000 if op=='damage' else 10000,'duration_ms':duration,'success_ratio':ratio(1),
           'animation':{'effect_asset_id':f'wk.asset.kr491.effect.{model:03d}','body_motion':'cast','direction_order':['N','W','S','E'],'impact_delay_ms':160,'front_back_order':'SOURCE_TABLE','sound_asset_id':'wk.asset.kr491.sound.003'},
           'historical_status':'AUTHORED_RANK1_OFFLINE_EXTENSION'}
        add(record(sid,'skill',d,['rule.exp2.rank1']))
    themes={'warrior':'cave','rogue':'forest','mage':'snow','poet':'water'}
    regions=load(WORK/'packages/WK-CONTENT-003/region-summary.json')['regions']
    for job in keys:
        cid='wk.class.'+job;mentor=mentors[job];qid=ids.get('quest','exp2.rank1.training.'+job)
        theme=themes[job];reg=max((r for r in regions if r['theme']==theme),key=lambda r:r['levels'][0]);material=ids.get('item','exp2.material.'+theme)
        boss=next((p for p in reversed(defs[reg['maps'][-1]]['data']['spawns']) if defs.get(p['monster_id'],{}).get('data',{}).get('spawn_rules',{}).get('boss')),None)
        objectives=[{'type':'collect','item_id':material,'count':6},{'type':'talk','npc_id':reg['scout_id'],'count':1}]
        if boss:objectives.append({'type':'kill','monster_id':boss['monster_id'],'map_id':reg['maps'][-1],'count':1})
        objectives.append({'type':'talk','npc_id':mentor,'count':1,'after_other_objectives':True})
        d={'name':dict(zip(keys,titles))[job]+' 승급 후 현장수련','start_npc_id':mentor,'complete_npc_id':mentor,
          'requirements':{'level':99,'advancement_rank':1,'class_ids':[cid]},'prerequisites':['wk.quest.advancement.'+job+'.1'],
          'objectives':objectives,'consume':[{'item_id':material,'quantity':6}],
          'rewards':[{'type':'item','item_id':manuals[job],'quantity':3}]+[{'type':'item','item_id':iid,'quantity':1} for iid in gear[job]],
          'repeat':{'mode':'once','cooldown_ms':0,'occurrence_counter':False},'completion_key':qid,'extension':True}
        add(record(qid,'quest',d,['rule.exp2.rank1']))
        edit(cid,'skill_ids',defs[cid]['data']['skill_ids']+newskills[job],'rule.exp2.rank1')
        services=copy.deepcopy(defs[mentor]['data']['services']);qs=next(s for s in services if s['type']=='quests');qs['quest_ids'].append(qid)
        edit(mentor,'services',services,'rule.exp2.rank1')
        dialogue=copy.deepcopy(defs[mentor]['data']['dialogue']);index=next(i for i,s in enumerate(services) if s['type']=='quests')
        dialogue.append({'id':'rank1_training','text':reg['name']+'의 길목 파수꾼을 찾아 수련을 시작하세요. 현지 재료 여섯 개를 모아 돌아오면 수련 문서 세 권과 직업 장비를 드립니다. 문서는 새 기술을 배울 때 한 권씩 소비되며 다시 지급되지 않습니다.',
          'choices':[{'label':'승급 후 수련 의뢰','service_index':index}]});edit(mentor,'dialogue',dialogue,'rule.exp2.rank1')
    for target,(old,d,fields,rule) in updates.items():add(patch_record(ids,old,d,sorted(fields),rule,'skills'))
    for r in records:
        r['references']=data_refs(r['data'],assets)
        if r['kind']=='skill':
            aid=r['data']['animation']['effect_asset_id'];md=assets[aid]['data']['metadata'];seq=md['front']+md['back']
            r['references'].append(ref('effect_sequence_selected',aid,{'frames':list(range(len(seq))),'scope':'SOURCE_SEQUENCE_DECLARED_NOT_PLAYED'}))
            r['references'].append(ref('effect_source_frames',md['sheet_id'],{'frames':sorted({f['frame'] for f in seq}),'scope':'DISTINCT_SOURCE_INDICES'}))
    p=WORK/'packages'/batch
    if p.exists():raise ValueError('New batch required')
    (p/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',p/'schema/content-v1.json')
    write(p/'provenance.json',[{'id':'rule.exp2.effects','source_mode':'INFERRED','basis':['119 representative original effect frames reviewed','existing199 skill names and declared effect category'],
       'rules':{'association':'element/purpose-compatible sequence pools, individual historical skill correspondence unverified','source':'front/back order, original delays and repeat metadata preserved in fixed asset definitions','stats':'no skill numeric/effect mechanics changed','counts':'effect sequence indices and underlying sheet frame indices kept distinct'}},
      {'id':'rule.exp2.rank1','source_mode':'INFERRED','basis':['existing four guild trainers and twelve advancement definitions','new reachable regional ecology and guaranteed materials'],
       'rules':{'path':'first advancement quest -> rank1 field training -> three bound manuals plus job weapon/body -> three new learned skills','bound':'manuals and gear cannot be sold/dropped; manuals consumed only on successful one-time learning','requirements':'existing learn.rank and quest.advancement_rank; item rank gate explicitly requires Codex support','mechanics':'known flat damage/heal/MP, status and cleanse operations, no new boss engine','balance':'new authored extension stats, not verified historical values'}}])
    shard(p,records);ids.save();write(p/'skills-summary.json',{'scope':'DATA_ONLY','counts':dict(collections.Counter(r['kind'] for r in records)),
       'existing_skill_visual_patches':visual_patches,'new_skills':12,'new_items':12,'new_rank1_quests':4,'class_skill_list_patches':4,'mentor_patches':4,
       'effect_models_referenced':sorted({r['data']['animation']['effect_asset_id'] for r in records if r['kind']=='skill'}),
       'teacher_paths':mentors,'new_skill_ids':dict(newskills),'private_new_files_required':False,'source_effect_representatives_reviewed':119,
       'game_import':'NOT_RUN','gameplay':'NOT_RUN','rank_gate_execution':'NOT_RUN'})
    print(batch,len(records),dict(collections.Counter(r['kind'] for r in records)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);build(p.parse_args().batch)
