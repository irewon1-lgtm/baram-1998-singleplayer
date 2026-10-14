#!/usr/bin/env python3
"""Convert verified 4.x source tiles/maps privately and attach authored gameplay.

The original layout, collision bits and object columns remain private. Only this
recipe/reader and evidence without source pixels are suitable for the repository.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image
from legacy_assets import Epf, dat_entries, read_palettes, private_path
from legacy_maps import tile_table, static_objects, map_cells

ROOT = Path(__file__).resolve().parents[1]
KR_SHA = 'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
NA_SHA = '9de5ebe95682ee6587ccf6f9e55227bdf671edd3c7197f77ab3021a6bc84eca4'
SELECTED = [0, 2, 3, 11, 13, 15, 17, 41, 53, 55, 62, 66, 100, 204, 205]
ROLES = {0:('village','고구려 마을 · 북미 지형 대체','village',[1,99]),
         2:('inn','주막 · 원본 실내','interior',[1,99]),
         3:('source_smith','대장간 · 원본 실내','interior',[1,99]),
         11:('guild','전사 수련원','interior',[5,99]),
         13:('mage_guild','주술사 수련원','interior',[5,99]),
         15:('rogue_guild','도적 수련원','interior',[5,99]),
         17:('poet_guild','도사 수련원','interior',[5,99]),
         41:('field','신수 들판 · 원본 지형','field',[1,15]),
         53:('cave','쥐굴 미로','dungeon',[5,15]),
         55:('bat_den','박쥐와 쥐굴','dungeon',[8,18]),
         62:('forest','뱀굴','dungeon',[15,25]),
         66:('deep','곰굴','dungeon',[20,30]),
         100:('ruins','깊은 감옥','dungeon',[25,40]),
         204:('rabbit_depth','토끼굴 깊은 길','dungeon',[10,30]),
         205:('foraged','채집 들판','field',[10,30])}


def sha(data): return hashlib.sha256(data).hexdigest()
def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')


def build(a):
    dest = private_path(a.assets)
    inputs = private_path(a.inputs)
    original = (inputs/'KR-4.91/NWind.dat').read_bytes()
    na = (inputs/'NA-4.95/NexusTK.dat').read_bytes()
    if sha(original)!=KR_SHA or sha(na)!=NA_SHA:
        raise ValueError('Verified original DAT pin mismatch')
    entries = dat_entries(original)
    na_entries = dat_entries(na)
    for g in 'abc':
        for ext in ['epf','pal','tbl']:
            key=f'tile{g}.{ext}'
            if entries[key][2]!=na_entries[key][2]:
                raise ValueError('Cross-version tile identity changed: '+key)
    epfs, palettes, tables = {}, {}, {}
    for g in 'ABC':
        epfs[g]=Epf(entries[f'tile{g.lower()}.epf'][2])
        palettes[g]=read_palettes(entries[f'tile{g.lower()}.pal'][2])
        tables[g]=tile_table(entries[f'tile{g.lower()}.tbl'][2],epfs[g].count,len(palettes[g]))
    objects=static_objects(entries['sobj.tbl'][2],epfs['C'].count)
    ledger=json.loads(Path(a.ledger).read_text())
    upload_hashes=collections.defaultdict(list)
    for f in ledger['frames']: upload_hashes[f['rgba_sha256']].append(f['asset_id'])
    tile_registry={'source_dat_sha256':KR_SHA,'shared_na_dat_sha256':NA_SHA,'groups':[],'frames':[]}
    cache={}
    for g in 'ABC':
        epf=epfs[g]; height=((epf.count+127)//128)*24
        epf_hash=sha(entries[f'tile{g.lower()}.epf'][2]);pal_hash=sha(entries[f'tile{g.lower()}.pal'][2])
        atlas=Image.new('RGBA',(3072,height))
        for i in range(epf.count):
            f=epf.frame(i); pal=tables[g].palettes[i]
            canvas=Image.new('RGBA',(24,24))
            if f.width and f.height:
                if f.left<0 or f.top<0 or f.left+f.width>24 or f.top+f.height>24:
                    raise ValueError(f'Unexpected original tile pivot {g}:{i}')
                canvas.paste(Image.frombytes('RGBA',(f.width,f.height),f.rgba(palettes[g][pal])),(f.left,f.top))
            key=f'KR491/{g}:{i}'; digest=sha(canvas.tobytes()); cache[key]=canvas
            aliases=upload_hashes.get(digest,[])
            atlas.paste(canvas,(i%128*24,i//128*24))
            tile_registry['frames'].append(dict(asset_id=key,group=g,index=i,palette_index=pal,
                source_file=f'tile{g.lower()}.epf',source_epf_sha256=epf_hash,
                source_pal_sha256=pal_hash,
                rgba_sha256=digest,uploaded_equal_ids=aliases,left=f.left,top=f.top,width=f.width,height=f.height,
                opaque=sum(f.alpha)//255,extraction='PASS',visual_review='NOT_REVIEWED'))
        png=dest/f'source_tiles/Tile{g}.png';png.parent.mkdir(exist_ok=True);atlas.save(png)
        tile_registry['groups'].append(dict(group=g,count=epf.count,path=f'source_tiles/Tile{g}.png',
            sha256=sha(png.read_bytes()),size=[3072,height]))
    write(dest/'source_tiles/registry.json',tile_registry)
    hints={int(r['id']):r for r in csv.DictReader(Path(a.dimensions).open())}
    all_maps=[]; inventory=[]
    for version in ['NA-4.03','NA-4.95']:
        for path in sorted((inputs/version).rglob('*.map'),key=lambda p:p.name.lower()):
            mid=int(path.stem[2:]);raw=path.read_bytes();hint=hints.get(mid)
            row=dict(asset_id=f'{version}/maps/{mid}',file=str(path.relative_to(inputs)),bytes=len(raw),sha256=sha(raw),
                     format='HEADERLESS_LE_U16_GROUND_AND_OBJECT',dimensions_basis='PRIVATE_REFERENCE_HINT_CHECKED_BYTE_COUNT',
                     visual_review='NOT_REVIEWED',game_connection='NOT_CONNECTED',status='NOT_RUN')
            if hint:
                w,h=int(hint['xs']),int(hint['ys']);row.update(width=w,height=h)
                if len(raw)==w*h*4:
                    try:
                        cells=map_cells(raw,w,h,tables,objects) if version=='NA-4.95' else None
                        row['status']='PASS_STRUCTURE_AND_ID_BOUNDS' if cells is not None else 'BLOCKED_VERSION_SPECIFIC_OBJECT_TABLE_MISSING'
                        if version=='NA-4.95' and mid in SELECTED:all_maps.append((mid,path,w,h,cells))
                    except ValueError as error:row.update(status='BLOCKED_ID_BOUNDS',error=str(error))
                else:row.update(status='BLOCKED_DIMENSION_HINT_MISMATCH',expected_bytes=w*h*4)
            else:row['status']='BLOCKED_DIMENSIONS_MISSING'
            inventory.append(row)
    world=json.loads((ROOT/'game/data/world.json').read_text())
    converted=[]
    for mid,path,w,h,cells in all_maps:
        if mid not in SELECTED:continue
        sid,name,kind,levels=ROLES[mid]
        ground=[['']*w for _ in range(h)];collision=[[0]*w for _ in range(h)];deco=[]
        preview=Image.new('RGBA',(w*24,h*24),(0,0,0,255))
        for j,c in enumerate(cells):
            y,x=divmod(j,w);ground[y][x]=c['tile'];collision[y][x]=c['collision']
            if c['tile']:preview.alpha_composite(cache[c['tile']],(x*24,y*24))
        for j,c in enumerate(cells):
            y,x=divmod(j,w)
            for k,frame in enumerate(objects[c['object_id']]['frames']):
                if frame is None or y-k<0:continue
                key=f'KR491/C:{frame}'
                deco.append(dict(x=x,y=y-k,tile=key,anchor_y=y,object_id=c['object_id'],column_part=k))
                preview.alpha_composite(cache[key],(x*24,(y-k)*24))
        m=dict(id=sid,name=name,kind=kind,width=w,height=h,ground=ground,
               blocked=[[bool(f) for f in row] for row in collision],collision_masks=collision,
               decorations=deco,portals=[],npcs=[],spawns=[],entry=[w//2,h//2],recommended_level=levels,
               original_map_id=mid,source_file=f'NA-4.95/Maps/{path.name}',source_sha256=sha(path.read_bytes()),
               source_kind='ORIGINAL_NA495_LAYOUT_SHARED_KR491_TILES',historic_identity='NA_LAYOUT_REPLACEMENT_NOT_KR1998_CONFIRMED',
               gameplay_kind='AUTHORED_OFFLINE_ROLES_AND_LINKS',revision='source-maps-1')
        converted.append(m)
        png=dest/f'source_maps/previews/{mid}.png';png.parent.mkdir(parents=True,exist_ok=True);preview.convert('RGB').save(png)
    world['maps']=converted
    world['revision']='source-maps-1'
    world['original_map_count']=len(converted)
    world['original_map_registry']='source_maps/inventory.json'
    write(dest/'source_maps/world.json',world)
    write(dest/'source_maps/inventory.json',inventory)
    report=dict(status='PASS_CONVERTED_PRIVATE_NOT_YET_GAMEPLAY',original_files=len(inventory),
        map_status_counts=dict(collections.Counter(r['status'] for r in inventory)),
        selected_maps=[dict(id=m['id'],original=m['original_map_id'],width=m['width'],height=m['height'],
                            source_sha256=m['source_sha256'],object_tile_placements=len(m['decorations'])) for m in converted],
        source_tile_frames=len(tile_registry['frames']),palettes={g:len(palettes[g]) for g in palettes},
        uploaded_ids_with_exact_correct_palette_equivalents=len(set(v for f in tile_registry['frames'] for v in f['uploaded_equal_ids'])),
        source_tiles_equal_uploaded=sum(bool(f['uploaded_equal_ids']) for f in tile_registry['frames']),
        object_columns=len(objects),original_geography='NORTH_AMERICA_REPLACEMENT_KOREAN_1998_IDENTITY_NOT_CONFIRMED',
        source_tiles_registry_sha256=sha((dest/'source_tiles/registry.json').read_bytes()),
        dimensions_reference_sha256=sha(Path(a.dimensions).read_bytes()))
    write(Path(a.report),report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['assets','inputs','ledger','dimensions','report']:p.add_argument('--'+key,required=True)
    build(p.parse_args())
