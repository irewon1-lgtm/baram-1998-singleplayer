"""Restore an exact private frozen generation into a new isolated directory."""
import argparse, hashlib, json, pathlib, stat, zipfile

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def restore(archive,expected,dest):
    if len(expected)!=64 or sha(archive)!=expected:raise ValueError('Pinned ZIP SHA mismatch')
    if dest.exists():raise ValueError('Destination already exists; preserve prior input generation')
    with zipfile.ZipFile(archive) as z:
        names=set(); total=0
        for info in z.infolist():
            p=pathlib.PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or info.filename in names or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe member')
            names.add(info.filename);total+=info.file_size
        if not names or len(names)>10000 or total>100*1024*1024:raise ValueError('Unexpected runtime package size')
        m=json.loads(z.read('runtime.json'))
        if m.get('schema')!='baram.work.p2.runtime/1' or not m.get('files'):raise ValueError('Empty/unknown manifest')
        declared={x['path'] for x in m['files']}|{'runtime.json'}
        if names!=declared:raise ValueError('Undeclared or missing archive member')
        for entry in m['files']:
            data=z.read(entry['path'])
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Member identity mismatch')
        dest.mkdir(parents=True,mode=0o700)
        z.extractall(dest)
    return {'status':'PASS_RESTORED_BYTES','generation':m['generation'],'files':len(names),'runtime_manifest_sha256':sha(dest/'runtime.json'),'execution':'NOT_RUN_BY_RESTORER'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--zip',required=True,type=pathlib.Path);p.add_argument('--sha256',required=True);p.add_argument('--destination',required=True,type=pathlib.Path);a=p.parse_args()
    print(json.dumps(restore(a.zip,a.sha256,a.destination)))
