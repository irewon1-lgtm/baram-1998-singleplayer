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
    if metadata.get('private_only') is not True or metadata.get('contains_user_saves') is not False:
        raise ValueError('Runtime must be private and contain no user saves')
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
    content = json.loads((stage/'private_content/ACTIVE.json').read_text(encoding='utf-8')) if (stage/'private_content/ACTIVE.json').exists() else {'release_id':'legacy-base'}
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    write_json(project/'data/build_info.json', {'commit':commit,'content_version':content['release_id'],'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'world_repairs_sha256':sha256(ROOT/'game/world_repairs.gd'),'save_format_version':2})
    cfg = (project/'project.godot').read_text(encoding='utf-8')
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
    presets=presets.replace('exclude_filter="build_world_cache.gd,*probe.gd,*runner.gd"',
        'exclude_filter="build_world_cache.gd,*probe.gd,*runner.gd,native_regression.gd,exercise.gd,data/balance_tests.json"')
    (project/'export_presets.cfg').write_text(presets, encoding='utf-8')
    write_json(out/'verification-members.json',['exercise.gd','work_play_probe.gd','native_regression.gd'])
    command([args.godot,'--headless','--path',ROOT/'game','--script',ROOT/'tools/pack_runtime.gd','--',
        '--root='+str(ROOT/'game'),'--manifest='+str(out/'verification-members.json'),
        '--out='+str(out/'verification.pck')],out/'verification-pack.log')
    cache=stage/'runtime_cache'
    if args.cache:
        shutil.copytree(Path(args.cache),cache)
        manifest=json.loads((cache/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('world_repairs_sha256')!=sha256(ROOT/'game/world_repairs.gd') or manifest['source_world_sha256']!=sha256(stage/'private_assets/source_maps/world.json') or manifest['content_version']!=content['release_id'] or manifest['sha256']!=sha256(cache/'world.bin'):
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
        'build':{'commit':commit,'content_version':content['release_id'],'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'world_repairs_sha256':sha256(ROOT/'game/world_repairs.gd'),'save_format_version':2},'packaging_engine':version,
        'template':template_info,'original_private_files':len([r for r in rows if r['path'].startswith('private_')]),
        'original_private_bytes_preserved':True,'files':[
            {'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)}
            for p in sorted(stage.rglob('*')) if p.is_file()]})
    write_json(out/'build.json',{'stage':str(stage),'project':str(project),'commit':commit,'status':'EXPORTED_NOT_EXECUTION_PASS'})
    print('BUILD_EXPORTED '+commit)


def run_probe(args, stage, mode, evidence, save, windowed=False):
    exe = stage/EXE
    if os.name=='nt':
        # Hosted runners have no WASAPI output device. Select Dummy explicitly
        # for this automated process; the shipped EXE keeps its normal driver.
        cmd=[str(exe),'--audio-driver','Dummy']
        if not windowed:cmd.append('--headless')
    else:
        if not args.godot:raise ValueError('Linux verification requires --godot')
        cmd=[args.godot,'--headless','--main-pack',str(exe)]
    cmd+=['--','--package-root='+str(stage),'--save='+str(save),
          '--verification-pack='+str(stage.parent/'verification.pck'),
          '--exercise='+mode,'--evidence='+str(evidence)]
    evidence.mkdir(parents=True,exist_ok=True)
    log_path=evidence/(mode+'.log')
    start=time.monotonic();peak=0;ready=None;last_stage='engine initialization'
    first_output=None;engine_bootstrap=None;ready_wall=None;window_samples=0
    with log_path.open('w',encoding='utf-8') as log:
        process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                peak=max(peak,process_rss(process.pid))
                if windowed:
                    state=windows_window_state(process.pid)
                    window_samples+=state['visible_windows']>0
                    if state['hung']:raise RuntimeError('Windows OS marked game window unresponsive during '+last_stage)
                raw=log_path.read_text(encoding='utf-8',errors='replace')
                if raw and first_output is None:first_output=time.monotonic()-start
                for line in raw.splitlines():
                    if line.startswith('BARAM_STARTUP '):
                        phase=json.loads(line.split(' ',1)[1]);last_stage=phase['stage']
                        if engine_bootstrap is None:engine_bootstrap=max(0,time.monotonic()-start-phase['elapsed_ms']/1000)
                    if line.startswith('BARAM_READY '):
                        ready=json.loads(line.split(' ',1)[1])
                        if ready_wall is None:ready_wall=time.monotonic()-start
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
    if os.name=='nt' and peak==0:raise RuntimeError('Windows memory monitor returned no evidence')
    if windowed and window_samples==0:raise RuntimeError('No visible native Windows window was observed')
    if windowed and not any(c['name']=='windowed_game_frame_rendered' and c['status']=='PASS' for c in report['checks']):
        raise RuntimeError('Normal Windows EXE did not prove a rendered game frame')
    return {'mode':mode,'status':'PASS','platform':report['platform'],'peak_rss_bytes':peak if peak else None,
            'execution_mode':'WINDOWED_EXE' if windowed else 'HEADLESS_EXE',
            'audio_output':'NOT_TESTED_CI_DUMMY_NO_AUDIO_DEVICE',
            'windows_message_pump':'PASS' if windowed else 'NOT_OBSERVED_HEADLESS',
            'visible_window_samples':window_samples if windowed else None,
            'first_engine_output_seconds':round(first_output,3) if first_output is not None else None,
            'engine_and_bootstrap_seconds':round(engine_bootstrap,3) if engine_bootstrap is not None else None,
            'startup_wall_seconds':round(ready_wall,3) if ready_wall is not None else None,
            'timing_sample_interval_ms':100,
            'rss_monitoring':'PASS' if peak else 'BLOCKED_LINUX_PID_NAMESPACE',
            'engine_static_memory_bytes':ready['static_memory'] or None,
            'engine_static_memory_monitoring':'OBSERVED' if ready['static_memory'] else 'UNAVAILABLE_ENGINE_BUILD',
            'wall_seconds':round(time.monotonic()-start,3),'startup':ready,
            'checks':[c['name'] for c in report['checks']],'game_build':report['game_build']}


def verify(args):
    out=Path(args.out).resolve();build_info=json.loads((out/'build.json').read_text(encoding='utf-8'))
    stage=Path(build_info['stage']);runs=[]
    if os.name=='nt':
        folder=out/'evidence'/'windowed'
        runs.append(run_probe(args,stage,'native-smoke',folder,folder/'saves/v2/character.json',windowed=True))
    for mode in ['native-smoke','native-core','native-restart']:
        folder=out/'evidence'/('smoke' if mode=='native-smoke' else 'core')
        runs.append(run_probe(args,stage,mode,folder,folder/'saves/v2/character.json'))
    manifest=json.loads((stage/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    if any(r['game_build']!=manifest['build']['commit'] for r in runs):raise ValueError('Evidence belongs to another build')
    result={'status':'PASS','windows_native_execution':'PASS' if os.name=='nt' else 'NOT_RUN_LINUX_EMBEDDED_PCK_ONLY',
            'windows_windowed_startup':'PASS' if os.name=='nt' else 'NOT_RUN_LINUX',
            'windows_message_pump':'PASS' if any(r['windows_message_pump']=='PASS' for r in runs) else 'NOT_RUN_LINUX',
            'game_function_automation':'PASS','actual_windows_gui':'BLOCKED_NO_OPERATOR_GUI_OBSERVATION',
            'runs':runs,'source_sha':manifest['build']['commit']}
    write_json(out/'verification.json',result)
    write_json(stage/'실행검증.json',result)
    print('VERIFICATION '+json.dumps(result,ensure_ascii=False))


def archive(args):
    out=Path(args.out).resolve();result=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    if result['status']!='PASS' or result['game_function_automation']!='PASS':raise ValueError('Verification gate failed')
    if args.require_windows and result['windows_native_execution']!='PASS':raise ValueError('Windows-native evidence is required')
    if args.require_windows and result.get('windows_windowed_startup')!='PASS':raise ValueError('Normal Windows EXE rendering evidence is required')
    if args.require_windows and result.get('windows_message_pump')!='PASS':raise ValueError('Windows message-pump evidence is required')
    if os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('BARAM_PRIVATE_REPOSITORY')!='true' and os.environ.get('BARAM_PRIVATE_DELIVERY_VERIFIED')!='true':
        raise ValueError('Public repository may not create/publish a plaintext private game ZIP')
    stage=Path(json.loads((out/'build.json').read_text(encoding='utf-8'))['stage'])
    manifest=json.loads((stage/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
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


def windows_window_state(pid):
    """Observe the game's actual native window, including Windows' hung flag."""
    import ctypes
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user.EnumWindows.restype=wintypes.BOOL
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype=wintypes.DWORD
    user.IsWindowVisible.argtypes=[wintypes.HWND];user.IsWindowVisible.restype=wintypes.BOOL
    user.IsHungAppWindow.argtypes=[wintypes.HWND];user.IsHungAppWindow.restype=wintypes.BOOL
    visible=[]
    @callback_type
    def inspect(hwnd,_parameter):
        owner=wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd):visible.append(bool(user.IsHungAppWindow(hwnd)))
        return True
    if not user.EnumWindows(inspect,0):raise RuntimeError('Native Windows window observation failed')
    return {'visible_windows':len(visible),'hung':any(visible)}


def process_rss(pid):
    if os.name!='nt':
        try:
            for line in Path(f'/proc/{pid}/status').read_text(encoding='utf-8').splitlines():
                if line.startswith('VmRSS:'):return int(line.split()[1])*1024
        except (FileNotFoundError,ProcessLookupError):pass
        return 0
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                  ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
                  ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
                  ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
                  ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:return 0
    try:
        counter=Counters();counter.cb=ctypes.sizeof(counter)
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(counter),counter.cb):return 0
        return int(counter.WorkingSetSize)
    finally:kernel.CloseHandle(handle)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['build','verify','archive'])
    p.add_argument('--runtime');p.add_argument('--template');p.add_argument('--godot');p.add_argument('--cache')
    p.add_argument('--out',required=True);p.add_argument('--require-windows',action='store_true')
    args=p.parse_args()
    {'build':build,'verify':verify,'archive':archive}[args.operation](args)
