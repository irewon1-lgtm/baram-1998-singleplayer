#!/usr/bin/env python3
"""Convert only the47 recovered inputs; good sheets are never regenerated."""
import argparse,io,shutil,sys,zipfile
from pathlib import Path
from PIL import Image
sys.dont_write_bytecode=True
from common import ROOT,WORK,IDs,load,write,file_sha,sha,record,shard
from probe_epf_clipping import ClippedEpf
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import dat_entries,read_palettes

def build(a):
    ids=IDs();probe=load(WORK/'catalog/expansion-2/epf-clipping-probe.json');entries=dat_entries(a.dat.read_bytes())
    p=WORK/'packages'/a.batch
    if p.exists():raise ValueError('Use new immutable batch')
    out=WORK/'drafts'/a.batch;out.mkdir(parents=True);records=[];total=0;pngs=0
    for row in probe['attempts']:
        if row['result']!='PASS':continue
        key=row['source_file'];stem=key[:-4];ep=ClippedEpf(entries[key][2]);frames=[ep.frame(i) for i in range(ep.count)]
        palkey=stem+'.pal' if stem+'.pal' in entries else 'baram.pal';pals=read_palettes(entries[palkey][2]);palette=pals[0]
        nonempty=[f for f in frames if f.width and f.height];left=min(f.left for f in nonempty);top=min(f.top for f in nonempty)
        cw=max(f.left+f.width for f in nonempty)-left;ch=max(f.top+f.height for f in nonempty)-top
        cols=max(1,min(8,4096//cw));capacity=cols*max(1,4096//ch);pages=[];fm=[]
        for start in range(0,len(frames),capacity):
            group=frames[start:start+capacity];im=Image.new('RGBA',(cols*cw,((len(group)+cols-1)//cols)*ch));member=f'kr491-ui/{stem}-{start//capacity:03d}.png'
            for n,f in enumerate(group):
                x=n%cols*cw;y=n//cols*ch;rgba=f.rgba(palette) if f.width and f.height else b''
                if rgba:im.paste(Image.frombytes('RGBA',(f.width,f.height),rgba),(x+f.left-left,y+f.top-top))
                fm.append({'frame':f.index,'path':member,'region':[x,y,cw,ch],'original_rect':[f.left,f.top,f.width,f.height],'pivot':[-left,-top],'palette':0,'rgba_sha256':sha(rgba),'opaque_pixels':sum(f.alpha)//255})
            dest=out/member;dest.parent.mkdir(exist_ok=True);b=io.BytesIO();im.save(b,format='PNG',compress_level=9);dest.write_bytes(b.getvalue())
            with Image.open(dest) as check:check.verify()
            pages.append({'path':member,'width':im.width,'height':im.height,'size_bytes':dest.stat().st_size,'sha256':file_sha(dest)});pngs+=1
        metadata={'source_file':key,'source_epf_sha256':sha(entries[key][2]),'palette_file':palkey,'palette_sha256':sha(entries[palkey][2]),'frames':fm,'pages':pages,
          'source_profile':'ORIGINAL_SPAN_POSITION_RECTANGLE_CLIP','clipped_runs':ep.clipped_runs,'clipped_pixels':ep.clipped_pixels,'original_offsets_preserved':True,
          'source_palette_selection':'source-specific palette if present, otherwise source baram.pal[0], same prior converter policy','native_raster_comparison':'NOT_RUN'}
        member=f'kr491-ui/{stem}.json';write(out/member,metadata);aid=ids.get('asset','kr491.sheet.'+stem)
        records.append(record(aid,'asset',{'name':stem,'asset_type':'frame_sheet','frame_count':ep.count,
          'acquisition':{'bundle_id':'wk.bundle.assets.002','member':member,'sha256':file_sha(out/member)},
          'metadata':{'canvas_px':[cw,ch],'pivot_px':[-left,-top],'pages':pages,'frame_metadata_member':member,'frame_metadata_sha256':file_sha(out/member),
            'alpha':'SOURCE_STENCIL_WITH_ORIGINAL_RECTANGLE_CLIP','source_file':key,'source_sha256':sha(entries[key][2]),'source_profile':'ORIGINAL_SPAN_POSITION_RECTANGLE_CLIP'},
          'semantic_status':'RECOVERED_UI_FRAMES_EVENT_BINDING_SEPARATE_NOT_GAME_IMPORTED'},['prov.ui.original-clip'],mode='DERIVED'));total+=ep.count
    (p/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',p/'schema/content-v1.json')
    write(p/'provenance.json',[{'id':'prov.ui.original-clip','source_mode':'DERIVED','source_dat_sha256':file_sha(a.dat),'decoder':'content-work/tools/probe_epf_clipping.py',
      'rules':{'mask':'advance original run&127 source span, consume row delimiter, intersect writes with original rectangle; no pixel recolor or next-row overwrite','proof':'NA495 original binary span clipping at40218d–4021c7 and402238–402272, plus20 unchanged normal-frame comparisons',
        'limit':'native client raster comparison NOT_RUN; asset decode readiness and UI event binding are separate'}}])
    shard(p,records);files=[{'path':str(x.relative_to(out)),'size_bytes':x.stat().st_size,'sha256':file_sha(x)} for x in sorted(out.rglob('*')) if x.is_file()]
    write(out/'PRIVATE_MANIFEST.json',{'privacy':'PRIVATE_ONLY','batch_id':a.batch,'files':files});bundle=WORK/'drafts'/a.bundle_name
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():
                info=zipfile.ZipInfo(str(f.relative_to(out)),(2026,10,14,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,f.read_bytes())
    with zipfile.ZipFile(bundle) as z:assert z.testzip() is None
    write(p/'acquisition.json',{'bundle_id':'wk.bundle.assets.002','file_name':bundle.name,'size_bytes':bundle.stat().st_size,'sha256':file_sha(bundle),'privacy':'PRIVATE_ONLY',
       'library_file_id':None,'work_acquisition':'PASS_ACTUAL_BYTES_AND_CRC','recipient_acquisition':'NOT_RUN','rebuild':{'source_dat_sha256':file_sha(a.dat),'tool':'content-work/tools/build_recovered_ui_assets.py'}})
    write(p/'recovery-summary.json',{'scope':'DATA_ONLY','new_asset_definitions':len(records),'source_frames':total,'png_files':pngs,'decode_state':'RECOVERED_AND_PNG_VERIFIED',
      'source_failure_count_before':58,'source_failure_count_after_decode':11,'remaining':['bow.epf ZERO_FRAMES','line001.epf empty bytes','9 original effect sequences zero delay/empty sequence'],
      'existing_good_asset_redecoded':0,'normal_representative_regression_count':20,'role_assigned_only':0,'content_event_links':'SEPARATE_PACKET_REQUIRED','game_import':'NOT_RUN','gameplay':'NOT_RUN'})
    ids.save();print(a.batch,'assets',len(records),'frames',total,'PNG',pngs,'ZIP bytes',bundle.stat().st_size)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--dat',type=Path,required=True);p.add_argument('--bundle-name',required=True);build(p.parse_args())
