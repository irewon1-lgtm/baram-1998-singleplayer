#!/usr/bin/env python3
"""Run the isolated verification APK twice on actual Android; require all checks.

Production APK OS-input checks remain a separate, exact-artifact result. This
package uses the same frozen game source/runtime and a test-only input runner.
Only this .verification package's disposable data is cleared.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import traceback

PACKAGE='org.irewon.baram.singleplayer.verification'

def adb(*args,check=True):
    result=subprocess.run(['adb',*map(str,args)],capture_output=True)
    if check and result.returncode:
        raise RuntimeError('adb failed: '+(result.stdout+result.stderr).decode(errors='replace')[:1000])
    return result.stdout

def locate(name,required=False):
    names=adb('shell','run-as',PACKAGE,'find','files','-name',name,check=False).decode().strip().splitlines()
    if len(names)==1:return names[0]
    if required:raise RuntimeError('Missing or ambiguous Android evidence: '+name)
    return None

def read(name):
    return adb('exec-out','run-as',PACKAGE,'cat',locate(name,True))

def run(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    checks=[];runs=[];logs=[];error=None
    def check(ok,name,**details):
        row={'name':name,'status':'PASS' if ok else 'FAIL','details':details};checks.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        if not ok:raise RuntimeError(name)
    try:
        adb('wait-for-device');adb('install','-r',args.apk)
        adb('shell','pm','clear',PACKAGE)
        component=adb('shell','cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN',
                      '-c','android.intent.category.LAUNCHER','-p',PACKAGE).decode().strip().splitlines()[-1]
        if not component.startswith(PACKAGE+'/'):raise RuntimeError('Verification launcher resolution failed')
        for mode in ['recovery-core','recovery-restart']:
            if mode=='recovery-restart':
                saved=read('character.json')
                adb('shell','am','force-stop',PACKAGE)
                adb('install','-r',args.apk)
                check(read('character.json')==saved,'verification_replace_install_preserves_earned_save_bytes')
            adb('logcat','-c');start=time.monotonic();peak=0;first_ready=None;next_mem=0
            adb('shell','am','start','-W','-n',component)
            report=None
            while time.monotonic()-start<args.timeout:
                raw=adb('logcat','-d','-v','brief').decode(errors='replace')
                if 'BARAM_READY ' in raw and first_ready is None:first_ready=time.monotonic()-start
                if 'SCRIPT ERROR:' in raw or 'FATAL EXCEPTION' in raw:
                    raise RuntimeError('Runtime error during '+mode)
                if time.monotonic()>=next_mem:
                    mem=adb('shell','dumpsys','meminfo',PACKAGE,check=False).decode(errors='replace')
                    values=re.findall(r'TOTAL PSS:\s*(\d+)',mem)
                    if values:peak=max(peak,int(values[-1])*1024)
                    next_mem=time.monotonic()+5
                name=mode+'-report.json'
                if locate(name):
                    report=json.loads(read(name));break
                time.sleep(.5)
            raw=adb('logcat','-d','-v','brief').decode(errors='replace');logs.append(raw)
            (out/(mode+'-logcat.log')).write_text(raw,encoding='utf-8')
            check(report is not None,mode+'_report_received',timeout_seconds=args.timeout)
            (out/(mode+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            check(report.get('platform')=='Android',mode+'_actual_android_platform',observed=report.get('platform'))
            check(report.get('status')=='PASS' and bool(report.get('checks')) and all(c.get('status')=='PASS' for c in report['checks']),
                  mode+'_all_executed_checks_pass',statuses={s:sum(c.get('status')==s for c in report.get('checks',[])) for s in ['PASS','FAIL','NOT_RUN','BLOCKED']})
            check(peak>0,mode+'_native_memory_observed',peak_pss_bytes=peak)
            check(first_ready is not None,mode+'_startup_marker_observed',seconds=first_ready)
            if args.source_sha:check(report.get('game_build')==args.source_sha,mode+'_expected_game_source',observed=report.get('game_build'))
            runs.append({'mode':mode,'status':'PASS','peak_pss_bytes':peak,'startup_wall_seconds':first_ready,
                         'wall_seconds':round(time.monotonic()-start,3),'game_build':report.get('game_build'),
                         'content_version':report.get('content_version')})
        check(len({(r['game_build'],r['content_version']) for r in runs})==1,'both_processes_same_source_and_content')
    except Exception:
        error=traceback.format_exc();(out/'failure.txt').write_text(error,encoding='utf-8');print(error,flush=True)
        checks.append({'name':'complete_native_recovery_flow','status':'FAIL'})
    finally:
        raw=adb('logcat','-d','-v','brief',check=False).decode(errors='replace');logs.append(raw)
        (out/'android-logcat.log').write_text('\n'.join(logs),encoding='utf-8')
        for name in ['character.json','expected-state.json']:
            if locate(name):(out/name).write_bytes(read(name))
        for line in adb('shell','run-as',PACKAGE,'find','files','-type','f',check=False).decode().splitlines():
            if '/verification/evidence/' not in line:continue
            relative=line.split('/verification/evidence/',1)[1]
            if '..' in Path(relative).parts:continue
            target=out/'game-evidence'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(adb('exec-out','run-as',PACKAGE,'cat',line,check=False))
        report={'status':'PASS' if error is None and checks and all(c['status']=='PASS' for c in checks) else 'FAIL',
                'scope':'ACTUAL_ANDROID35_VERIFICATION_APK_INPUT_RUNNER_NOT_PLAYER_APK_NOT_PHYSICAL_GALAXY',
                'production_apk_os_input':'SEPARATE_REPORT_REQUIRED','overall_game_complete':False,
                'apk_sha256':hashlib.sha256(Path(args.apk).read_bytes()).hexdigest(),
                'package':PACKAGE,'checks':checks,'runs':runs}
        (out/'android-recovery-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--timeout',type=int,default=1200);parser.add_argument('--source-sha')
    raise SystemExit(run(parser.parse_args()))
