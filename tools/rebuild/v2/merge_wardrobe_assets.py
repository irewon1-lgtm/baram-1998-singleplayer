#!/usr/bin/env python3
"""Merge reviewed actor-only wardrobe payload, preserving world/content bytes."""
import argparse,hashlib,json,copy,shutil
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args();stage=a.stage.resolve();runtime=a.runtime.resolve();cf=runtime/'gameplay_content.json';before=sha(cf.read_bytes());f=runtime/'gameplay-assets/actors.json';base=json.loads(f.read_text());added=json.loads((stage/'gameplay-assets/actors.json').read_text());looks=0;frames=0
 for lid,look in added['looks'].items():
  if lid in base['looks']:
   if 'player'not in lid:continue
   old=base['looks'][lid];clean=copy.deepcopy(look)
   for dirs in clean['animations'].values():
    for fs in dirs.values():
     for frame in fs:frame.pop('part_layers',None)
   steel_change=lid.startswith('g1_player') and old.get('source_parts',{}).get('sword')==1 and look.get('source_parts',{}).get('sword')==2
   if clean!=old and not steel_change:raise ValueError('Non-layer original actor changed:'+lid)
   base['looks'][lid]=look
  elif lid.endswith('_helmet')or lid.startswith('cape_'):base['looks'][lid]=look;looks+=1
  else:raise ValueError('Unexpected actor addition:'+lid)
 for key in ['player_part_layers','helmet_item_graphics','cape_item_graphics','item_equipment_graphics']:base[key]=added[key]
 for key in ['native_helmet_repair','cape_reconstruction','native_steel_repair']:base['source'][key]=added['source'][key]
 base['source']['members'].update(added['source']['members'])
 paths=set()
 for look in base['looks'].values():
  for dirs in look.get('animations',{}).values():
   for fs in dirs.values():
    for fr in fs:
     if fr.get('path'):paths.add(fr['path']);frames+=1
 for layer in base['player_part_layers'].values():paths.add(layer['path'])
 copied=0
 for path in paths:
  src=stage/'gameplay-assets'/path;dest=runtime/'gameplay-assets'/path
  if not src.exists():continue
  if dest.exists():
   if sha(src.read_bytes())!=sha(dest.read_bytes()):raise ValueError('Existing actor PNG differs:'+path)
  else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);copied+=1
 f.write_text(json.dumps(base,ensure_ascii=False,separators=(',',':'))+'\n')
 for name in ['HELMET_BINDING_REPAIR.json','CAPE_BINDING_REPAIR.json','STEEL_BINDING_REPAIR.json']:shutil.copyfile(stage/name,runtime/name)
 if sha(cf.read_bytes())!=before:raise ValueError('World content changed')
 report={'schema':'baram.wardrobe-merge/1','status':'REVIEWED_GENERIC_CATEGORY_COMPOSITES','content_sha256_preserved':before,'actors_sha256':sha(f.read_bytes()),'new_looks':looks,'new_copied_pngs':copied,'looks_total':len(base['looks']),'helmet_bindings':len(base['helmet_item_graphics']),'cape_bindings':len(base['cape_item_graphics']),'native_player_part_pngs':len(base['player_part_layers']),'receipt_excluded':'물병보관증 legacy slot=helmet but not wearable; no gameplay fields changed','limits':['Exact historical item/style/color binding unproven for native gray helmet and six cape categories','Generic metal Sword2 gray straight blade fixes wooden Sword1 mismatch; exact historical item identity unproven; native wooden styles preserved'],'human_review':'Root accepted actual helmet/cape north/south; actor agent reviewed actual4direction body0/body2/helmet/cape/equip/unequip; native steel category screenshot reviewed before merge; actual final production-source retest follows'}
 (runtime/'WARDROBE_MERGE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 manifestfile=runtime/'runtime.json';manifest=json.loads(manifestfile.read_text());manifest['files']=[{'path':str(p.relative_to(runtime)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(runtime.rglob('*'))if p.is_file()and p.name!='runtime.json'];manifest['fingerprint']=sha(json.dumps(manifest['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());manifestfile.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');report['runtime_sha256']=sha(manifestfile.read_bytes());report['runtime_fingerprint']=manifest['fingerprint'];print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
