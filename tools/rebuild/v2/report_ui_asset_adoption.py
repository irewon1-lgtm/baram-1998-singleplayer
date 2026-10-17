#!/usr/bin/env python3
"""Trace original UI/actor/icon pixels into the live HUD without copying assets.

The generated report distinguishes a decoded/bound family from actual screenshot
review. It never turns a catalog entry or a PNG existence check into VISUAL_PASS.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(runtime: Path, project: Path, evidence: Path) -> dict:
    assets=json.loads((runtime/'gameplay-assets/actors.json').read_text())
    kr=json.loads((runtime/'kr491/kr491_runtime.json').read_text())
    data=json.loads((runtime/'gameplay_content.json').read_text())
    ui=next(e for e in kr['ui'] if e['name']=='DLGNEW02')
    member=next(e for e in kr['source_members'] if e['member']=='DLGNEW02.epf')
    screenshots=[]
    for path in sorted(evidence.glob('hud-after-*.png')):
        screenshots.append({'path':str(path.resolve()),'sha256':sha(path),'scope':'Actual Linux Godot window, continued byte-identical prior natural save; XTEST UI input; not Android/Windows hardware'})
    def frames(look):
        for action,directions in look.get('animations',{}).items():
            for direction,entries in directions.items():
                for frame in entries:yield action,direction,frame
    player_looks={key:value for key,value in assets['looks'].items() if key.startswith('player_')}
    player_paths={f['path'] for look in player_looks.values() for _,_,f in frames(look)}
    actor_members=Counter(f['epf'] for look in player_looks.values() for _,_,entry in frames(look) for f in entry.get('source_frames',[]))
    return {
      'schema':'baram.v2.hud-source-adoption/1',
      'scope':'B5 source-first live HUD integration; no historical exact-HUD claim; no full 111-map or native-platform visual PASS implied',
      'runtime_manifest_sha256':sha(runtime/'runtime.json'),'gameplay_content_sha256':sha(runtime/'gameplay_content.json'),
      'source_archive':'KR_4.91_491v.zip / NWind.dat','source_container_sha256':assets['source']['dat_sha256'],
      'families':[
       {'family':'UI_SCROLL_WOOD_BUTTONS','former_defect':'SOURCE_PRESENT_UNUSED',
        'source_member':member,'palette_binding':ui.get('palette_binding'),
        'decoded_frame':ui['image'],'runtime_texture':'kr491/'+ui['image']['path'],
        'adopted_regions':{'parchment_tile':[333,196,16,16],'wood_button':[125,308,70,15],'scroll_top':[27,0,346,22],'scroll_bottom':[27,350,346,23],'scroll_left':[7,28,18,300],'scroll_right':[377,28,18,300]},
        'adaptation':'SOURCE_LUMINANCE_WARM_HONEY_RECONSTRUCTION: preserve source alpha, linework, grain, ornament; remap RGB dither through 7-step honey palette; nearest source tiles; reconstructed HUD arrangement.',
        'runtime_consumers':['ui/classic_skin.gd','ui/parchment_panel.gd','ui/classic_list.gd','ui/gameplay.gd::_build_ui'],
        'application':['left world frame','persistent right paperdoll + four tabs + dark status inset','left bottom quick actions/chat','dialogue/map/shop/close buttons'],
        'visual_review':'Actual HUD screen reviewed; colored dither scaling and wrapped meter captions were found and repaired. Full-game B5 visual quality remains separate.'},
       {'family':'FULL_BODY_PAPERDOLL','source_members':{m:assets['source']['members'][m] for m in ['Body.epf','Head.epf','Sword.epf','Shield.epf'] if m in assets['source']['members']},
        'runtime_catalog':'gameplay-assets/actors.json','player_looks':len(player_looks),'unique_runtime_frames':len(player_paths),'source_component_references':dict(actor_members),
        'runtime_consumers':['ui/gameplay.gd::_look_player','ui/gameplay.gd::_refresh_equipment_preview'],
        'application':'Persistent right HUD at integer2x standing south frame (integer1x on short surfaces), equipment side slots show separate item icons. Same selected look appears in world.',
        'limits':'Screenshot proves current equipped look only; icons are not claimed to be wearable overlays. Other source directions/equipment need their own runtime tests.'},
       {'family':'ITEM_ICONS','runtime_catalog':'gameplay-assets/actors.json:icons','item_definitions':len(data['items']),'icon_bindings':len(assets['icons']),
        'source_member':assets['source']['members']['Item.epf'],
        'runtime_consumers':['ui/gameplay.gd::_refresh_panels','ui/classic_list.gd'],
        'application':'Inventory/equipment list and weapon/armor side slots. Shared metadata/selection APIs retained.',
        'limits':'Actual visible rows checked, not1105 individually wearable.'},
       {'family':'SKILL_THUMBNAILS_AND_EFFECT_DEPTH','runtime_catalog':'kr491/kr491_runtime.json:effects','retained_sequences':len(kr['effects']),
        'runtime_consumers':['ui/gameplay.gd::_skill_icon','ui/gameplay.gd::_append_depth_effect','ui/gameplay.gd::_consume_events'],
        'application':'Skill list/three hotkey buttons show source effect frame alpha-cropped and nearest-resized24px; these are reconstructed effect thumbnails, not original skill icons. Back/front effect sets straddle actor foot depth; target damage summary duplicates suppressed.',
        'limits':'Named effect source identities and 4-job actual impact behavior separately tracked by actor/effect QA.'}
      ],
      'screenshots':screenshots,
      'source_hashes':{str(path.relative_to(project)):sha(path) for path in sorted((project/'ui').glob('*.gd')) if path.name in ['gameplay.gd','classic_skin.gd','parchment_panel.gd','classic_list.gd']},
      'platforms':{'Linux_window':'RUN_WITH_XTEST_INPUT','Android_hardware':'NOT_RUN','Windows_native':'NOT_RUN'},
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,required=True);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report(a.runtime,a.project,a.evidence),ensure_ascii=False,indent=2)+'\n')
    print(a.output)
if __name__=='__main__':main()
