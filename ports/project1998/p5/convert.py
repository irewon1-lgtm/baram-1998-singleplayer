#!/usr/bin/env python3
"""Extend the verified P1 compiler for one original P4 route and its actors."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
from PIL import Image

HERE = Path(__file__).resolve().parent
from scope import MAPS, EXCLUDED_NPCS, DEFERRED_MOBS, rows


def main():
    spec = importlib.util.spec_from_file_location('p1_compiler', HERE.parent / 'scripts/convert.py')
    p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
    p1.MAP_IDS = MAPS
    arguments = sys.argv[1:]
    source = Path(arguments[arguments.index('--source') + 1]).resolve()
    originals = Path(arguments[arguments.index('--originals') + 1]).resolve()
    out = Path(arguments[arguments.index('--output') + 1]).resolve()
    p1.main()
    assets = json.loads((out / 'assets.json').read_text())
    atlas = p1.Atlas(); old = Image.open(out / 'actors.png').convert('RGBA')
    for key, entry in assets['actor_regions'].items():
        x, y, w, h = entry['rect']; atlas.add(key, (old.crop((x, y, x + w, y + h)), entry['offset']))
    legacy = p1.dat_entries((originals / '4x/NexusTK.dat').read_bytes())
    epf = p1.Epf(legacy['MONSTER.EPF']); pals = p1.palettes(legacy['MONSTER.PAL']); table = p1.table(legacy['MONSTER.TBL'])
    spawn_ids = {r['SpnMobId'] for r in rows(source / 'game-data/Spawns.csv') if int(r['SpnMapId']) in MAPS}
    spawn_ids |= {r['MobId'] for r in rows(source / 'game-data/AreaSpawns.csv') if int(r['Map']) in MAPS}
    mobs = [m for m in rows(source / 'game-data/mobs.csv') if m['MobId'] in spawn_ids and m['MobId'] not in DEFERRED_MOBS]
    npcs = [n for n in rows(source / 'game-data/NPCs.csv')
            if n['NpcIdentifier'] not in EXCLUDED_NPCS and int(n['NpcMapId']) in MAPS]
    bindings = [('mob:' + m['Identifier'], int(m['MobLook']), int(m['MobLookColor'])) for m in mobs]
    # Placements may share a script identifier while using different art/dye.
    bindings += [('npc:' + n['NpcId'], int(n['NpcLook']), int(n['NpcLookColor'])) for n in npcs]
    provenance = []
    for prefix, look, dye in bindings:
        row = table[look]
        for direction in range(4):
            sequence = []
            for tick in range(max(1, row['Walk'])):
                index = row['Starting'] + direction * row['Walk'] + tick
                key = prefix + '-' + str(direction) + '-' + str(tick)
                atlas.add(key, epf.decode(index, pals[row['Palette']], dye))
                sequence.append({'key': key, 'source_frame': index})
            assets['animations'][prefix + '-' + str(direction)] = sequence
        provenance.append({'key': prefix, 'look': look, 'dye': dye, 'table': row})
    # Inventory/floor icons are source Item.epf frames, not replacement drawings.
    item_epf = p1.Epf(legacy['ITEM.EPF']); item_pals = p1.palettes(legacy['ITEM.PAL'])
    item_table = {}
    # Item.tbl also carries decimal fields. Only the integer ID/palette columns
    # belong to raster selection; the human/monster table parser is narrower.
    if 'ITEM.TBL' in legacy:
        for line in legacy['ITEM.TBL'].decode('ascii').splitlines():
            if not line.startswith('ID '): continue
            fields = {}
            for part in line.strip().strip(',').split(', '):
                key, value = part.rsplit(' ', 1)
                if key in ['ID', 'Palette']: fields[key] = int(value)
            item_table[fields['ID']] = fields
    icons = {}; icon_frames = set()
    for item in p1.csv_rows(source / 'game-data/Items.csv'):
        # ClientIcon is the source icon plus its palette variant in 4.95.
        icon = int(item.get('ItmIcon', '0') or 0)
        color = int(item.get('ItmIconColor', '0') or 0)
        if icon in {89, 99, 120, 149, 159, 180, 265, 450}: icon += color
        color = 0  # 4.95 resolves the selected icon frame; no per-icon dye channel.
        if icon < item_epf.count:
            palette = item_table.get(icon, {}).get('Palette', 0)
            key = 'item-frame:' + str(icon)
            if key not in icon_frames:
                atlas.add(key, item_epf.decode(icon, item_pals[palette], color)); icon_frames.add(key)
            icons[item['ItmIdentifier']] = {'key': key, 'frame': icon, 'palette': palette, 'dye': color}
    assets['ground_icons'] = {}
    for icon in [22, 72, 73]:
        key = 'item-frame:' + str(icon)
        if key not in icon_frames:
            palette = item_table.get(icon, {}).get('Palette', 0)
            atlas.add(key, item_epf.decode(icon, item_pals[palette])); icon_frames.add(key)
        assets['ground_icons'][str(icon)] = key
    # Same wire look/family/dye relation as Session.Entity.cs. This region's
    # merchant goods and the four original starter kits define the gear set.
    npc_keys = {n['NpcIdentifier'] for n in npcs}
    gear_keys = set('sword_of_power swift_dagger staff_of_power staff_of_defense jade_scale_mail summer_mail_dress merchant_waistcoat summer_blouse summer_garb summer_dress summer_robes summer_gown merchant_helm spring_helmet wooden_saber spring_garb novice_sword'.split())
    for row in rows(source / 'game-data/ShopStock.csv'):
        if row['NpcIdentifier'] in npc_keys: gear_keys.update(row['ItemKeys'].split('|'))
    regional = [r for r in rows(source / 'game-data/Items.csv') if r['ItmIdentifier'] in gear_keys]
    body_epf = p1.Epf(legacy['BODY.EPF']); head_epf = p1.Epf(legacy['HEAD.EPF'])
    body_pals = p1.palettes(legacy['BODY.PAL']); head_pals = p1.palettes(legacy['HEAD.PAL'])
    body_table = p1.table(legacy['BODY.TBL']); head_table = p1.table(legacy['HEAD.TBL'])
    armor_pairs = {(int(r['ItmLook']) if 0 <= int(r['ItmLook']) <= 66 else 0, int(r['ItmLookColor']))
                   for r in regional if r['ItmType'] == '4'} | {(0, 0), (2, 0), (3, 0)}
    for look, dye in sorted(armor_pairs):
        row = body_table[look]; head = head_table[0]
        for direction in range(4):
            for action, count in [('idle', 1), ('walk', 3), ('attack', 2)]:
                sequence = []
                for tick in range(count):
                    relative = direction * 3 + tick if action != 'attack' else 24 + direction * 2 + tick
                    parts = [body_epf.decode(row['Starting'] + relative, body_pals[row['Palette']], dye),
                             head_epf.decode(head['Starting'] + relative, head_pals[head['Palette']])]
                    parts = [part for part in parts if part is not None]
                    union = [min(p[1][0] for p in parts), min(p[1][1] for p in parts),
                             max(p[1][0] + p[0].width for p in parts), max(p[1][1] + p[0].height for p in parts)]
                    composite = Image.new('RGBA', (union[2] - union[0], union[3] - union[1]))
                    for image, offset in parts: composite.alpha_composite(image, (offset[0] - union[0], offset[1] - union[1]))
                    key = f'armor:{look}:{dye}-{action}-{direction}-{tick}'
                    atlas.add(key, (composite, union[:2])); sequence.append({'key': key})
                assets['animations'][f'armor:{look}:{dye}-{action}-{direction}'] = sequence
    weapons = {(int(r['ItmLook']), int(r['ItmLookColor'])) for r in regional if r['ItmType'] == '3'}
    assets['equipment_sources'] = []
    for look, dye in sorted(weapons):
        family, art = divmod(look, 10000)
        if family == 2:  # original 4.95 has no bow raster; do not invent one
            assets['equipment_sources'].append({'look': look, 'dye': dye, 'empty_in_original_4x': True}); continue
        name = {0: 'SWORD', 1: 'SPEAR'}.get(family, 'FAN')
        table = p1.table(legacy[name + '.TBL']); art = art if art in table else 0; row = table[art]
        epf = p1.Epf(legacy[name + '.EPF']); pals = p1.palettes(legacy[name + '.PAL'])
        for direction in range(4):
            for action, count in [('idle', 1), ('walk', 3), ('attack', 2)]:
                sequence = []
                for tick in range(count):
                    relative = direction * 3 + tick if action != 'attack' else 12 + direction * 2 + tick
                    index = row['Starting'] + relative; key = f'weapon:{look}:{dye}-{action}-{direction}-{tick}'
                    atlas.add(key, epf.decode(index, pals[row['Palette']], dye)); sequence.append({'key': key, 'source_frame': index})
                assets['animations'][f'weapon:{look}:{dye}-{action}-{direction}'] = sequence
        assets['equipment_sources'].append({'look': look, 'dye': dye, 'member': name + '.EPF', 'table_id': art})
    assets['actor_regions'] = atlas.write(out / 'actors.png')
    # Doors change SObj IDs at runtime. Include both original gate states even
    # when an open-state column does not occur in the raw map file.
    tiles = p1.dat_entries((originals / '533/Tile.dat').read_bytes())
    columns, _ = p1.sobj(tiles['SOBJ.TBL']); _, flags = p1.sobj(legacy['SOBJ.TBL'])
    frames = p1.Epf(tiles['TILEC.EPF']); palettes = p1.palettes(tiles['TILEC.PAL'])
    import numpy as np
    palette_ids = np.frombuffer(tiles['TILEC.TBL'], np.uint8, frames.count * 2, 4)[::2]
    object_atlas = p1.Atlas(); old_objects = Image.open(out / 'objects.png').convert('RGBA')
    for key, entry in assets['object_frames'].items():
        x, y, w, h = entry['rect']
        object_atlas.add(key, None if not w or not h else
                         (old_objects.crop((x, y, x + w, y + h)), entry['offset']))
    known = set(assets['object_frames'])
    for oid in [5, 6, 7, 8, 15, 16, 17, 18]:
        assets['objects'][str(oid)] = {'frames': columns[oid], 'collision_flags_4x': flags[oid]}
        for fid in columns[oid]:
            if fid and str(fid) not in known:
                object_atlas.add(str(fid), frames.decode(fid, palettes[int(palette_ids[fid])]))
                known.add(str(fid))
    assets['object_frames'] = object_atlas.write(out / 'objects.png')
    assets['p5_actor_sources'] = provenance; assets['item_icons'] = icons
    aliases = {4711: '시작 들판', 4712: '열린 들판', 4713: '숲길', 4714: '깊은 숲', 4715: '시골 농장',
               4716: '미그녹의 집', 4717: '도시 경계', 4718: '천사의 뜰', 36: '아이언하트의 집', 0: '국내성', 2: '주막'}
    for m in assets['maps']: m['name_ko'] = aliases.get(m['id'], m['name_ko'].replace("\\'", "'"))
    by_map = {m['id']: m for m in assets['maps']}
    for row in rows(source / 'game-data/PathHalls.csv'):
        mid = int(row['HallMap'])
        if mid in by_map:
            by_map[mid]['scripted_exits'] = [
                {'SourceX': 8, 'SourceY': 1, 'DestinationMapId': int(row['SanctumUnaligned']), 'kind': 'unaligned-sanctum'},
                {'SourceX': 1, 'SourceY': 23, 'DestinationMapId': int(row['GuildMap']), 'kind': 'class-guild', 'path': int(row['BaseClass'])}]
    p1.save_json(out / 'assets.json', assets)
    files = [{'path': str(p.relative_to(out)), 'size': p.stat().st_size, 'sha256': p1.sha(p.read_bytes())}
             for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'BUILD_ASSETS_MANIFEST.json']
    p1.save_json(out / 'BUILD_ASSETS_MANIFEST.json', {'files': files, 'source_inputs': p1.PINS,
                  'p5_actor_sources': provenance, 'scope': 'P5 Kugnae commerce, four class halls, Rat/Earth caves; not full world'})
    print(json.dumps({'p5_maps': list(MAPS), 'actor_sources': len(provenance), 'item_icons': len(icons)}))


if __name__ == '__main__': main()
