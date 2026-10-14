extends SceneTree
## Short integration checks against the ACTUAL activated Work release.
## Controlled states are not natural levelling or GUI gameplay evidence.
const Rules=preload("res://rules.gd")
const Registry=preload("res://content_registry.gd")
const Effects=preload("res://effect_runtime.gd")
const Store=preload("res://save_store.gd")
var options={}
var checks=[]
var content=Registry.new()
var rules=Rules.new()

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    call_deferred("run")

func verify(ok: bool,id: String,detail={}):
    checks.append({"id":id,"result":"PASS" if ok else "FAIL","observed":detail})
    print("WORK_CHECK "+id+" "+("PASS" if ok else "FAIL"))

func controlled(job="전사") -> Dictionary:
    var p=rules.new_player(job,"통합 검사 전용")
    p.level=99;p.gold=1000000000;p.strength=1000;p.hp_max=1000000;p.mp_max=1000000;p.hp=p.hp_max;p.mp=p.mp_max;p.xp2=1000000000000
    return p

func run():
    verify(content.load_directory(options.content),"active-release-bytes-and-assets",content.last_error)
    if not content.last_error.is_empty():finish();return
    content.apply_rules(rules)
    var world=JSON.parse_string(FileAccess.get_file_as_string(options.assets.path_join("source_maps/world.json")))
    world=content.merge_world(world)
    verify(content.last_error.is_empty(),"original-layout-adapter",content.last_error)
    var maps={};var count={};var errors=[]
    for id in content.records:count[content.records[id].kind]=int(count.get(content.records[id].kind,0))+1
    for m in world.maps:maps[m.id]=m
    for m in world.maps:
        if m.ground.size()!=int(m.height) or m.blocked.size()!=int(m.height):errors.append({"id":m.id,"field":"height"});continue
        for y in range(int(m.height)):
            if m.ground[y].size()!=int(m.width) or m.blocked[y].size()!=int(m.width):errors.append({"id":m.id,"field":"width","y":y})
        for portal in m.portals:
            if not maps.has(portal.target):errors.append({"id":m.id,"portal":portal.get("id",""),"field":"target","value":portal.target});continue
            var target=maps[portal.target];var xy=portal.entry
            if xy.size()!=2 or xy[0]<0 or xy[1]<0 or xy[0]>=int(target.width) or xy[1]>=int(target.height) or target.blocked[int(xy[1])][int(xy[0])]:errors.append({"id":m.id,"portal":portal.get("id",""),"field":"entry","value":xy})
    verify(errors.is_empty(),"runtime-map-cells-and-portals",{"errors":errors,"map_count":maps.size(),"active_definitions":count})
    var visited={};var queue=[world.home.map]
    while not queue.is_empty():
        var id=queue.pop_front()
        if visited.has(id):continue
        visited[id]=true
        for portal in maps[id].portals:
            if not visited.has(portal.target) and maps.has(portal.target):queue.append(portal.target)
    var work_scenes=[]
    for id in content.by_kind("map"):
        if content.definition(id).get("variant_active",true):work_scenes.append(world.map_aliases.get(id,id))
    verify(work_scenes.all(func(id):return visited.has(id)),"all-physical-Work-maps-connected-to-home",{"Work_scenes":work_scenes.size(),"graph_reachable_scenes":visited.size()})
    var steps=[]
    for job in Rules.JOBS:
        var valid=true;var previous=-1
        for level in range(1,100):
            var growth=rules.growth(job,level)
            if growth.is_empty() or int(growth.hp_gain_min)>int(growth.hp_gain_max_inclusive) or int(growth.mp_gain_min)>int(growth.mp_gain_max_inclusive):valid=false
            var next=rules.threshold(job,level)
            if level<99 and next<previous:valid=false
            if level<99:previous=next
        var p=rules.new_player(job,"곡선 검사")
        var gain=rules.award_xp(p,float(previous))
        verify(valid and p.level==99 and gain.size()==98 and rules.threshold(job,99)==-1,"growth-"+job+"-controlled-1-to-99-terminal",{"level":p.level,"gains":gain.size(),"natural_play":"NOT_RUN"})
    errors=[]
    for id in content.by_kind("skill"):
        var check=Effects.validate(Effects.compile_skill(content.definition(id)))
        if not check.ok:errors.append({"id":id,"error":check})
    verify(errors.is_empty(),"all-Work-skill-effect-operators-recognized",{"skills":content.by_kind("skill").size(),"errors":errors})
    var p=controlled()
    var offensive=content.by_kind("skill").filter(func(id):return content.definition(id).target=="enemy" and content.definition(id).effects[0].op=="damage")
    var monster=content.by_kind("monster")[0]
    var victim={"id":"runtime.test.victim","hp":1000000,"hp_max":1000000,"mp":100,"mp_max":100,"statuses":{},"spec":{"values":rules.by_id[monster].values}}
    var old_hp=victim.hp
    var result=Effects.apply(rules.actions,p,[victim],Effects.compile_skill(content.definition(offensive[0])))
    verify(result.ok and victim.hp<old_hp,"actual-Work-offensive-effect-changes-target-health",{"skill_id":offensive[0],"damage":old_hp-victim.hp})
    var healing=content.by_kind("skill").filter(func(id):return content.definition(id).effects[0].op=="heal_hp")[0]
    var spec=content.definition(healing);p=controlled(content.class_title(spec.class_ids[0],rules));p.hp=1
    verify(rules.actions.learn_skill(p,healing,spec).ok or rules.actions.last_error.code=="LEARN_COST","actual-Work-learn-handles-declared-materials",{"skill_id":healing})
    for ingredient in spec.learn.consume:rules.add_item(p,ingredient.item_id,int(ingredient.quantity))
    verify(rules.actions.learn_skill(p,healing,spec).ok,"actual-Work-skill-learning-atomic")
    result=Effects.apply(rules.actions,p,[],Effects.compile_skill(spec))
    verify(result.ok and p.hp>1,"actual-Work-healing-effect-changes-health")
    errors=[]
    for id in content.by_kind("drop_group"):
        var d=content.definition(id);var draw=Rules.Precision.draw(rules.rng,d.mode,d.rolls)
        if not draw.ok:errors.append({"id":id,"error":draw.error})
    verify(errors.is_empty(),"all-Work-drop-ratios-run-with-declared-mode",{"groups":content.by_kind("drop_group").size(),"errors":errors})
    p=controlled();var quest_id="wk.quest.daily.rabbit";var quest=content.definition(quest_id)
    verify(rules.actions.accept_quest(p,quest_id,quest).ok,"actual-Work-repeat-quest-accept")
    rules.actions.quest_event(p,"kill",quest.objectives[0].monster_id,int(quest.objectives[0].count))
    var gold=p.gold
    verify(rules.actions.claim_quest(p,quest_id).ok and p.gold==gold+50,"actual-Work-array-reward-claim")
    var claimed=p.duplicate(true)
    verify(not rules.actions.claim_quest(p,quest_id).ok and p==claimed,"actual-Work-quest-no-double-reward")
    verify(not rules.actions.accept_quest(p,quest_id,quest).ok,"actual-Work-repeat-cooldown")
    p.time_us+=int(quest.repeat.cooldown_ms)*1000
    verify(rules.actions.accept_quest(p,quest_id,quest).ok and p.quest_progress[quest_id].round==2,"actual-Work-repeat-new-round")
    p=controlled("주술사");quest_id="wk.quest.advancement.mage.1";quest=content.definition(quest_id)
    verify(rules.actions.accept_quest(p,quest_id,quest).ok,"actual-Work-advancement-quest-start")
    for objective in quest.objectives:
        if objective.type=="kill":rules.actions.quest_event(p,"kill",objective.monster_id,int(objective.count))
        if objective.type=="collect":rules.add_item(p,objective.item_id,int(objective.count))
    result=rules.actions.claim_quest(p,quest_id)
    verify(result.ok and p.rank==1,"actual-Work-advancement-reward-is-atomic",result)
    var enhancement=content.definition("wk.enhancement.offline_optional")
    p=controlled();var gear_type=enhancement.applicable_item_ids[0]
    verify(rules.actions.exchange(p,0,{gear_type:2}).ok,"actual-Work-two-independent-gear-instances")
    var gear_ids=rules.actions.instances(p,gear_type)
    var old=p.duplicate(true)
    verify(not rules.actions.enhance(p,gear_ids[0],enhancement).ok and p==old,"actual-Work-enhancement-disabled-by-default")
    p.extensions.optional_enhancement=true
    for ingredient in enhancement.stages[0].cost.materials:rules.add_item(p,ingredient.item_id,int(ingredient.quantity))
    result=rules.actions.enhance(p,gear_ids[0],enhancement)
    verify(result.ok and p.equipment_instances[gear_ids[1]].enhancement_level==0,"actual-Work-enhancement-one-instance-only",result)
    p=controlled();var recipe=content.definition("wk.recipe.rabbit_meat");var meat=recipe.consume[0].item_id
    rules.add_item(p,meat,2);p.hp=1
    verify(rules.actions.recipe(p,recipe).ok and p.inventory[meat]==1,"actual-Work-recipe-materials-output-and-cost")
    var expected=int(rules.item(meat).heal_amount)*2
    verify(rules.consume(p,meat) and p.hp==1+expected,"actual-Work-prepared-consumable-keeps-instance-modifier")
    p=controlled();var economy=content.definition("wk.economy.progression");var xp=p.xp2;var maximum=p.hp_max
    verify(rules.actions.experience_exchange(p,economy,0).ok and p.level==99 and p.hp_max==maximum+100 and p.xp2==xp-2000000,"actual-Work-level99-surplus-XP-exchange")
    var store=Store.new();store.content_version=content.version
    var save=options.private.path_join("work-save-copy.json")
    var snapshot={"player":p,"world":{},"loot":[],"clock":0.0,"rng_state":str(rules.rng.state)}
    verify(store.write_state(save,snapshot),"Work-content-version-save-written",store.last_error)
    var restored=store.read_state(save)
    verify(not restored.is_empty() and restored.player==p,"Work-content-save-roundtrip-preserves-state",store.last_error)
    if options.has("legacy"):
        var original_hash=FileAccess.get_sha256(options.legacy)
        var legacy=store.read_state(options.legacy)
        verify(not legacy.is_empty(),"actual-prior-level6-save-copy-read")
        if not legacy.is_empty():
            var prior=legacy.player.duplicate(true)
            rules.actions.ensure(legacy.player)
            verify(prior.level==legacy.player.level and prior.xp2==legacy.player.xp2 and prior.gold==legacy.player.gold and prior.quests==legacy.player.quests and prior.skills==legacy.player.skills,"actual-prior-progress-retained-under-Work-data")
            var destination=options.private.path_join("migrated-prior-save.json")
            verify(store.write_state(destination,legacy),"actual-prior-save-copy-migrated-and-resaved")
            restored=store.read_state(destination)
            verify(not restored.is_empty() and restored.player==legacy.player and FileAccess.get_sha256(options.legacy)==original_hash,"actual-prior-migrated-save-reloads-original-bytes-unchanged")
    var main=load("res://main.gd").new()
    main.rules=rules;main.world=world;main.maps=maps
    var current_spec=rules.monster(monster,world.replacements)
    var home=world.home
    var actor={"id":"test.restore.actor","kind":monster,"map":home.map,"x":home.entry[0],"y":home.entry[1],"home_x":home.entry[0],"home_y":home.entry[1],"alive":false,"hp":0,"hp_max":int(current_spec.values.hp),"mp":0,"mp_max":0,"respawn":4.0,"spec":current_spec}
    main.entities={actor.id:actor.duplicate(true)}
    var stale=actor.duplicate(true);stale.spec.values.hp+=123
    p=rules.new_player("전사","저장 정의 갱신 검사");p.map=home.map;p.x=home.entry[0];p.y=home.entry[1];p.world_revision=world.revision
    main.restore({"player":p,"world":{actor.id:stale},"loot":[],"rng_state":str(rules.rng.state)})
    verify(main.entities[actor.id].spec.values.hp==current_spec.values.hp and not main.entities[actor.id].alive and main.entities[actor.id].respawn==4.0,"saved-monster-instance-rebinds-current-definition-with-progress-preserved")
    main.free()
    var rank_gear="wk.item.exp2.rank1.gear.warrior.weapon"
    if content.records.has(rank_gear):
        p=controlled();rules.add_item(p,rank_gear,1)
        var instance=rules.actions.instances(p,rank_gear)[0];var before=p.duplicate(true)
        verify(not rules.actions.equip_instance(p,instance).ok and p==before,"actual-Work-rank1-equipment-rejects-unadvanced-player-atomically")
        p.rank=1
        verify(rules.actions.equip_instance(p,instance).ok,"actual-Work-rank1-equipment-applies-after-advancement")
        var skill_id="wk.skill.exp2.rank1.warrior.1";var skill=content.definition(skill_id)
        var manual=skill.learn.consume[0].item_id
        p=controlled();p.rank=1;rules.add_item(p,manual,2)
        verify(rules.actions.learn_skill(p,skill_id,skill).ok and p.inventory[manual]==1,"actual-Work-rank1-skill-consumes-one-bound-manual")
        before=p.duplicate(true)
        verify(rules.actions.learn_skill(p,skill_id,skill).ok and p==before,"actual-Work-repeat-skill-learning-consumes-no-second-manual")
        verify(not rules.trade(p,manual,1,100,false) and p==before,"actual-Work-bound-training-manual-cannot-be-sold")
    var rendering=load("res://work_assets.gd").new(content)
    rendering.soft_limit=1
    var sheet_a="wk.asset.kr491.sheet.tilea";var sheet_b="wk.asset.kr491.sheet.tileb"
    var page_a=content.definition(sheet_a).metadata.pages[0].path
    var page_b=content.definition(sheet_b).metadata.pages[0].path
    var page=rendering.texture(sheet_a,page_a);var retained=weakref(page);page=null
    rendering.texture(sheet_b,page_b)
    verify(retained.get_ref()!=null and rendering.frame_textures.size()==2 and rendering.texture_cache.size()==1,"drawn-texture-page-survives-reuse-cache-eviction-until-next-frame")
    rendering.begin_frame()
    rendering.texture(sheet_b,page_b)
    rendering.begin_frame()
    verify(retained.get_ref()==null,"texture-frame-lifetime-references-are-released-on-next-draw")
    finish()

func finish():
    var success=checks.all(func(c):return c.result=="PASS")
    var f=FileAccess.open(options.report,FileAccess.WRITE)
    f.store_string(JSON.stringify({"result":"PASS" if success else "FAIL","content_version":content.version,"checks":checks,"scope":"ACTUAL_WORK_DATA_HEADLESS_CONTROLLED_SYSTEMS_NOT_GUI_OR_NATURAL_PLAY"},"  "));f.close()
    quit(0 if success else 1)
