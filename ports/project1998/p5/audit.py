#!/usr/bin/env python3
"""Source keys, finite denominator, and source-boundary audit (not play proof)."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from scope import MAPS, DEFERRED_MOBS, EXCLUDED_NPCS, rows


def main():
    p=argparse.ArgumentParser()
    for k in ['source','experiment','converted','output']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();src=a.source.resolve();data=src/'game-data';content=a.experiment/'content'
    assets=json.loads((a.converted/'assets.json').read_text());idx={int(r['id']):r for r in rows(data/'map_index.csv')}
    checks=[]
    def check(name,ok):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})
        if not ok:print('FAIL',name)
    def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    check('47 explicit unique map IDs',len(MAPS)==len(set(MAPS))==47)
    check('map raw bytes, dimensions and hashes',all((content/f'maps/TK{mid}.map').read_bytes()==(data/f'maps/TK{mid}.map').read_bytes() and (content/f'maps/TK{mid}.map').stat().st_size==int(idx[mid]['xs'])*int(idx[mid]['ys'])*4 for mid in MAPS))
    warps=rows(content/'Warps.csv');original=[r for r in rows(data/'Warps.csv') if int(r['SourceMapId']) in MAPS]
    check('all source warp rows preserved including boundaries',warps==original)
    boundaries=[r for r in warps if int(r['DestinationMapId']) not in MAPS]
    internal=[r for r in warps if int(r['DestinationMapId']) in MAPS]
    warp_faults=[]
    for r in internal:
        for prefix in ['Source','Destination']:
            dim=idx[int(r[prefix+'MapId'])]
            if not(0<=int(r[prefix+'X'])<int(dim['xs']) and 0<=int(r[prefix+'Y'])<int(dim['ys'])):warp_faults.append(r)
    check('expanded map exits in bounds',not [r for r in warp_faults if r['SourceMapId']!='4711'])
    duplicates=[list(k) for k,n in Counter((r['SourceMapId'],r['SourceX'],r['SourceY']) for r in warps).items() if n>1]
    check('expanded map exit tiles unique',all(k==['4711','9','16'] for k in duplicates))
    npc=rows(content/'NPCs.csv');native_npc=[r for r in rows(data/'NPCs.csv') if int(r['NpcMapId']) in MAPS and r['NpcIdentifier'] not in EXCLUDED_NPCS]
    check('source NPC placements preserved',npc==native_npc)
    check('NPC coordinates in source maps',all(0<=int(r['NpcX'])<int(idx[int(r['NpcMapId'])]['xs']) and 0<=int(r['NpcY'])<int(idx[int(r['NpcMapId'])]['ys']) for r in npc))
    mobs={r['MobId']:r for r in rows(content/'mobs.csv')};items={r['ItmIdentifier']:r for r in rows(content/'Items.csv')}
    spawns=rows(content/'Spawns.csv');areas=rows(content/'AreaSpawns.csv')
    check('spawns reference existing definitions/maps',all(r['SpnMobId'] in mobs and int(r['SpnMapId']) in MAPS for r in spawns) and all(r['MobId'] in mobs and int(r['Map']) in MAPS for r in areas))
    check('timed group caps positive',all(int(r['Count'])>0 and int(r['Timer'])>=0 for r in areas))
    keys={r['NpcIdentifier'] for r in npc};shops=[r for r in rows(content/'ShopStock.csv') if r['NpcIdentifier'] in keys]
    shop_keys={k for r in shops for k in r['ItemKeys'].split('|') if k and k!='-'}
    buy_keys={k for r in rows(content/'ShopBuysFrom.csv') if r['NpcIdentifier'] in keys for k in r['ItemKeys'].split('|') if k and k!='-'}
    check('regional merchant goods resolve original item keys',all(k in items for k in shop_keys|buy_keys))
    for f in ['Items.csv','Spells.csv','SpellParams.csv','SpellLearnCosts.csv','spell_effects.csv','ShopStock.csv','ShopBuysFrom.csv','ShopCatalogues.csv','item_verbs.lua','spell_verbs.lua','npc_dialog.lua','mob_ai.lua']:
        check('unchanged '+f,digest(data/f)==digest(content/f))
    source_spatial_deferred=[r for r in rows(data/'Spawns.csv') if int(r['SpnMapId']) in MAPS and r['SpnMobId'] in DEFERRED_MOBS]
    # A gap is retained as a gap, not re-labelled as rendered/playable.
    icon_gaps=sorted(k for k in shop_keys|buy_keys if k not in assets['item_icons'])
    native_totals={f:len(rows(data/f)) for f in ['map_index.csv','Maps.csv','Warps.csv','NPCs.csv','mobs.csv','Items.csv','Spells.csv']}
    result={'status':'PASS_AUDIT_SCOPE' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,
        'source_head':'65cb3ef28f289ee35d19abfb6829d6120b9ec0cd','denominator':native_totals,
        'included':{'maps':len(MAPS),'npc_placements':len(npc),'mob_definitions_loaded':len(mobs),'spawned_mob_types':len({r['SpnMobId'] for r in spawns}|{r['MobId'] for r in areas}),'fixed_spawns':len(spawns),'area_rows':len(areas),'internal_warp_rows':len(internal),'boundary_warp_rows':len(boundaries),'regional_shop_keys':len(shops),'source_item_icons':len(assets['item_icons'])},
        'region_boundaries':boundaries,'deferred':{'harvesting_node_definitions':sorted(DEFERRED_MOBS),'fixed_spawn_rows':len(source_spatial_deferred),'reason':'Original 4.95 Monster.tbl has no looks 773,774,822. No substituted art. Harvesting remains outside this P5 increment.','merchant_icon_gaps':icon_gaps},
        'source_data_status':'FAIL_SOURCE_3_UNREACHABLE_ROWS' if warp_faults else 'PASS', 'known_source_warp_faults':warp_faults,'duplicates':duplicates,'playable_count':'NOT_INFERRED_FROM_PARSE_OR_CONVERSION; see native traversal and GUI evidence','native_android':'NOT_RUN_DEVICE_P5'}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','included','deferred']}));assert result['status']!='FAIL'
if __name__=='__main__':main()
