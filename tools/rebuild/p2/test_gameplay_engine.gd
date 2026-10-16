extends SceneTree
## Engine isolation fixtures, explicitly not historical data or natural leveling.
const EngineState = preload("res://state/gameplay_state.gd")
var checks: Array=[]
var failures := 0
var sequence := 0
var game
func check(id: String,good: bool,detail: Variant=null) -> void:
	checks.append({"id":id,"result":"PASS" if good else "FAIL","detail":detail})
	if not good: failures+=1
func command(type: String,extra: Dictionary={}) -> Dictionary:
	sequence+=1
	var cmd: Dictionary={"type":type,"request_id":"unit:"+str(sequence)}
	cmd.merge(extra)
	return game.command(cmd)
func fixture() -> Dictionary:
	var maps: Dictionary={"test:town":{"id":"test:town","width":10,"height":10,"blocked":[[0,0],[0,1],[0,2]],"exits":[{"x":8,"y":3,"to_map":"test:field","to_x":1,"to_y":3,"direction":1}],"spawns":[{"id":"spawn:a","monster_id":"monster:a","x":3,"y":3}]},"test:field":{"id":"test:field","width":10,"height":10,"blocked":[[6,6]],"exits":[{"x":0,"y":3,"to_map":"test:town","to_x":7,"to_y":3,"direction":3}],"spawns":[]}}
	var npcs: Dictionary={"npc:shop":{"id":"npc:shop","name":"검산상인","map_id":"test:town","x":2,"y":1,"services":["shop","repair","heal"],"heal_cost":5,"repair_cost_per_point":1.0,"shop":{"item:sword":{"buy_price":10,"sell_price":3},"item:acorn":{"buy_price":null,"sell_price":2}},"dialogue":{"greeting":"검산용 상점입니다."}}}
	var jobs: Array=["전사","도적","주술사","도사"]
	var skills: Dictionary={}
	for i in range(4):
		var id: String="npc:job"+str(i)
		npcs[id]={"id":id,"name":jobs[i]+"사범","map_id":"test:town","x":5,"y":2+i,"job":jobs[i],"services":["change_job","teach_skill"],"shop":{},"dialogue":{"greeting":jobs[i]+" 길드입니다."}}
		var skill_id: String="skill:heal"+str(i)
		skills[skill_id]={"id":skill_id,"name":jobs[i]+"기원","job":jobs[i],"learn_level":5+i,"learn_money":5,"ingredients":{"item:acorn":2},"kind":"heal","mp_cost":3,"power":20,"range":1,"cooldown":0.8,"impact_delay":0.25,"teacher_ids":[id],"effect_id":i,"sound_id":i}
	skills["skill:fire"]={"id":"skill:fire","name":"검산화염","job":"주술사","guardian":"주작","learn_level":6,"learn_money":0,"ingredients":{"item:acorn":1},"kind":"damage","mp_cost":5,"power":25,"range":4,"cooldown":0.8,"impact_delay":0.3,"teacher_ids":["npc:job2"],"effect_id":5,"sound_id":5}
	skills["skill:return"]={"id":"skill:return","name":"검산귀환","job":"common","learn_level":5,"learn_money":0,"ingredients":{"item:acorn":1},"kind":"return","mp_cost":2,"power":0,"range":0,"cooldown":0.5,"impact_delay":0.2,"teacher_ids":npcs.keys().filter(func(id): return str(id).begins_with("npc:job"))}
	return {"schema":"baram.p3.gameplay-definitions/1","profile":"TEST_ENGINE_FIXTURE_NOT_HISTORICAL","maps":maps,"npcs":npcs,"items":{"item:sword":{"id":"item:sword","name":"검산검","slot":"weapon","attack":6,"defense":0,"durability":100,"stack_max":1},"item:acorn":{"id":"item:acorn","name":"검산도토리","durability":0,"stack_max":99},"item:food":{"id":"item:food","name":"검산음식","hp_restore":10,"durability":0,"stack_max":99}},"monsters":{"monster:a":{"id":"monster:a","name":"검산토끼","hp":10,"attack":3,"xp":10,"aggression":"retaliate","move_interval":1000.0,"attack_interval":1.0,"respawn_seconds":2.0,"drops":[{"item_id":"item:acorn","chance":1.0,"quantity_min":1,"quantity_max":1}],"money_min":2,"money_max":2}},"skills":skills,"start":{"map_id":"test:town","x":2,"y":3,"money":0,"hp":50,"mp":25,"starter_items":[{"item_id":"item:sword","quantity":1}]},"gates":{"east":{"map_id":"test:town","x":7,"y":3},"west":{"map_id":"test:town","x":1,"y":3},"north":{"map_id":"test:town","x":2,"y":0},"south":{"map_id":"test:town","x":2,"y":8}},"respawn":{"map_id":"test:town","x":2,"y":7},"xp_thresholds":[0,10,20,30,40,50,60,70,80,90],"config":{"base_attack":4,"attack_windup":0.15,"attack_interval":0.5,"move_interval":0.1,"inventory_slots":8,"regen_interval":1000.0,"hp_per_level":8,"mp_per_level":6}}
func new_game() -> void:
	game=EngineState.new();sequence=0
	check("fixture_configures",game.configure(fixture()))
	check("new_character_created",game.create_character("검산캐릭","owner:test",{"seed":12345,"guardian":"주작"}).status=="OK")
func set_fixture(values: Dictionary={}) -> void:
	var payload: Dictionary=game.snapshot()
	for key in values: payload.character[key]=values[key]
	check("explicit_branch_fixture_restores",game.restore(payload).status=="OK")
func _initialize() -> void:
	new_game()
	check("level1_commoner_zero_xp_no_skills",game.state.character.level==1 and game.state.character.xp==0 and game.state.character.job=="commoner" and game.state.skills.is_empty())
	var before: String=JSON.stringify(game.state)
	check("unknown_command_refused",command("unknown").status=="REFUSED")
	check("refusal_mutates_nothing",before==JSON.stringify(game.state))
	check("nonmonotonic_request_rejected",game.command({"type":"move","request_id":"nonnumeric","dx":1,"dy":0}).reason=="REQUEST_ID_MONOTONIC_SEQUENCE_REQUIRED")
	check("malformed_move_refused",command("move",{"dx":0.5,"dy":0}).status=="REFUSED")
	check("cancel_no_state_change",command("cancel").status=="CANCELLED" and before==JSON.stringify(game.state))
	var initial_attack: int=int(game.derived_stats().attack)
	var weapon: String=str(game.state.inventory[0].instance_id)
	check("equip_owned_weapon",command("equip",{"instance_id":weapon}).status=="OK")
	check("equipment_changes_authoritative_attack",int(game.derived_stats().attack)>initial_attack)
	var attack: Dictionary=command("attack",{"target_id":"spawn:a"})
	check("attack_scheduled_no_instant_hp_change",attack.status=="OK" and int(game.state.monsters["spawn:a"].hp)==10)
	check("attack_spam_refused",command("attack",{"target_id":"spawn:a"}).reason=="ACTION_COOLDOWN")
	var after_start: Dictionary=game.snapshot()
	var death: Dictionary=game.tick(0.2)
	check("impact_changes_hp_kills_grants_xp_drop",not game.state.monsters["spawn:a"].alive and game.state.character.xp==10 and game.state.loot.size()==1 and game.state.character.money==2,death.events)
	var died_xp: int=int(game.state.character.xp)
	game.tick(0.5)
	check("reward_not_duplicated_by_frames",game.state.character.xp==died_xp)
	var loot_id: String=str(game.state.loot[0].loot_id)
	var request: String="pickup:1"
	var pickup: Dictionary=game.command({"type":"pickup","request_id":request,"loot_id":loot_id})
	check("actual_loot_pickup",pickup.status=="OK" and game.item_count("item:acorn")==1 and game.state.loot.is_empty())
	var picked: String=JSON.stringify(game.state)
	check("duplicate_pickup_idempotent",game.command({"type":"pickup","request_id":request,"loot_id":loot_id}).status=="DUPLICATE" and picked==JSON.stringify(game.state))
	check("second_pickup_refused_no_duplication",command("pickup",{"loot_id":loot_id}).reason=="LOOT_NOT_FOUND")
	var clone=EngineState.new();clone.configure(fixture());check("pending_action_snapshot_restores",clone.restore(after_start).status=="OK")
	clone.tick(0.2)
	check("save_at_windup_applies_impact_once",clone.state.character.xp==10 and clone.state.loot.size()==1)
	var partition=EngineState.new();partition.configure(fixture());partition.restore(after_start)
	for i in range(4): partition.tick(0.05)
	check("frame_partition_same_rng_reward",partition.state.character.xp==clone.state.character.xp and partition.state.rng_state==clone.state.rng_state and partition.state.loot==clone.state.loot)
	game.tick(2.0)
	check("monster_respawns_once_new_generation",game.state.monsters["spawn:a"].alive and int(game.state.monsters["spawn:a"].generation)==1)
	set_fixture({"x":2,"y":2})
	check("talk_returns_real_npc_dialogue",command("talk",{"npc_id":"npc:shop"}).events[0].text=="검산용 상점입니다.")
	var trade_before: String=JSON.stringify(game.state)
	check("unaffordable_buy_refused",command("buy",{"npc_id":"npc:shop","item_id":"item:sword","quantity":1}).reason=="INSUFFICIENT_MONEY")
	check("failed_purchase_atomic",trade_before==JSON.stringify(game.state))
	check("zero_quantity_refused",command("buy",{"npc_id":"npc:shop","item_id":"item:sword","quantity":0}).reason=="INVALID_QUANTITY")
	check("buy_only_item_not_sold",command("buy",{"npc_id":"npc:shop","item_id":"item:acorn","quantity":1}).reason=="NOT_FOR_SALE")
	var acorn_instance: String=""
	for item in game.state.inventory:
		if item.item_id=="item:acorn": acorn_instance=item.instance_id
	check("merchant_buys_dropped_item",command("sell",{"npc_id":"npc:shop","instance_id":acorn_instance,"quantity":1}).status=="OK" and game.state.character.money==4 and game.item_count("item:acorn")==0)
	set_fixture({"money":100,"hp":10,"mp":1})
	var buy: Dictionary=command("buy",{"npc_id":"npc:shop","item_id":"item:sword","quantity":1})
	check("purchase_cost_and_item_atomic",buy.status=="OK" and game.state.character.money==90 and game.state.inventory.size()==2)
	check("equipped_item_sale_refused",command("sell",{"npc_id":"npc:shop","instance_id":weapon,"quantity":1}).reason=="UNEQUIP_FIRST")
	check("inn_heal_cost_and_recovery",command("heal",{"npc_id":"npc:shop"}).status=="OK" and game.state.character.money==85 and game.state.character.hp==game.state.character.hp_max and game.state.character.mp==game.state.character.mp_max)
	for job_index in range(4):
		var job: String=["전사","도적","주술사","도사"][job_index]
		var teacher: String="npc:job"+str(job_index)
		var skill_id: String="skill:heal"+str(job_index)
		new_game()
		var payload: Dictionary=game.snapshot()
		payload.character.x=4;payload.character.y=2+job_index;payload.character.level=4;payload.character.xp=30;payload.character.money=100
		payload.inventory.append({"instance_id":"fixture:acorn","item_id":"item:acorn","quantity":20,"durability":0})
		check("fourjob_fixture_"+job,game.restore(payload).status=="OK")
		check("lv4_job_refused_"+job,command("change_job",{"npc_id":teacher,"job":job}).reason=="LEVEL_TOO_LOW")
		set_fixture({"level":5+job_index,"xp":40+10*job_index})
		check("job_actual_change_"+job,command("change_job",{"npc_id":teacher,"job":job}).status=="OK" and game.state.character.job==job)
		var wrong_teacher: String="npc:job"+str((job_index+1)%4)
		var before_wrong: String=JSON.stringify(game.state)
		check("wrong_teacher_refused_"+job,command("learn",{"npc_id":wrong_teacher,"skill_id":skill_id}).status=="REFUSED" and JSON.stringify(game.state)==before_wrong)
		check("learn_cost_and_material_single_commit_"+job,command("learn",{"npc_id":teacher,"skill_id":skill_id}).status=="OK" and game.state.character.money==95 and game.item_count("item:acorn")==18 and skill_id in game.state.skills)
		var before_repeat: String=JSON.stringify(game.state)
		check("already_learned_no_cost_"+job,command("learn",{"npc_id":teacher,"skill_id":skill_id}).reason=="ALREADY_LEARNED" and JSON.stringify(game.state)==before_repeat)
		set_fixture({"hp":10})
		var mp: int=int(game.state.character.mp)
		check("cast_commits_mp_"+job,command("cast",{"skill_id":skill_id}).status=="OK" and game.state.character.mp==mp-3 and game.state.character.hp==10)
		game.tick(0.3)
		check("actual_delayed_heal_"+job,game.state.character.hp==30)
		check("unlearned_spell_not_castable_"+job,command("cast",{"skill_id":"skill:fire","target_id":"spawn:a"}).reason=="SKILL_NOT_LEARNED")
	# End-to-end directional return on learnt skill, then strict restored state.
	new_game()
	var p: Dictionary=game.snapshot()
	p.character.x=4;p.character.y=4;p.character.level=6;p.character.xp=50;p.character.money=100
	p.inventory.append({"instance_id":"fixture:acorn","item_id":"item:acorn","quantity":20,"durability":0})
	game.restore(p)
	command("change_job",{"npc_id":"npc:job2","job":"주술사"})
	set_fixture({"guardian":"청룡"})
	var before_guardian: String=JSON.stringify(game.state)
	check("wrong_guardian_refused_without_cost",command("learn",{"npc_id":"npc:job2","skill_id":"skill:fire"}).reason=="WRONG_GUARDIAN" and JSON.stringify(game.state)==before_guardian)
	set_fixture({"guardian":"주작"})
	check("matching_guardian_skill_learns",command("learn",{"npc_id":"npc:job2","skill_id":"skill:fire"}).status=="OK")
	command("learn",{"npc_id":"npc:job2","skill_id":"skill:return"})
	var before_missing_direction: String=JSON.stringify(game.state)
	check("return_requires_direction_without_cost",command("cast",{"skill_id":"skill:return"}).reason=="DIRECTION_REQUIRED" and before_missing_direction==JSON.stringify(game.state))
	for direction in ["east","west","south","north"]:
		var result: Dictionary=command("cast",{"skill_id":"skill:return","direction":direction})
		check("return_cast_"+direction,result.status=="OK")
		game.tick(0.6)
		var gate: Dictionary=game.data.gates[direction]
		check("actual_direction_destination_"+direction,game.state.character.map_id==gate.map_id and game.state.character.x==gate.x and game.state.character.y==gate.y)
	var immutable: String=JSON.stringify(game.state)
	var other: Dictionary=game.snapshot();other.character.owner_id="owner:other"
	check("owner_mismatch_restore_preserves_state",game.restore(other).status=="OWNER_MISMATCH" and immutable==JSON.stringify(game.state))
	var bad: Dictionary=game.snapshot();bad.character.x=0;bad.character.y=0
	check("blocked_restore_preserves_state",game.restore(bad).status=="DEFERRED" and immutable==JSON.stringify(game.state))
	# Missing impact targets and a changed spawn generation must never receive rewards.
	new_game()
	var lost: Dictionary=game.snapshot()
	command("attack",{"target_id":"spawn:a"})
	lost=game.snapshot();lost.monsters["spawn:a"].x=7;lost.monsters["spawn:a"].y=7
	check("explicit_target_moved_fixture",game.restore(lost).status=="OK")
	var missed: Dictionary=game.tick(0.2)
	check("impact_rechecks_range_no_phantom_hit",game.state.monsters["spawn:a"].hp==10 and game.state.character.xp==0 and game.state.loot.is_empty() and missed.events.any(func(e):return e.type=="attack_missed"))
	new_game()
	command("attack",{"target_id":"spawn:a"})
	var replaced: Dictionary=game.snapshot();replaced.monsters["spawn:a"].generation=1
	game.restore(replaced);game.tick(0.2)
	check("pending_attack_never_hits_respawn_generation",game.state.monsters["spawn:a"].hp==10 and game.state.character.xp==0)
	# A full bag must preserve both payment and the world loot instance on refusal.
	new_game()
	var full: Dictionary=game.snapshot();full.character.x=2;full.character.y=2;full.character.money=100
	for i in range(7): full.inventory.append({"instance_id":"fixture:full"+str(i),"item_id":"item:sword","quantity":1,"durability":100})
	full.loot=[{"loot_id":"fixture:loot","item_id":"item:acorn","quantity":1,"map_id":"test:town","x":2,"y":3}]
	check("full_bag_fixture_restores",game.restore(full).status=="OK")
	var full_before: String=JSON.stringify(game.state)
	check("full_bag_buy_refused_atomically",command("buy",{"npc_id":"npc:shop","item_id":"item:sword","quantity":1}).reason=="INVENTORY_FULL" and full_before==JSON.stringify(game.state))
	check("full_bag_loot_preserved",command("pickup",{"loot_id":"fixture:loot"}).reason=="INVENTORY_FULL" and full_before==JSON.stringify(game.state))
	# Broken weapon remains owned but ceases to contribute; repair pays once.
	new_game()
	command("equip",{"instance_id":game.state.inventory[0].instance_id})
	var working_attack: int=int(game.derived_stats().attack)
	var broken: Dictionary=game.snapshot();broken.inventory[0].durability=0;broken.character.money=10;broken.character.x=2;broken.character.y=2
	check("broken_gear_fixture_restores",game.restore(broken).status=="OK")
	check("broken_gear_no_stat_bonus",int(game.derived_stats().attack)<working_attack)
	var broken_before: String=JSON.stringify(game.state)
	check("insufficient_repair_atomic",command("repair",{"npc_id":"npc:shop","instance_id":game.state.inventory[0].instance_id}).reason=="INSUFFICIENT_MONEY" and broken_before==JSON.stringify(game.state))
	set_fixture({"money":120})
	check("repair_cost_durability_stat_same_state",command("repair",{"npc_id":"npc:shop","instance_id":game.state.inventory[0].instance_id}).status=="OK" and game.state.character.money==20 and game.state.inventory[0].durability==100 and int(game.derived_stats().attack)==working_attack)
	# Death is an actual monster timeline event, not a direct hp=0 shortcut.
	new_game()
	var doomed: Dictionary=game.snapshot();doomed.character.hp=2;doomed.character.money=9;doomed.monsters["spawn:a"].aggro=true
	check("lethal_hit_fixture_restores",game.restore(doomed).status=="OK")
	var death_tick: Dictionary=game.tick(0.3)
	check("actual_monster_impact_death_once",game.state.character.dead and game.state.character.hp==0 and game.state.stats.deaths==1 and death_tick.events.any(func(e):return e.type=="player_died"))
	var dead_before: String=JSON.stringify(game.state)
	check("dead_movement_refused_no_mutation",command("move",{"dx":0,"dy":1}).reason=="CHARACTER_DEAD" and dead_before==JSON.stringify(game.state))
	var inventory_before: String=JSON.stringify(game.state.inventory)
	check("resurrection_safe_destination_resources",command("respawn").status=="OK" and not game.state.character.dead and game.state.character.hp>0 and game.state.character.x==2 and game.state.character.y==7 and game.state.character.money==9 and inventory_before==JSON.stringify(game.state.inventory))
	check("alive_cannot_duplicate_resurrection",command("respawn").reason=="NOT_DEAD")
	# Sequence watermark persists across bounded nonce-history eviction.
	new_game()
	var iid: String=str(game.state.inventory[0].instance_id)
	var ledger_ok := true
	for n in range(2100):
		var result: Dictionary=command("equip",{"instance_id":iid}) if n%2==0 else command("unequip",{"slot":"weapon"})
		if result.status!="OK": ledger_ok=false;break
	check("2100_commands_do_not_permanently_lock",ledger_ok and game.state.applied_request_ids.size()==2048 and int(game.state.request_watermarks.unit)==2100)
	var ledger_state: String=JSON.stringify(game.state)
	check("evicted_old_request_still_idempotent",game.command({"type":"equip","instance_id":iid,"request_id":"unit:1"}).status=="DUPLICATE" and ledger_state==JSON.stringify(game.state))
	var output_path: String=""
	var args:=OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i]=="--report": output_path=args[i+1]
	var summary: Dictionary={"schema":"baram.p3.engine-fixture-tests/1","scope":"Purpose-built engine isolation fixtures; not original values, natural leveling, GUI or device tests","engine":Engine.get_version_info(),"platform":OS.get_name(),"checks":checks,"failures":failures,"status":"PASS" if failures==0 else "FAIL"}
	if not output_path.is_empty():
		var file:=FileAccess.open(output_path,FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(summary,"  ")+"\n")
	print(JSON.stringify(summary))
	quit(0 if failures==0 else 1)
