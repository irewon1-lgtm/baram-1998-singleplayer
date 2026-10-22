"""Reproduce the established prefixed ZIP+manifest contract from current retained data.
Usage: python verification/r26/refresh_content.py --output-dir /absolute/output
The delivered archive remains a validated build input; this script never runs on game startup.
"""
import argparse,hashlib,json,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
data=R/'candidate/game-data';out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((R/'android/assets/content-manifest.json').read_text())
entries=sorted(p for p in data.rglob('*')if p.is_file());files=[];archive=out/'game-data.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
 for path in entries:
  name=path.relative_to(data).as_posix();content=path.read_bytes()
  info=zipfile.ZipInfo('game-data/'+name,(2026,10,21,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
  z.writestr(info,content);files.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
manifest['files']=files;manifest['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
manifest['r29_content_reproduction']={'scope':'Retained r28 registry/assets; only two southern fence pass flags on map1014 corrected in MapCells. Original map bytes and all content IDs retained.','MapCells_sha256':hashlib.sha256((data/'MapCells.csv').read_bytes()).hexdigest()}
(out/'content-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 assert set(z.namelist())=={'game-data/'+f['path']for f in files}
print(json.dumps({'files':len(files),'archive_sha256':manifest['archive_sha256'],'manifest':str(out/'content-manifest.json')}))
