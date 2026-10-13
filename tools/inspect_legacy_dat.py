#!/usr/bin/env python3
"""Read a legacy DAT directory without executing or redistributing game resources.

Layout cross-checked against MIT TKMapper FileHandlers/DatFileHandler.gd:
u32LE directory-slot count, repeated (u32LE offset, 13-byte filename), final offset.
This implementation is independently written; it exports names/sizes/hashes only.
"""
import argparse, collections, hashlib, json, struct
from pathlib import Path

def inspect(path):
    d=path.read_bytes();slots=struct.unpack_from('<I',d,0)[0]
    if slots<2 or slots>100000 or 4+17*(slots-1)+4>len(d):raise ValueError('Invalid directory bounds')
    rows=[]
    for i in range(slots-1):
        pos=4+17*i;start=struct.unpack_from('<I',d,pos)[0];end=struct.unpack_from('<I',d,pos+17)[0]
        name=d[pos+4:pos+17].split(b'\0',1)[0].decode('ascii',errors='replace')
        if start>end or end>len(d):raise ValueError('Invalid file bounds '+name)
        payload=d[start:end];row={'name':name,'offset':start,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
        if Path(name).suffix.lower()=='.epf':
            if len(payload)<12:row['epf_status']='EMPTY_OR_SHORT'
            else:
                frames,width,height,unknown,pixels=struct.unpack_from('<hhhhI',payload)
                row.update(epf_frames=frames,epf_width=width,epf_height=height)
                row['epf_status']='HEADER_TABLE_IN_BOUNDS' if frames>=0 and 12+pixels+frames*16<=len(payload) else 'INVALID_HEADER_TABLE'
        rows.append(row)
    return {'source':str(path),'source_sha256':hashlib.sha256(d).hexdigest(),'status':'PASS_DIRECTORY_BOUNDS_AND_HASHES_ONLY','entry_count':len(rows),'extensions':dict(collections.Counter(Path(r['name']).suffix.lower() for r in rows)),'entries':rows}

def main():
    a=argparse.ArgumentParser();a.add_argument('files',nargs='+');a.add_argument('--out',required=True);args=a.parse_args();reports=[]
    for f in args.files:
        try:r=inspect(Path(f))
        except (OSError,ValueError,struct.error) as e:r={'source':f,'status':'FAIL','error':str(e)}
        reports.append(r);print({k:v for k,v in r.items() if k!='entries'})
    Path(args.out).write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
    return int(any(r['status']=='FAIL' for r in reports))

if __name__=='__main__':raise SystemExit(main())
