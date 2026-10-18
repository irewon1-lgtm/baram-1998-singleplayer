"""Extract supplied original window/map art and original pickup body/head poses.

No third-party raster is committed. Inter.dat's palette-zero transparency is
decoded directly from its exact raster; unlike actor EPFs its stencil rows
contain +/-1 padding. Original nonzero palette pixels are retained verbatim.
"""
import argparse, hashlib, importlib.util, json, re, struct
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
INTER = '592cc8981e1887b7fe507a6097a50ef22be2ca325574446159d18bef5d79c37e'


def main():
    p=argparse.ArgumentParser()
    for name in ['originals','runtime','audit']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    spec=importlib.util.spec_from_file_location('p1_art',HERE.parent/'scripts/convert.py')
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    inter_raw=(a.originals/'4x/Inter.dat').read_bytes()
    assert hashlib.sha256(inter_raw).hexdigest()==INTER
    n_raw=(a.originals/'4x/NexusTK.dat').read_bytes()
    assert hashlib.sha256(n_raw).hexdigest()==c.PINS['4x/NexusTK.dat']
    inter=c.dat_entries(inter_raw);n=c.dat_entries(n_raw)
    palette=c.palettes(n['BARAM.PAL'])[0]
    out=a.runtime/'p6/art';out.mkdir(parents=True,exist_ok=True)
    audit=[]
    for name in ['ITEMINV','SPELLINV','SELFLOOK','SELFLOK2','SELFLOK3','USERSTAT','FIELD1','FIELD10']:
        epf=c.Epf(inter[name+'.EPF'])
        top,left,bottom,right,pix,mask=struct.unpack_from('<hhhhII',epf.raw,epf.toc)
        width,height=right-left,bottom-top
        assert mask-pix==width*height
        indices=np.frombuffer(epf.raw,np.uint8,width*height,12+pix).reshape(height,width)
        image=Image.fromarray(np.dstack((palette[indices],np.where(indices!=0,255,0).astype(np.uint8))))
        image.save(out/(name.lower()+'.png'))
        audit.append({'member':name+'.EPF','frame':0,'palette':'NexusTK.dat/BARAM.PAL#0',
                      'raster_sha256':hashlib.sha256(indices.tobytes()).hexdigest(),
                      'rgba_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
                      'width':width,'height':height,'alpha':'palette zero transparent'})
    assets=json.loads((a.runtime/'assets/assets.json').read_text())
    atlas=c.Atlas();animations={};poses=[]
    tables={k:c.table(n[k+'.TBL']) for k in ['BODY','HEAD']}
    epfs={k:c.Epf(n[k+'.EPF']) for k in ['BODY','HEAD']}
    pals={k:c.palettes(n[k+'.PAL']) for k in ['BODY','HEAD']}
    pairs={(2,0)}
    for key in assets['animations']:
        hit=re.match(r'armor:(\d+):(\d+)-',key)
        if hit:pairs.add(tuple(map(int,hit.groups())))
    for look,dye in sorted(pairs):
        for direction in range(4):
            relative=76+direction
            parts=[];provenance=[]
            for name,identity,color in [('BODY',look,dye),('HEAD',0,0)]:
                row=tables[name][identity];index=row['Starting']+relative
                part=epfs[name].decode(index,pals[name][row['Palette']],color)
                if part:parts.append(part)
                provenance.append({'member':name+'.EPF','part_id':identity,'frame':index,'palette':row['Palette'],'dye':color})
            union=[min(p[1][0] for p in parts),min(p[1][1] for p in parts),max(p[1][0]+p[0].width for p in parts),max(p[1][1]+p[0].height for p in parts)]
            image=Image.new('RGBA',(union[2]-union[0],union[3]-union[1]))
            for im,offset in parts:image.alpha_composite(im,(offset[0]-union[0],offset[1]-union[1]))
            key=f'armor:{look}:{dye}-pickup-{direction}'
            atlas.add(key,(image,union[:2]));animations[key]=[{'key':key}]
            if (look,dye)==(2,0):animations['pickup-'+str(direction)]=[{'key':key}]
            poses.append({'key':key,'source_frames':provenance})
    regions=atlas.write(out/'pickup.png')
    for region in regions.values():region['sheet']='pickup'
    (out/'assets.json').write_text(json.dumps({'actor_regions':regions,'animations':animations},indent=2)+'\n')
    # Render the preserved map words and object columns, rather than invent a
    # schematic. Max 640px thumbnails; runtime player/NPC/exit markers stay live.
    ground=Image.open(a.runtime/'assets/ground.png').convert('RGBA')
    objects=Image.open(a.runtime/'assets/objects.png').convert('RGBA')
    for m in assets['maps']:
        raw=(a.runtime/'assets'/m['raw_path']).read_bytes();cells=np.frombuffer(raw,'<u2').reshape(-1,2)
        canvas=Image.new('RGBA',(m['width']*24,m['height']*24),(27,30,19,255))
        for y in range(m['height']):
            for x in range(m['width']):
                g,o=map(int,cells[y*m['width']+x]);fid=int(m['ground_lookup'][str(g)])
                canvas.alpha_composite(ground.crop(((fid%64)*24,(fid//64)*24,(fid%64+1)*24,(fid//64+1)*24)),(x*24,y*24))
                if not o:continue
                for k,f in enumerate(assets['objects'][str(o)]['frames']):
                    if not f:continue
                    row=assets['object_frames'][str(f)];rx,ry,rw,rh=row['rect'];ox,oy=row['offset']
                    if rw and rh:canvas.alpha_composite(objects.crop((rx,ry,rx+rw,ry+rh)),(x*24+ox,(y-k)*24+oy))
        canvas.thumbnail((640,640),Image.Resampling.NEAREST)
        canvas.save(out/('map-'+str(m['id'])+'.png'))
    a.audit.write_text(json.dumps({'status':'PASS','inter_sha256':INTER,'windows':audit,'pickup_source_pose_assignment':'76..79, N/E/S/W, visually inspected source body/head contact sheet; native ActionType4',
                                 'pickup':poses,'local_maps':len(assets['maps']),'raster_rule':'same original raw map words, translated ground atlas slots, original object columns; max640 thumbnail'},indent=2)+'\n')
    print('REPAIR_ART',len(audit),len(poses),len(assets['maps']))


if __name__=='__main__':main()
