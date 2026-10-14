#!/usr/bin/env python3
"""Source-driven connected ecosystems, original layouts, authored solo content."""
import argparse,collections,copy,math,shutil,sys,zipfile
from pathlib import Path
sys.dont_write_bytecode=True
from common import ROOT,WORK,BASE,IDs,load,lines,write,file_sha,sha,record,ref,shard,ratio,round_int
from build_expansion_links import patch_record,data_refs
from preview_expansion_maps import setup,component
sys.path.insert(0,str(ROOT/'tools'))
from legacy_maps import map_cells

GROUND={
 'forest':{21,43,178,1820,2273,1408,1669,1670,1671,1643,1644,1652,3567,3544},
 'snow':{859,876,1429,1819,833,839,1128,1132,1945,1057},
 'water':{1569,1570,1571,2223,2269,2272,2127},
 'cave':{1434,1435,1436,1567,1568,1576,1577,1591,1593,1594,1596,1597,1605,2173,1463,2299,2129,2136,1374,1375,1376,1806,1710,1702,1769},
 'dry':{2333,2379,1223,1227,1274,1281,1291,1586,1589,905,986,987,42,64,405,406,2502,2503,8095,1101,1105,1528,1531,1536,1197,1198,427,428},
 'fire':{2400,2214}}
ROOMS={979,973,457,459,460,454,466,449,450,324,298,301,312,339,3342,651,621,626,631,632,633,634,573,582,591,600,607,791,782,4847,2666,890,834}
BANDS=[(1,10),(11,30),(31,50),(51,70),(71,90),(91,99)]
MINBAND={'forest':0,'cave':1,'dry':2,'water':2,'snow':3,'fire':4}
LABEL={'forest':'산기슭 숲길','cave':'폐광 탐사로','dry':'모래구릉 옛길','water':'강변 수로','snow':'북녘 설원','fire':'화산 바위굴'}
MATERIAL={'forest':'숲결 나뭇조각','cave':'폐광 광석','dry':'사구 유리돌','water':'수로 진주편','snow':'설원 얼음결정','fire':'화산 불씨돌'}
# Model silhouettes individually reviewed. Names and roles below are authored,
# not a claim that the KR491 table supplied these Korean monster names.
ACTORS=[
 ('forest',25,'도토리길 다람쥐','forager',3),('forest',34,'가시꽃 줄기','poison',18),
 ('forest',97,'풀숲 딱정벌레','guard',24),('forest',124,'가시깃 들새','ranged',32),
 ('forest',126,'그늘 버섯요괴','poison',44),('forest',156,'노란숲 들개','hunter',56),
 ('forest',242,'숲가루 나방','ranged',62),('forest',250,'이끼 사람','guard',68),
 ('forest',253,'움직이는 가시덤불','poison',78),('forest',277,'마른나무 원혼','boss',95),
 ('cave',29,'광맥 지네','poison',18),('cave',103,'동굴 늑대','hunter',28),
 ('cave',107,'갑각 지네장수','guard',46),('cave',114,'가시벌레','poison',38),
 ('cave',115,'외눈굴 감시자','ranged',58),('cave',118,'창든 해골병','guard',55),
 ('cave',123,'송곳거미','poison',66),('cave',152,'석회 털벌레','hunter',72),
 ('cave',159,'바위갑충','guard',81),('cave',173,'해골털벌레','boss',97),
 ('dry',104,'모래 들개','hunter',36),('dry',132,'사구 갑충무사','guard',53),
 ('dry',141,'마른숲 주술객','ranged',64),('dry',157,'돌비늘 도마뱀','guard',76),
 ('dry',174,'모래점액괴','guard',84),('dry',185,'사구 멧돼지장수','boss',96),
 ('water',108,'강굴 물뱀','poison',36),('water',158,'늪지 두꺼비','guard',48),
 ('water',167,'물안개 원혼','ranged',66),('water',184,'수초 코브라','poison',73),
 ('water',190,'갈대구렁이','hunter',81),('water',235,'물알집 거미','guard',88),
 ('water',287,'수로 붉은집게','boss',98),
 ('snow',117,'설원 흰늑대','hunter',58),('snow',162,'백골 호랑이','guard',72),
 ('snow',165,'푸른동굴 날개귀','ranged',79),('snow',195,'뿔달린 눈짐승','hunter',87),
 ('snow',198,'얼음사슴 원혼','ranged',92),('snow',291,'설벽 눈괴물','boss',99),
 ('snow',292,'서리요정','ranged',85),('snow',295,'움직이는 눈사람','guard',74),
 ('fire',112,'작은 불정령','ranged',76),('fire',163,'불깃 요조','hunter',85),
 ('fire',186,'화산 비늘요괴','poison',90),('fire',187,'불뿔 수문장','guard',94),
 ('fire',256,'불갑충 여왕','boss',98),('fire',322,'화산 다면수호자','boss',99),
 ('fire',323,'화염 얼굴귀','ranged',97),('snow',324,'서리형 원혼','ranged',96),
 ('cave',325,'백형 원혼','ranged',91),('forest',326,'붉은칼 산령','boss',99)]

def effective():
    assets={};defs={}
    for batch in ['WK-ASSETS-001','WK-CONTENT-001','WK-CONTENT-002']:
        for p in sorted((WORK/'packages'/batch).glob('content-*.jsonl')):
            for r in lines(p):
                (assets if r['kind']=='asset' else defs)[r.get('target_id',r['id'])]=r
    return assets,defs

def build(a):
    assets,defs=effective();ids=IDs();records=[];bynew={};patches={};mapdefs={};areas={};occupied=collections.defaultdict(set)
    package=WORK/'packages'/a.batch
    if package.exists():raise ValueError('New immutable batch required')
    private=WORK/'drafts'/a.batch;private.mkdir(parents=True)
    tables,objects,folder=setup(a.inputs);source=load(WORK/'catalog/expansion-2/map-characteristics.json')['rows']
    index=load(WORK/'HANDOFF_INDEX.json');deps=[{k:r[k] for k in ['batch_id','package_commit','manifest_sha256']} for r in index['packages']]
    def add(kind,key,data,rule='rule.exp2.region',ident=None):
        ident=ident or ids.get(kind,'exp2.'+key);r=record(ident,kind,data,[rule]);records.append(r);bynew[ident]=r;return ident
    def update(target,field,value,rule='rule.exp2.region'):
        if target not in patches:patches[target]=[defs[target],copy.deepcopy(defs[target]['data']),set(),rule]
        old,d,fields,rule=patches[target];parts=field.split('.');node=d
        for part in parts[:-1]:node=node[part]
        node[parts[-1]]=value;fields.add(field)
    def pick(mid,near=None,far=False):
        d=mapdefs[mid];near=near or d['entry'];free=areas[mid]-occupied[mid]-{tuple(d['entry'])}
        if not free:raise ValueError('Insufficient independent reachable placements '+mid)
        at=sorted(free,key=lambda q:(abs(q[0]-near[0])+abs(q[1]-near[1]),q[1],q[0]),reverse=far)[0];occupied[mid].add(at);return list(at)
    def map_make(row,name,levels,interior=False):
        source_id=row['original_map_id'];mid=ids.get('map',f'exp2.na495.{source_id}');w,h=row['dimensions'];raw=(folder/f'TK{source_id}.map').read_bytes()
        cells=map_cells(raw,w,h,tables,objects);area=component(cells,w,h);entry=list(min(area,key=lambda q:(abs(q[0]-w//2)+abs(q[1]-h//2),q[1],q[0])))
        member=f'layouts/{source_id}.json';oldformat=load(WORK/'packages/WK-CONTENT-001/acquisition.json')
        # Object tables are reused from the pinned previous private bundle.
        layout={'width':w,'height':h,'tile_size_px':24,'layers':{'ground':[c['ground_word'] for c in cells],'objects':[c['object_id'] for c in cells]},
          'collision_masks':[c['collision'] for c in cells],'objects_member':'shared/map-format.json',
          'objects_acquisition':{'bundle_id':oldformat['bundle_id'],'member':'shared/map-format.json','sha256':a.shared_format_sha},
          'source_map_sha256':sha(raw),'source_map_id':source_id,'source_dat_sha256':file_sha(next(a.inputs.rglob('NWind.dat'))),
          'coordinate_system':'TOP_LEFT_X_RIGHT_Y_DOWN_ZERO_BASED','raw_ground_words_with_TBL_bases':True}
        write(private/member,layout)
        d={'name':name,'width':w,'height':h,'tile_size_px':24,'coordinate_system':layout['coordinate_system'],
          'layers':{'layout_member':member,'tile_sheet_ids':[f'wk.asset.kr491.sheet.tile{x}' for x in 'abc']},
          'collision':{'layout_member':member,'format':'FOUR_BIT_DIRECTIONAL_MASK','solid_mask':15,'render_object_columns_upwards':True},
          'entry':entry,'portals':[],'spawns':[],'npc_placements':[],'recommended_level':list(levels),
          'layout_acquisition':{'bundle_id':'wk.bundle.regions.002','member':member,'sha256':file_sha(private/member),'source_original_map_id':source_id,'source_sha256':sha(raw)},
          'layout_dimensions_basis':'INFERRED_SQUARE_BYTE_COUNT_AND_CELL_REFERENCES','interior':interior,
          'historical_status':'ORIGINAL_NA495_GEOMETRY_AUTHORED_KOREAN_OFFLINE_EXTENSION','extension':True}
        add('map','unused',d,ident=mid);mapdefs[mid]=d;areas[mid]=area;return mid
    # Exclude reviewed palette/diagnostic mosaics and empty geometry. Small
    # duplicate-service interiors are reserve, not blindly populated.
    pools=collections.defaultdict(list);roompool=[];unselected=[]
    for row in source:
        ground=row['dominant_ground_words'][0][0] if row['dominant_ground_words'] else 0;w=row['dimensions'][0]
        if row['largest_static_component']<12:unselected.append({'original_map_id':row['original_map_id'],'reason':'No useful static walkable component'});continue
        if 220<=row['original_map_id']<=230:unselected.append({'original_map_id':row['original_map_id'],'reason':'Reviewed mosaic/diagnostic or mismatched palette terrain; verify compatible NA495 tile version'});continue
        theme=next((k for k,words in GROUND.items() if ground in words),None)
        if theme and (w>=24 and row['largest_static_component']>=48 or theme in ('cave','fire') and row['largest_static_component']>=36):pools[theme].append(row)
        elif ground in ROOMS:roompool.append(row)
        else:unselected.append({'original_map_id':row['original_map_id'],'reason':'Small/ambiguous role or unsuitable current ecology; retained, not forced into a hunting region'})
    regions=[];used_sources=set();names=['덕수','은채','길찬','마루','하늬','소담','해온','여울','가람','태솔','다온','노을','기오','연화','새봄','도윤','금실','하람','돌쇠','해솔','나린','수아','율호','청연','보름','별하','서안','이솔','아람','단비','라온','찬솔']
    for theme in GROUND:
        rows=sorted(pools[theme],key=lambda r:(r['dimensions'][0],r['largest_static_component'],r['original_map_id']))
        bandkeys=list(range(MINBAND[theme],len(BANDS)));groups=collections.defaultdict(list)
        for n,row in enumerate(rows):groups[bandkeys[min(len(bandkeys)-1,n*len(bandkeys)//max(1,len(rows))) ]].append(row)
        for band,group in groups.items():
            levels=BANDS[band];rid=f'{theme}.{levels[0]}';code=len(regions);label=LABEL[theme]+f' {levels[0]}–{levels[1]}구간'
            mids=[map_make(row,label+f' {n+1}지점',levels) for n,row in enumerate(group)];used_sources.update(row['original_map_id'] for row in group)
            regions.append({'key':rid,'theme':theme,'levels':levels,'name':label,'maps':mids,'person':names[code%len(names)]})
    # Single material per ecology has collection/crafting/sale uses, guaranteed
    # common drops for essential progression. Distinct materials aren't recolors.
    materials={}
    classes=['wk.class.warrior','wk.class.rogue','wk.class.mage','wk.class.poet'];jobs=['전사','도적','주술사','도사']
    def item_data(name,typ,slot,level,stats,icon,acq,buy=100,sell=40,class_ids=None,uses=None):
        defaults={k:0 for k in ['damage_min','damage_max','armor_class','hp_bonus','mp_bonus','strength_bonus','dexterity_bonus','intelligence_bonus','durability']};defaults.update(stats)
        return {'name':name,'item_type':typ,'slot':slot,'requirements':{'level':level,'strength':0,'class_ids':class_ids or classes,'gender':'any'},'stats':defaults,
          'stack_limit':1 if slot!='none' else 100,'prices':{'buy':buy,'sell':sell,'unit':'gold'},
          'flags':{'obtainable':True,'usable':bool(uses),'buyable':typ=='consumable','sellable':True,'droppable':True,'quest_bound':False},
          'use_effects':uses or [],'visual':{'icon_id':'wk.asset.kr491.sheet.item','icon_frame':icon,'identity':'REVIEWED_REPLACEMENT_ICON_INFERRED_NAME'},'acquisition':acq,'extension':True,'historical_status':'AUTHORED_OFFLINE_EXTENSION'}
    for theme in pools:
        materials[theme]=add('item','material.'+theme,item_data(MATERIAL[theme],'material','none',1,{},21,[],sell=10),'rule.exp2.equipment')
    monsters=[]
    for theme,model,name,behavior,level in ACTORS:
        if not pools[theme]:continue
        ident=ids.get('monster',f'exp2.source-model.{model}');dg=ids.get('drop_group',f'exp2.source-model.{model}')
        # Interpolate same-family source combat data at nearest recorded level;
        # these are inferred relative stats, never a fabricated original table.
        fam={'forest':'squirrel','cave':'skeleton','dry':'scorpion','water':'snake','snow':'north','fire':'dragon'}[theme]
        base=min((r['data'] for r in defs.values() if r['kind']=='monster'),key=lambda d:(abs(d['level']-level)+(0 if d.get('family')==fam else 10),d['name']))
        boss=behavior=='boss';mult=2 if boss else 1;hp=max(30,round_int(base['hp']*mult));xp=max(5,round_int(base['experience']*(1.5 if boss else 1)))
        data={'name':name,'level':level,'hp':hp,'mp':base['mp'],'attack':copy.deepcopy(base['attack']),'armor_class':base['armor_class'],'experience':xp,'gold':level*(12 if boss else 3),
          'behavior':copy.deepcopy(base['behavior']),'visual':{'asset_id':f'wk.asset.kr491.monster.{model:03d}','motion':['walk','attack'],'semantic_match':'REVIEWED_SILHOUETTE_AUTHORED_ROLE','palette_variant':0},
          'drop_group_id':dg,'spawn_rules':{'respawn_ms':180000 if boss else 30000,'max_live_per_point':1,'boss':boss,'respawn_when':'cooldown_elapsed','persist_death_cooldown':True,'region_ids':[]},
          'family':fam,'historical_status':'AUTHORED_OFFLINE_EXTENSION_WITH_ORIGINAL_SOURCE_MODEL'}
        data['behavior'].update(aggression='passive_until_hit' if behavior=='forager' else 'hostile',aggro_radius_tiles=0 if behavior=='forager' else 6,leash_radius_tiles=12,special=[])
        data['attack'].update(kind='ranged' if behavior=='ranged' else 'melee',range_tiles=5 if behavior=='ranged' else 1)
        if behavior=='guard':data['behavior']['move_interval_ms']=max(500,data['behavior']['move_interval_ms']);data['hp']=round_int(hp*1.25)
        if behavior=='hunter':data['behavior']['move_interval_ms']=max(300,round_int(data['behavior']['move_interval_ms']*.8))
        if behavior=='poison':data['behavior']['special']=[{'trigger':'attack_hit','op':'status','status':'poison','duration_ms':10000,'period_ms':2000,'damage':max(1,level//3),'probability':ratio(.15)}]
        add('monster','unused',data,'rule.exp2.ecology',ident)
        add('drop_group','unused',{'name':name+' 드롭','mode':'independent','rolls':[{'item_id':materials[theme],'quantity':{'min':1,'max':2 if boss else 1},'probability':ratio(1),'basis':'guaranteed_extension_progression_material'}]},'rule.exp2.ecology',dg)
        monsters.append({'id':ident,'data':data,'theme':theme,'boss':boss});bynew[materials[theme]]['data']['acquisition'].append({'kind':'monster_drop','monster_id':ident,'source_mode':'INFERRED'})
    # Existing source monsters participate too; no new ID for an old identity.
    for iid,r in defs.items():
        if r['kind']=='monster':monsters.append({'id':iid,'data':copy.deepcopy(r['data']),'theme':next((k for k,f in [('forest',['rabbit','squirrel','rat','fox','bear','tiger','deer']),('cave',['bat','skeleton','ghost','spider']),('dry',['scorpion','mantis','monkey']),('water',['snake','pig']),('snow',['north']),('fire',['dragon','guardian','bull','chicken'])] if r['data'].get('family') in f),'cave'),'boss':r['data']['spawn_rules']['boss']})
    def spawn(mid,m,number=0,boss=False):
        xy=pick(mid,far=True);radius=3;near=[list(p) for p in sorted(areas[mid]) if abs(p[0]-xy[0])+abs(p[1]-xy[1])<=radius][:12]
        pid=ids.get('spawn',f'exp2.{mid}.{m["id"]}.{number}');d=mapdefs[mid]
        d['spawns'].append({'placement_id':pid,'monster_id':m['id'],'x':xy[0],'y':xy[1],'max_live':1 if boss else min(5,max(2,len(near)//2)),
          'radius_tiles':radius,'spawn_cells':near,'respawn_ms':m['data']['spawn_rules']['respawn_ms'],'source_mode':'INFERRED'})
        if m['id'] in bynew and mid not in m['data']['spawn_rules']['region_ids']:m['data']['spawn_rules']['region_ids'].append(mid)
    for reg in regions:
        lo,hi=reg['levels'];pool=[m for m in monsters if m['theme']==reg['theme'] and not m['boss'] and lo<=m['data']['level']<=hi]
        if not pool:pool=sorted([m for m in monsters if m['theme']==reg['theme'] and not m['boss']],key=lambda m:abs(m['data']['level']-lo))[:3]
        reg['population_ids']=[]
        for n,mid in enumerate(reg['maps']):
            # A few meaningful spawn clusters, never one token spawn claiming
            # an entire220x220 map is populated or all source species selected.
            local=[pool[(n*3+j)%len(pool)] for j in range(min(3,len(pool)))]
            for j,m in enumerate(local):spawn(mid,m,j);reg['population_ids'].append(m['id'])
        bosses=[m for m in monsters if m['theme']==reg['theme'] and m['boss'] and lo<=m['data']['level']<=hi]
        if bosses:reg['boss']=min(bosses,key=lambda m:(abs(m['data']['level']-hi),m['id']));spawn(reg['maps'][-1],reg['boss'],9,True)
    # Ensure every new monster actually has at least one role-compatible spawn.
    for m in monsters:
        if m['id'] not in bynew or m['data']['spawn_rules']['region_ids']:continue
        reg=min((r for r in regions if r['theme']==m['theme']),key=lambda r:abs(sum(r['levels'])/2-m['data']['level']))
        spawn(reg['maps'][-1],m,19,m['boss'])
    roompool=sorted(roompool,key=lambda r:(r['dimensions'][0],-r['largest_static_component'],r['original_map_id']))
    rooms=iter(roompool);npc_models={'guide':[8,9,15,51,67,68,69,80,82,180,200,202,203,205,207,209,211,270,272,273,300],
      'supplier':[4,5,7,13,14,53,54,79,85,201,204,206,271,294,321], 'smith':[38,86,194,254,302,304],
      'scout':[2,6,10,11,12,16,36,37,60,63,64,65,66,81,84,143,144,145,146,147,148,149,150,151,208,261,262,264,265,274]}
    ncounter=collections.Counter();recipes=[];quest_ids=[]
    def npc(role,reg,mid):
        xy=pick(mid);pool=npc_models[role];model=pool[ncounter[role]%len(pool)];ncounter[role]+=1
        name=reg['person']+{'guide':' 길잡이','supplier':' 보급상','smith':' 대장장이','scout':' 길목 파수꾼'}[role];nid=ids.get('npc','exp2.'+reg['key']+'.'+role)
        d={'name':name,'visual':{'asset_id':f'wk.asset.kr491.monster.{model:03d}','motion':'walk','frame_ms':100,'identity':'REVIEWED_HUMAN_AUTHORED_PERSON'},
           'dialogue':[{'id':'greeting','text':f"{reg['name']}에 오신 것을 환영합니다. "+{'guide':'길목의 파수꾼에게 먼저 길을 확인하고 돌아오세요.','supplier':'여행에 필요한 회복약을 준비했습니다. 가격과 필요한 물품을 확인하세요.','smith':MATERIAL[reg['theme']]+'를 모으면 직업에 맞는 장비를 만들 수 있습니다. 재료와 돈은 함께 소비됩니다.','scout':'여기는 길이 갈라지는 곳입니다. 지나온 길의 출입구로 언제든 돌아갈 수 있습니다.'}[role],
             'choices':[]}], 'services':[], 'placements':[{'map_id':mid,'x':xy[0],'y':xy[1]}], 'interaction_range_tiles':2,'role':role,'dialogue_source':'AUTHORED_KOREAN_OFFLINE_NOT_HISTORICAL_QUOTE'}
        add('npc','unused',d,ident=nid);mapdefs[mid]['npc_placements'].append({'placement_id':ids.get('placement','exp2.'+nid),'npc_id':nid,'x':xy[0],'y':xy[1],'blocking':False});return nid,d
    gear={};potions={}
    for band,(lo,hi) in enumerate(BANDS):
        lv=max(1,lo);theme=['forest','cave','dry','water','snow','fire'][band]
        mats=materials.get(theme,materials['forest']);gear[band]=[]
        for j,cid in enumerate(classes):
            for slot in ['weapon','body']:
                name=f'{jobs[j]} '+['초행','광맥','사구','수로','설벽','화산'][band]+(' 무기' if slot=='weapon' else ' 도복')
                stats={'durability':10000,'damage_min':max(2,round_int((2+lv*.6)*(1.2 if j==0 else 1))) if slot=='weapon' else 0,
                  'damage_max':max(4,round_int((4+lv*.9)*(1.2 if j==0 else 1))) if slot=='weapon' else 0,
                  'armor_class':0 if slot=='weapon' else -max(1,round_int(lv/3)), 'hp_bonus':lv*(8 if j in (0,1) else 3),'mp_bonus':lv*(10 if j in (2,3) else 2)}
                rid=ids.get('recipe',f'exp2.{band}.{j}.{slot}');d=item_data(name,'weapon' if slot=='weapon' else 'armor',slot,lv,stats,0 if slot=='weapon' else 12,[{'kind':'recipe','recipe_id':rid,'source_mode':'INFERRED'}],buy=max(120,lv*lv*12),sell=max(40,lv*lv*4),class_ids=[cid])
                aid=f'wk.asset.kr491.'+('sword.'+f'{[0,17,50,56][j]+band:03d}' if slot=='weapon' else 'body.'+f'{[2,19,6,18][j]+band*2:03d}')
                d['visual'].update(equipment_asset_id=aid,attachment='ORIGINAL_FOOT_OVERLAY' if slot=='weapon' else 'BODY_REPLACEMENT',motion='sword' if slot=='weapon' else 'walk_unarmed')
                iid=add('item',f'gear.{band}.{j}.{slot}',d,'rule.exp2.equipment');gear[band].append(iid)
                recipes.append({'id':rid,'item_id':iid,'material_id':mats,'band':band,'data':{'name':name+' 제작','npc_id':None,'consume':[{'item_id':mats,'quantity':2+band*2}],
                   'outputs':[{'item_id':iid,'quantity':1}],'gold_cost':max(d['prices']['sell']+10,(lv+1)*40),'success_ratio':ratio(1),'extension':True}})
        potions[band]=[]
        for kind,op,amount,icon in [('회복약','heal_hp',max(40,lo*lo*8),10),('마력약','restore_mp',max(30,lo*lo*3),21)]:
            potions[band].append(add('item',f'potion.{band}.{op}',item_data(['초행','광맥','사구','수로','설벽','화산'][band]+' '+kind,'consumable','none',1,{},icon,[],buy=max(12,(lo+1)*3),sell=max(4,lo),uses=[{'op':op,'amount':amount,'target':'self'}]),'rule.exp2.equipment'))
    def link(src,dst):
        sd=mapdefs.get(src) or defs[src]['data'];dd=mapdefs.get(dst) or defs[dst]['data']
        if src in mapdefs:xy=pick(src);ports=sd['portals']
        else:
            if src not in areas:
                with zipfile.ZipFile(a.previous_bundle) as z:layout=load_bytes(z.read(sd['layout_acquisition']['member']))
                cells=[{'collision':m} for m in layout['collision_masks']];areas[src]=component(cells,sd['width'],sd['height']);mapdefs[src]=copy.deepcopy(sd)
                occupied[src].update((p['x'],p['y']) for key in ['portals','spawns','npc_placements'] for p in sd[key])
            xy=pick(src);ports=mapdefs[src]['portals']
        ports.append({'placement_id':ids.get('portal','exp2.'+src+'.to.'+dst),'x':xy[0],'y':xy[1],'destination_map_id':dst,'destination_xy':dd['entry'],'trigger':'interact','source_mode':'INFERRED'})
        if src in defs:update(src,'portals',ports)
    def attach(src,dst):link(src,dst);link(dst,src)
    anchors={'forest':'wk.map.region.squirrel','cave':'wk.map.region.bat','dry':next(i for i,r in defs.items() if r['kind']=='map' and r['data']['name']=='가재전갈굴'),
      'water':'wk.map.region.dragon','snow':next(i for i,r in defs.items() if r['kind']=='map' and r['data']['name']=='극지방'),'fire':'wk.map.region.dragon'}
    for reg in regions:
        band=BANDS.index(tuple(reg['levels']));first=reg['maps'][0]
        try:
            room=next(rooms);camp=map_make(room,reg['name']+' 보급소',reg['levels'],True);used_sources.add(room['original_map_id']);reg['camp']=camp
        except StopIteration:camp=first;reg['camp']=camp
        guide,gd=npc('guide',reg,camp);supply,sd=npc('supplier',reg,camp);smith,fd=npc('smith',reg,camp);scout,scd=npc('scout',reg,reg['maps'][-1])
        reg.update(guide_id=guide,supplier_id=supply,smith_id=smith,scout_id=scout)
        offers=[{'item_id':iid,'price_gold':bynew[iid]['data']['prices']['buy'],'stock':'infinite','requirements':{'min_level':0},'source_mode':'INFERRED'} for iid in potions[band]]
        sid=add('shop',reg['key']+'.supplies',{'name':reg['name']+' 여행 보급','npc_id':supply,'offers':offers,'currency':'gold','sell_policy':{'unit_price_field':'prices.sell','quest_bound':False,'atomic_transaction':True}},'rule.exp2.equipment')
        sd['services']=[{'type':'shop','shop_id':sid},{'type':'rest','gold_cost':max(5,reg['levels'][0]),'restore_hp':'max','restore_mp':'max'}];sd['dialogue'][0]['choices']=[{'label':'회복약 보기','service_index':0},{'label':'쉬어 가기','service_index':1}]
        for iid in potions[band]:bynew[iid]['data']['acquisition'].append({'kind':'shop','shop_id':sid,'source_mode':'INFERRED'})
        for rec in recipes:
            if rec['band']!=band:continue
            rd=copy.deepcopy(rec['data']);rd['npc_id']=smith;rd['consume'][0]['item_id']=materials[reg['theme']]
            if rec['data']['npc_id'] is None:
                rec['data']=rd;recipe_id=rec['id']
            else:
                recipe_id=ids.get('recipe','exp2.'+reg['key']+'.'+rec['item_id'])
                bynew[rec['item_id']]['data']['acquisition'].append({'kind':'recipe','recipe_id':recipe_id,'source_mode':'INFERRED'})
            add('recipe','unused',rd,'rule.exp2.equipment',recipe_id)
            fd['services'].append({'type':'recipe_book','recipe_id':recipe_id})
            fd['dialogue'][0]['choices'].append({'label':rd['name'],'service_index':len(fd['services'])-1})
        fd['services'].append({'type':'repair','price_multiplier':.001,'max_durability_field':'stats.durability'});fd['dialogue'][0]['choices'].append({'label':'장비 수리','service_index':len(fd['services'])-1})
        qs=[]
        for step in range(3 if 'boss' in reg else 2):
            qid=ids.get('quest','exp2.'+reg['key']+f'.{step+1}');mat=materials[reg['theme']]
            if step==0:objectives=[{'type':'talk','npc_id':scout,'count':1},{'type':'talk','npc_id':guide,'count':1,'after_other_objectives':True}];consume=[];title='돌아오는 길';text='길목 파수꾼을 찾아 귀환로를 확인하고 제게 돌아와 주세요.'
            elif step==1:objectives=[{'type':'collect','item_id':mat,'count':3},{'type':'talk','npc_id':smith,'count':1,'after_other_objectives':True}];consume=[{'item_id':mat,'quantity':3}];title='여행 장비 준비';text=MATERIAL[reg['theme']]+' 세 개를 대장장이에게 전달해 주세요. 사냥에서 확실히 얻을 수 있고 제출할 때만 소비됩니다.'
            else:objectives=[{'type':'kill','monster_id':reg['boss']['id'],'map_id':reg['maps'][-1],'count':1},{'type':'talk','npc_id':guide,'count':1,'after_other_objectives':True}];consume=[];title=reg['boss']['data']['name']+'의 길목';text=reg['boss']['data']['name']+' 때문에 마지막 길목이 막혔습니다. 토벌 후 돌아와 소식을 전해 주세요.'
            d={'name':reg['name']+' — '+title,'start_npc_id':guide,'complete_npc_id':smith if step==1 else guide,'requirements':{'level':reg['levels'][0],'class_ids':classes},'prerequisites':qs[-1:] if step else [],
              'objectives':objectives,'consume':consume,'rewards':[{'type':'experience','amount':max(100,reg['levels'][0]**3*10)*(step+1)},{'type':'gold','amount':max(20,reg['levels'][0]*30)},
                 {'type':'item','item_id':potions[band][0],'quantity':2}], 'repeat':{'mode':'once','cooldown_ms':0,'occurrence_counter':False},'completion_key':qid,'extension':True}
            add('quest','unused',d,ident=qid);qs.append(qid);quest_ids.append(qid)
            gd['dialogue'].append({'id':f'quest{step+1}','text':text,'choices':[{'label':'의뢰 목록 열기','service_index':0}]})
        gd['services']=[{'type':'quests','quest_ids':qs}];gd['dialogue'][0]['choices']=[{'label':'지역 의뢰 보기','service_index':0}]
        fd['services'].append({'type':'quests','quest_ids':qs[1:2]})
        scd['services']=[];scd['dialogue'][0]['choices']=[{'label':'길 안내를 마칩니다','close':True}]
        attach(anchors[reg['theme']],camp)
        if camp!=first:attach(camp,first)
        for x,y in zip(reg['maps'],reg['maps'][1:]):attach(x,y)
        # End shortcut returns to the camp. It's an intended return, not a trap.
        if len(reg['maps'])>1:attach(reg['maps'][-1],camp)
        reg['quest_ids']=qs;reg['gear_ids']=gear[band];reg.pop('boss',None)
    for rec in recipes:
        if rec['data']['npc_id'] is None:raise ValueError('Equipment growth band has no crafter '+rec['id'])
    for target,(old,d,fields,rule) in patches.items():
        r=patch_record(ids,old,d,sorted(fields),rule,'regions');records.append(r)
    for r in records:r['references']=data_refs(r['data'],assets)
    rules=[{'id':'rule.exp2.region','source_mode':'INFERRED','basis':['512 unique unselected source hash candidates, full lightweight cell validation','189 private layout representatives','131 dominant source ground types'],
       'rules':{'selection':'compatible terrain with useful original static component, rooms only for actual regional supply roles','geometry':'source cells, tiles, masks unchanged; square dimensions inferred','portals':'paired entry/return; existing lists extended with effective expected-value guard','shared_format':'original object table retained in WK-CONTENT-001 private bundle, no duplicate copy','not_selected':'diagnostic mosaics, small/ambiguous redundant roles and empty components stay in reserve','history':'NA495 geometry is not verified Korean1998 geography'}},
      {'id':'rule.exp2.ecology','source_mode':'INFERRED','basis':['327 source actor representatives, purpose-compatible models','nearest-level same-family preserved source combat records'],
       'rules':{'identity':'new authored extensions, stable IDs keyed by original source model','balance':'nearest source HP/attack/XP, explicit boss multipliers; not original Korean values','behavior':'existing wander/chase, melee/ranged and source-compatible poison operations','materials':'guaranteed common collection/crafting drops; no random essential gate','population':'several clusters in each selected hunting layout; existing monster IDs reused, named source species not duplicated'}},
      {'id':'rule.exp2.equipment','source_mode':'INFERRED','basis':['four playable classes, fixed six pre99 growth intervals','existing per-level weapon/armor completion rule'],
       'rules':{'new_gear':'one weapon and body armor per class/growth interval, class-specific HP/MP/damage purpose','recipes':'guaranteed outcome, consumes materials and gold; cash fee above output sell value','potions':'class-neutral supply at regional camp','history':'extensions; source-known basic rules unchanged'}},
    ]
    (package/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',package/'schema/content-v1.json');write(package/'provenance.json',rules);shard(package,records)
    manifest={'privacy':'PRIVATE_ONLY','batch_id':a.batch,'files':[{'path':str(p.relative_to(private)),'size_bytes':p.stat().st_size,'sha256':file_sha(p)} for p in sorted(private.rglob('*.json'))]}
    write(private/'PRIVATE_MANIFEST.json',manifest)
    bundle=WORK/'drafts'/a.bundle_name
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(private.rglob('*.json')):
            zi=zipfile.ZipInfo(str(p.relative_to(private)),(2026,10,14,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;z.writestr(zi,p.read_bytes())
    with zipfile.ZipFile(bundle) as z:assert z.testzip() is None
    write(package/'acquisition.json',{'bundle_id':'wk.bundle.regions.002','file_name':bundle.name,'size_bytes':bundle.stat().st_size,'sha256':file_sha(bundle),'privacy':'PRIVATE_ONLY',
       'work_acquisition':'PASS_ACTUAL_BYTES_AND_CRC','recipient_acquisition':'NOT_RUN','library_file_id':None,
       'shared_format_dependency':{'batch_id':'WK-CONTENT-001','bundle_id':'wk.bundle.regions.001','member':'shared/map-format.json','sha256':a.shared_format_sha},
       'rebuild':{'tool':'content-work/tools/build_expansion_regions.py','source_map_set':'NA495','base_game_commit':BASE}})
    summary={'scope':'DATA_ONLY','counts':dict(collections.Counter(r['kind'] for r in records)),'new_definitions':sum(r['operation']=='add' for r in records),'existing_definition_patches':len(patches),
       'physical_maps':len([r for r in records if r['kind']=='map' and r['operation']=='add']), 'distinct_source_hashes':len({r['data']['layout_acquisition']['source_sha256'] for r in records if r['kind']=='map' and r['operation']=='add'}),
       'new_region_groups':len(regions),'new_source_aliases':0,'source_pixels_copied':0,'new_monsters':len(ACTORS),'new_bosses':sum(x[3]=='boss' for x in ACTORS),
       'quests':len(quest_ids),'chain_regions':len(regions),'new_recipe_entries':sum(r['kind']=='recipe' for r in records),'growth_intervals':BANDS,'class_ids':classes,
       'used_original_map_ids':sorted(used_sources),'unselected_reasons':unselected,'remaining_compatible_room_ids':[r['original_map_id'] for r in roompool if r['original_map_id'] not in used_sources],
       'regions':regions,'game_import':'NOT_RUN','gameplay':'NOT_RUN','directional_mask_traversal':'NOT_RUN','dynamic_conditions':'NOT_RUN'}
    write(package/'region-summary.json',summary);ids.save();print(a.batch,summary['counts'],'maps',summary['physical_maps'],'regions',len(regions),'private bytes',bundle.stat().st_size)

def load_bytes(b):
    import json
    return json.loads(b)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--previous-bundle',type=Path,required=True);p.add_argument('--shared-format-sha',required=True);p.add_argument('--bundle-name',required=True);build(p.parse_args())
