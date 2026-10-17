#!/usr/bin/env python3
"""Hash-pinned Android APK update and ordinary ADB touch probe on a fresh KVM AVD.

No gameplay command, XP grant, save fixture or explicit smoke path is injected.
run-as reads diagnostic/save evidence and writes only an observation marker.
Screens and logs remain private. Pixel diversity is only a blank-frame guard;
visual review and real Galaxy/IME/listening certification remain separate.
"""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time

PACKAGE = 'com.irewon.baram.p3repair20261016'
RETAINED_CERT = 'c0bc3989d93d7b9443bbfa59281797a48e2b020e5da4b1dc91858768b35ccd05'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe relative path')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Path escapes root')
    dest = (root / Path(*path.parts)).resolve()
    if not dest.is_relative_to(root.resolve()):
        raise ValueError('Path escapes root')
    return dest


def request(path: Path) -> dict:
    d = json.loads(path.read_text(encoding='utf-8'))
    if d.get('schema') != 'baram.v2.android_native_request/1':
        raise ValueError('Unexpected request schema')
    for k in ['vault_commit', 'source_commit']:
        if not re.fullmatch('[0-9a-f]{40}', d.get(k, '')):
            raise ValueError('Pinned commit required: '+k)
    for k in ['new_apk_sha256','old_apk_sha256','source_content_fingerprint','runtime_manifest_sha256']:
        if not re.fullmatch('[0-9a-f]{64}', d.get(k, '')):
            raise ValueError('Exact hash required: '+k)
    old_version, new_version = d.get('old_version_code'), d.get('new_version_code')
    if (d.get('package') != PACKAGE or type(old_version) is not int or old_version != 3
            or type(new_version) is not int or new_version < 4 or new_version <= old_version):
        raise ValueError('Retained repair package and increasing code 3 to code 4 or newer required')
    if 'retained_signer_sha256' in d and d['retained_signer_sha256'] != RETAINED_CERT:
        raise ValueError('Request signer differs from retained repair identity')
    if not d.get('private_manifest_path','').startswith('v2-native/'):
        raise ValueError('Isolated private manifest required')
    if not d.get('encryption_public_key_pem','').startswith('-----BEGIN PUBLIC KEY-----'):
        raise ValueError('Session encryption public key required')
    return d


def apk_manifest(raw: bytes) -> dict:
    match = re.search(rb"^package: name='([^']+)' versionCode='([0-9]+)'", raw, re.MULTILINE)
    if not match:
        raise ValueError('Cannot read measured APK package/version from aapt badging')
    return {'package': match[1].decode('utf-8'), 'version_code': int(match[2])}


def installed_version_codes(raw: bytes) -> list[int]:
    return [int(value) for value in re.findall(rb'^\s*versionCode=([0-9]+)(?:\s|$)', raw, re.MULTILINE)]


def prepare(args) -> int:
    d = request(args.request)
    m = json.loads(relative(args.vault,d['private_manifest_path']).read_text(encoding='utf-8'))
    if m.get('schema') != 'baram.v2.android_native_chunks/1':
        raise ValueError('Unexpected private APK chunk manifest')
    for k in ['source_commit','source_content_fingerprint','runtime_manifest_sha256','new_apk_sha256','old_apk_sha256']:
        if m.get(k) != d[k]:
            raise ValueError('Private manifest does not match request: '+k)
    for k in ['package', 'old_version_code', 'new_version_code', 'retained_signer_sha256']:
        if k in m and m[k] != d.get(k, RETAINED_CERT if k == 'retained_signer_sha256' else None):
            raise ValueError('Private APK install contract does not match request: '+k)
    args.output.mkdir(parents=True,exist_ok=True)
    args.inputs.mkdir(parents=True,exist_ok=True)
    prepared = {'schema':'baram.v2.android_native_prepared/1'}
    for label in ['new','old']:
        chunks = m.get(label+'_apk_chunks',[])
        if not isinstance(chunks,list) or not 1 <= len(chunks) <= 512:
            raise ValueError('Invalid APK chunk count')
        destination = args.inputs/(label+'.apk')
        total = 0
        with destination.open('xb') as out:
            for chunk in chunks:
                p=relative(args.vault,chunk['path'])
                if p.suffix!='.b64' or p.stat().st_size>12*1024*1024:
                    raise ValueError('Invalid encoded chunk')
                data=base64.b64decode(p.read_bytes(),validate=True)
                if sha(data)!=chunk['sha256']:
                    raise ValueError('Decoded chunk hash mismatch')
                total+=len(data)
                if total>512*1024*1024:
                    raise ValueError('APK exceeds bounded size')
                out.write(data)
        if sha(destination.read_bytes()) != d[label+'_apk_sha256']:
            raise ValueError('Exact APK hash mismatch')
        prepared[label+'_apk']=str(destination.resolve())
        prepared[label+'_chunks_verified']=len(chunks)
    prepared.update({k:d[k]for k in ['source_commit','source_content_fingerprint','runtime_manifest_sha256','new_apk_sha256','old_apk_sha256']})
    write(args.output/'PREPARED.json',prepared)
    (args.output/'session-public-key.pem').write_text(d['encryption_public_key_pem'],encoding='ascii')
    print('Both exact private APKs reconstructed and verified; binary data is not logged.')
    return 0


class Probe:
    def __init__(self,args,d):
        self.args,self.d=args,d
        self.out=args.output/'execution';self.out.mkdir()
        self.base=[str(args.android_sdk/'platform-tools/adb'),'-s',args.serial]
        self.deadline=time.monotonic()+args.budget_seconds
        self.counter=0;self.pid=None;self.files=[];self.rows=[];self.recording=None;self.closing=False
        self.receipt={'schema':'baram.v2.android_native/1','status':'RUNNING',
            **{k:d[k]for k in ['new_apk_sha256','old_apk_sha256','source_commit','source_content_fingerprint','runtime_manifest_sha256']},
            'platform':'Android API35 x86_64 KVM emulator on standard public Ubuntu24.04 runner',
            'checks':[],'screenshots':[],'commands':[],
            'package':PACKAGE,'old_version_code':d['old_version_code'],'new_version_code':d['new_version_code'],
            'scope':f"Exact APK ordinary launch, ADB OS touch creation/walk/dialogue close/save/restart plus code{d['old_version_code']} to code{d['new_version_code']} update. Synthetic new characters without state grants.",
            'fingerprint_scope':'Source/runtime fingerprints are pinned exporter contracts. APK bytes are measured here; embedded source provenance is not reconstructed.',
            'visual_review':'PENDING_ENCRYPTED_SCREENSHOT_REVIEW','smoke_fixture':'NOT_RUN',
            'physical_Galaxy':'NOT_RUN','physical_IME':'NOT_RUN_ASCII_ADB_INPUT_ONLY',
            'physical_listening':'NOT_RUN','account_sync':'NOT_TESTED_BY_NATIVE_PROBE',
            'performance_scope':'Emulator observation only; not Galaxy certification; screen recording enabled'}
        self.save()

    def save(self):write(self.out/'RUN_RECEIPT.json',self.receipt)

    def check(self,label,condition,details=None):
        self.receipt['checks'].append({'id':label,'status':'PASS' if condition else 'FAIL','details':details});self.save()
        if not condition:raise AssertionError(label)

    def command(self,parts,label,*,timeout=25,allow=False,binary=False):
        if not self.closing and time.monotonic()>self.deadline:raise TimeoutError('Bounded probe budget expired')
        self.counter+=1;path=self.out/('%03d-%s.%s'%(self.counter,label,'bin'if binary else'log'))
        began=time.time_ns()
        r=subprocess.run(parts,capture_output=True,timeout=timeout if self.closing else min(timeout,max(1,self.deadline-time.monotonic())))
        path.write_bytes(r.stdout+(b''if binary else b'\nSTDERR\n'+r.stderr))
        entry={'id':label,'exit_code':r.returncode,'log':path.name,'bytes':len(r.stdout),'start_unix_ns':began,'end_unix_ns':time.time_ns()}
        if 'input'in parts:entry['OS_input_arguments']=parts[parts.index('input')+1:]
        self.receipt['commands'].append(entry)
        self.save()
        if r.returncode and not allow:raise RuntimeError('OS command failed: '+label)
        return r.stdout

    def adb(self,parts,label,**kw):return self.command(self.base+parts,label,**kw)

    def wait(self,action,seconds=25):
        until=min(self.deadline,time.monotonic()+seconds)
        while time.monotonic()<until:
            value=action()
            if value is not None:return value
            time.sleep(.5)
        raise TimeoutError('Observed Android condition did not arrive')

    def refresh(self):
        if not self.files:
            raw=self.adb(['shell','run-as',PACKAGE,'find','files','-maxdepth','6','-type','f'],'find-private-diagnostics',allow=True)
            self.files=[p for p in raw.decode(errors='replace').splitlines()if re.fullmatch(r'files(?:/[A-Za-z0-9_.-]+)+',p)]
        logs=[p for p in self.files if p.endswith('/gameplay-checkpoints.jsonl')]
        rows=[]
        for p in logs:
            raw=self.adb(['exec-out','run-as',PACKAGE,'cat',p],'read-checkpoints',allow=True)
            for line in raw.decode(errors='replace').splitlines():
                try:
                    row=json.loads(line)
                    if self.pid and row.get('pid')==self.pid:rows.append(row)
                except ValueError:pass
        self.rows=rows
        return rows

    def layout(self,label=None):
        self.refresh()
        candidates=[r['details']for r in self.rows if r.get('stage')=='ui_layout']
        if not candidates:return None
        last=candidates[-1]
        if label is not None and not any(c['text']==label for c in last.get('controls',[])):return None
        return last

    def stage(self,name):
        self.refresh()
        return next((r['details']for r in reversed(self.rows)if r.get('stage')==name),None)

    def saved(self):
        raw=self.adb(['shell','run-as',PACKAGE,'find','files','-maxdepth','7','-type','f'],'find-saves',allow=True)
        found=[]
        for path in raw.decode(errors='replace').splitlines():
            if '/characters/' not in path or not path.endswith('.json')or not re.fullmatch(r'files(?:/[A-Za-z0-9_.-]+)+',path):continue
            data=self.adb(['exec-out','run-as',PACKAGE,'cat',path],'read-save',allow=True)
            try:
                doc=json.loads(data)
                if isinstance(doc.get('payload'),dict):found.append((path,doc['payload'],data))
            except ValueError:pass
        return found

    def named_save(self,name):return next((x for x in self.saved()if x[1].get('character',{}).get('name')==name),None)

    def screenshot(self,label):
        from PIL import Image,ImageStat
        raw=self.adb(['exec-out','screencap','-p'],'screen-'+label,binary=True)
        path=self.out/(label+'.png');path.write_bytes(raw)
        im=Image.open(io.BytesIO(raw));im.load()
        variance=sum(ImageStat.Stat(im.convert('RGB')).var)
        self.check('nonblank_capture_'+label,im.width>=600 and im.height>=400 and variance>=5,
                   {'scope':'Blank-frame guard only; does not establish visible game UI','width':im.width,'height':im.height,'variance':variance})
        self.receipt['screenshots'].append({'filename':path.name,'sha256':sha(raw),'size':list(im.size)})
        self.save();return path

    def ocr(self,path):
        raw=self.command(['tesseract',str(path),'stdout','-l','kor+eng','--psm','11','tsv'],'screenshot-ocr')
        lines={}
        for row in csv.DictReader(io.StringIO(raw.decode(errors='replace')),delimiter='\t'):
            if not row.get('text','').strip():continue
            key=tuple(row[k]for k in ['page_num','block_num','par_num','line_num'])
            lines.setdefault(key,[]).append(row)
        result=[]
        for words in lines.values():
            left=min(int(w['left'])for w in words);top=min(int(w['top'])for w in words)
            right=max(int(w['left'])+int(w['width'])for w in words)
            bottom=max(int(w['top'])+int(w['height'])for w in words)
            result.append({'text':''.join(w['text']for w in words),'center':[(left+right)/2,(top+bottom)/2]})
        return result

    def tap(self,x,y,label):self.adb(['shell','input','tap',str(round(x)),str(round(y))],'tap-'+label);time.sleep(.5)

    def ocr_button(self,text,label):
        path=self.screenshot(label+'-before-input');rows=self.ocr(path)
        normalized=lambda s:re.sub(r'[^0-9A-Za-z가-힣]','',s)
        matches=[r for r in rows if normalized(text)in normalized(r['text'])]
        self.check('visible_OCR_control_'+label,len(matches)==1,{'match_count':len(matches),'method':'Korean screenshot OCR; no game callback'})
        self.tap(*matches[0]['center'],label)

    def frame(self):
        raw=self.adb(['shell','dumpsys','window','windows'],'window-frame').decode(errors='replace')
        for block in re.split(r'\n\s*Window #',raw):
            if PACKAGE not in block[:400]:continue
            match=re.search(r'(?:mFrame=|\bframe=)\[(\d+),(\d+)\]\[(\d+),(\d+)\]',block)
            if match:return tuple(map(int,match.groups()))
        raw=self.adb(['shell','dumpsys','activity','activities'],'activity-frame').decode(errors='replace')
        matches=re.findall(r'mAppBounds=Rect\((\d+),\s*(\d+)\s*-\s*(\d+),\s*(\d+)\)',raw)
        if matches:return tuple(map(int,matches[-1]))
        raise RuntimeError('Cannot establish OS-observed application surface bounds')

    def xy(self,x,y):
        self.refresh()
        rows=[r['details']['viewport']for r in self.rows if r.get('stage')=='process_ready'and'viewport'in r.get('details',{})]
        if not rows:raise RuntimeError('No viewport diagnostics for OS coordinate mapping')
        vw,vh=rows[-1];left,top,right,bottom=self.frame()
        return left+x*(right-left)/vw,top+y*(bottom-top)/vh

    def button(self,label):
        row=self.wait(lambda:self.layout(label));control=next(c for c in row['controls']if c['text']==label)
        x,y,w,h=control['rect'];self.tap(*self.xy(x+w/2,y+h/2),label)

    def select_character(self,name):
        row=self.wait(lambda:self.layout('이어 하기'))
        dropdowns=[c for c in row['controls']if c.get('class')=='OptionButton'and'Lv'in c['text']]
        self.check('character_picker_observed',len(dropdowns)==1)
        if name in dropdowns[0]['text']:return
        x,y,w,h=dropdowns[0]['rect'];self.tap(*self.xy(x+w/2,y+h/2),'character-dropdown')
        self.ocr_button(name,'choose-'+name)

    def capture_system(self,label):
        for parts,name in [(['shell','getprop'],'properties'),(['shell','dumpsys','meminfo',PACKAGE],'memory'),
                           (['shell','dumpsys','SurfaceFlinger'],'surfaceflinger'),(['shell','dumpsys','gfxinfo',PACKAGE,'framestats'],'framestats')]:
            self.adb(parts,label+'-'+name,allow=True)

    def collect_observation(self):
        raw=self.adb(['shell','run-as',PACKAGE,'find','files','-maxdepth','6','-type','f'],'find-final-observation',allow=True)
        for path in raw.decode(errors='replace').splitlines():
            if not re.fullmatch(r'files(?:/[A-Za-z0-9_.-]+)+',path):continue
            if PurePosixPath(path).name not in ['playability-frame-timeline.jsonl','gameplay-checkpoints.jsonl']:continue
            data=self.adb(['exec-out','run-as',PACKAGE,'cat',path],'collect-final-'+PurePosixPath(path).stem,binary=True,allow=True)
            (self.out/PurePosixPath(path).name).write_bytes(data)

    def launch(self,label,observe=False):
        self.adb(['shell','am','force-stop',PACKAGE],'stop-before-'+label)
        self.files=[]
        if observe:
            # Observation-only marker, never a smoke request or mutable game state.
            raw=self.adb(['shell','run-as',PACKAGE,'find','files','-maxdepth','6','-name','gameplay-checkpoints.jsonl'],'find-userdata',allow=True)
            paths=[p for p in raw.decode().splitlines()if re.fullmatch(r'files(?:/[A-Za-z0-9_.-]+)+',p)]
            folder=str(PurePosixPath(paths[-1]).parent)if paths else'files'
            self.adb(['shell','run-as',PACKAGE,'touch',folder+'/playability-observe.enabled'],'enable-observation-only')
        self.adb(['shell','am','start','-W','-n',PACKAGE+'/com.godot.game.GodotAppLauncher'],'launch-'+label,timeout=70)
        self.pid=int(self.wait(lambda:self.process_pid(),40))
        self.wait(lambda:self.stage('scene'),60)
        self.check(label+'_ordinary_mode',self.stage('scene').get('mode')=='ordinary_play')
        self.wait(lambda:self.stage('process_ready'),50)
        self.screenshot(label+'-menu')

    def process_pid(self):
        raw=self.adb(['shell','pidof',PACKAGE],'live-process',allow=True).decode().strip()
        return raw.split()[0]if raw else None

    def record_start(self,label):
        self.record_stop()
        remote='/sdcard/baram-v2-native-'+label+'.mp4'
        log=(self.out/('record-'+label+'.log')).open('wb')
        proc=subprocess.Popen(self.base+['shell','screenrecord','--bit-rate','3000000','--time-limit','180',remote],stdout=log,stderr=subprocess.STDOUT)
        self.recording=(proc,remote,log,label)

    def record_stop(self):
        if not self.recording:return
        proc,remote,log,label=self.recording
        self.adb(['shell','pkill','-2','screenrecord'],'stop-record-'+label,allow=True)
        try:proc.wait(15)
        except subprocess.TimeoutExpired:proc.terminate()
        log.close()
        self.adb(['pull',remote,str(self.out/('ordinary-'+label+'.mp4'))],'pull-video-'+label,timeout=45,allow=True)
        self.recording=None

    def create_old(self):
        self.launch('old-code3');self.record_start('old-code3')
        self.ocr_button('새 캐릭터','old-new-character')
        # Creation screen focuses its ordinary name LineEdit. ASCII ADB text is
        # explicitly not Korean IME verification.
        self.adb(['shell','input','text','NativeOld'],'old-name-input');time.sleep(.5)
        self.adb(['shell','input','keyevent','KEYCODE_BACK'],'old-hide-keyboard');time.sleep(.5)
        self.ocr_button('만들고 시작','old-create')
        saved=self.wait(lambda:self.named_save('NativeOld'),45)
        self.check('old_code3_normal_Lv1_creation',saved[1]['character']['level']==1 and saved[1]['character']['job']=='commoner')
        self.screenshot('old-code3-created')
        self.adb(['shell','input','keyevent','KEYCODE_BACK'],'old-normal-save-menu');time.sleep(1)
        saved=self.wait(lambda:self.named_save('NativeOld'))
        (self.out/'old-code3-save-before-update.json').write_bytes(saved[2])
        self.record_stop();return saved

    def install(self,apk,label,expected,expected_version):
        raw=self.adb(['install','-r','--no-incremental','--no-streaming',str(apk)],'install-'+label,timeout=150)
        self.check(label+'_install_success',b'Success'in raw)
        path=self.adb(['shell','pm','path',PACKAGE],label+'-installed-path').decode().strip().removeprefix('package:')
        if not re.fullmatch(r'/data/app/[A-Za-z0-9_./=+-]+/base\.apk',path):raise RuntimeError('Unexpected installed APK path')
        raw=self.adb(['shell','sha256sum',path],label+'-installed-byte-hash')
        self.check(label+'_installed_exact_apk',raw.decode().startswith(expected+' '))
        raw=self.adb(['shell','dumpsys','package',PACKAGE],label+'-installed-package-version')
        versions=installed_version_codes(raw)
        self.check(label+'_installed_package_version',bool(versions)and all(v==expected_version for v in versions),
                   {'requested_version':expected_version,'observed_version_codes':versions})

    def run_new(self,old_saved):
        version=self.d['new_version_code'];new_label='new-code'+str(version)
        self.launch(new_label,observe=True);self.record_start(new_label)
        if old_saved:
            preserved=self.wait(lambda:self.named_save('NativeOld'))
            self.check(f'code3_to{version}_update_preserves_save_bytes',preserved[2]==old_saved[2],{'before':sha(old_saved[2]),'after':sha(preserved[2])})
            self.button('이어 하기')
            loaded=self.wait(lambda:self.stage('loaded'))
            self.check(f'code{version}_reads_old_character',all(loaded['character'].get(k)==old_saved[1]['character'].get(k)for k in ['name','level','job','map_id','x','y']))
            self.screenshot('updated-old-character-resumed')
            self.button('저장 · 처음으로')
        self.button('새 캐릭터');self.button('name_input')
        self.adb(['shell','input','text','NativeNew'],'new-name-input');time.sleep(.5)
        self.adb(['shell','input','keyevent','KEYCODE_BACK'],'new-hide-keyboard');time.sleep(.5)
        self.button('만들고 시작')
        original=self.wait(lambda:self.named_save('NativeNew'))
        self.check(f'new_code{version}_ordinary_Lv1_creation',original[1]['character']['level']==1 and original[1]['character']['job']=='commoner')
        self.screenshot(new_label+'-created')
        row=self.wait(lambda:self.layout('대화'));x,y,w,h=row['view_rect']
        before=tuple(original[1]['character'][k]for k in ['map_id','x','y'])
        after=before
        for dx,dy in [(1,0),(0,1),(-1,0),(0,-1)]:
            start=self.xy(x+w*.4,y+h*.55);end=self.xy(x+w*.4+dx*85,y+h*.55+dy*85)
            self.adb(['shell','input','swipe',*map(lambda a:str(round(a)),[*start,*end]),'800'],'ordinary-touch-drag')
            time.sleep(3.3)
            saved=self.wait(lambda:self.named_save('NativeNew'))
            after=tuple(saved[1]['character'][k]for k in ['map_id','x','y'])
            if after!=before:break
        self.check('ADB_touch_walk_changes_saved_cell',after!=before,{'before':before,'after':after})
        self.button('저장 · 처음으로');self.select_character('NativeNew');self.button('이어 하기')
        row=self.wait(lambda:self.layout('대화'))
        npc=self.d.get('npc_probe',{'map_id':'gp:map:domestic_city','x':27,'y':33})
        saved=self.wait(lambda:self.named_save('NativeNew'))
        self.check('ordinary_NPC_same_map',saved[1]['character']['map_id']==npc['map_id'])
        x,y,w,h=row['view_rect'];fx,fy=row['view_focus'];zoom=row['view_zoom']
        tx=x+w/2+((npc['x']+.5)*24-fx)*zoom;ty=y+h/2+((npc['y']+.5)*24-fy)*zoom
        self.check('ordinary_NPC_within_visible_world',x<=tx<x+w and y<=ty<y+h)
        self.tap(*self.xy(tx,ty),'visible-NPC')
        self.wait(lambda:self.layout('X'),30);self.screenshot('NPC-dialogue-open')
        self.button('X')
        self.wait(lambda:True if self.layout()and not any(c['text']=='X'for c in self.layout()['controls'])else None,10)
        self.check('NPC_X_closed_by_ADB_touch',True);self.screenshot('NPC-dialogue-closed')
        self.button('저장 · 처음으로')
        saved=self.wait(lambda:self.named_save('NativeNew'))
        self.capture_system('after-ordinary-play');self.record_stop()
        self.launch('restart-code'+str(version),observe=True)
        self.select_character('NativeNew')
        self.button('이어 하기')
        loaded=self.wait(lambda:self.stage('loaded'))
        self.check('force_stop_restart_retains_character',all(loaded['character'].get(k)==saved[1]['character'].get(k)for k in ['name','level','job','map_id','x','y']),{'loaded_character':loaded['character']})
        self.screenshot(new_label+'-resumed');self.button('저장 · 처음으로')
        self.refresh()
        self.receipt['observed_engine_performance']=[r['details']for r in self.rows if r.get('stage')in ['performance','frame_timing']]


def run(args) -> int:
    if os.name!='posix' or not args.serial.startswith('emulator-'):
        raise ValueError('Fresh Linux KVM Android emulator required')
    d=request(args.request);prepared=json.loads((args.output/'PREPARED.json').read_text())
    probe=Probe(args,d);old_saved=None;failed=False;stream=None
    try:
        # Metadata and retained signer are verified before either installation.
        build=args.android_sdk/'build-tools/35.0.1'
        for label in ['old','new']:
            apk=Path(prepared[label+'_apk'])
            probe.check(label+'_exact_input_hash',sha(apk.read_bytes())==d[label+'_apk_sha256'])
            raw=probe.command([str(build/'aapt'),'dump','badging',str(apk)],label+'-badging')
            measured=apk_manifest(raw)
            probe.receipt.setdefault('measured_apk_manifests',{})[label]=measured
            probe.check(label+'_package_version',measured=={'package':PACKAGE,'version_code':d[label+'_version_code']},measured)
            raw=probe.command([str(build/'apksigner'),'verify','--print-certs',str(apk)],label+'-signature')
            cert=re.search(rb'certificate SHA-256 digest: ([0-9a-f]{64})',raw)
            probe.check(label+'_retained_signer',bool(cert)and cert[1].decode()==RETAINED_CERT)
        probe.command([str(args.android_sdk/'emulator/emulator'),'-accel-check'],'hardware-acceleration')
        probe.adb(['shell','getprop','ro.kernel.qemu'],'emulator-property')
        probe.capture_system('before-install')
        stream=(probe.out/'logcat-all.log').open('wb')
        logger=subprocess.Popen(probe.base+['logcat','-b','all','-v','threadtime'],stdout=stream,stderr=subprocess.STDOUT)
        probe.install(Path(prepared['old_apk']),'old-code3',d['old_apk_sha256'],d['old_version_code'])
        try:old_saved=probe.create_old()
        except Exception as error:
            failed=True;probe.receipt['old_update_setup_failure']=type(error).__name__+': '+str(error);probe.save()
            try:probe.screenshot('old-setup-failed')
            except Exception:pass
            probe.record_stop()
        probe.install(Path(prepared['new_apk']),'new-code'+str(d['new_version_code']),d['new_apk_sha256'],d['new_version_code'])
        try:probe.run_new(old_saved)
        except Exception as error:
            failed=True;probe.receipt['new_probe_failure']=type(error).__name__+': '+str(error);probe.save()
            try:probe.screenshot('new-probe-failed')
            except Exception:pass
        probe.receipt['status']='FAIL_NATIVE_PROBE'if failed else'PASS_NATIVE_TOUCH_UPDATE_SAVE_RESTART_PENDING_VISUAL_REVIEW'
        return 1 if failed else 0
    except Exception as error:
        probe.receipt['status']='FAIL_NATIVE_PROBE';probe.receipt['error']=type(error).__name__+': '+str(error)
        return 1
    finally:
        probe.closing=True
        try:probe.record_stop()
        except Exception:pass
        try:
            probe.collect_observation()
            probe.capture_system('final')
            probe.adb(['shell','am','force-stop',PACKAGE],'stop-after-probe',allow=True)
        except Exception:pass
        if 'logger'in locals():
            logger.terminate()
            try:logger.wait(10)
            except subprocess.TimeoutExpired:logger.kill()
        if stream:stream.close()
        probe.save()
        print(json.dumps({'status':probe.receipt['status'],'checks':len(probe.receipt['checks']),'screenshots':len(probe.receipt['screenshots']),'visual_review':probe.receipt['visual_review']}))


def public_summary(args) -> int:
    d=request(args.request);path=args.output/'execution/RUN_RECEIPT.json'
    receipt=json.loads(path.read_text())if path.exists()else{'status':'BLOCKED_BEFORE_ANDROID_PROBE','checks':[]}
    public={k:receipt.get(k,d.get(k))for k in ['schema','status','platform','package','old_version_code','new_version_code','measured_apk_manifests','new_apk_sha256','old_apk_sha256','source_commit','source_content_fingerprint','runtime_manifest_sha256','scope','fingerprint_scope','visual_review','smoke_fixture','physical_Galaxy','physical_IME','physical_listening','account_sync','performance_scope']}
    public['check_results']=[{'id':x['id'],'status':x['status']}for x in receipt.get('checks',[])]
    public['screenshots_videos_logs']='ENCRYPTED_ONLY_NO_PUBLIC_PLAINTEXT'
    write(args.summary,public);return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','run','public-summary'])
    p.add_argument('--request',type=Path,required=True);p.add_argument('--vault',type=Path,default=Path('vault'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--inputs',type=Path,default=Path('private-candidate-apks'))
    p.add_argument('--android-sdk',type=Path,default=Path(os.environ.get('ANDROID_HOME','/usr/local/lib/android/sdk')))
    p.add_argument('--serial',default='emulator-5554');p.add_argument('--budget-seconds',type=int,default=300)
    p.add_argument('--summary',type=Path)
    a=p.parse_args()
    return prepare(a)if a.mode=='prepare'else run(a)if a.mode=='run'else public_summary(a)


if __name__=='__main__':raise SystemExit(main())
