#!/usr/bin/env python3
"""Attach actual NPC, combat and travel roles to privately converted source maps."""
import argparse
import collections
import csv
import json
from pathlib import Path
from build_original_world import write
from legacy_assets import private_path


def connect(a):
    assets=private_path(a.assets)
    path=assets/'source_maps/world.json'
    world=json.loads(path.read_text());maps={m['id']:m for m in world['maps']}
    changes=[]

    def available(m,x,y):
        return 0<=x<m['width'] and 0<=y<m['height'] and not m['blocked'][y][x]

    def nearest(m,p,exclude=()):
        candidates=[(abs(x-p[0])+abs(y-p[1]),y,x) for y in range(m['height']) for x in range(m['width'])
                    if available(m,x,y) and (x,y) not in exclude]
        if not candidates:raise ValueError('No walkable cell in '+m['id'])
        _,y,x=min(candidates);return [x,y]

    def flood(m,start):
        seen={tuple(start)};todo=collections.deque([tuple(start)])
        while todo:
            x,y=todo.popleft()
            for nx,ny in [(x,y-1),(x-1,y),(x,y+1),(x+1,y)]:
                if (nx,ny) not in seen and available(m,nx,ny):
                    seen.add((nx,ny));todo.append((nx,ny))
        return seen

    def portal(m,p,target,entry,label,basis):
        x,y=p
        if not 0<=x<m['width'] or not 0<=y<m['height']:raise ValueError('Portal outside source map')
        old=m['collision_masks'][y][x]
        m['blocked'][y][x]=False;m['collision_masks'][y][x]=0
        m['portals'].append(dict(x=x,y=y,target=target,entry=entry,label=label,source_kind=basis))
        if old:changes.append(dict(scene=m['id'],x=x,y=y,previous_collision=old,change='OPEN_SOURCE_DOORWAY_GAMEPLAY_OVERLAY'))

    source_ids={m['original_map_id']:m for m in world['maps']}
    warps=list(csv.DictReader(Path(a.warps).open()))
    for r in warps:
        sid,did=int(r['SourceMapId']),int(r['DestinationMapId'])
        if sid not in source_ids or did not in source_ids:continue
        m,target=source_ids[sid],source_ids[did]
        p=[int(r['SourceX']),int(r['SourceY'])];entry=[int(r['DestinationX']),int(r['DestinationY'])]
        if 0<=entry[0]<target['width'] and 0<=entry[1]<target['height'] and 0<=p[0]<m['width'] and 0<=p[1]<m['height']:
            # These coordinates come from a private later restoration reference.
            # They are never presented as shipped Korean 1998 connection data.
            portal(m,p,target['id'],entry,target['name'],'OTHER_VERSION_REFERENCE_COORDINATE_VALIDATED')
            target['blocked'][entry[1]][entry[0]]=False;target['collision_masks'][entry[1]][entry[0]]=0
    for m in world['maps']:
        # A directional fence/door flag is not an all-direction solid wall.
        m['blocked']=[[mask==15 for mask in row] for row in m['collision_masks']]
        occupied={(p['x'],p['y']) for p in m['portals']}
        desired=([59,152] if m['id']=='village' else [21,12] if m['id']=='inn' else
                 [9,m['height']-3] if m['kind']=='interior' else [m['width']//2,m['height']-4])
        m['entry']=nearest(m,desired,occupied)
        component=flood(m,m['entry'])
        if len(component)<25 and m['kind']!='interior':
            seen=set();groups=[]
            for y in range(m['height']):
                for x in range(m['width']):
                    if available(m,x,y) and (x,y) not in seen:
                        group=flood(m,[x,y]);seen.update(group);groups.append(group)
            component=max(groups,key=len)
            m['entry']=list(min(component-occupied,key=lambda p:abs(p[0]-desired[0])+abs(p[1]-desired[1])))
        m['npcs']=[];m['spawns']=[]

    def npc(mid,p,kind,name,role,**other):
        m=maps[mid];component=flood(m,m['entry'])
        reserved={(n['x'],n['y']) for n in m['npcs']}|{(p['x'],p['y']) for p in m['portals']}|{tuple(m['entry'])}
        cells=component-reserved
        # Keep at least one walkable neighboring cell for interaction.
        roomy={at for at in cells if sum((at[0]+dx,at[1]+dy) in cells for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)])>=3}
        if roomy:cells=roomy
        if not cells:raise ValueError('No reachable NPC position: '+mid)
        x,y=min(cells,key=lambda q:(abs(q[0]-p[0])+abs(q[1]-p[1]),q[1],q[0]))
        spec=dict(id=mid+'-'+role+'-'+str(len(m['npcs'])),kind=kind,x=x,y=y,name=name,role=role,
                  source_kind='AUTHORED_SINGLEPLAYER_ROLE_ORIGINAL_KR491_SPRITE',**other)
        m['npcs'].append(spec);m['blocked'][y][x]=True
        return spec

    npc('village',[61,153],'merchant','장비상','shop')
    npc('village',[63,153],'teacher','초보 안내인','quest')
    npc('village',[65,153],'priest','성황','revive')
    npc('inn',[21,6],'innkeeper','주모','inn')
    npc('source_smith',[10,5],'merchant','대장장이','shop')
    for mid,job in [('guild','전사'),('rogue_guild','도적'),('mage_guild','주술사'),('poet_guild','도사')]:
        npc(mid,[9,7],'teacher',job+' 사범','trainer',job=job)
    # Author a route into the original terrain. No source floor/object is repainted.
    for first,second in [('field','cave'),('cave','bat_den'),('field','forest'),('forest','deep'),
                         ('field','rabbit_depth'),('rabbit_depth','foraged'),('deep','ruins')]:
        ma,mb=maps[first],maps[second]
        for m,target in [(ma,mb),(mb,ma)]:
            occupied={(p['x'],p['y']) for p in m['portals']}|{tuple(m['entry'])}
            component=flood(m,m['entry'])-occupied
            p=min(component,key=lambda q:(abs(q[0]-(m['entry'][0]+4))+abs(q[1]-m['entry'][1]),q[1],q[0]))
            portal(m,list(p),target['id'],target['entry'],target['name'],'GENERATED_SINGLEPLAYER_CONNECTION_VISIBLE_LABEL')
    # The guide offers meaningful transport in the large original city, and all
    # guild/inn doorways remain reachable by ordinary movement as well.
    destinations=['field','inn','source_smith','guild','rogue_guild','mage_guild','poet_guild']
    npc('village',[67,153],'teacher','길잡이','travel',destinations=destinations)
    for mid in ['field','cave','bat_den','forest','deep','ruins','rabbit_depth','foraged']:
        npc(mid,maps[mid]['entry'],'teacher','귀로 안내인','travel',destinations=['village'])
    species={'field':['rabbit','squirrel']*4,'cave':['rat']*6,'bat_den':['bat']*6,
             'forest':['snake']*6,'deep':['boar']*6,'ruins':['skeleton','rat']*4,
             'rabbit_depth':['rabbit','rat']*5,'foraged':['squirrel','spider']*4}
    for mid,kinds in species.items():
        m=maps[mid];component=flood(m,m['entry'])
        occupied={(p['x'],p['y']) for p in m['portals']}|{tuple(m['entry'])}
        candidates=sorted(component-occupied,key=lambda p:(abs(p[0]-m['entry'][0])+abs(p[1]-m['entry'][1]),p))
        candidates=[p for p in candidates if abs(p[0]-m['entry'][0])+abs(p[1]-m['entry'][1])>=4]
        if len(candidates)<len(kinds):raise ValueError('Source region has insufficient reachable spawning cells: '+mid)
        selected=[]
        for i,kind in enumerate(kinds):
            desired=candidates[min(i*3,len(candidates)-1)]
            p=next(p for p in candidates if p not in selected and (not selected or min(abs(p[0]-q[0])+abs(p[1]-q[1]) for q in selected)>=2))
            selected.append(p)
            m['spawns'].append(dict(id=f'{mid}-{i}',kind=kind,x=p[0],y=p[1]))
    world['start']={'map':'village','entry':maps['village']['entry']}
    world['home']={'map':'village','entry':maps['village']['entry']}
    world['revision']='source-maps-2'
    world['collision_overlay']=changes
    world['replacements'].update(boar='곰')
    world['travel_classification']='GENERATED_SINGLEPLAYER_ROLE_WITH_ORIGINAL_SOURCE_MAPS'
    world['shop_items'].extend(['연두색 남자도복','초록색 도포','보라 남자갑옷'])
    for m in world['maps']:
        for p in m['portals']:
            target=maps[p['target']]
            x,y=p['entry']
            if not available(target,x,y):p['entry']=target['entry']
        m['reachable_walk_cells']=len(flood(m,m['entry']))
        if m['reachable_walk_cells']<3:raise ValueError('Disconnected source region '+m['id'])
    write(path,world)
    report=dict(status='PASS_STATIC_REACHABILITY_NOT_GAMEPLAY',maps=len(maps),
                npcs=sum(len(m['npcs']) for m in maps.values()),spawns=sum(len(m['spawns']) for m in maps.values()),
                portals=sum(len(m['portals']) for m in maps.values()),doorway_collision_overlays=changes,
                original_source_floor_and_object_pixels_changed=0,
                maps_summary=[dict(id=m['id'],entry=m['entry'],reachable=m['reachable_walk_cells']) for m in maps.values()],
                source_kind='ORIGINAL_NA_MAPS_PLUS_AUTHORED_NPC_COMBAT_AND_TRAVEL_ROLES')
    write(Path(a.report),report);print(json.dumps({k:v for k,v in report.items() if k not in ['doorway_collision_overlays','maps_summary']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['assets','warps','report']:p.add_argument('--'+key,required=True)
    connect(p.parse_args())
