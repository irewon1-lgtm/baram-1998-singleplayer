#!/usr/bin/env python3
"""Inspect source terrain themes; images remain private temporary evidence."""
import argparse,collections,math,struct,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.dont_write_bytecode=True
from common import ROOT,WORK,load,lines,write
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import dat_entries,Epf,read_palettes
from legacy_maps import tile_table,static_objects,map_cells

def setup(inputs):
    dat=next(inputs.rglob('NWind.dat'));e=dat_entries(dat.read_bytes());tables={}
    for g in 'ABC':
        ep=Epf(e['tile'+g.lower()+'.epf'][2]);p=read_palettes(e['tile'+g.lower()+'.pal'][2]);tables[g]=tile_table(e['tile'+g.lower()+'.tbl'][2],ep.count,len(p))
    return tables,static_objects(e['sobj.tbl'][2],tables['C'].count),next(inputs.rglob('Maps'))

def component(cells,w,h):
    unseen={(i%w,i//w) for i,c in enumerate(cells) if c['collision']!=15};areas=[]
    while unseen:
        at=unseen.pop();todo=[at];group={at}
        while todo:
            x,y=todo.pop()
            for n in [(x,y-1),(x-1,y),(x,y+1),(x+1,y)]:
                if n in unseen:unseen.remove(n);todo.append(n);group.add(n)
        areas.append(group)
    return max(areas,key=len) if areas else set()

def inspect(inputs,shared):
    tables,objects,folder=setup(inputs);meta={g:load(shared/'kr491'/('tile'+g.lower()+'.json')) for g in 'ABC'}
    frames={g:{f['frame']:f for f in m['frames']} for g,m in meta.items()};pages={}
    def tile(g,i):
        f=frames[g][i];p=f['path']
        if p not in pages:pages[p]=Image.open(shared/p).convert('RGBA')
        x,y,w,h=f['region'];return pages[p].crop((x,y,x+w,y+h))
    rows=[];thumbnails=[];common=collections.Counter()
    for r in lines(WORK/'catalog/expansion-2/map-worklist.jsonl'):
        if r['classification']!='NEW_TERRAIN_SQUARE_INTERPRETABLE':continue
        w,h=r['dimensions'];cells=map_cells((folder/f"TK{r['original_map_id']}.map").read_bytes(),w,h,tables,objects);area=component(cells,w,h)
        dominant=collections.Counter(c['ground_word'] for c in cells if c['ground_word'] and c['ground_word']<tables['B'].base)
        top=dominant.most_common(6);primary=top[0][0] if top else 0;common[primary]+=1
        row={**r,'largest_static_component':len(area),'open_cells':sum(c['collision']!=15 for c in cells),
             'dominant_ground_words':top,'dominant_object_ids':collections.Counter(c['object_id'] for c in cells if c['object_id']).most_common(6)}
        rows.append(row)
        if len(area)<12:continue
        im=Image.new('RGBA',(w*24,h*24),(15,18,24,255))
        for i,c in enumerate(cells):
            word=c['ground_word'];x=i%w;y=i//w
            if word:
                g='B' if word>=tables['B'].base else 'A';pic=tile(g,word-tables[g].base);im.alpha_composite(pic,(x*24,y*24))
            for depth,fid in enumerate(objects[c['object_id']]['frames']):
                if fid is not None:
                    yy=(y-depth)*24
                    if yy>=0:im.alpha_composite(tile('C',fid),(x*24,yy))
        thumb=im.convert('RGB');thumb.thumbnail((136,136),Image.Resampling.NEAREST);thumbnails.append((r['original_map_id'],w,primary,thumb))
    write(WORK/'catalog/expansion-2/map-characteristics.json',{'rows':rows,'dominant_ground_counts':dict(common),'scope':'ORIGINAL_LAYOUT_STATIC_ANALYSIS_ONLY'})
    out=WORK/'drafts/expansion-2-review';out.mkdir(parents=True,exist_ok=True)
    primarys=common.most_common(120);im=Image.new('RGB',(1000,math.ceil(len(primarys)/10)*82),(38,42,49));draw=ImageDraw.Draw(im)
    for i,(word,n) in enumerate(primarys):
        if not word:continue
        t=tile('A',word-1).resize((48,48),Image.Resampling.NEAREST);x=(i%10)*100;y=(i//10)*82;im.paste(t,(x+24,y+4),t);draw.text((x+4,y+57),f'{word} ({n})',fill='white')
    im.save(out/'dominant-ground.png')
    # First representatives of each dominant ground and dimension class. A
    # representative is not evidence that all512 source layouts were viewed.
    seen=set();chosen=[]
    for mid,w,word,thumb in thumbnails:
        key=(word, 'room' if w<=20 else 'field' if w>=48 else 'dungeon')
        if key in seen:continue
        seen.add(key);chosen.append((mid,w,word,thumb))
    for start in range(0,len(chosen),48):
        group=chosen[start:start+48];im=Image.new('RGB',(1200,math.ceil(len(group)/8)*175),(38,42,49));draw=ImageDraw.Draw(im)
        for i,(mid,w,word,thumb) in enumerate(group):
            x=i%8*150;y=i//8*175;im.paste(thumb,(x+(150-thumb.width)//2,y+5));draw.text((x+4,y+145),f'{mid} {w}x{w} G{word}',fill='white')
        im.save(out/f'maps-{start//48:02d}.png')
    print({'analyzed':len(rows),'representatives_rendered':len(chosen),'dominant_ground_types':len(common),'usable_static':sum(r['largest_static_component']>=12 for r in rows)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--shared',type=Path,required=True);a=p.parse_args();inspect(a.inputs,a.shared)
