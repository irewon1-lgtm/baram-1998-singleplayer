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
  if str(rel)=='Server/Session.Combat.cs':
   adapted=adapted.replace('    private void SendAction(uint id, ActionType type, ushort time, byte param)\n    {\n        P6ObserveAction(id, type, time); // P6 outgoing action observer\n', '    private void SendAction(uint id, ActionType type, ushort time, byte param) =>\n').replace('$"action(0x1A) type={(byte)type} time={time}");\n    }', '$"action(0x1A) type={(byte)type} time={time}");')
  if str(rel)=='Server/Session.Entity.cs':adapted=adapted.replace('        P6ObserveSound(soundId, entityId, volume); // P6 outgoing media observer\n','')
  adapted=re.sub(r'        P6ObserveText\([^\n]* // P6 outgoing text observer\n','',adapted)
  files.append({'path':str(rel),'status':'PASS' if original==adapted else 'FAIL','original_sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
repo=Path(__file__).resolve().parent;p5=repo.parent/'p5';runtime=a.experiment/'runtime'
checks=[]
for name in ['Bootstrap.cs','GameCore.cs','Checkpoint.cs']:
 expected=(p5/name).read_text()
 if name=='Bootstrap.cs':expected=expected.replace('res://p5/main.tscn','res://p6/main.tscn').replace('P5 시작 실패','P6 시작 실패')
 if name=='GameCore.cs':expected=expected.replace('build = "0.0.5-p5"','media = _session.P6Media, poses = _session.P6Poses, texts = _session.P6Texts, effects = _session.P6Effects(), stats = _session.P6Stats(), build = "0.0.6-p6-fix2"').replace('_world = new World();','_world = new World();\n        _world.P6PlaceAccessibleNpcs(Godot.FileAccess.GetFileAsString("res://p6/art/npc-placements.json"));')
 checks.append({'path':name,'status':'PASS' if expected==(runtime/name).read_text() else 'FAIL'})
for f in sorted((repo/'client').glob('*')):
 if f.is_file() and f.suffix not in ['.uid','.import']:checks.append({'path':'client/'+f.name,'status':'PASS' if f.read_bytes()==(runtime/'p6'/f.name).read_bytes() else 'FAIL'})
checks.append({'path':'RepairCore.cs','status':'PASS' if (repo/'RepairCore.cs').read_bytes()==(runtime/'RepairCore.cs').read_bytes() else 'FAIL'})
checks.append({'path':'P6.Repair.cs','status':'PASS' if (repo/'RepairSession.cs').read_bytes()==(private/'Server/P6.Repair.cs').read_bytes() else 'FAIL'})
checks.append({'path':'P6.Placement.cs','status':'PASS' if (repo/'Placement.cs').read_bytes()==(private/'Server/P6.Placement.cs').read_bytes() else 'FAIL'})
for name,original in [('P4.Adapter.cs',p5/'Adapter.cs'),('P6.Media.cs',repo/'Media.cs')]:checks.append({'path':name,'status':'PASS' if original.read_bytes()==(private/'Server'/name).read_bytes() else 'FAIL'})
checks.append({'path':'P5 capsule/save identity unchanged','status':'PASS' if hashlib.sha256((runtime/'capsule.json').read_bytes()).hexdigest()=='a354ffd0e90a3d1ca447ad51f63e33f634e6a99d95e00890c866609f710507f6' else 'FAIL'})
result={'status':'PASS' if all(f['status']=='PASS' for f in files+checks) else 'FAIL','original_csharp_files':len(files),'original_bodies':files,'app_source_matches_repository':checks,'seams':['P3/P5 root/build/NPC observers unchanged','P6 outgoing sound/action/mini-text/speech observers; every original statement retained','GameCore read-only snapshots, original drop handler binding and explicit user-authorized SkipTutorial boundary','User-authorized NPC-instance relocation in a separate World partial; source definitions/map words unchanged'],'capsule':'exact P5 bytes retained'}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(files),len(checks));assert result['status']=='PASS'
