"""One final batch; failures are recorded independently and never relabelled as PASS."""
import argparse,datetime,hashlib,json,os,subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'verification/r25'))
from environment import ROOT,load_environment
p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--products',type=Path,required=True);p.add_argument('--baseline-apk',type=Path,required=True);a=p.parse_args()
e=load_environment(require_godot=True);out=ROOT/'evidence/r25/suite'/a.attempt;out.mkdir(parents=True,exist_ok=False)
products=a.products.resolve();env=e.process()|{'P1998_PROBE_PRODUCTS':str(products),'P1998_BASELINE_APK':str(a.baseline_apk.resolve())}
rows=[]
def run(name,cmd,category,result=None,extra=None):
 local=env|(extra or {});started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with(out/(name+'.log')).open('w')as log:code=subprocess.run([str(c)for c in cmd],env=local,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
 actual=None
 if result and Path(result).exists():actual=json.loads(Path(result).read_text())
 row=dict(name=name,category=category,exit=code,status='PASS'if code==0 else'FAIL',started=started,finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),result=str(Path(result).relative_to(ROOT))if result else None,observed_status=actual.get('status')if actual else None)
 rows.append(row);(out/'PROGRESS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True);return code
def console(name,file,extra=None):
 tag=a.attempt+'-'+name;target=ROOT/'evidence/r25/final-runtime'/tag/'RESULT.json'
 return run(name,['python3',ROOT/'verification/r24/run_console.py',tag,ROOT/'verification/r25'/file]+(extra or []),'ACTUAL_INPUT_OR_STORAGE',target,{'P1998_PROBE_RESULTS_ROOT':str(ROOT/'evidence/r25/final-runtime')})
run('synthetic-fixture',['python3',ROOT/'verification/r25/prepare_fixtures.py',a.attempt,'--products',products],'NEW_SYNTHETIC_FIXTURE',ROOT/'evidence/r25/fixtures'/a.attempt/'RESULT.json')
fixture=ROOT/'evidence/r25/fixtures'/a.attempt/'state'
console('transactions','TransactionProbe.cs');console('ordinary-shop','TransactionProbe.cs',['ordinary-only']);console('normal-entry-route','NormalEntryProbe.cs');console('diagnostic-stress','DiagnosticsProbe.cs')
run('crash-atomicity',['python3',ROOT/'verification/r25/run_crash.py',a.attempt,'--products',products],'ACTUAL_SQLITE_PROCESS_KILL',ROOT/'evidence/r25/crash'/a.attempt/'RESULT.json')
run('existing-console-regression',['python3',ROOT/'verification/r28/run_final_console.py',a.attempt,products],'EXISTING_ID_INPUT_SAVE_REGRESSIONS',ROOT/'evidence/r24'/('console-'+a.attempt)/'RESULT.json')
run('original-xunit',[e.dotnet,'test',ROOT/'candidate/Tests/Tests.csproj','-c','Release','--no-restore','-m:1','-p:UseSharedCompilation=false','--logger','trx','--results-directory',out/'xunit'],'ORIGINAL_UNIT_AND_INTEGRATION_TESTS')
for mode in ['all','r25appearance','r25cache','r25skins','r25performance']:
 tag=a.attempt+'-'+mode
 run('visual-'+mode,['python3',ROOT/'verification/r29/run_visual.py',tag,'--mode',mode],'ACTUAL_GODOT_RENDER',ROOT/'evidence/r25/visual'/tag/'RESULT.json')
run('actual-items-ui',['python3',ROOT/'verification/r28/run_existing_items_ui.py',a.attempt],'ACTUAL_GODOT_UI_INPUT_SAVE',ROOT/'evidence/r25/items-ui'/a.attempt/'RECEIPT.json',{'P1998_UI_FIXTURE':str(fixture)})
ui=ROOT/'evidence/r25/items-ui'/a.attempt/'runtime'
if(ui/'ko-checks.json').exists()and json.loads((ui/'ko-checks.json').read_text()).get('status','').startswith('PASS'):
 console('backup-restore','BackupProbe.cs',[str(ui/'r25-before-death-ui.zip')])
else:rows.append(dict(name='backup-restore',category='ACTUAL_STORAGE',status='BLOCKED',reason='Actual UI save fixture did not finish; source preserved.'))
report=dict(status='PASS_SCOPED_FINAL_REGRESSION'if all(x['status']=='PASS'for x in rows)else'FAIL_OR_BLOCKED',results=rows,physical_android='NOT_RUN',whole_game_performance='FAIL_RETAINED')
(out/'RESULT.json').write_text(json.dumps(report,indent=2));raise SystemExit(0 if report['status'].startswith('PASS')else 1)
