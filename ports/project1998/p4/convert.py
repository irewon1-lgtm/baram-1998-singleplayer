#!/usr/bin/env python3
"""Extend the verified P1 compiler for one original P4 route and its actors."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
from PIL import Image

HERE = Path(__file__).resolve().parent
MAPS = (4711, 4712, 4713, 4714, 4715, 4716, 4717, 4718, 36, 0, 2)
NPCS = {'WoodlandSmithNpc', 'WoodlandArmorerNpc', 'TutorialNpc1', 'TutorialNpc2',
        'MignokNpc', 'WoodlandGuardNpc', 'WoodlandAngelNpc', 'MainTutorialNpc', 'InnNpc'}


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
    mobs = [m for m in p1.csv_rows(source / 'game-data/mobs.csv') if m['Identifier'] in {'rabbit', 'squirrel'}]
    npcs = [n for n in p1.csv_rows(source / 'game-data/NPCs.csv')
            if n['NpcIdentifier'] in NPCS and int(n['NpcMapId']) in MAPS]
    assert len(npcs) == len(NPCS) and len({n['NpcIdentifier'] for n in npcs}) == len(NPCS)
    bindings = [('mob:' + m['Identifier'], int(m['MobLook']), int(m['MobLookColor'])) for m in mobs]
    bindings += [('npc:' + n['NpcIdentifier'], int(n['NpcLook']), int(n['NpcLookColor'])) for n in npcs]
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
    wanted = {'apple', 'wine', 'rabbit_meat', 'acorn', 'gold_acorn', 'wooden_saber', 'spring_garb', 'novice_sword',
              'comb', 'rice_wine', 'root_liquor', 'soup_bowl', 'thick_wine', 'yellow_scroll'}
    icons = {}
    for item in p1.csv_rows(source / 'game-data/Items.csv'):
        if item['ItmIdentifier'] not in wanted: continue
        # ClientIcon is the source icon plus its palette variant in 4.95.
        icon = int(item.get('ItmIcon', '0') or 0)
        color = int(item.get('ItmIconColor', '0') or 0)
        if icon in {89, 99, 120, 149, 159, 180, 265, 450}: icon += color
        color = 0  # 4.95 resolves the selected icon frame; no per-icon dye channel.
        if icon < item_epf.count:
            palette = item_table.get(icon, {}).get('Palette', 0)
            key = 'item:' + item['ItmIdentifier']; atlas.add(key, item_epf.decode(icon, item_pals[palette], color))
            icons[item['ItmIdentifier']] = {'key': key, 'frame': icon, 'palette': palette, 'dye': color}
    # P4's original equipment art. Human poses retain the verified P1 body/head
    # mapping; Sword.tbl uses twelve hold/walk and eight swing frames per art.
    body_epf = p1.Epf(legacy['BODY.EPF']); head_epf = p1.Epf(legacy['HEAD.EPF'])
    body_pal = p1.palettes(legacy['BODY.PAL']); head_pal = p1.palettes(legacy['HEAD.PAL'])
    body_row = p1.table(legacy['BODY.TBL'])[3]; head_row = p1.table(legacy['HEAD.TBL'])[0]
    sword_epf = p1.Epf(legacy['SWORD.EPF']); sword_pal = p1.palettes(legacy['SWORD.PAL']); swords = p1.table(legacy['SWORD.TBL'])
    for direction in range(4):
        for action, count in [('idle', 1), ('walk', 3), ('attack', 2)]:
            armor_sequence = []; weapon_sequences = {0: [], 1: []}
            for tick in range(count):
                relative = direction * 3 + tick if action != 'attack' else 24 + direction * 2 + tick
                parts = [body_epf.decode(body_row['Starting'] + relative, body_pal[body_row['Palette']]),
                         head_epf.decode(head_row['Starting'] + relative, head_pal[head_row['Palette']])]
                union = [min(p[1][0] for p in parts), min(p[1][1] for p in parts),
                         max(p[1][0] + p[0].width for p in parts), max(p[1][1] + p[0].height for p in parts)]
                composite = Image.new('RGBA', (union[2] - union[0], union[3] - union[1]))
                for image, offset in parts: composite.alpha_composite(image, (offset[0] - union[0], offset[1] - union[1]))
                key = f'armor:3-{action}-{direction}-{tick}'; atlas.add(key, (composite, union[:2])); armor_sequence.append({'key': key})
                for look in [0, 1]:
                    row = swords[look]; relative_weapon = direction * 3 + tick if action != 'attack' else 12 + direction * 2 + tick
                    key = f'weapon:{look}-{action}-{direction}-{tick}'
                    atlas.add(key, sword_epf.decode(row['Starting'] + relative_weapon, sword_pal[row['Palette']]))
                    weapon_sequences[look].append({'key': key, 'source_frame': row['Starting'] + relative_weapon})
            assets['animations'][f'armor:3-{action}-{direction}'] = armor_sequence
            for look in [0, 1]: assets['animations'][f'weapon:{look}-{action}-{direction}'] = weapon_sequences[look]
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
    assets['p4_actor_sources'] = provenance; assets['item_icons'] = icons
    aliases = {4711: '시작 들판', 4712: '열린 들판', 4713: '숲길', 4714: '깊은 숲', 4715: '시골 농장',
               4716: '미그녹의 집', 4717: '도시 경계', 4718: '천사의 뜰', 36: '아이언하트의 집', 0: '국내성', 2: '주막'}
    for m in assets['maps']: m['name_ko'] = aliases[m['id']]
    p1.save_json(out / 'assets.json', assets)
    files = [{'path': str(p.relative_to(out)), 'size': p.stat().st_size, 'sha256': p1.sha(p.read_bytes())}
             for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'BUILD_ASSETS_MANIFEST.json']
    p1.save_json(out / 'BUILD_ASSETS_MANIFEST.json', {'files': files, 'source_inputs': p1.PINS,
                  'p4_actor_sources': provenance, 'scope': 'one original newbie route, not the full world'})
    print(json.dumps({'p4_maps': list(MAPS), 'actor_sources': len(provenance), 'item_icons': len(icons)}))


if __name__ == '__main__': main()
