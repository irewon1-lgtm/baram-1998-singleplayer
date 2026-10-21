"""Uncontended ABBA host comparison: same closed seed, same source harness, fresh process per sample."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'verification/r25'))
from environment import load_environment
p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--seed',type=Path,required=True);a=p.parse_args();e=load_environment()
out=R/'evidence/r26/growth-pair'/a.attempt;out.mkdir(parents=True,exist_ok=False);rows=[]
seed=a.seed.resolve();fingerprint={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in seed.glob('project1998.db*')}
for i,kind in enumerate(['before','after','after','before']):
 dest=out/(str(i)+'-'+kind);dest.mkdir();shutil.copytree(seed,dest/'state');probe=getattr(a,kind).resolve()
 with(dest/'run.log').open('w')as log:
  code=subprocess.run([str(e.dotnet),str(probe),str(R/'candidate/game-data'),str(dest/'state'),str(dest/'RESULT.json'),'measure','128','70'],env=e.process(),stdout=log,stderr=subprocess.STDOUT).returncode
 result=json.loads((dest/'RESULT.json').read_text())if(dest/'RESULT.json').exists()else{}
 row={'order':i,'kind':kind,'exit':code,'cold_ms':result.get('cold_open_ms'),'p95_ms':result.get('input',{}).get('p95_ms'),'median_ms':result.get('input',{}).get('median_ms'),'cpu_ms':result.get('input',{}).get('actions_cpu_ms'),'allocation_per_action':result.get('input',{}).get('allocated_per_action')};rows.append(row);print(json.dumps(row),flush=True)
final={'status':'PASS_SCOPED_HOST_COMPARISON'if all(r['exit']==0 for r in rows)else'FAIL','rows':rows,'seed_hashes':fingerprint,'seed_bytes_unchanged':fingerprint=={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in seed.glob('project1998.db*')},'physical_android':'NOT_RUN','thermal':'NOT_RUN'}
(out/'RESULT.json').write_text(json.dumps(final,indent=2));raise SystemExit(0 if all(r['exit']==0 for r in rows)else 1)
