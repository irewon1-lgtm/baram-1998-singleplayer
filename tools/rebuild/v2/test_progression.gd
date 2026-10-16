extends "res://../../tools/rebuild/p2/test_gameplay_journey.gd"
## Four fresh characters, ordinary production commands/ticks only. No restore,
## state edits, direct grants or altered rules are used by this operator.
## Only navigation/fight helpers are inherited; the parent's run and explicit
## fixture/grant/reload branches are never invoked.
## Completion: earned Lv5+, real sale/purchase/equipment, each job change,
## collected learning materials, learned common return, cast and disk roundtrip.
## Simulation time is accelerated; this is not GUI/manual/device/1-99 proof.
const Game=preload("res://state/gameplay_state.gd")
const Store=preload("res://storage/gameplay_store.gd")
var job_results: Array=[]
var simulated_seconds:=0.0
var total_commands:=0
var run_started:=0
var initial_content_sha:=""
var initial_engine_sha:=""
var initial_store_sha:=""

func advance_time(seconds: float) -> void:
	# Same 50ms fixed-step engine; batching avoids copying a 74-map world on
	# every operator subframe. Calls obey the production five-second cap.
	var remaining:=seconds
	while remaining>0.00001:
		var chunk:=minf(5.0,remaining)
		var result: Dictionary=game.tick(chunk)
		transcript.append({"phase":active_phase,"tick":chunk,"events":result.get("events",[]),"after":brief()})
		remaining-=chunk; simulated_seconds+=chunk

func mark(name: String) -> void:
	var entry:={"name":name,"job":active_phase,"sequence":sequence,"sim_time":game.state.sim_time,"state":brief(),"stats":game.state.stats.duplicate(true)}
	milestones.append(entry)
	print("V2_PROGRESSION "+JSON.stringify(entry))

func hunting_map() -> String:
	for map in records("maps"):
		if str(map.get("id","")).ends_with("south_field") and not map.get("spawns",[]).is_empty(): return str(map.id)
	return ""

func hunt_until(level: int, requirements: Dictionary, money: int) -> bool:
	var field:=hunting_map()
	if field.is_empty(): return false
	var budget:=int(limits.kills)
	while budget>0:
		var enough:=int(char_state().level)>=level and int(char_state().money)>=money
		var wanted:=""
		for id in requirements:
			if item_count(str(id))<int(requirements[id]): enough=false; wanted=str(id); break
		if enough: return true
		if not travel_to(field): return false
		var target:=nearest_monster(wanted)
		if target.is_empty(): advance_time(1.0)
		elif not fight(target): return false
		budget-=1
	return false

func affordable_upgrade() -> Dictionary:
	var current_attack:=0
	for instance in game.state.inventory:
		if game.state.equipment.get("weapon","")==instance.instance_id: current_attack=int(record("items",instance.item_id).get("attack",0))
	var chosen: Dictionary={}
	for npc in records("npcs"):
		if str(npc.map_id) not in ["gp:map:domestic_city","gp:map:forge"]: continue
		for id in npc.get("shop",{}):
			var trade: Dictionary=npc.shop[id]
			var item:=record("items",str(id))
			if trade.get("buy_price")==null or str(item.get("slot",""))!="weapon" or int(item.get("attack",0))<=current_attack or int(item.get("required_level",1))>5: continue
			if item.get("required_job")!=null and str(item.required_job) not in ["","any","전직업","common",str(char_state().job)]: continue
			if not item.get("required_jobs",[]).is_empty() and str(char_state().job) not in item.required_jobs: continue
			if not game._advancement_eligible(item): continue
			var attributes_ok:=true
			for stat in ["strength","dexterity","intelligence"]:
				if int(item.get("required_"+stat,0))>int(game.derived_stats().get(stat,5)): attributes_ok=false
			if not attributes_ok: continue
			if chosen.is_empty() or int(trade.buy_price)<int(chosen.price): chosen={"npc_id":str(npc.id),"item_id":str(id),"price":int(trade.buy_price)}
	return chosen

func sell_earned_to(target: int) -> bool:
	for instance in game.state.inventory.duplicate(true):
		if int(char_state().money)>=target: break
		var npc:=merchant_for(str(instance.item_id),"sell_price")
		if npc.is_empty() or game.state.equipment.values().has(instance.instance_id): continue
		var price:=int(record("npcs",npc).shop[instance.item_id].sell_price)
		if price<=0: continue
		var quantity:=mini(int(instance.quantity),maxi(1,int(ceil(float(target-int(char_state().money))/float(price)))))
		if not approach_npc(npc): return false
		var before:=int(char_state().money)
		var sale:=send({"type":"sell","npc_id":npc,"instance_id":instance.instance_id,"quantity":quantity})
		if not check(active_phase+"_earned_sale_exact",sale.status=="OK" and int(char_state().money)==before+quantity*price,sale): return false
	return int(char_state().money)>=target

func run() -> void:
	run_started=Time.get_ticks_msec()
	var parsed: Variant=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	if not check("actual_current_content_loaded",typeof(parsed)==TYPE_DICTIONARY): finish(); return
	content=parsed; initial_content_sha=FileAccess.get_sha256(content_path)
	initial_engine_sha=FileAccess.get_sha256("res://state/gameplay_state.gd")
	initial_store_sha=FileAccess.get_sha256("res://storage/gameplay_store.gd")
	limits={"commands":50000,"kills":1200,"path_nodes":65536}
	for job in ["전사","도적","주술사","도사"]:
		active_phase=job; sequence=0
		game=Game.new()
		if not check(job+"_current_rules_configure",game.configure(content),game.errors): break
		var created: Dictionary=game.create_character("육성"+job,"fixture:natural-"+str(job.hash()),{"guardian":"주작","desired_job":job,"seed":12345})
		if not check(job+"_new_Lv1_zero_XP_money_skills",created.status=="OK" and char_state().level==1 and char_state().xp==0 and char_state().money==0 and char_state().job=="commoner" and game.state.skills.is_empty(),brief()): break
		var start:=brief()
		var starter_weapon: String=str(game.state.equipment.get("weapon",""))
		var before_attack:=int(game.derived_stats().attack)
		var removed:=send({"type":"unequip","slot":"weapon"})
		var without_attack:=int(game.derived_stats().attack)
		var equipped:=send({"type":"equip","instance_id":starter_weapon})
		if not check(job+"_starter_equipment_uses_real_stats",removed.status=="OK" and equipped.status=="OK" and without_attack<before_attack and int(game.derived_stats().attack)==before_attack): break
		var teacher: String=str(content.get("jobs",{}).get(job,{}).get("teacher_id",teacher_for(job)))
		if not check(job+"_walk_to_teacher_before_training",approach_npc(teacher),brief()): break
		var early:=send({"type":"change_job","npc_id":teacher,"job":job})
		if not check(job+"_Lv1_job_change_refused",early.status=="REFUSED" and early.reason=="LEVEL_TOO_LOW",early): break
		if not check(job+"_ordinary_south_exit_hunting_to_Lv5",hunt_until(5,{},0),brief()): break
		if not check(job+"_earned_XP_matches_kill_ledger",char_state().xp==game.state.stats.total_xp_earned and game.state.stats.kills>0 and game.state.stats.items_picked_up>0,brief()): break
		mark("earned_level5")
		if not check(job+"_walk_to_guild_for_job_change",approach_npc(teacher),brief()): break
		var at_job_level:=int(char_state().level)
		var changed:=send({"type":"change_job","npc_id":teacher,"job":job})
		if not check(job+"_earned_job_change",changed.status=="OK" and char_state().job==job and at_job_level>=5,changed): break
		mark("earned_job_changed")
		var upgrade:=affordable_upgrade()
		if not check(job+"_affordable_hometown_upgrade_exists",not upgrade.is_empty(),upgrade): break
		var acorn:=item_id("도토리")
		# Sale quantities are earned drops; hunt more if the seed's first
		# ordinary kills yielded fewer drops than the purchase requires.
		var sell_price:=int(record("npcs",merchant_for(acorn,"sell_price")).shop[acorn].sell_price)
		var sale_needed:=int(ceil(float(upgrade.price)/float(sell_price)))
		if not check(job+"_hunt_actual_sale_stock",hunt_until(int(char_state().level),{acorn:sale_needed},0),brief()): break
		if not check(job+"_earned_sale_finances_upgrade",sell_earned_to(int(upgrade.price)),brief()): break
		if not check(job+"_walk_to_actual_upgrade_merchant",approach_npc(upgrade.npc_id),brief()): break
		var cash:=int(char_state().money)
		var purchase:=send({"type":"buy","npc_id":upgrade.npc_id,"item_id":upgrade.item_id,"quantity":1})
		if not check(job+"_purchase_uses_only_earned_coins",purchase.status=="OK" and int(char_state().money)==cash-int(upgrade.price),purchase): break
		var owned:=instance_for(upgrade.item_id)
		before_attack=int(game.derived_stats().attack)
		var improved:=send({"type":"equip","instance_id":owned.get("instance_id","")})
		if not check(job+"_purchased_equipment_changes_attack",improved.status=="OK" and int(game.derived_stats().attack)>before_attack,improved): break
		mark("earned_trade_and_equipment")
		var back:=skill_id("비영사천문")
		var definition:=record("skills",back)
		if not check(job+"_common_return_has_real_conditions",not definition.is_empty() and not definition.get("ingredients",{}).is_empty(),definition): break
		if not check(job+"_hunt_full_learning_materials",hunt_until(int(definition.learn_level),definition.ingredients,int(definition.get("learn_money",0))),brief()): break
		if not check(job+"_walk_back_to_actual_skill_teacher",approach_npc(teacher),brief()): break
		var before_materials: Dictionary={}
		for id in definition.ingredients: before_materials[id]=item_count(str(id))
		cash=int(char_state().money)
		var learned:=send({"type":"learn","npc_id":teacher,"skill_id":back})
		var exact:=int(char_state().money)==cash-int(definition.get("learn_money",0))
		for id in before_materials: exact=exact and item_count(str(id))==int(before_materials[id])-int(definition.ingredients[id])
		if not check(job+"_earned_material_learning_exact",learned.status=="OK" and back in game.state.skills and exact,learned): break
		var cast:=send({"type":"cast","skill_id":back,"direction":"south"},float(definition.get("impact_delay",0.25))+0.2)
		var gate: Dictionary=content.gates.south
		if not check(job+"_earned_return_cast_reaches_real_gate",cast.status=="OK" and char_state().map_id==gate.map_id and char_state().x==gate.x and char_state().y==gate.y,cast): break
		mark("earned_learning_and_return")
		var store=Store.new()
		var path:="user://gameplay-p3/v2-natural-tests/"+str(run_started)+"/"+str(job.hash())+".json"
		var saved: Dictionary=store.write_game(path,game.snapshot(),str(char_state().owner_id),content)
		var read: Dictionary=store.read_game(path,str(char_state().owner_id),content)
		if not check(job+"_earned_progress_disk_roundtrip",saved.status=="SAVED" and read.status=="OK" and store._canonical(read.payload)==store._canonical(game.snapshot()),saved): break
		job_results.append({"job":job,"start":start,"job_change_level":at_job_level,"end":brief(),"stats":game.state.stats.duplicate(true),"command_count":sequence,"simulated_seconds":game.state.sim_time,"learned_skill":back,"learning_scope":"common return; unique job-specific late skills tested separately","save_status":saved.status})
		total_commands+=sequence
	check("all_four_natural_job_beginnings_completed",job_results.size()==4,job_results.size())
	check("current_content_unchanged_during_run",initial_content_sha==FileAccess.get_sha256(content_path))
	check("engine_and_store_unchanged_during_run",initial_engine_sha==FileAccess.get_sha256("res://state/gameplay_state.gd") and initial_store_sha==FileAccess.get_sha256("res://storage/gameplay_store.gd"))
	finish()

func finish() -> void:
	var report:={"schema":"baram.v2.four-job-natural-engine-progression/1","status":"PASS" if failures==0 and job_results.size()==4 else "FAIL","failures":failures,"checks":checks,"jobs":job_results,"milestones":milestones,"wall_seconds":float(Time.get_ticks_msec()-run_started)/1000.0,"simulated_seconds":simulated_seconds,"command_count":total_commands,"trace_entries":transcript.size(),"scope":"Four fresh characters; time-accelerated production commands and fixed-step ticks; no direct XP/money/item/skill grants, no fixture restore; not GUI/device/native Windows/Android/1-99 proof","content_sha256":initial_content_sha,"source_fingerprints":{"game_state":FileAccess.get_sha256("res://state/gameplay_state.gd"),"store":FileAccess.get_sha256("res://storage/gameplay_store.gd"),"operator":FileAccess.get_sha256(get_script().resource_path),"inherited_operator":FileAccess.get_sha256("res://../../tools/rebuild/p2/test_gameplay_journey.gd")}}
	for pair in [[report_path,report],[trace_path,{"schema":"baram.v2.natural-command-trace/1","commands":transcript}]]:
		if not str(pair[0]).is_empty():
			DirAccess.make_dir_recursive_absolute(str(pair[0]).get_base_dir())
			var file:=FileAccess.open(str(pair[0]),FileAccess.WRITE)
			if file: file.store_string(JSON.stringify(pair[1],"  ")+"\n"); file.close()
	print("V2_PROGRESSION_RESULT "+JSON.stringify({"status":report.status,"failures":failures,"jobs":job_results.size(),"report":report_path}))
	quit(0 if report.status=="PASS" else 1)
