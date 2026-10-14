#!/usr/bin/env python3
"""Guarded rank2/3 training and an explicit repair of inherited trainer menus."""
import argparse, collections, copy, shutil, sys
sys.dont_write_bytecode = True
from common import WORK, IDs, load, lines, write, record, ref, shard, ratio, round_int
from build_expansion_links import patch_record, data_refs

# All operations already occur in fixed CONTENT001/004. These are authored
# extensions, with distinct range/area/resource/status purposes, not source spells.
SPECS = {
    (2,'warrior'): [('진영 가르기','damage',14,'enemy',1,1,95000,0,18000,0,'damage'),
                    ('수문장의 호흡','remove_status',107,'self',0,0,0,1000,0,0,'poison')],
    (3,'warrior'): [('화산 결단','damage',5,'enemy',1,0,240000,0,45000,0,'damage'),
                    ('산맥 버팀','damage_reduction',119,'self',0,0,35,3000,0,12000,'damage')],
    (2,'rogue'): [('먼길 비수','damage',66,'enemy',5,0,80000,6000,6000,0,'damage'),
                  ('흔들린 시야','blind',102,'enemy',4,0,1,4500,0,8000,'damage')],
    (3,'rogue'): [('그늘 파동','damage',92,'enemy',2,2,150000,12000,12000,0,'damage'),
                  ('칼끝 억제','weaken',98,'enemy',4,0,25,6000,0,15000,'damage')],
    (2,'mage'): [('광맥 화염진','damage',111,'enemy',6,3,110000,18000,0,0,'fire'),
                 ('냉기의 사슬','paralyze',23,'enemy',5,0,1,8500,0,4000,'ice')],
    (3,'mage'): [('설원 광역냉광','damage',112,'enemy',6,4,200000,42000,0,0,'ice'),
                 ('마력 되채우기','restore_mp',74,'self',0,0,30000,0,50000,0,'damage')],
    (2,'poet'): [('보급길 큰기원','heal_hp',109,'self_or_ally',6,0,110000,14000,0,0,'damage'),
                 ('오염 걷어내기','remove_status',120,'self_or_ally',6,0,0,1600,0,0,'poison')],
    (3,'poet'): [('서리길 재생','revive',122,'self_or_ally',6,0,0,20000,0,0,'damage'),
                 ('수로 맑은방패','armor',51,'self',0,0,28,8000,0,45000,'damage')]
}

def build(batch):
    idx=load(WORK/'HANDOFF_INDEX.json');defs={};assets={}
    for entry in idx['packages']:
        for p in sorted((WORK/'packages'/entry['batch_id']).glob('content-*.jsonl')):
            for r in lines(p):(assets if r['kind']=='asset' else defs)[r.get('target_id',r['id'])]=r
    ids=IDs();records=[];changes={};menu_repairs=[];skills_by_job=collections.defaultdict(list)
    title={'warrior':'전사','rogue':'도적','mage':'주술사','poet':'도사'}
    regions=load(WORK/'packages/WK-CONTENT-003/region-summary.json')['regions']
    reg={t:max((r for r in regions if r['theme']==t),key=lambda r:r['levels'][0]) for t in ('forest','cave','dry','water','snow','fire')}
    def add(i,k,d):
        r=record(i,k,d,['rule.exp2.advanced-training']);r['references']=data_refs(d,assets);records.append(r)
    def edit(target,path,value):
        if target not in changes:changes[target]=[defs[target],copy.deepcopy(defs[target]['data']),set()]
        old,d,fields=changes[target];d[path]=value;fields.add(path)
    def boss(theme):
        candidates=[p for mid in reg[theme]['maps'] for p in defs[mid]['data']['spawns'] if defs[p['monster_id']]['data']['spawn_rules']['boss']]
        if not candidates:raise ValueError('No existing boss for '+theme)
        p=candidates[-1];mid=next(mid for mid in reversed(reg[theme]['maps']) if p in defs[mid]['data']['spawns'])
        return {'type':'kill','monster_id':p['monster_id'],'map_id':mid,'count':1}
    def talk(theme,role='scout'):
        return {'type':'talk','npc_id':reg[theme][role+'_id'],'count':1}
    def collect(theme,n):return {'type':'collect','item_id':'wk.item.exp2.material.'+theme,'count':n}
    potion='wk.item.exp2.potion.5.heal_hp'
    plans={
      (2,'warrior'):('보급소의 방위', [talk('cave','guide'),boss('cave'),collect('cave',8)],
                    '폐광의 길잡이에게 보급소 사정을 묻고 마지막 길목의 우두머리를 물리쳐 주세요. 폐광 광석 여덟 개도 가져오세요.'),
      (3,'warrior'):('두 길목의 수호', [talk('water'),talk('fire'),boss('fire'),collect('fire',10)],
                    '수로와 화산의 파수꾼에게 두 귀환로의 사정을 확인한 뒤 화산 우두머리를 토벌하세요. 화산 불씨돌 열 개를 제출하면 방위 수련을 마칩니다.'),
      (2,'rogue'):('돌아오는 첩보길', [talk('dry'),talk('forest'),collect('forest',8)],
                    '사구와 숲의 파수꾼에게 길목을 확인하고 귀환 경로를 익히세요. 숲결 나뭇조각 여덟 개가 수련 기록의 제출물입니다.'),
      (3,'rogue'):('산령의 발자취', [talk('forest','guide'),boss('forest'),talk('dry','guide'),collect('dry',10)],
                    '숲 길잡이를 만나 산령의 길목을 찾고 토벌한 뒤 사구 길잡이에게 소식을 전하세요. 사구 유리돌 열 개도 제출해 주세요.'),
      (2,'mage'):('불과 얼음의 기록', [collect('fire',5),collect('snow',5),talk('fire','smith'),talk('snow','smith')],
                    '화산 불씨돌과 설원 얼음결정을 각각 다섯 개 모으세요. 양쪽 대장장이에게 광물의 성질을 묻고 두 자료를 함께 제출하면 제어 수련을 마칩니다.'),
      (3,'mage'):('서리벽의 원류', [talk('snow'),boss('snow'),collect('snow',10),talk('cave','guide')],
                    '설원 파수꾼에게 원류의 길을 확인하고 설벽의 우두머리를 토벌하세요. 얼음결정 열 개를 모은 뒤 폐광 길잡이에게 조사 경로를 확인해 주세요.'),
      (2,'poet'):('여행자 보급 준비', [talk('water','guide'),{'type':'collect','item_id':potion,'count':4},talk('fire','supplier')],
                    '수로 길잡이에게 여행자의 사정을 듣고 화산 회복약 네 개를 준비하세요. 화산 보급상에게 보급로를 확인한 뒤 돌아오세요. 약은 완료할 때 한 번 소비합니다.'),
      (3,'poet'):('설원과 수로의 정화', [talk('snow','guide'),collect('snow',6),talk('water','guide'),collect('water',6)],
                    '설원과 수로 길잡이에게 현지 사정을 물으세요. 얼음결정과 수로 진주편을 각각 여섯 개 가져오면 정화 수련용 문서와 장비를 드립니다.')}
    mentors={job:next(r['data']['learn']['teacher_npc_ids'][0] for r in defs.values() if r['kind']=='skill' and r['data']['class_ids']==['wk.class.'+job]) for job in title}
    gear_models={
      (2,'warrior'):71,(3,'warrior'):77,(2,'rogue'):82,(3,'rogue'):88,
      (2,'mage'):72,(3,'mage'):75,(2,'poet'):78,(3,'poet'):87}
    for rank in (2,3):
        for job in title:
            cid='wk.class.'+job;mentor=mentors[job];qid=ids.get('quest',f'exp2.rank{rank}.training.{job}')
            manual=ids.get('item',f'exp2.rank{rank}.manual.{job}');gear=[]
            base=copy.deepcopy(defs[f'wk.item.exp2.rank1.manual.{job}']['data'])
            base.update(name=f'{title[job]} {rank}차 심화수련 문서',stack_limit=2,historical_status='AUTHORED_RANK23_TRAINING_TOKEN')
            base['requirements']['advancement_rank']=rank;base['acquisition']=[{'kind':'quest_reward','quest_id':qid,'source_mode':'INFERRED'}];add(manual,'item',base)
            for slot in ('weapon','body'):
                iid=ids.get('item',f'exp2.rank{rank}.gear.{job}.{slot}');gear.append(iid)
                d=copy.deepcopy(defs[f'wk.item.exp2.rank1.gear.{job}.{slot}']['data'])
                d['name']=f'{title[job]} {rank}차 '+('길목수호' if job=='warrior' else '첩보수련' if job=='rogue' else '원류수련' if job=='mage' else '보급정화')+(' 무기' if slot=='weapon' else ' 도복')
                d['requirements']['advancement_rank']=rank;scale={2:2,3:4}[rank]
                d['stats']={k:round_int(v*scale) if k!='durability' else v for k,v in d['stats'].items()}
                if slot=='weapon':d['visual']['equipment_asset_id']=f'wk.asset.kr491.sword.{gear_models[rank,job]:03d}'
                d['acquisition']=[{'kind':'quest_reward','quest_id':qid,'source_mode':'INFERRED'}];d['historical_status']='AUTHORED_RANK23_REWARD_NOT_ORIGINAL_EQUIPMENT';add(iid,'item',d)
            for n,(name,op,model,target,rng,aoe,amount,mp,hp,duration,element) in enumerate(SPECS[rank,job],1):
                sid=ids.get('skill',f'exp2.rank{rank}.{job}.{n}');skills_by_job[job].append(sid)
                effect={'op':op,'amount':amount,'scale':'flat','element':element} if op=='damage' else {'op':op,'amount':amount,'target':'self'} if op=='restore_mp' else {'op':'remove_status','status':'poison'} if op=='remove_status' else {'op':'revive','hp_fraction':ratio(.5),'mp_fraction':ratio(.25)} if op=='revive' else {'op':op,'amount':amount,'scale':'flat'} if op=='heal_hp' else {'op':'apply_status','status':op,'magnitude':amount,'stack':'refresh_duration'}
                d={'name':name,'class_ids':[cid],'learn':{'level':99,'money':0,'experience_cost':0,'consume':[{'item_id':manual,'quantity':1}],'teacher_npc_ids':[mentor],'rank':rank,'once':True},
                   'target':target,'range_tiles':rng,'aoe_radius_tiles':aoe,'effects':[effect],'cost':{'mp':mp,'hp':hp,'hp_fraction':ratio(0),'prevent_suicide':True},
                   'cooldown_ms':8000 if op=='damage' else 45000 if op=='revive' else 15000,'duration_ms':duration,'success_ratio':ratio(1),
                   'animation':{'effect_asset_id':f'wk.asset.kr491.effect.{model:03d}','body_motion':'cast','direction_order':['N','W','S','E'],'impact_delay_ms':160,'front_back_order':'SOURCE_TABLE','sound_asset_id':'wk.asset.kr491.sound.003'},
                   'historical_status':'AUTHORED_RANK23_OFFLINE_EXTENSION'}
                r=record(sid,'skill',d,['rule.exp2.advanced-training']);r['references']=data_refs(d,assets)
                md=assets[d['animation']['effect_asset_id']]['data']['metadata'];r['references'].append(ref('effect_source_frames',md['sheet_id'],{'frames':sorted({x['frame'] for x in md['front']+md['back']}),'scope':'DISTINCT_SOURCE_INDICES'}));records.append(r)
            name,objectives,text=plans[rank,job];consume=[{'item_id':o['item_id'],'quantity':o['count']} for o in objectives if o['type']=='collect']
            d={'name':f'{title[job]} {rank}차 현장수련 — '+name,'start_npc_id':mentor,'complete_npc_id':mentor,'requirements':{'level':99,'advancement_rank':rank,'class_ids':[cid]},
               'prerequisites':[f'wk.quest.advancement.{job}.{rank}',f'wk.quest.exp2.rank{rank-1}.training.{job}'],
               'objectives':objectives+[{'type':'talk','npc_id':mentor,'count':1,'after_other_objectives':True}], 'consume':consume,
               'rewards':[{'type':'item','item_id':manual,'quantity':2}]+[{'type':'item','item_id':i,'quantity':1} for i in gear],
               'repeat':{'mode':'once','cooldown_ms':0,'occurrence_counter':False},'completion_key':qid,'extension':True}
            add(qid,'quest',d)
            if mentor not in changes:changes[mentor]=[defs[mentor],copy.deepcopy(defs[mentor]['data']),set()]
            old,nd,fields=changes[mentor];services=nd['services'];qi=next(i for i,s in enumerate(services) if s['type']=='quests');services[qi]['quest_ids'].append(qid);fields.add('services')
            nd['dialogue'].append({'id':f'rank{rank}_training','text':text+' 문서는 기술 한 개를 배울 때 한 권씩 소비하며 보상은 한 번만 지급합니다.','choices':[{'label':f'{rank}차 수련 의뢰 보기','service_index':qi}]});fields.add('dialogue')
    for job,mentor in mentors.items():
        cid='wk.class.'+job;newlist=defs[cid]['data']['skill_ids']+skills_by_job[job];edit(cid,'skill_ids',newlist)
        old,d,fields=changes[mentor]
        svc=next(s for s in d['services'] if s['type']=='learn_skills' and s['class_id']==cid)
        additions=[s for s in newlist if s not in svc['skill_ids']];svc['skill_ids']+=additions;fields.add('services')
        menu_repairs.extend(s for s in additions if s.startswith('wk.skill.exp2.rank1.'))
    for target,(old,d,fields) in changes.items():
        r=patch_record(ids,old,d,sorted(fields),'rule.exp2.advanced-training','advanced');r['references']=data_refs(d,assets);records.append(r)
    p=WORK/'packages'/batch
    if p.exists():raise ValueError('Use a new immutable batch')
    (p/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',p/'schema/content-v1.json')
    write(p/'provenance.json',[{'id':'rule.exp2.advanced-training','source_mode':'INFERRED','basis':['fixed rank1 training, four source guild trainers, existing twelve advancement definitions','reviewed source weapon/effect representatives and existing regions'],
       'rules':{'rank_conditions':'original advancement thresholds untouched; quest and learning require actual completed rank','equipment':'rank1 template x2/x4 for rank2/rank3, same bound/cost rules; reviewed compatible weapon models','skills':'existing flat damage/heal/MP, revive/cleanse/status operations; authored range/area/resource/cooldown purposes','quests':'eight distinct cross-region reconnaissance/defense/material/supply tasks, no new artificial map','learn_menu_repair':'add inherited rank1 skill IDs to actual learn_skills service; preserve all prior menu entries','history':'none of the new names, dialogue, or numerical balance is claimed as original1998'}}])
    shard(p,records);ids.save()
    write(p/'advanced-summary.json',{'scope':'DATA_ONLY','counts':dict(collections.Counter(r['kind'] for r in records)),'new_skills':16,'new_items':24,'new_quests':8,'existing_npc_proposals':4,'existing_class_proposals':4,'rank1_skill_menu_repairs':menu_repairs,'private_new_files_required':False,'new_maps':0,'game_import':'NOT_RUN','gameplay':'NOT_RUN','required_runtime_operations_reused':True})
    print(batch,dict(collections.Counter(r['kind'] for r in records)),'rank1 menu repairs',len(menu_repairs))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--batch',required=True);build(a.parse_args().batch)
