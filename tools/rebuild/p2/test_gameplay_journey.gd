extends SceneTree
## Automated operator for the production GameState command path.
## The natural journey never assigns state, grants XP/items/money, or lowers rules.
## Branch fixtures are kept in a separate result section and explicitly labeled.
var checks: Array = []
var transcript: Array = []
var milestones: Array = []
var failures := 0
var game
var content: Dictionary = {}
var sequence := 0
var report_path := ""
var content_path := ""
var runtime_root := ""
var trace_path := ""
var owner := "p3-natural-operator"
var limits := {"commands":100000,"kills":3000,"path_nodes":65536}
var natural_start: Dictionary = {}
var natural_end: Dictionary = {}
var kill_edge_verified := false
var loot_edge_verified := false
var fixture_results: Array = []
var active_phase := "natural"
var canonicalizer = preload("res://storage/save_store.gd").new()
var scope_note := "Linux headless same GameState command dispatch as UI; not actual keyboard/IME/touch/audio/device validation. Normal commands automate a natural journey; explicitly labeled branch fixtures are not natural progression."

func check(id: String, good: bool, observed: Variant = null) -> bool:
	checks.append({"id":id,"result":"PASS" if good else "FAIL","observed":observed})
	if not good:
		failures += 1
		printerr("JOURNEY_FAIL "+id+" "+JSON.stringify(observed))
	return good

func _arg(name: String, fallback: String = "") -> String:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i] == name: return args[i+1]
	return fallback

func _initialize() -> void:
	content_path=_arg("--content")
	runtime_root=_arg("--runtime")
	report_path=_arg("--report")
	trace_path=_arg("--trace",report_path+".commands.json")
	call_deferred("run")

func finish() -> void:
	var digest := FileAccess.get_sha256(content_path) if FileAccess.file_exists(content_path) else ""
	var report := {"schema":"baram.gameplay-journey-evidence/1","platform":OS.get_name(),"engine":Engine.get_version_info(),"content_path":content_path.get_file(),"content_sha256":digest,"scope":scope_note,"checks":checks,"failures":failures,"status":"PASS" if failures==0 and not checks.is_empty() else "FAIL","natural_start":natural_start,"natural_end":natural_end,"milestones":milestones,"trace_entry_count":transcript.size(),"action_command_count":sequence,"source_fingerprints":{"game_state":FileAccess.get_sha256("res://state/gameplay_state.gd"),"gameplay_store":FileAccess.get_sha256("res://storage/gameplay_store.gd"),"operator":FileAccess.get_sha256(get_script().resource_path)},"fixture_branches":fixture_results,"trace":trace_path.get_file()}
	for pair in [[report_path,report],[trace_path,{"schema":"baram.gameplay-command-trace/1","content_sha256":digest,"creation":{"name":"자연육성","owner":owner,"options":{"guardian":"주작","desired_job":"주술사"}},"commands":transcript}]]:
		if not String(pair[0]).is_empty():
			DirAccess.make_dir_recursive_absolute(String(pair[0]).get_base_dir())
			var file := FileAccess.open(pair[0],FileAccess.WRITE)
			if file: file.store_string(JSON.stringify(pair[1],"  ")+"\n")
	print("JOURNEY_RESULT "+JSON.stringify({"status":report.status,"checks":checks.size(),"failures":failures,"commands":transcript.size(),"report":report_path}))
	quit(0 if failures==0 and not checks.is_empty() else 1)

func run() -> void:
	var parsed: Variant=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	if not check("load_actual_gameplay_content",typeof(parsed)==TYPE_DICTIONARY):
		finish();return
	content=parsed
	var engine=load("res://state/gameplay_state.gd")
	game=engine.new()
	if not check("configure_production_GameState",game.configure(content),game.errors):
		finish();return
	if _arg("--phase")=="reload":
		reload_worker();return
	var invalid: Dictionary=game.create_character("!",owner)
	check("invalid_creation_leaves_state_empty",invalid.status=="REFUSED" and game.state.is_empty(),invalid)
	var created: Dictionary=game.create_character("자연육성",owner,{"guardian":"주작","desired_job":"주술사"})
	if not check("natural_character_created",ok(created),created):
		finish();return
	natural_start=game.snapshot()
	check("new_commoner_Lv1_no_learned_skills",char_state().job=="commoner" and int(char_state().level)==1 and game.state.skills.is_empty(),brief())
	mark("created_local_commoner")
	for starter in game.state.inventory.duplicate(true):
		if not String(record("items",str(starter.item_id)).get("slot","")).is_empty():
			var slot:=String(record("items",str(starter.item_id)).get("slot",""))
			if game.state.equipment.get(slot)==starter.instance_id:
				check("declared_initial_equipment_"+str(starter.item_id),true,{"instance_id":starter.instance_id,"slot":slot})
			else:
				check("normal_start_equipment_"+str(starter.item_id),ok(send({"type":"equip","instance_id":starter.instance_id})))
	var start_map:=str(char_state().map_id)
	var start_x:=int(char_state().x)
	var start_y:=int(char_state().y)
	for delta in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,-1),Vector2i(0,1)]:
		var moved:=send({"type":"move","dx":delta.x,"dy":delta.y},0.2)
		check("town_cardinal_move_"+str(delta),ok(moved),moved)
	check("town_four_steps_return_same_position",str(char_state().map_id)==start_map and int(char_state().x)==start_x and int(char_state().y)==start_y,brief())
	var before_cancel:=canonicalizer.canonical(game.snapshot())
	var cancelled:=send({"type":"cancel"})
	check("cancel_exact_zero_state_change",cancelled.status=="CANCELLED" and canonicalizer.canonical(game.snapshot())==before_cancel,cancelled)
	var weapon:=item_id("목검")
	var forge:=merchant_for(weapon,"buy_price")
	var merchant:=merchant_for(item_id("토끼고기"),"sell_price")
	var teacher:=teacher_for("주술사")
	if not check("required_real_world_services_bound",not weapon.is_empty() and not forge.is_empty() and not merchant.is_empty() and not teacher.is_empty(),{"weapon":weapon,"forge":forge,"merchant":merchant,"teacher":teacher}):
		finish();return
	if not check("walk_town_into_forge",approach_npc(forge),brief()):
		finish();return
	check("individual_forge_dialogue",ok(send({"type":"talk","npc_id":forge})))
	var poor_before:=canonicalizer.canonical(game.snapshot())
	var too_many:=send({"type":"buy","npc_id":forge,"item_id":weapon,"quantity":999})
	check("insufficient_purchase_no_state_change",too_many.status=="REFUSED" and canonicalizer.canonical(game.snapshot())==poor_before,too_many)
	var negative_before:=canonicalizer.canonical(game.snapshot())
	var invalid_quantity:=send({"type":"buy","npc_id":forge,"item_id":weapon,"quantity":-1})
	check("negative_purchase_no_state_change",invalid_quantity.status=="REFUSED" and canonicalizer.canonical(game.snapshot())==negative_before,invalid_quantity)
	mark("walked_town_and_forge_no_free_purchase")
	var price:=int(record("npcs",forge).shop[weapon].buy_price)
	if not check("normal_exit_hunting_natural_level5",hunt_until(5,{item_id("도토리"):int(ceil(float(price)/5.0))},0),brief()):
		finish();return
	check("natural_experience_matches_kill_rewards",int(char_state().xp)==int(game.state.stats.total_xp_earned) and int(game.state.stats.kills)>0,{"stats":game.state.stats,"character":char_state()})
	mark("naturally_reached_level5")
	var sold:=false
	for name in ["토끼고기","도토리"]:
		var id:=item_id(name)
		var instance:=instance_for(id)
		var seller:=merchant_for(id,"sell_price")
		if instance.is_empty() or seller.is_empty(): continue
		var sale_price:=int(record("npcs",seller).shop[id].sell_price)
		var sale_quantity:=maxi(1,int(ceil(float(price)/float(sale_price))))
		if int(instance.quantity)<sale_quantity: continue
		if not approach_npc(seller): continue
		var count_before:=item_count(id)
		var money_before:=int(char_state().money)
		var sale_cmd: Dictionary={"type":"sell","npc_id":seller,"instance_id":instance.instance_id,"quantity":sale_quantity,"request_id":"sale:1"}
		var sale:=send(sale_cmd)
		check("normal_hunted_drop_sold",ok(sale) and item_count(id)==count_before-sale_quantity and int(char_state().money)==money_before+sale_quantity*sale_price,sale)
		var sale_snapshot:=canonicalizer.canonical(game.snapshot())
		var duplicate_sale:=send(sale_cmd)
		check("duplicate_sale_no_double_payment",duplicate_sale.status=="DUPLICATE" and canonicalizer.canonical(game.snapshot())==sale_snapshot,duplicate_sale)
		sold=true;break
	if not check("at_least_one_legitimate_drop_sale",sold):
		finish();return
	if not check("walk_back_to_forge",approach_npc(forge),brief()):
		finish();return
	var buy_money:=int(char_state().money)
	var bought:=send({"type":"buy","npc_id":forge,"item_id":weapon,"quantity":1,"request_id":"purchase:1"})
	if not check("normal_earned_money_purchase",ok(bought) and int(char_state().money)==buy_money-price,bought):
		finish();return
	var before_equip: Dictionary=game.derived_stats()
	var equipment_instance:=instance_for(weapon)
	var equipped:=send({"type":"equip","instance_id":equipment_instance.get("instance_id","")})
	check("owned_weapon_equipped_real_stats",ok(equipped) and int(game.derived_stats().attack)>int(before_equip.attack) and game.state.equipment.get("weapon")==equipment_instance.get("instance_id"),{"result":equipped,"before":before_equip,"after":game.derived_stats()})
	var take_off:=send({"type":"unequip","slot":"weapon"})
	check("unequip_reverts_same_authoritative_stats",ok(take_off) and int(game.derived_stats().attack)<int(before_equip.attack),take_off)
	check("reequip_same_instance",ok(send({"type":"equip","instance_id":equipment_instance.get("instance_id","")})))
	mark("sold_drop_bought_and_equipped_weapon")
	if not check("walk_to_mage_guild_and_master",approach_npc(teacher),brief()):
		finish();return
	check("mage_master_individual_dialogue",ok(send({"type":"talk","npc_id":teacher})))
	var job_before:=int(char_state().level)
	var changed:=send({"type":"change_job","npc_id":teacher,"job":"주술사","request_id":"job:1"})
	if not check("natural_mage_job_change_at_level5_or_higher",ok(changed) and char_state().job=="주술사" and job_before>=5,{"result":changed,"actual_level":job_before}):
		finish();return
	var job_state:=canonicalizer.canonical(game.snapshot())
	check("duplicate_job_request_no_change",send({"type":"change_job","npc_id":teacher,"job":"주술사","request_id":"job:1"}).status=="DUPLICATE" and canonicalizer.canonical(game.snapshot())==job_state)
	mark("naturally_changed_to_mage")
	var heal:=skill_id("누리의기원","주술사")
	var fire:=skill_id("화염주(화)","주술사")
	var back:=skill_id("비영사천문")
	var requirements: Dictionary={}
	for id in [heal,fire,back]:
		var skill:=record("skills",id)
		if not check("selected_skill_bound_"+id,not skill.is_empty(),id):
			finish();return
		for material in skill.get("ingredients",{}): requirements[material]=int(requirements.get(material,0))+int(skill.ingredients[material])
	if not check("natural_level6_and_all_original_learning_materials",hunt_until(int(record("skills",fire).learn_level),requirements,0),{"state":brief(),"required":requirements}):
		finish();return
	mark("naturally_hunted_full_learning_materials")
	if not finance_and_repair(requirements,forge,weapon):
		finish();return
	if not check("normal_walk_back_to_mage_teacher",approach_npc(teacher),brief()):
		finish();return
	for id in [heal,fire,back]:
		var definition:=record("skills",id)
		var before_money:=int(char_state().money)
		var before_materials: Dictionary={}
		for material in definition.ingredients: before_materials[material]=item_count(material)
		var request:="learning:"+str(sequence+1)
		var cmd: Dictionary={"type":"learn","npc_id":teacher,"skill_id":id,"request_id":request}
		var learned:=send(cmd)
		var consumed:=int(char_state().money)==before_money-int(definition.get("learn_money",0))
		for material in before_materials: consumed=consumed and item_count(material)==int(before_materials[material])-int(definition.ingredients[material])
		check("natural_skill_learn_consumes_exact_"+id,ok(learned) and id in game.state.skills and consumed,{"result":learned,"materials_before":before_materials,"definition":definition})
		var learn_state:=canonicalizer.canonical(game.snapshot())
		var duplicate:=send(cmd)
		check("duplicate_learning_does_not_consume_"+id,duplicate.status=="DUPLICATE" and canonicalizer.canonical(game.snapshot())==learn_state,duplicate)
	if failures>0:
		finish();return
	mark("learned_healing_fire_and_direction_return")
	if not test_natural_casts(heal,fire,back):
		finish();return
	natural_end=game.snapshot()
	mark("natural_journey_before_save")
	test_process_restart()
	test_job_fixtures()
	test_death_fixture()
	test_long_request_ledger()
	finish()

func records(key: String) -> Array:
	var value: Variant = content.get(key,{})
	if typeof(value) == TYPE_ARRAY: return value
	if typeof(value) == TYPE_DICTIONARY: return value.values()
	return []

func record(key: String, id: String) -> Dictionary:
	var value: Variant = content.get(key,{})
	if typeof(value)==TYPE_DICTIONARY and value.has(id): return value[id]
	for row in records(key):
		if String(row.get("id",row.get("map_id",""))) == id: return row
	return {}

func char_state() -> Dictionary:
	return game.state.get("character",{})

func state_digest() -> String:
	var state: Dictionary=game.snapshot()
	state.erase("applied_request_ids")
	return JSON.stringify(state).sha256_text()

func economic_state() -> Dictionary:
	var state: Dictionary=game.snapshot()
	return {"character":state.get("character",{}),"inventory":state.get("inventory",[]),"equipment":state.get("equipment",{}),"skills":state.get("skills",[]),"quests":state.get("quests",{}),"loot":state.get("loot",[])}

func brief() -> Dictionary:
	var c: Dictionary=char_state()
	return {"map_id":c.get("map_id"),"x":c.get("x"),"y":c.get("y"),"level":c.get("level"),"xp":c.get("xp"),"hp":c.get("hp"),"mp":c.get("mp"),"money":c.get("money"),"job":c.get("job"),"inventory_stacks":game.state.get("inventory",[]).size(),"skills":game.state.get("skills",[]).duplicate()}

func send(action: Dictionary, advance: float=0.0) -> Dictionary:
	sequence+=1
	if sequence>int(limits.commands):
		check("operator_command_budget",false,sequence)
		return {"status":"BUDGET"}
	var cmd: Dictionary=action.duplicate(true)
	if not cmd.has("request_id"): cmd.request_id="journey:"+str(sequence)
	var before:=brief()
	var result: Dictionary=game.command(cmd)
	transcript.append({"phase":active_phase,"sequence":sequence,"command":cmd,"result":result.duplicate(true),"before":before,"after":brief()})
	if advance>0: advance_time(advance)
	return result

func advance_time(seconds: float) -> void:
	# Production fixed-step tick input, never direct state assignment.
	var remaining:=seconds
	var events: Array=[]
	while remaining>0.00001:
		var step:=minf(0.1,remaining)
		var response: Dictionary=game.tick(step)
		events.append_array(response.get("events",[]))
		remaining-=step
	transcript.append({"phase":active_phase,"tick":seconds,"events":events,"after":brief()})

func mark(name: String) -> void:
	milestones.append({"name":name,"sequence":sequence,"state":game.snapshot()})
	transcript.append({"phase":active_phase,"milestone":{"name":name,"sequence":sequence},"after":brief()})
	print("JOURNEY_MILESTONE "+name+" "+JSON.stringify(brief()))

func ok(result: Dictionary) -> bool:
	return bool(result.get("ok",false)) or String(result.get("status", "")) in ["OK","APPLIED","SUCCESS","ACCEPTED","CREATED","STARTED","SAVED","DUPLICATE"]

func item_count(item_id: String) -> int:
	var total:=0
	for instance in game.state.get("inventory",[]):
		if instance.get("item_id")==item_id: total+=int(instance.get("quantity",1))
	return total

func instance_for(item_id: String) -> Dictionary:
	for instance in game.state.get("inventory",[]):
		if instance.get("item_id")==item_id: return instance
	return {}

func item_id(name: String) -> String:
	for row in records("items"):
		if row.get("name")==name: return String(row.id)
	return ""

func skill_id(name: String, job: String="") -> String:
	for row in records("skills"):
		if row.get("name")==name and (job.is_empty() or row.get("job")==job): return String(row.id)
	return ""

func occupied(map_id: String,x: int,y: int) -> bool:
	for npc in records("npcs"):
		if str(npc.map_id)==map_id and int(npc.x)==x and int(npc.y)==y: return true
	for monster in game.state.get("monsters",{}).values():
		if bool(monster.alive) and str(monster.map_id)==map_id and int(monster.x)==x and int(monster.y)==y: return true
	return false

func path_to(map_id: String,target: Vector2i,near: int=0,allow_exit: bool=false) -> Array:
	var c:=char_state()
	if str(c.map_id)!=map_id: return []
	var start:=Vector2i(int(c.x),int(c.y))
	var queue: Array=[start]
	var parents: Dictionary={start:start}
	var cursor:=0
	var exits: Dictionary={}
	for portal in record("maps",map_id).get("exits",[]): exits[Vector2i(int(portal.x),int(portal.y))]=true
	while cursor<queue.size() and cursor<int(limits.path_nodes):
		var point: Vector2i=queue[cursor];cursor+=1
		if absi(point.x-target.x)+absi(point.y-target.y)<=near:
			var path: Array=[]
			while point!=start:
				path.push_front(point)
				point=parents[point]
			return path
		for delta in [Vector2i(0,-1),Vector2i(1,0),Vector2i(0,1),Vector2i(-1,0)]:
			var next: Vector2i=point+delta
			if parents.has(next) or not game.valid_position(map_id,next.x,next.y) or occupied(map_id,next.x,next.y): continue
			if exits.has(next) and not (allow_exit and next==target): continue
			parents[next]=point;queue.append(next)
	return []

func walk_to(map_id: String,x: int,y: int,near: int=0,exit_ok: bool=false) -> bool:
	var retries:=0
	while str(char_state().map_id)==map_id and retries<600:
		var c:=char_state()
		if absi(int(c.x)-x)+absi(int(c.y)-y)<=near: return true
		var path:=path_to(map_id,Vector2i(x,y),near,exit_ok)
		if path.is_empty(): return false
		# Replan after each bounded segment as production monsters can wander.
		for point in path.slice(0,mini(8,path.size())):
			c=char_state()
			var result:=send({"type":"move","dx":point.x-int(c.x),"dy":point.y-int(c.y)},0.2)
			if not ok(result): break
			if str(char_state().map_id)!=map_id: return exit_ok
		retries+=1
	return str(char_state().map_id)!=map_id and exit_ok

func travel_to(target_map: String) -> bool:
	var budget:=30
	while str(char_state().map_id)!=target_map and budget>0:
		var source:=str(char_state().map_id)
		var queue: Array=[source]
		var parent: Dictionary={source:""}
		var via: Dictionary={}
		var cursor:=0
		while cursor<queue.size() and not parent.has(target_map):
			var map_id: String=queue[cursor];cursor+=1
			for portal in record("maps",map_id).get("exits",[]):
				var dest:=str(portal.to_map)
				if parent.has(dest) or int(char_state().level)<int(portal.get("minimum_level",1)): continue
				parent[dest]=map_id;via[dest]=portal;queue.append(dest)
		if not parent.has(target_map): return false
		var next:=target_map
		while str(parent[next])!=source: next=str(parent[next])
		var portal: Dictionary=via[next]
		if not walk_to(source,int(portal.x),int(portal.y),0,true): return false
		budget-=1
	return str(char_state().map_id)==target_map

func approach_npc(npc_id: String) -> bool:
	var npc:=record("npcs",npc_id)
	if npc.is_empty() or not travel_to(str(npc.map_id)): return false
	return walk_to(str(npc.map_id),int(npc.x),int(npc.y),1)

func teacher_for(job: String) -> String:
	for npc in records("npcs"):
		if npc.get("job")==job and "change_job" in npc.get("services",[]): return str(npc.id)
	return ""

func merchant_for(item: String,operation: String) -> String:
	for npc in records("npcs"):
		if npc.get("shop",{}).has(item) and npc.shop[item].get(operation)!=null: return str(npc.id)
	return ""

func nearest_monster(drop_item: String="") -> String:
	var chosen:=""
	var distance:=1000000
	for id in game.state.get("monsters",{}):
		var monster: Dictionary=game.state.monsters[id]
		if not monster.alive or str(monster.map_id)!=str(char_state().map_id): continue
		if not drop_item.is_empty():
			var match_drop:=false
			for drop in record("monsters",str(monster.monster_id)).get("drops",[]):
				if str(drop.item_id)==drop_item: match_drop=true
			if not match_drop: continue
		var delta:=absi(int(monster.x)-int(char_state().x))+absi(int(monster.y)-int(char_state().y))
		if delta<distance:
			distance=delta;chosen=str(id)
	return chosen

func collect_loot() -> bool:
	for loot in game.state.get("loot",[]).duplicate(true):
		if str(loot.map_id)!=str(char_state().map_id): continue
		if not walk_to(str(loot.map_id),int(loot.x),int(loot.y),1): return false
		var pickup_cmd: Dictionary={"type":"pickup","loot_id":str(loot.loot_id),"request_id":"pickup:"+str(sequence+1)}
		var pickup:=send(pickup_cmd)
		if not ok(pickup): return false
		if not loot_edge_verified and active_phase=="natural":
			var after_pickup:=canonicalizer.canonical(game.snapshot())
			var duplicate:=send(pickup_cmd)
			check("natural_drop_pickup_request_exactly_once",duplicate.status=="DUPLICATE" and canonicalizer.canonical(game.snapshot())==after_pickup,duplicate)
			expect_refusal("natural_drop_cannot_be_picked_twice",{"type":"pickup","loot_id":str(loot.loot_id)},["LOOT_NOT_FOUND"])
			loot_edge_verified=true
	return true

func fight(target_id: String) -> bool:
	var budget:=200
	while budget>0:
		if bool(char_state().dead):
			var respawn:=send({"type":"respawn"},0.2)
			if not ok(respawn): return false
			return true # legitimate death recovery; next hunt iteration travels back.
		var target: Dictionary=game.state.monsters.get(target_id,{})
		if target.is_empty() or not bool(target.alive):
			if not kill_edge_verified and active_phase=="natural" and not target.is_empty():
				var reward_state:=canonicalizer.canonical(game.snapshot())
				var dead_attack:=send({"type":"attack","target_id":target_id})
				check("dead_monster_cannot_award_XP_twice",dead_attack.status=="REFUSED" and canonicalizer.canonical(game.snapshot())==reward_state,dead_attack)
				kill_edge_verified=true
			return collect_loot()
		if not walk_to(str(target.map_id),int(target.x),int(target.y),1): return false
		var result:=send({"type":"attack","target_id":target_id},0.55)
		if not ok(result) and result.get("reason") not in ["TARGET_OUT_OF_REACH","ACTION_COOLDOWN"]: return false
		budget-=1
	return false

func hunt_until(level: int,requirements: Dictionary,money: int) -> bool:
	var field:=""
	for map in records("maps"):
		if not map.get("spawns",[]).is_empty(): field=str(map.id);break
	if field.is_empty(): return false
	var budget:=int(limits.kills)
	while budget>0:
		var enough:=int(char_state().level)>=level and int(char_state().money)>=money
		var wanted:=""
		for required in requirements:
			if item_count(str(required))<int(requirements[required]):
				enough=false;wanted=str(required);break
		if enough: return true
		if not travel_to(field): return false
		var target:=nearest_monster(wanted)
		if target.is_empty():
			advance_time(1.0);budget-=1;continue
		if not fight(target): return false
		budget-=1
	return false

func test_natural_casts(heal: String,fire: String,back: String) -> bool:
	var field:=""
	for map in records("maps"):
		if not map.get("spawns",[]).is_empty(): field=str(map.id);break
	if not check("learned_spells_walk_to_hunting",travel_to(field),brief()): return false
	var target:=nearest_monster()
	if target.is_empty(): advance_time(2.0);target=nearest_monster()
	if target.is_empty(): return check("live_monster_for_skill",false,brief())
	var monster: Dictionary=game.state.monsters[target]
	if not walk_to(str(monster.map_id),int(monster.x),int(monster.y),1): return check("approach_for_real_injury",false)
	# A normal attack provokes the selected retaliating creature; no HP assignment.
	send({"type":"attack","target_id":target},0.4)
	for _attempt in range(8):
		if int(char_state().hp)<int(char_state().hp_max): break
		monster=game.state.monsters[target]
		if not monster.alive: break
		walk_to(str(monster.map_id),int(monster.x),int(monster.y),1)
		advance_time(0.5)
	var before_hp:=int(char_state().hp)
	var before_mp:=int(char_state().mp)
	var healed:=send({"type":"cast","skill_id":heal},float(record("skills",heal).get("impact_delay",0.25))+0.1)
	check("naturally_learned_heal_changes_HP_and_MP",ok(healed) and int(char_state().hp)>before_hp and int(char_state().mp)<=before_mp-int(record("skills",heal).get("mp_cost",0)),{"result":healed,"hp_before":before_hp,"hp_after":char_state().hp,"mp_before":before_mp,"mp_after":char_state().mp})
	advance_time(1.0)
	target=nearest_monster()
	if target.is_empty(): advance_time(2.0);target=nearest_monster()
	if target.is_empty(): return check("fire_spell_live_target",false)
	monster=game.state.monsters[target]
	if not walk_to(str(monster.map_id),int(monster.x),int(monster.y),2): return check("fire_spell_approach",false)
	var target_hp:=int(game.state.monsters[target].hp)
	var target_generation:=int(game.state.monsters[target].generation)
	before_mp=int(char_state().mp)
	var cast:=send({"type":"cast","skill_id":fire,"target_id":target},float(record("skills",fire).get("impact_delay",0.25))+0.1)
	var applied: Dictionary=game.state.monsters[target]
	check("naturally_learned_fire_real_target_damage_MP",ok(cast) and int(applied.generation)==target_generation and int(applied.hp)<target_hp and int(char_state().mp)<=before_mp-int(record("skills",fire).get("mp_cost",0)),{"result":cast,"target_hp_before":target_hp,"target_after":applied,"mp_before":before_mp,"mp_after":char_state().mp})
	mark("real_heal_and_damage_spells_consumed_MP")
	var invalid_before:=canonicalizer.canonical(game.snapshot())
	var invalid_direction:=send({"type":"cast","skill_id":back,"direction":"invalid"})
	check("invalid_return_direction_no_cost_or_move",invalid_direction.status=="REFUSED" and canonicalizer.canonical(game.snapshot())==invalid_before,invalid_direction)
	for direction in ["east","west","south","north"]:
		advance_time(1.1)
		var definition:=record("skills",back)
		var mp_cost:=int(definition.get("mp_cost",0))
		var budget:=100
		while int(char_state().mp)<mp_cost and budget>0:
			advance_time(1.0);budget-=1
		var result:=send({"type":"cast","skill_id":back,"direction":direction},float(definition.get("impact_delay",0.25))+0.15)
		var destination: Dictionary=content.gates[direction]
		check("natural_directional_return_"+direction,ok(result) and str(char_state().map_id)==str(destination.map_id) and int(char_state().x)==int(destination.x) and int(char_state().y)==int(destination.y),{"result":result,"actual":brief(),"destination":destination})
	mark("four_distinct_direction_returns")
	return failures==0

func test_process_restart() -> void:
	var Store=load("res://storage/gameplay_store.gd")
	var store=Store.new()
	var saved_path:="user://gameplay-p3/journey-"+str(Time.get_ticks_usec())+".json"
	var save: Dictionary=store.write_game(saved_path,natural_end,owner,content)
	if not check("natural_gameplay_save_written",save.status=="SAVED",save): return
	var child_report:=report_path+".reload.json"
	var output: Array=[]
	var script_path: String=get_script().resource_path
	if script_path.begins_with("res://"): script_path=ProjectSettings.globalize_path(script_path)
	var args: PackedStringArray=["--headless","--path",ProjectSettings.globalize_path("res://"),"--script",script_path,"--","--content",content_path,"--phase","reload","--saved-user-path",saved_path,"--report",child_report]
	var exit_code:=OS.execute(OS.get_executable_path(),args,output,true)
	var child: Variant=JSON.parse_string(FileAccess.get_file_as_string(child_report))
	# Compare exactly the documented JSON persistence representation. Godot JSON
	# encoding rounds sub-ULP simulation float residue; discrete gameplay fields
	# and the serialized timestamps must still match with no tolerance fallback.
	var serialized_expected: Variant=JSON.parse_string(store._canonical(natural_end))
	var equal:=typeof(child)==TYPE_DICTIONARY and canonicalizer.canonical(child.get("payload",{}))==canonicalizer.canonical(serialized_expected)
	check("separate_process_restart_exact_gameplay_state",exit_code==0 and equal,{"exit_code":exit_code,"save_path":saved_path,"child_report":child_report.get_file(),"output":output,"same_state":equal})
	check("separate_process_can_continue_with_next_persisted_request_sequence",typeof(child)==TYPE_DICTIONARY and child.get("post_restart_move",{}).get("status")=="OK" and child.get("post_restart_save",{}).get("status")=="SAVED",{"move":child.get("post_restart_move",{}),"save":child.get("post_restart_save",{})} if typeof(child)==TYPE_DICTIONARY else child)
	# The primary save remains a non-user synthetic test artifact for reproducibility.

func reload_worker() -> void:
	var Store=load("res://storage/gameplay_store.gd")
	var store=Store.new()
	var saved: Dictionary=store.read_game(_arg("--saved-user-path"),owner,content)
	var restored: Dictionary={}
	if saved.status in ["OK","RECOVERED_BACKUP"]: restored=game.restore(saved.payload)
	var loaded_payload: Dictionary=game.snapshot()
	var continue_result: Dictionary={"status":"NOT_RUN"}
	if restored.get("status")=="OK":
		# Persisted move cooldown remains active after restart. Let normal time
		# advance before the next input, preserving the loaded snapshot above.
		game.tick(0.5)
		var next_sequence:=int(game.state.request_watermarks.get("journey",0))+1
		for delta in [Vector2i(-1,0),Vector2i(1,0),Vector2i(0,1),Vector2i(0,-1)]:
			var c:=char_state()
			if not game.valid_position(str(c.map_id),int(c.x)+delta.x,int(c.y)+delta.y) or occupied(str(c.map_id),int(c.x)+delta.x,int(c.y)+delta.y): continue
			continue_result=game.command({"type":"move","dx":delta.x,"dy":delta.y,"request_id":"journey:"+str(next_sequence)})
			break
	var continued_save: Dictionary={"status":"NOT_RUN"}
	if continue_result.get("status")=="OK": continued_save=store.write_game(_arg("--saved-user-path"),game.snapshot(),owner,content)
	var status:="PASS" if saved.status=="OK" and restored.get("status")=="OK" and continue_result.get("status")=="OK" and continued_save.get("status")=="SAVED" else "FAIL"
	var file:=FileAccess.open(report_path,FileAccess.WRITE)
	if file: file.store_string(JSON.stringify({"schema":"baram.gameplay-process-reload/1","status":status,"read_status":saved.status,"restore":restored,"payload":loaded_payload,"post_restart_move":continue_result,"post_restart_save":continued_save,"post_restart_state":game.snapshot()},"  ")+"\n")
	print("RELOAD_RESULT "+status)
	quit(0 if status=="PASS" else 1)

func fixture_inventory(payload: Dictionary,requirements: Dictionary) -> void:
	# Explicit branch fixture provisioning; never called for the natural character.
	for id in requirements:
		var remaining:=int(requirements[id])
		var max_stack:=int(record("items",id).get("stack_max",99))
		while remaining>0:
			var quantity:=mini(max_stack,remaining)
			payload.inventory.append({"instance_id":"fixture:"+str(payload.next_instance_id),"item_id":id,"quantity":quantity,"durability":int(record("items",id).get("durability",0))})
			payload.next_instance_id=int(payload.next_instance_id)+1
			remaining-=quantity

func test_job_fixtures() -> void:
	active_phase="explicit_branch_fixture"
	var EngineClass=load("res://state/gameplay_state.gd")
	for job in ["전사","도적","도사"]:
		var id:=skill_id("누리의기원",job)
		var definition:=record("skills",id)
		var teacher:=teacher_for(job)
		var npc:=record("npcs",teacher)
		var payload:=natural_end.duplicate(true)
		var level:=int(definition.get("learn_level",5))
		payload.character.job="commoner";payload.character.desired_job=job
		payload.character.level=level;payload.character.xp=int(content.xp_thresholds[level-1])
		payload.character.money=10000;payload.character.hp=int(payload.character.hp_max)-10
		payload.character.mp=payload.character.mp_max;payload.character.dead=false
		payload.character.map_id=npc.map_id;payload.character.x=int(npc.x);payload.character.y=int(npc.y)+1
		payload.skills=[];payload.hotkeys={};payload.pending_actions=[];payload.cooldowns={};payload.buffs={};payload.applied_request_ids=[]
		if payload.has("request_watermarks"): payload.request_watermarks={}
		payload.inventory=[];payload.equipment={}
		fixture_inventory(payload,definition.get("ingredients",{}))
		game=EngineClass.new();game.configure(content)
		var restored: Dictionary=game.restore(payload)
		var branch: Dictionary={"job":job,"fixture":"Explicit snapshot sets level, XP, money, learning materials, position; not natural progression","skill_id":id,"skill_name":definition.get("name"),"required_level":level,"restore":restored}
		check("branch_fixture_valid_"+job,ok(restored),restored)
		if not ok(restored): fixture_results.append(branch);continue
		var low_job: Dictionary=game.snapshot()
		low_job.character.level=4;low_job.character.xp=int(content.xp_thresholds[3])
		game.restore(low_job)
		expect_refusal("branch_Lv4_job_refused_"+job,{"type":"change_job","npc_id":teacher,"job":job},["LEVEL_TOO_LOW"])
		game.restore(payload)
		var changed:=send({"type":"change_job","npc_id":teacher,"job":job})
		check("separate_job_change_"+job,ok(changed) and char_state().job==job,changed)
		var prepared: Dictionary=game.snapshot()
		var low_skill: Dictionary=prepared.duplicate(true)
		low_skill.character.level=level-1;low_skill.character.xp=int(content.xp_thresholds[level-2])
		game.restore(low_skill)
		expect_refusal("branch_skill_actual_level_gate_"+job,{"type":"learn","npc_id":teacher,"skill_id":id},["LEVEL_TOO_LOW"])
		game.restore(prepared)
		var missing_material: Dictionary=prepared.duplicate(true)
		missing_material.inventory=[]
		game.restore(missing_material)
		expect_refusal("branch_missing_material_no_cost_"+job,{"type":"learn","npc_id":teacher,"skill_id":id},["INSUFFICIENT_MATERIALS"])
		game.restore(prepared)
		expect_refusal("branch_other_job_skill_refused_"+job,{"type":"learn","npc_id":teacher,"skill_id":skill_id("화염주(화)","주술사")},["WRONG_JOB","WRONG_SKILL_TEACHER"])
		var initial_materials: Dictionary={}
		for material in definition.get("ingredients",{}): initial_materials[material]=item_count(material)
		var money_before:=int(char_state().money)
		var learned:=send({"type":"learn","npc_id":teacher,"skill_id":id})
		var exact:=int(char_state().money)==money_before-int(definition.get("learn_money",0))
		for material in initial_materials: exact=exact and item_count(material)==int(initial_materials[material])-int(definition.ingredients[material])
		check("separate_job_learning_"+job,ok(learned) and exact and id in game.state.skills,{"result":learned,"materials_before":initial_materials})
		expect_refusal("branch_already_learned_no_double_cost_"+job,{"type":"learn","npc_id":teacher,"skill_id":id},["ALREADY_LEARNED"])
		var hp_before:=int(char_state().hp)
		var mp_before:=int(char_state().mp)
		var cast:=send({"type":"cast","skill_id":id},float(definition.get("impact_delay",0.25))+0.1)
		check("separate_job_representative_effect_"+job,ok(cast) and int(char_state().hp)>hp_before and int(char_state().mp)<=mp_before-int(definition.get("mp_cost",0)),{"result":cast,"before_hp":hp_before,"after_hp":char_state().hp,"before_mp":mp_before,"after_mp":char_state().mp})
		branch.results={"change_job":changed,"learn":learned,"cast":cast,"end":brief()}
		fixture_results.append(branch)

func expect_refusal(id: String,cmd: Dictionary,reasons: Array) -> bool:
	var before:=canonicalizer.canonical(game.snapshot())
	var result:=send(cmd)
	return check(id,result.status=="REFUSED" and result.reason in reasons and canonicalizer.canonical(game.snapshot())==before,result)

func test_death_fixture() -> void:
	active_phase="explicit_death_fixture"
	var EngineClass=load("res://state/gameplay_state.gd")
	var payload:=natural_end.duplicate(true)
	var chosen: Dictionary={}
	for candidate in payload.monsters.values():
		if candidate.alive and record("monsters",str(candidate.monster_id)).name=="다람쥐": chosen=candidate;break
	if not check("death_fixture_live_monster_exists",not chosen.is_empty()): return
	var spawn_point:=Vector2i(int(chosen.x)+1,int(chosen.y))
	for delta in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1)]:
		var point: Vector2i=Vector2i(int(chosen.x),int(chosen.y))+delta
		if game.valid_position(str(chosen.map_id),point.x,point.y): spawn_point=point;break
	payload.character.map_id=chosen.map_id;payload.character.x=spawn_point.x;payload.character.y=spawn_point.y
	payload.character.hp=1;payload.character.dead=false;payload.cooldowns={};payload.pending_actions=[]
	game=EngineClass.new();game.configure(content)
	var restored: Dictionary=game.restore(payload)
	if not check("explicit_death_fixture_restored",ok(restored),restored): return
	if game.state.equipment.has("weapon"): send({"type":"unequip","slot":"weapon"})
	var xp_before:=int(char_state().xp)
	var inventory_before:=canonicalizer.canonical(game.state.inventory)
	var attack:=send({"type":"attack","target_id":str(chosen.id)},0.6)
	for _attempt in range(10):
		if bool(char_state().dead): break
		var current: Dictionary=game.state.monsters[str(chosen.id)]
		if not current.alive: break
		walk_to(str(current.map_id),int(current.x),int(current.y),1)
		advance_time(0.5)
	if not check("normal_monster_hit_causes_fixture_death",bool(char_state().dead) and int(char_state().hp)==0,{"attack":attack,"state":brief()}): return
	expect_refusal("dead_movement_refused_without_mutation",{"type":"move","dx":1,"dy":0},["CHARACTER_DEAD"])
	expect_refusal("dead_directional_return_refused",{"type":"cast","skill_id":skill_id("비영사천문"),"direction":"north"},["CHARACTER_DEAD"])
	var resurrected:=send({"type":"respawn"},0.2)
	var destination: Dictionary=content.respawn
	check("real_resurrection_preserves_progress_and_unblocks",ok(resurrected) and not bool(char_state().dead) and int(char_state().hp)>0 and int(char_state().xp)==xp_before and canonicalizer.canonical(game.state.inventory)==inventory_before and str(char_state().map_id)==str(destination.map_id) and int(char_state().x)==int(destination.x) and int(char_state().y)==int(destination.y),{"result":resurrected,"state":brief()})
	fixture_results.append({"fixture":"ExplicitHP1/position fixture then production monster attack/death/respawn; not natural death","kind":"death_and_resurrection","end":brief()})

func test_long_request_ledger() -> void:
	active_phase="explicit_ledger_fixture"
	var EngineClass=load("res://state/gameplay_state.gd")
	var payload:=natural_end.duplicate(true)
	var teacher:=record("npcs",teacher_for("도사"))
	payload.character.map_id=teacher.map_id;payload.character.x=int(teacher.x);payload.character.y=int(teacher.y)+1
	payload.cooldowns={};payload.pending_actions=[];payload.applied_request_ids=[]
	if payload.has("request_watermarks"): payload.request_watermarks={}
	game=EngineClass.new();game.configure(content)
	var restored: Dictionary=game.restore(payload)
	if not check("ledger_fixture_restored",ok(restored),restored): return
	var first: Dictionary={"type":"move","dx":1,"dy":0,"request_id":"longstream:1"}
	var result:=send(first,0.2)
	var completed:=0
	if ok(result): completed=1
	for i in range(2,2052):
		result=send({"type":"move","dx":-1 if i%2==0 else 1,"dy":0,"request_id":"longstream:"+str(i)},0.2)
		if not ok(result): break
		completed+=1
	check("more_than_2048_actions_do_not_permanently_lock_game",completed==2051,{"successful_actions":completed,"last":result,"ledger_size":game.state.applied_request_ids.size()})
	var before:=canonicalizer.canonical(game.snapshot())
	var duplicate:=send(first)
	check("evicted_old_request_is_still_exactly_once",duplicate.status=="DUPLICATE" and canonicalizer.canonical(game.snapshot())==before,duplicate)
	fixture_results.append({"fixture":"Explicit safe-interior fixture, then2051 normal move commands; no ledger mutation after commands begin","kind":"long_request_stream","completed":completed})

func finance_and_repair(reserve: Dictionary,forge: String,weapon: String) -> bool:
	var owned:=instance_for(weapon)
	var definition:=record("items",weapon)
	var missing:=int(definition.get("durability",0))-int(owned.get("durability",0))
	if missing<=0: return check("natural_weapon_wear_observed",false,owned)
	var rate:=float(record("npcs",forge).get("repair_cost_per_point",content.get("config",{}).get("repair_price_per_point",0.1)))
	var cost:=maxi(1,int(ceil(float(missing)*rate)))
	var acorn:=item_id("도토리")
	var merchant:=merchant_for(acorn,"sell_price")
	var price:=int(record("npcs",merchant).shop[acorn].sell_price)
	var quantity:=maxi(1,int(ceil(float(maxi(0,cost-int(char_state().money)))/float(price))))
	var financed:=false
	for attempt in range(4):
		var required:=reserve.duplicate(true)
		required[acorn]=int(reserve.get(acorn,0))+quantity+4
		if not check("normal_hunting_finances_repair_round_"+str(attempt),hunt_until(int(char_state().level),required,0),{"repair_cost_initial":cost,"needed_materials":required,"state":brief()}): return false
		owned=instance_for(weapon)
		missing=int(definition.get("durability",0))-int(owned.durability)
		cost=maxi(1,int(ceil(float(missing)*rate)))
		quantity=maxi(1,int(ceil(float(maxi(0,cost-int(char_state().money)))/float(price))))
		if item_count(acorn)-quantity>=int(reserve.get(acorn,0)):
			financed=true;break
	if not check("repair_financing_converges_from_actual_wear",financed,{"available":item_count(acorn),"cost":cost,"quantity":quantity}): return false
	if not check("repair_sale_respects_learning_reserve",item_count(acorn)-quantity>=int(reserve.get(acorn,0)),{"available":item_count(acorn),"sale_quantity":quantity,"reserve":reserve.get(acorn,0),"repair_cost":cost}): return false
	if not approach_npc(merchant): return check("walk_to_repair_financing_merchant",false)
	owned=instance_for(acorn)
	var sold:=send({"type":"sell","npc_id":merchant,"instance_id":owned.instance_id,"quantity":quantity})
	if not check("legitimate_surplus_sale_pays_repair",ok(sold) and int(char_state().money)>=cost,sold): return false
	if not approach_npc(forge): return check("walk_to_repair_forge",false)
	owned=instance_for(weapon)
	var money_before:=int(char_state().money)
	var repaired:=send({"type":"repair","npc_id":forge,"instance_id":owned.instance_id})
	var updated:=instance_for(weapon)
	check("natural_repair_exact_money_and_full_durability",ok(repaired) and int(char_state().money)==money_before-cost and int(updated.durability)==int(definition.durability),{"result":repaired,"money_before":money_before,"cost":cost,"durability_before":owned.durability,"durability_after":updated.durability})
	mark("hunted_surplus_sold_and_repaired_actual_weapon")
	return ok(repaired)
