#!/usr/bin/env python3
"""Export all usable pinned KR491 sheets, reuse v125 atlases, preserve table motion.

No installers run; no changes outside content-work. Original pixels stay in the
private output/bundle; the public package holds definitions and acquisition pins.
"""
import argparse
import collections
import hashlib
import io
import re
import shutil
import struct
import sys
import wave
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw
sys.dont_write_bytecode=True
from common import ROOT, WORK, BASE, IDs, sha, file_sha, load, write, shard, record
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import Epf, dat_entries, read_palettes
from legacy_maps import tile_table

KR='f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'

def export(args):
    ids=IDs();source=Path(args.inputs);out=Path(args.private_out);out.mkdir(parents=True,exist_ok=True)
    package=WORK/'packages'/args.batch
    if package.exists(): raise ValueError('Immutable batch already exists')
    package.mkdir(parents=True);(package/'schema').mkdir()
    shutil.copy2(WORK/'schemas/content-v1.json',package/'schema/content-v1.json')
    dat=next(source.rglob('NWind.dat'));raw=dat.read_bytes()
    if sha(raw)!=KR:raise ValueError('Pinned KR491 DAT mismatch')
    entries=dat_entries(raw);bindings=load(ROOT/'game/data/runtime_bindings.json')
    records=[];failures=[];frame_counts={};seen_hashes=set();atlas_index={};sheet_palettes={}
    prov=[{'id':'prov.asset.kr491','source_mode':'ORIGINAL','file':'NWind.dat','sha256':KR,
           'rule':'Original EPF offsets/stencil and matching TBL/PAL; role bindings remain inferred'},
          {'id':'prov.asset.v125','source_mode':'DERIVED','rule':'Reuse already decoded, hash-pinned v125 atlases; no assumed motion for unknown tables'},
          {'id':'rule.visual.binding','source_mode':'INFERRED','rule':'N,W,S,E directions and body/weapon motion use existing runtime bindings; historical name identity remains unverified'}]

    # The source carries palette indices per model, icon, tile and effect frame.
    for key in ['body','head','sword','spear','shield','fan']:
        if key+'.tbl' in entries:
            rows=re.findall(r'ID (\d+), Palette (\d+), Starting (\d+)',entries[key+'.tbl'][2].decode('ascii'))
            sheet_palettes[key]={}
            total=Epf(entries[key+'.epf'][2]).count
            for j,(mid,pal,start) in enumerate(rows):
                end=int(rows[j+1][2]) if j+1<len(rows) else total
                for i in range(int(start),end):sheet_palettes[key][i]=int(pal)
    mt=[tuple(map(int,v)) for v in re.findall(r'ID (\d+), Palette (\d+), Starting (\d+), Walk (\d+), Attack (\d+), Delay (\d+), Shadow (\d+)',entries['monster.tbl'][2].decode('ascii'))]
    sheet_palettes['monster']={}
    mcount=Epf(entries['monster.epf'][2]).count
    for j,(mid,pal,start,walk,attack,delay,shadow) in enumerate(mt):
        end=mt[j+1][2] if j+1<len(mt) else mcount
        for i in range(start,end):sheet_palettes['monster'][i]=pal
    sheet_palettes['item']={int(i):int(p) for i,p in re.findall(r'ID (\d+), Palette (\d+)',entries['item.tbl'][2].decode('ascii'))}
    efrm=entries['effect.frm'][2];n=struct.unpack_from('<I',efrm)[0]
    if len(efrm)!=4+4*n:raise ValueError('Effect FRM byte count')
    sheet_palettes['effect']={i:struct.unpack_from('<I',efrm,4+4*i)[0] for i in range(n)}
    for g in 'abc':
        key='tile'+g;epf=Epf(entries[key+'.epf'][2]);pals=read_palettes(entries[key+'.pal'][2]);table=tile_table(entries[key+'.tbl'][2],epf.count,len(pals))
        sheet_palettes[key]=dict(enumerate(table.palettes))

    # Decode once per source sheet, preserving each raw frame's original pivot.
    for epf_key,(_,_,blob) in sorted(entries.items()):
        if not epf_key.endswith('.epf'):continue
        key=epf_key[:-4]
        try:
            epf=Epf(blob)
            if not epf.count:raise ValueError('ZERO_FRAMES')
            pal_key=key+'.pal' if key+'.pal' in entries else 'baram.pal'
            pals=read_palettes(entries[pal_key][2]);frames=[epf.frame(i) for i in range(epf.count)]
            nonempty=[f for f in frames if f.width and f.height]
            if not nonempty:raise ValueError('ALL_FRAMES_EMPTY')
            left=min(f.left for f in nonempty);top=min(f.top for f in nonempty)
            right=max(f.left+f.width for f in nonempty);bottom=max(f.top+f.height for f in nonempty)
            cw,ch=right-left,bottom-top
            if cw>4096 or ch>4096:raise ValueError('FRAME_CANVAS_EXCEEDS_BOUND')
            cols=max(1,min(32,4096//cw));perpage=cols*max(1,4096//ch)
            fm=[];pages=[];contact=Image.new('RGBA',(12*96,4*112),(26,29,35,255));draw=ImageDraw.Draw(contact)
            for page_start in range(0,epf.count,perpage):
                selected=frames[page_start:page_start+perpage];rows=(len(selected)+cols-1)//cols
                atlas=Image.new('RGBA',(cols*cw,rows*ch))
                page_path=f'kr491/{key}-{page_start//perpage:03d}.png'
                for j,f in enumerate(selected):
                    pi=sheet_palettes.get(key,{}).get(f.index,0)
                    if not 0<=pi<len(pals):raise ValueError(f'Missing palette {pi} for {key}:{f.index}')
                    x,y=j%cols*cw,j//cols*ch
                    rgba=b''
                    if f.width and f.height:
                        im=Image.frombytes('P',(f.width,f.height),f.indices)
                        im.putpalette([c for rgb in pals[pi].colors for c in rgb]);im=im.convert('RGBA')
                        im.putalpha(Image.frombytes('L',(f.width,f.height),f.alpha));rgba=im.tobytes()
                        atlas.paste(im,(x+f.left-left,y+f.top-top))
                        # Global RGBA dedup includes dimensions and offsets separately.
                        seen_hashes.add(sha(struct.pack('<II',f.width,f.height)+rgba))
                        if f.index<48:
                            preview=im.copy();preview.thumbnail((90,86),Image.Resampling.NEAREST)
                            cx,cy=f.index%12*96,f.index//12*112;contact.alpha_composite(preview,(cx+(96-preview.width)//2,cy+3))
                            draw.text((cx+3,cy+91),str(f.index),fill=(235,235,235,255))
                    fm.append({'frame':f.index,'path':page_path,'region':[x,y,cw,ch],'original_rect':[f.left,f.top,f.width,f.height],
                               'pivot':[-left,-top],'palette':pi,'rgba_sha256':sha(rgba),'opaque_pixels':sum(f.alpha)//255})
                dest=out/page_path;dest.parent.mkdir(exist_ok=True)
                buffer=io.BytesIO();atlas.save(buffer,format='PNG',compress_level=6);dest.write_bytes(buffer.getvalue())
                with Image.open(dest) as check:check.verify()
                pages.append({'path':page_path,'size_bytes':dest.stat().st_size,'sha256':file_sha(dest),'width':atlas.width,'height':atlas.height})
            metadata={'source_file':epf_key,'source_epf_sha256':sha(blob),'palette_file':pal_key,'palette_sha256':sha(entries[pal_key][2]),
                      'palette_ranges':[list(p.animation_ranges) for p in pals],'frames':fm,'pages':pages,'foot_pivot':[-left,-top],
                      'stencil':'EPF_ALPHA_PRESERVED_NO_COLORKEY_AVERAGING','directions':['N','W','S','E'],'generator':'build_assets.py/1'}
            mp=out/f'kr491/{key}.json';write(mp,metadata)
            cp=out/f'review/{key}.png';cp.parent.mkdir(exist_ok=True)
            buffer=io.BytesIO();contact.save(buffer,format='PNG');cp.write_bytes(buffer.getvalue())
            atlas_index[key]=metadata;frame_counts[key]=epf.count
            aid=ids.get('asset','kr491.sheet.'+key)
            records.append(record(aid,'asset',{'name':key,'asset_type':'tile_sheet' if key.startswith('tile') else 'frame_sheet',
              'acquisition':{'bundle_id':args.bundle_id,'member':f'kr491/{key}.json','sha256':file_sha(mp)},'frame_count':epf.count,
              'metadata':{'canvas_px':[cw,ch],'pivot_px':[-left,-top],'alpha':'EPF_STENCIL','pages':pages,
                'palette_count':len(pals),'frame_metadata_member':f'kr491/{key}.json','frame_metadata_sha256':file_sha(mp),
                'directions':['N','W','S','E'],'source_file':epf_key,'source_sha256':sha(blob)},
              'semantic_status':'DECODED_FRAMES_ROLE_UNRESOLVED'},['prov.asset.kr491'],mode='DERIVED'))
            print('decoded',key,epf.count,flush=True)
        except (ValueError,KeyError) as error:
            failures.append({'source_file':epf_key,'field':'EPF_or_palette','value':len(blob),'error':str(error),
              'status':'BLOCKED','expected':'nonempty valid EPF and explicit palette','resolution':'Use dlgframe for line UI, measured alternate version for empty bow; keep originals'})

    def model(key,mid,start,count,animations):
        if key not in atlas_index or start+count>frame_counts[key]:raise ValueError('Model frame range')
        aid=ids.get('asset',f'kr491.{key}.{mid:03d}')
        records.append(record(aid,'asset',{'name':f'{key} model {mid}','asset_type':'animation','frame_count':count,
          'acquisition':{'bundle_id':args.bundle_id,'member':f'kr491/{key}.json','sha256':file_sha(out/f'kr491/{key}.json')},
          'metadata':{'sheet_id':ids.get('asset','kr491.sheet.'+key),'source_model':mid,'starting_frame':start,'count':count,
                      'directions':['N','W','S','E'],'animations':animations,'foot_offsets_member':f'kr491/{key}.json',
                      'attachment':'ORIGINAL_FOOT_RELATIVE_OVERLAY','alpha':'EPF_STENCIL'},
          'semantic_status':'SOURCE_TABLE_MODEL_ROLE_UNRESOLVED'},['prov.asset.kr491','rule.visual.binding'],
          refs=[{'role':'sheet','id':ids.get('asset','kr491.sheet.'+key)}],mode='DERIVED'))
    motion=bindings['motion']
    for key,stride in [('body',104),('head',100),('sword',20),('spear',20),('shield',20),('fan',20)]:
        if key not in atlas_index:continue
        for mid in range(frame_counts[key]//stride):
            if key in ('body','head'):
                animations={k:{'offset':o,'frames_per_direction':2 if k.startswith('attack') else 1 if k in ('cast','pickup') else 3,
                               'directions':4,'frame_ms':100,'timing_mode':'INFERRED_EXISTING_RUNTIME'} for k,o in motion.items() if o<stride}
            else:
                animations={'walk':{'offset':0,'frames_per_direction':3,'directions':4,'frame_ms':100},
                            'attack':{'offset':12,'frames_per_direction':2,'directions':4,'frame_ms':100}}
            model(key,mid,mid*stride,stride,animations)
    for mid,pal,start,walk,attack,delay,shadow in mt:
        # The file allocates reserved poses too: preserve original starts; do not
        # treat unused padding as additional monsters.
        animations={'walk':{'offset':0,'frames_per_direction':walk,'directions':4,'frame_ms':max(1,delay)}}
        if attack:animations['attack']={'offset':walk*4,'frames_per_direction':attack,'directions':4,'frame_ms':max(1,delay)}
        model('monster',mid,start,4*(walk+attack),animations)
        records[-1]['data']['metadata'].update(palette=pal,shadow=shadow,walk=walk,attack=attack,delay_ms=delay)
    for match in re.finditer(r'^ID (\d+), (.*?)(?=^ID |\Z)',entries['effect.tbl'][2].decode('ascii'),re.M|re.S):
        mid=int(match[1]);text=match[0];nf=int(re.search(r'NumFrontFrames (\d+)',text)[1]);nb=int(re.search(r'NumBackFrames (\d+)',text)[1])
        frames=[{'frame':int(i),'delay_ms':int(ms),'alpha_parameter':float(a),'light_parameter':int(l)} for i,ms,a,l in re.findall(r'Frame# (\d+), Delay (\d+), Alpha ([\d.]+), Light (-?\d+)',text)]
        if not frames or len(frames)!=nf+nb or any(f['frame']>=frame_counts['effect'] or f['delay_ms']<=0 for f in frames):
            failures.append({'source_file':'effect.tbl','field':str(mid),'status':'BLOCKED','error':'Invalid original effect sequence'});continue
        repeats={k:int(v) for k,v in re.findall(r'(RepeatFrontFrom|RepeatFrontTo|RepeatBackFrom|RepeatBackTo) (-?\d+)',text)}
        aid=ids.get('asset',f'kr491.effect.{mid:03d}')
        records.append(record(aid,'asset',{'name':f'effect {mid}','asset_type':'effect_sequence','frame_count':len(frames),
          'acquisition':{'bundle_id':args.bundle_id,'member':'kr491/effect.json','sha256':file_sha(out/'kr491/effect.json')},
          'metadata':{'sheet_id':ids.get('asset','kr491.sheet.effect'),'front':frames[:nf],'back':frames[nf:],'repeat':repeats,
            'render_order':['back','actor','front'],'loop_capability_required':any(v>=0 for v in repeats.values()),'alpha':'EPF_STENCIL'},
          'semantic_status':'ORIGINAL_SEQUENCE_SKILL_ROLE_UNRESOLVED'},['prov.asset.kr491'],refs=[{'role':'sheet','id':ids.get('asset','kr491.sheet.effect')}],mode='DERIVED'))
    snd=dat.with_suffix('.snd')
    for key,(_,_,blob) in sorted(dat_entries(snd.read_bytes()).items()):
        if not key.endswith('.wav'):continue
        try:
            with wave.open(io.BytesIO(blob)) as w:meta={'channels':w.getnchannels(),'sample_width':w.getsampwidth(),'rate':w.getframerate(),'samples':w.getnframes()}
            dest=out/'sounds'/key;dest.parent.mkdir(exist_ok=True);dest.write_bytes(blob)
            records.append(record(ids.get('asset','kr491.sound.'+key[:-4]),'asset',{'name':key,'asset_type':'audio','frame_count':1,
              'acquisition':{'bundle_id':args.bundle_id,'member':'sounds/'+key,'sha256':sha(blob),'size_bytes':len(blob)},
              'metadata':dict(meta,duration_ms=meta['samples']*1000//meta['rate']),'semantic_status':'DECODED_AUDIO_EVENT_UNRESOLVED'},['prov.asset.kr491'],mode='DERIVED'))
        except (wave.Error,EOFError) as e:failures.append({'source_file':key,'field':'WAV','status':'FAIL','error':str(e)})
    # Reuse verified historical atlases without re-decoding their inputs.
    zpath=Path(args.v125)
    with zipfile.ZipFile(zpath) as z:
        for name in sorted(z.namelist()):
            if not name.endswith('_frame_index.json'):continue
            meta=__import__('json').loads(z.read(name));png=meta['atlas_filename'];data=z.read(png)
            with Image.open(io.BytesIO(data)) as check:check.verify()
            for member in [name,png]:
                dest=out/'v125'/member;dest.parent.mkdir(exist_ok=True);dest.write_bytes(z.read(member))
            kind=meta['kind'].lower();frame_counts['v125.'+kind]=meta['frame_count']
            records.append(record(ids.get('asset','v125.sheet.'+kind),'asset',{'name':'v125 '+kind,'asset_type':'frame_sheet',
              'frame_count':meta['frame_count'],'acquisition':{'bundle_id':args.bundle_id,'member':'v125/'+name,'sha256':sha(z.read(name))},
              'metadata':{'atlas_member':'v125/'+png,'sha256':sha(data),'frame_metadata_member':'v125/'+name,'cell_px':meta['cell_px'],
                'cols':meta['cols'],'original_offsets':'x_offset_signed/y_offset_signed','sequence_order':'SOURCE_INDEX','directions':'UNRESOLVED',
                'alpha':'PRESERVED_FROM_PREVIOUS_DECODER','source_spr_sha256':meta['source_spr_sha256']},
              'semantic_status':'DECODED_REUSED_MOTION_MAPPING_UNRESOLVED'},['prov.asset.v125'],mode='DERIVED'))
    write(out/'PRIVATE_MANIFEST.json',{'protocol_id':'BARAM_PARALLEL_V1','bundle_id':args.bundle_id,
      'files':[{'path':str(p.relative_to(out)),'size_bytes':p.stat().st_size,'sha256':file_sha(p)} for p in sorted(out.rglob('*')) if p.is_file()],
      'source_dat_sha256':KR,'public_pixels':False})
    bundle=Path(args.bundle);bundle.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():
                zi=zipfile.ZipInfo(str(p.relative_to(out)),(2026,10,14,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o100644<<16;z.writestr(zi,p.read_bytes())
    with zipfile.ZipFile(bundle) as z:
        if z.testzip() is not None:raise ValueError('Bundle CRC')
    shard(package,records);write(package/'provenance.json',prov)
    write(package/'acquisition.json',{'bundle_id':args.bundle_id,'file_name':bundle.name,'size_bytes':bundle.stat().st_size,'sha256':file_sha(bundle),
      'work_acquisition':'PASS_ACTUAL_BYTES_AND_ZIP_CRC','recipient_acquisition':'NOT_RUN','privacy':'PRIVATE_ONLY','library_file_id':None,
      'rebuild':{'tool':'content-work/tools/build_assets.py','sha256':file_sha(Path(__file__)),'base_game_commit':BASE,'source_dat_sha256':KR,'v125_archive_sha256':file_sha(zpath)}})
    write(WORK/'catalog/asset-build.json',{'batch_id':args.batch,'source_frames_by_sheet':frame_counts,'source_frame_count':sum(frame_counts.values()),
      'kr491_unique_rgba_with_dimensions':len(seen_hashes),'asset_definitions':len(records),'decoded_sheets':len(atlas_index),
      'failures':failures,'automatic_png_checks':sum(len(v['pages']) for v in atlas_index.values()),'visual_review':'NOT_RUN_AT_BUILD',
      'counts_scope':'Original frame indices, no padding counted as distinct models; v125 sheets counted separately until cross-version dedup'})
    write(WORK/'catalog/asset-errors.json',failures);ids.save()
    print('BUILT',len(records),'asset definitions',sum(frame_counts.values()),'frames','bundle',bundle.stat().st_size,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['inputs','private-out','v125','batch','bundle-id','bundle']:p.add_argument('--'+key,required=True)
    export(p.parse_args())
