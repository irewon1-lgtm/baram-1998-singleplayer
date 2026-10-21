"""Exact retained atlas pixels, authored final terrain; offline rendering, not Godot/device PASS."""
import json,pathlib,struct,csv,functools
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[2];ASSETS=ROOT/'android/assets/runtime'
C=json.loads((ASSETS/'catalog.json').read_text());ATLASES={}
def rows(n):return list(csv.DictReader(l for l in(ROOT/'candidate/game-data'/n).read_text(encoding='utf-8-sig').splitlines()if l.strip()and not l.lstrip().startswith('#')))
INDEX={int(x['id']):(int(x['xs']),int(x['ys']))for x in rows('map_index.csv')}
@functools.lru_cache(maxsize=50000)
def frame(k):
 f=C['frames'].get(k)
 if not f:return None
 file=f.get('atlas',f.get('atlas_file','atlas.png'))
 if file not in ATLASES:ATLASES[file]=Image.open(ASSETS/file).convert('RGBA')
 x,y,w,h=f['rect'];return ATLASES[file].crop((x,y,x+w,y+h)),f['origin']
def cells(mid):
 w,h=INDEX[mid];data=[list(x)for x in struct.iter_unpack('<HH',(ROOT/f'candidate/game-data/maps/TK{mid}.map').read_bytes())]
 for r in rows('MapCells.csv'):
  if r['Map'].isdigit() and int(r['Map'])==mid:
   x,y=int(r['X']),int(r['Y'])
   if not(0<=x<w and 0<=y<h):continue
   i=y*w+x;g,o=data[i]
   if r['Tile']:g=(g&0xc000)|int(r['Tile'])
   if r['Pass']:g=(g&0x3fff)|(int(r['Pass'])<<14)
   if r['Obj']:o=int(r['Obj'])
   data[i]=[g,o]
 return data,w,h
def render(data,w,h,box=None,scale=1,warps=()):
 x0,y0,x1,y1=box or(0,0,w,h);im=Image.new('RGBA',((x1-x0)*24,(y1-y0)*24),(0,0,0,255))
 def put(k,x,y):
  f=frame(k)
  if f:
   pic,origin=f;im.alpha_composite(pic,(round(x+origin[0]),round(y+origin[1])))
 for y in range(max(0,y0),min(h,y1)):
  for x in range(max(0,x0),min(w,x1)):
   g,o=data[y*w+x];k=C['grounds'].get(str(g))
   if k:put(k,(x-x0)*24,(y-y0)*24)
 # Anchor stacks can extend into the crop from below; preserve original draw order.
 for y in range(max(0,y0),min(h,y1+16)):
  for x in range(max(0,x0-8),min(w,x1+8)):
   o=data[y*w+x][1]
   for layer,k in enumerate(C['objects'].get(str(o),{}).get('frames',[])):
    if k:put(k,(x-x0)*24,(y-y0-layer)*24)
 d=ImageDraw.Draw(im)
 for x,y in warps:
  if x0<=x<x1 and y0<=y<y1:d.rectangle(((x-x0)*24,(y-y0)*24,(x-x0+1)*24-1,(y-y0+1)*24-1),outline='red',width=2)
 if scale!=1:im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
 return im.convert('RGB')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('map',type=int);p.add_argument('output');p.add_argument('--box',type=int,nargs=4);a=p.parse_args();data,w,h=cells(a.map);render(data,w,h,a.box).save(a.output)
