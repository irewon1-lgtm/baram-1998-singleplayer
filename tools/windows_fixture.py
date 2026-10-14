#!/usr/bin/env python3
"""Generate public CI-only graphics. These contain no original game pixels."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import wave
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')

def make(out,font):
    if out.exists():raise ValueError('Use a fresh fixture directory')
    assets=out/'private_assets';(assets/'tiles').mkdir(parents=True)
    groups=[]
    for group,count in {'A':4897,'B':2973,'C':6965}.items():
        png=assets/f'tiles/Tile{group}_palette0_atlas.png'
        Image.new('RGBA',(3072,((count+127)//128)*24),(38,74,45,255)).save(png)
        table=assets/f'tiles/Tile{group}_frame_map.json'
        save(table,{'count':count,'frames':[{'i':i,'x':i%128*24,'y':i//128*24} for i in range(count)]})
        groups.append({'group':group,'atlas_sha256':digest(png),'map_sha256':digest(table)})
    save(assets/'tiles/MANIFEST.json',{'groups':groups})
    (assets/'sprites').mkdir()
    image=assets/'sprites/fixture.png';Image.new('RGBA',(128*16,128*16),(90,140,180,255)).save(image)
    frames=[{'region':[i%16*128,i//16*128,128,128],'left':-10,'top':-24,'width':20,'height':24} for i in range(256)]
    spec={'path':'sprites/fixture.png','sha256':digest(image),'frames':frames,'canvas':[128,128],'origin':[64,80],
          'walk':3,'attack':2,'delay_ms':100,'lifetime_ms':800}
    names=['body_0','body_1','body_2','body_3','head_0','head_1','head_2','head_3','cloth_0','cloth_1','cloth_2','cloth_3',
           'wood_weapon','iron_weapon','spear_weapon','mail','robe','rabbit','squirrel','rat','snake','bat','boar','spider','skeleton',
           'merchant','teacher','priest','innkeeper','ghost','icons','ui_bars','ui_border','fx_heal','fx_fire','fx_buff','fx_damage',
           'fx_lightning','fx_poison','effect_damage','effect_heal']
    actors={n:dict(spec) for n in names}
    actors['icons']['names']=['토끼고기','목도','산삼','목검','초보 회복약']
    actors['draw_order']=['bwh']*256
    actors['motion_bindings']={};actors['equipment_bindings']={}
    actors['sound_bindings']={k:'sounds/fixture.wav' for k in ['attack','hit','skill','level']}
    save(assets/'actors.json',actors)
    (assets/'sounds').mkdir()
    with wave.open(str(assets/'sounds/fixture.wav'),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
        wav.writeframes(b''.join(struct.pack('<h',2000 if i%20<10 else -2000) for i in range(800)))
    (assets/'fonts').mkdir();shutil.copy2(font,assets/'fonts/NotoSansCJK-Regular.ttc')
    (assets/'source_maps').mkdir();shutil.copy2(ROOT/'game/data/world.json',assets/'source_maps/world.json')
    (out/'private_content').mkdir();(out/'licenses').mkdir()
    save(out/'PACKAGE_MANIFEST.json',{'private_only':True,'contains_user_saves':False,'fixture':True,
         'files':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)}
                  for p in sorted(out.rglob('*')) if p.is_file()]})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--font',required=True)
    args=parser.parse_args();make(Path(args.out),Path(args.font))
