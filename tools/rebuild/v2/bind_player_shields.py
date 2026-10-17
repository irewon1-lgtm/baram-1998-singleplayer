#!/usr/bin/env python3
"""Compose the retained native shield part into existing player frames only.

The equipped item-to-native Shield0 association is explicit reconstruction.
Body/head/weapon pixels, original offsets and DrwOrder tokens are preserved.
No full EPF family decode or source artwork in the checkout is performed.
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
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--dat',type=Path,required=True);ap.add_argument('--reader',type=Path,required=True);a=ap.parse_args()
 runtime=a.runtime.resolve();raw=a.dat.read_bytes()
 if sha(raw)!=DAT_SHA or sha(a.reader.read_bytes())!=READER_SHA:raise ValueError('Pinned source or existing decoder differs')
 spec=importlib.util.spec_from_file_location('retained_shield_reader',a.reader);reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
 dat=reader.dat_entries(raw);actors=json.loads((runtime/'gameplay-assets/actors.json').read_text());game=json.loads((runtime/'gameplay_content.json').read_text())
 draw=[s for s in dat['drworder.tbl'][2].decode('ascii').split(';')if s]
 if len(draw)!=100:raise ValueError('Unexpected source draw order')
 epfs={};pals={};cache={};members={}
 def native(src):
  family=src['epf'].removesuffix('.epf');key=(family,src['frame'],src['palette'],src.get('recolor_byte',0))
  if key not in cache:
   if family not in epfs:
    for n in [family+'.epf',family+'.pal']:
     name,offset,data=dat[n.lower()];members[name]={'member':name,'sha256':sha(data),'dat_offset':offset,'bytes':len(data)}
    epfs[family]=reader.Epf(dat[(family+'.epf').lower()][2]);pals[family]=reader.read_palettes(dat[(family+'.pal').lower()][2])
   f=epfs[family].frame(src['frame']);rgba=f.rgba(pals[family][src['palette']],src.get('recolor_byte',0))
   if src.get('rgba_sha256') and sha(rgba)!=src['rgba_sha256']:raise ValueError('Prior source-frame pixels differ: '+str(key))
   cache[key]=(Image.frombytes('RGBA',(f.width,f.height),rgba),[f.left,f.top])
  if not src.get('rgba_sha256'):
   src['rgba_sha256']=sha(cache[key][0].tobytes());src['offset']=cache[key][1]
  return cache[key]
 variants={};checks=[];output_paths=set();base_checks=0
 for lid,look in list(actors['looks'].items()):
  if 'player' not in lid or lid.endswith('_shield'):continue
  copy=json.loads(json.dumps(look));copy['id']=lid+'_shield';copy.setdefault('source_parts',{})['shield']=0
  copy['binding_scope']='Native KR491 Body/Head/weapon/Shield0 frames and source DrwOrder. Item-to-Shield0 appearance and unarmed+shield pose are explicit reconstruction; exact historical item ID unknown.'
  for action,directions in copy['animations'].items():
   for direction,frames in directions.items():
    for n,fr in enumerate(frames):
     originals=look['animations'][action][direction][n];original_img=Image.open(runtime/'gameplay-assets'/originals['path']).convert('RGBA')
     selected={src['epf'].removesuffix('.epf').lower():src for src in fr['source_frames']}
     bodyrel=next(src['relative_frame']for src in fr['source_frames']if src['epf']=='Body.epf')
     order=draw[bodyrel]
     origin=(64,96)
     def compose(parts):
      canvas=Image.new('RGBA',(128,128))
      for token in order:
       kind={'b':'body','h':'head','w':'sword','s':'shield'}.get(token)
       if kind in parts:
        im,off=native(parts[kind]);canvas.alpha_composite(im,(origin[0]+off[0],origin[1]+off[1]))
      bbox=canvas.getbbox()
      if bbox is None or bbox[0]<=0 or bbox[1]<=0 or bbox[2]>=128 or bbox[3]>=128:raise ValueError('Unsafe composed actor bounds')
      return canvas.crop(bbox),[bbox[0]-64,bbox[1]-96]
     base,offset=compose(selected)
     if base.tobytes()!=original_img.tobytes() or base.size!=original_img.size or offset!=originals['offset']:raise ValueError('Original compositor reproduction mismatch: '+lid+':'+action+':'+direction+':'+str(n))
     base_checks+=1
     # Original casting motion defines no Shield frame. Preserve source body pose.
     masterframes=actors['looks']['warrior_master']['animations'][action][direction]
     source=next((s for s in masterframes[n%len(masterframes)]['source_frames']if s['epf']=='Shield.epf'),None)
     if source is None:continue
     source=json.loads(json.dumps(source));source['frame']=int(source['relative_frame']);source['part_id']='KR491:shield:0';source['source_id']='KR491:sprite:Shield:'+str(source['frame']);source.pop('rgba_sha256',None)
     selected['shield']=source;im,offset=compose(selected);digest=sha(im.tobytes()+bytes(str(offset),'ascii'));relative='images/shield-'+digest[:24]+'.png';target=runtime/'gameplay-assets'/relative
     im.save(target);output_paths.add('gameplay-assets/'+relative)
     fr.update(path=relative,offset=offset,png_sha256=sha(target.read_bytes()),source_frames=list(selected.values()))
  variants[copy['id']]=copy
 actors['looks'].update(variants);actors['source']['members'].update(members)
 actors['shield_item_graphics']={iid:{'player_look_suffix':'_shield','source_ref':'KR491:shield:0','source_tier':'LEGACY_RECONSTRUCTED','rationale':'Native rectangular wood shield0 selected after inspecting all13 retained shield silhouettes for existing 사각방패; exact historical item-to-part ID unproven.'}for iid,it in game['items'].items()if it.get('slot')=='shield'}
 actors['source']['native_shield_repair']={'tool_sha256':sha(Path(__file__).read_bytes()),'container_sha256':DAT_SHA,'reader_sha256':READER_SHA,'source_draw_order_sha256':sha(dat['drworder.tbl'][2]),'exact_historical_item_binding':False}
 target=runtime/'gameplay-assets/actors.json';write(target,actors)
 manifest_path=runtime/'runtime.json';manifest=json.loads(manifest_path.read_text());files={f['path']:f for f in manifest['files']}
 for path in ['gameplay-assets/actors.json',*sorted(output_paths)]:
  p=runtime/path;files[path]={'path':path,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}
 manifest['files']=sorted(files.values(),key=lambda f:f['path']);manifest['fingerprint']=sha(json.dumps(manifest['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());write(manifest_path,manifest)
 report={'schema':'baram.native-shield-binding/1','status':'COMPOSED_RUNTIME_TEST_NOT_RUN','container_sha256':DAT_SHA,'reader_sha256':READER_SHA,
 'tool_sha256':sha(Path(__file__).read_bytes()),'members':members,'source_draw_order_sha256':sha(dat['drworder.tbl'][2]),'source_frames_decoded':len(cache),'existing_base_frames_reproduced_exactly':base_checks,
 'new_player_looks':len(variants),'new_unique_pngs':len(output_paths),'shield_item_graphics':actors['shield_item_graphics'],
 'exact_historical_item_binding':False,'casting_scope':'Original casting group omits held shield; unchanged source casting pose.',
 'actor_index_sha256':sha(target.read_bytes()),'native_platform':'NOT_RUN','visual_review':'NOT_RUN'}
 write(runtime/'SHIELD_BINDING_REPAIR.json',report);print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
