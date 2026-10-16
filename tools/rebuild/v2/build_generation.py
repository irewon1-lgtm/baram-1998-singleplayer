#!/usr/bin/env python3
"""Compile a fresh private, source-first G1 runtime from the frozen source set.

Original source rows stay attached to executable definitions. Source names,
learning conditions and documented drops are reused; unknown combat balance,
geography, offline adaptations and visual bindings are explicitly reconstructed.
No source archives, saves or earlier runtime generations are changed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
import wave

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'p2'))
from generation_contract import source_entities, clean_name, value_of, ADVANCEMENTS
import gameplay_assets

GENERATION = 'WORK-V2-G1-20261017'
CITY = 'gp:map:domestic_city'
BUYA = 'g1:map:buya_city'
JOBS = ('전사', '도적', '주술사', '도사')
REGION_LEVELS = {'왕초보 사냥터': 1, '쥐굴': 5, '뱀굴': 10, '곰, 호랑이굴': 15,
    '여우굴': 22, '자호굴': 28, '거미, 사마귀굴': 34, '가재, 전갈굴': 40,
    '해골굴': 45, '유령굴': 50, '흑해골굴': 55, '흑령굴': 60,
    '귀신굴': 65, '도깨비굴': 70, '산적굴': 75, '극지방': 80,
    '북방대초원': 83, '일본': 85, '한두고개': 88, '승급사냥터': 90,
    '쥐왕굴': 80, '뱀왕굴': 82, '돼지왕굴': 84, '닭왕굴': 84,
    '원숭이왕굴': 86, '소왕굴': 86, '토끼왕굴': 86, '구명곡,개왕굴': 87,
    '양왕굴': 87, '말왕굴': 88, '용 왕 굴': 92, '호랑이왕굴': 92,
    '초보자 사냥터': 1, '호랑이왕': 92, '개왕굴': 87}
ACTION_KINDS = {'damage','heal','buff','debuff','status','return','shrine','identify',
                'restore_mp','summon','cleanse','revive','loot','blink'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(value):
    if isinstance(value, Path): value = value.read_bytes()
    elif not isinstance(value, bytes): value = canonical(value).encode()
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def ident(prefix, name):
    return 'g1:' + prefix + ':' + sha(name)[:14]


def load_tables(normalized):
    # B2 selected the inventory; this reads only the gameplay tables it selected.
    names = ['kr_official_core', 'kr_official_items', 'kr_official_services',
             'kr_official_crafting_facts', 'kr_official_skill_effects',
             'kr_official_facility_rules', 'kr_official_flow']
    return {name+'.jsonl': [json.loads(x) for x in (normalized/(name+'.jsonl')).read_text().splitlines() if x.strip()]
            for name in names}


def annotate(row, kind, runtime_id, value, action, dependencies=(), tier='LEGACY_RECONSTRUCTED', rationale=None):
    return {'content_id': row.get('content_id', runtime_id), 'field': 'effective_definition',
        'source_tier': tier, 'source_ref': row.get('source_locator', row.get('source_id', 'MASTER_PLAN_V2')),
        'observed_version': row.get('build_profile_id', GENERATION), 'observed_date': '2026-10-17',
        'rationale': rationale or 'Reuse documented Korean fields; reconstruct missing runtime semantics and balance for offline play.',
        'selected_value': value, 'action_type': action, 'dependencies': list(dependencies),
        'runtime_ref': kind+'.'+runtime_id, 'evidence': {'source_record_sha256': sha(row)},
        'status': 'COMPILED_STATIC_VALIDATION_PENDING', 'runtime_test': 'NOT_RUN'}


def numeric(value, default=0):
    try: return float(value) if value is not None else default
    except (TypeError, ValueError): return default


def item_kind(name, source):
    compact = clean_name(name)
    if source.get('item_kind') == 'weapon' or any(x in compact for x in ('제삼검','철검','어전의칼','해골죽장','명삼지창','수리검','대마령봉')): return 'weapon', 'weapon'
    if '망또' in compact or '망토' in compact: return 'armor', 'cape'
    if any(x in compact for x in ('투구','모자','머리띠','머리장식','관')): return 'armor', 'helmet'
    if any(x in compact for x in ('반지','팔찌','팔지','장갑','골무')): return 'armor', 'ring'
    if '방패' in compact: return 'armor', 'shield'
    if any(x in compact for x in ('신발','장화','짚신','구두')): return 'armor', 'boots'
    if source.get('item_kind') == 'armour_or_accessory' or any(x in compact for x in ('웨딩드레스','산타클로스옷','죄수복','장삼')): return 'armor', 'armor'
    if any(x in compact for x in ('비서','귀가서')): return 'consumable', ''
    if any(x in compact for x in ('시약','고기','복숭아','화채','샘물','인삼','산삼','동동주','막걸리','세주','홍주','작약주')): return 'consumable', ''
    return 'material', ''


def build_items(data, entities, adoption):
    for iid, (kind, row, _) in entities.items():
        if kind != 'items' or iid in data['items']: continue
        source = value_of(row); name = row['entity_name_ko']; k, slot = item_kind(name, source)
        damage_min=source.get('damage_min');damage_max=source.get('damage_max')
        raw_damage=str(source.get('raw_numeric_cells',{}).get('위력',''))
        match=re.fullmatch(r'\s*(\d+)\s*[^\d\s]+\s*(\d+)\s*',raw_damage)
        if damage_min is None and damage_max is None and match:
            damage_min,damage_max=map(int,match.groups())
        average=(numeric(damage_min)+numeric(damage_max))/2
        inferred_level=max(1,min(95,int(math.sqrt(max(1,average))*1.6)))
        level = max(0, min(99, int(numeric(source.get('minimum_level'), inferred_level))))
        price = max(10, min(100000, int(numeric(source.get('listed_price'), 20 + level*30))))
        item = {'id': iid, 'name': name, 'kind': k, 'stack_max': 1 if slot else 999,
            'required_level': level, 'required_job': source.get('job_restriction_documented') or 'any',
            'buy_price': price, 'sell_price': max(1, price//4), 'source_value': deepcopy(source),
            'source_id': row.get('source_ids', []), 'source_pointer': row.get('source_locator'),
            'fact_status': 'ORIGINAL_FIELDS_WITH_RECONSTRUCTED_GAMEPLAY', 'original_native_id': None,
            'effective_field_status': {'name': 'LEGACY_VERIFIED', 'required_level': 'LEGACY_VERIFIED' if source.get('minimum_level') is not None else 'INFERRED',
                'combat_stats': 'LEGACY_RECONSTRUCTED', 'prices': 'LEGACY_RECONSTRUCTED', 'acquisition': 'LEGACY_RECONSTRUCTED'},
            'acquisition_paths': [], 'function_paths': []}
        raw_jobs=item['required_job']
        job_list=[j for j in JOBS if j in (raw_jobs if isinstance(raw_jobs,(list,tuple)) else str(raw_jobs))]
        if len(job_list)>1:item['required_jobs']=job_list;item['required_job']='any'
        elif len(job_list)==1:item['required_job']=job_list[0]
        else:item['required_job']='any'
        if slot:
            item.update(slot=slot, durability=max(100, min(3000, int(numeric(source.get('durability'), 200)))))
            if slot == 'weapon':
                avg=average
                item['attack'] = max(4, min(220, int(round(math.sqrt(max(1, avg))*3+level*.55))))
                item['damage_min'] = max(1, int(item['attack']*.8)); item['damage_max'] = int(item['attack']*1.2)
                item['look'] = 'player_weapon'
            else:
                ac=abs(numeric(source.get('armor_class'), 1+level//10))
                item['defense'] = max(1, min(28, int(round(ac*.55+level*.04))))
                item['look'] = 'player_armor'
            item['function_paths'].append({'kind':'equip', 'slot':slot})
            # Retain listed source price separately. Unknown or implausibly cheap
            # strong gear gets a consistent offline economic cost, never free.
            value_floor=int(item.get('attack',0)*35+item.get('defense',0)*45+level*level*2)
            item['buy_price']=max(price,value_floor);item['sell_price']=max(1,item['buy_price']//4)
            if source.get('required_strength') is not None:item['required_strength']=max(0,int(numeric(source['required_strength'])))
            if match:item['source_damage_reconstruction']={'raw':raw_damage,'damage_min':damage_min,'damage_max':damage_max,'rationale':'Two integer endpoints in the acquired source damage cell, separated by a corrupted range marker; source bytes retained.'}
        elif k=='consumable':
            if any(x in clean_name(name) for x in ('비서','귀가서')):
                item['action_type']='return';item['function_paths'].append({'kind':'return_to_city'})
            elif any(x in clean_name(name) for x in ('동동주','막걸리','세주','홍주','작약주','파란시약','보라시약','청색시약')):
                item['mp_restore']=max(20,min(650,20+price//3));item['function_paths'].append({'kind':'restore_mp'})
            else:
                item['hp_restore']=max(12,min(900,12+price//3));item['function_paths'].append({'kind':'restore_hp'})
        effect_map={'힘':'strength_bonus','민첩성':'dexterity_bonus','지력':'intelligence_bonus',
            '체력':'hp_bonus','마력':'mp_bonus','기력':'mp_bonus','재생력':'regen_bonus',
            '명중률':'accuracy_bonus','마법보호력':'magic_defense_bonus','파괴력':'damage_bonus'}
        item['source_effect_adoption']=[]
        for effect in source.get('effects',[]):
            label=effect.get('stat_label_documented');field=effect_map.get(label);delta=numeric(effect.get('delta'))
            if not field:
                item['source_effect_adoption'].append({'source':effect,'status':'UNSUPPORTED_SOURCE_FIELD','reason':'No acquired runtime unit mapping.'});continue
            value=int(delta)
            if field=='regen_bonus':value=int(math.copysign(max(1,round(abs(delta)/5)),delta))
            if field=='magic_defense_bonus':value=int(math.copysign(min(30,abs(delta)),delta))
            item[field]=int(item.get(field,0))+value
            item['source_effect_adoption'].append({'source':effect,'status':'USED_SCALED' if value!=delta else 'USED',
                'runtime_field':field,'effective_value':value,'rationale':'Published stat delta reused. Regen /5 per4secondtick; 기력→MP. Accuracy gives deterministic physical precision damage; magic protection reduces all offline enemy damage until distinct enemy spell types exist.'})
        item['gender_adoption']={'source_value':source.get('gender_documented'),'effective_value':'unisex',
            'source_tier':'LEGACY_RECONSTRUCTED','rationale':'Four-job offline character appearance supports both visual variants; source gender-labelled clothing remains distinct but wearable for either variant.'}
        data['items'][iid]=item
        adoption.append(annotate(row,'items',iid,{key:item.get(key) for key in ('kind','slot','attack','defense','hp_restore','mp_restore','action_type','required_level','required_strength','required_jobs','buy_price','source_effect_adoption','gender_adoption')}, 'equip' if slot else item.get('action_type', 'consume' if k=='consumable' else 'material')))
    return defaultdict(list, {name:[iid for iid,item in data['items'].items() if clean_name(item['name'])==name]
                              for name in {clean_name(item['name']) for item in data['items'].values()}})


def ensure_item(data, names, name, adoption, reason):
    name = {'토끼고리':'토끼고기','자호의 가죽':'자호의가죽','깨끗한 얼음':'깨끗한얼음','은나무 가지':'은나무가지', '도깨비들의 부싯돌':'부싯돌'}.get(name,name)
    key=clean_name(name)
    if names.get(key): return names[key][0]
    iid=ident('item',key);kind,slot=item_kind(name,{})
    data['items'][iid]={'id':iid,'name':name,'kind':kind,'stack_max':999,'required_level':0,'required_job':'any',
        'buy_price':None,'sell_price':10,'source_value':None,'source_id':[],
        'fact_status':'LEGACY_RECONSTRUCTED','effective_field_status':{'all':'LEGACY_RECONSTRUCTED'},
        'acquisition_paths':[],'function_paths':[]}
    if kind=='consumable': data['items'][iid].update(hp_restore=18,function_paths=[{'kind':'restore_hp'}])
    if slot:
        data['items'][iid].update(slot=slot,stack_max=1,durability=400,required_level=40,
            attack=55 if slot=='weapon' else 0,defense=8 if slot!='weapon' else 0,
            buy_price=2400,sell_price=600,function_paths=[{'kind':'equip','slot':slot}])
    names[key].append(iid)
    adoption.append(annotate({},'items',iid,{'name':name},'material',tier='LEGACY_RECONSTRUCTED',rationale=reason))
    return iid


def source_monster_level(source):
    region=source.get('region') or '야외'
    base=REGION_LEVELS.get(region, 45)
    xp=numeric((source.get('experience') or {}).get('value'), 0)
    if base==1: return 1
    # Published XP is retained, but converted to bounded offline combat tiers.
    variation=max(0,min(6,int(math.log10(max(1,xp)))-2))
    return min(99,base+variation)


def build_monsters(data, entities, names, adoption):
    regions=defaultdict(list)
    for iid,(kind,row,_) in entities.items():
        if kind!='monsters':continue
        source=value_of(row);region=source.get('region') or '야외';level=source_monster_level(source)
        if iid in data['monsters']:
            monster=data['monsters'][iid]
            monster['level']=level;monster['region']=region
        else:
            monster={'id':iid,'name':row['entity_name_ko'],'level':level,'region':region,
                'hp':int(20+level*6+level*level*.11),'attack':max(3,int(2+level*.6)),
                'defense':int(level*.09),'xp':max(8,int(8+level*level*.22)),
                'aggression':'retaliate' if level<12 else 'hostile','attack_interval':1.7 if level<40 else 1.45,
                'move_interval':1.7 if level<20 else 1.25,'respawn_seconds':15.0,
                'chase_range':5,'leash_range':7,'drops':[],'money_min':max(1,level//2),'money_max':max(3,level*2),
                'source_value':deepcopy(source),'source_id':row.get('source_ids',[]), 'source_pointer':row.get('source_locator'),
                'original_native_id':None,'fact_status':'ORIGINAL_FIELDS_WITH_RECONSTRUCTED_GAMEPLAY',
                'effective_field_status':{'name':'LEGACY_VERIFIED','region':'LEGACY_VERIFIED','published_xp':'LEGACY_VERIFIED','hp_attack_xp_drop_chance_AI':'LEGACY_RECONSTRUCTED'}}
            data['monsters'][iid]=monster
        drops={r['item_id']:r for r in monster['drops']}
        source_drop_names=source.get('possible_item_names',[])
        if source_drop_names==['용왕다람쥐의','방열쇠']:source_drop_names=['용왕다람쥐의방열쇠']
        for name in source_drop_names:
            if not isinstance(name,str) or not name.strip() or name.strip() in ('없음','무','돈'):continue
            loot=ensure_item(data,names,name,adoption,'Named monster drop in acquired Korean source; missing standalone item row reconstructed as usable material.')
            drops[loot]={'item_id':loot,'chance':.32,'quantity_min':1,'quantity_max':1,'source_tier':'LEGACY_VERIFIED_NAME_RECONSTRUCTED_ROLL'}
        monster['drops']=list(drops.values())
        regions[region].append(iid)
        adoption.append(annotate(row,'monsters',iid,{'level':level,'hp':monster['hp'],'xp':monster['xp'],'region':region},'combat',drops,
            rationale='Documented Korean species/region/drop names retained; bounded offline XP and combat use one level model, not original server statistics.'))
    return regions


class MapBuilder:
    def __init__(self,data,base,priority,output,adoption):
        self.data=data;self.base=base;self.priority=priority;self.output=output;self.adoption=adoption
        self.tiles={};self.tile_sources={}
        # Reuse already decoded native pixels; no archive re-decode or geometry claim.
        for path in sorted((priority/'maps').glob('*.json')):
            source=json.loads(path.read_text())
            if not isinstance(source,dict):continue
            floor=priority/'maps'/str(source.get('floor_png',''))
            if not floor.is_file():continue
            grounds=source.get('collisions',{}).get('ground_ids',[]);w=int(source.get('grid_width',64))
            with Image.open(floor) as im:
                for index,word in enumerate(grounds):
                    if word not in self.tiles and word and index//w*24+24<=im.height:
                        self.tiles[word]=im.crop((index%w*24,index//w*24,index%w*24+24,index//w*24+24)).convert('RGBA')
                        self.tile_sources[word]={'path':path.name,'cell':[index%w,index//w],'sha256':sha(floor)}
            if all(x in self.tiles for x in (1,52,153,323,324,327,333,370,488,593,697,714,1028)):break

    def make(self,mid,name,region='city',level=1,w=40,h=32):
        outdoor=region in ('city','북방대초원','일본','한두고개','극지방','승급사냥터','야외')
        preferred=52 if outdoor else 323
        if region=='극지방':preferred=697
        elif region=='일본':preferred=370
        elif region=='북방대초원':preferred=593
        elif region in ('승급사냥터','호랑이왕굴','용 왕 굴'):preferred=488
        ground=preferred if preferred in self.tiles else 52
        if region=='city':ground=153 if 153 in self.tiles else ground
        wall=(333 if not outdoor else 133) if region!='극지방' else 714
        if wall not in self.tiles:wall=ground
        road=ground if not outdoor or region=='극지방' else 1
        if road not in self.tiles:road=ground
        blocked=set();grounds=[ground]*(w*h)
        for y in range(h):
            for x in range(w):
                if x in (0,w-1) or y in (0,h-1):blocked.add((x,y));grounds[y*w+x]=wall
                elif x in (w//2,w//2-1) or y in (h//2,h//2-1):grounds[y*w+x]=road
                elif not outdoor and ground==323 and (x*31+y*17)%13==0:grounds[y*w+x]=327 if 327 in self.tiles else ground
        # Distinct chamber pillars preserve one connected component and all roads.
        seed=int(sha(mid)[:8],16)
        for n in range(6):
            x=4+(seed//(n+1)*7)%(w-9);y=4+(seed//(n+2)*11)%(h-9)
            if abs(x-w//2)<4 or abs(y-h//2)<4:continue
            for dx in range(2):
                for dy in range(2):blocked.add((x+dx,y+dy));grounds[(y+dy)*w+x+dx]=wall
        floor=Image.new('RGBA',(w*24,h*24))
        for cell,word in enumerate(grounds):floor.alpha_composite(self.tiles[word],(cell%w*24,cell//w*24))
        rel='gameplay/world/'+sha(mid)[:18]+'-floor.png';target=self.output/rel;target.parent.mkdir(parents=True,exist_ok=True);floor.save(target)
        m={'id':mid,'name':name,'width':w,'height':h,'tile_size':24,'map_version':'v2-g1-reconstructed-v1',
            'source_profile':'KR125_NATIVE_PIXELS_RECONSTRUCTED_KOREAN_REGION','source_geometry':None,
            'fact_status':'LEGACY_RECONSTRUCTED','geometry_note':'Korean guide region/name, deterministic reconstructed navigation; no claimed native server topology.',
            'ground_ids':grounds,'blocked':[list(p) for p in sorted(blocked,key=lambda p:(p[1],p[0]))],
            'objects':[],'exits':[],'spawns':[],'spawn_zones':[],'npcs':[],'landmarks':[],
            'return_city':CITY,'allow_return':True,'danger':'safe' if region=='city' else 'hunting',
            'recommended_level':level,'region':region,'floor_png':rel,'ground_layers':[{'path':rel,'x':0,'y':0}],
            'render_layers':'ground then foot-depth ordered structures/actors','collision_status':'RECONSTRUCTED_EXPLICIT_G1_GRID',
            'tile_bindings':{str(x):self.tile_sources[x] for x in set(grounds)}}
        if outdoor and region not in ('city','極地','극지방','일본'):
            source_objects=self.data['maps'][CITY]['objects']
            for x,y in ((5,4),(w-6,5),(6,h-6),(w-7,h-5)):
                for dx,native in ((-1,85),(0,86),(1,87)):
                    original=next((o for o in source_objects if o['native_id']==native),None)
                    if not original:continue
                    obj=deepcopy(original);obj.update(grid_x=x+dx,grid_y=y,x=(x+dx)*24,y=(y-original['height']+1)*24,depth_y=(y+1)*24)
                    m['objects'].append(obj)
                if [x,y] not in m['blocked']:m['blocked'].append([x,y])
        self.data['maps'][mid]=m
        self.adoption.append(annotate({},'maps',mid,{'name':name,'region':region,'width':w,'height':h,'source_tiles':sorted(set(grounds))},'map_navigation',
            rationale='Source region relationship reconstructed into linked bounded rooms with visible exits; native decoded ground pixels reused.'))
        return m

    def connect(self,a,b,direction='east',minimum_level=1):
        ma=self.data['maps'][a];mb=self.data['maps'][b]
        if direction=='east':pa=(int(ma['width'])-2,int(ma['height'])//2);pb=(1,int(mb['height'])//2);da='east';db='west';aa=(pa[0]-1,pa[1]);ab=(pb[0]+1,pb[1])
        elif direction=='north':pa=(int(ma['width'])//2,1);pb=(int(mb['width'])//2,int(mb['height'])-2);da='north';db='south';aa=(pa[0],pa[1]+1);ab=(pb[0],pb[1]-1)
        else:pa=(int(ma['width'])//2,int(ma['height'])-2);pb=(int(mb['width'])//2,1);da='south';db='north';aa=(pa[0],pa[1]-1);ab=(pb[0],pb[1]+1)
        # Multiple region entrances use separate tiles along the same border.
        def free_point(m,p,arrival):
            used={(e['x'],e['y']) for e in m['exits']}
            for offset in (0,3,-3,6,-6,9,-9,12,-12):
                q=(p[0],p[1]+offset) if direction=='east' else (p[0]+offset,p[1])
                arrive=(arrival[0],arrival[1]+offset) if direction=='east' else (arrival[0]+offset,arrival[1])
                if 1<=q[0]<m['width']-1 and 1<=q[1]<m['height']-1 and q not in used and list(q) not in m['blocked'] and list(arrive) not in m['blocked']:return q,arrive
            raise ValueError('No free region entrance '+m['id'])
        pa,aa=free_point(ma,pa,aa);pb,ab=free_point(mb,pb,ab)
        for m,p in ((ma,pa),(mb,pb)):
            if list(p) in m['blocked']:m['blocked'].remove(list(p))
        for m,p,target,arrival,direction in ((ma,pa,b,ab,da),(mb,pb,a,aa,db)):
            m['exits'].append({'id':ident('exit',m['id']+'>'+target),'x':p[0],'y':p[1],'to_map':target,
                'to_x':arrival[0],'to_y':arrival[1],'direction':direction,'minimum_level':1,'fact_status':'LEGACY_RECONSTRUCTED'})
            m['landmarks'].append({'name':self.data['maps'][target]['name'],'x':p[0],'y':p[1],'kind':'exit'})


def build_maps(data,regions,base,priority,output,adoption):
    builder=MapBuilder(data,base,priority,output,adoption)
    data['maps'][CITY]['name']='국내성'
    for d in ('north','east','south','west'):
        data['maps']['gp:map:'+d+'_field']['name']={'north':'국내성 북문 들판','south':'국내성 왕초보 사냥터','east':'국내성 동문 숲','west':'국내성 서문 숲'}[d]
    # A second city reuses the acquired native Korean architecture blueprint,
    # maintaining palace/streets/shops relationships while explicitly distinct
    # from a claim of exact original Buyeo server-cell reconstruction.
    buya=deepcopy(data['maps'][CITY]);buya.update(id=BUYA,name='부여성',exits=[],npcs=[],spawns=[],landmarks=deepcopy(data['maps'][CITY]['landmarks']),
        fact_status='LEGACY_RECONSTRUCTED',source_geometry=None,map_version='v2-g1-buya-from-korean-city-blueprint',return_city=BUYA)
    data['maps'][BUYA]=buya
    adoption.append(annotate({},'maps',BUYA,{'blueprint':CITY,'geometry':'existing Korean-native city architecture reused'},'map_navigation',
        rationale='Exact Buyeo native cell mapping unavailable; reuse existing Korean architecture and relative facility arrangement for a full playable second city.'))
    builder.connect('gp:map:north_field',BUYA,'north')
    hubs=[]
    for index,label in enumerate(('초급 사냥길','중급 사냥길','고급 사냥길','왕의 시련길')):
        mid=ident('map','travel-hub-'+str(index));builder.make(mid,label,'야외',1+index*25);hubs.append(mid)
    builder.connect('gp:map:east_field',hubs[0]);builder.connect(BUYA,hubs[1])
    builder.connect(hubs[0],hubs[1]);builder.connect(hubs[1],hubs[2]);builder.connect(hubs[2],hubs[3])
    region_maps={}
    for region,monsters in sorted(regions.items(),key=lambda r:(REGION_LEVELS.get(r[0],45),r[0])):
        if region in ('왕초보 사냥터','초보자 사냥터') and all(i in ['KRO-a278e4d3cd81','KRO-505b83a56a47'] for i in monsters):
            region_maps[region]=['gp:map:south_field'];continue
        levels=[data['monsters'][i]['level'] for i in monsters];level=min(levels)
        ordered=sorted(monsters,key=lambda i:(data['monsters'][i]['level'],data['monsters'][i]['name'],i))
        chunks=[ordered[i:i+8] for i in range(0,len(ordered),8)];mids=[]
        for floor,chunk in enumerate(chunks):
            mid=ident('map',region+':'+str(floor));name=region if len(chunks)==1 else region+' '+str(floor+1)+'층'
            m=builder.make(mid,name,region,level+floor*2);mids.append(mid)
            if floor:builder.connect(mids[-2],mid)
            for index,iid in enumerate(chunk):
                for copy in range(2):
                    x=6+(index%4)*8;y=7+(index//4)*13+copy*3
                    if [x,y] in m['blocked']:m['blocked'].remove([x,y])
                    m['spawns'].append({'id':ident('spawn',mid+':'+iid+':'+str(copy)),'monster_id':iid,'x':x,'y':y,
                        'respawn_seconds':float(data['monsters'][iid]['respawn_seconds']),'leash_radius':6,'roam_radius':2,'fact_status':'LEGACY_RECONSTRUCTED'})
        region_maps[region]=mids
        hub=hubs[min(3,level//25)]
        # Distribute branches north/south/east to keep portal cells distinct.
        branch=len(data['maps'][hub]['exits'])%3;builder.connect(hub,mids[0],('north','south','east')[branch])
    return builder,region_maps


def npc_position(data,map_id):
    m=data['maps'][map_id];used={(data['npcs'][i]['x'],data['npcs'][i]['y']) for i in m.get('npcs',[]) if i in data['npcs']}
    for y in (7,11,20,24,9,13):
        for x in range(5,m['width']-4,4):
            if (x,y) not in used and [x,y] not in m['blocked'] and all(abs(x-e['x'])+abs(y-e['y'])>2 for e in m['exits']):return x,y
    raise ValueError('NPC room full '+map_id)


def build_npcs(data,entities,builder,adoption):
    teachers=defaultdict(list);roles=defaultdict(list)
    job_tokens={'전사':('전사','warrior'),'도적':('도적','rogue'),'주술사':('주술사','mage'),'도사':('도사','poet')}
    for iid,(kind,row,_) in entities.items():
        if kind!='npcs':continue
        source=value_of(row);name=row['entity_name_ko'];loc=source.get('location_label_documented') or ''
        job=next((j for j in JOBS if j in loc),None)
        city=BUYA if '부여' in loc or name in ('차돌','소녀','몽이','연실이 연실언니 연실이모') else CITY
        if iid in data['npcs']:
            npc=data['npcs'][iid]
        else:
            mid=city;look='grocer'
            if job:
                key=job_tokens[job][1];look=key+'_master'
                if city==BUYA:
                    mid='g1:map:buya_'+key+'_guild'
                    if mid not in data['maps']:
                        builder.make(mid,'부여 '+job+'길드','city',w=20,h=18);builder.connect(city,mid,'south')
                else:mid='gp:map:'+key+'_guild'
            elif '주막' in loc:look='tavern'
            elif '대장간' in loc:look='forge'
            elif '갑옷' in loc or '포목' in loc:look='armorer'
            elif '혼례' in loc:look='poet_master'
            if city==BUYA and ('주막' in loc or '대장간' in loc):
                key='tavern' if '주막' in loc else 'forge';mid='g1:map:buya_'+key
                if mid not in data['maps']:
                    interior=deepcopy(data['maps']['gp:map:'+key]);interior.update(id=mid,name='부여 '+('주막' if key=='tavern' else '대장간'),exits=[],npcs=[],spawns=[],return_city=BUYA)
                    data['maps'][mid]=interior;builder.connect(city,mid,'south')
            x,y=npc_position(data,mid)
            npc={'id':iid,'name':name.split()[0],'map_id':mid,'x':x,'y':y,'look':look,'look_id':look,'direction':2,
                'services':[],'shop':{},'job':job,'dialogue':{'greeting':name.split()[0]+'입니다. 필요한 일과 물품을 확인하세요.','success':'완료했습니다.','failure':'조건과 물품을 확인하세요.','cancel':'다음에 다시 만나요.','revisit':'필요한 일이 있나요?'},
                'effective_field_status':{'position':'LEGACY_RECONSTRUCTED','look':'LEGACY_RECONSTRUCTED','dialogue':'LEGACY_RECONSTRUCTED'}}
            data['npcs'][iid]=npc;data['maps'][mid]['npcs'].append(iid)
        npc['source_value']=deepcopy(source);npc['source_id']=row.get('source_ids',[]);npc['source_pointer']=row.get('source_locator')
        if job:
            npc['services']=list(set(npc['services']+['change_job','teach_skill','advance','quest']));npc['job']=job
            teachers[job].append(iid);roles['guild'].append(iid)
        elif '대장간' in loc:
            npc['services']=list(set(npc['services']+['shop','repair','craft','quest']));roles['forge'].append(iid)
        elif '주막' in loc:
            npc['services']=list(set(npc['services']+['shop','quest','craft','storage']));roles['tavern'].append(iid)
        elif '갑옷' in loc or '포목' in loc:
            npc['services']=list(set(npc['services']+['shop','quest']));roles['tailor' if '포목' in loc else 'armorer'].append(iid)
        elif '백씨' in name:
            npc['services']=['shop','quest','craft'];roles['alchemy'].append(iid)
        else:
            # Two-player marriage/board games become useful offline errands,
            # explicitly adapted; no fictitious multiplayer service is enabled.
            npc['services']=['quest','craft'];roles['quest'].append(iid)
        adoption.append(annotate(row,'npcs',iid,{'map_id':npc['map_id'],'services':npc['services'],'position':[npc['x'],npc['y']]},'npc_service',
            rationale='Source name/location/merchant role reused. Online-only partner and board services adapted to offline delivery/travel commissions.'))
    roles['grocer']=[i for i,n in data['npcs'].items() if i=='gp:npc:grocer']
    roles['healer']=[i for i,n in data['npcs'].items() if i=='gp:npc:shrine_healer']
    for nid in roles['forge']:
        data['npcs'][nid]['services'].append('weapon_naming');data['npcs'][nid]['naming_cost']=20
    for nid in roles['guild']:
        data['npcs'][nid]['services'].append('training')
    return teachers,roles


def build_advancements(data,names,teachers,adoption):
    data['advancements']={}
    for title,(job,rank) in ADVANCEMENTS.items():
        iid=ident('advancement',title)
        material=ensure_item(data,names,['호박','진호박','용의비늘','화룡의비늘'][rank-1],adoption,'Source promotion materials adapted to offline advancement ladder.')
        previous=next((ident('advancement',t) for t,(j,r) in ADVANCEMENTS.items() if j==job and r==rank-1),None)
        data['advancements'][iid]={'id':iid,'name':title+' 승급','title':title,'job':job,'rank':rank,'previous_id':previous,
            'teacher_ids':teachers[job],'minimum_level':99,'money':rank*4000,'ingredients':{material:rank*3},
            'source_tier':'LEGACY_RECONSTRUCTED','rationale':'Original advancement names; source materials and single-player fee reconstructed.'}
        adoption.append(annotate({},'advancements',iid,{'title':title,'job':job,'rank':rank},'advance',[material,*teachers[job]]))


def build_rule_bindings(data,tables,teachers,roles,adoption):
    data['training_rules']={};data['rule_bindings']={}
    guilds=sum((teachers[j] for j in JOBS),[])
    for file in ('kr_official_facility_rules.jsonl','kr_official_flow.jsonl'):
        for row in tables[file]:
            if row.get('build_profile_id')!='KR_GUIDE_2001_SNAPSHOT':continue
            source=value_of(row);iid=row['content_id'];field=row.get('field_path','');name=row['entity_name_ko']
            if field.startswith('account.'):continue
            status='IMPLEMENTED';refs=[];rationale='Acquired source semantics connected to existing executable fields and NPC services.'
            if 'stat_purchase' in field or 'exchange_bands' in field:
                stat={'힘':'strength','민첩성':'dexterity','지력':'intelligence'}.get(source.get('stat'))
                if not stat:stat='hp_max' if 'hp_exchange' in field else 'mp_max'
                source_cost=source.get('xp_cost') or (source.get('bands') or [{}])[0].get('xp_cost',10000000)
                increase=source.get('increase') or source.get('increase_hp') or source.get('increase_mp') or 1
                jobs=source.get('job_group',JOBS)
                data['training_rules'][iid]={'id':iid,'name':name+' 수련','stat':stat,'minimum_level':90,
                    'xp_cost':max(1000,int(source_cost)//1000),'increase':int(increase),'cap':130 if stat in ('strength','dexterity','intelligence') else 10000,
                    'teacher_ids':sum((teachers[j] for j in jobs),[]),'source_value':deepcopy(source),'source_tier':'LEGACY_RECONSTRUCTED'}
                refs=['training_rules.'+iid];status='ADAPTED';rationale='Published Lv90 exchange retained; original XP costs divided by1000 for G1 XP scale. Original high-stat bands retained as source evidence; G1 uses first band below10000offlineHP/MP cap.'
            elif 'base_stat_limit' in field:refs=['config.base_stat_cap','training_rules'];status='ADAPTED';rationale='Source cap130 reused; base attributes start5 and grow by job level within cap, equipment bonuses additional.'
            elif name=='무한장':status='NON_G1_OFFLINE_REFERENCE';rationale='Player-versus-player service requires another player; excluded from authorized offline four-job G1.'
            elif name=='혼례식장':status='NON_G1_OFFLINE_REFERENCE';rationale='Spouse marriage and spouse teleport require another player; NPC remains a story commission provider, not claimed as original marriage implementation.'
            elif name=='전투윷방':refs=['npcs.KRO-NPC_SERVICE-cc6f3987e9e4b7','quests'];status='ADAPTED';rationale='Multiplayer board facility adapted to source-role monster-hunt commissions with explicit objectives/rewards. Paid randomized dice combat is not claimed as implemented.'
            elif field.startswith('creation.'):refs=['start','nation_starts','jobs'];status='ADAPTED';rationale='Offline name, appearance, guardian and nation creation; legacy online ID/password order excluded from offline character creation.'
            elif 'death_threshold' in field:refs=['config.death_inventory_loss','respawn']
            elif 'armor_order' in field:refs=['items'];status='ADAPTED';rationale='Source lower AC is converted to positive engine defense using abs(AC)*0.55; original signed AC preserved.'
            elif 'transport.' in field:
                refs=['skills','nation_gates','return_points'];status='ADAPTED' if 'target_level' in field else 'IMPLEMENTED'
                if status=='ADAPTED':rationale='Other-player teleport/summoning uses explicit home return/familiar offline substitution, retaining original lower-player-only source fact.'
            else:
                role='guild' if '길드' in name else 'tavern' if name=='주막' else 'forge' if name=='대장간' else 'armorer' if name=='갑옷상점' else 'tailor' if name=='포목상' else 'alchemy' if name=='시약상점' else 'healer'
                refs=['npcs.'+nid for nid in roles[role]]
                if name=='도사길드':status='ADAPTED';rationale='Source job change and skill learning connected; historical forget menu remains source evidence until explicit forgetting UI action.'
            binding={'content_id':iid,'name':name,'status':status,'runtime_refs':refs,'rationale':rationale,
                'source_value':deepcopy(source),'source_tier':'LEGACY_VERIFIED' if status=='IMPLEMENTED' else 'LEGACY_RECONSTRUCTED','source_ref':row.get('source_locator')}
            if '길드' in name:
                binding['excluded_optional_fields']={'forget_menu':'No skill-count cap in G1; learned skills remain usable, forgetting not required for progression.',
                    'personal_title':'Chosen advancement titles implemented; arbitrary title editing outside selected G1 core.'}
                binding['status']='ADAPTED'
            data['rule_bindings'][iid]=binding
            adoption.append(annotate(row,'rule_bindings',iid,binding,'rule_binding',refs,tier=binding['source_tier'],rationale=rationale))
    data['config']['base_stat_cap']=130
    data['nation_starts']={'고구려':{'map_id':'gp:map:tavern','x':10,'y':14},'부여':{'map_id':'g1:map:buya_tavern','x':10,'y':14}}
    data['return_points']=deepcopy(data['nation_starts'])
    data['nation_gates']={'고구려':deepcopy(data['gates']),'부여':{d:{**deepcopy(point),'map_id':BUYA} for d,point in data['gates'].items()}}


def skill_action(name,level,job):
    n=clean_name(name);power=int(16+level*3.1);mp=max(4,int(level*.7));common={'kind':'damage','delivery':'projectile','target':'monster','range':5,'power':power,'mp_cost':mp,'hp_cost':0,'cooldown':1.0,'duration':10.0}
    if n=='성황령':return {**common,'kind':'shrine','power':0,'mp_cost':0,'target':'self','range':0}
    if n=='물품감정':return {**common,'kind':'identify','power':0,'mp_cost':3,'target':'self','range':0}
    if n in ('비영사천문','귀환','출두'):return {**common,'kind':'return','power':0,'mp_cost':5,'target':'self','range':0,'offline_adaptation':'출두 targets the home city gates in the offline world.' if n=='출두' else None}
    if n=='부활':return {**common,'kind':'revive','target':'self','range':0,'power':250,'mp_cost':0,'cooldown':30.0}
    if any(x in n for x in ('기원','희원')):return {**common,'kind':'heal','target':'self','range':0,'power':int((25+level*8)*(1.3 if job=='도사' else 1)),'mp_cost':max(4,int(level*.45)),'cooldown':.65 if job=='도사' else 1.0}
    if n in ('해독','활력','시력회복','파혼술','퇴마주'):return {**common,'kind':'cleanse','target':'self','range':0,'power':0,'cleanse_statuses':{'해독':['poison'],'활력':['paralysis'],'시력회복':['silence'],'파혼술':['slow'],'퇴마주':['poison','silence']}[n]}
    if any(x in n for x in ('공력증','공력주입')):return {**common,'kind':'restore_mp','target':'self','range':0,'power':50+level*5,'mp_cost':0,'hp_cost':max(5,int(level*1.1)),'cooldown':4.0}
    if n=='노획':return {**common,'kind':'loot','target':'self','range':4,'power':0,'mp_cost':10}
    if n=='비영승보':return {**common,'kind':'blink','range':4,'power':0,'mp_cost':15,'cooldown':2.5}
    if n in ('소환','소혼강신','지영옥무'):return {**common,'kind':'summon','target':'self','range':5,'power':max(8,int(level*1.4)),'duration':25.0,'cooldown':30.0,'mp_cost':max(10,level)}
    if n in ('금수','야수','맹수','경수'):return {**common,'kind':'buff','target':'self','range':0,'power':0,'duration':30.0,'cooldown':3.0,'attack_bonus':max(4,level//3),'defense_bonus':max(1,level//10),'transform_family':{'금수':'돼지','경수':'토끼','야수':'여우','맹수':'곰'}[n]}
    if n in ('누리의빛','대지의빛','바다의빛'):return {**common,'kind':'identify','target':'self','range':0,'power':0,'mp_cost':5,'offline_adaptation':'Other-player inspection adapted to owned-item appraisal in the offline game.'}
    if n=='분신':return {**common,'kind':'buff','target':'self','range':0,'power':0,'attack_multiplier':2.0,'duration':20.0,'cooldown':5.0}
    if n=='기문방술':return {**common,'kind':'buff','target':'self','range':0,'power':0,'status':'stealth','duration':20.0,'cooldown':4.0,'defense_bonus':5}
    if n=='노도성황':return {**common,'kind':'status','status':'poison','power':50,'duration':10.0,'tick_interval':1.0,'cooldown':10.0,'offline_adaptation':'Published 3% recipient-max-HP per second is bounded to 50 damage ticks in G1 enemy HP scale.'}
    if n=='마기지체':return {**common,'kind':'buff','target':'self','range':0,'power':0,'defense_bonus':8,'reflect_fraction':.15,'duration':20.0,'cooldown':4.0,'offline_adaptation':'Curse retaliation adapted to damaging retaliation and body protection against offline enemies.'}
    if n in ('중독','마비','절망','혼돈','망각','부동력'):
        status={'중독':'poison','마비':'paralysis','절망':'silence','혼돈':'slow','망각':'slow','부동력':'paralysis'}[n]
        return {**common,'kind':'status','status':status,'power':max(4,level//3) if status=='poison' else 0,'duration':6.0 if status=='paralysis' else 12.0,'tick_interval':1.0,'cooldown':4.0}
    if n in ('저주','혼마술','무력화'):
        return {**common,'kind':'debuff','status':'silence' if n=='무력화' else 'slow','defense_bonus':-max(3,level//6),'move_multiplier':.6,'power':0,'duration':15.0,'cooldown':3.0}
    buffs=('이중공격','삼중공격','사중공격','오중공격','신의축복','신검합일','백호령','검신검귀','대력검신','무영보법','투명','무장','보호','차폐','대인차폐','금강불체','누리의힘','대지의힘','누리의빛','대지의빛','바다의빛','심안투영','진백호령','호체주술','반탄공','신령지익','파력무참')
    if n in buffs or '사자후' in n:
        b={**common,'kind':'buff','target':'self','range':0,'power':0,'duration':25.0,'cooldown':2.0,'attack_bonus':0,'defense_bonus':0,'attack_multiplier':1.0}
        if any(x in n for x in ('무장','보호','차폐','금강','호체','반탄')):b.update(defense_bonus=max(3,level//3),status='protection',damage_multiplier=.1 if n=='금강불체' else .5 if n=='보호' else .85)
        elif n in ('무영보법','투명','신령지익'):b.update(status='stealth' if n=='투명' else 'haste',move_multiplier=.69,duration=15.0)
        elif '중공격' in n:b['attack_multiplier']={'이':2.0,'삼':3.0,'사':4.0,'오':5.0}.get(n[0],2.0)
        else:b['attack_bonus']=max(3,level//3)
        if '사자후' in n:b.update(narration=name+'! 전투의 의지를 다집니다.',duration=35.0,attack_bonus=10)
        if n=='반탄공':b['reflect_fraction']=.25
        if n=='신령지익':b.update(status='protection',damage_multiplier=.5,defense_bonus=8)
        if n=='파력무참':b['attack_multiplier']=2.0
        return b
    if n in ('후면공격','측면공격','건곤대나이','동귀어진','필살검무','백호참','어검술','초혼비무','쇄혼비무','포효검황','백호검무','이기어검','기문방술','지영옥무','무형검'):
        common.update(delivery='area' if n in ('측면공격','쇄혼비무','포효검황','기문방술','지영옥무') else 'melee',range=2,radius=2,power=int(power*1.65),mp_cost=max(10,level//2),cooldown=2.0)
        if n in ('건곤대나이','동귀어진','필살검무'):common.update(hp_cost=max(5,level//2),power=int(power*2.0),cooldown=3.0)
    elif n=='흡성대법':common.update(delivery='melee',range=1,heal_fraction=.5,cooldown=2.0)
    elif n=='헬파이어':common.update(power=1250,mp_cost=180,cooldown=5.0)
    elif n in ('지진','삼매진화','지폭지술','노도성황') or '첨' in n:common.update(delivery='area',radius=2,range=5,power=int(power*.8),mp_cost=int(mp*1.25),cooldown=1.8)
    elif not any(x in n for x in ('화','자무','자영','자천','백열','백령','뢰','격참','최격')):
        raise ValueError('Unclassified source skill '+name)
    return common


def build_skills(data,entities,names,teachers,adoption,effect_rows):
    skills={}
    for iid,(kind,row,_) in entities.items():
        if kind!='skills':continue
        source=value_of(row);source_job=source['job'];job=ADVANCEMENTS.get(source_job,(source_job,0))[0];level=int(source['learn_level'])
        if job not in JOBS:job='COMMON_FOUR_STARTER_JOBS'
        ing={}
        for r in source.get('ingredients',[]):
            item=ensure_item(data,names,r['item_name_literal'],adoption,'Source skill learning ingredient; spelling aliases explicit, missing material reconstructed.')
            ing[item]=ing.get(item,0)+int(r['quantity'])
        spec=skill_action(row['entity_name_ko'],level,job)
        if spec.get('transform_family'):
            desired=spec.pop('transform_family');matches=[i for i,m in data['monsters'].items() if desired in m['name']]
            if not matches:raise ValueError('Transformation species unavailable '+desired)
            spec['form_monster_id']=matches[0]
        if spec['kind']=='summon':spec['monster_id']='KRO-a278e4d3cd81' # summon icon/companion explicitly adapted; no actor spawned as hostile.
        skill={'id':iid,'name':row['entity_name_ko'],'job':job,'learn_level':level,'learn_money':int((source.get('learn_money') or {}).get('value',3000 if source_job in ADVANCEMENTS else 0)),
            'ingredients':ing,'teacher_ids':sum((teachers[j] for j in JOBS),[]) if job=='COMMON_FOUR_STARTER_JOBS' else teachers[job],
            'guardian':source.get('guardian'),'source_value':deepcopy(source),'source_id':row.get('source_ids',[]),'source_pointer':row.get('source_locator'),
            'enabled':True,'windup':.18,'impact_delay':.32,'visual_duration':.7,'effect_id':13,'sound_id':17,
            'effective_field_status':{'learn_conditions':'LEGACY_VERIFIED','action':'LEGACY_RECONSTRUCTED','power_cost_timeline':'LEGACY_RECONSTRUCTED','visual_binding':'LEGACY_RECONSTRUCTED'},**spec}
        if source_job in ADVANCEMENTS:skill['required_advancement']=ident('advancement',source_job)
        if clean_name(row['entity_name_ko'])=='귀환':skill['return_to_inn']=True
        effect=next((r for r in effect_rows if r.get('parent_content_id')==iid),None)
        if effect:
            facts=effect.get('selected_original_value') or {}
            skill['source_effect_record']={'content_id':effect['content_id'],'source_ref':effect.get('source_locator'),'record_sha256':sha(effect),'selected_fields':deepcopy(facts)}
            heal=facts.get('healing.hp_amount')
            if skill['kind']=='heal' and isinstance(heal,dict) and numeric(heal.get('value'))>0:skill['power']=int(heal['value'])
            guardian=facts.get('damage.guardian_element')
            if isinstance(guardian,dict):skill['element']=guardian.get('element')
            skill['effect_field_adoption']={field:{'status':'ADAPTED' if any(x in field for x in ('other_player','multiple_people','lower_player','group','cost.','current_or_max','stat_scaling','all_magic','barrier','reflection','incoming_nullified','mutual_immobilization','periodic_hp_loss')) else 'USED_OR_SCALED',
                'runtime_action':skill['kind'],'rationale':'Source semantic family retained; numeric, target, collision and scaling details are bounded to the offline executor. Explicit source field remains available alongside effective values.'} for field in facts}
        # Keep familiar P3 effects/sounds on known IDs, and diversify families.
        skill['effect_id']={'heal':16,'cleanse':19,'buff':20,'status':14,'debuff':14,'shrine':14,'return':13,'summon':19,'revive':16}.get(spec['kind'],13)
        skill['sound_id']={'heal':5,'cleanse':6,'buff':7,'status':18,'debuff':19,'shrine':9,'return':8,'summon':20,'revive':5}.get(spec['kind'],17)
        if skill.get('element'):skill['effect_id']={'fire':13,'water':14,'earth':16,'lightning':19,'wind_lightning':19}.get(skill['element'],skill['effect_id'])
        if iid in data['skills']:
            for field in ('mp_cost','power','range','cooldown','windup','impact_delay','effect_id','sound_id'):
                if field in data['skills'][iid]:skill[field]=data['skills'][iid][field]
        from skill_semantics import adopt_skill_effects
        skill=adopt_skill_effects(skill,effect_rows,data)
        skills[iid]=skill
        adoption.append(annotate(row,'skills',iid,{k:skill.get(k) for k in ('job','kind','delivery','status','power','learn_level','required_advancement')},spec['kind'],[*ing,*skill['teacher_ids']],
            rationale='Source learning requirements retained. Semantic action family bound to executor; online player teleport/shout/summon adapted to offline home-gates, morale and companion respectively.'))
    data['skills']=skills


def build_economy_quests_crafts(data,entities,names,teachers,roles,region_maps,adoption):
    data['quests']={};data['recipes']={}
    for item in data['items'].values():item.setdefault('acquisition_paths',[]);item.setdefault('function_paths',[])
    # Source merchant roles stay separate: weapon, male armour, female tailor,
    # alchemy, inn refreshments. Every stock is a deliberate set, never global.
    role_for=lambda i:'forge' if i['kind']=='weapon' or i.get('slot')=='shield' else 'tailor' if i.get('slot')=='cape' or i.get('source_value',{}) and i['source_value'].get('gender_documented')=='여자' else 'armorer' if i.get('slot') else 'alchemy' if '시약' in i['name'] else 'tavern' if i['kind']=='consumable' else None
    prior_stock={iid:nid for nid,npc in data['npcs'].items() for iid,price in npc.get('shop',{}).items() if price.get('buy_price') is not None}
    for nid in data['npcs']:
        if data['npcs'][nid].get('shop'):data['npcs'][nid]['shop']={}
    for iid,item in data['items'].items():
        role=role_for(item)
        if not role or not roles[role]:continue
        sellers=roles[role]
        documented=[nid for nid in sellers if clean_name(item['name']) in [clean_name(n) for n in data['npcs'][nid].get('source_value',{}).get('sale_tokens',[])]]
        chosen=prior_stock.get(iid) or (documented[0] if documented else sellers[int(sha(iid)[:8],16)%len(sellers)])
        price=item.get('buy_price');price=20 if price is None else max(1,int(price))
        data['npcs'][chosen]['shop'][iid]={'buy_price':price,'sell_price':max(1,price//4)}
        item['buy_price']=price;item['sell_price']=max(1,price//4)
        item['acquisition_paths'].append({'kind':'shop','npc_id':chosen,'price':price})
    # Existing starter buyback remains at market, alongside trophies.
    grocer=roles['grocer'][0];data['npcs'][grocer]['shop']={}
    if 'quest' not in data['npcs'][grocer]['services']:data['npcs'][grocer]['services'].append('quest')
    for iid,item in data['items'].items():
        if item['kind']=='material' or iid in ('KRO-ITEM-1ec5d43f9e157e','gp:item:rabbit_meat'):
            data['npcs'][grocer]['shop'][iid]={'buy_price':None,'sell_price':max(1,int(item.get('sell_price') or 5))}
    # Bind all named drops and reconstruct unbound materials to a tier-appropriate
    # local enemy. No material exists only in a grant/debug menu.
    monsters=sorted(data['monsters'],key=lambda i:(data['monsters'][i].get('level',1),i))
    dropped=set()
    for mid,m in data['monsters'].items():
        for d in m['drops']:
            dropped.add(d['item_id']);data['items'][d['item_id']]['acquisition_paths'].append({'kind':'drop','monster_id':mid,'chance':d['chance']})
    for iid,item in data['items'].items():
        if item['acquisition_paths'] or iid in {r['item_id'] for r in data['start']['starter_items']}:continue
        name=item['name'];level=max(5,min(95,int(item.get('required_level',0)) or 10+int(sha(iid)[:2],16)%80))
        for token,desired in [('뱀',12),('곰',18),('여우',24),('호랑',20),('자호',30),('호박',65),('진호박',85),('얼음',82),('룡',94),('괘',94),('옥',92)]:
            if token in name:level=desired
        candidate=min(monsters,key=lambda m:(abs(data['monsters'][m].get('level',1)-level),sha(m+iid)))
        chance=.6 if level<40 else .35
        data['monsters'][candidate]['drops'].append({'item_id':iid,'chance':chance,'quantity_min':1,'quantity_max':2,'source_tier':'LEGACY_RECONSTRUCTED'})
        item['acquisition_paths'].append({'kind':'drop','monster_id':candidate,'chance':chance})
    # Real source recipes get explicit deterministic offline fee/chance policy.
    for iid,(kind,row,_) in entities.items():
        if kind!='recipes':continue
        v=value_of(row);result=v.get('result_name')
        if not result:result='녹호박장삼'
        output=ensure_item(data,names,result,adoption,'Documented craft result or limited clothing material reconstructed as offline craft.')
        mats=v.get('materials') or [{'item_name':v.get('material_item_name','녹호박'),'quantity':3}]
        ingredients={ensure_item(data,names,m['item_name'],adoption,'Documented source craft ingredient.'):max(1,int(m.get('quantity') or 1)) for m in mats}
        nid=roles['forge'][0] if any(t in (v.get('npc_location_description') or '') for t in ('대장간','극지방')) else (roles['tavern'][-1] if result in ('과일화채','깨끗한얼음','말린지네') else roles['quest'][0])
        recipe={'id':iid,'name':result+' 만들기','npc_id':nid,'minimum_level':1,'ingredients':ingredients,'money':max(0,int(v.get('money_cost') or 10)),
            'results':{output:max(1,int(v.get('quantity_result') or 1))},'success_probability':1.0,'source_value':deepcopy(v),
            'source_tier':'LEGACY_RECONSTRUCTED','rationale':'Known recipe materials reused; undocumented quantities=1, fee=10, deterministic success and one result are explicit offline reconstruction.'}
        data['recipes'][iid]=recipe
        if 'craft' not in data['npcs'][nid]['services']:data['npcs'][nid]['services'].append('craft')
        for mat in ingredients:data['items'][mat].setdefault('function_paths',[]).append({'kind':'craft_material','recipe_id':iid})
        data['items'][output].setdefault('acquisition_paths',[]).append({'kind':'craft','recipe_id':iid})
        adoption.append(annotate(row,'recipes',iid,recipe,'craft',list(ingredients)+[nid,output]))
    # Start supplies introduce each job naturally; all professions have a mid and
    # late hunting commission. Long progression is not represented as tested.
    acorn=names['도토리'][0];meat=names['토끼고기'][0]
    beginner=ident('quest','beginner-supplies')
    data['quests'][beginner]={'id':beginner,'name':'첫 사냥의 준비','npc_id':grocer,'minimum_level':1,'required_job':'any',
        'objectives':[{'kind':'collect','id':acorn,'count':4},{'kind':'collect','id':meat,'count':4}],
        'rewards':{'xp':80,'money':80,'items':{}},'source_tier':'LEGACY_RECONSTRUCTED','description':'동문이나 남문 초보 사냥터에서 도토리와 토끼고기를 모아 오세요.'}
    used=set()
    for skill in data['skills'].values():
        for mat in skill['ingredients']:data['items'][mat].setdefault('function_paths',[]).append({'kind':'skill_learning','skill_id':skill['id']});used.add(mat)
    for adv in data['advancements'].values():
        for mat in adv['ingredients']:data['items'][mat].setdefault('function_paths',[]).append({'kind':'advancement_material','advancement_id':adv['id']});used.add(mat)
    for iid,item in data['items'].items():
        if item.get('function_paths'):continue
        # Source quest/key/trophy fragments are useful hand-ins. Groups of three
        # make commissions, rather than one artificial quest per source row.
        used.add(iid)
    unserved=[i for i,item in data['items'].items() if not item.get('function_paths')]
    quest_npcs=roles['quest']+roles['tavern']+roles['forge']
    for group_index,start in enumerate(range(0,len(unserved),3)):
        group=unserved[start:start+3];nid=quest_npcs[group_index%len(quest_npcs)];qid=ident('quest','material-commission:'+':'.join(group))
        quest={'id':qid,'name':data['npcs'][nid]['name']+'의 수집 의뢰 '+str(group_index+1),'npc_id':nid,'minimum_level':1,'required_job':'any',
            'objectives':[{'kind':'collect','id':i,'count':2} for i in group],
            'rewards':{'xp':120+group_index*30,'money':100+group_index*20,'items':{}},
            'description':' · '.join(data['items'][i]['name']+' 2개' for i in group)+'를 구해 주세요.','source_tier':'LEGACY_RECONSTRUCTED',
            'rationale':'Unresolved Korean quest/key/trophy item purposes adapted to actual offline acquisition and hand-in paths.'}
        data['quests'][qid]=quest
        for i in group:data['items'][i]['function_paths'].append({'kind':'quest_handin','quest_id':qid})
    # Every NPC has a real source-role service or a meaningful travel/hunt quest.
    for index,(nid,npc) in enumerate(data['npcs'].items()):
        if 'quest' not in npc['services']:continue
        if any(q['npc_id']==nid for q in data['quests'].values()):continue
        target=monsters[min(len(monsters)-1,8+index*7)]
        qid=ident('quest','hunt:'+nid)
        data['quests'][qid]={'id':qid,'name':npc['name']+'의 사냥 의뢰','npc_id':nid,'minimum_level':1,'required_job':npc.get('job') or 'any',
            'objectives':[{'kind':'kill','id':target,'count':5}],
            'rewards':{'xp':max(60,data['monsters'][target]['xp']*4),'money':max(50,data['monsters'][target]['level']*15),'items':{}},
            'description':data['monsters'][target]['name']+' 5마리를 처치해 주세요.','source_tier':'LEGACY_RECONSTRUCTED'}
    # Late recipe inputs appended by recipe compilation require drop paths too.
    for iid,item in data['items'].items():
        item.setdefault('function_paths',[]);item.setdefault('acquisition_paths',[])
        if not item['acquisition_paths']:
            candidate=monsters[int(sha(iid)[:8],16)%len(monsters)]
            data['monsters'][candidate]['drops'].append({'item_id':iid,'chance':.5,'quantity_min':1,'quantity_max':1})
            item['acquisition_paths'].append({'kind':'drop','monster_id':candidate,'chance':.5})
        if item['kind'] in ('weapon','armor') and not any(p['kind']=='equip' for p in item['function_paths']):item['function_paths'].append({'kind':'equip','slot':item['slot']})
    for qid,q in data['quests'].items():
        adoption.append(annotate({},'quests',qid,{'name':q['name'],'objectives':q['objectives'],'rewards':q['rewards']},'quest',[q['npc_id']]+[x['id'] for x in q['objectives']]))


def build_native_assets(data,base,priority,p15,dat,reader,output,selection,adoption,weapon_selection=None):
    args=argparse.Namespace(output=output/'gameplay-assets',reader=reader,dat=dat,p15=p15,runtime=priority)
    src=gameplay_assets.Sources(args)
    actor_defs=json.loads((base/'gameplay-assets/actors.json').read_text())
    # Sources writes only newly selected private PNGs; earlier generation is copied.
    bindings=json.loads(selection.read_text()) if selection else {}
    direct=bindings.get('entity_bindings',{})
    families=bindings.get('families',{})
    weapon_bindings=json.loads(weapon_selection.read_text()) if weapon_selection else {}
    def part_for(iid,monster):
        entry=direct.get(iid)
        if isinstance(entry,int):return entry,'visual inspection'
        if isinstance(entry,dict):return int(entry['part_id']),entry.get('reason','visual inspection')
        for family,definition in families.items():
            if any(k in monster['name'] for k in definition.get('keywords',[])):return int(definition['part_id']),definition.get('rationale',family)
        raise ValueError('Monster visual binding required '+iid+' '+monster['name'])
    chosen={}
    for iid,monster in data['monsters'].items():
        if iid in ('KRO-a278e4d3cd81','KRO-505b83a56a47'):
            continue
        part,reason=part_for(iid,monster);look='g1_native_monster_'+str(part)
        monster['look']=look;monster['look_id']=look;chosen[look]={'part_id':part}
        monster['visual_binding']={'source_tier':'LEGACY_RECONSTRUCTED','source_ref':'KR491:monster:'+str(part),'rationale':reason,'exact_historical_entity_binding':False}
    icon_manifest=json.loads((priority/'icons/icons.json').read_text())
    icons_by_name=defaultdict(list)
    for entry in icon_manifest['entries']:icons_by_name[clean_name(entry['name_ko'])].append(entry)
    # Category native icons are visually chosen in the B1 sheet, never random.
    icon_parts=bindings.get('icon_categories',{'weapon':4,'armor':23,'helmet':49,'ring':59,'shield':60,'cape':23,'boots':23,'consumable':83,'material':90})
    config={'humanoids':{},'monsters':chosen,'icons':{}}
    weapon_runtime={}
    for iid,item in data['items'].items():
        if item.get('slot')!='weapon' or iid in actor_defs.get('item_equipment_graphics',{}):continue
        weapon=weapon_bindings.get('entity_bindings',{}).get(iid)
        if not weapon:
            weapon={'style':'sword','part_id':1,'icon_part_id':1,'rationale':'Source named missing weapon reconstructed with a visually selected native sword silhouette.'}
        style=weapon['style'];look='g1_player_'+style;armored='g1_player_armored_'+style
        for key,body,head in ((look,0,0),(look+'_alt',1,1),(armored,2,0),(armored+'_alt',3,1)):
            config['humanoids'][key]={'body':body,'head':head,'sword':int(weapon['part_id'])}
        weapon_runtime[iid]={'player_look':look,'armored_player_look':armored,'source_tier':'LEGACY_RECONSTRUCTED',
            'source_ref':'KR491:sword:'+str(weapon['part_id']),'rationale':weapon['rationale'],'style':style}
        item['weapon_visual_binding']=deepcopy(weapon_runtime[iid])
    for iid,item in data['items'].items():
        if iid in actor_defs['icons']:continue
        matches=icons_by_name.get(clean_name(item['name']),[])
        if matches:
            match=matches[0];image=Image.open(priority/'icons'/match['image_path']).convert('RGBA')
            frame=src.write_frame(image,[-image.width//2,-image.height],[{'official_binding_id':match['id'],'source_sha256':match['source_sha256']}])
            frame['fact_status']=match['fact_status'];actor_defs['icons'][iid]=frame
            item['icon_binding']={'source_tier':'LEGACY_VERIFIED','source_ref':match['id'],'rationale':'Exact Korean item-name binding from acquired icon table.'}
        else:
            category=item.get('slot',item['kind'])
            if item.get('action_type')=='return':category='scroll'
            elif any(x in item['name'] for x in ('호박','옥','여의주','수정','구슬')):category='jewel'
            elif '고기' in item['name']:category='meat'
            weapon=weapon_bindings.get('entity_bindings',{}).get(iid,{})
            part=int(weapon.get('icon_part_id',icon_parts.get(category,icon_parts['material'])))
            # Reconstruct category icon only when source name-to-native mapping is
            # unknown; explicit provenance prevents false exactness claims.
            config['icons'][iid]={'part_id':part}
            item['icon_binding']={'source_tier':'LEGACY_RECONSTRUCTED','source_ref':'KR491:item:'+str(part),'rationale':'Visually selected native category icon. Exact historical name/frame binding unavailable.'}
    gameplay_assets.build(src,config)
    newly=json.loads((output/'gameplay-assets/actors.json').read_text())
    actor_defs['looks'].update(newly['looks']);actor_defs['icons'].update(newly['icons'])
    actor_defs['generation']=GENERATION;actor_defs['source']['v2_selected_assets']=newly['source']
    actor_defs['item_equipment_graphics'].update(weapon_runtime)
    write(output/'gameplay-assets/actors.json',actor_defs)
    return {'decoded_frames':len(src.decoded),'native_monster_groups':len(chosen),'source_members':src.used}


def validate(data,root,selected):
    checks=[]
    def check(name,good,detail=None):
        checks.append({'id':name,'status':'PASS' if good else 'FAIL','details':detail})
        if not good:raise ValueError('G1 validation '+name+': '+str(detail))
    required=defaultdict(set)
    for iid,(kind,_,_) in selected.items():required[kind].add(iid)
    for kind,ids in required.items():check('frozen_source_'+kind,ids<=set(data[kind]),sorted(ids-set(data[kind])))
    reach={};world={data['start']['map_id']};queue=deque(world)
    while queue:
        mid=queue.popleft()
        for e in data['maps'][mid]['exits']:
            if e['to_map'] not in world:world.add(e['to_map']);queue.append(e['to_map'])
    check('all_maps_in_start_graph',world==set(data['maps']),sorted(set(data['maps'])-world))
    for mid,m in data['maps'].items():
        blocked={tuple(p) for p in m['blocked']};w,h=m['width'],m['height']
        start=next(((x,y) for y in range(h) for x in range(w) if (x,y) not in blocked),None)
        seen={start};queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for dx,dy in ((0,-1),(1,0),(0,1),(-1,0)):
                p=x+dx,y+dy
                if 0<=p[0]<w and 0<=p[1]<h and p not in blocked and p not in seen:seen.add(p);queue.append(p)
        check(mid+':walkable_component',len(seen)==w*h-len(blocked),{'reachable':len(seen),'walkable':w*h-len(blocked)})
        reach[mid]=seen
        for e in m['exits']:
            target=data['maps'].get(e['to_map'],{})
            check(e['id']+':exit', (e['x'],e['y']) in seen and target and [e['to_x'],e['to_y']] not in target['blocked'])
        for s in m['spawns']:check(s['id']+':spawn',s['monster_id'] in data['monsters'] and (s['x'],s['y']) in seen)
        check(mid+':floor_exists',(root/m['floor_png']).is_file())
    spawned={s['monster_id'] for m in data['maps'].values() for s in m['spawns']}
    check('all_monsters_spawn',spawned==set(data['monsters']),sorted(set(data['monsters'])-spawned))
    for nid,n in data['npcs'].items():
        check(nid+':reachable_npc',n['map_id'] in world and (n['x'],n['y']) in reach[n['map_id']])
        check(nid+':function',bool(n['services']))
        for iid,p in n.get('shop',{}).items():check(nid+':'+iid+':stock',iid in data['items'] and (p['buy_price'] is None or p['sell_price'] is None or p['buy_price']>=p['sell_price']>=0))
    for iid,item in data['items'].items():
        check(iid+':acquisition',bool(item.get('acquisition_paths')))
        check(iid+':function',bool(item.get('function_paths')))
    for iid,s in data['skills'].items():
        check(iid+':supported_action',s['kind'] in ACTION_KINDS)
        check(iid+':learning',1<=s['learn_level']<=99 and bool(s['teacher_ids']) and set(s['ingredients'])<=set(data['items']) and set(s['teacher_ids'])<=set(data['npcs']))
        if s.get('required_advancement'):check(iid+':advancement',s['required_advancement'] in data['advancements'])
    actors=json.loads((root/'gameplay-assets/actors.json').read_text())
    check('all_item_icons',set(data['items'])<=set(actors['icons']))
    check('all_actor_looks',{r.get('look_id',r.get('look')) for k in ('monsters','npcs') for r in data[k].values()}<=set(actors['looks']))
    check('four_jobs_99',set(JOBS)<=set(data['jobs']) and len(data['xp_thresholds'])==99 and data['config']['level_cap']==99)
    return {'status':'PASS','scope':'compiled static ID/reference/BFS/acquisition/function/native PNG validation; runtime and natural levelling NOT_RUN','count':len(checks),'failed':0,'checks':checks}


def freeze_runtime(data,output,base,adoption,static,asset_receipt):
    for mid,m in data['maps'].items():m['geometry_sha256']=sha({k:m[k] for k in ('width','height','blocked','exits')})
    old=json.loads((base/'gameplay_content.json').read_text())
    data['accepted_compatibility']=[{'profile':old['profile'],'compatibility':deepcopy(old['compatibility']),'manifest_sha256':old['manifest_sha256']}]
    data['compatibility']={'schema':str(old['compatibility']['schema']),
        'rules':sha({k:data[k] for k in ('items','skills','xp_thresholds','config','quests','recipes','advancements')}),
        'idset':sha({k:sorted(data[k]) for k in ('maps','items','skills','npcs','monsters','jobs')}),
        'map_geometry':sha({i:r['geometry_sha256'] for i,r in data['maps'].items()})}
    data['manifest_sha256']=sha({'compatibility':data['compatibility'],'profile':data['profile'],'compiler':sha(Path(__file__))})
    data['generation']=GENERATION;data['world_profile']='KR_RESOURCE_FIRST_G1_RECONSTRUCTED'
    data['compiler_provenance']={name:sha(HERE/name) for name in ('build_generation.py','generation_contract.py','skill_semantics.py','effect_assets.py')}
    data['deferred']={'higher_skill_ids':[],'unplaced_npc_contract_ids':[],'historical_exact_geometry':'Not required; adopted reconstructed geography.'}
    write(output/'gameplay_content.json',data)
    for a in adoption:a['status']='COMPILED_STATIC_VALIDATED';a['evidence']['validation_sha256']=sha(static)
    write(output/'G1_ADOPTION.json',{'schema':'baram.g1.adoption/1','generation':GENERATION,'entries':adoption,'source_ladder':['LEGACY_VERIFIED','LEGACY_RECONSTRUCTED','MODERN_BARAM_ADAPTED','OTHER_GAME_ADAPTED','INFERRED']})
    write(output/'G1_VALIDATION.json',static)
    write(output/'G1_ASSET_RECEIPT.json',asset_receipt)
    source=json.loads((output/'kr491/kr491_runtime.json').read_text())
    # Baseline closure has the effects used by P3; G1 uses the same native IDs.
    for s in data['skills'].values():
        if int(s['effect_id']) not in {int(x['id']) for x in source['effects']}:raise ValueError('Missing effect '+str(s['effect_id']))
        if int(s['sound_id']) not in {int(Path(x['member']).stem) for x in source['sounds']}:raise ValueError('Missing sound '+str(s['sound_id']))
    png=wav=0
    for p in sorted(output.rglob('*')):
        if p.suffix=='.png':
            with Image.open(p) as im:im.verify()
            png+=1
        if p.suffix=='.wav':
            with wave.open(str(p)) as f:
                if not f.readframes(f.getnframes()):raise ValueError('Empty waveform '+str(p))
            wav+=1
    paths=[{'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.rglob('*')) if p.is_file() and p.name!='runtime.json']
    manifest={'schema':'baram.work.p3.runtime/1','generation':GENERATION,'profile':data['profile'],'world_profile':data['world_profile'],
        'files':paths,'private_only':True,'compatibility':data['compatibility'],'parent_generation':'WORK-GAMEPLAY-GEN001',
        'parent_runtime_sha256':sha(base/'runtime.json'),'compiler_sha256':sha(Path(__file__)),
        'compiler_dependencies':deepcopy(data['compiler_provenance']),
        'input_definitions_sha256':sha(output/'gameplay_content.json'),'fingerprint':sha(paths),
        'dependency_closure':{'maps':len(data['maps']),'png_files_verified':png,'wav_files_decoded':wav},
        'excluded':['source archives','DAT','reference contact sheets','user saves','keys','source-only catalogs']}
    write(output/'runtime.json',manifest)
    return {'status':'COMPILED_STATICALLY_VALIDATED_RUNTIME_NOT_YET_PLAY_TESTED','output':str(output),'runtime_sha256':sha(output/'runtime.json'),
        'counts':{k:len(data[k]) for k in ('maps','monsters','items','npcs','skills','quests','recipes','advancements')},'validation_checks':static['count'],'png':png,'wav':wav}


def compile_generation(args):
    if args.output.exists():raise ValueError('Fresh output required; prior generations immutable.')
    repo=HERE.parents[2]
    if args.output.resolve()==repo or repo in args.output.resolve().parents:raise ValueError('Private runtime must stay outside git checkout.')
    tables=load_tables(args.normalized);data=json.loads((args.base/'gameplay_content.json').read_text())
    entities,decisions,aliases=source_entities(tables,data)
    shutil.copytree(args.base,args.output)
    adoption=[];names=build_items(data,entities,adoption)
    regions=build_monsters(data,entities,names,adoption)
    builder,region_maps=build_maps(data,regions,args.base,args.priority,args.output,adoption)
    teachers,roles=build_npcs(data,entities,builder,adoption)
    build_advancements(data,names,teachers,adoption)
    build_skills(data,entities,names,teachers,adoption,tables['kr_official_skill_effects.jsonl'])
    from effect_assets import bind_effect_assets
    effect_assets=bind_effect_assets(data,args.normalized,args.priority,args.output)
    build_economy_quests_crafts(data,entities,names,teachers,roles,region_maps,adoption)
    build_rule_bindings(data,tables,teachers,roles,adoption)
    data['xp_thresholds']=[0]
    for level in range(1,99):data['xp_thresholds'].append(data['xp_thresholds'][-1]+int(12+level*level*.85+level*7))
    data['config'].update(level_cap=99,inventory_capacity=120,regen_hp=3,regen_mp=8,heal_price=0,default_return_direction='east')
    data['job_growth']={'commoner':{'hp_per_level':8,'mp_per_level':5,'attack_per_level':.5},
        '전사':{'hp_per_level':18,'mp_per_level':5,'attack_per_level':1.5},'도적':{'hp_per_level':13,'mp_per_level':7,'attack_per_level':1.3},
        '주술사':{'hp_per_level':10,'mp_per_level':18,'attack_per_level':.6},'도사':{'hp_per_level':12,'mp_per_level':16,'attack_per_level':.7}}
    data['progression_model']={'source_tier':'LEGACY_RECONSTRUCTED','xp_formula':'level increment = round_down(12+0.85L²+7L)',
        'monster_hp_formula':'20+6L+0.11L²','monster_xp_formula':'8+0.22L² (baseline novice species source XP retained)',
        'natural_1_99_all_jobs':'NOT_RUN','region_maps':region_maps,'economic_policy':'Role-specific merchants; buy >= 4*sell, all reagents have drops and consuming functions.'}
    assets=build_native_assets(data,args.base,args.priority,args.p15,args.dat,args.reader,args.output,args.visual_selection,adoption,args.weapon_selection)
    assets['effect_bindings']=effect_assets
    static=validate(data,args.output,entities)
    return freeze_runtime(data,args.output,args.base,adoption,static,assets)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('base','priority','normalized','p15','dat','reader','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--visual-selection',type=Path)
    p.add_argument('--weapon-selection',type=Path)
    a=p.parse_args();print(json.dumps(compile_generation(a),ensure_ascii=False))


if __name__=='__main__':main()
