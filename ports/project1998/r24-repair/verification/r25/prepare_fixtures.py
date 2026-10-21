"""Generate isolated synthetic accounts by normal creation APIs, never recovered credentials."""
import argparse,json,os,subprocess
from pathlib import Path
from environment import ROOT,load_environment,validate
p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--toolchain');p.add_argument('--products',type=Path,required=True);a=p.parse_args()
e=load_environment(a.toolchain);out=ROOT/'evidence/r25/fixtures';out.mkdir(parents=True,exist_ok=True)
env=e.process()|{'P1998_PROBE_PRODUCTS':str(a.products.resolve()),'P1998_PROBE_RESULTS_ROOT':str(out)}
code=subprocess.run(['python3',str(ROOT/'verification/r24/run_console.py'),a.attempt,str(ROOT/'verification/r25/FixtureProbe.cs')],env=env,cwd=ROOT).returncode
(out/a.attempt/'ENVIRONMENT.json').write_text(json.dumps(validate(e),indent=2))
raise SystemExit(code)
