#!/usr/bin/env python3
"""Structural/progression graph checks. No gameplay or platform PASS inference."""
import argparse,json,hashlib
from pathlib import Path
from collections import Counter,deque
from build_g2_world import write,reachable
def run(root):
 d=json.load(open(root/'gameplay_content.json'));checks=[]
 def check(i,v,detail=None):checks.append({'id':i,'status':'PASS'if v else'FAIL','detail':detail})
 targets={'items':1000,'monsters':500,'skills':260,'npcs':80,'quests':150,'recipes':60}
 for k,n in targets.items():check('registered_'+k,len(d[k])>=n,len(d[k]))
 legacy=json.load(open(root/'G2_MAP_MIGRATION.json'));check('migration_id_preservation',legacy['all_source_ids_preserved'])
 check('spawn_budget',sum(len(m['spawns'])for m in d['maps'].values())<=d['config']['max_world_monsters'])
 landings={k:set()for k in d['maps']}
 for m in d['maps'].values():
  for e in m['exits']:landings[e['to_map']].add((int(e['to_x']),int(e['to_y'])))
 for mid,m in d['maps'].items():
  b={tuple(p)for p in m['blocked']};nodes={p['id']for p in m.get('gather_nodes',[])}
  check('grid:'+mid,len(m['ground_ids'])==m['width']*m['height']and(not m.get('edge_masks')or len(m['edge_masks'])==len(m['ground_ids'])))
  check('entrance_clear:'+mid,all((s['x'],s['y'])not in landings[mid]for s in m['spawns'])and all((n['x'],n['y'])not in landings[mid]for n in d['npcs'].values()if n['map_id']==mid))
  reached=set()
  for x,y in landings[mid]:
   if y*m['width']+x not in reached:reached.update(reachable(m,(x,y)))
  check('services_habitats_nodes_reachable:'+mid,all(p['y']*m['width']+p['x']in reached for p in m['spawns']+m.get('gather_nodes',[]))+all(n['y']*m['width']+n['x']in reached for n in d['npcs'].values()if n['map_id']==mid)==2)
  if mid in d['g2_world']['city_maps']:check('city_256:'+mid,m['width']>=256 and m['height']>=256)
 for mid in d['g2_world']['fields']:check('field_128:'+mid,d['maps'][mid]['width']>=128 and d['maps'][mid]['height']>=128)
 check('16_fields',len(d['g2_world']['fields'])>=16)
 check('12_families',len(d['g2_world']['dungeon_families'])>=12)
 for ids in d['g2_world']['dungeon_families']:check('four_floors:'+ids[0],len(ids)>=4 and all(d['maps'][mid]['width']>=64 and d['maps'][mid]['height']>=64 for mid in ids))
 for level in [1,5,15,30,60,99]:
  reached={d['start']['map_id']};q=deque(reached)
  while q:
   mid=q.popleft()
   for e in d['maps'][mid]['exits']:
    if level>=e.get('minimum_level',1)and e['to_map']not in reached:reached.add(e['to_map']);q.append(e['to_map'])
  check('level_graph:'+str(level),d['start']['map_id']in reached and(level!=99 or len(reached)==len(d['maps'])),{'reachable_maps':len(reached)})
 # No material is supplied solely by an output depending on itself.
 supplied=set()
 for n in d['npcs'].values():
  supplied.update(i for i,v in n.get('shop',{}).items()if v.get('buy_price')is not None)
 for m in d['monsters'].values():supplied.update(v['item_id']for v in m.get('drops',[])if v.get('chance',0)>0)
 for m in d['maps'].values():supplied.update(v['item_id']for v in m.get('gather_nodes',[]))
 for _ in range(len(d['recipes'])+len(d['quests'])):
  before=len(supplied)
  for r in d['recipes'].values():
   if set(r['ingredients'])<=supplied:supplied.update(r['results'])
  for r in d['quests'].values():
   if all(o['kind']!='collect'or o['id']in supplied for o in r['objectives']):supplied.update(r['rewards'].get('items',{}))
  if len(supplied)==before:break
 for iid,item in d['items'].items():check('acquisition:'+iid,iid in supplied or any(s['item_id']==iid for s in d['start']['starter_items']))
 for rid,r in d['recipes'].items():check('craft_materials:'+rid,set(r['ingredients'])<=supplied)
 semantic=Counter((m['name'],m['hp'],m['attack'],m.get('attack_range',1),m.get('on_hit_status',''),tuple((v['item_id'],v.get('chance'))for v in m.get('drops',[])))for m in d['monsters'].values())
 check('nonduplicate_monster_semantics',len(semantic)>=500,{'stable_ids':len(d['monsters']),'distinct_name_combat_drop_signatures':len(semantic),'method':'Spawn instances excluded. Exact baseline aliases collapsed; meaningful role variations retained.'})
 usage=json.load(open(root/'G2_WORLD_USAGE.json'));check('area_5x',usage['g2_area_A1']>=5*usage['baseline_area_A0'],usage['ratio'])
 result={'schema':'baram.g2.structural/1','scope':'Actual frozen definitions, source masks, area and normal level graph; NOT gameplay/visual/native certification','status':'PASS'if all(x['status']=='PASS'for x in checks)else'FAIL','checks':checks,'failures':sum(x['status']=='FAIL'for x in checks),'content_sha256':hashlib.sha256((root/'gameplay_content.json').read_bytes()).hexdigest()}
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime);write(a.output,r);print(json.dumps({'checks':len(r['checks']),'failures':r['failures'],'failed':[x for x in r['checks']if x['status']=='FAIL'][:12]},ensure_ascii=False));raise SystemExit(0 if not r['failures']else 1)
