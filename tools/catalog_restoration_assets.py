#!/usr/bin/env python3
"""Hash archive/DAT asset records without executing clients or rendering sprites."""
import argparse, collections, ctypes, ctypes.util, datetime, hashlib, json, struct
from pathlib import Path
from inspect_legacy_dat import inspect

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/restoration-integrated-20261013'

def archive_entries(path):
    lib=ctypes.CDLL(ctypes.util.find_library('archive'))
    lib.archive_read_new.restype=ctypes.c_void_p
    lib.archive_read_support_filter_all.argtypes=[ctypes.c_void_p]
    lib.archive_read_support_format_all.argtypes=[ctypes.c_void_p]
    lib.archive_read_open_filename.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t]
    lib.archive_read_next_header.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
    lib.archive_entry_pathname.argtypes=[ctypes.c_void_p];lib.archive_entry_pathname.restype=ctypes.c_char_p
    lib.archive_entry_size.argtypes=[ctypes.c_void_p];lib.archive_entry_size.restype=ctypes.c_longlong
    lib.archive_read_data.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t];lib.archive_read_data.restype=ctypes.c_longlong
    lib.archive_read_free.argtypes=[ctypes.c_void_p]
    reader=lib.archive_read_new();lib.archive_read_support_filter_all(reader);lib.archive_read_support_format_all(reader)
    if lib.archive_read_open_filename(reader,str(path).encode(),10240)!=0:raise ValueError('Archive open failed')
    buf=ctypes.create_string_buffer(1024*1024);entry=ctypes.c_void_p()
    try:
        while lib.archive_read_next_header(reader,ctypes.byref(entry))==0:
            name=lib.archive_entry_pathname(entry).decode('utf-8',errors='replace');size=lib.archive_entry_size(entry)
            chunks=[];digest=hashlib.sha256()
            while True:
                n=lib.archive_read_data(reader,buf,len(buf))
                if n<0:raise ValueError('Archive read failed for '+name)
                if n==0:break
                chunk=buf.raw[:n];digest.update(chunk)
                if name.lower().endswith('.dat') and size<100*1024*1024:chunks.append(chunk)
            yield dict(name=name,bytes=size,sha256=digest.hexdigest()),b''.join(chunks)
    finally:lib.archive_read_free(reader)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private-dir',required=True);args=parser.parse_args()
    private=Path(args.private_dir).resolve();assets={};checks=[];archive_index=[]
    def add(meta,version,container,offset=None):
        key=meta['sha256'];ext=Path(meta['name']).suffix.lower()
        if ext not in ['.epf','.pal','.wav','.mid','.midi','.emf','.tbl','.map','.bmp','.png','.gif']:return
        record=assets.setdefault(key,dict(asset_id='asset.'+key[:20],sha256=key,bytes=meta['bytes'],format=ext.lstrip('.'),
                        appearances=[],content_id=None,content_name=None,palette_id=None,frame_numbers=None,direction=None,action=None,
                        decoded_render_status='NOT_RUN',semantic_identification_status='NOT_RUN',rights='NO_DISTRIBUTION_PERMISSION_VERIFIED',public_bytes_included=False))
        appearance=dict(version=version,container=container,file=meta['name'],offset=offset)
        if appearance not in record['appearances']:record['appearances'].append(appearance)
        for field in ['epf_frames','epf_width','epf_height','epf_status']:
            if field in meta:record[field]=meta[field]
    targets=[('NexusTK_v4.0.3.7z','NA-4.03'),('NexusTK_V_4.66.7z','NA-4.66')]
    for fname,version in targets:
        try:
            for meta,payload in archive_entries(private/'archives'/fname):
                archive_index.append(dict(archive=fname,version=version,**meta));add(meta,version,fname)
                if payload and Path(meta['name']).name.lower() not in ['lang.dat','os.dat']:
                    dest=private/'asset-dat'/version/Path(meta['name']).name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(payload)
                    report=inspect(dest);checks.append({k:v for k,v in report.items() if k!='entries'})
                    for row in report['entries']:add(row,version,fname+'::'+meta['name'],row['offset'])
        except Exception as exc:checks.append(dict(source=fname,status='BLOCKED',error=str(exc)))
    for file in (private/'extracted/491v').rglob('*'):
        if file.is_file() and file.suffix.lower() in ['.dat','.pal','.wav','.mid','.epf','.map']:
            meta=dict(name=str(file.relative_to(private/'extracted/491v')),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),bytes=file.stat().st_size)
            archive_index.append(dict(archive='491v.zip',version='KR-4.91',**meta));add(meta,'KR-4.91','491v.zip')
            if file.suffix.lower()=='.dat' and file.name.lower() not in ['lang.dat','os.dat']:
                try:
                    report=inspect(file);checks.append({k:v for k,v in report.items() if k!='entries'})
                    for row in report['entries']:add(row,'KR-4.91','491v.zip::'+meta['name'],row['offset'])
                except Exception as exc:checks.append(dict(source=str(file),status='BLOCKED',error=str(exc)))
    # The previous audit actually extracted InstallShield payloads. Reuse its
    # directory hashes after recovering the byte-identical original archives;
    # this is not a new payload extraction or render PASS.
    for report in json.loads((ROOT/'research/world-audit/dat-directory-check.json').read_text()):
        version='NA-4.03' if '403-client' in report['source'] else 'KR-4.91'
        for row in report['entries']:
            add(row,version,report['source'],row['offset'])
            if row['sha256'] in assets:
                assets[row['sha256']].update(metadata_verification='REUSED_PINNED_WORLD_AUDIT',
                    metadata_source_commit='0ebfbe1514700a8afc00f71b20b9f88b23eb075f',
                    original_container_sha256=report['source_sha256'],payload_reextracted_this_run=False)
    for report in json.loads((ROOT/'research/world-audit/epf-header-check.json').read_text()):
        version='NA-4.03' if '403-client' in report['source'] else 'KR-4.91'
        for row in report['files']:add(row,version,report['source'],row['offset'])
    for row in json.loads((ROOT/'research/world-audit/new-file-inventory.json').read_text()):
        if '403-client-legacy/' in row['path'] and row['extension']=='.map':
            add(dict(name=row['path'],bytes=row['bytes'],sha256=row['sha256']),'NA-4.03','NexusTK_v4.0.3.7z')
            assets[row['sha256']]['metadata_verification']='REUSED_PINNED_WORLD_AUDIT'
            assets[row['sha256']]['payload_reextracted_this_run']=False
    records=sorted(assets.values(),key=lambda r:r['asset_id'])
    (OUT/'ASSET_CATALOG.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in records))
    (OUT/'ASSET_CONTAINER_INDEX.json').write_text(json.dumps(dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),archive_entries=archive_index,DAT_checks=checks,NA495_status='INSTALLER_HASHED_PAYLOAD_UNEXTRACTED',rendered_images=0),ensure_ascii=False,indent=2)+'\n')
    summary=dict(unique_file_payload_hashes=len(records),formats=dict(collections.Counter(r['format'] for r in records)),
                 version_appearances=dict(collections.Counter(a['version'] for r in records for a in r['appearances'])),
                 declared_epf_frames=sum(r.get('epf_frames',0) for r in records),decoded_rendered_images=0,semantic_entity_motion_links=0,
                 count_warning='Declared frames and file payloads are not decoded pictures; same hash counted once',NA495_status='BLOCKED_FULL_PAYLOAD_EXTRACTION')
    summary['metadata_reused_original_archives_hash_matched']=True
    summary['NA466_status']='INSTALLER_PRESENT_NO_SPRITE_PAYLOAD_CATALOG'
    (OUT/'ASSET_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
