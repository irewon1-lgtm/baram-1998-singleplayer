extends RefCounted
## P2 synthetic-fixture storage contract. Not an original Baram save format.
## Pattern provenance: OLD-SAVE-STORE (see PROVENANCE.json); rewritten, not copied.
## SHA-256 detects accidental damage; it does not authenticate an account.

const SCHEMA_ID = "baram.p2.synthetic-save"
const SCHEMA_VERSION = 1
const MAX_BYTES = 1024 * 1024
const MAX_ENTRIES = 1024
const MAX_DEPTH = 24
const MAX_INTEGER = 9007199254740991
const PHASES = ["after_pending_write", "after_pending_verify", "after_backup_write", "after_backup_verify", "after_backup_replace", "before_primary_replace", "after_primary_replace"]

var phase_observer: Callable

func _result(status: String, field: String = "") -> Dictionary:
	return {"status": status, "field": field}

func _keys(value: Variant, required: Array) -> bool:
	if typeof(value) != TYPE_DICTIONARY or value.size() != required.size():
		return false
	return value.has_all(required)

func _integer(value: Variant, minimum: int, maximum: int) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value)) and float(value) == floor(float(value)) and float(value) >= minimum and float(value) <= maximum

func _id(value: Variant) -> bool:
	if typeof(value) != TYPE_STRING or value.length() < 3 or value.length() > 128 or not value.contains(":"):
		return false
	for character in value:
		if not character in "abcdefghijklmnopqrstuvwxyz0123456789:._-":
			return false
	return not value.begins_with(":") and not value.ends_with(":")

func canonical(value: Variant) -> String:
	# Sorting at every nesting level and integral numeric normalization make JSON
	# stable after Godot JSON's float parsing and across the two export targets.
	match typeof(value):
		TYPE_DICTIONARY:
			var keys: Array = value.keys()
			keys.sort()
			var fields: PackedStringArray = []
			for key in keys:
				fields.append(JSON.stringify(str(key)) + ":" + canonical(value[key]))
			return "{" + ",".join(fields) + "}"
		TYPE_ARRAY:
			var fields: PackedStringArray = []
			for item in value:
				fields.append(canonical(item))
			return "[" + ",".join(fields) + "]"
		TYPE_INT, TYPE_FLOAT:
			if _integer(value, -MAX_INTEGER, MAX_INTEGER):
				return str(int(value))
	return JSON.stringify(value, "", true, true)

func _valid_position(position: Dictionary, catalog: Dictionary) -> bool:
	if not catalog.get("maps", {}).has(position.map_id):
		return false
	var map: Dictionary = catalog.maps[position.map_id]
	if not _integer(position.x, 0, int(map.width) - 1) or not _integer(position.y, 0, int(map.height) - 1):
		return false
	for blocked in map.get("blocked", []):
		if int(blocked[0]) == int(position.x) and int(blocked[1]) == int(position.y):
			return false
	return true

func _position(position: Variant, catalog: Dictionary, check_version: bool) -> Dictionary:
	if not _keys(position, ["map_id", "map_version", "x", "y"]):
		return _result("INVALID_STATE", "position.shape")
	if not _id(position.map_id) or typeof(position.map_version) != TYPE_STRING or position.map_version.is_empty() or position.map_version.length() > 128:
		return _result("INVALID_STATE", "position.id_version")
	if not catalog.get("maps", {}).has(position.map_id):
		return _result("UNKNOWN_ID", "position.map_id")
	if not _integer(position.x, 0, 65535) or not _integer(position.y, 0, 65535):
		return _result("INVALID_STATE", "position.coordinate_type_range")
	if check_version and catalog.maps[position.map_id].version != position.map_version:
		return _result("DEFERRED", "position.map_version")
	if not _valid_position(position, catalog):
		return _result("DEFERRED", "position.coordinate_mapping")
	return _result("OK")

func validate(state: Variant, expected_owner: String, catalog: Dictionary, check_map_version: bool = true) -> Dictionary:
	if not _keys(state, ["meta", "payload"]):
		return _result("INVALID_STATE", "state.shape")
	var meta: Variant = state.meta
	if not _keys(meta, ["schema_id", "schema_version", "content_profile", "content_manifest_sha256", "build_id", "owner_id", "character_id", "revision"]):
		return _result("UNSUPPORTED_FORMAT", "meta.shape")
	if _integer(meta.schema_version, SCHEMA_VERSION + 1, MAX_INTEGER):
		return _result("UNSUPPORTED_FUTURE", "meta.schema_version")
	if meta.schema_id != SCHEMA_ID or not _integer(meta.schema_version, SCHEMA_VERSION, SCHEMA_VERSION):
		return _result("UNSUPPORTED_FORMAT", "meta.schema")
	if not _id(meta.owner_id) or not _id(meta.character_id):
		return _result("INVALID_STATE", "meta.identity")
	if meta.owner_id != expected_owner:
		return _result("OWNER_MISMATCH", "meta.owner_id")
	if not _integer(meta.revision, 0, MAX_INTEGER):
		return _result("INVALID_STATE", "meta.revision")
	for key in ["content_profile", "build_id"]:
		if typeof(meta[key]) != TYPE_STRING or meta[key].is_empty() or meta[key].length() > 128:
			return _result("INVALID_STATE", "meta." + key)
	if typeof(meta.content_manifest_sha256) != TYPE_STRING or meta.content_manifest_sha256.length() != 64 or not meta.content_manifest_sha256.is_valid_hex_number(false):
		return _result("INVALID_STATE", "meta.content_manifest_sha256")
	if meta.content_profile != catalog.get("profile", "") or meta.content_manifest_sha256 != catalog.get("manifest_sha256", ""):
		return _result("DEFERRED", "meta.content_compatibility")
	var payload: Variant = state.payload
	if not _keys(payload, ["character", "inventory", "equipment", "skills", "loot"]):
		return _result("INVALID_STATE", "payload.shape")
	var character: Variant = payload.character
	if not _keys(character, ["id", "name", "level", "hp", "hp_max", "position"]):
		return _result("INVALID_STATE", "character.shape")
	if character.id != meta.character_id:
		return _result("INVALID_STATE", "character.id")
	if typeof(character.name) != TYPE_STRING or character.name.length() < 1 or character.name.length() > 24:
		return _result("INVALID_STATE", "character.name")
	for index in range(character.name.length()):
		var character_code: int = character.name.unicode_at(index)
		if character_code < 32 or character_code == 127:
			return _result("INVALID_STATE", "character.name_control")
	if not _integer(character.level, 1, 99) or not _integer(character.hp_max, 1, 1000000000) or not _integer(character.hp, 0, int(character.hp_max)):
		return _result("INVALID_STATE", "character.range")
	var position_result = _position(character.position, catalog, check_map_version)
	if position_result.status != "OK":
		return position_result
	if typeof(payload.inventory) != TYPE_ARRAY or typeof(payload.skills) != TYPE_ARRAY or typeof(payload.loot) != TYPE_ARRAY or typeof(payload.equipment) != TYPE_DICTIONARY:
		return _result("INVALID_STATE", "payload.collection_type")
	if payload.inventory.size() > MAX_ENTRIES or payload.skills.size() > MAX_ENTRIES or payload.loot.size() > MAX_ENTRIES:
		return _result("INVALID_STATE", "payload.collection_limit")
	var instances: Dictionary = {}
	for entry in payload.inventory:
		if not _keys(entry, ["instance_id", "item_id", "quantity"]) or not _id(entry.instance_id) or not _id(entry.item_id) or not _integer(entry.quantity, 1, 1000000000):
			return _result("INVALID_STATE", "inventory.entry")
		if instances.has(entry.instance_id):
			return _result("INVALID_STATE", "inventory.duplicate_instance")
		if not catalog.get("items", {}).has(entry.item_id):
			return _result("UNKNOWN_ID", "inventory.item_id")
		instances[entry.instance_id] = entry
	var equipped: Dictionary = {}
	for slot in payload.equipment:
		if slot not in ["weapon", "armor", "head"] or typeof(payload.equipment[slot]) != TYPE_STRING or not instances.has(payload.equipment[slot]):
			return _result("INVALID_STATE", "equipment.reference")
		var instance_id: String = payload.equipment[slot]
		if equipped.has(instance_id) or catalog.items[instances[instance_id].item_id].get("slot", "") != slot or int(instances[instance_id].quantity) != 1:
			return _result("INVALID_STATE", "equipment.slot_quantity")
		equipped[instance_id] = true
	var seen_skills: Dictionary = {}
	for skill_id in payload.skills:
		if not _id(skill_id) or not catalog.get("skills", {}).has(skill_id):
			return _result("UNKNOWN_ID", "skills.id")
		if seen_skills.has(skill_id):
			return _result("INVALID_STATE", "skills.duplicate")
		seen_skills[skill_id] = true
	var seen_loot: Dictionary = {}
	for loot in payload.loot:
		if not _keys(loot, ["loot_id", "item_id", "quantity", "position"]) or not _id(loot.loot_id) or not _id(loot.item_id) or not _integer(loot.quantity, 1, 1000000000):
			return _result("INVALID_STATE", "loot.entry")
		if seen_loot.has(loot.loot_id) or instances.has(loot.loot_id):
			return _result("INVALID_STATE", "loot.duplicate")
		if not catalog.get("items", {}).has(loot.item_id):
			return _result("UNKNOWN_ID", "loot.item_id")
		seen_loot[loot.loot_id] = true
		position_result = _position(loot.position, catalog, check_map_version)
		if position_result.status != "OK":
			return position_result
	return _result("OK")

func encode(state: Dictionary) -> String:
	var document: Dictionary = state.duplicate(true)
	document.sha256 = canonical(state).sha256_text()
	return canonical(document)

func decode(text: String, expected_owner: String, catalog: Dictionary) -> Dictionary:
	if text.to_utf8_buffer().size() > MAX_BYTES:
		return _result("SAVE_SIZE_LIMIT")
	var depth: int = 0
	var quoted: bool = false
	var escaped: bool = false
	for character in text:
		if escaped:
			escaped = false
		elif quoted and character == "\\":
			escaped = true
		elif character == '"':
			quoted = not quoted
		elif not quoted:
			if character in ["{", "["]:
				depth += 1
				if depth > MAX_DEPTH:
					return _result("SAVE_DEPTH_LIMIT")
			elif character in ["}", "]"]:
				depth -= 1
	var parser := JSON.new()
	if parser.parse(text) != OK or not _keys(parser.data, ["meta", "payload", "sha256"]):
		return _result("CORRUPT", "json")
	var document: Dictionary = parser.data
	if typeof(document.sha256) != TYPE_STRING:
		return _result("CORRUPT", "sha256.type")
	var digest: String = document.sha256
	document.erase("sha256")
	if canonical(document).sha256_text() != digest:
		return _result("CHECKSUM_MISMATCH", "sha256")
	var result = validate(document, expected_owner, catalog)
	if result.status == "OK":
		result.state = document
	return result

func _path_has_link(path: String) -> bool:
	# Godot has no no-follow/exclusive-open API. Reject pre-existing symlinks in
	# the entire path before reads/writes and recheck before replacement. Caller
	# must use an app-owned directory; this does not promise protection against
	# a concurrent process swapping filesystem entries between these checks.
	var current: String = ProjectSettings.globalize_path(path).simplify_path()
	if not current.is_absolute_path():
		return true
	for depth in range(256):
		var parent: String = current.get_base_dir()
		if parent == current or current.is_empty():
			return false
		var directory := DirAccess.open(parent)
		if directory != null and directory.is_link(current):
			return true
		current = parent
	return true

func read_one(path: String, expected_owner: String, catalog: Dictionary) -> Dictionary:
	if _path_has_link(path):
		return _result("UNSAFE_PATH_LINK")
	if not FileAccess.file_exists(path):
		return _result("MISSING")
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _result("READ_FAILED")
	if file.get_length() > MAX_BYTES:
		file.close()
		return _result("SAVE_SIZE_LIMIT")
	var text: String = file.get_as_text()
	file.close()
	return decode(text, expected_owner, catalog)

func read_state(path: String, expected_owner: String, catalog: Dictionary) -> Dictionary:
	# Read/recovery never alters either original. Caller must explicitly save to repair.
	var primary = read_one(path, expected_owner, catalog)
	primary.source = path
	if primary.status == "OK" or primary.status not in ["MISSING", "CORRUPT", "CHECKSUM_MISMATCH", "INVALID_STATE"]:
		return primary
	var backup = read_one(path + ".backup", expected_owner, catalog)
	if backup.status == "OK":
		backup.status = "RECOVERED_BACKUP"
		backup.primary_error = primary.status
		backup.source = path + ".backup"
		return backup
	primary.backup_error = backup.status
	return primary

func _write(path: String, text: String) -> bool:
	if _path_has_link(path):
		return false
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(text)
	file.flush()
	var error: Error = file.get_error()
	file.close()
	return error == OK

func _phase(phase: String, fault_phase: String) -> bool:
	if phase_observer.is_valid():
		phase_observer.call(phase)
	return phase == fault_phase

func write_state(path: String, state: Dictionary, expected_owner: String, catalog: Dictionary, fault_phase: String = "") -> Dictionary:
	var validation = validate(state, expected_owner, catalog)
	if validation.status != "OK":
		return validation
	for suffix in ["", ".pending", ".backup", ".backup.pending"]:
		if _path_has_link(path + suffix):
			return _result("UNSAFE_PATH_LINK", "primary" if suffix.is_empty() else suffix)
	var text: String = encode(state)
	if text.to_utf8_buffer().size() > MAX_BYTES:
		return _result("SAVE_SIZE_LIMIT")
	var previous: String = ""
	# A backup-only slot can be the sole surviving save. Check it even when no
	# primary exists, and never consume another owner's/future/deferred copy.
	if FileAccess.file_exists(path + ".backup"):
		var existing_backup = read_one(path + ".backup", expected_owner, catalog)
		if existing_backup.status != "OK":
			return _result("EXISTING_SAVE_NOT_WRITABLE", "backup." + existing_backup.status)
		previous = FileAccess.get_file_as_string(path + ".backup")
	if FileAccess.file_exists(path):
		var current = read_one(path, expected_owner, catalog)
		if current.status == "OK":
			previous = FileAccess.get_file_as_string(path)
		else:
			if current.status not in ["CORRUPT", "CHECKSUM_MISMATCH", "INVALID_STATE"]:
				return _result("EXISTING_SAVE_NOT_WRITABLE", current.status)
			var backup = read_one(path + ".backup", expected_owner, catalog)
			if backup.status != "OK":
				return _result("EXISTING_SAVE_NOT_WRITABLE", backup.status)
			var broken: PackedByteArray = FileAccess.get_file_as_bytes(path)
			if broken.size() > MAX_BYTES:
				return _result("SAVE_SIZE_LIMIT")
			var hasher := HashingContext.new()
			hasher.start(HashingContext.HASH_SHA256)
			hasher.update(broken)
			var corrupt_path: String = path + ".corrupt-" + hasher.finish().hex_encode()
			if _path_has_link(corrupt_path):
				return _result("UNSAFE_PATH_LINK", "corrupt_copy")
			if FileAccess.file_exists(corrupt_path):
				if FileAccess.get_file_as_bytes(corrupt_path) != broken:
					return _result("PRESERVATION_CONFLICT")
			elif DirAccess.copy_absolute(path, corrupt_path) != OK:
				return _result("PRESERVATION_FAILED")
			previous = FileAccess.get_file_as_string(path + ".backup")
	if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK:
		return _result("WRITE_FAILED", "directory")
	if not _write(path + ".pending", text):
		return _result("WRITE_FAILED", "pending")
	if _phase("after_pending_write", fault_phase):
		return _result("INJECTED_FAILURE", "after_pending_write")
	if read_one(path + ".pending", expected_owner, catalog).status != "OK":
		return _result("VERIFY_FAILED", "pending")
	if _phase("after_pending_verify", fault_phase):
		return _result("INJECTED_FAILURE", "after_pending_verify")
	if not previous.is_empty():
		if not _write(path + ".backup.pending", previous):
			return _result("WRITE_FAILED", "backup.pending")
		if _phase("after_backup_write", fault_phase):
			return _result("INJECTED_FAILURE", "after_backup_write")
		if read_one(path + ".backup.pending", expected_owner, catalog).status != "OK":
			return _result("VERIFY_FAILED", "backup.pending")
		if _phase("after_backup_verify", fault_phase):
			return _result("INJECTED_FAILURE", "after_backup_verify")
		if _path_has_link(path + ".backup.pending") or _path_has_link(path + ".backup"):
			return _result("UNSAFE_PATH_LINK", "backup_replace")
		if DirAccess.rename_absolute(path + ".backup.pending", path + ".backup") != OK:
			return _result("REPLACE_FAILED", "backup")
		if _phase("after_backup_replace", fault_phase):
			return _result("INJECTED_FAILURE", "after_backup_replace")
	if _phase("before_primary_replace", fault_phase):
		return _result("INJECTED_FAILURE", "before_primary_replace")
	if _path_has_link(path + ".pending") or _path_has_link(path):
		return _result("UNSAFE_PATH_LINK", "primary_replace")
	if DirAccess.rename_absolute(path + ".pending", path) != OK:
		return _result("REPLACE_FAILED", "primary")
	if _phase("after_primary_replace", fault_phase):
		return _result("COMMITTED_ACK_LOST", "after_primary_replace")
	return _result("SAVED")

func plan_map_update(state: Dictionary, expected_owner: String, old_catalog: Dictionary, target_catalog: Dictionary) -> Dictionary:
	# No implicit teleport, removal, or fabricated coordinate transformation.
	# This plan accepts only coordinates still valid on their same stable map ID.
	var source = validate(state, expected_owner, old_catalog)
	if source.status != "OK":
		return source
	var candidate: Dictionary = state.duplicate(true)
	candidate.meta.content_profile = target_catalog.get("profile", "")
	candidate.meta.content_manifest_sha256 = target_catalog.get("manifest_sha256", "")
	var positions: Array = [candidate.payload.character.position]
	for loot in candidate.payload.loot:
		positions.append(loot.position)
	for position in positions:
		if not _valid_position(position, target_catalog):
			return {"status": "DEFERRED", "field": "explicit_coordinate_mapping_required", "source": state.duplicate(true)}
		position.map_version = target_catalog.maps[position.map_id].version
	var result = validate(candidate, expected_owner, target_catalog)
	if result.status != "OK":
		return {"status": "DEFERRED", "field": result.field, "source": state.duplicate(true)}
	return {"status": "READY", "state": candidate, "source": state.duplicate(true), "policy": "same_map_valid_coordinates_preserved"}
