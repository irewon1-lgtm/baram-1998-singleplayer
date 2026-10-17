#!/usr/bin/env python3
"""Lossless runtime collision packing. Original geometry is retained separately.

This does not render, decode or regenerate source maps. Every cell is compared
before emitting the small production definition file. World/content IDs and
save compatibility pins remain identical because no gameplay rule changes.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Fresh output required')
    shutil.copytree(a.source,a.output)
    content=a.output/'gameplay_content.json';data=json.loads(content.read_text())
    checks=[]
    for mid,m in data['maps'].items():
        size=m['width']*m['height'];blocked=bytearray(size)
        for x,y in m['blocked']:blocked[y*m['width']+x]=1
        edges=bytes(m.get('edge_masks',[]))
        assert not edges or len(edges)==size
        original={k:m.pop(k)for k in ('ground_ids','edge_masks','blocked')if k in m}
        original['objects']=m.get('objects',[])
        m['objects']=[{k:o[k]for k in ('path','frame_png','x','y','depth_y','width_px','height_px')if k in o}for o in original['objects']]
        for o in m['objects']:
            if 'path'not in o:o['path']=o['frame_png']
            o.pop('frame_png',None)
        path='gameplay/geometry/'+hashlib.sha256(mid.encode()).hexdigest()[:24]+'.json'
        write(a.output/path,{'map_id':mid,'width':m['width'],'height':m['height'],**original})
        m['geometry_file']=path;m['blocked_base64']=base64.b64encode(blocked).decode()
        if edges:m['edge_masks_base64']=base64.b64encode(edges).decode()
        decoded=base64.b64decode(m['blocked_base64']);decoded_edges=base64.b64decode(m.get('edge_masks_base64',''))
        assert decoded==blocked and decoded_edges==edges
        assert {(n%m['width'],n//m['width'])for n,b in enumerate(decoded)if b}=={tuple(p)for p in original['blocked']}
        checks.append({'map_id':mid,'cells':size,'blocked':sum(blocked),'status':'PASS'})
    write(content,data)
    write(a.output/'G2_COLLISION_PACKING.json',{'schema':'baram.g2.collision-packing/1','status':'PASS_LOSSLESS_CELL_COMPARISON','source_definition_sha256':hashlib.sha256((a.source/'gameplay_content.json').read_bytes()).hexdigest(),'source_definition_bytes':(a.source/'gameplay_content.json').stat().st_size,'packed_definition_bytes':content.stat().st_size,'maps':checks,'policy':'Only memory representation changed. Original geometry and source-native layout evidence retained in geometry_file; save compatibility and rules unchanged.'})
    manifest=json.loads((a.output/'runtime.json').read_text());paths=[]
    for f in sorted(a.output.rglob('*')):
        if f.is_file()and f.name!='runtime.json':paths.append({'path':f.relative_to(a.output).as_posix(),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
    manifest['files']=paths;manifest['input_definitions_sha256']=hashlib.sha256(content.read_bytes()).hexdigest()
    manifest['fingerprint']=hashlib.sha256(json.dumps(paths,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    write(a.output/'runtime.json',manifest)
    print(json.dumps({'status':'PASS_LOSSLESS_CELL_COMPARISON','maps':len(checks),'definition_before':(a.source/'gameplay_content.json').stat().st_size,'definition_after':content.stat().st_size,'runtime_sha256':hashlib.sha256((a.output/'runtime.json').read_bytes()).hexdigest()}))


if __name__=='__main__':main()
