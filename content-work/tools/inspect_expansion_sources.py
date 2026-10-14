#!/usr/bin/env python3
"""Bounded, read-only source inventory and temporary contact sheets for Work2."""
import argparse
import collections
import json
import math
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.dont_write_bytecode = True
from common import ROOT, WORK, load, lines, write, file_sha
sys.path.insert(0, str(ROOT / 'tools'))
from legacy_assets import dat_entries, Epf, read_palettes
from legacy_maps import tile_table, static_objects, ground_id

def inspect(shared, inputs):
    assets = [r for p in (WORK/'packages/WK-ASSETS-001').glob('content-*.jsonl') for r in lines(p)]
    content = [r for p in (WORK/'packages/WK-CONTENT-001').glob('content-*.jsonl') for r in lines(p)]
    oldmaps = [r for p in (WORK/'catalog/source-maps').glob('*.jsonl') for r in lines(p)]
    oldassets = {r['asset_id']: r for p in (WORK/'catalog/unused-assets').glob('*.jsonl') for r in lines(p)}
    defs = {r['id']: r for r in assets}
    classifications = []
    for a in sorted(assets, key=lambda r:r['id']):
        d=a['data']; family=a['id'].split('.')[3]
        role = {'body':'player_body_or_clothing','head':'hair_headwear_variant','sword':'weapon_sword',
                'spear':'weapon_staff_or_spear','fan':'weapon_fan','shield':'shield_overlay',
                'monster':'actor_model_identity_unverified','effect':'spell_combat_effect','sound':'audio_event_unverified'}.get(family)
        if role is None:
            n=d['name'].lower()
            role='environment_tile' if d['asset_type']=='tile_sheet' else 'item_icons' if 'item' in n else 'frame_sheet_ui_or_environment'
        classifications.append({'asset_id':a['id'],'family':family,'role_class':role,
             'state':oldassets[a['id']]['state'],'identity':'UNVERIFIED_SOURCE_NAME',
             'frame_count':d['frame_count'],'metadata_sha256':d['acquisition']['sha256'],
             'next':'Use only reviewed purpose-compatible models; full animation review is separate'})
    dat=next(inputs.rglob('NWind.dat')); entries=dat_entries(dat.read_bytes());tables={}
    for g in 'ABC':
        ep=Epf(entries['tile'+g.lower()+'.epf'][2]); pals=read_palettes(entries['tile'+g.lower()+'.pal'][2])
        tables[g]=tile_table(entries['tile'+g.lower()+'.tbl'][2],ep.count,len(pals))
    objects=static_objects(entries['sobj.tbl'][2],tables['C'].count)
    selected={r['data']['layout_acquisition']['source_sha256'] for r in content if r['kind']=='map'}
    selected_source={r['data']['layout_acquisition']['source_original_map_id'] for r in content if r['kind']=='map'}
    seen={}; maps=[];folder=next(inputs.rglob('Maps'))
    for old in sorted(oldmaps,key=lambda r:r['original_map_id']):
        mid=old['original_map_id'];p=folder/f'TK{mid}.map';r=dict(old)
        if not p.is_file():r.update(classification='ACCESS_UNAVAILABLE',reason='Listed source file missing')
        else:
            raw=p.read_bytes();h=file_sha(p)
            if h!=old['sha256'] or len(raw)!=old['size_bytes']:
                r.update(classification='SOURCE_CHANGED',reason='Existing source pin differs')
            elif mid in selected_source:r.update(classification='ALREADY_SELECTED')
            elif h in selected:r.update(classification='IDENTICAL_SELECTED_TERRAIN')
            elif h in seen:r.update(classification='DUPLICATE_UNSELECTED_TERRAIN',duplicate_original_map_id=seen[h])
            elif len(raw)%4 or not raw:r.update(classification='DAMAGED_OR_INCOMPLETE',reason='4-byte cells not complete')
            else:
                try:
                    for word,obj in struct.iter_unpack('<HH',raw):
                        ground_id(word,tables)
                        if obj>=len(objects):raise ValueError(f'Object {obj} outside source table')
                    count=len(raw)//4;root=math.isqrt(count)
                    if root*root==count and 8<=root<=128:
                        r.update(classification='NEW_TERRAIN_SQUARE_INTERPRETABLE',dimensions=[root,root],
                          dimension_mode='INFERRED_SQUARE_BYTE_COUNT_NOT_HISTORICALLY_CONFIRMED')
                    else:r.update(classification='NEEDS_DIMENSION_EVIDENCE',reason='Cell references valid, dimensions ambiguous')
                except ValueError as e:r.update(classification='NEEDS_FORMAT_OR_VERSION',reason=str(e))
            seen.setdefault(h,mid)
        maps.append(r)
    out=WORK/'catalog/expansion-2';out.mkdir(exist_ok=True)
    (out/'asset-worklist.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in classifications))
    (out/'map-worklist.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in maps))
    write(out/'start.json',{'work_commit':'71d6359f8652e10d055326267ffb4677eee0d5d9','scope':'DATA_ONLY',
       'asset_count':len(assets),'asset_initial_states':dict(collections.Counter(r['state'] for r in classifications)),
       'map_count':len(maps),'map_classifications':dict(collections.Counter(r['classification'] for r in maps)),
       'sources':{'dat_sha256':file_sha(dat),'shared_private_manifest_sha256':file_sha(shared/'PRIVATE_MANIFEST.json')},
       'termination':'Process fixed inventory; do not add external discovery or fabricate roles to exhaust counts',
       'first_batch':'Existing runtime item classification, compatible equipment models, bounded explicit frame selections',
       'checks':['effective-state field guards','references/frame bounds','acquisition/use graph','map entry/return/static component','quest prerequisite and consume graph','defined buy/sell/crafting arbitrage'],
       'game_import':'NOT_RUN','gameplay':'NOT_RUN'})
    contact=WORK/'drafts/expansion-2-review';contact.mkdir(parents=True,exist_ok=True)
    for family in ['body','head','sword','spear','shield','fan','monster']:
        members=[r for r in assets if r['id'].startswith('wk.asset.kr491.'+family+'.')]
        metadata=load(shared/'kr491'/f'{family}.json');frameby={f['frame']:f for f in metadata['frames']};pages={}
        for start in range(0,len(members),100):
            group=sorted(members,key=lambda r:r['id'])[start:start+100]
            im=Image.new('RGB',(1000,math.ceil(len(group)/10)*108),(38,42,49));draw=ImageDraw.Draw(im)
            for n,a in enumerate(group):
                md=a['data']['metadata'];walk=md['animations'].get('walk',md['animations'].get('walk_unarmed'))
                local=walk['offset']+2*walk['frames_per_direction'] if walk else 0
                frame=frameby[md['starting_frame']+local];path=frame['path']
                if path not in pages:pages[path]=Image.open(shared/path).convert('RGBA')
                x,y,w,h=frame['region'];pic=pages[path].crop((x,y,x+w,y+h));bbox=pic.getbbox()
                if bbox:pic=pic.crop(bbox)
                scale=min(3,80/max(pic.size));pic=pic.resize((max(1,int(pic.width*scale)),max(1,int(pic.height*scale))),Image.Resampling.NEAREST)
                xx=(n%10)*100;yy=(n//10)*108;im.paste(pic,(xx+(100-pic.width)//2,yy+8),pic)
                draw.text((xx+5,yy+90),a['id'].split('.')[-1]+':'+family,fill='white')
            im.save(contact/f'{family}-{start//100:02d}.png')
    print(json.dumps(load(out/'start.json'),ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--shared',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True)
    a=p.parse_args();inspect(a.shared,a.inputs)
