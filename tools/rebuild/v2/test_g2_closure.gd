extends SceneTree
## Every selected ID uses authoritative commands. Level, money, attributes, RNG and companion
## ingredients are explicit fixtures; this is NOT natural all-content progression or visual QA.
const Game=preload("res://state/gameplay_state.gd")
var game
var original: Dictionary={}
var checks: Array=[]
var failures: int=0
var sequence: int=0
var spawn_by_monster: Dictionary={}
var item_routes: Dictionary={}
var monster_routes: Dictionary={}
var maps_reached: Dictionary={}
var loaded_engine_sha: String=""
var npcs_accessed: Dictionary={}

func check(id: String,good: bool,detail: Variant=null) -> void:
	checks.append({"id":id,"status":"PASS" if good else "FAIL","detail":detail})
	if not good: failures+=1

func command(type: String,extra: Dictionary={}) -> Dictionary:
	sequence+=1
	var value: Dictionary={"type":type,"request_id":"closure:"+str(sequence)}
	value.merge(extra)
	return game.command(value)

func context() -> void:
	game.state=original.duplicate(true)
	var c: Dictionary=game.state.character
	c.level=game.data.xp_thresholds.size();c.xp=game.data.xp_thresholds[-1];c.job="전사";c.money=900000000
	c.hp_max=1000000;c.hp=1000000;c.mp_max=1000000;c.mp=1000000;c.equipment_hp_bonus=0;c.equipment_mp_bonus=0
	c.base_stats={"strength":999999,"dexterity":999999,"intelligence":999999}
	game.state.inventory=[];game.state.equipment={};game.state.loot=[];game.state.skills=[];game.state.quests={};game.state.cooldowns={};game.state.pending_actions=[]
	game.state.buffs={"fixture:attack":{"expires_at":10000000.0,"attack":1000000000,"defense":0,"attack_multiplier":1.0}}
	for monster in game.state.monsters.values(): monster.ai_at=100000.0;monster.attack_at=100000.0

func job_fixture(job: String) -> void:
	game.state.character.job=job if job in ["전사","도적","주술사","도사"] else "전사"
	game.state.character.erase("advancement");game.state.character.erase("advancement_rank");game.state.character.erase("title")
	for advancement in game.data.get("advancements",{}).values():
		if str(advancement.job)==str(game.state.character.job) and int(advancement.get("rank",1))>int(game.state.character.get("advancement_rank",0)):
			game.state.character.advancement=advancement.id;game.state.character.advancement_rank=int(advancement.get("rank",1));game.state.character.title=advancement.get("title",advancement.id)

func near_npc(npc_id: String) -> bool:
	if not game.data.npcs.has(npc_id): return false
	var npc: Dictionary=game.data.npcs[npc_id]
	for offset in [Vector2i.DOWN,Vector2i.UP,Vector2i.LEFT,Vector2i.RIGHT]:
		var x: int=int(npc.x)+offset.x;var y: int=int(npc.y)+offset.y
		if game.valid_position(str(npc.map_id),x,y) and not game._occupied(str(npc.map_id),x,y):
			game.state.character.map_id=npc.map_id;game.state.character.x=x;game.state.character.y=y;game.state.cooldowns={};return true
	return false

func near_spawn(monster_id: String) -> String:
	for id in spawn_by_monster.get(monster_id,[]):
		var monster: Dictionary=game.state.monsters[id]
		for offset in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]:
			var x: int=int(monster.x)+offset.x;var y: int=int(monster.y)+offset.y
			if game.valid_position(str(monster.map_id),x,y) and not game._occupied(str(monster.map_id),x,y):
				game.state.character.map_id=monster.map_id;game.state.character.x=x;game.state.character.y=y;game.state.cooldowns={};return str(id)
	return ""

func add_materials(materials: Dictionary) -> bool:
	for item_id in materials:
		var missing: int=int(materials[item_id])-game.item_count(str(item_id))
		if missing>0 and not game._add_item(str(item_id),missing): return false
	return true

func first_instance(item_id: String) -> String:
	for item in game.state.inventory:
		if str(item.item_id)==item_id: return str(item.instance_id)
	return ""

func drop_seed(definition: Dictionary,item_id: String) -> int:
	# Select a declared deterministic RNG fixture which follows every normal preceding
	# money/roll/quantity draw. No drop probabilities or loot contents are changed.
	for seed in range(1,10001):
		var rng: int=(seed*1103515245+12345)&0x7fffffff
		if rng==0: rng=1
		for drop in definition.get("drops",[]):
			rng=(rng*1103515245+12345)&0x7fffffff
			if rng==0: rng=1
			if float(rng%1000000)/1000000.0<float(drop.get("chance",1.0)):
				if str(drop.item_id)==item_id: return seed
				rng=(rng*1103515245+12345)&0x7fffffff
				if rng==0: rng=1
	return 0

func kill_command(spawn_id: String) -> bool:
	var start: Dictionary=command("attack",{"target_id":spawn_id})
	if start.status!="OK": return false
	game.tick(maxf(0.25,float(game.data.get("config",{}).get("attack_windup",0.18))+0.1))
	return not bool(game.state.monsters[spawn_id].alive)

func acquire(item_id: String) -> Dictionary:
	var item: Dictionary=game.data.items[item_id]
	for path in item.get("acquisition_paths",[]):
		if str(path.kind)=="gather":
			var mid:=str(path.map_id)
			for node in game.data.maps[mid].get("gather_nodes",[]):
				if str(node.id)!=str(path.node_id):continue
				for delta in [Vector2i.UP,Vector2i.DOWN,Vector2i.LEFT,Vector2i.RIGHT]:
					var pos: Vector2i=Vector2i(node.x,node.y)+delta
					if game.valid_position(mid,pos.x,pos.y) and not game._occupied(mid,pos.x,pos.y):
						game.state.character.map_id=mid;game.state.character.x=pos.x;game.state.character.y=pos.y
						var response: Dictionary=command("gather",{"node_id":node.id})
						if response.status=="OK":return {"kind":"gather","node_id":node.id}
		if str(path.kind)=="shop":
			if not near_npc(str(path.npc_id)): continue
			var result: Dictionary=command("buy",{"npc_id":path.npc_id,"item_id":item_id,"quantity":1})
			if result.status=="OK": return {"kind":"shop","npc_id":path.npc_id,"quantity":game.item_count(item_id)}
		elif str(path.kind)=="drop":
			var spawn_id: String=near_spawn(str(path.monster_id))
			if spawn_id.is_empty(): continue
			var seed: int=drop_seed(game.data.monsters[str(path.monster_id)],item_id)
			if seed==0: continue
			game.state.rng_state=seed
			if not kill_command(spawn_id): continue
			for loot in game.state.loot.duplicate():
				if str(loot.item_id)==item_id:
					var result: Dictionary=command("pickup",{"loot_id":loot.loot_id})
					if result.status=="OK": return {"kind":"drop","monster_id":path.monster_id,"spawn_id":spawn_id,"fixture_seed":seed,"quantity":game.item_count(item_id)}
		elif str(path.kind)=="craft":
			var recipe_id: String=str(path.get("recipe_id",""))
			if not game.data.get("recipes",{}).has(recipe_id): continue
			var recipe: Dictionary=game.data.recipes[recipe_id]
			if near_npc(str(recipe.npc_id)) and add_materials(recipe.get("ingredients",{})):
				var result: Dictionary=command("craft",{"recipe_id":recipe_id,"npc_id":recipe.npc_id})
				if result.status=="OK" and game.item_count(item_id)>0: return {"kind":"craft","recipe_id":recipe_id,"quantity":game.item_count(item_id)}
	return {}

func function_item(item_id: String) -> Dictionary:
	var item: Dictionary=game.data.items[item_id]
	if not str(item.get("slot","")).is_empty():
		job_fixture(str(item.get("required_job","전사")))
		var result: Dictionary=command("equip",{"instance_id":first_instance(item_id)})
		return {"kind":"equip","status":result.status,"reason":result.reason}
	if int(item.get("hp_restore",0))>0 or int(item.get("mp_restore",0))>0 or not str(item.get("action_type","")).is_empty():
		game.state.character.hp=1;game.state.character.mp=1
		if str(item.get("action_type",""))=="cleanse": game.state.buffs["fixture:poison"]=game._status_definition({"power":1,"duration":10},"poison")
		var result: Dictionary=command("use_item",{"instance_id":first_instance(item_id)})
		return {"kind":"use_item","status":result.status,"reason":result.reason}
	for path in item.get("function_paths",[]):
		if str(path.kind)=="skill_learning":
			var id: String=str(path.skill_id);var skill: Dictionary=game.data.skills[id]
			job_fixture(str(skill.job));game.state.character.guardian=skill.get("guardian","주작")
			var teachers: Array=skill.get("teacher_ids",[])
			if teachers.is_empty(): continue
			var teacher: String=""
			for npc_id in teachers:
				if str(game.data.npcs[npc_id].get("job",""))==str(game.state.character.job): teacher=str(npc_id);break
			if teacher.is_empty() or not near_npc(teacher) or not add_materials(skill.get("ingredients",{})): continue
			var result: Dictionary=command("learn",{"skill_id":id,"npc_id":teacher})
			if result.status=="OK": return {"kind":"skill_learning","id":id,"status":"OK"}
		elif str(path.kind)=="quest_handin":
			var id: String=str(path.quest_id);var quest: Dictionary=game.data.quests[id]
			job_fixture(str(quest.get("required_job","전사")))
			if not near_npc(str(quest.npc_id)): continue
			for previous in quest.get("requires_quests",[]): game.state.quests[previous]={"status":"completed","progress":{}}
			var result: Dictionary=command("quest_accept",{"quest_id":id,"npc_id":quest.npc_id})
			if result.status!="OK": continue
			for objective in quest.get("objectives",[]):
				if str(objective.kind)=="collect": add_materials({str(objective.id):int(objective.get("count",1))})
				else:
					for n in range(int(objective.get("count",1))): game._quest_progress(str(objective.kind),str(objective.id))
			result=command("quest_complete",{"quest_id":id,"npc_id":quest.npc_id})
			if result.status=="OK": return {"kind":"quest_handin","id":id,"status":"OK"}
		elif str(path.kind)=="craft_material":
			var id: String=str(path.recipe_id);var recipe: Dictionary=game.data.recipes[id]
			if near_npc(str(recipe.npc_id)) and add_materials(recipe.get("ingredients",{})):
				var result: Dictionary=command("craft",{"recipe_id":id,"npc_id":recipe.npc_id})
				if result.status=="OK": return {"kind":"craft_material","id":id,"status":"OK"}
		elif str(path.kind)=="advancement_material":
			var id: String=str(path.advancement_id);var advancement: Dictionary=game.data.advancements[id]
			job_fixture(str(advancement.job))
			game.state.character.erase("advancement");game.state.character.erase("advancement_rank");game.state.character.erase("title")
			for previous in game.data.advancements.values():
				if str(previous.job)==str(advancement.job) and int(previous.get("rank",1))==int(advancement.get("rank",1))-1:
					game.state.character.advancement=previous.id;game.state.character.advancement_rank=previous.rank;game.state.character.title=previous.get("title",previous.id)
			var teacher: String=str(advancement.teacher_ids[0])
			if near_npc(teacher) and add_materials(advancement.get("ingredients",{})):
				var result: Dictionary=command("advance",{"advancement_id":id,"npc_id":teacher})
				if result.status=="OK": return {"kind":"advancement_material","id":id,"status":"OK"}
	# Sale is a legitimate economic action for otherwise non-consumable material.
	for npc_id in game.data.npcs:
		if game.data.npcs[npc_id].get("shop",{}).get(item_id,{}).get("sell_price")!=null and near_npc(str(npc_id)):
			var result: Dictionary=command("sell",{"npc_id":npc_id,"instance_id":first_instance(item_id),"quantity":1})
			if result.status=="OK": return {"kind":"sell","status":"OK"}
	return {"status":"REFUSED","reason":"NO_EXECUTABLE_FUNCTION_PATH"}

func run_items() -> void:
	for id in game.data.items:
		context()
		var acquisition: Dictionary=acquire(str(id))
		check("item_acquire:"+str(id),not acquisition.is_empty() and game.item_count(str(id))>0,acquisition)
		if acquisition.is_empty(): continue
		var action: Dictionary=function_item(str(id))
		check("item_function:"+str(id),str(action.get("status",""))=="OK",action)
		check("item_result_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")
		if str(action.get("status",""))=="OK": item_routes[id]={"acquisition":acquisition,"function":action}

func run_monsters() -> void:
	for id in game.data.monsters:
		context()
		var spawn: String=near_spawn(str(id))
		check("monster_spawn:"+str(id),not spawn.is_empty())
		if spawn.is_empty(): continue
		var start_xp: int=int(game.state.character.xp)
		check("monster_real_combat:"+str(id),kill_command(spawn),{"spawn_id":spawn})
		check("monster_reward_once:"+str(id),game.state.stats.kills==1 and game.state.character.xp==mini(game.MAX_VALUE,start_xp+int(game.data.monsters[id].xp)))
		var references: bool=true
		for loot in game.state.loot: references=references and game.data.items.has(str(loot.item_id))
		check("monster_rolled_drop_references:"+str(id),references,{"rolled_loot":game.state.loot.size()})
		if not game.state.monsters[spawn].alive: monster_routes[id]={"spawn_id":spawn,"rolled_loot":game.state.loot.duplicate(true)}

func run_exits() -> void:
	for map_id in game.data.maps:
		for exit in game.data.maps[map_id].get("exits",[]):
			context()
			var direction: Vector2i=Vector2i.ZERO
			for candidate in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
				var x: int=int(exit.x)-candidate.x;var y: int=int(exit.y)-candidate.y
				if game.can_step(str(map_id),x,y,int(exit.x),int(exit.y)) and not game._occupied(str(map_id),x,y): direction=candidate;break
			check("exit_approach:"+str(exit.id),direction!=Vector2i.ZERO)
			if direction==Vector2i.ZERO: continue
			game.state.character.map_id=map_id;game.state.character.x=int(exit.x)-direction.x;game.state.character.y=int(exit.y)-direction.y
			var result: Dictionary=command("move",{"dx":direction.x,"dy":direction.y})
			var c: Dictionary=game.state.character
			var passed: bool=result.status=="OK" and str(c.map_id)==str(exit.to_map) and int(c.x)==int(exit.to_x) and int(c.y)==int(exit.to_y)
			check("exit_real_transition:"+str(exit.id),passed,result.reason)
			if passed: maps_reached[map_id]=true;maps_reached[str(c.map_id)]=true
	for id in game.data.maps: check("map_real_exit_reached:"+str(id),maps_reached.has(id))

func run_facilities() -> void:
	for id in game.data.get("training_rules",{}):
		context()
		var rule: Dictionary=game.data.training_rules[id]
		var teacher: String=str(rule.teacher_ids[0])
		near_npc(teacher)
		game.state.character.xp=mini(game.MAX_VALUE,int(game.state.character.xp)+int(rule.xp_cost)*2)
		if str(rule.stat) in ["hp_max","mp_max"]: game.state.character[str(rule.stat)]=1;game.state.character["hp" if str(rule.stat)=="hp_max" else "mp"]=1
		else: game.state.character.base_stats[str(rule.stat)]=1
		var result: Dictionary=command("train",{"training_id":id,"npc_id":teacher})
		check("training_actual_rule:"+str(id),result.status=="OK",result.reason)
		check("training_actual_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")

func run_npcs() -> void:
	var first_item: String=str(game.data.items.keys()[0])
	var weapon_id: String=""
	for id in game.data.items:
		if str(game.data.items[id].get("slot",""))=="weapon": weapon_id=str(id);break
	for id in game.data.npcs:
		context()
		var npc: Dictionary=game.data.npcs[id]
		check("npc_reachable:"+str(id),near_npc(str(id)))
		var dialogue: Dictionary=command("talk",{"npc_id":id})
		var talked: bool=dialogue.status=="OK" and dialogue.events.any(func(event): return event.type=="dialogue" and str(event.npc_id)==str(id) and not str(event.text).is_empty())
		check("npc_real_dialogue:"+str(id),talked)
		if talked: npcs_accessed[id]=true
		if "storage" in npc.get("services",[]):
			game._add_item(first_item,1)
			var iid: String=first_instance(first_item)
			var deposited: Dictionary=command("store_deposit",{"npc_id":id,"instance_id":iid})
			var withdrawn: Dictionary=command("store_withdraw",{"npc_id":id,"instance_id":iid})
			check("npc_actual_storage:"+str(id),deposited.status=="OK" and withdrawn.status=="OK" and first_instance(first_item)==iid)
		if "weapon_naming" in npc.get("services",[]) and not weapon_id.is_empty():
			game._add_item(weapon_id,1)
			var iid: String=first_instance(weapon_id)
			check("npc_actual_weapon_naming:"+str(id),command("rename_weapon",{"npc_id":id,"instance_id":iid,"name":"자료보검"}).status=="OK")
		if "heal" in npc.get("services",[]):
			game.state.character.hp=1;game.state.character.mp=1
			check("npc_actual_heal:"+str(id),command("heal",{"npc_id":id}).status=="OK" and game.state.character.hp==game.state.character.hp_max)
		if "repair" in npc.get("services",[]) and not weapon_id.is_empty():
			game._add_item(weapon_id,1)
			var iid: String=first_instance(weapon_id);var index: int=game._inventory_index(iid)
			game.state.inventory[index].durability=0
			check("npc_actual_repair:"+str(id),command("repair",{"npc_id":id,"instance_id":iid}).status=="OK" and int(game.state.inventory[index].durability)>0)
		if "change_job" in npc.get("services",[]):
			game.state.character.job="commoner"
			check("npc_actual_job_change:"+str(id),command("change_job",{"npc_id":id,"job":npc.job}).status=="OK")
		if "teach_skill" in npc.get("services",[]):
			game.state.character.job=npc.job
			for skill_id in game.data.skills:
				var skill: Dictionary=game.data.skills[skill_id]
				if str(id) in skill.get("teacher_ids",[]) and not skill.has("required_advancement") and str(skill.job) in ["common","COMMON_FOUR_STARTER_JOBS",str(npc.job)]:
					game.state.character.guardian=skill.get("guardian","주작");add_materials(skill.get("ingredients",{}))
					check("npc_actual_teach_skill:"+str(id),command("learn",{"npc_id":id,"skill_id":skill_id}).status=="OK")
					break
		check("npc_result_save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")

func _initialize() -> void:
	loaded_engine_sha=FileAccess.get_sha256("res://state/gameplay_state.gd")
	var path: String=OS.get_environment("BARAM_G1_RUNTIME")
	var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(path.path_join("gameplay_content.json")))
	game=Game.new()
	check("g1_content_configures",typeof(raw)==TYPE_DICTIONARY and game.configure(raw),game.errors)
	if failures==0:
		check("g1_character_creates",game.create_character("전체자료시험","fixture:closure",{"seed":1}).status=="OK")
		game._spawn_all() # explicit exhaustive fixture; normal G2 lazily spawns visited maps
		original=game.snapshot()
		for id in original.monsters:
			var monster_id: String=str(original.monsters[id].monster_id)
			if not spawn_by_monster.has(monster_id): spawn_by_monster[monster_id]=[]
			spawn_by_monster[monster_id].append(id)
		run_items();run_monsters();run_exits();run_facilities();run_npcs()
	check("engine_source_unchanged_during_run",loaded_engine_sha==FileAccess.get_sha256("res://state/gameplay_state.gd"))
	var result: Dictionary={"schema":"baram.v2.g2-all-id-actions/1","status":"PASS" if failures==0 else "FAIL","scope":"Explicit level/money/stats/RNG/material fixtures with real buy/drop/pickup/craft/equip/use/learn/quest/advance/attack/move commands; not natural whole-game progression, visual or platform tests","runtime":path,"content_sha256":FileAccess.get_sha256(path.path_join("gameplay_content.json")),"engine_source_sha256":loaded_engine_sha,"checks":checks,"failures":failures,"counts":{"items_executed":item_routes.size(),"monsters_fought":monster_routes.size(),"maps_reached_by_exits":maps_reached.size(),"npcs_accessed":npcs_accessed.size()},"item_routes":item_routes,"monster_routes":monster_routes}
	var output: String=OS.get_environment("BARAM_G1_CLOSURE_REPORT")
	if not output.is_empty(): var file=FileAccess.open(output,FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n")
	print(JSON.stringify(result));quit(0 if failures==0 else 1)
