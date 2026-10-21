import argparse,json,os,signal,subprocess,time
from pathlib import Path
from environment import ROOT,load_environment
p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--products',type=Path,required=True);a=p.parse_args();e=load_environment();out=ROOT/'evidence/r25/crash'/a.attempt;out.mkdir(parents=True,exist_ok=False)
env=e.process()|{'P1998_PROBE_PRODUCTS':str(a.products.resolve()),'P1998_PROBE_RESULTS_ROOT':str(out)}
tag='compiled';code=subprocess.run(['python3',str(ROOT/'verification/r24/run_console.py'),tag,str(ROOT/'verification/r25/CrashProbe.cs'),'seed'],env=env,stdout=(out/'compile-driver.log').open('w'),stderr=subprocess.STDOUT).returncode
assert code==0,'Crash probe compile/seed failed'
dll=out/tag/'project/bin/Release/net9.0/Tests.dll';rows=[]
for mode in ['before','after']:
 state=out/mode;result=out/(mode+'.json');marker=out/(mode+'.marker')
 base=[str(e.dotnet),str(dll),str(ROOT/'candidate/game-data'),str(state),str(result)]
 assert subprocess.run(base+['seed'],env=env,stdout=subprocess.DEVNULL).returncode==0
 with(out/(mode+'.log')).open('w')as f:
  child=subprocess.Popen(base+[mode,str(marker)],env=env,stdout=f,stderr=subprocess.STDOUT)
  deadline=time.monotonic()+30
  while not marker.exists() and child.poll()is None and time.monotonic()<deadline:time.sleep(.05)
  assert marker.exists(),'No real transaction checkpoint'
  child.kill();child.wait(timeout=10)
 assert subprocess.run(base+['verify_'+mode],env=env,stdout=subprocess.DEVNULL).returncode==0
 rows.append(json.loads(result.read_text()))
(out/'RESULT.json').write_text(json.dumps({'status':'PASS','scenarios':rows,'physical_android':'NOT_RUN'},indent=2));print(json.dumps({'status':'PASS','scenarios':len(rows)}))
