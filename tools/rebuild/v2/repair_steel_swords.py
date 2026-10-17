#!/usr/bin/env python3
"""Repair generic metal sword looks using held native steel Sword2.

Head24 is visually selected from retained original Head pixels. It is a category
reconstruction, not historical item-to-part identity. Non-wearable receipts are
excluded; game stats, IDs, maps and save envelopes are never touched.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
from PIL import Image
DAT_SHA='f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
READER_SHA='f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--dat',type=Path,required=True);ap.add_argument('--reader',type=Path,required=True);a=ap.parse_args();runtime=a.runtime.resolve();raw=a.dat.read_bytes()
 if sha(raw)!=DAT_SHA or sha(a.reader.read_bytes())!=READER_SHA:raise ValueError('Pinned source/reader mismatch')
 spec=importlib.util.spec_from_file_location('native_helmet_reader',a.reader);reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
 dat=reader.dat_entries(raw);actors=json.loads((runtime/'gameplay-assets/actors.json').read_text());game=json.loads((runtime/'gameplay_content.json').read_text());draw=[x for x in dat['drworder.tbl'][2].decode('ascii').split(';')if x]
 # The retained source Head.tbl selected part24 has Starting2400/Palette0.
 if 'ID 2, Palette 0, Starting 40' not in dat['sword.tbl'][2].decode('ascii'):raise ValueError('Selected steel metadata changed')
 epfs={};pals={};cache={};members={}
 def native(src):
  family=src['epf'].removesuffix('.epf');key=(family,src['frame'],src['palette'],src.get('recolor_byte',0))
  if key not in cache:
   if family not in epfs:
    for name in [family+'.epf',family+'.pal']:
     actual,offset,data=dat[name.lower()];members[actual]={'member':actual,'sha256':sha(data),'dat_offset':offset,'bytes':len(data)}
    epfs[family]=reader.Epf(dat[(family+'.epf').lower()][2]);pals[family]=reader.read_palettes(dat[(family+'.pal').lower()][2])
   frame=epfs[family].frame(src['frame']);rgba=frame.rgba(pals[family][src['palette']],src.get('recolor_byte',0))
   if src.get('rgba_sha256') and sha(rgba)!=src['rgba_sha256']:raise ValueError('Prior source leaf changed')
   cache[key]=(Image.frombytes('RGBA',(frame.width,frame.height),rgba),[frame.left,frame.top])
  if not src.get('rgba_sha256'):src['rgba_sha256']=sha(cache[key][0].tobytes());src['offset']=cache[key][1]
  return cache[key]
 variants={};files=set();base_verified=0;changed_looks=0
 for lid,look in actors['looks'].items():
  if not lid.startswith('g1_player') or look.get('source_parts',{}).get('sword')!=1:continue
  look['source_parts']['sword']=2;look['binding_scope']='Native straight steel Sword2 visually replaces brown wooden Sword1 for generic metal sword category; original DrwOrder/anchors/actions unchanged; exact historical item identity unproven.';changed_looks+=1
  for action,dirs in look['animations'].items():
   for direction,frames in dirs.items():
    for fr in frames:
     parts={s['epf'].removesuffix('.epf').lower():s for s in fr['source_frames']};bodyrel=parts['body']['relative_frame'];order=draw[bodyrel]
     if 'sword'not in parts:continue # Original casting group carries no sword.
     def compose():
      canvas=Image.new('RGBA',(128,128))
      for token in order:
       kind={'b':'body','h':'head','w':'sword','s':'shield'}.get(token)
       if kind in parts:
        im,off=native(parts[kind]);canvas.alpha_composite(im,(64+off[0],96+off[1]))
      bbox=canvas.getbbox()
      if bbox is None or bbox[0]<=0 or bbox[1]<=0 or bbox[2]>=128 or bbox[3]>=128:raise ValueError('Steel sprite clipped')
      return canvas.crop(bbox),[bbox[0]-64,bbox[1]-96]
     reproduced,off=compose();old=Image.open(runtime/'gameplay-assets'/fr['path']).convert('RGBA')
     if reproduced.size!=old.size or reproduced.tobytes()!=old.tobytes() or off!=fr['offset']:raise ValueError('Base player differs before steel change')
     base_verified+=1;src=dict(parts['sword']);src.update(frame=40+int(src['relative_frame']),palette=0,recolor_byte=0,part_id='KR491:sword:2',source_id='KR491:sprite:Sword:'+str(40+int(src['relative_frame'])),recolor_semantics='SOURCE_PALETTE_UNSHIFTED');src.pop('rgba_sha256',None);parts['sword']=src
     im,off=compose();h=sha(im.tobytes()+bytes(str(off),'ascii'));path='images/steel-'+h[:24]+'.png';target=runtime/'gameplay-assets'/path;im.save(target);files.add('gameplay-assets/'+path)
     fr.update(path=path,offset=off,png_sha256=sha(target.read_bytes()),source_frames=list(parts.values()))
 actors['source']['members'].update(members);actors['source']['native_steel_repair']={'tool_sha256':sha(Path(__file__).read_bytes()),'container_sha256':DAT_SHA,'reader_sha256':READER_SHA,'selected_part':'KR491:sword:2','binding_status':'CATEGORY_RECONSTRUCTION_NOT_ITEM_EXACT'}
 bindings=0
 for item in actors['item_equipment_graphics'].values():
  if item.get('style')=='sword':
   item['source_ref']='KR491:sword:2';item['rationale']='Visually selected native straight steel blade Sword2, distinct from brown wooden Sword1 used by 목도; exact historical item identity unproven.';bindings+=1
 actorfile=runtime/'gameplay-assets/actors.json';actorfile.write_text(json.dumps(actors,ensure_ascii=False,separators=(',',':'))+'\n')
 report={'schema':'baram.native-steel-binding/1','status':'COMPOSED_ISOLATED_ACTUAL_REVIEW_REQUIRED','tool_sha256':sha(Path(__file__).read_bytes()),'container_sha256':DAT_SHA,'reader_sha256':READER_SHA,'source_members':members,'selected_native_part':'KR491:sword:2','base_frames_reproduced_exactly':base_verified,'decoded_selected_leaf_frames':len(cache),'changed_looks':changed_looks,'new_unique_pngs':len(files),'bound_items':bindings,'item_exact_identity':'UNPROVEN_GENERIC_STEEL_CATEGORY','wooden_sword1_scope':'Existing player_weapon/목도 and native wooden_sword60 unchanged','gameplay_content_unchanged_sha256':sha((runtime/'gameplay_content.json').read_bytes())}
 write(runtime/'STEEL_BINDING_REPAIR.json',report)
 manifestfile=runtime/'runtime.json';manifest=json.loads(manifestfile.read_text());manifest['files']=[{'path':str(p.relative_to(runtime)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(runtime.rglob('*'))if p.is_file()and p.name!='runtime.json'];manifest['fingerprint']=sha(json.dumps(manifest['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());write(manifestfile,manifest);print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
