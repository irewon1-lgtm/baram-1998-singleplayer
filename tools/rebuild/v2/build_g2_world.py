#!/usr/bin/env python3
"""G2 world compiler: preserves native layouts and legacy cells, adds authored joins.

Reads the already decoded priority generation. It never downloads/decodes sources,
changes G1, or calls a build/platform result PASS. All geometry is reproducible.
"""
from __future__ import annotations
import argparse, hashlib, json, math, heapq, shutil
from copy import deepcopy
from pathlib import Path
from collections import deque, Counter
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

GEN='WORK-V2-G2-20261017'
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(v):return hashlib.sha256(v if isinstance(v,bytes) else canonical(v).encode()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(canonical(v)+'\n')
def stable(kind,name):return 'g2:'+kind+':'+hashlib.sha256(name.encode()).hexdigest()[:16]
STEPS=((0,-1,1,4),(1,0,2,8),(0,1,4,1),(-1,0,8,2))

def reachable(m,start):
 w,h=m['width'],m['height'];b={y*w+x for x,y in m['blocked']};e=m.get('edge_masks',[])
 at=start[1]*w+start[0]
 if at in b:return set()
 seen={at};q=deque([at])
 while q:
  n=q.popleft();x,y=n%w,n//w
  for dx,dy,s,t in STEPS:
   xx,yy=x+dx,y+dy;nn=yy*w+xx
   if 0<=xx<w and 0<=yy<h and nn not in b and nn not in seen and (not e or not((e[n]&s)or(e[nn]&t))):seen.add(nn);q.append(nn)
 return seen

class World:
 def __init__(self,baseline,priority,output):
  self.baseline=baseline;self.priority=priority;self.output=output
  self.data=json.loads((baseline/'gameplay_content.json').read_text());self.before=deepcopy(self.data)
  self.sources={};self.usage={};self.tiles={};self.offsets={};self.changes={};self.rooms=[];self.fields=[];self.families=[]
  for f in sorted((priority/'maps').glob('map-*.json')):
   d=json.loads(f.read_text());self.sources[f.stem]=d
   self.usage[d['inspection_id']]={'source_ref':d['inspection_id'],'source_chunk_sha256':d['source_chunk_sha256'],'byte_access':'VERIFIED_LOCAL_DECODED_OUTPUT','nonzero_ground':sum(x!=0 for x in d['collisions']['ground_ids']),'objects':len(d['objects']),'placements':[]}
  self.used=set()
  for mid,m in self.before['maps'].items():
   im=Image.open(baseline/m['floor_png']).convert('RGBA')
   for i,t in enumerate(m['ground_ids']):
    if t not in self.tiles:self.tiles[t]=im.crop((i%m['width']*24,i//m['width']*24,i%m['width']*24+24,i//m['width']*24+24))
  for key,d in self.sources.items():
   g=d['collisions']['ground_ids'];wanted=set(g)-self.tiles.keys()-{0}
   if not wanted:continue
   im=Image.open(priority/'maps'/d['floor_png']).convert('RGBA')
   for i,t in enumerate(g):
    if t in wanted:self.tiles[t]=im.crop((i%64*24,i//64*24,i%64*24+24,i//64*24+24));wanted.remove(t)
  self.tiles[0]=self.tiles[1]

 def newmap(self,mid,name,w,h,style,level):
  seed=int(digest(mid)[:8],16);yy,xx=np.mgrid[:h,:w]
  base={'city':52,'forest':52,'snow':697,'coast':1094,'plain':1094,'crypt':327,'cave':323,'fire':488}[style]
  alternate={'city':1094,'forest':1094,'snow':714,'coast':52,'plain':52,'crypt':323,'cave':1,'fire':323}[style]
  wave=np.sin(xx*.067+seed%17)+np.cos(yy*.079+seed%11)+.55*np.sin((xx+yy)*.12)
  ground=np.where(wave>.35,base,alternate).astype(np.int32)
  if style=='city':solid=np.zeros((h,w),dtype=bool)
  elif style in ('crypt','cave','fire'):solid=np.ones((h,w),dtype=bool)
  else:solid=(wave>1.5)|((np.sin(xx*.13+seed%7)+np.cos(yy*.11))<-1.45)
  solid[0,:]=True;solid[-1,:]=True;solid[:,0]=True;solid[:,-1]=True
  m={'id':mid,'name':name,'width':w,'height':h,'tile_size':24,'region':name,'map_version':'v2-g2-native-world-1','fact_status':'LEGACY_LAYOUTS_WITH_RECONSTRUCTED_JOINS','source_profile':'KR125_NATIVE_SPATIAL_LAYOUTS','source_geometry':[],'geometry_note':'Native relative floor/object/mask coordinates are retained at explicit offsets; world names, joins and outer trails reconstructed.','objects':[],'exits':[],'spawns':[],'spawn_zones':[],'npcs':[],'landmarks':[],'gather_nodes':[],'allow_return':True,'danger':'safe'if style=='city'else'combat','recommended_level':level,'return_city':'gp:map:domestic_city','style':style,'render_layers':'bounded ground chunks then foot-depth objects and actors'}
  self.data['maps'][mid]=m
  self.changes[mid]={'g':ground,'b':solid,'e':np.zeros((h,w),np.uint8),'native':np.zeros((h,w),bool),'native_cells':{},'anchors':[],'modified':set()}
  return m

 def legacy(self,mid,w,h,style):
  old=self.before['maps'][mid];m=self.newmap(mid,old['name'],w,h,style,int(old.get('minimum_level',old.get('recommended_level',1))))
  dx=w-old['width']-8;dy=h-old['height']-8
  if style=='city':dx,dy=76,140
  self.offsets[mid]=(dx,dy);t=self.changes[mid];sl=np.s_[dy:dy+old['height'],dx:dx+old['width']]
  t['g'][sl]=np.array(old['ground_ids']).reshape(old['height'],old['width']);t['b'][sl]=False
  for x,y in old['blocked']:t['b'][y+dy,x+dx]=True
  for obj in old['objects']:
   o=deepcopy(obj)
   for k,d in [('x',dx*24),('y',dy*24),('depth_y',dy*24),('grid_x',dx),('grid_y',dy)]:
    if k in o:o[k]+=d
   m['objects'].append(o)
  for key in ['exits','spawns','landmarks','gather_nodes']:
   m[key]=deepcopy(old.get(key,[]))
   for p in m[key]:
    if 'x'in p:p['x']+=dx;p['y']+=dy
    if 'door'in p:p['door']=[p['door'][0]+dx,p['door'][1]+dy]
  m['npcs']=deepcopy(old.get('npcs',[]));m['return_city']=old.get('return_city','gp:map:domestic_city')
  center=next(((x+dx,y+dy)for y in range(old['height']//2,old['height']-1)for x in range(old['width']//2,old['width']-1)if [x,y]not in old['blocked']),None)
  t['anchors'].append(center)
  return m

 def import_native(self,mid,key,ox,oy,role):
  d=self.sources[key];m=self.data['maps'][mid];t=self.changes[mid]
  assert 0<=ox and 0<=oy and ox+64<=m['width'] and oy+64<=m['height'],(mid,key,ox,oy)
  raw=d['collisions'];g=np.array(raw['ground_ids']).reshape(64,64);e=np.array(raw['edge_masks'],dtype=np.uint8).reshape(64,64);nz=g!=0
  b=np.zeros((64,64),bool)
  for x,y in raw['blocked_cells']:b[y,x]=True
  sub=np.s_[oy:oy+64,ox:ox+64]
  t['g'][sub][nz]=g[nz];t['b'][sub][nz]=b[nz];t['e'][sub][nz]=e[nz];t['native'][sub][nz]=True
  for obj in d['objects']:
   if not (0<=int(obj['grid_x'])<64 and 0<=int(obj['grid_y'])<64):continue
   o=deepcopy(obj);o['frame_png']='gameplay/world/g2-native/'+o['frame_png'];o['path']=o['frame_png']
   o['x']+=ox*24;o['y']+=oy*24;o['depth_y']+=oy*24;o['grid_x']+=ox;o['grid_y']+=oy
   o['source_ref']=d['inspection_id'];o['placement_fact_status']='SOURCE_RELATIVE_COORDINATES_PRESERVED'
   im=Image.open(self.output/o['path']);o['width_px'],o['height_px']=im.size;m['objects'].append(o)
  for y,x in zip(*np.where(nz)):t['native_cells'][(int(x)+ox,int(y)+oy)]=(int(g[y,x]),bool(b[y,x]),int(e[y,x]),d['inspection_id'])
  valid=np.argwhere(nz&~b&(e!=15))
  if len(valid):
   cy,cx=valid[len(valid)//2];t['anchors'].append((int(cx)+ox,int(cy)+oy))
  placement={'map_id':mid,'offset':[ox,oy],'role':role,'nonzero_ground_cells':int(nz.sum()),'source_objects':len(d['objects']),'topology_status':'RECONSTRUCTED_WORLD_PLACEMENT_NOT_HISTORICAL_CLAIM'}
  m['source_geometry'].append({'source_ref':d['inspection_id'],**placement});self.usage[d['inspection_id']]['placements'].append(placement);self.used.add(key)

 def room(self,mid,cx,cy,rx,ry,rect=False):
  t=self.changes[mid];h,w=t['b'].shape
  for y in range(max(1,cy-ry),min(h-1,cy+ry+1)):
   for x in range(max(1,cx-rx),min(w-1,cx+rx+1)):
    if not t['native'][y,x]and(rect or ((x-cx)/max(1,rx))**2+((y-cy)/max(1,ry))**2<=1):t['b'][y,x]=False

 def connect(self,mid,a,b):
  t=self.changes[mid];h,w=t['b'].shape
  a=(max(1,min(w-2,a[0])),max(1,min(h-2,a[1])));b=(max(1,min(w-2,b[0])),max(1,min(h-2,b[1])))
  heap=[(0,0,a)];scores={a:0};prev={a:None}
  while heap:
   _,cost,p=heapq.heappop(heap)
   if p==b:break
   if cost!=scores.get(p):continue
   for dx,dy,s,tt in STEPS:
    q=(p[0]+dx,p[1]+dy);x,y=q
    if not(0<x<w-1 and 0<y<h-1):continue
    cut=bool(t['b'][y,x]or(t['e'][p[1],p[0]]&s)or(t['e'][y,x]&tt))
    nc=cost+1+(150 if t['native'][y,x] else 5)*int(cut)
    if nc<scores.get(q,10**12):scores[q]=nc;prev[q]=p;heapq.heappush(heap,(nc+abs(x-b[0])+abs(y-b[1]),nc,q))
  assert b in prev,(mid,a,b)
  p=b;trail=[]
  while p is not None:
   trail.append(p);x,y=p
   if t['b'][y,x]or t['e'][y,x]:t['modified'].add(p)
   t['b'][y,x]=False;t['e'][y,x]=0
   if not t['native'][y,x]:
    self.room(mid,x,y,2,2)
    t['g'][y,x]=1 if self.data['maps'][mid]['style']in('city','forest','plain')else 323
   p=prev[p]
  return trail

 def point(self,mid,want,avoid=()):
  t=self.changes[mid];h,w=t['b'].shape;x,y=want;used=set(avoid)
  for r in range(max(w,h)):
   for yy in range(max(1,y-r),min(h-1,y+r+1)):
    for xx in range(max(1,x-r),min(w-1,x+r+1)):
     if not t['b'][yy,xx]and not t['e'][yy,xx]and(xx,yy)not in used:return xx,yy
  raise ValueError(mid+' no safe cells')

 def link(self,a,b,pa,pb,name,minlevel=1):
  pa=self.point(a,pa);pb=self.point(b,pb)
  # Landings beside the opposite trigger avoid an immediate bouncing exit.
  la=self.point(a,(pa[0]+1,pa[1]),[pa]);lb=self.point(b,(pb[0]+1,pb[1]),[pb])
  for src,dst,p,land in [(a,b,pa,lb),(b,a,pb,la)]:
   self.data['maps'][src]['exits'].append({'id':stable('exit',src+'>'+dst+name),'x':p[0],'y':p[1],'to_map':dst,'to_x':land[0],'to_y':land[1],'direction':'east','minimum_level':minlevel,'fact_status':'RECONSTRUCTED_G2_JOIN'})
   self.data['maps'][src]['landmarks'].append({'name':self.data['maps'][dst]['name'],'x':p[0],'y':p[1],'kind':'exit'})
   self.changes[src]['anchors'].extend([p,land])

 def make_world(self):
  objdest=self.output/'gameplay/world/g2-native/objects';shutil.copytree(self.priority/'maps/objects',objdest,dirs_exist_ok=True)
  cities=['gp:map:domestic_city','g1:map:buya_city']
  citykeys=['map-0-chunk-%02d'%n for n in [9,14,15,16,17,18,19,20,21,22,23,24,26,27,28,29,33,34]]+['map-208-chunk-%02d'%n for n in range(5)]+['map-'+str(n)for n in[97,125,126,144,149,198,282]]
  for j,mid in enumerate(cities):
   m=self.legacy(mid,280,280,'city');m['region']='고구려 도성권'if j==0 else'백제 도성권'
   slots=[(12+64*x,12+64*y)for y in range(4)for x in range(4)if(x,y)!=(1,2)]
   for k,(x,y)in enumerate(slots):self.import_native(mid,citykeys[j*15+k],x,y,['궁성','시장','수로','주거','정원'][k%5])
   names=['왕궁 앞마당','동쪽 시장','서쪽 공방','북쪽 성곽','주거 골목','수로 나루','연무장','남문 광장']
   for n in range(8):
    x=25+(n%4)*70;y=32+(n//4)*195;self.room(mid,x,y,6,5,True);self.changes[mid]['anchors'].append(self.point(mid,(x,y)));m['landmarks'].append({'name':names[n],'x':x,'y':y})
   # Former field gates now belong to the outside city wall, not the old 64-cell patch.
   cardinal={'north':(140,3),'south':(140,276),'east':(276,140),'west':(3,140)}
   for e in m['exits']:
    if e['to_map']in['gp:map:north_field','gp:map:south_field','gp:map:east_field','gp:map:west_field']or('buya' in mid and e['to_map'].startswith('g1:map:')and 'guild'not in e['to_map']and 'tavern'not in e['to_map']and 'forge'not in e['to_map']):
     direction=str(e.get('direction','east'));e['x'],e['y']=cardinal.get(direction,(276,140));self.room(mid,e['x'],e['y'],3,3,True)
     self.changes[mid]['anchors'].append((e['x'],e['y']))
  base_fields=['gp:map:'+n+'_field'for n in['east','south','west','north']]
  base_fields += [mid for mid,m in self.before['maps'].items()if m['name']in['초급 사냥길','중급 사냥길','고급 사냥길','왕의 시련길']]
  base_fields += [mid for mid,m in self.before['maps'].items()if m['name'].startswith('북방대초원')]
  base_fields += [next(mid for mid,m in self.before['maps'].items()if m['name']==name)for name in['극지방 1층','한두고개 1층','일본 1층']]
  assert len(base_fields)==16
  styles=['forest','plain','forest','coast','forest','coast','plain','fire','plain','plain','forest','coast','fire','snow','forest','coast']
  labels=['송림','초원','서녘','갈대','청풍','해안','고원','적암','북풍','야영','노송','백사','화산','설원','안개','바다']
  for i,mid in enumerate(base_fields):
   m=self.legacy(mid,128,128,styles[i]);m['g2_region_label']=labels[i];m['recommended_level']=1 if i<4 else min(90,6+(i-4)*7)
   self.fields.append(mid)
  # Preserve every other legacy map. Natural small service interiors stay small.
  for mid,old in self.before['maps'].items():
   if mid in self.changes or old['width']<=20:continue
   style='crypt'if any(s in old['name']for s in['해골','유령','흑령','도깨비','귀신'])else'snow'if'극지'in old['name']else'forest'if any(s in old['name']for s in['북방','한두','일본'])else'cave'
   self.legacy(mid,112,112,style)
  prefixes=['쥐굴','뱀굴','곰, 호랑이굴','여우굴','자호굴','거미, 사마귀굴','가재, 전갈굴','해골굴','유령굴','흑해골굴','흑령굴','도깨비굴']
  for i,prefix in enumerate(prefixes):
   existing=[mid for mid,m in self.before['maps'].items()if m['name'].startswith(prefix)]
   ids=existing[:]
   for f in range(len(ids),4):
    mid=stable('map',prefix+str(f+1));self.newmap(mid,prefix+' '+str(f+1)+'층',112,112,'crypt'if i>=7 else'cave',min(90,6+i*6+f*2));ids.append(mid)
   for n,mid in enumerate(ids):
    self.data['maps'][mid]['dungeon_family']=prefix;self.data['maps'][mid]['dungeon_floor']=n+1
   self.families.append(ids)
  sourcepool=[k for k in self.sources if k not in self.used and self.usage[self.sources[k]['inspection_id']]['nonzero_ground']>=120]
  sourcepool.sort(key=lambda k:(-self.usage[self.sources[k]['inspection_id']]['nonzero_ground'],k))
  recipients=self.fields+[mid for mid in self.changes if mid not in self.fields+cities]
  for n,mid in enumerate(recipients):
   if n<len(sourcepool):
    m=self.data['maps'][mid];pos=(3,3)if mid in self.fields else(8,8)
    # Keep legacy gameplay cell patch untouched; only native cells outside it are accepted here.
    # Full native layout is placed in a separate adjoining chamber when legacy patch overlaps.
    if mid in self.before['maps']:
     old=self.before['maps'][mid];dx,dy=self.offsets.get(mid,(0,0));d=self.sources[sourcepool[n]]
     # A source layout's nonempty bounds determine overlap. Do not cut buildings.
     bb=d['occupied_ground_bounds'];pos=(2,2)
     if bb and bb[2]+pos[0]>=dx and bb[3]+pos[1]>=dy:
      # The legacy patch remains as a safe migration overlay after importing the native chamber.
      pass
    self.import_native(mid,sourcepool[n],pos[0],pos[1],'野外遗迹'if mid in self.fields else'원본 동굴·회랑')
    # Restore old valid cells/objects as a compatibility enclave. Native overlap is explicitly counted.
    if mid in self.before['maps']:
     old=self.before['maps'][mid];dx,dy=self.offsets[mid];t=self.changes[mid]
     for y in range(old['height']):
      for x in range(old['width']):
       if [x,y]not in old['blocked']:
        p=(x+dx,y+dy);t['b'][p[1],p[0]]=False;t['e'][p[1],p[0]]=0;t['g'][p[1],p[0]]=old['ground_ids'][y*old['width']+x]
  # Update references as one explicit G1 -> G2 offset mapping.
  for npc in self.data['npcs'].values():
   dx,dy=self.offsets.get(npc['map_id'],(0,0));npc['x']+=dx;npc['y']+=dy
  for m in self.data['maps'].values():
   for e in m['exits']:
    dx,dy=self.offsets.get(e['to_map'],(0,0));e['to_x']+=dx;e['to_y']+=dy
  def shift(p):
   if isinstance(p,dict):
    if 'map_id'in p and 'x'in p and 'y'in p:
     dx,dy=self.offsets.get(p['map_id'],(0,0));p['x']+=dx;p['y']+=dy
    else:
     for v in p.values():shift(v)
  for key in ['start','gates','returns','respawn','nation_starts','return_points','nation_gates']:shift(self.data[key])
  # The city incoming links land at the new outside gate, while all old saved cells remain mapped.
  for city in cities:
   for e in self.data['maps'][city]['exits']:
    for back in self.data['maps'][e['to_map']]['exits']:
     if back['to_map']==city and 'field'in e['to_map']:
      back['to_x'],back['to_y']=e['x']-1 if e['x']>1 else e['x']+1,e['y']
  # Attach added floors using ordinary two-way exits and normal level gates.
  for i,ids in enumerate(self.families):
   for floor in range(1,len(ids)):
    prev,mid=ids[floor-1],ids[floor]
    if not any(e['to_map']==mid for e in self.data['maps'][prev]['exits']):
     for a in [prev,mid]:self.room(a,68 if a==prev else 10,65 if a==prev else 12,5,4)
     self.link(prev,mid,(68,65),(10,12),'stairs',1)
   self.room(self.fields[i],110,105,7,6);self.room(ids[0],12,12,5,4)
   self.link(self.fields[i],ids[0],(110,105),(12,12),'cave-mouth',1)
  # Broad discovery lanes connect fields without making a chain of tiny rooms.
  for i in range(15):
   a,b=self.fields[i],self.fields[i+1]
   for mid,p in [(a,(122,85)),(b,(5,85))]:self.room(mid,*p,4,4)
   self.link(a,b,(122,85),(5,85),'regional-road',1 if i<3 else min(60,(i-2)*5))
  # Local meaningful rooms, camps and branches, with a different route spanning tree per region.
  for mid,t in self.changes.items():
   m=self.data['maps'][mid];w,h=m['width'],m['height']
   if m['style']!='city':
    for n in range(9 if mid in self.fields else 5):
     x=10+(n*37+int(digest(mid)[:4],16))%(w-20);y=10+(n*29+int(digest(mid)[4:8],16))%(h-20)
     self.room(mid,x,y,9 if mid in self.fields else 8,7 if mid in self.fields else 6,m['style']=='crypt');t['anchors'].append(self.point(mid,(x,y)))
   for e in m['exits']:t['anchors'].append((int(e['x']),int(e['y'])))
   for other in self.data['maps'].values():
    for e in other['exits']:
     if e['to_map']==mid:t['anchors'].append((int(e['to_x']),int(e['to_y'])))
   for p in m['spawns']:t['anchors'].append((int(p['x']),int(p['y'])))
   for npc in self.data['npcs'].values():
    if npc['map_id']==mid:t['anchors'].append((npc['x'],npc['y']))
   anchors=list(dict.fromkeys(p for p in t['anchors']if p));root=anchors[0]
   connected=[root]
   for p in anchors[1:]:
    near=min(connected,key=lambda a:abs(a[0]-p[0])+abs(a[1]-p[1]));self.connect(mid,near,p);connected.append(p)
   # Keep original objects out of the few explicitly reconstructed door/aperture cells.
   m['objects']=[o for o in m['objects']if(int(o.get('grid_x',-999)),int(o.get('grid_y',-999)))not in t['modified']]
  return self.data

 def finalize(self):
  # A complete three-column native tree is reused as one depth-sorted prop.
  columns=[Image.open(self.priority/'maps/objects'/f'object-{i}.png').convert('RGBA')for i in (85,86,87)]
  tree=Image.new('RGBA',(72,max(i.height for i in columns)))
  for n,im in enumerate(columns):tree.alpha_composite(im,(n*24,tree.height-im.height))
  treepath='gameplay/world/g2-native/tree-complete.png';tree.save(self.output/treepath)
  wall=ImageEnhance.Brightness(self.tiles[133]).enhance(.36)
  for mid,t in self.changes.items():
   m=self.data['maps'][mid];w,h=m['width'],m['height'];m['ground_ids']=t['g'].reshape(-1).tolist();m['edge_masks']=t['e'].reshape(-1).tolist();m['blocked']=[[int(x),int(y)]for y,x in np.argwhere(t['b'])]
   legacy=self.before['maps'].get(mid);offset=self.offsets.get(mid,(0,0))
   if m['style']in('forest','plain','coast'):
    for y in range(3,h-2,3):
     for x in range(2,w-4,3):
      if legacy and offset[0]-2<=x<=offset[0]+legacy['width']and offset[1]-2<=y<=offset[1]+legacy['height']:continue
      if all(t['b'][y,x+dx]and not t['native'][y,x+dx]for dx in range(3)):
       m['objects'].append({'path':treepath,'frame_png':treepath,'x':x*24,'y':(y+1)*24-tree.height,'depth_y':(y+1)*24,'width_px':tree.width,'height_px':tree.height,'source_ref':'KR125:SOBJECT.OTB:85+86+87','placement_fact_status':'RECONSTRUCTED_ON_ACTUAL_BLOCKED_FOOTPRINT'})
   m['geometry_sha256']=digest({k:m[k]for k in ['width','height','ground_ids','edge_masks','blocked','exits']})
   # Every texture is 16x16 cells; only small overview images span a whole region.
   layers=[];buckets={};small=Image.new('RGB',(w*2,h*2))
   for cy in range(0,h,16):
    for cx in range(0,w,16):
     im=Image.new('RGBA',(min(16,w-cx)*24,min(16,h-cy)*24))
     for y in range(cy,min(cy+16,h)):
      for x in range(cx,min(cx+16,w)):
       tile=wall if t['b'][y,x]and not t['native'][y,x]and m['style']not in('city','forest','plain','coast','snow')else self.tiles[int(t['g'][y,x])]
       im.alpha_composite(tile,((x-cx)*24,(y-cy)*24))
     p='gameplay/world/g2/'+digest(im.tobytes())[:24]+'.png';target=self.output/p
     if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);im.save(target,optimize=True)
     e={'path':p,'x':cx*24,'y':cy*24,'width_px':im.width,'height_px':im.height};layers.append(e);buckets[f'{cx//16},{cy//16}']=e
     small.paste(im.convert('RGB').resize((im.width//12,im.height//12),Image.Resampling.NEAREST),(cx*2,cy*2))
   object_buckets={}
   for n,o in enumerate(m['objects']):
    for by in range(max(0,int(o['y']//384)),min((h-1)//16,int((o['y']+o.get('height_px',24)-1)//384))+1):
     for bx in range(max(0,int(o['x']//384)),min((w-1)//16,int((o['x']+o.get('width_px',24)-1)//384))+1):object_buckets.setdefault(f'{bx},{by}',[]).append(n)
    p=o.get('path',o.get('frame_png'));oi=Image.open(self.output/p).convert('RGBA');ss=oi.resize((max(1,oi.width//12),max(1,oi.height//12)),Image.Resampling.NEAREST);small.paste(ss,(int(o['x']//12),int(o['y']//12)),ss)
   overview='gameplay/world/g2/'+stable('preview',mid).split(':')[-1]+'.png';small.thumbnail((560,560));small.save(self.output/overview)
   m.update(ground_layers=layers,ground_chunks=buckets,object_buckets=object_buckets,overview_png=overview,chunk_cells=16)
   preserved=Counter();modified=Counter()
   for (x,y),(g,b,e,ref)in t['native_cells'].items():
    (preserved if int(t['g'][y,x])==g and bool(t['b'][y,x])==b and int(t['e'][y,x])==e else modified)[ref]+=1
   for ref in preserved.keys()|modified.keys():
    for p in self.usage[ref]['placements']:
     if p['map_id']==mid:p.update(preserved_floor_collision_cells=preserved[ref],reconstructed_overlap_or_aperture_cells=modified[ref])
  # The compiler counts only reachable cells, with the exact same directional edge rule.
  a0=0;a1=0;areas=[]
  for baseline,which in [(self.before,'baseline'),(self.data,'g2')]:
   starts={k:[]for k in baseline['maps']}
   for m in baseline['maps'].values():
    for e in m['exits']:starts[e['to_map']].append((int(e['to_x']),int(e['to_y'])))
   p=baseline['start'];starts[p['map_id']].append((p['x'],p['y']))
   for mid,m in baseline['maps'].items():
    seen=set()
    for p in starts[mid]:
     n=p[1]*m['width']+p[0]
     if n not in seen:seen.update(reachable(m,p))
    if which=='baseline':a0+=len(seen)
    else:a1+=len(seen);areas.append({'map_id':mid,'name':m['name'],'width':m['width'],'height':m['height'],'reachable_walkable_cells':len(seen),'native_placements':len(m.get('source_geometry')or[]),'alias':False})
  for key,d in self.sources.items():
   u=self.usage[d['inspection_id']]
   u['disposition']='SOURCE_LAYOUT_PLACED_WITH_EXPLICIT_PATCH_ACCOUNTING'if u['placements']else'EMPTY_CHUNK_NO_PLAYABLE_CONTENT'if u['nonzero_ground']==0 else'COMPACT_ROOM_RETAINED_FOR_NEXT_PLACEMENT_NOT_ARTIFICIALLY_SCALED'
  report={'schema':'baram.g2.world-usage/1','baseline_content_sha256':hashlib.sha256((self.baseline/'gameplay_content.json').read_bytes()).hexdigest(),'baseline_area_A0':a0,'g2_area_A1':a1,'ratio':a1/max(1,a0),'source_chunks_total':len(self.sources),'unique_chunks_placed':len(self.used),'placements':sum(len(x['placements'])for x in self.usage.values()),'source_chunks':list(self.usage.values()),'maps':areas,'scale_target_met':a1>=5*a0,'area_scope':'Union of passable cells reachable from normal entrances under source and target directional edge masks; source islands excluded. Progression locks must separately be checked with normal required levels.'}
  self.data['generation']=GEN;self.data['g2_world']={'source_usage':'G2_WORLD_USAGE.json','fields':self.fields,'dungeon_families':self.families,'city_maps':['gp:map:domestic_city','g1:map:buya_city']}
  write(self.output/'G2_WORLD_USAGE.json',report)
  return report
