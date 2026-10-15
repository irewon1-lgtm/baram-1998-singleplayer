#!/usr/bin/env python3
"""Actual adb process/input/save evidence. File transport is not cloud sync."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from windows_ci import write_json, command

PACKAGE='org.irewon.baram.singleplayer.verification'
def adb(*args,check=True):
    return subprocess.run(['adb',*map(str,args)],capture_output=True,check=check)
def find_file(name):
    result=adb('shell','run-as',PACKAGE,'find','files','-name',name).stdout.decode().strip().splitlines()
    if len(result)!=1:raise RuntimeError('Missing/ambiguous Android '+name)
    return result[0]
def main(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    adb('install','-r',args.apk)
    adb('shell','pm','clear',PACKAGE)
    adb('logcat','-c')
    start=time.monotonic();peak=0;report=None;raw='';first_ready=None
    adb('shell','am','start','-W','-n',PACKAGE+'/com.godot.game.GodotApp')
    while time.monotonic()-start<180:
        raw=adb('logcat','-d','-v','brief').stdout.decode('utf-8',errors='replace')
        if 'BARAM_READY ' in raw and first_ready is None:first_ready=time.monotonic()-start
        mem=adb('shell','dumpsys','meminfo',PACKAGE,check=False).stdout.decode('utf-8',errors='replace')
        values=re.findall(r'TOTAL PSS:\s*(\d+)',mem)
        if values:peak=max(peak,int(values[-1])*1024)
        if 'BARAM_MOBILE_RESULT ' in raw:
            report=json.loads(raw.split('BARAM_MOBILE_RESULT ',1)[1].splitlines()[0]);break
        if 'SCRIPT ERROR:' in raw or 'FATAL EXCEPTION' in raw:break
        time.sleep(.5)
    (out/'android-logcat.log').write_text(raw,encoding='utf-8')
    if report is None:raise RuntimeError('No native Android result; inspect logcat')
    for name in ['character.json','mobile-report.json','android-frame.png']:
        content=adb('exec-out','run-as',PACKAGE,'cat',find_file(name)).stdout
        (out/name).write_bytes(content)
    if report['status']!='PASS' or report['platform']!='Android':raise RuntimeError('Android native test failed')
    if not peak:raise RuntimeError('Android PSS measurement missing')
    ready=re.findall(r'BARAM_READY (\{[^\n]+\})',raw)
    startup=json.loads(ready[-1]) if ready else {}
    installed=None
    # Emulator userdebug only. No change is made to any user's Galaxy device.
    root=adb('root',check=False)
    adb('wait-for-device')
    code=adb('shell','pm','path',PACKAGE).stdout.decode().strip().removeprefix('package:').removesuffix('/base.apk')
    size=adb('shell','du','-sk',code,check=False)
    if size.returncode==0:
        numbers=re.match(r'\s*(\d+)',size.stdout.decode())
        if numbers:installed=int(numbers[1])*1024
    if installed is None:raise RuntimeError('Android installed code size measurement unavailable')
    write_json(out/'android-metrics.json',{'scope':'ACTUAL_EMULATOR_FIXTURE_NOT_GALAXY_NOT_CLOUD',
        'platform':'Android','peak_observed_pss_bytes':peak,'installed_code_allocated_bytes':installed,
        'internal_game_ready_ms':startup.get('elapsed_ms'),'process_to_ready_seconds':round(first_ready,3) if first_ready else None,
        'apk_bytes':Path(args.apk).stat().st_size,'report':report})
    cmd=[args.godot,'--headless','--path',Path(args.project).resolve(),'--',
        '--assets='+str(Path(args.runtime).resolve()/'private_assets'),'--content='+str(Path(args.runtime).resolve()/'private_content'),
        '--save='+str(out/'character.json'),'--exercise=mobile-pc-resume','--expected='+str(out/'mobile-report.json'),'--evidence='+str(out/'pc-resume')]
    command(cmd,out/'pc-resume.log')
    resumed=json.loads((out/'pc-resume/mobile-pc-resume-report.json').read_text())
    if resumed['status']!='PASS':raise RuntimeError('PC did not restore Android progress')
    print('PC_ANDROID_PC_FILE_FORMAT_PASS; CLOUD_AND_GALAXY_NOT_VERIFIED')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['apk','out','godot','project','runtime']:p.add_argument('--'+key,required=True)
    main(p.parse_args())
