#!/usr/bin/env python3
"""Exhaustive, provenance-labeled isolated door contract tests through OS XTEST.

Initial saves are deliberately generated offline fixtures. They do NOT prove
natural progression, learned levels, account sync, or device behavior. Once a
process is launched, this operator never changes a save, calls an engine method,
injects an engine event, teleports, or uses developer navigation. Every accepted
step/transition is an actual cardinal XTEST key in the normal game window.
Screenshots/video are actual X framebuffer captures. Visual judgment remains
NOT_RUN until separately inspected; functional PASS never means VISUAL_PASS.
"""
from __future__ import annotations
import argparse, base64, csv, hashlib, html, json, os, shutil, subprocess, sys, tempfile, time
from collections import deque
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'p2'))
from gameplay_x11 import X11, checkpoints

DIRECTIONS=[('Up',0,-1,1,4),('Right',1,0,2,8),('Down',0,1,4,1),('Left',-1,0,8,2)]
class VisualCaptureOnly(Exception):pass
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def compact_maps(content):
    for m in content['maps'].values():
        m['_blocked']=set(map(tuple,m.get('blocked',[])))
        if m.get('blocked_base64'):
            m['_blocked']|={(i%m['width'],i//m['width']) for i,v in enumerate(base64.b64decode(m['blocked_base64'])) if v}
        m['_edges']=list(base64.b64decode(m.get('edge_masks_base64',''))) or m.get('edge_masks',[])
        m['_exits']={(int(e['x']),int(e['y'])) for e in m.get('exits',[])}
def route(content,map_id,origin,destination,extra_blocked=()):
    m=content['maps'][map_id];origin=tuple(origin);destination=tuple(destination)
    if not(0<=origin[0]<m['width'] and 0<=origin[1]<m['height']):return []
    blocked=m['_blocked']|set(extra_blocked)
    blocked|={(int(n['x']),int(n['y'])) for n in content['npcs'].values() if n['map_id']==map_id}
    if origin in blocked:return []
    q=deque([origin]);previous={origin:None};edges=m['_edges']
    while q:
        at=q.popleft()
        if at==destination:break
        for key,dx,dy,sb,tb in DIRECTIONS:
            n=(at[0]+dx,at[1]+dy)
            if n in previous or n in blocked or not(0<=n[0]<m['width'] and 0<=n[1]<m['height']):continue
            if n in m['_exits'] and n!=destination:continue
            if edges and (edges[at[1]*m['width']+at[0]]&sb or edges[n[1]*m['width']+n[0]]&tb):continue
            previous[n]=at;q.append(n)
    if destination not in previous:return []
    cells=[];at=destination
    while at!=origin:cells.append(at);at=previous[at]
    return cells[::-1]
def build_plan(content,content_path):
    compact_maps(content);cases=[]
    for map_id,m in content['maps'].items():
        for exit in m.get('exits',[]):
            target=(int(exit['x']),int(exit['y']));candidates=[]
            contract=next((r for r in m.get('door_contracts',[]) if r.get('id')==exit['id']),{})
            approach=tuple(contract['approach_cell']) if contract.get('approach_cell') else None
            for radius in [4,3,2,1]:
                for _,dx,dy,_,_ in DIRECTIONS:
                    start=(target[0]-dx*radius,target[1]-dy*radius)
                    if start in m['_blocked'] or start in m['_exits']:continue
                    path=route(content,map_id,start,target)
                    if path and len(path)<=radius+4 and (not approach or (path[-2] if len(path)>1 else start)==approach):candidates.append((abs(len(path)-4),start,path))
                if candidates:break
            pair=sorted([e for e in content['maps'][exit['to_map']].get('exits',[]) if e['to_map']==map_id],key=lambda e:abs(e['x']-exit['to_x'])+abs(e['y']-exit['to_y'])+abs(e['to_x']-exit['x'])+abs(e['to_y']-exit['y']))
            reverse_contract=next((r for r in content['maps'][exit['to_map']].get('door_contracts',[]) if pair and r.get('id')==pair[0]['id']),{})
            case={'case_id':f'door-{len(cases):03d}','map_id':map_id,'map_name':m['name'],'exit':exit,'return_exit':pair[0] if pair else None,'start':list(sorted(candidates)[0][1]) if candidates else list(target),'door_contract':contract,'reverse_door_contract':reverse_contract,'planning_status':'READY' if candidates and pair else 'FAIL_NO_APPROACH_OR_RETURN','natural_progression':False,'visual_status':'NOT_RUN'}
            cases.append(case)
    return {'schema':'baram.os-world-plan/1','content_sha256':sha(content_path),'map_count':len(content['maps']),'exit_count':len(cases),'cases':cases}

class Operator:
    def __init__(self,args,content,plan,out):
        self.a=args;self.c=content;self.plan=plan;self.out=out;self.proc=None;self.x=None;self.rec=None;self.started=time.monotonic();self.case=None
        self.temp=Path(tempfile.mkdtemp(prefix='baram-world-os-'));self.env=os.environ.copy()
        self.env.update(XDG_DATA_HOME=str(self.temp/'data'),XDG_CONFIG_HOME=str(self.temp/'config'),XAUTHORITY='',GODOT_SILENCE_ROOT_WARNING='1',BARAM_GAMEPLAY_RUNTIME=str(args.runtime.resolve()),BARAM_POSITION_OBSERVATION=str(self.temp/'position.json'))
        self.env.setdefault('LP_NUM_THREADS','2')
        self.user=self.temp/'data'/args.user_dir_name;self.cp=self.user/'gameplay-checkpoints.jsonl';self.pos=self.temp/'position.json'
        self.input_path=self.temp/'os-input-timeline.jsonl';self.inputs=self.input_path.open('a',buffering=1);self.results=[];self.captures=[];self.maps={};self.game_stream=None
    def log(self,kind,**data):
        row={'kind':kind,'case_id':self.case['case_id'] if self.case else None,'wall_unix_ns':time.time_ns(),'elapsed_s':round(time.monotonic()-self.started,3),**data};self.inputs.write(json.dumps(row,ensure_ascii=False)+'\n');return row
    def state(self):
        try:return json.loads(self.pos.read_text())
        except (OSError,json.JSONDecodeError):
            # Historical source lacks the new read-only position channel. Only
            # immobile visual previews may observe its loaded/layout checkpoint.
            if self.a.preview_scene:
                for row in reversed(checkpoints(self.cp)):
                    d=row.get('details',{});c=d.get('character_position',d.get('character',{}))
                    if c:return {'character':c,'revision':d.get('revision'),'ticks_usec':row.get('ticks_ms',0)*1000,'observation_scope':'Historical loaded fixture only, no movement result'}
            return {}
    def run(self,*items):
        return subprocess.run([str(self.a.xdotool.resolve()),*map(str,items)],env=self.env,check=True,capture_output=True,timeout=15)
    def key(self,key):
        self.run('windowfocus','--sync',self.x.window);self.log('key',key=key,method='XTEST press/release');self.run('key','--clearmodifiers','--delay','0',key)
    def layout(self):
        return next((r['details'] for r in reversed(checkpoints(self.cp)) if r.get('stage')=='ui_layout'),{})
    def click_button(self,label):
        r=next((c['rect'] for c in self.layout().get('controls',[]) if c['text']==label),None)
        if not r:raise RuntimeError('ordinary visible button absent: '+label)
        self.run('windowfocus','--sync',self.x.window);self.run('mousemove','--window',self.x.window,int(r[0]+r[2]/2),int(r[1]+r[3]/2));self.log('mouse_click',label=label,rect=r);self.run('click','1')
    def wait(self,predicate,timeout=25):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if (self.out/'STOP_OPERATOR').exists():raise RuntimeError('Operator cancelled; remaining cases NOT_RUN')
            if self.proc and self.proc.poll() is not None:raise RuntimeError('game process exited')
            value=predicate()
            if value:return value
            time.sleep(.04)
        raise TimeoutError('ordinary observation timeout')
    def capture(self,name):
        time.sleep(.22);path=self.out/(name+'.png')
        subprocess.run(['ffmpeg','-v','error','-y','-f','x11grab','-video_size',self.a.screen,'-i',self.env['DISPLAY'],'-frames:v','1',str(path)],env=self.env,capture_output=True,check=True,timeout=25)
        geometry={}
        if self.x:
            geometry={k:int(v) for l in self.run('getwindowgeometry','--shell',self.x.window).stdout.decode().splitlines() if '=' in l for k,v in [l.split('=',1)] if k in ['X','Y','WIDTH','HEIGHT']}
        crop=None
        if geometry:
            from PIL import Image
            crop=self.out/(name+'-game.png')
            im=Image.open(path);im.crop((geometry['X'],geometry['Y'],geometry['X']+geometry['WIDTH'],geometry['Y']+geometry['HEIGHT'])).save(crop)
        row=self.log('screenshot',file=path.name,sha256=sha(path),game_frame=crop.name if crop else None,game_frame_sha256=sha(crop) if crop else None,position=self.state(),window_geometry=geometry,view_rect=self.layout().get('view_rect'),view_zoom=self.layout().get('view_zoom'),view_focus=self.layout().get('view_focus'),content_sha256=self.plan['content_sha256']);self.captures.append(row);return crop.name if crop else path.name
    def start(self,case,fixture):
        self.case=case
        self.env['BARAM_PLAYABILITY_TRACE']=str(self.temp/(case['case_id']+'-frame-timeline.jsonl'))
        if self.user.exists():shutil.rmtree(self.user)
        saves=self.user/'gameplay-p3/characters';saves.mkdir(parents=True)
        shutil.copy2(fixture,saves/'world-qa-start.json');self.pos.unlink(missing_ok=True)
        command=[str(self.a.godot.resolve()),'--audio-driver','Dummy','--max-fps','60','--path',str(self.a.project.resolve())]
        if self.a.pack:command=[str(self.a.godot.resolve()),'--audio-driver','Dummy','--max-fps','60','--main-pack',str(self.a.pack.resolve())];self.env.pop('BARAM_GAMEPLAY_RUNTIME',None)
        self.game_stream=(self.temp/(case['case_id']+'.log')).open('wb')
        self.proc=subprocess.Popen(command,env=self.env,stdout=self.game_stream,stderr=subprocess.STDOUT)
        self.log('process_started',pid=self.proc.pid,command=command,fixture_sha256=sha(fixture),fixture_provenance='OFFLINE_QA_START_FIXTURE_NOT_NATURAL_PROGRESS')
        self.wait(lambda:self.layout().get('controls'),50);self.x=X11(self.env);self.click_button('이어 하기')
        self.wait(lambda:self.state().get('character'),35);time.sleep(.35)
        current=self.state()['character']
        if current['map_id']!=case['map_id'] or [int(current['x']),int(current['y'])]!=case['start']:raise RuntimeError('initial fixture not loaded at declared cell')
    def stop(self):
        if self.x and self.proc and self.proc.poll() is None:
            try:
                self.key('Escape');time.sleep(.1)
                label=next((c['text'] for c in self.layout().get('controls',[]) if c['text'] in ['저장','저장하고 처음으로']),None)
                if label:self.click_button(label);time.sleep(.3)
            except Exception:pass
        if self.x:self.x.close();self.x=None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.proc=None
        if self.game_stream:self.game_stream.close();self.game_stream=None
        if self.case:
            for suffix in ['.log','-frame-timeline.jsonl']:
                src=self.temp/(self.case['case_id']+suffix)
                if src.exists():shutil.copy2(src,self.out/src.name)
            if self.cp.exists():shutil.copy2(self.cp,self.out/(self.case['case_id']+'-checkpoints.jsonl'))
            save=self.user/'gameplay-p3/characters/world-qa-start.json'
            if save.exists():shutil.copy2(save,self.out/(self.case['case_id']+'-final-save.json'))
    def walk(self,map_id,target,expected_map=None,max_steps=220):
        target=tuple(target);temporary_obstacles={};detours=0
        for step in range(max_steps):
            observed=self.state();c=observed['character'];origin=(int(c['x']),int(c['y']))
            if c.get('dead'):raise RuntimeError('character died in OS door path')
            if expected_map and c['map_id']==expected_map:return observed
            if c['map_id']!=map_id:raise RuntimeError('unexpected map transition: '+c['map_id'])
            if origin==target:return observed
            path=route(self.c,map_id,origin,target)
            if not path:raise RuntimeError('no physical route from observed cell to door')
            temporary_obstacles={cell:until for cell,until in temporary_obstacles.items() if until>time.monotonic()}
            alternative=route(self.c,map_id,origin,target,temporary_obstacles)
            if alternative:path=alternative
            elif temporary_obstacles:
                # A live monster can occupy the intended return cell. Ordinary
                # users can step aside so it follows, then walk back. Do that
                # through OS keys; never remove/disable/relocate any actor.
                options=[]
                for _,ox,oy,_,_ in DIRECTIONS:
                    other=(origin[0]+ox,origin[1]+oy)
                    if other in self.c['maps'][map_id]['_exits'] or other in temporary_obstacles:continue
                    detour=route(self.c,map_id,origin,other,temporary_obstacles)
                    if len(detour)==1:options.append((-(abs(other[0]-target[0])+abs(other[1]-target[1])),other))
                if not options:
                    time.sleep(.3);continue
                path=[sorted(options)[0][1]]
            nxt=path[0];dx=nxt[0]-origin[0];dy=nxt[1]-origin[1];key=next(k for k,x,y,_,_ in DIRECTIONS if (x,y)==(dx,dy))
            success=False
            for attempt in range(4):
                before=self.state();self.key(key)
                try:
                    after=self.wait(lambda:(s if (s:=self.state()).get('ticks_usec')!=before.get('ticks_usec') else None),2.5)
                except TimeoutError:after=self.state()
                self.log('step_observation',before=before,after=after,intended=list(nxt),attempt=attempt)
                cc=after.get('character',{})
                if cc.get('map_id')!=map_id or (int(cc.get('x',-1)),int(cc.get('y',-1)))!=origin:success=True;break
                time.sleep(.2)
            if not success:
                temporary_obstacles[nxt]=time.monotonic()+2.0;detours+=1
                self.log('ordinary_obstacle_detour',observed=after,blocked_cell=list(nxt),attempt=detours,scope='Normal OS movement only; dynamic collision inferred from actual REFUSED input, actor not modified')
                if detours>12:raise RuntimeError('OS movement blocked after12normaldetourattempts: '+json.dumps(after))
                continue
            time.sleep(.17)
        raise RuntimeError('OS path step budget exceeded')
    def one(self,case,fixture):
        result={**case,'input_status':'NOT_RUN','visual_status':'NOT_RUN','natural_progression':False,'existing_save_coordinate_migration_status':'NOT_RUN','captures':[]}
        try:
            if sha(self.a.runtime/'gameplay_content.json')!=self.plan['content_sha256']:raise RuntimeError('CONTENT_CHANGED_DURING_QA; frozen-run invalid')
            if case['planning_status']!='READY':raise RuntimeError(case['planning_status'])
            self.start(case,fixture)
            prefix=case['case_id'];result['captures'].append(self.capture(prefix+'-approach'))
            if case['map_id'] not in self.maps:
                self.click_button('지도');self.wait(lambda:any(c['text']=='닫기 / 취소' for c in self.layout().get('controls',[])),8)
                overview=self.capture(prefix+'-overview');self.key('Escape');time.sleep(.25)
                self.maps[case['map_id']]={'map_id':case['map_id'],'name':case['map_name'],'runtime_frame':result['captures'][0],'overview_frame':overview,'coordinate':case['start'],'content_sha256':self.plan['content_sha256'],'visual_status':'NOT_RUN','provenance':'Offline initial save fixture, actual game renderer and OS map button'}
            if int(case['case_id'].split('-')[-1]) in self.a.visual_only_case:raise VisualCaptureOnly()
            e=case['exit'];result['approach_before']=self.state()
            if case.get('door_contract',{}).get('approach_cell'):self.walk(case['map_id'],case['door_contract']['approach_cell'])
            arrival=self.walk(case['map_id'],(e['x'],e['y']),e['to_map']);result['arrival']=arrival
            expected_direction={'north':0,'east':1,'south':2,'west':3}.get(e.get('direction'))
            if expected_direction is not None and int(arrival['character']['direction'])!=expected_direction:raise RuntimeError('arrival direction differs from exit contract')
            arrival_delta=[int(arrival['character']['x'])-int(e['to_x']),int(arrival['character']['y'])-int(e['to_y'])]
            result['arrival_anchor_delta']=arrival_delta
            if any(arrival_delta):raise RuntimeError('arrival differs from declared landing cell (occupancy fallback is recorded as failure, not accepted)')
            result['captures'].append(self.capture(prefix+'-arrival'))
            r=case['return_exit'];result['reverse_exit_id']=r['id']
            if case.get('reverse_door_contract',{}).get('approach_cell'):self.walk(e['to_map'],case['reverse_door_contract']['approach_cell'])
            returned=self.walk(e['to_map'],(r['x'],r['y']),case['map_id']);result['returned']=returned
            expected_reverse_direction={'north':0,'east':1,'south':2,'west':3}.get(r.get('direction'))
            if expected_reverse_direction is not None and int(returned['character']['direction'])!=expected_reverse_direction:raise RuntimeError('reverse arrival direction differs from exit contract')
            return_delta=[int(returned['character']['x'])-int(r['to_x']),int(returned['character']['y'])-int(r['to_y'])]
            result['return_anchor_delta']=return_delta
            if any(return_delta):raise RuntimeError('return differs from declared landing cell (occupancy fallback is recorded as failure, not accepted)')
            result['captures'].append(self.capture(prefix+'-returned'))
            self.walk(case['map_id'],case['start']);result['final']=self.state()
            result['input_status']='PASS_INPUT_DOOR_CONTRACT'
            result['final_start_reached']=True
        except VisualCaptureOnly:
            result['input_status']='NOT_RUN_VISUAL_RECAPTURE';result['input_reuse_requested']=True
        except Exception as exc:
            result['input_status']='FAIL';result['error']=str(exc)
            if self.proc and self.proc.poll() is None:
                try:result['captures'].append(self.capture(case['case_id']+'-failure'))
                except Exception as capture_exc:result['capture_error']=str(capture_exc)
        finally:self.stop()
        self.results.append(result);self.publish();print(json.dumps({'case_id':case['case_id'],'map_name':case['map_name'],'status':result['input_status'],'error':result.get('error')},ensure_ascii=False),flush=True)
    def publish(self):
        if not self.inputs.closed:self.inputs.flush()
        if self.input_path.exists():shutil.copy2(self.input_path,self.out/'os-input-timeline.jsonl')
        doc={'schema':'baram.os-world-door-results/1','scope':'ISOLATED_OFFLINE_INITIAL_FIXTURE_THEN_NORMAL_OS_KEYS; NOT_NATURAL_PROGRESSION; NOT_VISUAL_PASS; Linux only; Dummy audio','content_sha256':self.plan['content_sha256'],'runtime_sha256':sha(self.a.runtime/'runtime.json'),'maps':list(self.maps.values()),'case_results':self.results,'captures':self.captures,'operator_sha256':sha(__file__),'elapsed_s':time.monotonic()-self.started,'isolated_data_path':str(self.temp),'exact_pack_sha256':sha(self.a.pack) if self.a.pack else None,'source_fingerprint':{str(p.relative_to(self.a.project)):sha(p) for p in sorted(self.a.project.rglob('*')) if p.is_file() and p.suffix in ['.gd','.godot','.tscn']}}
        dump(self.out/'WORLD_DOOR_QA.json',doc)
        with (self.out/'WORLD_DOOR_QA.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['case_id','map_id','map_name','exit_id','to_map','x','y','minimum_level','input_status','visual_status','natural_progression','error','captures']);w.writeheader()
            for r in self.results:w.writerow({**{k:r.get(k,'') for k in ['case_id','map_id','map_name','input_status','visual_status','natural_progression','error']},**{k:r['exit'].get(k,'') for k in ['to_map','x','y','minimum_level']},'exit_id':r['exit']['id'],'captures':'|'.join(r['captures'])})
    def recording(self):
        if not self.a.record:return
        self.rec=subprocess.Popen(['ffmpeg','-v','warning','-y','-f','x11grab','-draw_mouse','1','-framerate','15','-video_size',self.a.screen,'-i',self.env['DISPLAY'],'-c:v','libx264','-threads','2','-preset','ultrafast','-crf','30','-pix_fmt','yuv420p',str(self.out/'unedited-os-door-session.mkv')],env=self.env,stdout=(self.out/'recorder.log').open('wb'),stderr=subprocess.STDOUT)
    def close(self):
        self.stop()
        if self.rec:
            self.rec.terminate()
            try:self.rec.wait(timeout=15)
            except subprocess.TimeoutExpired:self.rec.kill();self.rec.wait()
        self.inputs.close();self.publish()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['godot','project','runtime','xdotool','seed-save','output']:p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--pack',type=Path);p.add_argument('--plan-only',action='store_true');p.add_argument('--record',action='store_true');p.add_argument('--screen',default='1600x1000');p.add_argument('--user-dir-name',default='baram_rebuild_gameplay_001');p.add_argument('--case-start',type=int,default=0);p.add_argument('--case-count',type=int,default=9999)
    p.add_argument('--preview-scene',action='append',default=[],help='Read-only fixture-start visual preview map_id,x,y; no door PASS assigned')
    p.add_argument('--exclude-case',type=int,action='append',default=[],help='Exact same-fingerprint completed pilot case included separately by merger')
    p.add_argument('--visual-only-case',type=int,action='append',default=[],help='Current actual capture only, with earlier immutable functional proof ingested separately')
    a=p.parse_args();out=a.output.resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    out.mkdir(parents=True);content=json.loads((a.runtime/'gameplay_content.json').read_text());plan=build_plan(content,a.runtime/'gameplay_content.json');dump(out/'PLAN.json',plan)
    if a.plan_only:return 0
    selected=plan['cases'][a.case_start:a.case_start+a.case_count]
    selected=[r for r in selected if int(r['case_id'].split('-')[-1]) not in a.exclude_case]
    if a.preview_scene:
        selected=[]
        for i,spec in enumerate(a.preview_scene):
            map_id,x,y=spec.rsplit(',',2)
            selected.append({'case_id':f'preview-{i:03d}','map_id':map_id,'map_name':content['maps'][map_id]['name'],'start':[int(x),int(y)],'exit':{},'planning_status':'PREVIEW_ONLY','visual_status':'NOT_RUN'})
    selected_plan={**plan,'cases':selected};dump(out/'SELECTED_PLAN.json',selected_plan)
    fixture_temp=Path(tempfile.mkdtemp(prefix='baram-world-fixtures-'));env=os.environ.copy();env.update(XDG_DATA_HOME=str(fixture_temp/'data'),XDG_CONFIG_HOME=str(fixture_temp/'config'))
    fixture_index=out/'FIXTURE_PROVENANCE.json'
    script=Path(__file__).with_name('prepare_os_world_fixtures.gd')
    command=[str(a.godot.resolve()),'--headless','--path',str(a.project.resolve()),'--script',str(script.resolve()),'--',str((out/'SELECTED_PLAN.json').resolve()),str(a.seed_save.resolve()),str(a.runtime.resolve()),str(fixture_index)]
    with (out/'fixture-generation.log').open('wb') as f:subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
    index=json.loads(fixture_index.read_text());fixtures={}
    preserved=out/'initial-save-fixtures';preserved.mkdir()
    for r in index['records']:
        path=preserved/(r['case_id']+'.json');shutil.copy2(r['save_file'],path)
        if sha(path)!=r['sha256']:raise RuntimeError('Initial fixture byte preservation failed')
        r['preserved_initial_save']=str(path.relative_to(out));fixtures[r['case_id']]=path
    dump(fixture_index,index)
    shutil.copy2(a.seed_save,out/'fixture-seed-save.json')
    dump(out/'SEED_PROVENANCE.json',{'seed_save':str(a.seed_save.resolve()),'sha256':sha(a.seed_save),'fixture_changes':'position, level99/xp,HP100000/deadfalse/discovered_maps; pending_actions/summons/buffs/cooldowns cleared; all edits declared; no natural progression claim'})
    operator=Operator(a,content,plan,out)
    try:
        operator.recording()
        for case in selected:
            if (out/'STOP_OPERATOR').exists():break
            if a.preview_scene:
                operator.start(case,fixtures[case['case_id']]);operator.capture(case['case_id']+'-actual-game');operator.click_button('지도');time.sleep(.4);operator.capture(case['case_id']+'-actual-overview');operator.key('Escape');operator.stop()
            else:operator.one(case,fixtures[case['case_id']])
    finally:operator.close()
    return 0 if all(r['input_status']=='PASS_INPUT_DOOR_CONTRACT' for r in operator.results) else 1
if __name__=='__main__':raise SystemExit(main())
