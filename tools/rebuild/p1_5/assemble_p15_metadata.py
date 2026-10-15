"""Assemble existing evidence by reference. No game data defaults or runtime binding."""
import collections,csv,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'docs/rebuild/p1_5'
OLD=ROOT/'docs/rebuild/step01'
def sha(b):return hashlib.sha256(b).hexdigest()
def jl(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def writejl(p,rs):p.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rs))
def load(p):return json.loads(p.read_text())
def row_sources(r):
    ids=list(r.get('source_ids',[]))
    if r.get('source_id'):ids.append(r['source_id'])
    if isinstance(r.get('source'),dict) and r['source'].get('source_id'):ids.append(r['source']['source_id'])
    return ids

FIELD_FILES={
1:['kr_asset_ui_strings','kr_asset_sprite_frames','kr_official_flow','kr_official_creation_visual'],2:['save_contracts'],3:['save_contracts','kr_official_flow'],4:['save_contracts'],5:['kr_asset_ui_strings','kr_official_flow'],6:['kr_asset_parts','kr_asset_ui_strings','kr_official_flow','kr_official_creation_visual'],7:['kr_documented_fields','kr_official_flow'],8:['kr_asset_parts','kr_official_items','kr_official_image_bindings'],9:['kr_asset_parts','kr_asset_draw_order','kr_asset_monster_groups','kr_asset_sprite_frames'],10:['kr_official_core','kr_official_skill_effects'],11:['kr_asset_ui_strings','kr_official_flow'],12:['save_contracts'],13:['kr_official_map_assets','kr_official_full_maps'],14:['kr_official_services','kr_official_map_assets','kr_official_flow'],15:['kr_documented_fields','kr_official_flow','kr_official_crafting_facts'],16:['kr_official_core','kr_asset_monster_groups','kr_asset_parts'],17:['kr_official_core','na_reference_rtk_drops'],18:['kr_official_core','kr_official_flow','kr_official_skill_effects'],19:['kr_official_skill_effects','na_reference_spell_calls'],20:['kr_official_services','kr_official_items','kr_official_facility_rules'],21:['kr_official_items','kr_asset_parts'],22:['kr_asset_draw_order','kr_asset_sprite_frames','kr_asset_effect_frame_palettes'],23:['kr_asset_effect_sequences','kr_asset_legacy_effect_tables','kr_asset_guide_effects'],24:['kr_asset_sound_metadata','kr_asset_guide_effects'],25:['kr_asset_guide_effects','kr_official_npc_appearance'],26:['save_contracts'],27:['save_contracts'],28:['save_contracts'],29:['save_contracts'],30:['kr_documented_fields'],31:['save_contracts'],32:['save_contracts']}

AREAS=[
('A','NPC 외형','npc','name|alias|native_id|region|building|coordinate|direction|body_head_clothes_weapon|palette|motion_layer|screen_evidence|service','BND-033','P2-02','한국 NPC 개별 외형/좌표/부품 ID는 화면과 자산을 함께 확인; 같은 역할 외형 일괄 배정 금지'),
('B','NPC 대화·퀘스트','dialogue','spoken_text|choices|branch_condition|reward|consumption|failure|refusal|cancel|revisit|after_completion','BND-034','P3/P5','원문·공략 설명·재구성 구분; 전체 상태 그래프가 없으면 새 기준본에서 조건별 관측'),
('C','몬스터·스폰·드롭','monster','identity_variant_boss|region_floor|graphic|hp_stats|experience|aggression|movement_chase_return|attack_interval|death|respawn_delay|spawn_area_count_cap|item_relation|probability|probability_model|quantity|drop_condition|no_drop|ownership_despawn','BND-016;BND-017','P2-01/P3/P5','공식 표의 문서값과 NA 참고 소비 코드를 분리; 원작 확률/독립·배타/수량이 없으면 UNKNOWN'),
('D','조합·업그레이드·수리','craft','era_existence|recipe|materials|material_quantities|money|npc|level_job_condition|success_result|success_rate|failure_loss_or_keep|durability|repairability|repair_price','BND-035','P3/P5','현대 강화·옛 조합·퀘스트 업그레이드·수리 분리; 성공률 임의값 금지'),
('E','직업·기술·성장·경제','skill','peasant_start|job_change_level_npc|four_job_learning|learn_materials|learn_money|prerequisite|target|range_wall|cost_hp_mp|effect|duration|stack_dispel|failure|cooldown|experience_growth|promotion|equipment_condition|shop_stock_buy_sell_limit','BND-018;BND-020;BND-021','P2-04/P3/P5','2000/2001 profile dispatch 필수; 문서에 없는 수치·전직업 공통 기본값 금지'),
('F','모션·합성','motion','direction_order|frame_start_end|repeat|delay_raw_unit|origin_offset|palette|front_back_layer|action_entry_exit|transition_interrupt|body_weapon_alignment|existent_action_set','BND-009;BND-022','P2-02','한국 원본 표와 네 방향 행동을 대조; 이미지 추출 성공과 모션 의미·속도 복원 분리'),
('G','효과·음향·타격 시점','effect','skill_to_guide_image|guide_to_client_sequence|sequence_frames|layer_position|repeat_alpha_light|sound_id|wave_metadata|cast|impact|hit_display|actual_audio_output|next_action_time|latency_uncertainty','BND-023;BND-024','P2-03','모든 확보 GIF와 원본 프레임 비교; Delay raw 단위/음향/타격 시점은 정확한 P2 관측'),
('H','한국 지도·출구·귀환','map','era_city|dimensions|coordinate_origin|landmarks|buildings|four_gates|interiors|hunting_entrances|tiles_objects|collision_occlusion|npc_spawns|exits|return_by_country_direction|resurrection|summon_restriction','BND-013;BND-014','P2-01','공식 PCX와 원본 MAP 대응을 검증; NA 지명 교체·임시 포털·village 고정 금지'),
('I','로그인·생성·UI','creation','background_buttons|states|sound|name_input_error|cancel|creation_options|choice_order|initial_place_equipment_job|IME|right_four_panels|bottom_status|selection_scroll_empty_error|actual_icons|equipped_appearance','BND-001;BND-005;BND-006;BND-007','P2-04/P2-05','한국 공식 생성 절차·원본 문자열·사용자 UI 사진을 구분; 로그인 UI 마스크2개와 실제 IME 별도 관측'),
('J','저장·업데이트·환경','save','schema|payload_integrity|owner_stable_id_bounds|atomic_backup_recovery|coordinate_validity|explicit_migration|preserve_on_failure|offline_revision_conflict|same_account_roundtrip|windows|android|actual_galaxy|auth_environment_access','BND-026;BND-027;BND-028;BND-029','P2-05/P2-06','정적 참고 패턴과 실기기/실인증 구분; 좌표 일괄 입구 이동 금지')]

def main():
    original_ids={x['source_id'] for x in jl(OLD/'sources.jsonl')}
    base=[x for x in jl(OUT/'sources_delta.jsonl') if x['source_id'] in original_ids]
    reg={x['source_id']:x for x in base}
    def add(s):
        if not isinstance(s,dict) or not s.get('source_id'):return
        sid=s['source_id'];h=s.get('sha256')
        if sid in reg:
            if h and reg[sid].get('sha256') and h!=reg[sid]['sha256']:raise ValueError('Conflicting source hash: '+sid)
            return
        r=dict(s);r.setdefault('source_type','SOURCE_METADATA');r.setdefault('source_family','UNKNOWN');r.setdefault('source_path_or_url',s.get('url',s.get('original_url',s.get('path','UNKNOWN'))))
        if 'NEXON_OFFICIAL_GUIDE' in r['source_family']:
            r['source_generation']=r['source_family'];r['source_family']='NEXON_OFFICIAL_GUIDE'
        r.setdefault('fact_status','UNKNOWN');r.setdefault('game_region','UNKNOWN');r.setdefault('content_era','UNKNOWN');r.setdefault('use_status',r.get('utilization_status','ACQUIRED'));r['test_status']='NOT_RUN';r['new_runtime_binding']='NOT_STARTED';r['delta_operation']='ADD_SOURCE_OR_SOURCE_FIELD';reg[sid]=r
    ip=ROOT/'docs/rebuild/STEP015_WORK_INSTRUCTIONS.md'
    add({'source_id':'PLAN-P1_5-INSTRUCTIONS','source_type':'AUTHORITATIVE_PLAN_INPUT','source_family':'USER_AUTHORIZED_REBUILD_PLAN','source_path_or_url':'docs/rebuild/STEP015_WORK_INSTRUCTIONS.md@5d70e48e88a6a73553fee0f35c2c5812547d6dbf','sha256':sha(ip.read_bytes()),'game_region':'KR','content_era':'Target1998-2001; instruction2026-10-16','use_status':'IDENTIFIED'})
    research=[]
    for p in sorted(OUT.glob('research_*.json')):
        r=load(p);research.append((p.name,r))
        for key in ('sources','web_pages','web_images','image_sources','archive_sources'):
            if isinstance(r.get(key),list):
                for s in r[key]:add(s)
    writejl(OUT/'sources_delta.jsonl',list(reg.values()))
    catalogs=[];data={}
    for p in sorted((OUT/'selected_content').glob('*.jsonl')):
        rows=jl(p);data[p.stem]=rows;b=p.read_bytes();catalogs.append({'path':'selected_content/'+p.name,'sha256':sha(b),'bytes':len(b),'records':len(rows),'schema':'per-record provenance with source-qualified IDs','visibility':'PRIVATE_VALUE_EXPORT','record_types':dict(collections.Counter(r.get('kind',r.get('record_type','UNKNOWN')) for r in rows))})
    sp=OUT/'selected_content/save_contracts.json';save=load(sp);data['save_contracts']=save['contracts'];b=sp.read_bytes();catalogs.append({'path':'selected_content/save_contracts.json','sha256':sha(b),'bytes':len(b),'records':len(save['contracts']),'visibility':'PUBLIC_STATIC_REFERENCE_CONTRACT'})
    (OUT/'selected_content/catalog.json').write_text(json.dumps({'schema':'baram.p1_5.catalog/1','scope':'Exact required normalized file set, not game completion','normalized_catalogs':catalogs,'default_build_profile_id':None,'profile_dispatch_required':True},ensure_ascii=False,indent=2)+'\n')
    bindings=jl(OLD/'field_bindings.jsonl')
    for r in bindings:
        n=int(r['binding_id'].split('-')[1]);refs=[];sel=technical=recons=0;added_sources=set()
        for stem in FIELD_FILES.get(n,[]):
            if stem not in data:continue
            rows=data[stem];added_sources.update(s for row in rows for s in row_sources(row));orig=[x for x in rows if x.get('selected_original_value') is not None];tech=[x for x in rows if x.get('selected_for_p2_technical_input')];rc=[x for x in rows if x.get('reconstructed_value') is not None]
            sel+=len(orig);technical+=len(tech);recons+=len(rc)
            refs.append({'path':'selected_content/'+stem+('.json' if stem=='save_contracts' else '.jsonl'),'records':len(rows),'selected_original_records':len(orig),'technical_input_records':len(tech),'reconstructed_records':len(rc),'selection_field':'selected_original_value','profile_dispatch_required':True})
        r.update(delta_operation='REEVALUATE_EXISTING_GROUP',prior_ledger='docs/rebuild/step01/field_bindings.jsonl',selection_state='PARTIAL_FIELD_SELECTION_BY_REFERENCE' if sel or technical else 'SOURCE_OR_CONTRACT_ONLY',selected_original_value=None,selected_original_value_refs=refs,selected_record_counts={'original_fields_in_records':sel,'p2_technical_records':technical,'reconstruction_records':recons},fact_status='UNKNOWN',fact_scope='Group remains incomplete. Field-level facts/selections live once in normalized records; raw KR491 format facts are not target-era server facts.',default_build_profile_id=None,profile_dispatch_required=True,new_runtime_binding='NOT_STARTED',test_status='NOT_RUN',missing_information=r['missing_information']+'; 해결된 필드와 남은 공백은 해당 연구 JSON과 gaps_by_feature.csv를 참조.')
        r['source_ids']=sorted(set(r['source_ids']+['PLAN-P1_5-INSTRUCTIONS'])|added_sources)
    for bid,title,stems in [('BND-033','npc.individual_appearance_identity',['kr_official_services','kr_official_npc_appearance']),('BND-034','npc.dialogue_choices_quest_state',['kr_documented_fields','na_reference_npc_dialogue','na_reference_npc_calls']),('BND-035','craft.recipe_era_success_failure_and_repair',['kr_official_crafting_facts','kr_official_facility_rules','kr_official_services','kr_documented_fields','na_reference_craft_calls'])]:
        refs=[{'path':'selected_content/'+s+'.jsonl','records':len(data[s])} for s in stems if s in data]
        bindings.append({'binding_id':bid,'field_path':title,'delta_operation':'ADD_MISSING_GROUP','source_ids':sorted({'PLAN-P1_5-INSTRUCTIONS'}|{sid for stem in stems if stem in data for row in data[stem] for sid in row_sources(row)}),'selected_original_value':None,'selected_original_value_refs':refs,'selection_state':'PARTIAL_FIELD_SELECTION_BY_REFERENCE','fact_status':'UNKNOWN','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','default_build_profile_id':None,'profile_dispatch_required':True,'missing_information':'Full Korean native ID/behavior/conditions remain field-specific; see normalized rows and gaps.'})
    writejl(OUT/'field_bindings.jsonl',bindings)
    with (OUT/'gaps_by_feature.csv').open('w',encoding='utf-8-sig',newline='') as f:
        cols=['area','feature','target_field','known_entity_scope','target_global_population','gap_cause','status','evidence','binding_ids','blocking_stage','next_action'];w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for code,title,kind,fields,bids,stage,action in AREAS:
            bmap={b['binding_id']:b for b in bindings}
            refpaths=sorted({x['path'] for bid in bids.split(';') for x in bmap.get(bid,{}).get('selected_original_value_refs',[]) if not x['path'].startswith('selected_content/na_')})
            matching=[r for k,rows in data.items() if not k.startswith('na_') for r in rows if kind in str(r.get('record_type',r.get('kind','')))]
            count=len(matching)
            for fld in fields.split('|'):
                runtime=any(k in fld for k in ('interval','delay_raw_unit','impact','actual_audio','next_action','windows','android','galaxy','roundtrip','IME','action_entry','transition','coordinate_validity'))
                cause='RUNTIME_OBSERVATION_NEEDED' if runtime else 'UNIDENTIFIED' if any(k in fld for k in ('native_id','body_head','sound_id','motion_layer','collision')) else 'UNBOUND' if count or refpaths else 'MISSING_SOURCE'
                w.writerow(dict(zip(cols,[code,title,fld,f'관련 유형 {count}행; 입력풀 '+','.join(refpaths)+'; 원작 개체 분모 아님','UNKNOWN; known corpus only',cause,'PARTIAL_OR_BLOCKED_FIELD', 'selected_content/catalog.json; field_bindings.jsonl; research_*.json',bids,stage,action])))
    originals=[]
    for s in jl(OLD/'archive_sources.jsonl'):
        originals.append({k:s[k] for k in ['source_id','library_file_id','library_path','sha256','size_bytes']})
    manifest={'schema':'baram.p1_5.input_manifest/1','task_id':'BARAM_REBUILD_P1_5_001','base_plan_commit':'5d70e48e88a6a73553fee0f35c2c5812547d6dbf','originals':originals,'normalized_catalogs':catalogs,'default_build_profile_id':None,'working_profile_proposal':'2001 year-end per existing provisional RESTORATION_PROFILE; not frozen','profile_dispatch_required':True,'profile_conflicts':'research_official_core.json epoch_conflicts; independent review','original_resources_public':False,'private_handoff':'Exact file ID/hash in DELIVERY_RECEIPT.json outside the archive to avoid a self-referential hash','reference_package':{'path':'inputs/reference_sources.zip','sha256':'6e922fc3725c52e9bad3dd45924756c57e01781a36c9fd9b8eb35cd81291c508','bytes':124462848,'scope':'Full acquired reference sources with intentional sensitive RTK database/default-credential exclusions; SOURCE_MANIFEST inside package','execution':'NOT_RUN'},'source_acquisition_and_current_access':'source_access.json; research_*.json','replay_commands':{'archives':'python3 tools/rebuild/p1_5/recheck_archives.py --repo <checkout> --input-root <materialized42> --private-work <separate-private-dir> --legacy-parser-dir <extracted-references/legacy_parser_tools>','whole_byte_gate':'python3 tools/rebuild/step01/validate_step01.py --root <checkout> --input-map <current-step01-only-map2489> --output <new-result>','normalized_import':'python3 tools/rebuild/p1_5/import_dry_run.py --repo <checkout> --registry-dir <checkout>/docs/rebuild/p1_5 --input-map <current-full-import-map> --catalog-manifest <checkout>/docs/rebuild/p1_5/INPUT_MANIFEST.json --output <new-result>','portable_path_restore':'See handoff_input_contract.json: prepare_handoff_inputs.py produces separate exact-scope step01 and full import maps without executing sources'},'receiver_environment':'NOT_RUN; Work clean-directory check is not Codex G0','runtime_tests':'NOT_RUN','p2_executed':False,'security_exclusions':['private-intake','raw RTK database directory','docker-compose.yml','God_Tools.lua','.git directories','__pycache__','real user saves/signing keys'],'tools':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p.read_bytes())} for p in sorted((ROOT/'tools/rebuild/p1_5').glob('*.py')) if p.name!=Path(__file__).name]}
    manifest['replay_commands']['prepare_inputs']='python3 tools/rebuild/p1_5/prepare_handoff_inputs.py --package-root <extracted-handoff> --source-root <materialized-originals> --source-root <rechecked-byte-cache> --work-dir <private-resolver-cache> --output <current-map> --report <new-resolution-result>'
    manifest['replay_commands']['normalized_import']='python3 tools/rebuild/p1_5/import_dry_run.py --repo <extracted-handoff> --content-dir <extracted-handoff>/docs/rebuild/p1_5/selected_content --server-root <materialized-reference-sources> --input-map <current-map> --catalog-manifest <extracted-handoff>/docs/rebuild/p1_5/INPUT_MANIFEST.json --output <new-result>'
    (OUT/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sources':len(reg),'old_sources':len(original_ids),'normalized_files':len(catalogs),'normalized_rows':sum(c['records'] for c in catalogs),'bindings':len(bindings),'gap_fields':sum(len(x[3].split('|')) for x in AREAS)}))

if __name__=='__main__':main()
