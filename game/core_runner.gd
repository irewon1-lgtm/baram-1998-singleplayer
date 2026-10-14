extends SceneTree
## Short actual Godot system tests. Synthetic definitions never count as content.
const Rules=preload("res://rules.gd")
const Store=preload("res://save_store.gd")
const Precision=preload("res://precision.gd")
const Effects=preload("res://effect_runtime.gd")
const Pathfinder=preload("res://pathfinder.gd")
var checks=[]
var private_folder=""
var report=""
var rules=Rules.new()

func verify(ok: bool,id: String,details={}):
    checks.append({"id":id,"result":"PASS" if ok else "FAIL","observed":details})
    print("CORE_CHECK "+id+" "+("PASS" if ok else "FAIL"))

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--private="):private_folder=arg.trim_prefix("--private=")
        if arg.begins_with("--report="):report=arg.trim_prefix("--report=")
    call_deferred("run")

func run():
    DirAccess.make_dir_recursive_absolute(private_folder)
    var store=Store.new()
    var p=rules.new_player("전사","코드시험용")
    var item={"id":"test.item.blade","category":"item","name":"합성 검사 검","job":null,"values":{"damage_min":3,"damage_max":5,"stack_limit":1,"slot":"weapon","instance_equipment":true,"durability":100}}
    rules.contents.append(item);rules.by_id[item.id]=item;rules.rebuild_indexes()
    verify(rules.actions.exchange(p,-5,{item.id:2},"buy-1").ok,"instance-equipment-two-purchased")
    var ids=rules.actions.instances(p,item.id)
    verify(ids.size()==2 and ids[0]!=ids[1],"instance-ids-distinct")
    var old=p.duplicate(true)
    verify(rules.actions.exchange(p,-5,{item.id:2},"buy-1").ok and p==old,"transaction-event-idempotent")
    verify(not rules.actions.exchange(p,-999,{"도토리":1}).ok and p==old,"money-item-atomic-failure")
    verify(rules.actions.equip_instance(p,ids[0]).ok,"equip-specific-instance")
    var enhancement={"id":"test.item.enhance","applicable_item_ids":[item.id],"stages":[{"from_level":0,"gold_cost":3,"materials":[{"item_id":"도토리","quantity":1}],"outcomes":[{"result":"success","to_level":1,"bonuses":{"damage":2},"ratio":{"numerator":1,"denominator":1}}]}]}
    verify(rules.add_item(p,"도토리",2),"material-given-through-common-api")
    verify(rules.actions.enhance(p,ids[0],enhancement,"enhance-1").ok,"enhancement-cost-outcome-transaction")
    verify(p.equipment_instances[ids[0]].enhancement_level==1 and p.equipment_instances[ids[1]].enhancement_level==0 and item.values.damage_max==5,"one-gear-upgrade-definition-and-other-gear-unchanged")
    old=p.duplicate(true)
    verify(rules.actions.enhance(p,ids[0],enhancement,"enhance-1").ok and p==old,"enhancement-duplicate-event-no-cost-or-repeat")
    enhancement.stages[0].gold_cost=999
    var rng=rules.rng.state
    verify(not rules.actions.enhance(p,ids[1],enhancement,"enhance-fail").ok and p==old and rng==rules.rng.state,"enhancement-failure-state-and-rng-preserved")
    verify(rules.actions.equipped_bonus(p,"damage")==2,"individual-enhancement-affects-actual-equipment-rules")
    verify(rules.actions.unequip(p,"weapon").ok and p.equipped=="","unequip-common-api")
    var quest={"objectives":[{"id":"kill","type":"kill","target_id":"test.monster.one","quantity":2}],"consume":[],"rewards":{"gold":7,"experience":1,"items":[]},"repeat":{"enabled":true,"cooldown_ms":300}}
    verify(rules.actions.accept_quest(p,"test.quest.repeat",quest).ok,"quest-start")
    rules.actions.quest_event(p,"kill","test.monster.one",2)
    var gold=p.gold
    verify(rules.actions.claim_quest(p,"test.quest.repeat").ok and p.gold==gold+7,"quest-event-objective-and-reward")
    old=p.duplicate(true)
    verify(not rules.actions.claim_quest(p,"test.quest.repeat").ok and p==old,"quest-claim-duplicate-safe")
    verify(not rules.actions.accept_quest(p,"test.quest.repeat",quest).ok,"repeat-cooldown-milliseconds")
    Effects.tick(rules.actions,p,0.301)
    verify(rules.actions.accept_quest(p,"test.quest.repeat",quest).ok and p.quest_progress["test.quest.repeat"].round==2,"legitimate-repeat-new-round")
    rules.actions.quest_event(p,"kill","test.monster.one",2)
    verify(rules.actions.claim_quest(p,"test.quest.repeat").ok,"repeat-reward-not-mistaken-for-duplicate")
    var target={"id":"test.monster.one/instance1","hp":10,"hp_max":10,"mp":0,"mp_max":0}
    var other=target.duplicate(true);other.id="test.monster.one/instance2"
    var effects=[{"type":"damage","amount":3,"target":"enemy"}]
    verify(Effects.apply(rules.actions,p,[target],effects).ok and target.hp==7 and other.hp==10,"effect-instance-target-isolated")
    old=p.duplicate(true)
    var before=target.duplicate(true)
    verify(not Effects.apply(rules.actions,p,[target],[{"type":"damage","amount":3,"target":"enemy"},{"type":"unknown"}]).ok and p==old and target==before,"unknown-effect-entire-group-refused")
    verify(Effects.apply(rules.actions,p,[],[{"type":"status","status_id":"test-poison","duration_ms":2000,"tick_ms":300,"amount":1}]).ok,"status-duration-tick-declared")
    var hp=p.hp
    Effects.tick(rules.actions,p,0.301)
    verify(p.hp==hp-1,"status-real-state-tick")
    verify(Effects.apply(rules.actions,p,[],[{"type":"remove_status","status_id":"test-poison"}]).ok and not p.statuses.has("test-poison"),"cure-removes-actual-status")
    var advance={"name":"시험 승급","rank":1,"job":"전사","conditions":{"level_min":99,"hp_min":70,"mp_min":20,"gold_cost":2},"quest_id":"test.quest.repeat","granted_skill_ids":["test.skill.rank1"]}
    verify(not rules.actions.advance(p,"test.quest.rank",advance).ok,"advancement-low-level-refused")
    p.level=99;p.hp_max=100;p.hp=100;p.mp_max=30;p.mp=30
    verify(rules.actions.advance(p,"test.quest.rank",advance,"rank-1").ok and p.rank==1 and "test.skill.rank1" in p.skills,"advancement-stats-quest-cost-unlock")
    old=p.duplicate(true)
    verify(not rules.actions.advance(p,"test.quest.rank",advance).ok and p==old,"rank-duplicate-no-cost")
    verify(Precision.half_away(137.5)==138 and Precision.half_away(-137.5)==-138,"shared-half-away-rounding")
    verify(Precision.valid_ratio({"numerator":1,"denominator":1000000000}),"rare-ratio-not-zero")
    var no_drop=[{"ratio":{"numerator":1,"denominator":2},"item_id":"one"},{"ratio":{"numerator":1,"denominator":2},"item_id":""}]
    var max_items=0
    for i in range(100):max_items=maxi(max_items,Precision.draw(rules.rng,"exclusive",no_drop).items.size())
    verify(max_items==1,"exclusive-never-independent-double-drop")
    verify(not Precision.draw(rules.rng,"exclusive",[no_drop[0]]).ok,"exclusive-no-drop-must-be-explicit")
    verify(Precision.draw(rules.rng,"weighted",[{"weight":1},{"weight":3}]).ok,"weights-separate-from-probability")
    var walk=Pathfinder.search(Vector2i.ZERO,Vector2i(3,3),func(v,d):return v.x>=0 and v.y>=0 and v.x<5 and v.y<5,32)
    verify(walk.status=="FOUND" and walk.path.size()==6,"bounded-path-shortest-route")
    var blocked=Pathfinder.search(Vector2i.ZERO,Vector2i(999,999),func(v,d):return true,16)
    verify(blocked.status=="BUDGET_EXCEEDED" and blocked.visited<=16,"unreachable-search-always-terminates")
    var state={"player":p,"world":{},"loot":[],"rng_state":str(rules.rng.state),"content_version":"test-content-manifest"}
    var path=private_folder.path_join("system-save.json")
    verify(store.write_state(path,state),"schema2-verified-atomic-write")
    var loaded=store.read_state(path)
    verify(not loaded.is_empty() and loaded.player.equipment_instances==p.equipment_instances and loaded.player.quest_progress==p.quest_progress and loaded.player.rank==1,"gear-quest-rank-save-reload-preserved")
    var original=JSON.stringify({"schema":1,"payload":JSON.stringify(state),"sha256":JSON.stringify(state).sha256_text()})
    var legacy=private_folder.path_join("legacy-copy.json");store.write_bytes(legacy,original)
    loaded=store.read_state(legacy)
    verify(not loaded.is_empty() and FileAccess.get_file_as_string(legacy)==original,"legacy-read-migration-does-not-write-original")
    verify(store.write_state(legacy,loaded) and FileAccess.get_file_as_string(legacy+".legacy-v1.backup")==original,"legacy-rewrite-retains-exact-original-backup")
    verify(int(JSON.parse_string(FileAccess.get_file_as_string(legacy+".backup")).schema)==2,"old-reader-cannot-fallback-to-schema1-backup")
    var future=private_folder.path_join("future.json");store.write_bytes(future,JSON.stringify({"schema":99,"payload":"{}","sha256":""}));store.write_bytes(future+".backup",original)
    verify(store.read_state(future).is_empty() and store.last_status=="UNSUPPORTED_FUTURE","future-version-no-old-backup-downgrade")
    var future_bytes=FileAccess.get_file_as_string(future)
    verify(not store.write_state(future,state) and FileAccess.get_file_as_string(future)==future_bytes,"future-version-cannot-overwrite")
    var damaged=private_folder.path_join("damaged.json");store.write_bytes(damaged,"corrupt")
    verify(store.read_state(damaged).is_empty() and FileAccess.get_file_as_string(damaged)=="corrupt","damaged-save-safe-failure")
    var passed=checks.filter(func(c):return c.result=="PASS").size()
    var output={"status":"PASS" if passed==checks.size() else "FAIL","scope":"ACTUAL_GODOT_COMMON_SYSTEMS_SYNTHETIC_TEST_DATA_NOT_GUI_OR_NATURAL_LEVELING","checks":checks,"executed":checks.size(),"pass":passed,
        "source_sha256":{"rules":FileAccess.get_sha256("res://rules.gd"),"actions":FileAccess.get_sha256("res://core_actions.gd"),"store":FileAccess.get_sha256("res://save_store.gd"),"effects":FileAccess.get_sha256("res://effect_runtime.gd")}}
    var f=FileAccess.open(report,FileAccess.WRITE);f.store_string(JSON.stringify(output,"  "));f.close()
    rules=null
    quit(0 if passed==checks.size() else 1)
