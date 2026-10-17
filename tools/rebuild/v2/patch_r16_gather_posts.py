import json,base64,hashlib,sys
from pathlib import Path
from copy import deepcopy
from PIL import Image
sys.path.insert(0,'baram/tools/rebuild/v2');from repair_g2_world import write,digest,filehash
p=Path('private_runtime_world_r16');d=json.loads((p/'gameplay_content.json').read_text());old=json.load(open('private_runtime/gameplay_content.json'));pin={'profile':d['profile'],'compatibility':deepcopy(d['compatibility']),'manifest_sha256':d['manifest_sha256'],'map_transforms':{}};fixed=[]
for mid,m in d['maps'].items():
 b=bytearray(base64.b64decode(m['blocked_base64']));oldb=base64.b64decode(old['maps'][mid]['blocked_base64']);bad={(n['x'],n['y'])for n in m.get('gather_nodes',[])if b[n['y']*m['width']+n['x']]and not oldb[n['y']*m['width']+n['x']]}
 if not bad:continue
 removed=[];kept=[]
 for o in m['objects']:
  cell=(int(o['x'])//24,int(o['depth_y'])//24-1)
  if o.get('source_unit','').startswith('directional ')and cell in bad:removed.append(o)
  else:kept.append(o)
 m['objects']=kept
 for x,y in bad:b[y*m['width']+x]=0
 for c in m['door_contracts']:c['solid_post_cells']=[s for s in c.get('solid_post_cells',[])if tuple(s)not in bad]
 m['blocked_base64']=base64.b64encode(b).decode();g=json.loads((p/m['geometry_file']).read_text());g['blocked']=[s for s in g['blocked']if tuple(s)not in bad];g['objects']=deepcopy(kept);write(p/m['geometry_file'],g);m['geometry_sha256']=digest({k:g[k]for k in('width','height','ground_ids','edge_masks','blocked')}|{'exits':m['exits']})
 buckets={}
 for n,o in enumerate(kept):
  for by in range(max(0,int(o['y']//384)),min((m['height']-1)//16,int((o['y']+o['height_px']-1)//384))+1):
   for bx in range(max(0,int(o['x']//384)),min((m['width']-1)//16,int((o['x']+o['width_px']-1)//384))+1):buckets.setdefault(f'{bx},{by}',[]).append(n)
 m['object_buckets']=buckets
 overview=Image.new('RGBA',(m['width']*2,m['height']*2))
 for o in m['ground_layers']+sorted(kept,key=lambda o:o['depth_y']):
  im=Image.open(p/o['path']).convert('RGBA');im=im.resize((max(1,im.width//12),max(1,im.height//12)),Image.Resampling.NEAREST);overview.alpha_composite(im,(int(o['x']//12),int(o['y']//12)))
 overview.convert('RGB').save(p/m['overview_png']);fixed.append({'map_id':mid,'gather_cells':sorted([list(c)for c in bad]),'removed_directional_posts':len(removed)})
d['accepted_compatibility'].append(pin);d['compatibility']['map_geometry']=digest({mid:m['geometry_sha256']for mid,m in d['maps'].items()});d['manifest_sha256']=digest({'parent':pin['manifest_sha256'],'gather_post_conflict_repair':fixed,'geometry':d['compatibility']['map_geometry']});d['single_reference_world_repair']['gather_post_conflict_repair']=fixed;d['single_reference_world_repair']['tool_sha256']=filehash(Path('baram/tools/rebuild/v2/repair_g2_world.py'));write(p/'gameplay_content.json',d)
r=json.loads((p/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json').read_text());r.update(gather_post_conflict_repair=fixed,tool_sha256=d['single_reference_world_repair']['tool_sha256']);r['door_contracts']=[c for m in d['maps'].values()for c in m['door_contracts']];write(p/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json',r);write(Path('world-r16-repair.json'),r)
manifest=json.loads((p/'runtime.json').read_text());files=[{'path':str(f.relative_to(p)),'bytes':f.stat().st_size,'sha256':filehash(f)}for f in sorted(p.rglob('*'))if f.is_file()and f.name!='runtime.json'];manifest.update(files=files,fingerprint=digest(files),compatibility=deepcopy(d['compatibility']),input_definitions_sha256=filehash(p/'gameplay_content.json'));write(p/'runtime.json',manifest);print('FINAL_GEOMETRY_READY',len(fixed),filehash(p/'gameplay_content.json'),filehash(p/'runtime.json'))
