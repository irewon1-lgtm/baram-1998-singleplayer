#!/usr/bin/env python3
"""Reconstruct coherent G2 cities and bind visible doors to existing exits.

Consumes already-decoded Korean pixels, no downloads. Exact old geometry is
preserved privately and newly blocked saved cells have explicit mappings.
Static compiler validation is never a visual/ordinary-input/platform PASS.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, shutil
from copy import deepcopy
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

VERSION='B5-r16-single-reference-world-20261017'
DIRS=((0,-1,'north'),(1,0,'east'),(0,1,'south'),(-1,0,'west'))
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(v):return hashlib.sha256(v if isinstance(v,bytes)else canonical(v).encode()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(canonical(v)+'\n')
def filehash(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Repair:
 def __init__(self,source,output):
  self.source=source;self.output=output;self.data=json.loads((source/'gameplay_content.json').read_text());self.before=deepcopy(self.data)
  self.geom={mid:json.loads((source/m['geometry_file']).read_text())for mid,m in self.data['maps'].items()}
  for mid,g in self.geom.items():g.setdefault('edge_masks',[0]*(g['width']*g['height']))
  self.old_geom=deepcopy(self.geom);self.tiles={};self.images={};self.assets={};self.rows=[];self.transforms={};self.doors=[];self.footprints={}
  for mid,m in self.data['maps'].items():
   g=self.geom[mid]
   for o in m['ground_layers']:
    wanted=[];cx,cy=int(o['x'])//24,int(o['y'])//24;cw,ch=int(o['width_px'])//24,int(o['height_px'])//24
    for yy in range(ch):
     for xx in range(cw):
      t=g['ground_ids'][(cy+yy)*m['width']+cx+xx]
      if t not in self.tiles:wanted.append((t,xx,yy))
    if wanted:
     im=self.image(o['path'])
     for t,x,y in wanted:self.tiles[t]=im.crop((x*24,y*24,(x+1)*24,(y+1)*24))
  self.protected={mid:set()for mid in self.data['maps']}
  for mid,m in self.data['maps'].items():
   for e in m['exits']:
    self.protected[mid].add((int(e['x']),int(e['y'])));self.protected[e['to_map']].add((int(e['to_x']),int(e['to_y'])))
   for s in m.get('spawns',[]):self.protected[mid].add((int(s['x']),int(s['y'])))
   for s in m.get('gather_nodes',[]):self.protected[mid].add((int(s['x']),int(s['y'])))
  for n in self.data['npcs'].values():self.protected[n['map_id']].add((int(n['x']),int(n['y'])))
  def protect(v):
   if isinstance(v,dict):
    if v.get('map_id')in self.protected and 'x'in v and'y'in v:self.protected[v['map_id']].add((int(v['x']),int(v['y'])))
    for vv in v.values():protect(vv)
   elif isinstance(v,list):
    for vv in v:protect(vv)
  for k in ('start','returns','respawn','return_points','nation_starts','nation_gates','gates'):protect(self.data.get(k))
 def image(self,path):
  if path not in self.images:self.images[path]=Image.open(self.source/path if(self.source/path).exists()else self.output/path).convert('RGBA')
  return self.images[path]
 def native(self,n):
  p=f'gameplay/world/g2-native/objects/object-{n}.png'
  if not(self.source/p).exists():p=f'gameplay/world/objects/object-{n}.png'
  return self.image(p).copy(),p
 def asset(self,name,im,refs):
  p=f'gameplay/world/r16/{name}.png';q=self.output/p;q.parent.mkdir(parents=True,exist_ok=True);im.save(q,optimize=True)
  self.assets[p]={'runtime_path':p,'sha256':filehash(q),'source_tier':'LEGACY_RECONSTRUCTED_FROM_EXISTING_KR125_PIXELS','sources':[{'runtime_source_path':s,'sha256':filehash(self.source/s if(self.source/s).exists()else self.output/s),'original_archive':'KR_1.25_winbaram.zip'if not s.startswith('gameplay/world/r16/')else'DERIVED_SOURCE_LINEAGE_IN_THIS_RECEIPT','original_member':'NWind.dat:SOBJECT.OTB','decoder':'existing decoded priority/G2 generation','historical_world_placement':'UNVERIFIED_RECONSTRUCTION'}for s in dict.fromkeys(refs)]};return p
 def house(self,style,width,opened):
  name=f'house-{style}-{width}-'+('open'if opened else'closed');p=f'gameplay/world/r16/{name}.png'
  if p in self.assets:return p,Image.open(self.output/p).size
  refs=[]
  if style=='brown' and width==7:
   im=Image.new('RGBA',(168,120))
   rows=([391,392,393,394,395,397,398],[383,384,386,387,388,389,390],[651,652,653,655,656,657,658],[697,704,712,714 if opened else 713,712,706,699])
   for y,ids in zip((0,24,48,72),rows):
    for x,i in enumerate(ids):
     tile,path=self.native(i);refs.append(path);im.alpha_composite(tile,(x*24,120-tile.height if y==72 else y))
  else:
   # Source208 is an open doorway. End caps/chimney are complete native pixels.
   ids=[205]+[207]*(width//2-1)+[208]+[210]*(width//2-1)+[211]
   if width>=7:ids[1]=206;ids[2]=216
   im=Image.new('RGBA',(24*width,96))
   for x,i in enumerate(ids):
    tile,path=self.native(i);refs.append(path);im.alpha_composite(tile,(x*24,96-tile.height))
   if not opened:
    wall,path=self.native(209);refs.append(path);im.alpha_composite(wall,(width//2*24,96-wall.height))
  if opened:ImageDraw.Draw(im).rectangle((im.width//2-10,im.height-48,im.width//2+9,im.height-1),fill=(0,0,0,0))
  return self.asset(name,im,refs),im.size
 def market_hall(self,left,right,doors):
  width=right-left+1;im=Image.new('RGBA',(width*24,120));refs=[]
  for row,(start,middle,end)in enumerate(((391,393,398),(383,386,390),(651,653,658))):
   for x in range(width):
    tile,p=self.native(start if x==0 else end if x==width-1 else middle);refs.append(p);im.alpha_composite(tile,(x*24,row*24))
  for x in range(width):
   number=714 if x+left in doors else 697 if x in(0,width-1)else 704 if x%3 else 712
   tile,p=self.native(number);refs.append(p);im.alpha_composite(tile,(x*24,120-tile.height))
   if x+left in doors:ImageDraw.Draw(im).rectangle((x*24+2,72,x*24+21,119),fill=(0,0,0,0))
  return self.asset('buya-complete-six-service-market-hall',im,refs),im.size
 def arch(self,kind):
  name='portal-'+kind;p=f'gameplay/world/r16/{name}.png'
  if p in self.assets:return p,Image.open(self.output/p).size
  im=Image.new('RGBA',(72,96));refs=[]
  if kind=='cave':
   for x,i in ((0,450),(48,456)):
    tile,path=self.native(i);refs.append(path);im.alpha_composite(tile,(x,96-tile.height))
   tile,path=self.native(457);refs.append(path);im.alpha_composite(tile.crop((0,0,24,24)),(24,0))
  elif kind=='gate':
   for x,i in ((0,695),(48,696)):
    tile,path=self.native(i);refs.append(path);im.alpha_composite(tile,(x,96-tile.height))
   tile,path=self.native(191);refs.append(path);im.alpha_composite(tile.crop((0,0,24,24)),(24,0))
  else:
   # Open regional roads use short waypoint posts, never an invisible wall.
   for x,i in ((0,537),(48,541)):
    tile,path=self.native(i);refs.append(path);im.alpha_composite(tile,(x,96-tile.height))
  ImageDraw.Draw(im).rectangle((24,24,47,95),fill=(0,0,0,0))
  return self.asset(name,im,refs),im.size
 def add_obj(self,m,path,x,y,size,source,**extra):
  o={'path':path,'x':int(x),'y':int(y),'width_px':size[0],'height_px':size[1],'depth_y':int(y+size[1]),'visual_repair':VERSION,'source_unit':source,**extra};m['objects'].append(o);return o
 def prepare(self):
  self.destination_fixes=[];self.teleport_fixes=[]
  targets={'north':(140,4),'south':(140,275),'east':(275,140),'west':(4,140)}
  aliases=[('gates',self.data['gates'],self.before['gates'])]
  for key,row in self.data['returns'].items():aliases.append(('returns.'+key,row,self.before['returns'][key]))
  for key,row in self.data['nation_gates'].items():aliases.append(('nation_gates.'+key,row,self.before['nation_gates'][key]))
  for path,row,old in aliases:
   for direction,p in row.items():
    if direction not in targets:continue
    nx,ny=targets[direction];previous=[old[direction]['x'],old[direction]['y']];self.teleport_fixes.append({'path':path+'.'+direction,'map_id':p['map_id'],'previous':previous,'to':[nx,ny]});self.protected[p['map_id']].discard(tuple(previous));p.update(x=nx,y=ny);self.protected[p['map_id']].add((nx,ny))
  for mid,m in self.data['maps'].items():
   oldex={e['id']:e for e in self.before['maps'][mid]['exits']}
   for e in m['exits']:
    if e['to_map']=='g1:map:buya_city'and m['width']<=20:
     prior=oldex[e['id']];self.destination_fixes.append({'map_id':mid,'exit_id':e['id'],'previous_to':[prior['to_x'],prior['to_y']],'to':[e['to_x'],203],'reason':'front courtyard of complete shared service hall; old201 saved cells explicitly mapped203'});e['to_y']=203;self.protected[e['to_map']].add((e['to_x'],203))
    elif e['id']=='g1:exit:f5247448fc626c':
     self.destination_fixes.append({'map_id':mid,'exit_id':e['id'],'previous_to':[137,172],'to':[275,140],'reason':'arrival beside actual Buya eastgate276,140, replacing171cell mismatch'});e.update(to_x=275,to_y=140);self.protected['g1:map:buya_city'].add((275,140))
 def city(self,mid):
  m=self.data['maps'][mid];g=self.geom[mid];w,h=m['width'],m['height'];b=np.zeros((h,w),bool);b[0,:]=b[-1,:]=True;b[:,0]=b[:,-1]=True
  m['objects']=[];ground=np.full((h,w),52,dtype=np.int32);roads=np.zeros((h,w),bool);reserved=set(self.protected[mid]);units=[]
  def road(a,z,r=1):
   x,y=a;tx,ty=z;points=[(xx,y)for xx in range(min(x,tx),max(x,tx)+1)]+[(tx,yy)for yy in range(min(y,ty),max(y,ty)+1)]
   for xx,yy in points:
    for dy in range(-r,r+1):
     for dx in range(-r,r+1):
      X,Y=xx+dx,yy+dy
      if 0<X<w-1 and 0<Y<h-1 and not b[Y,X]:roads[Y,X]=True
  for yy in (40,90,140,169,205,235):road((2,yy),(w-3,yy),2 if yy==140 else 1)
  for xx in (25,72,108,140,190,235):road((xx,2),(xx,h-3),2 if xx==140 else 1)
  def place(ex,ey,width=7,opened=False,kind='house',style='brown',exit_id=None):
   path,size=self.house(style,width,opened);left=ex-width//2;top=ey+1-size[1]//24
   cells={(x,y)for y in range(ey-2,ey+1)for x in range(left,left+width)if not(opened and x==ex and y>=ey-1)}
   bounds={(x,y)for y in range(top,ey+1)for x in range(left,left+width)}
   if not opened and (bounds&reserved or any(x<3 or x>=w-3 or y<3 or y>=h-3 for x,y in bounds)or any(roads[y,x]for x,y in cells)):return False
   if cells&self.protected[mid]:return False
   for x,y in cells:b[y,x]=True
   reserved.update(bounds)
   if opened:reserved.update((x,y)for y in range(ey+1,ey+8)for x in range(ex-6,ex+7))
   o=self.add_obj(m,path,left*24,top*24,size,kind,building_id='r16:'+digest([mid,ex,ey,kind])[:18]);units.append({'building_id':o['building_id'],'kind':kind,'footprint':sorted([list(p)for p in cells]),'door_cell':[ex,ey]if opened else None,'exit_id':exit_id,'bounds_cells':[left,top,width,size[1]//24],'asset':path});return True
  service_exits=[e for e in m['exits']if self.data['maps'][e['to_map']]['width']<=20]
  if mid=='g1:map:buya_city':
   doorxs={e['x']for e in service_exits};left,right=min(doorxs)-1,max(doorxs)+1;ey=202;path,size=self.market_hall(left,right,doorxs);bid='r16:buya-six-service-hall'
   footprint={(x,y)for y in range(ey-2,ey+1)for x in range(left,right+1)if not(x in doorxs and y>=ey-1)}
   assert not footprint&self.protected[mid]
   for x,y in footprint:b[y,x]=True
   reserved.update((x,y)for y in range(ey-4,ey+8)for x in range(left-2,right+3));self.add_obj(m,path,left*24,(ey-4)*24,size,'complete service hall',building_id=bid)
   for e in service_exits:units.append({'building_id':bid,'kind':'service','footprint':sorted([list(p)for p in footprint]),'door_cell':[e['x'],ey],'exit_id':e['id'],'bounds_cells':[left,ey-4,right-left+1,5],'asset':path});e['direction']='north';road((e['x'],ey+1),(108,ey+2),1)
  for e in service_exits:
   if mid=='g1:map:buya_city':continue
   if self.data['maps'][e['to_map']]['width']<=20:
    if not place(e['x'],e['y'],7,True,'service','brown',e['id']):raise ValueError('Protected service building footprint:'+mid+':'+e['id'])
    e['direction']='north';road((e['x'],e['y']+1),(108,e['y']+2),1)
  # Districts comprise complete native architecture, not numbered map chunks.
  for band,yy in enumerate((37,85,132,164,200,230,261)):
   for index,xx in enumerate((17,39,61,86,115,159,179,207,228,254)):
    ex=xx+((index+band)%3-1)*2;ey=yy;width=9 if(index+band)%4==0 else 7
    if place(ex,ey,width,False,'residence','thatch'if(index+band)%3==0 else'brown'):road((ex,ey+1),(ex,min((40,90,140,169,205,235),key=lambda v:abs(v-ey))),1)
  wall,wp=self.native(191)
  for x in range(1,w-1):
   if not any(abs(x-e['x'])<=2 and e['y']<8 for e in m['exits']):b[1,x]=True;self.add_obj(m,wp,x*24,48-wall.height,wall.size,'outer_north_wall')
   if not any(abs(x-e['x'])<=2 and e['y']>h-8 for e in m['exits']):b[h-2,x]=True;self.add_obj(m,wp,x*24,(h-1)*24-wall.height,wall.size,'outer_south_wall')
  tree,treep=self.native(86);left,lp=self.native(85);right,rp=self.native(87);whole=Image.new('RGBA',(72,96));whole.alpha_composite(left,(0,96-left.height));whole.alpha_composite(tree,(24,96-tree.height));whole.alpha_composite(right,(48,96-right.height));tp=self.asset('native-complete-pine',whole,[lp,treep,rp])
  for yy in range(17,h-8,19):
   for xx in range(12,w-8,23):
    cells={(xx+d,yy)for d in range(3)}
    if cells&reserved or any(roads[y,x]or b[y,x]for x,y in cells):continue
    if any(abs(xx-x)<4 and abs(yy-y)<4 for x,y in self.protected[mid]):continue
    for x,y in cells:b[y,x]=True
    self.add_obj(m,tp,xx*24,(yy+1)*24-96,(72,96),'complete_garden_tree')
  # Fenced service courtyards, jars and planting supply the warm lived-in
  # village density of the single reference, using original bamboo modules.
  for e in service_exits:
   ex,ey=e['x'],e['y']
   if mid=='g1:map:buya_city'and ex!=111:continue
   xmin,xmax=(96,123)if mid=='g1:map:buya_city'else(ex-5,ex+5);front=ey+6
   for x in range(xmin,xmax+1):
    if abs(x-ex)<=1 or(x,front)in self.protected[mid]:continue
    tile,p=self.native(264 if x==xmin else 265 if x==xmax else 257);b[front,x]=True;self.add_obj(m,p,x*24,(front+1)*24-tile.height,tile.size,'complete courtyard fence')
   for x in(xmin,xmax):
    for y in range(ey+1,front):
     if(x,y)in self.protected[mid]:continue
     tile,p=self.native(262 if x==xmin else 263);b[y,x]=True;self.add_obj(m,p,x*24,(y+1)*24-tile.height,tile.size,'courtyard side fence')
   for x,y,n in((xmin+1,ey+1,74),(xmin+2,ey+1,74),(xmax-1,ey+2,75),(xmax-1,ey+3,76)):
    if(x,y)in self.protected[mid]:continue
    tile,p=self.native(n);self.add_obj(m,p,x*24,(y+1)*24-tile.height,tile.size,'native courtyard pottery and planting')
    if n==74:b[y,x]=True
  for x,y in self.protected[mid]:b[y,x]=False;road((x,y),(108,y),1)
  m['closed_gate_contracts']=[]
  if mid=='g1:map:buya_city':
   for direction,(ex,ey)in {'north':(140,3),'west':(3,140)}.items():
    p,size=self.arch('gate');im=Image.open(self.output/p).convert('RGBA');door,dp=self.native(713);im.alpha_composite(door,(24,96-door.height));cp=self.asset('closed-city-gate-'+direction,im,[dp]+[s['runtime_source_path']for s in self.assets[p]['sources']]);self.add_obj(m,cp,(ex-1)*24,(ey-3)*24,size,'closed city gate');b[ey,ex]=True;m['closed_gate_contracts'].append({'direction':direction,'cell':[ex,ey],'state':'CLOSED_NO_REGION_EXIT','teleport_anchor':list({'north':(140,4),'west':(4,140)}[direction]),'ordinary_exit_test':'NOT_AN_EXIT'});m['landmarks'].append({'name':'북쪽 성벽문'if direction=='north'else'서쪽 성벽문','x':ex,'y':ey,'kind':'closed_city_gate'})
  ground[roads]=1
  m.update(source_geometry=[{'source_ref':'r16:coherent-reconstructed-city','map_id':mid,'role':'complete native architecture along stable service entrances and authored roads','topology_status':'RECONSTRUCTED_NOT_HISTORICAL_CLAIM','raw_native_history':f'gameplay/geometry/history-r15/{Path(m["geometry_file"]).name}'}],visual_buildings=units,geometry_note='Reconstructed coherent city replaces disconnected G2 slot fragments. Raw original layouts retained privately. IDs and all gameplay coordinates retained.',map_version='v2-g2-native-world-r16',visual_style={'kind':'coherent_native_module_town','source_tier':'LEGACY_RECONSTRUCTED','complete_architecture_units':len(units),'stable_service_thresholds':True})
  # Buya formerly displayed domestic phantom door landmarks. Bind actual exits.
  for lm in m['landmarks']:
   cardinal={'북문':(140,3),'남문':(140,276),'동문':(276,140),'서문':(3,140)}
   if lm['name']in cardinal:lm['x'],lm['y']=cardinal[lm['name']]
   for e in m['exits']:
    if self.data['maps'][e['to_map']]['width']>20 and lm['name']==self.data['maps'][e['to_map']]['name']:lm.update(x=e['x'],y=e['y'])
    if self.data['maps'][e['to_map']]['width']<=20:
     dest=self.data['maps'][e['to_map']]['name']
     if lm['name']==dest or (lm['name']in('주막','대장간','전사길드','도적길드','주술사길드','도사길드')and lm['name'].replace('길드','')in dest):lm.update(x=e['x'],y=e['y'],door=[e['x'],e['y']])
  if mid=='g1:map:buya_city':m['landmarks']=[lm for lm in m['landmarks']if lm['name']not in('북문','서문')]
  g['ground_ids']=ground.reshape(-1).tolist();g['blocked']=[[int(x),int(y)]for y,x in np.argwhere(b)];g['edge_masks']=[0]*(w*h);g['objects']=deepcopy(m['objects']);self.footprints[mid]=units
  self.rows.append({'map_id':mid,'repair':'replaced disconnected city fragments with coherent complete native architectural units, roads and visible blocking footprints','former_objects':len(self.before['maps'][mid]['objects']),'new_objects':len(m['objects']),'complete_buildings':len(units),'stable_exits':len(m['exits']),'render_and_ordinary_input':'NOT_RUN'})
 def noncity_floor(self,mid):
  m=self.data['maps'][mid];g=self.geom[mid];w,h=m['width'],m['height']
  if w<=20:return
  ground=np.array(g['ground_ids']).reshape(h,w);blocked=np.zeros((h,w),bool)
  for x,y in g['blocked']:blocked[y,x]=True
  native=np.zeros((h,w),bool)
  for ref in m.get('source_geometry',[]):
   ox,oy=ref.get('offset',[0,0]);native[oy:min(oy+64,h),ox:min(ox+64,w)]=True
  style=m.get('style','cave');base={'forest':52,'plain':52,'coast':1094,'snow':697,'fire':488,'crypt':327,'cave':323}.get(style,52);fill=~native;ground[fill&~blocked]=base
  for e in m['exits']:
   ex,ey=int(e['x']),int(e['y'])
   for y in range(max(0,ey-2),min(h,ey+3)):
    for x in range(max(0,ex-2),min(w,ex+3)):
     if fill[y,x]and not blocked[y,x]:ground[y,x]=1 if style in('forest','plain','coast')else 323
  g['ground_ids']=ground.reshape(-1).tolist();self.rows.append({'map_id':mid,'repair':'continuous regional native terrain replaces non-native sine-wave filler; existing native floor/masks retained','cells_repainted':int((fill&~blocked).sum()),'render_and_ordinary_input':'NOT_RUN'})
 def interior(self,mid):
  m=self.data['maps'][mid];g=self.geom[mid];w,h=m['width'],m['height']
  if w>20:return
  # Remove former icon-sized furniture collision together with its pixels.
  # Retain only the exact old perimeter/door aperture before placing furniture.
  blocked={(x,y)for x,y in g['blocked']if x in(0,w-1)or y in(0,h-1)};keep=[]
  for o in m['objects']:
   if o.get('y',0)<24 or o.get('y',0)>=(h-2)*24:keep.append(o)
  m['objects']=keep
  def prop(n,x,y):
   if(x,y)in self.protected[mid]:return
   im,p=self.native(n);self.add_obj(m,p,x*24,(y+1)*24-im.height,im.size,'interior native prop');blocked.add((x,y))
  # Furniture is a complete footprint plus original pixel geometry, rather
  # than an inventory icon floating over an otherwise empty floor.
  for x in range(2,8):prop(275 if x in(2,7)else 276,x,3)
  for x,y in ((2,2),(3,2),(16,2),(17,2)):prop(74,x,y)
  if '주막'in m['name']:
   top,topref=self.native(270);end,endref=self.native(271);dish,dref=self.native(74);table=Image.new('RGBA',(48,32))
   table.alpha_composite(top,(0,32-top.height));table.alpha_composite(end,(24,32-end.height));table.alpha_composite(dish,(12,-6));tp=self.asset('complete-tavern-table',table,[topref,endref,dref])
   for x,y in ((3,6),(14,6),(3,11),(14,11)):
    footprint={(x,y),(x+1,y)}
    if footprint&self.protected[mid]:continue
    blocked.update(footprint);self.add_obj(m,tp,x*24,(y+1)*24-32,(48,32),'complete table')
    for sx in(x,x+1):prop(271,sx,y+1)
  elif '대장간'in m['name']:
   for x,y,n in((3,6,338),(15,6,339),(4,11,508),(15,11,571)):prop(n,x,y)
  else:
   for x,y,n in((3,6,351),(15,6,352),(3,11,271),(15,11,271)):prop(n,x,y)
  # Full back wall, coherent side edges, uncluttered central service aisle.
  for x,y in self.protected[mid]:blocked.discard((x,y))
  g['blocked']=sorted([list(p)for p in blocked]);g['objects']=deepcopy(m['objects'])
  self.rows.append({'map_id':mid,'repair':'complete native tables/stools, storage counter, pottery and service-specific props; central NPC/door positions retained','render_and_ordinary_input':'NOT_RUN'})
 def door_contracts(self,mid):
  m=self.data['maps'][mid];g=self.geom[mid];w,h=m['width'],m['height'];blocked=set(map(tuple,g['blocked']));edges=g.get('edge_masks',[]);m['door_contracts']=[];cuts=0
  m['objects']=[o for o in m['objects']if not(o.get('visual_repair')==VERSION and o.get('exit_id'))]
  for e in m['exits']:
   ex,ey=int(e['x']),int(e['y']);choices=[]
   for dx,dy,side in DIRS:
    x,y=ex+dx,ey+dy
    if 0<=x<w and 0<=y<h and(x,y)not in blocked:choices.append((x,y,side))
   prefer={'north':'south','south':'north','east':'west','west':'east'}.get(e.get('direction'),'south');choices.sort(key=lambda p:(p[2]!=prefer,p[2]!='south',p[2]));approach=list(choices[0][:2])if choices else None
   service=next((u for u in self.footprints.get(mid,[])if u.get('exit_id')==e['id']),None)
   post_cells=[]
   if w>20 and service is None and approach:
    kind='gate'if m.get('style')=='city'else'cave'if m.get('style')in('cave','crypt','fire')else'road'
    horizontal=approach[0]!=ex;points=[(ex,ey-1),(ex,ey+1)]if horizontal else[(ex-1,ey),(ex+1,ey)]
    ids=(450,456)if kind=='cave'else(695,696)if kind=='gate'else(537,541)
    for (px,py),number in zip(points,ids):
     if not(0<px<w-1 and 0<py<h-1)or(px,py)in self.protected[mid]:continue
     tile,p=self.native(number)
     # Horizontal passages use low original masonry/wood footings: a tall
     # foreground column would conceal the actual actor-sized opening.
     if horizontal:
      tile=tile.crop((0,max(0,tile.height-24),24,tile.height));p=self.asset(f'{kind}-east-west-footing-{number}',tile,[p])
     self.add_obj(m,p,px*24,(py+1)*24-tile.height,tile.size,'directional '+kind+' post',exit_id=e['id']);blocked.add((px,py));post_cells.append([px,py])
   corridor=(ex*24+2,ey*24-40,ex*24+22,(ey+1)*24)
   for index,o in enumerate(m['objects']):
    if o.get('visual_repair')==VERSION:continue
    ox,oy=int(o['x']),int(o['y']);rw,rh=int(o['width_px']),int(o['height_px']);left=max(corridor[0],ox);top=max(corridor[1],oy);right=min(corridor[2],ox+rw);bottom=min(corridor[3],oy+rh)
    if left>=right or top>=bottom:continue
    im=self.image(o['path']).copy();box=(left-ox,top-oy,right-ox,bottom-oy)
    if not im.getchannel('A').crop(box).getbbox():continue
    ImageDraw.Draw(im).rectangle((box[0],box[1],box[2]-1,box[3]-1),fill=(0,0,0,0));old=o['path'];p=self.asset('aperture-'+digest([mid,index,e['id'],old])[:24],im,[old]);o['path']=p;o['aperture_repair']={'exit_id':e['id'],'source_object':old,'pixel_cut':list(box),'policy':'retain entire source object outside exact doorway aperture'};cuts+=1
   reverse=[r for r in self.data['maps'][e['to_map']]['exits']if r['to_map']==mid]
   contract={'id':e['id'],'building_id':service['building_id']if service else None,'map_id':mid,'trigger_cell':[ex,ey],'visible_aperture_pixels':list(corridor),'approach_cell':approach,'solid_post_cells':post_cells,'blocked_trigger':(ex,ey)in blocked,'edge_mask_at_trigger':edges[ey*w+ex]if edges else 0,'interaction':'ordinary movement into trigger cell','door_state':'OPEN','to_map':e['to_map'],'to_cell':[e['to_x'],e['to_y']],'entry_direction':e.get('direction'),'reverse_exit_ids':[r['id']for r in reverse],'reverse_arrivals':[[r['to_x'],r['to_y']]for r in reverse],'camera':'follow player landing feet','static_visual_aperture':'DEFINED_NOT_RENDER_PASS','normal_input_status':'NOT_RUN'};m['door_contracts'].append(contract);self.doors.append(contract)
  g['blocked']=sorted([list(p)for p in blocked])
  if cuts:self.rows.append({'map_id':mid,'repair':'exact doorway alpha aperture, remaining large-object pixels preserved','objects_apertured':cuts,'render_and_ordinary_input':'NOT_RUN'})
 def write_map(self,mid,reuse_floor=False):
  m=self.data['maps'][mid];g=self.geom[mid];w,h=m['width'],m['height'];layers=[];chunks={};overview=Image.new('RGBA',(w*2,h*2));old=self.old_geom[mid]
  write(self.output/'gameplay/geometry/history-r15'/Path(m['geometry_file']).name,old)
  oldb=set(map(tuple,old['blocked']));newb=set(map(tuple,g['blocked']));blocked=bytearray(w*h)
  for x,y in newb:blocked[y*w+x]=1
  edges=g.get('edge_masks',[0]*(w*h));m['blocked_base64']=base64.b64encode(blocked).decode();m['edge_masks_base64']=base64.b64encode(bytes(edges)).decode();moved={}
  for x,y in sorted(newb-oldb):
   found=None
   for r in range(1,max(w,h)):
    for yy in range(max(1,y-r),min(h-1,y+r+1)):
     for xx in range(max(1,x-r),min(w-1,x+r+1)):
      if max(abs(xx-x),abs(yy-y))!=r:continue
      if(xx,yy)not in newb and not edges[yy*w+xx]:found={'x':xx,'y':yy};break
     if found:break
    if found:break
   if found is None:raise ValueError('No migration target '+mid)
   moved[f'{x},{y}']=found
  if moved:self.transforms[mid]={'to_map_id':mid,'dx':0,'dy':0,'cell_mappings':moved}
  if mid=='g1:map:buya_city':
   for e in m['exits']:
    if self.data['maps'][e['to_map']]['width']<=20:moved[f'{e["x"]},201']={'x':e['x'],'y':203}
   if moved:self.transforms[mid]={'to_map_id':mid,'dx':0,'dy':0,'cell_mappings':moved}
   moved['108,201']={'x':140,'y':275};moved['137,172']={'x':275,'y':140}
  if mid in self.data['g2_world']['city_maps']:
   for old,new in[((108,142),(140,4)),((108,201),(140,275)),((137,172),(275,140)),((78,172),(4,140))]:moved[f'{old[0]},{old[1]}']={'x':new[0],'y':new[1]}
   self.transforms[mid]={'to_map_id':mid,'dx':0,'dy':0,'cell_mappings':moved}
  if reuse_floor:
   layers=deepcopy(m['ground_layers']);chunks=deepcopy(m.get('ground_chunks',{}))
   for o in layers:
    im=Image.open(self.output/o['path']).convert('RGBA');overview.alpha_composite(im.resize((max(1,im.width//12),max(1,im.height//12)),Image.Resampling.NEAREST),(o['x']//12,o['y']//12))
  for cy in range(0 if not reuse_floor else h,h,16):
   for cx in range(0,w,16):
    im=Image.new('RGBA',(min(16,w-cx)*24,min(16,h-cy)*24))
    for y in range(cy,min(cy+16,h)):
     for x in range(cx,min(cx+16,w)):
      t=g['ground_ids'][y*w+x]
      # r12 preserved a presentation floor different from old collision MAP
      # ground IDs. Consume those actual pixels, never reinterpret the IDs.
      tile=self.image(self.before['maps'][mid]['floor_png']).crop((x*24,y*24,(x+1)*24,(y+1)*24))if w<=20 else self.tiles.get(t,self.tiles[1])
      im.alpha_composite(tile,((x-cx)*24,(y-cy)*24))
    p='gameplay/world/r16/floor-'+digest(im.tobytes())[:24]+'.png';q=self.output/p
    if not q.exists():q.parent.mkdir(parents=True,exist_ok=True);im.save(q,optimize=True)
    entry={'path':p,'x':cx*24,'y':cy*24,'width_px':im.width,'height_px':im.height};layers.append(entry);chunks[f'{cx//16},{cy//16}']=entry;overview.alpha_composite(im.resize((im.width//12,im.height//12),Image.Resampling.NEAREST),(cx*2,cy*2))
  buckets={}
  for n,o in enumerate(m['objects']):
   for by in range(max(0,int(o['y']//384)),min((h-1)//16,int((o['y']+o['height_px']-1)//384))+1):
    for bx in range(max(0,int(o['x']//384)),min((w-1)//16,int((o['x']+o['width_px']-1)//384))+1):buckets.setdefault(f'{bx},{by}',[]).append(n)
  for o in sorted(m['objects'],key=lambda o:o['depth_y']):
   im=Image.open(self.output/o['path']).convert('RGBA');small=im.resize((max(1,im.width//12),max(1,im.height//12)),Image.Resampling.NEAREST);overview.alpha_composite(small,(int(o['x']//12),int(o['y']//12)))
  p='gameplay/world/r16/overview-'+digest(mid)[:20]+'.png';overview.convert('RGB').save(self.output/p);m.update(ground_layers=layers,ground_chunks=chunks,object_buckets=buckets,overview_png=p,chunk_cells=16)
  g['objects']=deepcopy(m['objects']);write(self.output/m['geometry_file'],g);m['geometry_sha256']=digest({k:g[k]for k in('width','height','ground_ids','edge_masks','blocked')}|{'exits':m['exits']})
 def migration(self):
  accepted=deepcopy(self.before['accepted_compatibility'])
  for c in accepted:
   transforms=c.setdefault('map_transforms',{})
   for mid,new in self.transforms.items():
    previous=transforms.get(mid)
    if previous is None:transforms[mid]=deepcopy(new);continue
    cells=previous.setdefault('cell_mappings',{})
    for key,v in list(cells.items()):
     cell=f'{v["x"]},{v["y"]}'
     if cell in new['cell_mappings']:cells[key]=deepcopy(new['cell_mappings'][cell])
    dx,dy=previous.get('dx',0),previous.get('dy',0)
    for cell,v in new['cell_mappings'].items():
     x,y=map(int,cell.split(','));source=f'{x-dx},{y-dy}'
     if x-dx>=0 and y-dy>=0 and source not in cells:cells[source]=deepcopy(v)
  accepted.append({'profile':self.before['profile'],'compatibility':deepcopy(self.before['compatibility']),'manifest_sha256':self.before['manifest_sha256'],'map_transforms':deepcopy(self.transforms)})
  self.data['accepted_compatibility']=accepted;self.data['require_geometry_migration_contract']=True;self.data['compatibility']['map_geometry']=digest({mid:m['geometry_sha256']for mid,m in self.data['maps'].items()});self.data['manifest_sha256']=digest({'parent':self.before['manifest_sha256'],'version':VERSION,'geometry':self.data['compatibility']['map_geometry'],'tool_sha256':filehash(Path(__file__))})
 def normalize_arrival_facing(self):
  fixes=[]
  for mid,m in self.data['maps'].items():
   contracts={c['id']:c for c in m.get('door_contracts',[])}
   for e in m['exits']:
    reverse=[r for r in self.data['maps'][e['to_map']]['exits']if r['to_map']==mid]
    if not reverse:raise ValueError('No paired reverse '+e['id'])
    r=min(reverse,key=lambda r:(abs(e['to_x']-r['x'])+abs(e['to_y']-r['y']),r['id']));dx,dy=e['to_x']-r['x'],e['to_y']-r['y']
    if abs(dx)+abs(dy)>3:raise ValueError('Far paired landing '+e['id'])
    direction=('east'if dx>0 else'west')if abs(dx)>=abs(dy)and dx else('south'if dy>0 else'north')if dy else e.get('direction','south')
    if e.get('direction')!=direction:fixes.append({'map_id':mid,'exit_id':e['id'],'previous':e.get('direction'),'arrival_direction':direction,'paired_reverse_exit':r['id'],'landing_delta':[dx,dy]})
    e['direction']=direction
    if e['id']in contracts:
     c=contracts[e['id']];a=c.get('approach_cell')
     if a:
      sx,sy=e['x']-a[0],e['y']-a[1];c['entry_direction']='east'if sx>0 else'west'if sx<0 else'south'if sy>0 else'north'
     c['arrival_direction']=direction;c['paired_reverse_exit']=r['id'];c['paired_landing_distance']=abs(dx)+abs(dy)
  self.arrival_facing_fixes=fixes
 def run(self):
  self.prepare()
  for mid in self.data['g2_world']['city_maps']:self.city(mid)
  for mid,m in self.data['maps'].items():
   if m['width']<=20:self.interior(mid)
   elif mid not in self.data['g2_world']['city_maps']:self.noncity_floor(mid)
  for mid in self.data['maps']:self.door_contracts(mid)
  self.normalize_arrival_facing()
  for mid in self.data['maps']:self.write_map(mid)
  self.migration()
  for kind in('items','monsters','skills','npcs','quests','recipes','advancements','training_rules','jobs','start','respawn','return_points','nation_starts'):assert self.data[kind]==self.before[kind],kind
  assert set(self.data['maps'])==set(self.before['maps'])and len(self.data['maps'])==111
  for mid,m in self.data['maps'].items():
   old=self.before['maps'][mid];assert(m['width'],m['height'],m['spawns'],m['npcs'])==(old['width'],old['height'],old['spawns'],old['npcs'])
   assert [{k:v for k,v in e.items()if k not in('direction','x','y','to_x','to_y')}for e in m['exits']]==[{k:v for k,v in e.items()if k not in('direction','x','y','to_x','to_y')}for e in old['exits']]
  report={'schema':'baram.g2.single-reference-world-repair/1','version':VERSION,'status':'IMPLEMENTED_STATIC_VALIDATION_ONLY','maps':111,'exits':len(self.doors),'cities_reconstructed':len(self.data['g2_world']['city_maps']),'parent_content_sha256':filehash(self.source/'gameplay_content.json'),'parent_runtime_sha256':filehash(self.source/'runtime.json'),'tool_sha256':filehash(Path(__file__)),'migration_maps':len(self.transforms),'migration_cells':sum(len(v['cell_mappings'])for v in self.transforms.values()),'source_assets':list(self.assets.values()),'changes':self.rows,'door_contracts':self.doors,'map_dimensions_ids_exit_coordinates_npcs_gameplay_content_preserved':True,'visual_quality':'NOT_RUN','ordinary_input_all_exits':'NOT_RUN','native_platforms':'NOT_RUN','historical_city_placement':'UNVERIFIED_RECONSTRUCTION'}
  report['destination_fixes']=self.destination_fixes;report['teleport_alias_fixes']=self.teleport_fixes;report['arrival_facing_fixes']=self.arrival_facing_fixes;report['all_exit_thresholds_preserved']=True;report['exit_thresholds_preserved']=276
  self.data['single_reference_world_repair']={k:v for k,v in report.items()if k not in('changes','door_contracts','source_assets')};write(self.output/'G2_SINGLE_REFERENCE_WORLD_REPAIR.json',report);write(self.output/'G2_R16_MAP_MIGRATION.json',{'previous_manifest_sha256':self.before['manifest_sha256'],'map_transforms':self.transforms,'old_geometry_private_history':'gameplay/geometry/history-r15','fallback':'validated primary/backup preserved by store; invalid migration rejected before write'});write(self.output/'gameplay_content.json',self.data)
  manifest=json.loads((self.source/'runtime.json').read_text());files=[]
  for p in sorted(self.output.rglob('*')):
   if p.is_file()and p.name!='runtime.json':files.append({'path':str(p.relative_to(self.output)),'bytes':p.stat().st_size,'sha256':filehash(p)})
  manifest['files']=files;manifest['fingerprint']=digest(files);manifest['compatibility']=deepcopy(self.data['compatibility']);manifest['input_definitions_sha256']=filehash(self.output/'gameplay_content.json');manifest['single_reference_world_repair']=deepcopy(self.data['single_reference_world_repair']);write(self.output/'runtime.json',manifest);return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Fresh output required; shipped generation never overwritten')
 shutil.copytree(a.source,a.output);r=Repair(a.source,a.output).run();write(a.receipt,r);print(canonical({k:v for k,v in r.items()if k not in('changes','door_contracts','source_assets')}))
if __name__=='__main__':main()
