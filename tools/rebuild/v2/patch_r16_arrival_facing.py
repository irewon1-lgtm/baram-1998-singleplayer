#!/usr/bin/env python3
"""Final data-only correction: approach is distinct from arrival facing.
Run from restoration workspace after actor/effect stages. Records code hashes.
"""
import json,sys
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,'baram/tools/rebuild/v2')
from repair_g2_world import Repair,write,digest,filehash
p=Path('private_runtime_world_r16');d=json.loads((p/'gameplay_content.json').read_text());pin={'profile':d['profile'],'compatibility':deepcopy(d['compatibility']),'manifest_sha256':d['manifest_sha256'],'map_transforms':{}}
r=object.__new__(Repair);r.data=d;r.normalize_arrival_facing()
for mid,m in d['maps'].items():
 g=json.loads((p/m['geometry_file']).read_text());m['geometry_sha256']=digest({k:g[k]for k in('width','height','ground_ids','edge_masks','blocked')}|{'exits':m['exits']})
d['accepted_compatibility'].append(pin);d['compatibility']['map_geometry']=digest({mid:m['geometry_sha256']for mid,m in d['maps'].items()});d['manifest_sha256']=digest({'parent':pin['manifest_sha256'],'arrival_facing_fixes':r.arrival_facing_fixes,'geometry':d['compatibility']['map_geometry']})
stages=[]
for name in('repair_g2_world.py','patch_r16_gather_posts.py','patch_r16_landmarks.py','patch_r16_arrival_facing.py'):
 f=Path('baram/tools/rebuild/v2')/name;stages.append({'source':str(f.relative_to('baram')),'sha256':filehash(f)})
d['single_reference_world_repair'].update(arrival_facing_fixes=r.arrival_facing_fixes,tool_sha256=filehash(Path('baram/tools/rebuild/v2/repair_g2_world.py')),deterministic_source_stages=stages)
write(p/'gameplay_content.json',d);report=json.loads((p/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json').read_text());report.update(d['single_reference_world_repair']);report['door_contracts']=[c for m in d['maps'].values()for c in m['door_contracts']];write(p/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json',report);write(Path('world-r16-repair.json'),report)
manifest=json.loads((p/'runtime.json').read_text());files=[{'path':str(f.relative_to(p)),'bytes':f.stat().st_size,'sha256':filehash(f)}for f in sorted(p.rglob('*'))if f.is_file()and f.name!='runtime.json'];manifest.update(files=files,fingerprint=digest(files),compatibility=deepcopy(d['compatibility']),input_definitions_sha256=filehash(p/'gameplay_content.json'),single_reference_world_repair=deepcopy(d['single_reference_world_repair']));write(p/'runtime.json',manifest)
print('FINAL_WORLD_ACTOR_READY',len(r.arrival_facing_fixes),filehash(p/'gameplay_content.json'),filehash(p/'runtime.json'))
