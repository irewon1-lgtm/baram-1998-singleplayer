#!/usr/bin/env python3
"""Complete the existing Korean identities, with source-bound fields and overlays.

All definitions are declarative. Original maps remain in a private bundle. Known
numeric fields are copied unchanged into the proposal and guarded null fills are
explicit; source IDs are not reallocated. No game code or canonical data writes.
"""
import argparse
import collections
import copy
import io
import math
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path
sys.dont_write_bytecode=True
from common import ROOT, WORK, BASE, IDs, load, write, lines, file_sha, sha, canonical, round_int, ratio, record, ref, shard
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import dat_entries,Epf,read_palettes
from legacy_maps import tile_table,static_objects,map_cells

JOBS=['전사','도적','주술사','도사']
JOBKEY={'전사':'warrior','도적':'rogue','주술사':'mage','도사':'poet','평민':'novice'}
def norm(s):return re.sub(r'[\s/]+','',s or '')
def known(v,k,default):
    value=v['values'].get(k)
    return default if value is None else round_int(value) if isinstance(value,(int,float)) and not isinstance(value,bool) else value

def build(args):
    ids=IDs();base=load(ROOT/'game/data/numeric.json')['contents'];bycat=collections.defaultdict(list)
    for r in base:bycat[r['category']].append(r)
    catalog={r['content_id']:r for r in lines(ROOT/'research/restoration-integrated-20261013/CONTENT_CATALOG.jsonl')}
    fields={r['field_id']:r for r in lines(ROOT/'research/restoration-integrated-20261013/NUMERIC_MASTER.jsonl')}
    assets={r['id']:r for p in (WORK/'packages/WK-ASSETS-001').glob('content-*.jsonl') for r in lines(p)}
    package=WORK/'packages'/args.batch
    if package.exists():raise ValueError('Use a new batch, frozen packages are not overwritten')
    package.mkdir(parents=True);(package/'schema').mkdir();shutil.copy2(WORK/'schemas/content-v1.json',package/'schema/content-v1.json')
    out=Path(args.private_out);out.mkdir(parents=True,exist_ok=True)
    records=[];by_effective={};inferences=collections.Counter();null_fills=0;identity=[]
    rules=[
      {'id':'prov.numeric.base','source_mode':'ORIGINAL','file':'game/data/numeric.json','sha256':file_sha(ROOT/'game/data/numeric.json'),'base_game_commit':BASE,'field_classifications':'Keep original per-field provenance; external replacement and estimates are not KR-confirmed'},
      {'id':'prov.numeric.master','source_mode':'DERIVED','file':'research/restoration-integrated-20261013/NUMERIC_MASTER.jsonl','sha256':file_sha(ROOT/'research/restoration-integrated-20261013/NUMERIC_MASTER.jsonl')},
      {'id':'rule.item.complete','source_mode':'INFERRED','basis':['existing items at similar required level/type','known guide price and known damage/armor stats'],
       'rules':{'level':'existing; else special/gold tier 50, iron 20, other 1','weapon_damage':'max(1,2+floor(level*0.6)) .. max(min,4+floor(level*0.9))','armor_delta':'-max(1,round(level/3))','buy':'known vendor buy, else known guide listed price, else max(5,level^2*12)','sell':'known sell, else 40% buy','quest_trade':'not sold by vendors; account quest consume only','source_asset_identity':'Known bindings preserved; category-level original sprite replacement for unknown identity'}},
      {'id':'rule.monster.complete','source_mode':'INFERRED','basis':['source experience','existing early monster stats','visually reviewed source model representatives'],
       'rules':{'level':'log interpolate XP anchors (5,1),(250,8),(2500,20),(20000,35),(150000,55),(500000,70),(3000000,85),(10000000,99)','hp':'25 + level^2*9 + sqrt(XP)*3; named boss x4, only when unknown','attack':'2 + level^1.7/6, min 2; max 1.35x','movement':'900ms..300ms by level','respawn':'30s ordinary, 180s boss','aggro':'6 tiles hostile, 0 passive','money':'max(1,level*3)','no_historical_balance_claim':True}},
      {'id':'rule.drop.complete','source_mode':'INFERRED','basis':['DROP_RULES.jsonl possible items, not guaranteed','singleplayer acquisition for unused equipment/materials'],
       'rules':{'selection':'independent rolls; known exact ratio retained','unknown_probabilities':{'material':0.6,'consumable':0.25,'equipment':0.015,'quest':0.1},'quantity':'known quantity, else one','extra_acquisition':'closest compatible level monster; inferred, not source drop'}},
      {'id':'rule.map.overlay','source_mode':'INFERRED','basis':['pinned NA495 map bytes','KR491 tile/object tables','source map byte-count dimensions and inherited verified dimensions'],
       'rules':{'coordinates':'0-based x right/y down, 24px, top left','collision':'original 4-bit masks retained, mask15 solid; directional mapping requires importer capability','entry':'largest original walkable component; no pixel changes','links':'authored connected routes, two-way return portals in same reachable component','ecology':'source name family + XP level; inferred original role','history':'Original NA geography, not verified KR1998 layout'}},
      {'id':'rule.npc.complete','source_mode':'INFERRED','basis':['source NPC names and locations','source monster/human models','existing offline NPC services'],
       'rules':{'dialogue':'New Korean functional dialogue, not quoted historical dialogue','placements':'walkable reachable cell with interaction neighbor; mutual-exclusive same-name/location variants','shops':'ordinary goods by shop role; exact source prices kept','unknown_role':'craft/material exchange rather than functionless dialogue'}},
      {'id':'rule.skill.complete','source_mode':'INFERRED','basis':['known learn costs, level, healing, damage','existing skill_effects.json','similar-level/class skill effects'],
       'rules':{'MP':'known; else max(1,level/2)','HP':'known absolute/fraction; never permit suicide at cast','range':'known; else 1 melee /6 spell','cooldown':'known; else 1s, high offensive 4s','duration':'0 instant, known duration for status, otherwise 30s','damage':'known; otherwise max(20,level^2*5) times named melee multiplier','target':'solo effects for summon/recall are explicitly labelled offline replacements','unknown_effect':'deterministic category fallback, historical identity unverified'}},
      {'id':'rule.growth.complete','source_mode':'INFERRED','basis':['existing 401 source growth rows'],
       'rules':{'terminal':'level99 exp_to_next=0; terminal has no level100','cumulative':'start-of-level = previous cumulative_exp_to_next','missing_armor':'base max(0,100-level)','HP_MP':'retain source ranges; fill missing range from nearest same-class row','novice':'preserve existing levels1–5; selected classes have full1–99 tables','integer':'ROUND_HALF_UP ties away from zero'}},
      {'id':'rule.advancement.offline','source_mode':'INFERRED','basis':['known source rank/HP/MP conditions','four guild NPCs','source listed items and bosses'],
       'rules':{'level':'99 and previous rank','missing_MP':'warrior0, rogue90000 at rank3; source known thresholds retained','quest':'authored solo collection/kill quest, once, separate completion key per job/rank','exchange':'explicit level99 XP-to-max-HP/MP exchange, not a claimed historical formula'}},
      {'id':'rule.quest.offline','source_mode':'INFERRED','basis':['source hunting regions and items','existing first_steps/hunter starter quests (not duplicated)'],
       'rules':{'objectives':'region-specific kills + collection + NPC dialogue','reward':'XP/gold and level-compatible item; once per unique quest','consume':'collection objective item is atomically consumed at completion','repeat':'daily quest 24h cooldown, occurrence counter, one completion transaction ID','history':'OFFLINE_EXTENSION'}},
      {'id':'rule.enhancement.extension','source_mode':'INFERRED','basis':['existing item durability/stats and economy'],
       'rules':{'historical_existence':'NOT_CONFIRMED','default_enabled':False,'stages':'1–10','success':'90%,85%,80%,75%,65%,55%,45%,35%,25%,15%','failure':'early retain, stages5–8 downgrade,9–10 may destroy; exclusive rational probabilities','consume':'gold and material on each attempt, before outcome','stats':'one scalar per-item instance, base definition unchanged'}},
    ]
    rules.append({'id':'rule.numeric.mean.rounding','source_mode':'AVERAGED','basis':['Inherited KR_MEAN observation groups'],'rule':'Retain raw mean and source observations; integer values use ROUND_HALF_UP, ties away from zero; ratios remain rational. Squirrel XP7.5 proposes8 with an expected7.5 guard.'})
    def add(r):records.append(r);by_effective[r.get('target_id',r['id'])]=r;return r
    def patch(src,kind,data,rule,fill=None):
        nonlocal null_fills
        r=record(ids.get(kind,'proposal.'+src['id']),kind,data,['prov.numeric.base',rule],target=src['id'])
        r['field_provenance']={'retained_source_values':'prov.numeric.base / original canonical record per-field provenance','authored_runtime_fields':rule,'visual':'rule.visual.binding'}
        for k,value in (fill or {}).items():
            if src['values'].get(k) is None:
                r['changes'].append({'path':'values.'+k,'before':{'exists':k in src['values'],'value':None} if k in src['values'] else {'exists':False},
                  'after':value,'reason':'Fill source gap with recorded completion rule; do not overwrite changed Codex field','provenance_ref':rule});null_fills+=1
        for k,p in src.get('provenance',{}).items():
            f=fields.get(p.get('field_id'),{})
            if p.get('classification')=='KR_MEAN' and f.get('raw_average') is not None and f.get('unit') not in ('probability','fraction'):
                value=round_int(f['raw_average'])
                if src['values'][k]!=value:
                    r['changes'].append({'path':'values.'+k,'before':{'exists':True,'value':src['values'][k]},'after':value,'reason':'Apply user-mandated integer rounding to inherited raw mean','provenance_ref':'rule.numeric.mean.rounding'})
                    r['provenance_refs'].append('rule.numeric.mean.rounding')
        return add(r)
    def asset(key):
        ident='wk.asset.kr491.'+key
        if ident not in assets:raise ValueError('Missing required source asset '+ident)
        return ident
    class_ids={j:ids.get('class',JOBKEY[j]) for j in JOBS}
    item_by_name={}
    for v in sorted(bycat['item'],key=lambda r:r['id']):item_by_name.setdefault(norm(v['name']),v)
    item_ids={norm(v['name']):v['id'] for v in item_by_name.values()}
    npc_by_loc=collections.defaultdict(list)
    npc_primary={}
    for v in sorted(bycat['npc'],key=lambda r:r['id']):
        key=norm(v['name'])+'|'+norm(v['job']);npc_primary.setdefault(key,v['id']);npc_by_loc[norm(v['job'])].append(v)
    teachers={j:next(v['id'] for v in bycat['npc'] if norm(v['job'])=='고구려'+j+'길드') for j in JOBS}
    monster_levels={}
    anchors=[(5,1),(250,8),(2500,20),(20000,35),(150000,55),(500000,70),(3000000,85),(10000000,99)]
    def infer_level(xp):
        if xp<=anchors[0][0]:return 1
        for (a,la),(b,lb) in zip(anchors,anchors[1:]):
            if xp<=b:return round_int(la+(lb-la)*math.log(xp/a)/math.log(b/a))
        return 99
    for v in bycat['monster']:
        xp=known(v,'experience',max(5,known(v,'hp',100)*2));monster_levels[v['id']]=known(v,'level',infer_level(xp))
    # Source families are mapped to visually inspected representative source models.
    family_specs=[('북극','north',153),('용','dragon',189),('귀신','ghost',73),('유령','ghost',73),('해골','skeleton',30),
      ('전갈','scorpion',32),('가재','scorpion',286),('거미','spider',97),('사마귀','mantis',98),('원숭','monkey',88),
      ('호랑','tiger',29),('자호','tiger',29),('여우','fox',19),('구미','fox',19),('다람','squirrel',25),('토끼','rabbit',125),
      ('박쥐','bat',58),('쥐','rat',90),('곰','bear',127),('웅','bear',127),('뱀','snake',26),('백사','snake',26),('독사','snake',26),('살모사','snake',26),('구렁이','snake',26),
      ('사슴','deer',95),('닭','chicken',21),('돼지','pig',20),('소왕','bull',171)]
    def family(name,lev=1):
        for needle,key,model in family_specs:
            if needle in name:return key,model
        return ('guardian',36 if lev<50 else 142)
    def item_profile(v):
        name=v['name'];cat=catalog.get(v['id'],{}).get('item_kind')
        accessory=any(x in name for x in ['반지','팔찌','장갑','부적','선류'])
        helmet=any(x in name for x in ['투구','모자','머리띠'])
        quest=any(x in name for x in ['열쇠','괘','보관증','봉인','영혼','심장','증표'])
        typ='quest' if quest else 'accessory' if accessory else 'armor' if helmet or cat=='armor' else 'weapon' if cat=='weapon' else 'consumable' if any(x in name for x in ['시약','고기','주','비서','산삼']) else 'material'
        slot='weapon' if typ=='weapon' else 'head' if helmet else 'accessory' if typ=='accessory' else 'body' if typ=='armor' else 'none'
        level=known(v,'level_required',50 if any(x in name for x in ['금','용','황금','쇄자']) else 20 if '철' in name else 1)
        return typ,slot,max(0,min(99,level))
    drops=lines(ROOT/'research/restoration-integrated-20261013/DROP_RULES.jsonl');drop_by_mon=collections.defaultdict(list);mon_by_item=collections.defaultdict(set)
    for r in drops:drop_by_mon[r['monster_content_id']].append(r);mon_by_item[r['item_content_id']].add(r['monster_content_id'])
    bindings=load(ROOT/'game/data/runtime_bindings.json')
    def item_visual(v,typ,slot):
        name=v['name'];icon=bindings['icons'].get(name)
        if icon is None:icon=17 if typ=='weapon' else 44 if slot=='body' else 36 if slot in ('head','accessory') else 165 if typ=='consumable' else 214
        vis={'icon_id':asset('sheet.item'),'icon_frame':icon,'identity':'SOURCE_PIXELS_CATEGORY_REPLACEMENT_UNVERIFIED_NAME'}
        if slot=='weapon':vis.update(equipment_asset_id=asset('spear.001' if any(x in name for x in ['창','봉','장']) else 'sword.002'),attachment='ORIGINAL_FOOT_OVERLAY',motion='spear' if any(x in name for x in ['창','봉','장']) else 'sword')
        elif slot=='body':vis.update(equipment_asset_id=asset('body.018' if '포' in name or '삼' in name else 'body.019'),attachment='BODY_REPLACEMENT')
        elif slot=='head':vis.update(equipment_asset_id=asset('head.033'),attachment='HEAD_REPLACEMENT')
        elif slot=='accessory':vis.update(equipment_asset_id=asset('shield.001'),attachment='ORIGINAL_FOOT_OVERLAY')
        return vis
    # Item definitions and guarded fills retain the existing 534 identities.
    item_runtime={}
    for v in bycat['item']:
        typ,slot,level=item_profile(v);stats={k:known(v,k,0) for k in ['hp_bonus','mp_bonus','strength_bonus','dexterity_bonus','intelligence_bonus']}
        stats.update(damage_min=known(v,'damage_min',max(1,2+int(level*.6)) if slot=='weapon' else 0),damage_max=known(v,'damage_max',max(1,4+int(level*.9)) if slot=='weapon' else 0),
          armor_class=known(v,'armor_class',-max(1,round_int(level/3)) if slot in ('body','head','accessory') else 0),durability=known(v,'durability',10000 if slot!='none' else 0))
        stats['damage_max']=max(stats['damage_min'],stats['damage_max'])
        buy=known(v,'vendor_buy_price',known(v,'guide_listed_price',max(5,level*level*12)));sell=known(v,'vendor_sell_price',round_int(buy*.4))
        uses=[];heal=known(v,'heal_amount',max(20,level*20) if typ=='consumable' and any(x in v['name'] for x in ['고기','산삼','붉은','적색']) else 0);mp=known(v,'restore_mp',max(15,level*12) if typ=='consumable' and any(x in v['name'] for x in ['주','푸른','청색']) else 0)
        if heal:uses.append({'op':'heal_hp','amount':heal,'target':'self'})
        if mp:uses.append({'op':'restore_mp','amount':mp,'target':'self'})
        if '비서' in v['name']:uses.append({'op':'teleport_safe_return','destination':'home_city'})
        if typ=='consumable' and not uses:uses.append({'op':'heal_hp','amount':20,'target':'self','inferred':True})
        buyable=typ not in ('quest',) and level<=75
        acq=[{'kind':'monster_drop','monster_id':m,'source_mode':'ORIGINAL_POSSIBILITY_UNKNOWN_RATIO'} for m in sorted(mon_by_item.get(v['id'],()))]
        if not acq and not buyable:
            m=min(bycat['monster'],key=lambda m:(abs(monster_levels[m['id']]-max(20,level)),m['id']))
            acq=[{'kind':'monster_drop','monster_id':m['id'],'source_mode':'INFERRED'}]
            drop_by_mon[m['id']].append({'item_content_id':v['id'],'quantity':1,'probability':.1 if typ=='quest' else .015,'classification':'INFERRED_ACQUISITION_COMPLETION'})
        if buyable:acq.append({'kind':'shop_role','role':'smith' if slot=='weapon' else 'cloth' if slot!='none' else 'grocer','source_mode':'INFERRED'})
        data={'name':v['name'],'item_type':typ,'slot':slot,'requirements':{'level':level,'strength':known(v,'strength_required',0),'class_ids':list(class_ids.values()),'gender':'any'},
          'stats':stats,'stack_limit':1 if slot!='none' else known(v,'stack_limit',99 if typ=='quest' else 100),
          'prices':{'buy':buy,'sell':sell,'unit':'gold','guide_listed_price':v['values'].get('guide_listed_price')},
          'flags':{'obtainable':True,'usable':bool(uses),'buyable':buyable,'sellable':typ!='quest','droppable':typ!='quest','quest_bound':typ=='quest'},
          'use_effects':uses,'visual':item_visual(v,typ,slot),'acquisition':acq,'strength_durability_repair':{'price_multiplier':v['values'].get('repair_multiplier') or .001},
          'historical_status':'KNOWN_FIELDS_PRESERVED_COMPLETION_AND_LOOK_INFERRED'}
        fill={'level_required':level,'strength_required':data['requirements']['strength'],'stack_limit':data['stack_limit'],'vendor_buy_price':buy,'vendor_sell_price':sell,'heal_amount':heal,'restore_mp':mp,**stats}
        r=patch(v,'item',data,'rule.item.complete',fill);item_runtime[v['id']]=data
        r['references']=[ref('icon',data['visual']['icon_id'],{'frame':data['visual']['icon_frame']})]+[ref('class',c) for c in class_ids.values()]
        if 'equipment_asset_id' in data['visual']:r['references'].append(ref('equipment',data['visual']['equipment_asset_id']))
        r['references'] += [ref('acquisition',a['monster_id']) for a in acq if 'monster_id' in a]
    # Resolve missing materials explicitly, using source skill references as origin.
    def ensure_item(name,origin):
        key=norm(name)
        if key in item_ids:return item_ids[key]
        ident=ids.get('item','material.'+origin);item_ids[key]=ident
        data={'name':name,'item_type':'material','slot':'none','requirements':{'level':1,'strength':0,'class_ids':list(class_ids.values()),'gender':'any'},'stats':{'damage_min':0,'damage_max':0,'armor_class':0,'hp_bonus':0,'mp_bonus':0,'strength_bonus':0,'dexterity_bonus':0,'intelligence_bonus':0,'durability':0},'stack_limit':100,
          'prices':{'buy':50,'sell':20,'unit':'gold'},'flags':{'obtainable':True,'usable':False,'buyable':True,'sellable':True,'droppable':True,'quest_bound':False},'use_effects':[],
          'visual':{'icon_id':asset('sheet.item'),'icon_frame':214,'identity':'REPLACEMENT'},'acquisition':[{'kind':'shop_role','role':'grocer','source_mode':'INFERRED'}]}
        add(record(ident,'item',data,['rule.item.complete'],[ref('icon',asset('sheet.item'),{'frame':214})]));item_runtime[ident]=data;return ident
    # Monster behavior, source drop groups and actually usable acquisition paths.
    monster_runtime={}
    for v in bycat['monster']:
        lv=monster_levels[v['id']];xp=known(v,'experience',max(5,known(v,'hp',100)*2));boss=any(x in v['name'] for x in ['왕','대사','장군','용왕','수호','파수꾼'])
        fam,model=family(v['name'],lv);passive=lv<=5 and fam in ('rabbit','squirrel')
        amin=known(v,'attack_min',max(2,round_int(2+lv**1.7/6)));amax=known(v,'attack_max',max(amin,round_int(amin*1.35)))
        hp=known(v,'hp',round_int((25+lv*lv*9+math.sqrt(max(0,xp))*3)*(4 if boss else 1)));respawn=known(v,'respawn_interval_ms',180000 if boss else 30000)
        dg=ids.get('drop_group',v['id']);rolls=[];dedup=set()
        for drop in drop_by_mon.get(v['id'],[]):
            item=drop['item_content_id']
            if item in dedup:continue
            dedup.add(item);typ=item_runtime[item]['item_type'];prob=drop.get('probability')
            prob=(.6 if typ=='material' else .25 if typ=='consumable' else .1 if typ=='quest' else .015) if prob is None else prob
            rolls.append({'item_id':item,'quantity':{'min':max(1,round_int(drop.get('quantity') or 1)),'max':max(1,round_int(drop.get('quantity') or 1))},'probability':ratio(prob),'basis':'rule.drop.complete' if drop.get('probability') is None else 'source_or_explicit_completion'})
        if not rolls:
            iid=ensure_item('도토리','default-acorn')
            rolls=[{'item_id':iid,'quantity':{'min':1,'max':1},'probability':ratio(.1),'basis':'rule.drop.complete'}]
        add(record(dg,'drop_group',{'name':v['name']+' 드롭','mode':'independent','rolls':rolls},['rule.drop.complete'],[ref('drop_item',x['item_id']) for x in rolls]))
        data={'name':v['name'],'level':lv,'hp':max(1,hp),'mp':known(v,'mp',lv*4),'attack':{'min':amin,'max':amax,'interval_ms':known(v,'attack_interval_ms',1200),'kind':'melee' if fam not in ('ghost','dragon') else 'ranged','range_tiles':1 if fam not in ('ghost','dragon') else 5},
          'armor_class':known(v,'armor_class',max(-80,99-lv)),'experience':xp,'gold':max(0,lv*3),
          'behavior':{'aggression':'passive_until_hit' if passive else 'hostile','movement':'wander_and_chase','move_interval_ms':known(v,'move_interval_ms',max(300,900-lv*5)),
            'aggro_radius_tiles':known(v,'aggro_radius_tiles',0 if passive else 6),'leash_radius_tiles':known(v,'leash_radius_tiles',12),'hit_probability':ratio(v['values'].get('hit_probability') if v['values'].get('hit_probability') is not None else .9),
            'special':([{'trigger':'attack_hit','op':'status','status':'poison','duration_ms':10000,'period_ms':2000,'damage':max(1,lv//3),'probability':ratio(.15)}] if fam=='snake' and lv>8 else [])},
          'visual':{'asset_id':asset(f'monster.{model:03d}'),'motion':['walk','attack'],'semantic_match':'SOURCE_FAMILY_REPLACEMENT_INFERRED','palette_variant':0},'drop_group_id':dg,
          'spawn_rules':{'respawn_ms':respawn,'max_live_per_point':1,'boss':boss,'respawn_when':'cooldown_elapsed','persist_death_cooldown':True},'family':fam,'historical_status':'SOURCE_EXPERIENCE_AND_LISTED_DROPS_WITH_AUTHORED_COMBAT'}
        fill={'level':lv,'hp':data['hp'],'mp':data['mp'],'attack_min':amin,'attack_max':amax,'armor_class':data['armor_class'],'experience':xp,'respawn_interval_ms':respawn,'move_interval_ms':data['behavior']['move_interval_ms'],'attack_interval_ms':data['attack']['interval_ms'],'aggro_radius_tiles':data['behavior']['aggro_radius_tiles'],'leash_radius_tiles':data['behavior']['leash_radius_tiles'],'hit_probability':data['behavior']['hit_probability']['numerator']/1000000}
        r=patch(v,'monster',data,'rule.monster.complete',fill);r['references']=[ref('graphic',data['visual']['asset_id']),ref('drops',dg)];monster_runtime[v['id']]=data
    # Source layout conversion uses private bytes, not a public map-data dump.
    d=dat_entries(next(Path(args.inputs).rglob('NWind.dat')).read_bytes());tables={}
    for g in 'ABC':
        ep=Epf(d['tile'+g.lower()+'.epf'][2]);pals=read_palettes(d['tile'+g.lower()+'.pal'][2]);tables[g]=tile_table(d['tile'+g.lower()+'.tbl'][2],ep.count,len(pals))
    objects=static_objects(d['sobj.tbl'][2],tables['C'].count)
    na=Path(args.na_maps);hints={r['original']:(r['width'],r['height']) for r in load(ROOT/'docs/development/runs/20261014-assets/original-world-build.json')['selected_maps']}
    candidates=[];layouts={};map_rejections=[]
    for source in sorted(na.rglob('*.map'),key=lambda p:(len(p.stem),p.stem)):
        mid=int(re.search(r'(\d+)$',source.stem)[1]);raw=source.read_bytes();count=len(raw)//4
        if len(raw)%4:continue
        dim=hints.get(mid)
        if dim is None:
            root=math.isqrt(count)
            if root*root!=count or not 8<=root<=128:continue
            dim=(root,root)
        try:
            cells=map_cells(raw,*dim,tables,objects)
            # Components are original mask15 solid; directional flags remain in file.
            open_cells={(i%dim[0],i//dim[0]) for i,c in enumerate(cells) if c['collision']!=15}
            unseen=set(open_cells);groups=[]
            while unseen:
                st=min(unseen);todo=[st];area={st};unseen.remove(st)
                while todo:
                    x,y=todo.pop()
                    for at in [(x,y-1),(x-1,y),(x,y+1),(x+1,y)]:
                        if at in unseen:unseen.remove(at);area.add(at);todo.append(at)
                groups.append(area)
            area=max(groups,key=len) if groups else set()
            if len(area)<12:continue
            candidates.append((mid,source,dim,cells,area))
        except ValueError as e:map_rejections.append({'original_map_id':mid,'error':str(e),'status':'BLOCKED'})
    if len(candidates)<40:raise ValueError('Not enough independent source layouts for connected content')
    # Keep known low-level geography; additional regions use independent source maps.
    preferred=[0,2,3,11,13,15,17,41,53,55,62,66,100,204,205]
    available={c[0]:c for c in candidates};pool=[available[x] for x in preferred if x in available]+[c for c in candidates if c[0] not in preferred]
    used=set();by_map={};area_by_map={};layout_by_map={};map_defs=[];map_alias={};physical_by_name={}
    def choose(prefer=None,interior=False):
        if prefer in available and prefer not in used:c=available[prefer]
        else:
            options=[c for c in pool if c[0] not in used and (c[2][0]<=40 if interior else c[2][0]>=24)]
            if not options:options=[c for c in pool if c[0] not in used]
            c=options[0]
        used.add(c[0]);return c
    def map_data(name,key,levels,source=None,interior=False):
        c=choose(source,interior);mid,path,(w,h),cells,area=c
        source_key=sha(path.read_bytes());member='layouts/'+str(mid)+'.json'
        layers={'ground':[c['ground_word'] for c in cells],'objects':[c['object_id'] for c in cells]};coll=[c['collision'] for c in cells]
        layout={'width':w,'height':h,'tile_size_px':24,'layers':layers,'collision_masks':coll,'objects_member':'shared/map-format.json','source_map_sha256':source_key,
          'source_dat_sha256':'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7','source_map_id':mid,'coordinate_system':'TOP_LEFT_X_RIGHT_Y_DOWN_ZERO_BASED','raw_ground_words_with_TBL_bases':True}
        write(out/member,layout);layouts[member]=layout
        entry=list(min(area,key=lambda a:(abs(a[0]-w//2)+abs(a[1]-h//2),a[1],a[0])))
        data={'name':name,'width':w,'height':h,'tile_size_px':24,'coordinate_system':'TOP_LEFT_X_RIGHT_Y_DOWN_ZERO_BASED','layers':{'layout_member':member,'tile_sheet_ids':[asset('sheet.tilea'),asset('sheet.tileb'),asset('sheet.tilec')]},'collision':{'layout_member':member,'format':'FOUR_BIT_DIRECTIONAL_MASK','solid_mask':15,'render_object_columns_upwards':True},
          'entry':entry,'portals':[],'spawns':[],'npc_placements':[],'recommended_level':levels,'layout_acquisition':{'bundle_id':args.bundle_id,'member':member,'sha256':file_sha(out/member),'source_original_map_id':mid,'source_sha256':source_key},
          'historical_status':'ORIGINAL_NA495_LAYOUT_WITH_AUTHORED_KR_ROLE','layout_dimensions_basis':'INHERITED_BYTE_VERIFIED' if mid in hints else 'INFERRED_SQUARE_AND_CELL_REFERENCE_VERIFIED','interior':interior}
        by_map[key]=data;area_by_map[key]=area;layout_by_map[key]=layout;map_defs.append(key);return data
    family_map={};category_levels={'rabbit':[1,8],'squirrel':[1,8],'rat':[5,20],'bat':[5,25],'snake':[12,30],'fox':[15,40],'bear':[20,50],'tiger':[20,60],'spider':[30,65],'mantis':[30,65],'scorpion':[35,75],'skeleton':[40,80],'ghost':[50,90],'monkey':[35,85],'north':[60,99],'dragon':[70,99],'chicken':[35,90],'pig':[30,85],'bull':[45,99],'guardian':[50,99],'deer':[55,99]}
    def map_family(name):
        for token,f in [('왕초보','rabbit'),('쥐','rat'),('뱀','snake'),('여우','fox'),('곰','bear'),('호랑','tiger'),('자호','tiger'),('거미','spider'),('사마귀','mantis'),('가재','scorpion'),('전갈','scorpion'),('흑해골','skeleton'),('해골','skeleton'),('귀신','ghost'),('원숭','monkey'),('극지','north'),('소왕','bull'),('닭왕','chicken'),('토끼왕','rabbit'),('도깨비','guardian')]:
            if token in name:return f
        return 'guardian'
    for v in bycat['map']:
        n=norm(v['name']);fam=map_family(v['name']);interior='길드' in v['name'];prefer=15 if '고구려 도적' in v['name'] else 11 if '고구려 전사' in v['name'] else 13 if '고구려 주술사' in v['name'] else 17 if '고구려 도사' in v['name'] else 53 if v['name']=='쥐굴' else 62 if v['name']=='뱀굴' else 66 if v['name']=='곰호랑이굴' else 41 if '왕초보사냥' in v['name'] else None
        if n in physical_by_name:
            primary=physical_by_name[n];data=copy.deepcopy(by_map[primary]);data.update(name=v['name'],variant_group=primary,variant_active=False,identity_note='Same normalized source name, preserve old ID as conditional alias, do not instantiate twice');map_alias[v['id']]=primary
            r=patch(v,'map',data,'rule.map.overlay');r['references']=[ref('map_alias',primary)]+[ref('tile',a) for a in data['layers']['tile_sheet_ids']];identity.append({'kind':'map','alias':v['id'],'primary':primary,'basis':'source name whitespace/slash normalization'});continue
        physical_by_name[n]=v['id'];data=map_data(v['name'],v['id'],[1,99] if interior else category_levels[fam],prefer,interior)
        family_map.setdefault(fam,v['id']);r=patch(v,'map',data,'rule.map.overlay',{'width_tiles':data['width'],'height_tiles':data['height'],'spawn_x':data['entry'][0],'spawn_y':data['entry'][1],'entry_level_requirement':data['recommended_level'][0]});r['references']=[ref('tile',a) for a in data['layers']['tile_sheet_ids']]
    # Two national hubs, advanced regions and each distinct NPC service location.
    city_ids={nation:ids.get('map','city.'+code) for nation,code in [('고구려','goguryeo'),('부여','buyeo')]}
    for nation,mid in city_ids.items():add(record(mid,'map',map_data(nation+' 마을',mid,[1,99],0 if nation=='고구려' else None),['rule.map.overlay'],[ref('tile',a) for a in [asset('sheet.tilea'),asset('sheet.tileb'),asset('sheet.tilec')]]))
    for fam,lev in category_levels.items():
        if fam in family_map:continue
        mid=ids.get('map','region.'+fam);family_map[fam]=mid
        labels={'dragon':'용궁 사냥터','guardian':'십이지신 수련장','squirrel':'초보 들판','bat':'박쥐굴','pig':'돼지 수련장','deer':'사슴 수련장'}
        add(record(mid,'map',map_data(labels.get(fam,fam+' 사냥터'),mid,lev),['rule.map.overlay'],[ref('tile',a) for a in [asset('sheet.tilea'),asset('sheet.tileb'),asset('sheet.tilec')]]))
    loc_maps={};loc_codes={}
    for loc in sorted(npc_by_loc):
        matching=next((mid for name,mid in physical_by_name.items() if name==loc),None)
        if matching:loc_maps[loc]=matching;continue
        if loc in city_ids:loc_maps[loc]=city_ids[loc];continue
        code='facility.'+npc_by_loc[loc][0]['id'].split('.')[-1];mid=ids.get('map',code);loc_maps[loc]=mid;loc_codes[mid]=loc
        data=map_data(npc_by_loc[loc][0]['job'] or '미확정 거점',mid,[1,99],interior=True)
        add(record(mid,'map',data,['rule.map.overlay'],[ref('tile',a) for a in data['layers']['tile_sheet_ids']]))
    # Spawn definitions evenly distribute all source monsters on reachable cells.
    occupied=collections.defaultdict(set)
    for monster_id,data in sorted(monster_runtime.items()):
        mid=family_map.get(data['family'],family_map['guardian']);area=area_by_map[mid]
        picks=sorted(area,key=lambda a:(a[1],a[0]));excluded=occupied[mid]|{tuple(by_map[mid]['entry'])};free=[a for a in picks if a not in excluded]
        if not free:raise ValueError('Insufficient source walkable spawn points')
        at=free[len(free)//2];occupied[mid].add(at)
        count=1 if data['spawn_rules']['boss'] else 2
        by_map[mid]['spawns'].append({'placement_id':ids.get('spawn','monster.'+monster_id),'monster_id':monster_id,'x':at[0],'y':at[1],
          'max_live':count,'radius_tiles':2,'spawn_cells':[list(at)],'respawn_ms':data['spawn_rules']['respawn_ms'],'source_mode':'INFERRED'})
        data['spawn_rules']['region_ids']=[mid];by_effective[monster_id]['references'].append(ref('region',mid))
    shop_ids={};npc_data={};quests_by_npc=collections.defaultdict(list)
    for v in bycat['npc']:
        loc=norm(v['job']);mid=loc_maps[loc];key=norm(v['name'])+'|'+loc;primary=npc_primary[key];active=v['id']==primary
        job=next((j for j in JOBS if j in loc),None);role='trainer' if job and '길드' in loc else 'smith' if '대장' in loc else 'cloth' if any(x in loc for x in ['갑옷','포목']) else 'inn' if '주막' in loc or any(x in v['name'] for x in ['왈숙','연실']) else 'grocer' if '푸줏' in loc else 'revive' if '성황' in loc else 'craft'
        if active:
            area=area_by_map[mid];entry=tuple(by_map[mid]['entry']);free=area-occupied[mid]-{entry}
            at=min(free,key=lambda a:(abs(a[0]-entry[0])+abs(a[1]-entry[1]),a[1],a[0]));occupied[mid].add(at)
            by_map[mid]['npc_placements'].append({'placement_id':ids.get('placement','npc.'+v['id']),'npc_id':v['id'],'x':at[0],'y':at[1],'blocking':False})
            placements=[{'map_id':mid,'x':at[0],'y':at[1]}]
        else:placements=[];identity.append({'kind':'npc','alias':v['id'],'primary':primary,'basis':'same normalized name and source location; no second live service NPC'})
        services=[];model=68 if role=='trainer' else 51 if role=='inn' else 41 if role=='revive' else 67
        if role in ('smith','cloth','grocer','inn','craft'):
            sid=ids.get('shop',v['id']);shop_ids[v['id']]=sid;offers=[]
            for iid,it in sorted(item_runtime.items()):
                if not it['flags']['buyable']:continue
                ok=it['slot']=='weapon' if role=='smith' else it['slot'] in ('body','head','accessory') if role=='cloth' else it['item_type']=='consumable' if role=='inn' else it['slot']=='none'
                if ok:offers.append({'item_id':iid,'price_gold':it['prices']['buy'],'stock':'infinite','requirements':{'min_level':0},'source_mode':'INFERRED_STOCK_SOURCE_PRICE_RETAINED'})
            if not offers:
                iid=ensure_item('도토리','default-acorn');offers=[{'item_id':iid,'price_gold':item_runtime[iid]['prices']['buy'],'stock':'infinite','requirements':{'min_level':0}}]
            add(record(sid,'shop',{'name':v['name']+' '+role,'npc_id':v['id'],'offers':offers,'currency':'gold','sell_policy':{'unit_price_field':'prices.sell','quest_bound':False,'atomic_transaction':True}},['rule.npc.complete'],[ref('owner',v['id'])]+[ref('sale',x['item_id']) for x in offers]));services.append({'type':'shop','shop_id':sid})
        if role=='smith':services.append({'type':'repair','price_multiplier':.001,'max_durability_field':'stats.durability'})
        if role=='trainer':services.append({'type':'learn_skills','class_id':class_ids[job]});services.append({'type':'experience_exchange','economy_id':ids.get('economy','progression')})
        if role=='inn':services.append({'type':'rest','gold_cost':5,'restore_hp':'max','restore_mp':'max'});services.append({'type':'recipe_book','recipe_id':ids.get('recipe','rabbit_meat')})
        if role=='revive':services.append({'type':'revive','gold_cost':0,'hp_fraction':ratio(.25),'mp_fraction':ratio(.25)})
        services.append({'type':'quests','quest_ids':quests_by_npc[v['id']]})
        data={'name':v['name'],'visual':{'asset_id':asset(f'monster.{model:03d}'),'motion':'walk','frame_ms':100,'identity':'ROLE_REPLACEMENT'},
          'dialogue':[{'id':'greeting','text':f"{v['name']}입니다. 필요한 일을 골라 주세요.",'choices':[{'label':{'trainer':'기술 배우기','smith':'장비 구입·수리','cloth':'옷과 장신구 보기','inn':'주막 이용','grocer':'물품 보기','revive':'부활','craft':'재료 교환'}[role],'service_index':0},{'label':'의뢰 확인','service_index':len(services)-1}]}],
          'services':services,'placements':placements,'interaction_range_tiles':known(v,'interaction_range_tiles',2),'role':role,
          'identity_variants':{'primary_id':primary,'active':active,'source_location':v['job'],'selector':'normalized_name_location_once'},'dialogue_source':'AUTHORED_KOREAN_OFFLINE_NOT_HISTORICAL_QUOTE'}
        r=patch(v,'npc',data,'rule.npc.complete',{'local_npc_x':placements[0]['x'] if placements else 0,'local_npc_y':placements[0]['y'] if placements else 0,'interaction_range_tiles':data['interaction_range_tiles'],'move_interval_ms':0})
        r['references']=[ref('graphic',data['visual']['asset_id']),ref('placement_map',mid)]+([ref('variant_primary',primary)] if not active else [])
        npc_data[v['id']]=data
    # All regions/facilities have a reachable return route, not just registration.
    def attach(a,b):
        for src,dest in [(a,b),(b,a)]:
            area=area_by_map[src];used_cells=occupied[src]|{tuple(by_map[src]['entry'])}|{(p['x'],p['y']) for p in by_map[src]['portals']}
            free=area-used_cells
            if not free:raise ValueError('No reachable source portal location')
            at=min(free,key=lambda q:(abs(q[0]-by_map[src]['entry'][0])+abs(q[1]-by_map[src]['entry'][1]),q[1],q[0]))
            by_map[src]['portals'].append({'placement_id':ids.get('portal',src+'.to.'+dest),'x':at[0],'y':at[1],'destination_map_id':dest,'destination_xy':by_map[dest]['entry'],'trigger':'interact','source_mode':'INFERRED'})
    attach(city_ids['고구려'],city_ids['부여'])
    for mid in map_defs:
        if mid in city_ids.values():continue
        nation='부여' if '부여' in by_map[mid]['name'] else '고구려';attach(city_ids[nation],mid)
    # Skills: complete target/effect/resource/animation data for all 199 source IDs.
    skill_by_class=collections.defaultdict(list)
    old_effects=load(ROOT/'game/data/skill_effects.json');skill_primary={}
    for v in sorted(bycat['spell'],key=lambda r:r['id']):skill_primary.setdefault(norm(v['job'])+'|'+norm(v['name']),v['id'])
    for v in bycat['spell']:
        name=v['name'];lv=max(1,min(99,known(v,'learn_level',50)));job=v['job'];jobs=[j for j in JOBS if j in job]
        if not jobs:jobs=JOBS.copy()
        known_effect=old_effects.get(job+':'+name,{})
        effects=[];target='enemy';fx='damage';ranged=6;aoe=known(v,'aoe_radius_tiles',1 if '첨' in name else 0)
        heal=known(v,'heal_amount',max(50,lv*lv*3) if any(x in name for x in ['기원','희원']) else 0)
        damage=known(v,'base_damage',max(20,lv*lv*5))
        if any(x in name for x in ['기원','희원']):effects=[{'op':'heal_hp','amount':max(1,heal),'scale':'flat'}];target='self_or_ally';fx='heal'
        elif name=='해독':effects=[{'op':'remove_status','status':'poison'}];target='self_or_ally';fx='buff'
        elif '공력증강' in name:effects=[{'op':'restore_mp','fraction':ratio(.5)}];target='self';fx='buff'
        elif any(x in name for x in ['비영사천문','귀환','출두','소환','비영승보']):
            effects=[{'op':'teleport','mode':'directional_town_gate' if '비영' in name and '승보' not in name else 'home_city' if '귀환' in name else 'adjacent_enemy' if '승보' in name else 'safe_region_entry','offline_replacement':name in ('출두','소환')}];target='self';fx='buff'
        elif '성황령'==name:effects=[{'op':'teleport','mode':'revival_npc','requires_ghost':True}];target='self';fx='buff'
        elif '감정' in name:effects=[{'op':'inspect_item'}];target='inventory_item';fx='buff'
        elif any(x in name for x in ['무장','보호','차폐','힘','보법','신검','대력','백호령','공격','경수','금수','빛','축복']):
            status='armor' if any(x in name for x in ['무장','차폐']) else 'damage_reduction' if '보호' in name else 'strength' if '힘' in name else 'invisibility' if '보법' in name else 'light' if '빛' in name else 'transform' if name in ('경수','금수') else 'attack_multiplier'
            effects=[{'op':'apply_status','status':status,'magnitude':max(1,lv//5),'stack':'refresh_duration'}];target='self';fx='buff'
        elif any(x in name for x in ['중독','마비','혼돈','절망','망각','저주','파혼','혼마']):
            status='poison' if '독' in name else 'stun' if '마비' in name else 'blind' if '절망' in name else 'confuse' if '혼돈' in name else 'armor_debuff'
            effects=[{'op':'apply_status','status':status,'magnitude':max(1,lv//5),'stack':'refresh_duration'}];fx='poison'
        elif any(x in name for x in ['부활','활인']):effects=[{'op':'revive','hp_fraction':ratio(.25),'mp_fraction':ratio(.1)}];target='self_or_ally';fx='heal'
        elif '사자후' in name:effects=[{'op':'local_message','channel':'offline_world'}];target='self';fx='buff'
        else:
            fx='fire' if any(x in name for x in ['화','불','헬']) else 'lightning' if any(x in name for x in ['뢰','풍']) else 'damage'
            effects=[{'op':'damage','amount':max(1,damage),'scale':'flat','element':fx}]
            if any(x in name for x in ['검무','비무','검귀','어검','백호']):effects[0]['scale']='flat_plus_current_hp_fraction';effects[0]['hp_fraction']=ratio(.5);ranged=1
        # Source confirmed 0 damage must not turn an offensive completion into 0.
        if known_effect.get('op')=='damage' and effects and effects[0]['op']=='damage' and damage==0:effects[0]['amount']=known_effect.get('damage',max(20,lv*lv*5))
        materials=[]
        for k,qty in v['values'].items():
            if k.startswith('learn_materials.') and k.endswith('.quantity') and qty:
                mn=k[len('learn_materials.'):-len('.quantity')];iid=ensure_item(mn,v['id'].split('.')[-1]+'.'+str(len(materials)))
                materials.append({'item_id':iid,'quantity':max(1,round_int(qty))})
        duration=known(v,'duration_ms',30000 if any(e['op']=='apply_status' for e in effects) else 0)
        fnum=bindings['skill_effects'][fx];aid=asset(f'effect.{fnum:03d}')
        data={'name':name,'class_ids':[class_ids[j] for j in jobs],
          'learn':{'level':lv,'money':known(v,'learn_money',lv*20),'experience_cost':known(v,'learn_experience_cost',0),'consume':materials,'teacher_npc_ids':[teachers[j] for j in jobs],'rank':0,'once':True},
          'target':target,'range_tiles':known(v,'range_tiles',ranged),'aoe_radius_tiles':aoe,'effects':effects,
          'cost':{'mp':known(v,'cast_mp',max(1,lv//2)),'hp':known(v,'cast_hp',0),'hp_fraction':ratio(v['values'].get('cast_hp_fraction') or 0),'prevent_suicide':True},
          'cooldown_ms':known(v,'cooldown_ms',4000 if lv>=70 and target=='enemy' else 1000),'duration_ms':duration,
          'success_ratio':ratio(v['values'].get('success_probability') if v['values'].get('success_probability') is not None else 1),
          'animation':{'effect_asset_id':aid,'body_motion':'cast','direction_order':['N','W','S','E'],'impact_delay_ms':160,'front_back_order':'SOURCE_TABLE','sound_asset_id':asset('sound.003') if 'wk.asset.kr491.sound.003' in assets else next(a for a in assets if '.sound.' in a)},
          'historical_status':'SOURCE_LEARN_VALUES_AND_KNOWN_EFFECT_FIELDS_WITH_AUTHORED_COMPLETION','variant':{'primary_id':skill_primary[norm(job)+'|'+norm(name)],'role':'primary' if skill_primary[norm(job)+'|'+norm(name)]==v['id'] else 'source_variant','activation':'same_named_skill_variant_selection'}}
        fill={'learn_level':lv,'learn_money':data['learn']['money'],'learn_experience_cost':data['learn']['experience_cost'],'cast_mp':data['cost']['mp'],'cast_hp':data['cost']['hp'],'cast_hp_fraction':v['values'].get('cast_hp_fraction') or 0,'base_damage':effects[0].get('amount',0) if effects[0]['op']=='damage' else 0,'heal_amount':heal,'range_tiles':data['range_tiles'],'aoe_radius_tiles':aoe,'duration_ms':duration,'cooldown_ms':data['cooldown_ms'],'success_probability':data['success_ratio']['numerator']/1000000}
        r=patch(v,'skill',data,'rule.skill.complete',fill);r['references']=[ref('effect',aid),ref('sound',data['animation']['sound_asset_id'])]+[ref('class',c) for c in data['class_ids']]+[ref('teacher',x) for x in data['learn']['teacher_npc_ids']]+[ref('material',x['item_id']) for x in materials]
        for j in jobs:skill_by_class[j].append(v['id'])
    # Growth table is start-of-level cumulative XP, with explicit terminal row.
    growth_by_class=collections.defaultdict(list)
    for j in JOBS:
        rows=sorted([v for v in bycat['growth'] if v['job']==j],key=lambda v:v['level']);previous=0
        for v in rows:
            lv=v['level'];terminal=lv==99;to_next=0 if terminal else known(v,'exp_band_to_next',max(300,round_int(lv**3*100)))
            hpmin=known(v,'hp_gain_min',40);hpmax=known(v,'hp_gain_max_inclusive',hpmin);mpmin=known(v,'mp_gain_min',20);mpmax=known(v,'mp_gain_max_inclusive',mpmin)
            data={'name':v['name'],'class_id':class_ids[j],'level':lv,'terminal':terminal,'exp_to_next':to_next,'cumulative_exp':previous,
              'hp_gain':{'min':hpmin,'max':hpmax,'selection':'uniform_inclusive'},'mp_gain':{'min':mpmin,'max':mpmax,'selection':'uniform_inclusive'},'base_armor_class':known(v,'base_armor_class',max(0,100-lv)),
              'source_class_scope':j,'no_level_100':True}
            r=patch(v,'growth',data,'rule.growth.complete',{'base_armor_class':data['base_armor_class']});r['references']=[ref('class',class_ids[j])];growth_by_class[j].append(v['id'])
            previous=known(v,'cumulative_exp_to_next',previous+to_next) if not terminal else previous
    # Preserve novice source rows as conditional global phase, not a fifth full job.
    novice_id=ids.get('class','novice')
    for v in bycat['growth']:
        if v['job']!='평민':continue
        lv=v['level'];data={'name':v['name'],'class_id':novice_id,'level':lv,'terminal':False,'exp_to_next':known(v,'exp_band_to_next',300),
          'cumulative_exp':known(v,'cumulative_exp_to_next',300)-known(v,'exp_band_to_next',300),'hp_gain':{'min':known(v,'hp_gain_min',45),'max':known(v,'hp_gain_max_inclusive',55)},'mp_gain':{'min':known(v,'mp_gain_min',32),'max':known(v,'mp_gain_max_inclusive',36)},'base_armor_class':known(v,'base_armor_class',100-lv),'phase':'pre_job_levels_1_5'}
        r=patch(v,'growth',data,'rule.growth.complete');r['references']=[ref('class',novice_id)];growth_by_class['평민'].append(v['id'])
    # Guild services make every source skill and advancement reachable.
    for j,npc in teachers.items():
        service=next(s for s in npc_data[npc]['services'] if s['type']=='learn_skills');service['skill_ids']=skill_by_class[j]
    advancement_by_class=collections.defaultdict(list);advance_quests=[]
    for v in bycat['advancement']:
        j=v['job'];rank=known(v,'rank',1);qid=ids.get('quest','advancement.'+JOBKEY[j]+'.'+str(rank));advance_quests.append(qid)
        lower=[a for a in bycat['advancement'] if a['job']==j and a['values']['rank']==rank-1];higher=[a for a in bycat['advancement'] if a['job']==j and a['values']['rank']==rank+1]
        data={'name':v['name'],'class_id':class_ids[j],'rank':rank,'conditions':{'level':99,'max_hp':known(v,'hp_required',rank*50000),'max_mp':known(v,'mp_required',0 if j=='전사' else 90000 if j=='도적' else rank*50000),'previous_rank':rank-1},'npc_id':teachers[j],'quest_id':qid,
          'granted_skill_ids':[sid for sid in skill_by_class[j] if by_effective[sid]['data']['learn']['level']==99][:rank],'next_rank_id':higher[0]['id'] if higher else None,'historical_status':'SOURCE_THRESHOLDS_WITH_OFFLINE_SOLO_QUEST'}
        r=patch(v,'advancement',data,'rule.advancement.offline',{'mp_required':data['conditions']['max_mp']});r['references']=[ref('class',class_ids[j]),ref('npc',teachers[j]),ref('quest',qid)]+[ref('skill',s) for s in data['granted_skill_ids']]+([ref('next_rank',data['next_rank_id'])] if data['next_rank_id'] else [])
        advancement_by_class[j].append(v['id']);material=ensure_item('웅담','advancement-bear');bosses=[m for m,d in monster_runtime.items() if d['spawn_rules']['boss'] and d['level']>=70]
        boss=sorted(bosses,key=lambda m:(monster_runtime[m]['level'],m))[min(rank-1,len(bosses)-1)]
        quest={'name':v['name']+' 승급 의뢰','start_npc_id':teachers[j],'complete_npc_id':teachers[j],'requirements':{'level':99,'class_ids':[class_ids[j]],'advancement_rank':rank-1,'max_hp':data['conditions']['max_hp'],'max_mp':data['conditions']['max_mp']},
          'prerequisites':[ids.get('quest','advancement.'+JOBKEY[j]+'.'+str(rank-1))] if rank>1 else [],'objectives':[{'type':'kill','monster_id':boss,'count':rank},{'type':'collect','item_id':material,'count':rank*5}],
          'consume':[{'item_id':material,'quantity':rank*5}],'rewards':[{'type':'advancement','advancement_id':v['id']}],'repeat':{'mode':'once','cooldown_ms':0,'occurrence_counter':False},'completion_key':qid,'extension':True,'source_mode_note':'AUTHORED_OFFLINE_SOLO_REQUIREMENTS'}
        add(record(qid,'quest',quest,['rule.advancement.offline'],[ref('start',teachers[j]),ref('end',teachers[j]),ref('boss',boss),ref('material',material),ref('rank',v['id'])]+[ref('prior_quest',q) for q in quest['prerequisites']]));quests_by_npc[teachers[j]].append(qid)
    for j in JOBS:
        jobidx=JOBS.index(j);body,head,tint=bindings['players'][jobidx]
        data={'name':j,'starter':{'level':1,'hp':50,'mp':35,'gold':30,'selected_job_applies_from_level':6,'novice_growth_ids':growth_by_class['평민'],'starter_item_ids':[item_ids[norm('목도')]],'basic_attack_interval_ms':600},'growth_ids':growth_by_class[j],'skill_ids':skill_by_class[j],'advancement_ids':advancement_by_class[j],
          'visual':{'body_asset_id':asset(f'body.{body:03d}'),'head_asset_id':asset(f'head.{head:03d}'),'source_recolor_parameter':tint,'rendered_palette_variant':0,'recolor_not_applied_to_bundle':True,'draw_order':'SOURCE_DRWORDER_TABLE_REQUIRED'},'growth_start_level':1}
        add(record(class_ids[j],'class',data,['rule.growth.complete'],[ref('body',data['visual']['body_asset_id']),ref('head',data['visual']['head_asset_id'])]+[ref('growth',g) for g in data['growth_ids']]+[ref('skill',s) for s in data['skill_ids']]+[ref('advancement',s) for s in data['advancement_ids']]))
    add(record(novice_id,'class',{'name':'평민 성장 단계','starter':{'hp':50,'mp':35,'level':1},'growth_ids':growth_by_class['평민'],'skill_ids':[],'advancement_ids':[],'visual':{'body_asset_id':asset('body.002'),'head_asset_id':asset('head.000')},'growth_start_level':1,'growth_end_level':5,'phase_only':True},['rule.growth.complete'],[ref('growth',g) for g in growth_by_class['평민']]))
    # Independent regional quests; the existing starter two quests are retained.
    guide=teachers['전사'];quest_ids=[]
    for fam,mid in sorted(family_map.items()):
        mons=sorted([m for m,d in monster_runtime.items() if d['family']==fam],key=lambda m:(monster_runtime[m]['level'],m))
        if not mons:continue
        monster=mons[len(mons)//2];material=next(iter(drop_by_mon[monster]),{}).get('item_content_id',item_ids[norm('도토리')]);lv=monster_runtime[monster]['level'];qid=ids.get('quest','hunt.'+fam)
        reward_candidates=[(iid,it) for iid,it in item_runtime.items() if it['slot']!='none' and it['requirements']['level']<=lv and it['flags']['obtainable']]
        reward_item=max(reward_candidates,key=lambda t:(t[1]['requirements']['level'],t[0]))[0]
        data={'name':by_map[mid]['name']+' 토벌 의뢰','start_npc_id':guide,'complete_npc_id':guide,'requirements':{'level':max(1,lv-10),'class_ids':list(class_ids.values())},'prerequisites':[],
          'objectives':[{'type':'kill','monster_id':monster,'count':5,'map_id':mid},{'type':'collect','item_id':material,'count':3},{'type':'talk','npc_id':guide,'count':1,'after_other_objectives':True}],
          'consume':[{'item_id':material,'quantity':3}],'rewards':[{'type':'experience','amount':monster_runtime[monster]['experience']*3},{'type':'gold','amount':max(20,lv*10)},{'type':'item','item_id':reward_item,'quantity':1}],
          'repeat':{'mode':'once','cooldown_ms':0,'occurrence_counter':False},'completion_key':qid,'extension':True}
        add(record(qid,'quest',data,['rule.quest.offline'],[ref('giver',guide),ref('area',mid),ref('kill',monster),ref('collect',material),ref('reward',reward_item)]));quests_by_npc[guide].append(qid);quest_ids.append(qid)
    daily=ids.get('quest','daily.rabbit');rabbit=next(m for m,d in monster_runtime.items() if d['name']=='토끼');acorn=item_ids[norm('도토리')]
    add(record(daily,'quest',{'name':'매일 들판 돌보기','start_npc_id':guide,'complete_npc_id':guide,'requirements':{'level':1},'prerequisites':[],'objectives':[{'type':'kill','monster_id':rabbit,'count':10}],'consume':[],'rewards':[{'type':'gold','amount':50},{'type':'item','item_id':acorn,'quantity':5}],
      'repeat':{'mode':'cooldown','cooldown_ms':86400000,'occurrence_counter':True,'clock':'saved_monotonic_elapsed_time_no_wallclock_reward_duplication'},'completion_key':daily,'extension':True},['rule.quest.offline'],[ref('giver',guide),ref('kill',rabbit),ref('reward',acorn)]));quests_by_npc[guide].append(daily)
    # A real consumable recipe and optional, explicitly nonhistorical enhancement.
    cook=ids.get('recipe','rabbit_meat');inn_npc=next(v['id'] for v in bycat['npc'] if npc_data[v['id']]['role']=='inn');meat=item_ids[norm('토끼고기')]
    add(record(cook,'recipe',{'name':'토끼고기 손질','npc_id':inn_npc,'consume':[{'item_id':meat,'quantity':2}],'outputs':[{'item_id':meat,'quantity':1,'item_instance_modifier':{'heal_multiplier':2,'prepared':True}}],'gold_cost':5,'success_ratio':ratio(1),'extension':True},['rule.quest.offline'],[ref('cook',inn_npc),ref('ingredient',meat),ref('result',meat)]))
    rate=[.9,.85,.8,.75,.65,.55,.45,.35,.25,.15];material=ensure_item('철','enhancement-iron');enh=ids.get('enhancement','offline_optional')
    stages=[]
    for level,p in enumerate(rate,1):
        fail=round_int((1-p)*1000000);down=0 if level<=4 else fail if level<=8 else fail//2;destroy=0 if level<=8 else fail//4;retain=fail-down-destroy
        stages.append({'level':level,'cost':{'gold':level*level*100,'materials':[{'item_id':material,'quantity':level}]},'stat_modifier':{'weapon_damage_bonus':level*2,'armor_class_delta':-level,'hp_bonus':level*10},
          'outcomes':[{'result':'success','probability':ratio(p),'new_level':level},{'result':'retain','probability':{'numerator':retain,'denominator':1000000},'new_level':level-1},{'result':'downgrade','probability':{'numerator':down,'denominator':1000000},'new_level':max(0,level-2)},{'result':'destroy','probability':{'numerator':destroy,'denominator':1000000},'destroy_instance':True}],
          'failure_state':'No stat application on failed result; consume costs once per transaction'})
    eligible=[iid for iid,d in item_runtime.items() if d['slot']!='none']
    add(record(enh,'enhancement',{'name':'개인용 선택 강화','extension':True,'default_enabled':False,'applicable_item_ids':eligible,'stages':stages,'instance_state':'upgrade_level=0..10; effective stats computed from immutable base'},['rule.enhancement.extension'],[ref('material',material)]+[ref('eligible_item',i) for i in eligible]))
    econ=ids.get('economy','progression')
    add(record(econ,'economy',{'name':'개인용 금전·99레벨 경험치 교환','currency':'gold','vendor_rules':{'sell':'item prices.sell','rounding':'HALF_AWAY_FROM_ZERO','overflow_limit':9007199254740991,'atomic_transactions':True,'no_negative_balance':True,'quest_bound_sell':False},
      'experience_exchange':{'level_required':99,'npc_ids':list(teachers.values()),'cost_xp':1000000,'level_preserved':True,'options':[{'stat':'max_hp','amount':100},{'stat':'max_mp','amount':50}],'max_stat_cap':2000000,'original_formula_confirmed':False}},['rule.advancement.offline'],[ref('npc',n) for n in teachers.values()]))
    # Attach service IDs after every definition exists, and refresh guarded value.
    for r in records:
        data=r['data']
        if r['kind']=='map' and r.get('target_id',r['id']) in by_map:
            r['data']=by_map[r.get('target_id',r['id'])];data=r['data']
            r['references'] += [ref('spawn',s['monster_id']) for s in data['spawns']]+[ref('npc',n['npc_id']) for n in data['npc_placements']]+[ref('portal',p['destination_map_id']) for p in data['portals']]
        if r['kind']=='npc':
            r['references'] += [ref('shop',s['shop_id']) for s in data['services'] if 'shop_id' in s]+[ref('recipe',s['recipe_id']) for s in data['services'] if 'recipe_id' in s]+[ref('quest',q) for s in data['services'] for q in s.get('quest_ids',[])]+[ref('class',s['class_id']) for s in data['services'] if 'class_id' in s]+[ref('economy',s['economy_id']) for s in data['services'] if 'economy_id' in s]
        if r['operation']=='propose_patch':r['changes'][0]['after']=copy.deepcopy(r['data'])
    # Late supplemental materials are available from the actual grocer offers.
    offered={o['item_id'] for r in records if r['kind']=='shop' for o in r['data']['offers']}
    grocery=next(r for r in records if r['kind']=='shop' and npc_data[r['data']['npc_id']]['role'] in ('grocer','craft'))
    for iid,it in item_runtime.items():
        if iid not in offered and it['flags']['buyable']:
            grocery['data']['offers'].append({'item_id':iid,'price_gold':it['prices']['buy'],'stock':'infinite','requirements':{'min_level':0},'source_mode':'INFERRED_ACQUISITION_COMPLETION'})
            grocery['references'].append(ref('sale',iid))
    write(out/'shared/map-format.json',{'objects':objects,'tile_tables':{g:{'base':tables[g].base,'kind':tables[g].kind,'count':tables[g].count,'sheet_asset_id':asset('sheet.tile'+g.lower())} for g in tables},
      'draw_order':entries_draw_order(d),'source_dat_sha256':'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7','alpha':'EPF_STENCIL','object_column_direction':'BOTTOM_UP'})
    # Cross-package provenance is explicit; rule.visual.binding lives in assets.
    write(package/'provenance.json',rules);shard(package,records)
    write(out/'PRIVATE_MANIFEST.json',{'protocol_id':'BARAM_PARALLEL_V1','bundle_id':args.bundle_id,'files':[{'path':str(p.relative_to(out)),'size_bytes':p.stat().st_size,'sha256':file_sha(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.name!='PRIVATE_MANIFEST.json'],'source':'Pinned NA495 layouts, gameplay overlays live in public declarative package'})
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():
                zi=zipfile.ZipInfo(str(p.relative_to(out)),(2026,10,14,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o100644<<16;z.writestr(zi,p.read_bytes())
    bundle=Path(args.bundle);bundle.write_bytes(buf.getvalue())
    with zipfile.ZipFile(bundle) as z:
        if z.testzip() is not None:raise ValueError('Private map bundle CRC')
    write(package/'acquisition.json',{'bundle_id':args.bundle_id,'file_name':bundle.name,'size_bytes':bundle.stat().st_size,'sha256':file_sha(bundle),'library_file_id':None,'privacy':'PRIVATE_ONLY','work_acquisition':'PASS_ACTUAL_BYTES_AND_CRC','recipient_acquisition':'NOT_RUN','rebuild':{'tool':'content-work/tools/build_content.py','sha256':file_sha(Path(__file__)),'base_game_commit':BASE,'source_map_set':'NA495','asset_dependency':'WK-ASSETS-001'}})
    write(WORK/'catalog/content-build.json',{'batch_id':args.batch,'counts':dict(collections.Counter(r['kind'] for r in records)),'operations':dict(collections.Counter(r['operation'] for r in records)),'guarded_null_fill_fields':null_fills,
      'existing_numeric_id_count':len(base),'completed_existing_id_count':sum(r['operation']=='propose_patch' for r in records),'new_identity_count':sum(r['operation']=='add' for r in records),
      'physical_map_definitions':len(by_map),'original_layout_sources':len(layouts),'unique_source_layout_hashes':len({r['source_map_sha256'] for r in layouts.values()}),'tile_placements':sum(x['width']*x['height'] for x in layouts.values()),
      'spawn_points':sum(len(m['spawns']) for m in by_map.values()),'max_live_monsters':sum(s['max_live'] for m in by_map.values() for s in m['spawns']),
      'NPC_placements':sum(len(m['npc_placements']) for m in by_map.values()),'portals':sum(len(m['portals']) for m in by_map.values()),'identity_aliases':identity,
      'source_candidate_layouts':len(candidates),'source_map_rejections':map_rejections,'new_quest_count':len(advance_quests)+len(quest_ids)+1,'enhancement_default_enabled':False,'gameplay':'NOT_RUN'})
    write(WORK/'catalog/content-identity-aliases.json',identity);ids.save()
    print('BUILT',len(records),'records',null_fills,'conditional null fills',len(by_map),'maps',flush=True)
def entries_draw_order(entries):return [x for x in entries['drworder.tbl'][2].decode('ascii').strip().split(';') if len(x)==4]

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['batch','inputs','na-maps','private-out','bundle-id','bundle']:p.add_argument('--'+k,required=True)
    build(p.parse_args())
