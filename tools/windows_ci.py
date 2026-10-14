#!/usr/bin/env python3
"""Build and verify current game source against a private, hash-pinned runtime.

No plaintext asset/artifact upload is permitted from a public repository.
The private workflow runs the EXE natively. Local Linux checks are labeled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_windows import pe_info, sha256, safe_path, README, VERSION

NAME = '바람의나라_Windows64_복구판'
EXE = '바람의나라.exe'


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def command(args, log, timeout=300):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout)
    output = result.stdout+result.stderr
    Path(log).write_text(output, encoding='utf-8')
    if result.returncode or re.search(r'(?m)^(SCRIPT ERROR:|ERROR:)', output):
        raise RuntimeError(f'Command failed; see {Path(log).name}')
    return output


def validate_runtime(runtime):
    metadata = json.loads((runtime/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    rows = [x for x in metadata['files'] if x['path'].startswith(('private_assets/', 'private_content/', 'licenses/'))]
    expected = {x['path'] for x in rows}
    actual = {p.relative_to(runtime).as_posix() for f in ['private_assets','private_content','licenses']
              for p in (runtime/f).rglob('*') if p.is_file()}
    if expected != actual:
        raise ValueError('Private runtime membership differs from pinned manifest')
    for row in rows:
        path = runtime/str(safe_path(row['path']))
        if path.stat().st_size != row['bytes'] or sha256(path) != row['sha256']:
            raise ValueError('Private runtime integrity failure')
    return metadata, rows


def build(args):
    runtime = Path(args.runtime).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    stage, project = out/NAME, out/'export-source'
    if stage.exists() or project.exists():
        raise ValueError('Choose a new output directory; previous builds are preserved')
    metadata, rows = validate_runtime(runtime)
    stage.mkdir()
    for row in rows:
        path = row['path']
        target = stage/path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime/path, target)
    shutil.copytree(ROOT/'game', project, ignore=shutil.ignore_patterns('.godot', '*.uid'))
    content = json.loads((stage/'private_content/ACTIVE.json').read_text()) if (stage/'private_content/ACTIVE.json').exists() else {'release_id':'legacy-base'}
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    write_json(project/'data/build_info.json', {'commit':commit,'content_version':content['release_id']})
    cfg = (project/'project.godot').read_text()
    cfg = cfg.replace('run/main_scene="res://main.tscn"', 'run/main_scene="res://windows_bootstrap.tscn"')
    (project/'project.godot').write_text(cfg, encoding='utf-8')
    template = Path(args.template).resolve()
    template_info = pe_info(template)
    version = command([args.godot, '--headless','--version'], out/'engine-version.log').strip()
    if not version.startswith(VERSION+'.'):raise ValueError('Editor/template version mismatch')
    presets = f'''[preset.0]
name="Windows64"
platform="Windows Desktop"
runnable=true
advanced_options=false
dedicated_server=false
export_filter="all_resources"
include_filter="*.json"
exclude_filter="build_world_cache.gd,*probe.gd,*runner.gd"
script_export_mode=1
[preset.0.options]
custom_template/release={json.dumps(str(template).replace(chr(92),'/'))}
binary_format/embed_pck=true
binary_format/architecture="x86_64"
debug/export_console_wrapper=0
codesign/enable=false
application/modify_resources=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
'''
    # work_play_probe is required by native_regression; explicitly include it.
    presets=presets.replace('exclude_filter="build_world_cache.gd,*probe.gd,*runner.gd"', 'exclude_filter="build_world_cache.gd"')
    (project/'export_presets.cfg').write_text(presets, encoding='utf-8')
    cache=stage/'runtime_cache'
    if args.cache:
        shutil.copytree(Path(args.cache),cache)
        manifest=json.loads((cache/'manifest.json').read_text())
        if manifest['source_world_sha256']!=sha256(stage/'private_assets/source_maps/world.json') or manifest['content_version']!=content['release_id'] or manifest['sha256']!=sha256(cache/'world.bin'):
            raise ValueError('Cached world does not match private runtime')
    else:
        command([args.godot,'--headless','--path',ROOT/'game','--script','build_world_cache.gd','--',
                 '--assets='+str(stage/'private_assets'),'--content='+str(stage/'private_content'),'--out='+str(cache)], out/'cache.log')
    command([args.godot,'--headless','--editor','--path',project,'--import','--quit'],out/'import.log')
    command([args.godot,'--headless','--path',project,'--export-release','Windows64',stage/EXE],out/'export.log')
    pe_info(stage/EXE)
    for row in rows:
        if sha256(stage/row['path'])!=row['sha256']:raise ValueError('Private data changed during build')
    (stage/'처음읽기.txt').write_text(README+'\n복구판: 첫 화면에 로딩 단계가 표시됩니다. 실행 오류 로그는 저장 폴더 주변 logs/startup.json 및 사용자 데이터 logs/godot.log에 자동 기록됩니다.\n', encoding='utf-8-sig')
    write_json(stage/'실행검증.json',{'windows_native_execution':'NOT_RUN','actual_windows_gui':'BLOCKED_NO_OPERATOR_GUI', 'game_function_automation':'NOT_RUN'})
    write_json(stage/'PACKAGE_MANIFEST.json',{'private_only':True,'contains_user_saves':False,
        'build':{'commit':commit,'content_version':content['release_id']},'packaging_engine':version,
        'template':template_info,'original_private_files':len([r for r in rows if r['path'].startswith('private_')]),
        'original_private_bytes_preserved':True,'files':[
            {'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)}
            for p in sorted(stage.rglob('*')) if p.is_file()]})
    write_json(out/'build.json',{'stage':str(stage),'project':str(project),'commit':commit,'status':'EXPORTED_NOT_EXECUTION_PASS'})
    print('BUILD_EXPORTED '+commit)


def run_probe(args, stage, mode, evidence, save):
    exe = stage/EXE
    if os.name=='nt':
        cmd=[str(exe),'--headless']
    else:
        if not args.godot:raise ValueError('Linux verification requires --godot')
        cmd=[args.godot,'--headless','--main-pack',str(exe)]
    cmd+=['--','--package-root='+str(stage),'--save='+str(save),
          '--exercise='+mode,'--evidence='+str(evidence)]
    evidence.mkdir(parents=True,exist_ok=True)
    import psutil
    log_path=evidence/(mode+'.log')
    start=time.monotonic();peak=0;ready=None;last_stage='engine initialization'
    with log_path.open('w',encoding='utf-8') as log:
        process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        monitor=psutil.Process(process.pid)
        try:
            while process.poll() is None:
                try:peak=max(peak,monitor.memory_info().rss)
                except psutil.NoSuchProcess:pass
                raw=log_path.read_text(encoding='utf-8',errors='replace')
                for line in raw.splitlines():
                    if line.startswith('BARAM_STARTUP '):last_stage=json.loads(line.split(' ',1)[1])['stage']
                    if line.startswith('BARAM_READY '):ready=json.loads(line.split(' ',1)[1])
                if ready is None and time.monotonic()-start>60:raise TimeoutError('Startup timeout at '+last_stage)
                if time.monotonic()-start>240:raise TimeoutError('Game regression timeout')
                if peak>2*1024**3:raise MemoryError('Peak RSS exceeds 2 GiB')
                time.sleep(.1)
        except BaseException:
            process.kill();process.wait();raise
    raw=log_path.read_text(encoding='utf-8',errors='replace')
    if process.returncode or re.search(r'(?m)^(SCRIPT ERROR:|ERROR:)',raw):raise RuntimeError('EXE error; inspect '+log_path.name)
    report=json.loads((evidence/(mode+'-report.json')).read_text(encoding='utf-8'))
    if report['status']!='PASS' or any(c['status']!='PASS' for c in report['checks']):raise RuntimeError('Game checks failed')
    if ready is None or ready['elapsed_ms']>60000:raise RuntimeError('Missing/tardy ready marker')
    return {'mode':mode,'status':'PASS','platform':report['platform'],'peak_rss_bytes':peak,
            'wall_seconds':round(time.monotonic()-start,3),'startup':ready,
            'checks':[c['name'] for c in report['checks']],'game_build':report['game_build']}


def verify(args):
    out=Path(args.out).resolve();build_info=json.loads((out/'build.json').read_text())
    stage=Path(build_info['stage']);runs=[]
    for mode in ['native-smoke','native-core','native-restart']:
        folder=out/'evidence'/('smoke' if mode=='native-smoke' else 'core')
        runs.append(run_probe(args,stage,mode,folder,folder/'saves/v2/character.json'))
    manifest=json.loads((stage/'PACKAGE_MANIFEST.json').read_text())
    if any(r['game_build']!=manifest['build']['commit'] for r in runs):raise ValueError('Evidence belongs to another build')
    result={'status':'PASS','windows_native_execution':'PASS' if os.name=='nt' else 'NOT_RUN_LINUX_EMBEDDED_PCK_ONLY',
            'game_function_automation':'PASS','actual_windows_gui':'BLOCKED_NO_OPERATOR_GUI_OBSERVATION',
            'runs':runs,'source_sha':manifest['build']['commit']}
    write_json(out/'verification.json',result)
    write_json(stage/'실행검증.json',result)
    print('VERIFICATION '+json.dumps(result,ensure_ascii=False))


def archive(args):
    out=Path(args.out).resolve();result=json.loads((out/'verification.json').read_text())
    if result['status']!='PASS' or result['game_function_automation']!='PASS':raise ValueError('Verification gate failed')
    if args.require_windows and result['windows_native_execution']!='PASS':raise ValueError('Windows-native evidence is required')
    if os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('BARAM_PRIVATE_REPOSITORY')!='true':
        raise ValueError('Public repository may not create/publish a plaintext private game ZIP')
    stage=Path(json.loads((out/'build.json').read_text())['stage'])
    manifest=json.loads((stage/'PACKAGE_MANIFEST.json').read_text())
    manifest['files']=[{'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)}
                       for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='PACKAGE_MANIFEST.json']
    manifest['verification']=result
    write_json(stage/'PACKAGE_MANIFEST.json',manifest)
    target=out/(NAME+'_'+result['source_sha'][:10]+'.zip')
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,NAME+'/'+p.relative_to(stage).as_posix())
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise ValueError('ZIP CRC failed')
    write_json(out/'delivery.json',{'file':str(target),'bytes':target.stat().st_size,'sha256':sha256(target),
                                  'verification':result})
    print('ZIP_READY '+str(target))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['build','verify','archive'])
    p.add_argument('--runtime');p.add_argument('--template');p.add_argument('--godot');p.add_argument('--cache')
    p.add_argument('--out',required=True);p.add_argument('--require-windows',action='store_true')
    args=p.parse_args()
    {'build':build,'verify':verify,'archive':archive}[args.operation](args)
