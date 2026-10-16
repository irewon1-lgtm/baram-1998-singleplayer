#!/usr/bin/env python3
"""Restore the larger isolated map inspection generation with two exact hash pins.

The legacy GEN003 restorer's100MiB budget remains unchanged. This new scope has
250storage chunks and an explicit192MiB uncompressed cap; no arbitrary archives.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

def digest(data): return hashlib.sha256(data).hexdigest()

def restore(a):
    if not all(re.fullmatch('[0-9a-f]{64}',s) for s in [a.sha256,a.manifest_sha256]):raise ValueError('Two exact SHA pins required')
    if digest(a.zip.read_bytes()) != a.sha256:raise ValueError('Archive hash mismatch')
    if a.destination.exists():raise ValueError('Existing destination preserved')
    with zipfile.ZipFile(a.zip) as z:
        members=z.infolist();names=[i.filename for i in members]
        if len(names)!=4237 or len(set(names))!=len(names) or sum(i.file_size for i in members)>192*1024*1024:
            raise ValueError('Unexpected priority generation budget')
        for info in members:
            p=PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe member')
        raw=z.read('runtime.json')
        if digest(raw)!=a.manifest_sha256:raise ValueError('Manifest pin mismatch')
        m=json.loads(raw)
        if m.get('schema')!='baram.work.p2.runtime/1' or m.get('generation')!='WORK-PRIORITY-GEN002':raise ValueError('Unexpected generation')
        if set(names)!={e['path'] for e in m['files']}|{'runtime.json'}:raise ValueError('Undeclared/missing member')
        for entry in m['files']:
            b=z.read(entry['path'])
            if len(b)!=entry['bytes'] or digest(b)!=entry['sha256']:raise ValueError('Member bytes mismatch: '+entry['path'])
        a.destination.mkdir(parents=True,mode=0o700)
        z.extractall(a.destination)
        for entry in m['files']:
            b=(a.destination/entry['path']).read_bytes()
            if len(b)!=entry['bytes'] or digest(b)!=entry['sha256']:raise ValueError('Restored file differs: '+entry['path'])
    receipt={'result':'PASS_EXACT_PRIORITY_BYTES','generation':m['generation'],'files':len(names),'zip_sha256':a.sha256,'manifest_sha256':a.manifest_sha256,'uncompressed_bytes':sum(i.file_size for i in members),'runtime_execution':'NOT_RUN_BY_RESTORER'}
    a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['zip','destination','receipt']:p.add_argument('--'+k,type=Path,required=True)
    for k in ['sha256','manifest-sha256']:p.add_argument('--'+k,required=True)
    restore(p.parse_args())
