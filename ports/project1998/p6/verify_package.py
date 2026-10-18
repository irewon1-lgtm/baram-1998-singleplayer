"""Check frozen runtime bytes, raw JSON and imported assets in the signed APK."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    for k in ['experiment','apk','output']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();runtime=a.experiment/'runtime';frozen=json.loads((a.experiment/'APP_FREEZE.json').read_text())
    drift=[r['path'] for r in frozen['files'] if not (runtime/r['path']).is_file() or sha(runtime/r['path'])!=r['sha256']]
    imports=[];raw={}
    with zipfile.ZipFile(a.apk) as z:
        names=set(z.namelist())
        for f in ['capsule.json','capsule.zip','migration.json','p6/locale.json','p6/art/assets.json','p6/art/npc-placements.json']:
            raw[f]=z.read('assets/'+f)==(runtime/f).read_bytes()
        for directory in ['p6/art','audio','fonts','assets']:
            for f in sorted((runtime/directory).glob('*.import')):
                paths=re.findall(r'path="res://([^"\n]+)"',f.read_text())
                assert paths,(str(f),'missing import path')
                for path in paths:imports.append({'source':str(f.relative_to(runtime))[:-7],'imported':path,'in_apk':'assets/'+path in names})
        maps=[r for r in frozen['files'] if r['path'].startswith('assets/maps/')]
        map_ok=all(z.read('assets/'+r['path'])==(runtime/r['path']).read_bytes() for r in maps)
        assert len(maps)==47
    result={'status':'PASS' if not drift and all(raw.values()) and all(x['in_apk'] for x in imports) and map_ok else 'FAIL','frozen_inputs':len(frozen['files']),'drift':drift,'raw_exact':raw,'map_files_exact':len(maps) if map_ok else False,'imports':imports,'sound_imports':sum(x['source'].endswith('.wav') for x in imports),'apk_sha256':sha(a.apk)}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(frozen['files']),len(imports));assert result['status']=='PASS'
if __name__=='__main__':main()
