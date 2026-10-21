"""Pinned, portable tool/fixture resolution. No network or product mutations on import."""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2]
class EnvironmentUnavailable(RuntimeError):pass
@dataclass(frozen=True)
class Environment:
 toolchain:Path
 dotnet:Path
 godot:Path
 feed:Path
 packages:Path
 def process(self):
  return os.environ|{'P1998_TOOLCHAIN':str(self.toolchain),'DOTNET_ROOT':str(self.dotnet.parent),'DOTNET_CLI_HOME':str(self.toolchain/'dotnet-home'),'NUGET_PACKAGES':str(self.packages),'DOTNET_PROCESSOR_COUNT':'1','MSBUILDDISABLENODEREUSE':'1','GODOT_SILENCE_ROOT_WARNING':'1','LD_LIBRARY_PATH':str(self.packages/'sqlitepclraw.lib.e_sqlite3/2.1.6/runtimes/linux-x64/native')+':'+str(self.toolchain/'sysroot/usr/lib/x86_64-linux-gnu'),'PATH':str(self.dotnet.parent)+':'+os.environ['PATH']}
def load_environment(toolchain=None,require_godot=False):
 raw=toolchain or os.environ.get('P1998_TOOLCHAIN')
 if not raw:raise EnvironmentUnavailable('P1998_TOOLCHAIN or --toolchain is required; no silent tool-version fallback.')
 t=Path(raw).expanduser().resolve();dotnet=t/'dotnet/dotnet'
 candidates=sorted((t/'godot-mono').glob('Godot_v4.6-stable_mono_linux_x86_64/Godot_v4.6-stable_mono_linux.x86_64'))
 godot=candidates[0]if candidates else t/'godot-mono/MISSING_GODOT_4.6_MONO'
 missing=[str(p)for p in [dotnet,t/'nuget/feed']+([godot]if require_godot else[])if not p.exists()]
 if missing:raise EnvironmentUnavailable('Missing pinned inputs: '+', '.join(missing))
 return Environment(t,dotnet,godot,t/'nuget/feed',t/'nuget/packages')
def validate(e):
 rows=[]
 for name,path,expected in [('dotnet',e.dotnet,'9.0.319'),('godot',e.godot,'4.6.stable.mono.official.89cea1439')]:
  if not path.exists():rows.append(dict(name=name,status='BLOCKED',reason='Missing '+str(path)));continue
  p=subprocess.run([str(path),'--version'],env=e.process(),text=True,capture_output=True,timeout=30)
  rows.append(dict(name=name,status='PASS'if p.returncode==0 and p.stdout.strip()==expected else'FAIL',expected=expected,observed=p.stdout.strip(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 return rows
def run(command,log,e,cwd=ROOT):
 log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('w')as f:p=subprocess.run([str(x)for x in command],cwd=cwd,env=e.process(),stdout=f,stderr=subprocess.STDOUT)
 return p.returncode
