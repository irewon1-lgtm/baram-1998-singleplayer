"""Materialize a text-only repair overlay in the canonical checkout; never copy keys/saves/assets."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from environment import ROOT
p=argparse.ArgumentParser();p.add_argument('--canonical',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
out=a.canonical/'ports/project1998/r24-repair';out.mkdir(parents=True,exist_ok=True)
extensions={'.cs','.py','.json','.md','.txt','.csv','.csproj','.godot','.cfg','.props','.targets','.html'}
skip={'.git','.godot','obj','bin','evidence','__pycache__','state','profiles','logs'}
with zipfile.ZipFile(a.baseline)as z:
 baseline={n.split('/',1)[1]:hashlib.sha256(z.read(n)).hexdigest()for n in z.namelist()if '/'in n and not n.endswith('/')}
 copied=[]
 for folder in ['candidate','Host','android','verification','r25-report']:
  for f in (ROOT/folder).rglob('*'):
   if not f.is_file()or f.is_symlink()or f.suffix not in extensions:continue
   rel=f.relative_to(ROOT)
   if any(x in skip for x in rel.parts):continue
   if rel.parts[:2]==('android','assets') and f.name!='skin-families.json':continue
   h=hashlib.sha256(f.read_bytes()).hexdigest()
   if baseline.get(rel.as_posix())==h:continue
   target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target);copied.append(rel.as_posix())
 state=json.loads((ROOT/'verification/r25/STATE.json').read_text())
 for phase,paths in state.get('evidence',{}).items():
  for name in paths:
   f=ROOT/name
   if f.suffix not in {'.json','.log','.txt','.md','.csv'}:continue
   target=out/'evidence'/phase/(f.parent.name+'-'+f.name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
(out/'OVERLAY.json').write_text(json.dumps({'baseline_sha256':hashlib.sha256(a.baseline.read_bytes()).hexdigest(),'files':sorted(copied),'user_saves_or_keys_included':False},indent=2))
print(json.dumps({'files':len(copied),'overlay':str(out)}))
