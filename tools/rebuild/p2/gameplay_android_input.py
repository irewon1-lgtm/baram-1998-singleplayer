"""Same-APK ordinary Android UI probe, using observed layout and screen bounds."""
import hashlib
import json
from pathlib import Path
import secrets
import time
from PIL import Image, ImageChops

def probe(base, package, userdata, output, run, read_private, launch, capture, resume_proof=None):
    proof={'scope':'Android emulator ADB touch/ASCII string injection, not physical Galaxy or actual IME','checks':[]}
    shot=output/'screen-after-systemui-wait.png'
    if not shot.exists(): shot=output/'screen-default-first-frame.png'
    image=Image.open(shot).convert('RGB')
    colors=image.getcolors(image.width*image.height)
    candidates=[(n,c) for n,c in colors if max(abs(c[i]-[22,35,33][i]) for i in range(3))<=2]
    if not candidates or max(candidates)[0]<image.width*image.height*.2:
        return {**proof,'status':'BLOCKED_SCREEN_BOUNDS','reason':'No verified ordinary app background rectangle; no blind taps'}
    color=max(candidates)[1]
    mask=ImageChops.difference(image,Image.new('RGB',image.size,color)).convert('L').point(lambda x:255 if x==0 else 0)
    bounds=mask.getbbox();proof['observed_app_bounds']=bounds
    if not bounds:return {**proof,'status':'BLOCKED_SCREEN_BOUNDS'}
    def rows():
        raw,_=read_private(userdata+'/gameplay-checkpoints.jsonl')
        parsed=[]
        for line in raw.splitlines():
            try:parsed.append(json.loads(line))
            except ValueError:pass
        (output/'ordinary-ui-checkpoints.json').write_text(json.dumps(parsed,ensure_ascii=False,indent=2)+'\n')
        # A process restart appends to the log. Stale layouts from the old
        # process must never guide touches in the new process.
        starts=[i for i,r in enumerate(parsed) if r.get('stage')=='engine']
        return parsed[starts[-1]:] if starts else parsed
    def control(text):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            history=rows()
            viewport=next((r['details']['viewport'] for r in reversed(history) if r.get('stage')=='first_frame'),[1100,720])
            layouts=[r for r in history if r.get('stage')=='ui_layout']
            if layouts:
                for c in layouts[-1]['details']['controls']:
                    if c['text']==text:
                        x,y,w,h=c['rect']
                        if x<0 or y<0 or x+w>viewport[0] or y+h>viewport[1]:raise RuntimeError('Offscreen mobile control '+text)
                        return int(bounds[0]+(x+w/2)*(bounds[2]-bounds[0])/viewport[0]),int(bounds[1]+(y+h/2)*(bounds[3]-bounds[1])/viewport[1])
            time.sleep(2)
        raise RuntimeError('Visible control unavailable: '+text)
    counter=0
    def wait_saved(path, predicate):
        deadline=time.monotonic()+35
        last={}
        while time.monotonic()<deadline:
            raw,_=read_private(path)
            try:last=json.loads(raw)['payload']
            except (ValueError,KeyError):pass
            if last and predicate(last):return last
            time.sleep(2)
        if not last:raise RuntimeError('No readable saved state within35s')
        return last
    def tap(text):
        nonlocal counter
        counter+=1;x,y=control(text)
        result=run(base+['shell','input','tap',str(x),str(y)],'ui-tap-%02d'%counter,30)
        if result['exit_code']!=0:raise RuntimeError('Tap failed '+text)
        time.sleep(.5)
    def hold(text):
        nonlocal counter
        counter+=1;x,y=control(text)
        # TCG is slower than realtime; keep the observed button pressed long
        # enough for actual app frames rather than testing a 1.2s race.
        run(base+['shell','input','swipe',str(x),str(y),str(x),str(y),'6000'],'ui-hold-%02d'%counter,30)
        time.sleep(2)
    try:
        if resume_proof is not None:
            previous=json.loads(Path(resume_proof).read_text())
            current=json.loads((output/'RUN_RECEIPT.json').read_text())
            if previous['apk_sha256'] != current['apk_sha256']:
                raise RuntimeError('Resume proof APK does not match installed tested APK')
            old=previous['ordinary_input_probe']
            if len(old['checks'])<3 or not all(c['pass'] for c in old['checks'][:3]):
                raise RuntimeError('Resume requires actual completed creation/movement/save checks')
            proof['checks']=old['checks'][:3]
            proof['reused_creation_movement_save_evidence']=str(resume_proof)
            before={'character':old['before']}
            name=old['saved']['name']
            path=userdata+'/gameplay-p3/characters/'+hashlib.sha256(('local-profile:default:'+name).encode()).hexdigest()[:24]+'.json'
            raw,_=read_private(path)
            saved=json.loads(raw)['payload']
            if saved['character'] != old['saved']:
                raise RuntimeError('Saved character differs from stopped checkpoint; never silently replace it')
            proof.update(before=before['character'],saved=saved['character'])
        else:
            tap('새 캐릭터')
            # ADB tap returns before a slow TCG app processes its focus event.
            # Wait for the observed creation layout and explicitly focus its field.
            tap('name_input')
            name='and'+secrets.token_hex(4)
            run(base+['shell','input','text',name],'ui-ascii-name',30)
            capture('ordinary-name-entered')
            # The captured emulator form has no soft keyboard overlay. Do not send
            # Back speculatively: the observed run03 Back event closed the activity.
            tap('만들고 시작');time.sleep(1)
            path=userdata+'/gameplay-p3/characters/'+hashlib.sha256(('local-profile:default:'+name).encode()).hexdigest()[:24]+'.json'
            raw=b''
            for attempt in range(8):
                raw,_=read_private(path)
                if raw.strip():break
                time.sleep(1)
            before=json.loads(raw)['payload']
            proof['before']=before['character']
            proof['checks'].append({'id':'ordinary_touch_creation_commoner','pass':before['character']['job']=='commoner' and before['character']['level']==1 and before['skills']==[]})
            control('공격');control('기술')
            proof['checks'].append({'id':'mobile_action_controls_onscreen','pass':True})
            hold('→');tap('저장하고 처음으로')
            saved=wait_saved(path,lambda s:s['character']['x']>before['character']['x'])
            proof['saved']=saved['character']
            proof['checks'].append({'id':'ordinary_touch_moves_and_saves','pass':saved['character']['x']>before['character']['x']})
            capture('ordinary-moved-saved')
            previous_pid=rows()[-1]['pid']
            run(base+['shell','am','force-stop',package],'ui-stop-after-save',30)
            if not launch('ordinary-ui-restart'):raise RuntimeError('Ordinary restart failed')
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                history=rows()
                if history and history[0].get('pid')!=previous_pid and any(r.get('stage')=='ui_layout' for r in history):break
                time.sleep(2)
            else:raise RuntimeError('Restart produced no fresh process layout within90s')
        # Earlier diagnostic characters are preserved. Select this run's actual
        # character through the ordinary drop-down instead of assuming slot0.
        listing=run(base+['shell','run-as',package,'ls',userdata+'/gameplay-p3/characters'],'ui-profile-list',30)
        names=sorted(n for n in Path(listing['log']).read_text().splitlines() if len(n)==29 and n.endswith('.json') and all(c in '0123456789abcdef' for c in n[:-5]))
        target=Path(path).name
        if target not in names:raise RuntimeError('Created character missing from preserved profile list')
        index=names.index(target)
        option=next(c for c in rows()[-1]['details']['controls'] if c['class']=='OptionButton')
        if not option['text'].startswith(name+' · '):
            tap(option['text'])
            capture('ordinary-profile-selection')
            run(base+['shell','input','keyevent','122']+['20']*index+['66'],'ui-select-created-profile',30)
            # Godot's popup closes asynchronously on this TCG emulator. Keep
            # Continue separate from the closing event; run06 captured this race.
            time.sleep(4)
            capture('ordinary-profile-selected')
        proof['profile_selection']={'filename':target,'index':index,'preserved_profiles':len(names),'already_selected':option['text'].startswith(name+' · ')}
        tap('이어 하기');time.sleep(1)
        control('공격') # restored gameplay, not the old menu frame
        history=rows();loaded=[r['details']['character'] for r in history if r.get('stage')=='loaded'][-1]
        proof['checks'].append({'id':'ordinary_android_process_restart_same_progress','pass':loaded==saved['character']})
        # Walk back along the just-observed traversable path after restart.
        hold('←');tap('저장하고 처음으로')
        after=wait_saved(path,lambda s:s['character']['x']<saved['character']['x'] and s['request_watermarks'].get('ui',0)>saved['request_watermarks'].get('ui',0))
        proof['checks'].append({'id':'post_restart_touch_nonce_and_save','pass':after['character']['x']<saved['character']['x'] and after['request_watermarks'].get('ui',0)>saved['request_watermarks'].get('ui',0)})
        proof.update(before=before['character'],saved=saved['character'],after=after['character'],watermarks=[saved['request_watermarks'],after['request_watermarks']])
        capture('ordinary-ui-complete')
    except Exception as exc:
        proof['reason']=str(exc)
        capture('ordinary-ui-failed')
    proof['status']='PASS' if len(proof['checks'])==5 and all(x['pass'] for x in proof['checks']) and not proof.get('reason') else 'FAIL'
    return proof
