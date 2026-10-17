extends SceneTree
## Deliberate small engine fixtures: these prove action semantics, not natural 1–99 or platforms.
const EngineState=preload("res://state/gameplay_state.gd")
var game
var checks: Array=[]
var failures: int=0
var sequence: int=0

func check(id: String,good: bool,detail: Variant=null) -> void:
	checks.append({"id":id,"result":"PASS" if good else "FAIL","detail":detail})
	if not good: failures+=1

func command(type: String,extra: Dictionary={}) -> Dictionary:
	sequence+=1
	var cmd: Dictionary={"type":type,"request_id":"b3:"+str(sequence)}
	cmd.merge(extra)
	return game.command(cmd)

func fixture() -> Dictionary:
	var skills: Dictionary={}
	for kind in ["heal","buff","debuff","status","return","shrine","identify","restore_mp","summon","cleanse","revive","loot","blink"]:
		skills[kind]={"id":kind,"name":kind,"job":"common","learn_level":5,"kind":kind,"mp_cost":2,"power":20,"range":6,"duration":1.5,"cooldown":0.2,"impact_delay":0.1,"ingredients":{},"teacher_ids":[]}
	skills.buff.merge({"status":"stealth","attack_bonus":3,"defense_bonus":2})
	skills.debuff.merge({"status":"paralysis","target":"monster"})
	skills.status.merge({"status":"poison","status_power":7,"tick_interval":0.2,"target":"monster"})
	skills.summon.merge({"monster_id":"monster","power":11,"attack_interval":0.2})
	for delivery in ["melee","projectile","area"]:
		skills[delivery]={"id":delivery,"name":delivery,"job":"common","learn_level":5,"kind":"damage","delivery":delivery,"mp_cost":2,"power":40,"range":6,"radius":1,"cooldown":0.2,"impact_delay":0.1,"ingredients":{},"teacher_ids":[]}
	skills.melee["heal_fraction"]=0.5
	var npcs: Dictionary={}
	var growth: Dictionary={}
	var advancement: Dictionary={}
	for index in range(4):
		var job: String=["전사","도적","주술사","도사"][index]
		npcs[job]={"id":job,"name":job+"사범","map_id":"town","x":2,"y":2,"job":job,"services":["change_job","teach_skill","quest","craft","advance","training","storage","weapon_naming"],"shop":{}}
		growth[job]={"hp_per_level":8+index,"mp_per_level":6-index,"attack_per_level":0.25+index*0.1}
		advancement[job+"1"]={"id":job+"1","job":job,"rank":1,"title":job+"승급","minimum_level":99,"teacher_ids":[job],"money":10,"ingredients":{"material":2}}
		advancement[job+"2"]={"id":job+"2","job":job,"rank":2,"title":job+"승급2","minimum_level":99,"teacher_ids":[job],"money":10,"ingredients":{"material":2}}
	var xp: Array=[]
	for level in range(99): xp.append(level*100)
	return {"profile":"B3_ACTION_FIXTURE","maps":{"town":{"id":"town","width":12,"height":12,"blocked":[[0,0]],"exits":[],"spawns":[{"id":"a","monster_id":"monster","x":4,"y":3},{"id":"b","monster_id":"monster","x":5,"y":3}]},"field":{"id":"field","width":12,"height":12,"blocked":[],"exits":[],"spawns":[]}},"npcs":npcs,"items":{"material":{"id":"material","name":"재료","stack_max":99,"durability":0},"result":{"id":"result","name":"완성품","stack_max":99,"durability":0},"sword":{"id":"sword","name":"검","slot":"weapon","attack":4,"durability":100,"stack_max":1},"scroll":{"id":"scroll","name":"귀환비서","action_type":"return","durability":0,"stack_max":99}},"skills":skills,"monsters":{"monster":{"id":"monster","name":"시험괴물","hp":1000,"attack":5,"defense":0,"xp":100,"aggression":"hostile","move_interval":1000,"attack_interval":1,"drops":[],"money_min":1,"money_max":1}},"start":{"map_id":"town","x":3,"y":3,"hp":100,"mp":100,"money":100,"starter_items":[{"item_id":"material","quantity":20},{"item_id":"sword","quantity":1},{"item_id":"scroll","quantity":2}]},"respawn":{"map_id":"town","x":8,"y":8},"shrine":{"map_id":"town","x":7,"y":8},"gates":{"east":{"map_id":"field","x":2,"y":2}},"xp_thresholds":xp,"job_growth":growth,"quests":{"q":{"id":"q","npc_id":"전사","minimum_level":1,"objectives":[{"kind":"kill","id":"monster","count":1},{"kind":"collect","id":"material","count":2}],"rewards":{"money":7,"xp":100,"items":{"result":1}}}},"recipes":{"r":{"id":"r","npc_id":"전사","ingredients":{"material":3},"money":5,"results":{"result":2}}},"advancements":advancement,"training_rules":{"strength":{"stat":"strength","minimum_level":90,"xp_cost":20,"increase":2,"cap":500,"teacher_ids":["전사"]},"health":{"stat":"hp_max","minimum_level":90,"xp_cost":20,"increase":10,"cap":100000,"teacher_ids":["전사"]}},"config":{"regen_interval":10000,"max_summons":2}}

func fresh(job: String="주술사") -> void:
	game=EngineState.new();sequence=0
	check("fixture_configure",game.configure(fixture()),game.errors)
	check("create_legacy_shape",game.create_character("시험캐릭","owner",{"seed":4}).status=="OK")
	var snapshot: Dictionary=game.snapshot()
	snapshot.character.job=job;snapshot.character.level=10;snapshot.character.xp=900
	snapshot.character.direction=2
	snapshot.skills=game.data.skills.keys()
	for monster in snapshot.monsters.values(): monster.ai_at=1000.0;monster.attack_at=1000.0
	check("fixture_restore",game.restore(snapshot).status=="OK")

func cast(skill: String,extra: Dictionary={}) -> Dictionary:
	var args: Dictionary={"skill_id":skill}
	args.merge(extra)
	return command("cast",args)

func runtime_skill_sweep(path: String) -> void:
	var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(path.path_join("gameplay_content.json")))
	check("g1_real_definitions_json",typeof(raw)==TYPE_DICTIONARY)
	if typeof(raw)!=TYPE_DICTIONARY: return
	game=EngineState.new();sequence=0
	check("g1_real_definitions_configure",game.configure(raw),game.errors)
	if not game.errors.is_empty(): return
	check("g1_real_character_create",game.create_character("자료시험","fixture:g1",{"seed":41}).status=="OK")
	if game.state.is_empty(): return
	game._spawn_all() # explicit precondition fixture, full G2 definitions retained
	var original: Dictionary=game.snapshot()
	var monster_id: String=""
	var standing: Dictionary={}
	for id in original.monsters:
		var monster: Dictionary=original.monsters[id]
		for offset in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]:
			var x: int=int(monster.x)+offset.x;var y: int=int(monster.y)+offset.y
			if game.valid_position(str(monster.map_id),x,y) and not game._occupied(str(monster.map_id),x,y):
				monster_id=str(id);standing={"map_id":monster.map_id,"x":x,"y":y};break
		if not monster_id.is_empty(): break
	check("g1_real_target_reachable_fixture",not monster_id.is_empty())
	if monster_id.is_empty(): return
	var first_item_id: String=str(raw.items.keys()[0])
	for id in raw.skills:
		var skill: Dictionary=raw.skills[id]
		game.state=original.duplicate(true)
		var c: Dictionary=game.state.character
		c.job=str(skill.job) if str(skill.job) in ["전사","도적","주술사","도사"] else "전사"
		c.guardian=skill.get("guardian","주작");c.level=raw.xp_thresholds.size();c.xp=raw.xp_thresholds[-1]
		c.hp_max=1000000;c.hp=500000;c.mp_max=1000000;c.mp=500000
		c.map_id=standing.map_id;c.x=standing.x;c.y=standing.y
		game.state.skills=[id]
		for monster in game.state.monsters.values(): monster.ai_at=100000.0;monster.attack_at=100000.0
		for advancement in raw.get("advancements",{}).values():
			if str(advancement.job)==str(c.job) and int(advancement.get("rank",1))>int(c.get("advancement_rank",0)):
				c.advancement=advancement.id;c.advancement_rank=int(advancement.get("rank",1));c.title=advancement.get("title",advancement.id)
		var extra: Dictionary={"target_id":monster_id,"direction":"east"}
		var kind: String=str(skill.kind)
		if kind in ["revive","shrine"]: c.hp=0;c.dead=true
		if kind=="identify":
			game.state.inventory.append({"instance_id":"fixture:identify","item_id":first_item_id,"quantity":1,"durability":int(raw.items[first_item_id].get("durability",0))})
			extra.instance_id="fixture:identify"
		if kind=="cleanse":
			var cleansed_status: String=str(skill.get("cleanse_statuses",["poison"])[0])
			game.state.buffs["fixture:effect"]=game._status_definition({"power":1,"duration":20},cleansed_status)
		if kind=="loot":
			var offset: Vector2i=[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT][int(c.direction)] if bool(skill.get("pickup_front_only",false)) else Vector2i.ZERO
			game.state.loot.append({"loot_id":"fixture:loot","item_id":first_item_id,"quantity":1,"map_id":c.map_id,"x":int(c.x)+offset.x,"y":int(c.y)+offset.y})
		if kind=="blink":
			var target: Dictionary=game.state.monsters[monster_id]
			for direction in range(4):
				var offset: Vector2i=[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT][direction]
				if game.valid_position(str(c.map_id),int(target.x)+offset.x,int(target.y)+offset.y) and not game._occupied(str(c.map_id),int(target.x)+offset.x,int(target.y)+offset.y): c.direction=direction;break
		var response: Dictionary=cast(str(id),extra)
		check("g1_cast:"+str(id),response.status=="OK",{"kind":kind,"reason":response.reason})
		if response.status!="OK": continue
		var saved: Dictionary=game.snapshot()
		check("g1_pending_save:"+str(id),game.validate_payload(saved).status=="OK")
		var applied: bool=response.events.any(func(event): return str(event.type)=="skill_applied" and str(event.get("skill_id",""))==str(id))
		for step in range(12):
			var result: Dictionary=game.tick(0.25)
			if result.events.any(func(event): return str(event.type)=="skill_applied" and str(event.get("skill_id",""))==str(id)): applied=true
		check("g1_actual_apply:"+str(id),applied,{"kind":kind,"power":skill.get("power"),"delivery":skill.get("delivery")})
		check("g1_result_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")

func runtime_service_fixture(original: Dictionary,npc_id: String,job: String="전사") -> bool:
	game.state=original.duplicate(true)
	var npc: Dictionary=game.data.npcs[npc_id]
	var c: Dictionary=game.state.character
	c.job=job if job in ["전사","도적","주술사","도사"] else "전사"
	c.level=game.data.xp_thresholds.size();c.xp=game.data.xp_thresholds[-1];c.money=900000000
	c.map_id=npc.map_id
	game.state.inventory=[];game.state.equipment={}
	for monster in game.state.monsters.values(): monster.ai_at=100000.0;monster.attack_at=100000.0
	for offset in [Vector2i.DOWN,Vector2i.UP,Vector2i.LEFT,Vector2i.RIGHT]:
		if game.valid_position(str(npc.map_id),int(npc.x)+offset.x,int(npc.y)+offset.y) and not game._occupied(str(npc.map_id),int(npc.x)+offset.x,int(npc.y)+offset.y): c.x=int(npc.x)+offset.x;c.y=int(npc.y)+offset.y;return true
	return false

func runtime_service_sweep(path: String) -> void:
	var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(path.path_join("gameplay_content.json")))
	if typeof(raw)!=TYPE_DICTIONARY: return
	game=EngineState.new();sequence=0
	if not game.configure(raw): return
	if game.create_character("서비스시험","fixture:services",{"seed":37}).status!="OK": return
	var original: Dictionary=game.snapshot()
	for id in raw.get("quests",{}):
		var definition: Dictionary=raw.quests[id]
		check("g1_quest_npc_reachable:"+str(id),runtime_service_fixture(original,str(definition.npc_id),str(definition.get("required_job","전사"))))
		for previous in definition.get("requires_quests",[]): game.state.quests[previous]={"status":"completed","progress":{}}
		var accepted: Dictionary=command("quest_accept",{"quest_id":id,"npc_id":definition.npc_id})
		check("g1_quest_accept:"+str(id),accepted.status=="OK",accepted.reason)
		if accepted.status!="OK": continue
		for objective in definition.get("objectives",[]):
			if str(objective.kind)=="collect": game._add_item(str(objective.id),int(objective.get("count",1)))
			elif str(objective.kind)=="kill":
				# Explicit finite objective fixture uses the authoritative event counter.
				for count in range(int(objective.get("count",1))): game._quest_progress("kill",str(objective.id))
			elif str(objective.kind) in ["visit","talk","craft","equip"]:game._quest_progress(str(objective.kind),str(objective.id))
		var completed: Dictionary=command("quest_complete",{"quest_id":id,"npc_id":definition.npc_id})
		check("g1_quest_complete:"+str(id),completed.status=="OK",completed.reason)
		check("g1_quest_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")
	for id in raw.get("recipes",{}):
		var definition: Dictionary=raw.recipes[id]
		check("g1_recipe_npc_reachable:"+str(id),runtime_service_fixture(original,str(definition.npc_id),str(definition.get("required_job","전사"))))
		for item_id in definition.get("ingredients",{}): game._add_item(str(item_id),int(definition.ingredients[item_id]))
		var result: Dictionary=command("craft",{"recipe_id":id,"npc_id":definition.npc_id})
		check("g1_recipe_craft:"+str(id),result.status=="OK",result.reason)
		var outputs: bool=true
		for item_id in definition.get("results",{}): outputs=outputs and game.item_count(str(item_id))>=int(definition.results[item_id])
		check("g1_recipe_outputs:"+str(id),outputs)
		check("g1_recipe_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")
	for id in raw.get("advancements",{}):
		var definition: Dictionary=raw.advancements[id]
		var npc_id: String=str(definition.teacher_ids[0])
		check("g1_advancement_npc_reachable:"+str(id),runtime_service_fixture(original,npc_id,str(definition.job)))
		var required_rank: int=int(definition.get("rank",1))-1
		for previous in raw.advancements.values():
			if str(previous.job)==str(definition.job) and int(previous.get("rank",1))==required_rank:
				game.state.character.advancement=previous.id;game.state.character.advancement_rank=required_rank;game.state.character.title=previous.get("title",previous.id)
		for item_id in definition.get("ingredients",{}): game._add_item(str(item_id),int(definition.ingredients[item_id]))
		var result: Dictionary=command("advance",{"advancement_id":id,"npc_id":npc_id})
		check("g1_advancement_execute:"+str(id),result.status=="OK",result.reason)
		check("g1_advancement_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")

func _initialize() -> void:
	fresh()
	game.state.character.hp=30
	check("heal_schedules",cast("heal").status=="OK");game.tick(0.15)
	check("heal_actual_resource",game.state.character.hp==50)
	game.tick(0.2);game.state.character.mp=20
	check("restore_mp_schedules",cast("restore_mp").status=="OK");game.tick(0.15)
	check("restore_mp_actual_resource",game.state.character.mp==38)
	fresh()
	check("shrine_alive_refused",cast("shrine").reason=="GHOST_REQUIRED")
	game.state.character.hp=0;game.state.character.dead=true
	check("shrine_dead_schedules",cast("shrine").status=="OK");game.tick(0.15)
	check("shrine_moves_ghost_without_revive",game.state.character.dead and game.state.character.x==7 and game.state.character.y==8)
	fresh()
	var broken: Dictionary=fixture();broken.skills.melee.kind="fake"
	var bad=EngineState.new()
	check("unknown_kind_fails_configuration",not bad.configure(broken) and bad.errors.has("UNSUPPORTED_SKILL:melee"))
	broken=fixture();broken.skills.melee.delivery="fake"
	check("unknown_delivery_fails_configuration",not bad.configure(broken))
	var original: String=JSON.stringify(game.state)
	check("refused_cast_atomic",cast("melee",{"target_id":"unknown"}).reason=="TARGET_OUT_OF_REACH" and JSON.stringify(game.state)==original)
	check("dialog_cancel_atomic",command("cancel").status=="CANCELLED" and JSON.stringify(game.state)==original)
	game.state.character.hp=30
	check("melee_schedules",cast("melee",{"target_id":"a"}).status=="OK" and game.state.monsters.a.hp==1000)
	var pending: Dictionary=game.snapshot()
	var clone=EngineState.new();clone.configure(fixture())
	check("pending_cast_roundtrip",clone.restore(pending).status=="OK")
	game.tick(0.15);clone.tick(0.15)
	check("melee_lifesteal_real_impact",game.state.monsters.a.hp==960 and game.state.character.hp==50)
	check("save_windup_exact_once",game.state.monsters==clone.state.monsters and game.state.character==clone.state.character)
	var after: String=JSON.stringify(game.state)
	check("duplicate_cast_idempotent",game.command({"type":"cast","request_id":"b3:3","skill_id":"melee","target_id":"a"}).status=="DUPLICATE" and JSON.stringify(game.state)==after)
	fresh()
	check("projectile_schedules",cast("projectile",{"target_id":"a"}).status=="OK")
	game.tick(0.1);check("projectile_flight_delays_impact",game.state.monsters.a.hp==1000)
	game.tick(0.15);check("projectile_impacts",game.state.monsters.a.hp==960)
	fresh()
	check("area_schedules",cast("area",{"target_id":"a"}).status=="OK")
	game.tick(0.15);check("area_hits_two_distinct_targets",game.state.monsters.a.hp==960 and game.state.monsters.b.hp==960)
	fresh()
	cast("melee",{"target_id":"a"})
	var paid: int=int(game.state.character.mp)
	check("cancel_pending_cast",command("cancel_pending").status=="OK")
	game.tick(0.3)
	check("cancelled_cast_no_hit_no_refund",game.state.monsters.a.hp==1000 and game.state.character.mp==paid)
	fresh()
	cast("buff");game.tick(0.15)
	check("stealth_buff_stats",game._has_status(game.state.buffs,"stealth") and int(game.derived_stats().defense)==2)
	game.state.monsters.a.x=3;game.state.monsters.a.y=4;game.state.monsters.a.attack_at=0.0
	game.tick(0.3)
	check("stealth_blocks_hostile_attack",game.state.character.hp==100)
	cast("melee",{"target_id":"a"})
	check("offensive_action_breaks_stealth",not game._has_status(game.state.buffs,"stealth"))
	fresh()
	game.data.skills.buff["form_monster_id"]="monster";game.data.skills.buff["reflect_fraction"]=0.25
	cast("buff");game.tick(0.15)
	check("transformation_preserves_form",game.state.buffs.buff.form_monster_id=="monster" and game.validate_payload(game.snapshot()).status=="OK")
	game._damage_player(20,"a")
	check("reflection_damages_real_attacker",game.state.monsters.a.hp<1000)
	fresh()
	cast("debuff",{"target_id":"a"});game.tick(0.15)
	check("paralysis_persisted",game._has_status(game.state.monsters.a.statuses,"paralysis"))
	var saved: Dictionary=game.snapshot();clone=EngineState.new();clone.configure(fixture())
	check("status_roundtrip",clone.restore(saved).status=="OK")
	clone.state.monsters.a.x=3;clone.state.monsters.a.y=4;clone.state.monsters.a.attack_at=0.0;clone.state.monsters.a.ai_at=0.0
	clone.tick(0.5);check("paralysis_stops_monster",clone.state.character.hp==100 and clone.state.monsters.a.x==3 and clone.state.monsters.a.y==4)
	clone.tick(1.2);check("status_expires",not clone._has_status(clone.state.monsters.a.statuses,"paralysis"))
	fresh()
	cast("status",{"target_id":"a"});game.tick(0.55)
	check("poison_has_periodic_damage",game.state.monsters.a.hp==986)
	var malformed: Dictionary=game.snapshot();malformed.monsters.a.statuses.status.next_tick="invalid"
	var unchanged: String=JSON.stringify(game.state)
	check("malformed_status_restore_rejected",game.restore(malformed).status!="OK" and unchanged==JSON.stringify(game.state))
	fresh()
	game.state.buffs.poison=game._status_definition({"power":5,"duration":3},"poison")
	check("cleanse_schedules",cast("cleanse").status=="OK");game.tick(0.15)
	check("cleanse_removes_harmful_status",game.state.buffs.is_empty())
	fresh()
	cast("summon");game.tick(0.35)
	check("summon_entity_attacks",game.state.summons.size()==1 and game.state.monsters.a.hp<1000)
	clone=EngineState.new();clone.configure(fixture())
	check("summon_roundtrip",clone.restore(game.snapshot()).status=="OK")
	game.tick(1.5);check("summon_expires",game.state.summons.is_empty())
	fresh()
	var sword: String=game.state.inventory[1].instance_id
	check("identify_requires_owned_item",cast("identify",{"instance_id":"fake"}).reason=="ITEM_NOT_OWNED")
	cast("identify",{"instance_id":sword});game.tick(0.15)
	check("identify_properties_are_persistent",game.state.inventory[1].identified and game.validate_payload(game.snapshot()).status=="OK")
	game.tick(0.2);check("identify_duplicate_refused",cast("identify",{"instance_id":sword}).reason=="ALREADY_IDENTIFIED")
	fresh()
	cast("blink",{"target_id":"a"});game.tick(0.15)
	check("blink_changes_real_position",game.state.character.x==4 and game.state.character.y==4)
	fresh()
	game.state.loot=[{"loot_id":"loot:test","item_id":"material","quantity":2,"map_id":"town","x":4,"y":4}]
	cast("loot");game.tick(0.15)
	check("loot_collects_normal_instance",game.item_count("material")==22 and game.state.loot.is_empty())
	fresh()
	game.state.character.hp=0;game.state.character.dead=true
	check("revive_dead_cast",cast("revive").status=="OK");game.tick(0.15)
	check("revive_restores_alive",not game.state.character.dead and game.state.character.hp==50)
	fresh()
	cast("return",{"direction":"east"});game.tick(0.15)
	check("return_real_destination",game.state.character.map_id=="field" and game.state.character.x==2)
	fresh()
	var scroll: String=game.state.inventory[2].instance_id
	check("return_scroll_consumes_one",command("use_item",{"instance_id":scroll}).status=="OK" and game.state.character.map_id=="field" and game.item_count("scroll")==1)
	fresh("전사")
	check("quest_accept",command("quest_accept",{"quest_id":"q","npc_id":"전사"}).status=="OK")
	var before_quest: String=JSON.stringify(game.state)
	check("incomplete_quest_no_cost",command("quest_complete",{"quest_id":"q","npc_id":"전사"}).reason=="QUEST_OBJECTIVE_INCOMPLETE" and before_quest==JSON.stringify(game.state))
	game._hit_monster(game.state.monsters.a,1000,"fixture")
	check("quest_kill_progress_from_actual_kill",game.state.quests.q.progress["kill:monster"]==1)
	var money: int=int(game.state.character.money)
	check("quest_completion_rewards_consumes",command("quest_complete",{"quest_id":"q","npc_id":"전사"}).status=="OK" and game.item_count("material")==18 and game.item_count("result")==1 and game.state.character.money==money+7)
	var before_repeat: String=JSON.stringify(game.state)
	check("quest_repeat_no_rewards",command("quest_complete",{"quest_id":"q","npc_id":"전사"}).reason=="QUEST_NOT_ACTIVE" and before_repeat==JSON.stringify(game.state))
	clone=EngineState.new();clone.configure(fixture());check("completed_quest_roundtrip",clone.restore(game.snapshot()).status=="OK")
	check("craft_outputs_and_cost",command("craft",{"recipe_id":"r","npc_id":"전사"}).status=="OK" and game.item_count("material")==15 and game.item_count("result")==3)
	var craft_before: String=JSON.stringify(game.state)
	check("craft_duplicate_request_no_cost",game.command({"type":"craft","recipe_id":"r","npc_id":"전사","request_id":"b3:"+str(sequence)}).status=="DUPLICATE" and JSON.stringify(game.state)==craft_before)
	game.state.character.money=0
	var empty_money: String=JSON.stringify(game.state)
	check("craft_failure_atomic",command("craft",{"recipe_id":"r","npc_id":"전사"}).status=="REFUSED" and JSON.stringify(game.state)==empty_money)
	for job in ["전사","도적","주술사","도사"]:
		fresh(job)
		check("advancement_lowlevel_"+job,command("advance",{"advancement_id":job+"1","npc_id":job}).reason=="LEVEL_TOO_LOW")
		game._grant_xp(10000)
		check("growth99_"+job,game.state.character.level==99 and game.state.character.hp_max==100+89*int(game.data.job_growth[job].hp_per_level))
		check("advancement_order_"+job,command("advance",{"advancement_id":job+"2","npc_id":job}).reason=="ADVANCEMENT_ORDER_REQUIRED")
		check("advancement_cost_title_"+job,command("advance",{"advancement_id":job+"1","npc_id":job}).status=="OK" and game.state.character.advancement_rank==1 and game.item_count("material")==18 and game.state.character.money==90)
		clone=EngineState.new();clone.configure(fixture());check("advancement_roundtrip_"+job,clone.restore(game.snapshot()).status=="OK")
		var before_advance: String=JSON.stringify(game.state)
		check("advancement_repeat_no_cost_"+job,command("advance",{"advancement_id":job+"1","npc_id":job}).status=="REFUSED" and JSON.stringify(game.state)==before_advance)
	fresh("전사")
	game.data.skills.buff["move_multiplier"]=0.69
	check("move_baseline",command("move",{"dx":-1,"dy":0}).status=="OK")
	var baseline_interval: float=float(game.state.cooldowns.move)-game._now()
	fresh("전사");game.data.skills.buff["move_multiplier"]=0.69
	cast("buff");game.tick(0.15)
	check("move_haste",command("move",{"dx":-1,"dy":0}).status=="OK")
	check("haste_reduces_actual_interval",float(game.state.cooldowns.move)-game._now()<baseline_interval)
	fresh("전사")
	var weapon_id: String=game.state.inventory[1].instance_id
	game.data.items.sword["required_strength"]=40
	check("source_strength_restriction",command("equip",{"instance_id":weapon_id}).reason=="ATTRIBUTE_TOO_LOW")
	game.state.character.base_stats.strength=40
	check("strength_met_equips",command("equip",{"instance_id":weapon_id}).status=="OK")
	check("equipped_storage_refused",command("store_deposit",{"instance_id":weapon_id,"npc_id":"전사"}).reason=="UNEQUIP_FIRST")
	command("unequip",{"slot":"weapon"})
	check("weapon_custom_name",command("rename_weapon",{"instance_id":weapon_id,"npc_id":"전사","name":"시험보검"}).status=="OK" and game.state.inventory[1].custom_name=="시험보검" and game.state.character.money==80)
	var named: String=JSON.stringify(game.state)
	check("name_repeat_no_charge",command("rename_weapon",{"instance_id":weapon_id,"npc_id":"전사","name":"시험보검"}).reason=="NAME_UNCHANGED" and named==JSON.stringify(game.state))
	check("bank_deposit_real_instance",command("store_deposit",{"instance_id":weapon_id,"npc_id":"전사"}).status=="OK" and game._inventory_index(weapon_id)<0 and game.state.bank_inventory[0].custom_name=="시험보검")
	clone=EngineState.new();clone.configure(game.data)
	check("bank_named_save_roundtrip",clone.restore(game.snapshot()).status=="OK" and clone.state.bank_inventory[0].instance_id==weapon_id)
	check("bank_withdraw_preserves_identity",command("store_withdraw",{"instance_id":weapon_id,"npc_id":"전사"}).status=="OK" and game.state.bank_inventory.is_empty() and game.state.inventory[game._inventory_index(weapon_id)].custom_name=="시험보검")
	var withdrawal: String=JSON.stringify(game.state)
	check("withdraw_repeat_no_duplicate",command("store_withdraw",{"instance_id":weapon_id,"npc_id":"전사"}).status=="REFUSED" and withdrawal==JSON.stringify(game.state))
	var malformed_bank: Dictionary=game.snapshot();malformed_bank.bank_inventory=[malformed_bank.inventory[0].duplicate(true)]
	check("bank_duplicate_global_instance_rejected",game.restore(malformed_bank).status!="OK")
	check("training_low_level_refused",command("train",{"training_id":"strength","npc_id":"전사"}).reason=="LEVEL_TOO_LOW")
	game.state.character.level=90;game.state.character.xp=8900
	var training_before: String=JSON.stringify(game.state)
	check("training_no_delevel",command("train",{"training_id":"strength","npc_id":"전사"}).reason=="INSUFFICIENT_SURPLUS_XP" and training_before==JSON.stringify(game.state))
	game.state.character.xp=9000
	var strength_before: int=int(game.derived_stats().strength)
	check("training_xp_for_strength",command("train",{"training_id":"strength","npc_id":"전사"}).status=="OK" and game.derived_stats().strength==strength_before+2 and game.state.character.xp==8980 and game.state.character.level==90)
	var trained: String=JSON.stringify(game.state)
	check("training_request_idempotent",game.command({"type":"train","training_id":"strength","npc_id":"전사","request_id":"b3:"+str(sequence)}).status=="DUPLICATE" and trained==JSON.stringify(game.state))
	var hpmax: int=int(game.state.character.hp_max)
	check("training_maxhp",command("train",{"training_id":"health","npc_id":"전사"}).status=="OK" and game.state.character.hp_max==hpmax+10)
	clone=EngineState.new();clone.configure(game.data)
	check("trained_stats_roundtrip",clone.restore(game.snapshot()).status=="OK" and clone.state.character.base_stats==game.state.character.base_stats)
	fresh()
	game.data.items.sword.merge({"hp_bonus":250,"mp_bonus":120,"strength_bonus":2,"intelligence_bonus":4,"dexterity_bonus":3,"accuracy_bonus":3,"damage_bonus":3,"regen_bonus":2,"magic_defense_bonus":2})
	var gear_id: String=game.state.inventory[1].instance_id
	var hp_before: int=int(game.state.character.hp_max)
	var attr_before: int=int(game.derived_stats().strength)
	check("sourcegear_equips",command("equip",{"instance_id":gear_id}).status=="OK")
	check("sourcegear_resources_and_attributes",game.state.character.hp_max==hp_before+250 and game.state.character.mp_max==220 and game.derived_stats().strength==attr_before+2 and game.derived_stats().regen_bonus==2 and game.derived_stats().magic_defense==2)
	var gear_payload: Dictionary=game.snapshot();clone=EngineState.new();clone.configure(game.data)
	check("sourcegear_restore_no_stack",clone.restore(gear_payload).status=="OK" and clone.state.character.hp_max==hp_before+250)
	clone.restore(clone.snapshot());check("sourcegear_repeat_restore_no_stack",clone.state.character.hp_max==hp_before+250)
	command("unequip",{"slot":"weapon"});check("sourcegear_unequip_removes_resources",game.state.character.hp_max==hp_before and game.derived_stats().strength==attr_before)
	command("equip",{"instance_id":gear_id});command("unequip",{"slot":"weapon"});check("sourcegear_repeated_equip_no_stack",game.state.character.hp_max==hp_before)
	fresh()
	game.data.skills.buff.merge({"status":"protection","damage_multiplier":0.0,"rooted":true,"barrier_radius":1},true)
	cast("buff");game.tick(0.15)
	game._damage_player(100,"a");check("immunity_zero_damage",game.state.character.hp==100)
	check("rooted_prevents_player_move",command("move",{"dx":-1,"dy":0}).reason=="STATUS_PREVENTS_ACTION")
	check("barrier_blocks_monster_approach",not game._monster_move(game.state.monsters.a,-1,0))
	fresh()
	game.data.skills.buff.merge({"status":"stealth","next_hit_multiplier":7.5},true)
	cast("buff");game.tick(0.15)
	var damage_base: int=int(game.derived_stats().attack)
	command("attack",{"target_id":"a"});game.tick(0.25)
	check("stealth_next_hit_multiplier",game.state.monsters.a.hp==1000-int(round(damage_base*7.5)))
	check("next_hit_consumed_once",not game.state.buffs.has("buff"))
	fresh()
	game.data.skills.buff.merge({"evasion_chance":1.0},true)
	cast("buff");game.tick(0.15);game._damage_player(50,"a")
	check("evasion_prevents_real_damage",game.state.character.hp==100)
	fresh()
	game.data.skills.buff.merge({"finisher_multiplier":2.0,"status":""},true)
	cast("buff");game.tick(0.25);cast("melee",{"target_id":"a"});game.tick(0.15)
	check("finisher_affects_skill_damage",game.state.monsters.a.hp==920,{"hp":game.state.monsters.a.hp,"pending":game.state.pending_actions,"buffs":game.state.buffs})
	fresh()
	game.data.skills.melee.merge({"hp_cost_all":true,"allow_lethal_hp_cost":true},true)
	check("sacrifice_cast",cast("melee",{"target_id":"a"}).status=="OK")
	check("sacrifice_hits_then_dies_consistently",game.state.monsters.a.hp==960 and game.state.character.dead and game.state.character.hp==0 and game.validate_payload(game.snapshot()).status=="OK")
	fresh()
	game.data.skills.restore_mp.merge({"restore_full_mp":true,"hp_cost_fraction":0.5,"mp_cost":0},true)
	game.state.character.mp=1;cast("restore_mp");game.tick(0.15)
	check("restore_full_mp_charges_current_hp_fraction",game.state.character.mp==100 and game.state.character.hp==50,game.state.character)
	fresh()
	game.data.skills.projectile["mp_cost_all"]=true
	cast("projectile",{"target_id":"a"});check("all_mp_cost_committed",game.state.character.mp==0)
	fresh()
	game.data.skills.area["directional_pattern"]=["front","back"]
	game.state.character.direction=1;game.state.monsters.b.x=2;game.state.monsters.b.y=3
	cast("area",{"target_id":"a"});game.tick(0.15)
	check("directional_pattern_hits_front_and_back",game.state.monsters.a.hp==960 and game.state.monsters.b.hp==960)
	fresh()
	game.state.monsters.a.x=6;game.data.skills.melee["pull_target"]=true
	cast("melee",{"target_id":"a"});game.tick(0.15)
	check("pull_changes_monster_position",game._distance(game.state.monsters.a,game.state.character)==1)
	fresh()
	game.data.skills.status["poison_hp_fraction"]=0.03
	cast("status",{"target_id":"a"});game.tick(0.35)
	check("poison_fraction_uses_target_max_hp",game.state.monsters.a.hp==970)
	fresh()
	game.data.skills.buff["inspect_self_fields"]=["abilities","inventory"]
	cast("buff");var inspected: Dictionary=game.tick(0.15)
	check("inspection_emits_real_stats_inventory",inspected.events.any(func(event): return event.type=="player_inspected" and event.stats.has("strength") and event.inventory.size()==3))
	fresh()
	game.data.nation_starts={"고구려":{"map_id":"town","x":3,"y":3},"부여":{"map_id":"field","x":2,"y":2}}
	game.data.nation_gates={"부여":{"east":{"map_id":"field","x":8,"y":8}}}
	game.data.return_points={"부여":{"map_id":"field","x":6,"y":6}}
	var nation_data: Dictionary=game.data.duplicate(true);game=EngineState.new();game.configure(nation_data)
	check("nation_creation_uses_selected_start",game.create_character("부여시험","owner",{"nationality":"부여"}).status=="OK" and game.state.character.map_id=="field" and game.state.character.x==2)
	game.state.character.job="전사";game.state.skills=["return"];cast("return",{"direction":"east"});game.tick(0.15)
	check("nation_return_uses_selected_gates",game.state.character.x==8 and game.state.character.map_id=="field")
	game.tick(0.3);game.data.skills["return"]["return_to_inn"]=true;cast("return");game.tick(0.15)
	check("nation_inn_return_needs_no_direction",game.state.character.x==6 and game.state.character.y==6)
	fresh()
	game.data.skills.buff.merge({"status":"","reflect_fraction":1.0,"reflect_probability":0.0},true)
	cast("buff");game.tick(0.15);game._damage_player(20,"a")
	check("reflection_probability_zero_no_reflect",game.state.monsters.a.hp==1000)
	game.state.buffs.buff.reflect_probability=1.0;game._damage_player(20,"a")
	check("reflection_probability_one_reflects",game.state.monsters.a.hp==982)
	fresh()
	game.state.buffs.poison=game._status_definition({"duration":5},"poison")
	game.state.buffs.slow=game._status_definition({"duration":5},"slow")
	game.data.skills.cleanse["cleanse_statuses"]=["poison"]
	cast("cleanse");game.tick(0.15)
	check("cleanse_narrow_status_selection",not game.state.buffs.has("poison") and game.state.buffs.has("slow"))
	fresh()
	game.data.skills.status.merge({"status":"slow","forget_aggro":true},true)
	game.state.monsters.a.aggro=true;cast("status",{"target_id":"a"});game.tick(0.15)
	check("forget_aggro_actual_flag",not game.state.monsters.a.aggro)
	fresh()
	game.state.monsters.a.x=3;game.state.monsters.a.y=4
	game.state.monsters.a.statuses={"blind":game._status_definition({"duration":5},"blindness")}
	game._resolve_action({"kind":"monster_attack","target_id":"a","target_generation":0,"map_id":"town"})
	check("blindness_reduces_monster_outgoing",game.state.character.hp==97)
	fresh()
	game.data.skills.loot["pickup_front_only"]=true
	game.state.loot=[{"loot_id":"behind","item_id":"material","quantity":1,"map_id":"town","x":3,"y":2}]
	check("front_loot_rejects_behind",cast("loot").reason=="NO_NEARBY_LOOT")
	game.state.loot[0].y=4;cast("loot");game.tick(0.15)
	check("front_loot_collects_facing_cell",game.item_count("material")==21)
	fresh()
	game.state.monsters.a.x=6;game.data.skills.melee["blink_to_target"]=true
	cast("melee",{"target_id":"a"});game.tick(0.15)
	check("blink_attack_moves_and_hits",game._distance(game.state.monsters.a,game.state.character)==1 and game.state.monsters.a.hp==960)
	fresh()
	game.state.character.hp=0;game.state.character.dead=true
	game._grant_xp(1000)
	check("posthumous_xp_never_invalidates_ghost",game.state.character.dead and game.state.character.hp==0 and game.validate_payload(game.snapshot()).status=="OK")
	fresh()
	game.state.buffs.paralysis=game._status_definition({"duration":5},"paralysis")
	game.data.skills.cleanse["cleanse_statuses"]=["paralysis"]
	check("paralysis_matching_cleanse_can_cast",cast("cleanse").status=="OK");game.tick(0.15)
	check("paralysis_self_cleanse_ends_block",not game._has_status(game.state.buffs,"paralysis"))
	var runtime: String=OS.get_environment("BARAM_G1_RUNTIME")
	if not runtime.is_empty(): runtime_skill_sweep(runtime);runtime_service_sweep(runtime)
	print(JSON.stringify({"schema":"baram.v2.g2-actions/1","status":"PASS" if failures==0 else "FAIL","scope":"Linux Godot engine isolation fixtures; no GUI, natural growth or platform claim","engine":Engine.get_version_info(),"checks":checks,"failures":failures}))
	quit(0 if failures==0 else 1)
