#!/usr/bin/env python3
"""Own a private X11 display, exercise the real game, capture screen and relaunch."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
import wave
from PIL import Image, ImageChops, ImageGrab

ROOT = Path(__file__).resolve().parents[1]


def execute(args):
    directory = Path(args.out).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1')
    for name, folder in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
        p = directory / folder
        p.mkdir(exist_ok=True)
        environment[name] = str(p)
    Path('/tmp/.X11-unix').mkdir(mode=0o1777, exist_ok=True)
    read_fd, write_fd = os.pipe()
    display_log = (directory / 'xvfb.log').open('w')
    server = subprocess.Popen([args.xvfb,'-displayfd',str(write_fd),'-screen','0','960x640x24','-nolisten','tcp'],
        pass_fds=(write_fd,),stdout=display_log,stderr=subprocess.STDOUT,env=environment)
    os.close(write_fd)
    processes = []
    report = {'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope':'REAL_GAME_X11_WINDOW_AND_GODOT_INPUT_EVENTS', 'runs':[], 'status':'NOT_RUN'}
    try:
        if not select.select([read_fd], [], [], 15)[0]:
            raise RuntimeError('Xvfb readiness timeout')
        display = os.read(read_fd,32).decode().strip()
        if not display.isdecimal():
            raise RuntimeError('Invalid X11 display')
        environment['DISPLAY'] = ':' + display
        modes = args.modes.split(',')
        for mode in modes:
            folder = directory / ('primary' if mode in ('primary','restart') else mode)
            folder.mkdir(exist_ok=True)
            save = folder / 'character.json'
            if mode != 'restart' and save.exists():
                raise RuntimeError('Use a fresh evidence directory; existing saves are preserved')
            command = [args.godot,'--path',str(ROOT/'game'),'--display-driver','x11','--rendering-method','gl_compatibility',
                '--audio-driver','Dummy','--','--assets='+str(Path(args.assets).resolve()),'--save='+str(save),
                '--exercise='+mode,'--evidence='+str(folder)]
            log = (folder / (mode+'.log')).open('w')
            process = subprocess.Popen(command,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            processes.append(process)
            deadline = time.monotonic() + args.timeout
            xchecks = []
            pending = b''
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise RuntimeError('Game exercise timed out: '+mode)
                if not select.select([process.stdout],[],[],0.2)[0]:
                    continue
                pending += os.read(process.stdout.fileno(),65536)
                while b'\n' in pending:
                    raw,pending = pending.split(b'\n',1)
                    line = raw.decode('utf-8',errors='replace')+'\n'
                    log.write(line);log.flush()
                    if 'SCRIPT ERROR:' in line or line.startswith('ERROR:'):
                        raise RuntimeError('Runtime error: '+line.strip())
                    if line.startswith('SCREEN_CHECK '):
                        print(mode,line.strip(),flush=True)
                    if line.startswith('SCREEN_CAPTURE_READY '):
                        name = line.strip().split(' ',1)[1]
                        screen = ImageGrab.grab(xdisplay=environment['DISPLAY']).convert('RGB')
                        path = folder / (name+'-x11.png')
                        screen.save(path)
                        viewport = Image.open(folder/(name+'.png')).convert('RGB')
                        difference = ImageChops.difference(screen,viewport)
                        near = sum(max(pixel) < 8 for pixel in difference.getdata())
                        fraction = near/(960*640)
                        colors = len(screen.getcolors(960*640) or [])
                        xchecks.append({'name':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                        'matching_screen_fraction':fraction,'distinct_colors':colors,
                                        'status':'PASS' if fraction>.70 and colors>128 else 'FAIL'})
            remainder = (pending+process.stdout.read()).decode('utf-8',errors='replace')
            log.write(remainder);log.close()
            result_file = folder/(mode+'-report.json')
            if not result_file.exists():
                raise RuntimeError('Game did not produce an executed report: '+mode)
            result = json.loads(result_file.read_text())
            audio_path = folder/'mixed-audio.wav'
            audio_check = {'status':'NOT_RUN'}
            if audio_path.exists():
                with wave.open(str(audio_path)) as audio:
                    raw = audio.readframes(audio.getnframes())
                    import array, math
                    samples = array.array('h',raw) if audio.getsampwidth()==2 else array.array('B',raw)
                    offset=0 if audio.getsampwidth()==2 else 128
                    rms=math.sqrt(sum((v-offset)**2 for v in samples)/max(1,len(samples)))
                    audio_check={'status':'PASS_PCM_SIGNAL' if len(samples)>0 and rms>0 else 'FAIL',
                                 'samples':len(samples),'rms':rms,'driver':'Dummy','audible_human_review':'NOT_RUN'}
            entry={'mode':mode,'exit_code':process.returncode,'game_report':str(result_file),'game_status':result['status'],
                   'x11_captures':xchecks,'audio_mix':audio_check,'argv':command,
                   'registered_tiles':result['registered_tiles'],'checks':len(result['checks'])}
            report['runs'].append(entry)
            if process.returncode or result['status']!='PASS_EXECUTED_SCREEN_INPUT' or not xchecks or any(c['status']!='PASS' for c in xchecks):
                raise RuntimeError('Executed game check failed; inspect preserved '+mode+' evidence')
        report['status']='PASS_EXECUTED_SCREEN_INPUT_AND_RESTART' if 'restart' in modes else 'PASS_EXECUTED_SCREEN_INPUT'
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,KeyboardInterrupt) as exc:
        report.update(status='FAIL',error=str(exc))
        print('FAIL',str(exc),flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        os.close(read_fd)
        if server.poll() is None:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
        display_log.close()
        report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [ROOT/'game/main.gd',ROOT/'game/exercise.gd',ROOT/'game/rules.gd',ROOT/'game/save_store.gd',Path(__file__).resolve()]}
        Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(report['status'],flush=True)
    return 0 if report['status'].startswith('PASS_') else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--report',required=True)
    p.add_argument('--modes',default='primary,restart,class-1,class-2,class-3')
    p.add_argument('--godot',default='godot')
    p.add_argument('--xvfb',default='/workspace/baram-private/setup/x11/usr/bin/Xvfb')
    p.add_argument('--timeout',type=int,default=300)
    raise SystemExit(execute(p.parse_args()))
