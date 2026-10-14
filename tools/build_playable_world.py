#!/usr/bin/env python3
"""Author offline maps with unique original tiles; no claim of historic map identity."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    maps = []
    used = {}

    def make(mid, name, kind, seed, floor, enemies, recommended):
        rng = random.Random(seed)
        w, h = 40, 28
        grid = [[rng.choice(floor) for _ in range(w)] for _ in range(h)]
        blocked = [[False] * w for _ in range(h)]
        deco = []
        for y in range(h):
            for x in range(w):
                if x in (0, w-1) or y in (0, h-1):
                    grid[y][x] = 'B:720' if kind == 'dungeon' else 'A:246' if kind == 'interior' else 'A:80'
                    blocked[y][x] = True
                if kind == 'village' and (10 <= x <= 14 or y == 12):
                    grid[y][x] = ['A:97', 'A:98', 'A:99'][(x+y) % 3]
                if kind == 'dungeon' and x in (8, 22, 31) and y not in (7, 12, 20):
                    grid[y][x] = ['B:650','B:651','B:652'][(x+y) % 3]
                    blocked[y][x] = True
        if kind == 'village':
            for bx, by in [(2, 4), (20, 4), (24, 17)]:
                roof = [list(range(0,9)), [16,17,18,19,20,21,22,22,23],
                        [28,29,30,31,32,33,34,34,35], [51,52,52,52,52,52,52,52,53],
                        [51,52,52,88,89,90,91,52,53]]
                for dy, row in enumerate(roof):
                    for dx, tile in enumerate(row):
                        deco.append(dict(x=bx+dx,y=by+dy,tile=f'C:{tile}'))
                        blocked[by+dy][bx+dx] = True
                blocked[by+4][bx+4] = False
        elif kind == 'interior':
            for x in range(3, 37):
                deco.append(dict(x=x, y=3, tile=f'C:{172+x%4}'))
                blocked[3][x] = True
            for y in range(5, 10):
                for x in range(24, 29):
                    grid[y][x] = f'A:{472+(x+y)%6}'
        else:
            # Rivers and branching crossings make authored collision visible.
            if kind == 'field':
                for y in range(1,h-1):
                    if y not in (10,11,12):
                        for x in (28,29):
                            grid[y][x] = ['B:96','B:97','B:98'][(x+y)%3]
                            blocked[y][x] = True
                for x in range(27,31):
                    for y in (10,11,12): grid[y][x]='A:268' if y%2 else 'A:269'
            for x,y in [(4,5),(21,6),(5,20),(34,18)]:
                for k in range(3):
                    deco.append(dict(x=x+k,y=y,tile=f'C:{105+k}'))
                    blocked[y][x+k]=True
        spawns=[]
        for i, enemy in enumerate(enemies):
            x,y = (13+i%5*3, 12+i//5*4)
            if blocked[y][x]: x,y=16,12
            spawns.append(dict(id=f'{mid}-{i}', kind=enemy, x=x,y=y))
        m=dict(id=mid,name=name,kind=kind,width=w,height=h,ground=grid,blocked=blocked,
               decorations=deco,portals=[],npcs=[],spawns=spawns,recommended_level=recommended,
               source_kind='GENERATED_LAYOUT_WITH_ORIGINAL_UNDATED_TILES', historic_identity='UNVERIFIED',
               layout_seed=seed,entry=[12,12])
        maps.append(m)
        return m

    town=make('village','부여 초보마을 · 복원 배치','village',1998,[f'A:{i}' for i in range(16,21)],[],[1,5])
    field=make('field','남쪽 초보 사냥터','field',1999,[f'A:{i}' for i in range(0,21)],
               ['rabbit','rabbit','squirrel','squirrel','rabbit','squirrel','rabbit','squirrel'],[1,5])
    inn=make('inn','주막','interior',2000,[f'A:{i}' for i in range(448,467)],[],[1,99])
    guild=make('guild','직업 수련원','interior',2001,[f'A:{i}' for i in range(312,320)],[],[5,30])
    cave=make('cave','쥐굴','dungeon',4,[f'B:{i}' for i in range(624,636)],['rat']*6+['bat']*2,[5,15])
    forest=make('forest','숲과 뱀굴 입구','field',5,[f'A:{i}' for i in range(174,180)],['snake']*4+['boar']*4,[15,25])
    deep=make('deep','깊은 동굴','dungeon',6,[f'A:{i}' for i in range(424,436)],['spider']*4+['skeleton']*4,[20,30])
    ruins=make('ruins','폐허 · 초보 여정 마지막 구간','dungeon',7,[f'A:{i}' for i in range(312,332)],['skeleton']*6+['spider']*2,[25,30])

    def portal(a, x, y, b, tx,ty, label):
        a['blocked'][y][x]=False
        a['portals'].append(dict(x=x,y=y,target=b['id'],entry=[tx,ty],label=label))
        a['ground'][y][x]='A:268'
    portal(town,15,12,field,12,12,'남쪽 사냥터');portal(field,11,12,town,14,12,'초보마을')
    portal(town,6,8,inn,12,12,'주막');portal(inn,11,12,town,6,9,'마을')
    portal(town,24,8,guild,12,12,'수련원');portal(guild,11,12,town,24,9,'마을')
    portal(field,22,12,cave,12,12,'쥐굴');portal(cave,11,12,field,21,12,'사냥터')
    portal(field,35,12,forest,12,12,'숲');portal(forest,11,12,field,34,12,'사냥터')
    portal(cave,35,12,deep,12,12,'깊은 동굴');portal(deep,11,12,cave,34,12,'쥐굴')
    portal(deep,35,12,ruins,12,12,'폐허');portal(ruins,11,12,deep,34,12,'깊은 동굴')
    town['npcs']=[dict(id='merchant',kind='merchant',x=12,y=11,name='장비상',role='shop'),
                  dict(id='teacher',kind='teacher',x=12,y=9,name='초보 안내인',role='quest'),
                  dict(id='priest',kind='priest',x=18,y=12,name='성황',role='revive')]
    inn['npcs']=[dict(id='innkeeper',kind='innkeeper',x=12,y=10,name='주모',role='inn')]
    guild['npcs']=[dict(id='trainer',kind='teacher',x=12,y=10,name='직업 사범',role='trainer')]
    for m in maps:
        for row in m['ground']:
            for tile in row:used[tile]=used.get(tile,0)+1
        for d in m['decorations']:used[d['tile']]=used.get(d['tile'],0)+1
        for n in m['npcs']:m['blocked'][n['y']][n['x']]=True
    output=ROOT/'game/data/world.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(maps=maps,shop_items=['목도','목검','철단도','철검','도토리','토끼고기','산삼'],
        generated_map_count=len(maps), tile_placements=sum(used.values()),unique_tile_ids=len(used),
        replacements={'rat':'병든쥐','bat':'박쥐','snake':'독사','boar':'곰','spider':'서생원','skeleton':'보라박쥐'},
        generated_quests=[dict(id='first_steps',kills=5,xp=300,gold=50),dict(id='hunter',kills=25,xp=1200,gold=100)],
        numeric_overrides={'starter_hp':50,'starter_mp':35,'starter_strength':5,'starter_gold':30,
                           'strength_per_level':1,'attack_interval_ms':600,'impact_ms':160,
                           'walk_interval_ms':180,'advanced_monster_gold':20},
        override_classification='DEV_ESTIMATE_GAME_COMPLETION_NOT_KR_CONFIRMED'),ensure_ascii=False,separators=(',',':'))+'\n')
    report=ROOT/'docs/development/runs/20261014-assets/world-build.json'
    report.write_text(json.dumps(dict(maps=[{k:m[k] for k in ['id','name','kind','recommended_level','source_kind']} for m in maps],
        tile_placements=sum(used.values()),unique_tile_ids=len(used),usage=used),ensure_ascii=False,indent=2)+'\n')
    print('AUTHORED_MAPS',len(maps),'TILE_PLACEMENTS',sum(used.values()),'UNIQUE_IDS',len(used))


if __name__=='__main__':build()
