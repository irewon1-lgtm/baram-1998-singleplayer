#!/usr/bin/env python3
"""Run one bounded X11/llvmpipe process using restored r13 tools."""
import argparse, datetime, json, os, signal, socket, subprocess, sys, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--attempt', required=True)
p.add_argument('--timeout', type=int, default=3600)
p.add_argument('--tools', type=Path, default=Path(os.environ['P1998_TOOLCHAIN']))
p.add_argument('command', nargs=argparse.REMAINDER)
a = p.parse_args()
cmd = a.command[1:] if a.command[:1] == ['--'] else a.command
if not cmd:
    p.error('Missing actual command.')
tools = a.tools.resolve()
sysroot = tools / 'sysroot'
logs = Path(__file__).resolve().parents[3] / 'evidence/r20-performance/display' / a.attempt
logs.mkdir(parents=True, exist_ok=False)
display = None
for number in range(120, 220):
    if Path('/tmp/.X' + str(number) + '-lock').exists():
        continue
    with socket.socket() as stream:
        try:
            stream.bind(('127.0.0.1', 6000 + number))
        except OSError:
            continue
    display = number
    break
if display is None:
    raise SystemExit('No unused bounded X11 display.')
env = os.environ | {
    'DISPLAY': '127.0.0.1:' + str(display),
    'LD_LIBRARY_PATH': str(sysroot / 'usr/lib/x86_64-linux-gnu') + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else ''),
    'PATH': str(tools / 'dotnet') + ':' + str(sysroot / 'usr/bin') + ':' + os.environ['PATH'],
    'DOTNET_ROOT': str(tools / 'dotnet'), 'LIBGL_ALWAYS_SOFTWARE': '1',
    'LP_NUM_THREADS': '2', 'GODOT_SILENCE_ROOT_WARNING': '1',
}
xcmd = [str(sysroot / 'usr/bin/Xvfb'), ':' + str(display), '-screen', '0', '1280x800x24',
        '-nolisten', 'unix', '-listen', 'tcp', '-ac', '-noreset',
        '-xkbdir', str(sysroot / 'usr/share/X11/xkb'), '-fp', str(sysroot / 'usr/share/fonts/X11/misc')]
receipt = {
    'status': 'RUNNING', 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'command': cmd, 'Xvfb_command': xcmd, 'DISPLAY': env['DISPLAY'],
    'renderer': 'Actual Mesa llvmpipe OpenGL on Xvfb; audio selection is caller owned',
    'scope': 'Process execution only. Caller must inspect actual checks; physical Android NOT_RUN.',
}
(logs / 'launch.json').write_text(json.dumps(receipt, indent=2) + '\n')
child = None
with (logs / 'xvfb.log').open('w') as xlog:
    xserver = subprocess.Popen(xcmd, env=env, stdout=xlog, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(100):
            if xserver.poll() is not None:
                raise RuntimeError('Own Xvfb exited before display readiness.')
            try:
                with socket.create_connection(('127.0.0.1', 6000 + display), timeout=.1):
                    pass
                break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Own Xvfb readiness timeout.')
        receipt['child_spawn_dispatch_monotonic_ns'] = time.monotonic_ns()
        child = subprocess.Popen(cmd, env=env, start_new_session=True)
        try:
            code = child.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
            code = 124
        receipt.update(status='PROCESS_EXIT_ZERO_CHECK_ACTUAL_REPORT' if code == 0 else 'PROCESS_FAILED', exit_code=code)
    except BaseException as error:
        receipt.update(status='DISPLAY_OR_LAUNCH_FAILURE', error=repr(error))
        code = 1
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=10)
    finally:
        if xserver.poll() is None:
            os.killpg(xserver.pid, signal.SIGTERM)
            try:
                xserver.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(xserver.pid, signal.SIGKILL)
                xserver.wait(timeout=10)
        receipt['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (logs / 'launch.json').write_text(json.dumps(receipt, indent=2) + '\n')
sys.exit(code)
