#!/usr/bin/env python3
"""Fetch researched originals to an external private folder; verify pinned SHA256, never execute."""
import argparse, hashlib, json, pathlib, urllib.request

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=pathlib.Path,required=True)
    parser.add_argument('--destination',type=pathlib.Path,required=True)
    args=parser.parse_args(); destination=args.destination.resolve()
    repository=pathlib.Path(__file__).resolve().parents[1]
    if destination==repository or repository in destination.parents:
        parser.error('destination must be outside this public repository')
    destination.mkdir(parents=True,exist_ok=True);results=[]
    for record in json.loads(args.manifest.read_text()):
        filename=record['filename']
        if pathlib.Path(filename).name!=filename:
            raise ValueError('unsafe filename')
        target=destination/filename;expected=record['sha256'];row={'filename':filename,'expected_sha256':expected,'status':'FAILED'}
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()==expected:
                row['status']='PASS_EXISTING_BYTES_HASH_ONLY';results.append(row);continue
            row['error']='existing file hash mismatch; retained';results.append(row);continue
        for url in record['urls']:
            temporary=destination/(filename+'.partial')
            try:
                digest=hashlib.sha256()
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as response, temporary.open('wb') as output:
                    while block:=response.read(1024*1024):digest.update(block);output.write(block)
                row.update(url=url,actual_sha256=digest.hexdigest())
                if digest.hexdigest()!=expected:
                    row['error']='hash mismatch; partial retained';continue
                temporary.replace(target);row['status']='PASS_DOWNLOAD_HASH_ONLY';break
            except Exception as error:row['error']=str(error)
        results.append(row)
    report=destination/'refetch-results.json';report.write_text(json.dumps(results,indent=2));print(report)
    return int(any(row['status']=='FAILED' for row in results))

if __name__=='__main__':raise SystemExit(main())
