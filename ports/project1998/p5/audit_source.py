"""Remove only declared transport/path seams and compare every original C# body."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser()
for k in ['source','experiment','output']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();src=a.source.resolve();private=a.experiment/'source';files=[]
for folder in ['Shared.Core','Shared','Protocol.Tk495','Server']:
 for f in sorted((src/folder).rglob('*.cs')):
  if {'bin','obj'}&set(f.parts):continue
  rel=f.relative_to(src);original=f.read_text(encoding='utf-8-sig');adapted=(private/rel).read_text(encoding='utf-8-sig')
  if str(rel)=='Shared/RepoPaths.cs':adapted=re.sub(r'        // P3 host supplies its absolute app-private deployment root\.\n.*?(?=        var dir = new DirectoryInfo)', '', adapted, flags=re.S)
  if str(rel)=='Server/World.SpawnDirector.cs':adapted=adapted.replace('internal sealed partial class SpawnDirector','internal sealed class SpawnDirector')
  if str(rel) in ['Server/Session.Dialog.cs','Server/Session.Shop.cs']:
   adapted=re.sub(r'        // P4 presentation transport observes this original outgoing window\.\n        (?:P4Show\(.*|P4Message = text;)\n','',adapted)
  files.append({'path':str(rel),'status':'PASS' if original==adapted else 'FAIL','original_sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
repo=Path(__file__).resolve().parent
checks=[{'path':str(f.relative_to(repo)),'status':'PASS' if f.read_bytes()==(a.experiment/'runtime'/('p5/'+str(f.relative_to(repo/'client')) if f.is_relative_to(repo/'client') else f.name)).read_bytes() else 'FAIL'} for f in [repo/'Bootstrap.cs',repo/'GameCore.cs',repo/'Checkpoint.cs',*sorted((repo/'client').glob('*'))]]
checks.append({'path':'Adapter.cs','status':'PASS' if (repo/'Adapter.cs').read_bytes()==(private/'Server/P4.Adapter.cs').read_bytes() else 'FAIL'})
result={'status':'PASS' if all(f['status']=='PASS' for f in files+checks) else 'FAIL','original_csharp_files':len(files),'original_bodies':files,'app_source_matches_repository':checks,'seams':['explicit absolute root','Server OutputType=Library and Program excluded','SpawnDirector partial modifier','outgoing NPC/shop UI observers'],'lua':'audited byte-identical by content audit'}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(files),len(checks));assert result['status']=='PASS'
