#!/usr/bin/env python3
"""Read private source containers statically; emit identities, not asset bytes.

Never launches source executables or imported helpers. ZIP uses Python's CRC
checks; 7z uses host libarchive via ctypes. InstallShield/NSIS are deliberately
reported as unsupported rather than passed to an installer. Temporary download
fragments are ignored. Outputs are deterministic for identical input bytes.
"""
from __future__ import annotations
import argparse, collections, ctypes, hashlib, io, json, os, re, struct, wave, zipfile
from pathlib import Path

VERSION = "baram-static-inventory/1.0"
MAX_ENTRY = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024

def sha(data): return hashlib.sha256(data).hexdigest()
def jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in rows))
def kind(name):
    s = Path(name).suffix.lower()
    return {'.map':'map', '.epf':'sprite', '.spr':'sprite', '.png':'image', '.bmp':'image', '.pcx':'image', '.jpg':'image', '.pal':'palette', '.tbl':'table', '.tab':'table', '.frm':'animation', '.elt':'effect_layer', '.wav':'audio', '.mp3':'audio', '.mid':'audio', '.snd':'audio', '.dat':'data_container', '.dna':'graphics_metadata', '.dsc':'graphics_metadata', '.chm':'help', '.hlp':'help', '.txt':'document', '.md':'document', '.html':'document', '.htm':'document', '.rtf':'document', '.json':'metadata', '.csv':'metadata', '.zip':'archive', '.7z':'archive', '.cab':'archive', '.exe':'executable', '.py':'source', '.gd':'source', '.c':'source', '.cpp':'source', '.h':'source', '.cs':'source', '.lua':'source'}.get(s,'other')
def fix_zip_name(info):
    if not info.flag_bits & 0x800:
        try: return info.filename.encode('cp437').decode('cp949'), 'cp949_from_zip_legacy_bytes'
        except (UnicodeError, LookupError): pass
    return info.filename, 'zip_utf8_or_original'
def decode_text(data):
    for enc in ('utf-8-sig','cp949','euc-kr','utf-16'):
        try: return data.decode(enc),enc
        except UnicodeError: pass
    return data.decode('cp949',errors='replace'),'cp949_replacement'

class LibArchive:
    def __init__(self):
        self.l=ctypes.CDLL('libarchive.so.13')
        for fn,rest,args in [
            ('archive_read_new',ctypes.c_void_p,[]),
            ('archive_read_support_filter_all',ctypes.c_int,[ctypes.c_void_p]),
            ('archive_read_support_format_all',ctypes.c_int,[ctypes.c_void_p]),
            ('archive_read_open_memory',ctypes.c_int,[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t]),
            ('archive_read_next_header',ctypes.c_int,[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]),
            ('archive_entry_pathname',ctypes.c_char_p,[ctypes.c_void_p]),
            ('archive_entry_size',ctypes.c_longlong,[ctypes.c_void_p]),
            ('archive_entry_filetype',ctypes.c_int,[ctypes.c_void_p]),
            ('archive_read_data',ctypes.c_ssize_t,[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t]),
            ('archive_error_string',ctypes.c_char_p,[ctypes.c_void_p]),
            ('archive_read_free',ctypes.c_int,[ctypes.c_void_p]),
        ]:
            f=getattr(self.l,fn);f.restype=rest;f.argtypes=args
    def entries(self,data):
        l=self.l;a=l.archive_read_new();buf=ctypes.create_string_buffer(data)
        try:
            l.archive_read_support_filter_all(a);l.archive_read_support_format_all(a)
            def error():
                s=l.archive_error_string(a);return s.decode(errors='replace') if s else 'unknown libarchive error'
            if l.archive_read_open_memory(a,buf,len(data))<0:raise ValueError(error())
            total=0;out=[];e=ctypes.c_void_p();block=ctypes.create_string_buffer(1024*1024)
            while True:
                code=l.archive_read_next_header(a,ctypes.byref(e))
                if code==1:break
                if code<0:raise ValueError(error())
                name=l.archive_entry_pathname(e).decode('utf-8',errors='replace')
                size=l.archive_entry_size(e)
                if size<0 or size>MAX_ENTRY:raise ValueError('entry size safety limit: '+name)
                chunks=[]
                while True:
                    n=l.archive_read_data(a,block,len(block))
                    if n<0:raise ValueError(error())
                    if n==0:break
                    chunks.append(block.raw[:n]);total+=n
                    if total>MAX_TOTAL:raise ValueError('archive total safety limit')
                b=b''.join(chunks)
                if l.archive_entry_filetype(e)==0o040000:continue
                out.append((name,b,'libarchive_path'))
            return out
        finally:l.archive_read_free(a)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--private-work',type=Path,required=True);ap.add_argument('--replacement-root',type=Path);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);args.private_work.mkdir(parents=True,exist_ok=True)
    previous=json.loads((args.inputs/'Baram1998Assets/PRIVATE_ASSET_INVENTORY_20261014.json').read_text())
    expected={x['library_name']:x for x in previous['files']}
    files=sorted(f for f in args.inputs.rglob('*') if f.is_file() and '.openai-download-' not in f.name and f.name!='CSO_ONE_통합.html')
    prior_path=args.output/'archive_sources.jsonl'
    prior_ids={r['library_path']:r['source_id'] for r in (json.loads(l) for l in prior_path.read_text().splitlines())} if prior_path.exists() else {}
    next_id=max((int(x.split('-')[1]) for x in prior_ids.values()),default=0)+1
    for f in files:
        lp='/'+f.relative_to(args.inputs).as_posix()
        if lp not in prior_ids:prior_ids[lp]=f'LIB-{next_id:03d}';next_id+=1
    files.sort(key=lambda f:prior_ids['/'+f.relative_to(args.inputs).as_posix()])
    la=LibArchive();sources=[];members=[];cache={};metadata={};containers=[];seen={}

    def inspect(data,name,source_id,parent='',depth=0):
        path=parent+'!'+name if parent else name
        digest=sha(data);k=kind(name)
        rec={'source_id':source_id,'archive_member':path,'size_bytes':len(data),'sha256':digest,'kind':k,'depth':depth,'inspection':'BYTES_READ_HASHED','parser_version':VERSION}
        rid=source_id+'-M-'+sha(path.encode())[:12];rec['member_id']=rid
        rec['original_id_candidate']=Path(name).stem if Path(name).stem.isdigit() else None
        hints=[]
        for term,target in [('effect','effect_frames'),('sound','sound_ids'),('snd','sound_ids'),('frame','animation_frames'),('body','character_body'),('head','character_head'),('weapon','weapon_layers'),('tile','map_tiles'),('map','geography'),('tbl','mapping_tables'),('pal','palette')]:
            if term in name.lower():hints.append(target)
        rec['mapping_candidates']=sorted(set(hints))
        if digest in seen:rec['same_bytes_as_member_id']=seen[digest]
        else:seen[digest]=rid
        members.append(rec)
        if k=='audio' and data[:4]==b'RIFF':
            try:
                with wave.open(io.BytesIO(data),'rb') as w:rec['wave']={'channels':w.getnchannels(),'rate_hz':w.getframerate(),'sample_width':w.getsampwidth(),'frames':w.getnframes(),'duration_seconds':round(w.getnframes()/w.getframerate(),6)}
            except Exception as exc:rec['wave_error']=str(exc)
        if k in ('metadata','document') and len(data)<16*1024*1024:
            metadata[(source_id,path)]=data
        iscontainer=data.startswith(b'PK\x03\x04') or data.startswith(b"7z\xbc\xaf\x27\x1c") or data.startswith(b'MSCF') or data.startswith(b'ISc(')
        if k=='archive' or iscontainer:
            if depth>=4:rec['container_status']='DEPTH_LIMIT_NOT_INSPECTED';return
            c={'source_id':source_id,'archive_member':path,'sha256':digest,'format_magic':data[:8].hex()}
            containers.append(c)
            try:
                if digest in cache:entries=cache[digest];c['reuse']='SAME_BYTES_ARCHIVE_LIST_REUSED'
                elif data.startswith(b'PK'):
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        if sum(i.file_size for i in z.infolist())>MAX_TOTAL:raise ValueError('archive total safety limit')
                        entries=[]
                        for i in z.infolist():
                            if i.is_dir():continue
                            if i.file_size>MAX_ENTRY:raise ValueError('entry size safety limit')
                            nm,enc=fix_zip_name(i);entries.append((nm,z.read(i),enc))
                    cache[digest]=entries
                elif data.startswith(b'ISc('):raise ValueError('InstallShield CAB unsupported by installed static readers; not executed')
                else:
                    entries=la.entries(data);cache[digest]=entries
                c['status']='LISTED_HASHED';c['members']=len(entries);rec['container_status']='LISTED_HASHED'
                for nm,b,enc in entries:
                    child_idx=len(members)
                    inspect(b,nm,source_id,path,depth+1)
                    members[child_idx].setdefault('name_encoding',enc)
            except Exception as exc:c['status']='DECODE_FAILED';c['error']=str(exc);rec['container_status']='DECODE_FAILED';rec['container_error']=str(exc)
        elif k=='executable':
            rec['execution']='NOT_RUN_STATIC_ONLY'
            rec['installer_markers']={sig.decode(errors='replace'):data.find(sig) for sig in (b'MSCF',b'ISc(',b'Nullsoft',b'Inno Setup',b'InstallShield') if data.find(sig)>=0}

    for idx,f in enumerate(files,1):
        rel=f.relative_to(args.inputs).as_posix();sid=prior_ids['/'+rel];v=expected.get(f.name)
        replacement=args.replacement_root/rel if args.replacement_root else None
        actual=replacement if replacement and replacement.is_file() else f
        data=actual.read_bytes();digest=sha(data)
        reg='KR' if f.name.startswith('KR_') else 'NA' if f.name.startswith('NA_') else 'UNKNOWN_OR_MIXED'
        build=(re.search(r'^(?:KR|NA)_([0-9.]+)',f.name) or [None,'UNKNOWN'])[1]
        r={'source_id':sid,'source_type':'PRIVATE_LIBRARY_FILE','library_path':'/'+rel,'local_materialization_path':str(actual),'library_file_id':os.getxattr(f,'user.library-file-id').decode(),'library_file_version':os.getxattr(f,'user.library-file-version').decode(),'size_bytes':len(data),'sha256':digest,'game_region':reg,'client_build':build,'version_basis':'FILENAME_CLAIM_NOT_EXECUTABLE_VERSION_CHECK' if build!='UNKNOWN' else 'UNKNOWN','content_era':'UNKNOWN','captured_at':'2026-10-15','parser_version':VERSION,'fact_status':'UNKNOWN','byte_identity_status':'SHA256_COMPUTED','use_status':'ACQUIRED','runtime_test':'NOT_RUN','notes':[]}
        if actual!=f:
            bad=f.read_bytes();r['initial_materialization']={'path':str(f),'size_bytes':len(bad),'sha256':sha(bad),'status':'INCOMPLETE_RETAINED_REPLACEMENT_VERIFIED'}
        if v:
            r['previous_inventory']={'expected_sha256':v['sha256'],'expected_size_bytes':v['bytes'],'hash_match':digest==v['sha256'],'size_match':len(data)==v['bytes']}
            if digest!=v['sha256']:r['notes'].append('SOURCE_IDENTITY_MISMATCH_WITH_20261014_INVENTORY')
        before=len(members);inspect(data,f.name,sid);r['inventory_member_count']=len(members)-before-1
        r['container_status']=members[before].get('container_status','NOT_A_SUPPORTED_CONTAINER')
        if r['container_status']=='LISTED_HASHED':r['use_status']='DECODED'
        sources.append(r)
        print(sid,rel,len(data),r['inventory_member_count'],r['container_status'],flush=True)
    jsonl(args.output/'archive_sources.jsonl',sources);jsonl(args.output/'archive_members.jsonl',members)
    jsonl(args.private_work/'container_results.jsonl',containers)
    for (sid,path),data in metadata.items():
        dest=args.private_work/(sid+'-'+sha(path.encode())[:16]+Path(path).suffix)
        dest.write_bytes(data)
    index=[{'source_id':sid,'archive_member':p,'private_metadata_path':str(args.private_work/(sid+'-'+sha(p.encode())[:16]+Path(p).suffix)),'sha256':sha(b)} for (sid,p),b in metadata.items()]
    jsonl(args.private_work/'metadata_index.jsonl',index)
    summary={'sources':len(sources),'members_including_top_level':len(members),'unique_byte_hashes':len({r['sha256'] for r in members}),'containers':containers,'kind_counts':dict(collections.Counter(r['kind'] for r in members)),'source_identity_mismatches':[r['source_id'] for r in sources if r.get('previous_inventory',{}).get('hash_match') is False]}
    (args.private_work/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
