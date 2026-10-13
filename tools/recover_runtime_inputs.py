#!/usr/bin/env python3
"""Resume only the pinned stage-4 inputs; never rewrite the Work research ledgers."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
from legacy_assets import private_path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'research/restoration-integrated-20261013/INPUT_RECOVERY.json'
ARCHIVES = {'491v.zip', 'NexusTK_v4.0.3.7z', 'NexusTK_V_4.66.7z', 'nexus495.exe', 'BARAM.PAL'}
REFERENCES = {'DizzyThermal/EPFViewer', 'DizzyThermal/TKMapper', 'project1998/Project1998'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def file_sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def archive(task, directory):
    record = {key: task[key] for key in ('id', 'url', 'expected_sha256', 'relative_path')}
    record.update(kind='ORIGINAL_ARCHIVE', started_at=now(), status='BLOCKED')
    destination = directory / task['relative_path']
    record['local_path'] = str(destination)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        private_path(destination)
        if destination.exists():
            actual = file_sha(destination)
            if actual != task['expected_sha256']:
                record.update(status='FAIL', actual_sha256=actual,
                              error='Existing file hash differs; preserved, not overwritten')
                return record
            record.update(status='PASS_REUSED_LOCAL_BYTES', actual_sha256=actual, bytes=destination.stat().st_size)
            return record
        temporary = destination.with_name(destination.name + '.partial')
        if temporary.exists():
            record['error'] = 'Existing partial download preserved; inspect/move it before resuming'
            return record
        request = urllib.request.Request(task['url'], headers={'User-Agent': 'Baram-private-restoration/1.0'})
        with urllib.request.urlopen(request, timeout=45) as response:
            record.update(http_status=response.status, final_url=response.url)
            with temporary.open('xb') as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
        actual = file_sha(temporary)
        record.update(actual_sha256=actual, bytes=temporary.stat().st_size)
        if actual != task['expected_sha256']:
            record.update(status='FAIL', error='Downloaded SHA256 mismatch; partial quarantined, never activated')
        else:
            temporary.rename(destination)
            record['status'] = 'PASS_BYTES_HASH_MATCH'
    except (OSError, ValueError) as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        record['finished_at'] = now()
    return record


def reference(task, directory):
    record = {key: task[key] for key in ('name', 'url', 'commit')}
    record.update(kind='EXTERNAL_REFERENCE', started_at=now(), status='BLOCKED')
    destination = directory / 'repos' / task['name']
    record['local_path'] = str(destination)
    try:
        private_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            subprocess.run(['git', 'clone', '--no-checkout', task['url'], str(destination)],
                           check=True, capture_output=True, text=True, timeout=180)
            subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', task['commit']],
                           check=True, capture_output=True, text=True, timeout=180)
        head = subprocess.check_output(['git', '-C', str(destination), 'rev-parse', 'HEAD'], text=True).strip()
        if head != task['commit']:
            record.update(status='FAIL', actual_commit=head, error='Existing different checkout preserved; use a fresh private directory')
            return record
        fsck = subprocess.run(['git', '-C', str(destination), 'fsck', '--no-reflogs'], capture_output=True, text=True, timeout=90)
        record.update(actual_commit=head, fsck_exit=fsck.returncode,
                      status='PASS_PINNED_CHECKOUT' if fsck.returncode == 0 else 'FAIL')
        if fsck.returncode:
            record['error'] = fsck.stderr[-1000:]
    except (OSError, subprocess.SubprocessError) as exc:
        # Do not serialize command environments or remote credential configuration.
        record['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        record['finished_at'] = now()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--only', choices=['archives', 'references', 'all'], default='all')
    args = parser.parse_args()
    destination = private_path(args.private_dir)
    records = json.loads(LEDGER.read_text())['records']
    tasks = []
    if args.only in ('archives', 'all'):
        tasks.extend((archive, row) for row in records if row.get('kind') == 'ORIGINAL_ARCHIVE' and row['id'] in ARCHIVES)
    if args.only in ('references', 'all'):
        tasks.extend((reference, row) for row in records if row.get('name') in REFERENCES)
    report = dict(executed_at=now(), source_ledger=str(LEDGER.relative_to(ROOT)),
                  source_ledger_sha256=file_sha(LEDGER), research_base='2775b1166a760b6a1757f09f2faf1e799d3fd59e',
                  scope='PINNED_INPUT_RECOVERY_ONLY_NO_EXTRACTION_RENDER_OR_PLAY', records=[])
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(function, task, destination) for function, task in tasks]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            report['records'].append(record)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(record.get('id', record.get('name')), record['status'], flush=True)
    return int(any(not row['status'].startswith('PASS_') for row in report['records']))


if __name__ == '__main__':
    raise SystemExit(main())
