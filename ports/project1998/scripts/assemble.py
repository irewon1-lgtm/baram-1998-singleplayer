#!/usr/bin/env python3
"""Materialize a private, standalone Godot runtime without writing art into Git."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--converted',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--font-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();checkout=Path(__file__).resolve().parents[3]
    if out.is_relative_to(checkout):raise ValueError('Private runtime must remain outside public checkout')
    out.mkdir(parents=True,exist_ok=True)
    game=Path(__file__).resolve().parents[1]/'game'
    shutil.copytree(game,out,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.godot','*.uid','export_presets.cfg'))
    shutil.copytree(a.converted,out/'assets',dirs_exist_ok=True,ignore=shutil.ignore_patterns('reference','CONVERSION_TESTS.json'))
    (out/'fonts').mkdir(exist_ok=True)
    shutil.copyfile(a.font_dir/'NotoSansKR[wght].ttf',out/'fonts/NotoSansKR.ttf')
    shutil.copyfile(a.font_dir/'OFL.txt',out/'fonts/OFL.txt')
    assets=json.loads((out/'assets/assets.json').read_text())
    with (a.source/'game-data/Warps.csv').open(encoding='utf-8-sig') as f:warps=list(csv.DictReader(f))
    for m in assets['maps']:
        mid=int(m['id']);raw=(out/'assets'/m['raw_path']).read_bytes()
        def free(x,y):
            if x<0 or y<0 or x>=m['width'] or y>=m['height']:return False
            n=(y*m['width']+x)*4;word=int.from_bytes(raw[n:n+2],'little');obj=int.from_bytes(raw[n+2:n+4],'little')
            return word>>14==0 and (obj==0 or int(assets['objects'][str(obj)]['collision_flags_4x'])!=15)
        if mid==4711:
            m['tech_start']=[3,5]
            m['tech_start_source']='Shared/CharacterFactory.cs NewCharacterSpawn: (4711,3,5)'
        else:
            candidates=[w for w in warps if w['DestinationMapId']==str(mid) and free(int(w['DestinationX']),int(w['DestinationY']))]
            assert candidates,mid
            w=candidates[0];m['tech_start']=[int(w['DestinationX']),int(w['DestinationY'])]
            m['tech_start_source']='Original Warps.csv arrival; WarpId '+w['WarpId']+'; test scene selection, not a new warp'
        assert free(*m['tech_start'])
    (out/'assets/assets.json').write_text(json.dumps(assets,ensure_ascii=False,indent=2)+'\n')
    receipt={'package':'com.irewon.baram.project1998.dev','user_dir':'project1998_s10fe_p2_20261018',
             'source_game_files':[{ 'path':str(p.relative_to(game)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(game.rglob('*')) if p.is_file()],
             'asset_json_sha256':hashlib.sha256((out/'assets/assets.json').read_bytes()).hexdigest(),
             'tech_scene_starts':[{k:m[k] for k in ['id','tech_start','tech_start_source']} for m in assets['maps']]}
    (out/'ASSEMBLY.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'runtime':str(out),'maps':receipt['tech_scene_starts']},ensure_ascii=False))


if __name__=='__main__':main()
