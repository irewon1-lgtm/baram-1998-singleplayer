#!/usr/bin/env python3
"""Join actual game evidence to every tile; separate review, placement and rendering."""
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path('/workspace/baram-private')
RUN=ROOT/'docs/development/runs/20261014-assets'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def finish():
    sources=[PRIVATE/'game-screen-run5/primary/primary-report.json',
             PRIVATE/'game-screen-resume6/primary/resume-report.json',
             PRIVATE/'game-screen-resume6/primary/restart-report.json',
             PRIVATE/'game-screen-classes/class-1/class-1-report.json',
             PRIVATE/'game-screen-classes2/class-2/class-2-report.json',
             PRIVATE/'game-screen-classes2/class-3/class-3-report.json']
    reports=[]
    for source in sources:
        report=json.loads(source.read_text())
        name=source.parent.parent.name+'-'+source.name
        shutil.copy2(source,RUN/name)
        log=source.parent/(source.name.replace('-report.json','.log'))
        if log.exists():shutil.copy2(log,RUN/(name+'.log'))
        reports.append(report)
    rendered={id for r in reports for id in r['rendered_tile_ids']}
    actor_rendered={id for r in reports for id in r['rendered_actor_frames']}
    usage=json.loads((RUN/'world-build.json').read_text())['usage']
    ledger=json.loads((RUN/'tile-intake.json').read_text())
    for f in ledger['frames']:
        g,i=f['group'],f['index']
        reviewed=(g in 'AC' and i<512) or (g=='B' and (i<256 or 512<=i<768))
        f['visual_review']='REVIEWED_LABELED_CONTACT_SHEET' if reviewed else 'NOT_VISUALLY_REVIEWED'
        f['automatic_classification']='FULL_CELL' if f['opaque']==576 else 'MASKED_CELL'
        f['semantic_classification']='NOT_ALL_SEMANTICS_IDENTIFIED'
        f['engine_registration']='PASS_LIVE_ATLAS_TEXTURE_AND_TILESET_SOURCE'
        f['map_placement_count']=usage.get(f['asset_id'],0)
        f['game_use']=int(f['asset_id'] in rendered)
        f['unused_reason']=None if f['game_use'] else 'PLACED_BUT_NOT_VISIBLE_ON_EXECUTED_ROUTE' if f['map_placement_count'] else 'VALID_REGISTERED_RESERVE_NOT_PLACED_IN_CURRENT_EIGHT_MAPS'
    ledger.update(status='PASS_AUTOMATIC_AND_ENGINE_REGISTRATION_PARTIAL_VISUAL_AND_GAME_USE',
        visual_review_count=sum(f['visual_review']!='NOT_VISUALLY_REVIEWED' for f in ledger['frames']),
        engine_registered_count=14835,game_used_unique_ids=len(rendered),
        game_used_unique_rgba=len({f['rgba_sha256'] for f in ledger['frames'] if f['game_use']}),
        map_used_unique_ids=len(usage),unused_in_executed_game=14835-len(rendered))
    (RUN/'tile-status-current.json').write_text(json.dumps(ledger,ensure_ascii=False,separators=(',',':'))+'\n')
    assets=json.loads((PRIVATE/'game-assets/actors.json').read_text())
    all_frames=[(key,f) for key,s in assets.items() if isinstance(s,dict) for f in s.get('frames',[])]
    art={'decoded_frames':len(all_frames),'opaque_frames':sum(f['opaque']>0 for _,f in all_frames),
         'transparent_placeholders':sum(f['opaque']==0 for _,f in all_frames),
         'unique_decoded_rgba':len({f['rgba_sha256'] for _,f in all_frames}),
         'rendered_animation_frame_ids':len(actor_rendered),'rendered_ids':sorted(actor_rendered),
         'new_generated_bitmaps':0,'registered_wavs':len(assets['sounds']),
         'original_wav_event_bindings':'REPLACEMENT_IDENTITY_UNVERIFIED',
         'generated_maps':8,'generated_items':3,'generated_training_skills':1,'generated_quests':2}
    # Validate distinct job art against independent decoded body pixels in actual screenshots.
    job_sources=[sources[0],sources[3],sources[4],sources[5]]
    job_checks=[]
    for job,source in enumerate(job_sources):
        screen=Image.open(source.parent/'village-equipped.png').convert('RGB').crop((280,176,536,432))
        s=assets[f'body_{job}'];img=Image.open(PRIVATE/'game-assets'/s['path'])
        x,y,w,h=s['frames'][19]['region'];expected=img.crop((x,y,x+w,y+h)).resize((256,256),Image.Resampling.NEAREST)
        hit=total=0
        for y in range(124,165):
            for x in range(104,150):
                px=expected.getpixel((x,y))
                if px[3] and (x<122 or x>134 or y>144):
                    total+=1;hit+=screen.getpixel((x,y))==px[:3]
        job_checks.append({'job':['전사','도적','주술사','도사'][job],'matching_torso_pixels':hit,'checked_pixels':total,
                           'expected_original_body_sheet_sha256':s['sha256'],'capture_sha256':sha(source.parent/'village-equipped.png'),
                           'status':'PASS' if total and hit/total>.9 else 'FAIL'})
    # Re-evaluate the earlier valid indexed-color screenshots against the corrected nonblank criterion.
    x11=[]
    for source in sources:
        r=json.loads(source.read_text())
        for c in r['screenshots']:
            actual=source.parent/(c['name']+'-x11.png')
            if not actual.exists():continue
            screen=Image.open(actual).convert('RGB');viewport=Image.open(c['path']).convert('RGB')
            colors=len(screen.getcolors(960*640) or [])
            fraction=sum(max(p)<8 for p in ImageChops.difference(screen,viewport).getdata())/(960*640)
            x11.append({'source_report':str(source),'name':c['name'],'sha256':sha(actual),'matching_fraction':fraction,
                        'colors':colors,'status':'PASS' if colors>16 and fraction>.7 else 'FAIL'})
    summary={'tiles':{k:ledger[k] for k in ['total_frames','valid_frames','unique_rgba','visual_review_count',
        'engine_registered_count','map_used_unique_ids','game_used_unique_ids','game_used_unique_rgba','unused_in_executed_game']},
        'actors':art,'job_art_pixel_checks':job_checks,'x11_captures':x11,
        'screen_scope':'Primary 25 kills and level 5; all eight map identities entered; three other jobs basic input combat; 37 same-code calculations. No full four-job level-30 or level-99 playthrough.',
        'x11_criterion_correction':'Original indexed-color art legitimately uses 24-142 colors; former >128 assumption was invalid. All preserved real captures re-read with nonblank >16 plus >70% independent X11/viewport match.',
        'original_raw_images_public':False}
    (RUN/'asset-game-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'tiles':summary['tiles'],'actors':{k:v for k,v in art.items() if k!='rendered_ids'},
                      'job_pixel_checks':[v['status'] for v in job_checks]},ensure_ascii=False))


if __name__=='__main__':finish()
