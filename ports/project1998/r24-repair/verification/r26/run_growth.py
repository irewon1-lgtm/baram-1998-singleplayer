"""Before/after comparisons use byte-identical synthetic seeds and one fresh process per case."""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / 'verification/r25'))
from environment import load_environment
p = argparse.ArgumentParser(); p.add_argument('attempt'); p.add_argument('--products', type=Path, required=True)
p.add_argument('--seeds', type=Path); a = p.parse_args(); e = load_environment()
out = R / 'evidence/r26/growth' / a.attempt; out.mkdir(parents=True, exist_ok=False)
env = e.process() | {'P1998_PROBE_PRODUCTS': str(a.products.resolve()), 'P1998_PROBE_RESULTS_ROOT': str(out)}
source = R / 'verification/r26/CumulativePerformanceProbe.cs'
code = subprocess.run(['python3', str(R/'verification/r24/run_console.py'), 'compile-and-seed', str(source), 'prepare', '0', '1'], env=env, stdout=(out/'compile-seed.log').open('w'), stderr=subprocess.STDOUT).returncode
if code: raise SystemExit(code)
dll = out/'compile-and-seed/project/bin/Release/net9.0/Tests.dll'
seed_root = a.seeds.resolve() if a.seeds else out/'seeds'
rows = []
for history, level in [(0, 1), (0, 70), (32, 70), (128, 70)]:
    name = f'history{history}-level{level}'; dest = out/name; dest.mkdir()
    seed = seed_root/name
    if not a.seeds:
        seed.mkdir(parents=True)
        with (dest/'prepare.log').open('w') as log:
            code = subprocess.run([str(e.dotnet),str(dll),str(R/'candidate/game-data'),str(seed/'state'),str(seed/'RESULT.json'),'prepare',str(history),str(level)],env=env,stdout=log,stderr=subprocess.STDOUT).returncode
        if code: raise RuntimeError(f'prepare {name} failed: {code}')
    shutil.copytree(seed/'state', dest/'state')
    initial_hash = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (dest/'state').glob('project1998.db*')} 
    with (dest/'run.log').open('w') as log:
        code = subprocess.run([str(e.dotnet),str(dll),str(R/'candidate/game-data'),str(dest/'state'),str(dest/'RESULT.json'),'measure',str(history),str(level)],env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    result = json.loads((dest/'RESULT.json').read_text()) if (dest/'RESULT.json').exists() else {}
    row = dict(case=name,exit=code,status=result.get('status','FAIL_NO_RESULT'),initial_database_sha256=initial_hash,
               cold_ms=result.get('cold_open_ms'),input=result.get('input',{}).get('p95_ms'),world=result.get('world'))
    rows.append(row); print(json.dumps(row),flush=True)
    (out/'PROGRESS.json').write_text(json.dumps(rows,indent=2))
report = dict(status='PASS_SCOPED_HOST' if all(x['exit']==0 for x in rows) else 'FAIL',rows=rows,
    products=str(a.products),seeds=str(seed_root),physical_android='NOT_RUN',heat='NOT_RUN',
    product_hashes=json.loads((out/'compile-and-seed/RUN.json').read_text())['products'])
(out/'RESULT.json').write_text(json.dumps(report,indent=2)); raise SystemExit(0 if all(x['exit']==0 for x in rows) else 1)
