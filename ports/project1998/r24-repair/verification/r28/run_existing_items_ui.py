#!/usr/bin/env python3
"""Actual item UI regression on a newly generated nonidentifying r25 baseline; no missing old fixture bytes claimed."""
import argparse,datetime,hashlib,json,os,shutil,sqlite3,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--skip-compile',action='store_true');a=p.parse_args()
r=Path(__file__).resolve().parents[2];t=Path(os.environ['P1998_TOOLCHAIN']);out=r/'evidence/r25/items-ui'/a.attempt;out.mkdir(parents=True,exist_ok=False)
source=Path(os.environ['P1998_UI_FIXTURE']);runtime=out/'runtime';runtime.mkdir();(runtime/'state').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[source/'state/project1998.db',source/'g2-local-profile.json',source/'ko-contract.json',source/'local-character-selection-v1.json']+list((source/'profiles').glob('*.json'))+list((source/'state/offline-save-watermarks').glob('*.json'))
files=[p for p in files if p.exists()];before={str(p.relative_to(source)):sha(p)for p in files}
with sqlite3.connect('file:'+str((source/'state/project1998.db').resolve())+'?mode=ro',uri=True)as s,sqlite3.connect(runtime/'state/project1998.db')as d:
 s.backup(d);characters=dict(s.execute('select username,json from characters'));d.execute('pragma journal_mode=DELETE')
s.close();d.close()
contract=json.loads((source/'ko-contract.json').read_text());assert hashlib.sha256(characters[contract['id']].encode()).hexdigest()==contract['character_sha256'],'The new r25 fixture must match its generated contract'
for p in files:
 if p.name=='project1998.db':continue
 dst=runtime/p.relative_to(source);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
project=out/'test-only-project'
shutil.copytree(r/'android',project,ignore=shutil.ignore_patterns('.godot','obj','bin'))
# Only verification code differs: wait for HUD presentation after host snapshots.
smoke=project/'Stage4Smoke.cs'; original=smoke.read_text(); modified=original.replace('while (!predicate())','while (!predicate())',1).replace('    private async Task Click(Control control', '    private async Task Click(Control control',1)
loc=project/'LocalizationSmoke.cs'; original_loc=loc.read_text(); modified_loc=original_loc.replace('await WaitUi(()=>p.Capture().Dialog?.Kind==2,"Actual original F1 menu from Main command");','await WaitUi(()=>p.Capture().Dialog?.Kind==2 && _hud.Buttons.TryGetValue("dialog-menu-1",out var presented) && presented.IsVisibleInTree(),"Actual original F1 menu from Main command");')
assert original_loc!=modified_loc
loc.write_text(modified_loc)
(out/'TEST_ONLY_OVERLAY.json').write_text(json.dumps({'reason':'Server snapshot can precede next Main HUD frame; wait for existing menu button as well. No gameplay/product source change.','original_sha256':hashlib.sha256(original_loc.encode()).hexdigest(),'overlay_sha256':sha(loc),'only_modified_cs':'LocalizationSmoke.cs'},indent=2))
shutil.copy2(r/'verification/r28/ExistingItemsUiSmoke.cs',project/'ItemsUiSmoke.cs')
shutil.copy2(r/'verification/r24/TRANSLATIONS.json',project/'r24-translations.json')
main=project/'Main.cs'; text=main.read_text(); anchor='            if (OS.GetCmdlineUserArgs().Contains("--ko-localization-smoke")) CallDeferred(nameof(BeginLocalizationSmoke));'
assert anchor in text
main.write_text(text.replace(anchor,anchor+'\n            if (OS.GetCmdlineUserArgs().Contains("--r24-items-ui")) CallDeferred(nameof(BeginR24ItemsUiSmoke));'))
(out/'R24-TEST-ONLY-OVERLAY.json').write_text(json.dumps({'main_original_sha256':hashlib.sha256(text.encode()).hexdigest(),'main_overlay_sha256':sha(main),'new_test_only_file':'ItemsUiSmoke.cs','test_source_sha256':sha(project/'ItemsUiSmoke.cs'),'precondition':'New synthetic baseline is opened first. Selected test copy then explicitly seeded through original SaveOfflineSnapshot; other saved characters remain unchanged. No injected file or test fixture enters the APK.'},indent=2))
products=Path(os.environ['P1998_PROBE_PRODUCTS']); csproj=project/'G1BProbe.csproj'; cs=csproj.read_text(); refs=''.join('<Reference Include="'+f.stem+'"><HintPath>'+str(f)+'</HintPath></Reference>' for f in products.glob('*.dll') if f.stem not in ['GodotSharp','G1BProbe'])
csproj.write_text(cs.replace('<ProjectReference Include="../Host/EmbeddedHost.csproj" />',refs))
if (r/'android/.godot/imported').exists():shutil.copytree(r/'android/.godot/imported',project/'.godot/imported',dirs_exist_ok=True)

with zipfile.ZipFile(Path(os.environ['P1998_BASELINE_APK']))as z:
 for n in z.namelist():
  if n.startswith('assets/.godot/imported/'):
   dst=project/n[7:]
   if not dst.exists():dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(n))
env=os.environ|{'PATH':str(t/'dotnet')+':'+os.environ['PATH'],'DOTNET_ROOT':str(t/'dotnet'),'DOTNET_CLI_HOME':str(t/'dotnet-home'),'NUGET_PACKAGES':str(t/'nuget/packages'),'DOTNET_PROCESSOR_COUNT':'1','MSBUILDDISABLENODEREUSE':'1','P1998_G2_DATA':str(runtime),'GODOT_SILENCE_ROOT_WARNING':'1','LD_LIBRARY_PATH':str(t/'nuget/packages/sqlitepclraw.lib.e_sqlite3/2.1.6/runtimes/linux-x64/native')}
rec={'schema':'P1998_R24_FULL_UI_1','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'physical_android':'NOT_RUN','fixture':'NEW_R25_SYNTHETIC_BASELINE; the supplied current contract hash is checked. Original old fixture bytes are unavailable.','parent_character_hash_matches':True,'parent_source_hashes':before,'steps':[]}
def run(name,cmd):
 with(out/(name+'.log')).open('w')as f:x=subprocess.run([str(c)for c in cmd],env=env,cwd=r,stdout=f,stderr=subprocess.STDOUT)
 rec['steps'].append({'step':name,'command':[str(c)for c in cmd],'exit':x.returncode});return x.returncode
code=0
if not a.skip_compile:code=run('compile',[t/'dotnet/dotnet','build',project/'G1BProbe.csproj','-c','Release','-m:1','-p:NuGetAudit=false','-p:RestoreSources='+str(t/'nuget/feed')])
godot=t/'godot-mono/Godot_v4.6-stable_mono_linux_x86_64/Godot_v4.6-stable_mono_linux.x86_64'
if code==0:code=run('import',[godot,'--headless','--editor','--path',project,'--import','--quit'])
if code==0:
 release=project/'.godot/mono/temp/bin/Release';shutil.copytree(release,release.with_name('Debug'),dirs_exist_ok=True)
 rec['products']={p.name:sha(p)for p in release.glob('*.dll')}
 code=run('actual-Godot-UI',['python3',r/'verification/r20/performance/display.py','--attempt','r25-items-ui-'+a.attempt,'--timeout','480','--',godot,'--path',project,'--display-driver','x11','--rendering-method','gl_compatibility','--rendering-driver','opengl3','--audio-driver','Dummy','--','--r24-items-ui'])
checks=json.loads((runtime/'ko-checks.json').read_text())if(runtime/'ko-checks.json').exists()else{'status':'NOT_RUN','checks':[]}
rec['check_status']=checks['status'];rec['check_count']=len(checks['checks']);rec['parent_source_bytes_preserved']=before=={str(p.relative_to(source)):sha(p)for p in files}
with sqlite3.connect('file:'+str(runtime/'state/project1998.db')+'?mode=ro',uri=True)as s,sqlite3.connect(out/'closed-test.sqlite3')as d:
 s.backup(d);d.execute('pragma journal_mode=DELETE');after=dict(d.execute('select username,json from characters'));rec['integrity']=d.execute('pragma integrity_check').fetchall()
rec['other_characters_unchanged']={k:after[k]==v for k,v in characters.items()if k!=contract['id']}
rec['status']='PASS_SCOPED_FULL_UI_NPC_SHOP_QUEST_SAVE'if code==0 and checks['status'].startswith('PASS')and rec['parent_source_bytes_preserved']and all(rec['other_characters_unchanged'].values())else'FAIL_OR_INCOMPLETE'
rec['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();(out/'RECEIPT.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps({k:v for k,v in rec.items()if k in['status','check_status','check_count','other_characters_unchanged','parent_source_bytes_preserved']}));raise SystemExit(0 if rec['status'].startswith('PASS')else 1)
