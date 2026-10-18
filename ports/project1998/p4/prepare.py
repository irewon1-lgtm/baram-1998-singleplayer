#!/usr/bin/env python3
"""Assemble the private original-code P4 route, keeping game bytes out of Git."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from convert import MAPS, NPCS

HERE = Path(__file__).resolve().parent
HEAD = '65cb3ef28f289ee35d19abfb6829d6120b9ec0cd'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ['source', 'output', 'font-dir', 'sqlite-android-nupkg', 'converted']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); src = a.source.resolve(); out = a.output.resolve()
    command = [sys.executable, str(HERE.parent / 'p3/prepare.py')]
    for key, value in vars(a).items(): command += ['--' + key.replace('_', '-'), str(value)]
    subprocess.run(command, check=True)
    content = out / 'content'; shutil.rmtree(content); content.mkdir()
    spatial_empty = {'AmbushConfig.csv', 'AmbushBursts.csv', 'EventCaves.csv', 'FallRooms.csv',
                     'MythicCaves.csv', 'PathHalls.csv', 'WorldMapTriggers.csv', 'WorldMapDests.csv',
                     'ForageAreas.csv', 'AreaSpawnsCrafting.csv', 'AreaSpawnsTrap.csv', 'ArenaDoors.csv'}
    selectors = {
        'map_index.csv': lambda r: int(r['id']) in MAPS,
        'Maps.csv': lambda r: int(r['MapId']) in MAPS,
        'NPCs.csv': lambda r: int(r['NpcMapId']) in MAPS and r['NpcIdentifier'] in NPCS,
        'mobs.csv': lambda r: r['Identifier'] in {'rabbit', 'squirrel'},
        'Spawns.csv': lambda r: int(r['SpnMapId']) in MAPS and r['SpnMobId'] in {'1', '2'},
        'AreaSpawns.csv': lambda r: int(r['Map']) in MAPS and r['MobId'] in {'1', '2'},
        'Warps.csv': lambda r: int(r['SourceMapId']) in MAPS and int(r['DestinationMapId']) in MAPS,
        'WarpQuestLocks.csv': lambda r: int(r['FromMap']) in MAPS and int(r['ToMap']) in MAPS,
        'NPCEquipment.csv': lambda r: False,
        'MobEquipment.csv': lambda r: False,
    }
    # These are positional numeric tables without a header. Preserve byte-for-byte.
    raw = {'Tile533Map.csv', 'Obj533Fix.csv', 'ObjectFlagOverrides.csv'}
    audit = []
    for f in sorted((src / 'game-data').glob('*.csv')):
        target = content / f.name
        if f.name in raw:
            shutil.copyfile(f, target); audit.append({'path': f.name, 'source_sha256': sha(f), 'kept': 'all'}); continue
        with f.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(line for line in stream if line.strip() and not line.lstrip().startswith('#'))
            fields = reader.fieldnames; rows = list(reader)
        select = selectors.get(f.name)
        if select is None and f.name not in spatial_empty:
            map_field = next((k for k in ['Map', 'MapId'] if k in fields), None)
            if map_field: select = lambda r, k=map_field: r[k].isdigit() and int(r[k]) in MAPS
        kept = [] if f.name in spatial_empty else [r for r in rows if select is None or select(r)]
        if select is None and f.name not in spatial_empty:
            shutil.copyfile(f, target)
        else:
            with target.open('w', encoding='utf-8', newline='') as stream:
                w = csv.DictWriter(stream, fieldnames=fields); w.writeheader(); w.writerows(kept)
        audit.append({'path': f.name, 'source_sha256': sha(f), 'source_rows': len(rows), 'kept_rows': len(kept)})
    for name in ['item_verbs.lua', 'spell_verbs.lua', 'npc_dialog.lua', 'mob_ai.lua', 'SObj.tbl']:
        shutil.copyfile(src / 'game-data' / name, content / name)
    (content / 'maps').mkdir()
    for mid in MAPS: shutil.copyfile(src / f'game-data/maps/TK{mid}.map', content / f'maps/TK{mid}.map')
    manifest = {'schema': 'project1998.p4.capsule.v1', 'original_head': HEAD, 'maps': list(MAPS),
                'files': [{'path': str(f.relative_to(content)), 'sha256': sha(f)} for f in sorted(content.rglob('*')) if f.is_file()]}
    runtime = out / 'runtime'
    (runtime / 'capsule.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(runtime / 'capsule.zip', 'w') as archive:
        for row in manifest['files']:
            info = zipfile.ZipInfo(row['path'], (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (content / row['path']).read_bytes())
    for name in ['Probe.cs', 'ProbeStore.cs', 'InteractiveCore.cs', 'Scenario.cs', 'fixtures.json']:
        (runtime / name).unlink()
    shutil.rmtree(runtime / 'play')
    for name in ['Bootstrap.cs', 'Checkpoint.cs', 'GameCore.cs']: shutil.copyfile(HERE / name, runtime / name)
    if (HERE / 'client').exists(): shutil.copytree(HERE / 'client', runtime / 'p4')
    (runtime / 'main.tscn').write_text('''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://Bootstrap.cs" id="1"]
[node name="P4" type="Control"]
layout_mode=3
anchors_preset=15
anchor_right=1.0
anchor_bottom=1.0
grow_horizontal=2
grow_vertical=2
script=ExtResource("1")
''')
    project = runtime / 'project.godot'
    project.write_text(project.read_text().replace('Project1998 P3 Core Probe', 'Project1998 P4'))
    assets = runtime / 'assets'; shutil.rmtree(assets)
    assets.mkdir()
    for name in ['ground.png', 'objects.png', 'actors.png', 'assets.json']:
        shutil.copyfile(a.converted / name, assets / name)
    shutil.copytree(a.converted / 'maps', assets / 'maps')
    server = out / 'source/Server'; shutil.copyfile(HERE / 'Adapter.cs', server / 'P4.Adapter.cs')
    (server / 'P3.OfflineApi.cs').unlink()
    patches = []
    def patch(file, old, new, purpose):
        target = server / file; before = sha(target); text = target.read_text()
        assert text.count(old) == 1, (file, old)
        target.write_text(text.replace(old, new))
        patches.append({'path': 'Server/' + file, 'before_sha256': before, 'after_sha256': sha(target), 'purpose': purpose})
    patch('World.SpawnDirector.cs', 'internal sealed class SpawnDirector', 'internal sealed partial class SpawnDirector', 'serialization host seam; no rule-body edit')
    hooks = [
        ('Session.Dialog.cs', 'private void SendScriptMessageP(uint npcId, string msg, DialogPortrait p, bool prev, bool next)',
         'P4Show(new P4Window { kind = "text", npc = npcId, text = msg });'),
        ('Session.Dialog.cs', 'private void SendNpcMenuP(Mob npc, DialogPortrait p, string prompt, IReadOnlyList<string> options)',
         'P4Show(new P4Window { kind = "menu", npc = npc.Id, text = prompt, options = options.ToArray() });'),
        ('Session.Dialog.cs', 'private void SendInputBox(uint entityId, DialogPortrait portrait, string prompt)',
         'P4Show(new P4Window { kind = "input", npc = entityId, text = prompt });'),
        ('Session.Dialog.cs', 'private void SendMiniText(string text, ushort type = 3)', 'P4Message = text;'),
        ('Session.Shop.cs', 'private void SendBuyGrid(Mob npc, string prompt, IReadOnlyList<GridRow> rows)',
         'P4Show(new P4Window { kind = "buy", npc = npc.Id, text = prompt, names = rows.Select(r => r.Name).ToArray(), prices = rows.Select(r => r.Number).ToArray() });'),
        ('Session.Shop.cs', 'private void SendSellGrid(Mob npc, string prompt, IReadOnlyList<byte> slots)',
         'P4Show(new P4Window { kind = "sell", npc = npc.Id, text = prompt, slots = slots.Select(s => (int)s).ToArray(), names = slots.Select(s => { var i = _char.Inventory.FirstOrDefault(i => i.Slot == s - 1); return i is null ? "?" : Content.ItemById(i.ItemId)!.Name + " x" + i.Amount; }).ToArray() });'),
        ('Session.Shop.cs', 'private void SendAmountPrompt(Mob npc, string prompt, string itemName, int max)',
         'P4Show(new P4Window { kind = "amount", npc = npc.Id, text = prompt, names = new[] { itemName }, max = max });'),
    ]
    for file, signature, hook in hooks:
        start = '    ' + signature + '\n    {'
        patch(file, start, start + '\n        // P4 presentation transport observes this original outgoing window.\n        ' + hook, 'observe outgoing UI only; original body retained verbatim')
    (out / 'P4_SOURCE_AUDIT.json').write_text(json.dumps({'original_head': HEAD, 'bounded_content': audit,
        'private_source_changes': patches, 'additional_host_code_sha256': sha(HERE / 'Adapter.cs'),
        'capsule_sha256': sha(runtime / 'capsule.json'), 'p3_save_policy': 'separate untouched user://p3; P4 uses user://p4/v1',
        'rules': 'Original handlers, Combat, ItemVerb/SpellVerb and Lua quest files execute unchanged'}, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'maps': list(MAPS), 'capsule': sha(runtime / 'capsule.json')}))


if __name__ == '__main__': main()
