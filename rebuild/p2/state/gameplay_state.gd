extends RefCounted
## One authoritative offline P3 state. Definitions are immutable; UI sends commands.
## All costs/rewards commit atomically; visual frames never drive combat or RNG.
const JOBS := ["전사", "도적", "주술사", "도사"]
const STEP := 0.05
const MAX_REQUESTS := 2048
const MAX_VALUE := 1000000000
var state: Dictionary = {}
var data: Dictionary = {}
var errors: Array[String] = []
var _blocked: Dictionary = {}
var _events: Array = []

func configure(definitions: Dictionary) -> bool:
	errors.clear()
	for key in ["profile", "maps", "npcs", "items", "monsters", "skills", "start", "gates", "respawn", "xp_thresholds"]:
		if not definitions.has(key): errors.append("MISSING_DEFINITION:"+key)
	if not errors.is_empty(): return false
	if definitions.maps.is_empty() or definitions.xp_thresholds.size()<5: errors.append("EMPTY_WORLD_OR_GROWTH")
	data=definitions.duplicate(true)
	_blocked.clear()
	for map_id in data.maps:
		var map: Dictionary=data.maps[map_id]
		if int(map.get("width",0))<=0 or int(map.get("height",0))<=0:
			errors.append("INVALID_MAP_SIZE:"+str(map_id))
		_blocked[map_id]={}
		for point in map.get("blocked",[]):
			_blocked[map_id][str(int(point[0]))+","+str(int(point[1]))]=true
	for map_id in data.maps:
		for exit in data.maps[map_id].get("exits",[]):
			if not valid_position(str(exit.to_map),int(exit.to_x),int(exit.to_y)): errors.append("INVALID_EXIT_DESTINATION:"+str(map_id))
	for id in data.npcs:
		var npc: Dictionary=data.npcs[id]
		if not valid_position(str(npc.map_id),int(npc.x),int(npc.y)): errors.append("INVALID_NPC_POSITION:"+str(id))
		for item_id in npc.get("shop",{}):
			if not data.items.has(item_id): errors.append("UNKNOWN_SHOP_ITEM:"+str(item_id))
			var trade: Dictionary=npc.shop[item_id]
			if trade.get("buy_price")!=null and int(trade.buy_price)<0: errors.append("NEGATIVE_SHOP_PRICE")
			if trade.get("sell_price")!=null and int(trade.sell_price)<0: errors.append("NEGATIVE_SHOP_PRICE")
	for id in data.skills:
		var skill: Dictionary=data.skills[id]
		if str(skill.get("kind","")) not in ["damage","heal","buff","return","shrine","identify","restore_mp"]: errors.append("UNSUPPORTED_SKILL:"+str(id))
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
	return errors.is_empty()

func valid_position(map_id: String,x: int,y: int) -> bool:
	if not data.get("maps",{}).has(map_id): return false
	var map: Dictionary=data.maps[map_id]
	return x>=0 and y>=0 and x<int(map.width) and y<int(map.height) and not _blocked.get(map_id,{}).has(str(x)+","+str(y))

func _config(key: String,fallback: Variant) -> Variant:
	return data.get("config",{}).get(key,fallback)

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
	var start: Dictionary=data.start
	var seed: int=int(options.get("seed",abs((owner+":"+name).hash()))) & 0x7fffffff
	if seed==0: seed=1
	var hp: int=int(start.get("hp",50))
	var mp: int=int(start.get("mp",30))
	state={"schema":"baram.p3.gameplay-payload/1","profile":data.profile,
		"character":{"id":"character:"+(owner+":"+name).sha256_text().substr(0,20),"name":name,"owner_id":owner,"job":"commoner","desired_job":options.get("desired_job"),"level":1,"xp":0,"hp":hp,"hp_max":hp,"mp":mp,"mp_max":mp,"money":int(start.get("money",0)),"map_id":str(start.map_id),"x":int(start.x),"y":int(start.y),"direction":2,"dead":false,"appearance":options.get("appearance",{}).duplicate(true),"nationality":options.get("nationality","고구려"),"guardian":options.get("guardian","주작")},
		"inventory":[],"equipment":{},"skills":[],"hotkeys":{},"quests":{},"loot":[],"monsters":{},"buffs":{},"cooldowns":{},"revision":1,"rng_state":seed,"applied_request_ids":[],"request_watermarks":{},"sim_time":0.0,"time_accumulator":0.0,"pending_actions":[],"next_instance_id":1,"next_loot_id":1,"stats":{"kills":0,"deaths":0,"total_xp_earned":0,"money_earned":0,"items_picked_up":0},"shop_purchases":{}}
	for item in start.get("starter_items",[]):
		if not data.items.has(str(item.item_id)) or not _add_item(str(item.item_id),int(item.get("quantity",1))):
			state={}
			return _response("REFUSED","INVALID_STARTER_ITEM")
	_spawn_all()
	for slot in start.get("initial_equipment",{}):
		var item_id: String=str(start.initial_equipment[slot])
		for item in state.inventory:
			if str(item.item_id)==item_id and str(data.items[item_id].get("slot",""))==str(slot):
				state.equipment[str(slot)]=item.instance_id
				break
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
	if payload.inventory.size()>int(_config("inventory_slots",_config("inventory_capacity",60))) or payload.loot.size()>2048 or payload.monsters.size()>1024 or payload.pending_actions.size()>32 or payload.applied_request_ids.size()>MAX_REQUESTS: return invalid
	var ids: Dictionary={}
	for instance in payload.inventory:
		if typeof(instance)!=TYPE_DICTIONARY or not instance.has_all(["instance_id","item_id","quantity","durability"]): return invalid
		var id: String=str(instance.item_id)
		if not data.items.has(id) or ids.has(str(instance.instance_id)): return {"status":"UNKNOWN_ID","reason":"ITEM_REFERENCE_OR_DUPLICATE","changed":false,"events":[]}
		if not _integer(instance.quantity,1,int(data.items[id].get("stack_max",99))) or not _integer(instance.durability,0,int(data.items[id].get("durability",0))): return invalid
		ids[str(instance.instance_id)]=instance
	var equipped: Dictionary={}
	for slot in payload.equipment:
		var iid: String=str(payload.equipment[slot])
		if not ids.has(iid) or equipped.has(iid) or str(data.items[ids[iid].item_id].get("slot",""))!=str(slot): return invalid
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
	state=prior.duplicate(true)
	var result: Dictionary=_execute(cmd)
	if result.status=="OK" and bool(result.get("changed",false)):
		state.applied_request_ids.append(request_id)
		if state.applied_request_ids.size()>MAX_REQUESTS: state.applied_request_ids.pop_front()
		state.request_watermarks[stream]=sequence
		state.revision=int(prior.revision)+1
		return _response("OK",str(result.reason),true)
	state=prior
	return _response(str(result.status),str(result.reason),false)

func _execute(cmd: Dictionary) -> Dictionary:
	var type: String=str(cmd.get("type",""))
	if type=="cancel": return _response("CANCELLED","CANCELLED")
	if type=="respawn": return _respawn()
	if bool(state.character.dead) and type not in ["talk","cast"]: return _response("REFUSED","CHARACTER_DEAD")
	match type:
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

func _occupied(map_id: String,x: int,y: int,exclude: String="") -> bool:
	for npc in data.npcs.values():
		if str(npc.map_id)==map_id and int(npc.x)==x and int(npc.y)==y: return true
	for id in state.monsters:
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

func _transition(map_id: String,x: int,y: int,direction: int,reason: String) -> bool:
	if not valid_position(map_id,x,y) or _occupied(map_id,x,y): return false
	var c: Dictionary=state.character
	var source: Dictionary={"map_id":c.map_id,"x":c.x,"y":c.y}
	c.map_id=map_id;c.x=x;c.y=y;c.direction=direction
	state.pending_actions=[]
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
	if not valid_position(str(c.map_id),x,y) or _occupied(str(c.map_id),x,y): return _response("REFUSED","BLOCKED_TILE")
	for exit in data.maps[c.map_id].get("exits",[]):
		if int(exit.x)==x and int(exit.y)==y:
			if int(c.level)<int(exit.get("minimum_level",1)): return _response("REFUSED","EXIT_LEVEL_REQUIRED")
			if not _transition(str(exit.to_map),int(exit.to_x),int(exit.to_y),_direction_value(exit.get("direction",_direction(dx,dy))),"exit"): return _response("REFUSED","DESTINATION_UNAVAILABLE")
			return _response("OK","MAP_TRANSITION",true)
	var from: Dictionary={"x":c.x,"y":c.y}
	c.x=x;c.y=y;c.direction=_direction(dx,dy)
	state.cooldowns["move"]=_now()+float(_config("move_interval",0.14))
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
	return _response("OK","DIALOGUE_OPENED")

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
	if def.get("required_job")!=null and str(def.required_job) not in ["","any","전직업","common"] and str(def.required_job)!=str(state.character.job): return _response("REFUSED","WRONG_JOB")
	if int(def.get("durability",0))>0 and int(item.durability)<=0: return _response("REFUSED","ITEM_BROKEN")
	if state.equipment.get(slot)==item.instance_id: return _response("REFUSED","ALREADY_EQUIPPED")
	state.equipment[slot]=item.instance_id
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
	var result: Dictionary={"attack":int(_config("base_attack",3))+int(state.get("character",{}).get("level",1))/3,"defense":int(_config("base_defense",0)),"attack_range":1,"attack_multiplier":1.0,"hp_max":int(state.get("character",{}).get("hp_max",0)),"mp_max":int(state.get("character",{}).get("mp_max",0))}
	for id in state.get("equipment",{}).values():
		var index: int=_inventory_index(str(id))
		if index<0: continue
		var item: Dictionary=state.inventory[index];var def: Dictionary=data.items[item.item_id]
		if int(def.get("durability",0))>0 and int(item.durability)<=0: continue
		result.attack=int(result.attack)+int(def.get("attack",0));result.defense=int(result.defense)+int(def.get("defense",0))
		result.attack_range=maxi(int(result.attack_range),int(def.get("attack_range",1)))
	for buff in state.get("buffs",{}).values():
		result.attack=int(result.attack)+int(buff.get("attack",0));result.defense=int(result.defense)+int(buff.get("defense",0))
		result.attack_multiplier=float(result.attack_multiplier)*float(buff.get("attack_multiplier",1.0))
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
	var def: Dictionary=data.monsters[target.monster_id]
	state.character.direction=_direction(int(target.x)-int(state.character.x),int(target.y)-int(state.character.y))
	var interval: float=float(_config("attack_interval",0.5))
	var windup: float=float(_config("attack_windup",0.18))
	state.cooldowns["combat_until"]=_now()+5.0
	state.cooldowns["attack"]=_now()+interval;state.cooldowns["action"]=_now()+windup
	state.pending_actions.append({"kind":"attack","due":_now()+windup,"map_id":state.character.map_id,"target_id":target.id,"target_generation":target.generation,"range":int(derived_stats().attack_range),"damage":int(derived_stats().attack),"effect_id":_config("attack_effect_id",null),"sound_id":_config("attack_sound_id",null)})
	_event("attack_started",{"target_id":target.id,"duration":interval,"impact_delay":windup,"sound_id":_config("swing_sound_id",null)})
	return _response("OK","ATTACK_STARTED",true)

func _cast(cmd: Dictionary) -> Dictionary:
	var id: String=str(cmd.get("skill_id",""))
	if id not in state.skills or not data.skills.has(id): return _response("REFUSED","SKILL_NOT_LEARNED")
	var skill: Dictionary=data.skills[id];var kind: String=str(skill.kind)
	if str(state.character.job)=="commoner": return _response("REFUSED","JOB_CHANGE_REQUIRED")
	if str(skill.job)!=str(state.character.job) and str(skill.job) not in ["common","COMMON_FOUR_STARTER_JOBS"]: return _response("REFUSED","WRONG_JOB")
	if skill.get("guardian")!=null and str(skill.guardian)!=str(state.character.get("guardian","주작")): return _response("REFUSED","WRONG_GUARDIAN")
	if bool(state.character.dead) and kind!="shrine": return _response("REFUSED","CHARACTER_DEAD")
	if kind=="shrine" and not bool(state.character.dead): return _response("REFUSED","GHOST_REQUIRED")
	if not _ready("skill:"+id) or not _ready("action"): return _response("REFUSED","ACTION_COOLDOWN")
	var mp_cost: int=int(skill.get("mp_cost",0));var hp_cost: int=int(skill.get("hp_cost",0))
	if int(state.character.mp)<mp_cost or int(state.character.hp)<=hp_cost and kind!="shrine": return _response("REFUSED","INSUFFICIENT_HP_MP")
	var target: Dictionary={}
	if kind=="damage":
		target=_target(str(cmd.get("target_id","")),int(skill.get("range",4)))
		if target.is_empty(): return _response("REFUSED","TARGET_OUT_OF_REACH")
	var destination: Dictionary={}
	if kind=="return":
		var direction: String=str(cmd.get("direction",""))
		if direction not in ["east","west","south","north","동","서","남","북"]: return _response("REFUSED","DIRECTION_REQUIRED")
		direction={"동":"east","서":"west","남":"south","북":"north"}.get(direction,direction)
		if not data.gates.has(direction): return _response("REFUSED","RETURN_DESTINATION_UNKNOWN")
		destination=data.gates[direction].duplicate(true)
		if not valid_position(str(destination.map_id),int(destination.x),int(destination.y)) or _occupied(str(destination.map_id),int(destination.x),int(destination.y)): return _response("REFUSED","DESTINATION_UNAVAILABLE")
	if kind=="heal" and int(state.character.hp)>=int(state.character.hp_max): return _response("REFUSED","HP_ALREADY_FULL")
	if kind=="restore_mp" and int(state.character.mp)>=int(state.character.mp_max): return _response("REFUSED","MP_ALREADY_FULL")
	var delay: float=float(skill.get("impact_delay",skill.get("windup",0.25)))
	if kind=="damage": state.cooldowns["combat_until"]=_now()+5.0
	state.character.mp=int(state.character.mp)-mp_cost
	if hp_cost>0: state.character.hp=int(state.character.hp)-hp_cost
	state.cooldowns["skill:"+id]=_now()+float(skill.get("cooldown",0.8));state.cooldowns["action"]=_now()+delay
	state.pending_actions.append({"kind":"skill","skill_id":id,"due":_now()+delay,"map_id":state.character.map_id,"target_id":target.get("id",""),"target_generation":target.get("generation",0),"destination":destination,"direction":cmd.get("direction",""),"range":int(skill.get("range",4))})
	_event("cast_started",{"skill_id":id,"target_id":target.get("id",""),"impact_delay":delay,"duration":float(skill.get("duration",1.0)),"sound_id":skill.get("start_sound_id"),"mp_cost":mp_cost,"hp_cost":hp_cost})
	return _response("OK","CAST_STARTED",true)

func _use_item(cmd: Dictionary) -> Dictionary:
	var index: int=_inventory_index(str(cmd.get("instance_id","")))
	if index<0: return _response("REFUSED","ITEM_NOT_OWNED")
	if not _ready("use_item"): return _response("REFUSED","ACTION_COOLDOWN")
	var instance: Dictionary=state.inventory[index];var def: Dictionary=data.items[instance.item_id]
	var hp: int=int(def.get("hp_restore",0));var mp: int=int(def.get("mp_restore",0))
	if hp<=0 and mp<=0: return _response("REFUSED","ITEM_NOT_CONSUMABLE")
	if (hp<=0 or int(state.character.hp)>=int(state.character.hp_max)) and (mp<=0 or int(state.character.mp)>=int(state.character.mp_max)): return _response("REFUSED","RESOURCE_ALREADY_FULL")
	state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+hp);state.character.mp=mini(int(state.character.mp_max),int(state.character.mp)+mp)
	instance.quantity=int(instance.quantity)-1
	if int(instance.quantity)==0: state.inventory.remove_at(index)
	state.cooldowns["use_item"]=_now()+float(_config("item_use_interval",0.5))
	_event("item_used",{"item_id":instance.item_id,"hp_restore":hp,"mp_restore":mp})
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
		c.level=int(c.level)+1;c.hp_max=int(c.hp_max)+int(_config("hp_per_level",8));c.mp_max=int(c.mp_max)+int(_config("mp_per_level",6))
		c.hp=c.hp_max;c.mp=c.mp_max
		_event("level_up",{"level":c.level,"xp":c.xp,"hp_max":c.hp_max,"mp_max":c.mp_max})

func _kill_monster(target: Dictionary) -> void:
	if not bool(target.alive): return
	var def: Dictionary=data.monsters[target.monster_id]
	target.hp=0;target.alive=false;target.aggro=false;target.respawn_at=_now()+float(target.respawn_seconds)
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
	var defense: int=int(data.monsters[target.monster_id].get("defense",0))
	var actual: int=maxi(1,damage-defense)
	target.hp=maxi(0,int(target.hp)-actual);target.aggro=true
	_event("monster_hit",{"target_id":target.id,"damage":actual,"hp":target.hp,"source":source,"effect_id":effect_id,"sound_id":sound_id,"map_id":target.map_id,"x":target.x,"y":target.y})
	if int(target.hp)<=0: _kill_monster(target)

func _damage_player(damage: int,source: String) -> void:
	if bool(state.character.dead): return
	state.cooldowns["combat_until"]=_now()+5.0
	var actual: int=maxi(1,damage-int(derived_stats().defense))
	state.character.hp=maxi(0,int(state.character.hp)-actual)
	_event("player_hit",{"damage":actual,"hp":state.character.hp,"source":source,"sound_id":_config("player_hit_sound_id",null)})
	for iid in state.equipment.values():
		var index: int=_inventory_index(str(iid))
		if index>=0 and int(state.inventory[index].durability)>0: state.inventory[index].durability=int(state.inventory[index].durability)-1
	if int(state.character.hp)==0:
		state.character.dead=true;state.pending_actions=[];state.buffs={};state.stats.deaths=int(state.stats.deaths)+1
		var lost: int=int(floor(int(state.character.money)*float(_config("death_money_loss_fraction",_config("death_money_loss_ratio",0.0)))))
		state.character.money=int(state.character.money)-lost
		_event("player_died",{"money_lost":lost,"xp_lost":0,"inventory_preserved":true,"resurrection_available":true})

func _resolve_action(action: Dictionary) -> void:
	if str(action.map_id)!=str(state.character.map_id):
		_event("action_cancelled",{"reason":"MAP_CHANGED_NO_REFUND","kind":action.kind})
		return
	if action.kind=="attack":
		var target: Dictionary=_target(str(action.target_id),int(action.range))
		if target.is_empty() or int(target.generation)!=int(action.target_generation):
			_event("attack_missed",{"target_id":action.target_id,"reason":"TARGET_MOVED_OR_GONE"});return
		_hit_monster(target,int(action.damage),"attack",action.get("effect_id"),action.get("sound_id"))
		var iid: String=str(state.equipment.get("weapon",""));var index: int=_inventory_index(iid)
		if index>=0 and int(state.inventory[index].durability)>0: state.inventory[index].durability=int(state.inventory[index].durability)-1
	elif action.kind=="monster_attack":
		if not state.monsters.has(str(action.target_id)): return
		var monster: Dictionary=state.monsters[action.target_id]
		if not monster.alive or int(monster.generation)!=int(action.target_generation) or bool(state.character.dead) or _distance(monster,state.character)>1: return
		_damage_player(int(data.monsters[monster.monster_id].attack),str(monster.id))
	else:
		var skill: Dictionary=data.skills[str(action.skill_id)];var kind: String=str(skill.kind)
		if bool(state.character.dead) and kind!="shrine": return
		if kind=="damage":
			var target: Dictionary=_target(str(action.target_id),int(action.range))
			if target.is_empty() or int(target.generation)!=int(action.target_generation):
				_event("cast_missed",{"skill_id":action.skill_id,"reason":"TARGET_MOVED_OR_GONE_NO_REFUND"});return
			_hit_monster(target,int(skill.get("power",5)),str(action.skill_id),skill.get("effect_id"),skill.get("sound_id"))
		elif kind=="heal": state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+int(skill.get("power",20)))
		elif kind=="restore_mp": state.character.mp=mini(int(state.character.mp_max),int(state.character.mp)+int(skill.get("power",20)))
		elif kind=="buff":
			state.buffs[str(action.skill_id)]={"expires_at":_now()+float(skill.get("duration",20.0)),"attack":int(skill.get("attack_bonus",0)),"defense":int(skill.get("defense_bonus",0)),"attack_multiplier":float(skill.get("attack_multiplier",1.0))}
		elif kind=="return":
			var d: Dictionary=action.destination
			if not _transition(str(d.map_id),int(d.x),int(d.y),_direction_value(d.get("direction",2)),"directional_return"):
				_event("cast_failed",{"skill_id":action.skill_id,"reason":"DESTINATION_BECAME_UNAVAILABLE_NO_REFUND"});return
		elif kind=="shrine":
			var d: Dictionary=data.get("shrine",data.respawn)
			if not _transition(str(d.map_id),int(d.x),int(d.y),_direction_value(d.get("direction",2)),"ghost_to_shrine"):
				_event("cast_failed",{"skill_id":action.skill_id,"reason":"SHRINE_DESTINATION_UNAVAILABLE"});return
		_event("skill_applied",{"skill_id":action.skill_id,"kind":kind,"effect_id":skill.get("effect_id"),"sound_id":skill.get("sound_id"),"duration":float(skill.get("visual_duration",0.8)),"map_id":state.character.map_id,"x":state.character.x,"y":state.character.y,"hp":state.character.hp,"mp":state.character.mp})

func _monster_move(monster: Dictionary,dx: int,dy: int) -> bool:
	var x: int=int(monster.x)+dx;var y: int=int(monster.y)+dy
	if not valid_position(str(monster.map_id),x,y) or _occupied(str(monster.map_id),x,y,str(monster.id)) or (str(monster.map_id)==str(state.character.map_id) and x==int(state.character.x) and y==int(state.character.y)): return false
	for exit in data.maps[monster.map_id].get("exits",[]):
		if int(exit.x)==x and int(exit.y)==y: return false
	var from: Dictionary={"x":monster.x,"y":monster.y}
	monster.x=x;monster.y=y
	_event("monster_moved",{"target_id":monster.id,"from":from,"x":x,"y":y,"map_id":monster.map_id})
	return true

func _update_monster(monster: Dictionary) -> void:
	if str(monster.map_id)!=str(state.character.map_id): return
	var def: Dictionary=data.monsters[monster.monster_id]
	if not monster.alive:
		if _now()>=float(monster.respawn_at) and not _occupied(str(monster.map_id),int(monster.spawn_x),int(monster.spawn_y),str(monster.id)) and not (int(monster.spawn_x)==int(state.character.x) and int(monster.spawn_y)==int(state.character.y)):
			monster.x=monster.spawn_x;monster.y=monster.spawn_y;monster.hp=int(def.hp);monster.alive=true;monster.aggro=false;monster.generation=int(monster.generation)+1;monster.ai_at=_now()+float(def.get("move_interval",1.0));monster.attack_at=_now()+float(def.get("attack_interval",1.0))
			_event("monster_respawned",{"target_id":monster.id,"monster_id":monster.monster_id,"generation":monster.generation})
		return
	if bool(state.character.dead): return
	var distance: int=_distance(monster,state.character)
	var hostile: bool=bool(monster.aggro) or str(def.get("aggression","retaliate")) in ["hostile","HOSTILE_DOCUMENTED"]
	if hostile and distance<=1 and _now()>=float(monster.attack_at):
		monster.attack_at=_now()+float(def.get("attack_interval",1.0))
		state.pending_actions.append({"kind":"monster_attack","target_id":monster.id,"target_generation":monster.generation,"map_id":monster.map_id,"due":_now()+float(def.get("attack_windup",0.2))})
		_event("monster_attack_started",{"target_id":monster.id,"impact_delay":float(def.get("attack_windup",0.2))})
	if _now()<float(monster.ai_at): return
	monster.ai_at=_now()+maxf(0.2,float(def.get("move_interval",1.0)))
	var low_hp_flee: bool=bool(def.get("low_hp_flee",false)) and int(monster.hp)<int(def.hp)*float(def.get("flee_hp_fraction",0.3))
	var dx: int=0;var dy: int=0
	var home_distance: int=absi(int(monster.x)-int(monster.spawn_x))+absi(int(monster.y)-int(monster.spawn_y))
	if home_distance>int(def.get("leash_range",8)):
		monster.aggro=false
		dx=signi(int(monster.spawn_x)-int(monster.x));dy=signi(int(monster.spawn_y)-int(monster.y))
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
	state=prior.duplicate(true)
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
		for monster in state.monsters.values(): _update_monster(monster)
		# Out of combat, slow native stat recovery is a declared balance rule.
		if not bool(state.character.dead) and _ready("combat_until") and int(floor(_now()/float(_config("regen_interval",4.0))))>int(floor((_now()-STEP)/float(_config("regen_interval",4.0)))):
			state.character.hp=mini(int(state.character.hp_max),int(state.character.hp)+int(_config("regen_hp",1)))
			state.character.mp=mini(int(state.character.mp_max),int(state.character.mp)+int(_config("regen_mp",2)))
		steps+=1
	if seconds>5.0: _event("time_clamped",{"requested_seconds":seconds,"simulated_seconds":5.0})
	state.revision=int(prior.revision)+1
	return _response("OK","TIME_ADVANCED",true)
