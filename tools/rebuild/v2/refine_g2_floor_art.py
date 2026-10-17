#!/usr/bin/env python3
"""Bounded R17 visual refinement; no collision/object/door/gameplay changes.

Replace high-contrast whole-cell grass variation with one coherent native
meadow and sparse complete native foliage. Stamp small original gray outcrop
clusters wholly within blocked wall mass. All existing object/portal pixels,
contract coordinates, normal-input physics and save identity remain unchanged.
"""
import argparse,json,shutil,hashlib
from pathlib import Path
from copy import deepcopy
import numpy as np
from PIL import Image
from repair_g2_world import Repair as Native,write,digest,filehash

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--native-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Refusing existing generation')
 shutil.copytree(a.source,a.output);d=json.loads((a.source/'gameplay_content.json').read_text());before=deepcopy(d);native=Native(a.native_source,a.output);rows=[];sources={};cities=set(d['g2_world']['city_maps'])
 for number in(75,76,78,79):
  im,path=native.native(number);sources[number]=(im,path)
 cluster=Image.new('RGBA',(72,48))
 for number,pos in((78,(0,16)),(79,(19,2)),(78,(36,0)),(79,(48,23))):cluster.alpha_composite(sources[number][0],pos)
 for mid,m in d['maps'].items():
  if m['width']<=20 or mid in cities:continue
  w,h=m['width'],m['height'];style=m.get('style','cave');blocked=np.frombuffer(__import__('base64').b64decode(m['blocked_base64']),dtype=np.uint8).reshape(h,w).astype(bool);floor=Image.new('RGBA',(w*24,h*24))
  for o in m['ground_layers']:floor.alpha_composite(Image.open(a.source/o['path']).convert('RGBA'),(o['x'],o['y']))
  base=52 if style in('forest','plain')else int(m['visual_style']['walkable_native_ground_ids'][0]);pixels=np.asarray(floor).copy();foliage=0;outcrops=0;seed=int(digest(mid)[:8],16)
  if style in('forest','plain','coast','snow'):
   # One continuous source texture: no high-contrast 24px patch lottery.
   grass=np.tile(np.asarray(native.tiles[base]),(h,w,1));walk_pixels=np.repeat(np.repeat(~blocked,24,0),24,1);pixels[walk_pixels]=grass[walk_pixels]
   for dx,dy in((0,-1),(0,1),(-1,0),(1,0)):
    edge=(~blocked)&np.roll(blocked,(-dy,-dx),(0,1))
    for y,x in zip(*np.where(edge)):
     ys=slice(y*24,y*24+3)if dy<0 else slice(y*24+21,y*24+24)if dy>0 else slice(y*24,y*24+24);xs=slice(x*24,x*24+3)if dx<0 else slice(x*24+21,x*24+24)if dx>0 else slice(x*24,x*24+24);pixels[ys,xs,:3]=(pixels[ys,xs,:3].astype(np.uint16)*64//100).astype(np.uint8)
   floor=Image.fromarray(pixels,'RGBA')
   if style in('forest','plain'):
    for y in range(2,h-2):
     for x in range(2,w-2):
      value=int(digest([seed,x,y])[:8],16)
      if value%113 or blocked[y,x]or any(abs(x-e['x'])+abs(y-e['y'])<=3 for e in m['exits']):continue
      im=sources[75 if value&1 else 76][0];floor.alpha_composite(im,(x*24+(value//7)%7-3,y*24+(value//17)%7-3));foliage+=1
  else:floor=Image.fromarray(pixels,'RGBA')
  # Original low rock clusters break large wall sheets without introducing
  # a new collision cell, new raised prop, or imagery across a walkable cell.
  for y in range(2,h-4):
   for x in range(2,w-4):
    value=int(digest([seed,'rock',x,y])[:8],16)
    if value%173 or not blocked[y:y+2,x:x+3].all()or any(abs(x-e['x'])+abs(y-e['y'])<=4 for e in m['exits']):continue
    floor.alpha_composite(cluster if value&1 else cluster.transpose(Image.Transpose.FLIP_LEFT_RIGHT),(x*24,y*24));outcrops+=1
  layers=[];chunks={}
  for cy in range(0,h,16):
   for cx in range(0,w,16):
    chunk=floor.crop((cx*24,cy*24,min(w,cx+16)*24,min(h,cy+16)*24));rel='gameplay/world/r17-art/floor-'+digest(chunk.tobytes())[:24]+'.png';target=a.output/rel
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);chunk.save(target)
    o={'path':rel,'x':cx*24,'y':cy*24,'width_px':chunk.width,'height_px':chunk.height};layers.append(o);chunks[f'{cx//16},{cy//16}']=o
  m.update(ground_layers=layers,ground_chunks=chunks);m['visual_style']['meadow_refinement']='continuous native meadow; sparse original small foliage'if style in('forest','plain')else'preserved walkable native floor';m['visual_style']['blocked_outcrop_clusters']=outcrops
  if style in('forest','plain','coast','snow'):m['presentation_ground_ids']=[133 if blocked[y,x]else base for y in range(h)for x in range(w)];m['visual_style']['walkable_native_ground_ids']=[base]
  overview=floor.resize((w*2,h*2),Image.Resampling.NEAREST)
  for o in sorted(m['objects'],key=lambda o:o['depth_y']):
   im=Image.open(a.output/o['path']).convert('RGBA');im=im.resize((max(1,im.width//12),max(1,im.height//12)),Image.Resampling.NEAREST);overview.alpha_composite(im,(int(o['x']//12),int(o['y']//12)))
  rel='gameplay/world/r17-art/overview-'+digest(mid)[:20]+'.png';overview.convert('RGB').save(a.output/rel);m['overview_png']=rel;rows.append({'map_id':mid,'style':style,'native_base_ground':base,'small_native_foliage':foliage,'outcrop_clusters_wholly_on_blocked_mass':outcrops})
 for mid,m in d['maps'].items():
  for key in('id','width','height','blocked_base64','edge_masks_base64','objects','door_contracts','exits','spawns','npcs','geometry_sha256'):assert m.get(key)==before['maps'][mid].get(key),(mid,key)
 for key in d:
  if key!='maps':assert d[key]==before[key],key
 report={'schema':'baram.g2.bounded-floor-art/1','status':'IMPLEMENTED_ART_ONLY_NOT_VISUAL_PASS','tool_sha256':filehash(Path(__file__)),'source_content_sha256':filehash(a.source/'gameplay_content.json'),'source_runtime_sha256':filehash(a.source/'runtime.json'),'all_objects_doors_trigger_landing_masks_and_save_identity_unchanged':True,'maps':rows,'original_source_sprites':[{'id':n,'path':path,'sha256':filehash(a.source/path),'archive':'KR_1.25_winbaram.zip','member':'NWind.dat:SOBJECT.OTB'}for n,(_,path)in sources.items()],'actual_visual_review':'NOT_RUN'}
 d['bounded_floor_art_refinement']={k:v for k,v in report.items()if k not in('maps','original_source_sprites')};write(a.output/'gameplay_content.json',d);write(a.output/'G2_R17_FLOOR_ART_REFINEMENT.json',report);write(a.receipt,report)
 manifest=json.loads((a.source/'runtime.json').read_text());files=[{'path':str(f.relative_to(a.output)),'bytes':f.stat().st_size,'sha256':filehash(f)}for f in sorted(a.output.rglob('*'))if f.is_file()and f.name!='runtime.json'];manifest.update(files=files,fingerprint=digest(files),input_definitions_sha256=filehash(a.output/'gameplay_content.json'),bounded_floor_art_refinement=deepcopy(d['bounded_floor_art_refinement']));write(a.output/'runtime.json',manifest);print('ART_READY',filehash(a.output/'gameplay_content.json'),filehash(a.output/'runtime.json'))
if __name__=='__main__':main()
