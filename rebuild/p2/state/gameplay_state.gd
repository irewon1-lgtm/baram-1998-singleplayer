extends RefCounted
## One authoritative offline P3 state. Definitions are immutable; UI sends commands.
## All costs/rewards commit atomically; visual frames never drive combat or RNG.
const JOBS := ["전사", "도적", "주술사", "도사"]
const STEP := 0.05
const MAX_REQUESTS := 2048
const MAX_VALUE := 1000000000
const SKILL_KINDS := ["damage","heal","buff","debuff","status","return","shrine","identify","restore_mp","summon","cleanse","revive","loot","blink"]
const STATUS_KINDS := ["stealth","paralysis","poison","slow","silence","protection","haste","blindness"]
var state: Dictionary = {}
var data: Dictionary = {}
var errors: Array[String] = []
var _blocked: Dictionary = {}
var _events: Array = []
# Transaction-local indices. They are rebuilt from the full saved world, never
# serialized; inactive records remain in state and keep their original IDs/order.
var _in_transaction := false
var _map_monster_ids: Dictionary = {}
var _detached_monsters: Dictionary = {}
var _status_monster_ids: Array = []
var _npc_cells: Dictionary = {}
var _edge_masks: Dictionary = {}
var _indexed_maps: Dictionary = {}
var _indexed_monster_count := -1

func configure(definitions: Dictionary) -> bool:
	errors.clear()
	for key in ["profile", "maps", "npcs", "items", "monsters", "skills", "start", "gates", "respawn", "xp_thresholds"]:
		if not definitions.has(key): errors.append("MISSING_DEFINITION:"+key)
	if not errors.is_empty(): return false
	if definitions.maps.is_empty() or definitions.xp_thresholds.size()<5: errors.append("EMPTY_WORLD_OR_GROWTH")
	data=definitions.duplicate(true)
	_blocked.clear()
	_edge_masks.clear()
	_indexed_monster_count=-1
	_npc_cells.clear()
	for map_id in data.maps:
		var map: Dictionary=data.maps[map_id]
		if int(map.get("width",0))<=0 or int(map.get("height",0))<=0:
			errors.append("INVALID_MAP_SIZE:"+str(map_id))
		_edge_masks[map_id]=Marshalls.base64_to_raw(str(map.edge_masks_base64)) if map.has("edge_masks_base64") else PackedByteArray(map.get("edge_masks",[]))
		if not _edge_masks[map_id].is_empty() and _edge_masks[map_id].size()!=int(map.width)*int(map.height): errors.append("INVALID_EDGE_MASK_COUNT:"+str(map_id))
		var cells:=PackedByteArray()
		if map.has("blocked_base64"):
			cells=Marshalls.base64_to_raw(str(map.blocked_base64))
			if cells.size()!=int(map.width)*int(map.height):errors.append("INVALID_BLOCKED_COUNT:"+str(map_id))
		else:
			cells.resize(int(map.width)*int(map.height));cells.fill(0)
			for point in map.get("blocked",[]):
				if int(point[0])>=0 and int(point[0])<int(map.width) and int(point[1])>=0 and int(point[1])<int(map.height):cells[int(point[1])*int(map.width)+int(point[0])]=1
		_blocked[map_id]=cells
	if not errors.is_empty():return false
	for map_id in data.maps:
		for exit in data.maps[map_id].get("exits",[]):
			if not valid_position(str(exit.to_map),int(exit.to_x),int(exit.to_y)): errors.append("INVALID_EXIT_DESTINATION:"+str(map_id))
	for id in data.npcs:
		var npc: Dictionary=data.npcs[id]
		var npc_map: String=str(npc.map_id)
		if not _npc_cells.has(npc_map): _npc_cells[npc_map]={}
		_npc_cells[npc_map][Vector2i(int(npc.x),int(npc.y))]=true
		if not valid_position(str(npc.map_id),int(npc.x),int(npc.y)): errors.append("INVALID_NPC_POSITION:"+str(id))
		for item_id in npc.get("shop",{}):
			if not data.items.has(item_id): errors.append("UNKNOWN_SHOP_ITEM:"+str(item_id))
			var trade: Dictionary=npc.shop[item_id]
			if trade.get("buy_price")!=null and int(trade.buy_price)<0: errors.append("NEGATIVE_SHOP_PRICE")
			if trade.get("sell_price")!=null and int(trade.sell_price)<0: errors.append("NEGATIVE_SHOP_PRICE")
	for id in data.items:
		var item: Dictionary=data.items[id]
		if str(item.get("action_type","")) not in ["","return","cleanse"]: errors.append("UNSUPPORTED_ITEM_ACTION:"+str(id))
	for id in data.skills:
		var skill: Dictionary=data.skills[id]
		if str(skill.get("kind","")) not in SKILL_KINDS: errors.append("UNSUPPORTED_SKILL:"+str(id))
		if str(skill.get("delivery","melee")) not in ["melee","projectile","area"]: errors.append("UNSUPPORTED_DELIVERY:"+str(id))
		if str(skill.get("on_hit_status","")) not in STATUS_KINDS+[""]: errors.append("UNSUPPORTED_ON_HIT_STATUS:"+str(id))
		if str(skill.get("status","")) not in STATUS_KINDS+[""]: errors.append("UNSUPPORTED_STATUS:"+str(id))
		if str(skill.get("kind",""))=="summon" and not data.monsters.has(str(skill.get("monster_id",""))): errors.append("UNKNOWN_SUMMON_MONSTER:"+str(id))
		if not str(skill.get("form_monster_id","")).is_empty() and not data.monsters.has(str(skill.form_monster_id)): errors.append("UNKNOWN_TRANSFORMATION_MONSTER:"+str(id))
		if float(skill.get("reflect_fraction",0.0))<0 or float(skill.get("reflect_fraction",0.0))>1: errors.append("INVALID_REFLECTION:"+str(id))
		for field in ["reflect_probability","evasion_chance","hp_cost_fraction","poison_hp_fraction"]:
			if float(skill.get(field,0.0))<0 or float(skill.get(field,0.0))>1: errors.append("INVALID_SKILL_FRACTION:"+str(id)+":"+field)
		if typeof(skill.get("directional_pattern",[]))!=TYPE_ARRAY: errors.append("INVALID_DIRECTIONAL_PATTERN:"+str(id))
		else:
			for direction in skill.get("directional_pattern",[]):
				if direction not in ["front","back","left","right"]: errors.append("UNSUPPORTED_DIRECTIONAL_PATTERN:"+str(id))
		for status in skill.get("cleanse_statuses",[]):
			if str(status) not in STATUS_KINDS: errors.append("UNSUPPORTED_CLEANSE_STATUS:"+str(id))
		if str(skill.get("kind","")) in ["debuff","status"] and str(skill.get("status","")) not in STATUS_KINDS: errors.append("STATUS_REQUIRED:"+str(id))
		if float(skill.get("heal_fraction",0.0))<0 or float(skill.get("heal_fraction",0.0))>1: errors.append("INVALID_LIFESTEAL:"+str(id))
		if int(skill.get("mp_cost",0))<0 or int(skill.get("hp_cost",0))<0 or float(skill.get("impact_delay",0.0))<0 or float(skill.get("duration",1.0))<=0: errors.append("INVALID_SKILL_COST_OR_DURATION:"+str(id))
		for item_id in skill.get("ingredients",{}):
			if not data.items.has(item_id): errors.append("UNKNOWN_LEARNING_ITEM:"+str(item_id))
		for teacher_id in skill.get("teacher_ids",[]):
			if not data.npcs.has(teacher_id): errors.append("UNKNOWN_TEACHER:"+str(teacher_id))
	for id in data.monsters:
		for drop in data.monsters[id].get("drops",[]):
			if not data.items.has(str(drop.item_id)): errors.append("UNKNOWN_DROP_ITEM:"+str(drop.item_id))
	for map_id in data.maps:
		for spawn in data.maps[map_id].get("spawns",[]):
			if not data.monsters.has(str(spawn.monster_id)) or not valid_position(str(map_id),int(spawn.x),int(spawn.y)): errors.append("INVALID_SPAWN:"+str(spawn.get("id","")))
	if not valid_position(str(data.start.map_id),int(data.start.x),int(data.start.y)): errors.append("INVALID_START")
	if not valid_position(str(data.respawn.map_id),int(data.respawn.x),int(data.respawn.y)): errors.append("INVALID_RESPAWN")
	var previous := -1
	for threshold in data.xp_thresholds:
		if not _integer(threshold,0,MAX_VALUE) or int(threshold)<=previous: errors.append("INVALID_XP_THRESHOLDS")
		previous=int(threshold)
	for direction in data.gates:
		var gate: Dictionary=data.gates[direction]
		if not valid_position(str(gate.map_id),int(gate.x),int(gate.y)): errors.append("INVALID_GATE:"+str(direction))
	for id in data.get("quests",{}):
		var quest: Dictionary=data.quests[id]
		if not data.npcs.has(str(quest.get("npc_id",""))): errors.append("UNKNOWN_QUEST_NPC:"+str(id))
		for objective in quest.get("objectives",[]):
			var kind: String=str(objective.get("kind",""));var reference: String=str(objective.get("id",""))
			if kind not in ["kill","collect","visit","talk","craft","equip"] or int(objective.get("count",1))<1: errors.append("INVALID_QUEST_OBJECTIVE:"+str(id))
			elif not data.get({"kill":"monsters","collect":"items","visit":"maps","talk":"npcs","craft":"recipes","equip":"items"}[kind],{}).has(reference): errors.append("UNKNOWN_QUEST_REFERENCE:"+str(id))
		for item_id in quest.get("rewards",{}).get("items",{}):
			if not data.items.has(item_id): errors.append("UNKNOWN_QUEST_REWARD:"+str(id))
	for id in data.get("recipes",{}):
		var recipe: Dictionary=data.recipes[id]
		if not data.npcs.has(str(recipe.get("npc_id",""))): errors.append("UNKNOWN_CRAFT_NPC:"+str(id))
		for field in ["ingredients","results"]:
			for item_id in recipe.get(field,{}):
				if not data.items.has(item_id) or int(recipe[field][item_id])<1: errors.append("INVALID_RECIPE_ITEM:"+str(id))
	for id in data.get("training_rules",{}):
		var training: Dictionary=data.training_rules[id]
		if str(training.get("stat","")) not in ["strength","dexterity","intelligence","hp_max","mp_max"] or int(training.get("xp_cost",0))<=0 or int(training.get("increase",0))<=0 or int(training.get("cap",0))<=0: errors.append("INVALID_TRAINING_RULE:"+str(id))
		for teacher in training.get("teacher_ids",[]):
			if not data.npcs.has(str(teacher)): errors.append("UNKNOWN_TRAINING_TEACHER:"+str(id))
	for id in data.get("advancements",{}):
		var advancement: Dictionary=data.advancements[id]
		if str(advancement.get("job","")) not in JOBS: errors.append("UNKNOWN_ADVANCEMENT_JOB:"+str(id))
		for teacher in advancement.get("teacher_ids",[]):
			if not data.npcs.has(str(teacher)): errors.append("UNKNOWN_ADVANCEMENT_TEACHER:"+str(id))
	return errors.is_empty()

func valid_position(map_id: String,x: int,y: int) -> bool:
	if not data.get("maps",{}).has(map_id): return false
	var map: Dictionary=data.maps[map_id]
	return x>=0 and y>=0 and x<int(map.width) and y<int(map.height) and _blocked[map_id][y*int(map.width)+x]==0

func _config(key: String,fallback: Variant) -> Variant:
	return data.get("config",{}).get(key,fallback)

func can_step(map_id: String,from_x: int,from_y: int,to_x: int,to_y: int) -> bool:
	if not valid_position(map_id,from_x,from_y) or not valid_position(map_id,to_x,to_y): return false
	var dx:=to_x-from_x;var dy:=to_y-from_y
	if absi(dx)+absi(dy)!=1:return false
	var masks: PackedByteArray=_edge_masks.get(map_id,PackedByteArray())
	if masks.is_empty():return true
	var w: int=int(data.maps[map_id].width)
	var source_bit:=1 if dy<0 else 2 if dx>0 else 4 if dy>0 else 8
	var target_bit:=4 if dy<0 else 8 if dx>0 else 1 if dy>0 else 2
	return not ((masks[from_y*w+from_x]&source_bit) or (masks[to_y*w+to_x]&target_bit))

func _active_monster(monster: Dictionary,map_id: String="") -> bool:
	if map_id.is_empty():map_id=str(state.character.map_id)
	if str(monster.map_id)!=map_id:return false
	if not bool(_config("lazy_world_spawns",false)):return true
	return maxi(absi(int(monster.x)-int(state.character.x)),absi(int(monster.y)-int(state.character.y)))<=int(_config("active_ai_radius",32))

func _reindex_monsters() -> void:
	if _indexed_monster_count==state.monsters.size():return
	_indexed_maps={}
	for id in state.monsters:
		var mid: String=str(state.monsters[id].map_id)
		if not _indexed_maps.has(mid):_indexed_maps[mid]=[]
		_indexed_maps[mid].append(id)
	_indexed_monster_count=state.monsters.size()

func _spawn_map(map_id: String) -> void:
	for spawn in data.maps[map_id].get("spawns",[]):
		var id: String=str(spawn.id)
		if state.monsters.has(id):continue
		var definition: Dictionary=data.monsters[str(spawn.monster_id)]
		state.monsters[id]={"id":id,"monster_id":str(spawn.monster_id),"map_id":map_id,"x":int(spawn.x),"y":int(spawn.y),"spawn_x":int(spawn.x),"spawn_y":int(spawn.y),"hp":int(definition.hp),"alive":true,"generation":0,"respawn_at":0.0,"ai_at":0.0,"attack_at":0.0,"aggro":false,"respawn_seconds":float(spawn.get("respawn_seconds",definition.get("respawn_seconds",8.0)))}

func _gather(cmd: Dictionary) -> Dictionary:
	var mid: String=str(state.character.map_id)
	var id: String=str(cmd.get("node_id",""));var node: Dictionary={}
	for row in data.maps[mid].get("gather_nodes",[]):
		if str(row.id)==id:node=row;break
	if node.is_empty():return _response("REFUSED","UNKNOWN_GATHER_NODE")
	if absi(int(node.x)-int(state.character.x))+absi(int(node.y)-int(state.character.y))>1:return _response("REFUSED","GATHER_OUT_OF_REACH")
	if int(state.character.level)<int(node.get("minimum_level",1)):return _response("REFUSED","LEVEL_TOO_LOW")
	if not state.has("gathered_nodes"):state["gathered_nodes"]={}
	if _now()<float(state.gathered_nodes.get(id,0)):return _response("REFUSED","GATHER_NOT_READY")
	if not _add_item(str(node.item_id),int(node.get("quantity",1))):return _response("REFUSED","INVENTORY_FULL")
	state.gathered_nodes[id]=_now()+float(node.get("respawn_seconds",40))
	_event("gathered",{"node_id":id,"item_id":node.item_id,"quantity":node.get("quantity",1)})
	return _response("OK","GATHERED",true)

func _travel(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")),"travel")
	if npc.is_empty():return _response("REFUSED","TRAVEL_NPC_REQUIRED")
	var mid: String=str(cmd.get("map_id",""))
	if mid not in state.character.get("discovered_maps",[]) or mid==str(state.character.map_id):return _response("REFUSED","DESTINATION_NOT_DISCOVERED")
	var point: Dictionary={}
	for n in data.npcs.values():
		if str(n.map_id)==mid and "travel" in n.get("services",[]):point=n;break
	if point.is_empty():return _response("REFUSED","NO_TRAVEL_CAMP")
	var fee:=maxi(10,int(data.maps[mid].get("recommended_level",1))*2)
	if int(state.character.money)<fee:return _response("REFUSED","INSUFFICIENT_MONEY")
	if bool(_config("lazy_world_spawns",false)): _spawn_map(mid)
	var arrival: Dictionary={}
	for offset in [Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT,Vector2i.UP]:
		arrival=_arrival_position(mid,int(point.x)+offset.x,int(point.y)+offset.y,true)
		if not arrival.is_empty():break
	if arrival.is_empty() or not _transition(mid,int(arrival.x),int(arrival.y),2,"camp_travel"):return _response("REFUSED","DESTINATION_UNAVAILABLE")
	state.character.money=int(state.character.money)-fee
	_event("travelled",{"map_id":mid,"money":fee})
	return _response("OK","TRAVELLED",true)

func _integer(value: Variant,minimum: int,maximum: int) -> bool:
	return typeof(value) in [TYPE_INT,TYPE_FLOAT] and is_finite(float(value)) and float(value)==floor(float(value)) and float(value)>=minimum and float(value)<=maximum

func _safe_name(value: String) -> bool:
	if value.length()<2 or value.length()>12: return false
	for c in value:
		var u: int=c.unicode_at(0)
		if not ((u>=0xAC00 and u<=0xD7A3) or (u>=0x3131 and u<=0x318E) or (u>=48 and u<=57) or (u>=65 and u<=90) or (u>=97 and u<=122)): return false
	return true

func _response(status: String,reason: String,changed: bool=false) -> Dictionary:
	return {"status":status,"reason":reason,"changed":changed,"events":_events.duplicate(true)}

func _event(type: String,values: Dictionary={}) -> void:
	var event: Dictionary={"type":type,"time":float(state.get("sim_time",0.0)),"revision":int(state.get("revision",0))}
	event.merge(values)
	_events.append(event)

func create_character(name: String,owner: String,options: Dictionary={}) -> Dictionary:
	_events=[]
	if data.is_empty(): return _response("REFUSED","NOT_CONFIGURED")
	if not state.is_empty(): return _response("REFUSED","CHARACTER_ALREADY_EXISTS")
	if not _safe_name(name) or owner.is_empty() or owner.length()>128: return _response("REFUSED","INVALID_NAME_OR_OWNER")
	var start: Dictionary=data.start.duplicate(true)
	var nationality: String=str(options.get("nationality","고구려"))
	if not data.get("nation_starts",{}).is_empty():
		if not data.nation_starts.has(nationality): return _response("REFUSED","UNKNOWN_NATIONALITY")
		start.merge(data.nation_starts[nationality],true)
	var seed: int=int(options.get("seed",abs((owner+":"+name).hash()))) & 0x7fffffff
	if seed==0: seed=1
	var hp: int=int(start.get("hp",50))
	var mp: int=int(start.get("mp",30))
	state={"schema":"baram.p3.gameplay-payload/1","profile":data.profile,
		"character":{"id":"character:"+(owner+":"+name).sha256_text().substr(0,20),"name":name,"owner_id":owner,"job":"commoner","desired_job":options.get("desired_job"),"level":1,"xp":0,"hp":hp,"hp_max":hp,"mp":mp,"mp_max":mp,"money":int(start.get("money",0)),"map_id":str(start.map_id),"x":int(start.x),"y":int(start.y),"direction":2,"dead":false,"appearance":options.get("appearance",{}).duplicate(true),"nationality":options.get("nationality","고구려"),"guardian":options.get("guardian","주작"),"base_stats":{"strength":5,"dexterity":5,"intelligence":5}},
		"inventory":[],"equipment":{},"skills":[],"hotkeys":{},"quests":{},"loot":[],"monsters":{},"buffs":{},"cooldowns":{},"revision":1,"rng_state":seed,"applied_request_ids":[],"request_watermarks":{},"sim_time":0.0,"time_accumulator":0.0,"pending_actions":[],"next_instance_id":1,"next_loot_id":1,"stats":{"kills":0,"deaths":0,"total_xp_earned":0,"money_earned":0,"items_picked_up":0},"shop_purchases":{}}
	for item in start.get("starter_items",[]):
		if not data.items.has(str(item.item_id)) or not _add_item(str(item.item_id),int(item.get("quantity",1))):
			state={}
			return _response("REFUSED","INVALID_STARTER_ITEM")
	if bool(_config("lazy_world_spawns",false)): _spawn_map(str(state.character.map_id))
	else: _spawn_all()
	state.character["discovered_maps"]=[str(state.character.map_id)]
	for slot in start.get("initial_equipment",{}):
		var item_id: String=str(start.initial_equipment[slot])
		for item in state.inventory:
			if str(item.item_id)==item_id and str(data.items[item_id].get("slot",""))==str(slot):
				state.equipment[str(slot)]=item.instance_id
				break
	_sync_equipment_resources()
	var validation: Dictionary=validate_payload(state,owner)
	if validation.status!="OK":
		state={}
		return _response("REFUSED","INVALID_CREATED_STATE:"+str(validation.reason))
	_event("character_created",{"name":name,"map_id":str(start.map_id)})
	return _response("OK","CHARACTER_CREATED",true)

func snapshot() -> Dictionary:
	return state.duplicate(true)

func restore(payload: Dictionary) -> Dictionary:
	_events=[]
	var expected_owner: String=str(state.get("character",{}).get("owner_id",payload.get("character",{}).get("owner_id","")))
	var check: Dictionary=validate_payload(payload,expected_owner)
	if check.status!="OK": return check
	state=payload.duplicate(true)
	_indexed_monster_count=-1
	_sync_equipment_resources()
	if state!=payload:
		state.revision=int(payload.revision)+1
		_event("save_normalized",{"reason":"EQUIPMENT_RESOURCE_BONUSES"})
	return _response("OK","RESTORED",true)

func validate_payload(payload: Dictionary,expected_owner: String="") -> Dictionary:
	var invalid: Dictionary={"status":"INVALID_STATE","reason":"PAYLOAD_SHAPE","changed":false,"events":[]}
	for key in ["schema","profile","character","inventory","equipment","skills","quests","loot","monsters","buffs","cooldowns","revision","rng_state","applied_request_ids","request_watermarks","sim_time","time_accumulator","pending_actions","next_instance_id","next_loot_id","stats","shop_purchases"]:
		if not payload.has(key): return invalid
	if payload.schema!="baram.p3.gameplay-payload/1" or payload.profile!=data.get("profile"): return {"status":"DEFERRED","reason":"PROFILE_OR_SCHEMA_MISMATCH","changed":false,"events":[]}
	if typeof(payload.character)!=TYPE_DICTIONARY or typeof(payload.inventory)!=TYPE_ARRAY or typeof(payload.equipment)!=TYPE_DICTIONARY or typeof(payload.skills)!=TYPE_ARRAY or typeof(payload.loot)!=TYPE_ARRAY or typeof(payload.monsters)!=TYPE_DICTIONARY or typeof(payload.pending_actions)!=TYPE_ARRAY or typeof(payload.applied_request_ids)!=TYPE_ARRAY or typeof(payload.request_watermarks)!=TYPE_DICTIONARY: return invalid
	var c: Dictionary=payload.character
	for key in ["id","name","owner_id","job","desired_job","level","xp","hp","hp_max","mp","mp_max","money","map_id","x","y","direction","dead","appearance"]:
		if not c.has(key): return invalid
	if not expected_owner.is_empty() and c.owner_id!=expected_owner: return {"status":"OWNER_MISMATCH","reason":"OWNER_MISMATCH","changed":false,"events":[]}
	if not _safe_name(str(c.name)) or str(c.id).is_empty() or str(c.owner_id).is_empty(): return invalid
	if c.job!="commoner" and c.job not in JOBS: return invalid
	if not _integer(c.level,1,data.xp_thresholds.size()) or not _integer(c.xp,0,MAX_VALUE) or not _integer(c.money,0,MAX_VALUE): return invalid
	for key in ["hp_max","mp_max"]:
		if not _integer(c[key],1,MAX_VALUE): return invalid
	if not _integer(c.hp,0,int(c.hp_max)) or not _integer(c.mp,0,int(c.mp_max)): return invalid
	if bool(c.dead)!=(int(c.hp)==0): return invalid
	if not _integer(c.direction,0,3) or not _integer(c.x,0,65535) or not _integer(c.y,0,65535) or not valid_position(str(c.map_id),int(c.x),int(c.y)): return {"status":"DEFERRED","reason":"INVALID_POSITION","changed":false,"events":[]}
	if not _integer(payload.revision,0,MAX_VALUE) or not _integer(payload.rng_state,1,0x7fffffff): return invalid
	if not is_finite(float(payload.sim_time)) or float(payload.sim_time)<0 or float(payload.sim_time)>MAX_VALUE: return invalid
	if not is_finite(float(payload.time_accumulator)) or float(payload.time_accumulator)<0 or float(payload.time_accumulator)>=STEP+0.00001: return invalid
	if typeof(payload.get("bank_inventory",[]))!=TYPE_ARRAY or payload.get("bank_inventory",[]).size()>int(_config("bank_slots",120)): return invalid
	if payload.inventory.size()>int(_config("inventory_slots",_config("inventory_capacity",60))) or payload.loot.size()>2048 or payload.monsters.size()>int(_config("max_world_monsters",1024)) or payload.pending_actions.size()>32 or payload.applied_request_ids.size()>MAX_REQUESTS: return invalid
	if typeof(c.get("discovered_maps",[]))!=TYPE_ARRAY or c.get("discovered_maps",[]).size()>256: return invalid
	for map_id in c.get("discovered_maps",[]):
		if not data.maps.has(str(map_id)): return invalid
	if typeof(payload.get("gathered_nodes",{}))!=TYPE_DICTIONARY or payload.get("gathered_nodes",{}).size()>2048: return invalid
	for available in payload.get("gathered_nodes",{}).values():
		if typeof(available) not in [TYPE_INT,TYPE_FLOAT] or not is_finite(float(available)) or float(available)<0: return invalid
	var ids: Dictionary={}
	var inventory_ids: Dictionary={}
	for instance in payload.inventory: inventory_ids[str(instance.get("instance_id",""))]=true
	for instance in payload.inventory+payload.get("bank_inventory",[]):
		if typeof(instance)!=TYPE_DICTIONARY or not instance.has_all(["instance_id","item_id","quantity","durability"]): return invalid
		var id: String=str(instance.item_id)
		if not data.items.has(id) or ids.has(str(instance.instance_id)): return {"status":"UNKNOWN_ID","reason":"ITEM_REFERENCE_OR_DUPLICATE","changed":false,"events":[]}
		if not _integer(instance.quantity,1,int(data.items[id].get("stack_max",99))) or not _integer(instance.durability,0,int(data.items[id].get("durability",0))): return invalid
		if instance.has("identified") and typeof(instance.identified)!=TYPE_BOOL: return invalid
		if instance.has("custom_name") and not _safe_name(str(instance.custom_name)): return invalid
		ids[str(instance.instance_id)]=instance
	var equipped: Dictionary={}
	for slot in payload.equipment:
		var iid: String=str(payload.equipment[slot])
		if not inventory_ids.has(iid) or not ids.has(iid) or equipped.has(iid) or str(data.items[ids[iid].item_id].get("slot",""))!=str(slot): return invalid
		equipped[iid]=true
	var seen: Dictionary={}
	for id in payload.skills:
		if not data.skills.has(str(id)) or seen.has(str(id)): return invalid
		seen[str(id)]=true
	for loot in payload.loot:
		if typeof(loot)!=TYPE_DICTIONARY or not loot.has_all(["loot_id","item_id","quantity","map_id","x","y"]): return invalid
		if not data.items.has(str(loot.item_id)) or not _integer(loot.quantity,1,MAX_VALUE) or not valid_position(str(loot.map_id),int(loot.x),int(loot.y)): return invalid
		if seen.has(str(loot.loot_id)): return invalid
		seen[str(loot.loot_id)]=true
	for id in payload.monsters:
		var monster: Dictionary=payload.monsters[id]
		if not monster.has_all(["monster_id","map_id","x","y","hp","alive","spawn_x","spawn_y","respawn_at","generation","ai_at","attack_at","aggro"]): return invalid
		if not data.monsters.has(str(monster.monster_id)) or not valid_position(str(monster.map_id),int(monster.x),int(monster.y)): return invalid
		if not _integer(monster.hp,0,int(data.monsters[monster.monster_id].hp)) or bool(monster.alive)!=(int(monster.hp)>0): return invalid
	if typeof(payload.quests)!=TYPE_DICTIONARY or typeof(payload.buffs)!=TYPE_DICTIONARY: return invalid
	for id in payload.quests:
		if not data.get("quests",{}).has(str(id)) or typeof(payload.quests[id])!=TYPE_DICTIONARY: return invalid
		var quest: Dictionary=payload.quests[id]
		if quest.get("status","") not in ["active","completed"] or typeof(quest.get("progress",{}))!=TYPE_DICTIONARY: return invalid
		for key in quest.get("progress",{}):
			if not _integer(quest.progress[key],0,MAX_VALUE): return invalid
	for id in payload.buffs:
		if not _valid_status(payload.buffs[id]): return invalid
	for monster in payload.monsters.values():
		if typeof(monster.get("statuses",{}))!=TYPE_DICTIONARY: return invalid
		for status in monster.get("statuses",{}).values():
			if not _valid_status(status): return invalid
	if payload.has("summons"):
		if typeof(payload.summons)!=TYPE_ARRAY or payload.summons.size()>32: return invalid
		for summon in payload.summons:
			if typeof(summon)!=TYPE_DICTIONARY or not summon.has_all(["id","monster_id","map_id","x","y","expires_at","attack_at","power","range","interval"]): return invalid
			if not _integer(summon.power,0,MAX_VALUE) or not _integer(summon.range,0,256) or not _integer(summon.x,0,65535) or not _integer(summon.y,0,65535): return invalid
			if typeof(summon.expires_at) not in [TYPE_INT,TYPE_FLOAT] or typeof(summon.attack_at) not in [TYPE_INT,TYPE_FLOAT] or typeof(summon.interval) not in [TYPE_INT,TYPE_FLOAT]: return invalid
			if not data.monsters.has(str(summon.monster_id)) or not valid_position(str(summon.map_id),int(summon.x),int(summon.y)) or not is_finite(float(summon.expires_at)) or float(summon.expires_at)<0 or not is_finite(float(summon.attack_at)) or float(summon.interval)<0.1: return invalid
	for cache in ["equipment_hp_bonus","equipment_mp_bonus"]:
		if c.has(cache) and not _integer(c[cache],-MAX_VALUE,MAX_VALUE): return invalid
	if c.has("base_stats"):
		if typeof(c.base_stats)!=TYPE_DICTIONARY: return invalid
		for stat in ["strength","dexterity","intelligence"]:
			if not _integer(c.base_stats.get(stat),1,MAX_VALUE): return invalid
	if c.has("advancement"):
		if not data.get("advancements",{}).has(str(c.advancement)): return invalid
		var advancement: Dictionary=data.advancements[str(c.advancement)]
		if str(advancement.job)!=str(c.job) or not _integer(c.get("advancement_rank",0),1,10) or int(c.advancement_rank)!=int(advancement.get("rank",1)): return invalid
	elif int(c.get("advancement_rank",0))!=0: return invalid
	for stream in payload.request_watermarks:
		if typeof(stream)!=TYPE_STRING or str(stream).length()>96 or not _integer(payload.request_watermarks[stream],0,9007199254740991): return invalid
	for request in payload.applied_request_ids:
		if typeof(request)!=TYPE_STRING or str(request).length()>128: return invalid
	for action in payload.pending_actions:
		if typeof(action)!=TYPE_DICTIONARY or not action.has_all(["kind","due","map_id"]): return invalid
		if not is_finite(float(action.due)) or action.kind not in ["attack","skill","monster_attack"] or not data.maps.has(str(action.map_id)): return invalid
		if action.kind=="skill" and not data.skills.has(str(action.get("skill_id",""))): return invalid
	for key in payload.cooldowns:
		if not is_finite(float(payload.cooldowns[key])) or float(payload.cooldowns[key])<0: return invalid
	return {"status":"OK","reason":"VALIDATED","changed":false,"events":[]}

func _spawn_all() -> void:
	for map_id in data.maps:
		for spawn in data.maps[map_id].get("spawns",[]):
			var id: String=str(spawn.id)
			var def: Dictionary=data.monsters[str(spawn.monster_id)]
			state.monsters[id]={"id":id,"monster_id":str(spawn.monster_id),"map_id":str(map_id),"x":int(spawn.x),"y":int(spawn.y),"spawn_x":int(spawn.x),"spawn_y":int(spawn.y),"hp":int(def.hp),"alive":true,"generation":0,"respawn_at":0.0,"ai_at":0.0,"attack_at":0.0,"aggro":false,"respawn_seconds":float(spawn.get("respawn_seconds",def.get("respawn_seconds",8.0)))}

func _begin_transaction(prior: Dictionary) -> void:
	# Keep rollback isolation without cloning every monster on every input/frame.
	# Every other mutable branch is still deeply copied, including inventory,
	# nested quests, pending actions, request tracking and RNG's scalar state.
	state=prior.duplicate()
	for key in prior:
		if typeof(prior[key]) in [TYPE_DICTIONARY,TYPE_ARRAY]:
			state[key]=prior[key].duplicate(key!="monsters")
	_in_transaction=true
	_reindex_monsters()
	_map_monster_ids=_indexed_maps
	_detached_monsters={};_status_monster_ids=[]
	for id in state.monsters:
		var monster: Dictionary=state.monsters[id]
		if _active_monster(monster) or not monster.get("statuses",{}).is_empty():
			_detach_monster(str(id));_status_monster_ids.append(id)

func _detach_monster(id: String) -> void:
	if _detached_monsters.has(id): return
	state.monsters[id]=state.monsters[id].duplicate(true)
	_detached_monsters[id]=true

func _ensure_map_mutable(map_id: String) -> void:
	if not _in_transaction: return
	_reindex_monsters()
	_map_monster_ids=_indexed_maps
	for id in _map_monster_ids.get(map_id,[]):
		if _active_monster(state.monsters[id],map_id): _detach_monster(str(id))
	# A return/blink can enter a new map during a multi-step tick. Preserve the
	# old global insertion order for status ticks, drops, events and RNG draws.
	_status_monster_ids=[]
	for id in state.monsters:
		if _detached_monsters.has(id): _status_monster_ids.append(id)

func _end_transaction() -> void:
	_in_transaction=false
	_map_monster_ids={};_detached_monsters={};_status_monster_ids=[]

func command(cmd: Dictionary) -> Dictionary:
	_events=[]
	if state.is_empty(): return _response("REFUSED","NO_CHARACTER")
	var request_id: String=str(cmd.get("request_id",""))
	if request_id.is_empty() or request_id.length()>128: return _response("REFUSED","REQUEST_ID_REQUIRED")
	var split_at: int=request_id.rfind(":")
	if split_at<1 or split_at>96 or not request_id.substr(split_at+1).is_valid_int(): return _response("REFUSED","REQUEST_ID_MONOTONIC_SEQUENCE_REQUIRED")
	var stream: String=request_id.substr(0,split_at)
	var sequence: int=int(request_id.substr(split_at+1))
	if sequence<1 or sequence>9007199254740991: return _response("REFUSED","REQUEST_SEQUENCE_INVALID")
	if sequence<=int(state.request_watermarks.get(stream,0)): return _response("DUPLICATE","REQUEST_ALREADY_APPLIED")
	var prior: Dictionary=state
	_begin_transaction(prior)
	var result: Dictionary=_execute(cmd)
	if result.status=="OK" and bool(result.get("changed",false)):
		_sync_equipment_resources()
		state.applied_request_ids.append(request_id)
		if state.applied_request_ids.size()>MAX_REQUESTS: state.applied_request_ids.pop_front()
		state.request_watermarks[stream]=sequence
		state.revision=int(prior.revision)+1
		_end_transaction()
		return _response("OK",str(result.reason),true)
	state=prior
	_end_transaction()
	return _response(str(result.status),str(result.reason),false)

func _execute(cmd: Dictionary) -> Dictionary:
	var type: String=str(cmd.get("type",""))
	if type=="cancel": return _response("CANCELLED","CANCELLED")
	if type=="cancel_pending":
		var pending: Array=state.pending_actions.filter(func(action): return str(action.kind)!="skill")
		if pending.size()==state.pending_actions.size(): return _response("REFUSED","NO_PENDING_CAST")
		state.pending_actions=pending
		_event("action_cancelled",{"reason":"USER_CANCELLED_NO_REFUND","kind":"skill"})
		return _response("OK","PENDING_CAST_CANCELLED",true)
	if type=="respawn": return _respawn()
	if type=="move" and state.buffs.values().any(func(buff): return bool(buff.get("rooted",false))): return _response("REFUSED","STATUS_PREVENTS_ACTION")
	var cleanse_statuses: Array=[]
	if type=="cast" and data.skills.has(str(cmd.get("skill_id",""))):
		var requested_skill: Dictionary=data.skills[str(cmd.skill_id)]
		if str(requested_skill.kind)=="cleanse": cleanse_statuses=requested_skill.get("cleanse_statuses",["poison","paralysis","slow","silence","blindness"])
	if (_has_status(state.buffs,"paralysis") and type in ["move","attack","cast"] and "paralysis" not in cleanse_statuses) or (_has_status(state.buffs,"silence") and type=="cast" and "silence" not in cleanse_statuses): return _response("REFUSED","STATUS_PREVENTS_ACTION")
	if bool(state.character.dead) and type not in ["talk","cast"]: return _response("REFUSED","CHARACTER_DEAD")
	match type:
		"gather": return _gather(cmd)
		"travel": return _travel(cmd)
		"move": return _move(cmd)
		"attack": return _attack(cmd)
		"pickup": return _pickup(cmd)
		"talk": return _talk(cmd)
		"buy": return _buy(cmd)
		"sell": return _sell(cmd)
		"equip": return _equip(cmd)
		"unequip": return _unequip(cmd)
		"repair": return _repair(cmd)
		"heal": return _heal(cmd)
		"change_job": return _change_job(cmd)
		"quest_accept": return _quest_accept(cmd)
		"quest_complete": return _quest_complete(cmd)
		"craft": return _craft(cmd)
		"advance": return _advance(cmd)
		"train": return _train(cmd)
		"store_deposit": return _store_transfer(cmd,true)
		"store_withdraw": return _store_transfer(cmd,false)
		"rename_weapon": return _rename_weapon(cmd)
		"learn": return _learn(cmd)
		"cast": return _cast(cmd)
		"bind_hotkey":
			var slot:=str(cmd.get("slot",""));var skill:=str(cmd.get("skill_id",""))
			if slot not in ["1","2","3","4","5","6","7","8","9"]: return _response("REFUSED","INVALID_HOTKEY")
			if skill not in state.skills: return _response("REFUSED","SKILL_NOT_LEARNED")
			state.hotkeys[slot]=skill
			_event("hotkey_bound",{"slot":slot,"skill_id":skill})
			return _response("OK","HOTKEY_BOUND",true)
		"use_item": return _use_item(cmd)
	return _response("REFUSED","UNKNOWN_COMMAND")

func _now() -> float:
	return float(state.sim_time)

func _ready(key: String) -> bool:
	return _now()+0.00001>=float(state.cooldowns.get(key,0.0))

func occupied_cells(map_id: String) -> Dictionary:
	# One truthful snapshot per path query, rather than a global scan per BFS cell.
	var cells: Dictionary=_npc_cells.get(map_id,{}).duplicate()
	for monster in state.get("monsters",{}).values():
		if bool(monster.alive) and str(monster.map_id)==map_id:
			cells[Vector2i(int(monster.x),int(monster.y))]=true
	return cells

func _occupied(map_id: String,x: int,y: int,exclude: String="") -> bool:
	if _npc_cells.get(map_id,{}).has(Vector2i(x,y)): return true
	var ids: Array=_map_monster_ids.get(map_id,[]) if _in_transaction else state.monsters.keys()
	for id in ids:
		var m: Dictionary=state.monsters[id]
		if id!=exclude and m.alive and str(m.map_id)==map_id and int(m.x)==x and int(m.y)==y: return true
	return false

func _distance(a: Dictionary,b: Dictionary) -> int:
	return absi(int(a.x)-int(b.x))+absi(int(a.y)-int(b.y))

func _direction(dx: int,dy: int) -> int:
	if dx>0: return 1
	if dx<0: return 3
	if dy<0: return 0
	return 2

func _direction_value(value: Variant) -> int:
	if typeof(value)==TYPE_STRING:
		return int({"north":0,"east":1,"south":2,"west":3,"북":0,"동":1,"남":2,"서":3}.get(value,2))
	return clampi(int(value),0,3)

func _arrival_position(map_id: String,x: int,y: int,allow_nearby: bool) -> Dictionary:
	# Off-map monsters do not walk while the player is elsewhere. An old save
	# can therefore keep an arrival anchor occupied indefinitely. Only dynamic
	# monster occupancy permits a nearby landing; invalid/NPC anchors still fail.
	if not valid_position(map_id,x,y) or _npc_cells.get(map_id,{}).has(Vector2i(x,y)): return {}
	if not _occupied(map_id,x,y): return {"x":x,"y":y}
	if not allow_nearby: return {}
	var anchor:=Vector2i(x,y)
	var queue: Array[Vector2i]=[anchor]
	var seen: Dictionary={anchor:true}
	var index:=0
	while index<queue.size():
		var current: Vector2i=queue[index];index+=1
		for offset in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
			var next: Vector2i=current+offset
			if seen.has(next) or absi(next.x-x)+absi(next.y-y)>4: continue
			seen[next]=true
			if not can_step(map_id,current.x,current.y,next.x,next.y) or _occupied(map_id,next.x,next.y): continue
			var is_exit:=false
			for exit in data.maps[map_id].get("exits",[]):
				if int(exit.x)==next.x and int(exit.y)==next.y: is_exit=true;break
			if is_exit: continue
			# Search stays in the anchor's reachable component. It never jumps
			# across a wall, NPC, living monster or another exit trigger.
			queue.append(next)
			return {"x":next.x,"y":next.y}
	return {}

func _transition(map_id: String,x: int,y: int,direction: int,reason: String) -> bool:
	if bool(_config("lazy_world_spawns",false)): _spawn_map(map_id)
	var point:=_arrival_position(map_id,x,y,reason in ["exit","item_return","resurrection","inn_return","directional_return","ghost_to_shrine"])
	if point.is_empty(): return false
	x=int(point.x);y=int(point.y)
	var c: Dictionary=state.character
	var source: Dictionary={"map_id":c.map_id,"x":c.x,"y":c.y}
	c.map_id=map_id;c.x=x;c.y=y;c.direction=direction
	_ensure_map_mutable(map_id)
	if not c.has("discovered_maps"): c["discovered_maps"]=[]
	if map_id not in c.discovered_maps: c.discovered_maps.append(map_id)
	state.pending_actions=[]
	state["summons"]=[]
	_quest_progress("visit",map_id)
	state.cooldowns["move"]=_now()+float(_config("move_interval",0.14))
	_event("map_changed",{"from":source,"map_id":map_id,"x":x,"y":y,"direction":direction,"reason":reason})
	return true

func _move(cmd: Dictionary) -> Dictionary:
	if not _integer(cmd.get("dx"),-1,1) or not _integer(cmd.get("dy"),-1,1): return _response("REFUSED","INVALID_DIRECTION")
	var dx: int=int(cmd.dx);var dy: int=int(cmd.dy)
	if absi(dx)+absi(dy)!=1: return _response("REFUSED","CARDINAL_ONLY")
	if not _ready("move") or not _ready("action"): return _response("REFUSED","ACTION_COOLDOWN")
	var c: Dictionary=state.character
	var x: int=int(c.x)+dx;var y: int=int(c.y)+dy
	if not can_step(str(c.map_id),int(c.x),int(c.y),x,y) or _occupied(str(c.map_id),x,y): return _response("REFUSED","BLOCKED_TILE")
	for exit in data.maps[c.map_id].get("exits",[]):
		if int(exit.x)==x and int(exit.y)==y:
			if int(c.level)<int(exit.get("minimum_level",1)): return _response("REFUSED","EXIT_LEVEL_REQUIRED")
			if not _transition(str(exit.to_map),int(exit.to_x),int(exit.to_y),_direction_value(exit.get("direction",_direction(dx,dy))),"exit"): return _response("REFUSED","DESTINATION_UNAVAILABLE")
			return _response("OK","MAP_TRANSITION",true)
	var from: Dictionary={"x":c.x,"y":c.y}
	c.x=x;c.y=y;c.direction=_direction(dx,dy)
	state.cooldowns["move"]=_now()+float(_config("move_interval",0.14))*_move_multiplier()
	_event("moved",{"from":from,"x":x,"y":y,"direction":c.direction,"map_id":c.map_id})
	return _response("OK","MOVED",true)

func _near_npc(id: String,service: String="") -> Dictionary:
	if not data.npcs.has(id): return {}
	var npc: Dictionary=data.npcs[id]
	if str(npc.map_id)!=str(state.character.map_id) or _distance(npc,state.character)>int(npc.get("interaction_range",2)): return {}
	if not service.is_empty() and service not in npc.get("services",[]): return {}
	return npc

func _talk(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")))
	if npc.is_empty(): return _response("REFUSED","NPC_OUT_OF_REACH")
	var dialogue: Dictionary=npc.get("dialogue",{})
	_event("dialogue",{"npc_id":npc.id,"name":npc.name,"text":str(dialogue.get("greeting",npc.name+"입니다.")),"services":npc.get("services",[]),"shop":npc.get("shop",{}),"job":npc.get("job")})
	_quest_progress("talk",str(npc.id))
	return _response("OK","DIALOGUE_OPENED",true)

func _inventory_index(instance_id: String) -> int:
	for i in range(state.inventory.size()):
		if str(state.inventory[i].instance_id)==instance_id: return i
	return -1

func item_count(item_id: String) -> int:
	var count := 0
	for item in state.get("inventory",[]):
		if str(item.item_id)==item_id: count+=int(item.quantity)
	return count

func _add_item(item_id: String,quantity: int) -> bool:
	if quantity<=0 or not data.items.has(item_id): return false
	var max_stack: int=int(data.items[item_id].get("stack_max",99))
	var available: int=(int(_config("inventory_slots",_config("inventory_capacity",60)))-state.inventory.size())*max_stack
	for item in state.inventory:
		if str(item.item_id)==item_id: available+=max_stack-int(item.quantity)
	if available<quantity: return false
	for item in state.inventory:
		if str(item.item_id)==item_id:
			var n: int=mini(quantity,max_stack-int(item.quantity))
			item.quantity=int(item.quantity)+n;quantity-=n
			if quantity==0: return true
	while quantity>0:
		var n: int=mini(quantity,max_stack)
		state.inventory.append({"instance_id":"instance:"+str(state.next_instance_id),"item_id":item_id,"quantity":n,"durability":int(data.items[item_id].get("durability",0))})
		state.next_instance_id=int(state.next_instance_id)+1
		quantity-=n
	return true

func _remove_item(item_id: String,quantity: int) -> bool:
	if quantity<0 or item_count(item_id)<quantity: return false
	for i in range(state.inventory.size()-1,-1,-1):
		var item: Dictionary=state.inventory[i]
		if str(item.item_id)!=item_id: continue
		if str(item.instance_id) in state.equipment.values(): continue
		var n: int=mini(quantity,int(item.quantity))
		item.quantity=int(item.quantity)-n;quantity-=n
		if int(item.quantity)==0: state.inventory.remove_at(i)
		if quantity==0: return true
	return quantity==0

func _buy(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")))
	if npc.is_empty(): return _response("REFUSED","NPC_OUT_OF_REACH")
	var id: String=str(cmd.get("item_id",""))
	if not npc.get("shop",{}).has(id) or npc.shop[id].get("buy_price")==null: return _response("REFUSED","NOT_FOR_SALE")
	if not _integer(cmd.get("quantity",1),1,999): return _response("REFUSED","INVALID_QUANTITY")
	var q: int=int(cmd.get("quantity",1));var price: int=int(npc.shop[id].buy_price)*q
	if price<0 or price>MAX_VALUE or int(state.character.money)<price: return _response("REFUSED","INSUFFICIENT_MONEY")
	var key: String=str(npc.id)+"/"+id
	var bought: int=int(state.shop_purchases.get(key,0))
	if npc.shop[id].get("stock_limit")!=null and bought+q>int(npc.shop[id].stock_limit): return _response("REFUSED","OUT_OF_STOCK")
	if not _add_item(id,q): return _response("REFUSED","INVENTORY_FULL")
	state.character.money=int(state.character.money)-price
	state.shop_purchases[key]=bought+q
	_event("bought",{"npc_id":npc.id,"item_id":id,"quantity":q,"money_change":-price})
	return _response("OK","BOUGHT",true)

func _sell(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")))
	if npc.is_empty(): return _response("REFUSED","NPC_OUT_OF_REACH")
	var index: int=_inventory_index(str(cmd.get("instance_id","")))
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	var item: Dictionary=state.inventory[index]
	if str(item.instance_id) in state.equipment.values(): return _response("REFUSED","UNEQUIP_FIRST")
	if not npc.get("shop",{}).has(str(item.item_id)) or npc.shop[item.item_id].get("sell_price")==null: return _response("REFUSED","MERCHANT_DOES_NOT_BUY")
	if not _integer(cmd.get("quantity",1),1,int(item.quantity)): return _response("REFUSED","INVALID_QUANTITY")
	var q: int=int(cmd.get("quantity",1));var price: int=int(npc.shop[item.item_id].sell_price)*q
	if price<0 or int(state.character.money)+price>MAX_VALUE: return _response("REFUSED","MONEY_LIMIT")
	state.character.money=int(state.character.money)+price
	item.quantity=int(item.quantity)-q
	if int(item.quantity)==0: state.inventory.remove_at(index)
	_event("sold",{"npc_id":npc.id,"item_id":item.item_id,"quantity":q,"money_change":price})
	return _response("OK","SOLD",true)

func _equip(cmd: Dictionary) -> Dictionary:
	var index: int=_inventory_index(str(cmd.get("instance_id","")))
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	var item: Dictionary=state.inventory[index];var def: Dictionary=data.items[item.item_id]
	var slot: String=str(def.get("slot",""))
	if slot.is_empty(): return _response("REFUSED","ITEM_NOT_EQUIPMENT")
	if int(state.character.level)<int(def.get("required_level",1)): return _response("REFUSED","LEVEL_TOO_LOW")
	if not _advancement_eligible(def): return _response("REFUSED","ADVANCEMENT_REQUIRED")
	for stat in ["strength","dexterity","intelligence"]:
		if int(derived_stats().get(stat,0))<int(def.get("required_"+stat,0)): return _response("REFUSED","ATTRIBUTE_TOO_LOW")
	if def.get("required_job")!=null and str(def.required_job) not in ["","any","전직업","common"] and str(def.required_job)!=str(state.character.job): return _response("REFUSED","WRONG_JOB")
	if not def.get("required_jobs",[]).is_empty() and str(state.character.job) not in def.required_jobs: return _response("REFUSED","WRONG_JOB")
	if int(def.get("durability",0))>0 and int(item.durability)<=0: return _response("REFUSED","ITEM_BROKEN")
	if state.equipment.get(slot)==item.instance_id: return _response("REFUSED","ALREADY_EQUIPPED")
	state.equipment[slot]=item.instance_id
	_quest_progress("equip",str(item.item_id))
	_event("equipped",{"slot":slot,"instance_id":item.instance_id,"item_id":item.item_id})
	return _response("OK","EQUIPPED",true)

func _unequip(cmd: Dictionary) -> Dictionary:
	var slot: String=str(cmd.get("slot",""))
	if not state.equipment.has(slot): return _response("REFUSED","SLOT_EMPTY")
	var id: String=str(state.equipment[slot]);state.equipment.erase(slot)
	_event("unequipped",{"slot":slot,"instance_id":id})
	return _response("OK","UNEQUIPPED",true)

func _repair(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")),"repair")
	if npc.is_empty(): return _response("REFUSED","REPAIR_NPC_REQUIRED")
	var index: int=_inventory_index(str(cmd.get("instance_id","")))
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	var instance: Dictionary=state.inventory[index];var def: Dictionary=data.items[instance.item_id]
	var missing: int=int(def.get("durability",0))-int(instance.durability)
	if missing<=0: return _response("REFUSED","NO_REPAIR_NEEDED")
	var cost: int=maxi(1,int(ceil(float(missing)*float(npc.get("repair_cost_per_point",_config("repair_price_per_point",0.1))))))
	if int(state.character.money)<cost: return _response("REFUSED","INSUFFICIENT_MONEY")
	state.character.money=int(state.character.money)-cost;instance.durability=int(def.durability)
	_event("repaired",{"instance_id":instance.instance_id,"cost":cost})
	return _response("OK","REPAIRED",true)

func _heal(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")),"heal")
	if npc.is_empty(): return _response("REFUSED","HEALER_REQUIRED")
	if int(state.character.hp)>=int(state.character.hp_max) and int(state.character.mp)>=int(state.character.mp_max): return _response("REFUSED","RESOURCE_ALREADY_FULL")
	var cost: int=int(npc.get("heal_cost",_config("heal_price",5)))
	if int(state.character.money)<cost: return _response("REFUSED","INSUFFICIENT_MONEY")
	state.character.money=int(state.character.money)-cost
	state.character.hp=int(state.character.hp_max);state.character.mp=int(state.character.mp_max)
	_event("healed",{"npc_id":npc.id,"cost":cost,"hp":state.character.hp,"mp":state.character.mp})
	return _response("OK","HEALED",true)

func _change_job(cmd: Dictionary) -> Dictionary:
	var job: String=str(cmd.get("job",""));var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")))
	if job not in JOBS: return _response("REFUSED","UNKNOWN_JOB")
	if npc.is_empty() or str(npc.get("job",""))!=job or "change_job" not in npc.get("services",[]): return _response("REFUSED","WRONG_JOB_TEACHER")
	if str(state.character.job)!="commoner": return _response("REFUSED","ALREADY_HAS_JOB")
	if int(state.character.level)<5: return _response("REFUSED","LEVEL_TOO_LOW")
	var cost: int=int(npc.get("job_change_cost",0))
	if int(state.character.money)<cost: return _response("REFUSED","INSUFFICIENT_MONEY")
	state.character.money=int(state.character.money)-cost;state.character.job=job;state.character.desired_job=job
	_event("job_changed",{"job":job,"npc_id":npc.id})
	return _response("OK","JOB_CHANGED",true)

func _learn(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("skill_id",""))
	if not data.skills.has(id): return _response("REFUSED","UNKNOWN_SKILL")
	var skill: Dictionary=data.skills[id];var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")))
	if npc.is_empty() or "teach_skill" not in npc.get("services",[]): return _response("REFUSED","SKILL_TEACHER_REQUIRED")
	if str(state.character.job)=="commoner": return _response("REFUSED","JOB_CHANGE_REQUIRED")
	if str(npc.get("job",""))!=str(state.character.job): return _response("REFUSED","WRONG_JOB_TEACHER")
	if not skill.get("teacher_ids",[]).is_empty() and str(npc.id) not in skill.teacher_ids: return _response("REFUSED","WRONG_SKILL_TEACHER")
	if str(skill.job)!=str(state.character.job) and str(skill.job) not in ["common","COMMON_FOUR_STARTER_JOBS"]: return _response("REFUSED","WRONG_JOB")
	if id in state.skills: return _response("REFUSED","ALREADY_LEARNED")
	if not _advancement_eligible(skill): return _response("REFUSED","ADVANCEMENT_REQUIRED")
	if int(state.character.level)<int(skill.learn_level): return _response("REFUSED","LEVEL_TOO_LOW")
	if skill.get("guardian")!=null and str(skill.guardian)!=str(state.character.get("guardian","주작")): return _response("REFUSED","WRONG_GUARDIAN")
	var money: int=int(skill.get("learn_money",0))
	if int(state.character.money)<money: return _response("REFUSED","INSUFFICIENT_MONEY")
	for item_id in skill.get("ingredients",{}):
		if item_count(str(item_id))<int(skill.ingredients[item_id]): return _response("REFUSED","INSUFFICIENT_MATERIALS")
	for item_id in skill.get("ingredients",{}):
		if not _remove_item(str(item_id),int(skill.ingredients[item_id])): return _response("REFUSED","MATERIAL_EQUIPPED")
	state.character.money=int(state.character.money)-money
	state.skills.append(id)
	if state.hotkeys.size()<9: state.hotkeys[str(state.hotkeys.size()+1)]=id
	_event("skill_learned",{"skill_id":id,"npc_id":npc.id,"money_cost":money,"ingredients":skill.get("ingredients",{})})
	return _response("OK","SKILL_LEARNED",true)

func derived_stats() -> Dictionary:
	var growth: Dictionary=data.get("job_growth",{}).get(str(state.get("character",{}).get("job","commoner")),{})
	var result: Dictionary={"attack":int(_config("base_attack",3))+int(float(state.get("character",{}).get("level",1))*float(growth.get("attack_per_level",1.0/3.0))),"defense":int(_config("base_defense",0)),"attack_range":1,"attack_multiplier":1.0,"hp_max":int(state.get("character",{}).get("hp_max",0)),"mp_max":int(state.get("character",{}).get("mp_max",0))}
	result.merge(_base_attributes())
	result.merge({"regen_bonus":0,"accuracy":0,"magic_defense":0})
	for id in state.get("equipment",{}).values():
		var index: int=_inventory_index(str(id))
		if index<0: continue
		var item: Dictionary=state.inventory[index];var def: Dictionary=data.items[item.item_id]
		if int(def.get("durability",0))>0 and int(item.durability)<=0: continue
		result.attack=int(result.attack)+int(def.get("attack",0))+int(def.get("damage_bonus",0))+int(def.get("accuracy_bonus",0));result.defense=int(result.defense)+int(def.get("defense",0))
		for stat in ["strength","dexterity","intelligence"]: result[stat]=int(result[stat])+int(def.get(stat+"_bonus",0))
		result.regen_bonus=int(result.regen_bonus)+int(def.get("regen_bonus",0));result.accuracy=int(result.accuracy)+int(def.get("accuracy_bonus",0));result.magic_defense=int(result.magic_defense)+int(def.get("magic_defense_bonus",0))
		result.attack_range=maxi(int(result.attack_range),int(def.get("attack_range",1)))
	for buff in state.get("buffs",{}).values():
		result.attack=int(result.attack)+int(buff.get("attack",0));result.defense=int(result.defense)+int(buff.get("defense",0))
		result.attack_multiplier=float(result.attack_multiplier)*float(buff.get("attack_multiplier",1.0))*(1.0+float(buff.get("accuracy_bonus",0.0)))
	result.attack=int(round(float(result.attack)*float(result.attack_multiplier)))
	return result

func stats() -> Dictionary:
	var values: Dictionary=derived_stats()
	values["hp_max"]=state.get("character",{}).get("hp_max",0)
	values["mp_max"]=state.get("character",{}).get("mp_max",0)
	return values

func _line_clear(map_id: String,a: Dictionary,b: Dictionary) -> bool:
	var x: int=int(a.x);var y: int=int(a.y);var tx: int=int(b.x);var ty: int=int(b.y)
	var dx: int=absi(tx-x);var sx: int=1 if x<tx else -1;var dy: int=-absi(ty-y);var sy: int=1 if y<ty else -1;var err: int=dx+dy
	var budget := 256
	while budget>0:
		if not valid_position(map_id,x,y): return false
		if x==tx and y==ty: return true
		var e2: int=2*err
		if e2>=dy: err+=dy;x+=sx
		if e2<=dx: err+=dx;y+=sy
		budget-=1
	return false

func _target(id: String,range_cells: int) -> Dictionary:
	if not state.monsters.has(id): return {}
	var target: Dictionary=state.monsters[id]
	if not target.alive or str(target.map_id)!=str(state.character.map_id) or _distance(target,state.character)>range_cells or not _line_clear(str(target.map_id),state.character,target): return {}
	return target

func attack_target(range_cells: int = 1) -> String:
	# Facing first, then nearest cardinal neighbour, with stable ID tie-breaking.
	# _target retains wall, life, map and range checks for every candidate.
	var c: Dictionary=state.character
	var facing: Vector2i=[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT][int(c.direction)]
	var ids: Array=state.monsters.keys();ids.sort()
	var chosen:="";var score:=999999
	for id in ids:
		var target:=_target(str(id),range_cells)
		if target.is_empty(): continue
		var offset:=Vector2i(int(target.x)-int(c.x),int(target.y)-int(c.y))
		var next:=_distance(target,c)*10+(0 if offset==facing else 1)
		if next<score: score=next;chosen=str(id)
	return chosen

func _attack(cmd: Dictionary) -> Dictionary:
	if not _ready("attack") or not _ready("action"): return _response("REFUSED","ACTION_COOLDOWN")
	var target_id:=str(cmd.get("target_id",""))
	if target_id.is_empty(): target_id=attack_target(int(derived_stats().attack_range))
	if target_id.is_empty(): return _response("REFUSED","NO_NEARBY_TARGET")
	var target: Dictionary=_target(target_id,int(derived_stats().attack_range))
	if target.is_empty(): return _response("REFUSED","TARGET_OUT_OF_REACH")
	var attack_power: int=int(derived_stats().attack)
	var next_hit: float=_consume_next_hit()
	_break_stealth()
	state.character.direction=_direction(int(target.x)-int(state.character.x),int(target.y)-int(state.character.y))
	var interval: float=float(_config("attack_interval",0.5))
	var windup: float=float(_config("attack_windup",0.18))
	state.cooldowns["combat_until"]=_now()+5.0
	state.cooldowns["attack"]=_now()+interval;state.cooldowns["action"]=_now()+windup
	state.pending_actions.append({"kind":"attack","due":_now()+windup,"map_id":state.character.map_id,"target_id":target.id,"target_generation":target.generation,"range":int(derived_stats().attack_range),"damage":int(round(float(attack_power)*next_hit)),"directional_pattern":_attack_pattern(),"origin_x":state.character.x,"origin_y":state.character.y,"facing":state.character.direction,"effect_id":_config("attack_effect_id",null),"sound_id":_config("attack_sound_id",null)})
	_event("attack_started",{"target_id":target.id,"duration":interval,"impact_delay":windup,"sound_id":_config("swing_sound_id",null)})
	return _response("OK","ATTACK_STARTED",true)

func _cast(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("skill_id",""))
	if id not in state.skills or not data.skills.has(id): return _response("REFUSED","SKILL_NOT_LEARNED")
	var skill: Dictionary=data.skills[id];var kind: String=str(skill.kind)
	if kind not in SKILL_KINDS: return _response("REFUSED","UNSUPPORTED_ACTION")
	if str(state.character.job)=="commoner": return _response("REFUSED","JOB_CHANGE_REQUIRED")
	if str(skill.job)!=str(state.character.job) and str(skill.job) not in ["common","COMMON_FOUR_STARTER_JOBS"]: return _response("REFUSED","WRONG_JOB")
	if not _advancement_eligible(skill): return _response("REFUSED","ADVANCEMENT_REQUIRED")
	if skill.get("guardian")!=null and str(skill.guardian)!=str(state.character.get("guardian","주작")): return _response("REFUSED","WRONG_GUARDIAN")
	if bool(state.character.dead) and kind not in ["shrine","revive"]: return _response("REFUSED","CHARACTER_DEAD")
	if kind in ["shrine","revive"] and not bool(state.character.dead): return _response("REFUSED","GHOST_REQUIRED")
	if not _ready("skill:"+id) or not _ready("action"): return _response("REFUSED","ACTION_COOLDOWN")
	var mp_cost: int=int(skill.get("mp_cost",0));var hp_cost: int=int(skill.get("hp_cost",0))
	if int(state.character.mp)<mp_cost: return _response("REFUSED","INSUFFICIENT_HP_MP")
	if bool(skill.get("mp_cost_all",false)): mp_cost=int(state.character.mp)
	if skill.has("hp_cost_fraction"): hp_cost=maxi(hp_cost,int(floor(float(state.character.hp)*float(skill.hp_cost_fraction))))
	if bool(skill.get("hp_cost_all",false)): hp_cost=int(state.character.hp)
	var lethal: bool=hp_cost>=int(state.character.hp) and hp_cost>0 and bool(skill.get("allow_lethal_hp_cost",false))
	if int(state.character.mp)<mp_cost or (int(state.character.hp)<=hp_cost and kind not in ["shrine","revive"] and not lethal): return _response("REFUSED","INSUFFICIENT_HP_MP")
	var target: Dictionary={}
	var targets_monster: bool=kind in ["damage","debuff","blink"] or (kind=="status" and str(skill.get("target","monster"))!="self")
	if targets_monster:
		target=_target(str(cmd.get("target_id","")),int(skill.get("range",4)))
		if target.is_empty(): return _response("REFUSED","TARGET_OUT_OF_REACH")
		if str(skill.get("delivery","melee"))=="melee" and kind=="damage" and _distance(target,state.character)>int(skill.get("range",1)): return _response("REFUSED","TARGET_OUT_OF_REACH")
	var destination: Dictionary={}
	if kind=="return":
		if bool(skill.get("return_to_inn",false)):
			destination=data.get("return_points",{}).get(str(state.character.get("nationality","고구려")),{}).duplicate(true)
			if destination.is_empty(): return _response("REFUSED","RETURN_DESTINATION_UNKNOWN")
		else:
			var direction: String=str(cmd.get("direction",""))
			if direction not in ["east","west","south","north","동","서","남","북"]: return _response("REFUSED","DIRECTION_REQUIRED")
			direction={"동":"east","서":"west","남":"south","북":"north"}.get(direction,direction)
			var gates: Dictionary=_return_gates()
			if not gates.has(direction): return _response("REFUSED","RETURN_DESTINATION_UNKNOWN")
			destination=gates[direction].duplicate(true)
		# Keep the original anchor in the pending action; occupancy is resolved
		# again at impact rather than reserving a stale provisional fallback.
		if _arrival_position(str(destination.map_id),int(destination.x),int(destination.y),true).is_empty(): return _response("REFUSED","DESTINATION_UNAVAILABLE")
	if kind=="blink":
		var offset: Vector2i=[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT][int(state.character.direction)]
		var x: int=int(target.x)+offset.x;var y: int=int(target.y)+offset.y
		if not valid_position(str(target.map_id),x,y) or _occupied(str(target.map_id),x,y): return _response("REFUSED","DESTINATION_UNAVAILABLE")
		destination={"map_id":target.map_id,"x":x,"y":y,"direction":state.character.direction}
	if kind=="loot" and not state.loot.any(func(loot): return _loot_in_range(loot,skill)): return _response("REFUSED","NO_NEARBY_LOOT")
	if kind=="identify":
		var item_index: int=_inventory_index(str(cmd.get("instance_id","")))
		if item_index<0: return _response("REFUSED","ITEM_NOT_OWNED")
		if bool(state.inventory[item_index].get("identified",false)): return _response("REFUSED","ALREADY_IDENTIFIED")
	if kind=="summon" and state.get("summons",[]).size()>=int(_config("max_summons",3)): return _response("REFUSED","SUMMON_LIMIT")
	if kind=="heal" and int(state.character.hp)>=int(state.character.hp_max): return _response("REFUSED","HP_ALREADY_FULL")
	if kind=="restore_mp" and int(state.character.mp)>=int(state.character.mp_max): return _response("REFUSED","MP_ALREADY_FULL")
	if kind=="cleanse" and not state.buffs.values().any(func(buff): return str(buff.get("status","")) in skill.get("cleanse_statuses",["poison","paralysis","slow","silence"])): return _response("REFUSED","NO_HARMFUL_STATUS")
	var delay: float=float(skill.get("impact_delay",skill.get("windup",0.25)))
	if str(skill.get("delivery",""))=="projectile" and not target.is_empty(): delay+=float(_distance(target,state.character))/maxf(1.0,float(skill.get("projectile_speed",10.0)))
	if targets_monster: state.cooldowns["combat_until"]=_now()+5.0;_break_stealth()
	var original_hp: int=int(state.character.hp);var original_mp: int=int(state.character.mp)
	state.character.mp=int(state.character.mp)-mp_cost
	if hp_cost>0: state.character.hp=int(state.character.hp)-hp_cost
	state.cooldowns["skill:"+id]=_now()+float(skill.get("cooldown",0.8));state.cooldowns["action"]=_now()+float(skill.get("windup",skill.get("impact_delay",0.25)))
	state.pending_actions.append({"kind":"skill","skill_id":id,"due":_now()+delay,"map_id":state.character.map_id,"target_id":target.get("id",""),"target_generation":target.get("generation",0),"destination":destination,"instance_id":str(cmd.get("instance_id","")),"direction":cmd.get("direction",""),"range":int(skill.get("range",4)),"power":int(round(float(int(skill.get("power",0))+int(original_hp*float(skill.get("power_hp_fraction",0.0)))+int(original_mp*float(skill.get("power_mp_fraction",0.0))))*_finisher_multiplier(kind)))})
	if lethal:
		var sacrifice: Dictionary=state.pending_actions.pop_back()
		_resolve_skill(sacrifice)
		state.character.hp=0;_die_player()
	if str(skill.get("delivery",""))=="projectile":
		_event("projectile_started",{"skill_id":id,"target_id":target.get("id",""),"map_id":state.character.map_id,"from_x":state.character.x,"from_y":state.character.y,"to_x":target.get("x",state.character.x),"to_y":target.get("y",state.character.y),"duration":delay,"effect_id":skill.get("effect_id")})
	_event("cast_started",{"skill_id":id,"target_id":target.get("id",""),"delivery":skill.get("delivery","melee"),"impact_delay":delay,"duration":float(skill.get("duration",1.0)),"sound_id":skill.get("start_sound_id"),"mp_cost":mp_cost,"hp_cost":hp_cost})
	return _response("OK","CAST_STARTED",true)

func _use_item(cmd: Dictionary) -> Dictionary:
	var index: int=_inventory_index(str(cmd.get("instance_id","")))
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	if not _ready("use_item"): return _response("REFUSED","ACTION_COOLDOWN")
	var instance: Dictionary=state.inventory[index];var def: Dictionary=data.items[instance.item_id]
	var hp: int=int(def.get("hp_restore",0));var mp: int=int(def.get("mp_restore",0))
	var action_type: String=str(def.get("action_type",""))
	if action_type=="return":
		var direction: String=str(cmd.get("direction",data.get("default_return_direction","east")))
		direction={"동":"east","서":"west","남":"south","북":"north"}.get(direction,direction)
		var gates: Dictionary=_return_gates()
		if not gates.has(direction): return _response("REFUSED","RETURN_DESTINATION_UNKNOWN")
		var point: Dictionary=gates[direction]
		if not cmd.has("direction") and data.get("return_points",{}).has(str(state.character.get("nationality","고구려"))): point=data.return_points[str(state.character.get("nationality","고구려"))]
		if not _transition(str(point.map_id),int(point.x),int(point.y),_direction_value(point.get("direction",2)),"item_return"): return _response("REFUSED","DESTINATION_UNAVAILABLE")
	elif action_type=="cleanse":
		var harmful: Array=state.buffs.keys().filter(func(id): return str(state.buffs[id].get("status","")) in ["poison","paralysis","slow","silence"])
		if harmful.is_empty(): return _response("REFUSED","NO_HARMFUL_STATUS")
		for id in harmful: state.buffs.erase(id)
	elif not action_type.is_empty(): return _response("REFUSED","UNSUPPORTED_ITEM_ACTION")
	elif hp<=0 and mp<=0: return _response("REFUSED","ITEM_NOT_CONSUMABLE")
	elif (hp<=0 or int(state.character.hp)>=int(state.character.hp_max)) and (mp<=0 or int(state.character.mp)>=int(state.character.mp_max)): return _response("REFUSED","RESOURCE_ALREADY_FULL")
	state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+hp);state.character.mp=mini(int(state.character.mp_max),int(state.character.mp)+mp)
	instance.quantity=int(instance.quantity)-1
	if int(instance.quantity)==0: state.inventory.remove_at(index)
	state.cooldowns["use_item"]=_now()+float(_config("item_use_interval",0.5))
	_event("item_used",{"item_id":instance.item_id,"action_type":action_type,"hp_restore":hp,"mp_restore":mp})
	return _response("OK","ITEM_USED",true)

func _pickup(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("loot_id",""))
	for i in range(state.loot.size()):
		var loot: Dictionary=state.loot[i]
		if str(loot.loot_id)!=id: continue
		if str(loot.map_id)!=str(state.character.map_id) or _distance(loot,state.character)>1: return _response("REFUSED","LOOT_OUT_OF_REACH")
		if not _add_item(str(loot.item_id),int(loot.quantity)): return _response("REFUSED","INVENTORY_FULL")
		state.loot.remove_at(i);state.stats.items_picked_up=int(state.stats.items_picked_up)+int(loot.quantity)
		_event("picked_up",{"loot_id":id,"item_id":loot.item_id,"quantity":loot.quantity})
		return _response("OK","PICKED_UP",true)
	return _response("REFUSED","LOOT_NOT_FOUND")

func _respawn() -> Dictionary:
	if not bool(state.character.dead): return _response("REFUSED","NOT_DEAD")
	var point: Dictionary=data.respawn
	if not _transition(str(point.map_id),int(point.x),int(point.y),_direction_value(point.get("direction",2)),"resurrection"): return _response("REFUSED","RESPAWN_DESTINATION_UNAVAILABLE")
	state.character.dead=false;state.character.hp=maxi(1,int(round(int(state.character.hp_max)*float(_config("resurrection_hp_fraction",0.5)))))
	state.character.mp=maxi(0,int(round(int(state.character.mp_max)*float(_config("resurrection_mp_fraction",0.25)))))
	state.buffs={};state.cooldowns={};state.pending_actions=[]
	_event("resurrected",{"hp":state.character.hp,"mp":state.character.mp})
	return _response("OK","RESURRECTED",true)

func _random_int(low: int,high: int) -> int:
	state.rng_state=(int(state.rng_state)*1103515245+12345) & 0x7fffffff
	if int(state.rng_state)==0: state.rng_state=1
	return low+int(state.rng_state)%(high-low+1)

func _roll(chance: float) -> bool:
	return float(_random_int(0,999999))/1000000.0<chance

func _grant_xp(xp: int) -> void:
	var c: Dictionary=state.character
	c.xp=mini(MAX_VALUE,int(c.xp)+xp);state.stats.total_xp_earned=int(state.stats.total_xp_earned)+xp
	var max_level: int=data.xp_thresholds.size()
	while int(c.level)<max_level and int(c.xp)>=int(data.xp_thresholds[int(c.level)]):
		var growth: Dictionary=data.get("job_growth",{}).get(str(c.job),{})
		if not c.has("base_stats"): c["base_stats"]=_base_attributes()
		for stat in ["strength","dexterity","intelligence"]: c.base_stats[stat]=mini(MAX_VALUE,int(c.base_stats[stat])+_attribute_gain(str(c.job),stat))
		c.level=int(c.level)+1;c.hp_max=int(c.hp_max)+int(growth.get("hp_per_level",_config("hp_per_level",8)));c.mp_max=int(c.mp_max)+int(growth.get("mp_per_level",_config("mp_per_level",6)))
		if not bool(c.dead): c.hp=c.hp_max;c.mp=c.mp_max
		_event("level_up",{"level":c.level,"xp":c.xp,"hp_max":c.hp_max,"mp_max":c.mp_max})

func _kill_monster(target: Dictionary) -> void:
	if not bool(target.alive): return
	var def: Dictionary=data.monsters[target.monster_id]
	target.hp=0;target.alive=false;target.aggro=false;target.respawn_at=_now()+float(target.respawn_seconds)
	_quest_progress("kill",str(target.monster_id))
	state.stats.kills=int(state.stats.kills)+1
	_grant_xp(int(def.xp))
	var cash: int=_random_int(int(def.get("money_min",0)),int(def.get("money_max",0)))
	state.character.money=mini(MAX_VALUE,int(state.character.money)+cash);state.stats.money_earned=int(state.stats.money_earned)+cash
	for drop in def.get("drops",[]):
		if not _roll(float(drop.get("chance",1.0))): continue
		var quantity: int=_random_int(int(drop.get("quantity_min",1)),int(drop.get("quantity_max",1)))
		var id: String="loot:"+str(state.next_loot_id);state.next_loot_id=int(state.next_loot_id)+1
		state.loot.append({"loot_id":id,"item_id":str(drop.item_id),"quantity":quantity,"map_id":target.map_id,"x":target.x,"y":target.y})
		_event("loot_dropped",{"loot_id":id,"item_id":drop.item_id,"quantity":quantity,"map_id":target.map_id,"x":target.x,"y":target.y})
	_event("monster_died",{"target_id":target.id,"monster_id":target.monster_id,"xp":int(def.xp),"money":cash,"generation":target.generation})

func _hit_monster(target: Dictionary,damage: int,source: String,effect_id: Variant=null,sound_id: Variant=null) -> void:
	if not target.alive: return
	var definition: Dictionary=data.monsters[target.monster_id]
	var element: String=str(data.skills.get(source,{}).get("element","physical"))
	damage=maxi(1,int(round(float(damage)*float(definition.get("resistances",{}).get(element,1.0))*(1.0-float(definition.get("guard_reduction",0.0))))))
	var defense: int=int(definition.get("defense",0))
	for status in target.get("statuses",{}).values(): defense+=int(status.get("defense",0))
	var actual: int=maxi(1,damage-defense)
	target.hp=maxi(0,int(target.hp)-actual);target.aggro=true
	_event("monster_hit",{"target_id":target.id,"damage":actual,"hp":target.hp,"source":source,"effect_id":effect_id,"sound_id":sound_id,"map_id":target.map_id,"x":target.x,"y":target.y})
	if int(target.hp)<=0: _kill_monster(target)

func _damage_player(damage: int,source: String) -> void:
	if bool(state.character.dead): return
	state.cooldowns["combat_until"]=_now()+5.0
	var multiplier: float=1.0
	for buff in state.buffs.values(): multiplier*=float(buff.get("damage_multiplier",1.0))
	for buff in state.buffs.values():
		var evasion: float=float(buff.get("evasion_chance",0.0))
		if evasion>0 and _roll(evasion): _event("player_evaded",{"source":source});return
	if multiplier<=0: _event("player_blocked",{"source":source,"damage":0});return
	var actual: int=maxi(1,int(round(float(damage-int(derived_stats().defense)-int(derived_stats().magic_defense))*multiplier)))
	state.character.hp=maxi(0,int(state.character.hp)-actual)
	_event("player_hit",{"damage":actual,"hp":state.character.hp,"source":source,"sound_id":_config("player_hit_sound_id",null)})
	for iid in state.equipment.values():
		var index: int=_inventory_index(str(iid))
		if index>=0 and int(state.inventory[index].durability)>0: state.inventory[index].durability=int(state.inventory[index].durability)-1
	if int(state.character.hp)==0:
		_die_player()
	elif state.monsters.has(source) and bool(state.monsters[source].alive):
		var reflected: float=0.0
		for buff in state.buffs.values():
			var probability: float=float(buff.get("reflect_probability",1.0))
			if probability>=1.0 or _roll(probability): reflected+=float(buff.get("reflect_fraction",0.0))
		if reflected>0:
			_hit_monster(state.monsters[source],maxi(1,int(round(float(actual)*minf(1.0,reflected)))),"reflection")
			_event("damage_reflected",{"target_id":source,"fraction":minf(1.0,reflected)})

func _resolve_action(action: Dictionary) -> void:
	if str(action.map_id)!=str(state.character.map_id):
		_event("action_cancelled",{"reason":"MAP_CHANGED_NO_REFUND","kind":action.kind})
		return
	if action.kind=="attack":
		if bool(state.character.dead): return
		var target: Dictionary=_target(str(action.target_id),int(action.range))
		if target.is_empty() or int(target.generation)!=int(action.target_generation):
			_event("attack_missed",{"target_id":action.target_id,"reason":"TARGET_MOVED_OR_GONE"});return
		_hit_monster(target,int(action.damage),"attack",action.get("effect_id"),action.get("sound_id"))
		for neighbour in _pattern_targets(action.get("directional_pattern",[]),state.character,int(action.get("facing",state.character.direction))):
			if str(neighbour.id)!=str(target.id): _hit_monster(neighbour,int(action.damage),"attack",action.get("effect_id"),action.get("sound_id"))
		var iid: String=str(state.equipment.get("weapon",""));var index: int=_inventory_index(iid)
		if index>=0 and int(state.inventory[index].durability)>0: state.inventory[index].durability=int(state.inventory[index].durability)-1
	elif action.kind=="monster_attack":
		if not state.monsters.has(str(action.target_id)): return
		var monster: Dictionary=state.monsters[action.target_id]
		if not monster.alive or int(monster.generation)!=int(action.target_generation) or bool(state.character.dead) or _distance(monster,state.character)>int(data.monsters[monster.monster_id].get("attack_range",1)) or not _line_clear(str(monster.map_id),monster,state.character): return
		if _has_status(monster.get("statuses",{}),"paralysis") or _has_status(state.buffs,"stealth") or _barrier_blocks(monster): return
		var outgoing: int=int(data.monsters[monster.monster_id].attack)
		if _has_status(monster.get("statuses",{}),"blindness"): outgoing=maxi(1,int(round(outgoing*0.6)))
		_damage_player(outgoing,str(monster.id))
		var definition: Dictionary=data.monsters[monster.monster_id]
		if str(definition.get("on_hit_status","")) in STATUS_KINDS and not bool(state.character.dead):
			var status: String=str(definition.on_hit_status)
			state.buffs["monster:"+str(monster.id)]=_status_definition({"duration":definition.get("status_duration",5),"status_power":definition.get("status_power",1)},status)
	else:
		_resolve_skill(action)

func _resolve_skill(action: Dictionary) -> void:
	var skill: Dictionary=data.skills[str(action.skill_id)];var kind: String=str(skill.kind)
	if bool(state.character.dead) and kind not in ["shrine","revive"]: return
	if kind in ["damage","debuff","blink"] or (kind=="status" and str(skill.get("target","monster"))!="self"):
		var target: Dictionary=_target(str(action.target_id),int(action.range))
		if target.is_empty() or int(target.generation)!=int(action.target_generation):
			_event("cast_missed",{"skill_id":action.skill_id,"reason":"TARGET_MOVED_OR_GONE_NO_REFUND"});return
		if bool(skill.get("blink_to_target",false)):
			for offset in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
				var x: int=int(target.x)+offset.x;var y: int=int(target.y)+offset.y
				if valid_position(str(target.map_id),x,y) and not _occupied(str(target.map_id),x,y):
					_transition(str(target.map_id),x,y,int(state.character.direction),"blink_attack");break
		if bool(skill.get("pull_target",false)):
			for offset in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
				var x: int=int(state.character.x)+offset.x;var y: int=int(state.character.y)+offset.y
				if valid_position(str(target.map_id),x,y) and not _occupied(str(target.map_id),x,y,str(target.id)):
					target.x=x;target.y=y;_event("monster_pulled",{"target_id":target.id,"map_id":target.map_id,"x":x,"y":y});break
		var targets: Array=[target]
		if kind=="damage" and str(skill.get("delivery","melee"))=="area":
			targets=[]
			for candidate in state.monsters.values():
				if bool(candidate.alive) and str(candidate.map_id)==str(target.map_id) and _distance(candidate,target)<=int(skill.get("radius",1)) and _line_clear(str(target.map_id),target,candidate): targets.append(candidate)
		if not skill.get("directional_pattern",[]).is_empty(): targets=_pattern_targets(skill.directional_pattern,state.character,int(state.character.direction))
		if kind=="blink":
			var point: Dictionary=action.destination
			if not _transition(str(point.map_id),int(point.x),int(point.y),int(point.direction),"blink"):
				_event("cast_failed",{"skill_id":action.skill_id,"reason":"DESTINATION_BECAME_UNAVAILABLE_NO_REFUND"});return
		for monster in targets:
			if kind=="damage":
				var before_hp: int=int(monster.hp)
				_hit_monster(monster,int(action.get("power",skill.get("power",5))),str(action.skill_id),skill.get("effect_id"),skill.get("sound_id"))
				if float(skill.get("heal_fraction",0.0))>0:
					state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+int(round(float(before_hp-int(monster.hp))*float(skill.heal_fraction))))
			if bool(skill.get("forget_aggro",false)): monster.aggro=false;monster.ai_at=_now()+float(skill.get("duration",3.0))
			var status: String=str(skill.get("on_hit_status",skill.get("status","")))
			if not status.is_empty() and bool(monster.alive):
				if not monster.has("statuses"): monster["statuses"]={}
				monster.statuses[str(action.skill_id)]=_status_definition(skill,status)
				monster.aggro=not bool(skill.get("forget_aggro",false))
				_event("status_applied",{"skill_id":action.skill_id,"target_id":monster.id,"status":status})
	elif kind=="revive":
		state.character.dead=false;state.character.hp=maxi(1,int(round(float(state.character.hp_max)*float(skill.get("hp_fraction",0.5)))))
		state.buffs={};state.pending_actions=[]
		_event("revived",{"hp":state.character.hp,"skill_id":action.skill_id})
	elif kind=="loot":
		var collected: Array=[]
		for loot in state.loot:
			if _loot_in_range(loot,skill):
				if _add_item(str(loot.item_id),int(loot.quantity)):
					collected.append(loot);state.stats.items_picked_up=int(state.stats.items_picked_up)+int(loot.quantity)
					_event("picked_up",{"loot_id":loot.loot_id,"item_id":loot.item_id,"quantity":loot.quantity})
		for loot in collected: state.loot.erase(loot)
		if collected.is_empty(): _event("cast_failed",{"skill_id":action.skill_id,"reason":"NO_SPACE_OR_LOOT_NO_REFUND"});return
	elif kind=="heal": state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+int(skill.get("power",20)))
	elif kind=="restore_mp": state.character.mp=int(state.character.mp_max) if bool(skill.get("restore_full_mp",false)) else mini(int(state.character.mp_max),int(state.character.mp)+int(skill.get("power",20)))
	elif kind=="buff" or kind=="status":
		state.buffs[str(action.skill_id)]=_status_definition(skill,str(skill.get("status","")))
	elif kind=="cleanse":
		for id in state.buffs.keys():
			if str(state.buffs[id].get("status","")) in skill.get("cleanse_statuses",["poison","paralysis","slow","silence"]): state.buffs.erase(id)
	elif kind=="identify":
		var index: int=_inventory_index(str(action.get("instance_id","")))
		if index<0: _event("cast_failed",{"skill_id":action.skill_id,"reason":"ITEM_NO_LONGER_OWNED_NO_REFUND"});return
		state.inventory[index]["identified"]=true
		_event("item_identified",{"instance_id":action.instance_id,"item_id":state.inventory[index].item_id,"properties":data.items[state.inventory[index].item_id].duplicate(true)})
	elif kind=="summon":
		if not state.has("summons"): state["summons"]=[]
		if state.summons.size()>=int(_config("max_summons",3)): _event("cast_failed",{"skill_id":action.skill_id,"reason":"SUMMON_LIMIT_NO_REFUND"});return
		var id: String="summon:"+str(state.next_instance_id);state.next_instance_id=int(state.next_instance_id)+1
		state.summons.append({"id":id,"monster_id":str(skill.monster_id),"map_id":state.character.map_id,"x":state.character.x,"y":state.character.y,"expires_at":_now()+float(skill.get("duration",20.0)),"attack_at":_now()+0.2,"power":int(skill.get("power",5)),"range":int(skill.get("range",4)),"interval":maxf(0.1,float(skill.get("attack_interval",1.0)))})
		_event("summoned",{"summon_id":id,"monster_id":skill.monster_id,"map_id":state.character.map_id,"x":state.character.x,"y":state.character.y,"duration":skill.get("duration",20.0)})
	elif kind=="return":
		var d: Dictionary=action.destination
		if not _transition(str(d.map_id),int(d.x),int(d.y),_direction_value(d.get("direction",2)),"inn_return" if bool(skill.get("return_to_inn",false)) else "directional_return"):
			_event("cast_failed",{"skill_id":action.skill_id,"reason":"DESTINATION_BECAME_UNAVAILABLE_NO_REFUND"});return
	elif kind=="shrine":
		var d: Dictionary=data.get("shrine",data.respawn)
		if not _transition(str(d.map_id),int(d.x),int(d.y),_direction_value(d.get("direction",2)),"ghost_to_shrine"):
			_event("cast_failed",{"skill_id":action.skill_id,"reason":"SHRINE_DESTINATION_UNAVAILABLE"});return
	else:
		_event("cast_failed",{"skill_id":action.skill_id,"reason":"UNSUPPORTED_ACTION"});return
	if not skill.get("inspect_self_fields",[]).is_empty(): _event("player_inspected",{"fields":skill.inspect_self_fields,"stats":derived_stats(),"inventory":state.inventory.duplicate(true)})
	if bool(skill.get("reveal_hidden",false)): _event("nearby_revealed",{"positions":state.monsters.values().filter(func(monster): return bool(monster.alive) and str(monster.map_id)==str(state.character.map_id)).map(func(monster): return {"id":monster.id,"x":monster.x,"y":monster.y})})
	if not str(skill.get("narration","")).is_empty(): _event("skill_narration",{"skill_id":action.skill_id,"text":str(skill.narration)})
	_event("skill_applied",{"skill_id":action.skill_id,"kind":kind,"effect_id":skill.get("effect_id"),"sound_id":skill.get("sound_id"),"duration":float(skill.get("visual_duration",0.8)),"map_id":state.character.map_id,"x":state.character.x,"y":state.character.y,"hp":state.character.hp,"mp":state.character.mp})

func _monster_move(monster: Dictionary,dx: int,dy: int) -> bool:
	var x: int=int(monster.x)+dx;var y: int=int(monster.y)+dy
	if _barrier_blocks({"map_id":monster.map_id,"x":x,"y":y}): return false
	if not can_step(str(monster.map_id),int(monster.x),int(monster.y),x,y) or _occupied(str(monster.map_id),x,y,str(monster.id)) or (str(monster.map_id)==str(state.character.map_id) and x==int(state.character.x) and y==int(state.character.y)): return false
	for exit in data.maps[monster.map_id].get("exits",[]):
		if int(exit.x)==x and int(exit.y)==y: return false
	var from: Dictionary={"x":monster.x,"y":monster.y}
	monster.x=x;monster.y=y
	_event("monster_moved",{"target_id":monster.id,"from":from,"x":x,"y":y,"map_id":monster.map_id})
	return true

func _update_monster(monster: Dictionary) -> void:
	if not _active_monster(monster): return
	var def: Dictionary=data.monsters[monster.monster_id]
	if not monster.alive:
		if _now()>=float(monster.respawn_at) and not _occupied(str(monster.map_id),int(monster.spawn_x),int(monster.spawn_y),str(monster.id)) and not (int(monster.spawn_x)==int(state.character.x) and int(monster.spawn_y)==int(state.character.y)):
			monster["statuses"]={}
			monster.x=monster.spawn_x;monster.y=monster.spawn_y;monster.hp=int(def.hp);monster.alive=true;monster.aggro=false;monster.generation=int(monster.generation)+1;monster.ai_at=_now()+float(def.get("move_interval",1.0));monster.attack_at=_now()+float(def.get("attack_interval",1.0))
			_event("monster_respawned",{"target_id":monster.id,"monster_id":monster.monster_id,"generation":monster.generation})
		return
	if bool(state.character.dead) or _has_status(monster.get("statuses",{}),"paralysis"): return
	var distance: int=_distance(monster,state.character)
	var hostile: bool=(bool(monster.aggro) or str(def.get("aggression","retaliate")) in ["hostile","HOSTILE_DOCUMENTED"]) and not _has_status(state.buffs,"stealth")
	if hostile and distance<=int(def.get("attack_range",1)) and _line_clear(str(monster.map_id),monster,state.character) and _now()>=float(monster.attack_at) and state.pending_actions.size()<32:
		monster.attack_at=_now()+float(def.get("attack_interval",1.0))
		state.pending_actions.append({"kind":"monster_attack","target_id":monster.id,"target_generation":monster.generation,"map_id":monster.map_id,"due":_now()+float(def.get("attack_windup",0.2))})
		_event("monster_attack_started",{"target_id":monster.id,"impact_delay":float(def.get("attack_windup",0.2))})
	if _now()<float(monster.ai_at): return
	var slow: float=2.0 if _has_status(monster.get("statuses",{}),"slow") else 1.0
	monster.ai_at=_now()+maxf(0.2,float(def.get("move_interval",1.0)))*slow
	var low_hp_flee: bool=bool(def.get("low_hp_flee",false)) and int(monster.hp)<int(def.hp)*float(def.get("flee_hp_fraction",0.3))
	var dx: int=0;var dy: int=0
	var home_distance: int=absi(int(monster.x)-int(monster.spawn_x))+absi(int(monster.y)-int(monster.spawn_y))
	if home_distance>int(def.get("leash_range",8)):
		monster.aggro=false
		dx=signi(int(monster.spawn_x)-int(monster.x));dy=signi(int(monster.spawn_y)-int(monster.y))
	elif hostile and int(def.get("attack_range",1))>1 and distance<=int(def.get("attack_range",1)) and not low_hp_flee:
		return
	elif (hostile or low_hp_flee) and distance<=int(def.get("chase_range",6)):
		dx=signi(int(state.character.x)-int(monster.x));dy=signi(int(state.character.y)-int(monster.y))
		if low_hp_flee: dx=-dx;dy=-dy
	else:
		var direction: int=_random_int(0,4)
		if direction==0: dx=1
		elif direction==1: dx=-1
		elif direction==2: dy=1
		elif direction==3: dy=-1
	if dx!=0 and dy!=0:
		if _random_int(0,1)==0: dy=0
		else: dx=0
	if dx!=0 or dy!=0: _monster_move(monster,dx,dy)

func tick(seconds: float) -> Dictionary:
	_events=[]
	if state.is_empty() or not is_finite(seconds) or seconds<=0.0: return _response("NO_CHANGE","NO_TIME_ADVANCE")
	var prior: Dictionary=state
	_begin_transaction(prior)
	state.time_accumulator=float(state.time_accumulator)+minf(seconds,5.0)
	var steps := 0
	while float(state.time_accumulator)+0.000001>=STEP and steps<100:
		state.time_accumulator=maxf(0.0,float(state.time_accumulator)-STEP)
		state.sim_time=float(state.sim_time)+STEP
		var due: Array=[];var pending: Array=[]
		for action in state.pending_actions:
			if float(action.due)<=_now()+0.000001: due.append(action)
			else: pending.append(action)
		state.pending_actions=pending
		for action in due: _resolve_action(action)
		for id in state.buffs.keys():
			if _now()>=float(state.buffs[id].expires_at):
				state.buffs.erase(id);_event("buff_expired",{"skill_id":id})
		_update_statuses()
		_update_summons()
		for monster_id in _map_monster_ids.get(str(state.character.map_id),[]):
			_update_monster(state.monsters[monster_id])
		# Out of combat, slow native stat recovery is a declared balance rule.
		if not bool(state.character.dead) and _ready("combat_until") and int(floor(_now()/float(_config("regen_interval",4.0))))>int(floor((_now()-STEP)/float(_config("regen_interval",4.0)))):
			state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+int(_config("regen_hp",1))+int(derived_stats().get("regen_bonus",0)))
			state.character.mp=mini(int(state.character.mp_max),int(state.character.mp)+int(_config("regen_mp",2))+int(derived_stats().get("regen_bonus",0)))
		steps+=1
	if seconds>5.0: _event("time_clamped",{"requested_seconds":seconds,"simulated_seconds":5.0})
	_sync_equipment_resources()
	state.revision=int(prior.revision)+1
	_end_transaction()
	return _response("OK","TIME_ADVANCED",true)

func _valid_status(value: Variant) -> bool:
	if typeof(value)!=TYPE_DICTIONARY or not value.has("expires_at") or typeof(value.expires_at) not in [TYPE_INT,TYPE_FLOAT] or not is_finite(float(value.expires_at)) or float(value.expires_at)<0: return false
	if str(value.get("status","")) not in STATUS_KINDS+[""]: return false
	if not str(value.get("form_monster_id","")).is_empty() and not data.monsters.has(str(value.form_monster_id)): return false
	if typeof(value.get("directional_pattern",[]))!=TYPE_ARRAY: return false
	for direction in value.get("directional_pattern",[]):
		if direction not in ["front","back","left","right"]: return false
	if str(value.get("status",""))=="poison" and (not value.has("next_tick") or not value.has("tick_interval")): return false
	for key in ["attack","defense","power"]:
		if value.has(key) and not _integer(value[key],-MAX_VALUE,MAX_VALUE): return false
	for key in ["attack_multiplier","damage_multiplier","move_multiplier","next_tick","tick_interval","reflect_fraction","reflect_probability","evasion_chance","next_hit_multiplier","poison_hp_fraction","finisher_multiplier","accuracy_bonus"]:
		if value.has(key) and (typeof(value[key]) not in [TYPE_INT,TYPE_FLOAT] or not is_finite(float(value[key])) or float(value[key])<0): return false
	return true

func _has_status(statuses: Dictionary,status: String) -> bool:
	for entry in statuses.values():
		if str(entry.get("status",""))==status and float(entry.expires_at)>_now(): return true
	return false

func _status_definition(skill: Dictionary,status: String) -> Dictionary:
	return {"barrier_radius":int(skill.get("barrier_radius",0)),"finisher_multiplier":float(skill.get("finisher_multiplier",1.0)),"accuracy_bonus":float(skill.get("accuracy_bonus",0.0)),"directional_pattern":skill.get("directional_pattern",[]).duplicate(),"rooted":bool(skill.get("rooted",false)),"next_hit_multiplier":float(skill.get("next_hit_multiplier",1.0)),"evasion_chance":float(skill.get("evasion_chance",0.0)),"reflect_probability":float(skill.get("reflect_probability",1.0)),"poison_hp_fraction":float(skill.get("poison_hp_fraction",0.0)),"form_monster_id":str(skill.get("form_monster_id","")),"reflect_fraction":clampf(float(skill.get("reflect_fraction",0.0)),0.0,1.0),"expires_at":_now()+float(skill.get("status_duration",skill.get("duration",20.0))),"status":status,"attack":int(skill.get("attack_bonus",0)),"defense":int(skill.get("defense_bonus",0)),"attack_multiplier":float(skill.get("attack_multiplier",1.0)),"damage_multiplier":float(skill.get("damage_multiplier",0.6 if status=="protection" else 1.0)),"move_multiplier":float(skill.get("move_multiplier",0.7 if status=="haste" else (2.0 if status=="slow" else 1.0))),"power":int(skill.get("status_power",skill.get("power",1))),"next_tick":_now()+maxf(0.1,float(skill.get("tick_interval",1.0))),"tick_interval":maxf(0.1,float(skill.get("tick_interval",1.0)))}

func _move_multiplier() -> float:
	var multiplier: float=1.0
	for buff in state.buffs.values(): multiplier*=float(buff.get("move_multiplier",1.0))
	return maxf(0.1,multiplier)

func _break_stealth() -> void:
	for id in state.buffs.keys():
		if str(state.buffs[id].get("status",""))=="stealth": state.buffs.erase(id);_event("stealth_broken",{"skill_id":id})

func _update_statuses() -> void:
	var ids: Array=_status_monster_ids if _in_transaction else state.monsters.keys()
	for monster_id in ids:
		var monster: Dictionary=state.monsters[monster_id]
		for id in monster.get("statuses",{}).keys():
			var effect: Dictionary=monster.statuses[id]
			if _now()>=float(effect.expires_at): monster.statuses.erase(id);_event("status_expired",{"target_id":monster.id,"skill_id":id});continue
			if bool(monster.alive) and str(effect.get("status",""))=="poison" and _now()+0.000001>=float(effect.next_tick):
				effect.next_tick=_now()+maxf(0.1,float(effect.get("tick_interval",1.0)))
				_hit_monster(monster,maxi(1,int(data.monsters[monster.monster_id].hp*float(effect.get("poison_hp_fraction",0.0))) if float(effect.get("poison_hp_fraction",0.0))>0 else int(effect.get("power",1))),str(id))
	for id in state.buffs.keys():
		if not state.buffs.has(id): continue
		var effect: Dictionary=state.buffs[id]
		if str(effect.get("status",""))=="poison" and not bool(state.character.dead) and _now()+0.000001>=float(effect.get("next_tick",MAX_VALUE)):
			effect.next_tick=_now()+maxf(0.1,float(effect.get("tick_interval",1.0)))
			_damage_player(maxi(1,int(effect.get("power",1))),"poison:"+str(id))

func _update_summons() -> void:
	if not state.has("summons"): return
	var retained: Array=[]
	for summon in state.summons:
		if bool(state.character.dead) or _now()>=float(summon.expires_at) or str(summon.map_id)!=str(state.character.map_id):
			_event("summon_expired",{"summon_id":summon.id});continue
		summon.x=state.character.x;summon.y=state.character.y
		if _now()>=float(summon.attack_at):
			summon.attack_at=_now()+float(summon.interval)
			var target_id: String=attack_target(int(summon.range))
			if not target_id.is_empty():
				_hit_monster(state.monsters[target_id],int(summon.power),str(summon.id))
				_event("summon_attack",{"summon_id":summon.id,"target_id":target_id,"monster_id":summon.monster_id})
		retained.append(summon)
	state.summons=retained

func _advancement_eligible(definition: Dictionary) -> bool:
	var required_id: String=str(definition.get("required_advancement",""))
	if required_id.is_empty(): return true
	if not data.get("advancements",{}).has(required_id): return false
	return str(data.advancements[required_id].job)==str(state.character.job) and int(state.character.get("advancement_rank",0))>=int(data.advancements[required_id].get("rank",1))

func _quest_progress(kind: String,id: String) -> void:
	for quest_id in state.get("quests",{}):
		var progress: Dictionary=state.quests[quest_id]
		if str(progress.get("status",""))!="active" or not data.get("quests",{}).has(quest_id): continue
		for objective in data.quests[quest_id].get("objectives",[]):
			if str(objective.kind)==kind and str(objective.id)==id:
				var key: String=kind+":"+id
				progress.progress[key]=1 if kind=="visit" else mini(MAX_VALUE,int(progress.progress.get(key,0))+1)

func _quest_accept(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("quest_id",""))
	if not data.get("quests",{}).has(id): return _response("REFUSED","UNKNOWN_QUEST")
	var quest: Dictionary=data.quests[id]
	if str(cmd.get("npc_id",""))!=str(quest.npc_id) or _near_npc(str(quest.npc_id),"quest").is_empty(): return _response("REFUSED","QUEST_NPC_REQUIRED")
	if state.quests.has(id): return _response("REFUSED","QUEST_ALREADY_ACCEPTED")
	if int(state.character.level)<int(quest.get("minimum_level",1)): return _response("REFUSED","LEVEL_TOO_LOW")
	if str(quest.get("required_job","")) not in ["","any",str(state.character.job)]: return _response("REFUSED","WRONG_JOB")
	for previous in quest.get("requires_quests",[]):
		if str(state.quests.get(previous,{}).get("status",""))!="completed": return _response("REFUSED","PREVIOUS_QUEST_REQUIRED")
	state.quests[id]={"status":"active","progress":{}}
	for objective in quest.get("objectives",[]):
		if str(objective.kind)=="visit" and str(objective.id)==str(state.character.map_id): state.quests[id].progress["visit:"+str(objective.id)]=1
	_event("quest_accepted",{"quest_id":id,"npc_id":quest.npc_id})
	return _response("OK","QUEST_ACCEPTED",true)

func _quest_complete(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("quest_id",""))
	if not data.get("quests",{}).has(id): return _response("REFUSED","UNKNOWN_QUEST")
	var quest: Dictionary=data.quests[id]
	if str(cmd.get("npc_id",""))!=str(quest.npc_id) or _near_npc(str(quest.npc_id),"quest").is_empty(): return _response("REFUSED","QUEST_NPC_REQUIRED")
	if str(state.quests.get(id,{}).get("status",""))!="active": return _response("REFUSED","QUEST_NOT_ACTIVE")
	for objective in quest.get("objectives",[]):
		var amount: int=item_count(str(objective.id)) if str(objective.kind)=="collect" else int(state.quests[id].progress.get(str(objective.kind)+":"+str(objective.id),0))
		if amount<int(objective.get("count",1)): return _response("REFUSED","QUEST_OBJECTIVE_INCOMPLETE")
	for objective in quest.get("objectives",[]):
		if str(objective.kind)=="collect" and bool(objective.get("consume",true)) and not _remove_item(str(objective.id),int(objective.get("count",1))): return _response("REFUSED","MATERIAL_EQUIPPED")
	var rewards: Dictionary=quest.get("rewards",{})
	for item_id in rewards.get("items",{}):
		if not _add_item(str(item_id),int(rewards.items[item_id])): return _response("REFUSED","INVENTORY_FULL")
	if int(state.character.money)+int(rewards.get("money",0))>MAX_VALUE: return _response("REFUSED","MONEY_LIMIT")
	state.character.money=int(state.character.money)+int(rewards.get("money",0))
	_grant_xp(int(rewards.get("xp",0)))
	state.quests[id].status="completed"
	_event("quest_completed",{"quest_id":id,"rewards":rewards})
	return _response("OK","QUEST_COMPLETED",true)

func _craft(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("recipe_id",""))
	if not data.get("recipes",{}).has(id): return _response("REFUSED","UNKNOWN_RECIPE")
	var recipe: Dictionary=data.recipes[id]
	if str(cmd.get("npc_id",""))!=str(recipe.npc_id) or _near_npc(str(recipe.npc_id),"craft").is_empty(): return _response("REFUSED","CRAFT_NPC_REQUIRED")
	if int(state.character.level)<int(recipe.get("minimum_level",1)): return _response("REFUSED","LEVEL_TOO_LOW")
	if str(recipe.get("required_job","")) not in ["","any",str(state.character.job)]: return _response("REFUSED","WRONG_JOB")
	if not _pay_requirements(recipe): return _response("REFUSED","INSUFFICIENT_MONEY_OR_MATERIALS")
	for item_id in recipe.get("results",{}):
		if not _add_item(str(item_id),int(recipe.results[item_id])): return _response("REFUSED","INVENTORY_FULL")
	_quest_progress("craft",id)
	_event("crafted",{"recipe_id":id,"results":recipe.get("results",{})})
	return _response("OK","CRAFTED",true)

func _pay_requirements(definition: Dictionary) -> bool:
	var money: int=int(definition.get("money",0))
	if money<0 or int(state.character.money)<money: return false
	for item_id in definition.get("ingredients",{}):
		if not _remove_item(str(item_id),int(definition.ingredients[item_id])): return false
	state.character.money=int(state.character.money)-money
	return true

func _advance(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("advancement_id",""))
	if not data.get("advancements",{}).has(id): return _response("REFUSED","UNKNOWN_ADVANCEMENT")
	var advancement: Dictionary=data.advancements[id]
	var npc_id: String=str(cmd.get("npc_id",""))
	if npc_id not in advancement.get("teacher_ids",[]) or _near_npc(npc_id,"advance").is_empty(): return _response("REFUSED","ADVANCEMENT_TEACHER_REQUIRED")
	if str(advancement.job)!=str(state.character.job): return _response("REFUSED","WRONG_JOB")
	if int(state.character.level)<int(advancement.get("minimum_level",99)): return _response("REFUSED","LEVEL_TOO_LOW")
	if int(state.character.get("advancement_rank",0))+1!=int(advancement.get("rank",1)): return _response("REFUSED","ADVANCEMENT_ORDER_REQUIRED")
	if not _pay_requirements(advancement): return _response("REFUSED","INSUFFICIENT_MONEY_OR_MATERIALS")
	state.character["advancement"]=id;state.character["advancement_rank"]=int(advancement.get("rank",1));state.character["title"]=str(advancement.get("title",id))
	_event("advanced",{"advancement_id":id,"job":state.character.job,"rank":state.character.advancement_rank,"title":state.character.title})
	return _response("OK","ADVANCED",true)

func _attribute_gain(job: String,stat: String) -> int:
	var primary: String={"전사":"strength","도적":"dexterity","주술사":"intelligence","도사":"intelligence"}.get(job,"")
	return maxi(0,int(data.get("job_growth",{}).get(job,{}).get(stat+"_per_level",2 if primary==stat else 1)))

func _base_attributes() -> Dictionary:
	var c: Dictionary=state.get("character",{})
	if c.has("base_stats"): return c.base_stats.duplicate(true)
	var result: Dictionary={}
	for stat in ["strength","dexterity","intelligence"]: result[stat]=5+maxi(0,int(c.get("level",1))-1)*_attribute_gain(str(c.get("job","commoner")),stat)
	return result

func _train(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("training_id",""))
	if not data.get("training_rules",{}).has(id): return _response("REFUSED","UNKNOWN_TRAINING_RULE")
	var rule: Dictionary=data.training_rules[id]
	var npc_id: String=str(cmd.get("npc_id",""))
	if npc_id not in rule.get("teacher_ids",[]) or _near_npc(npc_id,"training").is_empty(): return _response("REFUSED","TRAINING_NPC_REQUIRED")
	var c: Dictionary=state.character
	if int(c.level)<int(rule.get("minimum_level",90)): return _response("REFUSED","LEVEL_TOO_LOW")
	var cost: int=int(rule.xp_cost)
	if int(c.xp)-cost<int(data.xp_thresholds[int(c.level)-1]): return _response("REFUSED","INSUFFICIENT_SURPLUS_XP")
	var stat: String=str(rule.stat);var increase: int=int(rule.increase)
	if not c.has("base_stats"): c["base_stats"]=_base_attributes()
	var current: int=int(c[stat]) if stat in ["hp_max","mp_max"] else int(c.base_stats[stat])
	if current+increase>int(rule.cap): return _response("REFUSED","TRAINING_CAP_REACHED")
	c.xp=int(c.xp)-cost
	if stat in ["hp_max","mp_max"]:
		c[stat]=current+increase
		var resource: String="hp" if stat=="hp_max" else "mp"
		c[resource]=mini(int(c[stat]),int(c[resource])+increase)
	else: c.base_stats[stat]=current+increase
	_event("trained",{"training_id":id,"stat":stat,"increase":increase,"value":current+increase,"xp_cost":cost})
	return _response("OK","TRAINED",true)

func _store_transfer(cmd: Dictionary,deposit: bool) -> Dictionary:
	var npc_id: String=str(cmd.get("npc_id",""))
	if _near_npc(npc_id,"storage").is_empty(): return _response("REFUSED","STORAGE_NPC_REQUIRED")
	if not state.has("bank_inventory"): state["bank_inventory"]=[]
	var source: Array=state.inventory if deposit else state.bank_inventory
	var destination: Array=state.bank_inventory if deposit else state.inventory
	var instance_id: String=str(cmd.get("instance_id",""))
	if deposit and instance_id in state.equipment.values(): return _response("REFUSED","UNEQUIP_FIRST")
	var index: int=-1
	for i in range(source.size()):
		if str(source[i].instance_id)==instance_id: index=i;break
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	var capacity: int=int(_config("bank_slots",120)) if deposit else int(_config("inventory_slots",_config("inventory_capacity",60)))
	if destination.size()>=capacity: return _response("REFUSED","STORAGE_FULL" if deposit else "INVENTORY_FULL")
	var instance: Dictionary=source[index]
	destination.append(instance);source.remove_at(index)
	_event("stored" if deposit else "withdrawn",{"instance_id":instance_id,"item_id":instance.item_id,"quantity":instance.quantity,"npc_id":npc_id})
	return _response("OK","STORED" if deposit else "WITHDRAWN",true)

func _rename_weapon(cmd: Dictionary) -> Dictionary:
	var npc: Dictionary=_near_npc(str(cmd.get("npc_id","")),"weapon_naming")
	if npc.is_empty(): return _response("REFUSED","WEAPON_NAMING_NPC_REQUIRED")
	var index: int=_inventory_index(str(cmd.get("instance_id","")))
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	var instance: Dictionary=state.inventory[index]
	if str(data.items[instance.item_id].get("slot",""))!="weapon": return _response("REFUSED","WEAPON_REQUIRED")
	var name: String=str(cmd.get("name",""))
	if not _safe_name(name): return _response("REFUSED","INVALID_CUSTOM_NAME")
	if str(instance.get("custom_name",""))==name: return _response("REFUSED","NAME_UNCHANGED")
	var cost: int=maxi(0,int(npc.get("naming_cost",20)))
	if int(state.character.money)<cost: return _response("REFUSED","INSUFFICIENT_MONEY")
	state.character.money=int(state.character.money)-cost;instance["custom_name"]=name
	_event("weapon_named",{"instance_id":instance.instance_id,"name":name,"cost":cost})
	return _response("OK","WEAPON_NAMED",true)

func _return_gates() -> Dictionary:
	return data.get("nation_gates",{}).get(str(state.character.get("nationality","고구려")),data.gates)

func _sync_equipment_resources() -> void:
	if state.is_empty(): return
	var hp_bonus: int=0;var mp_bonus: int=0
	for iid in state.get("equipment",{}).values():
		var index: int=_inventory_index(str(iid))
		if index<0: continue
		var instance: Dictionary=state.inventory[index];var definition: Dictionary=data.items[instance.item_id]
		if int(definition.get("durability",0))>0 and int(instance.durability)<=0: continue
		hp_bonus+=int(definition.get("hp_bonus",0));mp_bonus+=int(definition.get("mp_bonus",0))
	var c: Dictionary=state.character
	if hp_bonus==0 and mp_bonus==0 and not c.has("equipment_hp_bonus") and not c.has("equipment_mp_bonus"): return
	c.hp_max=maxi(1,int(c.hp_max)-int(c.get("equipment_hp_bonus",0))+hp_bonus)
	c.mp_max=maxi(1,int(c.mp_max)-int(c.get("equipment_mp_bonus",0))+mp_bonus)
	c["equipment_hp_bonus"]=hp_bonus;c["equipment_mp_bonus"]=mp_bonus
	c.hp=mini(int(c.hp),int(c.hp_max));c.mp=mini(int(c.mp),int(c.mp_max))

func _consume_next_hit() -> float:
	var multiplier: float=1.0
	for id in state.buffs.keys():
		if float(state.buffs[id].get("next_hit_multiplier",1.0))>1.0:
			multiplier=maxf(multiplier,float(state.buffs[id].next_hit_multiplier));state.buffs.erase(id)
	return multiplier

func _attack_pattern() -> Array:
	var pattern: Array=[]
	for buff in state.buffs.values():
		for direction in buff.get("directional_pattern",[]):
			if direction not in pattern: pattern.append(direction)
	return pattern

func _pattern_targets(pattern: Array,origin: Dictionary,facing: int) -> Array:
	var targets: Array=[]
	var directions: Array=[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]
	for word in pattern:
		var offset: int=int({"front":0,"right":1,"back":2,"left":3}.get(word,0))
		var at: Vector2i=directions[(facing+offset)%4]
		for monster in state.monsters.values():
			if bool(monster.alive) and str(monster.map_id)==str(origin.map_id) and int(monster.x)==int(origin.x)+at.x and int(monster.y)==int(origin.y)+at.y and _line_clear(str(origin.map_id),origin,monster): targets.append(monster)
	return targets
func _die_player() -> void:
	if bool(state.character.dead): return
	state.character.dead=true;state.pending_actions=[];state.buffs={};state["summons"]=[];state.stats.deaths=int(state.stats.deaths)+1
	var lost: int=int(floor(int(state.character.money)*float(_config("death_money_loss_fraction",_config("death_money_loss_ratio",0.0)))))
	state.character.money=int(state.character.money)-lost
	_event("player_died",{"money_lost":lost,"xp_lost":0,"inventory_preserved":true,"resurrection_available":true})

func _finisher_multiplier(kind: String) -> float:
	var result: float=1.0
	if kind=="damage":
		for buff in state.buffs.values(): result*=float(buff.get("finisher_multiplier",1.0))
	return result

func _loot_in_range(loot: Dictionary,skill: Dictionary) -> bool:
	if str(loot.map_id)!=str(state.character.map_id) or _distance(loot,state.character)>int(skill.get("range",3)): return false
	if bool(skill.get("pickup_front_only",false)):
		var offset: Vector2i=[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT][int(state.character.direction)]
		return int(loot.x)==int(state.character.x)+offset.x and int(loot.y)==int(state.character.y)+offset.y
	return true

func _barrier_blocks(point: Dictionary) -> bool:
	if str(point.map_id)!=str(state.character.map_id): return false
	for buff in state.buffs.values():
		if int(buff.get("barrier_radius",0))>0 and _distance(point,state.character)<=int(buff.barrier_radius): return true
	return false

