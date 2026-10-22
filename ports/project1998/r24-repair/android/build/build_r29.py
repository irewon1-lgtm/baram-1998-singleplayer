#!/usr/bin/env python3
"""Build the V4 r29 seven-HUD and backed-up totogo position recovery update APK; strict frozen inputs and real package checks."""
import argparse
import hashlib
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
workspace = Path(os.environ.get('P1998_WORKSPACE', str(root.parents[2]))).resolve()
parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, default=workspace, help='Logical workspace containing latest r20 deliverables and private-r0; override for portable source copies.')
parser.add_argument('--tools', type=Path, default=workspace / 'toolchain-r27')
parser.add_argument('--packages', type=Path, default=workspace / 'toolchain-r27/nuget/packages')
parser.add_argument('--sqlite-android', type=Path, default=workspace / 'toolchain-r27/nuget/feed/sqlitepclraw.lib.e_sqlite3.android.2.1.6.nupkg')
parser.add_argument('--version-code',type=int,default=33)
parser.add_argument('--attempt', default='r29-001')
parser.add_argument('--staging', type=Path, default=workspace / 'p1998-r29-build')
parser.add_argument('--output', type=Path, help='New output APK path; an existing output is never overwritten.')
parser.add_argument('--private-signing', type=Path, default=workspace / 'private-r0', help='Existing private signing key directory; never embedded.')
parser.add_argument('--prepare-only', action='store_true')
parser.add_argument('--recovered-host', action='store_true', help='Record unavailable historical SDK cache rechecks after an executor reset; current attempt sources remain mandatory.')
parser.add_argument('--keep-sdk-output-copies', action='store_true', help='Keep private SDK outputs when disk space is sufficient; avoid replacing outputs while the exporter may still write them.')
args = parser.parse_args()
if not re.fullmatch(r'r29-[0-9]+', args.attempt):
    parser.error('Expected a unique r29-NNN build attempt.')
if not args.keep_sdk_output_copies:
    parser.error('Stage8 export requires --keep-sdk-output-copies after the recorded r9 exporter SDK race.')
workspace = args.workspace.resolve()
tools = args.tools.resolve()
staging = args.staging.resolve()
staging.mkdir(parents=True, exist_ok=True)
nuget_config=staging/'dotnet-home/.nuget/NuGet/NuGet.Config'
nuget_config.parent.mkdir(parents=True,exist_ok=True)
nuget_config.write_text('<configuration><packageSources><clear/><add key="verified-official-packages" value="'+str(args.tools.resolve()/'nuget/feed')+'"/></packageSources></configuration>')
process_tmp = staging / 'tmp'
process_tmp.mkdir(parents=True, exist_ok=True)
apk = (args.output or workspace / 'r29-deliverables/Project1998-G7-V4-r29-arm64.apk').resolve()
if apk.exists():
    raise SystemExit('Existing APK preserved: ' + str(apk))
apk.parent.mkdir(parents=True, exist_ok=True)
logs = root / 'evidence' / ('build-' + args.attempt)
logs.mkdir(parents=True, exist_ok=False)
private = args.private_signing.resolve()
key = private / 'r0-development.keystore'
password_file = private / 'signing-password'
if not key.is_file() or not password_file.is_file():
    raise SystemExit('Existing development signing key unavailable; no replacement generated.')
sdk = tools / 'dotnet'
env = os.environ | {
    'DOTNET_ROOT': str(sdk), 'DOTNET_CLI_HOME': str(staging / 'dotnet-home'),
    'NUGET_PACKAGES': str(args.packages), 'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
    'MSBUILDDISABLENODEREUSE': '1', 'GODOT_SILENCE_ROOT_WARNING': '1',
    # Godot invokes dotnet publish with default maxcpucount. This host denies
    # MSBuild worker named-pipe sockets; one visible build CPU keeps it in-proc.
    # It is a build-process setting, not an application runtime setting.
    'DOTNET_PROCESSOR_COUNT': '1', 'DOTNET_CLI_USE_MSBUILD_SERVER':'0',
    # Offline exact-lock reproducibility; preserve separate current advisory evidence.
    'NuGetAudit': 'false', 'UseMonoRuntime': 'true', 'RestoreSources': str(tools / 'nuget/feed'),
    'XDG_CONFIG_HOME': str(staging / 'editor-config'), 'XDG_DATA_HOME': str(staging / 'editor-data'),
    'XDG_CACHE_HOME': str(staging / 'editor-cache'),
    'JAVA_HOME': os.environ.get('P1998_JAVA_HOME', '/usr/lib/jvm/java-17-openjdk-amd64'),
    'TMP': str(process_tmp), 'TEMP': str(process_tmp),
    'PATH': str(sdk) + ':' + os.environ['PATH'], 'TMPDIR': str(process_tmp),
}
godot = tools / 'godot-mono/Godot_v4.6-stable_mono_linux_x86_64/Godot_v4.6-stable_mono_linux.x86_64'
android = tools / 'android-sdk/build-tools/35.0.1'
def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def source_fingerprint():
    inputs = {}
    folders = [root.parent / 'Host'] + [root.parent / 'candidate' / part
        for part in ['Server', 'Shared', 'Shared.Core', 'Protocol.Tk495']]
    for folder in folders:
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(folder)
            if any(part in ['obj', 'bin'] for part in relative.parts):
                continue
            if path.is_file() and (path.suffix in ['.cs', '.csproj'] or path.name == 'packages.lock.json'):
                inputs[(root.parent.name + '/' + path.relative_to(root.parent).as_posix())] = sha(path)
    # r16 adds user-approved compatibility content. Freeze its raw sources as
    # well as the ZIP so a late content edit cannot hide behind an older archive.
    for path in sorted((root.parent / 'candidate/game-data').rglob('*')):
        if path.is_file():
            inputs[root.parent.name + '/' + path.relative_to(root.parent).as_posix()] = sha(path)
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in ['obj', 'bin', '.godot', 'evidence'] for part in relative.parts):
            continue
        if not path.is_file():
            continue
        if relative.parts[0] == 'assets' and (path.name.startswith('g1a-normal-earned.sqlite3') or 'test-only' in relative.parts):
            continue  # excluded from this playable APK; not a frozen product input
        if relative.parts[0] in ['assets', 'native', 'Localization'] or path.suffix in ['.cs', '.csproj', '.tscn', '.gd', '.gdshader', '.uid', '.import', '.cfg', '.godot', '.sln'] or path.name == 'packages.lock.json' or (relative.parts[0] == 'build' and path.suffix == '.py'):
            inputs[(root.parent.name + '/' + path.relative_to(root.parent).as_posix())] = sha(path)
    # Inherited compiler/SDK settings also affect otherwise identical C# inputs.
    for folder in [root.parent, root.parent / 'candidate', root.parent / 'Host', root]:
        for name in ['Directory.Build.props', 'Directory.Build.targets', 'Directory.Packages.props', 'global.json', '.editorconfig', 'NuGet.Config', 'nuget.config']:
            setting = folder / name
            if setting.is_file():
                inputs[root.parent.name + '/' + setting.relative_to(root.parent).as_posix()] = sha(setting)
    return inputs

def verify_runtime_assets(package):
    """Require every selected original asset, or its current Godot import, in APK.

    Imported byte hashes are package proofs only. Runtime visual/audio behavior is
    verified separately; this check never reports Android execution or audibility.
    """
    rows = []
    names = set(package.namelist())
    for source in sorted((root / 'assets/runtime').rglob('*')):
        if not source.is_file() or source.suffix in ['.import', '.uid']:
            continue
        relative = source.relative_to(root).as_posix()
        entry = 'assets/' + relative
        row = {'source': relative, 'source_bytes': source.stat().st_size,
               'source_sha256': sha(source)}
        if entry in names and source.suffix != '.png':
            packaged = hashlib.sha256(package.read(entry)).hexdigest()
            if packaged != row['source_sha256']:
                raise SystemExit('APK original runtime asset differs: ' + relative)
            row.update(route='ORIGINAL_BYTES', apk_payloads={entry: packaged})
        else:
            imported = Path(str(source) + '.import')
            if not imported.is_file():
                raise SystemExit('APK runtime asset missing without import: ' + relative)
            metadata = imported.read_text()
            if entry in names:
                original_hash = hashlib.sha256(package.read(entry)).hexdigest()
                if original_hash != row['source_sha256']:
                    raise SystemExit('APK original texture bytes differ: ' + relative)
                row['original_bytes_also_present'] = {entry: original_hash}
            source_line = re.search(r'^source_file=("[^"\n]+")$', metadata, re.M)
            if source_line is None or json.loads(source_line.group(1)) != 'res://' + relative:
                raise SystemExit('Runtime import does not identify the selected source: ' + relative)
            remap = metadata.split('[remap]', 1)[-1].split('\n[', 1)[0]
            destinations = [json.loads(value) for value in re.findall(
                r'^path(?:\.[A-Za-z0-9_]+)?=("[^"\n]+")$', remap, re.M)]
            if not destinations:
                raise SystemExit('Runtime import has no resource path: ' + relative)
            metadata_entries = [entry + '.import', entry + '.remap']
            metadata_entry = next((name for name in metadata_entries if name in names), None)
            if metadata_entry is None:
                raise SystemExit('APK runtime asset has no resource remapping: ' + relative)
            exported_metadata = package.read(metadata_entry).decode('utf-8')
            payloads = {}
            source_md5 = hashlib.md5(source.read_bytes()).hexdigest()
            for resource in destinations:
                if not resource.startswith('res://.godot/imported/') or '..' in resource.split('/'):
                    raise SystemExit('Unexpected imported resource path: ' + resource)
                payload_entry = 'assets/' + resource[6:]
                if payload_entry not in names:
                    continue  # Platform variants may be omitted when not selected.
                local_payload = root / resource[6:]
                import_key = re.fullmatch(r'(.+-[a-f0-9]{32})(?:\..+)', local_payload.name)
                md5_cache = local_payload.parent / (import_key.group(1) + '.md5') if import_key else local_payload.with_suffix('.md5')
                if not local_payload.is_file() or not md5_cache.is_file() or 'source_md5="' + source_md5 + '"' not in md5_cache.read_text():
                    raise SystemExit('Runtime import is stale or missing for source: ' + relative)
                if resource not in exported_metadata:
                    raise SystemExit('APK runtime remapping omits its actual payload: ' + relative)
                payload_hash = hashlib.sha256(package.read(payload_entry)).hexdigest()
                if payload_hash != sha(local_payload):
                    raise SystemExit('APK imported runtime payload differs: ' + relative)
                payloads[payload_entry] = payload_hash
            if not payloads:
                raise SystemExit('APK imported runtime resource missing: ' + relative)
            row.update(route='GODOT_IMPORTED_SELECTED_SOURCE', source_md5=source_md5,
                       import_metadata_sha256=sha(imported), apk_remapping=metadata_entry,
                       apk_remapping_sha256=hashlib.sha256(package.read(metadata_entry)).hexdigest(),
                       apk_payloads=payloads)
        rows.append(row)
    if not rows:
        raise SystemExit('No selected runtime assets were verified.')
    receipt = {'status': 'PASS_SCOPED_PACKAGE_BYTES', 'selected_source_assets': len(rows),
               'android_execution': 'NOT_RUN', 'audible_output': 'NOT_RUN', 'assets': rows}
    (logs / 'RUNTIME_ASSET_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

def verify_bootstrap_resources(package):
    # GDScript must survive a release export before it can report managed startup
    # failures. This is a byte/resource check, not a claim of Android execution.
    rows = []
    names = set(package.namelist())
    for relative in ['Boot.tscn', 'Boot.gd']:
        original = root / relative
        if not original.is_file():
            raise SystemExit('Native bootstrap source missing: ' + relative)
        entry = 'assets/' + relative
        row = {'source': relative, 'source_sha256': sha(original)}
        if entry in names:
            payload = package.read(entry)
            if hashlib.sha256(payload).hexdigest() != row['source_sha256']:
                raise SystemExit('Unconverted bootstrap source differs: ' + relative)
            row['payload_entry'] = entry
        elif entry + '.remap' in names:
            remapping = package.read(entry + '.remap').decode('utf-8')
            match = re.search(r'^path=("[^"\n]+")$', remapping, re.M)
            if match is None:
                raise SystemExit('Bootstrap resource remap has no payload path: ' + relative)
            resource = json.loads(match.group(1))
            if not resource.startswith('res://') or '..' in resource.split('/'):
                raise SystemExit('Bootstrap remap path invalid: ' + relative)
            mapped = 'assets/' + resource[6:]
            if mapped not in names:
                raise SystemExit('Bootstrap compiled payload missing: ' + mapped)
            payload = package.read(mapped)
            row.update(payload_entry=mapped, remap_entry=entry + '.remap',
                remap_sha256=hashlib.sha256(remapping.encode()).hexdigest())
        else:
            raise SystemExit('Bootstrap source/compiled remap absent: ' + relative)
        if not payload:
            raise SystemExit('Bootstrap payload is empty: ' + relative)
        row.update(payload_bytes=len(payload), payload_sha256=hashlib.sha256(payload).hexdigest())
        rows.append(row)
    receipt = {'status': 'PASS_SCOPED_BOOTSTRAP_PACKAGED_BYTES_AND_REMAPS',
        'android_execution': 'NOT_RUN', 'resources': rows}
    (logs / 'BOOTSTRAP_RESOURCE_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def dedup_published_sdk_duplicates(folders=None, receipt_name="POST_PUBLISH_SDK_DUPLICATE_RECLAIM.json", phase="POST_PUBLISH"):
    """Retain exact output paths/bytes, reclaim only finished SDK copies.

    The Android exporter is now a reader of these fully published outputs.
    Atomic replacement lets existing open file handles finish reading the old
    exact bytes; later opens read identical SDK bytes. No SDK files are written.
    """
    if args.keep_sdk_output_copies:
        free = os.statvfs(staging).f_bavail * os.statvfs(staging).f_frsize
        report = {'status': 'NOT_RUN_SDK_RECLAIM_DISABLED_PRIVATE_COPIES_RETAINED',
            'scope': 'No generated SDK output replacement while exporter may still be writing.',
            'free_before': free, 'free_after': free, 'rows': [],
            'reason': 'Recovered overlay has ample space; actual r9-003 detected an exporter output changing during post-publish reclaim. All APK, source, native, alignment and signature checks remain required.'}
        (logs / receipt_name).write_text(json.dumps(report, indent=2) + '\n')
        print(phase.lower(), 'SDK reclaim NOT_RUN; private copies retained; free', free, flush=True)
        return
    from collections import defaultdict
    if folders is None:
        folders = [root.parent / 'candidate' / part / 'bin/ExportRelease'
            for part in ['Server', 'Shared', 'Shared.Core', 'Protocol.Tk495']]
        folders += [root.parent / 'Host/bin/ExportRelease', root / '.godot/mono/temp/bin/ExportRelease']
    files = [p for folder in folders for p in folder.rglob('*')
        if p.is_file() and not p.is_symlink()
        and p.name not in ['G1BProbe.dll', 'EmbeddedHost.dll', 'Server.dll', 'Shared.dll', 'Shared.Core.dll', 'Protocol.Tk495.dll']
        and p.suffix in ['.dll', '.pdb', '.so', '.a', '.dylib', '.jar', '.dex']]
    wanted = {(p.name, p.stat().st_size) for p in files}
    candidates = defaultdict(list)
    for folder, directories, names in os.walk(args.packages):
        for name in names:
            path = Path(folder) / name
            if (name, path.stat().st_size) in wanted:
                candidates[(name, path.stat().st_size)].append(path)
    # GodotSharp symbols are shipped with the official engine API, rather than
    # the NuGet package. They are also immutable SDK sources, not app outputs.
    for configuration in ['Release', 'Debug']:
        api = godot.parent / 'GodotSharp/Api' / configuration
        if api.is_dir():
            for path in api.iterdir():
                if path.is_file() and (path.name, path.stat().st_size) in wanted:
                    candidates[(path.name, path.stat().st_size)].append(path)
    sdk_hashes = {}
    rows = []
    before = os.statvfs(staging).f_bavail * os.statvfs(staging).f_frsize
    for path in files:
        stat = path.stat()
        matches = candidates[(path.name, stat.st_size)]
        if not matches:
            continue
        digest = sha(path)
        for sdk_source in matches:
            if sdk_source not in sdk_hashes:
                sdk_hashes[sdk_source] = sha(sdk_source)
            if sdk_hashes[sdk_source] != digest:
                continue
            current = path.stat()
            if path.is_symlink() or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns):
                raise SystemExit('Finished SDK output unexpectedly changed during reclaim: ' + str(path))
            temporary = path.with_name(path.name + '.p1998-sdk-link')
            temporary.symlink_to(sdk_source)
            os.replace(temporary, path)
            if sha(path) != digest:
                raise SystemExit('Linked SDK output differs: ' + str(path))
            rows.append({'generated': str(path), 'bytes': stat.st_size, 'sha256': digest,
                'recovery_source': str(sdk_source), 'allocated_bytes': stat.st_blocks * 512,
                'original_device': stat.st_dev, 'original_inode': stat.st_ino,
                'original_mtime_ns': stat.st_mtime_ns})
            break
    receipt = {'status': 'PASS_EXACT_' + phase + '_SDK_DUPLICATE_RECLAIM',
        'scope': 'Own finished SDK output copies only; original product, app DLLs, assets, data, logs and APKs untouched.',
        'free_before': before, 'free_after': os.statvfs(staging).f_bavail * os.statvfs(staging).f_frsize,
        'rows': rows,
        'restore_recipe': 'Copy exact recovery_source into a private regular temporary file, verify SHA, replace generated symlink atomically before writing/rebuilding old output paths.'}
    (logs / receipt_name).write_text(json.dumps(receipt, indent=2) + '\n')
    print(phase.lower(), 'exact SDK duplicate links', len(rows), 'free', receipt['free_after'], flush=True)


def pre_export_memory_guard():
    # The successful r8 export-only retry began with 437,534,720 free bytes;
    # a fresh publish needs extra headroom because its temporary runtime copies
    # do not already exist. Reclaim only our finished SDK output duplicates,
    # then stop before publish rather than repeating the known ENOSPC failure.
    folders = [root.parent / 'candidate' / part / 'bin/Release'
        for part in ['Server', 'Shared', 'Shared.Core', 'Protocol.Tk495']]
    folders += [root.parent / 'Host/bin/Release', root / '.godot/mono/temp/bin/Release']
    dedup_published_sdk_duplicates(folders,
        'PRE_EXPORT_SDK_DUPLICATE_RECLAIM.json', 'PRE_EXPORT')
    free = os.statvfs(staging).f_bavail * os.statvfs(staging).f_frsize
    required = 450 * 1024 * 1024
    report = {'status': 'PASS_EXPORT_SPACE_RESERVE' if free >= required
              else 'BLOCKED_EXPORT_SPACE_RESERVE',
        'free_bytes': free, 'minimum_free_bytes': required,
        'basis': 'r8 actual publish ENOSPC retained; r8 successful retry started with 437,534,720 bytes and existing partial publish outputs. New r16 publish requires 450MiB before starting.',
        'actual_android_export': 'NOT_RUN', 'stage6': 'PRIOR_EVIDENCE_ONLY_NOT_R29_DEVICE_PASS', 'stage7': 'IN_PROGRESS', 'stage8': 'IN_PROGRESS_NOT_WHOLE_STAGE_PASS'}
    (logs / 'PRE_EXPORT_MEMORY_GUARD.json').write_text(json.dumps(report, indent=2) + '\n')
    if free < required:
        raise SystemExit('BLOCKED before publish: insufficient verified export filesystem reserve; prior successful compilation evidence retained.')


def verify_sdk_recovery_sources_unchanged():
    path = logs / 'POST_PUBLISH_SDK_DUPLICATE_RECLAIM.json'
    if not path.is_file():
        raise SystemExit('Actual Android export did not reach the post-publish SDK duplicate guard.')
    reports = [json.loads(path.read_text())]
    early = logs / 'PRE_EXPORT_SDK_DUPLICATE_RECLAIM.json'
    if early.is_file():
        reports.append(json.loads(early.read_text()))
    sources = {}
    for report in reports:
        for row in report['rows']:
            source, expected = row['recovery_source'], row['sha256']
            if source in sources and sources[source] != expected:
                raise SystemExit('Conflicting SDK recovery SHA evidence: ' + source)
            sources[source] = expected
    current_attempt_sources = set(sources)
    preflight = root.parent / 'evidence/r13-build-preflight'
    supplemental = list(preflight.glob('pc-compile-*/DESKTOP_SDK_DUPLICATE_RECLAIM.json'))
    supplemental += list(preflight.glob('CANDIDATE_PC*_SDK_DUPLICATE_RECLAIM.json'))
    for supplemental_receipt in sorted(supplemental):
        for row in json.loads(supplemental_receipt.read_text())['rows']:
            source, expected = row['recovery_source'], row['sha256']
            if source in sources and sources[source] != expected:
                raise SystemExit('Conflicting SDK recovery SHA evidence: ' + source)
            sources[source] = expected
    old_generated_reclaim = root.parent / 'evidence/r13-build-preflight/OLD_GENERATED_SDK_DUPLICATE_RECLAIM.json'
    if old_generated_reclaim.is_file():
        old_report = json.loads(old_generated_reclaim.read_text())
        for source, expected in old_report['canonical_sources_sha256'].items():
            if source in sources and sources[source] != expected:
                raise SystemExit('Conflicting SDK recovery SHA evidence: ' + source)
            sources[source] = expected
    unavailable_historical = []
    for source, expected in sources.items():
        if not Path(source).is_file() and args.recovered_host and source not in current_attempt_sources:
            unavailable_historical.append({'path': source, 'expected_sha256': expected,
                'status': 'NOT_RUN_HISTORICAL_CACHE_LOST_IN_EXECUTOR_RESET'})
            continue
        if sha(source) != expected:
            raise SystemExit('SDK recovery source changed through export: ' + source)
    receipt = {'status': 'PASS_ALL_SDK_RECOVERY_SOURCE_BYTES_UNCHANGED',
        'unique_sources': len(sources) - len(unavailable_historical), 'android_execution': 'NOT_RUN',
        'current_attempt_sources_all_mandatory': True,
        'historical_unavailable_after_executor_reset': unavailable_historical}
    (logs / 'SDK_RECOVERY_SOURCES_UNCHANGED.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def run(name, command):
    path = logs / (name + '.log')
    with path.open('w') as out:
        if name == 'godot-release-export':
            # Actual publish is complete when Godot begins Android packaging.
            # At that point only byte-identical SDK output duplicates are linked
            # back to their immutable sources to bound exporter temporary RAM.
            proc = subprocess.Popen([str(v) for v in command], cwd=root, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                for line in proc.stdout:
                    out.write(line); out.flush()
                    if 'Started Exporting for Android' in line:
                        dedup_published_sdk_duplicates()
                proc.wait()
            except BaseException:
                # This is our own Popen child. A helper/interrupt failure must
                # not leave an exporter writing after the build has failed.
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=10)
                raise
        else:
            proc = subprocess.run([str(v) for v in command], cwd=root, env=env,
                                  stdout=out, stderr=subprocess.STDOUT)
    print(name, 'exit', proc.returncode, flush=True)
    if proc.returncode:
        print(path.read_text(errors='replace')[-8000:])
        raise SystemExit(proc.returncode)
    return path.read_text(errors='replace')

# Asset/source ownership stays outside this build driver. Validate the prepared
# immutable original content and native payload; never synthesize or seed a game DB.
content = root.parent / 'candidate/game-data'
archive = root / 'assets/game-data.zip'
manifest_path = root / 'assets/content-manifest.json'
if not archive.is_file() or not manifest_path.is_file():
    raise SystemExit('Prepared original content archive/manifest missing; asset owner must supply them before freeze.')
manifest_document = json.loads(manifest_path.read_text())
manifest = manifest_document['files']
pixel_folder = root / 'assets/runtime'
pixel_index = json.loads((pixel_folder/'character-pixels.json').read_text())
if pixel_index['blob_sha256'] != sha(pixel_folder/'character-pixels.bin') or pixel_index['source_catalog_sha256'] != sha(pixel_folder/'catalog.json'):
    raise SystemExit('Lossless character pixel inputs differ; regenerate and verify before freezing.')

if not manifest or len({entry['path'] for entry in manifest}) != len(manifest) or manifest_document['archive_sha256'] != sha(archive):
    raise SystemExit('Prepared content archive/manifest empty, duplicated, or mismatched.')
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None or set(z.namelist()) != {'game-data/' + entry['path'] for entry in manifest}:
        raise SystemExit('Prepared content ZIP entries or CRC differ from the manifest.')
    for entry in manifest:
        src = content / entry['path']
        if not src.is_file() or src.stat().st_size != entry['bytes'] or sha(src) != entry['sha256']:
            raise SystemExit('Original content source differs: ' + entry['path'])
        if hashlib.sha256(z.read('game-data/' + entry['path'])).hexdigest() != entry['sha256']:
            raise SystemExit('Archived content differs: ' + entry['path'])
# Earned fixtures may be used by isolated verification tools, never default play
# initialization. They are excluded from this playable APK by the export preset.
expected_fixture = None
fixture = root / 'assets/g1a-normal-earned.sqlite3'
if fixture.is_file():
    expected_fixture = sha(fixture)
    if expected_fixture != '76b7056729d8c2f7857633d2666a2bc0e86ec0ebc1b4bf1d424e220f2de34176':
        raise SystemExit('Optional immutable verification fixture differs.')
with zipfile.ZipFile(args.sqlite_android) as package:
    with zipfile.ZipFile(io.BytesIO(package.read('lib/net6.0-android31.0/SQLitePCLRaw.lib.e_sqlite3.android.aar'))) as aar:
        for rid, abi in [('android-arm64', 'arm64-v8a')]:
            dest = root / 'native' / rid / 'libe_sqlite3.so'
            if not dest.is_file() or sha(dest) != hashlib.sha256(aar.read('jni/' + abi + '/libe_sqlite3.so')).hexdigest():
                raise SystemExit('Prepared native SQLite missing/mismatched: ' + rid)

settings = staging / 'editor-config/godot/editor_settings-4.6.tres'
settings.parent.mkdir(parents=True, exist_ok=True)
settings.write_text('[gd_resource type="EditorSettings" format=3]\n[resource]\n'
    + 'export/android/android_sdk_path=' + json.dumps(str(tools / 'android-sdk')) + '\n'
    + 'export/android/java_sdk_path=' + json.dumps(env['JAVA_HOME']) + '\n')
templates = tools / 'templates-mono/templates'
(root / 'export_presets.cfg').write_text('''[preset.0]
name="G7 Android Release"
platform="Android"
runnable=true
export_filter="all_resources"
include_filter="assets/**"
exclude_filter="evidence/*,build/*,native/*,README.md,*.csproj,*.sln,*.lock.json,assets/g1a-normal-earned.sqlite3*,assets/test-only/*"
export_path=""
script_export_mode=2
[preset.0.options]
custom_template/debug="%s"
custom_template/release="%s"
gradle_build/use_gradle_build=false
architectures/armeabi-v7a=false
architectures/arm64-v8a=true
architectures/x86=false
architectures/x86_64=false
package/unique_name="com.irewon.project1998.g1bv4"
package/name="Project1998 V4"
package/signed=false
version/code=29
version/name="0.1.0-g7-v4-r29"
launcher_icons/main_192x192="res://assets/runtime/ui-extra/launcher-original.png"
launcher_icons/adaptive_foreground_432x432="res://assets/runtime/ui-extra/launcher-original.png"
screen/immersive_mode=true
screen/orientation=4
user_data_backup/allow=false
permissions/internet=false
permissions/access_network_state=false
dotnet/include_scripts_content=false
dotnet/include_debug_symbols=false
dotnet/embed_build_outputs=true
dotnet/android_use_linux_bionic=false
''' % (templates / 'android_debug.apk', templates / 'android_release.apk'))

preset=root/'export_presets.cfg'
preset.write_text(preset.read_text().replace('version/code=29',f'version/code={args.version_code}'))

if args.prepare_only:
    prepared = {'status': 'PREPARED_NOT_BUILT', 'content_files': len(manifest),
                'content_archive_sha256': sha(archive), 'native_package_sha256': sha(args.sqlite_android)}
    (logs / 'PREPARE_RECEIPT.json').write_text(json.dumps(prepared, indent=2) + '\n')
    print(json.dumps(prepared), flush=True)
    raise SystemExit(0)

# Resolve the actual Android restore graph before freezing build inputs. A fresh
# copied project initially has only neutral targets; Godot's final publish target
# is android-arm64 and must not silently change the accepted package locks.
run('godot-preflight-import', [godot, '--headless', '--editor', '--path', root, '--import', '--quit'])
run('host-android-restore', [sdk / 'dotnet', 'restore', root.parent / 'Host/EmbeddedHost.csproj', '-r', 'android-arm64', '-p:Configuration=Release', '-p:UseMonoRuntime=true',
    '-m:1', '-nr:false', '-p:NuGetAudit=false', '--ignore-failed-sources'])
run('android-restore', [sdk / 'dotnet', 'restore', root / 'G1BProbe.csproj', '-r', 'android-arm64', '-p:Configuration=Release', '-p:UseMonoRuntime=true',
    '-m:1', '-nr:false', '-p:NuGetAudit=false', '--ignore-failed-sources'])
for label, path, target in [('Host', root.parent / 'Host/packages.lock.json', 'net8.0/android-arm64'),
                            ('Android', root / 'packages.lock.json', 'net9.0/android-arm64')]:
    raw_lock = path.read_bytes()
    dependencies = json.loads(raw_lock)['dependencies']
    if target not in dependencies or any('GodotSharpEditor' in entries for entries in dependencies.values()):
        raise SystemExit('Preflight did not resolve the final Android Release dependency graph for ' + label)
    (logs / ('FROZEN_' + label + '_packages.lock.json')).write_bytes(raw_lock)
inputs = source_fingerprint()
(logs / 'SOURCE_INPUTS.json').write_text(json.dumps(inputs, indent=2) + '\n')
run('dotnet-info', [sdk / 'dotnet', '--info'])
csharp_build_log = run('csharp-build', [sdk / 'dotnet', 'build', root / 'G1BProbe.csproj', '-c', 'Release',
    '-t:Rebuild', '--no-restore', '--tl:off', '-m:1', '-nr:false',
    '-p:UseSharedCompilation=false', '-p:NuGetAudit=false', '--ignore-failed-sources', '-clp:Summary'])
# Actual r10 desktop attempts002/003 exited0 on an incomplete incremental path;
# full rebuild004 produced matching DLLs and the complete top-level summary.
# An exit code or existing assembly alone does not establish build completion.
if ('Build succeeded.' not in csharp_build_log
        or not re.search(r'^\s*0 Warning\(s\)\s*$', csharp_build_log, re.M)
        or not re.search(r'^\s*0 Error\(s\)\s*$', csharp_build_log, re.M)
        or not re.search(r'^\s*G1BProbe -> .+G1BProbe\.dll\s*$', csharp_build_log, re.M)):
    raise SystemExit('C# build returned without a complete top-level zero-warning/error summary; export not accepted.')
run('godot-import', [godot, '--headless', '--editor', '--path', root, '--import', '--quit'])
pre_export_memory_guard()
unsigned = staging / ('g1b-' + args.attempt + '-unsigned.apk')
run('godot-release-export', [godot, '--headless', '--path', root, '--export-release',
    'G7 Android Release', unsigned])
# Godot can report an export error while returning exit 0. Reject the actual
# unsigned artifact before signing if the managed application did not export.
with zipfile.ZipFile(unsigned) as z:
    names = z.namelist()
    for abi in ['arm64-v8a']:
        if 'lib/' + abi + '/libe_sqlite3.so' not in names:
            raise SystemExit('Export returned without required native SQLite for ' + abi)
    for assembly in ['G1BProbe.dll', 'EmbeddedHost.dll', 'Server.dll', 'Shared.dll', 'Shared.Core.dll', 'Protocol.Tk495.dll']:
        if sum(name.endswith('/' + assembly) for name in names) != 1:
            raise SystemExit('Export did not include exactly one arm64 copy of ' + assembly)
run('project-config-load', [sys.executable, root / 'build/verify_project_config.py', '--apk', unsigned,
    '--project', root / 'project.godot', '--godot', godot, '--output', logs / 'project-config-load'])
config_load = json.loads((logs / 'project-config-load/RECEIPT.json').read_text())
# Phone delivery is one APK below the connector's 100 MiB limit. Preserve each
# native payload byte while deflating the extraction-enabled arm64 libraries.
# The actual manifest must explicitly permit extraction; never assume it.
manifest_xml = run('manifest-before-compression', [android / 'aapt2', 'dump', 'xmltree', unsigned, '--file', 'AndroidManifest.xml'])
if not re.search(r'android:extractNativeLibs[^\n]*=true', manifest_xml):
    raise SystemExit('Native compression requires actual extractNativeLibs=true.')
compact = staging / ('g1b-' + args.attempt + '-compact.apk')
compression_rows = {}
import copy
with zipfile.ZipFile(unsigned) as src, zipfile.ZipFile(compact, 'x') as dst:
    for info in src.infolist():
        if 'x86_64' in info.filename:
            raise SystemExit('Unexpected x86_64 payload in arm64-only export: ' + info.filename)
        target = copy.copy(info)
        if info.filename.startswith('lib/arm64-v8a/') and info.filename.endswith(('.so', '.a')):
            target.compress_type = zipfile.ZIP_DEFLATED
        digest = hashlib.sha256()
        with src.open(info) as a, dst.open(target, 'w') as b:
            for block in iter(lambda: a.read(1048576), b''):
                digest.update(block); b.write(block)
        compression_rows[info.filename] = {'bytes': info.file_size, 'sha256': digest.hexdigest(),
            'before_compression': info.compress_type, 'after_compression': target.compress_type}
with zipfile.ZipFile(compact) as package:
    if package.testzip() is not None:
        raise SystemExit('Compressed unsigned ZIP failed CRC validation.')
    for name, row in compression_rows.items():
        with package.open(name) as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise SystemExit('Compressed native/retained payload bytes differ: ' + name)
if compact.stat().st_size >= 100 * 1024 * 1024:
    raise SystemExit('Phone APK still exceeds connector 100 MiB limit.')
compression_receipt = {'status': 'PASS_ALL_ENTRY_BYTES_UNCHANGED_COMPACT_ARM64',
    'before': {'bytes': unsigned.stat().st_size, 'sha256': sha(unsigned)},
    'after': {'bytes': compact.stat().st_size, 'sha256': sha(compact)},
    'entries': compression_rows, 'manifest_extract_native_libs': True, 'android_execution': 'NOT_RUN'}
(logs / 'COMPACT_ARM64_RECEIPT.json').write_text(json.dumps(compression_receipt, indent=2) + '\n')
unsigned.unlink()  # exact decompressed entry bytes verified above; own generated intermediate
unsigned = compact
aligned = staging / ('g1b-' + args.attempt + '-aligned.apk')
run('zipalign', [android / 'zipalign', '-f', '-P', '16', '4', unsigned, aligned])
# Only this attempt's reproducible unsigned intermediate is removed after
# zipalign succeeded. Preserve its hash/size first and keep the aligned payload
# until the separately signed APK has passed its independent checks.
unsigned_receipt = {'scope': 'Own reproducible unsigned build intermediate only',
    'path': str(unsigned), 'bytes': unsigned.stat().st_size, 'sha256': sha(unsigned),
    'zipalign_exit': 0, 'aligned_payload': str(aligned)}
(logs / 'UNSIGNED_INTERMEDIATE_RECEIPT.json').write_text(json.dumps(unsigned_receipt, indent=2) + '\n')
unsigned.unlink()
env['G1B_SIGNING_PASSWORD'] = password_file.read_text().strip()
run('sign', [android / 'apksigner', 'sign', '--ks', key, '--ks-key-alias', 'r0probe',
    '--ks-pass', 'env:G1B_SIGNING_PASSWORD', '--key-pass', 'env:G1B_SIGNING_PASSWORD', '--out', apk, aligned])
signature = run('signature', [android / 'apksigner', 'verify', '--verbose', '--print-certs', apk])
certificate = 'ecea13778e2466b3e568f45bfe1facb6fd708bdd0ed3f6ae2a4c305da2ebb030'
assert 'certificate SHA-256 digest: ' + certificate in signature
run('alignment', [android / 'zipalign', '-c', '-P', '16', '4', apk])
badging = run('badging', [android / 'aapt2', 'dump', 'badging', apk])
permissions = run('permissions', [android / 'aapt2', 'dump', 'permissions', apk])
assert 'android.permission.INTERNET' not in permissions
assert "name='com.irewon.project1998.g1bv4'" in badging
assert f"versionCode='{args.version_code}'" in badging
assert "versionName='0.1.0-g7-v4-r29'" in badging
assert "native-code: 'arm64-v8a'" in badging and 'x86_64' not in badging
assert apk.stat().st_size < 100 * 1024 * 1024
with zipfile.ZipFile(apk) as z:
    for name, row in compression_rows.items():
        with z.open(name) as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise SystemExit('Signed APK changes a compacted payload: ' + name)
    if z.testzip() is not None:
        raise SystemExit('Signed APK ZIP CRC validation failed.')
    natives = {abi: hashlib.sha256(z.read('lib/' + abi + '/libe_sqlite3.so')).hexdigest()
               for abi in ['arm64-v8a']}
    dlls = [p for p in z.namelist() if p.endswith('/Server.dll') or p.endswith('/Shared.dll')]
    assembly_hashes = {p: hashlib.sha256(z.read(p)).hexdigest() for p in z.namelist()
        if p.endswith(('/Server.dll', '/Shared.dll', '/Shared.Core.dll', '/Protocol.Tk495.dll', '/EmbeddedHost.dll', '/G1BProbe.dll'))}
    for abi in ['arm64']:
        probe_il = z.read('assets/.godot/mono/publish/' + abi + '/G1BProbe.dll')
        host_il = z.read('assets/.godot/mono/publish/' + abi + '/EmbeddedHost.dll')
        if 'P1998-G7-V4-20261022-r29'.encode('utf-16le') not in probe_il:
            raise SystemExit('APK contains a stale diagnostic app assembly for ' + abi)
        if b'HostBootstrap' not in host_il or b'EntryDiagnostics' not in host_il or b'EmbeddedStartupException' not in host_il:
            raise SystemExit('APK omits required startup bootstrap/diagnostics for ' + abi)
    if 'assets/assets/runtime/catalog.json' not in z.namelist() or hashlib.sha256(z.read('assets/assets/runtime/catalog.json')).hexdigest() != sha(root / 'assets/runtime/catalog.json'):
        raise SystemExit('APK runtime catalog missing or differs from frozen client input.')
    config_bytes = z.read('assets/project.binary')
    if len(config_bytes) <= 8 or config_bytes[:4] != b'ECFG' or hashlib.sha256(config_bytes).hexdigest() != config_load['project_binary_sha256']:
        raise SystemExit('Signed APK binary project settings differ from verified nonempty ECFG.')
    if any(not item.is_dir() and item.file_size == 0 for item in z.infolist()):
        raise SystemExit('Signed APK includes an empty packaged file.')
    runtime_assets = verify_runtime_assets(z)
    bootstrap_resources = verify_bootstrap_resources(z)
    if any(name.startswith('assets/assets/g1a-normal-earned.sqlite3') or name.startswith('assets/assets/test-only/') for name in z.namelist()):
        raise SystemExit('Verification fixture family leaked into the default playable APK.')
    if hashlib.sha256(z.read('assets/assets/game-data.zip')).hexdigest() != sha(archive):
        raise SystemExit('APK content archive differs from the frozen original content input.')
run('launcher-resource-review', [sys.executable, root.parent / 'verification/r16/toolchain/verify_launcher.py',
    '--apk', apk, '--source', root / 'assets/runtime/ui-extra/launcher-original.png',
    '--official-template', tools / 'templates-mono/templates/android_release.apk',
    '--output', logs / 'LAUNCHER_RESOURCE_REVIEW.json'])
sdk_recovery_sources = verify_sdk_recovery_sources_unchanged()
after = source_fingerprint()
if inputs != after:
    changed = sorted(p for p in set(inputs) | set(after) if inputs.get(p) != after.get(p))
    (logs / 'SOURCE_CHANGED_DURING_BUILD.json').write_text(json.dumps(changed, indent=2) + '\n')
    raise SystemExit('Build inputs changed during export; this APK is not accepted as a matched candidate.')
post_build_locks = {}
for label, path in [('Host', root.parent / 'Host/packages.lock.json'), ('Android', root / 'packages.lock.json')]:
    raw = path.read_bytes()
    copied = logs / ('POST_BUILD_' + label + '_packages.lock.json')
    copied.write_bytes(raw)
    post_build_locks[label] = {'source': str(path), 'sha256': sha(path),
        'dependency_targets': list(json.loads(raw)['dependencies']), 'evidence': copied.name,
        'frozen_sha256': sha(logs / ('FROZEN_' + label + '_packages.lock.json'))}
post_inputs = {'status': 'PASS_ALL_FROZEN_INPUTS_UNCHANGED', 'source_input_count': len(inputs),
    'source_inputs_sha256': sha(logs / 'SOURCE_INPUTS.json'), 'inputs_equal_after_export': inputs == after,
    'post_abi_package_locks': post_build_locks}
(logs / 'POST_BUILD_INPUTS_UNCHANGED.json').write_text(json.dumps(post_inputs, indent=2) + '\n')
receipt = {'status': 'BUILD_PASS', 'kind': 'R29_SEVEN_HUD_AND_TOTOGO_POSITION_ONLY_RECOVERY',
    'build_id': 'P1998-G7-V4-20261022-r29', 'apk': str(apk), 'bytes': apk.stat().st_size,
    'sha256': sha(apk), 'native': natives, 'content_archive_sha256': sha(archive),
    'certificate_sha256': certificate,
    'content_files': len(manifest), 'release_export': True, 'trimmed': False, 'aot': False,
    'optional_source_test_fixture_sha256': expected_fixture, 'test_fixture_packaged': False,
    'device_runtime': 'NOT_RUN', 'stage7_runtime': 'NOT_RUN', 'stage6': 'PRIOR_EVIDENCE_ONLY_NOT_R29_DEVICE_PASS', 'stage7': 'IN_PROGRESS', 'stage8': 'IN_PROGRESS_NOT_WHOLE_STAGE_PASS', 'original_assemblies': dlls}
receipt['assembly_sha256'] = assembly_hashes
receipt['project_binary_bytes'] = len(config_bytes)
receipt['project_binary_sha256'] = hashlib.sha256(config_bytes).hexdigest()
receipt['project_settings_load_receipt_sha256'] = sha(logs / 'project-config-load/RECEIPT.json')
receipt['binary_settings_loaded_without_textual_fallback'] = True
receipt['runtime_asset_receipt_sha256'] = sha(logs / 'RUNTIME_ASSET_RECEIPT.json')
receipt['runtime_asset_sources_verified'] = runtime_assets['selected_source_assets']
receipt['bootstrap_resource_receipt_sha256'] = sha(logs / 'BOOTSTRAP_RESOURCE_RECEIPT.json')
receipt['launcher_resource_receipt_sha256'] = sha(logs / 'LAUNCHER_RESOURCE_REVIEW.json')
receipt['source_inputs_sha256'] = sha(logs / 'SOURCE_INPUTS.json')
receipt['source_input_count'] = len(inputs)
receipt['post_abi_package_locks'] = post_build_locks
receipt['post_build_inputs_receipt_sha256'] = sha(logs / 'POST_BUILD_INPUTS_UNCHANGED.json')
receipt['package'] = 'com.irewon.project1998.g1bv4'
receipt['version_code'] = args.version_code
receipt['version_name'] = '0.1.0-g7-v4-r29'
prior = Path(os.environ['P1998_BASELINE_APK'])
if not prior.is_file() or prior.stat().st_size != 98843787 or sha(prior) != '2066fd5032b3f2a75749f97817010a7e69ad1d96db56e630cd6d7a5b3957c2ec':
    raise SystemExit('Latest r27 predecessor is unavailable or differs; do not replace it.')
receipt['previous_apk_preserved'] = str(prior)
receipt['predecessor_verification'] = {'status':'PASS_ACTUAL_LATEST_R28_BYTES','sha256':sha(prior),'bytes':prior.stat().st_size}
receipt['abis'] = ['arm64-v8a']
receipt['phone_compact_receipt_sha256'] = sha(logs / 'COMPACT_ARM64_RECEIPT.json')
receipt['sdk_recovery_sources_receipt_sha256'] = sha(logs / 'SDK_RECOVERY_SOURCES_UNCHANGED.json')
(logs / 'BUILD_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
(logs / 'ALIGNED_INTERMEDIATE_RECEIPT.json').write_text(json.dumps({
    'scope': 'Own generated aligned unsigned artifact; removed after signed APK validation',
    'bytes': aligned.stat().st_size, 'sha256': sha(aligned), 'signed_apk_sha256': receipt['sha256'],
    'all_original_entry_bytes_verified_in_signed_apk': True}, indent=2) + '\n')
aligned.unlink()
print(json.dumps(receipt), flush=True)
