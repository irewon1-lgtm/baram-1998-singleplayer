extends SceneTree
## Real rules against the activated release; controlled XP is not gameplay.
const Rules=preload("res://rules.gd")
const Registry=preload("res://content_registry.gd")
var rules=Rules.new()
var registry=Registry.new()
var checks=[]
var options={}

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    call_deferred("run")

func check(ok: bool,id: String,observed={}):
    checks.append({"id":id,"result":"PASS" if ok else "FAIL","observed":observed})
    print("PROGRESSION "+id+" "+("PASS" if ok else "FAIL"))

func run():
    check(registry.load_directory(options.content),"active-release-hash-and-assets",registry.last_error)
    if not registry.last_error.is_empty():finish();return
    registry.apply_rules(rules)
    check(not rules.growth("평민",1).is_empty() and rules.growth("평민",1).hp_gain_min==45,"work-novice-growth-resolves-to-save-job-identity")
    var p=rules.new_character("새로운평민","주술사")
    check(p.job=="평민" and p.level==1 and p.skills.is_empty() and p.hotbar==["","",""],"new-character-novice-without-unearned-skills",{"job":p.job,"level":p.level,"skills":p.skills})
    check(rules.equip(p,"목도") and rules.display_name(p.equipped)=="목도","level-1-novice-can-equip-supplied-wooden-weapon")
    check(rules.weapon_attack_profile(p).kind=="melee" and rules.weapon_attack_profile(p).range_tiles==1,"starter-weapon-retains-one-tile-physical-range")
    var unchanged=p.duplicate(true)
    check(not rules.choose_job(p,"주술사").ok and p==unchanged,"job-choice-under-level-5-atomic-refusal")
    check(not rules.learn(p,"kr.spell.cdc9baba76f2") and p==unchanged,"novice-cannot-learn-class-spell")
    p.hotbar[0]="kr.spell.cdc9baba76f2"
    check(not rules.can_cast_skill(p,p.hotbar[0]).ok,"hotbar-does-not-grant-spell-ownership")
    p.hotbar[0]=""
    var levels=rules.award_xp(p,99999999)
    check(p.level==5 and levels==[2,3,4,5] and p.xp2==rules.threshold("평민",4)*2,"novice-stops-at-level-5-and-discards-unearned-overflow",{"level":p.level,"xp2":p.xp2,"gains":levels})
    unchanged=p.duplicate(true)
    check(not rules.choose_job(p,"미구현직업").ok and p==unchanged,"unknown-job-refused-without-state-change")
    var keep={"xp2":p.xp2,"level":p.level,"hp_max":p.hp_max,"mp_max":p.mp_max,"gold":p.gold,"inventory":p.inventory.duplicate(true)}
    check(rules.choose_job(p,"주술사").ok and p.job=="주술사","level-5-explicit-class-selection")
    check(keep.xp2==p.xp2 and keep.level==p.level and keep.hp_max==p.hp_max and keep.mp_max==p.mp_max and keep.gold==p.gold and keep.inventory==p.inventory,"job-selection-keeps-earned-progress-and-inventory")
    check(rules.knows_skill(p,"물품감정") and rules.can_cast_skill(p,"물품감정").ok,"appraisal-auto-granted-on-initial-job-choice")
    unchanged=p.duplicate(true)
    check(not rules.choose_job(p,"전사").ok and p==unchanged,"existing-job-never-reassigned")
    var saved_novice=p.duplicate(true);saved_novice.job="평민";saved_novice.xp2=999999
    rules.award_xp(saved_novice,0)
    check(saved_novice.xp2==999999,"legacy-novice-experience-never-reduced-by-new-cap")
    check(not rules.knows_skill(p,"비영사천문") and not rules.can_cast_skill(p,"비영사천문").ok,"teleport-not-automatically-granted")
    rules.add_item(p,"도토리",30)
    unchanged=p.duplicate(true)
    check(not rules.learn(p,"화염주(화)") and p==unchanged,"mage-offensive-spell-refuses-level-5-before-cost")
    levels=rules.award_xp(p,float(rules.threshold("주술사",5))-float(p.xp2)/2.0)
    check(p.level==6 and levels==[6],"class-progression-resumes-to-level-6-after-choice",{"level":p.level,"growth_log":p.growth_log})
    var acorns=int(p.inventory.get(rules.find_content("item","도토리").id,0))
    check(rules.learn(p,"화염주(화)") and rules.knows_skill(p,"화염주(화)") and int(p.inventory.get(rules.find_content("item","도토리").id,0))==acorns-10,"level-6-mage-spell-learns-with-source-material-cost")
    check(rules.can_cast_skill(p,"kr.spell.cdc9baba76f2").ok,"learned-source-id-spell-passes-use-gate")
    unchanged=p.duplicate(true)
    check(rules.learn(p,"화염주(화)") and p==unchanged,"duplicate-learn-is-idempotent-and-cost-free")
    for job in Rules.JOBS:
        var novice=rules.new_character("각직업검사")
        rules.award_xp(novice,1200)
        check(rules.choose_job(novice,job).ok and novice.job==job and rules.can_cast_skill(novice,"물품감정").ok,"all-four-job-choices-"+job)
        var common=rules.spell_record(novice,"비영사천문")
        check(not common.is_empty() and common.values.allowed_jobs.size()==4,"common-spell-resolves-for-"+job)
    var legacy=rules.new_player("전사","이전저장캐릭터")
    legacy.level=1;legacy.skills.append("kr.spell.cdc9baba76f2");legacy.hotbar[0]="kr.spell.cdc9baba76f2"
    unchanged=legacy.duplicate(true)
    check(not rules.can_cast_skill(legacy,"kr.spell.cdc9baba76f2").ok and legacy==unchanged,"legacy-wrong-class-spell-blocked-without-rewriting-save")
    legacy.skills.append("kr.spell.f4dece63378d")
    unchanged=legacy.duplicate(true)
    check(not rules.can_cast_skill(legacy,"kr.spell.f4dece63378d").ok and legacy==unchanged,"legacy-under-level-spell-retained-but-use-blocked")
    check(rules.can_cast_skill(legacy,"기초 회복").ok,"previously-owned-legacy-training-skill-preserved")
    var ghost=p.duplicate(true)
    ghost.hp=0
    check(not rules.can_cast_skill(ghost,"비영사천문").ok,"dead-character-cannot-bypass-learning")
    var base=Rules.new()
    var old=base.new_player("도사","이전이름저장")
    old.level=5;old.skills.append("누리의기원")
    unchanged=old.duplicate(true)
    registry.apply_rules(base)
    check(base.can_cast_skill(old,"누리의기원").ok and old==unchanged,"old-name-keyed-job-spell-remains-resolvable-without-save-migration")
    finish()

func finish():
    var failed=checks.filter(func(c):return c.result=="FAIL")
    var report={"status":"PASS" if failed.is_empty() else "FAIL","scope":"ACTUAL_GODOT_RULES_CONTROLLED_STATES_NOT_NATURAL_PLAYTHROUGH","content_version":registry.version,"checks":checks,"sources":["KR-1999-U019","KR-1999-U025","KR-2001-0267"]}
    var path=options.get("report","/tmp/baram-progression.json")
    DirAccess.make_dir_recursive_absolute(path.get_base_dir())
    var file=FileAccess.open(path,FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "))
    quit(0 if failed.is_empty() else 1)
