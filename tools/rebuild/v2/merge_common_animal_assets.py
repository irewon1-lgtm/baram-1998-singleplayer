#!/usr/bin/env python3
"""Merge only reviewed animal looks/aliases/PNGs into a new world runtime clone."""
import argparse,hashlib,json,shutil
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args();stage=a.stage.resolve();root=a.runtime.resolve();content_before=sha((root/'gameplay_content.json').read_bytes());actorfile=root/'gameplay-assets/actors.json';actors=json.loads(actorfile.read_text());new=json.loads((stage/'gameplay-assets/actors.json').read_text());receipt=json.loads((stage/'COMMON_ANIMAL_REPAIR.json').read_text());before_sha=sha(actorfile.read_bytes());files=set()
 for lid in receipt['affected_looks']:
  look=new['looks'][lid];base=lid.split('_color')[0];prior=actors['looks'][base]
  for action,dirs in look['animations'].items():
   for direction,frames in dirs.items():
    old=prior['animations'][action][direction]
    if len(old)!=len(frames):raise ValueError('Actor frame count changed')
    for i,fr in enumerate(frames):
     if fr['offset']!=old[i]['offset']or fr['duration_ms']!=old[i]['duration_ms']:raise ValueError('Actor anchor/timing changed')
     files.add(fr['path'])
  actors['looks'][lid]=look
 for entity,l in receipt['entity_aliases'].items():actors.setdefault('actor_aliases',{})[entity]=l['new_look']
 actors['source']['common_animal_repair']=new['source']['common_animal_repair'];copied=0
 for path in files:
  src=stage/'gameplay-assets'/path;dest=root/'gameplay-assets'/path
  if dest.exists():
   if sha(src.read_bytes())!=sha(dest.read_bytes()):raise ValueError('Existing animal PNG differs')
  else:shutil.copyfile(src,dest);copied+=1
 actorfile.write_text(json.dumps(actors,ensure_ascii=False,separators=(',',':'))+'\n');shutil.copyfile(stage/'COMMON_ANIMAL_REPAIR.json',root/'COMMON_ANIMAL_REPAIR.json')
 if sha((root/'gameplay_content.json').read_bytes())!=content_before:raise ValueError('World content changed')
 report={'schema':'baram.common-animal-merge/1','status':'REVIEWED_EXPLICIT_RECONSTRUCTION_AND_NATIVE_PALETTES','content_sha256_preserved':content_before,'actors_before_sha256':before_sha,'actors_after_sha256':sha(actorfile.read_bytes()),'replaced_or_added_looks':receipt['affected_looks'],'entity_aliases':receipt['entity_aliases'],'affected_maps':receipt['affected_maps'],'copied_new_pngs':copied,'preserved':'Every content ID/stat/AI/hitbox/collision/map/exit/route and selectedframe offset/duration; actorartalias changes only','visual_review_scope':'Root reviewed actual front/side; actoragent12standing/walk/attack frames. Bear explicit reconstructed anatomy, not native/historicalbearclaim; named colors sourcepalette reconstruction.'}
 (root/'COMMON_ANIMAL_MERGE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');mf=root/'runtime.json';m=json.loads(mf.read_text());m['files']=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(root.rglob('*'))if p.is_file()and p.name!='runtime.json'];m['fingerprint']=sha(json.dumps(m['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());mf.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');report['runtime_sha256']=sha(mf.read_bytes());print(json.dumps({k:report[k]for k in ['content_sha256_preserved','actors_before_sha256','actors_after_sha256','copied_new_pngs','runtime_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
