import argparse,hashlib,json,os,re,subprocess,time,traceback
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--apk',required=True);parser.add_argument('--out',required=True);parser.add_argument('--driver');args=parser.parse_args();BASE=Path.cwd();APK=Path(args.apk).resolve();OUT=Path(args.out).resolve();OUT.mkdir(parents=True,exist_ok=True);SCREEN_H=720;P='org.irewon.baram.singleplayer';checks=[]
def adb(*args,check=True,timeout=30):
 r=subprocess.run(['adb',*map(str,args)],capture_output=True,timeout=timeout)
 if check and r.returncode:raise RuntimeError((r.stdout+r.stderr).decode(errors='replace')[:500])
 return r.stdout
def record(ok,name,**extra):
 checks.append({'status':'PASS' if ok else 'FAIL','test':name,'observed':extra});print(name,checks[-1]['status'],flush=True);report()
def report():
 (OUT/'results.json').write_text(json.dumps({'environment':'Android 35 x86_64 emulator / software TCG; no physical Galaxy','apk_sha256':hashlib.sha256(APK.read_bytes()).hexdigest(),'checks':checks},ensure_ascii=False,indent=2))
def key(code):adb('shell','input','keyevent',code);time.sleep(.3)
def tap(x,y):adb('shell','input','tap',int(x),int(y));time.sleep(.3)
def screenshot(name):(OUT/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
def diag():
 old=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
 for name in old:adb('shell','rm','-f',name)
 key(138)
 for i in range(30):
  files=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
  if files:
   try:return json.loads(adb('exec-out','cat',files[0]))
   except json.JSONDecodeError:pass
  time.sleep(.3)
 raise RuntimeError('No game diagnostic')
def ui(d):
 vw,vh=d['viewport'];scale=SCREEN_H/vh;px=vw-min(344,max(284,vw*.315));return vw,vh,px,scale
def tab(i,d):
 vw,vh,px,s=ui(d);w=vw-px;tap((px+10+(i%2)*(w-20)/2+(w-20)/4)*s,(12+(i//2)*46+22)*s)
def save(d):
 vw,vh,px,s=ui(d);tap((px+141)*s,(vh-21)*s);time.sleep(.7)
 files=adb('shell','find',f'/data/user/0/{P}/files','-name','character.json').decode().splitlines()
 if len(files)!=1:raise RuntimeError('Save file not found')
 return json.loads(json.loads(adb('exec-out','cat',files[0]))['payload'])
def celltap(x,y,lift=22):
 d=diag();vw,vh,px,s=ui(d);sx=8+(x-d['camera'][0])*48+24;sy=40+(y-d['camera'][1])*48+48-lift
 if not (20<sx<px-20 and 62<sy<vh-130):return False
 tap(sx*s,sy*s);return True
def settled():
 for _ in range(14):
  d=diag()
  if d['menu'] or not d['navigation_path']:time.sleep(.35);return d
  time.sleep(.2)
 return diag()
def confirm(d):
 vw,vh,px,s=ui(d);tap((px/2)*s,(vh-180)*s)
try:
 adb('root',check=False);adb('wait-for-device',timeout=40)
 adb('shell','wm','size','1280x720');adb('shell','wm','density','160')
 adb('shell','settings','put','secure','immersive_mode_confirmations','confirmed')
 adb('logcat','-c');component=adb('shell','cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER','-p',P).decode().strip().splitlines()[-1]
 adb('shell','am','start','-W','-n',component,timeout=50)
 for _ in range(100):
  log=adb('logcat','-d','-v','brief').decode(errors='replace')
  if 'BARAM_READY ' in log:break
  if 'SCRIPT ERROR:' in log or 'FATAL EXCEPTION' in log:raise RuntimeError('Native engine startup error')
  time.sleep(1)
 else:raise RuntimeError('Native startup timeout')
 record(True,'exact_release_APK_launched_by_Android')
 d=diag();vw,vh,px,s=ui(d)
 if d['menu']=='creation':tap(480*s,401*s);time.sleep(1);d=diag()
 record(d['menu']=='','native_pointer_character_creation');initial=d['position']
 for i in range(4):
  tab(i,d);time.sleep(.4);screenshot(['items','skills','equipment','stats'][i]);now=diag();record(now['menu']=='' and now['position']==initial,'native_tab_'+str(i)+'_does_not_move')
 state=save(d);record(state['player']['skills']==[],'native_new_character_has_no_unearned_skills')
 tab(0,d);tap((px+53)*s,(vh-21)*s);time.sleep(.5);screenshot('korean-map');key(4);d=diag()
 # Real normal exit created by world repair, not guide travel.
 record(celltap(57,150),'normal_town_exit_visible_for_touch');d=settled();screenshot('hunting-entry')
 record(d['map_id']=='field','native_pointer_normal_town_exit')
 if d['map_id']!='field':raise RuntimeError('Normal exit did not enter field')
 initial_state=save(d);done=set()
 for attempt in range(12):
  d=diag();state=save(d);p=state['player'];wanted='토끼' if attempt%2==0 else '다람쥐'
  targets=[e for e in state['world'].values() if e['map']=='field' and e['alive'] and e['spec']['name']==wanted]
  targets.sort(key=lambda e:abs(e['x']-p['x'])+abs(e['y']-p['y']))
  if not targets:continue
  e=targets[0]
  if not celltap(e['x'],e['y'],32):continue
  d=diag();vw,vh,px,s=ui(d);x=(px-8-68*.65)*s;y=(vh-114-68*.65)*s
  adb('shell','input','swipe',int(x),int(y),int(x),int(y),1800,timeout=15);time.sleep(.6)
  state=save(d)
  if not state['world'][e['id']]['alive']:done.add(wanted)
  for drop in state['loot']:
   if drop['map']=='field' and celltap(drop['x'],drop['y'],12):settled()
  screenshot('hunting-'+str(attempt))
  current=save(diag())
  if len(done)==2 and current['player']['kills']>=5 and current['player']['inventory']!=initial_state['player']['inventory']:break
 record('토끼' in done,'native_normal_rabbit_defeated');record('다람쥐' in done,'native_normal_squirrel_defeated')
 state=save(diag());record(state['player']['xp2']>initial_state['player']['xp2'],'native_real_experience_gain');record(state['player']['inventory']!=initial_state['player']['inventory'],'native_real_drop_pickup')
 celltap(30,56);d=settled();record(d['map_id']=='village','native_pointer_return_exit');screenshot('returned')
 if d['map_id']=='village' and state['player']['kills']>=5:
  celltap(63,153,62);settled();time.sleep(.5)
 state=save(diag());record(state['player']['level']>1,'native_earned_hunt_quest_level_up',level=state['player']['level'])
 saved=state['player'];adb('shell','am','force-stop',P);adb('logcat','-c');adb('shell','am','start','-W','-n',component,timeout=50)
 for _ in range(100):
  if 'BARAM_READY ' in adb('logcat','-d','-v','brief').decode(errors='replace'):break
  time.sleep(.5)
 d=diag();loaded=save(d)['player'];record(loaded['inventory']==saved['inventory'] and loaded['level']==saved['level'] and loaded['equipped']==saved['equipped'],'native_save_restart_preserves_progress');screenshot('restart')
 # Reinstall the identical release without clearing data and compare save bytes.
 adb('shell','am','force-stop',P)
 names=adb('shell','find',f'/data/user/0/{P}/files','-name','character.json').decode().splitlines()
 before=adb('exec-out','cat',names[0]);adb('install','--no-incremental','-r',APK,timeout=120)
 record(adb('exec-out','cat',names[0])==before,'same_package_replacement_install_preserves_save_bytes')
 adb('shell','am','start','-W','-n',component,timeout=50);time.sleep(4);d=diag()
 if args.driver:
  import select
  adb('push',args.driver,'/data/local/tmp/baram-pointer.jar')
  driver=subprocess.Popen(['adb','shell','CLASSPATH=/data/local/tmp/baram-pointer.jar','app_process','/system/bin','PointerDriver'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(OUT/'pointer-driver.log').open('w'),text=True)
  def send(action,*points):
   driver.stdin.write(json.dumps({'action':action,'points':points})+'\n');driver.stdin.flush()
   if not select.select([driver.stdout],[],[],12)[0]:raise RuntimeError('Native pointer timeout')
   if driver.stdout.readline().strip()!='INJECTED':raise RuntimeError('Native pointer rejected')
   time.sleep(.12)
  vw,vh,px,s=ui(d);left=[3,100*s,400*s];down=[3,100*s,460*s];attack=[7,(px-8-68*.65)*s,(vh-114-68*.65)*s]
  send(0,left);send(2,down);send(5|(1<<8),down,attack);time.sleep(.8);screenshot('two-pointers')
  send(6|(1<<8),down,attack);d=diag()
  record(d['input']['direct_direction']==2 and d['input']['pointer_count']==1,'native_attack_release_keeps_joystick_pointer')
  record(any(e['event']=='attack_started' for e in d['recent_events']),'native_second_pointer_attacks_during_joystick')
  send(1,down);time.sleep(.3);d=diag();record(d['input']['direct_direction']==-1 and d['input']['pointer_count']==0,'native_all_fingers_released_no_stuck_input')
  driver.stdin.close();driver.wait(timeout=10)
 adb('shell','wm','size','1280x800');SCREEN_H=800;time.sleep(2);d=diag();start=d['position']
 for i in range(4):tab(i,d);screenshot('tablet-tab-'+str(i))
 record(diag()['position']==start,'native_tablet_four_tabs_without_movement')
except Exception:
 (OUT/'failure.txt').write_text(traceback.format_exc());print(traceback.format_exc(),flush=True);record(False,'native_flow_completed')
 try:screenshot('failure')
 except Exception:pass
finally:
 try:(OUT/'android.log').write_bytes(adb('logcat','-d','-v','brief'))
 except Exception:pass
 report()
