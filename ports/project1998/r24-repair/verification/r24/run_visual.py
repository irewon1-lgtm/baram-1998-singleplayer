#!/usr/bin/env python3
"""Execute the actual UI source at its public scene/render interfaces; isolated decoded fixture."""
import argparse,csv,hashlib,json,os,shutil,struct,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--mode',default='layout');a=p.parse_args()
root=Path(__file__).resolve().parents[2];tools=Path(os.environ['P1998_TOOLCHAIN'])
out=root/'evidence/r24/visual'/a.attempt;out.mkdir(parents=True,exist_ok=False)
project=root.parent/'r24-visual-projects'/a.attempt;project.mkdir(parents=True,exist_ok=False)
names=['GameView.cs','GameHud.cs','ArtCatalog.cs','ActorPose.cs','TileMotion.cs','InputIntentState.cs','KoreanText.cs','ReconstructedGraphics.cs','GameAudio.cs']
for n in names:shutil.copy2(root/'android'/n,project/n)
shutil.copy2(root/'verification/r24/VisualProbe.cs',project/'VisualProbe.cs')
shutil.copy2(root/'verification/r24/GraphicsProbe.cs',project/'GraphicsProbe.cs')
shutil.copy2(root/'candidate/game-data/RecoveredItems.json',project/'recovered-items.json')
(project/'skin-icons.json').write_text(json.dumps({x['ItmId']:int(x['ItmIcon']) for x in csv.DictReader((root/'candidate/game-data/Items.csv').read_text().splitlines()) if x['ItmType']=='27'}))
shutil.copy2(root/'evidence/r24/assets-audit/ALL-286-ASSET-AUDIT.json',project/'asset-286.json')
shutil.copy2(root/'verification/r24/assets-audit/reconstructed-role-spec.json',project/'reconstructed-roles.json')
shutil.copytree(root/'android/assets',project/'assets',ignore=shutil.ignore_patterns('game-data.zip','g1a-normal-earned*','test-only'))
# Preserve imported original bytes so an unchanged atlas need not be reimported.
with zipfile.ZipFile(Path(os.environ['P1998_BASELINE_APK'])) as z:
 for n in z.namelist():
  if n.startswith('assets/.godot/imported/'):
   dst=project/n[7:];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(n))
shutil.copy2(root/'android/Localization/ko-KR.json',project/'ko-KR.json')
prod=Path(os.environ.get('P1998_PROBE_PRODUCTS',str(root/'android/.godot/mono/temp/bin/Release')))
refs=''.join('<Reference Include="'+n[:-4]+'"><HintPath>'+str(prod/n)+'</HintPath><Private>true</Private></Reference>' for n in ['EmbeddedHost.dll','Server.dll','Shared.dll','Shared.Core.dll','Protocol.Tk495.dll'])
(project/'VisualProbe.csproj').write_text('<Project Sdk="Godot.NET.Sdk/4.6.0"><PropertyGroup><TargetFramework>net9.0</TargetFramework><EnableDynamicLoading>true</EnableDynamicLoading><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><TreatWarningsAsErrors>true</TreatWarningsAsErrors><UseSharedCompilation>false</UseSharedCompilation></PropertyGroup><ItemGroup>'+refs+'<EmbeddedResource Include="ko-KR.json" /></ItemGroup></Project>')
cfg=(root/'android/project.godot').read_text().replace('res://Boot.tscn','res://VisualProbe.tscn').replace('"G1BProbe"','"VisualProbe"')
(project/'project.godot').write_text(cfg)
(project/'VisualProbe.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://VisualProbe.cs" id="1"]\n[node name="VisualProbe" type="Control"]\nlayout_mode=3\nanchors_preset=15\nanchor_right=1.0\nanchor_bottom=1.0\nscript=ExtResource("1")\n')
rows=list(csv.DictReader((root/'candidate/game-data/map_index.csv').read_text().splitlines()))
rules=json.loads((root/'candidate/game-data/RestoredContent.json').read_text())
selected=set([330,334,333,340,4711,4715])|set(rules['NewMaps'])|{x['map']for x in json.loads((root/'verification/r24/BASELINE-ROOMS.json').read_text())['new_maps']}|{x['Map']for x in rules['Regions']}
maps=[];(project/'terrain').mkdir()
for m in rows:
 if int(m['id'])not in selected:continue
 shutil.copy2(root/'candidate/game-data/maps'/('TK'+m['id']+'.map'),project/'terrain'/('TK'+m['id']+'.map'))
 maps.append({'id':int(m['id']),'name':m['name'],'width':int(m['xs']),'height':int(m['ys'])})
(project/'terrain-input.json').write_text(json.dumps(maps))
env=os.environ|{'PATH':str(tools/'dotnet')+':'+os.environ['PATH'],'DOTNET_ROOT':str(tools/'dotnet'),'DOTNET_CLI_HOME':str(tools/'dotnet-home'),'NUGET_PACKAGES':str(tools/'nuget/packages'),'DOTNET_PROCESSOR_COUNT':'1','MSBUILDDISABLENODEREUSE':'1','GODOT_SILENCE_ROOT_WARNING':'1'}
godot=tools/'godot-mono/Godot_v4.6-stable_mono_linux_x86_64/Godot_v4.6-stable_mono_linux.x86_64'
commands=[[str(tools/'dotnet/dotnet'),'build',str(project/'VisualProbe.csproj'),'-c','Release','-m:1','-p:NuGetAudit=false','-p:RestoreSources='+str(tools/'nuget/feed')],[str(godot),'--headless','--editor','--path',str(project),'--import','--quit']]
rec={'attempt':a.attempt,'mode':a.mode,'source_hashes':{n:hashlib.sha256((project/n).read_bytes()).hexdigest() for n in names},'physical_android':'NOT_RUN','scope':'ACTUAL_SOURCE_PUBLIC_UI_AND_DECODED_RENDER_FIXTURE_NOT_NATURAL_PROGRESS','steps':[]}
for i,cmd in enumerate(commands):
 with (out/('step'+str(i)+'.log')).open('w') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 rec['steps'].append({'command':cmd,'exit':r.returncode})
 if r.returncode:break
else:
 release=project/'.godot/mono/temp/bin/Release';shutil.copytree(release,release.with_name('Debug'),dirs_exist_ok=True)
 cmd=['python3',str(root/'verification/r20/performance/display.py'),'--attempt','r21-'+a.attempt,'--timeout','1800','--',str(godot),'--path',str(project),'--display-driver','x11','--rendering-method','gl_compatibility','--rendering-driver','opengl3','--audio-driver','Dummy','--','--out='+str(out),'--mode='+a.mode]
 with (out/'run.log').open('w') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 rec['steps'].append({'command':cmd,'exit':r.returncode})
rec['status']='EXECUTED_REVIEW_RESULT' if (out/'RESULT.json').exists() else 'BLOCKED_NO_RESULT'
(out/'RUN.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps({'attempt':a.attempt,'status':rec['status'],'exit':r.returncode,'out':str(out)}));raise SystemExit(r.returncode)
