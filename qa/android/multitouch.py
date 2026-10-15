"""Native Android two-pointer checks on an unchanged signed player APK."""
import argparse, hashlib, json, subprocess, time, traceback, select
from pathlib import Path
P='org.irewon.baram.singleplayer'
def adb(*args):
    return subprocess.check_output(['adb',*map(str,args)],stderr=subprocess.STDOUT)
def main(a):
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);checks=[];driver=None;recording=None
    def check(ok,name,**details):
        checks.append(dict(name=name,status='PASS' if ok else 'FAIL',details=details));print(name,checks[-1]['status'],flush=True)
    def key(code):adb('shell','input','keyevent',code);time.sleep(.35)
    def shot(name):(out/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
    def diag():
        files=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
        for f in files:adb('shell','rm','-f',f)
        for attempt in range(60):
            if attempt%10==0:key(138)
            files=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
            if files:
                try:return json.loads(adb('exec-out','cat',files[0]))
                except json.JSONDecodeError:pass
            time.sleep(.2)
        raise RuntimeError('Diagnostic unavailable')
    def player():
        key(135)
        files=adb('shell','find',f'/data/user/0/{P}/files','-name','character.json').decode().splitlines()
        if len(files)!=1:raise RuntimeError('Expected one normal save')
        return json.loads(json.loads(adb('exec-out','cat',files[0]))['payload'])['player']
    def send(action,*points):
        driver.stdin.write(json.dumps({'action':action,'points':points})+'\n');driver.stdin.flush()
        if not select.select([driver.stdout],[],[],15)[0]:raise RuntimeError('OS pointer delivery timed out')
        answer=driver.stdout.readline().strip()
        if answer!='INJECTED':raise RuntimeError('OS rejected pointer event: '+answer)
        time.sleep(.12)
    try:
        adb('root');adb('wait-for-device');adb('shell','wm','size','1280x720');adb('shell','wm','density','160')
        adb('shell','settings','put','secure','immersive_mode_confirmations','confirmed')
        adb('install','-r',a.apk);adb('logcat','-c')
        component=adb('shell','cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER','-p',P).decode().strip().splitlines()[-1]
        adb('shell','am','start','-W','-n',component)
        for _ in range(100):
            if 'BARAM_READY ' in adb('logcat','-d','-v','brief').decode(errors='replace'):break
            time.sleep(1)
        else:raise RuntimeError('Startup timed out')
        key(66);key(33);d=diag();check(d['menu']=='','normal_player_creation')
        novice=player();check(novice['level']==1 and novice['job']=='평민' and not novice['skills'] and not any(novice['hotbar']),'native_pointer_new_character_has_no_unearned_skills')
        recording=subprocess.Popen(['adb','shell','screenrecord','--time-limit','180','/sdcard/baram-pointers.mp4'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        adb('push',a.driver,'/data/local/tmp/baram-pointer.jar')
        driver=subprocess.Popen(['adb','shell','CLASSPATH=/data/local/tmp/baram-pointer.jar','app_process','/system/bin','PointerDriver'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'driver.log').open('w'),text=True)
        # Actual OS pointer IDs are preserved across multi-pointer up/move events.
        origin=[3,140,600];left=[3,65,600];attack=[7,1200,650]
        before=diag();send(0,origin);send(2,left);time.sleep(.7)
        send(5|(1<<8),left,attack);time.sleep(1);shot('two-finger-move-attack')
        send(2,left,[7,650,250]);send(6|(1<<8),left,[7,650,250])
        after_release=diag();time.sleep(.7);continuing=diag()
        check(continuing['input']['direct_direction']==1 and continuing['input']['pointer_count']==1 and continuing['position'][0]<before['position'][0],'right_finger_release_keeps_joystick_active',before=before['position'],after=continuing['position'],input=continuing['input'])
        check(any(e['event']=='attack_started' for e in continuing['recent_events']),'OS_second_pointer_attacks_while_joystick_held')
        send(5|(1<<8),left,[7,1100,650]);send(6|(1<<8),left,[7,1100,650]);time.sleep(.8)
        check(not any(e['event']=='skill_started' for e in diag()['recent_events']) and player()['mp']==novice['mp'],'OS_second_pointer_respects_empty_novice_skill_slot')
        send(1,left);time.sleep(.5);stopped=diag();time.sleep(.7);check(diag()['position']==stopped['position'] and stopped['input']['direct_direction']==-1 and stopped['input']['pointer_count']==0,'all_released_no_stuck_movement')
        shot('two-finger-released')
        # Four native joystick directions, including visible idle and attacks.
        for direction,(dx,dy) in enumerate([(0,-70),(-70,0),(0,70),(70,0)]):
            point=[3,140+dx,600+dy];send(0,origin);send(2,point);time.sleep(.35);shot(f'joystick-{direction}-walk')
            send(1,point);time.sleep(.3);d=diag();check(d['direction']==direction,'OS_joystick_direction_'+str(direction));shot(f'joystick-{direction}-idle')
            send(0,attack);time.sleep(.2);shot(f'joystick-{direction}-attack');send(1,attack);time.sleep(.7)
        # Home while a finger remains down, then resume without recreating input.
        send(0,origin);send(2,left);key(3);time.sleep(.5)
        adb('shell','am','start','-W','-n',component);time.sleep(.5)
        send(1,left);d=diag();time.sleep(.8);check(diag()['position']==d['position'] and d['input']['direct_direction']==-1 and d['input']['pointer_count']==0,'background_while_held_clears_input');shot('background-resumed')
    except Exception:
        (out/'failure.txt').write_text(traceback.format_exc());print(traceback.format_exc());shot('failure');checks.append({'name':'native_pointer_flow','status':'FAIL'})
    finally:
        if driver:
            try:driver.stdin.close();driver.wait(timeout=10)
            except (BrokenPipeError,subprocess.TimeoutExpired):driver.kill()
        if recording:
            subprocess.run(['adb','shell','pkill','-2','screenrecord'],capture_output=True)
            try:recording.wait(timeout=15)
            except subprocess.TimeoutExpired:recording.kill()
            subprocess.run(['adb','pull','/sdcard/baram-pointers.mp4',str(out/'Android-native-pointers.mp4')],capture_output=True)
        (out/'android.log').write_bytes(adb('logcat','-d','-v','brief'))
        report={'status':'PASS' if checks and all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'apk_sha256':hashlib.sha256(Path(a.apk).read_bytes()).hexdigest(),'scope':'Android35 native MotionEvent OS two-pointer injection; not physical Galaxy'}
        (out/'multitouch-report.json').write_text(json.dumps(report,indent=2));return 0 if report['status']=='PASS' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apk',required=True);p.add_argument('--driver',required=True);p.add_argument('--out',required=True);raise SystemExit(main(p.parse_args()))
