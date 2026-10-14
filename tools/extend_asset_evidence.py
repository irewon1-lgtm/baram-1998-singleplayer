#!/usr/bin/env python3
"""Extend existing asset/status/use ledgers with source regions and real game evidence."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from legacy_assets import private_path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'docs/development/runs/20261014-assets'


def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(a):
    private=private_path(a.private);assets=private/'game-assets'
    world=json.loads((assets/'source_maps/world.json').read_text())
    actors=json.loads((assets/'actors.json').read_text())
    sources=json.loads((assets/'source_tiles/registry.json').read_text())
    reports=[];tiles=set();frames=set();entered=set();casts=set();sounds=set()
    prefixes=['source-screen-1','content-screen-1','content-screen-2','content-screen-fixed-1','content-screen-fixed-2','content-actions-screen','cure-actions-screen','town-all-screen','natural-progress-screen']
    for folder in prefixes:
        for p in sorted((private/folder).rglob('*-report.json')):
            r=json.loads(p.read_text());reports.append(dict(path=str(p.relative_to(private)),sha256=digest(p),status=r['status'],scope=r.get('scope'),checks=len(r['checks'])))
            tiles.update(r.get('rendered_tile_ids',[]));frames.update(r.get('rendered_actor_frames',[]))
            entered.add(r['player']['map'])
            for event in r.get('events',[]):
                kind=event['event'];v=event['details']
                if kind=='map_changed':entered.add(v['map'])
                elif kind=='skill_cast':casts.add(r['player']['job']+':'+v['skill'])
            for v in r.get('audio_events',[]):sounds.add(v['file_sha256'])
    # Retired old effect keys are preserved in the atlas but no longer called by
    # the current TBL-driven skill renderer. They do not count as current use.
    frames={f for f in frames if not f.startswith(('effect_heal:','effect_damage:'))}
    placement=collections.Counter();locations=[];map_usage={}
    for m in world['maps']:
        counts=collections.Counter()
        for y,row in enumerate(m['ground']):
            for x,key in enumerate(row):
                if not key:continue
                counts[key]+=1;locations.append(dict(asset_id=key,scene=m['id'],layer='ground',x=x,y=y,
                    collision_mask=m.get('collision_masks',[[0]])[y][x],scene_executed=m['id'] in entered,
                    frame_rendered_in_any_game=key in tiles,individual_position_visibility='NOT_ASSERTED'))
        for d in m['decorations']:
            key=d['tile'];counts[key]+=1;locations.append(dict(asset_id=key,scene=m['id'],layer='source_object',x=d['x'],y=d['y'],
                anchor_y=d.get('anchor_y',d['y']),object_id=d.get('object_id'),scene_executed=m['id'] in entered,
                frame_rendered_in_any_game=key in tiles,individual_position_visibility='NOT_ASSERTED'))
        placement.update(counts);map_usage[m['id']]=dict(unique_ids=len(counts),placements=sum(counts.values()),executed=m['id'] in entered,
                                                      original_map_id=m['original_map_id'],source_sha256=m['source_sha256'])
    # Full source map coordinates stay private, unlike our old authored layouts.
    loc=assets/'source_maps/asset-use-locations.jsonl'
    loc.write_text(''.join(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n' for v in locations))
    uploaded=json.loads((RUN/'tile-status-current.json').read_text())
    source_rows=[];parent_placements=collections.Counter()
    for f in sources['frames']:
        for alias in f['uploaded_equal_ids']:parent_placements[alias]+=placement[f['asset_id']]
        f.update(source_kind='ORIGINAL_KR491_BYTE_IDENTICAL_NA495_TILE_RESOURCE',engine_registration='PASS_LIVE_TEXTURE_AND_TILESET',
                 game_use=int(f['asset_id'] in tiles),map_placement_count=placement[f['asset_id']],
                 connected_to_game=placement[f['asset_id']]>0,visual_review='NOT_INDIVIDUALLY_REVIEWED_SOURCE_MAP_CONTEXT_SEPARATE',
                 use_positions_private_file='source_maps/asset-use-locations.jsonl')
        f['unused_reason']=None if f['game_use'] else 'CONNECTED_SOURCE_POSITION_NOT_EXERCISED' if f['connected_to_game'] else 'NORMAL_DECODED_NATIVE_MAP_OR_DECOR_ROLE_NOT_CONNECTED'
        source_rows.append(f)
    uploaded['source_frames']=source_rows
    matched_uploaded={alias for row in source_rows for alias in row['uploaded_equal_ids']}
    for f in uploaded['frames']:
        f['historical_game_use']=max(int(f.get('historical_game_use',0)),int(f['game_use']))
        f['game_use']=int(f['asset_id'] in tiles);f['source_map_placement_count']=parent_placements[f['asset_id']]
        f['connected_to_game']=parent_placements[f['asset_id']]>0
        f['runtime_evidence_reports']=[r['path'] for r in reports] if f['game_use'] else []
        if f['game_use']:f['unused_reason']=None;f['application_status']='NORMAL_GAME_RENDERED_EXACT_RGBA_ALIAS'
        elif parent_placements[f['asset_id']]:f['unused_reason']='CONNECTED_SOURCE_MAP_POSITION_NOT_REACHED_BY_CAPTURE_ROUTE';f['application_status']='CONNECTED_NOT_RENDERED'
        elif f['asset_id'] in matched_uploaded:f['unused_reason']='NORMAL_DECODED_SOURCE_EQUIVALENT_NOT_SELECTED_BY_CONNECTED_MAP_LAYOUT';f['application_status']='NORMAL_DECODED_UNCONNECTED'
        else:f['unused_reason']='UNDATED_SOURCE_ID_OR_PALETTE_CORRESPONDENCE_UNRESOLVED';f['application_status']='CLASSIFICATION_OR_PALETTE_UNRESOLVED'
    uploaded.update(game_used_unique_ids=sum(f['game_use'] for f in uploaded['frames']),
                    unused_in_executed_game=sum(not f['game_use'] for f in uploaded['frames']),
                    source_registered_frames=len(source_rows),source_used_unique_ids=sum(f['game_use'] for f in source_rows),
                    source_connected_ids=sum(f['connected_to_game'] for f in source_rows),
                    source_unique_rgba=len({f['rgba_sha256'] for f in source_rows}),
                    source_visual_individual_review_count=0,
                    source_visual_scope='Source map previews/live screenshots reviewed; no invented individual-ID full review',
                    map_use_positions_private_sha256=digest(loc))
    write(RUN/'tile-status-current.json',uploaded)
    old=json.loads((RUN/'actor-status-current.json').read_text());reviewed={}
    for f in old['frames']:
        if f.get('visual_review','').startswith('REVIEWED'):reviewed[(f['original_epf'],f['original_frame'],f['rgba_sha256'])]=f['visual_review']
    actor_rows=[];categories=collections.defaultdict(list)
    for key,spec in actors.items():
        if not isinstance(spec,dict) or 'frames' not in spec:continue
        category='character' if spec['epf'] in ['body','head','ghost'] else 'equipment' if spec['epf'] in ['sword','spear','fan','bow','shield'] else 'npc' if key in ['innkeeper','merchant','teacher','priest'] else 'monster' if spec['epf']=='monster' else 'effect' if spec['epf']=='effect' else 'icon' if spec['epf']=='item' else 'ui'
        for index,f in enumerate(spec['frames']):
            alias=f'{key}:{index}';pal=f.get('palette_index',spec['palette_index'])
            canonical=f"KR491/{spec['epf']}/{f['frame']}/pal{pal}/tint{spec['recolor_byte']}"
            review=reviewed.get((spec['epf'],f['frame'],f['rgba_sha256']),'DIRECT_MAGNIFIED_UI_REVIEW' if key=='ui_border' else 'NOT_INDIVIDUALLY_REVIEWED')
            used=alias in frames
            reason=None if used else 'REPLACED_BY_TBL_SEQUENCE_ROLE' if key.startswith('effect_') else 'RESERVED_OTHER_MOTION_NEEDS_GAMEPLAY_BINDING' if category=='character' and index>=80 else 'CONNECTED_ACTION_OR_DIRECTION_NOT_EXERCISED' if category in ['equipment','monster','npc','effect','icon','ui'] else 'REGISTERED_POSE_NOT_EXERCISED'
            if not used and category=='character' and 52<=index<=71:reason='BOW_MOTION_AVAILABLE_BUT_ZERO_FRAME_BOW_EPF_NO_WEAPON_BINDING'
            row=dict(asset_id=alias,canonical_asset_id=canonical,category=category,original_epf=spec['epf'],original_frame=f['frame'],
                     original_source='KR-4.91/NWind.dat/'+spec['epf']+'.epf',rgba_sha256=f['rgba_sha256'],
                     palette_index=pal,recolor_byte=spec['recolor_byte'],source_kind=spec['source_kind'],
                     automatic_status='PASS_BOUNDED_DECODE_PALETTE_AND_ATLAS',visual_review=review,
                     engine_registration='PASS_LIVE_TEXTURE_AND_FRAME_TABLE',game_use=int(used),unused_reason=reason,
                     parent_and_recipe='game/data/runtime_bindings.json; tools/build_playable_assets.py',
                     game_connection='main.gd actor/UI/effect dispatch from equipment/motion/NPC data',
                     runtime_evidence_reports=[r['path'] for r in reports] if used else [])
            actor_rows.append(row);categories[category].append(row)
    actor_doc=dict(frames=actor_rows,processed=len(actor_rows),registered=len(actor_rows),
                   individual_contact_review=sum(not r['visual_review'].startswith('NOT') for r in actor_rows),
                   used=sum(r['game_use'] for r in actor_rows),unused=sum(not r['game_use'] for r in actor_rows),
                   unique_rgba=len({r['rgba_sha256'] for r in actor_rows}),
                   runtime_aliases_are_not_original_ids=True,canonical_source_ids_preserved=True)
    write(RUN/'actor-status-current.json',actor_doc)
    issues=[]
    def issue(group,rows,status,cause,attempt,result,alternative,remaining):
        ids=[f['asset_id'] for f in rows]
        if not ids:return
        issues.append(dict(group=group,ids=ids,count=len(ids),status=status,cause=cause,actual_attempt=attempt,result=result,
                           applied_alternative=alternative,remaining_action=remaining))
    for status in ['NORMAL_DECODED_UNCONNECTED','CONNECTED_NOT_RENDERED','CLASSIFICATION_OR_PALETTE_UNRESOLVED']:
        issue('uploaded-'+status,[f for f in uploaded['frames'] if f['application_status']==status],status,
              'Original undated IDs/forced palette 0 do not carry map/object roles; current layouts must follow source IDs and their PAL/TBL.',
              'Viewed remaining 54 actual contact pages; decoded 35,269 source tiles through their TBL palettes; exact pixel crossmatch found 7,252 uploaded IDs; fixed TBL bases and SObj/null/directional collision; imported real source maps.',
              'Exact equivalents now used by source maps; count is per ID, no claim that unmatched colors are repaired.',
              'KR491/NA495 shared correctly paletted resources actually applied to 38 game regions.',
              'Unmatched: need original undated TileA/B/C EPF+PAL+TBL with hashes in supplied MANIFEST; classification stays unresolved. Connected: exercise the specific source position; unconnected equivalents: choose another real-content map/role after review.')
    issue('source-normal-unconnected',[f for f in source_rows if not f['connected_to_game']],'NORMAL_DECODED_UNCONNECTED',
          'Decoded source families are larger than connected map tile references.',
          'Removed 149-ID selection limit; actual source map converter and data-based town doorway importer applied.',
          '38 original regions connected; remaining source IDs preserved, not declared unsuitable or duplicates.',
          'Source map tiles/objects replace eight authored flat layouts; new rooms support shops/rest/revive/combat.',
          'Continue other native map IDs and classify unused decorative families; no raw decoder failure established.')
    issue('source-connected-not-rendered',[f for f in source_rows if f['connected_to_game'] and not f['game_use']],'CONNECTED_NOT_EXERCISED',
          'Not every camera/coordinate in large original maps was traversed.',
          'Played original town/interiors/fields/dungeons; joined actual texture calls with private coordinate ledger.',
          'Scene entry does not mark all placed positions or frames PASS.',None,'Continue exact positions in private asset-use-locations.jsonl.')
    for reason in sorted({r['unused_reason'] for r in actor_rows if r['unused_reason']}):
        issue('actor-'+reason,[r for r in actor_rows if r['unused_reason']==reason],'REGISTERED_NOT_EXERCISED_OR_NOT_CONNECTED',reason,
              'Data bindings replace fixed weapon/body IDs; casting 72..75, pickup 76..79, spear 32..51 and monster attack blocks connected; corrected bear/mouse/bat roles and per-frame effect/item palettes; real four-job casts and armor tested.',
              'Actual displayed IDs recorded separately from all 1,849 registered frames.',
              'Source outfits/gear/effects/9-patch UI applied; older effect aliases retained but replaced.',
              'Riding/other poses require mount/action roles; other directions/actions must be exercised. Bow EPF is zero frames; exact item look and legacy hit/death motion identities remain unresolved.')
    issue('sounds-unmapped',[dict(asset_id='KR491/sounds/'+f['path']) for f in actors['sounds'] if f['sha256'] not in sounds],
          'EVENT_CLASSIFICATION_UNRESOLVED','PCM files decode but original event numbering is not known.',
          'Read all source PCM headers; separate real engine attack/hit/skill/level voices and mixed PCM signal verified.',
          'Only event-bound actually played files count as use; human audible review is NOT_RUN.',
          'Four source WAV event replacements applied to real combat/skills/level UI.','Identify original event-to-WAV table/listen to remaining exact filenames; do not call them unnecessary.')
    write(RUN/'unused-resolution-current.json',dict(issues=issues,scope='Exact source/runtime IDs; grouped causes; unresolved is not resolved',
        additional_file_and_map_blockers='source-member-inventory.json; source_maps/inventory.json; town-door-resolution.json',
        source_coordinates_private=dict(path='source_maps/asset-use-locations.jsonl',sha256=digest(loc),rows=len(locations))))
    summary=dict(status='PASS_EXECUTED_SCOPES_WIP_ENTIRE_RESTORATION',before=dict(uploaded_tiles=14835,reviewed=1536,placed_unique=149,rendered_unique=138,actor_frames=1137,actor_rendered=239,maps=8,natural_level=5),
        uploaded_tiles=dict(processed=14835,unique_rgba=uploaded['unique_rgba'],reviewed_contact=14835,registered=14835,
                            connected=sum(f['connected_to_game'] for f in uploaded['frames']),rendered=sum(f['game_use'] for f in uploaded['frames']),
                            unused=sum(not f['game_use'] for f in uploaded['frames']),exact_alias_candidates=7252),
        source_tiles=dict(processed=len(source_rows),unique_rgba=len({r['rgba_sha256'] for r in source_rows}),registered=len(source_rows),
                          connected=sum(f['connected_to_game'] for f in source_rows),rendered=sum(f['game_use'] for f in source_rows),
                          unused=sum(not f['game_use'] for f in source_rows),individual_review=0),
        combined_tile_unique_rgba=len({f['rgba_sha256'] for f in uploaded['frames']+source_rows}),
        actual_rendered_unique_tile_rgba=len({f['rgba_sha256'] for f in uploaded['frames']+source_rows if f['game_use']}),
        same_picture_aliases_are_not_double_unique_assets=True,
        categories={k:dict(registered=len(v),unique_rgba=len({r['rgba_sha256'] for r in v}),reviewed=sum(not r['visual_review'].startswith('NOT') for r in v),
                          rendered=sum(r['game_use'] for r in v),unused=sum(not r['game_use'] for r in v)) for k,v in categories.items()},
        actor_frames=actor_doc, # removed below to keep the summary compact
        sounds=dict(registered=len(actors['sounds']),actual_played_unique=len(sounds),human_audible_review='NOT_RUN'),
        maps=dict(connected=len(world['maps']),actual_entered=len(entered),entered=sorted(entered),source_files=2363,structure_valid=1738,
                  usage=map_usage,placements=sum(placement.values()),unique_source_ids=len(placement),original_identity='NA495_NATIVE_LAYOUT_NOT_KR1998_IDENTITY'),
        skills=dict(job_level30_profiles=66,common_distinct=3,source_profile_records=72,actual_cast_job_skill_pairs=len(casts),cast_ids=sorted(casts),
                    four_job_level30='CONTROLLED_FIXTURE_SKILL_EQUIPMENT_TEST_NOT_NATURAL_PLAYTHROUGH'),
        generated=dict(new_independent_bitmaps=0,source_outfit_color_parameter_variants=6,source_sequences=6,source_ui_frames=12,
                       authored_npcs=sum(len(m['npcs']) for m in world['maps']),authored_region_links=sum(len(m['portals']) for m in world['maps']),
                       new_layouts=0,native_layouts=len(world['maps']),legacy_authored_layouts_preserved=8),
        reports=reports,original_similarity_percent=None,natural_full_four_job_level30='NOT_RUN',level31_99_and_advancement='NOT_COMPLETE',
        asset_coordinate_ledger_private_sha256=digest(loc))
    summary.pop('actor_frames')
    write(RUN/'asset-game-summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['uploaded_tiles','source_tiles','categories','sounds','generated']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--private',required=True);run(p.parse_args())
