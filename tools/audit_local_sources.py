#!/usr/bin/env python3
"""Metadata-only audit. Never copies external file contents into the output."""
import argparse, collections, csv, hashlib, json, subprocess
from pathlib import Path
from datetime import datetime, timezone

def git(p, *args):
    return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()

def main():
    a=argparse.ArgumentParser(); a.add_argument('--root',action='append',required=True); a.add_argument('--out',required=True)
    args=a.parse_args(); out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    repos=[]; all_files=[]; contents=collections.defaultdict(list)
    for root in args.root:
        for gd in sorted(Path(root).rglob('.git')):
            p=gd.parent
            try: sha=git(p,'rev-parse','HEAD'); names=git(p,'ls-files','-z').split('\0');url=git(p,'remote','get-url','origin')
            except subprocess.CalledProcessError: continue
            name=url.removesuffix('.git').split('github.com/')[-1]
            if any(x['name']==name for x in repos):continue
            files=[]; license_files=[]
            for n in names:
                if not n:continue
                f=p/n
                if not f.is_file():continue
                data=f.read_bytes(); ext=f.suffix.lower(); digest=hashlib.sha256(data).hexdigest()
                row={'repository':name,'path':n,'bytes':len(data),'sha256':digest,'extension':ext}
                if ext=='.csv':
                    try:
                        rows=list(csv.reader(data.decode('utf-8-sig').splitlines()));row['csv_raw_records_after_first']=max(0,len(rows)-1);row['columns']=rows[0] if rows else []
                    except (UnicodeError,csv.Error):row['csv_parse']='FAIL'
                files.append(row);contents[digest].append(name+':'+n)
                if f.name.lower() in ('license','license.md','license.txt','copying','copying.md','copying.txt') and 'node_modules/' not in n:license_files.append(n)
            count=collections.Counter(x['extension'] for x in files)
            repos.append({'name':name,'url':url,'commit':sha,'local_path':str(p.resolve()),'collection':'git clone --depth=1','clone_status':'PASS','file_inspection':'PASS','build_status':'NOT_RUN','play_status':'NOT_RUN','tracked_files':len(files),'extensions':dict(count),'license_files':license_files})
            all_files.extend(files)
    report={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Tracked file bytes read and SHA256 calculated; CSV rows are raw parsed rows, not runtime-loaded entities. Extension counts include tooling/dependencies; no year/authenticity or gameplay PASS implied.','repositories':repos}
    (out/'repository-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (out/'file-inventory.json').write_text(json.dumps(all_files,ensure_ascii=False,indent=2)+'\n')
    cross=[{'sha256':h,'paths':v} for h,v in contents.items() if len({x.split(':')[0] for x in v})>1]
    (out/'cross-repository-duplicates.json').write_text(json.dumps(cross,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'repo':r['name'],'sha':r['commit'],'files':r['tracked_files'],'licenses':r['license_files']} for r in repos],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
