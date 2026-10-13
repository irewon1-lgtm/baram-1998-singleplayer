#!/usr/bin/env python3
"""Build field-level production drafts, source observations, and explicit gaps.

This is a data compiler. It does not implement combat, simulate play, or prove
the production assumptions reproduce an original Korean server.
"""
import argparse, collections, csv, datetime, hashlib, json, math, re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/restoration-integrated-20261013';KR=ROOT/'research/korean-history-20261013'
CLASSES={0:'평민',1:'전사',2:'도적',3:'주술사',4:'도사'}

def readl(path):return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
def writej(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def writel(name,rows):(OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
def norm(s):return re.sub(r'\s+','',s or '')
def number(s):
    try:return float(s) if '.' in str(s) else int(s)
    except (ValueError,TypeError):return None
def shortid(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:16]

FIELDS={
 'monster':{'level':'level','hp':'HP','mp':'MP','attack_min':'damage','attack_max':'damage','armor_class':'AC','experience':'XP','move_interval_ms':'ms','attack_interval_ms':'ms','respawn_interval_ms':'ms','aggro_radius_tiles':'tile','leash_radius_tiles':'tile','hit_probability':'probability'},
 'item':{'level_required':'level','strength_required':'stat','durability':'durability_point','vendor_buy_price':'전','vendor_sell_price':'전','repair_multiplier':'ratio','damage_min':'damage','damage_max':'damage','armor_class':'AC','hp_bonus':'HP','mp_bonus':'MP','strength_bonus':'stat','dexterity_bonus':'stat','intelligence_bonus':'stat','stack_limit':'count','heal_amount':'HP','restore_mp':'MP'},
 'spell':{'learn_level':'level','learn_money':'전','cast_mp':'MP','cast_hp':'HP','cast_hp_fraction':'ratio','base_damage':'damage','heal_amount':'HP','range_tiles':'tile','aoe_radius_tiles':'tile','duration_ms':'ms','cooldown_ms':'ms','success_probability':'probability','learn_experience_cost':'XP'},
 'npc':{'local_npc_x':'tile','local_npc_y':'tile','interaction_range_tiles':'tile','move_interval_ms':'ms'},
 'map':{'width_tiles':'tile','height_tiles':'tile','spawn_x':'tile','spawn_y':'tile','entry_level_requirement':'level'},
 'growth':{'cumulative_exp_to_next':'XP','exp_band_to_next':'XP','hp_gain_min':'HP','hp_gain_max_inclusive':'HP','mp_gain_min':'MP','mp_gain_max_inclusive':'MP','base_armor_class':'AC'},
 'advancement':{'rank':'rank','hp_required':'HP','mp_required':'MP'},
}
EXTRA_UNITS={'guide_listed_price':'전','learn_materials':'count','drop_probability':'probability','armor_delta':'AC','strength_bonus':'stat','initial_hp_min':'HP','initial_hp_max':'HP','initial_mp_min':'MP','initial_mp_max':'MP','initial_stat':'stat'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--private-dir',required=True);a=p.parse_args();private=Path(a.private_dir)
    p1998=private/'repos/project1998/Project1998';data=p1998/'game-data';tables={};filehash={}
    def csvtable(name):
        if name not in tables:
            file=data/name;filehash[name]=hashlib.sha256(file.read_bytes()).hexdigest()
            with file.open(encoding='utf-8-sig') as f:tables[name]=list(csv.DictReader(f))
        return tables[name]
    catalogs=readl(OUT/'CONTENT_CATALOG.jsonl');catalog={r['content_id']:r for r in catalogs}
    bykey={(r['category'],norm(r['name']),r.get('class_scope') or ''):r for r in catalogs if r['namespace']=='KR'}
    original=readl(KR/'facts.jsonl');reviewed=readl(OUT/'VERIFIED_CANDIDATE_FACTS.jsonl');supplement=readl(OUT/'GAP_SUPPLEMENT_FACTS.jsonl')
    records=original+reviewed+supplement;facts_by_entity=collections.defaultdict(list);observations=[];observation_by_id={};obs=collections.defaultdict(list)
    sources={r['id']:r for r in json.loads((KR/'sources.json').read_text())}
    def source(source_id,name,path,kind='EXTERNAL_RESTORATION',region='NA'):
        sources.setdefault(source_id,dict(id=source_id,kind=kind,game_region=region,publication_date=None,actual_game_period=None,
            game_version='RESTORATION_PIN_2026' if kind=='EXTERNAL_RESTORATION' else None,
            original_url='https://github.com/project1998/Project1998/blob/36905428ff59329be28c6a4579e41f4fd9e9a967/'+path if kind=='EXTERNAL_RESTORATION' else None,
            file=path,sha256=filehash.get(name),rights='NO_ROOT_LICENSE_REFERENCE_FACTS_ONLY' if kind=='EXTERNAL_RESTORATION' else 'INDEPENDENT_PRODUCTION_ASSUMPTION',raw_bytes_public=False))
    def observe(content,field,value,record_id,source_id,position,year=None,kind='KR_CONFIRMED',raw_token=None,conversion=None):
        if value is None or isinstance(value,(str,dict,list)):return None
        oid='OBS-'+shortid([content['content_id'],record_id,field])
        r=dict(observation_id=oid,content_id=content['content_id'],content_name=content['name'],field=field,original_value=value,unit=FIELDS.get(content['category'],{}).get(field,EXTRA_UNITS.get(field,'count' if field.endswith('.quantity') else 'UNCLASSIFIED')),
               record_id=record_id,source_id=source_id,source_url=sources.get(source_id,{}).get('final_url') or sources.get(source_id,{}).get('original_url'),
               source_sha256=sources.get(source_id,{}).get('sha256'),position=position,year=year,kind=kind,original_token=raw_token,
               publication_date=sources.get(source_id,{}).get('publication_date'),capture_timestamp=sources.get(source_id,{}).get('capture_timestamp'),
               actual_game_period=None,game_version=sources.get(source_id,{}).get('game_version'),conversion=conversion,game_runtime_verified=False)
        if raw_token is not None and number(raw_token) is not None:
            r['literal_source_numeric_value']=number(raw_token)
        if conversion:r['normalized_value']=value
        observations.append(r);observation_by_id[oid]=r;obs[(content['content_id'],field)].append(r);return r
    def content_for(r):
        cat={'map_site':'map'}.get(r['category'],r['category']);scope=r.get('class_scope') or r['fields'].get('class')
        if cat=='npc':scope=r['fields'].get('guide_location') or r['fields'].get('nation')
        key=(cat,norm(r['name']),scope or '')
        c=bykey.get(key)
        if c is None:
            # Do not silently infer the class of an unscoped historical skill.
            c=dict(content_id='kr.'+cat+'.'+shortid(key),category=cat,name=r['name'],class_scope=scope,namespace='KR',original_game_id=None,record_ids=[],versions=[],selection='CANDIDATE',game_implemented=False)
            catalog[c['content_id']]=c;bykey[key]=c
        if r['id'] not in c['record_ids']:c['record_ids'].append(r['id'])
        return c
    for r in records:
        c=content_for(r);facts_by_entity[c['content_id']].append(r)
        for field,value in r['fields'].items():
            if type(value) not in [int,float,bool]:continue
            if field not in FIELDS.get(c['category'],{}) and field not in EXTRA_UNITS:continue
            observe(c,field,value,r['id'],r['source_id'],r['position'],r['year'],raw_token=r.get('source_numeric_tokens',{}).get(field))
        if c['category']=='spell':
            for material in r['fields'].get('learn_materials') or []:
                if material.get('quantity') is not None:observe(c,'learn_materials.'+norm(material['name'])+'.quantity',material['quantity'],r['id'],r['source_id'],r['position'],r['year'])
        # Split endpoint ranges; never mistake an advisory hunting range for an entrance restriction.
        if c['category']=='item':
            for old,new in [('price','guide_listed_price')]:
                if type(r['fields'].get(old)) in [int,float]:observe(c,new,r['fields'][old],r['id']+':'+old,r['source_id'],r['position'],r['year'])
    # These magazine facts explicitly name the warrior spells; link them without
    # conflating learning gold, learning level or cast MP.
    for r in original:
        if r['id'] in ['KR-2000-0256','KR-2000-0257','KR-2000-0258']:
            skill=r['name'].removesuffix(' 마력');c=bykey.get(('spell',norm(skill),'전사'))
            if c:observe(c,'cast_mp',r['fields']['cast_mp'],r['id'],r['source_id'],r['position'],r['year'])
    # Preserve the five already authorized mixed-profile observations, including patch-before/after numbers.
    old_averages=json.loads((KR/'IMPLEMENTATION_AVERAGES.json').read_text())['values']
    overrides={}
    for average in old_averages:
        key=(average['category'],norm(average['name']),average.get('class_scope') or '');c=bykey.get(key)
        if not c:continue
        for i,o in enumerate(average['observations']):
            observe(c,average['field'],o['value'],average['id']+':'+str(i),o['source_id'],o['position'],o['year'])
        overrides[(c['content_id'],average['field'])]=average
    # Explicit 1999 receipt documents the NPC's purchase of acorns, not both price directions.
    acorn=bykey.get(('item','도토리',''))
    if acorn:
        for r in original:
            v=r['fields']
            if v.get('item')=='도토리' and type(v.get('unit_sale_price_derived')) in [int,float]:
                observe(acorn,'vendor_sell_price',v['unit_sale_price_derived'],r['id'],r['source_id'],r['position'],r['year'],conversion='receipt_total / sold_quantity')
    # External replacements are admitted only on these explicitly documented correspondence candidates.
    correspondences={('monster','토끼'):'rabbit',('monster','다람쥐'):'squirrel',('monster','시궁쥐'):'sewer_rat',('monster','박쥐'):'bat',('monster','병든쥐'):'sick_rat',('monster','흡혈쥐'):'vampire_rat',('monster','서생원'):'rat_boss',('item','목도'):'wooden_saber',('item','목검'):'wooden_sword',('item','도토리'):'acorn',('item','토끼고기'):'rabbit_meat'}
    external_by_cat={}
    for name,cat,keycol in [('mobs.csv','monster','Identifier'),('Items.csv','item','ItmIdentifier')]:
        rs=csvtable(name);external_by_cat[cat]={row[keycol]:(i,row) for i,row in enumerate(rs,2)}
        source('P1998-'+name,name,'game-data/'+name)
    fieldmap={'monster':{'Vita':'hp','Exp':'experience','Level':'level','MinDmg':'attack_min','MaxDmg':'attack_max','MobArmor':'armor_class','MobMoveTime':'move_interval_ms'},
              'item':{'ItmBuyPrice':'vendor_buy_price','ItmSellPrice':'vendor_sell_price','ItmDurability':'durability','ItmMinimumSDamage':'damage_min','ItmMaximumSDamage':'damage_max','ItmArmor':'armor_class','ItmLevel':'level_required','ItmMightRequired':'strength_required','ItmVita':'hp_bonus','ItmMana':'mp_bonus','ItmMight':'strength_bonus','ItmGrace':'dexterity_bonus','ItmWill':'intelligence_bonus','ItmStackAmount':'stack_limit'}}
    for (cat,name),identifier in correspondences.items():
        c=bykey.get((cat,norm(name),''));found=external_by_cat.get(cat,{}).get(identifier)
        if not c or not found:continue
        i,row=found;fname='mobs.csv' if cat=='monster' else 'Items.csv';c['external_correspondence_candidate']=dict(identifier=identifier,path='game-data/'+fname,line=i,identity_verified_full_KR=False)
        for old,new in fieldmap[cat].items():
            value=number(row[old])
            if new=='stack_limit' and value==0:continue # 0 has an upstream-specific nonstackable meaning.
            observe(c,new,value,'P1998:'+fname+':'+str(i),'P1998-'+fname,dict(file='game-data/'+fname,line=i,column=old),kind='EXTERNAL_REPLACEMENT')
    # The external table is cumulative-to-next-level, not a per-level XP cost.
    exp=csvtable('LevelExp.csv');growth=csvtable('PathGrowth.csv')
    source('P1998-LevelExp.csv','LevelExp.csv','game-data/LevelExp.csv');source('P1998-PathGrowth.csv','PathGrowth.csv','game-data/PathGrowth.csv')
    growth_by_path={int(r['path']):(i,r) for i,r in enumerate(growth,2)};exp_by_path=collections.defaultdict(dict)
    for i,r in enumerate(exp,2):exp_by_path[int(r['Path'])][int(r['Level'])]=(i,int(r['CumExp']))
    for path,scope in CLASSES.items():
        for level in range(1,100):
            if path==0 and level>5:continue
            c=dict(content_id=f'kr.growth.{path}.{level:02d}',category='growth',name=scope+' 레벨 '+str(level),class_scope=scope,level=level,namespace='KR',original_game_id=None,record_ids=[],versions=['PRODUCTION_DRAFT_1998_2001'],selection='PRODUCTION_TARGET',game_implemented=False)
            catalog[c['content_id']]=c;facts_by_entity[c['content_id']]=[]
            if level<99:
                line,threshold=exp_by_path[path][level];prev=exp_by_path[path].get(level-1,(0,0))[1]
                observe(c,'cumulative_exp_to_next',threshold,'P1998:LevelExp:'+str(line),'P1998-LevelExp.csv',dict(file='game-data/LevelExp.csv',line=line,column='CumExp'),kind='EXTERNAL_REPLACEMENT',conversion='row level L is threshold to reach L+1')
                observe(c,'exp_band_to_next',threshold-prev,'P1998:LevelExp:'+str(line)+':band','P1998-LevelExp.csv',dict(file='game-data/LevelExp.csv',line=line,column='CumExp'),kind='EXTERNAL_REPLACEMENT',conversion='CumExp(L)-CumExp(L-1); previous 0 at L=1')
            gi,g=growth_by_path[0 if level<5 else path]
            for old,new,shift in [('hpMin','hp_gain_min',0),('hpMax','hp_gain_max_inclusive',-1),('mpMin','mp_gain_min',0),('mpMax','mp_gain_max_inclusive',-1)]:
                observe(c,new,int(g[old])+shift,'P1998:PathGrowth:'+str(gi)+':'+new,'P1998-PathGrowth.csv',dict(file='game-data/PathGrowth.csv',line=gi,column=old),kind='EXTERNAL_REPLACEMENT',raw_token=g[old],conversion='exclusive max - 1' if shift else None)
    sources['DEV-20261013']=dict(id='DEV-20261013',kind='PRODUCTION_ASSUMPTIONS',game_region='KR_BLEND',original_url=None,file='research/restoration-integrated-20261013/PRODUCTION_ASSUMPTIONS.json',publication_date='2026-10-13',actual_game_period=None,game_version='PRODUCTION_DRAFT',rights='INDEPENDENT_DATA',raw_bytes_public=False)
    assumptions=dict(profile='KR_BLEND_1998_2001_PRODUCTION_DRAFT',historical_original=False,runtime_verified=False,
      integer_rules={'level':'CEILING','count':'ROUND_HALF_UP','durability_point':'ROUND_HALF_UP','AC':'ROUND_HALF_UP','전':'ROUND_HALF_UP','HP':'ROUND_HALF_UP','MP':'ROUND_HALF_UP','damage':'ROUND_HALF_UP','tile':'ROUND_HALF_UP','stat':'ROUND_HALF_UP','ms':'ROUND_HALF_UP'},
      xp_rule='Retain fractional XP in data. Runtime uses fixed point XP scale=2; do not round each squirrel kill to 8.',
      scalar_defaults={'monster_hp':'ceil(10 + 4*sqrt(max(XP,1))) unless explicit replacement exists','monster_level':'clamp(ceil(log2(max(XP,1)+1)*3),1,99)','monster_attack_min':'max(1,ceil(level/4))','monster_attack_max':'2*attack_min','monster_mp':1,'monster_move_ms':1200,'monster_attack_ms':1000,'monster_respawn_ms':15000,'aggro_radius_tiles':5,'leash_radius_tiles':8,'hit_probability':0.9,
                       'item_buy_price':'guide listed price if positive, else 10*max(level_required,1); this is an assumed purchase direction','item_sell_price':'floor(production_buy_price*0.5)','repair_multiplier':0.5,'equipment_durability':3000,'weapon_damage_min':'5+level_required','weapon_damage_max':'10+2*level_required','unreported_equipment_bonus':0,'material_stack_limit':99,'equipment_stack_limit':1,
                       'spell_cast_mp':'max(1,ceil(learn_level/2)) when cast is active and source absent','spell_damage':'2*learn_level+10 for explicit attack family','spell_heal_fallback':'50 for Nuri; otherwise max(50,10*learn_level) for named healing family','spell_duration_ms':30000,'spell_cooldown_ms':1000,'spell_range_tiles':6,'spell_success_probability':1.0,
                       'ordinary_listed_drop_probability':0.5,'drop_quantity':1,'map_width_tiles':64,'map_height_tiles':64,'map_spawn_tile':4,'NPC_local_tile':4,'NPC_interaction_radius':2},
      map_policy='Production draft numeric coordinates only. Do not treat as historical coordinates or a valid placement in extracted maps. Codex must bind map, collision and portal data before activating.',
      NPC_policy='Each NPC draft point must be bound to its own verified interior/map; equal (4,4) across records does not authorize placing all NPCs in one tile.',
      exclusions=['C05 contradictory Donggui mechanic','C10 white-tiger 800 XP','unknown class identity','unknown levels outside early target'],
      price_note='vendor_buy_price means player pays NPC; vendor_sell_price means NPC pays player. Guide prices retain their separate original field.',
      full_scope_note='Defaults populate early playable scalar draft only; later unresolved fields stay gaps. Complete scalar input does not certify content, geometry, rights or original fidelity.')
    writej('PRODUCTION_ASSUMPTIONS.json',assumptions)
    # A named early roster is determined from available low-level source content, not from search counts.
    beginner_names={norm(r['name']) for r in reviewed if r['category']=='monster' and '/dungeon/begin.html' in r['source_url']}
    early_ids=set()
    def kr_values(c,field):return [o for o in obs[(c['content_id'],field)] if o['kind']=='KR_CONFIRMED']
    for c in catalog.values():
        if c['namespace']!='KR':continue
        cat=c['category'];rows=facts_by_entity[c['content_id']]
        if cat=='growth' and c['level']<=30:early_ids.add(c['content_id'])
        elif cat=='monster' and norm(c['name']) in beginner_names:early_ids.add(c['content_id'])
        elif cat=='item':
            levels=[o['original_value'] for o in kr_values(c,'level_required')]
            if levels and min(levels)<=30:early_ids.add(c['content_id'])
        elif cat=='spell' and c.get('class_scope') in CLASSES.values() or cat=='spell' and c.get('class_scope')=='공통':
            levels=[o['original_value'] for o in kr_values(c,'learn_level')]
            if levels and min(levels)<=30:early_ids.add(c['content_id'])
        elif cat=='map' and any(term in norm(c['name']) for term in ['왕초보','쥐굴','뱀굴','곰','호랑이','여우굴','길드']):early_ids.add(c['content_id'])
        elif cat=='npc' and any(term in str(c.get('class_scope')) for term in ['주막','대장간','갑옷점','포목상','길드','성황당']) and not any(term in c['name'] for term in ['언니','형제들','네']):early_ids.add(c['content_id'])
    # Include every material needed by the early spell roster and every early monster's listed drop.
    for cid in list(early_ids):
        c=catalog[cid]
        for r in facts_by_entity[cid]:
            for value in (r['fields'].get('learn_materials') or [])+(r['fields'].get('drop_item_names') or []):
                n=value.get('name') if isinstance(value,dict) else value
                target=bykey.get(('item',norm(n),''))
                if target:early_ids.add(target['content_id'])
    masters=[];gaps=[];averages=[];chosen={}
    for c in sorted(catalog.values(),key=lambda r:r['content_id']):
        if c['namespace']!='KR' or c['category'] not in FIELDS:continue
        cid=c['content_id'];cat=c['category'];name=norm(c['name']);early=cid in early_ids
        c['production_stage']='LEVEL_1_30' if early else 'LATER_OR_UNRESOLVED'
        fields=dict(FIELDS[cat]);rows=facts_by_entity[cid]
        for key in obs:
            if key[0]==cid and obs[key]:fields.setdefault(key[1],obs[key][0]['unit'])
        itemkind=next((r['fields']['item_kind'] for r in rows if r['fields'].get('item_kind')),None)
        if cat=='item' and itemkind is None:itemkind='material'
        c['item_kind']=itemkind if cat=='item' else None
        for field,unit in fields.items():
            required=field in FIELDS[cat] or field.startswith('learn_materials.')
            if cat=='growth' and c['level']==99 and field in ['cumulative_exp_to_next','exp_band_to_next']:required=False
            if cat=='item' and itemkind not in ['weapon','armor'] and field in ['strength_required','durability','repair_multiplier','damage_min','damage_max','armor_class','hp_bonus','mp_bonus','strength_bonus','dexterity_bonus','intelligence_bonus']:required=False
            if cat=='item' and itemkind=='armor' and field in ['damage_min','damage_max']:required=False
            if cat=='spell' and c.get('class_scope') is None:required=False
            options=[o for o in obs[(cid,field)] if not any(issue.startswith(('C10_','C05_','COMPOSITE_')) for r in rows if r['id']==o['record_id'] for issue in r.get('issues',[]))]
            if name in ['白虎王','백호왕'] and field=='experience':options=[o for o in options if o['original_value']!=800]
            korea=[o for o in options if o['kind']=='KR_CONFIRMED'];external=[o for o in options if o['kind']=='EXTERNAL_REPLACEMENT']
            value=None;kind='GAP';linked=[];conversion=None;raw_mean=None
            if korea:
                distinct=sorted(set(o['original_value'] for o in korea))
                if (cid,field) in overrides:distinct=overrides[(cid,field)]['distinct_source_values']
                if len(distinct)>1:
                    raw_mean=sum(distinct)/len(distinct);value=raw_mean;kind='KR_MEAN';linked=[o['observation_id'] for o in korea]
                    averages.append(dict(content_id=cid,field=field,distinct_values=distinct,raw_arithmetic_mean=raw_mean,observation_ids=linked,profile='KR_BLEND_1998_2001',historical_original=False))
                else:value=distinct[0];kind='KR_CONFIRMED';linked=[o['observation_id'] for o in korea]
            elif external:value=external[0]['original_value'];kind='EXTERNAL_REPLACEMENT';linked=[external[0]['observation_id']]
            # Early production defaults are independent assumptions, not unknown original zeroes.
            if value is None and early and required:
                level=chosen.get((cid,'learn_level'),chosen.get((cid,'level_required'),5))
                xp_values=[o['original_value'] for o in obs[(cid,'experience')] if o['kind']=='KR_CONFIRMED']
                guide_values=[o['original_value'] for o in obs[(cid,'guide_listed_price')] if o['kind']=='KR_CONFIRMED']
                xp=sum(set(xp_values))/len(set(xp_values)) if xp_values else chosen.get((cid,'experience'),10)
                guide=sum(set(guide_values))/len(set(guide_values)) if guide_values else 10*max(level or 1,1)
                mlevel=max(1,min(99,math.ceil(math.log2(max(xp,1)+1)*3)))
                defaults={
                  'monster':dict(level=mlevel,hp=math.ceil(10+4*math.sqrt(max(xp,1))),mp=1,attack_min=max(1,math.ceil(mlevel/4)),attack_max=2*max(1,math.ceil(mlevel/4)),armor_class=0,experience=10,move_interval_ms=1200,attack_interval_ms=1000,respawn_interval_ms=15000,aggro_radius_tiles=5,leash_radius_tiles=8,hit_probability=.9),
                  'item':dict(level_required=1,strength_required=1,durability=3000,vendor_buy_price=max(1,guide),vendor_sell_price=math.floor(chosen.get((cid,'vendor_buy_price'),10)*.5),repair_multiplier=.5,damage_min=5+(level or 1),damage_max=10+2*(level or 1),armor_class=-1,hp_bonus=0,mp_bonus=0,strength_bonus=0,dexterity_bonus=0,intelligence_bonus=0,stack_limit=1 if itemkind in ['weapon','armor'] else 99,heal_amount=0,restore_mp=0),
                  'spell':dict(learn_level=5,learn_money=0,cast_mp=max(1,math.ceil((level or 5)/2)),cast_hp=0,cast_hp_fraction=0,base_damage=2*(level or 5)+10 if any(t in name for t in ['염주','무주','열주','진주','참주','지진']) else 0,heal_amount=50 if name=='누리의기원' else max(50,10*(level or 5)) if any(t in name for t in ['기원','희원']) else 0,range_tiles=6,aoe_radius_tiles=1 if '첨' in name or '희원' in name else 0,duration_ms=30000,cooldown_ms=1000,success_probability=1,learn_experience_cost=0),
                  'npc':dict(local_npc_x=4,local_npc_y=4,interaction_range_tiles=2,move_interval_ms=1500),
                  'map':dict(width_tiles=64,height_tiles=64,spawn_x=4,spawn_y=4,entry_level_requirement=1),
                  'growth':dict(base_armor_class=100-c.get('level',1))}
                if field in defaults.get(cat,{}):
                    value=defaults[cat][field];kind='DEV_ESTIMATE'
                    o=observe(c,field,value,'DEV:'+cid+':'+field,'DEV-20261013',dict(file='PRODUCTION_ASSUMPTIONS.json',rule=cat+'.'+field),kind='DEV_ESTIMATE');linked=[o['observation_id']]
            if kind=='KR_MEAN' and unit=='level':value=math.ceil(value);conversion='CEILING_OF_SOURCE_MEAN'
            elif kind=='KR_MEAN' and unit not in ['XP','ratio','probability']:
                value=int(Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP));conversion='ROUND_HALF_UP_OF_SOURCE_MEAN'
            if type(value) in [int,float]:chosen[(cid,field)]=value
            status='SOURCE_CONTENT_VERIFIED_NOT_RUNTIME' if kind=='KR_CONFIRMED' else 'PRODUCTION_DRAFT_NOT_RUNTIME' if value is not None else 'BLOCKED_MISSING_VALUE'
            if cat in ['npc','map'] and kind=='DEV_ESTIMATE':status='DRAFT_REQUIRES_MAP_LAYOUT_VERIFICATION'
            if name=='동귀어진' and field in ['cast_hp','cast_hp_fraction','base_damage']:value=None;kind='GAP';status='BLOCKED_C05_EFFECT_CONFLICT'
            row=dict(field_id='FIELD-'+shortid([cid,field]),content_id=cid,content_name=c['name'],category=cat,class_scope=c.get('class_scope'),level=c.get('level'),field=field,value=value,unit=unit,
                     production_profile='KR_BLEND_1998_2001_PRODUCTION_DRAFT',classification=kind,required=required,early_scope=early,
                     source_observation_ids=linked,source_ids=sorted({observation_by_id[oid]['source_id'] for oid in linked}),raw_average=raw_mean,integer_conversion=conversion,
                     applicable=value is not None,application_status=status,additional_validation=['Codex same-code calculation and full flow test','Replace with historical evidence when found']+(['Bind map/collision/portal before activation'] if cat in ['map','npc'] else []),game_runtime_verified=False)
            masters.append(row)
            if required and value is None:gaps.append(dict(gap_id='GAP-'+row['field_id'],content_id=cid,content_name=c['name'],field=field,unit=unit,importance='P0' if early else 'P1',
                      reason=status,search_target='Contemporary KR guide/server/client test; matching pinned replacement if unavailable',external_replacement_allowed=name!='동귀어진',estimate_needed=True,early_scope=early))
    # Per-item drops carry probabilities separately. Listing an item is not 100% drop proof.
    drop_rules=[]
    for c in catalog.values():
        if c['namespace']!='KR' or c['category']!='monster':continue
        ids=c['content_id'];drops={}
        for r in facts_by_entity[ids]:
            for name in r['fields'].get('drop_item_names') or []:
                target=bykey.get(('item',norm(name),''))
                if target:drops[target['content_id']]=dict(content_id=target['content_id'],name=target['name'],record=r)
        for iid,item in drops.items():
            r=item['record'];prob=r['fields'].get('drop_probability')
            rule=dict(drop_rule_id='DROP-'+shortid([ids,iid]),monster_content_id=ids,item_content_id=iid,item_name=item['name'],quantity=1,
                      probability=prob if prob is not None else .5 if ids in early_ids else None,
                      classification='KR_CONFIRMED' if prob is not None else 'DEV_ESTIMATE' if ids in early_ids else 'GAP',
                      selection_mode=r['fields'].get('drop_mode','LISTED_POSSIBILITIES_NOT_PROVEN_GUARANTEED'),source_record_id=r['id'],
                      source_id=r['source_id'],game_runtime_verified=False)
            drop_rules.append(rule)
            for suffix,value,unit,classification in [('probability',rule['probability'],'probability',rule['classification']),('quantity',1,'count','DEV_ESTIMATE')]:
                field='drop.'+iid+'.'+suffix;linked=[]
                if value is not None:
                    kind='KR_CONFIRMED' if classification=='KR_CONFIRMED' else 'DEV_ESTIMATE'
                    o=observe(c,field,value,r['id']+':'+field,r['source_id'] if kind=='KR_CONFIRMED' else 'DEV-20261013',r['position'] if kind=='KR_CONFIRMED' else dict(file='PRODUCTION_ASSUMPTIONS.json',rule='drop_'+suffix),kind=kind)
                    o['unit']=unit;linked=[o['observation_id']]
                row=dict(field_id='FIELD-'+shortid([ids,field]),content_id=ids,content_name=c['name'],category='monster',class_scope=None,level=None,field=field,value=value,unit=unit,
                         production_profile='KR_BLEND_1998_2001_PRODUCTION_DRAFT',classification=classification,required=True,early_scope=ids in early_ids,source_observation_ids=linked,
                         source_ids=[observation_by_id[o]['source_id'] for o in linked],raw_average=None,integer_conversion=None,applicable=value is not None,
                         application_status='PRODUCTION_DRAFT_NOT_RUNTIME' if value is not None else 'BLOCKED_MISSING_VALUE',additional_validation=['Seeded drop test in the actual game calculator; preserve mutually exclusive groups'],game_runtime_verified=False)
                masters.append(row)
                if value is None:gaps.append(dict(gap_id='GAP-'+row['field_id'],content_id=ids,content_name=c['name'],field=field,unit=unit,importance='P0' if ids in early_ids else 'P1',reason='Per-item probability absent',search_target='Contemporary drop table or actual game observation',external_replacement_allowed=True,estimate_needed=True,early_scope=ids in early_ids))
    assumptions['xp_fixed_point_scale']=math.lcm(2,*[len(r['distinct_values']) for r in averages if any(m['content_id']==r['content_id'] and m['field']==r['field'] and m['unit']=='XP' for m in masters)])
    writej('PRODUCTION_ASSUMPTIONS.json',assumptions)
    writel('CONTENT_CATALOG.jsonl',sorted(catalog.values(),key=lambda r:r['content_id']));writel('NUMERIC_MASTER.jsonl',masters);writel('NUMERIC_SOURCES.jsonl',observations);writel('NUMERIC_GAPS.jsonl',gaps);writel('DROP_RULES.jsonl',drop_rules)
    writej('SOURCE_VERSION_RIGHTS_LEDGER.json',dict(sources=list(sources.values()),policy='Original year/region/meaning preserved; external code and protected resource bytes not published'))
    writej('IMPLEMENTATION_MEANS.json',averages);writej('FIELD_SCHEMA.json',dict(required_fields=FIELDS,extra_units=EXTRA_UNITS,identity_policy='Never average identifiers, source years or guide coordinates',profile_version='1.0'))
    required=[r for r in masters if r['required']];early=[r for r in required if r['early_scope']];later=[r for r in required if not r['early_scope']]
    summary=dict(scope='Required scalar draft fields; per-drop probability coverage is reported separately. Geometry, mechanics, assets and rights are independent blockers.',
                 required_fields=len(required),filled_required_fields=sum(r['value'] is not None for r in required),classifications=dict(collections.Counter(r['classification'] for r in required)),
                 early_required_fields=len(early),early_filled_fields=sum(r['value'] is not None for r in early),early_input_rate=sum(r['value'] is not None for r in early)/len(early),
                 early_source_confirmed=sum(r['classification']=='KR_CONFIRMED' for r in early),early_source_match_rate=sum(r['classification']=='KR_CONFIRMED' for r in early)/len(early),
                 later_required_fields=len(later),remaining_scalar_gaps=len(gaps),draft_geometry_values=sum(r['application_status']=='DRAFT_REQUIRES_MAP_LAYOUT_VERIFICATION' for r in early),
                 content_counts_KR=dict(collections.Counter(c['category'] for c in catalog.values() if c['namespace']=='KR')),
                 early_entity_counts=dict(collections.Counter(c['category'] for c in catalog.values() if c['content_id'] in early_ids)),
                 original_runtime_match_rate='UNVERIFIED',drop_rule_count=len(drop_rules),drop_probability_gaps=sum(r['probability'] is None for r in drop_rules),
                 actual_game_simulations_executed=0)
    writej('NUMERIC_SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
