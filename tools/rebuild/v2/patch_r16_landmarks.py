import json,sys
from pathlib import Path
sys.path.insert(0,'baram/tools/rebuild/v2');from repair_g2_world import write,digest,filehash
p=Path('private_runtime_world_r16');d=json.loads((p/'gameplay_content.json').read_text());fixes=[]
for mid in d['g2_world']['city_maps']:
 m=d['maps'][mid]
 for lm in m['landmarks']:
  old=[lm['x'],lm['y']];cardinal={'북문':(140,3),'남문':(140,276),'동문':(276,140),'서문':(3,140)}
  if lm['name']in cardinal:lm['x'],lm['y']=cardinal[lm['name']]
  for e in m['exits']:
   if d['maps'][e['to_map']]['width']>20 and lm['name']==d['maps'][e['to_map']]['name']:lm.update(x=e['x'],y=e['y'])
  if[lm['x'],lm['y']]!=old:fixes.append({'map_id':mid,'name':lm['name'],'previous':old,'to':[lm['x'],lm['y']]})
 if mid=='g1:map:buya_city':m['landmarks']=[lm for lm in m['landmarks']if lm['name']not in('북문','서문')]
d['single_reference_world_repair']['landmark_coordinate_fixes']=fixes;d['single_reference_world_repair']['tool_sha256']=filehash(Path('baram/tools/rebuild/v2/repair_g2_world.py'));write(p/'gameplay_content.json',d)
r=json.loads((p/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json').read_text());r['landmark_coordinate_fixes']=fixes;r['tool_sha256']=d['single_reference_world_repair']['tool_sha256'];write(p/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json',r);write(Path('world-r16-repair.json'),r)
manifest=json.loads((p/'runtime.json').read_text());files=[{'path':str(f.relative_to(p)),'bytes':f.stat().st_size,'sha256':filehash(f)}for f in sorted(p.rglob('*'))if f.is_file()and f.name!='runtime.json'];manifest.update(files=files,fingerprint=digest(files),input_definitions_sha256=filehash(p/'gameplay_content.json'));write(p/'runtime.json',manifest)
print('FINAL_WORLD_ACTOR_READY',filehash(p/'gameplay_content.json'),filehash(p/'runtime.json'))
