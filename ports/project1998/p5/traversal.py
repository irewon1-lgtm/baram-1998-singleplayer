import argparse,json,shutil,sqlite3,subprocess
from pathlib import Path
from tooling import environment
p=argparse.ArgumentParser()
for k in ['workspace','experiment','output','checkpoint']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();w=a.workspace.resolve();e=a.experiment.resolve();o=a.output.resolve();o.mkdir(parents=True,exist_ok=False);env=environment(w,e)
shutil.copyfile(Path(__file__).with_name('Traversal.cs'),o/'Program.cs')
(o/'Traversal.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><TreatWarningsAsErrors>true</TreatWarningsAsErrors></PropertyGroup><ItemGroup><ProjectReference Include="'+str(e/'source/Server/Server.csproj')+'" /></ItemGroup></Project>')
with sqlite3.connect(a.checkpoint) as c:value=json.loads(c.execute('SELECT json FROM checkpoint WHERE slot=1').fetchone()[0])
(o/'character.json').write_text(json.dumps(value['character']))
for name,cmd in [('build',[e/'dotnet-wrapper/dotnet','build',o/'Traversal.csproj','-m:1','-nr:false','-p:UseSharedCompilation=false','-p:NuGetAudit=false','-v','minimal']),('run',[w/'toolchain/dotnet/dotnet',o/'bin/Debug/net8.0/Traversal.dll',e/'content',o/'state',o/'character.json',o/'TRAVERSAL.json'])]:
 with (o/(name+'.log')).open('w') as f:r=subprocess.run([str(x) for x in cmd],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=240)
 if r.returncode:print((o/(name+'.log')).read_text()[-2500:]);raise SystemExit(r.returncode)
print(json.loads((o/'TRAVERSAL.json').read_text())['status'])
