extends RefCounted
## Frozen P3 input closure. Existing bounded PNG/WAV loader is reused.
const PrivateContent = preload("res://content/private_content.gd")
var assets = PrivateContent.new()
var data: Dictionary = {}
var actors: Dictionary = {}
var manifest: Dictionary = {}
var effects: Dictionary = {}
var sounds: Dictionary = {}
var errors: Array[String] = []

func _error(code: String) -> void:
	if code not in errors: errors.append(code)
	if code not in assets.errors: assets.errors.append(code)

func _actor_asset_path(relative: String) -> String:
	return relative if relative.begins_with("gameplay-assets/") else "gameplay-assets/"+relative

func open(path: String) -> bool:
	errors.clear()
	assets.errors.clear()
	effects.clear()
	sounds.clear()
	assets.root = path
	manifest = assets.read_json("runtime.json")
	if manifest.get("schema", "") != "baram.work.p3.runtime/1":
		errors.append("P3_RUNTIME_MANIFEST_REQUIRED")
		return false
	for entry in manifest.get("files", []):
		var relative := str(entry.get("path", ""))
		if not assets.safe(relative):
			errors.append("UNSAFE_REFERENCE")
			continue
		var target := path.path_join(relative)
		if not FileAccess.file_exists(target) and not ResourceLoader.exists(target):
			errors.append("MISSING:"+relative)
		elif not path.begins_with("res://") and FileAccess.get_sha256(target) != entry.get("sha256", ""):
			errors.append("HASH_MISMATCH:"+relative)
	data = assets.read_json("gameplay_content.json")
	actors = assets.read_json("gameplay-assets/actors.json")
	if actors.get("schema", "") != "baram.gameplay.actor-assets/1":
		_error("ACTOR_ASSET_SCHEMA_REQUIRED")
	var source := assets.read_json("kr491/kr491_runtime.json")
	for effect in source.get("effects", []): effects[str(effect.get("id"))] = effect
	for sound in source.get("sounds", []):
		var member := str(sound.get("member", "")).get_file().get_basename()
		if not member.is_valid_int():
			_error("SOUND_MEMBER_ID_REQUIRED:"+member)
			continue
		var id := str(int(member))
		if sounds.has(id):
			_error("DUPLICATE_SOUND_ID:"+id)
			continue
		sounds[id] = sound
		# Keep the original padded member and source namespace as aliases.
		# Alias lookup never combines distinct source IDs or waveforms.
		sounds[member] = sound
		if sound.has("source_id"): sounds[str(sound.source_id)] = sound
	errors.append_array(assets.errors)
	if data.is_empty() or actors.get("looks", {}).is_empty(): errors.append("EMPTY_GAMEPLAY_INPUT")
	return errors.is_empty()

func icon(item_id: String) -> Texture2D:
	var entry: Variant = actors.get("icons", {}).get(item_id, {})
	var path := str(entry.get("path", "")) if typeof(entry) == TYPE_DICTIONARY else str(entry)
	if not path.is_empty(): path = _actor_asset_path(path)
	if path.is_empty(): path = str(data.get("items", {}).get(item_id, {}).get("icon", ""))
	if path.is_empty():
		_error("MISSING_ITEM_ICON:"+item_id)
		return null
	return assets.texture(path)

func actor(look: String, animation: String, direction: int, time: float) -> Dictionary:
	var definition: Dictionary = actors.get("looks", {}).get(look, {})
	var animations: Dictionary = definition.get("animations", {})
	if definition.is_empty() or not animations.has(animation) or direction < 0 or direction > 3 or not is_finite(time) or time < 0:
		_error("MISSING_OR_INVALID_ACTOR_ACTION:"+look+":"+animation+":"+str(direction))
		return {}
	var selected: Dictionary = animations[animation]
	var frames: Array = selected.get(str(direction), [])
	if frames.is_empty() or frames.size() > 64:
		_error("ACTOR_FRAME_SET_REQUIRED:"+look+":"+animation+":"+str(direction))
		return {}
	var total := 0.0
	for frame in frames:
		var duration := float(frame.get("duration_ms",0))
		var path := str(frame.get("path",""))
		var offset: Variant = frame.get("offset")
		if not is_finite(duration) or duration <= 0 or duration > 1000 or path.is_empty() or not assets.safe(_actor_asset_path(path)) or typeof(offset) != TYPE_ARRAY or offset.size() != 2:
			_error("INVALID_ACTOR_FRAME:"+look+":"+animation)
			return {}
		for value in offset:
			if not is_finite(float(value)) or absf(float(value)) > 4096:
				_error("INVALID_ACTOR_OFFSET:"+look+":"+animation)
				return {}
		total += duration
	var elapsed := fmod(time * 1000.0, maxf(total, 1.0))
	for frame in frames:
		elapsed -= float(frame.get("duration_ms", 130))
		if elapsed < 0: return frame
	return frames[-1]
