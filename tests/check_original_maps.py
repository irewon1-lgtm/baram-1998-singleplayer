#!/usr/bin/env python3
"""Check new source-map decoding against actual pinned source bytes and bad inputs."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from legacy_assets import Epf, dat_entries, read_palettes
from legacy_maps import tile_table, static_objects, map_cells, ground_id


def run(a):
    raw=Path(a.dat).read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
    entries=dat_entries(raw);tables={};results=[]
    def check(name,fn):
        try:fn();results.append(dict(name=name,status='PASS'))
        except (AssertionError,ValueError,struct.error) as e:results.append(dict(name=name,status='FAIL',error=str(e)))
    def reject(fn):
        try:fn()
        except ValueError:return
        raise AssertionError('Malformed input was accepted')
    for group in 'ABC':
        e=Epf(entries[f'tile{group.lower()}.epf'][2]);p=read_palettes(entries[f'tile{group.lower()}.pal'][2])
        tables[group]=tile_table(entries[f'tile{group.lower()}.tbl'][2],e.count,len(p))
    objects=static_objects(entries['sobj.tbl'][2],16409)
    def bases():
        assert tables['A'].base==1 and tables['B'].base==49152
        assert ground_id(1,tables)=='KR491/A:0' and ground_id(49152,tables)=='KR491/B:0'
        assert ground_id(49153,tables)=='KR491/B:1' and ground_id(0,tables)==''
    check('actual_table_bases_select_different_sheets_without_masking',bases)
    check('null_object_has_no_collision_despite_header_flag',lambda:exec('assert objects[0]["collision"]==0 and objects[0]["frames"]==[]',{'objects':objects}))
    check('actual_object_one_is_column_95_86_74',lambda:exec('assert objects[1]["frames"]==[95,86,74]',{'objects':objects}))
    check('maximum_one_based_tilec_word_stays_in_bounds',lambda:exec('assert max(w for o in objects for w in o["raw_frame_words"])==16409',{'objects':objects}))
    town=Path(a.map).read_bytes()
    def first_cell():
        c=map_cells(town,220,220,tables,objects)
        assert len(c)==48400 and c[0]['tile']=='KR491/A:42' and c[0]['collision']==0
    check('actual_city_byte_count_and_first_cell',first_cell)
    check('wrong_dimensions_rejected',lambda:reject(lambda:map_cells(town,221,220,tables,objects)))
    check('truncated_map_rejected',lambda:reject(lambda:map_cells(town[:-1],220,220,tables,objects)))
    check('out_of_range_ground_rejected',lambda:reject(lambda:map_cells(struct.pack('<HH',40000,0),1,1,tables,objects)))
    check('out_of_range_static_object_rejected',lambda:reject(lambda:map_cells(struct.pack('<HH',1,65535),1,1,tables,objects)))
    check('missing_palette_rejected',lambda:reject(lambda:tile_table(entries['tilea.tbl'][2],9922,1)))
    check('truncated_object_table_rejected',lambda:reject(lambda:static_objects(entries['sobj.tbl'][2][:-4],16409)))
    report=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',
                scope='SOURCE_FORMAT_AND_BOUNDS_NOT_LIVE_CLIENT_EQUIVALENCE',checks=results,
                source_sha256=hashlib.sha256(raw).hexdigest(),map_sha256=hashlib.sha256(town).hexdigest())
    Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(report['status'],len(results))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['dat','map','report']:p.add_argument('--'+key,required=True)
    raise SystemExit(run(p.parse_args()))
