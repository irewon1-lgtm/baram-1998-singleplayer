#!/usr/bin/env python3
"""Run retained evidence analysis and bind the actual inputs/tool/output."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def fingerprint(path):
    return {'file':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} if path.exists() else {'file':str(path),'status':'ABSENT'}


def find_host_environment(root):
    for parent in root.parents:
        candidate=parent/'HOST_ENVIRONMENT.json'
        if candidate.is_file():return candidate
    return root/'HOST_ENVIRONMENT.json'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    parser.add_argument('--analyzer',type=Path,default=Path(__file__).with_name('analyze_playability.py'))
    args=parser.parse_args();root=args.directory.resolve();analyzer=args.analyzer.resolve()
    paths=[root/name for name in ['OS_PLAYABILITY.json','journey-frame-timeline.jsonl','restart-frame-timeline.jsonl','os-input-timeline.jsonl','external-rss.jsonl']]
    paths.append(find_host_environment(root))
    result=json.loads((root/'OS_PLAYABILITY.json').read_text())
    if not result.get('final') and not result.get('before_restart'):paths.extend(sorted(root.glob('data/*/gameplay-p3/characters/*.json')))
    before=[fingerprint(path) for path in paths];tool_before=fingerprint(analyzer)
    (root/'analyzer-source.py').write_bytes(analyzer.read_bytes())
    command=[sys.executable,str(analyzer),str(args.directory)];started=time.time_ns()
    process=subprocess.run(command,capture_output=True,text=True)
    ended=time.time_ns();after=[fingerprint(path) for path in paths]
    (root/'ANALYZER.stdout.log').write_text(process.stdout);(root/'ANALYZER.stderr.log').write_text(process.stderr)
    receipt={'schema':'baram.playability-analysis-execution/1','command':command,'cwd':str(Path.cwd()),
             'started_unix_ns':started,'ended_unix_ns':ended,'exit_code':process.returncode,
             'analyzer_before':tool_before,'analyzer_after':fingerprint(analyzer),
             'analyzer_snapshot':fingerprint(root/'analyzer-source.py'),'wrapper':fingerprint(Path(__file__).resolve()),
             'inputs_before':before,'inputs_after':after,'input_files_unchanged':before==after,
             'output':fingerprint(root/'FINAL_ANALYSIS.json')}
    (root/'ANALYZER_RUN.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(process.stdout,end='');print(process.stderr,end='',file=sys.stderr)
    return process.returncode if process.returncode else 0 if before==after and tool_before==receipt['analyzer_after'] else 1


if __name__=='__main__':raise SystemExit(main())
