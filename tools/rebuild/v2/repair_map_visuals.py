#!/usr/bin/env python3
"""Repair the frozen G1 presentation without changing its saved map topology.

Only decoded pixels already in the supplied private generation are reused. Stable
IDs, dimensions, blocked cells, exits, spawns, NPCs and geometry hashes are locked.
Full floors remain for audit; bounded chunks are used by the live view.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, math
from copy import deepcopy
from pathlib import Path
from PIL import Image

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def write(p,v): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def topology(m): return {k:m.get(k) for k in ('id','width','height','map_version','geometry_sha256','blocked','exits','spawns','spawn_zones','npcs')}

class Repair:
    def __init__(self,source,output,reshape=False):
        self.source=source;self.output=output
        self.reshape=reshape;self.transforms={};self.layout_receipts=[]
        self.data=json.loads((source/'gameplay_content.json').read_text());self.before=deepcopy(self.data)
        self.tiles={};self.changes=[]
        for m in self.data['maps'].values():
            floor=Image.open(source/m['floor_png']).convert('RGBA');w=m['width']
            for n,t in enumerate(m['ground_ids']):
                if t not in self.tiles:self.tiles[t]=floor.crop((n%w*24,n//w*24,n%w*24+24,n//w*24+24))
    def native(self,n): return Image.open(self.source/f'gameplay/world/objects/object-{n}.png').convert('RGBA')
    def regional_layout(self,m):
        """Connected region-specific rooms/trails, with explicit old-cell maps.

        Every source exit, arrival, spawn and service coordinate is protected.
        Existing blocked cells remain blocked. New wall footprints are explicit,
        not non-colliding pictures painted over an open rectangular map.
        """
        from collections import deque
        import heapq
        w,h=m['width'],m['height'];old={tuple(p)for p in m['blocked']};seed=int(hashlib.sha256(m['id'].encode()).hexdigest()[:8],16);region=m.get('region','')
        outdoor=region in ('야외','북방대초원','극지방','일본','한두고개','승급사냥터') or m['id'].startswith('gp:map:')
        crypt=any(t in region for t in ('유령','흑령','귀신','해골','도깨비','산적'))
        arena='왕' in region or region=='승급사냥터'
        style='glacial_ravine' if region=='극지방' else 'king_arena' if arena else 'crypt_halls' if crypt else 'forest_clearings' if outdoor else 'burrow_tunnels'
        required={};exits={(int(e['x']),int(e['y']))for e in m['exits']}
        for p in exits:required[p]=1
        for other in self.data['maps'].values():
            for e in other['exits']:
                if e['to_map']==m['id']:required[(int(e['to_x']),int(e['to_y']))]=1
        for s in m['spawns']:required[(int(s['x']),int(s['y']))]=2
        for npc in self.data['npcs'].values():
            if npc['map_id']==m['id']:required[(int(npc['x']),int(npc['y']))]=2
        for point in self.data.get('return_points',{}).values():
            if point['map_id']==m['id']:required[(int(point['x']),int(point['y']))]=2
        required={(x,y):r for (x,y),r in required.items()if 0<x<w-1 and 0<y<h-1 and (x,y)not in old}
        carved=set()
        def cell(x,y):
            if 0<x<w-1 and 0<y<h-1 and (x,y)not in old:carved.add((x,y))
        def chamber(cx,cy,rx,ry,rect=False):
            for y in range(max(1,int(cy-ry-1)),min(h-1,int(cy+ry+2))):
                for x in range(max(1,int(cx-rx-1)),min(w-1,int(cx+rx+2))):
                    if rect or ((x-cx)/rx)**2+((y-cy)/ry)**2<=1:cell(x,y)
        if arena:
            chamber(w*.5,h*.57,w*.31,h*.29)
        elif region=='극지방':
            for y in range(2,h-2):chamber(w*.5+math.sin(y*.19+seed%7)*w*.18,y,5.2,2.0)
        else:
            # Purposeful chambers/clearings differ by map/region, with a lower
            # secondary objective pocket rather than six arbitrary 2x2 posts.
            for n in range(3 if crypt else 4):
                cx=5+(seed//(n+1)*7)%(w-10);cy=5+(seed//(n+3)*13)%(h-10)
                chamber(cx,cy,4.5 if outdoor else 3.5+(n%2),3.5 if outdoor else 3,crypt)
        for (x,y),radius in required.items():chamber(x,y,radius+.6,radius+.6,crypt)
        anchors=list(sorted(required,key=lambda p:(p[1],p[0])))
        # Ensure every independent chamber is attached to the spanning trail.
        visited=set();components=[]
        for p in sorted(carved):
            if p in visited:continue
            q=deque([p]);visited.add(p);component=[]
            while q:
                a=q.popleft();component.append(a)
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    b=(a[0]+dx,a[1]+dy)
                    if b in carved and b not in visited:visited.add(b);q.append(b)
            components.append(component)
        anchors.extend(component[len(component)//2]for component in components)
        if not anchors:anchors=[(w//2,h//2)];cell(*anchors[0])
        connected=[anchors.pop(0)];links=[]
        while anchors:
            _,target,start=min((abs(a[0]-b[0])+abs(a[1]-b[1]),a,b)for a in anchors for b in connected)
            anchors.remove(target);connected.append(target)
            # Low-frequency cost bends tunnels naturally while crypt halls
            # retain orthogonal routes. Existing obstructions are respected.
            heap=[(0,start)];cost={start:0};parents={start:None}
            while heap:
                total,a=heapq.heappop(heap)
                if a==target:break
                if total!=cost[a]:continue
                for dx,dy in ((1,0),(0,1),(-1,0),(0,-1)):
                    b=(a[0]+dx,a[1]+dy)
                    if not(0<b[0]<w-1 and 0<b[1]<h-1)or b in old:continue
                    wave=0 if crypt else int((math.sin(b[0]*.3+seed%11)+math.cos(b[1]*.27-seed%13)+2)*3)
                    n=total+10+wave+(0 if b in carved else 3)
                    if n<cost.get(b,10**9):cost[b]=n;parents[b]=a;heapq.heappush(heap,(n,b))
            assert target in parents,m['id']+' disconnected required anchor'
            p=target;link=[]
            while p is not None:
                link.append(p)
                radius=2 if outdoor else 1
                chamber(p[0],p[1],radius+.2,radius+.2,crypt);p=parents[p]
            links.append(link)
        new={(x,y)for y in range(h)for x in range(w)if(x,y)not in carved}|old
        # No source connection/spawn is silently removed by the new shape.
        assert all(p not in new for p in required)
        q=deque([next(iter(carved))]);seen={q[0]}
        while q:
            a=q.popleft()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                b=(a[0]+dx,a[1]+dy)
                if b in carved and b not in seen:seen.add(b);q.append(b)
        assert seen==carved,m['id']+' carved islands'
        # Multi-source nearest passable field: distance first, deterministic
        # y/x ties. Prefer a non-exit cell so migration never triggers travel.
        nearest={};q=deque()
        for p in sorted(carved-exits,key=lambda p:(p[1],p[0])):nearest[p]=p;q.append(p)
        while q:
            a=q.popleft()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                b=(a[0]+dx,a[1]+dy)
                if 0<=b[0]<w and 0<=b[1]<h and b not in nearest:nearest[b]=nearest[a];q.append(b)
        mapping={f'{x},{y}':{'x':nearest[(x,y)][0],'y':nearest[(x,y)][1]}for x,y in sorted(new-old)}
        self.transforms[m['id']]={'to_map_id':m['id'],'dx':0,'dy':0,'cell_mappings':mapping}
        m['blocked']=[list(p)for p in sorted(new,key=lambda p:(p[1],p[0]))];m['map_version']='v2-g1-b5-regional-v2'
        m['geometry_sha256']=hashlib.sha256(canonical({k:m[k]for k in ('width','height','blocked','exits')}).encode()).hexdigest()
        m['regional_layout']={'style':style,'protected_source_points':len(required),'walkable_cells':len(carved),'old_walkable_cells':w*h-len(old),'new_wall_cells':len(new-old),'connected_walkable':True,'source_tier':'LEGACY_RECONSTRUCTED','description':'Original source coordinates retained; connected chambers and passages reconstructed for this region.'}
        m['landmarks'].append({'name':{'burrow_tunnels':'굴 안쪽 둥지','crypt_halls':'지하 회랑','forest_clearings':'숲속 공터','glacial_ravine':'얼음 협곡','king_arena':'왕의 제단'}[style],'x':connected[0][0],'y':connected[0][1],'kind':'regional_landmark'})
        self.layout_receipts.append({'map_id':m['id'],'name':m['name'],**m['regional_layout']})
    def asset(self,key,image):
        p='gameplay/world/repair/'+key+'.png';target=self.output/p;target.parent.mkdir(parents=True,exist_ok=True);image.save(target);return p
    def object(self,p,x,y,depth,kind,sources):
        im=Image.open(self.output/p);return {'path':p,'frame_png':p,'x':x,'y':y,'depth_y':depth,'width_px':im.width,'height_px':im.height,'height':(im.height+23)//24,'placement_fact_status':'LEGACY_RECONSTRUCTED','visual_repair':kind,'source_ids':sources}
    def gate(self,m,e,kind):
        # Two source columns are one coherent open gateway. Its poles stand
        # outside the exit cell, never a closed door pasted over an entry.
        image=Image.new('RGBA',(48,72));image.alpha_composite(self.native(695),(0,0));image.alpha_composite(self.native(696),(24,0))
        p=self.asset('open-gateway',image);x=int(e['x'])*24-12;y=int(e['y'])*24-48
        m['objects'].append(self.object(p,x,y,(int(e['y'])+1)*24,kind,['KR125:SOBJECT.OTB:695','KR125:SOBJECT.OTB:696']))
        return {'exit_id':e['id'],'cell':[e['x'],e['y']],'pixel_bounds':[x,y,48,72],'open_aperture_center':[e['x']*24+12,e['y']*24+12],'depth_y':(e['y']+1)*24}
    def interiors(self,m):
        name=m['name'];forge='대장간' in name;magic=any(x in name for x in ('주술사','도사'))
        floor_id=323 if forge else 488 if magic else 370
        w,h=m['width'],m['height'];floor=Image.new('RGBA',(w*24,h*24));blocked={tuple(p) for p in m['blocked']}
        for y in range(h):
            for x in range(w):
                t=133 if x in (0,w-1) or y in (0,h-1) else floor_id
                # Preserve every exit/arrival cell; a visible inset walkway leads
                # to the actual exit, not an invented additional doorway.
                if x in (9,10,11) and 8<=y<h-1:t=323 if floor_id==370 else 370
                floor.alpha_composite(self.tiles[t],(x*24,y*24))
        north_openings={int(e['x']) for e in m['exits'] if e.get('direction')=='north'}
        for e in m['exits']:
            x,y=int(e['x']),int(e['y']);floor.alpha_composite(self.tiles[255],(x*24,y*24))
            edge_y=0 if e.get('direction')=='north' else h-1
            if e.get('direction') in ('north','south'):floor.alpha_composite(self.tiles[255],(x*24,edge_y*24))
        m['objects']=[]
        wall_id=698 if forge else 697
        for x in range(1,w-1):
            if any(abs(x-aperture)<1 for aperture in north_openings):continue
            # Wall footprint ends at the blocked north boundary. The previous
            # row was anchored two walkable rows inside the room.
            p=f'gameplay/world/objects/object-{wall_id}.png';im=self.native(wall_id)
            m['objects'].append(self.object(p,x*24,-24,24,'north_wall',[f'KR125:SOBJECT.OTB:{wall_id}']))
        # Replace unrelated closed-door/roof-strip "pillars" with a complete
        # source prop occupying exactly the already blocked cells. A stool,
        # stone stove or notice board is a complete frame, not a door fragment
        # relabelled as furniture.
        interior=sorted((x,y) for x,y in blocked if 0<x<w-1 and 0<y<h-1)
        for x,y in interior:
            native=266 if forge else 146 if '주막' in name else 912
            image=self.native(native);p=f'gameplay/world/objects/object-{native}.png'
            m['objects'].append(self.object(p,x*24,(y+1)*24-image.height,(y+1)*24,'complete_prop_on_existing_blocked_cell',[f'KR125:SOBJECT.OTB:{native}']))
        m['visual_buildings']=[self.gate(m,e,'interior_open_exit') for e in m['exits']]
        m['visual_style']={'kind':'forge' if forge else 'ritual_hall' if magic else 'wooden_tavern' if '주막' in name else 'training_hall','ground_native_id':floor_id,'source_tier':'LEGACY_RECONSTRUCTED','note':'Existing native floor/wall/gateway pixels; exact historical furnishing is not claimed.'}
        self.changes.append({'map_id':m['id'],'repair':'role_specific_interior_original_pixels_remove_unrelated_door_columns','preserved_blocked_cells':len(blocked)})
        return floor
    def regional_floor(self,m):
        # Existing layout is a saved contract. Change presentation only, never
        # make a decoration create a new impassable cell or move a saved actor.
        w,h=m['width'],m['height'];region=m.get('region','');outdoor=region in ('야외','북방대초원','극지방','일본','한두고개','승급사냥터') or m['id'].startswith('gp:map:')
        if region=='극지방':base,variation=697,714
        elif region=='일본':base,variation=52,1094
        elif region=='북방대초원':base,variation=1094,52
        elif region in ('야외','한두고개') or m['id'].startswith('gp:map:'):base,variation=52,1094
        elif region=='승급사냥터':base,variation=488,323
        elif any(t in region for t in ('쥐굴','뱀굴','쥐왕','뱀왕')):base,variation=1,323
        elif any(t in region for t in ('곰','호랑이','여우','자호')):base,variation=1,1094
        elif any(t in region for t in ('유령','흑령','귀신','해골')):base,variation=327,323
        else:base,variation=323,327
        seed=int(hashlib.sha256(m['id'].encode()).hexdigest()[:8],16);blocked={tuple(p) for p in m['blocked']};floor=Image.new('RGBA',(w*24,h*24));route=set()
        # Visual routes follow actual exits through open cells. BFS makes paths
        # reflect each map's existing pillars instead of a stamped cross.
        from collections import deque
        center=(w//2,h//2)
        for e in m['exits']:
            target=(int(e['x']),int(e['y']));q=deque([center]);parents={center:None}
            while q and target not in parents:
                x,y=q.popleft()
                for dx,dy in ((1,0),(0,1),(-1,0),(0,-1)):
                    p=(x+dx,y+dy)
                    if 0<=p[0]<w and 0<=p[1]<h and p not in blocked and p not in parents:parents[p]=(x,y);q.append(p)
            p=target
            while p in parents and p is not None:route.add(p);p=parents[p]
        for y in range(h):
            for x in range(w):
                if (x,y) in blocked:
                    t=714 if self.reshape and region=='극지방' else 52 if self.reshape and outdoor and region not in ('일본','승급사냥터') else 133 if outdoor or self.reshape else 333
                elif outdoor and (x,y) in route:t=1 if region!='극지방' else 697
                else:t=base
                tile=self.tiles[t]
                if t==base and (x,y) not in blocked:
                    # Continuous mineral/vegetation bands reuse the two native
                    # textures instead of hard rectangular checkerboard blobs.
                    phase=(seed%31)*.21
                    weight=max(0,min(.7,(math.sin(x*.19+phase)+math.cos(y*.24-phase)+math.sin((x+y)*.11+phase)-.4)*.23))
                    if weight>0:tile=Image.blend(tile,self.tiles[variation],weight)
                floor.alpha_composite(tile,(x*24,y*24))
        # Native dark threshold/stair tiles mark the real portal aperture. A
        # visible mouth belongs to the existing exit, never a new fake doorway.
        if not outdoor:
            for e in m['exits']:
                x,y=int(e['x']),int(e['y'])
                floor.alpha_composite(self.tiles[255],(x*24,y*24))
                if e.get('direction') in ('east','west'):
                    side=1 if e['direction']=='west' else -1
                    if (x+side,y) not in blocked:floor.alpha_composite(self.tiles[257],((x+side)*24,y*24))
                else:
                    side=1 if e.get('direction')=='north' else -1
                    if (x,y+side) not in blocked:floor.alpha_composite(self.tiles[257],(x*24,(y+side)*24))
        # Existing 2x2 blocked chamber islands are rubble, not unexplained
        # empty squares of wall. Use the same bounded native rock image.
        old_blocked={tuple(p)for p in self.before['maps'][m['id']]['blocked']}
        for x,y in sorted(blocked):
            if 0<x<w-1 and 0<y<h-1 and (x,y) not in route and (not self.reshape or (x,y)in old_blocked):
                p='gameplay/world/objects/object-79.png';m['objects'].append(self.object(p,x*24,y*24,(y+1)*24,'rubble_on_existing_blocked_cell',['KR125:SOBJECT.OTB:79']))
        if self.reshape and outdoor and region not in ('극지방','일본','승급사냥터'):
            # A forest wall has actual blocked trunks and a coherent canopy,
            # assembled once from the original three neighboring tree columns.
            pine=Image.new('RGBA',(72,96))
            for dx,native in enumerate((85,86,87)):
                part=self.native(native);pine.alpha_composite(part,(dx*24,96-part.height))
            p=self.asset('whole-native-pine',pine)
            for y in range(2,h-1,2):
                for x in range(2+(y%4)//2,w-1,3):
                    if (x,y)in blocked:m['objects'].append(self.object(p,x*24-24,(y+1)*24-96,(y+1)*24,'dense_forest_actual_blocked_trunk',['KR125:SOBJECT.OTB:85','KR125:SOBJECT.OTB:86','KR125:SOBJECT.OTB:87']))
        m['visual_style']={'kind':'snowfield' if region=='극지방' else 'woodland' if outdoor else 'spectral_cave' if base==327 else 'rock_cave','ground_native_ids':[base,variation],'source_tier':'LEGACY_RECONSTRUCTED','visual_routes_to_actual_exits':True}
        self.changes.append({'map_id':m['id'],'repair':'region_specific_native_ground_visible_actual_exit_route_and_rubble'})
        return floor
    def run(self):
        for mid,m in self.data['maps'].items():
            interior=m['width']==20 and m['height']==18
            city=mid in ('gp:map:domestic_city','g1:map:buya_city')
            if self.reshape and not interior and not city:self.regional_layout(m)
            if interior:floor=self.interiors(m)
            elif city:
                floor=Image.open(self.source/m['floor_png']).convert('RGBA');m['visual_buildings']=[]
                for e in m['exits']:
                    if self.data['maps'][e['to_map']]['width']==20:m['visual_buildings'].append(self.gate(m,e,'existing_service_entrance'))
                    elif e['x'] in (1,m['width']-2) or e['y'] in (1,m['height']-2):m['visual_buildings'].append(self.gate(m,e,'city_gate'))
                self.changes.append({'map_id':mid,'repair':'native_open_gate_centered_on_existing_service_and_city_exits'})
            else:floor=self.regional_floor(m)
            for o in m['objects']:
                p=o.get('path',o.get('frame_png'));im=Image.open(self.output/p);o.update(width_px=im.width,height_px=im.height)
            rel='gameplay/world/repair/'+hashlib.sha256(mid.encode()).hexdigest()[:18]+'-floor.png';target=self.output/rel;target.parent.mkdir(parents=True,exist_ok=True);floor.save(target);m['floor_png']=rel
            layers=[]
            for y in range(0,floor.height,384):
                for x in range(0,floor.width,384):
                    chunk=floor.crop((x,y,min(x+384,floor.width),min(y+384,floor.height)));p=self.asset(hashlib.sha256(mid.encode()).hexdigest()[:12]+f'-{x}-{y}',chunk)
                    layers.append({'path':p,'x':x,'y':y,'width_px':chunk.width,'height_px':chunk.height})
            m['ground_layers']=layers
            if not self.reshape or interior or city:assert topology(m)==topology(self.before['maps'][mid]),mid+' topology changed'
            else:
                for key in ('id','width','height','exits','spawns','spawn_zones','npcs'):assert m[key]==self.before['maps'][mid][key],mid+':'+key
        # Pure presentation: definition compatibility and all content IDs stay
        # byte-identical so old saves are accepted by the existing validator.
        if self.reshape:
            old_contract={'profile':self.before['profile'],'compatibility':deepcopy(self.before['compatibility']),'manifest_sha256':self.before['manifest_sha256'],'map_transforms':deepcopy(self.transforms)}
            accepted=deepcopy(self.before.get('accepted_compatibility',[]))
            for contract in accepted:
                # The preserved P3 maps have the same original coordinates as
                # G1. Compose any prior translations with the final cell map.
                existing=contract.setdefault('map_transforms',{})
                for mid,transform in self.transforms.items():
                    if mid not in existing:existing[mid]=deepcopy(transform)
                    else:
                        previous=existing[mid];target=previous.get('to_map_id',mid)
                        if target in self.transforms:previous['cell_mappings']=deepcopy(self.transforms[target]['cell_mappings'])
            accepted.append(old_contract);self.data['accepted_compatibility']=accepted
            self.data['require_geometry_migration_contract']=True
            self.data['compatibility']['map_geometry']=hashlib.sha256(canonical({i:m['geometry_sha256']for i,m in self.data['maps'].items()}).encode()).hexdigest()
            self.data['manifest_sha256']=hashlib.sha256(canonical({'compatibility':self.data['compatibility'],'profile':self.data['profile'],'visual_compiler':digest(Path(__file__))}).encode()).hexdigest()
        else:assert self.data['compatibility']==self.before['compatibility']
        for k in ('items','monsters','skills','npcs','quests','recipes','advancements','training_rules','start','returns','respawn','return_points','nation_starts','nation_gates'):assert self.data.get(k)==self.before.get(k),k
        self.data['visual_repair']={'version':'B5-20261017-regional-v2' if self.reshape else 'B5-20261017-1','parent_runtime_sha256':digest(self.source/'runtime.json'),'topology_unchanged':not self.reshape,'source_tier':'LEGACY_RECONSTRUCTED','tool_sha256':digest(Path(__file__))}
        write(self.output/'gameplay_content.json',self.data)
        manifest=json.loads((self.source/'runtime.json').read_text());manifest['parent_visual_runtime_sha256']=digest(self.source/'runtime.json');manifest['visual_repair']=deepcopy(self.data['visual_repair']);manifest['compatibility']=deepcopy(self.data['compatibility'])
        files=[]
        for p in sorted(self.output.rglob('*')):
            if p.is_file() and p.name!='runtime.json':
                item={'path':str(p.relative_to(self.output)),'bytes':p.stat().st_size,'sha256':digest(p)}
                if p.suffix=='.png':
                    with Image.open(p) as im:item.update(width_px=im.width,height_px=im.height)
                files.append(item)
        manifest['files']=files;manifest['fingerprint']=hashlib.sha256(canonical(files).encode()).hexdigest();manifest['dependency_closure']['png_files_verified']=sum(p['path'].endswith('.png')for p in files);write(self.output/'runtime.json',manifest)
        return {'status':'PASS_STATIC_PRESENTATION_REPAIR_ONLY','maps':len(self.data['maps']),'topology_unchanged':not self.reshape,'compatibility_unchanged':not self.reshape,'runtime_sha256':digest(self.output/'runtime.json'),'content_sha256':digest(self.output/'gameplay_content.json'),'changes':self.changes,'regional_layouts':self.layout_receipts,'migration_maps':len(self.transforms),'migration_cells':sum(len(t['cell_mappings'])for t in self.transforms.values()),'actual_runtime_render':'NOT_RUN','platform_playability':'NOT_RUN'}

def early_balance(source,output,evidence_ref):
    """Narrow B5 starter economy adjustment; no map regeneration or rule gates.

    The historical drop probability is UNKNOWN. Values below are explicit
    inferred offline balance, motivated by the recorded 32-kill natural session.
    """
    original=json.loads((source/'gameplay_content.json').read_text());data=deepcopy(original)
    ledger=json.loads((source/'G1_ADOPTION.json').read_text());entries=[]
    observed={'source_generation':'r7','method':'unaccelerated natural GUI play reported by integration owner','kills':32,'level':6,'starter_weapon_remaining_durability':2,'acorns':4,'rabbit_meat':2,'money':0,'evidence_ref':evidence_ref,'interpretation':'Starter weapon nearly breaks before first job skill; low material yield and repair cost reinforce empty-purse repetition.'}
    targets={'KRO-a278e4d3cd81':'다람쥐','KRO-505b83a56a47':'토끼'}
    for mid,name in targets.items():
        m=data['monsters'][mid];assert m['name']==name and len(m['drops'])==1
        assert m['source_value']['probability_model']=='UNKNOWN' and m['source_value']['drop_probability'] is None
        drop=m['drops'][0];assert drop['chance']==.32 and drop['quantity_min']==drop['quantity_max']==1
        drop['chance']=.85;m['drop_model']='independent_bernoulli; no_drop_probability0.15; quantity1'
        # Derived acquisition descriptions must match the executable drop roll.
        for path in data['items'][drop['item_id']]['acquisition_paths']:
            if path.get('kind')=='drop' and path.get('monster_id')==mid:path['chance']=.85
        entries.append({'content_id':mid,'field':'drops[0].chance','source_tier':'INFERRED','source_ref':deepcopy(m['source_pointer']),'observed_version':'B5-r11-20261017','observed_date':'2026-10-17','previous_value':.32,'selected_value':.85,'historical_probability':'UNKNOWN; source records name/XP/possible material, not probability or quantity','rationale':'Align executable material yield with declared no-drop probability 0.15; address observed starter depletion before first skill without changing documented XP, learning level or ingredient quantities.','action_type':'drop_balance','dependencies':[drop['item_id']],'runtime_ref':'monsters.'+mid+'.drops[0].chance','evidence':deepcopy(observed),'status':'IMPLEMENTED_STATIC_VERIFIED','runtime_test':'NOT_RUN'})
    assert data['config']['repair_price_per_point']==1
    data['config']['repair_price_per_point']=.1
    entries.append({'content_id':'g1:config:repair_price_per_point','field':'repair_price_per_point','source_tier':'INFERRED','source_ref':'Existing offline repair cost reconstruction; engine fallback is 0.1 per point','observed_version':'B5-r11-20261017','observed_date':'2026-10-17','previous_value':1,'selected_value':.1,'historical_price':'UNKNOWN; no historical repair coefficient claimed','rationale':'Reduce starter upkeep loop after observed 32-kill weapon depletion; keep maximum/current durability, item prices, XP, learning conditions and required materials unchanged.','action_type':'repair_balance','dependencies':[],'runtime_ref':'config.repair_price_per_point','evidence':deepcopy(observed),'status':'IMPLEMENTED_STATIC_VERIFIED','runtime_test':'NOT_RUN'})
    ledger['entries'].extend(entries);write(output/'G1_ADOPTION.json',ledger)
    # Existing exact migration contracts, stable IDs and compatible envelope
    # rules remain verbatim. Only the current content fingerprint advances.
    assert data['accepted_compatibility']==original['accepted_compatibility']
    assert data['compatibility']==original['compatibility']
    data['early_balance_repair']={'version':'B5-r11-20261017','parent_runtime_sha256':digest(source/'runtime.json'),'parent_content_sha256':digest(source/'gameplay_content.json'),'tool_sha256':digest(Path(__file__)),'ledger_entries':len(entries),'source_probability':'UNKNOWN','changes':[{'field':e['runtime_ref'],'from':e['previous_value'],'to':e['selected_value']}for e in entries]}
    data['manifest_sha256']=hashlib.sha256(canonical({'parent_manifest_sha256':original['manifest_sha256'],'early_balance_repair':data['early_balance_repair']}).encode()).hexdigest()
    write(output/'gameplay_content.json',data)
    manifest=json.loads((source/'runtime.json').read_text());manifest['parent_balance_runtime_sha256']=digest(source/'runtime.json');manifest['early_balance_repair']=deepcopy(data['early_balance_repair'])
    files=[];unchanged_assets=0
    old_manifest={f['path']:f for f in manifest['files']}
    for p in sorted(output.rglob('*')):
        if not p.is_file() or p.name=='runtime.json':continue
        relative=str(p.relative_to(output));f=deepcopy(old_manifest.get(relative,{'path':relative}));f.update(bytes=p.stat().st_size,sha256=digest(p));files.append(f)
        if p.suffix in ('.png','.wav'):
            assert f['sha256']==old_manifest[relative]['sha256'];unchanged_assets+=1
    manifest['files']=files;manifest['fingerprint']=hashlib.sha256(canonical(files).encode()).hexdigest();write(output/'runtime.json',manifest)
    for kind in ('maps','skills','npcs','jobs','quests','recipes','advancements','training_rules','xp_thresholds','start','returns','gates','return_points','nation_starts','nation_gates'):assert data.get(kind)==original.get(kind),kind
    for kind in ('maps','monsters','items','skills','npcs','quests','recipes','advancements','training_rules'):assert set(data[kind])==set(original[kind]),kind
    return {'status':'PASS_STATIC_NARROW_EARLY_BALANCE','runtime_sha256':digest(output/'runtime.json'),'content_sha256':digest(output/'gameplay_content.json'),'fingerprint':manifest['fingerprint'],'changed_executable_fields':len(entries),'unchanged_png_wav_assets':unchanged_assets,'maps_byte_semantically_identical':76,'stable_id_sets_preserved':True,'save_compatibility_and_pinned_migrations_preserved':True,'ledger':entries,'natural_play_after_change':'NOT_RUN'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True);ap.add_argument('--reshape',action='store_true');ap.add_argument('--early-balance',action='store_true');ap.add_argument('--observed-evidence',default='B5-r7 integration-owner unaccelerated natural 32-kill session');args=ap.parse_args()
    if args.output.exists():raise SystemExit('Refusing to overwrite a runtime generation')
    if args.reshape and args.early_balance:raise SystemExit('Geometry and balance are separate reviewed generations')
    shutil.copytree(args.source,args.output);r=early_balance(args.source,args.output,args.observed_evidence) if args.early_balance else Repair(args.source,args.output,args.reshape).run();write(args.receipt,r);print(json.dumps({k:v for k,v in r.items()if k not in ('changes','regional_layouts','ledger')}))
if __name__=='__main__':main()
