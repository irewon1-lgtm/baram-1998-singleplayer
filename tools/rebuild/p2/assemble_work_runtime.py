"""Freeze only derived runtime assets; never copy original installers, keys or saves."""
import argparse, hashlib, json, pathlib, shutil, sys
from cache_fingerprint import fingerprint
from verify_kr491_assets import verify


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def freeze(maps, kr491, policy, output):
    if output.exists(): raise ValueError('Generation output exists; select a new generation, never overwrite')
    verify(kr491)
    map_index=json.loads((maps/'index.json').read_text()); assets=json.loads((kr491/'kr491_runtime.json').read_text()); pol=json.loads(policy.read_text())
    if not map_index.get('maps') or not assets.get('parts') or len(assets.get('effects',[]))!=128 or len(assets.get('sounds',[]))!=163:raise ValueError('Empty or incomplete required unit')
    for m in map_index['maps']:
        d=json.loads((maps/m['json']).read_text())
        if not d.get('objects') or len(d['collisions']['ground_ids'])!=4096:raise ValueError('Incomplete map dependency closure')
    for kind,parts in assets['parts'].items():
        for p in parts:
            if not p.get('frames'):raise ValueError('Empty original part')
            for f in p['frames']:
                if sha(kr491/f['path'])!=f['sha256']:raise ValueError('Part image hash mismatch')
    for s in assets['sounds']:
        if sha(kr491/s['path'])!=s['sha256']:raise ValueError('Sound hash mismatch')
    code_dir=pathlib.Path(__file__).parent
    components={'input':hashlib.sha256(enc([map_index['source_zip_sha256'],assets['input_sha256']])).hexdigest(), 'parser':hashlib.sha256(enc([map_index.get('parser_sha256'),assets.get('builder_sha256')])).hexdigest(), 'converter':hashlib.sha256(enc({p.name:sha(p) for p in sorted(code_dir.glob('*.py'))})).hexdigest(), 'config':hashlib.sha256(enc(pol)).hexdigest(), 'profile':hashlib.sha256(b'KR125+KR491 diagnostic; default historical profile NULL').hexdigest(), 'schema':hashlib.sha256(b'baram.work.p2.runtime/1').hexdigest(), 'mapping':hashlib.sha256(enc(assets['motion_inspection'])).hexdigest()}
    output.mkdir(parents=True)
    for src,unit in [(maps,'maps'),(kr491,'kr491')]:
        for p in sorted(src.rglob('*')):
            if p.is_file() and p.suffix.lower() in {'.json','.png','.wav'} and '__pycache__' not in p.parts and p.name!='BUILD_RESULT.json':
                dest=output/unit/p.relative_to(src); dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    shutil.copyfile(policy,output/'work_batch_policy.json')
    files=[{'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.rglob('*')) if p.is_file()]
    manifest={'schema':'baram.work.p2.runtime/1','generation':output.name,'fingerprint':fingerprint(components),'cache_components':components,'historical_profile_default':None,'profiles':{'maps':'KR1.25 original map render; city names/target-era identity not established','kr491':'KR4.91 original asset inspection; motion semantic inference; original timing unresolved'},'work_batch_policy':'work_batch_policy.json','files':files,'private_only':True,'excluded':['original archives','DAT/SND/EXE binaries','signing keys','fonts','user saves','source SQL/accounts']}
    (output/'runtime.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return {'status':'FROZEN_DERIVED_RUNTIME','root':str(output),'files':len(files),'bytes':sum(x['bytes'] for x in files),'sha256':sha(output/'runtime.json'),'fingerprint':manifest['fingerprint']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--maps',required=True,type=pathlib.Path);p.add_argument('--kr491',required=True,type=pathlib.Path);p.add_argument('--policy',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
    try:print(json.dumps(freeze(a.maps,a.kr491,a.policy,a.output)))
    except Exception as e:print(json.dumps({'status':'FAIL','reason':str(e)}));sys.exit(1)
