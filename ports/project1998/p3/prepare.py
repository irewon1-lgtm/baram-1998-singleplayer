#!/usr/bin/env python3
"""Make a bounded, private P3 source-linked experiment; no original code in Git.

The unchanged Server project is the desktop oracle. The private app build adds
OfflineApi.cs and changes OutputType to Library, without altering rule bodies.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import io
import zipfile
import xml.etree.ElementTree as ET

ORIGINAL_HEAD = '65cb3ef28f289ee35d19abfb6829d6120b9ec0cd'
P3 = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--font-dir', type=Path, required=True)
    p.add_argument('--sqlite-android-nupkg', type=Path, required=True)
    a = p.parse_args(); src = a.source.resolve(); out = a.output.resolve()
    pins = json.loads((P3 / 'source_pins.json').read_text())
    assert pins['head'] == ORIGINAL_HEAD
    drift = [entry['path'] for entry in pins['files'] if not (src / entry['path']).is_file()
             or sha(src / entry['path']) != entry['sha256']]
    if drift: raise ValueError('Pinned source drift: ' + ', '.join(drift))
    repo = P3.parents[2]
    if out.is_relative_to(repo) or out == src or out.is_relative_to(src):
        raise ValueError('Use a separate private output directory')
    if out.exists():
        raise ValueError('Output already exists; choose a new run directory')
    out.mkdir(parents=True)
    private_src = out / 'source'; private_src.mkdir()
    inventory = []
    for folder in ['Shared.Core', 'Shared', 'Protocol.Tk495', 'Server']:
        shutil.copytree(src / folder, private_src / folder,
                        ignore=shutil.ignore_patterns('bin', 'obj'))
        for f in sorted((src / folder).rglob('*')):
            if f.is_file() and not {'bin', 'obj'} & set(f.relative_to(src).parts):
                inventory.append({'path': str(f.relative_to(src)), 'sha256': sha(f)})
    shutil.copyfile(src / 'Directory.Build.props', private_src / 'Directory.Build.props')
    project = private_src / 'Server/Server.csproj'
    text = project.read_text(encoding='utf-8-sig').replace('<OutputType>Exe</OutputType>', '<OutputType>Library</OutputType>')
    text = text.replace('</Project>', '<ItemGroup><Compile Remove="Program.cs" /></ItemGroup>\n</Project>')
    assert text != project.read_text(encoding='utf-8-sig')
    project.write_text(text)
    shutil.copyfile(P3 / 'OfflineApi.cs', private_src / 'Server/P3.OfflineApi.cs')
    # Host-path seam only: embedded Android may have an empty assembly base
    # directory. Avoid a desktop ancestor walk outside the app sandbox.
    paths = private_src / 'Shared/RepoPaths.cs'
    original_paths_hash = sha(paths)
    needle = '        var dir = new DirectoryInfo(AppContext.BaseDirectory);'
    replacement = '''        // P3 host supplies its absolute app-private deployment root.
        var appRoot = Environment.GetEnvironmentVariable("P1998_P3_ROOT");
        if (appRoot is not null)
        {
            if (string.IsNullOrWhiteSpace(appRoot) || !Path.IsPathFullyQualified(appRoot))
                throw new InvalidDataException("P3 deployment root must be absolute and non-empty");
            return Path.GetFullPath(appRoot);
        }
''' + needle
    paths_text = paths.read_text()
    assert paths_text.count(needle) == 1, 'Pinned RepoPaths host seam changed'
    paths.write_text(paths_text.replace(needle, replacement))
    path_overlay = {'path': 'Shared/RepoPaths.cs', 'source_sha256': original_paths_hash,
                    'private_build_sha256': sha(paths), 'override': 'P1998_P3_ROOT',
                    'scope': 'deployment-root resolution only; no rule-body edits',
                    'original_desktop_fallback': 'unchanged when override is absent'}
    (out / 'HOST_PATH_OVERLAY.json').write_text(json.dumps(path_overlay, indent=2) + '\n')
    content = out / 'content'; content.mkdir(parents=True)
    (out / 'runtime').mkdir()
    content_audit = []
    # All other tables are header-only, not missing, so no full-world population
    # hides in this experiment. Source rows retain raw IDs and values.
    full = {'ServerTuning.csv', 'EraFeatures.csv', 'ObjectFlagOverrides.csv', 'Tile533Map.csv', 'Obj533Fix.csv'}
    selectors = {
        'map_index.csv': lambda r: r['id'] == '4711',
        'Maps.csv': lambda r: r['MapId'] == '4711',
        'Items.csv': lambda r: r['ItmIdentifier'] in {'acorn', 'apple', 'wine', 'wooden_sword'},
        'ItemParams.csv': lambda r: r['key'] in {'acorn', 'apple', 'wine'},
        'mobs.csv': lambda r: r['MobId'] == '1',
    }
    for f in sorted((src / 'game-data').glob('*.csv')):
        with f.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(line for line in stream if line.strip() and not line.lstrip().startswith('#')); fields = reader.fieldnames
            rows = list(reader)
        keep = rows if f.name in full else [r for r in rows if selectors.get(f.name, lambda _: False)(r)]
        target = content / f.name
        if f.name in full:
            shutil.copyfile(f, target)
        else:
            with target.open('w', encoding='utf-8', newline='') as stream:
                w = csv.DictWriter(stream, fieldnames=fields); w.writeheader(); w.writerows(keep)
        content_audit.append({'path': f.name, 'source_sha256': sha(f), 'capsule_sha256': sha(target),
                              'source_rows': len(rows), 'kept_rows': len(keep)})
    for name in ['item_verbs.lua', 'spell_verbs.lua', 'npc_dialog.lua', 'mob_ai.lua', 'SObj.tbl']:
        shutil.copyfile(src / 'game-data' / name, content / name)
        content_audit.append({'path': name, 'source_sha256': sha(src / 'game-data' / name), 'capsule_sha256': sha(content / name)})
    (content / 'maps').mkdir()
    map_file = src / 'game-data/maps/TK4711.map'
    assert map_file.stat().st_size == 16 * 16 * 4
    shutil.copyfile(map_file, content / 'maps' / map_file.name)
    content_audit.append({'path': 'maps/' + map_file.name, 'source_sha256': sha(map_file), 'capsule_sha256': sha(content / 'maps' / map_file.name)})
    manifest = {'schema': 'project1998.p3.capsule.v1', 'original_head': ORIGINAL_HEAD,
                'source_files': inventory, 'content_files': content_audit,
                'overlay': {'path': 'Server/P3.OfflineApi.cs', 'sha256': sha(P3 / 'OfflineApi.cs')},
                'source_project_changes': ['Server OutputType Exe to Library', 'Exclude host-only top-level Program.cs'],
                'world': {'maps': [4711], 'automatic_spawns': 0, 'npcs': 0, 'warps': 0, 'item_rows': 4, 'mob_rows': 1}}
    # Preserve the v1 capsule identity so this repair accepts existing saves.
    # Build-only source changes are audited separately from the saved capsule.
    (out / 'SOURCE_LINK_MANIFEST.json').write_text(json.dumps(
        manifest | {'host_path_overlay': path_overlay}, indent=2) + '\n')
    (content / 'capsule.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copyfile(content / 'capsule.json', out / 'runtime/capsule.json')
    # CSVs are raw rule data, not Godot localization tables. A deterministic
    # capsule avoids the CSV translation importer and preserves source bytes.
    with zipfile.ZipFile(out / 'runtime/capsule.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for row in content_audit:
            info = zipfile.ZipInfo(row['path'], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (content / row['path']).read_bytes())
    for name in ['Scenario.cs', 'Probe.cs', 'ProbeStore.cs']:
        shutil.copyfile(P3 / name, out / 'runtime' / name)
    shutil.copytree(P3 / 'godot', out / 'runtime', dirs_exist_ok=True)
    shutil.copyfile(P3 / 'fixtures.json', out / 'runtime/fixtures.json')
    (out / 'runtime/fonts').mkdir()
    for origin, target in [('NotoSansKR[wght].ttf', 'NotoSansKR.ttf'), ('OFL.txt', 'OFL.txt')]:
        shutil.copyfile(a.font_dir / origin, out / 'runtime/fonts' / target)
    # The server's net8.0 SQLite bundle contains desktop RIDs, not Android.
    # Bring the SAME 2.1.6 upstream Android binary, explicitly per ABI, into
    # dotnet publish so Godot's C# export plugin adds it as a shared object.
    with zipfile.ZipFile(a.sqlite_android_nupkg) as package:
        with zipfile.ZipFile(io.BytesIO(package.read('lib/net6.0-android31.0/SQLitePCLRaw.lib.e_sqlite3.android.aar'))) as aar:
            native = []
            for rid, abi in [('android-arm64', 'arm64-v8a'), ('android-x64', 'x86_64')]:
                target = out / 'native' / rid / 'libe_sqlite3.so'; target.parent.mkdir(parents=True)
                target.write_bytes(aar.read('jni/' + abi + '/libe_sqlite3.so'))
                native.append({'rid': rid, 'abi': abi, 'sha256': sha(target)})
    (out / 'SQLITE_ANDROID.json').write_text(json.dumps({'package': 'SQLitePCLRaw.lib.e_sqlite3.android',
        'version': '2.1.6', 'nupkg_sha256': sha(a.sqlite_android_nupkg), 'native': native}, indent=2) + '\n')
    app = out / 'runtime/P3Probe.csproj'
    app.write_text('''<Project Sdk="Godot.NET.Sdk/4.6.0">
  <PropertyGroup><TargetFramework>net9.0</TargetFramework><EnableDynamicLoading>true</EnableDynamicLoading>
    <Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <UseSharedCompilation>false</UseSharedCompilation><BuildInParallel>false</BuildInParallel>
  </PropertyGroup>
  <ItemGroup><ProjectReference Include="../source/Server/Server.csproj" /></ItemGroup>
  <ItemGroup Condition="Exists('../native/$(RuntimeIdentifier)/libe_sqlite3.so')">
    <Content Include="../native/$(RuntimeIdentifier)/libe_sqlite3.so" Link="libe_sqlite3.so" CopyToOutputDirectory="PreserveNewest" CopyToPublishDirectory="Always" />
  </ItemGroup>
</Project>\n''')
    project_guid = '{506849E8-B94B-4F48-86CD-E0DD772DE301}'
    configs = ['Debug', 'Release', 'ExportDebug', 'ExportRelease']
    solution = ['Microsoft Visual Studio Solution File, Format Version 12.00', '# Visual Studio Version 17',
        'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "P3Probe", "P3Probe.csproj", "' + project_guid + '"',
        'EndProject', 'Global', '\tGlobalSection(SolutionConfigurationPlatforms) = preSolution']
    solution += ['\t\t' + c + '|Any CPU = ' + c + '|Any CPU' for c in configs]
    solution += ['\tEndGlobalSection', '\tGlobalSection(ProjectConfigurationPlatforms) = postSolution']
    for c in configs:
        for kind in ['ActiveCfg', 'Build.0']:
            solution.append('\t\t' + project_guid + '.' + c + '|Any CPU.' + kind + ' = ' + c + '|Any CPU')
    solution += ['\tEndGlobalSection', 'EndGlobal', '']
    (out / 'runtime/P3Probe.sln').write_text('\n'.join(solution))
    oracle = out / 'oracle'; oracle.mkdir()
    shutil.copyfile(P3 / 'Scenario.cs', oracle / 'Scenario.cs')
    shutil.copyfile(P3 / 'Oracle.cs', oracle / 'Program.cs')
    oracle.joinpath('Oracle.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><OutputType>Exe</OutputType>
    <DefineConstants>ORIGINAL_ORACLE</DefineConstants><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors><UseSharedCompilation>false</UseSharedCompilation>
  </PropertyGroup>
  <ItemGroup><ProjectReference Include="%s" /></ItemGroup>
</Project>\n''' % (src / 'Server/Server.csproj'))
    dependency = []
    for name in ['Shared.Core', 'Shared', 'Protocol.Tk495', 'Server', 'LoginServer']:
        tree = ET.parse(src / name / (name + '.csproj'))
        dependency.append({'project': name, 'target_framework': 'net8.0 (Directory.Build.props)',
                           'packages': [x.attrib for x in tree.findall('.//PackageReference')],
                           'projects': [x.attrib['Include'] for x in tree.findall('.//ProjectReference')]})
    (out / 'DEPENDENCIES.json').write_text(json.dumps(dependency, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'linked_source_files': len(inventory), 'content_manifest_sha256': sha(content / 'capsule.json'), 'world': manifest['world']}))


if __name__ == '__main__': main()
