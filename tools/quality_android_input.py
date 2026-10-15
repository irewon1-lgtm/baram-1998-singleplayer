#!/usr/bin/env python3
"""Exercise the exact signed release APK with Android OS input, no test pack."""
import argparse,hashlib,json,subprocess,time,re,traceback,xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
P='org.irewon.baram.singleplayer'
def adb(*args,check=True):
 r=subprocess.run(['adb',*map(str,args)],capture_output=True)
 if check and r.returncode:raise RuntimeError((r.stdout+r.stderr).decode(errors='replace')[:500])
 return r.stdout

def main(a):
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);checks=[];log_segments=[];recording=None
 maps={m['id']:m for m in json.loads(Path(a.world).read_text())['maps']}
 def check(ok,name,**details):
  checks.append(dict(name=name,status='PASS' if ok else 'FAIL',details=details));print(name,checks[-1]['status'],flush=True)
 def shot(name):
  (out/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
 def key(code):adb('shell','input','keyevent',code);time.sleep(.2)
 def tap(x,y):adb('shell','input','tap',int(x),int(y));time.sleep(.15)
 def diag():
  names=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
  for name in names:adb('shell','rm','-f',name) # This test's previous diagnostic, never a save.
  key(138)
  for attempt in range(100):
   # Diagnostic keys are read-only; retry delivery if the emulator was busy
   # committing a normal save. Frame/save timings still expose every stall.
   if attempt in [15,40,70]:key(138)
   names=adb('shell','find',f'/data/user/0/{P}/files','-path','*/diagnostics/latest.json').decode().splitlines()
   if len(names)==1:
    try:return json.loads(adb('exec-out','cat',names[0]))
    except json.JSONDecodeError:pass
   time.sleep(.2)
  raise RuntimeError('F8 diagnostic missing after bounded wait')
 def dismiss_fullscreen_notice():
  adb('shell','uiautomator','dump','/sdcard/baram-window.xml',check=False)
  raw=adb('exec-out','cat','/sdcard/baram-window.xml',check=False)
  if not raw.strip():return
  try:tree=ET.fromstring(raw)
  except ET.ParseError:return
  for node in tree.iter('node'):
   if node.get('text') in ['Got it','확인'] and node.get('package') in ['android','com.android.systemui']:
    bounds=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
    if len(bounds)==4:tap((bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2);print('Dismissed Android first-use fullscreen notice',flush=True)
 def launch(resume=False):
  prior_pid=adb('shell','pidof',P,check=False).strip()
  comp=adb('shell','cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER','-p',P).decode().strip().splitlines()[-1]
  adb('shell','am','start','-W','-n',comp)
  until=time.monotonic()+100
  while time.monotonic()<until:
   raw=adb('logcat','-d','-v','brief').decode(errors='replace')
   same_process=resume and prior_pid and prior_pid==adb('shell','pidof',P,check=False).strip()
   if 'BARAM_READY ' in raw or same_process:
    dismiss_fullscreen_notice();return
   if 'SCRIPT ERROR:' in raw or 'FATAL EXCEPTION' in raw:raise RuntimeError('Engine error during startup')
   time.sleep(1)
  raise RuntimeError('Startup timed out')
 def ui_point(id,d):
  w,h=1280,720;scale=h/d['viewport'][1];vw,vh=d['viewport'];u=72
  if id=='bag':return ((vw-16-u*1.5-10)*scale,(12+u*.5)*scale)
  if id=='menu':return ((vw-16-u*.5)*scale,(12+u*.5)*scale)
  if id=='attack':return ((vw-16-u*.65)*scale,(vh-12-u*.65)*scale)
  if id=='skill0':return ((vw-16-u*1.87)*scale,(vh-12-u*.57)*scale)
  return (80,45)
 def read_save():
  key(135)
  diag() # Wait for the game input queue to drain after the save commit.
  names=adb('shell','find',f'/data/user/0/{P}/files','-name','character.json').decode().splitlines()
  if len(names)!=1:raise RuntimeError('Expected one normal character save')
  envelope=json.loads(adb('exec-out','cat',names[0]))
  return json.loads(envelope['payload'])
 def tap_cell(x,y,lift=20):
  d=diag();scale=720/d['viewport'][1]
  sx=((x-d['camera'][0])*48+24)*scale;sy=((y-d['camera'][1])*48+48-lift)*scale
  if not (50<sx<1230 and 110<sy<620):raise RuntimeError('Adventure target is outside the unobstructed field')
  tap(sx,sy)
 def settled(limit=12):
  until=time.monotonic()+limit
  while time.monotonic()<until:
   d=diag()
   if d['menu']:return d
   if not d['navigation_path']:
    time.sleep(.35);d=diag()
    if not d['navigation_path']:return d
   time.sleep(.3)
  raise RuntimeError('OS destination did not settle within bounded timeout')
 def adventure():
  d=diag();home=d['map_id']
  guide=next(n for n in maps[home]['npcs'] if n.get('role')=='travel')
  tap_cell(guide['x'],guide['y'],42);d=settled()
  distance=abs(d['position'][0]-guide['x'])+abs(d['position'][1]-guide['y'])
  check(d['menu']=='travel' and distance<=1,'OS_NPC_tap_approaches_before_dialogue',distance=distance);shot('adventure-NPC')
  if d['menu']!='travel':raise RuntimeError('Travel NPC was not reached')
  for _ in range(guide['destinations'].index('field')):key(20)
  key(66);time.sleep(.5);d=diag();check(d['map_id']=='field','OS_existing_travel_to_hunting_map');shot('adventure-field')
  if d['map_id']!='field':raise RuntimeError('Normal travel did not reach field')
  initial=read_save();killed=False;picked=False
  for attempt in range(12):
   state=read_save();p=state['player']
   rabbits=[e for e in state['world'].values() if e.get('map')=='field' and e.get('alive') and e.get('spec',{}).get('name')=='토끼']
   rabbits.sort(key=lambda e:abs(e['x']-p['x'])+abs(e['y']-p['y']))
   if not rabbits:break
   target=rabbits[0];tap_cell(target['x'],target['y'],42)
   d=diag();x,y=ui_point('attack',d)
   adb('shell','input','swipe',int(x),int(y),int(x),int(y),2400)
   time.sleep(.3);state=read_save();killed=state['player']['xp2']>initial['player']['xp2'];shot('adventure-combat')
   drops=[n for n in state['loot'] if n['map']=='field']
   if not drops:continue
   drop=drops[0];before=int(state['player']['inventory'].get(drop['item'],0))
   p=state['player'];m=maps['field']
   for dx,dy in [(3,0),(-3,0),(0,3),(0,-3)]:
    x,y=p['x']+dx,p['y']+dy
    if 0<=x<m['width'] and 0<=y<m['height'] and not m['blocked'][y][x]:
     tap_cell(x,y);settled();break
   tap_cell(drop['x'],drop['y'],14);settled();after=read_save()
   picked=int(after['player']['inventory'].get(drop['item'],0))>before
   if picked:shot('adventure-loot');break
  check(killed,'OS_selected_monster_attack_awards_real_experience')
  check(picked,'OS_real_drop_tap_approaches_and_increases_inventory')
  d=diag();before=read_save()['player'];tap(*ui_point('skill0',d));time.sleep(.7)
  after=read_save()['player']
  check(before['job']=='평민' and not before['skills'] and not any(before['hotbar']) and after['mp']==before['mp'],'OS_novice_empty_skill_slot_does_not_cast_or_spend_mp',level=before['level'])
  guide=next(n for n in maps['field']['npcs'] if n.get('role')=='travel')
  tap_cell(guide['x'],guide['y'],42);d=settled()
  if d['menu']!='travel':raise RuntimeError('Return guide was not reached')
  key(66);check(diag()['map_id']==home,'OS_return_to_town_without_teleport_fixture')
 def floor_goal(d,iteration):
  m=maps[d['map_id']];origin=tuple(d['position'])
  npc_cells={(n['x'],n['y']) for n in m['npcs']}
  doors={(p['x'],p['y']) for p in m['portals']}
  options=[(-3,0),(3,0),(0,3),(0,-3),(-3,2),(3,2)]
  if iteration%2:options.reverse()
  for dx,dy in options:
   goal=(origin[0]+dx,origin[1]+dy)
   if goal in npc_cells or (goal[0],goal[1]+1) in npc_cells:continue
   queue=deque([origin]);seen={origin};found=False
   while queue and len(seen)<512:
    cell=queue.popleft()
    if cell==goal:found=True;break
    for (sx,sy),mask in zip([(0,-1),(-1,0),(0,1),(1,0)],[1,8,2,4]):
     x,y=cell[0]+sx,cell[1]+sy;n=(x,y)
     if n in seen or n in npc_cells or n in doors or not(0<=x<m['width'] and 0<=y<m['height']):continue
     if m['blocked'][y][x] or (m.get('collision_masks',[] ) and int(m['collision_masks'][y][x])&mask):continue
     seen.add(n);queue.append(n)
   if found:return goal
  raise RuntimeError('No nearby unobstructed floor test destination')
 try:
  adb('root',check=False);adb('wait-for-device')
  adb('shell','wm','size','1280x720');adb('shell','wm','density','160')
  # Match Android CTS's emulator fixture: this is the fullscreen navigation
  # tutorial, not a permission/security prompt. Player APK remains unchanged.
  adb('shell','settings','put','secure','immersive_mode_confirmations','confirmed')
  adb('install','-r',a.apk);adb('logcat','-c');launch();shot('01-creation')
  key(66);time.sleep(1);key(33) # Existing equip key E.
  d=diag();check(d['menu']=='','normal_character_creation');shot('02-field-phone')
  initial=read_save()['player']
  check(initial['level']==1 and initial['job']=='평민' and not initial['skills'] and not any(initial['hotbar']),'OS_new_character_level1_commoner_no_unearned_skills',job=initial['job'],level=initial['level'])
  start=time.monotonic()
  recording=subprocess.Popen(['adb','shell','screenrecord','--time-limit','180','/sdcard/baram-quality.mp4'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for code,name in [(19,'up'),(21,'left'),(20,'down'),(22,'right')]:
   key(code);shot('direction-'+name);key(62);time.sleep(.7)
  adventure()
  # First measure coordinate conversion with a stationary camera. During a
  # moving adb gesture, the camera can advance after our read-only snapshot;
  # the game correctly uses the camera at touch-down, not the observer's age.
  d=settled();fixed_goal=floor_goal(d,0);tap_cell(*fixed_goal);d=settled()
  check(d['position']==list(fixed_goal),'stationary_OS_floor_coordinate_exact',expected=list(fixed_goal),observed=d['position'])
  # Retarget arrival is checked against the final command accepted at touch
  # time. Keep every command so failures cannot be hidden by a later success.
  before=diag();generation=before['navigation_generation']
  commands=[]
  for i in range(24):
   latest=floor_goal(diag(),i);tap_cell(*latest)
   accepted=diag();events=[e for e in accepted['recent_events'] if e['event']=='navigation_search']
   if not events:raise RuntimeError('No navigation event after OS floor tap')
   commands.append(events[-1]['details'])
  (out/'retarget-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2))
  latest=list(map(int,re.findall(r'-?\d+',str(commands[-1]['goal']))))
  d=settled()
  check(d['navigation_generation']>=generation+20,'OS_taps_dispatch_20plus_destination_commands',before=generation,after=d['navigation_generation'])
  check(commands[-1]['status']=='FOUND' and d['position']==latest and not d['navigation_path'],'OS_24_retargets_finish_at_latest_floor_destination',expected=latest,observed=d['position'])
  time.sleep(1);check(diag()['position']==d['position'],'cancelled_paths_do_not_restart')
  shot('03-destination-movement')
  tap(*ui_point('bag',d));d=diag();check(d['menu']=='inventory','one_tap_bag');shot('04-bag')
  position=d['position'];tap(640,270);time.sleep(.6);d2=diag();check(d2['position']==position and d2['navigation_path']==[],'modal_tap_no_field_movement')
  key(4);check(diag()['menu']=='','OS_Android_back_closes_bag')
  tap(80,45);check(diag()['menu']=='status','portrait_opens_status');shot('05-status');key(4)
  d=diag();tap(*ui_point('menu',d));check(diag()['menu']=='pause','menu_icon');shot('06-menu')
  # The existing touch menu exposes the same geometry map as the M key.
  scale=720/d['viewport'][1];vw,vh=d['viewport'];width=min(760,vw-32);rx=max(16,(vw-760)/2);ry=20
  bw=(width-68)/2;bh=min(72,max(48,(vh-56-180)/4-10))
  tap((rx+28+bw+12+bw/2)*scale,(ry+96+bh/2)*scale)
  check(diag()['menu']=='world_map','OS_touch_menu_opens_spatial_world_map');shot('06-spatial-map');key(4)
  key(41);check(diag()['menu']=='world_map','OS_M_key_opens_same_spatial_map');key(4)
  # OS lifecycle + drag release; touch drag ownership tested separately by game event suite.
  adb('shell','input','swipe',130,600,230,600,700);key(3);time.sleep(1);launch(resume=True);time.sleep(.8)
  before=diag()['position'];time.sleep(1);check(diag()['position']==before,'OS_background_return_no_stuck_movement')
  # Exactly the same signed APK can be installed over its own data without wiping.
  key(135);d=diag() # F5, then wait for the commit before inspecting the file.
  names=adb('shell','find',f'/data/user/0/{P}/files','-name','character.json').decode().splitlines();assert len(names)==1
  saved=adb('exec-out','cat',names[0]);adb('shell','am','force-stop',P);adb('install','-r',a.apk)
  check(adb('exec-out','cat',names[0])==saved,'replace_install_preserves_save_bytes')
  log_segments.append(adb('logcat','-d','-v','brief').decode(errors='replace'))
  (out/'diagnostic-before-restart.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
  adb('logcat','-c');launch();time.sleep(1);shot('07-restarted')
  # Ten minutes of OS-driven movement / combat buttons / menus / saves.
  iteration=0
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
  adb('shell','am','force-stop',P);adb('shell','wm','size','1280x800')
  log_segments.append(adb('logcat','-d','-v','brief').decode(errors='replace'));adb('logcat','-c');launch();time.sleep(1);shot('10-tablet-field')
  td=diag();check(td['viewport'][1]>0 and td['menu']=='','tablet_ratio_rendered_NOT_GALAXY')
  key(4);check(diag()['menu']=='pause','tablet_Back_opens_menu');shot('11-tablet-menu');key(4)
 except Exception:
  failure=traceback.format_exc();(out/'failure.txt').write_text(failure);print(failure,flush=True);shot('failure')
  checks.append({'name':'complete_OS_flow','status':'FAIL'})
 finally:
  if recording and recording.poll() is None:
   adb('shell','pkill','-2','screenrecord',check=False);recording.wait(timeout=15)
  adb('pull','/sdcard/baram-quality.mp4',out/'08-Android-exact-apk.mp4',check=False)
  raw='\n'.join(log_segments+[adb('logcat','-d','-v','brief').decode(errors='replace')]);(out/'android-logcat.log').write_text(raw)
  errors=[line for line in raw.splitlines() if 'FATAL EXCEPTION' in line or ('godot' in line.lower() and ('SCRIPT ERROR:' in line or 'ERROR:' in line))]
  (out/'OS-renderer-messages.txt').write_text('\n'.join(line for line in raw.splitlines() if 'eglCodecCommon' in line and 'ERROR:' in line))
  check(not errors,'no_runtime_engine_errors',errors=errors[:10])
  report={'status':'PASS' if checks and all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'apk_sha256':hashlib.sha256(Path(a.apk).read_bytes()).hexdigest(),'package':P,'scope':'EXACT_RELEASE_APK_ANDROID_35_X86_64_OS_INPUT_NOT_GALAXY','ARM64_hardware':'NOT_RUN'}
  (out/'android-quality-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  print(json.dumps(report,ensure_ascii=False));return 0 if report['status']=='PASS' else 1
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apk',required=True);p.add_argument('--out',required=True);p.add_argument('--world',required=True);raise SystemExit(main(p.parse_args()))
