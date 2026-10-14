#!/usr/bin/env python3
"""Real pinned inputs: reject damaged files and IDs; retain existing different files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from import_private_tile_atlases import install, verify_bundle
from intake_private_tiles import store_preserving


def run(a):
    directory=Path(a.out).resolve();directory.mkdir(parents=True,exist_ok=True)
    base=Path(a.assets).resolve();results=[]
    env=dict(os.environ)
    for variable,folder in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
        env[variable]=str(directory/folder)
    bundle=Path(a.bundle)
    target=directory/'repeat-import'
    install(bundle,target)
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir()}
    install(bundle,target)
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir()}
    results.append({'name':'repeat_pinned_import_reuses_same_bytes','status':'PASS' if before==after else 'FAIL'})
    retained=directory/'existing-different.txt';retained.write_text('keep user bytes')
    rejected=False
    try:store_preserving(retained,b'new bytes')
    except ValueError:rejected=True
    results.append({'name':'different_existing_file_not_overwritten','status':'PASS' if rejected and retained.read_text()=='keep user bytes' else 'FAIL'})
    for name,data in [('corrupt.zip',b'broken'),('unsafe-path.zip',None)]:
        path=directory/name
        if data:path.write_bytes(data)
        else:
            with ZipFile(path,'w') as z:z.writestr('../escaped.txt','unsafe')
        rejected=False
        try:verify_bundle(path)
        except (ValueError,OSError):rejected=True
        results.append({'name':'reject_'+name,'status':'PASS' if rejected and not (directory.parent/'escaped.txt').exists() else 'FAIL'})
    for case in ['valid','missing_file','wrong_hash','wrong_tile_id']:
        folder=directory/case;folder.mkdir(exist_ok=True)
        shutil.copytree(base/'tiles',folder/'tiles',dirs_exist_ok=True)
        shutil.copy2(base/'actors.json',folder/'actors.json')
        (folder/'sprites').symlink_to(base/'sprites',target_is_directory=True)
        if case=='missing_file':(folder/'tiles/TileA_palette0_atlas.png').unlink()
        elif case=='wrong_hash':
            p=folder/'tiles/TileA_palette0_atlas.png';p.write_bytes(p.read_bytes()+b'altered')
        elif case=='wrong_tile_id':
            p=folder/'tiles/TileA_frame_map.json';mapping=json.loads(p.read_text());mapping['frames'][0]['i']=4897
            p.write_text(json.dumps(mapping));m=folder/'tiles/MANIFEST.json';manifest=json.loads(m.read_text())
            manifest['groups'][0]['map_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();m.write_text(json.dumps(manifest))
        report=folder/'probe.json'
        command=[a.godot,'--headless','--path',str(ROOT/'game'),'--script','res://asset_validation_probe.gd','--',
                 '--assets='+str(folder),'--report='+str(report)]
        proc=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
        (folder/'probe.log').write_text(proc.stdout+proc.stderr)
        observed=json.loads(report.read_text()) if report.exists() else {'accepted':None}
        expected=case=='valid'
        results.append({'name':'engine_'+case,'status':'PASS' if proc.returncode==0 and observed['accepted']==expected else 'FAIL',
                        'observed':observed,'exit_code':proc.returncode})
    result={'status':'PASS_EXECUTED_INPUT_BOUNDARIES' if all(r['status']=='PASS' for r in results) else 'FAIL',
            'results':results,'scope':'ACTUAL_IMPORTER_AND_ACTUAL_GAME_LOADER; PRIVATE_INPUTS_NEVER_MODIFIED'}
    Path(a.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status'].startswith('PASS') else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',required=True);p.add_argument('--bundle',required=True)
    p.add_argument('--out',required=True);p.add_argument('--report',required=True);p.add_argument('--godot',default='godot')
    raise SystemExit(run(p.parse_args()))
