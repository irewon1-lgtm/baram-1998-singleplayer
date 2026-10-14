#!/usr/bin/env python3
"""Reproduce declared Work layout members; never author or edit Work content.

The serialization follows the reviewed frozen Work map_make converter. Every
source map and output member must match the published SHA before intake.
"""
import argparse,json
from pathlib import Path
from legacy_assets import dat_entries,Epf,read_palettes
from legacy_maps import tile_table,static_objects,map_cells
from baram_content import sha,encode,atomic_write,safe_relative
KR='f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'

def run(a):
    package=Path(a.package);output=Path(a.output);dat=Path(a.dat).read_bytes()
    if sha(dat)!=KR:raise ValueError('Original DAT differs from Work pin')
    entries=dat_entries(dat);tables={}
    for group in 'ABC':
        key='tile'+group.lower();epf=Epf(entries[key+'.epf'][2]);pals=read_palettes(entries[key+'.pal'][2])
        tables[group]=tile_table(entries[key+'.tbl'][2],epf.count,len(pals))
    objects=static_objects(entries['sobj.tbl'][2],tables['C'].count)
    acquisition=json.loads((package/'acquisition.json').read_text());shared=acquisition['shared_format_dependency']
    records=[json.loads(line) for f in sorted(package.glob('content-*.jsonl')) for line in f.read_text().splitlines()]
    verified=[];errors=[];members={}
    for record in records:
        if record['kind']!='map' or record['operation']!='add':continue
        data=record['data'];pin=data['layout_acquisition'];source=int(pin['source_original_map_id'])
        raw=(Path(a.maps)/('TK'+str(source)+'.map')).read_bytes()
        if sha(raw)!=pin['source_sha256']:raise ValueError('Source map pin differs: '+str(source))
        cells=map_cells(raw,data['width'],data['height'],tables,objects)
        layout=dict(width=data['width'],height=data['height'],tile_size_px=24,
                    layers=dict(ground=[c['ground_word'] for c in cells],objects=[c['object_id'] for c in cells]),
                    collision_masks=[c['collision'] for c in cells],objects_member=shared['member'],
                    objects_acquisition={k:shared[k] for k in ['bundle_id','member','sha256']},
                    source_map_sha256=sha(raw),source_map_id=source,source_dat_sha256=KR,
                    coordinate_system='TOP_LEFT_X_RIGHT_Y_DOWN_ZERO_BASED',raw_ground_words_with_TBL_bases=True)
        raw_layout=(json.dumps(layout,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
        actual=sha(raw_layout)
        if actual!=pin['sha256']:errors.append(dict(id=record['id'],member=pin['member'],actual=actual,expected=pin['sha256']));continue
        atomic_write(output/str(safe_relative(pin['member'])),raw_layout);verified.append(record['id']);members[pin['member']]=actual
    report=dict(protocol_id='BARAM_PARALLEL_V1',batch_id=json.loads((package/'manifest.json').read_text())['batch_id'],
                acquisition_method='DECLARED_LAYOUT_REBUILD_FROM_EXISTING_HASH_PINNED_MAP_BYTES',
                verified_ids=verified,errors=errors,verified_member_sha256=members,directory=str(output),
                whole_private_zip_acquired=False,scope='ACQUISITION_NOT_CONTENT_AUTHORING_OR_GAMEPLAY')
    atomic_write(a.report,encode(report));print('Verified original-layout members',len(verified),'failures',len(errors))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['package','output','dat','maps','report']:p.add_argument('--'+key,required=True)
    run(p.parse_args())
