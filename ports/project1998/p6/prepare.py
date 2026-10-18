#!/usr/bin/env python3
"""Add P6 presentation and the user-authorized tutorial-bypass repair to P5."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPSULE = 'a354ffd0e90a3d1ca447ad51f63e33f634e6a99d95e00890c866609f710507f6'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    for key in ['source','output','font-dir','sqlite-android-nupkg','converted','ko-source','originals']:
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--references',type=Path,required=True)
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
    c=runtime/'GameCore.cs';c.write_text(c.read_text().replace('build = "0.0.5-p5"','media = _session.P6Media, poses = _session.P6Poses, texts = _session.P6Texts, effects = _session.P6Effects(), stats = _session.P6Stats(), build = "0.0.6-p6-fix2"').replace('_world = new World();','_world = new World();\n        _world.P6PlaceAccessibleNpcs(Godot.FileAccess.GetFileAsString("res://p6/art/npc-placements.json"));'))
    shutil.copyfile(HERE/'RepairCore.cs',runtime/'RepairCore.cs')
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
    shutil.copyfile(HERE/'RepairSession.cs',server/'P6.Repair.cs')
    shutil.copyfile(HERE/'Placement.cs',server/'P6.Placement.cs')
    for name,signature,hook in [
        ('Session.Dialog.cs','private void SendMiniText(string text, ushort type = 3)','P6ObserveText(type == 0 ? "chat" : "mini", 0, text);'),
        ('Session.GmCommands.cs','private void SendSpeech(byte chatType, uint id, byte[] msg)','P6ObserveText("chat", id, System.Text.Encoding.ASCII.GetString(msg));')]:
        target=server/name;text=target.read_text();needle='    '+signature+'\n    {'
        assert text.count(needle)==1
        text=text.replace(needle,needle+'\n        '+hook+' // P6 outgoing text observer')
        target.write_text(text)
    target=server/'Session.Combat.cs';text=target.read_text()
    needle='    private void SendAction(uint id, ActionType type, ushort time, byte param) =>\n'
    original=needle+'        SendMap(ServerOp.Action, _gameInc++, ActionBody(id, type, time, param),\n                $"action(0x1A) type={(byte)type} time={time}");'
    replacement=needle.replace(' =>','')+'    {\n        P6ObserveAction(id, type, time); // P6 outgoing action observer\n'+original[len(needle):]+'\n    }'
    assert text.count(original)==1;text=text.replace(original,replacement);target.write_text(text)
    subprocess.run([sys.executable,str(HERE/'repair_art.py'),'--originals',str(a.originals),'--runtime',str(runtime),'--audit',str(out/'REPAIR_ART_AUDIT.json')],check=True)
    subprocess.run([sys.executable,str(HERE/'reference_art.py'),'--source',str(a.source),'--originals',str(a.originals),'--runtime',str(runtime),'--references',str(a.references),'--audit',str(out/'REFERENCE_ART_AUDIT.json')],check=True)
    (out/'P6_SOURCE_AUDIT.json').write_text(json.dumps({'capsule_sha256':CAPSULE,'source':'P5 preparation + reversible outgoing sound/action observers; read-only stats; user-authorized offline tutorial skip',
        'save_identity':'unchanged P5 v2; profile-p6.json is a separate optional display alias/preferences file',
        'adapter_sha256':sha(server/'P4.Adapter.cs'),'media_sha256':sha(server/'P6.Media.cs'),
        'repair_session_sha256':sha(server/'P6.Repair.cs'),'repair_core_sha256':sha(runtime/'RepairCore.cs'),
        'art_audit_sha256':sha(out/'REPAIR_ART_AUDIT.json')},indent=2)+'\n')
    print('P6_PREPARED',out)

if __name__=='__main__':main()
