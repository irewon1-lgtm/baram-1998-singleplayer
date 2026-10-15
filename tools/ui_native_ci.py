"""Native artifact verification; original files and output stay in a private vault."""
import argparse,base64,hashlib,json,os,re,shutil,subprocess,time,urllib.request,zipfile
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def api(repo,path,data=None):
 token=os.environ['GH_TOKEN'];body=json.dumps(data).encode() if data is not None else None
 request=urllib.request.Request('https://api.github.com/repos/'+repo+'/'+path,data=body,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 with urllib.request.urlopen(request,timeout=120) as response:return json.load(response)
def prepare(a):
 runtime=Path(a.runtime).resolve();patch=Path(a.patch).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
 if sha(patch)!=a.patch_sha:raise ValueError('Input patch hash mismatch')
 with zipfile.ZipFile(patch) as z:
  for n in z.namelist():
   if '..' in Path(n).parts or n.startswith('/') or '\\' in n:raise ValueError('Unsafe patch path')
  z.extractall(out/'patch')
 patchdir=out/'patch';delta=json.loads((patchdir/'engine_delta.json').read_text())
 original=runtime/'template-win64.exe'
 if sha(original)!=delta['base_sha256']:raise ValueError('Pinned engine mismatch')
 data=bytearray(original.read_bytes());data.extend(b'\0'*max(0,delta['result_bytes']-len(data)))
 for edit in delta['edits']:
  value=base64.b64decode(edit['data']);data[edit['offset']:edit['offset']+len(value)]=value
 data=data[:delta['result_bytes']];exe=runtime/'바람의나라.exe';exe.write_bytes(data)
 if sha(exe)!=delta['result_sha256']:raise ValueError('Exact EXE reconstruction failed')
 for n in ['private_content/ACTIVE.json','PACKAGE_MANIFEST.json']:
  shutil.copy2(patchdir/n,runtime/n)
 active=json.loads((runtime/'private_content/ACTIVE.json').read_text());new=runtime/'private_content/releases'/active['release_id']
 new.mkdir(parents=True,exist_ok=True)
 shutil.copytree(runtime/'private_content/releases/9e30ec651489a4f5bdbf5c4e727a41a3c7a2b2825a373262056c1e896a82fb7c/files',new/'files',dirs_exist_ok=True)
 shutil.copy2(patchdir/'private_content/releases'/active['release_id']/'release.json',new/'release.json')
 cache=runtime/'runtime_cache';shutil.rmtree(cache,ignore_errors=True);cache.mkdir()
 script=out/'unpack_cache.gd';script.write_text('extends SceneTree\nfunc _initialize():\n    var a=OS.get_cmdline_user_args()\n    var f=FileAccess.open_compressed(a[0],FileAccess.READ)\n    var target=FileAccess.open(a[1],FileAccess.WRITE)\n    target.store_buffer(f.get_buffer(f.get_length()));target.close();quit()\n',encoding='utf-8')
 engine=str(Path(a.godot).resolve()) if a.godot else str(exe)
 result=subprocess.run([engine,'--headless','--script',str(script),'--',str(patchdir/'compressed-world.bin'),str(cache/'world.bin')],capture_output=True,text=True,timeout=90)
 (out/'cache-unpack.log').write_text(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError('Cache decode failed')
 shutil.copy2(patchdir/'world-manifest.json',cache/'manifest.json')
 cm=json.loads((cache/'manifest.json').read_text())
 if sha(cache/'world.bin')!=cm['sha256']:raise ValueError('Exact cached world reconstruction failed')
 import sys
 sys.path.insert(0,str(Path(a.source).resolve()/'tools'))
 from windows_ci import validate_runtime
 _,rows=validate_runtime(runtime)
 shutil.copy2(patchdir/'repair-verification.pck',out/'repair-verification.pck')
 dump(out/'prepared.json',{'exe_sha256':sha(exe),'cache_sha256':sha(cache/'world.bin'),'content':active['release_id'],'checked_files':len(rows),'source':delta['source']})
 print('PRIVATE_RUNTIME_AND_EXACT_EXE_RESTORED')
def windows(a):
 out=Path(a.out).resolve();runtime=Path(a.runtime).resolve();out.mkdir(parents=True,exist_ok=True)
 info=json.loads((Path(a.prepare)/'prepared.json').read_text());exe=runtime/'바람의나라.exe';rows=[]
 def execute(mode,save,touch=True):
  folder=out/mode;folder.mkdir(parents=True,exist_ok=True)
  command=[str(exe),'--audio-driver','Dummy','--','--save='+str(save),'--verification-pack='+str(Path(a.prepare).resolve()/'repair-verification.pck'),'--exercise='+mode,'--evidence='+str(folder)]
  if touch:command.append('--touch-test=true')
  log=folder/'engine.log';start=time.monotonic();hung=False
  import sys
  sys.path.insert(0,str(Path(a.source).resolve()/'tools'))
  from windows_ci import windows_window_state
  with log.open('w',encoding='utf-8') as stream:
   process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
   visible=0
   while process.poll() is None:
    state=windows_window_state(process.pid);visible+=state['visible_windows']>0
    if state['hung']:hung=True
    if time.monotonic()-start>380:process.kill();raise RuntimeError('Native Windows story timeout')
    time.sleep(.15)
  raw=log.read_text(encoding='utf-8',errors='replace')
  report=json.loads((folder/'story.json').read_text(encoding='utf-8'))
  ok=process.returncode==0 and not hung and visible>0 and all(row['status']=='PASS' for row in report['checks']) and report['source_build']==info['source'] and 'SCRIPT ERROR:' not in raw and not re.search(r'(?m)^ERROR:',raw)
  rows.append({'mode':mode,'status':'PASS' if ok else 'FAIL','native_windows':True,'visible_samples':visible,'hung':hung,'checks':len(report['checks']),'seconds':round(time.monotonic()-start,2)})
  dump(out/'results.json',{'status':'PASS' if all(row['status']=='PASS' for row in rows) else 'FAIL','environment':'Windows GitHub standard hosted runner, actual EXE and visible native window','source':info['source'],'exe_sha256':sha(exe),'cache_sha256':info['cache_sha256'],'content':info['content'],'runs':rows})
  if not ok:raise RuntimeError('Native Windows '+mode+' failed')
 save=out/'한글_저장_시험/saves/v2/character.json';save.parent.mkdir(parents=True,exist_ok=True)
 execute('repair-normal',save)
 execute('repair-equipment',save)
 execute('repair-restore',save)
 execute('repair-layout-desktop',save,False)
 # Native keyboard input against the default desktop mode.
 import ctypes
 user32=ctypes.windll.user32;process_log=out/'keyboard.log'
 with process_log.open('w',encoding='utf-8') as stream:
  process=subprocess.Popen([str(exe),'--audio-driver','Dummy','--','--save='+str(save)],stdout=stream,stderr=subprocess.STDOUT)
  started=time.monotonic();handle=0
  while time.monotonic()-started<55:
   found=[]
   def visit(hwnd,_):
    pid=ctypes.c_ulong();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if pid.value==process.pid and user32.IsWindowVisible(hwnd):found.append(hwnd)
    return True
   callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)(visit);user32.EnumWindows(callback,0)
   if found and 'BARAM_READY ' in process_log.read_text(encoding='utf-8',errors='replace'):handle=found[0];break
   time.sleep(.15)
  if not handle:process.kill();raise RuntimeError('Default desktop window not observed')
  user32.ShowWindow(handle,9);user32.SetForegroundWindow(handle);time.sleep(.2)
  def key(vk,seconds=.25):
   user32.keybd_event(vk,0,0,0);time.sleep(seconds);user32.keybd_event(vk,0,2,0);time.sleep(.2)
  key(0x26);key(0x20,.5);key(0x4f);key(0x49);key(0x77,.05)
  diagnostic=save.parent/'diagnostics/latest.json';until=time.monotonic()+10
  while not diagnostic.exists() and time.monotonic()<until:time.sleep(.1)
  observed=json.loads(diagnostic.read_text(encoding='utf-8'))
  events=observed['recent_events'];movement=any(e['event']=='moved' for e in events);attack=any(e['event']=='attack_started' for e in events);tabs=sum(e['event']=='sidebar_tab' for e in events)>=2
  ok=movement and attack and tabs
  rows.append({'mode':'default_desktop_OS_keyboard','status':'PASS' if ok else 'FAIL','native_windows':True,'movement':movement,'space_attack':attack,'equipment_and_inventory_shortcuts':tabs})
  user32.PostMessageW(handle,0x0010,0,0)
  try:process.wait(timeout=15)
  except subprocess.TimeoutExpired:process.kill()
  dump(out/'results.json',{'status':'PASS' if all(row['status']=='PASS' for row in rows) else 'FAIL','environment':'Windows GitHub standard hosted runner, actual EXE and visible native window','source':info['source'],'exe_sha256':sha(exe),'cache_sha256':info['cache_sha256'],'content':info['content'],'runs':rows})
  if not ok:raise RuntimeError('Native default desktop keyboard regression')
 print('NATIVE_WINDOWS_STORY_PASS')
def publish(a):
 out=Path(a.out).resolve();archive=out/'native-evidence.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in out.rglob('*'):
   if p.is_file() and p!=archive and p.suffix not in ['.apk','.exe'] and 'save' not in p.relative_to(out).as_posix():z.write(p,p.relative_to(out))
 files=[archive]
 if a.apk:files.append(Path(a.apk).resolve())
 rows=[];elements=[]
 for source in files:
  with source.open('rb') as f:
   index=0
   while block:=f.read(16*1024*1024):
    name=source.name+f'.part{index:03d}';blob=api(a.repo,'git/blobs',{'content':base64.b64encode(block).decode(),'encoding':'base64'})
    elements.append({'path':'native-delivery/'+name,'mode':'100644','type':'blob','sha':blob['sha']});rows.append({'file':source.name,'part':name,'bytes':len(block),'sha256':hashlib.sha256(block).hexdigest()});index+=1
 manifest={'source':a.commit,'platform':a.platform,'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in files],'parts':rows}
 blob=api(a.repo,'git/blobs',{'content':json.dumps(manifest,indent=2),'encoding':'utf-8'});elements.append({'path':'native-delivery/manifest.json','mode':'100644','type':'blob','sha':blob['sha']})
 ref=api(a.repo,'git/ref/heads/'+a.base_branch);parent=ref['object']['sha'];tree_base=api(a.repo,'git/commits/'+parent)['tree']['sha']
 tree=api(a.repo,'git/trees',{'base_tree':tree_base,'tree':elements});commit=api(a.repo,'git/commits',{'message':'Private native '+a.platform+' evidence and requested player artifact','tree':tree['sha'],'parents':[parent]})
 api(a.repo,'git/refs',{'ref':'refs/heads/delivery/ui-'+a.platform+'-'+a.commit[:8],'sha':commit['sha']})
 print('PRIVATE_NATIVE_DELIVERY_STORED '+a.platform+' '+commit['sha'])
if __name__=='__main__':
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
 p=sub.add_parser('prepare')
 for key in ['runtime','patch','patch-sha','out','source']:p.add_argument('--'+key,required=True)
 p.add_argument('--godot')
 p=sub.add_parser('windows')
 for key in ['runtime','out','prepare','source']:p.add_argument('--'+key,required=True)
 p=sub.add_parser('publish')
 for key in ['out','repo','commit','platform','base-branch']:p.add_argument('--'+key,required=True)
 p.add_argument('--apk')
 args=parser.parse_args();globals()[args.command](args)
