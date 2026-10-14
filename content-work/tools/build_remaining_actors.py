#!/usr/bin/env python3
"""Connect remaining reviewed source actors to placed NPCs and hunting ecology."""
import argparse,collections,copy,shutil,sys,zipfile
sys.dont_write_bytecode=True
from common import WORK,IDs,load,lines,write,record,shard,ratio,round_int
from build_expansion_links import patch_record,data_refs
from preview_expansion_maps import component

NPC_MODELS=[0,1,3,39,40,41,42,43,44,45,46,47,48,49,52,55,56,57,61,70,71,72,74,75,76,77,78,87,109,116,133,134,137,138,139,140,178,208,210,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,236,237,238,239,240,241,244,245,246,247,259,260,261,262,263,264,265,266,267,274,276,288,289,290,296,297,298,299,301,303,305,306,312,313]
OBJECTS={58:('갈림길 작은 제단','forest'),106:('여행자 보급궤','water'),154:('폐광 기록묘','cave'),307:('산길 이정석','cave'),317:('푸른 길목거울','snow'),318:('붉은 길목거울','fire'),319:('옛길 수호인형','forest'),320:('방위 기록깃발','dry')}
# Placeholders, stand-alone shadow, partial pose consumers, and the remaining
# stages of one rock are reserved explicitly; they are not invented enemies.
RESERVE={35:'SOURCE_WHITE_POINT',50:'SOURCE_DARK_POINT',92:'GROUND_SHADOW_COMPONENT',96:'TINY_DARK_COMPONENT',248:'SMALL_FLOATING_HUMAN_POSE_EVENT_UNRESOLVED',249:'SMALL_FLOATING_HUMAN_POSE_EVENT_UNRESOLVED',255:'PARTIAL_GREY_APPARITION_EVENT_UNRESOLVED',257:'PARTIAL_GREY_APPARITION_EVENT_UNRESOLVED',258:'PARTIAL_GREY_APPARITION_EVENT_UNRESOLVED',278:'GROUND_SHADOW_COMPONENT',308:'ROCK_DAMAGE_STAGE_CONSUMER_REQUIRED',309:'ROCK_DAMAGE_STAGE_CONSUMER_REQUIRED',310:'ROCK_DAMAGE_STAGE_CONSUMER_REQUIRED',311:'ROCK_DAMAGE_STAGE_CONSUMER_REQUIRED',315:'FLOATING_POSE_EVENT_UNRESOLVED',316:'FLOATING_POSE_EVENT_UNRESOLVED'}
CREATURES=[
 (17,'그늘 늑혼','forest',17,'hunter'),(18,'그늘 장정혼','cave',29,'guard'),(20,'이끼굴 들쥐','forest',22,'poison'),
 (21,'그늘 토끼령','forest',25,'forager'),(22,'풀숲 소령','forest',31,'ranged'),(23,'등불 소인','forest',39,'guard'),(24,'그늘 버섯괴','forest',43,'poison'),
 (27,'배회하는 해골령','cave',52,'ranged'),(31,'녹슨칼 해골병','cave',37,'guard'),(32,'푸른굴 지네','cave',26,'poison'),(33,'굴그늘 뱀령','cave',42,'hunter'),
 (59,'불뿔 의식귀','fire',95,'ranged'),(62,'폐광 검은장막','cave',97,'boss'),(83,'뿔가면 주박사','dry',74,'ranged'),
 (88,'뿔그늘 눈짐승','snow',78,'hunter'),(89,'가는그늘 소귀','forest',68,'poison'),(91,'두개굴 들쥐','cave',47,'poison'),(93,'그늘숲 지킴이','forest',61,'guard'),(94,'굴끝 장막귀','cave',88,'ranged'),
 (99,'큰뿔 숲장수','forest',51,'guard'),(100,'회색숲 잠행객','forest',62,'hunter'),(101,'사구 붉은추적자','dry',73,'ranged'),(102,'설원 푸른봉인객','snow',86,'poison'),
 (111,'가시갈퀴 목령','forest',54,'poison'),(113,'폐광 골갑장수','cave',63,'guard'),(119,'독골 해골병','cave',75,'poison'),(120,'청골 작은굴령','cave',41,'hunter'),(121,'뼈가면 들쥐','forest',32,'guard'),(122,'큰굴 뼈들쥐','cave',66,'guard'),
 (127,'석벽 사당원혼','cave',84,'ranged'),(128,'수로 돼지장수','water',56,'guard'),(129,'사구 철갑견장','dry',67,'hunter'),(130,'숲길 범장수','forest',72,'hunter'),(131,'갈대 토끼술객','water',51,'ranged'),(135,'광맥 멧장수','cave',71,'guard'),
 (155,'폐광 이끼거인','cave',77,'guard'),(160,'사구 큰귀장수','dry',82,'guard'),(161,'석문 뿔장수','cave',91,'guard'),(164,'검은불 깃령','fire',98,'ranged'),(169,'철엽 숲문장','forest',83,'guard'),(171,'돌외투 망령','cave',86,'ranged'),
 (172,'말라붙은 숲가지','forest',72,'poison'),(175,'굴러드는 화강괴','cave',65,'guard'),(176,'끝굴 낫원혼','cave',99,'boss'),(177,'그늘굴 난장이','cave',59,'ranged'),(179,'갈대투구 주박사','water',88,'ranged'),(181,'뿔난 이끼둥이','forest',44,'forager'),
 (182,'푸른굴 머리원혼','cave',63,'ranged'),(183,'광맥 긴지네','cave',68,'poison'),(188,'설문 황금가면','snow',96,'ranged'),(191,'붉은늪 둥근장수','water',73,'guard'),(192,'사구 쌍도끼 문장','dry',93,'guard'),(193,'눈길 마른목령','snow',82,'poison'),
 (196,'흙가면 사구괴','dry',86,'guard'),(197,'갈대 배회령','water',81,'hunter'),(199,'서리굴 작은령','snow',89,'poison'),(251,'흙결 사람나무','forest',89,'guard'),(252,'수로 나선세머리','water',98,'boss'),
 (110,'흰면 장막녀','cave',87,'ranged'),(268,'나무그늘 숲원숭이','forest',36,'forager'),(269,'이끼굴 긴팔귀','cave',58,'hunter'),(279,'갈대그늘 부엉귀','water',69,'guard'),
 (275,'뿔난 숲삵','forest',57,'hunter'),(280,'푸른눈 주박녀','snow',91,'ranged'),(281,'흰장막 눈귀','snow',97,'poison'),(282,'황금주박 소령','dry',92,'ranged'),(283,'사구 날개가면','dry',99,'boss'),(284,'눈길 흉갑객','snow',92,'guard'),(285,'풀끝 부유령','forest',94,'ranged'),(314,'갈대허수 원혼','water',96,'poison')]

def build(batch,old_bundle,new_bundle):
    idx=load(WORK/'HANDOFF_INDEX.json');assets={};defs={}
    entries=[e for e in idx['packages'] if e['batch_id'] not in ('WK-ASSETS-002','WK-ASSETS-003','WK-CONTENT-006','WK-CONTENT-008')]
    for entry in entries:
        for p in sorted((WORK/'packages'/entry['batch_id']).glob('content-*.jsonl')):
            for r in lines(p):(assets if r['kind']=='asset' else defs)[r.get('target_id',r['id'])]=r
    remaining={int(r['asset_id'].rsplit('.',1)[1]) for r in lines(WORK/'catalog/expansion-2/asset-after.jsonl') if r['family']=='monster' and r['state']=='DECODED_UNUSED'}
    used={*NPC_MODELS,*OBJECTS,*[s[0] for s in CREATURES]};assert len(used)==len(NPC_MODELS)+len(OBJECTS)+len(CREATURES),'model assigned twice'
    assert not used-remaining,used-remaining
    unassigned=remaining-used-RESERVE.keys();assert not unassigned,unassigned
    assert not used & RESERVE.keys(),'reserved model also assigned'
    assert not RESERVE.keys()-remaining,'reserved model no longer unused'
    ids=IDs();rs=[];newdefs={};updates={};areas={};layouts={};occupied=collections.defaultdict(set)
    maps={i:r['data'] for i,r in defs.items() if r['kind']=='map'};regions=load(WORK/'packages/WK-CONTENT-003/region-summary.json')['regions']
    bundles={'wk.bundle.regions.001':zipfile.ZipFile(old_bundle),'wk.bundle.regions.002':zipfile.ZipFile(new_bundle)}
    def add(kind,key,data):
        i=ids.get(kind,'exp3.'+key);r=record(i,kind,data,['rule.exp3.actor-role']);rs.append(r);newdefs[i]=r;return i
    def change(mid):
        if mid not in updates:updates[mid]=[defs[mid],copy.deepcopy(maps[mid]),set()]
        return updates[mid][1]
    def pick(mid,far=False):
        if mid not in areas:
            a=maps[mid]['layout_acquisition'];layout=__import__('json').loads(bundles[a['bundle_id']].read(a['member']));layouts[mid]=layout
            areas[mid]=component([{'collision':c} for c in layout['collision_masks']],maps[mid]['width'],maps[mid]['height'])
            occupied[mid].add(tuple(maps[mid]['entry']))
            for key in ('portals','npc_placements','spawns'):
                for v in maps[mid][key]:occupied[mid].add((v['x'],v['y']));occupied[mid].update(tuple(q) for q in v.get('spawn_cells',[]))
        free=areas[mid]-occupied[mid];assert free,'no safe cell '+mid
        entry=maps[mid]['entry'];xy=min(free,key=lambda q:((-1 if far else 1)*(abs(q[0]-entry[0])+abs(q[1]-entry[1])),q[1],q[0]));occupied[mid].add(xy);return xy
    def region(theme,level):return min((r for r in regions if r['theme']==theme),key=lambda r:abs(sum(r['levels'])/2-level))
    source_monsters=[r['data'] for r in defs.values() if r['kind']=='monster'];new_monsters=[];item_drops=collections.defaultdict(list)
    for model,name,theme,level,role in CREATURES:
        reg=region(theme,level);mid=reg['maps'][(model*7)%len(reg['maps'])];base=min(source_monsters,key=lambda d:(abs(d['level']-level),d['name']));d=copy.deepcopy(base)
        d.update(name=name,level=level,hp=max(30,round_int(base['hp']*(2 if role=='boss' else 1.25 if role=='guard' else 1))),experience=max(5,round_int(base['experience']*(1.5 if role=='boss' else 1))),gold=level*(12 if role=='boss' else 3),family='authored_'+theme,historical_status='AUTHORED_SOURCE_MODEL_CREATURE_NOT_ORIGINAL_NAME')
        d['attack'].update(kind='ranged' if role=='ranged' else 'melee',range_tiles=5 if role=='ranged' else 1)
        d['behavior'].update(aggression='passive_until_hit' if role=='forager' else 'hostile',aggro_radius_tiles=0 if role=='forager' else 6,leash_radius_tiles=12,special=[])
        if role=='hunter':d['behavior']['move_interval_ms']=max(300,round_int(d['behavior']['move_interval_ms']*.8))
        if role=='poison':d['behavior']['special']=[{'trigger':'attack_hit','op':'status','status':'poison','duration_ms':10000,'period_ms':2000,'damage':max(1,level//3),'probability':ratio(.15)}]
        d['visual']={'asset_id':f'wk.asset.kr491.monster.{model:03d}','motion':['walk','attack'],'semantic_match':'REVIEWED_SILHOUETTE_INFERRED_ROLE_NOT_SOURCE_IDENTITY','palette_variant':0}
        d['spawn_rules']={'respawn_ms':180000 if role=='boss' else 30000,'max_live_per_point':1,'boss':role=='boss','respawn_when':'cooldown_elapsed','persist_death_cooldown':True,'region_ids':[mid]}
        monster=ids.get('monster',f'exp3.source-model.{model}');group=ids.get('drop_group',f'exp3.source-model.{model}');d['drop_group_id']=group
        add('monster',f'source-model.{model}',d)
        rolls=[{'item_id':'wk.item.exp2.material.'+theme,'quantity':{'min':1,'max':2 if role=='boss' else 1},'probability':ratio(1),'basis':'guaranteed shared regional material, existing crafting/quest use'}]
        gear=load(WORK/'packages/WK-CONTENT-007/gear-summary.json')['definitions'];pool=[x for x in gear if x['level']<=level and x['region'].startswith(theme+'.')]
        if pool:
            item=min(pool,key=lambda x:abs(x['level']-level))['item_id'];rolls.append({'item_id':item,'quantity':{'min':1,'max':1},'probability':ratio(.05 if role=='boss' else .015),'basis':'authored rare alternate source for already craftable weapon'});item_drops[item].append(monster)
        add('drop_group',f'source-model.{model}',{'name':name+' 드롭','mode':'independent','rolls':rolls})
        for n in range(1 if role=='boss' else 2):
            xy=pick(mid,True);cells=[list(q) for q in sorted(areas[mid]-occupied[mid]) if abs(q[0]-xy[0])+abs(q[1]-xy[1])<=2][:8];cells=[list(xy),*cells];occupied[mid].update(tuple(q) for q in cells)
            md=change(mid);md['spawns'].append({'placement_id':ids.get('spawn',f'exp3.{model}.{n}'),'monster_id':monster,'x':xy[0],'y':xy[1],'radius_tiles':2,'spawn_cells':cells,'max_live':1 if role=='boss' else 2,'respawn_ms':d['spawn_rules']['respawn_ms'],'source_mode':'INFERRED'});updates[mid][2].add('spawns')
        new_monsters.append({'source_model':model,'id':monster,'name':name,'theme':theme,'role':role,'level':level,'map_id':mid})
    firstnames=['하람','윤수','모연','길재','은솔','담희','도림','태주','서린','지안','연화','해원','가윤','소율','민하','수겸','이솔','아람','유찬','다인','보름','초희','지후','나래','다솔','세진','윤하','주원','세림','은재','가람','하늬']
    surnames=['서','윤','남','곽'];roles=['길목 기록관','약초 기록가','방위 교관','여행길 안내인','우물 관리인','마을 서기','수련 조교','의례 사제','포구 전령','길목 순찰원','산길 수집가','행상길 안내인']
    roletexts=['여기서 보고 들은 길목 소식을 장부에 남깁니다. 귀환길을 먼저 익히고 깊은 곳으로 들어가세요.','회복약은 현지 보급상에게서 구할 수 있습니다. 상처가 깊어지기 전에 쉬어 가세요.','혼자 많은 적을 상대하려 하지 마세요. 길목에서 한 무리씩 상대하고 귀환로를 남겨 두세요.','길이 갈라져도 지나온 출입구로 돌아갈 수 있습니다. 먼 곳에 가기 전에 보급소 위치부터 기억하세요.','우물과 휴식터 주변은 여행자가 쉬는 곳입니다. 싸움을 끌고 들어오지 않도록 조심하세요.','이 고장의 재료는 현지 대장장이가 장비로 바꿔 줍니다. 제작할 때 재료와 돈이 함께 듭니다.','기술은 직업 길드에서 배웁니다. 수련 문서는 해당 수련 의뢰를 마친 뒤 얻을 수 있습니다.','쓰러진 여행자의 소식은 성황당과 길드에 전합니다. 살아 돌아오는 것이 가장 먼저입니다.','멀리 떨어진 길잡이에게 소식을 전하는 일도 수련입니다. 토벌만으로 이 고장의 사정을 모두 알 수는 없습니다.','새로운 길목에 들어가기 전에 필요한 레벨과 장비를 살피세요. 강한 적의 길목은 돌아가도 괜찮습니다.','한 번 모은 재료를 무심코 버리지 마세요. 현지 제작과 의뢰의 제출물로 쓰일 수 있습니다.','여행에 앞서 약과 장비를 준비하세요. 물품을 살 때 가격을 보고, 판매할 때 받을 돈도 확인하세요.']
    npcs=[]
    for n,model in enumerate(NPC_MODELS):
        reg=regions[n%len(regions)];mid=reg['camp'];xy=pick(mid);role=roles[n%len(roles)];name=surnames[n//32]+firstnames[n%32]+' '+role
        d={'name':name,'visual':{'asset_id':f'wk.asset.kr491.monster.{model:03d}','motion':'walk','frame_ms':assets[f'wk.asset.kr491.monster.{model:03d}']['data']['metadata']['animations']['walk']['frame_ms'],'identity':'REVIEWED_FULL_FIGURE_AUTHORED_RESIDENT'},
           'dialogue':[{'id':'greeting','text':reg['name']+'에서 '+role+' 일을 맡은 '+name.split()[0]+'입니다. '+roletexts[n%len(roles)],'choices':[{'label':'길목 이야기를 마칩니다','close':True}]}],
           'services':[],'placements':[{'map_id':mid,'x':xy[0],'y':xy[1]}],'interaction_range_tiles':2,'role':'ambient','dialogue_source':'AUTHORED_KOREAN_NOT_HISTORICAL_QUOTE'}
        if n%12==1:
            d['services']=[{'type':'rest','gold_cost':max(5,reg['levels'][0]),'restore_hp':'max','restore_mp':'max'}];d['dialogue'][0]['choices'].insert(0,{'label':'잠시 쉬어 가기','service_index':0})
        nid=add('npc',f'source-model.{model}',d);md=change(mid);md['npc_placements'].append({'placement_id':ids.get('placement',f'exp3.actor.{model}'),'npc_id':nid,'x':xy[0],'y':xy[1],'blocking':False});updates[mid][2].add('npc_placements');npcs.append({'id':nid,'model':model,'region':reg,'name':name})
    objects={}
    for model,(name,theme) in OBJECTS.items():
        reg=region(theme,75);mid=reg['maps'][model%len(reg['maps'])];xy=pick(mid)
        text={'forest':'닳은 표면에는 숲의 길잡이와 귀환로를 기억하라는 글이 남아 있습니다.','cave':'돌에 새긴 글은 광맥을 찾을 때 보급소로 돌아가는 길부터 확인하라고 알려 줍니다.','water':'보급품 옆의 장부에는 회복약을 챙기고 수로 길잡이에게 소식을 전하라는 기록이 있습니다.','snow':'눈길에서 보급소와 길잡이 위치를 잊지 않도록 남긴 오래된 표식입니다.','fire':'불꽃 길목의 오래된 표식입니다. 마지막 길목에 들어가기 전에 보급소를 확인하라는 기록이 있습니다.','dry':'사구 파수꾼이 여행자의 귀환 소식을 기록한 깃발입니다.'}[theme]
        d={'name':name,'visual':{'asset_id':f'wk.asset.kr491.monster.{model:03d}','motion':'walk','frame_ms':100,'identity':'SOURCE_OBJECT_FIGURE_AUTHORED_INTERACTABLE_NOT_A_HUMAN'},'dialogue':[{'id':'read','text':text,'choices':[{'label':'기록을 덮습니다','close':True}]}],'services':[],'placements':[{'map_id':mid,'x':xy[0],'y':xy[1]}],'interaction_range_tiles':2,'role':'world_object','dialogue_source':'AUTHORED_KOREAN_NOT_HISTORICAL_QUOTE'}
        nid=add('npc',f'object-model.{model}',d);md=change(mid);md['npc_placements'].append({'placement_id':ids.get('placement',f'exp3.object.{model}'),'npc_id':nid,'x':xy[0],'y':xy[1],'blocking':False});updates[mid][2].add('npc_placements');objects[model]=nid
    def resident(theme,n=0):return [x for x in npcs if x['region']['theme']==theme][n%len([x for x in npcs if x['region']['theme']==theme])]
    def talk(npc):return {'type':'talk','npc_id':npc,'count':1}
    def material(theme,count):return {'type':'collect','item_id':'wk.item.exp2.material.'+theme,'count':count}
    def hunt(model):
        m=next(x for x in new_monsters if x['source_model']==model);return {'type':'kill','monster_id':m['id'],'map_id':m['map_id'],'count':1}
    storyplans=[
       ('forest','숲길 사람들의 안부',[talk(resident('forest',1)['id']),material('forest',2)],'숲길 이웃에게 안부를 묻고 길목 표식을 고칠 나뭇조각 두 개를 모아 주세요.'),
       ('dry','교역 장부의 빈칸',[material('forest',4),material('cave',2),talk(resident('water',1)['id'])],'숲과 광맥의 교역품을 대조하고 수로의 전령에게 운송 소식을 확인해 주세요.'),
       ('water','우물 주변의 소문',[hunt(179),talk(resident('water',2)['id']),material('water',3)],'우물 주변을 어지럽히는 주박사를 물리치고 이웃에게 소식을 물은 뒤 수로 재료 세 개를 가져오세요.'),
       ('forest','야간 순찰의 귀환',[talk(resident('forest',3)['id']),hunt(100)],'순찰원에게 야간 길목을 확인하고 회색숲 잠행객을 토벌한 뒤 살아 돌아와 주세요.'),
       ('snow','눈길 여행자의 준비',[talk(resident('snow',1)['id']),material('fire',2),material('snow',4)],'눈길 안내인에게 보급 사정을 물으세요. 불씨돌 두 개와 얼음결정 네 개로 여행자 준비를 도와 주세요.'),
       ('cave','묘역에 남은 두 기록',[talk(objects[154]),talk(objects[307])],'폐광 기록묘와 산길 이정석의 기록을 함께 읽고 묘역으로 돌아오는 길을 확인해 주세요.'),
       ('cave','끝굴의 소식',[talk(resident('cave',1)['id']),hunt(62)],'탐사 기록가에게 마지막 길목을 확인하고 검은장막을 물리친 뒤 소식을 전해 주세요.'),
       ('cave','무너진 길목의 정리',[hunt(175),material('cave',3),talk(resident('cave',2)['id'])],'굴러드는 화강괴를 물리치고 광석 세 개를 모아 길목 관리인에게 사정을 확인해 주세요.'),
       ('water','궤에 적힌 보급 약속',[talk(objects[106]),material('water',5)],'여행자 보급궤의 장부를 읽고 다음 여행자를 위한 수로 재료 다섯 개를 준비해 주세요.'),
       ('snow','거울과 길잡이의 말',[talk(objects[317]),talk(resident('snow',2)['id'])],'푸른 길목거울에 남은 기록을 읽고 눈길 길잡이에게 귀환 경로를 확인해 주세요.'),
       ('fire','불길 속의 오래된 표식',[talk(objects[318]),material('fire',3)],'붉은 길목거울에 남은 표식을 확인하고 불씨돌 세 개를 모아 화산 길잡이에게 보고해 주세요.'),
       ('dry','기록깃발의 인계',[talk(objects[320]),talk(resident('dry',1)['id'])],'방위 기록깃발을 읽고 사구 순찰원에게 다음 여행자의 귀환로를 전해 주세요.'),
       ('forest','수호인형과 이웃들',[talk(objects[319]),talk(resident('forest',2)['id']),material('forest',3)],'수호인형의 기록과 마을 이웃의 말을 함께 확인하고 나뭇조각 세 개로 표식을 보수할 준비를 해 주세요.'),
       ('water','세머리의 길목',[talk(resident('water',3)['id']),hunt(252)],'수로 순찰원에게 마지막 길목을 물은 뒤 나선세머리를 토벌하고 소식을 전해 주세요.'),
       ('dry','사구의 마지막 경계',[talk(resident('dry',2)['id']),hunt(283),material('dry',4)],'날개가면의 길목을 확인하고 토벌한 뒤 사구 유리돌 네 개를 제출해 경계 기록을 마쳐 주세요.'),
       ('cave','낫원혼의 봉인 기록',[talk(objects[154]),hunt(176),material('cave',6)],'묘역의 기록을 읽고 끝굴 낫원혼을 토벌하세요. 광석 여섯 개로 봉인 기록을 보존할 준비를 마칩니다.')]
    quest_ids=[]
    for n,(theme,title,objectives,text) in enumerate(storyplans):
        giver=resident(theme,n);nid=giver['id'];reg=giver['region']
        objective_levels=[reg['levels'][0]]
        for o in objectives:
            if o['type']=='kill':objective_levels.append(next(x['level'] for x in new_monsters if x['id']==o['monster_id']))
            if o['type']=='talk':objective_levels.extend(maps[p['map_id']]['recommended_level'][0] for p in newdefs[o['npc_id']]['data']['placements'])
        level=min(99,max(objective_levels))
        potion='wk.item.exp2.potion.'+str(min(5,max(0,(level-1)//20)))+'.heal_hp';qid=ids.get('quest',f'exp3.resident-story.{n+1}')
        q={'name':title,'start_npc_id':nid,'complete_npc_id':nid,'requirements':{'level':level,'class_ids':['wk.class.'+c for c in ['warrior','rogue','mage','poet']]},'prerequisites':[],'objectives':objectives+[talk(nid)|{'after_other_objectives':True}],
           'consume':[{'item_id':o['item_id'],'quantity':o['count']} for o in objectives if o['type']=='collect'],'rewards':[{'type':'gold','amount':max(20,level*30)},{'type':'experience','amount':max(100,level**3*5)},{'type':'item','item_id':potion,'quantity':2}],
           'repeat':{'mode':'once','cooldown_ms':0,'occurrence_counter':False},'completion_key':qid,'extension':True}
        add('quest',f'resident-story.{n+1}',q);quest_ids.append(qid);nd=newdefs[nid]['data'];nd['services'].append({'type':'quests','quest_ids':[qid]});nd['dialogue'].append({'id':f'story{n+1}','text':text+' 제출물은 의뢰 완료 때만 한 번 소비하며 보상은 한 번 지급합니다.','choices':[{'label':title+' 의뢰 확인','service_index':len(nd['services'])-1}]})
    for item,mobs in item_drops.items():
        old=defs[item];d=copy.deepcopy(old['data']);d['acquisition'] += [{'kind':'monster_drop','monster_id':m,'source_mode':'INFERRED'} for m in mobs]
        r=patch_record(ids,old,d,['acquisition'],'rule.exp3.actor-role','new-drop-source');rs.append(r)
    for mid,(old,d,fields) in updates.items():rs.append(patch_record(ids,old,d,sorted(fields),'rule.exp3.actor-role','actor-placements'))
    for r in rs:r['references']=data_refs(r['data'],assets)
    p=WORK/'packages'/batch
    if p.exists():raise ValueError('Use a new immutable package')
    (p/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',p/'schema/content-v1.json');shard(p,rs);ids.save()
    write(p/'provenance.json',[{'id':'rule.exp3.actor-role','source_mode':'INFERRED','basis':['existing four private source-actor representative sheets and exact TBL motion definitions','fixed remaining190 actor models','existing regional layout acquisition, material/crafting economy and nearest-level combat records'],
      'rules':{'identity':'authored names and NPC roles; Korean1998 identity is not claimed','palette_variants':'existing source variants have distinct region/level/behaviour/service roles; no new bitmap or recolor counted','npc':'full source figures as residents; artefacts explicitly world_object rather than people','combat':'existing chase/melee/ranged/poison only, nearest-level source-derived stats; bossesx2 HP andx1.5 XP','drops':'guaranteed shared material plus optional1.5%/5% already-craftable weapon; rare item never a necessary progression gate','quests':'sixteen distinct reconnaissance/cross-region/record-reading/supply/boss stories, no same-name count cloning','coordinates':'extend only exact map spawn/NPC fields; use largest static open component, no overlap with portals or known spawn cells; directional real movement NOT_RUN','reserves':'dots/shadows/partial poses/rock damage stages have specific unimplemented consumer reasons; not force-assigned'}}])
    write(p/'actors-summary.json',{'scope':'DATA_ONLY','counts':dict(collections.Counter(r['kind'] for r in rs)),'new_monsters':len(CREATURES),'new_bosses':sum(x[4]=='boss' for x in CREATURES),'new_resident_npcs':len(NPC_MODELS),'new_interactable_objects':len(OBJECTS),'new_quests':len(quest_ids),'new_graphics_files':0,'original_models_connected':len(used),'reserved_models':[{'model':m,'reason':reason} for m,reason in RESERVE.items()],'monsters':new_monsters,'resident_models':NPC_MODELS,'objects':objects,'guarded_map_fields':{k:sorted(v[2]) for k,v in updates.items()},'new_drop_item_paths':len(item_drops),'game_import':'NOT_RUN','gameplay':'NOT_RUN','directional_collision':'NOT_RUN'})
    for z in bundles.values():z.close()
    print(batch,dict(collections.Counter(r['kind'] for r in rs)),len(used),'source actor models connected')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--old-bundle',type=__import__('pathlib').Path,required=True);p.add_argument('--new-bundle',type=__import__('pathlib').Path,required=True);a=p.parse_args();build(a.batch,a.old_bundle,a.new_bundle)
