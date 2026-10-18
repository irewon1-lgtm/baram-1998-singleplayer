#!/usr/bin/env python3
"""Install the exact candidate and exercise real Android input/lifecycle offline.

The emulator and adb share this process's namespace. Nothing is represented as
Galaxy hardware performance; a physical S10 FE is a separate NOT_RUN_DEVICE gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

PACKAGE='com.irewon.baram.project1998.dev'


def main():
    p=argparse.ArgumentParser()
    for name in ['sdk','avd-root','android-user','apk','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for k,v in vars(a).items():setattr(a,k,v.resolve())
    out=a.output;out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(ANDROID_SDK_ROOT=str(a.sdk),ANDROID_AVD_HOME=str(a.avd_root),ANDROID_USER_HOME=str(a.android_user))
    adb=str(a.sdk/'platform-tools/adb');serial='emulator-5554'
    checks=[];emu=None;log=None;record={'status':'BLOCKED_ENVIRONMENT','galaxy_device':'NOT_RUN_DEVICE','apk_sha256':hashlib.sha256(a.apk.read_bytes()).hexdigest()}
    def command(args,timeout=25,check=False,binary=False):
        return subprocess.run(args,env=env,capture_output=True,text=not binary,timeout=timeout,check=check)
    def ad(*args,**kw):return command([adb,'-s',serial,*args],**kw)
    def check(name,ok,detail=None):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail});print(checks[-1],flush=True)
        if not ok:raise AssertionError(name)
    def telemetry(timeout=20,predicate=None):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            r=ad('shell','run-as',PACKAGE,'cat','files/p2/diagnostics.json')
            try:
                d=json.loads(r.stdout)
                if predicate is None or predicate(d):return d
            except ValueError:pass
            time.sleep(.5)
        raise TimeoutError('Android runtime telemetry not observed')
    def capture(name):
        r=ad('exec-out','screencap','-p',binary=True)
        check('Android screencap '+name,r.returncode==0 and r.stdout.startswith(b'\x89PNG'))
        (out/(name+'.png')).write_bytes(r.stdout)
    try:
        command([adb,'start-server'],check=True)
        log=(out/'emulator.log').open('w')
        emu=subprocess.Popen([str(a.sdk/'emulator/emulator'),'-avd','p1998-p2','-no-window','-no-audio','-no-boot-anim','-no-snapshot',
            '-read-only','-accel','off','-gpu','swiftshader_indirect','-memory','2048','-cores','2','-port','5554','-skin','1280x800'],env=env,stdout=log,stderr=subprocess.STDOUT)
        start=time.monotonic();booted=False
        while time.monotonic()-start<240:
            if emu.poll() is not None:raise RuntimeError('Emulator exited '+str(emu.returncode))
            r=ad('shell','getprop','sys.boot_completed',timeout=8)
            if r.stdout.strip()=='1':booted=True;break
            if int(time.monotonic()-start)%30<2:print('Android boot pending',round(time.monotonic()-start),flush=True)
            time.sleep(1)
        if not booted:raise TimeoutError('Android guest did not finish booting in 240 seconds')
        check('Actual Android 35 emulator boots',True,round(time.monotonic()-start,2))
        ad('shell','wm','size','1280x800');ad('shell','wm','density','160');ad('shell','input','keyevent','82')
        ad('shell','settings','put','global','window_animation_scale','0')
        ad('shell','settings','put','global','transition_animation_scale','0')
        installed=ad('install','-r',str(a.apk),timeout=90)
        check('Exact signed APK installs',installed.returncode==0 and 'Success' in installed.stdout,installed.stdout+installed.stderr)
        ad('shell','svc','wifi','disable');ad('shell','svc','data','disable')
        ad('shell','settings','put','global','airplane_mode_on','1')
        ad('shell','am','broadcast','-a','android.intent.action.AIRPLANE_MODE','--ez','state','true')
        ad('logcat','-c')
        launch=ad('shell','am','start','-n',PACKAGE+'/com.godot.game.GodotApp',timeout=45)
        (out/'activity-launch.txt').write_text(launch.stdout+launch.stderr)
        d=telemetry(timeout=50)
        check('Offline Android app opens with original assets',d['map_id']=='4711' and d['position']==[3,5],{k:d[k] for k in ['device_name','map_id','position','save_status']})
        capture('android-start')
        # Native Android tap events, not model API calls.
        sx=round(((9+.5)*24-d['camera'][0])*d['zoom']+d['world_rect'][0]);sy=round(((6+.5)*24-d['camera'][1])*d['zoom']+d['world_rect'][1])
        ad('shell','input','tap',str(sx),str(sy))
        d=telemetry(timeout=40,predicate=lambda x:x['position']==[9,6] and not x['moving'])
        check('Android touch tap reaches exact original map cell',d['position']==[9,6],d['last_tap'])
        ad('shell','input','tap','1190','730');d=telemetry(timeout=15,predicate=lambda x:x['attacks']>=1)
        check('Android attack touch works',d['attacks']>=1,d['attacks'])
        capture('android-moved')
        ad('shell','input','tap','1030','730');time.sleep(1)
        before=telemetry()
        ad('shell','input','keyevent','KEYCODE_HOME');time.sleep(1)
        ad('shell','am','start','-n',PACKAGE+'/com.godot.game.GodotApp')
        after=telemetry(timeout=25,predicate=lambda x:len(x['lifecycle'])>=2 and not x['paused'])
        check('Android Home/background return preserves position and releases movement',after['position']==before['position'] and after['held']==[0,0],after['lifecycle'])
        ad('shell','am','force-stop',PACKAGE)
        ad('shell','am','start','-n',PACKAGE+'/com.godot.game.GodotApp')
        restarted=telemetry(timeout=30,predicate=lambda x:x['loaded_save'])
        check('Android cold relaunch resumes local save',restarted['position']==before['position'],restarted['position'])
        capture('android-resumed')
        logs=ad('logcat','-d',timeout=20).stdout
        (out/'logcat.txt').write_text(logs)
        check('No observed app fatal/script exception','FATAL EXCEPTION' not in logs and 'SCRIPT ERROR' not in logs)
        (out/'ANDROID_DIAGNOSTICS.json').write_text(json.dumps(restarted,ensure_ascii=False,indent=2))
        record['status']='PASS_EMULATOR_OBSERVED_SCOPE'
    except (RuntimeError,TimeoutError,subprocess.TimeoutExpired) as e:
        record['error']=str(e);print('Android environment blocked:',str(e),flush=True)
    except Exception as e:
        record.update(status='FAIL_OBSERVED_ANDROID',error=repr(e));raise
    finally:
        record.update(checks=checks,scope='Actual Android emulator only, CPU software rendering. Never a Galaxy S10 FE performance test.')
        (out/'ANDROID_QA.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        try:ad('emu','kill',timeout=8)
        except Exception:pass
        if emu is not None and emu.poll() is None:
            emu.terminate()
            try:emu.wait(timeout=8)
            except subprocess.TimeoutExpired:emu.kill();emu.wait()
        command([adb,'kill-server'])
        if log is not None:log.close()


if __name__=='__main__':main()
