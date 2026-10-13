#!/usr/bin/env python3
"""Research-only localhost startup/probe. Uses an external reviewed checkout, never vendors it."""
import argparse, json, os, signal, socket, subprocess, time
from pathlib import Path

def main():
    a=argparse.ArgumentParser();a.add_argument('--source',required=True);a.add_argument('--dotnet',required=True);a.add_argument('--state',required=True);a.add_argument('--logs',required=True);args=a.parse_args()
    repo=Path(args.source).resolve();dotnet=Path(args.dotnet).resolve();state=Path(args.state).resolve();logs=Path(args.logs).resolve()
    state.mkdir(parents=True,exist_ok=True);logs.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,P1998_BIND='127.0.0.1',P1998_STATE=str(state),DOTNET_ROOT=str(dotnet.parent),DOTNET_CLI_TELEMETRY_OPTOUT='1')
    report={'scope':'Headless localhost login/name-check/character-create/handoff/world-entry only; no Windows rendering or hunting PASS','runs':[]};processes=[]
    try:
        for project,ports in [('LoginServer','3100,3101'),('Server','3105,3106')]:
            # Refuse occupied ports rather than killing another process.
            for port in map(int,ports.split(',')):
                with socket.socket() as s:s.bind(('127.0.0.1',port))
            log=(logs/('live-'+project+'.log')).open('w')
            p=subprocess.Popen([str(dotnet),str(repo/project/'bin/Debug/net8.0'/(project+'.dll')),'--ports',ports],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append((p,log))
            row={'process':project,'ports':ports,'ready':False};report['runs'].append(row)
            for _ in range(80):
                if p.poll() is not None:break
                try:
                    with socket.create_connection(('127.0.0.1',int(ports.split(',')[0])),timeout=.2):pass
                    row['ready']=True;break
                except OSError:time.sleep(.1)
        if all(r['ready'] for r in report['runs']):
            # Fixed synthetic credentials used only in this isolated throwaway state.
            r=subprocess.run([str(dotnet),str(repo/'LoginProbe/bin/Debug/net8.0/LoginProbe.dll'),'--host','127.0.0.1','--port','3100','--user','worldaudit','--pass','audit123'],cwd=repo,env=env,capture_output=True,text=True,timeout=25)
            (logs/'live-loginprobe.log').write_text(r.stdout+r.stderr);report['probe_exit']=r.returncode
            report['character_created']='create ->' in r.stdout;report['world_entry']='SUCCESS:' in r.stdout
    except Exception as e:report['error']=str(e)
    finally:
        for p,log in processes:
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGINT)
                try:p.wait(timeout=8)
                except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=3)
            log.close()
        report['result']='PASS_HEADLESS_LOGIN_ONLY' if report.get('probe_exit')==0 else 'FAIL'
        (logs/'live-login-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS_HEADLESS_LOGIN_ONLY' else 1

if __name__=='__main__':raise SystemExit(main())
