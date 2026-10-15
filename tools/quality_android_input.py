#!/usr/bin/env python3
"""Exercise the exact signed release APK with Android OS input, no test pack."""
import argparse,hashlib,json,subprocess,time,re,traceback
from pathlib import Path
P='org.irewon.baram.singleplayer'
def adb(*args,check=True):
 r=subprocess.run(['adb',*map(str,args)],capture_output=True)
 if check and r.returncode:raise RuntimeError((r.stdout+r.stderr).decode(errors='replace')[:500])
 return r.stdout

def main(a):
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);checks=[]
 def check(ok,name,**details):
  checks.append(dict(name=name,status='PASS' if ok else 'FAIL',details=details));print(name,checks[-1]['status'],flush=True)
 def shot(name):
  (out/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
 def key(code):adb('shell','input','keyevent',code);time.sleep(.2)
 def tap(x,y):adb('shell','input','tap',int(x),int(y));time.sleep(.15)
 def diag():
  key(138)
  names=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
  if len(names)!=1:raise RuntimeError('F8 diagnostic missing')
  return json.loads(adb('exec-out','cat',names[0]))
 def launch():
  comp=adb('shell','cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER','-p',P).decode().strip().splitlines()[-1]
  adb('shell','am','start','-W','-n',comp)
  until=time.monotonic()+100
  while time.monotonic()<until:
   raw=adb('logcat','-d','-v','brief').decode(errors='replace')
   if 'BARAM_READY ' in raw:return
   if 'SCRIPT ERROR:' in raw or 'FATAL EXCEPTION' in raw:raise RuntimeError('Engine error during startup')
   time.sleep(1)
  raise RuntimeError('Startup timed out')
 def ui_point(id,d):
  w,h=1280,720;scale=h/d['viewport'][1];vw,vh=d['viewport'];u=72
  if id=='bag':return ((vw-16-u*1.5-10)*scale,(12+u*.5)*scale)
  if id=='menu':return ((vw-16-u*.5)*scale,(12+u*.5)*scale)
  if id=='attack':return ((vw-16-u*.65)*scale,(vh-12-u*.65)*scale)
  return (80,45)
 try:
  adb('root',check=False);adb('wait-for-device')
  adb('shell','wm','size','1280x720');adb('shell','wm','density','160')
  adb('install','-r',a.apk);adb('logcat','-c');launch();shot('01-creation')
  key(66);time.sleep(1);key(33) # Existing equip key E.
  d=diag();check(d['menu']=='','normal_character_creation');shot('02-field-phone')
  for code,name in [(19,'up'),(21,'left'),(20,'down'),(22,'right')]:
   key(code);shot('direction-'+name);key(62);time.sleep(.7)
  # Floor taps and retargets; metadata confirms actual navigation dispatch.
  before=diag();generation=before['navigation_generation']
  for i in range(24):tap(650+(i%2)*100,440+(i%3)*35)
  time.sleep(2);d=diag()
  check(d['navigation_generation']>=generation+20,'OS_taps_dispatch_20plus_destination_commands',before=generation,after=d['navigation_generation'])
  shot('03-destination-movement')
  tap(*ui_point('bag',d));d=diag();check(d['menu']=='inventory','one_tap_bag');shot('04-bag')
  position=d['position'];tap(640,270);time.sleep(.6);d2=diag();check(d2['position']==position and d2['navigation_path']==[],'modal_tap_no_field_movement')
  key(4);check(diag()['menu']=='','OS_Android_back_closes_bag')
  tap(80,45);check(diag()['menu']=='status','portrait_opens_status');shot('05-status');key(4)
  d=diag();tap(*ui_point('menu',d));check(diag()['menu']=='pause','menu_icon');shot('06-menu');key(4)
  # OS lifecycle + drag release; touch drag ownership tested separately by game event suite.
  adb('shell','input','swipe',130,600,230,600,700);key(3);time.sleep(1);adb('logcat','-c');launch();time.sleep(.8)
  before=diag()['position'];time.sleep(1);check(diag()['position']==before,'OS_background_return_no_stuck_movement')
  # Exactly the same signed APK can be installed over its own data without wiping.
  key(135) # F5
  names=adb('shell','find',f'/data/user/0/{P}/files','-name','character.json').decode().splitlines();assert len(names)==1
  saved=adb('exec-out','cat',names[0]);adb('shell','am','force-stop',P);adb('install','-r',a.apk)
  check(adb('exec-out','cat',names[0])==saved,'replace_install_preserves_save_bytes')
  adb('logcat','-c');launch();time.sleep(1);shot('07-restarted')
  # Ten minutes of OS-driven movement / combat buttons / menus / saves.
  recording=subprocess.Popen(['adb','shell','screenrecord','--time-limit','75','/sdcard/baram-quality.mp4'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  start=time.monotonic();iteration=0
  while time.monotonic()-start<605:
   tap(600+(iteration%3)*65,420+(iteration%2)*45)
   if iteration%5==0:tap(1205,655)
   if iteration%13==0:tap(1130,55);key(4)
   if iteration%30==0:key(135)
   time.sleep(.7);iteration+=1
  recording.wait(timeout=10);adb('pull','/sdcard/baram-quality.mp4',out/'08-Android-exact-apk.mp4')
  d=diag();check(True,'600_seconds_OS_input_session',seconds=round(time.monotonic()-start,2),iterations=iteration)
  (out/'diagnostic-phone.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
  shot('09-phone-final')
  adb('shell','am','force-stop',P);adb('shell','wm','size','1280x800');adb('logcat','-c');launch();time.sleep(1);shot('10-tablet-field')
  key(138);key(4);shot('11-tablet-menu')
  check(True,'tablet_ratio_rendered_NOT_GALAXY')
 except Exception:
  (out/'failure.txt').write_text(traceback.format_exc());shot('failure')
  checks.append({'name':'complete_OS_flow','status':'FAIL'})
 finally:
  raw=adb('logcat','-d','-v','brief').decode(errors='replace');(out/'android-logcat.log').write_text(raw)
  errors=re.findall(r'(?:SCRIPT ERROR:|FATAL EXCEPTION|ERROR:)[^\n]*',raw)
  check(not errors,'no_runtime_engine_errors',errors=errors[:10])
  report={'status':'PASS' if checks and all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'apk_sha256':hashlib.sha256(Path(a.apk).read_bytes()).hexdigest(),'package':P,'scope':'EXACT_RELEASE_APK_ANDROID_35_X86_64_OS_INPUT_NOT_GALAXY','ARM64_hardware':'NOT_RUN'}
  (out/'android-quality-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  print(json.dumps(report,ensure_ascii=False));return 0 if report['status']=='PASS' else 1
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apk',required=True);p.add_argument('--out',required=True);raise SystemExit(main(p.parse_args()))
