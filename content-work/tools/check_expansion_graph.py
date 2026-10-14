#!/usr/bin/env python3
"""Short effective-state graph and defined-transaction checks; no gameplay claim."""
import argparse,collections,datetime,sys
from pathlib import Path
sys.dont_write_bytecode=True
from common import WORK,load,lines,write,file_sha

def check(package,deps,write_report=True):
    package=Path(package);defs={};own=[];errors=[];checks=collections.Counter()
    for d in [*map(Path,deps),package]:
        for p in sorted(d.glob('content-*.jsonl')):
            for r in lines(p):
                defs[r.get('target_id',r['id'])]=r
                if d==package:own.append(r)
    def fail(r,field,message):errors.append({'content_id':r.get('target_id',r['id']),'field':field,'reason':message})
    maps={i:r['data'] for i,r in defs.items() if r['kind']=='map' and r['data'].get('variant_active') is not False}
    items={i:r['data'] for i,r in defs.items() if r['kind']=='item'}
    offers=collections.defaultdict(list);drops=collections.defaultdict(list);outputs=collections.defaultdict(list);rewards=collections.defaultdict(list);uses=collections.defaultdict(list)
    for i,r in defs.items():
        d=r['data']
        if r['kind']=='shop':
            for o in d['offers']:offers[o['item_id']].append((i,o['price_gold']))
        if r['kind']=='drop_group':
            for o in d['rolls']:
                if o.get('probability',{'numerator':o.get('weight',1)})['numerator']>0:drops[o['item_id']].append(i)
        if r['kind']=='recipe':
            for o in d['outputs']:outputs[o['item_id']].append(i)
            for o in d['consume']:uses[o['item_id']].append(i)
        if r['kind']=='quest':
            for o in d['rewards']:
                if o['type']=='item':rewards[o['item_id']].append(i)
            for o in d['consume']:uses[o['item_id']].append(i)
        if r['kind']=='skill':
            for o in d['learn']['consume']:uses[o['item_id']].append(i)
    roots={'wk.map.city.goguryeo','wk.map.city.buyeo'};reachable=roots&maps.keys();todo=list(reachable)
    while todo:
        here=todo.pop()
        for portal in maps[here]['portals']:
            there=portal['destination_map_id']
            if there in maps and there not in reachable:reachable.add(there);todo.append(there)
    reverse=collections.defaultdict(set)
    for mid,d in maps.items():
        for p in d['portals']:reverse[p['destination_map_id']].add(mid)
    returns=roots&maps.keys();todo=list(returns)
    while todo:
        here=todo.pop()
        for there in reverse[here]:
            if there not in returns:returns.add(there);todo.append(there)
    npc_at=collections.defaultdict(list);spawn_at=collections.defaultdict(set)
    for mid,d in maps.items():
        for p in d['npc_placements']:npc_at[p['npc_id']].append((mid,p['x'],p['y']))
        for p in d['spawns']:spawn_at[p['monster_id']].add(mid)
    for r in own:
        i=r.get('target_id',r['id']);d=r['data'];kind=r['kind']
        if kind=='map':
            checks['map_entry_return_graph']+=1
            if i not in reachable or i not in returns:fail(r,'portals','No declared route from and back to existing national hubs')
        if kind=='monster':
            checks['monster_spawn']+=1
            if not spawn_at[i]:fail(r,'spawn_rules','Defined monster has no physical spawn')
        if kind=='npc':
            checks['npc_placements']+=1
            for p in d['placements']:
                if (p['map_id'],p['x'],p['y']) not in npc_at[i]:fail(r,'placements','NPC and map placement disagree')
                if p['map_id'] not in reachable:fail(r,'placements','NPC is not reachable through declared routes')
            for dialog in d['dialogue']:
                if not dialog.get('text','').strip():fail(r,'dialogue','Empty final dialogue')
                for c in dialog.get('choices',[]):
                    if 'service_index' in c and not 0<=c['service_index']<len(d['services']):fail(r,'dialogue.choices','Service index outside NPC service list')
        if kind=='item' and d['flags']['obtainable']:
            checks['obtainable_items']+=1
            if not offers[i] and not drops[i] and not outputs[i] and not rewards[i]:fail(r,'acquisition','No actual shop/drop/recipe/reward produces item')
            for a in d['acquisition']:
                if a['kind']=='recipe' and a['recipe_id'] not in outputs[i]:fail(r,'acquisition.recipe','Declared recipe does not output this item')
                if a['kind']=='shop' and a['shop_id'] not in [s for s,_ in offers[i]]:fail(r,'acquisition.shop','Declared shop has no offer for this item')
                if a['kind']=='monster_drop':
                    m=defs.get(a['monster_id']);dg=m['data']['drop_group_id'] if m else None
                    if dg not in drops[i] or not spawn_at[a['monster_id']]:fail(r,'acquisition.monster_drop','Drop group or reachable monster spawn missing')
            if d['item_type']=='material':
                checks['material_uses']+=1
                if not uses[i] and not d['flags']['sellable']:fail(r,'use','Material has no consume or sale use')
        if kind=='shop':
            checks['shop_transactions']+=len(d['offers'])
            if not npc_at[d['npc_id']]:fail(r,'npc_id','Shop owner is not placed')
            for o in d['offers']:
                it=items[o['item_id']]
                if not it['flags']['buyable'] or not it['flags']['obtainable']:fail(r,'offers','Disabled item offered')
                if it['flags']['sellable'] and o['price_gold']<it['prices']['sell']:fail(r,'offers','Infinite buy-and-sell money loop')
        if kind=='recipe':
            checks['recipe_transactions']+=1
            if not d['consume'] or any(o['quantity']<=0 for o in d['consume']):fail(r,'consume','Positive input consumption required')
            # Even with freely farmed inputs, no pure cash craft-and-sell loop.
            cash=sum(items[o['item_id']]['prices']['sell']*o['quantity'] for o in d['outputs'] if items[o['item_id']]['flags']['sellable'])
            if cash>d['gold_cost']:fail(r,'gold_cost','Output cash exceeds fee before considering consumed inputs')
            if not npc_at[d['npc_id']]:fail(r,'npc_id','Crafter is not physically placed')
            owner=defs[d['npc_id']]['data']
            if not any(s.get('recipe_id')==i for s in owner['services']):fail(r,'npc_id','Crafter has no service for this recipe')
        if kind=='quest':
            checks['closed_quest_definitions']+=1
            for key in ['start_npc_id','complete_npc_id']:
                if not npc_at[d[key]]:fail(r,key,'Quest NPC not physically placed')
            for o in d['objectives']:
                if o['type']=='kill' and o.get('map_id') not in spawn_at[o['monster_id']]:fail(r,'objectives','Kill target not spawned in required map')
                if o['type']=='collect' and not offers[o['item_id']] and not drops[o['item_id']] and not outputs[o['item_id']] and not rewards[o['item_id']]:fail(r,'objectives','Collection item not obtainable')
                if o['type']=='talk' and not npc_at[o['npc_id']]:fail(r,'objectives','Talk target not placed')
            for o in d['consume']:
                if not any(x['type']=='collect' and x['item_id']==o['item_id'] and x['count']>=o['quantity'] for x in d['objectives']):fail(r,'consume','Submission quantity is absent from collection objective')
        if kind=='skill':
            checks['skill_learn_paths']+=1
            for npc in d['learn']['teacher_npc_ids']:
                if not npc_at[npc]:fail(r,'learn','Teacher not placed')
            for o in d['learn']['consume']:
                if not offers[o['item_id']] and not drops[o['item_id']] and not outputs[o['item_id']] and not rewards[o['item_id']]:fail(r,'learn.consume','Learning material unavailable')
    report={'scope':'DATA_ONLY','result':'FAIL' if errors else 'PASS','batch_id':package.name,'executed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'command':' '.join(sys.argv),'checks':dict(checks),'errors':errors,'input_content_sha256':{p.name:file_sha(p) for p in package.glob('content-*.jsonl')},
      'static_map_graph':'Directed declared portal graph only, not directional tile collision or real movement',
      'economy_scope':'Declared finite recipe/shop rules only; live game economy NOT_RUN','game_import':'NOT_RUN','gameplay':'NOT_RUN'}
    if write_report:write(package/'connection-validation.json',report)
    print({k:report[k] for k in ['batch_id','result','checks','errors']});return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package');p.add_argument('--dependency',action='append',default=[]);p.add_argument('--report-only',action='store_true');a=p.parse_args();r=check(a.package,a.dependency,not a.report_only);raise SystemExit(r['result']!='PASS')
