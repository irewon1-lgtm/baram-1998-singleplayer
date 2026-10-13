#!/usr/bin/env python3
"""Recover pinned references outside the public repository; publish metadata only."""
import argparse, concurrent.futures, datetime, hashlib, json, subprocess, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/restoration-integrated-20261013'

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def download(task, destination):
    started = time.monotonic()
    record = {k:v for k,v in task.items() if k != 'cached'}
    record['started_at'] = now()
    path = destination / task['relative_path']
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == task['expected_sha256']:
            record.update(status='PASS_REUSED_LOCAL_BYTES', actual_sha256=task['expected_sha256'], bytes=path.stat().st_size)
        else:
            req = urllib.request.Request(task['url'], headers={'User-Agent':'Historical-data-research/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                digest = hashlib.sha256()
                with path.open('wb') as output:
                    while True:
                        chunk = response.read(1024*1024)
                        if not chunk: break
                        output.write(chunk); digest.update(chunk)
                actual = digest.hexdigest()
                record.update(http_status=response.status, final_url=response.url, actual_sha256=actual, bytes=path.stat().st_size,
                              status='PASS_BYTES_HASH_MATCH' if actual == task['expected_sha256'] else 'FAIL_HASH_MISMATCH')
    except Exception as exc:
        record.update(status='BLOCKED', error=type(exc).__name__+': '+str(exc))
    record.update(seconds=round(time.monotonic()-started,3), local_path=str(path))
    return record

def checkout(task, destination):
    started = time.monotonic(); path=destination/'repos'/task['name']
    path.parent.mkdir(parents=True,exist_ok=True)
    record=dict(task, started_at=now(), local_path=str(path))
    try:
        if not (path/'.git').exists():
            subprocess.run(['git','clone','--filter=blob:none','--no-checkout',task['url'],str(path)],check=True, capture_output=True, timeout=180)
        subprocess.run(['git','-C',str(path),'checkout','--detach',task['commit']],check=True,capture_output=True,timeout=180)
        head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        fsck=subprocess.run(['git','-C',str(path),'fsck','--no-reflogs'],capture_output=True,text=True,timeout=90)
        record.update(status='PASS_PINNED_CHECKOUT' if head==task['commit'] and fsck.returncode==0 else 'FAIL',actual_commit=head,fsck_exit=fsck.returncode,fsck_diagnostic=fsck.stderr[-800:])
    except Exception as exc:
        record.update(status='BLOCKED',error=type(exc).__name__+': '+str(exc))
    record['seconds']=round(time.monotonic()-started,3)
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private-dir',required=True);args=parser.parse_args()
    destination=Path(args.private_dir).resolve()
    if destination==ROOT or ROOT in destination.parents: parser.error('private-dir must be outside the public repository')
    sources=json.loads((ROOT/'research/korean-history-20261013/sources.json').read_text())
    candidates=[json.loads(line) for line in (ROOT/'research/korean-history-20261013/extracted-candidates.jsonl').read_text().splitlines()]
    ids={row['source_id'] for row in candidates};tasks=[]
    for src in sources:
        if src['id'] in ids:
            tasks.append(dict(kind='KR_CANDIDATE_SOURCE',id=src['id'],url=src.get('final_url') or src['requested_url'],expected_sha256=src['sha256'],relative_path='kr-html/'+src['id']+'.html'))
    # Recover every archive already registered by the previous world audit.
    for src in json.loads((ROOT/'research/world-audit/acquired-original-files.json').read_text()):
        tasks.append(dict(kind='ORIGINAL_ARCHIVE',id=src['filename'],url=src['urls'][0],expected_sha256=src['sha256'],relative_path='archives/'+src['filename']))
    wanted={'project1998/Project1998','mun5424/Baram_Legacy','unkmc/RTK-Server','DizzyThermal/EPFViewer','DizzyThermal/TKMapper','Essorcal/project1998-docs'}
    repo_tasks=[r for r in json.loads((ROOT/'research/community-audit/repository-audit.json').read_text())['repositories'] if r['name'] in wanted]
    repo_tasks.append(dict(name='bosbabi168-cpu/RTK-java-version',url='https://github.com/bosbabi168-cpu/RTK-java-version.git',commit='fec7b36bae0b18471391d652d35a96793cf0be5a',root_license='NOT_VERIFIED',reuse_decision='REFERENCE_ONLY'))
    records=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(download,t,destination) for t in tasks]+[pool.submit(checkout,t,destination) for t in repo_tasks]
        for future in concurrent.futures.as_completed(futures):
            record=future.result();records.append(record)
            (OUT/'INPUT_RECOVERY.json').write_text(json.dumps(dict(executed_at=now(),command='python tools/recover_restoration_inputs.py --private-dir '+str(destination),records=records),ensure_ascii=False,indent=2)+'\n')
            print(record.get('id',record.get('name')),record['status'],flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
