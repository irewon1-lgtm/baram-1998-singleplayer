#!/usr/bin/env python3
"""Run the actual priority inspector with isolated loopback X11/Pulse output."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import time
from work_platform import snapshot, dump, digest, run_logged, empty_output

def main(a):
    empty_output(a.output)
    src=snapshot(a.project);inputs=snapshot(a.runtime)
    root=a.system_root.resolve();out=a.output.resolve();env=os.environ.copy()
    modules=root/'usr/lib/pulse-16.1+dfsg1/modules'
    env.update({'LD_LIBRARY_PATH':':'.join(map(str,[root/'usr/lib/x86_64-linux-gnu',root/'usr/lib/x86_64-linux-gnu/pulseaudio',modules])),
        'DISPLAY':'127.0.0.1:196','PULSE_SERVER':'tcp:127.0.0.1:4726','XAUTHORITY':str(out/'x11.auth'),
        'PULSE_RUNTIME_PATH':str(out/'pulse-runtime'),'PULSE_STATE_PATH':str(out/'pulse-state'),'PULSE_CONFIG_PATH':str(out),
        'BARAM_P2_RUNTIME':str(a.runtime.resolve()),'BARAM_P2_REPORT':str(out/'priority-smoke.json'),'GODOT_SILENCE_ROOT_WARNING':'1'})
    Path(env['PULSE_RUNTIME_PATH']).mkdir(mode=0o700)
    env['PATH']=str(root/'usr/bin')+os.pathsep+env['PATH']
    subprocess.run([str(root/'usr/bin/xauth'),'-f',env['XAUTHORITY'],'add',env['DISPLAY'],'MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],env=env,check=True,capture_output=True)
    (out/'x11.auth').chmod(0o600)
    (out/'pulse.conf').write_text('load-module module-native-protocol-tcp listen=127.0.0.1 port=4726 auth-anonymous=1\nload-module module-null-sink sink_name=p2_capture rate=48000 channels=2\nset-default-sink p2_capture\n')
    (out/'fonts.conf').write_text('<fontconfig><include>/etc/fonts/fonts.conf</include><dir>'+str(root/'usr/share/fonts/truetype/nanum')+'</dir></fontconfig>')
    env['FONTCONFIG_FILE']=str(out/'fonts.conf')
    processes=[];receipt={'schema':'baram.priority.linux_run/1','platform':'Linux Xvfb/Pulse virtual output','hardware_listening':'NOT_RUN','native_platforms':'NOT_RUN','source_before':src,'runtime_before':inputs}
    try:
        for name,cmd in [('xvfb',[str(root/'usr/bin/Xvfb'),':196','-screen','0','1280x900x24','-nolisten','unix','-nolisten','local','-listen','tcp','-auth',env['XAUTHORITY']]),
                         ('pulse',[str(root/'usr/bin/pulseaudio'),'--daemonize=no','--exit-idle-time=-1','--use-pid-file=no','--disable-shm=yes','--dl-search-path='+str(modules),'-n','-F',str(out/'pulse.conf')])]:
            log=(out/(name+'.log')).open('wb');processes.append(subprocess.Popen(cmd,env=env,stdout=log,stderr=log))
        time.sleep(2)
        receipt['servers_alive']=[p.poll() is None for p in processes]
        if not all(receipt['servers_alive']):
            receipt['result']='BLOCKED_VIRTUAL_SERVERS'
        else:
            flag='--p2-priority-smoke' if a.smoke=='priority' else '--p2-original-smoke'
            cmd=[str(a.godot.resolve()),'--path',str(a.project.resolve()),'--rendering-method','gl_compatibility','--',flag]
            receipt['application']=run_logged(cmd,out/'application.log',env,a.timeout)
            receipt['result']='EXIT_'+str(receipt['application']['exit_code'])
            report=out/'priority-smoke.json'
            if report.exists():receipt['report_sha256']=digest(report)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
    receipt['sources_unchanged']=src==snapshot(a.project)
    receipt['runtime_unchanged']=inputs==snapshot(a.runtime)
    dump(out/'RUN_RECEIPT.json',receipt)
    print(receipt.get('result'))
    return 0 if receipt.get('application',{}).get('exit_code')==0 and receipt['sources_unchanged'] and receipt['runtime_unchanged'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['project','runtime','godot','system-root','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--timeout',type=int,default=120)
    p.add_argument('--smoke',choices=['priority','original'],default='priority')
    raise SystemExit(main(p.parse_args()))
