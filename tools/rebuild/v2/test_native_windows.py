#!/usr/bin/env python3
"""Exact candidate probe on a real Windows desktop; no injected game commands.

Only OS SendInput produces game input. Screenshots are private evidence requiring
human review; pixel diversity is merely a blank-frame guard. Unicode SendInput is
not an IME test. No real user save, account endpoint, or existing install is used.
"""
from __future__ import annotations
import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
import time
import zipfile


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('Unsafe relative path')
    p, w = PurePosixPath(name), PureWindowsPath(name)
    if p.is_absolute() or w.is_absolute() or w.drive or '..' in p.parts or ':' in name:
        raise ValueError('Unsafe relative path')
    dest = (root / Path(*p.parts)).resolve()
    if not dest.is_relative_to(root.resolve()):
        raise ValueError('Path escapes root')
    return dest


def request(path: Path) -> dict:
    d = json.loads(path.read_text(encoding='utf-8'))
    if d.get('schema') != 'baram.v2.native_request/1':
        raise ValueError('Unexpected request schema')
    if not re.fullmatch('[0-9a-f]{40}', d.get('vault_commit', '')):
        raise ValueError('Private vault must use pinned commit SHA')
    for k in ['windows_zip_sha256', 'windows_exe_sha256', 'source_content_fingerprint', 'runtime_manifest_sha256']:
        if not re.fullmatch('[0-9a-f]{64}', d.get(k, '')):
            raise ValueError('Missing exact hash: ' + k)
    if not re.fullmatch('[0-9a-f]{40}', d.get('source_commit', '')):
        raise ValueError('Missing source commit')
    if not d.get('encryption_public_key_pem', '').startswith('-----BEGIN PUBLIC KEY-----'):
        raise ValueError('Session encryption public key required')
    if not d.get('private_manifest_path', '').startswith('v2-native/'):
        raise ValueError('Expected isolated v2-native path')
    return d


def prepare(args: argparse.Namespace) -> int:
    d = request(args.request)
    manifest_path = relative(args.vault, d['private_manifest_path'])
    m = json.loads(manifest_path.read_text(encoding='utf-8'))
    if m.get('schema') != 'baram.v2.native_chunks/1':
        raise ValueError('Unexpected private chunk manifest')
    for k in ['source_commit', 'source_content_fingerprint', 'runtime_manifest_sha256']:
        if m.get(k) != d[k]:
            raise ValueError('Private manifest mismatch: ' + k)
    if m.get('zip_sha256') != d['windows_zip_sha256']:
        raise ValueError('Private ZIP contract mismatch')
    chunks = m.get('chunks', [])
    if not isinstance(chunks, list) or not 1 <= len(chunks) <= 512:
        raise ValueError('Invalid chunk count')
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / 'candidate.zip'
    if destination.exists():
        raise ValueError('Refuse evidence overwrite')
    total = 0
    with destination.open('xb') as out:
        for chunk in chunks:
            path = relative(args.vault, chunk['path'])
            if path.suffix != '.b64' or path.stat().st_size > 12 * 1024 * 1024:
                raise ValueError('Invalid encoded chunk')
            data = base64.b64decode(path.read_bytes(), validate=True)
            if sha(data) != chunk['sha256']:
                raise ValueError('Decoded chunk SHA mismatch')
            total += len(data)
            if total > 512 * 1024 * 1024:
                raise ValueError('Candidate exceeds bounded size')
            out.write(data)
    if sha(destination.read_bytes()) != d['windows_zip_sha256']:
        raise ValueError('Reassembled candidate ZIP SHA mismatch')
    extraction = args.output / 'candidate'
    with zipfile.ZipFile(destination) as z:
        entries = z.infolist()
        if sum(x.file_size for x in entries) > 700 * 1024 * 1024:
            raise ValueError('Expanded candidate exceeds bound')
        seen = set()
        for item in entries:
            p = relative(extraction, item.filename)
            key = str(p).casefold()
            if key in seen or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Duplicate ZIP path or symlink')
            seen.add(key)
        z.extractall(extraction)
    exes = list(extraction.rglob('*.exe'))
    if len(exes) != 1 or sha(exes[0].read_bytes()) != d['windows_exe_sha256']:
        raise ValueError('Exact EXE SHA mismatch')
    (args.output / 'session-public-key.pem').write_text(d['encryption_public_key_pem'], encoding='ascii')
    write(args.output / 'PREPARED.json', {'schema': 'baram.v2.native_prepared/1',
        'exe': str(exes[0].resolve()), 'zip_sha256': d['windows_zip_sha256'],
        'exe_sha256': d['windows_exe_sha256'], 'source_commit': d['source_commit'],
        'source_content_fingerprint': d['source_content_fingerprint'],
        'runtime_manifest_sha256': d['runtime_manifest_sha256'], 'chunks_verified': len(chunks)})
    print('Exact private candidate reconstructed and verified; no binary data logged.')
    return 0


class Desktop:
    def __init__(self, pid: int):
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.SetProcessDPIAware()
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        windows = []
        def visit(hwnd, unused):
            owner = wintypes.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and self.user.IsWindowVisible(hwnd):
                rect = wintypes.RECT()
                self.user.GetClientRect(hwnd, ctypes.byref(rect))
                if rect.right > 300 and rect.bottom > 200:
                    windows.append(hwnd)
            return True
        self.user.EnumWindows.argtypes = [callback, wintypes.LPARAM]
        self.user.EnumWindows(callback(visit), 0)
        if not windows:
            raise RuntimeError('No visible native candidate window')
        self.hwnd = windows[0]
        self.user.ShowWindow(self.hwnd, 9)
        self.user.SetForegroundWindow(self.hwnd)
        time.sleep(.3)
        if self.user.GetForegroundWindow() != self.hwnd:
            raise RuntimeError('Candidate window is not foreground; refuse blind input')
        class Mouse(ctypes.Structure):
            _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                        ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class Keyboard(ctypes.Structure):
            _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                        ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class Payload(ctypes.Union):
            _fields_ = [('mi', Mouse), ('ki', Keyboard)]
        class Input(ctypes.Structure):
            _anonymous_ = ('payload',)
            _fields_ = [('type', wintypes.DWORD), ('payload', Payload)]
        self.Mouse, self.Keyboard, self.Input = Mouse, Keyboard, Input
        self.user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.user.SendInput.restype = wintypes.UINT

    def send(self, item):
        if self.user.GetForegroundWindow() != self.hwnd:
            raise RuntimeError('Lost foreground; input stopped')
        if self.user.SendInput(1, ctypes.byref(item), ctypes.sizeof(item)) != 1:
            raise ctypes.WinError(ctypes.get_last_error())

    def key(self, vk: int, seconds=.06):
        item = self.Input(type=1);item.ki = self.Keyboard(vk, 0, 0, 0, 0);self.send(item)
        time.sleep(seconds)
        item.ki.dwFlags = 2;self.send(item)

    def text(self, text: str):
        for character in text:
            item = self.Input(type=1);item.ki = self.Keyboard(0, ord(character), 4, 0, 0);self.send(item)
            item.ki.dwFlags = 6;self.send(item)

    def bounds(self):
        rect, origin = wintypes.RECT(), wintypes.POINT(0, 0)
        if not self.user.GetClientRect(self.hwnd, ctypes.byref(rect)) or not self.user.ClientToScreen(self.hwnd, ctypes.byref(origin)):
            raise ctypes.WinError(ctypes.get_last_error())
        return origin.x, origin.y, rect.right, rect.bottom

    def click(self, x: float, y: float):
        ox, oy, width, height = self.bounds()
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError('Control is outside native client surface')
        self.user.SetCursorPos(round(ox+x), round(oy+y))
        item = self.Input(type=0);item.mi = self.Mouse(0, 0, 0, 2, 0, 0);self.send(item)
        time.sleep(.08);item.mi.dwFlags=4;self.send(item)

    def screenshot(self, path: Path):
        from PIL import ImageGrab, ImageStat
        x, y, w, h = self.bounds()
        image = ImageGrab.grab(bbox=(x, y, x+w, y+h), all_screens=True)
        image.save(path)
        variance = sum(ImageStat.Stat(image.convert('RGB')).var)
        if w < 600 or h < 400 or variance < 5:
            raise RuntimeError('Missing, undersized or near-uniform native screenshot; no UI PASS')
        return {'filename':path.name,'sha256':sha(path.read_bytes()),'size':[w,h], 'pixel_variance':variance,
                'scope':'OS screenshot captured; diversity is only blank-frame guard; visual review required'}


def wait_for(action, seconds=20):
    until = time.monotonic()+seconds
    while time.monotonic()<until:
        result = action()
        if result is not None:
            return result
        time.sleep(.15)
    raise TimeoutError('Native condition did not arrive before deadline')


def run(args: argparse.Namespace) -> int:
    if os.name != 'nt':
        raise ValueError('Actual Windows required; Linux and Wine refused')
    d=request(args.request);prepared=json.loads((args.output/'PREPARED.json').read_text())
    exe=Path(prepared['exe'])
    if sha(exe.read_bytes()) != d['windows_exe_sha256']:
        raise ValueError('Candidate changed since reconstruction')
    evidence=args.output/'execution';evidence.mkdir()
    user=evidence/'isolated-roaming';user.mkdir()
    env=os.environ.copy();env['APPDATA']=str(user.resolve());env['BARAM_PLAYABILITY_TRACE']='1'
    for key in ['BARAM_GAMEPLAY_RUNTIME','BARAM_GAMEPLAY_REPORT','BARAM_P2_RUNTIME','BARAM_P2_REPORT']:
        env.pop(key,None)
    receipt={'schema':'baram.v2.windows_native/1','status':'RUNNING','platform':sys.platform,
             'source_commit':d['source_commit'],'exe_sha256':d['windows_exe_sha256'],
             'zip_sha256':d['windows_zip_sha256'],'source_content_fingerprint':d['source_content_fingerprint'],
             'runtime_manifest_sha256':d['runtime_manifest_sha256'],'checks':[],'screenshots':[],
             'fingerprint_scope':'Source/runtime fingerprints are pinned export-contract values; exact uploaded ZIP/EXE hashes are measured here. This probe does not reconstruct source provenance from EXE.',
             'scope':'Windows OS EXE, SendInput ordinary creation/navigation/dialogue/close/save/restart; synthetic new profile; no state grants',
             'IME':'NOT_RUN_UNICODE_SENDINPUT_ONLY','physical_input_audio_Galaxy':'NOT_RUN',
             'visual_review':'PENDING_ENCRYPTED_SCREENSHOT_REVIEW'}
    process=None;log=None
    def check(name,value,details=None):
        receipt['checks'].append({'id':name,'status':'PASS' if value else 'FAIL','details':details})
        write(evidence/'RUN_RECEIPT.json',receipt)
        if not value:raise AssertionError(name)
    def records():
        found=[]
        for path in user.rglob('gameplay-checkpoints.jsonl'):
            try: lines=path.read_text(encoding='utf-8',errors='replace').splitlines()
            except OSError: continue
            for line in lines:
                try:
                    row=json.loads(line)
                    if process and row.get('pid')==process.pid:found.append(row)
                except ValueError:pass
        return found
    def layout(label=None):
        rows=[r['details'] for r in records() if r.get('stage')=='ui_layout']
        for row in reversed(rows):
            if label is None or any(c['text']==label for c in row.get('controls',[])):return row
        return None
    def button(desktop,label):
        row=wait_for(lambda:layout(label));control=next(c for c in row['controls'] if c['text']==label)
        x,y,w,h=control['rect'];desktop.click(x+w/2,y+h/2);time.sleep(.4)
    def current_save():
        for path in user.rglob('characters/*.json'):
            try:
                doc=json.loads(path.read_text(encoding='utf-8'));return doc.get('payload')
            except (ValueError,OSError):pass
        return None
    def launch(name):
        nonlocal process,log
        log=(evidence/(name+'.log')).open('w',encoding='utf-8')
        process=subprocess.Popen([str(exe),'--position','20,20','--resolution','1100x720','--rendering-method','gl_compatibility'],env=env,stdout=log,stderr=subprocess.STDOUT,cwd=exe.parent)
        desktop=wait_for(lambda:try_desktop(process),30)
        wait_for(lambda:layout('새 캐릭터'),40)
        check(name+'_ordinary_mode',any(r.get('details',{}).get('mode')=='ordinary_play' for r in records()))
        receipt['screenshots'].append(desktop.screenshot(evidence/(name+'-menu.png')))
        return desktop
    def stop():
        nonlocal process,log
        if process and process.poll() is None:
            desktop.user.PostMessageW(desktop.hwnd,0x0010,0,0)
            process.wait(15)
        if log:log.close()
    try:
        desktop=launch('first')
        button(desktop,'새 캐릭터')
        button(desktop,'name_input')
        desktop.text('윈도우검증')
        button(desktop,'만들고 시작')
        wait_for(lambda:next((r for r in records() if r.get('stage')=='character_created'),None),25)
        original=wait_for(current_save)
        check('ordinary_new_Lv1_commoner',original['character']['level']==1 and original['character']['job']=='commoner')
        receipt['screenshots'].append(desktop.screenshot(evidence/'01-world-created.png'))
        # Real held keyboard input. Candidate autosave supplies observed progress.
        before=(original['character']['map_id'],original['character']['x'],original['character']['y'])
        probe=d.get('npc_probe',{'map_id':'gp:map:domestic_city','x':27,'y':33})
        preferred=[]
        if probe['x']!=original['character']['x']:preferred.append(0x27 if probe['x']>original['character']['x'] else 0x25)
        if probe['y']!=original['character']['y']:preferred.append(0x28 if probe['y']>original['character']['y'] else 0x26)
        directions=list(dict.fromkeys(preferred+[0x27,0x28,0x25,0x26]))
        moved=original;after=before;attempts=[]
        for vk in directions:
            desktop.key(vk,.55);time.sleep(3.3)
            moved=wait_for(current_save)
            after=(moved['character']['map_id'],moved['character']['x'],moved['character']['y'])
            attempts.append({'virtual_key':vk,'saved_cell':after})
            if after!=before:break
        check('OS_SendInput_walk_changes_saved_cell',after!=before,{'before':before,'after':after,'ordinary_direction_attempts':attempts})
        button(desktop,'저장 · 처음으로')
        button(desktop,'이어 하기')
        active=wait_for(lambda:layout('대화'))
        check('ordinary_NPC_probe_same_map',moved['character']['map_id']==probe['map_id'])
        # World click uses the actual logged view transform, not a game command.
        x,y,w,h=active['view_rect'];fx,fy=active['view_focus'];zoom=active['view_zoom']
        desktop.click(x+w/2+((probe['x']+.5)*24-fx)*zoom,y+h/2+((probe['y']+.5)*24-fy)*zoom)
        wait_for(lambda:layout('X'),30)
        receipt['screenshots'].append(desktop.screenshot(evidence/'02-NPC-dialogue.png'))
        button(desktop,'X')
        # Closing emits a new layout with no close control; stale dialogue rows
        # must not satisfy the assertion below.
        wait_for(lambda:layout() if layout() and not any(c['text']=='X' for c in layout()['controls']) else None,10)
        check('NPC_X_closed_by_OS_mouse',True)
        receipt['screenshots'].append(desktop.screenshot(evidence/'03-NPC-closed.png'))
        button(desktop,'저장 · 처음으로')
        saved=wait_for(current_save);stop()
        check('ordinary_process_clean_exit',process.returncode==0,process.returncode)
        desktop=launch('restart')
        button(desktop,'이어 하기')
        loaded=wait_for(lambda:next((r['details'] for r in records() if r.get('stage')=='loaded'),None))
        expected=saved['character'];actual=loaded['character']
        keys=['name','map_id','x','y','level','job']
        check('native_restart_retains_character_cell',all(actual.get(k)==expected.get(k)for k in keys),{k:actual.get(k)for k in keys})
        receipt['screenshots'].append(desktop.screenshot(evidence/'04-resumed.png'))
        button(desktop,'저장 · 처음으로');stop()
        check('restart_process_clean_exit',process.returncode==0,process.returncode)
        receipt['status']='PASS_NATIVE_OS_INPUT_SAVE_RESTART_PENDING_VISUAL_REVIEW'
        return 0
    except Exception as error:
        receipt['status']='FAIL_NATIVE_PROBE';receipt['error']=type(error).__name__+': '+str(error)
        return 1
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(8)
            except subprocess.TimeoutExpired:process.kill()
        if log and not log.closed:log.close()
        write(evidence/'RUN_RECEIPT.json',receipt)
        print(json.dumps({'status':receipt['status'],'checks':len(receipt['checks']),
                          'visual_review':receipt['visual_review'],'screenshots':len(receipt['screenshots'])}))


def try_desktop(process):
    if process.poll() is not None:raise RuntimeError('Candidate process exited before UI')
    try:return Desktop(process.pid)
    except RuntimeError:return None


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','run','public-summary'])
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--vault',type=Path,default=Path('vault'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--summary',type=Path)
    a=p.parse_args()
    if a.mode=='prepare':return prepare(a)
    if a.mode=='run':return run(a)
    d=request(a.request);path=a.output/'execution/RUN_RECEIPT.json'
    receipt=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'status':'BLOCKED_BEFORE_NATIVE_PROBE','checks':[]}
    public={k:receipt.get(k)for k in ['schema','status','platform','exe_sha256','zip_sha256','source_commit','source_content_fingerprint','runtime_manifest_sha256','fingerprint_scope','scope','IME','physical_input_audio_Galaxy','visual_review']}
    public['check_results']=[{'id':x['id'],'status':x['status']}for x in receipt.get('checks',[])]
    public['screenshots']='ENCRYPTED_ONLY_NO_PUBLIC_PLAINTEXT';public['account_sync']='NOT_TESTED_BY_NATIVE_PROBE'
    write(a.summary,public)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
