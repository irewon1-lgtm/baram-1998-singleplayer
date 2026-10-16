#!/usr/bin/env python3
"""Compile a small P3 Korean-source world and executable definitions.

Original published fields, source-resource pixels, and reconstructed geography /
balance are separate. The unknown 49 storage chunk topology is never asserted.
Writes only a fresh sparse gameplay overlay, not original / GEN002 inputs.
"""
from __future__ import annotations
import argparse
from collections import deque,Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from PIL import Image
import kr125_map
from priority_maps import save_png, write, READER_SHA256

PROFILE='KR_GUIDE_2001_WORKING_PROVISIONAL'
CITY='gp:map:domestic_city'
ACORN='KRO-ITEM-1ec5d43f9e157e'
MEAT='gp:item:rabbit_meat'
WOOD='KRO-ITEM-be19434c5b2ee6'
SWORD='KRO-ITEM-89a184f51172c1'
WINE='KRO-ITEM-29c43190955429'
CLOTHES='gp:item:starter_clothes'
ARMOR='gp:item:novice_armor'
SQUIRREL='KRO-a278e4d3cd81'
RABBIT='KRO-505b83a56a47'
MASTERS={'전사':('KRO-NPC_SERVICE-d276c50324a779','태백','warrior'),
         '도적':('KRO-NPC_SERVICE-09df887c0d7548','마로','rogue'),
         '주술사':('KRO-NPC_SERVICE-b1176f92bc9e27','해두','mage'),
         '도사':('KRO-NPC_SERVICE-1fbe93b95e5d54','진선','poet')}

def digest(data):
    if isinstance(data,Path):data=data.read_bytes()
    elif not isinstance(data,bytes):data=json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()

def records(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def compile_content(base:Path,rules_path:Path,normalized:Path,maps_path:Path,client_zip:Path,reader_path:Path,output:Path):
    if output.exists():raise ValueError('Fresh output generation required; existing input remains immutable')
    rules=json.loads(rules_path.read_text());assert rules['profile']==PROFILE
    official_items=records(normalized/'kr_official_items.jsonl')
    official_core=records(normalized/'kr_official_core.jsonl')
    official_maps=records(normalized/'kr_official_full_maps.jsonl')
    selected_items={r['entity_name_ko']:r for r in official_items if r.get('build_profile_id')=='KR_GUIDE_2001_SNAPSHOT'}
    selected_monsters={r['entity_name_ko']:r for r in official_core if r.get('build_profile_id')=='KR_GUIDE_2001_SNAPSHOT' and r['record_type']=='monster'}
    output.mkdir(parents=True);world_dir=output/'gameplay/world';world_dir.mkdir(parents=True)
    (world_dir/'objects').mkdir()
    if digest(reader_path)!=READER_SHA256:raise ValueError('Pinned reviewed DAT/PAL reader hash mismatch')
    import importlib.util,sys
    spec=importlib.util.spec_from_file_location('gameplay_legacy_assets',reader_path);reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
    if digest(client_zip)!=kr125_map.CLIENT_SHA256:raise ValueError('KR125 source hash mismatch')
    with zipfile.ZipFile(client_zip) as z:
        entries=reader.dat_entries(z.read('winbaram.dat'))
    palette=reader.read_palettes(entries['windland.pal'][2])[0].colors
    counts={g:len(entries[f'tile{g.lower()}.bmp'][2])//576 for g in 'ABC'}
    source_map=json.loads((maps_path/'map-0-chunk-15.json').read_text())
    source_ground=source_map['collisions']['ground_ids'];source_objects=source_map['objects']
    tile_cache={};used_objects=set();bindings=[]
    def tile(word):
        if word not in tile_cache:
            g,i=kr125_map.ground_tile(word,counts)
            data=entries[f'tile{g.lower()}.bmp'][2][i*576:(i+1)*576]
            tile_cache[word]=Image.frombytes('RGBA',(24,24),bytes(c for v in data for c in (*palette[v],255)))
        return tile_cache[word]
    def copied_object(obj):
        n=obj['native_id'];relative=f'gameplay/world/objects/object-{n}.png'
        if n not in used_objects:
            src=maps_path/obj['frame_png']
            with Image.open(src) as im:im.verify()
            shutil.copyfile(src,output/relative)
            used_objects.add(n)
        return relative
    native_object_meta={r['native_id']:r for r in source_objects}
    def world(mid,name,w=64,h=64,ground=52):
        return {'id':mid,'name':name,'width':w,'height':h,'tile_size':24,'map_version':'p3-reconstructed-v1',
          'source_profile':'KR125_NATIVE_GRAPHICS_WITH_RECONSTRUCTED_P3_GEOGRAPHY','fact_status':'RECONSTRUCTED',
          'source_geometry':None,'geometry_note':'New P3 layout using original Korean tiles/objects; not verified historical native map coordinates',
          'ground_ids':[ground]*(w*h),'objects':[],'blocked':[],'exits':[],'spawns':[],'spawn_zones':[],'npcs':[],
          'landmarks':[],'return_city':CITY,'allow_return':True,'danger':'safe','render_layers':'ground then foot-depth ordered structures/actors'}
    def block(m,x,y):
        if 0<=x<m['width'] and 0<=y<m['height'] and [x,y] not in m['blocked']:m['blocked'].append([x,y])
    def unblock(m,x,y):
        if [x,y] in m['blocked']:m['blocked'].remove([x,y])
    def paint(m,x,y,word):
        if 0<=x<m['width'] and 0<=y<m['height']:m['ground_ids'][y*m['width']+x]=word
    def road(m,x1,y1,x2,y2,width=1,word=1):
        for x in range(min(x1,x2),max(x1,x2)+1):
            for y in range(min(y1,y2),max(y1,y2)+1):
                for dx in range(-(width//2),width//2+1):
                    for dy in range(-(width//2),width//2+1):paint(m,x+dx,y+dy,word);unblock(m,x+dx,y+dy)
    def obj(m,n,x,y,physical=False):
        if n not in native_object_meta:raise ValueError(f'Native object{n} absent from authenticated source chunk')
        src=native_object_meta[n]
        m['objects'].append({'native_id':n,'frame_png':copied_object(src),'x':x*24,'y':(y-src['height']+1)*24,
          'grid_x':x,'grid_y':y,'depth_y':(y+1)*24,'height':src['height'],'source_id':f'KR125:SOBJECT.OTB:{n}',
          'placement_fact_status':'RECONSTRUCTED','edge_mask':src['edge_mask']})
        if physical:block(m,x,y)
    def tree(m,x,y):
        for dx,n in [(-1,85),(0,86),(1,87)]:obj(m,n,x+dx,y,physical=dx==0)
    def stamp(m,sx,sy,w,h,dx,dy,label):
        for y in range(h):
            for x in range(w):paint(m,dx+x,dy+y,source_ground[(sy+y)*64+sx+x]);block(m,dx+x,dy+y)
        for src in source_objects:
            if sx<=src['grid_x']<sx+w and sy<=src['grid_y']<sy+h:
                nx=dx+src['grid_x']-sx;ny=dy+src['grid_y']-sy
                obj(m,src['native_id'],nx,ny)
        bindings.append({'field':f'maps.{m["id"]}.building.{label}','source_id':'LIB-009!0.map!storage_chunk15',
          'source_rect':[sx,sy,w,h],'effective_rect':[dx,dy,w,h],'fact_status':'RECONSTRUCTED',
          'reason':'Visible Korean architecture fragments reused; new facility association/coordinates, not original city identity'})
    town=world(CITY,'국내성 · 작업용 재구성')
    # Main cardinal streets and a visible eastern canal, crossed at actual bridges.
    for y in range(1,63):
        for x in range(36,39):paint(town,x,y,1028);block(town,x,y)
    road(town,32,1,32,62,width=5)
    road(town,1,32,62,32,width=5)
    road(town,32,57,55,57,width=3)
    for x in range(64):
        if not 30<=x<=34:
            obj(town,735,x,0,True);obj(town,735,x,63,True)
    for y in range(1,63):
        if not 30<=y<=34:
            obj(town,191,0,y,True);obj(town,191,63,y,True)
    buildings=[('tavern','주막',(10,4,20,10),(4,5),(15,15)),
      ('forge','대장간',(10,17,17,14),(40,5),(48,19)),
      ('warrior_guild','전사길드',(10,17,17,14),(4,40),(12,54)),
      ('mage_guild','주술사길드',(10,17,17,14),(40,40),(48,54)),
      ('rogue_guild','도적길드',(10,4,20,10),(3,23),(12,34)),
      ('poet_guild','도사길드',(10,4,20,10),(40,23),(49,34))]
    maps={CITY:town};doors={}
    for key,label,rect,dest,door in buildings:
        stamp(town,*rect,*dest,label)
        x,y=door;doors[key]=door
        # Door is placed outside the collision footprint; source architecture
        # remains opaque and collidable, never pretending original passability.
        road(town,x,y,x,min(60,y+2),width=1)
        road(town,x,min(60,y+2),32,min(60,y+2),width=1)
        town['landmarks'].append({'name':label,'x':x,'y':y,'door':[x,y],'fact_status':'RECONSTRUCTED'})
        mid='gp:map:'+key;interior=world(mid,label,20,18,153)
        for yy in range(18):
            for xx in range(20):
                if xx in [0,19] or yy in [0,17]:block(interior,xx,yy);paint(interior,xx,yy,152)
        # Actual Korean wall / wooden-door sprites; different room furniture.
        for xx in range(1,19):obj(interior,697 if key in ['tavern','poet_guild'] else 698,xx,2)
        for xx in range(3,18,6):obj(interior,735,xx,6,True)
        for xx in range(3,18,6):obj(interior,715,xx,5,True)
        road(interior,10,7,10,16,width=3)
        interior['exits']=[{'id':key+'-out','x':10,'y':16,'to_map':CITY,'to_x':x,'to_y':y+1,'direction':'south','fact_status':'RECONSTRUCTED'}]
        town['exits'].append({'id':key+'-in','x':x,'y':y,'to_map':mid,'to_x':10,'to_y':15,'direction':'north','fact_status':'RECONSTRUCTED'})
        maps[mid]=interior
    # Ornament and recognizable shrine / market, away from all required paths.
    for x,y in [(5,19),(23,8),(25,19),(57,21),(6,58),(24,57),(58,58),(55,37)]:tree(town,x,y)
    town['landmarks'] += [{'name':'성황당','x':29,'y':21},{'name':'장터','x':25,'y':29},
      {'name':'북문','x':32,'y':2},{'name':'동문','x':61,'y':32},{'name':'남문','x':32,'y':61},{'name':'서문','x':2,'y':32},
      {'name':'수로 · 돌다리','x':37,'y':29}]
    gate_data={'north':((32,1),(32,2),(16,30),(16,29)),
      'south':((32,62),(32,61),(16,1),(16,2)),
      'east':((62,32),(61,32),(1,16),(2,16)),
      'west':((1,32),(2,32),(30,16),(29,16))}
    gates={};field_names={'north':'북문 초보 들판','south':'남문 왕초보 사냥터','east':'동문 초보 숲','west':'서문 초보 숲'}
    for direction,(city_trigger,city_arrival,field_trigger,field_arrival) in gate_data.items():
        mid=f'gp:map:{direction}_field';m=world(mid,field_names[direction],32,32);m['danger']='novice_hunting'
        for y in range(32):
            for x in range(32):
                if x in [0,31] or y in [0,31]:block(m,x,y)
        road(m,16,1,16,30,width=3);road(m,1,16,30,16,width=3)
        for x,y in [(4,4),(13,4),(22,4),(28,4),(4,14),(27,13),(4,25),(14,27),(27,27),(22,28)]:tree(m,x,y)
        # A small native-water pond with a walkable perimeter; no hidden spawn.
        for yy in range(22,25):
            for xx in range(3,6):paint(m,xx,yy,1028);block(m,xx,yy)
        ft=field_trigger;ca=city_arrival;ct=city_trigger;fa=field_arrival
        m['exits']=[{'id':direction+'-field-to-city','x':ft[0],'y':ft[1],'to_map':CITY,'to_x':ca[0],'to_y':ca[1],'direction':{'north':'south','south':'north','east':'west','west':'east'}[direction],'fact_status':'RECONSTRUCTED'}]
        town['exits'].append({'id':direction+'-city-to-field','x':ct[0],'y':ct[1],'to_map':mid,'to_x':fa[0],'to_y':fa[1],'direction':direction,'fact_status':'RECONSTRUCTED'})
        gates[direction]={'map_id':CITY,'x':ca[0],'y':ca[1],'direction':direction,'fact_status':'RECONSTRUCTED'}
        for zi,(zx,zy) in enumerate([(5,6),(21,6),(6,20),(21,20)]):
            zone={'id':f'{direction}-zone-{zi}','rect':[zx,zy,7,7],'population':4,'fact_status':'BALANCE_ESTIMATE'};m['spawn_zones'].append(zone)
            for k,(dx,dy) in enumerate([(0,0),(4,0),(0,4),(4,4)]):
                x,y=zx+dx,zy+dy
                if [x,y] in m['blocked']:unblock(m,x,y);paint(m,x,y,52)
                mon=SQUIRREL if (zi+k)%2==0 else RABBIT
                m['spawns'].append({'id':f'gp:spawn:{direction}:{zi}:{k}','monster_id':mon,'x':x,'y':y,'zone_id':zone['id'],
                  'respawn_seconds':8.0 if mon==RABBIT else 10.0,'leash_radius':6,'roam_radius':3,'fact_status':'BALANCE_ESTIMATE'})
        maps[mid]=m
    # Source fields only; unknown bidirectional vendor economics documented below.
    items={}
    def additem(name,iid=None,**effective):
        src=selected_items.get(name);iid=iid or src['content_id']
        item={'id':iid,'name':name,'original_native_id':None,'stack_max':999,'source_value':src['original_value'] if src else None,
          'source_id':src['source_ids'] if src else [],'source_pointer':src['source_locator'] if src else None,
          'fact_status':'ORIGINAL_FIELDS_WITH_RECONSTRUCTED_GAMEPLAY' if src else 'RECONSTRUCTED',
          'effective_field_status':{},**effective}
        for field in effective:item['effective_field_status'][field]='RECONSTRUCTED'
        if src:
            for field,orig in [('required_level','minimum_level'),('damage_min','damage_min'),('damage_max','damage_max')]:
                if orig in src['original_value'] and src['original_value'][orig] is not None:item[field]=src['original_value'][orig];item['effective_field_status'][field]='ORIGINAL_VERIFIED'
        items[iid]=item;return item
    additem('목도',WOOD,kind='weapon',slot='weapon',attack=7,damage_min=5,damage_max=10,durability=100,required_level=0,required_job='any',buy_price=None,sell_price=None,stack_max=1,look='player_equipped')
    additem('목검',SWORD,kind='weapon',slot='weapon',attack=12,durability=150,required_level=0,required_job='any',buy_price=20,sell_price=5,stack_max=1,look='player_equipped')
    additem('사두목도',kind='weapon',slot='weapon',attack=20,durability=200,required_level=0,required_job='any',buy_price=60,sell_price=15,stack_max=1,look='player_equipped')
    additem('도토리',ACORN,kind='material',buy_price=None,sell_price=5)
    additem('토끼고기',MEAT,kind='consumable',hp_restore=8,buy_price=None,sell_price=8)
    additem('동동주',WINE,kind='consumable',mp_restore=20,buy_price=10,sell_price=2)
    additem('초보옷',CLOTHES,kind='armor',slot='armor',defense=1,durability=100,required_level=0,required_job='any',buy_price=20,sell_price=5,stack_max=1,look='player_base')
    additem('초보갑옷',ARMOR,kind='armor',slot='armor',defense=3,durability=160,required_level=3,required_job='any',buy_price=40,sell_price=10,stack_max=1,look='player_equipped')
    npcs={}
    def npc(iid,name,map_id,x,y,look,services,dialogue,job=None,shop=None):
        source=next((r for r in rules['npcs'] if r['id']==iid),None)
        n={'id':iid,'name':name,'map_id':map_id,'x':x,'y':y,'look':look,'services':services,'look_id':look,'dialogue':{
          'greeting':dialogue,'success':'좋습니다. 다시 필요하면 찾아오세요.','failure':'조건과 가지고 있는 물품을 다시 확인해 주세요.','cancel':'천천히 생각하고 다시 오세요.',
          'revisit':dialogue},'shop':shop or {},'source_contract':source,'source_value':source['value'] if source else None,
          'effective_field_status':{'position':'RECONSTRUCTED','look':'RECONSTRUCTED','dialogue':'RECONSTRUCTED','prices':'BALANCE_ESTIMATE'},'job':job}
        npcs[iid]=n;maps[map_id]['npcs'].append(iid);return n
    for job,(iid,name,key) in MASTERS.items():
        npc(iid,name,'gp:map:'+key+'_guild',10,7,key+'_master',['change_job','teach_skill'],f'{name}입니다. {job}의 길을 택하려면 5레벨 이상이어야 합니다. 배울 기술의 비용과 재료를 확인하세요.',job)
    npc('KRO-NPC_SERVICE-1e329bf1dc2165','왈숙', 'gp:map:tavern',10,7,'tavern',['shop'],
        '어서 와요. 주막의 동동주로 기력을 보충하고 쉬어 가세요.',shop={WINE:{'buy_price':10,'sell_price':2}})
    npc('KRO-NPC_SERVICE-42b4704cb5c0d5','털보','gp:map:forge',10,7,'forge',['shop','repair'],
        '무기는 손에 맞는 것이 좋아. 목검과 사두목도를 보고, 닳은 장비도 수리해 주지.',shop={i:{'buy_price':items[i]['buy_price'],'sell_price':items[i]['sell_price']} for i in [SWORD,selected_items['사두목도']['content_id']]})
    npc('KRO-NPC_SERVICE-a0c0960283ad50','떼보',CITY,25,29,'armorer',['shop'],
        '옷과 갑옷은 내가 맡지. 입을 수 있는 레벨을 살펴보고 골라 보게.',shop={i:{'buy_price':items[i]['buy_price'],'sell_price':items[i]['sell_price']} for i in [CLOTHES,ARMOR]})
    npc('gp:npc:grocer','장터 식재료상',CITY,27,33,'grocer',['shop'],
        '초보 사냥터에서 얻은 도토리와 토끼고기를 사들입니다. 기술 재료로 쓸 몫은 남겨 두세요.',shop={ACORN:{'buy_price':None,'sell_price':5},MEAT:{'buy_price':None,'sell_price':8}})
    npc('gp:npc:shrine_healer','성황당지기',CITY,29,22,'healer',['heal','revive'],
        '성황당에 오셨군요. 지친 몸을 돌보고 쓰러진 이가 다시 길을 나서도록 돕겠습니다.')
    # First skills for all four jobs retain *individual* documented learn levels.
    skill_ids=['KRO-77f964c0bd64','KRO-32c49870aa62','KRO-4eeca26285d6','KRO-62769e97ce90',
      'KRO-972853314e6a','KRO-33876779ed3b','KRO-3559b12ed6a7','KRO-9fa71eae9c36','KRO-a1b768df5f76','KRO-f0fcaedd0fba']
    skills={}
    for iid in skill_ids:
        src=next(r for r in rules['skills'] if r['id']==iid);v=src['value'];job=v['job'];name=src['name']
        ing={ACORN if q['item_name_literal']=='도토리' else MEAT:q['quantity'] for q in v['ingredients']}
        if name=='비영사천문':kind,power,mp,rng,cool,wind,impact,effect,sound='return',0,5,0,1.4,.28,.5,13,8
        elif name=='성황령':kind,power,mp,rng,cool,wind,impact,effect,sound='shrine',0,0,0,1.2,.2,.42,14,9
        elif '기원' in name:
            vals={'전사':(20,6,.8,.18,.34,19,6),'도적':(22,5,.75,.15,.31,20,7),'주술사':(25,5,.9,.22,.4,0,4),'도사':(35,4,.65,.16,.29,16,5)}
            power,mp,cool,wind,impact,effect,sound=vals[job];kind,rng='heal',0
        else:
            idx=['주작','현무','백호','청룡'].index(v['guardian']);kind,power,mp,rng,cool,wind,impact,effect,sound='damage',20+idx,6,5,1.0+idx*.05,.22+idx*.02,.4+idx*.03,[13,14,16,19][idx],[17,18,19,20][idx]
        teachers=[r[0] for j,r in MASTERS.items() if job=='COMMON_FOUR_STARTER_JOBS' or j==job]
        skills[iid]={'id':iid,'name':name,'job':job,'learn_level':v['learn_level'],'learn_money':v['learn_money']['value'],
          'ingredients':ing,'kind':kind,'mp_cost':mp,'hp_cost':0,'power':power,'range':rng,'cooldown':cool,'windup':wind,
          'impact_delay':impact,'effect_id':effect,'sound_id':sound,'teacher_ids':teachers,'guardian':v.get('guardian'),
          'source_value':v,'source_id':src['source_id'],'source_pointer':src['source_pointer'],'original_native_id':None,
          'effective_field_status':{'learn_level':'ORIGINAL_VERIFIED','learn_money':'ORIGINAL_VERIFIED','ingredient_quantities':'ORIGINAL_VERIFIED',
             'ingredient_runtime_IDs':'RECONSTRUCTED_ALIAS','kind':'CORROBORATED','mp_cost':'BALANCE_ESTIMATE','power':'BALANCE_ESTIMATE','range':'BALANCE_ESTIMATE','timeline':'RECONSTRUCTED','effect_sound_binding':'RECONSTRUCTED'},'enabled':True}
    monsters={}
    for name,iid,loot,hp,attack,movement,look in [('다람쥐',SQUIRREL,ACORN,24,3,1.3,'squirrel'),('토끼',RABBIT,MEAT,18,2,1.6,'rabbit')]:
        src=selected_monsters[name];sv=src['original_value'];assert src['content_id']==iid
        monsters[iid]={'id':iid,'name':name,'hp':hp,'attack':attack,'defense':0,'xp':sv['experience']['value'],
          'aggression':'retaliate','attack_interval':1.4,'move_interval':movement,'respawn_seconds':10.0,'look':look,'look_id':look,
          'drops':[{'item_id':loot,'chance':.85,'quantity_min':1,'quantity_max':1}],
          'drop_model':'independent_bernoulli; no_drop_probability0.15; quantity1','money_min':0,'money_max':0,
          'source_value':sv,'source_id':src['source_ids'],'source_pointer':src['source_locator'],'original_native_id':None,
          'effective_field_status':{'name':'ORIGINAL_VERIFIED','xp':'ORIGINAL_VERIFIED','possible_item_name':'ORIGINAL_VERIFIED','hp':'BALANCE_ESTIMATE','attack':'BALANCE_ESTIMATE','AI':'RECONSTRUCTED','drop_chance':'BALANCE_ESTIMATE','spawn':'BALANCE_ESTIMATE'}}
    for mid,m in maps.items():
        # NPC occupancy is enforced by the state actor layer; NPC ground cells
        # remain structurally walkable for spawn/save coordinate validation.
        floor=Image.new('RGBA',(m['width']*24,m['height']*24),(0,0,0,255))
        for cell,word in enumerate(m['ground_ids']):
            if word:floor.alpha_composite(tile(word),((cell%m['width'])*24,(cell//m['width'])*24))
        rel=f'gameplay/world/{mid.split(":")[-1]}-floor.png';save_png(floor,output/rel)
        m['floor_png']=rel;m['ground_layers']=[{'path':rel,'x':0,'y':0}]
        m['blocked']=sorted(m['blocked'],key=lambda p:(p[1],p[0]))
        # Separate path navigation collision from native visual-resource masks.
        m['collision_status']='RECONSTRUCTED_EXPLICIT_P3_GRID';m['geometry_sha256']=digest({k:m[k] for k in ['width','height','blocked','exits']})
    jobs={'commoner':{'name':'평민','minimum_level':1},**{job:{'name':job,'minimum_level':5,'teacher_id':r[0]} for job,r in MASTERS.items()}}
    data={'schema':'baram.gameplay.content/1','profile':PROFILE,'world_profile':'KR_DOMESTIC_CITY_P3_RECONSTRUCTED_V1',
      'maps':maps,'npcs':npcs,'items':items,'monsters':monsters,'skills':skills,'jobs':jobs,
      'xp_thresholds':[0,15,35,60,90,130,180,245,325,425],
      'start':{'map_id':CITY,'x':32,'y':36,'money':0,'hp':50,'mp':25,'job':'commoner','guardian':'주작',
        'starter_items':[{'item_id':WOOD,'quantity':1},{'item_id':CLOTHES,'quantity':1}],'initial_equipment':{'weapon':WOOD,'armor':CLOTHES}},
      'gates':gates,'returns':{CITY:gates},'respawn':{'map_id':CITY,'x':29,'y':23},
      'config':{'base_attack':4,'base_defense':0,'attack_interval':.55,'attack_windup':.13,'attack_range':1,'hp_per_level':8,'mp_per_level':5,
        'attack_sound_id':1,'swing_sound_id':3,'player_hit_sound_id':10,'attack_effect_id':0,
        'pickup_sound_id':2,'transaction_sound_id':12,'equip_sound_id':13,
        'move_interval':.16,'inventory_capacity':40,'repair_price_per_point':1,'heal_price':0,'death_money_loss_ratio':0.0,
        'death_inventory_loss':'NONE_WORKING_P3_POLICY','drop_expiry_seconds':3600,'level_cap':10,'natural_progression_job':'주술사',
        'natural_progression_guardian':'주작','natural_progression_skill':'KRO-3559b12ed6a7'},
      'source_skill_catalog':rules['skills'],'source_npc_catalog':rules['npcs'],
      'deferred':{'higher_skill_ids':[s['id'] for s in rules['skills'] if s['id'] not in skills],
        'unplaced_npc_contract_ids':[n['id'] for n in rules['npcs'] if n['id'] not in npcs],
        'source_map_geometry':'Unknown server topology and active bounds preserved; P3 reconstruction is separate'},
      'provenance':{'rules_profile':PROFILE,'rules_sha256':digest(rules_path),'parent_runtime_sha256':digest(base/'runtime.json'),
        'kr125_zip_sha256':digest(client_zip),'kr491_usage':'Original KR4.91 sprites/effects/sounds as separate resource-version with reconstruction of semantics',
        'world_geometry_fact_status':'RECONSTRUCTED','monster_2001_selection':'Published2001squirrelXP10 selected instead of2000XP5; rabbitXP5 retained',
        'source_value_policy':'Preserve original source_value; effective fields separately tagged; no historical precision claim for reconstructed positions/timing/drop probabilities',
        'balance_fields':['xp_thresholds','start_hp_mp_money','monster_hp_attack_intervals','drop_model','vendor_direction_assignment_and_bid_ask','repair/death/heal policy','skill_mp_power_range_timeline','basic_attack_and_UI_sound_effect_bindings'],
        'building_bindings':bindings,'source_city_map_candidates':[r['content_id'] for r in official_maps]},
      'artifacts':{'actors':'gameplay-assets/actors.json','base_generation':'WORK-PRIORITY-GEN002'}}
    data['compatibility']={'schema':'1','rules':digest({'items':{i:{k:v for k,v in r.items() if k not in ['look','look_id','source_pointer']} for i,r in items.items()},
      'skills':{i:{k:v for k,v in r.items() if k not in ['effect_id','sound_id','source_pointer']} for i,r in skills.items()},'xp':data['xp_thresholds'],'config':data['config']}),
      'idset':digest({k:sorted(data[k]) for k in ['maps','items','skills','npcs','monsters','jobs']}),
      'map_geometry':digest({i:r['geometry_sha256'] for i,r in maps.items()})}
    native_assets=json.loads((base/'kr491/kr491_runtime.json').read_text())
    sound_ids={int(Path(r['member']).stem) for r in native_assets['sounds']}
    referenced={r['sound_id'] for r in skills.values()}|{v for k,v in data['config'].items() if k.endswith('sound_id')}
    if not referenced<=sound_ids:raise ValueError(f'Unknown native sound IDs {referenced-sound_ids}')
    effect_ids={int(r['id']) for r in native_assets['effects']}
    if not {r['effect_id'] for r in skills.values()}<=effect_ids:raise ValueError('Unknown effect reference')
    validation=validate(data,output)
    data['manifest_sha256']=digest({'compatibility':data['compatibility'],'profile':PROFILE,'compiler':digest(Path(__file__))})
    write(output/'gameplay_content.json',data)
    write(output/'GAMEPLAY_CONTENT_RECEIPT.json',{'status':'COMPILED_AND_STATICALLY_VALIDATED','profile':PROFILE,'compiler_sha256':digest(Path(__file__)),
      'definition_sha256':digest(output/'gameplay_content.json'),'maps':len(maps),'npcs':len(npcs),'items':len(items),'skills_enabled':len(skills),
      'source_skills_retained':len(rules['skills']),'source_npcs_retained':len(rules['npcs']),'original_source_fields_not_gameplay_runtime_PASS':True,
      'validation':validation,'original_inputs_preserved':True,'runtime_test':'NOT_RUN'})
    return {'status':'COMPILED_AND_STATICALLY_VALIDATED','output':str(output),'maps':len(maps),'npcs':len(npcs),'skills':len(skills),'validation':validation}

def validate(data,root):
    checks=[]
    def check(i,good,details=None):
        checks.append({'id':i,'status':'PASS' if good else 'FAIL','details':details})
        if not good:raise ValueError(f'Gameplay content invalid {i}: {details}')
    reach={}
    for mid,m in data['maps'].items():
        b={tuple(p) for p in m['blocked']};w,h=m['width'],m['height']
        start=next(((x,y) for y in range(h) for x in range(w) if (x,y) not in b),None)
        seen={start};q=deque([start])
        while q:
            x,y=q.popleft()
            for dx,dy in [(0,-1),(1,0),(0,1),(-1,0)]:
                p=x+dx,y+dy
                if 0<=p[0]<w and 0<=p[1]<h and p not in b and p not in seen:seen.add(p);q.append(p)
        reach[mid]=seen
        check(f'{mid}:single_walkable_component',len(seen)==w*h-len(b),{'reachable':len(seen),'walkable':w*h-len(b)})
        for e in m['exits']:
            t=data['maps'].get(e['to_map']);dest=e['to_x'],e['to_y']
            check(f'{mid}:{e["id"]}:valid_exit', (e['x'],e['y']) in seen and t is not None and 0<=dest[0]<t['width'] and 0<=dest[1]<t['height'] and list(dest) not in t['blocked'])
        for s in m['spawns']:
            check(f'{mid}:{s["id"]}:valid_spawn',s['monster_id'] in data['monsters'] and (s['x'],s['y']) in seen and all(abs(s['x']-e['x'])+abs(s['y']-e['y'])>=5 for e in m['exits']))
        for n in m['npcs']:
            npc=data['npcs'][n];x,y=npc['x'],npc['y']
            check(n+':npc_ground_walkable',(x,y) in seen)
            check(n+':reachable_interaction',any((x+dx,y+dy) in seen for dx,dy in [(0,-1),(1,0),(0,1),(-1,0)]))
    for iid,s in data['skills'].items():
        check(iid+':ingredient_closure',all(i in data['items'] and q>0 for i,q in s['ingredients'].items()))
        check(iid+':teacher_permission',all(n in data['npcs'] and (s['job']=='COMMON_FOUR_STARTER_JOBS' or data['npcs'][n]['job']==s['job']) for n in s['teacher_ids']))
    for nid,n in data['npcs'].items():
        for iid,p in n['shop'].items():
            check(nid+':'+iid+':no_arbitrage',iid in data['items'] and (p['buy_price'] is None or p['sell_price'] is None or p['buy_price']>=p['sell_price']>=0))
    for direction,d in data['gates'].items():check('return:'+direction, (d['x'],d['y']) in reach[d['map_id']])
    check('spawn_ids_globally_unique',len({s['id'] for m in data['maps'].values() for s in m['spawns']})==sum(len(m['spawns']) for m in data['maps'].values()))
    pngs=list(root.rglob('*.png'))
    for p in pngs:
        with Image.open(p) as im:im.verify()
        with Image.open(p) as im:im.load()
    check('all_png_structure_decode',True,{'png_count':len(pngs)})
    return {'status':'PASS','count':len(checks),'failed':0,'checks':checks,'scope':'static BFS/refs/economy/PNG; runtime gameplay NOT_RUN'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['base','rules','normalized','maps','client_zip','reader','output']:p.add_argument('--'+key.replace('_','-'),required=True,type=Path)
    a=p.parse_args();print(json.dumps(compile_content(a.base,a.rules,a.normalized,a.maps,a.client_zip,a.reader,a.output),ensure_ascii=False))
if __name__=='__main__':main()
