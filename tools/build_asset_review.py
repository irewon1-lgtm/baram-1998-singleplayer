#!/usr/bin/env python3
"""Generate all tile contact pages, source namespaces, classifications and use positions."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from legacy_assets import private_path

ROOT=Path(__file__).resolve().parents[1]
MANUAL={}


def classify(group, start, end, label):
    for i in range(start,end+1):MANUAL[f'{group}:{i}']=label


for params in [('A',0,20,'GRASS'),('A',80,80,'VEGETATED_BORDER'),('A',97,99,'DIRT_PATH'),
    ('A',174,179,'GRASS_PATH_EDGE'),('A',246,246,'STONE_BORDER'),('A',268,269,'BRICK_STAIRS'),
    ('A',312,331,'STONE_FLOOR_EDGE'),('A',424,435,'CAVE_GROUND'),('A',448,466,'WOOD_FLOOR'),
    ('A',472,477,'CARPET'),('B',96,98,'WATER'),('B',624,635,'CAVE_EARTH'),
    ('B',650,652,'CAVE_WALL'),('B',720,720,'ROCK_BORDER'),('C',0,8,'ROOF'),
    ('C',16,23,'ROOF'),('C',28,35,'ROOF'),('C',51,53,'WALL'),('C',88,91,'DOOR'),
    ('C',105,107,'STONE_WALL'),('C',172,175,'WINDOW_WALL')]:classify(*params)


def build(a):
    private=private_path(a.assets)
    folder=private/'review'
    folder.mkdir(exist_ok=True)
    ledger=json.loads(Path(a.ledger).read_text())
    manifest=json.loads((private/'tiles/MANIFEST.json').read_text())
    groups={g['group']:g for g in manifest['groups']}
    pages=[]
    for group in 'ABC':
        atlas=Image.open(private/f'tiles/Tile{group}_palette0_atlas.png').convert('RGBA')
        table=json.loads((private/f'tiles/Tile{group}_frame_map.json').read_text())
        for first in range(0,len(table['frames']),256):
            last=min(first+256,len(table['frames']))
            name=f'{group}-{first//256:02d}.png'
            sheet=Image.new('RGB',(832,1056),(30,34,40));draw=ImageDraw.Draw(sheet)
            for j,i in enumerate(range(first,last)):
                f=table['frames'][i]
                tile=atlas.crop((f['x'],f['y'],f['x']+24,f['y']+24)).resize((48,48),Image.Resampling.NEAREST)
                x,y=j%16*52,j//16*66
                sheet.paste(tile,(x,y),tile);draw.text((x,y+48),f'{group}:{i}',fill='white')
            sheet.save(folder/name)
            reviewed=(group in 'AC' and first in (0,256)) or (group=='B' and first in (0,512))
            pages.append({'group':group,'page':first//256,'first':first,'last':last-1,'frames':last-first,
                'path':'review/'+name,'sha256':hashlib.sha256((folder/name).read_bytes()).hexdigest(),
                'image_decode':'PASS','visual_review':'PREVIOUS_IDENTICAL_SOURCE_RANGE_REVIEWED' if reviewed else 'NOT_REVIEWED'})
    for f in ledger['frames']:
        f['canonical_asset_id']=f"uploaded-editor-undated/palette0/{f['group']}/{f['index']}"
        f['legacy_runtime_alias']=f['asset_id']
        f['source_epf_sha256']=groups[f['group']]['source_epf_sha256']
        f['source_palette_sha256']=groups[f['group']]['source_pal_sha256']
        f['contact_page']=f"review/{f['group']}-{f['index']//256:02d}.png"
        f['contact_cell']=[f['index']%16, f['index']%256//16]
        f['semantic_classification']=MANUAL.get(f['asset_id'],'UNKNOWN')
        f['classification_basis']='CONTACT_SHEET_AND_MAP_USE' if f['asset_id'] in MANUAL else 'NOT_CONFIRMED'
        f['classification_confidence']=0.8 if f['asset_id'] in MANUAL else 0.0
        f['collision_policy']='EXPLICIT_PER_SCENE_GRID_NOT_INFERRED_FROM_TILE_ID'
    Path(a.ledger).write_text(json.dumps(ledger,ensure_ascii=False,separators=(',',':'))+'\n')
    html='''<!doctype html><meta charset="utf-8"><title>개인용 전체 타일 검토</title>
<style>body{background:#202228;color:#eee;font:16px sans-serif}img{image-rendering:pixelated;max-width:100%}button,input,select{font-size:18px}header{position:sticky;top:0;background:#202228;padding:12px}</style>
<header>전체 14,835프레임 연락시트 · 자동 생성과 직접 시각 검토는 별도 기록합니다.<br>
<select id="group"><option>A</option><option>B</option><option>C</option></select>
<button id="prev">이전</button><button id="next">다음</button>
프레임 <input id="index" type="number" value="0" min="0"><button id="go">찾기</button><span id="label"></span></header><img id="sheet">
<script>const counts={A:4897,B:2973,C:6965};let page=0;const group=document.getElementById('group');
function show(){let g=group.value;page=Math.max(0,Math.min(page,Math.ceil(counts[g]/256)-1));document.getElementById('sheet').src=g+'-'+String(page).padStart(2,'0')+'.png';document.getElementById('label').textContent=' '+g+':'+page*256+'~'+Math.min(counts[g]-1,page*256+255);}
document.getElementById('prev').onclick=()=>{page--;show()};document.getElementById('next').onclick=()=>{page++;show()};group.onchange=()=>{page=0;show()};document.getElementById('go').onclick=()=>{page=Math.floor(Number(document.getElementById('index').value)/256);show()};show();</script>'''
    (folder/'index.html').write_text(html)
    world=json.loads((ROOT/'game/data/world.json').read_text())
    locations=[]
    for m in world['maps']:
        for y,row in enumerate(m['ground']):
            for x,id in enumerate(row):
                locations.append({'asset_id':id,'scene':m['id'],'layer':'ground','x':x,'y':y,
                    'blocked':m['blocked'][y][x],'validation':'SCENE_ENTERED_RENDERED_IDS_RECORDED_NOT_EVERY_POSITION_VISUALLY_REVIEWED'})
        for d in m['decorations']:
            locations.append({'asset_id':d['tile'],'scene':m['id'],'layer':'decoration','x':d['x'],'y':d['y'],
                'blocked':m['blocked'][d['y']][d['x']],'validation':'PLACEMENT_VALID_ACTUAL_VISIBILITY_PER_EXECUTED_ROUTE'})
    out=Path(a.report)
    out.write_text(json.dumps({'status':'PASS_GENERATED_CONTACT_PAGES_AND_USAGE_MAP_NOT_FULL_VISUAL_REVIEW',
        'pages':pages,'page_count':len(pages),'covered_frames':sum(p['frames'] for p in pages),
        'direct_review_frames':1536,'semantic_classified_ids':len(MANUAL),'map_placements':len(locations),
        'browser_ui_runtime':'NOT_RUN_CONTACT_PNGS_GENERATED_AND_READABLE','namespaced_source':'uploaded-editor-undated/palette0'},ensure_ascii=False,indent=2)+'\n')
    out.with_name('asset-use-locations.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n' for v in locations))
    for p in pages:
        im=Image.open(private/p['path']);im.load()
    print('CONTACT_PAGES',len(pages),'FRAMES',sum(p['frames'] for p in pages),'LOCATIONS',len(locations))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',required=True)
    p.add_argument('--ledger',required=True)
    p.add_argument('--report',required=True)
    build(p.parse_args())
