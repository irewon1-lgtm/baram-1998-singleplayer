extends RefCounted
## P3 snapshots only. Original P2 synthetic save algorithms remain untouched.
## SHA detects corruption; local owner strings are not online authentication.
const BaseStore = preload("res://storage/save_store.gd")
const GameState = preload("res://state/gameplay_state.gd")
const SCHEMA := "baram.gameplay-save/1"
const ROOT := "user://gameplay-p3/"
const MAX_BYTES := 4 * 1024 * 1024
const MAX_ENTRIES := 4096
const MAX_SAFE_INTEGER := 9007199254740991
const PHASES := ["after_pending_write", "after_pending_verify", "after_backup_write", "after_backup_verify", "after_backup_replace", "before_primary_replace", "after_primary_replace"]
var base = BaseStore.new()
var phase_observer: Callable
var fault_phase := ""

func result(status: String, reason: String = "", revision: int = -1) -> Dictionary:
	return {"status":status,"reason":reason,"revision":revision}

func _int(value: Variant, minimum: int = 0, maximum: int = MAX_SAFE_INTEGER) -> bool:
	return base._integer(value, minimum, maximum)

func _id(value: Variant) -> bool:
	if typeof(value) != TYPE_STRING or value.is_empty() or value.length() > 128: return false
	for c in value:
		if not c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-": return false
	return true

func _plain(value: Variant, depth: int = 0) -> bool:
	if depth > 24: return false
	match typeof(value):
		TYPE_NIL, TYPE_BOOL: return true
		TYPE_STRING: return value.length() <= 16384
		TYPE_INT: return _int(value, -MAX_SAFE_INTEGER, MAX_SAFE_INTEGER)
		TYPE_FLOAT: return is_finite(value) and absf(value) <= MAX_SAFE_INTEGER
		TYPE_DICTIONARY:
			if value.size() > MAX_ENTRIES: return false
			for key in value:
				if typeof(key) != TYPE_STRING or key.length() > 256 or not _plain(value[key],depth+1): return false
			return true
		TYPE_ARRAY:
			if value.size() > MAX_ENTRIES: return false
			for entry in value:
				if not _plain(entry,depth+1): return false
			return true
	return false

func _path(path: String) -> bool:
	if not path.begins_with(ROOT) or path.contains("\\") or path.contains("..") or path.ends_with("/") or path.length() > 512: return false
	return path.simplify_path() == path and not base._path_has_link(path)

func _compat(content: Dictionary) -> Dictionary:
	return content.get("compatibility", {}).duplicate(true)

func _valid_compat(value: Variant) -> bool:
	if not base._keys(value,["schema","rules","idset","map_geometry"]): return false
	for key in value:
		if typeof(value[key])==TYPE_STRING:
			if value[key].is_empty() or value[key].length()>128: return false
		elif not _int(value[key],0,MAX_SAFE_INTEGER): return false
	return true

func _phase(name: String) -> bool:
	if phase_observer.is_valid(): phase_observer.call(name)
	return name == fault_phase

func _encode(document: Dictionary) -> String:
	var output := document.duplicate(true)
	output.sha256 = _canonical(document).sha256_text()
	return _canonical(output)

func _canonical(value: Variant) -> String:
	# Godot's JSON parser can change the last binary digit of a full-precision
	# decimal (observed 21.310000000000166 -> 21.31000000000017). P3 uses a
	# 50ms simulation step; persist fractional timers at 1 microsecond precision.
	# Discrete values remain exact integers. Do not alter the historical P2 store.
	match typeof(value):
		TYPE_DICTIONARY:
			var keys: Array=value.keys()
			keys.sort()
			var fields: PackedStringArray=[]
			for key in keys: fields.append(JSON.stringify(str(key))+":"+_canonical(value[key]))
			return "{"+",".join(fields)+"}"
		TYPE_ARRAY:
			var fields: PackedStringArray=[]
			for item in value: fields.append(_canonical(item))
			return "["+",".join(fields)+"]"
		TYPE_INT: return str(value)
		TYPE_FLOAT:
			if _int(value,-MAX_SAFE_INTEGER,MAX_SAFE_INTEGER): return str(int(value))
			var number:=String.num(value,6)
			if "." in number:
				while number.ends_with("0"): number=number.left(-1)
				if number.ends_with("."): number=number.left(-1)
			return "0" if number=="-0" else number
	return JSON.stringify(value)

func _decode(text: String, owner: String, content: Dictionary) -> Dictionary:
	if text.to_utf8_buffer().size() > MAX_BYTES: return result("SAVE_SIZE_LIMIT")
	var depth := 0
	var quoted := false
	var escaped := false
	for c in text:
		if escaped: escaped=false
		elif quoted and c=="\\": escaped=true
		elif c=='"': quoted=not quoted
		elif not quoted:
			if c in ["{","["]:
				depth+=1
				if depth>24: return result("SAVE_DEPTH_LIMIT")
			elif c in ["}","]"]: depth-=1
	var parser := JSON.new()
	if parser.parse(text) != OK or typeof(parser.data) != TYPE_DICTIONARY: return result("CORRUPT","json")
	var doc: Dictionary = parser.data
	if not base._keys(doc,["schema","owner","revision","profile","compatibility","manifest_sha256","payload","sha256"]): return result("UNSUPPORTED_FORMAT","envelope.shape")
	var digest: Variant = doc.sha256
	doc.erase("sha256")
	if typeof(digest) != TYPE_STRING: return result("CHECKSUM_MISMATCH")
	if _canonical(doc).sha256_text() != digest and base.canonical(doc).sha256_text() != digest: return result("CHECKSUM_MISMATCH")
	if doc.schema != SCHEMA: return result("UNSUPPORTED_FORMAT","schema")
	if doc.owner != owner: return result("OWNER_MISMATCH")
	if not _int(doc.revision) or typeof(doc.payload) != TYPE_DICTIONARY or doc.payload.get("revision") != doc.revision: return result("INVALID_STATE","revision")
	if doc.profile != content.get("profile",""): return result("DEFERRED","profile")
	var compat := _compat(content)
	if not _valid_compat(doc.compatibility) or not _valid_compat(compat): return result("DEFERRED","compatibility_missing")
	for key in ["schema","rules","idset"]:
		if doc.compatibility.get(key) != compat[key]: return result("DEFERRED","compatibility."+key)
	var valid: Dictionary = validate_payload(doc.payload,owner,content)
	if valid.status != "OK": return valid
	return {"status":"OK","reason":"","revision":int(doc.revision),"payload":doc.payload.duplicate(true),"document":doc,"geometry_changed":doc.compatibility.get("map_geometry") != compat.map_geometry,"manifest_changed":doc.manifest_sha256 != content.get("manifest_sha256","")}

func _read_one(path: String, owner: String, content: Dictionary) -> Dictionary:
	if not _path(path): return result("UNSAFE_PATH")
	if not FileAccess.file_exists(path): return result("MISSING")
	var file := FileAccess.open(path,FileAccess.READ)
	if file == null: return result("READ_FAILED")
	if file.get_length() > MAX_BYTES:
		file.close()
		return result("SAVE_SIZE_LIMIT")
	var text := file.get_as_text()
	file.close()
	return _decode(text,owner,content)

func read_game(path: String, owner: String, content: Dictionary) -> Dictionary:
	if not _id(owner): return result("OWNER_MISMATCH")
	var primary := _read_one(path,owner,content)
	primary.source=path
	if primary.status == "OK" or primary.status not in ["MISSING","CORRUPT","CHECKSUM_MISMATCH","INVALID_STATE"]: return primary
	var backup := _read_one(path+".backup",owner,content)
	if backup.status == "OK":
		backup.status="RECOVERED_BACKUP"
		backup.primary_error=primary.status
		backup.source=path+".backup"
		return backup
	primary.backup_error=backup.status
	return primary

func write_game(path: String, payload: Dictionary, owner: String, content: Dictionary) -> Dictionary:
	var valid := validate_payload(payload,owner,content)
	if valid.status != "OK": return valid
	for suffix in ["",".pending",".backup",".backup.pending"]:
		if not _path(path+suffix): return result("UNSAFE_PATH",suffix)
	var compatibility := _compat(content)
	if not _valid_compat(compatibility): return result("INVALID_CONTENT","compatibility")
	var document := {"schema":SCHEMA,"owner":owner,"revision":payload.revision,"profile":content.get("profile",""),"compatibility":compatibility,"manifest_sha256":content.get("manifest_sha256",""),"payload":payload.duplicate(true)}
	var text := _encode(document)
	if text.to_utf8_buffer().size() > MAX_BYTES: return result("SAVE_SIZE_LIMIT")
	var previous := ""
	var previous_revision := -1
	if FileAccess.file_exists(path+".backup"):
		var backup := _read_one(path+".backup",owner,content)
		if backup.status != "OK": return result("EXISTING_SAVE_NOT_WRITABLE","backup."+backup.status)
		previous=FileAccess.get_file_as_string(path+".backup")
		previous_revision=backup.revision
	if FileAccess.file_exists(path):
		var current := _read_one(path,owner,content)
		if current.status == "OK":
			previous=FileAccess.get_file_as_string(path)
			previous_revision=current.revision
		elif current.status in ["CORRUPT","CHECKSUM_MISMATCH","INVALID_STATE"] and not previous.is_empty():
			var broken := FileAccess.get_file_as_bytes(path)
			var hasher := HashingContext.new()
			hasher.start(HashingContext.HASH_SHA256)
			hasher.update(broken)
			var preserved := path+".corrupt-"+hasher.finish().hex_encode()
			if not _path(preserved): return result("UNSAFE_PATH","corrupt_copy")
			if FileAccess.file_exists(preserved):
				if FileAccess.get_file_as_bytes(preserved) != broken: return result("PRESERVATION_CONFLICT")
			elif DirAccess.copy_absolute(path,preserved) != OK: return result("PRESERVATION_FAILED")
		else: return result("EXISTING_SAVE_NOT_WRITABLE",current.status)
	if previous_revision > int(payload.revision): return result("STALE_REVISION","older_than_saved",previous_revision)
	if previous_revision == int(payload.revision):
		var old := _decode(previous,owner,content)
		if old.status != "OK" or _canonical(old.payload) != _canonical(payload): return result("REVISION_CONFLICT")
		if FileAccess.file_exists(path) and _read_one(path,owner,content).status == "OK": return {"status":"SAVED","reason":"IDENTICAL_SNAPSHOT","revision":int(payload.revision),"bytes":text.to_utf8_buffer().size()}
	if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK: return result("WRITE_FAILED","directory")
	if not base._write(path+".pending",text): return result("WRITE_FAILED","pending")
	if _phase("after_pending_write"): return result("INJECTED_FAILURE","after_pending_write")
	if _read_one(path+".pending",owner,content).status != "OK": return result("VERIFY_FAILED","pending")
	if _phase("after_pending_verify"): return result("INJECTED_FAILURE","after_pending_verify")
	if not previous.is_empty():
		if not base._write(path+".backup.pending",previous): return result("WRITE_FAILED","backup.pending")
		if _phase("after_backup_write"): return result("INJECTED_FAILURE","after_backup_write")
		if _read_one(path+".backup.pending",owner,content).status != "OK": return result("VERIFY_FAILED","backup.pending")
		if _phase("after_backup_verify"): return result("INJECTED_FAILURE","after_backup_verify")
		if not _path(path+".backup.pending") or not _path(path+".backup"): return result("UNSAFE_PATH","backup_replace")
		if DirAccess.rename_absolute(path+".backup.pending",path+".backup") != OK: return result("REPLACE_FAILED","backup")
		if _phase("after_backup_replace"): return result("INJECTED_FAILURE","after_backup_replace")
	if _phase("before_primary_replace"): return result("INJECTED_FAILURE","before_primary_replace")
	if not _path(path+".pending") or not _path(path): return result("UNSAFE_PATH","primary_replace")
	if DirAccess.rename_absolute(path+".pending",path) != OK: return result("REPLACE_FAILED","primary")
	if _phase("after_primary_replace"): return result("COMMITTED_ACK_LOST","after_primary_replace",int(payload.revision))
	return {"status":"SAVED","reason":"","revision":int(payload.revision),"bytes":text.to_utf8_buffer().size()}

func validate_payload(payload: Dictionary, owner: String, content: Dictionary) -> Dictionary:
	if not _id(owner) or not _plain(payload): return result("INVALID_STATE","owner_or_json_types")
	var fields := ["schema","profile","character","inventory","equipment","skills","hotkeys","quests","loot","monsters","buffs","cooldowns","revision","rng_state","applied_request_ids","request_watermarks","sim_time","time_accumulator","pending_actions","next_instance_id","next_loot_id","stats","shop_purchases"]
	if not base._keys(payload,fields): return result("INVALID_STATE","payload.shape")
	for key in ["character","equipment","hotkeys","quests","monsters","buffs","cooldowns","request_watermarks","stats","shop_purchases"]:
		if typeof(payload[key]) != TYPE_DICTIONARY: return result("INVALID_STATE",key+".type")
	for key in ["inventory","skills","loot","applied_request_ids","pending_actions"]:
		if typeof(payload[key]) != TYPE_ARRAY: return result("INVALID_STATE",key+".type")
	if not payload.character.has_all(["id","name","owner_id","job","desired_job","level","xp","hp","hp_max","mp","mp_max","money","map_id","x","y","direction","dead","appearance"]): return result("INVALID_STATE","character.shape")
	if typeof(payload.character.appearance) != TYPE_DICTIONARY or typeof(payload.character.dead) != TYPE_BOOL: return result("INVALID_STATE","character.types")
	if not payload.character.appearance.is_empty():
		if not base._keys(payload.character.appearance,["variant"]) or not _int(payload.character.appearance.variant,0,1): return result("INVALID_STATE","appearance.reference")
	if not _id(payload.character.id) or not _id(payload.character.owner_id) or typeof(payload.character.name) != TYPE_STRING: return result("INVALID_STATE","character.identity")
	for key in ["profile","maps","npcs","items","monsters","skills","start","gates","respawn","xp_thresholds"]:
		if not content.has(key): return result("INVALID_CONTENT",key)
	for key in ["maps","npcs","items","monsters","skills","start","gates","respawn"]:
		if typeof(content[key]) != TYPE_DICTIONARY: return result("INVALID_CONTENT",key+".type")
	if typeof(content.xp_thresholds) != TYPE_ARRAY: return result("INVALID_CONTENT","xp_thresholds.type")
	var engine = GameState.new()
	if not engine.configure(content): return result("INVALID_CONTENT",JSON.stringify(engine.errors))
	# Protect the authoritative validator's typed accesses from malformed structures.
	for row in payload.inventory:
		if typeof(row) != TYPE_DICTIONARY or not row.has_all(["instance_id","item_id","quantity","durability"]): return result("INVALID_STATE","inventory.shape")
		if not content.items.has(row.item_id): return result("DEFERRED","inventory.item_reference")
	for row in payload.loot:
		if typeof(row) != TYPE_DICTIONARY or not row.has_all(["loot_id","item_id","quantity","map_id","x","y"]): return result("INVALID_STATE","loot.shape")
		if not _int(row.x,0,65535) or not _int(row.y,0,65535): return result("INVALID_STATE","loot.coordinate_type")
		if not engine.valid_position(str(row.map_id),int(row.x),int(row.y)): return result("DEFERRED","loot.coordinate_mapping")
		if not content.items.has(row.item_id): return result("DEFERRED","loot.item_reference")
	for id in payload.monsters:
		if typeof(payload.monsters[id]) != TYPE_DICTIONARY: return result("INVALID_STATE","monster.type")
		var monster: Dictionary=payload.monsters[id]
		if not monster.has_all(["map_id","x","y","spawn_x","spawn_y"]): return result("INVALID_STATE","monster.position_shape")
		if not content.monsters.has(monster.get("monster_id","")): return result("DEFERRED","monster.definition_reference")
		for key in ["x","y","spawn_x","spawn_y"]:
			if not _int(monster[key],0,65535): return result("INVALID_STATE","monster.coordinate_type")
		if not engine.valid_position(str(monster.map_id),int(monster.x),int(monster.y)) or not engine.valid_position(str(monster.map_id),int(monster.spawn_x),int(monster.spawn_y)): return result("DEFERRED","monster.coordinate_mapping")
	for row in payload.pending_actions:
		if typeof(row) != TYPE_DICTIONARY: return result("INVALID_STATE","action.type")
		if not content.maps.has(row.get("map_id","")): return result("DEFERRED","action.map_reference")
	for id in payload.skills:
		if not content.skills.has(id): return result("DEFERRED","skills.reference")
	var authoritative: Dictionary=engine.validate_payload(payload,owner)
	if authoritative.status != "OK": return result(authoritative.status,authoritative.get("reason",""))
	var instances := {}
	for row in payload.inventory:
		if not _id(row.instance_id) or not _id(row.item_id): return result("INVALID_STATE","inventory.id")
		instances[row.instance_id]=true
	for slot in payload.equipment:
		var id: String=str(payload.equipment[slot])
		for row in payload.inventory:
			if row.instance_id==id and int(row.quantity)!=1: return result("INVALID_STATE","equipment.quantity")
	for row in payload.loot:
		if not _id(row.loot_id) or instances.has(row.loot_id): return result("INVALID_STATE","loot.id_collision")
		if not _int(row.x,0,65535) or not _int(row.y,0,65535): return result("INVALID_STATE","loot.coordinate_type")
		instances[row.loot_id]=true
	for key in ["next_instance_id","next_loot_id"]:
		if not _int(payload[key],1,1000000000): return result("INVALID_STATE",key)
	for key in payload.hotkeys:
		if str(key) not in ["1","2","3","4","5","6","7","8","9"] or payload.hotkeys[key] not in payload.skills: return result("INVALID_STATE","hotkey.reference")
	for id in payload.buffs:
		var buff: Variant=payload.buffs[id]
		if not content.skills.has(id) or id not in payload.skills or typeof(buff)!=TYPE_DICTIONARY or not buff.has_all(["expires_at","attack","defense","attack_multiplier"]): return result("INVALID_STATE","buff.reference")
		if not _timer(buff.expires_at) or not _int(buff.attack,-1000000000,1000000000) or not _int(buff.defense,-1000000000,1000000000) or typeof(buff.attack_multiplier) not in [TYPE_INT,TYPE_FLOAT] or not is_finite(float(buff.attack_multiplier)) or float(buff.attack_multiplier)<0 or float(buff.attack_multiplier)>1000: return result("INVALID_STATE","buff.range")
	for id in payload.monsters:
		var monster: Dictionary=payload.monsters[id]
		if monster.get("id")!=id or not _id(id) or not _int(monster.generation,0,1000000000) or typeof(monster.alive)!=TYPE_BOOL or typeof(monster.aggro)!=TYPE_BOOL: return result("INVALID_STATE","monster.identity")
		for key in ["x","y","spawn_x","spawn_y"]:
			if not _int(monster[key],0,65535): return result("INVALID_STATE","monster.coordinate_type")
		if not engine.valid_position(monster.map_id,int(monster.spawn_x),int(monster.spawn_y)): return result("DEFERRED","monster.spawn_position")
		for key in ["respawn_at","ai_at","attack_at","respawn_seconds"]:
			if not monster.has(key) or not _timer(monster[key]): return result("INVALID_STATE","monster.timer")
	for action in payload.pending_actions:
		if not _timer(action.due): return result("INVALID_STATE","action.due")
		if not str(action.get("target_id","")).is_empty() and not payload.monsters.has(action.target_id): return result("INVALID_STATE","action.target")
		if action.kind=="skill" and action.skill_id not in payload.skills: return result("INVALID_STATE","action.unlearned_skill")
		if not _int(action.get("target_generation",0),0,1000000000): return result("INVALID_STATE","action.generation")
		if typeof(action.get("destination",{}))!=TYPE_DICTIONARY: return result("INVALID_STATE","action.destination_type")
		var destination: Dictionary=action.get("destination",{})
		if not destination.is_empty():
			if not destination.has_all(["map_id","x","y"]) or not _int(destination.x,0,65535) or not _int(destination.y,0,65535) or not engine.valid_position(destination.map_id,int(destination.x),int(destination.y)): return result("DEFERRED","action.destination")
	for key in payload.cooldowns:
		if not _timer(payload.cooldowns[key]): return result("INVALID_STATE","cooldown.range")
	for key in payload.stats:
		if not _int(payload.stats[key],0,1000000000): return result("INVALID_STATE","stats.range")
	for key in payload.shop_purchases:
		var parts: PackedStringArray=str(key).split("/")
		if parts.size()!=2 or not content.npcs.has(parts[0]) or not content.items.has(parts[1]) or not _int(payload.shop_purchases[key],0,1000000000): return result("INVALID_STATE","shop_purchase.reference")
	var requests := {}
	for id in payload.applied_request_ids:
		if not _id(id) or requests.has(id): return result("INVALID_STATE","request.duplicate_or_id")
		requests[id]=true
	for stream in payload.request_watermarks:
		if not _id(stream) or not _int(payload.request_watermarks[stream],0,MAX_SAFE_INTEGER): return result("INVALID_STATE","request.watermark")
	return result("OK")

func _timer(value: Variant) -> bool:
	return typeof(value) in [TYPE_INT,TYPE_FLOAT] and is_finite(float(value)) and float(value)>=0 and float(value)<=1000000000
