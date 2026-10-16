#!/usr/bin/env python3
"""Freeze only the P3 world/actors and actually selected effects/sounds closure."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import wave
from PIL import Image
from priority_maps import write

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canon(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def safe(path):
    p=Path(path)
    if p.is_absolute() or '..' in p.parts or '\\' in path:raise ValueError(f'Unsafe relative path {path}')
    return p

def freeze(base,overlay,actors,output):
    if output.exists():raise ValueError('Output exists; fresh generation required')
    repo=Path(__file__).resolve().parents[3]
    if output.resolve()==repo or repo in output.resolve().parents:raise ValueError('Original-derived runtime must stay outside public checkout')
    defs=json.loads((overlay/'gameplay_content.json').read_text())
    actor_receipt=json.loads((actors/'ASSET_RECEIPT.json').read_text())
    actor_defs=json.loads((actors/'actors.json').read_text())
    missing_icons=set(defs['items'])-set(actor_defs['icons'])
    if missing_icons:raise ValueError(f'Missing active item icons {sorted(missing_icons)}')
    missing_looks={r.get('look_id',r.get('look')) for kind in ['npcs','monsters'] for r in defs[kind].values()}-set(actor_defs['looks'])
    if missing_looks:raise ValueError(f'Missing actor looks {sorted(missing_looks)}')
    source=json.loads((base/'kr491/kr491_runtime.json').read_text())
    output.mkdir(parents=True)
    def copy(src,relative,expected=None):
        relative=safe(relative);dst=output/relative
        if expected and sha(src)!=expected:raise ValueError(f'Input hash mismatch {src.name}')
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        if sha(src)!=sha(dst):raise ValueError(f'Copy hash mismatch {relative}')
    copy(overlay/'gameplay_content.json','gameplay_content.json')
    for p in sorted((overlay/'gameplay').rglob('*')):
        if p.is_file() and p.suffix.lower() in ['.png','.json']:copy(p,p.relative_to(overlay).as_posix())
    for r in actor_receipt['required_package_files']:
        copy(actors/safe(r['path']),'gameplay-assets/'+r['path'],r['sha256'])
    effect_ids={int(s['effect_id']) for s in defs['skills'].values() if s.get('effect_id') is not None}
    sound_ids={int(s['sound_id']) for s in defs['skills'].values() if s.get('sound_id') is not None}
    for k,v in defs.get('config',{}).items():
        if v is not None and k.endswith('effect_id'):effect_ids.add(int(v))
        if v is not None and k.endswith('sound_id'):sound_ids.add(int(v))
    kept_effects=[deepcopy(e) for e in source['effects'] if int(e['id']) in effect_ids]
    if {int(e['id']) for e in kept_effects}!=effect_ids:raise ValueError('Unknown referenced effect')
    kept_sounds=[]
    for s in source['sounds']:
        native=int(Path(s['member']).stem)
        if native in sound_ids:
            item=deepcopy(s);item['id']=native;kept_sounds.append(item)
    if {int(s['id']) for s in kept_sounds}!=sound_ids:raise ValueError('Unknown referenced sound')
    kept_ui=deepcopy(source.get('ui',[]))
    paths=set()
    def references(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k=='path' and isinstance(v,str) and v.lower().endswith(('.png','.wav')):paths.add(v)
                else:references(v)
        elif isinstance(obj,list):
            for v in obj:references(v)
    references(kept_effects);references(kept_sounds);references(kept_ui)
    for path in sorted(paths):copy(base/'kr491'/safe(path),'kr491/'+path)
    subset={k:deepcopy(source[k]) for k in ['schema','source_id','source_version','target1998_2001_match','input_sha256','source_members'] if k in source}
    subset.update({'effects':kept_effects,'sounds':kept_sounds,'ui':kept_ui,'parts':{},'character_variants':[],
      'selection_scope':'P3 dependency closure only; original KR491 index remains unchanged in parent generation',
      'original_source_effect_count':len(source['effects']),'original_source_sound_count':len(source['sounds']),
      'sound_id_semantics':'Original native WAV member number, not compacted array index',
      'parent_runtime_sha256':sha(base/'runtime.json')})
    write(output/'kr491/kr491_runtime.json',subset)
    # Verify every actual output file, not only the manifest's hashes.
    png=wav=0
    for p in output.rglob('*'):
        if p.suffix=='.png':
            with Image.open(p) as im:im.verify()
            with Image.open(p) as im:im.load()
            png+=1
        elif p.suffix=='.wav':
            with wave.open(str(p),'rb') as stream:
                frames=stream.readframes(stream.getnframes())
                if not frames:raise ValueError('Empty selected WAV')
            wav+=1
    rows=[{'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.rglob('*')) if p.is_file()]
    manifest={'schema':'baram.work.p3.runtime/1','generation':'WORK-GAMEPLAY-GEN001','profile':defs['profile'],
      'world_profile':defs.get('world_profile'),'files':rows,'private_only':True,'compatibility':defs['compatibility'],
      'parent_generation':'WORK-PRIORITY-GEN002','parent_runtime_sha256':sha(base/'runtime.json'),
      'compiler_sha256':sha(Path(__file__)),'input_definitions_sha256':sha(overlay/'gameplay_content.json'),
      'actor_receipt_sha256':sha(actors/'ASSET_RECEIPT.json'),'fingerprint':canon(rows),
      'excluded':['unselected original maps/effects/sounds','original archives/DAT/SND/EXE','contact sheets','raw reference data','fonts','signing keys','user saves','tests/logs'],
      'dependency_closure':{'effect_ids':sorted(effect_ids),'sound_native_ids':sorted(sound_ids),'actor_package_files':len(actor_receipt['required_package_files']),
        'maps':len(defs['maps']),'png_files_verified':png,'wav_files_decoded':wav}}
    write(output/'runtime.json',manifest)
    # Final manifest file list is checked against actual bytes after it is frozen.
    for r in rows:
        if sha(output/r['path'])!=r['sha256']:raise ValueError('Frozen bytes changed')
    result={'status':'FROZEN_MINIMAL_P3_RUNTIME','output':str(output),'files':len(rows)+1,
      'bytes':sum(r['bytes'] for r in rows)+(output/'runtime.json').stat().st_size,'runtime_sha256':sha(output/'runtime.json'),
      'png_verified':png,'wav_decoded':wav,'effect_ids':sorted(effect_ids),'sound_native_ids':sorted(sound_ids),
      'runtime_gameplay':'NOT_RUN','source_archives_or_user_saves_copied':False}
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['base','overlay','actors','output']:p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args();print(json.dumps(freeze(a.base,a.overlay,a.actors,a.output),ensure_ascii=False))
