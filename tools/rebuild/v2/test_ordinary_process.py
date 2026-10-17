#!/usr/bin/env python3
"""Ordinary GUI create/cancel, OS X11 input, save and separate-process continuation.

Runs inside with_display.py. R16 compact footer exposes the same save/menu callback as '저장'. Synthetic OS events are not physical keys or Korean
IME, and Linux Godot loading an exported Windows PCK is not native Windows.
"""
import argparse,json,os,subprocess,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'p2'))
from gameplay_x11 import X11,control,checkpoints

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--godot',required=True,type=Path);p.add_argument('--project',type=Path)
 p.add_argument('--runtime',type=Path);p.add_argument('--pack',type=Path)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--user-dir',default='baram_rebuild_gameplay_001');p.add_argument('--xdotool',type=Path,required=True)
 a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(parents=True)
 e=os.environ.copy();e.update(XDG_DATA_HOME=str(o/'data'),XDG_CONFIG_HOME=str(o/'config'),XAUTHORITY='',GODOT_SILENCE_ROOT_WARNING='1')
 if a.pack:e.pop('BARAM_GAMEPLAY_RUNTIME',None)
 elif a.runtime:e['BARAM_GAMEPLAY_RUNTIME']=str(a.runtime.resolve())
 else:raise ValueError('Explicit runtime or final pack required')
 command=[str(a.godot.resolve()),'--audio-driver','Dummy']+(['--main-pack',str(a.pack.resolve())] if a.pack else ['--path',str(a.project.resolve())])
 cpath=o/'data'/a.user_dir/'gameplay-checkpoints.jsonl';saves=cpath.parent/'gameplay-p3/characters'
 result={'scope':'Actual Linux OpenGL window, synthetic X11 events, ordinary game mode, no progress grants; not native Windows/Android/physical IME','checks':[],'pack_sha256':hashlib.sha256(a.pack.read_bytes()).hexdigest() if a.pack else None,'runtime_manifest_sha256':hashlib.sha256((a.runtime/'runtime.json').read_bytes()).hexdigest() if a.runtime else None}
 def check(i,b,details=None):result['checks'].append({'id':i,'status':'PASS' if b else 'FAIL','details':details})
 def wait_stage(stage,since=0):
  end=time.monotonic()+25
  while time.monotonic()<end:
   rows=checkpoints(cpath)
   if any(r.get('stage')==stage for r in rows[since:]):return rows
   if process.poll() is not None:raise RuntimeError('Game process stopped before '+stage)
   time.sleep(.1)
  raise TimeoutError(stage)
 def capture(name):
  r=subprocess.run(['ffmpeg','-loglevel','error','-y','-f','x11grab','-video_size','1600x1000','-i',e['DISPLAY'],'-frames:v','1',str(o/(name+'.png'))],env=e,capture_output=True,timeout=20)
  check(name+':external_window_capture',r.returncode==0,r.stderr.decode()[:200])
 def attach_input():
  instance=X11(e)
  def run(*args):subprocess.run([str(a.xdotool.resolve()),*map(str,args)],env=e,check=True,capture_output=True,timeout=10)
  def focus():run('windowfocus','--sync',instance.window)
  def click(rect):
   focus();run('mousemove','--window',instance.window,int(rect[0]+rect[2]/2),int(rect[1]+rect[3]/2));run('click','1');time.sleep(.25)
  def key(name,hold=.05):
   focus();run('keydown','--clearmodifiers',name);time.sleep(hold);run('keyup',name);time.sleep(.05)
  def text(value):focus();run('type','--clearmodifiers','--delay','30',value)
  instance.click=click;instance.key=key;instance.text=text
  return instance
 result['input_method']='XTEST through xdotool with explicit focus before each action; XSendEvent-only prior attempt retained as failed input method'
 process=None;x=None
 try:
  with (o/'ordinary.log').open('wb') as log:
   process=subprocess.Popen(command,env=e,stdout=log,stderr=subprocess.STDOUT)
   wait_stage('ui_layout');x=attach_input();capture('01-menu')
   x.click(control(cpath,'새 캐릭터'));time.sleep(.25);x.text('cancelv2');x.click(control(cpath,'취소'))
   check('cancel_creates_no_save',not list(saves.glob('*.json')))
   x.click(control(cpath,'새 캐릭터'));time.sleep(.25);x.text('v2player');x.click(control(cpath,'만들고 시작'))
   wait_stage('character_created');time.sleep(.7)
   files=list(saves.glob('*.json'));check('ordinary_creation_saved',len(files)==1)
   if len(files)!=1:raise RuntimeError('Expected one normal character save')
   first=json.loads(files[0].read_text())['payload'];check('ordinary_Lv1_commoner_no_skills',first['character']['level']==1 and first['character']['job']=='commoner' and not first['skills'])
   x.key('Down',5.0);time.sleep(.4);x.key('space',.15);time.sleep(.3)
   capture('02-world')
   x.click(control(cpath,'저장'));time.sleep(.6)
   after=json.loads(files[0].read_text())['payload']
   check('OS_input_movement_saved',(after['character']['map_id'],after['character']['x'],after['character']['y'])!=(first['character']['map_id'],first['character']['x'],first['character']['y']),{'before':first['character'],'after':after['character']})
   check('saved_request_stream_advanced',after['request_watermarks'].get('ui',0)>0)
   x.close();x=None;process.terminate();process.wait(timeout=10)
  since=len(checkpoints(cpath))
  with (o/'restart.log').open('wb') as log:
   process=subprocess.Popen(command,env=e,stdout=log,stderr=subprocess.STDOUT)
   wait_stage('ui_layout',since);x=attach_input();x.click(control(cpath,'이어 하기'));rows=wait_stage('loaded',since)
   loaded=[r for r in rows[since:] if r.get('stage')=='loaded'][-1]['details']['character']
   check('new_process_load_exact_saved_character',loaded==after['character'],loaded)
   time.sleep(.5)
   for direction in ('Down','Left','Right','Up'):x.key(direction,.4)
   time.sleep(.2);capture('03-resumed')
   x.click(control(cpath,'저장'));time.sleep(.5)
   final=json.loads(files[0].read_text())['payload']
   check('continued_process_new_requests_save',final['request_watermarks'].get('ui',0)>after['request_watermarks'].get('ui',0))
   result['final_character']=final['character'];result['commands']='Ordinary synthetic X11 mouse/keyboard only; no engine fixture or state grants'
 except Exception as ex:
  result['error']=str(ex)
 finally:
  if x:x.close()
  if process and process.poll() is None:process.terminate();process.wait(timeout=10)
 result['status']='PASS' if not result.get('error') and result['checks'] and all(c['status']=='PASS' for c in result['checks']) else 'FAIL'
 (o/'ORDINARY_PROCESS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'checks':len(result['checks']),'error':result.get('error')}))
 return 0 if result['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
