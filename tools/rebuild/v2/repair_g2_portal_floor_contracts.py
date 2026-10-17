#!/usr/bin/env python3
"""Correct paired entrance side and reconstruct coherent biome presentation.

Existing map IDs, trigger cells, collision/edge masks and content stay intact.
Native pixels come from the already restored Korean runtime. Complete original
city/interior buildings remain; wrongly assigned temple/garden chunks in caves
are retained privately, replaced with biome-appropriate native static units.
No compiler result certifies visual quality or actual OS movement.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,shutil
from collections import deque
from copy import deepcopy
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageEnhance
from repair_g2_world import Repair as Native,canonical,digest,filehash,write

VERSION='B5-r17-portal-biome-paired-side-20261017'
STEPS=((0,-1,1,4,'north'),(1,0,2,8,'east'),(0,1,4,1,'south'),(-1,0,8,2,'west'))
def direction(dx,dy):return('east'if dx>0 else'west')if abs(dx)>=abs(dy)and dx else('south'if dy>0 else'north')

class Repair:
 def __init__(self,source,native,output):
  self.source=source;self.output=output;self.data=json.loads((source/'gameplay_content.json').read_text());self.before=deepcopy(self.data)
  self.native=Native(native,output);self.tiles=self.native.tiles;self.assets={};self.placements=[];self.transforms={};self.fixes=[]
  self.geometry={mid:json.loads((source/m['geometry_file']).read_text())for mid,m in self.data['maps'].items()}
  self.structural_before=digest({mid:{'width':m['width'],'height':m['height'],'blocked':m['blocked_base64'],'edges':m.get('edge_masks_base64',''),'triggers':[[e['id'],e['x'],e['y']]for e in m['exits']]}for mid,m in self.data['maps'].items()})
 def asset(self,name,im,refs):
  p='gameplay/world/r17/'+name+'.png';q=self.output/p;q.parent.mkdir(parents=True,exist_ok=True);im.save(q)
  self.assets[p]={'runtime_path':p,'sha256':filehash(q),'source_tier':'LEGACY_RECONSTRUCTED_FROM_EXISTING_KOREAN_PIXELS','sources':[{'runtime_path':s,'sha256':filehash(self.source/s),'original_archive':'KR_1.25_winbaram.zip','original_member':'NWind.dat:SOBJECT.OTB','decoder':'existing decoded G2 generation'}for s in dict.fromkeys(refs)]};return p
 def native_image(self,n):
  p=f'gameplay/world/g2-native/objects/object-{n}.png'
  if not(self.source/p).exists():p=f'gameplay/world/objects/object-{n}.png'
  return Image.open(self.source/p).convert('RGBA'),p
 def approaches(self):
  self.choices={};self.components={};self.pairs={};lookup={}
  for mid,m in self.data['maps'].items():
   w,h=m['width'],m['height'];b=base64.b64decode(m['blocked_base64']);edge=base64.b64decode(m.get('edge_masks_base64',''))or bytes(w*h);triggers={(e['x'],e['y'])for e in m['exits']};labels=[-1]*(w*h);components=[]
   for at in range(w*h):
    x,y=at%w,at//w
    if b[at]or labels[at]>=0 or(x,y)in triggers:continue
    label=len(components);labels[at]=label;q=deque([at]);size=0
    while q:
     p=q.popleft();px,py=p%w,p//w;size+=1
     for dx,dy,s,t,_ in STEPS:
      xx,yy=px+dx,py+dy;n=yy*w+xx
      if 0<=xx<w and 0<=yy<h and labels[n]<0 and not b[n]and(xx,yy)not in triggers and not(edge[p]&s or edge[n]&t):labels[n]=label;q.append(n)
    components.append({'size':size,'required':0})
   occupied=set()
   for n in list(self.data['npcs'].values())+m.get('spawns',[])+m.get('gather_nodes',[]):
    if n.get('map_id',mid)!=mid:continue
    x,y=int(n['x']),int(n['y']);occupied.add((x,y));label=labels[y*w+x]
    if label>=0:components[label]['required']+=1
   oldcontracts={c['id']:c for c in m.get('door_contracts',[])}
   for e in m['exits']:
    key=mid,e['id'];lookup[key]=e;options=[];x,y=e['x'],e['y'];old=oldcontracts.get(e['id'],{}).get('approach_cell')
    for dx,dy,s,t,_ in STEPS:
     xx,yy=x+dx,y+dy
     if 0<=xx<w and 0<=yy<h and labels[yy*w+xx]>=0 and not(edge[y*w+x]&s or edge[yy*w+xx]&t):
      c=components[labels[yy*w+xx]];options.append((int(c['required']>0),c['size'],(xx,yy)not in occupied,[xx,yy]==old,xx,yy))
    if not options:raise ValueError('No reachable approach '+str(key))
    selected=max(options);self.choices[key]=[selected[-2],selected[-1]]
   self.components[mid]={'count':len(components),'largest':max((c['size']for c in components),default=0)}
  for key,e in lookup.items():
   mid,_=key;reverse=[r for r in self.data['maps'][e['to_map']]['exits']if r['to_map']==mid]
   r=min(reverse,key=lambda r:(abs(e['to_x']-r['x'])+abs(e['to_y']-r['y']),r['id']));self.pairs[key]=(e['to_map'],r['id'])
  for key,reverse in self.pairs.items():
   if self.pairs.get(reverse)!=key:raise ValueError('Nonmutual exit pairing '+str((key,reverse)))
  for key,e in lookup.items():
   reverse=self.pairs[key];new=self.choices[reverse];old=[e['to_x'],e['to_y']];target=lookup[reverse];e.update(to_x=new[0],to_y=new[1],direction=direction(new[0]-target['x'],new[1]-target['y']))
   if old!=new:
    self.fixes.append({'source_map':key[0],'exit_id':key[1],'target_map':e['to_map'],'previous_arrival':old,'arrival':new,'paired_reverse_exit':reverse[1]})
    transform=self.transforms.setdefault(e['to_map'],{'to_map_id':e['to_map'],'dx':0,'dy':0,'cell_mappings':{}});cell=f'{old[0]},{old[1]}'
    if cell in transform['cell_mappings']and transform['cell_mappings'][cell]!={'x':new[0],'y':new[1]}:raise ValueError('Conflicting saved landing mapping '+cell)
    transform['cell_mappings'][cell]={'x':new[0],'y':new[1]}
  for mid,m in self.data['maps'].items():
   oldc={c['id']:c for c in m.get('door_contracts',[])};contracts=[]
   for e in m['exits']:
    key=mid,e['id'];c=deepcopy(oldc[e['id']]);a=self.choices[key];reverse=self.pairs[key];c.update(approach_cell=a,entry_direction=direction(e['x']-a[0],e['y']-a[1]),arrival_direction=e['direction'],to_cell=[e['to_x'],e['to_y']],paired_reverse_exit=reverse[1],paired_landing_distance=1,reverse_arrivals=[self.choices[key]],normal_input_status='NOT_RUN_AFTER_PAIRED_SIDE_FIX');contracts.append(c)
   m['door_contracts']=contracts
 def add(self,m,path,x,y,w,h,depth,kind,**extra):
  m['objects'].append({'path':path,'x':int(x),'y':int(y),'width_px':w,'height_px':h,'depth_y':int(depth),'source_unit':kind,'visual_repair':VERSION,**extra})
 def tiled(self,ids):
  rows=[]
  for row in ids:
   rows.append(np.concatenate([np.asarray(self.tiles[t])for t in row],axis=1))
  return Image.fromarray(np.concatenate(rows,axis=0),'RGBA')
 def portal_floor(self,kind,axis):
  name='complete-threshold-'+kind+'-'+axis;p='gameplay/world/r17/'+name+'.png'
  if p in self.assets:return p
  im=Image.new('RGBA',(72,72));draw=ImageDraw.Draw(im)
  if kind=='road':
   # Three complete original stone pavers mark an actual crossing, even if
   # a protected resource prevents one roadside sign from being placed.
   for x in(0,24,48):
    tile=self.tiles[133].copy();mask=Image.new('L',(24,24));ImageDraw.Draw(mask).rounded_rectangle((1,3,22,21),radius=4,fill=255);tile.putalpha(mask);im.alpha_composite(tile,(x,24))
  else:
   # A complete low stone stair/mouth is a walkable original-texture unit.
   # It is painted below actors. The only blocking bases remain the exact
   # original two post cells, represented by separate complete stone units.
   wall=self.tiled([[323]*3]*3);mask=Image.new('L',(72,72));ImageDraw.Draw(mask).rounded_rectangle((0,3,71,68),radius=11,fill=255);wall.putalpha(mask);im.alpha_composite(wall)
   inner=self.tiled([[324]*2]*2);im.alpha_composite(inner,(12,12));draw=ImageDraw.Draw(im)
   # Native stair treads239..241 are complete floor pixels; no inventory icon
   # or disconnected side-of-cliff sprite substitutes for the entrance.
   for n in range(5):
    y=15+n*8
    for col,t in enumerate((239,240)):
     strip=self.tiles[t].crop((0,8,24,14));im.alpha_composite(strip,(12+col*24,y))
   draw.line((11,12,60,12),fill=(25,23,22,255),width=2);draw.line((11,59,60,59),fill=(158,147,130,255),width=2)
   if kind=='cave-mouth':
    hole=self.tiles[349].resize((36,36),Image.Resampling.NEAREST);im.alpha_composite(hole,(18,9))
  if axis=='NS':im=im.transpose(Image.Transpose.ROTATE_90)
  path=self.asset(name,im,[]);self.assets[path]['source_ground_ids']=[133]if kind=='road'else[323,324,239,240,349];return path
 def post(self,kind,index,axis):
  name='complete-post-'+kind+'-'+axis+'-'+str(index);path='gameplay/world/r17/'+name+'.png'
  if path in self.assets:
   im=Image.open(self.output/path);return path,im.size
  refs=[]
  if kind=='road':im,p=self.native_image(538 if index==0 else 540);refs.append(p)
  else:
   height=24 if axis=='EW'else 48;im=Image.new('RGBA',(24,height));tile=self.tiles[133]
   for y in range(0,height,24):im.alpha_composite(tile,(0,y))
   draw=ImageDraw.Draw(im);draw.line((0,0,0,height-1),fill=(53,51,47,255),width=2);draw.line((1,height-1,23,height-1),fill=(41,39,37,255),width=3);draw.line((2,1,22,1),fill=(183,179,163,255),width=2)
  path=self.asset(name,im,refs)
  if not refs:self.assets[path]['source_ground_ids']=[133]
  return path,im.size
 def biome_floor(self,mid):
  m=self.data['maps'][mid];g=self.geometry[mid];w,h=m['width'],m['height'];style=m.get('style','cave');blocked=np.frombuffer(base64.b64decode(m['blocked_base64']),dtype=np.uint8).reshape(h,w).astype(bool);yy,xx=np.mgrid[:h,:w];noise=((xx*73856093)^(yy*19349663)^int(digest(mid)[:8],16))%100
  walking={'forest':52,'plain':56,'coast':1,'snow':697,'cave':291,'crypt':324,'fire':284}.get(style,291);variation={'forest':57,'plain':58,'coast':25,'snow':714,'cave':292,'crypt':325,'fire':291}.get(style,292);wall=133 if style in('forest','plain','coast','snow')else 323
  ids=np.full((h,w),walking,dtype=np.int32);ids[(noise<8)&~blocked]=variation;ids[blocked]=wall
  unique=np.unique(ids);bank=np.stack([np.asarray(self.tiles[int(t)])for t in unique]);indices=np.searchsorted(unique,ids);pixels=bank[indices].transpose(0,2,1,3,4).reshape(h*24,w*24,4).copy()
  # A shadow is tied to each real wall edge, not to source chunk rectangles.
  for dx,dy in((0,-1),(0,1),(-1,0),(1,0)):
   neighbor=np.roll(blocked,(-dy,-dx),(0,1));edge=(~blocked)&neighbor
   for y,x in zip(*np.where(edge)):
    ys=slice(y*24,y*24+3)if dy<0 else slice(y*24+21,y*24+24)if dy>0 else slice(y*24,y*24+24)
    xs=slice(x*24,x*24+3)if dx<0 else slice(x*24+21,x*24+24)if dx>0 else slice(x*24,x*24+24)
    pixels[ys,xs,:3]=(pixels[ys,xs,:3].astype(np.uint16)*64//100).astype(np.uint8)
  floor=Image.fromarray(pixels,'RGBA');layers=[];chunks={}
  for cy in range(0,h,16):
   for cx in range(0,w,16):
    chunk=floor.crop((cx*24,cy*24,min(w,cx+16)*24,min(h,cy+16)*24));rel='gameplay/world/r17/floor-'+digest(chunk.tobytes())[:24]+'.png';p=self.output/rel
    if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);chunk.save(p)
    o={'path':rel,'x':cx*24,'y':cy*24,'width_px':chunk.width,'height_px':chunk.height};layers.append(o);chunks[f'{cx//16},{cy//16}']=o
  m.update(ground_layers=layers,ground_chunks=chunks,presentation_ground_ids=ids.reshape(-1).tolist(),visual_style={'kind':'coherent_'+style,'source_tier':'LEGACY_RECONSTRUCTED','walkable_native_ground_ids':[walking,variation],'blocked_native_ground_id':wall,'floor_follows_actual_collision':True,'wall_edge_shadow':True})
  # Inappropriate original temple/garden/room chunks are not claimed as caves.
  # Their raw objects stay in immutable source/history; only appropriate native
  # rock/torch/tree families populate the final presentation of each biome.
  previous=m['objects'];m['objects']=[];added=0
  if style in('forest','plain','coast','snow'):
   path='gameplay/world/r16/native-complete-pine.png'
   for y in range(3,h-3,5):
    for x in range(2,w-4,5):
     if all(blocked[y,x+d]for d in range(3))and not blocked[y+1,x+1]:self.add(m,path,x*24,(y+1)*24-96,72,96,(y+1)*24,'complete native biome tree');added+=1
  else:
   rock,rp=self.native_image(78);torch,tp=self.native_image(449)
   for y in range(3,h-3,7):
    for x in range(3,w-3,11):
     if blocked[y,x]and not blocked[y+1,x]:
      im,p=(torch,tp)if(x+y)%3==0 else(rock,rp);self.add(m,p,x*24,(y+1)*24-im.height,im.width,im.height,(y+1)*24,'complete native biome rock or torch');added+=1
  self.placements.append({'map_id':mid,'style':style,'repair':'replace theme-mismatched native static district objects with appropriate complete native biome units; floor/wall pixels follow preserved actual masks','previous_static_objects':len(previous),'new_biome_props':added,'walkable_ground_ids':[walking,variation],'blocked_ground_id':wall,'raw_objects_preserved_in_source_and_history':True,'actual_render':'NOT_RUN'})
 def portals(self,mid):
  m=self.data['maps'][mid]
  if m['width']<=20:return
  m['objects']=[o for o in m['objects']if not o.get('source_unit','').startswith('directional ')]
  for c in m['door_contracts']:
   if c.get('building_id'):continue
   ex,ey=c['trigger_cell'];old=next(v for v in self.before['maps'][mid]['door_contracts']if v['id']==c['id']);old_a=old['approach_cell'];axis='EW'if old_a[0]!=ex else'NS';style=m.get('style','cave');target=self.data['maps'][c['to_map']]
   kind='gate'if style=='city'else'stairs'if style in('cave','crypt','fire')else'cave-mouth'if target.get('style')in('cave','crypt','fire')else'road';p=self.portal_floor(kind,axis)
   self.add(m,p,(ex-1)*24,(ey-1)*24,72,72,-1000000,'complete native-texture '+kind+' threshold',exit_id=c['id'],portal_axis=axis,art_role='walkable threshold below actors')
   if kind=='gate'and axis=='NS'and len(c.get('solid_post_cells',[]))==2:
    name='complete-city-gateway-NS';gp='gameplay/world/r17/'+name+'.png'
    if gp not in self.assets:
     left,lp=self.native_image(695);right,rp=self.native_image(696);im=Image.new('RGBA',(72,72));im.alpha_composite(left);im.alpha_composite(right,(48,0));im.alpha_composite(left.crop((0,0,24,24)),(24,0));gp=self.asset(name,im,[lp,rp])
    self.add(m,gp,(ex-1)*24,(ey-2)*24,72,72,(ey+1)*24,'complete original native city gateway',exit_id=c['id'])
   else:
    for n,(x,y)in enumerate(c.get('solid_post_cells',[])):
     pp,size=self.post('road'if kind=='road'else'stone',n,axis);self.add(m,pp,x*24,(y+1)*24-size[1],size[0],size[1],(y+1)*24,'complete blocking portal base',exit_id=c['id'])
   c.update(portal_art={'kind':kind,'axis':axis,'complete_floor_unit':p,'source_fact_status':'LEGACY_RECONSTRUCTED','actual_render':'NOT_RUN'},source_approach_component='largest reachable component with gameplay positions, excluding all triggers',normal_input_status='NOT_RUN_R17')
 def map_metadata(self,mid):
  m=self.data['maps'][mid];g=self.geometry[mid];w,h=m['width'],m['height'];buckets={}
  for n,o in enumerate(m['objects']):
   for by in range(max(0,int(o['y']//384)),min((h-1)//16,int((o['y']+o['height_px']-1)//384))+1):
    for bx in range(max(0,int(o['x']//384)),min((w-1)//16,int((o['x']+o['width_px']-1)//384))+1):buckets.setdefault(f'{bx},{by}',[]).append(n)
  m['object_buckets']=buckets
  overview=Image.new('RGBA',(w*2,h*2))
  for o in m['ground_layers']+sorted(m['objects'],key=lambda o:o['depth_y']):
   im=Image.open(self.output/o['path']).convert('RGBA');im=im.resize((max(1,im.width//12),max(1,im.height//12)),Image.Resampling.NEAREST);overview.alpha_composite(im,(int(o['x']//12),int(o['y']//12)))
  rel='gameplay/world/r17/overview-'+digest(mid)[:20]+'.png';overview.convert('RGB').save(self.output/rel);m['overview_png']=rel
  history=self.output/'gameplay/geometry/history-r16'/Path(m['geometry_file']).name;history.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.source/m['geometry_file'],history)
  g['objects']=deepcopy(m['objects']);write(self.output/m['geometry_file'],g);m['geometry_sha256']=digest({k:g[k]for k in('width','height','ground_ids','edge_masks','blocked')}|{'exits':m['exits']})
 def migration(self):
  accepted=deepcopy(self.before['accepted_compatibility'])
  for contract in accepted:
   transforms=contract.setdefault('map_transforms',{})
   for mid,new in self.transforms.items():
    prior=transforms.get(mid)
    if prior is None:transforms[mid]=deepcopy(new);continue
    cells=prior.setdefault('cell_mappings',{})
    for key,value in list(cells.items()):
     target=f'{value["x"]},{value["y"]}'
     if target in new['cell_mappings']:cells[key]=deepcopy(new['cell_mappings'][target])
    dx,dy=prior.get('dx',0),prior.get('dy',0)
    for key,value in new['cell_mappings'].items():
     x,y=map(int,key.split(','));source=f'{x-dx},{y-dy}'
     if x>=dx and y>=dy and source not in cells:cells[source]=deepcopy(value)
  accepted.append({'profile':self.before['profile'],'compatibility':deepcopy(self.before['compatibility']),'manifest_sha256':self.before['manifest_sha256'],'map_transforms':deepcopy(self.transforms)})
  self.data['accepted_compatibility']=accepted;self.data['compatibility']['map_geometry']=digest({mid:m['geometry_sha256']for mid,m in self.data['maps'].items()});self.data['manifest_sha256']=digest({'parent':self.before['manifest_sha256'],'version':VERSION,'geometry':self.data['compatibility']['map_geometry'],'tool':filehash(Path(__file__))})
 def run(self):
  self.approaches()
  cities=set(self.data['g2_world']['city_maps'])
  for mid,m in self.data['maps'].items():
   if m['width']>20 and mid not in cities:self.biome_floor(mid)
   self.portals(mid);self.map_metadata(mid)
  self.migration()
  structural=digest({mid:{'width':m['width'],'height':m['height'],'blocked':m['blocked_base64'],'edges':m.get('edge_masks_base64',''),'triggers':[[e['id'],e['x'],e['y']]for e in m['exits']]}for mid,m in self.data['maps'].items()})
  assert structural==self.structural_before
  for kind in('items','monsters','skills','npcs','quests','recipes','advancements','training_rules','jobs','start','returns','respawn','gates','return_points','nation_starts','nation_gates','visual_effect_repair'):assert self.data.get(kind)==self.before.get(kind),kind
  for mid,m in self.data['maps'].items():
   for c in m['door_contracts']:
    pair=self.pairs[(mid,c['id'])];reverse=next(v for v in self.data['maps'][pair[0]]['door_contracts']if v['id']==pair[1]);assert c['to_cell']==reverse['approach_cell']
  report={'schema':'baram.g2.portal-biome-paired-side/1','version':VERSION,'status':'IMPLEMENTED_STATIC_ONLY','maps':len(self.data['maps']),'exits':sum(len(m['exits'])for m in self.data['maps'].values()),'source_content_sha256':filehash(self.source/'gameplay_content.json'),'source_runtime_sha256':filehash(self.source/'runtime.json'),'tool_sha256':filehash(Path(__file__)),'structural_collision_trigger_fingerprint':structural,'collision_masks_dimensions_trigger_ids_coordinates_unchanged':True,'paired_arrival_fixes':self.fixes,'migration_maps':len(self.transforms),'migration_cells':sum(len(t['cell_mappings'])for t in self.transforms.values()),'biome_reconstructions':self.placements,'source_assets':list(self.assets.values()),'source_native_floor_members':['NWind.dat:tilea.bmp','NWind.dat:tileb.bmp','NWind.dat:tilec.bmp','NWind.dat:windland.pal'],'visual_quality':'NOT_RUN','ordinary_input':'NOT_RUN_AFTER_PAIRED_SIDE_FIX','native_platform':'NOT_RUN'}
  self.data['portal_biome_paired_side_repair']={k:v for k,v in report.items()if k not in('source_assets','biome_reconstructions','paired_arrival_fixes')};write(self.output/'G2_R17_PORTAL_BIOME_CONTRACTS.json',report);write(self.output/'G2_R17_MAP_MIGRATION.json',{'source_manifest_sha256':self.before['manifest_sha256'],'map_transforms':self.transforms});write(self.output/'gameplay_content.json',self.data)
  manifest=json.loads((self.source/'runtime.json').read_text());files=[]
  for p in sorted(self.output.rglob('*')):
   if p.is_file()and p.name!='runtime.json':files.append({'path':str(p.relative_to(self.output)),'bytes':p.stat().st_size,'sha256':filehash(p)})
  manifest.update(files=files,fingerprint=digest(files),compatibility=deepcopy(self.data['compatibility']),input_definitions_sha256=filehash(self.output/'gameplay_content.json'),portal_biome_paired_side_repair=deepcopy(self.data['portal_biome_paired_side_repair']));write(self.output/'runtime.json',manifest);return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--native-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Refusing to overwrite existing runtime generation')
 shutil.copytree(a.source,a.output);r=Repair(a.source,a.native_source,a.output).run();write(a.receipt,r);print(canonical({k:v for k,v in r.items()if k not in('source_assets','biome_reconstructions','paired_arrival_fixes')}))
if __name__=='__main__':main()
