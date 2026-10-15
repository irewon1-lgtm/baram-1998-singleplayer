#!/usr/bin/env python3
"""Release a validated ZIP to an authenticated private GitHub vault only."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import zipfile
from windows_ci import sha256

def gh(*args,optional=False):
    r=subprocess.run(['gh',*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if r.returncode and not optional:raise RuntimeError('Private GitHub operation failed')
    return r

def publish(args):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo):raise ValueError('Invalid private vault name')
    repo=json.loads(gh('api','repos/'+args.repo).stdout)
    if repo.get('private') is not True:raise ValueError('Private delivery destination required')
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if args.diagnostics_only:
        import os
        tag='diagnostics-'+os.environ.get('GITHUB_RUN_ID','local')+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
        asset=out/'private-diagnostics.zip'
        with zipfile.ZipFile(asset,'x',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob('*')):
                if p.is_file() and (p.suffix=='.log' or p.name.endswith('-report.json') or p.name=='verification.json'):
                    z.write(p,p.relative_to(out).as_posix())
        notes='Execution failed. Player ZIP publication was blocked. These diagnostics remain private.'
        # Keep text diagnostics directly readable through the private repository
        # API, including when this browser cannot download a draft release asset.
        logs={p.relative_to(out).as_posix():p.read_text(encoding='utf-8',errors='replace')
              for p in sorted(out.rglob('*')) if p.is_file() and
              (p.suffix=='.log' or p.name.endswith('-report.json') or p.name=='verification.json')}
        payload=json.dumps({'status':'FAILED_DELIVERY_BLOCKED','logs':logs},ensure_ascii=False).encode('utf-8')
        request=out/'private-diagnostic-request.json'
        request.write_text(json.dumps({'message':'Preserve private Windows failure diagnostics',
            'content':base64.b64encode(payload).decode('ascii')}),encoding='utf-8')
        gh('api','--method','PUT','repos/'+args.repo+'/contents/diagnostics/'+tag+'.json','--input',str(request))
    else:
        delivery=json.loads((out/'delivery.json').read_text())
        checks=delivery['verification']
        if checks.get('status')!='PASS' or checks.get('windows_native_execution')!='PASS' or checks.get('windows_windowed_startup')!='PASS' or checks.get('windows_message_pump')!='PASS' or checks.get('game_function_automation')!='PASS':
            raise ValueError('Native verification gate failed')
        asset=Path(delivery['file'])
        if asset.stat().st_size!=delivery['bytes'] or sha256(asset)!=delivery['sha256']:raise ValueError('Player ZIP changed')
        with zipfile.ZipFile(asset) as z:
            if z.testzip():raise ValueError('ZIP CRC failure')
        tag='win-'+checks['source_sha'][:12]+'-'+delivery['sha256'][:8]
        notes=f"Source: {checks['source_sha']}\nWindows-native normal window/rendered startup frame: PASS\nWindows-native automated input/save/restart: PASS\nOperator GUI/audio: BLOCKED / not observed\nZIP SHA256: {delivery['sha256']}\n"
    if gh('release','view',tag,'--repo',args.repo,optional=True).returncode==0:raise ValueError('Preserve existing version; release already exists')
    note_path=out/'release-notes.txt';note_path.write_text(notes,encoding='utf-8')
    gh('release','create',tag,'--repo',args.repo,'--draft','--title',tag,'--notes-file',str(note_path))
    gh('release','upload',tag,str(asset),'--repo',args.repo)
    if not args.diagnostics_only:
        evidence=out/'verification-evidence.zip'
        with zipfile.ZipFile(evidence,'x',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob('*')):
                if p.is_file() and (p.suffix=='.log' or p.name.endswith('-report.json') or p.name=='verification.json' or p.name=='windows-startup-frame.png'):
                    z.write(p,p.relative_to(out).as_posix())
        gh('release','upload',tag,str(evidence),'--repo',args.repo)
    if not args.diagnostics_only:gh('release','edit',tag,'--repo',args.repo,'--draft=false')
    print('PRIVATE_DELIVERY https://github.com/'+args.repo+'/releases/tag/'+tag)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True);p.add_argument('--diagnostics-only',action='store_true')
    publish(p.parse_args())
