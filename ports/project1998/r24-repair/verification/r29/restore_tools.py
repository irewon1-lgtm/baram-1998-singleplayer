"""Recover the exact previously qualified tool archives after workspace maintenance."""
import concurrent.futures, hashlib, json, os, shutil, tarfile, urllib.request, zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
tools = root.parents[1] / 'toolchain-r27'
downloads = tools / 'downloads'
downloads.mkdir(parents=True, exist_ok=True)
receipt = json.loads((root / 'verification/r25/toolchain/RESTORE_RECEIPT.json').read_text())
runtime = json.loads((root / 'verification/r25/toolchain/NET8_RUNTIME.json').read_text())
jobs = receipt['downloads'] + [dict(runtime, name='dotnet-runtime-8.0.32-linux-x64.tar.gz', target='dotnet')]
records = []

def fetch(row, destination):
    expected = row.get('sha512') or row.get('sha256') or row.get('sha1')
    algorithm = 'sha512' if row.get('sha512') else 'sha256' if row.get('sha256') else 'sha1'
    def valid():
        return destination.exists() and hashlib.file_digest(destination.open('rb'), algorithm).hexdigest() == expected
    if not valid():
        partial = destination.with_suffix(destination.suffix + '.partial')
        url = row['url']
        # Cache-distinct request avoids earlier read-only Range probes being served as full archives.
        url += ('&' if '?' in url else '?') + 'p1998=r27-tools-full'
        with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        partial.replace(destination)
    if not valid() and row.get('bytes'):
        total = row['bytes']
        parts = list(range(0, total, 8 * 1024 * 1024))
        def range_part(start):
            end = min(total, start + 8 * 1024 * 1024) - 1
            part = destination.with_name(destination.name + f'.range-{start}')
            if part.exists() and part.stat().st_size == end-start+1: return part
            request = urllib.request.Request(row['url'] + f'?p1998-r27-range={start}', headers={'Range':f'bytes={start}-{end}'})
            with urllib.request.urlopen(request, timeout=60) as response:
                assert response.headers.get('Content-Range') == f'bytes {start}-{end}/{total}'
                data = response.read()
            assert len(data) == end-start+1
            part.write_bytes(data)
            return part
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            pieces = list(executor.map(range_part, parts))
        with destination.open('wb') as output:
            for piece in pieces:
                with piece.open('rb') as source: shutil.copyfileobj(source, output)
    assert valid(), f'Archive checksum mismatch: {destination.name}'
    print('VERIFIED', destination.name, destination.stat().st_size, flush=True)
    return destination

def recover(row):
    archive = fetch(row, downloads / row['name'])
    target = row.get('target')
    if target:
        destination = tools / target
        destination.mkdir(parents=True, exist_ok=True)
        if archive.name.endswith('.tar.gz'):
            with tarfile.open(archive) as bundle: bundle.extractall(destination, filter='data')
        else:
            with zipfile.ZipFile(archive) as bundle:
                members = bundle.infolist()
                if target == 'templates-mono':
                    members = [m for m in members if m.filename in ['templates/android_debug.apk', 'templates/android_release.apk']]
                if target.startswith('android-sdk/'):
                    top = members[0].filename.split('/')[0]
                    for member in members:
                        relative = Path(member.filename).relative_to(top)
                        if str(relative) == '.': continue
                        out = destination / relative
                        if member.is_dir(): out.mkdir(parents=True, exist_ok=True)
                        else:
                            out.parent.mkdir(parents=True, exist_ok=True)
                            with bundle.open(member) as source, out.open('wb') as sink: shutil.copyfileobj(source, sink)
                            out.chmod((member.external_attr >> 16) | 0o700)
                else:
                    for member in members:
                        bundle.extract(member, destination)
                        path = destination / member.filename
                        if path.is_file() and member.external_attr >> 16: path.chmod(member.external_attr >> 16)
    records.append(dict(row, status='CURRENT_ARCHIVE_HASH_VERIFIED_AND_EXTRACTED', local=str(archive)))

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(recover, jobs))

feed = tools / 'nuget/feed'
feed.mkdir(parents=True, exist_ok=True)
pins = json.loads((root / 'verification/r25/toolchain/nuget-pins.json').read_text())
known = {row['name'].lower(): row for row in json.loads((root / 'verification/r25/toolchain/EXECUTED-DEPENDENCY-RESTORE.json').read_text())}
packages = set()
for lock in [root/'android/packages.lock.json', root/'Host/packages.lock.json', root/'candidate/Tests/packages.lock.json']:
    if lock.exists():
        for group in json.loads(lock.read_text())['dependencies'].values():
            for name, row in group.items():
                if row.get('type') != 'Project': packages.add((name.lower(), row['resolved']))
for name, version in [('godot.net.sdk','4.6.0'),('sqlitepclraw.lib.e_sqlite3.android','2.1.6'),
    ('microsoft.netcore.app.ref','8.0.32'),('microsoft.aspnetcore.app.ref','8.0.32'),
    ('microsoft.netcore.app.host.linux-x64','8.0.32'),('microsoft.netcore.app.runtime.mono.android-arm64','8.0.32'),
    ('microsoft.netcore.app.runtime.mono.android-arm64','9.0.21')]: packages.add((name,version))

def package(pair):
    name, version = pair
    filename = f'{name}.{version}.nupkg'
    destination = feed / filename
    found = [p for p in (tools/'godot-mono').rglob('*.nupkg') if p.name.lower() == filename]
    if found:
        shutil.copy2(found[0], destination)
        if filename in known and hashlib.sha256(destination.read_bytes()).hexdigest() != known[filename]['sha256']:
            # NuGet's signed archive can differ from Godot's bundled unsigned copy.
            # Recover the exact previously pinned archive instead of accepting a new ZIP hash.
            fetch(dict(known[filename], url=f'https://api.nuget.org/v3-flatcontainer/{name}/{version}/{filename}'), destination)
    elif filename in known:
        fetch(dict(known[filename], url=f'https://api.nuget.org/v3-flatcontainer/{name}/{version}/{filename}'), destination)
    else:
        if not destination.exists():
            with urllib.request.urlopen(f'https://api.nuget.org/v3-flatcontainer/{name}/{version}/{filename}', timeout=60) as source, destination.open('wb') as sink:
                shutil.copyfileobj(source, sink)
        print('RESTORE_LOCK_WILL_VERIFY', filename, flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor: list(executor.map(package, sorted(packages)))
(tools/'offline.nuget.config').write_text('<configuration><packageSources><clear/><add key="local" value="'+str(feed)+'"/></packageSources></configuration>')
(root/'verification/r29/TOOLCHAIN-RECOVERY.json').write_text(json.dumps(dict(status='VERIFIED_CURRENT_ARCHIVES',tools=str(tools),archives=records,packages=len(packages)),indent=2))
print('TOOLS_READY', tools, flush=True)
