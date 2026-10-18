#!/usr/bin/env python3
"""Add presentation-only P6 to the reproducible P5 source/content build."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPSULE = 'a354ffd0e90a3d1ca447ad51f63e33f634e6a99d95e00890c866609f710507f6'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    for key in ['source','output','font-dir','sqlite-android-nupkg','converted','ko-source','originals']:
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(); out=a.output.resolve()
    command=[sys.executable,str(HERE.parent/'p5/prepare.py')]
    for k in ['source','output','font_dir','sqlite_android_nupkg','converted']:
        command += ['--'+k.replace('_','-'),str(getattr(a,k))]
    subprocess.run(command,check=True)
    runtime=out/'runtime'
    assert sha(runtime/'capsule.json')==CAPSULE,'P6 must retain the P5 save/content identity'
    shutil.rmtree(runtime/'p5');shutil.copytree(HERE/'client',runtime/'p6')
    subprocess.run([sys.executable,str(HERE/'catalog.py'),'--source',str(a.source),'--ko-source',str(a.ko_source),
                    '--output',str(runtime/'p6/locale.json'),'--audit',str(out/'LOCALIZATION_AUDIT.json')],check=True)
    subprocess.run([sys.executable,str(HERE/'audio.py'),'--originals',str(a.originals),'--output',str(runtime/'audio'),
                    '--audit',str(out/'AUDIO_AUDIT.json')],check=True)
    b=runtime/'Bootstrap.cs';b.write_text(b.read_text().replace('res://p5/main.tscn','res://p6/main.tscn').replace('P5 시작 실패','P6 시작 실패'))
    c=runtime/'GameCore.cs';c.write_text(c.read_text().replace('build = "0.0.5-p5"','media = _session.P6Media, build = "0.0.6-p6"'))
    project=runtime/'project.godot'
    project.write_text(project.read_text().replace('Project1998 P5','Project1998 P6').replace('window/handheld/orientation=0',
        'window/handheld/orientation=6\nwindow/stretch/aspect="expand"'))
    # Outgoing transport observers only. The exact inserted text is reversible
    # by audit_source.py; every original statement remains intact.
    server=out/'source/Server';shutil.copyfile(HERE/'Media.cs',server/'P6.Media.cs')
    target=server/'Session.Entity.cs';text=target.read_text()
    needle='        var d = new List<byte> { 0x00, 0x03 };'
    hook='        P6ObserveSound(soundId, entityId, volume); // P6 outgoing media observer\n'
    assert text.count(needle)==1;text=text.replace(needle,hook+needle);target.write_text(text)
    (out/'P6_SOURCE_AUDIT.json').write_text(json.dumps({'capsule_sha256':CAPSULE,'source':'P5 preparation + reversible outgoing sound observer',
        'save_identity':'unchanged P5 v2; profile-p6.json is a separate optional display alias/preferences file',
        'adapter_sha256':sha(server/'P4.Adapter.cs'),'media_sha256':sha(server/'P6.Media.cs')},indent=2)+'\n')
    print('P6_PREPARED',out)

if __name__=='__main__':main()
