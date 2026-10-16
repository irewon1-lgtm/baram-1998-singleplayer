"""Explicit synthetic X11 events for ordinary-app tests; not hardware/IME input."""
import ctypes as C
import json
import os
import time

class Key(C.Structure):
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('window',C.c_ulong),('root',C.c_ulong),('subwindow',C.c_ulong),('time',C.c_ulong),('x',C.c_int),('y',C.c_int),('x_root',C.c_int),('y_root',C.c_int),('state',C.c_uint),('keycode',C.c_uint),('same_screen',C.c_int)]
class Event(C.Union):
    _fields_=[('key',Key),('padding',C.c_long*24)]

class X11:
    def __init__(self,env):
        os.environ['XAUTHORITY']=env['XAUTHORITY']
        self.x=C.CDLL('libX11.so.6')
        for name,ret,args in [('XOpenDisplay',C.c_void_p,[C.c_char_p]),('XDefaultRootWindow',C.c_ulong,[C.c_void_p]),
            ('XQueryTree',C.c_int,[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.POINTER(C.c_ulong)),C.POINTER(C.c_uint)]),
            ('XFetchName',C.c_int,[C.c_void_p,C.c_ulong,C.POINTER(C.c_char_p)]),('XStringToKeysym',C.c_ulong,[C.c_char_p]),
            ('XKeysymToKeycode',C.c_uint,[C.c_void_p,C.c_ulong]),('XSetInputFocus',C.c_int,[C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]),
            ('XSendEvent',C.c_int,[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)]),('XFlush',C.c_int,[C.c_void_p]),
            ('XFree',C.c_int,[C.c_void_p]),('XCloseDisplay',C.c_int,[C.c_void_p])]:
            f=getattr(self.x,name);f.restype=ret;f.argtypes=args
        self.display=self.x.XOpenDisplay(env['DISPLAY'].encode())
        if not self.display:raise RuntimeError('XOpenDisplay failed')
        self.root=self.x.XDefaultRootWindow(self.display)
        self.window=self.find(self.root)
        if not self.window:raise RuntimeError('Godot ordinary window not found')
        self.x.XSetInputFocus(self.display,self.window,2,0);self.x.XFlush(self.display)
    def find(self,window,depth=0):
        name=C.c_char_p()
        if self.x.XFetchName(self.display,window,C.byref(name)) and name.value:
            title=name.value.decode(errors='replace');self.x.XFree(name)
            if 'Baram First Journey' in title:return window
        if depth>4:return 0
        root=C.c_ulong();parent=C.c_ulong();children=C.POINTER(C.c_ulong)();count=C.c_uint()
        if not self.x.XQueryTree(self.display,window,C.byref(root),C.byref(parent),C.byref(children),C.byref(count)):return 0
        values=[children[i] for i in range(count.value)]
        if children:self.x.XFree(children)
        for child in values:
            result=self.find(child,depth+1)
            if result:return result
        return 0
    def event(self,kind,code,x=1,y=1):
        e=Event();e.key=Key(kind,0,1,self.display,self.window,self.root,0,0,int(x),int(y),int(x),int(y),0,code,1)
        mask={2:1,3:2,4:4,5:8}[kind]
        if not self.x.XSendEvent(self.display,self.window,0,mask,C.byref(e)):raise RuntimeError('XSendEvent refused')
        self.x.XFlush(self.display)
    def click(self,rect):
        x=rect[0]+rect[2]/2;y=rect[1]+rect[3]/2
        self.event(4,1,x,y);time.sleep(.07);self.event(5,1,x,y);time.sleep(.25)
    def key(self,name,hold=.05):
        code=self.x.XKeysymToKeycode(self.display,self.x.XStringToKeysym(name.encode()))
        if not code:raise ValueError('Unmapped keysym '+name)
        self.event(2,code);time.sleep(hold);self.event(3,code);time.sleep(.03)
    def text(self,value):
        for char in value:self.key(char,.02)
    def close(self):self.x.XCloseDisplay(self.display)

def checkpoints(path):
    if not path.exists():return []
    result=[]
    for line in path.read_text().splitlines():
        try:result.append(json.loads(line))
        except json.JSONDecodeError:pass
    return result

def control(path,text):
    for row in reversed(checkpoints(path)):
        if row.get('stage')=='ui_layout':
            for c in row['details']['controls']:
                if c['text']==text:return c['rect']
    raise RuntimeError('Visible control missing: '+text)

def probe(env,out):
    checkpoint=out/'isolated-data/baram_rebuild_gameplay_001/gameplay-checkpoints.jsonl'
    saves=out/'isolated-data/baram_rebuild_gameplay_001/gameplay-p3/characters'
    x=X11(env);proof={'method':'synthetic X11 mouse and physical-key events; ASCII name, not IME','checks':[]}
    try:
        x.click(control(checkpoint,'새 캐릭터'))
        time.sleep(.3)
        x.text('canceltest')
        x.click(control(checkpoint,'취소'))
        proof['checks'].append({'id':'ordinary_creation_cancel_zero_save','pass':not list(saves.glob('*.json'))})
        x.click(control(checkpoint,'새 캐릭터'));time.sleep(.2)
        x.text('playtester')
        x.click(control(checkpoint,'만들고 시작'));time.sleep(.8)
        files=list(saves.glob('*.json'))
        proof['checks'].append({'id':'ordinary_creation_saved_by_UI','pass':len(files)==1})
        if len(files)!=1:raise RuntimeError('Character creation did not produce one save')
        first=json.loads(files[0].read_text())['payload']
        x.key('Right',.7);time.sleep(.4)
        x.click(control(checkpoint,'저장하고 처음으로'));time.sleep(.5)
        after=json.loads(files[0].read_text())['payload']
        proof['before']=first['character'];proof['after']=after['character']
        proof['checks'].append({'id':'ordinary_OS_key_movement_saved','pass':after['character']['x']>first['character']['x'] and after['request_watermarks'].get('ui',0)>0})
        proof['checks'].append({'id':'ordinary_commoner_no_attack_skill','pass':after['character']['level']==1 and after['character']['job']=='commoner' and not after['skills']})
        proof['save_file']=str(files[0]);proof['request_watermark']=after['request_watermarks'].get('ui',0)
    except Exception as exc:proof['error']=str(exc)
    finally:x.close()
    proof['status']='PASS' if len(proof['checks'])==4 and all(c['pass'] for c in proof['checks']) and not proof.get('error') else 'FAIL'
    return proof

def resume_probe(env,out,prior):
    checkpoint=out/'isolated-data/baram_rebuild_gameplay_001/gameplay-checkpoints.jsonl'
    path=out/'isolated-data/baram_rebuild_gameplay_001/gameplay-p3/characters'/os.path.basename(prior['save_file'])
    before=json.loads(path.read_text())['payload'];proof={'checks':[],'method':'new ordinary process, synthetic X11 Continue and movement'}
    x=X11(env)
    try:
        x.click(control(checkpoint,'이어 하기'));time.sleep(.7)
        loaded=[r for r in checkpoints(checkpoint) if r.get('stage')=='loaded'][-1]['details']['character']
        proof['checks'].append({'id':'ordinary_new_process_same_progress','pass':loaded==before['character']})
        x.key('Down',.5);time.sleep(.3)
        x.click(control(checkpoint,'저장하고 처음으로'));time.sleep(.4)
        after=json.loads(path.read_text())['payload']
        proof['checks'].append({'id':'ordinary_next_persisted_UI_nonce_moves_and_saves','pass':after['character']['y']>before['character']['y'] and after['request_watermarks'].get('ui',0)>before['request_watermarks'].get('ui',0)})
        proof['before']=before['character'];proof['after']=after['character'];proof['watermarks']=[before['request_watermarks'],after['request_watermarks']]
    except Exception as exc:proof['error']=str(exc)
    finally:x.close()
    proof['status']='PASS' if len(proof['checks'])==2 and all(c['pass'] for c in proof['checks']) and not proof.get('error') else 'FAIL'
    return proof
