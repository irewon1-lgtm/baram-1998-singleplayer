#!/usr/bin/env python3
"""Actual X11 OS input and engine viewport captures, all in one network namespace."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def main():
    p=argparse.ArgumentParser()
    for name in ['godot','runtime','display-root','output','visual-script']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for k,v in vars(a).items():setattr(a,k,v.resolve())
    out=a.output;out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(DISPLAY='127.0.0.1:99',GODOT_SILENCE_ROOT_WARNING='1',
        LD_LIBRARY_PATH=str(a.display_root/'usr/lib/x86_64-linux-gnu'),XDG_DATA_HOME=str(out/'data'),XDG_CONFIG_HOME=str(out/'config'))
    xvfb_log=(out/'xvfb.log').open('w')
    server=subprocess.Popen([str(a.display_root/'usr/bin/Xvfb'),':99','-screen','0','1280x800x24','-ac','-nolisten','local','-nolisten','unix','-listen','tcp'],env=env,stdout=xvfb_log,stderr=subprocess.STDOUT)
    xdo=str(a.display_root/'usr/bin/xdotool')
    def x(*args):return subprocess.run([xdo,*map(str,args)],env=env,capture_output=True,text=True,check=True)
    checks=[]
    def check(name,condition,details=None):
        checks.append({'name':name,'status':'PASS' if condition else 'FAIL','details':details});print(checks[-1],flush=True)
        if not condition:raise AssertionError(name)
    process=None
    def launch(suffix):
        log=(out/(suffix+'.log')).open('w')
        return subprocess.Popen([str(a.godot),'--path',str(a.runtime),'--position','0,0','--resolution','1280x800','--audio-driver','Dummy'],env=env,stdout=log,stderr=subprocess.STDOUT)
    def diagnostics():
        paths=list((out/'data').rglob('diagnostics.json'))
        if paths:
            try:return json.loads(paths[0].read_text())
            except (ValueError,OSError):pass
        return None
    def wait_for(predicate,seconds=15):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            d=diagnostics()
            if d and predicate(d):return d
            if process is not None and process.poll() is not None:raise RuntimeError('Godot exited early')
            time.sleep(.1)
        raise TimeoutError('Expected actual runtime state was not observed')
    def capture():x('key','F12');time.sleep(.35)
    try:
        for i in range(30):
            try:x('getdisplaygeometry');break
            except subprocess.CalledProcessError:
                if server.poll() is not None:raise RuntimeError('Xvfb failed')
                time.sleep(.15)
        process=launch('ordinary')
        d=wait_for(lambda d:d['elapsed_seconds']>1)
        check('Fresh isolated app starts on original map 4711 at (3,5)',d['map_id']=='4711' and d['position']==[3,5],d['position'])
        check('Korean local save writes',d['revision']>=1 and '보호' not in d['save_status'],d['save_status'])
        capture()
        x('keydown','Right');time.sleep(.65);x('keyup','Right')
        d=wait_for(lambda d:not d['moving'] and d['position'][0]>3)
        check('Ordinary OS direction input moves the player',d['completed_moves']>=2,d['position'])
        # Tap a fixed free point in the original field through the actual GUI.
        sx=round(((9+.5)*24-d['camera'][0])*d['zoom']+d['world_rect'][0])
        sy=round(((6+.5)*24-d['camera'][1])*d['zoom']+d['world_rect'][1])
        print('Actual target screen coordinate',sx,sy,'runtime geometry',d['world_rect'],d['camera'],flush=True)
        x('mousemove',sx,sy,'click',1)
        d=wait_for(lambda d:d['position']==[9,6] and not d['moving'],seconds=10)
        check('Actual mouse/touch-style tap reaches its map cell',d['position']==[9,6],d['position'])
        capture()
        # Hold up past the map boundary, then release. No state injection.
        x('keydown','Up');time.sleep(2.5);x('keyup','Up')
        d=wait_for(lambda d:not d['moving'] and d['blocked_moves']>0)
        check('Original collision/bounds stop sustained ordinary input',d['position'][1]>=0 and d['blocked_moves']>0,{'at':d['position'],'blocked':d['blocked_moves']})
        x('key','space');time.sleep(.25)
        d=wait_for(lambda d:d['attacks']>=1)
        check('Original attack animation is triggered by ordinary input',d['attacks']>=1,d['attacks'])
        x('mousemove',1030,730,'click',1);time.sleep(.7)
        saved=diagnostics();capture()
        process.terminate();process.wait(timeout=5);process=None
        # Existing custom data and the separate save survive a cold process restart.
        process=launch('cold-resume')
        d=wait_for(lambda d:d['loaded_save'])
        check('Cold restart resumes the saved coordinates',d['position']==saved['position'],{'before':saved['position'],'after':d['position']})
        for xcoord,mid in [(1060,'0'),(1198,'2'),(922,'4711')]:
            x('mousemove',xcoord,50,'click',1)
            d=wait_for(lambda d:d['map_id']==mid)
            capture();check('Original test scene selector '+mid,d['map_id']==mid,d['position'])
        check('No scripts or rendering errors in executed app log','SCRIPT ERROR' not in (out/'ordinary.log').read_text() and 'ERROR:' not in (out/'ordinary.log').read_text())
        final=diagnostics();(out/'HOST_DIAGNOSTICS.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
        process.terminate();process.wait(timeout=5);process=None
        visual_env=env.copy();visual_env['XDG_DATA_HOME']=str(out/'visual-data')
        result=subprocess.run([str(a.godot),'--path',str(a.runtime),'--audio-driver','Dummy','--script',str(a.visual_script),'--',str(out/'visual')],env=visual_env,capture_output=True,text=True,timeout=60)
        (out/'visual.log').write_text(result.stdout+result.stderr)
        check('Actual engine scene captures complete',result.returncode==0 and (out/'visual/VISUAL_SCENES.json').exists(),result.returncode)
        check('Visual probe has no script errors','SCRIPT ERROR' not in result.stdout+result.stderr and 'ERROR:' not in result.stdout+result.stderr)
    finally:
        if process is not None:process.terminate();process.wait(timeout=8)
        server.terminate();server.wait(timeout=8)
        (out/'HOST_QA.json').write_text(json.dumps({'checks':checks,'status':'PASS' if checks and all(c['status']=='PASS' for c in checks) else 'FAIL',
            'scope':'Actual Linux X11 keyboard/mouse input and OpenGL viewport; not an Android or Galaxy execution'},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
