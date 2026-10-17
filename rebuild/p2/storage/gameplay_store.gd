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
# Reuse only a fully configured, privately owned definition snapshot. Comparing
# the complete value (rather than manifest/object identity/a short hash) catches
# in-place nested changes to a caller's mutable Dictionary. No caller receives
# this snapshot; the authoritative validator only reads it.
var _validation_engine: RefCounted
var validation_content_sha256 := ""
var content_configurations := 0
const DECODE_CACHE_LIMIT := 4
var _decoded_cache: Array = []
# Same verified bytes may recur as primary/backup/pending. Cached payloads are
# never returned by reference, and files are still read before cache lookup.
var last_timings: Dictionary = {}
var _writing := false
# Encoding/plain-type caches are pure value caches. Record-local semantic
# predicates additionally require the identical private definition engine;
# authoritative whole-payload validation is never skipped.
# Each record owns a deep snapshot. Native full Dictionary equality detects
# changes even when a caller reuses/mutates the same source Dictionary.
const MONSTER_RECORD_CACHE_LIMIT := 1024
var _monster_record_cache: Dictionary = {}
var _id_value_cache: Dictionary = {}

func _cache_monster_record(id: String, record: Dictionary) -> Dictionary:
	var cached: Dictionary = _monster_record_cache.get(id,{})
	if not cached.is_empty() and cached.snapshot == record: return cached
	if not _monster_record_cache.has(id) and _monster_record_cache.size() >= MONSTER_RECORD_CACHE_LIMIT:
		_monster_record_cache.erase(_monster_record_cache.keys()[0])
	cached = {"snapshot":record.duplicate(true),"plain":false,"canonical":""}
	_monster_record_cache[id] = cached
	return cached

func _plain_game_payload(payload: Dictionary) -> bool:
	# Monster values always occur at depth two of a gameplay payload. Reuse
	# only that exact bounded-JSON check. Typed value matching runs every save;
	# local semantics are memoized only for an unchanged record/generation,
	# while GameState.validate_payload still checks the whole payload each time.
	if payload.size() > MAX_ENTRIES: return false
	for key in payload:
		if typeof(key) != TYPE_STRING or key.length() > 256: return false
		if key == "monsters" and typeof(payload[key]) == TYPE_DICTIONARY and payload[key].size() <= MONSTER_RECORD_CACHE_LIMIT:
			for id in payload[key]:
				if typeof(id) != TYPE_STRING or id.length() > 256: return false
				var record: Variant = payload[key][id]
				if typeof(record) != TYPE_DICTIONARY:
					if not _plain(record,2): return false
					continue
				var cached: Dictionary = _monster_record_cache.get(id,{})
				if not cached.is_empty() and cached.plain and cached.snapshot == record:
					# Dictionary equality treats String and StringName keys as
					# equivalent. Native typed bytes close that type-only gap;
					# the cached bounded shape makes encoding this match safe.
					var typed: PackedByteArray=var_to_bytes(record)
					if cached.get("plain_bytes",PackedByteArray()) == typed: continue
				# Reject unbounded/deep/object input before making any deep copy
				# or typed-byte encoding of a new/changed untrusted record.
				if not _plain(record,2): return false
				cached = _cache_monster_record(id,record)
				cached.plain = true
				cached["plain_bytes"] = var_to_bytes(record)
		elif not _plain(payload[key],1): return false
	return true

func _canonical_monsters(monsters: Dictionary, validated_records: bool = false) -> String:
	var ids: Array = monsters.keys()
	ids.sort()
	var fields: PackedStringArray=[]
	for id in ids:
		var record: Variant = monsters[id]
		var encoded: String
		if typeof(id)==TYPE_STRING and typeof(record)==TYPE_DICTIONARY:
			# Only write_game's synchronous post-validation encode can use the
			# already checked records. Generic encoding and external disk decode
			# still compare the complete current value with the private snapshot.
			var cached: Dictionary = _monster_record_cache.get(id,{}) if validated_records else {}
			if cached.is_empty(): cached = _cache_monster_record(id,record)
			if cached.canonical.is_empty(): cached.canonical = _canonical(record)
			encoded = cached.canonical
			if not cached.has("member_key"): cached["member_key"]=JSON.stringify(id)+":"
			fields.append(cached.member_key+encoded)
			continue
		else: encoded = _canonical(record)
		fields.append(JSON.stringify(str(id))+":"+encoded)
	return "{"+",".join(fields)+"}"

func _canonical_save_document(document: Dictionary, validated_monsters: bool = false) -> String:
	# Generic callers (including sequential-sync metadata) retain _canonical.
	var payload: Variant = document.get("payload")
	if typeof(payload) != TYPE_DICTIONARY or payload.get("schema","") != "baram.p3.gameplay-payload/1" or typeof(payload.get("monsters")) != TYPE_DICTIONARY:
		return _canonical(document)
	var payload_keys: Array = payload.keys()
	payload_keys.sort()
	var payload_fields: PackedStringArray=[]
	for key in payload_keys:
		var encoded := _canonical_monsters(payload[key],validated_monsters) if key=="monsters" else _canonical(payload[key])
		payload_fields.append(JSON.stringify(str(key))+":"+encoded)
	var encoded_payload := "{"+",".join(payload_fields)+"}"
	var keys: Array = document.keys()
	keys.sort()
	var fields: PackedStringArray=[]
	for key in keys:
		fields.append(JSON.stringify(str(key))+":"+(encoded_payload if key=="payload" else _canonical(document[key])))
	return "{"+",".join(fields)+"}"

func _content_engine(content: Dictionary) -> RefCounted:
	if _validation_engine != null and content == _validation_engine.data:
		return _validation_engine
	_decoded_cache.clear()
	_validation_engine = null
	validation_content_sha256 = ""
	var engine = GameState.new()
	if not engine.configure(content): return null
	_validation_engine = engine
	validation_content_sha256 = var_to_bytes(engine.data).hex_encode().sha256_text()
	content_configurations += 1
	return engine

func _freeze_definitions(value: Variant) -> void:
	match typeof(value):
		TYPE_DICTIONARY:
			for child in value.values(): _freeze_definitions(child)
			value.make_read_only()
		TYPE_ARRAY:
			for child in value: _freeze_definitions(child)
			value.make_read_only()

func prepare_content(content: Dictionary) -> Dictionary:
	# Optional fast path for a loaded generation: return a private, recursively
	# read-only snapshot, never freeze the caller's mutable content. Supplying
	# this same value to read/write avoids repeated full-generation equality.
	# Reloaded/changed generations must call prepare_content again. The generic
	# mutable-content API remains supported and checks the complete value.
	for key in ["profile","maps","npcs","items","monsters","skills","start","gates","respawn","xp_thresholds"]:
		if not content.has(key): return {}
	for key in ["maps","npcs","items","monsters","skills","start","gates","respawn"]:
		if typeof(content[key]) != TYPE_DICTIONARY: return {}
	if typeof(content.xp_thresholds) != TYPE_ARRAY: return {}
	var engine := _content_engine(content)
	if engine == null: return {}
	_freeze_definitions(engine.data)
	# Prepare the generation's initial monster serialization during explicit
	# content loading, rather than make the first confirmed create/save pay
	# the one-time 752-record cache fill in its input/render frame.
	if _monster_record_cache.is_empty():
		var prior: Dictionary=engine.state
		engine.state={"monsters":{}}
		engine._spawn_all()
		for id in engine.state.monsters:
			var record: Dictionary=engine.state.monsters[id]
			var cached:=_cache_monster_record(str(id),record)
			_id(str(id))
			cached.plain=_plain(record,2)
			cached["plain_bytes"]=var_to_bytes(record)
			cached.canonical=_canonical(record)
		engine.state=prior
	return engine.data

func _verified_cached_decode(text: String, owner: String, content: Dictionary, isolate: bool = true) -> Dictionary:
	if _validation_engine == null or content != _validation_engine.data: return {}
	for entry in _decoded_cache:
		if entry.owner == owner and entry.text == text:
			if entry.decoded.is_empty():
				# Written bytes already passed full candidate validation and exact
				# atomic read-back. Parse only when a caller actually needs a full
				# payload, preserving disk timer precision and isolated read results.
				var document: Dictionary = JSON.parse_string(text)
				document.erase("sha256")
				entry.decoded = {"status":"OK","reason":"","revision":int(document.revision),"payload":document.payload.duplicate(true),"document":document,"geometry_changed":false,"manifest_changed":false,"migration_required":false,"added_spawns":[]}
			return entry.decoded.duplicate(isolate)
	return {}

func _decoded_metadata(decoded: Dictionary) -> Dictionary:
	# Only successful private decodes reach this helper. Migration approval is
	# preserved; metadata alone must never suppress source-archive handling.
	return {"status":"OK","reason":decoded.get("reason",""),"revision":decoded.revision,"migration_required":decoded.get("migration_required",false)}

func _verified_cached_metadata(text: String, owner: String, content: Dictionary) -> Dictionary:
	if _validation_engine == null or content != _validation_engine.data: return {}
	for entry in _decoded_cache:
		if entry.owner == owner and entry.text == text:
			if entry.has("written_revision"):
				return {"status":"OK","revision":entry.written_revision,"migration_required":false}
			if entry.decoded.get("status") == "OK": return _decoded_metadata(entry.decoded)
	return {}

func _remember_decode(text: String, owner: String, decoded: Dictionary, owned: bool = false) -> void:
	if decoded.status != "OK": return
	_decoded_cache.push_front({"text":text,"owner":owner,"decoded":decoded if owned else decoded.duplicate(true)})
	if _decoded_cache.size() > DECODE_CACHE_LIMIT: _decoded_cache.pop_back()

func _verify_written(path: String, expected: String) -> bool:
	# These bytes encode an already validated candidate / verified old document.
	# Exact read-back equality proves the full intended envelope was written;
	# unknown external bytes still take _decode's full checksum/semantic path.
	if not _path(path): return false
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null: return false
	if file.get_length() > MAX_BYTES:
		file.close()
		return false
	var actual := file.get_buffer(file.get_length())
	file.close()
	return actual == expected.to_utf8_buffer()

func _timing(key: String, started: int) -> void:
	last_timings[key] = float(Time.get_ticks_usec() - started) / 1000.0
const MIGRATION_PHASES := ["after_migration_source_preserved", "after_migration_backup_preserved"]

func result(status: String, reason: String = "", revision: int = -1) -> Dictionary:
	return {"status":status,"reason":reason,"revision":revision}

func _int(value: Variant, minimum: int = 0, maximum: int = MAX_SAFE_INTEGER) -> bool:
	return base._integer(value, minimum, maximum)

func _id(value: Variant) -> bool:
	if typeof(value) != TYPE_STRING or value.is_empty() or value.length() > 128: return false
	# This is a pure predicate on an immutable String value, independent of
	# game/content state. Repeated 752 stable-ID character scans add no safety.
	if _id_value_cache.has(value): return bool(_id_value_cache[value])
	var valid := true
	for c in value:
		if not c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-":
			valid = false
			break
	if _id_value_cache.size() >= MAX_ENTRIES: _id_value_cache.erase(_id_value_cache.keys()[0])
	_id_value_cache[value] = valid
	return valid

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

func _migration_contract(document: Dictionary, content: Dictionary) -> Dictionary:
	# An ID set/rules change is never made compatible by a checksum alone. The
	# new content must explicitly pin the complete shipped source generation.
	var accepted: Variant=content.get("accepted_compatibility",[])
	if typeof(accepted)!=TYPE_ARRAY or accepted.size()>128: return {}
	for row in accepted:
		if typeof(row)!=TYPE_DICTIONARY or not row.has_all(["profile","compatibility","manifest_sha256"]): continue
		if row.size()!=3 and not (row.size()==4 and row.has("map_transforms")): continue
		if not _valid_compat(row.compatibility): continue
		if row.profile==document.profile and row.manifest_sha256==document.manifest_sha256 and _canonical(row.compatibility)==_canonical(document.compatibility):
			return row.duplicate(true)
	return {}

func _valid_cell_transform(transform: Variant) -> bool:
	if typeof(transform) != TYPE_DICTIONARY or not transform.has_all(["to_map_id","dx","dy"]): return false
	if transform.size() != 3 and not (transform.size() == 4 and transform.has("cell_mappings")): return false
	if not _id(transform.to_map_id) or not _int(transform.dx,-65535,65535) or not _int(transform.dy,-65535,65535): return false
	var cells: Variant = transform.get("cell_mappings",{})
	if typeof(cells) != TYPE_DICTIONARY or cells.size() > 65536: return false
	for key in cells:
		if typeof(key) != TYPE_STRING or key.length() > 11: return false
		var parts: PackedStringArray = key.split(",")
		if parts.size() != 2: return false
		for part in parts:
			if not part.is_valid_int() or str(int(part)) != part or not _int(int(part),0,65535): return false
		var target: Variant = cells[key]
		if not base._keys(target,["x","y"]) or not _int(target.x,0,65535) or not _int(target.y,0,65535): return false
	return true

func _transform_position(position: Dictionary, transforms: Dictionary, x_key: String="x", y_key: String="y") -> bool:
	if not position.has_all(["map_id",x_key,y_key]): return false
	if not transforms.has(str(position.map_id)): return true
	var transform: Variant=transforms[str(position.map_id)]
	# _migrate_payload checks every contract row once, including unused rows.
	# Here only the matching coordinate is inspected; large explicit cell
	# tables must not be rescanned for every saved monster/loot instance.
	if typeof(transform) != TYPE_DICTIONARY or not transform.has_all(["to_map_id","dx","dy"]): return false
	if not _int(position[x_key],0,65535) or not _int(position[y_key],0,65535): return false
	var cell := str(int(position[x_key]))+","+str(int(position[y_key]))
	var cells: Dictionary=transform.get("cell_mappings",{})
	if cells.has(cell):
		# Explicit coordinates are final destination cells. Unlisted cells keep
		# the existing uniform-offset behavior; no nearest-cell guess at load.
		position[x_key]=int(cells[cell].x)
		position[y_key]=int(cells[cell].y)
	else:
		position[x_key]=int(position[x_key])+int(transform.dx)
		position[y_key]=int(position[y_key])+int(transform.dy)
	position.map_id=transform.to_map_id
	return true

func _migrate_payload(payload: Dictionary, contract: Dictionary, content: Dictionary) -> Dictionary:
	var candidate: Dictionary=payload.duplicate(true)
	var transforms: Variant=contract.get("map_transforms",{})
	if typeof(transforms)!=TYPE_DICTIONARY or transforms.size() > 4096: return result("DEFERRED","migration.map_transforms")
	for map_id in transforms:
		if not _id(map_id) or not _valid_cell_transform(transforms[map_id]): return result("DEFERRED","migration.transform_contract")
		if not content.maps.has(str(transforms[map_id].to_map_id)): return result("DEFERRED","migration.transform_target_map")
	if not transforms.is_empty():
		if typeof(candidate.get("character"))!=TYPE_DICTIONARY or not _transform_position(candidate.character,transforms): return result("DEFERRED","migration.character_position")
		if typeof(candidate.get("loot"))!=TYPE_ARRAY or typeof(candidate.get("monsters"))!=TYPE_DICTIONARY or typeof(candidate.get("pending_actions"))!=TYPE_ARRAY: return result("INVALID_STATE","migration.payload_shape")
		for loot in candidate.loot:
			if typeof(loot)!=TYPE_DICTIONARY or not _transform_position(loot,transforms): return result("DEFERRED","migration.loot_position")
		for monster in candidate.monsters.values():
			if typeof(monster)!=TYPE_DICTIONARY: return result("INVALID_STATE","migration.monster_shape")
			# Current and home cells share the old map: transform both before
			# replacing map_id, rather than accidentally applying offsets twice.
			var home: Dictionary={"map_id":monster.get("map_id"),"x":monster.get("spawn_x"),"y":monster.get("spawn_y")}
			if not _transform_position(home,transforms) or not _transform_position(monster,transforms): return result("DEFERRED","migration.monster_position")
			monster.spawn_x=home.x; monster.spawn_y=home.y
		if candidate.has("summons"):
			if typeof(candidate.summons)!=TYPE_ARRAY: return result("INVALID_STATE","migration.summons_type")
			for summon in candidate.summons:
				if typeof(summon)!=TYPE_DICTIONARY or not _transform_position(summon,transforms): return result("DEFERRED","migration.summon_position")
		for action in candidate.pending_actions:
			if typeof(action)!=TYPE_DICTIONARY: return result("INVALID_STATE","migration.action_shape")
			if transforms.has(str(action.get("map_id",""))):
				var point: Dictionary={"map_id":action.map_id,"x":action.get("x",0),"y":action.get("y",0)}
				if not _transform_position(point,transforms): return result("DEFERRED","migration.action_position")
				action.map_id=point.map_id
				if action.has("x"): action.x=point.x
				if action.has("y"): action.y=point.y
			var destination: Variant=action.get("destination",{})
			if typeof(destination)!=TYPE_DICTIONARY: return result("INVALID_STATE","migration.action_destination_type")
			if not destination.is_empty() and not _transform_position(destination,transforms): return result("DEFERRED","migration.action_destination")
	# Existing living/dead monster instances keep their IDs, HP, cells and
	# timers. Only absent content-generation spawns are initialized normally.
	if typeof(candidate.get("monsters"))!=TYPE_DICTIONARY: return result("INVALID_STATE","migration.monsters")
	var engine=GameState.new()
	if not engine.configure(content): return result("INVALID_CONTENT","migration.configure")
	engine.state={"monsters":{}}
	engine._spawn_all()
	var added: Array=[]
	for id in engine.state.monsters:
		if not candidate.monsters.has(id):
			candidate.monsters[id]=engine.state.monsters[id].duplicate(true)
			added.append(id)
	return {"status":"OK","payload":candidate,"added_spawns":added}

func _preserve_migration_source(path: String) -> Dictionary:
	if not _path(path) or not FileAccess.file_exists(path): return result("UNSAFE_PATH","migration_source")
	var bytes:=FileAccess.get_file_as_bytes(path)
	var hasher:=HashingContext.new()
	hasher.start(HashingContext.HASH_SHA256)
	hasher.update(bytes)
	var archive:=path+".pre-migration-"+hasher.finish().hex_encode()
	if not _path(path) or not _path(archive): return result("UNSAFE_PATH","migration_archive")
	if FileAccess.file_exists(archive):
		if FileAccess.get_file_as_bytes(archive)!=bytes: return result("PRESERVATION_CONFLICT","migration_archive")
	elif DirAccess.copy_absolute(path,archive)!=OK: return result("PRESERVATION_FAILED","migration_copy")
	if FileAccess.get_file_as_bytes(archive)!=bytes or FileAccess.get_file_as_bytes(path)!=bytes: return result("PRESERVATION_FAILED","migration_verify")
	return {"status":"OK","archive":archive}

func _phase(name: String) -> bool:
	if phase_observer.is_valid(): phase_observer.call(name)
	return name == fault_phase

func _encode(document: Dictionary, validated_monsters: bool = false) -> String:
	# Canonicalize the payload once. The checksum field is excluded from its
	# own digest; JSON member order does not change the persisted contract.
	var body := _canonical_save_document(document,validated_monsters)
	if document.has("sha256"):
		var output := document.duplicate(true)
		output.sha256 = body.sha256_text()
		return _canonical(output)
	return body.left(-1) + ("," if not document.is_empty() else "") + '"sha256":' + JSON.stringify(body.sha256_text()) + "}"

func _remember_written(text: String, owner: String, content: Dictionary, revision: int) -> void:
	if _validation_engine == null or content != _validation_engine.data: return
	# Only called after full validation, exact read-back and atomic commit.
	# Keep the exact verified bytes, not another pair of full-world deep copies.
	# The next save needs revision/rotation metadata; read_game and same-revision
	# conflict checks still materialize the complete canonical decoded payload.
	_decoded_cache.push_front({"text":text,"owner":owner,"written_revision":revision,"decoded":{}})
	if _decoded_cache.size() > DECODE_CACHE_LIMIT: _decoded_cache.pop_back()

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

func _decode(text: String, owner: String, content: Dictionary, isolate: bool = true) -> Dictionary:
	var cached := _verified_cached_decode(text, owner, content, isolate)
	if not cached.is_empty(): return cached
	var decoded := _decode_uncached(text, owner, content)
	_remember_decode(text, owner, decoded)
	return decoded

func _decode_uncached(text: String, owner: String, content: Dictionary) -> Dictionary:
	var utf8 := text.to_utf8_buffer()
	if utf8.size() > MAX_BYTES: return result("SAVE_SIZE_LIMIT")
	var depth := 0
	var quoted := false
	var escaped := false
	# JSON structure uses ASCII only. Non-ASCII UTF-8 bytes are inert here;
	# preserve the original quote/escape/depth order and let JSON.parse retain
	# responsibility for malformed quotes, negative/final depth and escapes.
	for c in utf8:
		if escaped: escaped=false
		elif quoted and c==92: escaped=true
		elif c==34: quoted=not quoted
		elif not quoted:
			if c==123 or c==91:
				depth+=1
				if depth>24: return result("SAVE_DEPTH_LIMIT")
			elif c==125 or c==93: depth-=1
	utf8.clear()
	var parser := JSON.new()
	if parser.parse(text) != OK or typeof(parser.data) != TYPE_DICTIONARY: return result("CORRUPT","json")
	var doc: Dictionary = parser.data
	if not base._keys(doc,["schema","owner","revision","profile","compatibility","manifest_sha256","payload","sha256"]): return result("UNSUPPORTED_FORMAT","envelope.shape")
	var digest: Variant = doc.sha256
	doc.erase("sha256")
	if typeof(digest) != TYPE_STRING: return result("CHECKSUM_MISMATCH")
	if _canonical_save_document(doc).sha256_text() != digest and base.canonical(doc).sha256_text() != digest: return result("CHECKSUM_MISMATCH")
	if doc.schema != SCHEMA: return result("UNSUPPORTED_FORMAT","schema")
	if doc.owner != owner: return result("OWNER_MISMATCH")
	if not _int(doc.revision) or typeof(doc.payload) != TYPE_DICTIONARY or doc.payload.get("revision") != doc.revision: return result("INVALID_STATE","revision")
	if doc.profile != content.get("profile",""): return result("DEFERRED","profile")
	var compat := _compat(content)
	if not _valid_compat(doc.compatibility) or not _valid_compat(compat): return result("DEFERRED","compatibility_missing")
	var contract: Dictionary={}
	var requires_migration:=false
	for key in ["schema","rules","idset"]:
		if doc.compatibility.get(key) != compat[key]:
			contract=_migration_contract(doc,content)
			if contract.is_empty(): return result("DEFERRED","compatibility."+key)
			requires_migration=true
	var geometry_changed: bool=doc.compatibility.get("map_geometry") != compat.map_geometry
	if geometry_changed:
		# Geometry-only legacy updates remain non-teleporting unless the new
		# generation explicitly pins an exact source and provides transforms.
		# A generation changing walkable cells requires a pinned source contract;
		# unknown manifests cannot bypass it through the old geometry-only path.
		if contract.is_empty(): contract=_migration_contract(doc,content)
		if bool(content.get("require_geometry_migration_contract",false)) and contract.is_empty(): return result("DEFERRED","compatibility.map_geometry_contract")
		if not contract.is_empty() and (contract.has("map_transforms") or bool(content.get("require_geometry_migration_contract",false))): requires_migration=true
	var candidate: Dictionary=doc.payload.duplicate(true)
	var added_spawns: Array=[]
	if requires_migration:
		var migrated:=_migrate_payload(candidate,contract,content)
		if migrated.status!="OK": return migrated
		candidate=migrated.payload
		added_spawns=migrated.added_spawns
	var valid: Dictionary = validate_payload(candidate,owner,content)
	if valid.status != "OK": return valid
	return {"status":"OK","reason":"MIGRATION_AVAILABLE" if requires_migration else "","revision":int(doc.revision),"payload":candidate,"document":doc,"geometry_changed":geometry_changed,"manifest_changed":doc.manifest_sha256 != content.get("manifest_sha256",""),"migration_required":requires_migration or geometry_changed,"added_spawns":added_spawns}

func _read_one(path: String, owner: String, content: Dictionary, isolate: bool = true, metadata_only: bool = false) -> Dictionary:
	if not _path(path): return result("UNSAFE_PATH")
	if not FileAccess.file_exists(path): return result("MISSING")
	var file := FileAccess.open(path,FileAccess.READ)
	if file == null: return result("READ_FAILED")
	if file.get_length() > MAX_BYTES:
		file.close()
		return result("SAVE_SIZE_LIMIT")
	var bytes := file.get_buffer(file.get_length())
	file.close()
	var text := bytes.get_string_from_utf8()
	if bytes != text.to_utf8_buffer(): return result("CORRUPT","utf8")
	if metadata_only:
		var metadata := _verified_cached_metadata(text,owner,content)
		if not metadata.is_empty(): return metadata
		# Writer-only cold path: all unknown-byte size/depth/JSON/checksum/
		# owner/content/migration/semantic checks still execute. The parsed
		# result has no external owner, so transfer it to the private cache
		# rather than deep-copying a full world for an unused caller payload.
		var decoded := _decode_uncached(text,owner,content)
		if decoded.status != "OK": return decoded
		_remember_decode(text,owner,decoded,true)
		return _decoded_metadata(decoded)
	return _decode(text,owner,content,isolate)

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
	# Main-thread synchronous API: reject a reentrant callback save rather than
	# let an older outer transaction replace a newer nested revision.
	if _writing: return result("BUSY","save_in_progress")
	_writing = true
	last_timings = {}
	var started := Time.get_ticks_usec()
	var saved := _write_game(path, payload, owner, content)
	_timing("total_ms", started)
	_writing = false
	return saved

func _write_game(path: String, payload: Dictionary, owner: String, content: Dictionary) -> Dictionary:
	var started := Time.get_ticks_usec()
	var valid := validate_payload(payload,owner,content)
	_timing("validation_ms", started)
	if valid.status != "OK": return valid
	# Pin the privately owned generation for this synchronous transaction. An
	# observer/caller mutating its original definitions cannot change the save.
	content = _validation_engine.data
	for suffix in ["",".pending",".backup",".backup.pending"]:
		if not _path(path+suffix): return result("UNSAFE_PATH",suffix)
	var compatibility := _compat(content)
	if not _valid_compat(compatibility): return result("INVALID_CONTENT","compatibility")
	started = Time.get_ticks_usec()
	# Encoding is synchronous and read-only, before any observer callback. Its
	# resulting immutable text already pins the complete candidate; cloning all
	# 752 records immediately before serializing them adds no isolation.
	var document := {"schema":SCHEMA,"owner":owner,"revision":payload.revision,"profile":content.get("profile",""),"compatibility":compatibility,"manifest_sha256":content.get("manifest_sha256",""),"payload":payload}
	var text := _encode(document,true)
	_timing("encoding_ms", started)
	started = Time.get_ticks_usec()
	if text.to_utf8_buffer().size() > MAX_BYTES: return result("SAVE_SIZE_LIMIT")
	var previous := ""
	var previous_revision := -1
	var previous_decoded: Dictionary = {}
	var primary_valid := false
	var migration_sources: Array[String]=[]
	var primary_requires_migration:=false
	if FileAccess.file_exists(path+".backup"):
		var backup := _read_one(path+".backup",owner,content,false,true)
		if backup.status != "OK": return result("EXISTING_SAVE_NOT_WRITABLE","backup."+backup.status)
		if backup.get("migration_required",false): migration_sources.append(path+".backup")
		previous=FileAccess.get_file_as_string(path+".backup")
		previous_revision=backup.revision
		previous_decoded=backup
	if FileAccess.file_exists(path):
		var current := _read_one(path,owner,content,false,true)
		if current.status == "OK":
			primary_valid=true
			primary_requires_migration=bool(current.get("migration_required",false))
			if primary_requires_migration: migration_sources.append(path)
			previous=FileAccess.get_file_as_string(path)
			previous_revision=current.revision
			previous_decoded=current
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
	_timing("existing_read_ms", started)
	if previous_revision > int(payload.revision): return result("STALE_REVISION","older_than_saved",previous_revision)
	if previous_revision == int(payload.revision):
		var old := previous_decoded
		if not old.has("payload"): old = _decode(previous,owner,content,false)
		if old.status != "OK" or _canonical(old.payload) != _canonical(payload): return result("REVISION_CONFLICT")
		if primary_valid and not primary_requires_migration: return {"status":"SAVED","reason":"IDENTICAL_SNAPSHOT","revision":int(payload.revision),"bytes":text.to_utf8_buffer().size()}
	if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK: return result("WRITE_FAILED","directory")
	var preserved_migration_sources: Array=[]
	# Preserve source bytes before even writing the migrated candidate. Backups
	# may later rotate, but these content-addressed archives are never rotated.
	for source in migration_sources:
		var preserved:=_preserve_migration_source(source)
		if preserved.status!="OK": return preserved
		preserved_migration_sources.append(preserved.archive)
		var phase_name:="after_migration_source_preserved" if source==path else "after_migration_backup_preserved"
		if _phase(phase_name): return result("INJECTED_FAILURE",phase_name)
	started = Time.get_ticks_usec()
	if not base._write(path+".pending",text): return result("WRITE_FAILED","pending")
	if _phase("after_pending_write"): return result("INJECTED_FAILURE","after_pending_write")
	if not _verify_written(path+".pending",text): return result("VERIFY_FAILED","pending")
	_timing("pending_write_verify_ms", started)
	if _phase("after_pending_verify"): return result("INJECTED_FAILURE","after_pending_verify")
	if not previous.is_empty():
		started = Time.get_ticks_usec()
		if not base._write(path+".backup.pending",previous): return result("WRITE_FAILED","backup.pending")
		if _phase("after_backup_write"): return result("INJECTED_FAILURE","after_backup_write")
		if not _verify_written(path+".backup.pending",previous): return result("VERIFY_FAILED","backup.pending")
		_timing("backup_write_verify_ms", started)
		if _phase("after_backup_verify"): return result("INJECTED_FAILURE","after_backup_verify")
		if not _path(path+".backup.pending") or not _path(path+".backup"): return result("UNSAFE_PATH","backup_replace")
		if DirAccess.rename_absolute(path+".backup.pending",path+".backup") != OK: return result("REPLACE_FAILED","backup")
		if _phase("after_backup_replace"): return result("INJECTED_FAILURE","after_backup_replace")
	started = Time.get_ticks_usec()
	if _phase("before_primary_replace"): return result("INJECTED_FAILURE","before_primary_replace")
	if not _path(path+".pending") or not _path(path): return result("UNSAFE_PATH","primary_replace")
	if DirAccess.rename_absolute(path+".pending",path) != OK: return result("REPLACE_FAILED","primary")
	_timing("primary_replace_ms", started)
	if _phase("after_primary_replace"): return result("COMMITTED_ACK_LOST","after_primary_replace",int(document.revision))
	started = Time.get_ticks_usec()
	_remember_written(text, owner, content, int(document.revision))
	_timing("remember_verified_ms", started)
	return {"status":"SAVED","reason":"MIGRATED" if not preserved_migration_sources.is_empty() else "","revision":int(document.revision),"bytes":text.to_utf8_buffer().size(),"preserved_migration_sources":preserved_migration_sources}

func validate_payload(payload: Dictionary, owner: String, content: Dictionary) -> Dictionary:
	var section_started := Time.get_ticks_usec()
	if not _id(owner) or not _plain_game_payload(payload): return result("INVALID_STATE","owner_or_json_types")
	_timing("state_plain_ms", section_started)
	var fields := ["schema","profile","character","inventory","equipment","skills","hotkeys","quests","loot","monsters","buffs","cooldowns","revision","rng_state","applied_request_ids","request_watermarks","sim_time","time_accumulator","pending_actions","next_instance_id","next_loot_id","stats","shop_purchases"]
	if not payload.has_all(fields): return result("INVALID_STATE","payload.shape")
	for key in payload:
		if key not in fields and key not in ["summons","bank_inventory"]: return result("INVALID_STATE","payload.unknown_field")
	if payload.has("summons") and typeof(payload.summons)!=TYPE_ARRAY: return result("INVALID_STATE","summons.type")
	if payload.has("bank_inventory") and typeof(payload.bank_inventory)!=TYPE_ARRAY: return result("INVALID_STATE","bank_inventory.type")
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
	section_started = Time.get_ticks_usec()
	var engine = _content_engine(content)
	_timing("content_check_ms", section_started)
	if engine == null: return result("INVALID_CONTENT","definition_validation")
	# Protect the authoritative validator's typed accesses from malformed structures.
	for row in payload.inventory+payload.get("bank_inventory",[]):
		if typeof(row) != TYPE_DICTIONARY or not row.has_all(["instance_id","item_id","quantity","durability"]): return result("INVALID_STATE","inventory.shape")
		if not content.items.has(row.item_id): return result("DEFERRED","inventory.item_reference")
	for row in payload.loot:
		if typeof(row) != TYPE_DICTIONARY or not row.has_all(["loot_id","item_id","quantity","map_id","x","y"]): return result("INVALID_STATE","loot.shape")
		if not _int(row.x,0,65535) or not _int(row.y,0,65535): return result("INVALID_STATE","loot.coordinate_type")
		if not engine.valid_position(str(row.map_id),int(row.x),int(row.y)): return result("DEFERRED","loot.coordinate_mapping")
		if not content.items.has(row.item_id): return result("DEFERRED","loot.item_reference")
	var unchecked_monsters: Array=[]
	for id in payload.monsters:
		if typeof(payload.monsters[id]) != TYPE_DICTIONARY: return result("INVALID_STATE","monster.type")
		var monster: Dictionary=payload.monsters[id]
		# _plain_game_payload already checked the complete current typed value
		# against this private snapshot, or fully checked a changed/new record.
		# Reuse only these record-local store predicates for the same immutable
		# definitions. The authoritative full payload validator still runs below.
		var cached: Dictionary=_monster_record_cache.get(id,{})
		if cached.get("semantic_generation",-1) == content_configurations: continue
		unchecked_monsters.append(id)
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
	section_started = Time.get_ticks_usec()
	var authoritative: Dictionary=engine.validate_payload(payload,owner)
	_timing("authoritative_state_ms", section_started)
	if authoritative.status != "OK": return result(authoritative.status,authoritative.get("reason",""))
	var instances := {}
	for row in payload.inventory+payload.get("bank_inventory",[]):
		if not _id(row.instance_id) or not _id(row.item_id): return result("INVALID_STATE","inventory.id")
		if instances.has(row.instance_id): return result("INVALID_STATE","inventory_or_bank.duplicate_id")
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
	for id in unchecked_monsters:
		var monster: Dictionary=payload.monsters[id]
		if monster.get("id")!=id or not _id(id) or not _int(monster.generation,0,1000000000) or typeof(monster.alive)!=TYPE_BOOL or typeof(monster.aggro)!=TYPE_BOOL: return result("INVALID_STATE","monster.identity")
		# Coordinate types and current/home walkability were already checked
		# above before the read-only authoritative validator. Repeating the
		# same four range checks and home lookup cannot detect a new mutation.
		for key in ["respawn_at","ai_at","attack_at","respawn_seconds"]:
			if not monster.has(key) or not _timer(monster[key]): return result("INVALID_STATE","monster.timer")
		var cached: Dictionary=_monster_record_cache.get(id,{})
		# A monotonic generation number keeps this cache from retaining old
		# full definition engines across reloads when different records change.
		if not cached.is_empty(): cached["semantic_generation"]=content_configurations
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
