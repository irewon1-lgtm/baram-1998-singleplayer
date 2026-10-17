#!/usr/bin/env python3
"""Unaccelerated ordinary Linux GUI play through OS XTEST only.

The operator reads already committed user saves and content as observations. It
never writes a save, grants progress, invokes a game method, or injects engine
events. Synthetic mouse/keys are explicitly not human, Korean IME, Windows, or
Android evidence. Run inside toolchain/run_gui.py in the same namespace.
"""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p2'))
from gameplay_x11 import X11, checkpoints


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--godot', type=Path, required=True)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--pack', type=Path, help='Run an exact exported PCK; runtime remains read-only observation/fingerprint input')
    p.add_argument('--candidate-file', type=Path, action='append', default=[], help='Hash associated delivery file without executing a different platform')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=2700)
    p.add_argument('--name', default='osjourney')
    p.add_argument('--job', default='주술사', choices=['전사', '도적', '주술사', '도사'])
    p.add_argument('--record', action='store_true')
    p.add_argument('--user-dir-name', default='baram_rebuild_gameplay_001', help='Actual Godot custom user directory for the tested project/pack')
    p.add_argument('--resume-user-dir-name', default='baram_rebuild_gameplay_001', help='Original natural-session data directory name, copied without payload edits')
    p.add_argument('--resume-data', type=Path, help='Byte-identical copy of a completed naturally earned isolated session; no payload edits or grants')
    p.add_argument('--continuous-after-preflight', action='store_true', help='Keep same process and raw recording after successful natural ability preflight, then run requested continuous stress duration')
    p.add_argument('--targeted-followup', action='store_true', help='Reserve actual fire/return materials, use visible dialogue scrolling, then demonstrate ordinary learned projectile and return')
    p.add_argument('--compare-recording', action='store_true', help='Run 30s of the same ordinary input with recording off and on before journey')
    p.add_argument('--advance-hunting', action='store_true', help='After natural level 8 and actual learned skills, walk to the existing rat cave')
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        raise ValueError('Fresh isolated output required: ' + str(out))
    out.mkdir(parents=True)
    operator_source=Path(__file__).read_bytes()
    (out/'operator-source.py').write_bytes(operator_source)
    # A workspace sync can replace an open destination inode while a long tool
    # session runs. Record open-FD streams outside the synced workspace and only
    # publish complete, externally validated files after their writers close.
    temporary_root=Path(tempfile.mkdtemp(prefix='baram-ordinary-'))
    env = os.environ.copy()
    env.update(XDG_DATA_HOME=str(temporary_root / 'data'), XDG_CONFIG_HOME=str(temporary_root / 'config'),
               XAUTHORITY='', GODOT_SILENCE_ROOT_WARNING='1',
               BARAM_GAMEPLAY_RUNTIME=str(a.runtime.resolve()),
               BARAM_PLAYABILITY_TRACE=str(temporary_root / 'frame-timeline.jsonl'))
    if any('/' in name or '..' in name for name in [a.user_dir_name,a.resume_user_dir_name]):raise ValueError('Simple custom user directory names required')
    if a.resume_data:
        shutil.copytree(a.resume_data.resolve()/a.resume_user_dir_name,temporary_root/'data'/a.user_dir_name,dirs_exist_ok=True)
    cpath = temporary_root / 'data' / a.user_dir_name / 'gameplay-checkpoints.jsonl'
    if a.resume_data:cpath.unlink(missing_ok=True)  # copied instrumentation log; earned save bytes remain untouched
    saves = cpath.parent / 'gameplay-p3/characters'
    content = json.loads((a.runtime / 'gameplay_content.json').read_text())
    if a.pack:
        env.pop('BARAM_GAMEPLAY_RUNTIME',None);env.pop('BARAM_P2_RUNTIME',None)
    command = [str(a.godot.resolve()), '--audio-driver', 'Dummy'] + (['--main-pack',str(a.pack.resolve())] if a.pack else ['--path', str(a.project.resolve())])
    start = time.monotonic()
    input_path = temporary_root / 'os-input-timeline.jsonl'
    observations = []
    result = {'scope': 'Ordinary Linux OpenGL GUI, unaccelerated XTEST mouse/keys; read-only committed saves; no grants or callbacks. Not human/native Windows/Android/IME/audio listening.',
              'requested_seconds': a.seconds, 'checks': [], 'observations': observations,
              'operator_sha256': hashlib.sha256(operator_source).hexdigest(),
              'isolated_session_directory': str(temporary_root),
              'continued_naturally_earned_data': {'directory':str(a.resume_data.resolve()),'from_user_dir':a.resume_user_dir_name,'to_user_dir':a.user_dir_name,'method':'Byte-identical continuity import between isolated Linux test directories; not authenticated sync. No payload edits or grants.','files':[{'file':str(f.relative_to(a.resume_data)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(a.resume_data.rglob('*')) if f.is_file()]} if a.resume_data else None,
              'targeted_followup':a.targeted_followup,
              'exact_pack_sha256': hashlib.sha256(a.pack.read_bytes()).hexdigest() if a.pack else None,
              'associated_candidate_files': [{'file':str(f.resolve()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in a.candidate_file],
              'runtime_manifest_sha256': hashlib.sha256((a.runtime / 'runtime.json').read_bytes()).hexdigest(),
              'content_sha256': hashlib.sha256((a.runtime / 'gameplay_content.json').read_bytes()).hexdigest(),
              'project_source_sha256': {str(f.relative_to(a.project)): hashlib.sha256(f.read_bytes()).hexdigest()
                                        for f in sorted(a.project.rglob('*')) if f.is_file() and f.suffix in ['.gd', '.godot', '.tscn']},
              'environment': {'platform': sys.platform, 'display': env.get('DISPLAY'), 'screen': '1600x1000', 'game_viewport': '1100x720', 'recording_fps': 30 if a.record else 0, 'audio': 'Dummy'}}
    process = None
    recorder = None
    x = None
    savefile = None
    hunting_map = 'gp:map:south_field'
    def log(kind, **data):
        row = {'kind': kind, 'wall_unix_ns': time.time_ns(), 'operator_elapsed_s': round(time.monotonic() - start, 3), **data}
        with input_path.open('a') as input_log:
            input_log.write(json.dumps(row, ensure_ascii=False) + '\n')
        return row
    def observe(name, **details):
        if process and process.poll() is None:
            try:
                status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in Path('/proc',str(process.pid),'status').read_text().splitlines() if ':' in line}
                details['os_process_memory']={k:status[k] for k in ['VmRSS','VmHWM','VmSize','Threads'] if k in status}
            except OSError:pass
        row = log('observation', name=name, **details)
        observations.append(row)
        (out / 'progress.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
        print(json.dumps(row, ensure_ascii=False), flush=True)
    def check(name, okay, details=None):
        result['checks'].append({'id': name, 'status': 'NOT_RUN' if okay is None else 'PASS' if okay else 'FAIL', 'details': details})
    def run(*args):
        subprocess.run(['xdotool', *map(str, args)], env=env, check=True, capture_output=True, timeout=10)
    def focus(): run('windowfocus', '--sync', x.window)
    def click_xy(px, py, description=''):
        focus(); log('mouse_click', x=int(px), y=int(py), description=description)
        run('mousemove', '--window', x.window, int(px), int(py)); run('click', '1'); time.sleep(.18)
    def key(name, hold=.05):
        focus(); log('key', key=name, hold_s=hold)
        run('keydown', '--clearmodifiers', name); time.sleep(hold); run('keyup', name); time.sleep(.04)
    def latest_layout():
        for row in reversed(checkpoints(cpath)):
            if row.get('stage') == 'ui_layout': return row['details']
        return {}
    def button(prefix, exact=False, optional=False):
        controls=latest_layout().get('controls', [])
        footer=next((c['rect'] for c in controls if c['text']=='닫기 / 취소'),None)
        pager=next((c['rect'] for c in controls if c['text']=='이전'),None)
        close_x=next((c['rect'] for c in controls if c['text']=='X'),None)
        for item in controls:
            if item['text'] == prefix if exact else item['text'].startswith(prefix):
                rect = item['rect']
                if rect[1] < 0 or rect[1]+rect[3] > 720:
                    continue
                if footer and close_x and item['text'] not in ['X','닫기 / 취소','다음','이전']:
                    if abs(rect[0]-footer[0])>=1:continue  # field controls behind the ordinary modal are not OS targets
                    clip_top=close_x[1]+close_x[3]+4
                    clip_bottom=(pager[1] if pager else footer[1])-4
                    if rect[1]<clip_top or rect[1]+rect[3]>clip_bottom:continue
                click_xy(rect[0]+rect[2]/2, rect[1]+rect[3]/2, item['text'])
                return item['text']
        if optional: return None
        raise RuntimeError('Visible OS target absent: ' + prefix)
    def wait_stage(stage, since=0, timeout=30):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            rows=checkpoints(cpath)
            found=[r for r in rows[since:] if r.get('stage')==stage]
            if found: return found[-1]
            if process.poll() is not None: raise RuntimeError('Game process exited before '+stage)
            time.sleep(.1)
        raise TimeoutError('Stage: '+stage)
    def state(settle=0):
        if settle: time.sleep(settle)
        if process.poll() is not None: raise RuntimeError('Game process exited')
        if (out/'STOP_OPERATOR').exists(): raise RuntimeError('Operator cancellation requested; product result not established')
        return json.loads(savefile.read_text())['payload']
    def capture(name):
        path=out/(name+'.png')
        r=subprocess.run(['ffmpeg','-loglevel','error','-y','-f','x11grab','-video_size','1600x1000','-i',env['DISPLAY'],'-frames:v','1',str(path)],env=env,capture_output=True,timeout=20)
        log('screenshot',name=name,success=r.returncode==0)
        return str(path)
    def start_recorder():
        nonlocal recorder
        recorder=subprocess.Popen(['ffmpeg','-loglevel','warning','-y','-f','x11grab','-draw_mouse','1','-framerate','30','-video_size','1600x1000','-i',env['DISPLAY'],'-c:v','libx264','-preset','ultrafast','-crf','29','-pix_fmt','yuv420p',str(temporary_root/'ordinary-unedited.mkv')],env=env,stdout=(temporary_root/'recorder.log').open('wb'),stderr=subprocess.STDOUT)
        log('video_recording_started',recorder_pid=recorder.pid)
    def recording_comparison(recording):
        observe('recording_comparison_start',recording=recording,committed_character=state()['character'])
        began=time.monotonic()
        while time.monotonic()-began<30:
            for direction in ['Left','Right','Up','Down']:
                key(direction,.32);time.sleep(.6)
        observe('recording_comparison_end',recording=recording,elapsed_s=time.monotonic()-began,committed_character=state(3.3)['character'])
    def world_click(target, character, description='ground'):
        layout=latest_layout()
        rect=layout.get('view_rect')
        if not rect:
            attack=next(c['rect'] for c in layout['controls'] if c['text']=='공격')
            rect=[8,39,attack[0]+100-8,attack[1]+72-39]
        zoom=layout.get('view_zoom',1.65)
        # The ordinary camera clamps at map edges and centers small maps. A
        # character-relative projection aimed at the wrong ground near exits.
        # Reproduce only the public canvas transform using read-only content
        # and a settled committed character; never invoke the game's methods.
        m=content['maps'][character['map_id']]
        extent=(m['width']*24,m['height']*24)
        half=(rect[2]/(2*zoom),rect[3]/(2*zoom))
        focus=[character['x']*24+12,character['y']*24+12]
        for axis in (0,1):
            focus[axis]=max(half[axis],min(extent[axis]-half[axis],focus[axis])) if extent[axis]>=2*half[axis] else extent[axis]/2
        px=rect[0]+rect[2]/2+(target[0]*24+12-focus[0])*zoom
        py=rect[1]+rect[3]/2+(target[1]*24+12-focus[1])*zoom
        px=max(rect[0]+12,min(rect[0]+rect[2]-12,px))
        py=max(rect[1]+12,min(rect[1]+rect[3]-12,py))
        # Action buttons cover only the lower-right corner, not the entire
        # bottom edge where real map exits may sit.
        if px>rect[0]+rect[2]-112 and py>rect[1]+rect[3]-140:
            px=rect[0]+rect[2]-120
        click_xy(px,py,description)
    def grid_route(payload, destination, reach=0):
        c=payload['character']; m=content['maps'][c['map_id']]
        origin=(int(c['x']),int(c['y'])); destination=tuple(map(int,destination))
        blocked={tuple(v) for v in m.get('blocked',[])}
        blocked|={(int(n['x']),int(n['y'])) for n in content['npcs'].values() if n['map_id']==c['map_id']}
        blocked|={(int(m['x']),int(m['y'])) for m in payload['monsters'].values() if m['map_id']==c['map_id'] and m['alive'] and (int(m['x']),int(m['y'])) not in [origin,destination]}
        exits={(int(e['x']),int(e['y'])) for e in m.get('exits',[])}
        q=deque([origin]); previous={origin:origin}; found=None
        while q:
            at=q.popleft()
            if abs(at[0]-destination[0])+abs(at[1]-destination[1])<=reach:
                found=at; break
            for dx,dy in [(0,-1),(1,0),(0,1),(-1,0)]:
                n=(at[0]+dx,at[1]+dy)
                if n in previous or n in blocked or not(0<=n[0]<m['width'] and 0<=n[1]<m['height']): continue
                if n in exits and n!=destination: continue
                previous[n]=at; q.append(n)
        if found is None: return []
        route=[]
        while found!=origin: route.append(found); found=previous[found]
        return route[::-1]
    def walk_to(destination, reach=0, expected_map=None, limit=70):
        end=time.monotonic()+limit; initial_map=state()['character']['map_id']; stagnant=0; last=None
        while time.monotonic()<end:
            s=state(3.25); c=s['character']
            if expected_map and c['map_id']==expected_map: return True
            if c['map_id']!=initial_map: return not expected_map
            if abs(c['x']-destination[0])+abs(c['y']-destination[1])<=reach: return True
            route=grid_route(s,destination,reach)
            if not route: return False
            pos=(c['x'],c['y']); stagnant=stagnant+1 if pos==last else 0; last=pos
            if stagnant>=4: observe('navigation_stagnant',character=c,destination=destination); return False
            # Only tap actually visible ground: the game's normal pathfinder then walks there.
            visible=[t for t in route if abs(t[0]-c['x'])<=5 and abs(t[1]-c['y'])<=3]
            world_click(visible[-1] if visible else route[0],c,'ordinary ground navigation')
        return False
    def go_map(target):
        c=state()['character']
        if c['map_id']==target: return True
        q=deque([c['map_id']]); prev={c['map_id']:None}; edges={}
        while q:
            m=q.popleft()
            if m==target: break
            for e in content['maps'][m].get('exits',[]):
                if e['to_map'] not in prev: prev[e['to_map']]=m; edges[e['to_map']]=e; q.append(e['to_map'])
        if target not in prev: return False
        path=[]; m=target
        while prev[m] is not None: path.append(edges[m]); m=prev[m]
        for e in path[::-1]:
            if not walk_to((e['x'],e['y']),expected_map=e['to_map'],limit=110): return False
            observe('map_entered',map_id=e['to_map'],character=state()['character'])
        return True
    def talk(name):
        npc=next(n for n in content['npcs'].values() if n['name']==name)
        if not go_map(npc['map_id']): return False
        if not walk_to((npc['x'],npc['y']),reach=int(npc.get('interaction_range',2))): return False
        key('Return'); time.sleep(.3); return True
    def close_modal(method='Escape'):
        controls=latest_layout().get('controls',[])
        has_modal=any(c['text']=='닫기 / 취소' for c in controls)
        if method=='Escape':key('Escape')
        elif has_modal:button(method,exact=True)
        else:
            observe('operator_close_target_already_absent',requested=method,interpretation='No modal footer in latest ordinary layout; preserve incident and use normal Esc recovery')
            capture('close-already-absent-'+str(len(observations)));key('Escape')
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and any(c['text']=='닫기 / 취소' for c in latest_layout().get('controls',[])):time.sleep(.05)
        still_modal=any(c['text']=='닫기 / 취소' for c in latest_layout().get('controls',[]))
        if still_modal:raise RuntimeError('Actual modal remains after ordinary close input')
    def hunt_cycle():
        s=state();c=s['character']
        if c.get('dead'):
            button('부활',exact=True); state(3.3);go_map(hunting_map);return
        if c['map_id']!=hunting_map:
            if not go_map(hunting_map):raise RuntimeError('Normal route to hunting field failed')
            s=state();c=s['character']
        loot=[v for v in s['loot'] if v['map_id']==c['map_id']]
        if loot:
            item=min(loot,key=lambda t:abs(t['x']-c['x'])+abs(t['y']-c['y']))
            d=abs(item['x']-c['x'])+abs(item['y']-c['y'])
            if d<=1: key('z');state(.2)
            elif d<=5: world_click((item['x'],item['y']),c,'walk to earned loot');time.sleep(1);key('z')
        monsters=[(k,v) for k,v in s['monsters'].items() if v['map_id']==c['map_id'] and v['alive']]
        if not monsters:time.sleep(1);return
        mid,m=min(monsters,key=lambda kv:abs(kv[1]['x']-c['x'])+abs(kv[1]['y']-c['y']))
        world_click((m['x'],m['y']),c,'visible monster '+mid)
        # A user's follow-up attack should not immediately cancel the just-set
        # normal walking route before it reaches the visible target.
        distance=abs(m['x']-c['x'])+abs(m['y']-c['y'])
        if distance>1:time.sleep(min(1.4,(distance-1)*.18+.25))
        if (s['skills'] and content['skills'][s['skills'][0]].get('kind')=='damage') or (a.targeted_followup and any(content['skills'][sid].get('kind')=='damage' for sid in s['skills'])):
            button('기술',exact=True);time.sleep(.3)
        for _ in range(4):key('space');time.sleep(.53)
        key('z');time.sleep(.25)
    def trade_and_train():
        before=state()
        if not talk('장터 식재료상'):return False
        capture('grocer-dialogue');close_modal('X')
        # Bag is initially selected; normal visible parchment row then the sell button.
        inventory=before['inventory']
        for inst in inventory:
            definition=content['items'][inst['item_id']]
            if inst['instance_id'] in before['equipment'].values():continue
            name=definition['name']; matched=False
            for item in latest_layout().get('controls',[]):
                if ':  '+name+' ×' in item['text']:
                    r=item['rect'];click_xy(r[0]+r[2]/2,r[1]+r[3]/2,item['text']);matched=True;break
            if matched:
                # Mage's first attack needs acorns, so trade earned meat while
                # preserving acorns. Other items retain ten as visible reserves.
                count=min(5,int(inst['quantity'])) if inst['item_id']=='gp:item:rabbit_meat' else min(5,max(0,int(inst['quantity'])-10))
                for _ in range(count):button('가까운 상인에게 판매');time.sleep(.2)
        observe('earned_loot_sale_attempt',before_money=before['character']['money'],after_character=state(3.3)['character'])
        if talk('털보'):
            capture('forge-dialogue');button('목검 구매',optional=True);close_modal('닫기 / 취소')
            time.sleep(.3);button('지도',exact=True);time.sleep(.2);close_modal('Escape')
            for item in latest_layout().get('controls',[]):
                if ':  목검 ×' in item['text']:
                    r=item['rect'];click_xy(r[0]+r[2]/2,r[1]+r[3]/2,item['text']);button('장착 / 사용');break
        teacher={'전사':'태백','도적':'마로','주술사':'해두','도사':'진선'}[a.job]
        if not talk(teacher):return False
        capture('guild-dialogue')
        button(a.job+' 전직',optional=True)
        # Only currently visible, actually eligible starter skills are attempted.
        for prefix in {'전사':['이중공격','누리의기원','비영사천문'], '도적':['성황령','누리의기원','비영사천문'], '주술사':['화염주(화)','누리의기원','비영사천문'], '도사':['누리의기원','태양의기원','비영사천문']}[a.job]:
            button(prefix+' 학습',optional=True);time.sleep(.25)
        close_modal('Escape');observe('ordinary_job_and_learning_attempt',character=state(3.3)['character'],skills=state()['skills'])
        return state()['character']['job']!='commoner'
    def learn_scrolled_skill(name):
        # Open a fresh ordinary dialogue so its scroll starts at zero. Use OS
        # wheel input; the read-only layout supplies geometry, never callbacks.
        close_modal('Escape');key('Return');time.sleep(.35)
        for page in range(12):
            layout=latest_layout();controls=layout.get('controls',[])
            learned=next((r for r in controls if r['text'].startswith(name+' [배움]')),None)
            if learned:return True
            target=next((r for r in controls if r['text'].startswith(name+' 학습')),None)
            if target:
                rect=target['rect']
                previous=next((r['rect'] for r in controls if r['text']=='이전'),None)
                footer=next(r['rect'] for r in controls if r['text']=='닫기 / 취소')
                clip_end=(previous[1] if previous else footer[1])-4
                offset=0
                if rect[1]+rect[3]>clip_end:
                    row_rects=[r['rect'] for r in controls if abs(r['rect'][0]-rect[0])<1 and abs(r['rect'][2]-rect[2])<1 and r['text'] not in ['닫기 / 취소','다음','이전']]
                    offset=max(0,max(r[1]+r[3] for r in row_rects)-clip_end)
                    focus();run('mousemove','--window',x.window,int(rect[0]+rect[2]/2),int(clip_end-50));log('mouse_wheel',direction='down',steps=20,description='ordinary dialogue scroll to '+name)
                    run('click','--repeat',20,'--delay',20,'5');time.sleep(.35)
                capture('visible-learning-'+str(page)+'-'+str(len(observations)))
                click_xy(rect[0]+rect[2]/2,rect[1]+rect[3]/2-offset,'visible scrolled '+name+' 학습')
                after=state(3.3)
                learned_ids=[sid for sid in after['skills'] if content['skills'][sid]['name']==name]
                observe('ordinary_scrolled_learning',skill_name=name,page=page+1,scroll_offset_px=offset,learned_ids=learned_ids,character=after['character'])
                return bool(learned_ids)
            if not button('다음',exact=True,optional=True):return False
            time.sleep(.35)
        return False
    def select_learned_skill(name):
        for _ in range(4):
            for item in latest_layout().get('controls',[]):
                if ':  '+name in item['text']:
                    r=item['rect'];click_xy(r[0]+r[2]/2,r[1]+r[3]/2,item['text']);return True
            key('Tab');time.sleep(.25)
        return False
    def trade_surplus():
        before=state()
        if not talk('장터 식재료상'):raise RuntimeError('Normal surplus-sale route failed')
        close_modal('X')
        # Navigate tabs through ordinary keys until the bag is actually visible.
        for _ in range(4):
            if any(':  토끼고기 ×' in r['text'] for r in latest_layout().get('controls',[])):break
            key('Tab');time.sleep(.2)
        quantity=sum(int(i['quantity']) for i in before['inventory'] if i['item_id']=='gp:item:rabbit_meat')
        for item in latest_layout().get('controls',[]):
            if ':  토끼고기 ×' in item['text']:
                r=item['rect'];click_xy(r[0]+r[2]/2,r[1]+r[3]/2,item['text'])
                for _ in range(min(5,max(0,quantity-10))):button('가까운 상인에게 판매');time.sleep(.2)
                break
        observe('ordinary_surplus_trade',before_character=before['character'],after_character=state(3.3)['character'],meat_reserved=10)
    def try_return_skill():
        s=state()
        learned=[sid for sid in s['skills'] if content['skills'][sid].get('kind')=='return']
        if not learned:
            observe('return_skill_not_learned',status='NOT_RUN',reason='Natural materials/learning not completed')
            return False
        skill_name=content['skills'][learned[0]]['name']
        if not select_learned_skill(skill_name):return False
        for item in latest_layout().get('controls',[]):
            if ':  '+skill_name in item['text']:
                r=item['rect'];click_xy(r[0]+r[2]/2,r[1]+r[3]/2,item['text']);button('선택 기술 사용');time.sleep(3.3)
                observe('learned_return_skill_used',before_map=s['character']['map_id'],after_character=state()['character'])
                return state()['character']['map_id']!=s['character']['map_id']
        observe('return_skill_control_not_observed',status='NOT_RUN',name=skill_name)
        return False
    try:
        with (temporary_root/'game.log').open('wb') as game_log:
            process=subprocess.Popen(command,env=env,stdout=game_log,stderr=subprocess.STDOUT)
            wait_stage('ui_layout');x=X11(env)
            capture('01-menu')
            if a.record and not a.compare_recording:start_recorder()
            if a.resume_data:
                since=len(checkpoints(cpath));button('이어 하기',exact=True);wait_stage('loaded',since);time.sleep(.7)
                files=list(saves.glob('*.json'));check('continued_real_earned_character_one_save',len(files)==1)
                if len(files)!=1:raise RuntimeError('Targeted follow-up requires exactly one preserved natural character')
                savefile=files[0];first=state()
                observe('continued_naturally_earned_character',character=first['character'],skills=first['skills'],stats=first['stats'])
            else:
                button('새 캐릭터',exact=True);run('type','--clearmodifiers','--delay','30','cancelos');button('취소',exact=True)
                check('creation_cancel_zero_save',not list(saves.glob('*.json')))
                button('새 캐릭터',exact=True);run('type','--clearmodifiers','--delay','30',a.name);button('만들고 시작',exact=True)
                wait_stage('character_created');time.sleep(1)
                files=list(saves.glob('*.json'));check('ordinary_creation_one_save',len(files)==1)
                if len(files)!=1:raise RuntimeError('Normal character creation failed')
                savefile=files[0];first=state();check('Lv1_commoner_zero_skills',first['character']['level']==1 and first['character']['job']=='commoner' and not first['skills'])
            play_start=time.monotonic();observe('ordinary_play_start',character=first['character']);capture('02-created')
            if a.record and a.compare_recording:
                recording_comparison(False);start_recorder();play_start=time.monotonic()
                observe('recorded_journey_start',character=state()['character'])
                recording_comparison(True)
            if not a.resume_data:
                if talk('왈숙'):
                    capture('03-tavern-dialogue');modal_before=state();close_modal('X');key('Down',.35);modal_after=state(3.3)
                    check('ordinary_tavern_open_X_close_movement_resumes',(modal_before['character']['x'],modal_before['character']['y'])!=(modal_after['character']['x'],modal_after['character']['y']),{'before':modal_before['character'],'after':modal_after['character']})
                    check('closing_NPC_does_not_trade',modal_before['inventory']==modal_after['inventory'] and modal_before['character']['money']==modal_after['character']['money'])
                else:check('ordinary_tavern_open_X_close',False)
                button('지도',exact=True);time.sleep(.3);capture('04-map-dialogue');close_modal('닫기 / 취소')
                check('ordinary_map_footer_close',True)
            if not go_map('gp:map:south_field'):raise RuntimeError('Beginner field unreachable through ordinary OS movement')
            capture('05-first-field')
            trained=False;last_report=-60;last_capture=-180;initial15=False;last_training_attempt=-180;targeted_ready=False;last_surplus_trade=0
            while time.monotonic()-play_start<a.seconds:
                elapsed=time.monotonic()-play_start
                s=state();c=s['character']
                if elapsed-last_report>=45:
                    last_report=elapsed;observe('live_progress',play_seconds=round(elapsed,2),character=c,stats=s['stats'],skills=s['skills'],inventory=[{'item_id':i['item_id'],'quantity':i['quantity']} for i in s['inventory']])
                if elapsed-last_capture>=180:
                    last_capture=elapsed;capture('play-'+str(int(elapsed)))
                if elapsed>=900 and not initial15:
                    initial15=True;observe('initial_15_minutes_completed',character=c,stats=s['stats']);capture('initial-15-minutes')
                if a.targeted_followup and not targeted_ready:
                    teacher={'전사':'태백','도적':'마로','주술사':'해두','도사':'진선'}[a.job]
                    names=['화염주(화)','비영사천문'] if a.job=='주술사' else ['비영사천문']
                    wanted=[sid for name in names for sid,d in content['skills'].items() if d['name']==name and (d['job']==a.job or d['job']=='COMMON_FOUR_STARTER_JOBS') and d['learn_level']<=c['level']]
                    missing=[sid for sid in wanted if sid not in s['skills']]
                    requirements={}
                    for sid in missing:
                        for item_id,quantity in content['skills'][sid].get('ingredients',{}).items():requirements[item_id]=requirements.get(item_id,0)+int(quantity)
                    inventory={item_id:sum(int(i['quantity']) for i in s['inventory'] if i['item_id']==item_id) for item_id in requirements}
                    if all(inventory[item_id]>=quantity for item_id,quantity in requirements.items()):
                        if not talk(teacher):raise RuntimeError('Normal route to teacher failed in earned-character follow-up')
                        for name in names:check('ordinary_scrolled_learning_'+name,learn_scrolled_skill(name))
                        close_modal('Escape');go_map('gp:map:south_field');hunting_map='gp:map:south_field'
                        # Select the newly learned real attack in the visible skill
                        # panel, then use the existing ordinary combat buttons.
                        if not select_learned_skill('화염주(화)'):raise RuntimeError('Actually learned projectile missing from ordinary skill panel')
                        current=state();cc=current['character']
                        monsters=[v for v in current['monsters'].values() if v['map_id']==cc['map_id'] and v['alive']]
                        target=min(monsters,key=lambda v:abs(v['x']-cc['x'])+abs(v['y']-cc['y']))
                        if abs(target['x']-cc['x'])+abs(target['y']-cc['y'])>4:walk_to((target['x'],target['y']),reach=4)
                        key('Escape')  # normal field cancel stops walking/auto-attack before the isolated spell input
                        before_projectile=state(3.3);capture('ordinary-before-projectile')
                        button('기술',exact=True);capture('ordinary-projectile-effect');after_projectile=state(3.3)
                        capture('ordinary-learned-projectile')
                        check('ordinary_learned_attack_MP_cost_observed',True if after_projectile['character']['mp']<before_projectile['character']['mp'] else None,{'before_mp':before_projectile['character']['mp'],'after_mp':after_projectile['character']['mp'],'before_level':before_projectile['character']['level'],'after_level':after_projectile['character']['level'],'scope':'No basic attack is issued during this isolated ordinary spell observation; persistent MP cost and target health corroborate the original video.'})
                        before_monsters={k:{f:v[f] for f in ['hp','alive','x','y']} for k,v in before_projectile['monsters'].items() if v['map_id']=='gp:map:south_field'}
                        after_monsters={k:{f:v[f] for f in ['hp','alive','x','y']} for k,v in after_projectile['monsters'].items() if v['map_id']=='gp:map:south_field'}
                        damaged=[k for k,v in before_monsters.items() if k in after_monsters and (after_monsters[k]['hp']<v['hp'] or (v['alive'] and not after_monsters[k]['alive']))]
                        check('ordinary_learned_projectile_target_damage',bool(damaged) or after_projectile['stats']['kills']>before_projectile['stats']['kills'],{'damaged_monsters':damaged,'before':before_monsters,'after':after_monsters})
                        observe('ordinary_projectile_use_attempt',before_character=before_projectile['character'],after_character=after_projectile['character'],before_stats=before_projectile['stats'],after_stats=after_projectile['stats'],damaged_monsters=damaged)
                        trained=True;last_training_attempt=elapsed
                        preflight_return=try_return_skill();check('ordinary_preflight_learned_return',preflight_return)
                        preflight_checks=[c for c in result['checks'] if c['id'].startswith('ordinary_scrolled_learning_') or c['id'] in ['ordinary_learned_attack_MP_cost_observed','ordinary_learned_projectile_target_damage','ordinary_preflight_learned_return']]
                        if any(c['status']!='PASS' for c in preflight_checks):raise RuntimeError('Natural ability preflight incomplete; preserve evidence before continuous stress')
                        observe('natural_ability_preflight_completed',character=state()['character'],skills=state()['skills'])
                        if not a.continuous_after_preflight:break
                        if not go_map(hunting_map):raise RuntimeError('Normal route back after preflight return failed')
                        select_learned_skill('화염주(화)')
                        targeted_ready=True;play_start=time.monotonic();last_report=-60;last_capture=-180;initial15=False;last_surplus_trade=0
                        observe('continuous_stress_started',requested_seconds=a.seconds,character=state()['character'],skills=state()['skills']);continue
                    hunt_cycle();continue
                if not a.targeted_followup and (not trained or not s['skills']) and c['level']>=6 and s['stats']['items_picked_up']>=10 and elapsed-last_training_attempt>=180:
                    last_training_attempt=elapsed;trained=trade_and_train();go_map(hunting_map)
                if targeted_ready and elapsed-last_surplus_trade>=300:
                    last_surplus_trade=elapsed
                    check('ordinary_repeated_learned_return_'+str(int(elapsed)),try_return_skill())
                    trade_surplus();go_map(hunting_map);select_learned_skill('화염주(화)')
                if a.advance_hunting and hunting_map=='gp:map:south_field' and c['level']>=8 and s['skills']:
                    target=next((mid for mid,m in content['maps'].items() if m['name']=='쥐굴 1층'),None)
                    if target and go_map(target):
                        hunting_map=target;observe('natural_next_hunting_area',character=state()['character'],skills=state()['skills']);capture('next-hunting-area')
                hunt_cycle()
            if a.continuous_after_preflight:check('continuous_requested_stress_duration',targeted_ready and time.monotonic()-play_start>=a.seconds,{'stress_seconds':time.monotonic()-play_start,'required_seconds':a.seconds})
            final_play=state(3.3);capture('06-final-play');observe('requested_play_duration_completed',play_seconds=time.monotonic()-play_start,character=final_play['character'],stats=final_play['stats'])
            result['ordinary_return_skill']=try_return_skill()
            check('ordinary_natural_combat_kills',final_play['stats']['kills']>0,final_play['stats'])
            check('ordinary_loot_picked_up',final_play['stats']['items_picked_up']>0,final_play['stats'])
            button('저장 · 처음으로',exact=True);time.sleep(.7);before_restart=state()
            if (temporary_root/'frame-timeline.jsonl').exists():shutil.copy2(temporary_root/'frame-timeline.jsonl',out/'journey-frame-timeline.jsonl')
            check('natural_job_change_and_skill_learning',(before_restart['character']['job']!='commoner' and bool(before_restart['skills'])) if last_training_attempt>=0 else None,{'job':before_restart['character']['job'],'skills':before_restart['skills'],'learning_attempted':last_training_attempt>=0})
            result['before_restart']=before_restart
            process.terminate();process.wait(timeout=15);x.close();x=None
            since=len(checkpoints(cpath));process=subprocess.Popen(command,env=env,stdout=game_log,stderr=subprocess.STDOUT)
            wait_stage('ui_layout',since);x=X11(env);button('이어 하기',exact=True)
            loaded=wait_stage('loaded',since)['details']['character'];check('new_process_same_saved_character',loaded==before_restart['character'],loaded)
            time.sleep(.7);key('Left',.5);state(3.3);capture('07-restarted');button('저장 · 처음으로',exact=True);time.sleep(.5)
            after=state();check('restarted_input_requests_advance',after['request_watermarks'].get('ui',0)>before_restart['request_watermarks'].get('ui',0))
            if (temporary_root/'frame-timeline.jsonl').exists():shutil.copy2(temporary_root/'frame-timeline.jsonl',out/'restart-frame-timeline.jsonl')
            result['final']=after
    except Exception as ex:
        result['error']=str(ex);observe('operator_stopped',error=str(ex))
        try:capture('failure')
        except Exception:pass
        # A harness error must preserve its evidence before attempting ordinary
        # save-to-menu, which also flushes the frozen app's accumulated trace.
        if savefile and process and process.poll() is None:
            try:
                key('Escape');time.sleep(.25);button('저장 · 처음으로',exact=True);time.sleep(.7)
                if (temporary_root/'frame-timeline.jsonl').exists():shutil.copy2(temporary_root/'frame-timeline.jsonl',out/'journey-frame-timeline.jsonl')
                observe('ordinary_save_after_operator_error',character=state()['character'])
            except Exception as recovery:observe('ordinary_error_recovery_incomplete',error=str(recovery))
    finally:
        if x:x.close()
        if process and process.poll() is None:process.terminate();process.wait(timeout=15)
        if recorder and recorder.poll() is None:
            recorder.send_signal(2)
            try:recorder.wait(timeout=20)
            except subprocess.TimeoutExpired:recorder.kill();recorder.wait()
        if recorder:
            raw=temporary_root/'ordinary-unedited.mkv'
            remuxed=temporary_root/'ordinary-unedited.mp4'
            remux=subprocess.run(['ffmpeg','-v','error','-y','-i',str(raw),'-c','copy',str(remuxed)],capture_output=True,timeout=120)
            probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size','-show_entries','stream=r_frame_rate,nb_frames','-of','json',str(remuxed)],capture_output=True,text=True,timeout=30)
            try:video_metadata=json.loads(probe.stdout)
            except json.JSONDecodeError:video_metadata={}
            result['video_validation']={'remux_returncode':remux.returncode,'ffprobe_returncode':probe.returncode,'metadata':video_metadata,'stderr':probe.stderr or remux.stderr.decode(errors='replace')}
            valid=remux.returncode==0 and probe.returncode==0 and float(video_metadata.get('format',{}).get('duration',0))>=(1 if a.targeted_followup and not a.continuous_after_preflight else a.seconds)
            check('unedited_video_readable_and_duration',valid,result['video_validation'])
            if remuxed.exists() and probe.returncode==0:
                publishing=out/'.finalizing-video.mp4';shutil.copy2(remuxed,publishing);os.replace(publishing,out/'ordinary-unedited.mp4')
            elif raw.exists():shutil.copy2(raw,out/'ordinary-unedited-incomplete.mkv')
        for name in ['game.log','recorder.log','os-input-timeline.jsonl','frame-timeline.jsonl']:
            if (temporary_root/name).exists():shutil.copy2(temporary_root/name,out/name)
        if (temporary_root/'data').exists():shutil.copytree(temporary_root/'data',out/'data',dirs_exist_ok=True)
    result['wall_seconds']=round(time.monotonic()-start,2)
    result['performance_checkpoints']=[r for r in checkpoints(cpath) if r.get('stage') in ['performance','frame_timing']]
    result['engine_error_lines']=[line for line in (out/'game.log').read_text(errors='replace').splitlines() if 'ERROR:' in line or 'SCRIPT ERROR' in line]
    check('no_ordinary_engine_errors',not result['engine_error_lines'],result['engine_error_lines'])
    result['evidence_files']=[{'file':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(out.iterdir()) if f.is_file() and f.name not in ['OS_PLAYABILITY.json']]
    result['status']='FAIL' if result.get('error') or any(c['status']=='FAIL' for c in result['checks']) else 'PARTIAL_NOT_RUN' if any(c['status']=='NOT_RUN' for c in result['checks']) else 'PASS_OBSERVED_SCOPE'
    (out/'OS_PLAYABILITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'error':result.get('error'),'wall_seconds':result['wall_seconds'],'output':str(out)},ensure_ascii=False),flush=True)
    return 0 if result['status']=='PASS_OBSERVED_SCOPE' else 1

if __name__=='__main__':raise SystemExit(main())
