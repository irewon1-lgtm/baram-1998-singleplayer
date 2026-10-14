#!/usr/bin/env python3
"""Verify new actor cells and quest menus against pinned source layouts."""
import argparse,collections,datetime,json,sys,zipfile
from contextlib import ExitStack
from pathlib import Path
sys.dont_write_bytecode=True
from common import WORK,load,lines,write,file_sha,sha

def check(package,deps,bundles):
    package=Path(package);effective={};before={};own=[];errors=[];counts=collections.Counter()
    for d in [*map(Path,deps),package]:
        for f in sorted(d.glob('content-*.jsonl')):
            for r in lines(f):
                i=r.get('target_id',r['id'])
                if d==package:
                    own.append(r)
                    if i in effective:before[i]=effective[i]
                effective[i]=r
    def fail(i,field,reason):errors.append({'content_id':i,'field':field,'reason':reason})
    acquisitions={a['file_name']:a for d in map(Path,deps) if (d/'acquisition.json').exists() for a in [load(d/'acquisition.json')]}
    with ExitStack() as stack:
        readers={};layouts={};components={}
        for p in map(Path,bundles):
            a=acquisitions.get(p.name)
            if not a or p.stat().st_size!=a['size_bytes'] or file_sha(p)!=a['sha256']:
                fail(p.name,'bundle','Pinned dependency size/SHA mismatch');continue
            readers[a['bundle_id']]=stack.enter_context(zipfile.ZipFile(p));counts['pinned_layout_bundles']+=1
        def source(mid):
            if mid in layouts:return layouts[mid],components[mid]
            m=effective[mid]['data'];a=m['layout_acquisition'];reader=readers[a['bundle_id']];raw=reader.read(a['member'])
            if sha(raw)!=a['sha256']:fail(mid,'layout_acquisition','Layout member SHA mismatch')
            v=json.loads(raw);w,h=m['width'],m['height'];masks=v['collision_masks']
            if (v['width'],v['height'])!=(w,h) or len(masks)!=w*h:fail(mid,'dimensions','Source dimensions/cell count mismatch')
            def open_cell(x,y):return 0<=x<w and 0<=y<h and masks[y*w+x]!=15
            entry=tuple(m['entry']);seen={entry};todo=collections.deque([entry])
            if not open_cell(*entry):fail(mid,'entry','Solid source entry')
            while todo:
                x,y=todo.popleft()
                for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if q not in seen and open_cell(*q):seen.add(q);todo.append(q)
            layouts[mid]=v;components[mid]=seen;counts['source_layouts']+=1
            return v,seen
        new_placement_ids=set()
        for r in own:
            if r['kind']!='map':continue
            mid=r.get('target_id',r['id']);d=r['data'];old=before[mid]['data'];layout,reachable=source(mid)
            if d['portals']!=old['portals'] or d['entry']!=old['entry']:fail(mid,'portals/entry','Existing routes changed')
            occupied={tuple(old['entry'])}
            for group in ('portals','spawns','npc_placements'):
                for p in old[group]:
                    occupied.add((p['x'],p['y']));occupied.update(map(tuple,p.get('spawn_cells',[])))
            for group in ('spawns','npc_placements'):
                old_ids={p['placement_id']:p for p in old[group]};current_ids={p['placement_id']:p for p in d[group]}
                if any(current_ids.get(i)!=p for i,p in old_ids.items()):fail(mid,group,'Existing placement changed or removed')
                for p in d[group]:
                    if p['placement_id'] in old_ids:continue
                    if p['placement_id'] in new_placement_ids:fail(mid,group,'Duplicate new placement ID')
                    new_placement_ids.add(p['placement_id']);counts['new_'+group]+=1
                    anchor=(p['x'],p['y']);cells=set(map(tuple,p.get('spawn_cells',[list(anchor)])))
                    cells.add(anchor)
                    if not cells<=reachable:fail(mid,group,'New cells unreachable from source entry under solid-mask interpretation')
                    if cells & occupied:fail(mid,group,'New cells overlap an entry/portal/existing or new actor')
                    if group=='spawns' and any(abs(q[0]-anchor[0])+abs(q[1]-anchor[1])>p['radius_tiles'] for q in cells):fail(mid,group,'Spawn cell outside declared radius')
                    occupied.update(cells);counts['new_actor_cells']+=len(cells)
        for r in own:
            if r['kind']!='quest':continue
            i=r['id'];q=r['data'];giver=effective[q['start_npc_id']]['data']
            if not any(s.get('type')=='quests' and i in s.get('quest_ids',[]) for s in giver['services']):fail(i,'start_npc_id','Giver menu does not offer quest')
            counts['quest_menu_links']+=1
            for o in q['objectives']:
                needed=[]
                if o['type']=='talk':needed=[effective[p['map_id']]['data']['recommended_level'][0] for p in effective[o['npc_id']]['data']['placements']]
                if o['type']=='kill':needed=[effective[o['monster_id']]['data']['level']]
                if needed and q['requirements']['level']<max(needed):fail(i,'requirements.level','Requirement below declared objective location/monster level')
    report={'batch_id':package.name,'scope':'NEW_ACTOR_SOURCE_CELLS_AND_QUEST_MENUS_ONLY','result':'FAIL' if errors else 'PASS',
            'executed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':dict(counts),'errors':errors,
            'input_content_sha256':{p.name:file_sha(p) for p in sorted(package.glob('content-*.jsonl'))},
            'movement_interpretation':'Collision mask 15 is solid; cardinal open-cell connectivity. Directional movement not tested.',
            'directional_movement':'NOT_RUN','game_import':'NOT_RUN','gameplay':'NOT_RUN'}
    write(package/'actor-placement-validation.json',report)
    print(json.dumps({k:report[k] for k in ('batch_id','result','checks','errors')},ensure_ascii=False));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package');p.add_argument('--dependency',action='append',default=[]);p.add_argument('--bundle',action='append',default=[])
    a=p.parse_args();r=check(a.package,a.dependency,a.bundle);raise SystemExit(r['result']!='PASS')
