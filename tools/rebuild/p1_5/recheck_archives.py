"""Read-only source/member reconciliation; never runs installers or writes named payload paths."""
import argparse, collections, hashlib, importlib.util, io, json, sys, zipfile
from pathlib import Path, PurePosixPath

VERSION = 'p1.5-source-recheck/1.0'
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024

def digest(b): return hashlib.sha256(b).hexdigest()
def lines(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def module(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    sys.modules[name] = m; s.loader.exec_module(m); return m

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--private-work',type=Path,required=True)
    ap.add_argument('--legacy-parser-dir',type=Path,required=True); a=ap.parse_args()
    work=a.private_work;work.mkdir(parents=True,exist_ok=True);pool=work/'objects';pool.mkdir(exist_ok=True)
    old=a.repo/'docs/rebuild/step01';out=a.repo/'docs/rebuild/p1_5'
    sources=lines(old/'archive_sources.jsonl'); members=lines(old/'archive_members.jsonl')
    expected={(r['source_id'],r['archive_member']):r for r in members}; found={};errors=[]; containers=[]
    mapping={}; source_results=[]; total=0; processed=0; new=[]
    pins={a.repo/'tools/rebuild/step01/inventory_archives.py':'d50c9e9393868d9bfa6fe991df7e6c829bcadd279a6baaca93f06625c9e79607',
          a.legacy_parser_dir/'legacy_assets.py':'f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2',
          a.legacy_parser_dir/'legacy_installers.py':'5dd1d31cd287a01a8da494c315df5479a032a0a18979a30901bee49b558fd382'}
    for path,pin in pins.items():
        if digest(path.read_bytes())!=pin:raise ValueError('Parser code fingerprint mismatch before import: '+path.name)
    inv=module('inventory_recheck',a.repo/'tools/rebuild/step01/inventory_archives.py')
    sys.path.insert(0,str(a.legacy_parser_dir)); import legacy_assets,legacy_installers
    la=inv.LibArchive()

    def inspect(sid,name,data,depth=0):
        nonlocal total,processed
        processed+=len(data)
        if len(data)>MAX_FILE or processed>MAX_TOTAL:raise ValueError('Processing byte budget exceeded')
        h=digest(data);r=expected.get((sid,name)); obj=pool/h
        if obj.exists() and (obj.stat().st_size!=len(data) or digest(obj.read_bytes())!=h):
            raise ValueError('Cached object byte identity mismatch: '+h)
        if not obj.exists():
            total+=len(data)
            if total>MAX_TOTAL:raise ValueError('Total object byte budget exceeded')
            obj.write_bytes(data)
        if r:
            status='MATCH' if h==r['sha256'] and len(data)==r['size_bytes'] else 'MISMATCH'
            found[r['member_id']]={'member_id':r['member_id'],'source_id':sid,'archive_member':name,'status':status,'sha256':h,'size_bytes':len(data)}
            mapping[r['member_id']]=str(obj)
        else:new.append({'source_id':sid,'archive_member':name,'sha256':h,'size_bytes':len(data)})
        if depth>=6:return
        entries=None; kind=None
        try:
            if data.startswith(b'PK\x03\x04'):
                kind='ZIP'; entries=[]
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    subtotal=0
                    for info in z.infolist():
                        if info.is_dir():continue
                        if info.file_size>MAX_FILE:raise ValueError('ZIP entry byte limit')
                        subtotal+=info.file_size
                        if subtotal>MAX_TOTAL:raise ValueError('ZIP declared total limit')
                        n,_=inv.fix_zip_name(info)
                        if PurePosixPath(n.replace('\\','/')).is_absolute() or '..' in PurePosixPath(n.replace('\\','/')).parts:raise ValueError('Unsafe archive path')
                        mode=info.external_attr>>16
                        if mode&0o170000==0o120000:raise ValueError('Symlink rejected')
                        entries.append((n,z.read(info)))
            elif data.startswith(b"7z\xbc\xaf\x27\x1c") or data.startswith(b'MSCF'):
                kind='LIBARCHIVE';entries=[(n,b) for n,b,_ in la.entries(data)]
            elif data.startswith(b'ISc('):
                kind='INSTALLSHIELD4';entries=[(meta['path'],b) for meta,b in legacy_installers.installshield4(data) if b is not None]
            elif name.lower().endswith(('!nwind.dat','!nwind.snd','!winbaram.dat')):
                kind='DAT_DIRECTORY';entries=[(n,b) for n,_,b in legacy_assets.dat_entries(data).values()]
            if entries is not None:
                containers.append({'source_id':sid,'archive_member':name,'sha256':h,'reader':kind,'status':'DECODED','entries':len(entries)})
                for n,b in entries:
                    if len(b)>MAX_FILE:raise ValueError('Decoded entry byte limit')
                    pp=PurePosixPath(n.replace('\\','/'))
                    if pp.is_absolute() or '..' in pp.parts or (pp.parts and ':' in pp.parts[0]):raise ValueError('Unsafe archive entry name')
                    inspect(sid,name+'!'+n,b,depth+1)
        except Exception as e:
            errors.append({'source_id':sid,'archive_member':name,'sha256':h,'reader':kind,'status':'UNDECODED','error':str(e)})

    for s in sources:
        p=a.input_root/Path(s['library_path']).name
        if not p.is_file(): p=Path(s['local_materialization_path'])
        rr={k:s[k] for k in ['source_id','library_file_id','library_path','sha256','size_bytes']}
        rr['previous_audit_unavailable']=s['source_id'] in {f'LIB-{i:03}' for i in range(29,36)}
        if not p.is_file():rr.update(status='BLOCKED',reason='No current byte path')
        elif p.stat().st_size>MAX_FILE:rr.update(status='BLOCKED',reason='Source byte safety limit')
        else:
            b=p.read_bytes();h=digest(b)
            rr.update(status='MATCH' if h==s['sha256'] and len(b)==s['size_bytes'] else 'MISMATCH',actual_sha256=h,actual_size_bytes=len(b))
            mapping[s['source_id']]=str(p)
            if rr['status']=='MATCH':inspect(s['source_id'],Path(s['library_path']).name,b)
        source_results.append(rr)
        print(s['source_id'],rr['status'],flush=True)
    member_results=[found.get(r['member_id'],{'member_id':r['member_id'],'source_id':r['source_id'],'archive_member':r['archive_member'],'status':'BLOCKED','reason':'Exact bytes not reached by supported reader'}) for r in members]
    helpers=[a.repo/'tools/rebuild/step01/inventory_archives.py',a.legacy_parser_dir/'legacy_assets.py',a.legacy_parser_dir/'legacy_installers.py',Path(__file__)]
    report={'task_id':'BARAM_REBUILD_P1_5_001','parser_version':VERSION,'parser_fingerprints':{p.name:digest(p.read_bytes()) for p in helpers},'originals':source_results,'summary':{'original_expected':len(sources),'original_status':dict(collections.Counter(r['status'] for r in source_results)),'member_expected':len(members),'member_status':dict(collections.Counter(r['status'] for r in member_results)),'unique_expected_member_hashes':len({r['sha256'] for r in members}),'actual_unique_member_hashes':len({r['sha256'] for r in member_results if r['status']=='MATCH'}),'new_nested_records':len(new),'decode_result':'BLOCKED' if errors else 'PASS_FOR_SUPPORTED_CONTAINERS','processed_bytes':processed,'stored_new_bytes':total},'members':member_results,'containers':containers,'decode_errors':errors,'new_members':new,'scope':'BYTE/CONTAINER CHECK ONLY; NOT HISTORICAL FACT, MALWARE OR GAMEPLAY PASS','runtime_tests':'NOT_RUN'}
    (out/'source_access.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (work/'input_map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary']))
    return 1 if any(r['status']=='MISMATCH' for r in source_results+member_results) else 2 if errors or any(r['status']=='BLOCKED' for r in source_results+member_results) else 0

if __name__=='__main__':sys.exit(main())
