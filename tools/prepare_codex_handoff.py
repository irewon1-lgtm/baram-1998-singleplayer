#!/usr/bin/env python3
"""Prepare tests, feature evidence, source comparisons and unresolved bindings."""
import argparse, collections, datetime, hashlib, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/restoration-integrated-20261013'
def readl(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def writej(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def writel(n,rs):(OUT/n).write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rs))
def norm(s):return re.sub(r'\s+','',s or '')
def main():
    p=argparse.ArgumentParser();p.add_argument('--private-dir',required=True);a=p.parse_args();private=Path(a.private_dir);upstream=private/'repos/project1998/Project1998'
    catalog=readl(OUT/'CONTENT_CATALOG.jsonl');master=readl(OUT/'NUMERIC_MASTER.jsonl');by={(r['content_id'],r['field']):r for r in master}
    def find(name,field,scope=None):return next(r for r in master if norm(r['content_name'])==norm(name) and r['field']==field and (scope is None or r['class_scope']==scope))
    tests=[]
    def test(tid,name,inputs,expected,refs=None,precondition=None):
        tests.append(dict(test_id=tid,name=name,inputs=inputs,expected_conditions=expected,field_refs=refs or [],precondition=precondition,
                          execution_status='NOT_RUN',observed_result=None,evidence_log=None,required_calculator='The same module called by the actual game; no separate simulation formula'))
    squirrel=find('다람쥐','experience');sword=find('목검','damage_min');gun=find('건곤대나이','learn_level','전사');shield=find('사각방패','armor_class')
    test('XP-FRACTION','분수 경험치 누적',dict(monster_xp=squirrel['value'],kills=10,starting_xp=0),dict(final_xp=75,per_kill_rounding_forbidden=True),[squirrel['field_id']])
    for path,scope in [(1,'전사'),(2,'도적'),(3,'주술사'),(4,'도사')]:
        for level in [1,5,29,98]:
            r=by[(f'kr.growth.{path}.{level:02d}','cumulative_exp_to_next')]
            test(f'XP-{path}-{level}','누적 경험치 경계 '+scope+' '+str(level),dict(class_scope=scope,current_level=level,threshold=r['value'],xp_before=r['value']-1,award=1),dict(level_after=level+1,threshold_is_cumulative=True),[r['field_id']])
        test(f'GROWTH-{path}','1~30 성장 '+scope,dict(class_scope=scope,start_level=1,job_select_level=5,target_level=30,random_seed=19982001),dict(all_29_levelups_in_valid_inclusive_hp_mp_ranges=True,peasant_growth_used_before_job_selection=True,save_reload_preserves_level_hp_mp_xp_gold=True),[by[(f'kr.growth.{path}.05','hp_gain_min')]['field_id'],by[(f'kr.growth.{path}.05','hp_gain_max_inclusive')]['field_id']])
    test('XP-99-CAP','99레벨 상한',dict(current_level=99,xp_award=1000000),dict(level_after=99,xp_bank_preserved=True),precondition='Decide and implement post-99 XP conversion separately; never use missing next threshold as a level-100 gate')
    test('INTEGER-LEARN','평균 습득레벨 정수화',dict(raw_average=71.5),dict(applied_level=72),[gun['field_id']])
    test('INTEGER-AC','평균 AC 정수화',dict(raw_average=-11.5),dict(applied_armor_class=-12),[shield['field_id']])
    test('EQUIP-STRENGTH','착용 힘 경계',dict(item='목검',required_strength=5,player_strength_cases=[4,5]),dict(equip_results=[False,True],failed_equip_leaves_inventory_unchanged=True),[find('목검','strength_required')['field_id']])
    test('DAMAGE-ARMOR','대체 방어력 공식',dict(raw_damage=100,target_armor_cases=[100,0,-80,-95],armor_floor=-95),dict(damage_cases=[200,100,20,5],rounding='floor once at final multiplication'),precondition='Only if the selected development path adopts the explicitly labeled NA replacement formula')
    test('CAST-RESOURCES','MP·HP 차감 원자성',dict(mp_before=20,required_mp=21,hp_before=50),dict(cast_succeeds=False,mp_after=20,hp_after=50,cooldown_not_started=True))
    test('HEAL-CAP','회복 상한',dict(hp_before=90,hp_max=100,heal=50),dict(hp_after=100))
    test('LEARN-COST','습득 비용과 시전 비용 분리',dict(skill='누리의기원',class_scope='전사',level=10,gold=30,acorns=70),dict(learn_gold_deduction=30,learn_acorn_deduction=70,learning_gold_never_used_as_cast_mp=True),[find('누리의기원','learn_money','전사')['field_id']])
    test('LEARN-ABORT','제물 부족',dict(gold=30,acorns=69,required_acorns=70),dict(learn_succeeds=False,gold_after=30,acorns_after=69))
    test('DROP-10PCT','서생원 산삼 확률',dict(kills=100000,seed=1999,item='산삼',probability=.1),dict(drop_count_min=9500,drop_count_max=10500,listed_item_not_forced_to_probability_one=True),precondition='Use the actual game RNG, source-linked 10% rule and independently meaningful tolerance')
    test('DROP-ALTERNATIVE','대체 드롭 그룹',dict(group=['철단도','철검'],mode='ALTERNATIVE_NOT_INDEPENDENT',seed=2001),dict(at_most_one_of_group_per_group_roll=True),precondition='Source says alternative possibilities; choose and label group roll probability separately')
    test('TRADE-ROUNDTRIP','구매·판매·금전',dict(gold=1000,buy_price=20,sell_price=10,quantity=3),dict(gold_after_buy=940,gold_after_resell=970,negative_balance_forbidden=True))
    test('REPAIR-RTK','RTK 대체 수리 계산',dict(buy_price=20,max_durability=4000,current_durability=2000,coefficient=.5),dict(repair_cost=5,after_durability=4000),precondition='If adopting RTK formula; original Korean repair formula remains unverified')
    test('REPAIR-BOUNDARY','수리 경계',dict(max_durability=4000,current_durability=4000,gold=0),dict(repair_cost=0,zero_max_durability_never_divided=True,nonrepairable_item_rejected=True))
    test('CRAFT-ATOMIC','제작 거래 원자성',dict(seed=1998,ingredients_sufficient=False),dict(no_gold_or_item_deduction=True,no_product_grant=True))
    test('PROGRESSION-RESOURCES','각 직업 성장 경제',dict(classes=['전사','도적','주술사','도사'],target_level=30,seed=19982001,buy_sell_prices='NUMERIC_MASTER',drops='DROP_RULES'),dict(no_required_skill_material_without_obtainable_source=True,no_negative_gold=True,no_required_equipment_stronger_than_available_strength=True),precondition='Requires actual NPC inventories, spawns, mappings and mechanics; input readiness is not this test passing')
    writej('BALANCE_TESTS.json',dict(test_count=len(tests),scope='Input and expected conditions only',execution_status='NOT_RUN',actual_simulations_executed=0,tests=tests))
    # Evidence is a file/hash/line reference. Presence never means this repository runs that code.
    feature_specs=[
     ('character_create','캐릭터 생성','Shared/CharacterFactory.cs','PlaceNewCharacter'),('class_select','직업 선택','Server/NpcAbility.cs','ClassTrainerAbility'),
     ('movement','이동·방향','Server/Session.Navigation.cs','private'),('collision','충돌','Server/World.cs','TryMove'),('map_transition','맵 전환','Server/Session.Navigation.cs','Map'),
     ('pickup','아이템 획득','Server/Session.Items.cs','HandlePickup'),('inventory','가방','Server/Session.Items.cs','Inventory'),('equip','착용·해제','Server/Session.Items.cs','HandleUseItem'),
     ('equipment_stats','장비 능력치','Server/Session.Items.cs','WeaponTotals'),('equipment_appearance','장비 외형','Server/Session.Entity.cs','look'),
     ('spell_learn','기술 습득','Server/NpcAbility.cs','ClassTrainerAbility'),('spell_input','단축키·기술 입력','Server/Session.cs','ClientOp.Cast'),('spell_target','기술 대상 선택','Server/Session.Spells.cs','HandleCast'),
     ('dialogue','NPC 대화','Server/Session.Dialog.cs','Dlg'),('shop','구매·판매','Server/NpcAbility.cs','ShopAbility'),('repair','장비 수리','Server/NpcAbility.cs','RepairAbility'),
     ('quest','퀘스트','Server/NpcAbility.cs','QuestAbility'),('mob_ai','몬스터 AI','Server/World.MobAiTick.cs','Tick'),('melee','일반 공격','Server/Session.Combat.cs','HandleAttack'),
     ('magic_attack','마법 공격','Server/Session.Spells.cs','HandleCast'),('damage_death','피격·사망','Server/Session.Combat.cs','Death'),('levelup','경험치·레벨업','Server/Session.CharacterApi.cs','private void LevelUp'),
     ('gold_drop','금전·드롭','Server/World.cs','Loot'),('craft','제작','Server/CraftingToggles.cs','IsEnabled'),('trade','거래','Server/Session.cs','Exchange'),
     ('animation_sound','애니메이션·효과음·타격 타이밍','Server/Session.Entity.cs','Sound'),('advancement','레벨 99·승급','Server/NpcAbility.cs','Mark'),
     ('singleplayer_assist','싱글플레이 보조',None,None),('save_load','저장·불러오기','Server/Session.CharacterApi.cs','SaveChar'),('offline','인터넷 없는 실행','Server/Program.cs','Main')]
    features=[]
    for fid,name,file,needle in feature_specs:
        path=upstream/file if file else None;exists=bool(path and path.exists());line=None;matched=False
        if exists:
            text=path.read_text(errors='replace');hits=[i for i,l in enumerate(text.splitlines(),1) if needle.lower() in l.lower()];line=hits[0] if hits else None;matched=bool(hits)
        status='EXTERNAL_CODE_REFERENCE_FOUND' if matched else 'NEEDS_TARGETED_CODE_REVIEW' if exists else 'NO_CONFIRMED_CODE_PATH'
        if fid=='repair':status='EXTERNAL_STUB_ONLY'
        if fid=='craft':status='EXTERNAL_FRAGMENT_ONLY'
        features.append(dict(feature_id=fid,name=name,data_status='PARTIAL_SOURCE_DATA',code_status=status,code_evidence=dict(repository='project1998/Project1998',commit='36905428ff59329be28c6a4579e41f4fd9e9a967',path=file,line=line,sha256=hashlib.sha256(path.read_bytes()).hexdigest() if exists else None),
                             game_implementation='NOT_RUN',automatic_game_test='NOT_RUN',actual_screen_operation='NOT_RUN',needs_own_implementation_or_adaptation=True,
                             note='Read-only source evidence; no external source is included or approved for public reuse'+('; repair menu is an explanatory stub' if fid=='repair' else '')))
    writej('FEATURE_MATRIX.json',dict(features=features,dimensions=['data_status','code_status','game_implementation','automatic_game_test','actual_screen_operation']))
    asset_gaps=[];content_gaps=[]
    required_content={
      'monster':['native_id','hunting_map_ids','ai_behavior','spawn_rules','drop_groups','sprite_bindings','sound_bindings'],
      'item':['native_id','item_kind','wear_slot','allowed_classes','allowed_sexes','drop_sources','recipe','icon_binding','wear_binding','floor_binding'],
      'spell':['native_id','class_scope','learn_material_links','damage_formula','healing_formula','target_rule','effect_code','key_binding','animation_binding','sound_binding'],
      'npc':['native_id','map_id','dialogue','shop_inventory','learnable_spells','repair_rules','quest_rules','sprite_binding'],
      'map':['native_id','tile_grid','collision_grid','portals','spawns','tile_palette','bgm_binding','quest_links']}
    for c in catalog:
        if c['namespace']!='KR' or c['category'] not in required_content:continue
        for field in required_content[c['category']]:
            known=field=='class_scope' and c.get('class_scope') is not None or field=='item_kind' and c.get('item_kind') is not None
            content_gaps.append(dict(content_id=c['content_id'],name=c['name'],category=c['category'],field=field,status='KNOWN_DRAFT' if known else 'NEEDS_MAPPING_OR_IMPLEMENTATION',early_scope=c.get('production_stage')=='LEVEL_1_30'))
        kinds={'monster':['idle','walk','attack','hit','death','sound'],'npc':['idle','walk','sound'],'item':['icon','wear','floor'],'spell':['effect','cast_sound'],'map':['tile','bgm']}[c['category']]
        for action in kinds:
            directions=[0,1,2,3] if action in ['idle','walk','attack','hit','death','wear'] else [None]
            for direction in directions:asset_gaps.append(dict(content_id=c['content_id'],content_name=c['name'],category=c['category'],required_action=action,direction=direction,asset_id=None,frame_numbers=None,palette_id=None,status='NOT_MAPPED',early_scope=c.get('production_stage')=='LEVEL_1_30'))
    for scope in ['전사','도적','주술사','도사']:
        for action in ['idle','walk','attack','cast','hit','death']:
            for direction in [0,1,2,3]:asset_gaps.append(dict(content_id='player.'+scope,content_name=scope,category='player',required_action=action,direction=direction,asset_id=None,frame_numbers=None,palette_id=None,status='NOT_MAPPED',early_scope=True))
    writel('ASSET_BINDING_GAPS.jsonl',asset_gaps);writel('CONTENT_FIELD_MATRIX.jsonl',content_gaps)
    writej('FEATURE_SUMMARY.json',dict(total_features=len(features),source_code_reference_features=sum(f['code_status']=='EXTERNAL_CODE_REFERENCE_FOUND' for f in features),stub_features=sum(f['code_status']=='EXTERNAL_STUB_ONLY' for f in features),code_review_gaps=[f['feature_id'] for f in features if f['code_status'] in ['NEEDS_TARGETED_CODE_REVIEW','NO_CONFIRMED_CODE_PATH']],needs_own_implementation_or_adaptation=len(features),gameplay_unverified=len(features),asset_binding_gaps=len(asset_gaps),content_field_mapping_gaps=sum(r['status']=='NEEDS_MAPPING_OR_IMPLEMENTATION' for r in content_gaps)))
    def evidence(root,file,description):
        path=root/file
        return dict(path=file,sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,description=description,status='READ_BYTES_STATIC_ONLY' if path.exists() else 'BLOCKED_MISSING_FILE')
    rtk=private/'repos/unkmc/RTK-Server';java=private/'repos/bosbabi168-cpu/RTK-java-version';com=private/'extracted/CoM_NexusTK_Private_Server_Core_Files'
    comparison=[
     dict(project='Project1998',version='2026 reconstruction targeting NA4.95; not proven KR1998~2001',commit='36905428ff59329be28c6a4579e41f4fd9e9a967',reuse='NO_ROOT_LICENSE_REFERENCE_ONLY',evidence=[evidence(upstream,'game-data/LevelExp.csv','Cumulative threshold for L -> L+1; no subtraction on level up'),evidence(upstream,'game-data/PathGrowth.csv','Upper growth bound exclusive in Random.Next; data normalizes to inclusive max minus one'),evidence(upstream,'Server/Session.Items.cs','S weapon roll and class/strength terms; NA-specific interpretation'),evidence(upstream,'Server/Combat.cs','Damage floor once after (100+max(AC,floor))/100; human floor -80, mob -95'),evidence(upstream,'Server/NpcAbility.cs','RepairAbility exists but is only a stub; code presence is not working repair')],KR_comparison='Rabbit XP5 and squirrel XP2001=10 partly match; squirrel blend7.5; HP/AI/full entity match unverified',gameplay_status='NOT_RUN_THIS_WORK'),
     dict(project='Baram Legacy',version='Undated later catalogue; not a playable server',commit='d4c6aab686baab4b338c217965f549b169f18036',reuse='NO_ROOT_LICENSE_REFERENCE_ONLY',evidence=[evidence(private/'repos/mun5424/Baram_Legacy','app/models/monster.rb','Imports a catalogue; no real combat/level calculator found'),evidence(private/'repos/mun5424/Baram_Legacy','app/assets/images/monsters/monsters.xlsx','619 body rows, rabbit XP5 and squirrel XP10; labels include pre5.50 and post-era references'),evidence(private/'repos/mun5424/Baram_Legacy','app/assets/images/monsters/items.xlsx','2180 body rows; identity/image IDs rather than complete item stats')],KR_comparison='Catalogue names and selected XP are reference evidence, not 1998 runtime proof',gameplay_status='NOT_RUN'),
     dict(project='RTK/Mithia later branch',version='Later 7.x lineage; balance not assumed equal to NA4.95 or KR',commit='e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6',reuse='NO_ROOT_LICENSE_REFERENCE_ONLY',evidence=[evidence(rtk,'rtklua/Accepted/Scripts/swingDamage.lua','Bosses can use L damage; invisibility9; differs from P1998 S-only/invisibility5'),evidence(rtk,'rtklua/Accepted/player.lua','Repair coefficient0.5, ceil; role and duration semantics differ')],KR_comparison='Foreign replacement only; do not average this with Korean source values',gameplay_status='NOT_RUN'),
     dict(project='CoM/Mithia',version='2014 archive',archive_sha256='b077718f31f74d666fb3487f582279a11be535e0f081d6920d3acbd8658f072d',reuse='NO_PERMISSION_REFERENCE_ONLY',evidence=[evidence(com,'mithialua/Accepted/player.lua','Repair coefficient0.30 versus RTK0.5; equal-gold boundary differs across repair routines'),evidence(com,'mithialua/formulae.txt','Hit/crit/regen formulas are later design notes, not contemporary Korean measurements')],KR_comparison='Must stay independent of KR year profiles',gameplay_status='NOT_RUN'),
     dict(project='Java RTK',version='2026 Java port; RTK2 own protocol, separate libGDX client',commit='fec7b36bae0b18471391d652d35a96793cf0be5a',reuse='NO_VERIFIED_REUSE_PERMISSION',evidence=[evidence(java,'src/org/rtk/map/Pc.java','Checks cumulative class level threshold, delegates actual growth to onLevel Lua'),evidence(java,'luascript/Accepted/Scripts/swingDamage.lua','Lua gameplay implementation is separate from Java transport'),evidence(java,'src/org/rtk/map/Combat.java','Delegates damage to script, not an independent old-Korean damage formula')],KR_comparison='Native4.95 compatibility and Korean data not proven',gameplay_status='NOT_RUN')]
    originals=json.loads((ROOT/'research/world-audit/acquired-original-files.json').read_text())
    for label,filename in [('한국4.91','491v.zip'),('NexusTK4.03','NexusTK_v4.0.3.7z'),('NexusTK4.66','NexusTK_V_4.66.7z'),('NexusTK4.95','nexus495.exe')]:
        record=next(r for r in originals if r['filename']==filename)
        comparison.append(dict(project=label,version=record['version'],archive_sha256=record['sha256'],urls=record['urls'],reuse=record['reuse'],KR_comparison='Client archive does not establish server XP/HP/price/drop formulas; asset identity and rendering remain separate',gameplay_status='NOT_RUN'))
    writej('SERVER_KR_COMPARISON.json',comparison)
    ledger=json.loads((OUT/'SOURCE_VERSION_RIGHTS_LEDGER.json').read_text())
    ledger['original_archives']=originals
    ledger['external_repositories']=json.loads((ROOT/'research/community-audit/repository-audit.json').read_text())['repositories']
    ledger['current_recovery_manifest']='INPUT_RECOVERY.json'
    ledger['explicit_profile_categories']=['KR_1998','KR_1999','KR_2000','KR_2001','NA_LEGACY_CLIENT','NA_RESTORATION','LATER_MITHIA_RTK','LATER_CLASSIC_REFERENCE','DEV_ESTIMATE','KR_BLEND_USER_MEAN']
    writej('SOURCE_VERSION_RIGHTS_LEDGER.json',ledger)
    writej('DEVELOPMENT_PATH_COMPARISON.json',dict(stage=5,decision='NOT_MADE_WORK_PREPARATION_ONLY',options=[
      dict(path='Original client + local server',candidates=['NA4.95 + Project1998','KR4.91 + adapted server'],benefit='Existing original renderer/input/protocol',blockers=['NA4.95 payload extraction and real client test','KR4.91 protocol and Korean fonts/text compatibility','Original assets and external server public-reuse permissions','Repair and Korean content still require implementation']),
      dict(path='Independent offline runtime/client',candidates=['Own runtime with permitted MIT DAT/EPF tools'],benefit='Single-process offline save and replaceable version profiles',blockers=['Implement renderer/input/UI/combat/NPC/store','Bind and verify all assets and map collision','Use permitted resources or replace assets before public packaging'])],order='Stage4 asset decode/binding evidence -> stage5 path decision -> stage6 working beginner loop'))
    print(json.dumps(dict(prepared_test_definitions=len(tests),actual_test_runs=0,features=len(features),unmapped_asset_requirements=len(asset_gaps),comparisons=len(comparison)),ensure_ascii=False))

if __name__=='__main__':main()
