#!/usr/bin/env python3
"""Extract the verified legacy inputs statically, publishing metadata only."""
import argparse
import ctypes
import ctypes.util
import datetime
import hashlib
import json
from pathlib import Path
import zipfile
import zlib
from legacy_assets import AssetError, private_path
from legacy_installers import installshield4, wise_streams, wise_named_records

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sevenzip_files(path):
    library = ctypes.CDLL(ctypes.util.find_library('archive'))
    library.archive_read_new.restype = ctypes.c_void_p
    for name in ['archive_read_support_filter_all', 'archive_read_support_format_all', 'archive_read_free']:
        getattr(library, name).argtypes = [ctypes.c_void_p]
    library.archive_read_open_filename.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    library.archive_read_next_header.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    library.archive_entry_pathname.argtypes = [ctypes.c_void_p]
    library.archive_entry_pathname.restype = ctypes.c_char_p
    library.archive_read_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    library.archive_read_data.restype = ctypes.c_longlong
    library.archive_error_string.argtypes = [ctypes.c_void_p]
    library.archive_error_string.restype = ctypes.c_char_p
    reader = library.archive_read_new()
    library.archive_read_support_filter_all(reader); library.archive_read_support_format_all(reader)
    entry = ctypes.c_void_p(); buffer = ctypes.create_string_buffer(1024 * 1024)
    try:
        if library.archive_read_open_filename(reader, str(path).encode(), 10240) != 0:
            raise AssetError('7z open failed')
        while True:
            status = library.archive_read_next_header(reader, ctypes.byref(entry))
            if status == 1: break
            if status != 0: raise AssetError('7z header failed')
            name = library.archive_entry_pathname(entry).decode('utf-8')
            chunks = []
            while True:
                size = library.archive_read_data(reader, buffer, len(buffer))
                if size == 0: break
                if size < 0: raise AssetError('7z payload read failed')
                chunks.append(buffer.raw[:size])
                if sum(map(len, chunks)) > 128 * 1024 * 1024: raise AssetError('7z member output bound exceeded')
            yield name, b''.join(chunks)
    finally:
        library.archive_read_free(reader)


def write_private(path, payload):
    private_path(path)
    if path.is_symlink(): raise AssetError('Symlink output refused')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != payload:
        raise AssetError('Different existing output preserved: ' + str(path))
    path.write_bytes(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args(); private = private_path(args.private_dir)
    ledger = json.loads((ROOT / 'research/restoration-integrated-20261013/INPUT_RECOVERY.json').read_text())['records']
    pins = {r['id']: r for r in ledger if r.get('kind') == 'ORIGINAL_ARCHIVE'}
    golden = {Path(r['source']).name.lower(): r['source_sha256'] for r in json.loads((ROOT / 'research/world-audit/dat-directory-check.json').read_text())}
    reports = []
    for version, filename in [('KR-4.91','491v.zip'),('NA-4.03','NexusTK_v4.0.3.7z'),('NA-4.95','nexus495.exe'),('NA-4.66','NexusTK_V_4.66.7z')]:
        record = dict(version=version, archive=filename, started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      status='NOT_RUN', method='STATIC_ONLY_NO_INSTALLER_EXECUTION', files=[], streams=[], public_bytes_included=False)
        try:
            source = private / 'archives' / filename; data = source.read_bytes()
            record['archive_sha256'] = sha(data)
            if sha(data) != pins[filename]['expected_sha256']: raise AssetError('Original archive SHA256 mismatch')
            output = private / 'runtime-inputs' / version
            if version == 'KR-4.91':
                with zipfile.ZipFile(source) as archive: cab = archive.read('Install/DATA1.CAB')
            elif version == 'NA-4.03':
                cab = next(blob for name,blob in sevenzip_files(source) if name.lower().endswith('/data1.cab'))
            elif version == 'NA-4.66':
                name,blob = next(sevenzip_files(source)); record['outer_payload_sha256'] = sha(blob)
                write_private(output / 'nxuswind.exe', blob)
                record.update(status='BLOCKED', reason='Distinct InstallShield self-extractor: no CAB/ZIP signature or validated Wise DEFLATE/CRC chain; original EXE not executed')
                reports.append(record); continue
            if version in ('KR-4.91','NA-4.03'):
                record['cab_sha256'] = sha(cab)
                for row,blob in installshield4(cab):
                    if blob is not None:
                        row['sha256'] = sha(blob)
                        expected = golden.get(row['name'].lower())
                        if expected and expected != sha(blob): raise AssetError('Inherited DAT SHA256 mismatch')
                        if expected: row['inherited_hash_match'] = True
                        destination = output / row['path']; write_private(destination,blob); row['local_path'] = str(destination)
                    record['files'].append(row)
            else:
                # Proven by the pinned 4.95 PE: initial stream at 15041, all streams end at EOF.
                for row,blob in wise_streams(data,15041):
                    row['sha256'] = sha(blob); record['streams'].append(row)
                    write_private(output / 'streams' / f'{row["index"]:04d}.bin',blob)
                script = (output / 'streams/0001.bin').read_bytes()
                for name,row,position in wise_named_records(script,record['streams']):
                    blob = (output / 'streams' / f'{row["index"]:04d}.bin').read_bytes()
                    destination = output / name; write_private(destination,blob)
                    record['files'].append(dict(name=name,local_path=str(destination),sha256=sha(blob),bytes=len(blob),
                                                stream_index=row['index'],script_name_offset=position,
                                                binding='SCRIPT_PHYSICAL_STREAM_BOUNDS_CRC32_AND_DECLARED_SIZE',status='PASS_NAMED_FILE_EXTRACT'))
                required = {'Inter.dat','NexusTK.dat','NexusTK.exe','NexusTK.snd','Patcher.exe'}
                if not required.issubset({r['name'] for r in record['files']}): raise AssetError('Required 4.95 filenames not resolved')
                record['remaining_unnamed_streams'] = len(record['streams']) - len({r['stream_index'] for r in record['files']})
            record['status'] = 'PASS_RESOURCE_PAYLOAD_EXTRACTION_ONLY'
        except (OSError,ValueError,zlib.error,StopIteration) as exc:
            record.update(status='FAIL',error=type(exc).__name__+': '+str(exc))
        record['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); reports.append(record)
        print(version,record['status'],'files',len(record['files']),'streams',len(record['streams']),flush=True)
    target = Path(args.report); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({'executed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 'scope':'STATIC_RESOURCE_EXTRACTION_NOT_CLIENT_COMPATIBILITY_OR_PLAY','records':reports},ensure_ascii=False,indent=2)+'\n')
    return int(any(r['status']=='FAIL' for r in reports))


if __name__ == '__main__':
    raise SystemExit(main())
