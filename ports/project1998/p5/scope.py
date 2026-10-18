"""The first P5 region: source Kugnae commerce, four paths, Rat/Earth caves.

Scope is explicit. Loading a row or compiling a map does not mark it playable.
"""
import csv
from collections import defaultdict

LEGACY_MAPS = (4711, 4712, 4713, 4714, 4715, 4716, 4717, 4718, 36, 0, 2)
MAPS = LEGACY_MAPS + (3, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18,
                     28, 29, 37, 38, 43) + tuple(range(50, 64)) + tuple(range(3701, 3705))
DEFERRED_MOBS = {'542', '543', '544', '545'}  # harvesting nodes require absent 4.95 art 773/774/822
EXCLUDED_NPCS = {'F1Npc', 'TreasurePortalNpc'}  # off-screen/system NPC, not world actors


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(line for line in stream if line.strip() and not line.lstrip().startswith('#')))


def roster(source, legacy=False):
    """Mirror only the roster ORDER, never spawn/combat rules.

    This maps old saved indices onto the expanded source roster. Original
    Spawns rows then non-timed AreaSpawns members form each map's point list.
    Timed AreaSpawns form groups in first-seen Group order.
    """
    maps = LEGACY_MAPS if legacy else MAPS
    points, groups = defaultdict(list), defaultdict(list)
    for row in rows(source / 'Spawns.csv'):
        if int(row['SpnMapId']) in maps and row['SpnMobId'] not in DEFERRED_MOBS and (not legacy or row['SpnMobId'] in {'1', '2'}):
            points[int(row['SpnMapId'])].append('spawn:' + row['SpnId'])
    for index, row in enumerate(rows(source / 'AreaSpawns.csv')):
        mid = int(row['Map'])
        if mid not in maps or row['MobId'] in DEFERRED_MOBS or (legacy and row['MobId'] not in {'1', '2'}): continue
        if int(row['Timer'] or 0) > 0:
            key = 'group:' + row['Group']
            if key not in groups[mid]: groups[mid].append(key)
        else:
            points[mid].extend(f'area:{index}:{i}' for i in range(int(row['Count'])))
    return points, groups
