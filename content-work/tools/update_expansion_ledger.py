#!/usr/bin/env python3
"""Join fixed starting inventory to exact package data; never claim game usage."""
import collections,datetime,sys
sys.dont_write_bytecode=True
from common import WORK,load,write,lines,file_sha,canonical

def update():
    index=load(WORK/'HANDOFF_INDEX.json');assets={};defs={};all_records=[];origins={};later_new=collections.Counter();later_bosses=0
    for entry in index['packages']:
        for p in sorted((WORK/'packages'/entry['batch_id']).glob('content-*.jsonl')):
            for r in lines(p):
                ident=r.get('target_id',r['id']);(assets if r['kind']=='asset' else defs)[ident]=r
                all_records.append(r);origins[ident]=entry['batch_id']
                if entry['batch_id']!='WK-CONTENT-001' and r['kind']!='asset' and r['operation']=='add':
                    later_new[r['kind']]+=1
                    if r['kind']=='monster' and r['data'].get('spawn_rules',{}).get('boss'):later_bosses+=1
    consumers=collections.defaultdict(list);selectors=collections.defaultdict(set)
    for i,r in defs.items():
        for a in r['references']:
            if a['id'] not in assets:continue
            consumers[a['id']].append({'target_id':i,'kind':r['kind'],'role':a['role']})
            s=a.get('selector',{});selectors[a['id']].update(s.get('frames',[]))
            if 'frame' in s:selectors[a['id']].add(s['frame'])
    dependency=set()
    for aid in consumers:
        md=assets[aid]['data']['metadata']
        if md.get('sheet_id'):dependency.add(md['sheet_id'])
    reasons={
      'sound-event':{'reason':'Decoded original WAV has no verified source event association; duration alone cannot identify combat, UI or monster role.','next':'Resolve original event mapping or listen to a targeted subset before assigning a compatible consumer.'},
      'head-choice':{'reason':'Original model contains face/hair, not a verified helmet. Existing four fixed class appearances do not expose a hairstyle choice.','next':'Use a separately declared player-appearance capability and original attachment offsets; do not force heads into helmet slots.'},
      'actor-identity':{'reason':'Source actor is decoded but no purpose-compatible content identity/placement has been completed. Human, creature, scenery and shadow models must not be interchanged.','next':'Target the exact remaining source model representative and motion table, then build its complete NPC or monster ecosystem.'},
      'shield-consumer':{'reason':'Source shield is decoded, but current fixed content has no verified compatible offhand consumer or source stat/attachment mapping.','next':'Use an independent offhand capability packet with an actual obtainable shield, compatible offsets and intended combat role.'},
      'fan-consumer':{'reason':'Three original fan models have no current completed fan-weapon consumer; weapon-family motion support at the receiver is unconfirmed.','next':'Create a separate fan weapon/recipe/acquisition packet and declare the required attachment capability.'},
      'weapon-reserve':{'reason':'Source weapon is decoded but has no current completed item consumer; bows and incompatible silhouettes were excluded rather than mislabeled.','next':'Review this exact remaining model and match a distinct existing or obtainable extension weapon role.'},
      'effect-reserve':{'reason':'Source effect has no completed compatible gameplay-event association. Successful decoding does not establish an original spell identity.','next':'Use a verified or inferred compatible event without changing source timing or forcing an unrelated spell.'},
      'mounted-effect-reserve':{'reason':'Recovered effect99 depicts a mounted apparition; no suitable implemented summon/ride event is established.','next':'Retain as an optional effect until a compatible consumer and its capability are defined.'},
      'ui-event':{'reason':'Original UI image is decoded; the current content protocol has no completed UI-skin consumer for this exact panel/button. A role label alone does not bind a runtime event.','next':'Bind the panel to an existing UI scene through an explicit supported capability, with exact crop/button/text regions and event identifiers.'},
      'v125-motion':{'reason':'Historical v125 sheet is preserved but source motion/attachment mapping is not resolved for a completed consumer.','next':'Resolve source sequence and offsets before deriving compatible actors or overlays; do not assume KR491 tables apply.'},
      'no-draw-input':{'reason':'Source bytes contain zero frames or an empty timeline. There are no original drawable pixels to extract.','next':'Preserve original history and reuse a compatible existing asset for a necessary consumer.'}}
    actor_reserves={}
    for entry in index['packages']:
        summary_path=WORK/'packages'/entry['batch_id']/'actors-summary.json'
        if summary_path.exists():
            for reserve in load(summary_path).get('reserved_models',[]):actor_reserves[reserve['model']]=reserve['reason']
    rows=[]
    for aid,r in sorted(assets.items()):
        d=r['data'];family=aid.split('.')[3];state='CONTENT_DEFINED_REFERENCE' if aid in consumers else 'CONTENT_DEFINED_DEPENDENCY' if aid in dependency else 'DECODED_UNUSED'
        reason=None
        if state=='DECODED_UNUSED':
            reason='v125-motion' if '.v125.' in aid else 'mounted-effect-reserve' if aid.endswith('effect.099') else {'sound':'sound-event','head':'head-choice','monster':'actor-identity','shield':'shield-consumer','fan':'fan-consumer','sword':'weapon-reserve','spear':'weapon-reserve','effect':'effect-reserve','sheet':'ui-event'}.get(family,'ui-event')
        reserve_detail=actor_reserves.get(int(aid.rsplit('.',1)[1])) if family=='monster' and state=='DECODED_UNUSED' else None
        rows.append({'asset_id':aid,'family':family,'name':d['name'],'asset_type':d['asset_type'],'frame_count':d['frame_count'],'state':state,'source_package':origins[aid],'consumer_count':len({x['target_id'] for x in consumers[aid]}),'consumer_refs':consumers[aid],'explicit_selected_indices':sorted(selectors[aid]),'reason_id':reason,'specific_reserve_reason':reserve_detail,'recipient_acquisition':'NOT_RUN','game_import':'NOT_RUN','play_verified':'NOT_RUN'})
    out=WORK/'catalog/expansion-2';(out/'asset-after.jsonl').write_text(''.join(canonical(r)+'\n' for r in rows))
    write(out/'remaining-reasons.json',reasons)
    source_maps=lines(out/'map-worklist.jsonl');region=load(WORK/'packages/WK-CONTENT-003/region-summary.json');used=set(region['used_original_map_ids']);reserved={r['original_map_id']:r['reason'] for r in region['unselected_reasons']}
    room_reserve=set(region['remaining_compatible_room_ids']);mrows=[]
    for r in source_maps:
        d=dict(r);mid=d['original_map_id']
        if mid in used:d.update(state='CONTENT_DEFINED_VALIDATED',package='WK-CONTENT-003',unused_reason=None)
        elif d['classification']=='ALREADY_SELECTED':d['package']='WK-CONTENT-001'
        elif d['classification'] in ('DUPLICATE_UNSELECTED_TERRAIN','IDENTICAL_SELECTED_TERRAIN'):d.update(state='SOURCE_DUPLICATE_PRESERVED',next='Reuse the existing source terrain; do not count as a new unique map.')
        elif d['classification']=='NEEDS_DIMENSION_EVIDENCE':d.update(state='BLOCKED_DIMENSION_EVIDENCE',next='Find source map width/height or matching map metadata; valid cells alone do not prove a square map.')
        else:d.update(state='ROLE_RESERVE',unused_reason=reserved.get(mid,'Compatible service interior retained; current24 region groups already have supply/guide/crafting services.' if mid in room_reserve else 'Role not completed'),next='Use this terrain only for a distinct needed connected region/service, or resolve the recorded geometry/palette issue.')
        d.update(game_import='NOT_RUN',play_verified='NOT_RUN');mrows.append(d)
    (out/'map-after.jsonl').write_text(''.join(canonical(r)+'\n' for r in mrows))
    errors=[]
    recovered=load(out/'epf-clipping-probe.json');epf_rows={r['source_file']:r for r in recovered['attempts']}
    effects=load(WORK/'packages/WK-ASSETS-003/recovery-summary.json');erows={str(r['source_model']):r for r in effects['attempts']}
    for r in load(WORK/'catalog/asset-errors.json'):
        d=dict(r);e=epf_rows.get(r.get('source_file')) or erows.get(str(r.get('field')))
        if e:
            restored=e.get('result')=='PASS' or e.get('status')=='SOURCE_TIMELINE_RECOVERED';d['status']='SOURCE_DECODE_RECOVERED' if restored else 'BLOCKED_EMPTY_INPUT';d['current_evidence']=e
        errors.append(d)
    write(out/'asset-errors-current.json',{'source_history_unchanged':'catalog/asset-errors.json','remaining_source_inputs':sum(x['status'].startswith('BLOCKED') for x in errors),'rows':errors,'gameplay':'NOT_RUN'})
    counts=collections.Counter(r['kind'] for r in defs.values());new=collections.Counter();proposals=collections.Counter()
    for r in all_records:
        if origins.get(r.get('target_id',r['id'])) is None:continue
        if r['operation']=='add':new[r['kind']]+=1
        else:proposals[r['kind']]+=1
    initial=load(out/'start.json');source_frame=load(WORK/'catalog/asset-build.json')['source_frame_count']
    asset_groups=collections.defaultdict(collections.Counter)
    for r in rows:asset_groups[r['family']][r['state']]+=1
    summary={'scope':'DATA_ONLY_CONTENT_REFERENCES_NOT_GAME_USAGE','observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'package_ids':[x['batch_id'] for x in index['packages']],
      'asset_definitions':len(assets),'asset_states':dict(collections.Counter(r['state'] for r in rows)),'asset_states_by_family':dict(asset_groups),'initial_asset_states':initial['asset_initial_states'],'initial_asset_definitions':initial['asset_count'],
      'source_frame_indices':source_frame+75,'source_frame_note':'Prior74079 whole-sheet source frames plus75 newly decoded UI frames. Eight recovered effects reuse old frames, no new pixels. Model/sequence entries are not added to this total.',
      'explicit_selected_index_counts_by_asset_type':dict(collections.Counter({typ:sum(len(r['explicit_selected_indices']) for r in rows if r['asset_type']==typ) for typ in sorted({r['asset_type'] for r in rows})})),
      'effective_nonasset_definitions_by_kind':dict(counts),'new_definitions_including_fixed_work001_by_kind':dict(new),'proposal_records_by_kind':dict(proposals),'source_map_files':len(mrows),'source_map_states':dict(collections.Counter(r['state'] for r in mrows)),
      'original_physical_maps':63,'original_distinct_terrain_hashes':60,'new_physical_maps':322,'new_distinct_source_terrain_hashes':322,'effective_logical_map_definitions':counts['map'],'map_aliases_not_new_terrain':1,
      'new_content_since_work001':{'physical_maps':later_new['map'],'region_groups':24,'monsters':later_new['monster'],'bosses':later_bosses,'items':later_new['item'],'npcs':later_new['npc'],'shops':later_new['shop'],'quests':later_new['quest'],'skills':later_new['skill'],'recipe_entries':later_new['recipe']},
      'recovered_ui_sheets':47,'recovered_ui_frames':75,'recovered_ui_png_files':47,'recovered_effect_timelines':8,'recovered_effect_timelines_content_linked':7,'recovered_effect_timed_wait_entries':17,'remaining_empty_source_inputs':3,
      'rank1_teacher_menu_links_repaired':12,'rank2_3_teacher_menu_links_added':16,'whole_game_completion_percent':'NOT_COMPUTED','recipient_acquisition':'NOT_RUN','game_import':'NOT_RUN','gameplay':'NOT_RUN','historical_identity':'Mixed source and explicitly authored/inferred extensions, no new historical proof'}
    write(out/'current-summary.json',summary)
    print({k:summary[k] for k in ('asset_definitions','asset_states','source_map_states','new_content_since_work001','remaining_empty_source_inputs')})

if __name__=='__main__':update()
