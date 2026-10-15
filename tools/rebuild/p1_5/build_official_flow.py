#!/usr/bin/env python3
"""Pinned source manifest supplies hashes and URLs; no network or runtime execution."""
from pathlib import Path
import json,hashlib,re,collections
import argparse
cli=argparse.ArgumentParser(description='Static official Korean guide fact extraction; does not execute game/server code')
cli.add_argument('--input-dir',type=Path,required=True,help='Private pinned official HTML directory containing acquisition.json')
cli.add_argument('--out-dir',type=Path,required=True,help='P1.5 report directory')
a=cli.parse_args();p=a.input_dir;out=a.out_dir
(out/'selected_content').mkdir(parents=True,exist_ok=True)
ss=json.loads((p/'acquisition.json').read_text());rows=[];used={}
def src(suffix):return next(s for s in ss if s['status']==200 and s['original_url'].endswith(suffix))
def emit(suffix,anchor,entity,field,value,line_span=1,selected=True,note=None):
 s=src(suffix);s['local_private_path']=str(p/Path(s['local_private_path']).name);source_bytes=Path(s['local_private_path']).read_bytes();assert hashlib.sha256(source_bytes).hexdigest()==s['sha256'];txt=source_bytes.decode('cp949');off=txt.find(anchor);assert off>=0,(suffix,anchor);line=txt[:off].count('\n')+1;rid='KRO-FLOW-'+hashlib.sha256((suffix+field+entity).encode()).hexdigest()[:12];used[s['source_id']]=s
 rows.append(dict(content_id=rid,record_type=field.split('.')[0],entity_name_ko=entity,field_path=field,original_value=value,reconstructed_value=None,selected_original_value=value if selected else None,selected_for_build=selected,selected_for_p2_technical_input=True,source_ids=[s['source_id']],source_family='NEXON_OFFICIAL_GUIDE',source_locator={'url':s['source_path_or_url'],'original_url':s['original_url'],'line_start':line,'line_end':line+line_span-1},input_sha256=s['sha256'],parser_version='p15-official-flow-curation-v1',game_region='KR',client_build='UNKNOWN',archive_capture_at=s['archive_capture_at'],content_era=s['content_era'],source_authored_or_modified_at=s['source_authored_or_modified_at'],build_profile_id='KR_GUIDE_2001_SNAPSHOT',selection_scope='PROFILE_SCOPED_PUBLISHED_FIELDS_ONLY',require_profile_dispatch=True,global_default_selected=False,target_profile_resolution='UNRESOLVED',gameplay_binding_requires_profile_decision=True,profile_is_client_version=False,fact_status='ORIGINAL_VERIFIED',fact_scope='Explicit officialpublished fields; server/client execution not performed',historical_match='CONTEMPORANEOUS_OFFICIAL_DOCUMENT',use_status='IDENTIFIED',new_runtime_binding='NOT_STARTED',test_status='NOT_RUN',required_implementation='Keep sourceepoch and profile selection separate; preserve unconfirmed fields',notes=note))
char='/guide/start/character.html'
emit(char,'우선 캐릭터의','캐릭터 생성','creation.documented_option_set',{'id_and_password_before_appearance':True,'gender':['여성','남성'],'appearance_control':'left/right arrows','nationality':['고구려','부여'],'guardian':['청룡','백호','주작','현무'],'document_option_numbering':['아이디/패스워드','음양 성별','외형','국가','신수'],'actual_selection_event_order':None,'valid_name_regex':None,'max_name_characters':None},3,note='Document numberedoptions are not proof UI enforces a sequentialwizard. Namevalidation limits remainnull; no NAASCII rule.')
for stat,anchor in [('힘','[ 힘 ]'),('민첩성','[ 민첩성 ]'),('지력','[ 지력 ]')]:
 emit(char,anchor,stat,'growth.documented_base_stat_limit',{'stat':stat,'base_min':1,'base_max':130,'equipment_bonus_additional':True,'comparison_2000_page_base_max':150},4,note='2001officialpage says130and equipmentbonus;2000officialpage says150. Preserve epochconflict; not average.')
 emit(char,anchor,stat,'growth.documented_stat_purchase',{'stat':stat,'required_level':90,'xp_cost':10000000,'increase':1},4,note='Published90+purchase rule; no perlevelgrowthcurve inferred.')
emit(char,'[ 체력 ]','체력','growth.documented_death_threshold',{'hp':0,'state':'ghost'},4,note='Deathstate fact only; deathloot/XP penalties separate unknown.')
emit(char,'AC(Armor','무장강도','combat.documented_armor_order',{'stat':'AC','lower_is_stronger':True},2)
# Exactranges/costs factual, but ambiguousprinted boundaries remaintext rather than inventedintervalinclusivity.
for group,anchor,bands in [
 ('전사/도적','체력 50 올릴때',[('0~80만미만',10000000),('80만~100만미만',20000000),('100만~120만',50000000),('120만~130만',100000000),('130만~',200000000)]),
 ('주술사/도사','체력 50 올릴때',[('0~40만미만',10000000),('40만~50만미만',20000000),('50만~60만',50000000),('60만~70만',100000000),('70만~',200000000)])]:
 emit(char,anchor,group+' 체력','growth.documented_hp_exchange_bands',{'job_group':group.split('/'),'increase_hp':50,'required_level':90,'bands':[{'current_hp_range_literal':r,'xp_cost':c,'boundary_inclusivity':'ONLY_미만_EXPLICIT_OTHER_BOUNDARIES_UNRESOLVED'} for r,c in bands]},20,note='No assumedhalf-openintervals where sourceomits미만. XPcostgrowth supported; exactboundarybehavior P2observationneeded.')
for group,anchor,bands in [
 ('전사/도적','마력 50을 올릴때',[('0~10만',20000000),('10만~15만',40000000),('15~20만',100000000),('20만~',200000000)]),
 ('주술사/도사','마력 50을 올릴때',[('0~60만',20000000),('60만~70만',40000000),('70만~80만',100000000),('80만~',200000000)])]:
 emit(char,anchor,group+' 마력','growth.documented_mp_exchange_bands',{'job_group':group.split('/'),'increase_mp':50,'required_level':90,'bands':[{'current_mp_range_literal':r,'xp_cost':c,'boundary_inclusivity':'UNRESOLVED'} for r,c in bands]},18,note='Source마력 section accidentallylabels current체력; keep bandmeaning andliteraltypo note;15~20만 lacksfirst만 andmustnot silentlynormalize.')
common='/guide/middle/magic/common.html'
emit(common,'죽어서 유령','성황령','transport.documented_state_and_destination',{'required_player_state':'ghost','destination_kind':'shrine_entrance','actual_revival':False,'map_id':None,'left_right_selection':None},5)
emit(common,'국내성 혹은 부여성','비영사천문','transport.documented_gate_options',{'cities':['국내성','부여성'],'directions':['동','서','남','북'],'destination_kind':'city_gate','specific_map_ids':None,'country_restrictions':None},3,note='Originalfourgateconcept; never mapalloptions toonevillage. Exactcityselectionrule unresolved.')
wiz='/guide/middle/magic/wizard.html'
emit(wiz,'자신의 나라 주막','귀환(주술사)','transport.documented_country_destination',{'job':'주술사','destination_kind':'own_nation_tavern','destination_map_id':None},3)
emit(wiz,'자신보다 낮은 레벨','출두(주술사)','transport.documented_target_level',{'job':'주술사','spell':'출두','target_level_relation':'strictly_lower','region_blacklist':None,'offline_other_player_policy':None},3)
emit(wiz,'자신보다 레벨이 낮은','소환(주술사)','transport.documented_target_level',{'job':'주술사','spell':'소환','target_level_relation':'strictly_lower','region_blacklist':None,'offline_other_player_policy':None},3)
# Historicalservicepolicy is evidence oforiginalaccountmodel, explicitlyexcludedfrompersonalofflineproduct.
emit('/guide/start/rule.html','2000년 1월 1일','옛 온라인 휴면ID 정책','account.historical_service_policy_excluded',{'policy_effective_from':'2000-01-01','inactive_online_account_deletion_existed':True,'personal_offline_save_deletion_adopted':False},4,selected=False,note='Sourcehistoricalserviceexpiry must noterasepersonalofflineprofiles/saves. Not authorization forrealaccountchanges.')
emit('/guide/start/start.html','넥슨클럽은','옛 넥슨클럽','account.documented_club_role',{'nexon_club_role':'freeemail/passwordrecoveryservice','old_character_id_password_separate':True,'modern_cross_device_auth_verified':False},3,note='Contemporaneousdocument separatescharactercredentials andNexonClubrecovery. Modernrealaccountsync NOT_RUN.')
f=out/'selected_content/kr_official_flow.jsonl';f.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));(out/'research_official_flow.json').write_text(json.dumps({'task_id':'BARAM_REBUILD_P1_5_001','status':'PARTIAL','sources':list(used.values()),'records':len(rows),'counts_by_type':dict(collections.Counter(r['record_type'] for r in rows)),'outputs':[{'path':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size,'records':len(rows)}],'parser_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'note':'Selectionscope isdocumentfacts; targetprofilechoices/boundaries remainexplicit. No runtime executed.'},ensure_ascii=False,indent=2)+'\n');print(len(rows))
