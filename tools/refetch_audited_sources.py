#!/usr/bin/env python3
"""Restore audited commits outside the public checkout; no code execution."""
import argparse, json, subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dest',required=True);ap.add_argument('--all-audited',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];dest=Path(args.dest).resolve()
    if dest==root or root in dest.parents:ap.error('Destination must be outside the public repository')
    report=json.loads((root/'research/community-audit/repository-audit.json').read_text())
    original={x['name'] for x in json.loads((root/'research/community_sources_20261013.json').read_text())['repositories']}
    for r in report['repositories']:
        if not args.all_audited and r['name'] not in original:continue
        target=dest/r['name'];target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            actual=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
            if actual!=r['commit']:raise SystemExit('Existing checkout SHA mismatch: '+r['name'])
        else:
            subprocess.run(['git','clone','--no-checkout',r['url'],str(target)],check=True,timeout=300)
            subprocess.run(['git','-C',str(target),'checkout','--detach',r['commit']],check=True,timeout=60)
        print(r['name'],r['commit'])

if __name__=='__main__':main()
