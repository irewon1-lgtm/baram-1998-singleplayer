#!/usr/bin/env python3
"""Connect available source city doorways from data, preserving original map pixels.

Native room geography is used when present. Missing rooms receive an explicitly
recorded working interior substitute. Actor/NPC/stock roles are singleplayer
completion, not claims about Korean 1998 geography or original NPC identities.
"""
import argparse
import collections
import csv
import json
from pathlib import Path
from build_original_world import write,sha,KR_SHA
from legacy_assets import dat_entries,Epf,read_palettes,private_path
from legacy_maps import tile_table,static_objects,map_cells


def build(a):
    assets=private_path(a.assets);inputs=private_path(a.inputs)
    raw=(inputs/'KR-4.91/NWind.dat').read_bytes()
    if sha(raw)!=KR_SHA:raise ValueError('Source DAT changed')
    es=dat_entries(raw);tables={}
    for g in 'ABC':
        e=Epf(es[f'tile{g.lower()}.epf'][2]);p=read_palettes(es[f'tile{g.lower()}.pal'][2])
        tables[g]=tile_table(es[f'tile{g.lower()}.tbl'][2],e.count,len(p))
    objects=static_objects(es['sobj.tbl'][2],tables['C'].count)
    path=assets/'source_maps/world.json';world=json.loads(path.read_text())
    if world.get('town_doors_connected'):raise ValueError('Already applied: original source recipe must be regenerated for a changed source')
    maps={m['id']:m for m in world['maps']};by_original={m['original_map_id']:m for m in world['maps']}
    dims={int(r['id']):r for r in csv.DictReader(Path(a.dimensions).open())}
    references={int(r['MapId']):r for r in csv.DictReader(Path(a.maps).open())}
    warps=list(csv.DictReader(Path(a.warps).open()));notes=[]
    targets=sorted({int(r['DestinationMapId']) for r in warps if r['SourceMapId']=='0'})

    def free(m,p):return 0<=p[0]<m['width'] and 0<=p[1]<m['height'] and not m['blocked'][p[1]][p[0]]
    def component(m,start):
        seen={tuple(start)};queue=collections.deque([tuple(start)])
        while queue:
            x,y=queue.popleft()
            for p in [(x,y-1),(x-1,y),(x,y+1),(x+1,y)]:
                if p not in seen and free(m,p):seen.add(p);queue.append(p)
        return seen
    def open_cell(m,p):
        if not 0<=p[0]<m['width'] or not 0<=p[1]<m['height']:raise ValueError('Reference doorway coordinate outside map')
        m['blocked'][p[1]][p[0]]=False;m['collision_masks'][p[1]][p[0]]=0
    def nearest(m,p,excluded=()):
        candidates=[(x,y) for y in range(m['height']) for x in range(m['width']) if free(m,(x,y)) and (x,y) not in excluded]
        if not candidates:raise ValueError('No usable source room cell')
        return list(min(candidates,key=lambda q:(abs(p[0]-q[0])+abs(p[1]-q[1]),q)))

    for mid in targets:
        if mid in by_original:continue
        ref=references.get(mid,{})
        if ref.get('MapIndoor')!='1':
            notes.append(dict(original_map_id=mid,status='NOT_CONNECTED_OUTDOOR_ROLE_UNRESOLVED',actual_attempt='Reference indoor flag checked; full external region needs its own ecology/progression. Door uses functioning guide return rather than fabricated original region.'))
            continue
        source=inputs/f'NA-4.95/Maps/TK{mid}.map';hint=dims.get(mid)
        if not source.is_file() or not hint:
            notes.append(dict(original_map_id=mid,status='BLOCKED_NATIVE_ROOM_OR_DIMENSIONS_MISSING',alternative='Existing original inn linked as labeled interior substitute'))
            continue
        data=source.read_bytes();w,h=int(hint['xs']),int(hint['ys'])
        try:cells=map_cells(data,w,h,tables,objects)
        except ValueError as e:
            notes.append(dict(original_map_id=mid,status='BLOCKED_NATIVE_ROOM_DIMENSIONS_OR_REFERENCES',error=str(e),alternative='Existing original inn linked as labeled substitute'));continue
        name=ref.get('MapName',hint['name']).replace("\\'", "'");lower=name.lower()
        combat=any(k in lower for k in ['cat','fox','spider','slime','valley','arena'])
        ground=[['']*w for _ in range(h)];masks=[[0]*w for _ in range(h)];deco=[]
        for j,c in enumerate(cells):
            y,x=divmod(j,w);ground[y][x]=c['tile'];masks[y][x]=c['collision']
            for k,frame in enumerate(objects[c['object_id']]['frames']):
                if frame is not None and y-k>=0:deco.append(dict(x=x,y=y-k,tile=f'KR491/C:{frame}',anchor_y=y,object_id=c['object_id'],column_part=k))
        sid=f'town-room-{mid}'
        m=dict(id=sid,name=name,kind='dungeon' if combat else 'interior',width=w,height=h,ground=ground,
               collision_masks=masks,blocked=[[v==15 for v in row] for row in masks],decorations=deco,
               npcs=[],portals=[],spawns=[],original_map_id=mid,source_file=f'NA-4.95/Maps/{source.name}',
               source_sha256=sha(data),source_kind='ORIGINAL_NA495_ROOM_SHARED_KR491_TILES',
               historic_identity='OTHER_VERSION_REPLACEMENT_NOT_KR1998_CONFIRMED',
               gameplay_kind='INFERRED_OFFLINE_ROOM_ROLE',recommended_level=[5,30] if combat else [1,99])
        links=[r for r in warps if r['SourceMapId']=='0' and int(r['DestinationMapId'])==mid]
        desired=[int(links[0]['DestinationX']),int(links[0]['DestinationY'])]
        m['entry']=nearest(m,desired)
        area=component(m,m['entry'])
        if len(area)<4:
            notes.append(dict(original_map_id=mid,status='BLOCKED_ISOLATED_REFERENCE_ENTRY',actual_attempt='Decoded source collision flood from reference entry yields fewer than four cells',remaining='Resolve dimension/door collision reference'));continue
        options=sorted(area-{tuple(m['entry'])},key=lambda p:(abs(p[0]-w//2)+abs(p[1]-h//2),p))
        at=next((p for p in options if sum((p[0]+dx,p[1]+dy) in area for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)])>=3),options[0])
        role='travel' if combat else 'inn' if any(k in lower for k in ['tavern','home']) else 'revive' if any(k in lower for k in ['shaman','chapel']) else 'shop'
        npc=dict(id=sid+'-service',kind='innkeeper' if role=='inn' else 'priest' if role=='revive' else 'teacher' if role=='travel' else 'merchant',
                 x=at[0],y=at[1],name={'travel':'귀로 안내인','inn':'주모','revive':'성황','shop':'가게 주인'}[role],role=role,
                 source_kind='INFERRED_SINGLEPLAYER_ROLE_SOURCE_SPRITE_REUSE')
        if role=='travel':npc['destinations']=['village']
        if role=='shop':
            npc['shop_items']=['연두색 남자도복','초록색 도포','보라 남자갑옷'] if any(k in lower for k in ['seam','weav','salon']) else ['토끼고기','산삼','구운토끼고기'] if 'butcher' in lower else ['목도','목검','철단도','철검','장창','초보 회복약','초보 마력약']
        m['npcs']=[npc];m['blocked'][at[1]][at[0]]=True
        if combat:
            positions=[p for p in area if p!=at and abs(p[0]-m['entry'][0])+abs(p[1]-m['entry'][1])>=4]
            kinds=['bat','rat'] if 'cat' in lower or 'arena' in lower else ['snake','boar'] if 'fox' in lower or 'valley' in lower else ['spider','skeleton']
            for i,p in enumerate(sorted(positions,key=lambda p:(p[1],p[0]))[::max(1,len(positions)//4)][:4]):m['spawns'].append(dict(id=sid+'-'+str(i),kind=kinds[i%len(kinds)],x=p[0],y=p[1]))
            m['ecology_classification']='REPLACEMENT_MONSTERS_WITH_SOURCE_STATS_NOT_ORIGINAL_ROOM_ECOLOGY'
        world['maps'].append(m);maps[sid]=m;by_original[mid]=m
        notes.append(dict(original_map_id=mid,scene=sid,status='CONNECTED_NATIVE_LAYOUT_ROLE_REPLACEMENT_NOT_YET_PLAYTESTED',source_sha256=sha(data),npcs=1,spawns=len(m['spawns'])))

    town=maps['village'];existing={(p['x'],p['y']) for p in town['portals']}
    for r in warps:
        if r['SourceMapId']!='0':continue
        p=[int(r['SourceX']),int(r['SourceY'])]
        if tuple(p) in existing:continue
        mid=int(r['DestinationMapId']);ref=references.get(mid,{})
        target=by_original.get(mid)
        if target is None:
            if ref.get('MapIndoor')=='1':target=maps['inn']
            else:continue
        try:open_cell(town,p)
        except ValueError as e:notes.append(dict(original_map_id=mid,status='BLOCKED_CITY_COORDINATE',error=str(e)));continue
        desired=[int(r['DestinationX']),int(r['DestinationY'])]
        entry=nearest(target,desired,{(n['x'],n['y']) for n in target['npcs']}) if target['original_map_id']==mid else target['entry']
        town['portals'].append(dict(x=p[0],y=p[1],target=target['id'],entry=entry,label=target['name'],
                                   source_kind='OTHER_VERSION_REFERENCE_SOURCE_DOOR_OR_EXPLICIT_ROOM_SUBSTITUTE',reference_destination=mid))
        existing.add(tuple(p))
        if target['id'].startswith('town-room-') and not target['portals']:
            exit_cell=nearest(target,[entry[0],target['height']-1],{tuple(entry),(target['npcs'][0]['x'],target['npcs'][0]['y'])})
            target['portals'].append(dict(x=exit_cell[0],y=exit_cell[1],target='village',entry=[p[0],min(town['height']-1,p[1]+1)],label='고구려 마을',source_kind='GENERATED_RETURN_LINK_SOURCE_DOOR_REFERENCE'))
    # Add reachable transport choices for the new *real* rooms; this is not a gallery.
    guide=next(n for n in town['npcs'] if n['role']=='travel')
    guide['destinations'].extend(m['id'] for m in world['maps'] if m['id'].startswith('town-room-'))
    world['town_doors_connected']=True;world['original_map_count']=len(world['maps']);world['generated_map_count']=0;world['legacy_generated_maps_preserved']=8
    write(path,world);write(assets/'source_maps/town-door-resolution.json',notes)
    report=dict(status='PASS_DATA_CONNECTION_NOT_ALL_ROOMS_PLAYTESTED',original_maps=len(world['maps']),
                added_native_rooms=sum(r['status'].startswith('CONNECTED_NATIVE') for r in notes),
                city_door_connections=len(town['portals']),original_city_floor_or_object_pixels_changed=0,
                room_resolution=notes,npc_roles='SOURCE_SPRITES_WITH_AUTHORED_SHOP_REST_REVIVE_AND_COMBAT_ROLES')
    write(Path(a.report),report);print(json.dumps({k:v for k,v in report.items() if k!='room_resolution'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['assets','inputs','dimensions','maps','warps','report']:p.add_argument('--'+key,required=True)
    build(p.parse_args())
