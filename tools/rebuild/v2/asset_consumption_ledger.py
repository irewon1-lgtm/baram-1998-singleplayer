#!/usr/bin/env python3
"""Connect retained Korean member/frame receipts to actual runtime consumers.

Private output contains only references/hashes, never copied source artwork.
Runtime byte verification is distinct from capture and human visual approval.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--captures',type=Path)
    ap.add_argument('--dat',type=Path)
    ap.add_argument('--archive',type=Path)
    args=ap.parse_args();root=args.runtime.resolve();out=args.output.resolve()
    actors=read(root/'gameplay-assets/actors.json');kr=read(root/'kr491/kr491_runtime.json');game=read(root/'gameplay_content.json')
    members={m['member']:m for m in kr['source_members']}
    members.update(actors['source']['members'])
    source={'recorded_archive':'KR_4.91_491v.zip','recorded_container':'NWind.dat','archive_member_chain':['Install/DATA1.CAB','NWind.dat'],'container_sha256':actors['source']['dat_sha256'],
            'source_id':kr['source_id'],'target_1998_2001_historical_match':kr.get('target1998_2001_match','NOT_ESTABLISHED'),'original_archive_bytes_revalidated_this_run':False,
            'note':'Retained pinned extraction provenance. Original archive is not re-downloaded/re-decoded. Runtime PNG bytes are independently hashed below.',
            'reader_sha256':actors['source']['reader_sha256'],'builder_sha256':actors['source']['builder_sha256'],'native_shield_repair':actors['source'].get('native_shield_repair'),'native_steel_repair':actors['source'].get('native_steel_repair'),'native_helmet_repair':actors['source'].get('native_helmet_repair'),'cape_reconstruction':actors['source'].get('cape_reconstruction')}
    if args.archive:
        source['archive_sha256']=sha(args.archive);source['original_archive_bytes_revalidated_this_run']=True
    if args.dat:
        raw=args.dat.read_bytes();observed=hashlib.sha256(raw).hexdigest()
        if observed!=source['container_sha256']:raise ValueError('Restored original DAT container differs from retained provenance')
        verified=[]
        for name,m in members.items():
            offset=m.get('dat_offset',m.get('dat_byte_offset'));length=m.get('bytes')
            if offset is None or length is None:continue
            actual=hashlib.sha256(raw[offset:offset+length]).hexdigest()
            if actual!=m['sha256']:raise ValueError('Retained original member differs: '+name)
            verified.append({'member':name,'sha256':actual,'offset':offset,'bytes':length})
        source['container_bytes_revalidated_this_run']=True;source['raw_members_revalidated_without_redecode']=verified
    captures=read(args.captures) if args.captures else {'captures':[]}
    seen=defaultdict(list)
    for capture in captures['captures']:
        for layer in capture['visible_layers']:
            seen[layer['runtime_path']].append({'capture':capture['file'],'map_id':capture['map_id'],'cell':capture['cell'],
             'world_top_left':layer.get('world_top_left'),'screen_rect':layer.get('screen_rect'),'consumer':layer.get('consumer','visible_world_layer'),'original_frame':layer.get('original_frame'),'method':capture['method']})
    byte_cache={};errors=[]
    def runtime_receipt(path,expected):
        if path not in byte_cache:
            f=root/path
            byte_cache[path]={'exists':f.is_file(),'sha256':sha(f) if f.is_file() else None}
        rec=byte_cache[path]
        if not rec['exists'] or (expected and rec['sha256']!=expected):errors.append({'path':path,'expected':expected,'actual':rec})
        return {'path':path,'recorded_sha256':expected,'observed_sha256':rec['sha256'],'bytes_status':'PASS' if rec['exists'] and (not expected or rec['sha256']==expected) else 'FAIL',
                'capture_status':'PRODUCTION_RENDER_FIXTURE_CAPTURED' if seen[path] else 'NOT_CAPTURED',
                'visual_approval':'NOT_INFERRED_FROM_HASH_OR_CAPTURE','capture_uses':seen[path]}
    def frame_sources(frames):
        result=[]
        for f in frames:
            epf=f.get('epf',f.get('epf_member'))
            if not epf:
                result.append({'official_binding_id':f.get('official_binding_id'),'original_image_sha256':f.get('source_sha256'),'frame':None,'source_kind':'retained_archived_Nexon_official_image'})
                continue
            result.append({'member':epf,'member_sha256':members.get(epf,{}).get('sha256'),'palette_member':f.get('palette_member'),
              'palette_member_sha256':members.get(f.get('palette_member'),{}).get('sha256'),'frame':f['frame'],'palette':f.get('palette'),
              'offset':f.get('offset'),'rgba_sha256':f.get('rgba_sha256'),'recolor_byte':f.get('recolor_byte'),
              'recolor_semantics':f.get('recolor_semantics'),'source_id':f.get('source_id'),'part_id':f.get('part_id'),'relative_frame':f.get('relative_frame'),'source_original_rgba_sha256':f.get('source_original_rgba_sha256'),'source_indices_and_alpha_sha256':f.get('source_indices_and_alpha_sha256'),'reconstructed_palette_ramp':f.get('reconstructed_palette_ramp'),'source_body_part':f.get('source_body_part')})
        return result
    records=[]
    for lid,look in actors['looks'].items():
        for action,directions in look['animations'].items():
            for direction,frames in directions.items():
                for i,frame in enumerate(frames):
                    path='gameplay-assets/'+frame['path']
                    records.append({'family':'actor','look':lid,'action':action,'direction':int(direction),'frame_index':i,
                     'binding_scope':look.get('binding_scope'),'decoder_sources':frame_sources(frame['source_frames']),
                     'runtime':runtime_receipt(path,frame['png_sha256']),'runtime_consumer':'gameplay.gd::_actor_layer / _player_frame_layers / _refresh_equipment_preview',
                     'foot_anchor':{'frame_offset':frame['offset'],'world_formula':'cell*(24,24)+(12,24)+frame.offset'},'duration_ms':frame['duration_ms']})
    native_part_sources={}
    for look in actors['looks'].values():
        for directions in look['animations'].values():
            for frames in directions.values():
                for frame in frames:
                    source_by_kind={f.get('epf','').removesuffix('.epf').lower():f for f in frame.get('source_frames',[])}
                    for part_id in frame.get('part_layers',[]):
                        part=actors.get('player_part_layers',{}).get(part_id,{})
                        if part.get('kind') in source_by_kind:native_part_sources[part_id]=source_by_kind[part['kind']]
    for part_id,part in actors.get('player_part_layers',{}).items():
        records.append({'family':'native_player_part','part_id':part_id,'kind':part['kind'],'decoder_sources':frame_sources([native_part_sources[part_id]]),
          'runtime':runtime_receipt('gameplay-assets/'+part['path'],part['png_sha256']),'runtime_consumer':'gameplay.gd::_player_frame_layers (only when a cape is equipped)',
          'foot_anchor':{'frame_offset':part['offset'],'world_formula':'cell*(24,24)+(12,24)+native leaf offset'},'layer_order':'Native DrwOrder; north cape after body; other directions before parts; casting retains no native weapon/shield'})
    for iid,frame in actors['icons'].items():
        records.append({'family':'item_icon','item_id':iid,'name':game['items'][iid]['name'],
         'decoder_sources':frame_sources(frame['source_frames']),'item_source_pointer':game['items'][iid].get('source_pointer'),'runtime':runtime_receipt('gameplay-assets/'+frame['path'],frame['png_sha256']),
         'runtime_consumer':'GameContent.icon / inventory/equipment slots/loot (icon is not worn avatar)',
         'historical_binding':frame.get('fact_status','RECONSTRUCTED')})
    skills_by_effect=defaultdict(list)
    for sid,skill in game['skills'].items():skills_by_effect[int(skill['effect_id'])].append({'skill_id':sid,'name':skill['name'],'job':skill['job'],
         'kind':skill['kind'],'delivery':skill.get('delivery'),'binding':skill.get('effect_asset_binding',{})})
    for effect in kr['effects']:
        preview=effect.get('priority_preview',{})
        seqs=preview.get('whole',{}) if preview.get('whole_sequence_available') else {}
        if not seqs:
            for fragment in preview.get('fragments',[]):seqs.setdefault(fragment['side'],[]).extend(fragment['frames'])
        for side,frames in seqs.items():
            for i,frame in enumerate(frames):
                image=frame['image'];records.append({'family':'effect','effect_id':effect['id'],'side':side,'frame_index':i,
                 'sequence_source':effect['source'],'decoder_sources':frame_sources([image]),
                 'runtime':runtime_receipt('kr491/'+image['path'],image['sha256']),
                 'runtime_consumer':'gameplay.gd::_consume_events → _render_world → Effect.layers → OriginalView',
                 'sequence_duration_semantics':preview.get('renderer'),'frame_duration_ms':frame['duration_ms'],
                 'bound_skills':skills_by_effect[effect['id']],'historical_timing_audio':'NOT_ESTABLISHED'})
    weapon_styles=Counter(v.get('style','legacy') for v in actors['item_equipment_graphics'].values())
    shield_looks=[lid for lid,l in actors['looks'].items() if l.get('source_parts',{}).get('shield') is not None]
    slot_tables={'shield':'shield_item_graphics','helmet':'helmet_item_graphics','head':'helmet_item_graphics','cape':'cape_item_graphics'}
    missing_worn=[{'item_id':iid,'name':v['name'],'slot':v.get('slot'),'classification':'EXCLUDED_NONWEARABLE_RECEIPT' if any(t in v['name'] for t in ['보관증','보관권','교환권']) else 'REFERENCE_UNCERTAIN',
      'reason':'Legacy broad name classification placed a receipt in helmet slot; deliberately no avatar part' if any(t in v['name'] for t in ['보관증','보관권','교환권']) else 'No selected original/reconstructed avatar layer for this slot.'}
      for iid,v in game['items'].items() if v.get('slot')in slot_tables and iid not in actors.get(slot_tables[v['slot']],{})]
    report={'schema':'baram.asset-consumption.actor-effect/1','source':source,
      'fingerprints':{p:sha(root/p) for p in ['runtime.json','gameplay_content.json','gameplay-assets/actors.json','kr491/kr491_runtime.json']},
      'summary':{'looks':len(actors['looks']),'icons':len(actors['icons']),'wearable_weapon_bindings':len(actors['item_equipment_graphics']),
      'helmet_category_bindings':len(actors.get('helmet_item_graphics',{})),'cape_category_bindings':len(actors.get('cape_item_graphics',{})),'native_player_part_pngs':len(actors.get('player_part_layers',{})),'wearable_identity_status':'GENERIC_NATIVE_HELMET/SHIELD_AND_RECONSTRUCTED_CAPE_CATEGORIES_NOT_ITEM_EXACT; native steel category corrected separately from wooden; exact item identity unproven','weapon_styles':dict(weapon_styles),'effects':len(kr['effects']),'skill_bindings':len(game['skills']),
      'skill_binding_methods':dict(Counter(s.get('effect_asset_binding',{}).get('method','UNKNOWN') for s in game['skills'].values())),
      'records':len(records),'families':dict(Counter(r['family']for r in records)),'unique_pngs_verified':len(byte_cache),
      'paths_captured_in_actual_production_renderer':sum(bool(seen[p]) for p in byte_cache),'byte_failures':len(errors),
      'shield_looks':shield_looks,'missing_worn_slots':dict(Counter(r['slot'] for r in missing_worn))},
      'scope':'Runtime member/frame/hash consumption audit and actual production-render fixture association. No all-asset visual PASS, native platform, source-era exactness or normal-input claim.',
      'status':'PASS_RUNTIME_BYTES_ONLY' if not errors else 'FAIL_RUNTIME_BYTES','errors':errors,'missing_worn_slot_bindings':missing_worn,
      'records':records}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    summary=out.with_name(out.stem+'_SUMMARY.json');summary.write_text(json.dumps({k:v for k,v in report.items()if k not in ['records','missing_worn_slot_bindings']},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False));return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
