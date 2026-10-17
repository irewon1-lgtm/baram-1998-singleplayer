#!/usr/bin/env python3
"""Bind explicit reconstructed capes plus native player source-part layers.
No content fields change. Capes use exact source-part anchors and source draw
ordering, inserted after body for north and before body for other directions.
"""
import argparse,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
from PIL import Image
DAT_SHA='f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
READER_SHA='f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['runtime','dat','reader','cape-prototype']:p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();runtime=a.runtime.resolve();raw=a.dat.read_bytes()
 if sha(raw)!=DAT_SHA or sha(a.reader.read_bytes())!=READER_SHA:raise ValueError('Pinned native source mismatch')
 spec=importlib.util.spec_from_file_location('cape_part_reader',a.reader);reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
 dat=reader.dat_entries(raw);draw=[x for x in dat['drworder.tbl'][2].decode('ascii').split(';')if x]
 file=runtime/'gameplay-assets/actors.json';actors=json.loads(file.read_text());cape=json.loads((a.cape_prototype/'cape-layer-looks.json').read_text());content_before=sha((runtime/'gameplay_content.json').read_bytes())
 cache={};epfs={};pals={};parts_written=set();frames=0
 for lid,look in actors['looks'].items():
  if 'player'not in lid:continue
  for action,dirs in look['animations'].items():
   for direction,items in dirs.items():
    for fr in items:
     parts={s['epf'].removesuffix('.epf').lower():s for s in fr['source_frames']};order=draw[parts['body']['relative_frame']];layers=[]
     for token in order:
      kind={'b':'body','h':'head','w':'sword','s':'shield'}.get(token)
      if kind not in parts:continue
      src=parts[kind];family=src['epf'].removesuffix('.epf');key=(family,src['frame'],src['palette'],src.get('recolor_byte',0))
      if key not in cache:
       if family not in epfs:epfs[family]=reader.Epf(dat[(family+'.epf').lower()][2]);pals[family]=reader.read_palettes(dat[(family+'.pal').lower()][2])
       leaf=epfs[family].frame(src['frame']);rgba=leaf.rgba(pals[family][src['palette']],src.get('recolor_byte',0))
       if src.get('rgba_sha256')and sha(rgba)!=src['rgba_sha256']:raise ValueError('Native leaf hash differs')
       image=Image.frombytes('RGBA',(leaf.width,leaf.height),rgba);offset=[leaf.left,leaf.top];path='images/player-part-'+sha(rgba+str(offset).encode())[:24]+'.png';dest=runtime/'gameplay-assets'/path;image.save(dest);parts_written.add(path)
       cache[key]={'kind':kind,'path':path,'offset':offset,'png_sha256':sha(dest.read_bytes())}
      part_id=cache[key]['path'].split('/')[-1].removesuffix('.png');actors.setdefault('player_part_layers',{})[part_id]=cache[key];layers.append(part_id)
     fr['part_layers']=layers;frames+=1
 for look in cape['looks'].values():
  for dirs in look['animations'].values():
   for frames2 in dirs.values():
    for fr in frames2:
     src=a.cape_prototype/fr['path'];dest=runtime/'gameplay-assets'/fr['path'];shutil.copyfile(src,dest)
     if sha(dest.read_bytes())!=fr['png_sha256']:raise ValueError('Cape copy mismatch')
 actors['looks'].update(cape['looks']);actors['cape_item_graphics']=cape['cape_item_graphics'];actors['source']['cape_reconstruction']={'source':cape['source'],'recipe':cape['recipe'],'limits':cape['limits'],'integration_tool_sha256':sha(Path(__file__).read_bytes()),'layer_order':'native DrwOrder; north cape inserted directly after body/before head, other directions before native parts; no weapon/shield added to native casting'}
 file.write_text(json.dumps(actors,ensure_ascii=False,separators=(',',':'))+'\n')
 report={'schema':'baram.cape-native-layers/1','status':'COMPOSED_ACTUAL_GAME_REVIEW_REQUIRED','native_player_frames':frames,'native_unique_part_pngs':len(parts_written),'cape_looks':len(cape['looks']),'cape_bindings':len(cape['cape_item_graphics']),'content_unchanged':content_before==sha((runtime/'gameplay_content.json').read_bytes()),'content_sha256':content_before,'actor_sha256':sha(file.read_bytes()),'source_dat_sha256':DAT_SHA}
 (runtime/'CAPE_BINDING_REPAIR.json').write_text(json.dumps(report,indent=2)+'\n')
 manifestfile=runtime/'runtime.json';manifest=json.loads(manifestfile.read_text());manifest['files']=[{'path':str(p.relative_to(runtime)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(runtime.rglob('*'))if p.is_file()and p.name!='runtime.json'];manifest['fingerprint']=sha(json.dumps(manifest['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());manifestfile.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
