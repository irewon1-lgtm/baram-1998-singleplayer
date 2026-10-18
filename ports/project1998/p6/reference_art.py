"""Extract UI decoration from the user's references and audit NPC visibility.

The private screenshot inputs are pinned. Only the decorative border, blank
paper and two unlettered crests are retained; all player text, gear and numbers
are excluded. Public Git contains this reproducible extraction, not the images.
"""
import argparse, hashlib, importlib.util, json, struct, csv, sys
from pathlib import Path
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
REFERENCE_PINS={'01-11345.jpg': '9e499011c36214334137fe486cf5c399305f749176a25c715f6f0a5fff5723a2', '08-11325.jpg': '692bbde05e09e7b6697583565db5112855a92517d5c6fc298e877637163304f0', '09-11326.jpg': 'c9daf6faf8489a742c02fad1d973adde2f42ec445b28e9378927fd45e10b0436'}

def main():
    p=argparse.ArgumentParser()
    for k in ['references','runtime','originals','audit','source']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();out=a.runtime/'p6/art'
    for name,digest in REFERENCE_PINS.items():assert hashlib.sha256((a.references/name).read_bytes()).hexdigest()==digest,name
    source=a.references/'08-11325.jpg';im=Image.open(source).convert('RGBA')
    assert im.size==(1536,864)
    records=[]
    def crop(name,box):
        pic=im.crop(box);pic.save(out/(name+'.png'));records.append({'name':name,'source':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'crop':box});return pic
    # Four separate border strips. No reference inventory content is packaged.
    # The high-resolution video still has a player-overlay icon at its upper
    # right. Take the unoccluded top curl from the supplied static screenshot.
    source=a.references/'01-11345.jpg';im=Image.open(source).convert('RGBA')
    crop('curl-top',(614,487,839,529))
    source=a.references/'08-11325.jpg';im=Image.open(source).convert('RGBA')
    crop('curl-left',(1108,135,1135,470))
    crop('curl-right',(1385,135,1414,470))
    source=a.references/'01-11345.jpg';im=Image.open(source).convert('RGBA')
    crop('curl-bottom',(614,783,839,828))
    source=a.references/'08-11325.jpg';im=Image.open(source).convert('RGBA')
    crop('crest',(1110,649,1181,719))
    crop('clan-crest',(1110,720,1181,790))
    # The bottom crest bears a source caption, so use the clean native totem
    # for that control instead of baking a reference player's interface text.
    source=a.references/'09-11326.jpg';im=Image.open(source).convert('RGBA')
    crop('title-left',(412,0,459,38))
    crop('title-right',(705,0,751,38))
    crop('paper-tile',(1252,426,1324,466))
    spec=importlib.util.spec_from_file_location('art',HERE.parent/'scripts/convert.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    inter=c.dat_entries((a.originals/'4x/Inter.dat').read_bytes());n=c.dat_entries((a.originals/'4x/NexusTK.dat').read_bytes());pal=c.palettes(n['BARAM.PAL'])[0]
    for name in ['FRAME','TOTEM']:
        e=c.Epf(inter[name+'.EPF']);top,left,bottom,right,pix,mask=struct.unpack_from('<hhhhII',e.raw,e.toc)
        w,h=right-left,bottom-top;idx=np.frombuffer(e.raw,np.uint8,w*h,12+pix).reshape(h,w)
        Image.fromarray(np.dstack((pal[idx],np.where(idx!=0,255,0).astype('uint8')))).save(out/(name.lower()+'.png'))
    # Clean brown paper window; raw game art is not repainted or recoloured.
    tile=Image.open(out/'paper-tile.png');paper=Image.new('RGBA',(384,480))
    for y in range(0,480,tile.height):
        for x in range(0,384,tile.width):paper.paste(tile,(x,y))
    paper.save(out/'classic-paper.png')
    window=Image.new('RGBA',(384,580),(74,35,14,255))
    for y in range(65,520,tile.height):
        for x in range(28,357,tile.width):window.paste(tile,(x,y))
    for name,box in [('top',(0,0,384,72)),('bottom',(0,508,384,580)),('left',(0,70,35,510)),('right',(348,70,384,510))]:
        part=Image.open(out/('curl-'+name+'.png'));window.paste(part.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS),box[:2])
    window.save(out/'classic-window.png')
    assets=json.loads((a.runtime/'assets/assets.json').read_text());objects=Image.open(a.runtime/'assets/objects.png').convert('RGBA')
    npcrows=list(csv.DictReader((a.runtime.parent/'content/NPCs.csv').open()))
    # Original repository's own retail/5.33 table decoder, with exact supplied
    # 5.33 art, fills 29 regional merchant icons absent from the older 4.95 DAT.
    # No fallback artwork and no changes to item IDs, properties or save data.
    sys.path.insert(0,str(a.source/'re'))
    spec=importlib.util.spec_from_file_location('source_icon_format',a.source/'re/icon_downscale.py');ic=importlib.util.module_from_spec(spec);spec.loader.exec_module(ic)
    assert hashlib.sha256((a.originals/'533/Misc.dat').read_bytes()).hexdigest()=='96eb14dd06a54f7bb6cc8c80c5f0cc4fcfbaf66086ca8185d57eedb1d008ea6f'
    assert hashlib.sha256((a.source/'re/icon_downscale.py').read_bytes()).hexdigest()=='b66e3830eb76cbe5189421a1af96040dac6ebdd899b87e19be17517cd14694c3'
    modern=ic.ItemArt('supplied5.33',a.originals/'533/Misc.dat')
    item_epf=c.Epf(modern.epf);item_pals=c.palettes(modern.pal)
    npc_keys={row['NpcIdentifier'] for row in npcrows};regional=set()
    for filename in ['ShopStock.csv','ShopBuysFrom.csv']:
        for row in csv.DictReader((a.runtime.parent/'content'/filename).open()):
            if row['NpcIdentifier'] in npc_keys:regional.update(k for k in row['ItemKeys'].split('|') if k and k!='-')
    item_rows={row['ItmIdentifier']:row for row in csv.DictReader((a.runtime.parent/'content/Items.csv').open())}
    supplemental=c.Atlas();icon_sources=[];icon_bindings={};unresolved=[]
    for key in sorted(regional-set(assets['item_icons'])):
        row=item_rows[key];index=int(row['ItmIcon']);dye=int(row['ItmIconColor']);art_key='item533:%d:%d' %(index,dye)
        if index>=item_epf.count:unresolved.append(key);continue
        palette=modern.recs[index][1];decoded=item_epf.decode(index,item_pals[palette],dye)
        supplemental.add(art_key,decoded);icon_bindings[key]={'key':art_key,'frame':index,'palette':palette,'dye':dye}
        icon_sources.append({'item':key,'key':art_key,'member':'533/Misc.dat/ITEM.EPF','frame':index,'palette':palette,'dye':dye,'rgba_sha256':hashlib.sha256(decoded[0].tobytes()).hexdigest()})
    extra=json.loads((out/'assets.json').read_text());regions=supplemental.write(out/'extra-icons.png')
    for region in regions.values():region['sheet']='extra_icons'
    extra['actor_regions'].update(regions);extra['item_icons']=icon_bindings
    (out/'assets.json').write_text(json.dumps(extra,indent=2)+'\n')
    plans=[]
    for row in npcrows:
        if row.get('Enabled')=='0':continue
        mid=int(row['NpcMapId']);nid=int(row['NpcId']);x0=int(row['NpcX']);y0=int(row['NpcY'])
        m=next(m for m in assets['maps'] if int(m['id'])==mid);w,h=m['width'],m['height']
        cells=np.frombuffer((a.runtime/'assets'/m['raw_path']).read_bytes(),'<u2').reshape(h,w,2).copy()
        for cell in m.get('authored_map_cells',[]):
            # Native collision remains authoritative; candidate art uses the
            # unchanged raw map unless an explicit object override is present.
            pass
        anim=assets['animations']['npc:'+str(nid)+'-'+str(int(row['NpcSide']))][0]['key'];reg=assets['actor_regions'][anim];off=reg['offset'];_,_,rw,rh=reg['rect']
        def covered(x,y):
            box=(x*24+12+off[0],y*24+12+off[1],x*24+12+off[0]+rw,y*24+12+off[1]+rh)
            mask=Image.new('L',(rw,rh))
            for yy in range(max(0,y),min(h,y+18)):
                for xx in range(max(0,x-5),min(w,x+6)):
                    oid=int(cells[yy,xx,1])
                    if not oid:continue
                    for k,f in enumerate(assets['objects'][str(oid)]['frames']):
                        if not f:continue
                        r=assets['object_frames'][str(f)];rx,ry,ww,hh=r['rect'];ox,oy=r['offset'];dx=xx*24+ox-box[0];dy=(yy-k)*24+oy-box[1]
                        if dx>=rw or dy>=rh or dx+ww<=0 or dy+hh<=0:continue
                        alpha=objects.crop((rx,ry,rx+ww,ry+hh)).getchannel('A');mask.paste(alpha,(dx,dy),alpha)
            return round(float(np.count_nonzero(np.asarray(mask)))/max(1,rw*rh),4)
        original=covered(x0,y0);candidates=[]
        for radius in range(13):
            ring=[]
            for y in range(max(1,y0-radius),min(h-1,y0+radius+1)):
                for x in range(max(1,x0-radius),min(w-1,x0+radius+1)):
                    if abs(x-x0)+abs(y-y0)!=radius:continue
                    if int(cells[y,x,0])>>14 or int(cells[y,x,1]):continue
                    if any(int(nr['NpcId'])!=nid and int(nr['NpcMapId'])==mid and abs(x-int(nr['NpcX']))+abs(y-int(nr['NpcY']))<3 for nr in npcrows):continue
                    score=covered(x,y)
                    if score<=0.04:ring.append([x,y,score])
            candidates.extend(sorted(ring,key=lambda z:(z[2],-z[1],z[0])))
            if len(candidates)>=48:break
        plans.append({'npc':nid,'map':mid,'key':row['NpcIdentifier'],'source':[x0,y0],'source_visual_coverage':original,'candidates':candidates})
    (out/'npc-placements.json').write_text(json.dumps(plans,indent=2)+'\n')
    a.audit.write_text(json.dumps({'reference_decoration':records,'supplemental_item_icons':icon_sources,'merchant_icon_gaps':unresolved,'source_icon_decoder_sha256':hashlib.sha256((a.source/'re/icon_downscale.py').read_bytes()).hexdigest(),'misc_sha256':hashlib.sha256((a.originals/'533/Misc.dat').read_bytes()).hexdigest(),'npc_candidates':plans,'policy':'native placement layer picks a source position if visible/reachable, else nearest clear candidate in the main native walk component; never changes map words or NPC definitions'},indent=2)+'\n')
    print('REFERENCE_ART',len(records),'NPCS',len(plans))

if __name__=='__main__':main()
