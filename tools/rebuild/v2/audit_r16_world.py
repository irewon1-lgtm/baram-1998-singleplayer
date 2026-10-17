import json,base64,hashlib,sys
from pathlib import Path
from collections import deque
p=Path(sys.argv[1]if len(sys.argv)>1 else'private_runtime_world_r16');data=json.loads((p/'gameplay_content.json').read_text());old=json.load(open((Path(sys.argv[2])if len(sys.argv)>2 else Path('private_runtime'))/'gameplay_content.json'));fail=[];checks=[];far=[];total=0
for mid,m in data['maps'].items():
 w,h=m['width'],m['height'];b=base64.b64decode(m['blocked_base64']);e=base64.b64decode(m.get('edge_masks_base64',''));g=json.loads((p/m['geometry_file']).read_text());blocked=set(map(tuple,g['blocked']));assert len(b)==w*h
 for d in m['door_contracts']:
  x,y=d['trigger_cell'];a=d['approach_cell']
  if b[y*w+x]:fail.append([mid,d['id'],'trigger_blocked'])
  if a is None or b[a[1]*w+a[0]]:fail.append([mid,d['id'],'approach_blocked'])
  if a:
   dx,dy=x-a[0],y-a[1];mask={(0,-1):(1,4),(1,0):(2,8),(0,1):(4,1),(-1,0):(8,2)}.get((dx,dy))
   if not mask or (e and (e[a[1]*w+a[0]]&mask[0]or e[y*w+x]&mask[1])):fail.append([mid,d['id'],'approach_edge_blocked'])
  for sx,sy in d.get('solid_post_cells',[]):
   if not b[sy*w+sx]:fail.append([mid,d['id'],'visible_post_not_blocked'])
 for ex in m['exits']:
  back=[r for r in data['maps'][ex['to_map']]['exits']if r['to_map']==mid];distance=min(abs(ex['to_x']-r['x'])+abs(ex['to_y']-r['y'])for r in back)if back else None
  if distance is None or distance>3:far.append([mid,ex['id'],distance])
  dm=data['maps'][ex['to_map']];bb=base64.b64decode(dm['blocked_base64'])
  if bb[ex['to_y']*dm['width']+ex['to_x']]:fail.append([mid,ex['id'],'landing_blocked'])
 # Prove actual movement topology connects all exits within each map, using
 # production two-sided masks. This is static graph evidence, not OS input.
 starts=[(int(r['to_x']),int(r['to_y']))for mm in data['maps'].values()for r in mm['exits']if r['to_map']==mid]
 if not starts:starts=[tuple(data['start'][k]for k in('x','y'))]if data['start']['map_id']==mid else []
 if starts:
  sx,sy=starts[0];q=deque([(sx,sy)]);seen={(sx,sy)}
  while q:
   x,y=q.popleft();at=y*w+x
   for dx,dy,mask,reverse in((0,-1,1,4),(1,0,2,8),(0,1,4,1),(-1,0,8,2)):
    xx,yy=x+dx,y+dy;key=xx,yy
    if 0<=xx<w and 0<=yy<h and key not in seen and not b[yy*w+xx] and(not e or not(e[at]&mask or e[yy*w+xx]&reverse)):seen.add(key);q.append(key)
  for ex in m['exits']:
   if(ex['x'],ex['y'])not in seen:fail.append([mid,ex['id'],'exit_disconnected'])
  for npc in data['npcs'].values():
   if npc['map_id']==mid and(npc['x'],npc['y'])not in seen:fail.append([mid,npc['id'],'npc_disconnected'])
  total+=len(seen)
 checks.append({'map_id':mid,'exits':len(m['exits']),'posts':sum(len(d.get('solid_post_cells',[]))for d in m['door_contracts']),'maximum_floor_chunk_dimension':max(max(o['width_px'],o['height_px'])for o in m['ground_layers'])})
for mid,t in json.loads((p/('G2_R17_MAP_MIGRATION.json'if(p/'G2_R17_MAP_MIGRATION.json').exists()else'G2_R16_MAP_MIGRATION.json')).read_text())['map_transforms'].items():
 m=data['maps'][mid];b=base64.b64decode(m['blocked_base64']);e=base64.b64decode(m.get('edge_masks_base64',''))
 for key,v in t['cell_mappings'].items():
  at=v['y']*m['width']+v['x']
  if b[at]:fail.append([mid,key,'unsafe_migration_target',v])
result={'status':'PASS_STATIC_GEOMETRY'if not fail and not far else'FAIL','scope':'static two-sided directional collision graph, protected source/target door cells, visible post footprints, paired landing distance and explicit migration targets; no render or ordinary-input PASS','failures':fail,'far_landings':far,'maps':checks,'reachable_cells':total,'migration_valid_position_policy':'Production GameplayState.valid_position checks bounds and blocked bytes; directional edge bits are separately checked for approach can_step, not treated as occupied cells. Prior all-edge-zero audit was stricter than production and preserved separately.','content_sha256':hashlib.sha256((p/'gameplay_content.json').read_bytes()).hexdigest()}
Path('evidence').mkdir(exist_ok=True);Path('evidence/world-r17-static-geometry.json'if 'r17'in p.name else'evidence/world-r16-static-geometry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='maps'},ensure_ascii=False))
