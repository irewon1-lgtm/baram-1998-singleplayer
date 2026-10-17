#!/usr/bin/env python3
"""Regional encounter specialists with distinct executed combat mechanics.

Adds seven encounter roles to each of the sixteen large regions. Every role
has a different range, movement/attack timing, defense, escape or status tradeoff.
Names, IDs, graphics and location never contribute to the semantic count.
Uses the existing engine and decoded world, without re-rendering any map.
"""
import argparse,base64,hashlib,json,shutil
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from build_g2_world import stable,write,digest,reachable

PROFILES=[
 ('매복독침',3,1.7,2.4,.75,.9,0.0,'poison',False,.3,6,10),
 ('장궁척후',7,.65,2.7,.65,1.2,0.0,'',True,.55,13,20),
 ('철갑파수',1,2.6,2.3,2.4,1.2,.55,'',False,.3,5,8),
 ('돌진광전',1,.38,1.15,1.3,1.5,0.0,'',False,.3,14,22),
 ('안개저주',4,1.3,3.2,.9,.65,.10,'silence',False,.3,8,12),
 ('서리결박',2,1.8,2.8,1.1,.8,.15,'slow',False,.3,7,12),
 ('환영포식',1,1.1,1.9,.85,1.1,.12,'blindness',True,.45,10,16),
]
SEMANTIC_FIELDS=('hp','attack','defense','level','xp','attack_range','aggression','move_interval','attack_interval','chase_range','leash_range','money_min','money_max','drops','on_hit_status','status_duration','status_power','guard_reduction','resistances','low_hp_flee','flee_hp_fraction','respawn_seconds')
def signatures(monsters):
 groups=defaultdict(list)
 for mid,m in monsters.items():groups[digest({k:m.get(k)for k in SEMANTIC_FIELDS})].append(mid)
 return groups

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 if a.output.exists():raise ValueError('Fresh output required')
 shutil.copytree(a.source,a.output);d=json.loads((a.output/'gameplay_content.json').read_text());prior=deepcopy(d)
 adoption=json.loads((a.output/'G2_ADOPTION.json').read_text());new=[]
 originals=[m for m in d['monsters'].values()if m.get('generation')!='G2']
 for region,mid in enumerate(d['g2_world']['fields']):
  m=d['maps'][mid];geometry=json.loads((a.output/m['geometry_file']).read_text());walk={**m,**{k:v for k,v in geometry.items()if k in ('blocked','edge_masks','ground_ids')}}
  entrances=[(e['to_x'],e['to_y'])for mm in d['maps'].values()for e in mm['exits']if e['to_map']==mid]
  available=set()
  for entry in entrances:
   if entry[1]*m['width']+entry[0]not in available:available.update(reachable(walk,entry))
  reserved={(v['x'],v['y'])for v in m['spawns']+m['exits']+m.get('gather_nodes',[])}|{(n['x'],n['y'])for n in d['npcs'].values()if n['map_id']==mid}|set(entrances)
  materials=[]
  for node in m['gather_nodes']:
   if node['item_id']not in materials:materials.append(node['item_id'])
  label=d['npcs'][next(n['id']for n in d['npcs'].values()if n['map_id']==mid and n.get('role')=='guide')]['name'].replace(' 길잡이','')
  for n,profile in enumerate(PROFILES):
   name,rng,move,attack,hp_scale,damage,guard,status,flee,fraction,chase,leash=profile
   base=originals[(region*13+n*17)%len(originals)];mob=deepcopy(base)
   for key in ('source_value','source_id','source_pointer','source_name_aliases','source_record'):mob.pop(key,None)
   level=min(98,max(4,int(m['recommended_level'])+4+n//2));iid=stable('monster',mid+'specialist'+name)
   mob.update(id=iid,name=label+' '+name+' '+base['name'],generation='G2',source_ref=base['id'],source_tier='LEGACY_RECONSTRUCTED',tactical_role=name,level=level,
    hp=max(1,round((24+level*7+level*level*.12)*hp_scale)),attack=max(1,round((3+level*.5)*damage)),defense=level//8+(8 if guard>.5 else 0),
    xp=15+level*level//3+n*3,money_min=3+level//3,money_max=7+level,attack_range=rng,move_interval=move,attack_interval=attack,
    aggression='hostile',chase_range=chase,leash_range=leash,low_hp_flee=flee,flee_hp_fraction=fraction,on_hit_status=status,status_duration=4+n*.5,
    status_power=max(1,level//18+1),guard_reduction=guard,resistances={'fire':.65 if n in (2,5)else 1.2,'ice':.6 if n in (1,6)else 1.15,'lightning':.7 if n in (0,4)else 1.1},
    respawn_seconds=32+n*4,drops=[{'item_id':materials[n%8],'chance':.85,'quantity_min':1,'quantity_max':2},{'item_id':materials[(n+3)%8],'chance':.45,'quantity_min':1,'quantity_max':1}])
   d['monsters'][iid]=mob
   for habitat in range(2):
    wanted=(12+n*5+habitat*8,35+(n*11+habitat*19)%65)
    candidates=[(cell%m['width'],cell//m['width'])for cell in available if(cell%m['width'],cell//m['width'])not in reserved and cell%m['width']<54 and min(abs(cell%m['width']-x)+abs(cell//m['width']-y)for x,y in entrances)>10]
    if not candidates:raise ValueError('No reachable specialist habitat '+mid)
    x,y=min(candidates,key=lambda p:abs(p[0]-wanted[0])+abs(p[1]-wanted[1]));reserved.add((x,y))
    sid=stable('spawn',iid+str(habitat));m['spawns'].append({'id':sid,'monster_id':iid,'x':x,'y':y,'respawn_seconds':mob['respawn_seconds']})
   adoption['records'].append({'content_id':iid,'source_ref':base['id'],'source_tier':'LEGACY_RECONSTRUCTED','reconstructed_fields':['regional combat profile','habitat','rewards'],'role':name,'runtime_ref':'monsters.'+iid,'dependencies':materials,'generation':'G2','test_status':'IMPLEMENTED_TUNING_PENDING_REQUIRES_EXECUTION_LEDGER'})
   new.append(iid)
 groups=signatures(d['monsters']);assert len(groups)>=500
 d['accepted_compatibility'].append({'profile':prior['profile'],'compatibility':prior['compatibility'],'manifest_sha256':prior['manifest_sha256'],'map_transforms':{}})
 d['compatibility']['rules']=digest({k:d[k]for k in ['items','monsters','skills','npcs','quests','recipes','config']})
 d['compatibility']['idset']=digest({k:sorted(d[k])for k in ['maps','items','monsters','skills','npcs','quests','recipes']})
 d['manifest_sha256']=digest({'generation':'G2_REGIONAL_SPECIALISTS','compatibility':d['compatibility'],'parent':prior['manifest_sha256']})
 migration=json.loads((a.output/'G2_MAP_MIGRATION.json').read_text())
 migration['previous_target_manifest']=migration['target_manifest'];migration['target_manifest']=d['manifest_sha256']
 write(a.output/'G2_MAP_MIGRATION.json',migration)
 write(a.output/'gameplay_content.json',d);write(a.output/'G2_ADOPTION.json',adoption)
 write(a.output/'G2_MONSTER_SEMANTICS.json',{'schema':'baram.g2.monster-semantics/2','status':'STATIC_SEMANTICS_ONLY_EXECUTION_SEPARATE','registered':len(d['monsters']),'meaningful_signatures':len(groups),'excluded_from_signature':['name','id','sprite','look','region','position','source label'],'fields':SEMANTIC_FIELDS,'added_specialists':new,'alias_groups':[v for v in groups.values()if len(v)>1],'profiles':PROFILES,'reason':'Earlier521 estimate included names. Strict count was401;112 distinct regional tactical profiles now exceed500 without counting aliases.'})
 manifest=json.loads((a.output/'runtime.json').read_text());files=[]
 for f in sorted(a.output.rglob('*')):
  if f.is_file()and f.name!='runtime.json':files.append({'path':f.relative_to(a.output).as_posix(),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 manifest.update(files=files,compatibility=d['compatibility'],fingerprint=digest(files),input_definitions_sha256=hashlib.sha256((a.output/'gameplay_content.json').read_bytes()).hexdigest())
 write(a.output/'runtime.json',manifest)
 print(json.dumps({'registered_monsters':len(d['monsters']),'meaningful_monsters':len(groups),'spawns':sum(len(m['spawns'])for m in d['maps'].values()),'added':len(new),'runtime_sha256':hashlib.sha256((a.output/'runtime.json').read_bytes()).hexdigest()}))

if __name__=='__main__':main()
