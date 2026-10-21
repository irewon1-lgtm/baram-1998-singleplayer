import pathlib,os,subprocess,json,hashlib,shutil,sys
r=pathlib.Path(__file__).resolve().parents[2];t=pathlib.Path(os.environ['P1998_TOOLCHAIN'])
out=pathlib.Path(os.environ.get('P1998_PROBE_PRODUCT_ROOT',str(r/'evidence/r24/products')))/sys.argv[1];out.mkdir(parents=True,exist_ok=False)
def sources():return {str(f.relative_to(r)):hashlib.sha256(f.read_bytes()).hexdigest()for d in ('candidate/Server','candidate/Shared','Host','android')for f in(r/d).glob('*.cs')}
before=sources()
env=os.environ|{'DOTNET_ROOT':str(t/'dotnet'),'DOTNET_CLI_HOME':str(t/'dotnet-home'),'NUGET_PACKAGES':str(t/'nuget/packages'),'DOTNET_PROCESSOR_COUNT':'1','MSBUILDDISABLENODEREUSE':'1'}
cmd=[str(t/'dotnet/dotnet'),'build',str(r/'android/G1BProbe.csproj'),'-c','Release','-m:1','-p:UseSharedCompilation=false','-p:NuGetAudit=false','-p:RestoreSources='+str(t/'nuget/feed')]
with(out/'build.log').open('w')as f:code=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT).returncode
after=sources()
if before!=after:code=2
if code==0:
 source=r/'android/.godot/mono/temp/bin/Release'
 for f in source.iterdir():
  if f.is_file():shutil.copy2(f,out/f.name)
rec={'exit':code,'command':cmd,'source_hashes':before,'post_source_hashes':after,'source_unchanged_during_build':before==after,'products':{f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in out.glob('*.dll')}}
(out/'BUILD.json').write_text(json.dumps(rec,indent=2));print(json.dumps({'exit':code,'products':str(out)}));sys.exit(code)
