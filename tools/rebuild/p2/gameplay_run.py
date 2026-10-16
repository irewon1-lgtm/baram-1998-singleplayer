#!/usr/bin/env python3
"""Frozen P3 GUI execution on isolated loopback X11/Pulse; no hardware claims."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import time
from work_platform import snapshot, dump, digest, run_logged, empty_output

def main(a):
    empty_output(a.output)
    src=snapshot(a.project); inputs=snapshot(a.runtime)
    root=a.system_root.resolve(); out=a.output.resolve(); env=os.environ.copy()
    modules=root/'usr/lib/pulse-16.1+dfsg1/modules'
    env.update({'LD_LIBRARY_PATH':':'.join(map(str,[root/'usr/lib/x86_64-linux-gnu',root/'usr/lib/x86_64-linux-gnu/pulseaudio',modules])),
        'DISPLAY':'127.0.0.1:196','PULSE_SERVER':'tcp:127.0.0.1:4726','XAUTHORITY':str(out/'x11.auth'),
        'PULSE_RUNTIME_PATH':str(out/'pulse-runtime'),'PULSE_STATE_PATH':str(out/'pulse-state'),'PULSE_CONFIG_PATH':str(out),
        'BARAM_GAMEPLAY_RUNTIME':str(a.runtime.resolve()),'BARAM_GAMEPLAY_REPORT':str(out/'gameplay-smoke.json'),
        'BARAM_GAMEPLAY_EVIDENCE':str(out/'screens'),'GODOT_SILENCE_ROOT_WARNING':'1',
        'XDG_DATA_HOME':str(out/'isolated-data'),'XDG_CONFIG_HOME':str(out/'isolated-config')})
    if a.trace: env['BARAM_GAMEPLAY_TRACE']=str(a.trace.resolve())
    Path(env['PULSE_RUNTIME_PATH']).mkdir(mode=0o700)
    env['PATH']=str(root/'usr/bin')+os.pathsep+env['PATH']
    subprocess.run([str(root/'usr/bin/xauth'),'-f',env['XAUTHORITY'],'add',env['DISPLAY'],'MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],env=env,check=True,capture_output=True)
    (out/'x11.auth').chmod(0o600)
    (out/'pulse.conf').write_text('load-module module-native-protocol-tcp listen=127.0.0.1 port=4726 auth-anonymous=1\nload-module module-null-sink sink_name=gameplay_capture rate=48000 channels=2\nset-default-sink gameplay_capture\n')
    (out/'fonts.conf').write_text('<fontconfig><include>/etc/fonts/fonts.conf</include><dir>'+str(root/'usr/share/fonts/truetype/nanum')+'</dir></fontconfig>')
    env['FONTCONFIG_FILE']=str(out/'fonts.conf')
    processes=[]; recorder=None
    receipt={'schema':'baram.gameplay.linux-run/1','platform':'Linux Xvfb/Pulse virtual output','hardware_listening':'NOT_RUN','actual_IME':'NOT_RUN','source_before':src,'runtime_before':inputs}
    try:
        for name,cmd in [('xvfb',[str(root/'usr/bin/Xvfb'),':196','-screen','0','1280x900x24','-nolisten','unix','-nolisten','local','-listen','tcp','-auth',env['XAUTHORITY']]),
                         ('pulse',[str(root/'usr/bin/pulseaudio'),'--daemonize=no','--exit-idle-time=-1','--use-pid-file=no','--disable-shm=yes','--dl-search-path='+str(modules),'-n','-F',str(out/'pulse.conf')])]:
            log=(out/(name+'.log')).open('wb'); processes.append(subprocess.Popen(cmd,env=env,stdout=log,stderr=log))
        time.sleep(2)
        receipt['servers_alive']=[p.poll() is None for p in processes]
        if not all(receipt['servers_alive']): raise RuntimeError('Virtual output server failed')
        cmd=[str(a.godot.resolve()),'--path',str(a.project.resolve()),'--rendering-method','gl_compatibility']
        with (out/'ordinary.log').open('wb') as log:
            ordinary=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
            processes.append(ordinary)
            time.sleep(4)
            receipt['ordinary_alive_after_four_seconds']=ordinary.poll() is None
            if a.os_probe:
                from gameplay_x11 import probe
                receipt['ordinary_input_probe']=probe(env,out)
            receipt['ordinary_screen']=run_logged(['ffmpeg','-y','-f','x11grab','-video_size','1280x900','-i',env['DISPLAY'],'-frames:v','1',str(out/'ordinary.png')],out/'ordinary-capture.log',env,15)
            ordinary.terminate(); ordinary.wait(timeout=10)
        if a.os_probe and receipt.get('ordinary_input_probe',{}).get('status')=='PASS':
            from gameplay_x11 import resume_probe
            with (out/'ordinary-restart.log').open('wb') as log:
                ordinary=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
                processes.append(ordinary); time.sleep(4)
                receipt['ordinary_restart_probe']=resume_probe(env,out,receipt['ordinary_input_probe'])
                ordinary.terminate();ordinary.wait(timeout=10)
        if a.video:
            log=(out/'video.log').open('wb')
            recorder=subprocess.Popen(['ffmpeg','-y','-f','x11grab','-framerate','12','-video_size','1280x900','-i',env['DISPLAY'],
                '-f','pulse','-i','gameplay_capture.monitor','-c:v','libx264','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p','-c:a','aac',str(out/'gameplay.mp4')],env=env,stdout=log,stderr=log)
            time.sleep(1)
        receipt['application']=run_logged(cmd+['--','--gameplay-smoke'],out/'application.log',env,a.timeout)
        receipt['result']='PASS' if receipt['application']['exit_code']==0 else 'FAIL_OR_TIMEOUT'
        if a.os_probe and (receipt.get('ordinary_input_probe',{}).get('status')!='PASS' or receipt.get('ordinary_restart_probe',{}).get('status')!='PASS'):
            receipt['result']='FAIL_ORDINARY_INPUT_OR_RESTART'
        report=out/'gameplay-smoke.json'
        if report.exists(): receipt['report_sha256']=digest(report)
    except Exception as exc:
        receipt['result']='FAILED'; receipt['reason']=str(exc)
    finally:
        if recorder and recorder.poll() is None:
            recorder.send_signal(2)
            try:recorder.wait(timeout=10)
            except subprocess.TimeoutExpired:recorder.kill();recorder.wait()
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
    receipt['sources_unchanged']=src==snapshot(a.project)
    receipt['runtime_unchanged']=inputs==snapshot(a.runtime)
    receipt['artifacts']={p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in out.glob('*') if p.is_file() and p.suffix in ['.mp4','.png','.json']}
    dump(out/'RUN_RECEIPT.json',receipt)
    print(receipt['result'])
    return 0 if receipt['result']=='PASS' and receipt['sources_unchanged'] and receipt['runtime_unchanged'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['project','runtime','godot','system-root','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--trace',type=Path)
    p.add_argument('--video',action='store_true')
    p.add_argument('--os-probe',action='store_true')
    p.add_argument('--timeout',type=int,default=180)
    raise SystemExit(main(p.parse_args()))
