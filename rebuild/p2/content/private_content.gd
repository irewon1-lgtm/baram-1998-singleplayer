extends RefCounted
## Loads an explicitly supplied, frozen private generation. No fallback artwork.
var root: String = ""
var manifest: Dictionary = {}
var maps: Dictionary = {}
var kr491: Dictionary = {}
var policy: Dictionary = {}
var errors: Array[String] = []
var consumed: Dictionary = {}
var textures: Dictionary = {}
var priority: Dictionary = {}
const MAX_TEXTURE_PIXELS := 16 * 1024 * 1024
var texture_pixels := 0
var texture_order: Array[String] = []
var texture_sizes: Dictionary = {}
var sound_cache: Dictionary = {}
var texture_decode_count := 0
var texture_cache_hits := 0
var texture_evictions := 0
var texture_decode_usec := 0

func safe(relative: String) -> bool:
	if relative.is_empty() or relative.is_absolute_path() or ".." in relative.split("/") or "\\" in relative:
		errors.append("UNSAFE_ASSET_PATH: "+relative)
		return false
	return true

func read_json(relative: String) -> Dictionary:
	if not safe(relative): return {}
	var path := root.path_join(relative)
	if not FileAccess.file_exists(path):
		errors.append("MISSING: " + relative)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		errors.append("INVALID_JSON: " + relative)
		return {}
	consumed[relative] = true
	return parsed

func open_generation(path: String) -> bool:
	root = path
	manifest = read_json("runtime.json")
	if manifest.get("schema", "") != "baram.work.p2.runtime/1":
		errors.append("UNSUPPORTED_RUNTIME_SCHEMA")
		return false
	if manifest.get("files",[]).is_empty():
		errors.append("EMPTY_REQUIRED_FILE_SET")
		return false
	# Hash checks are performed by the assembler before staging. Check actual
	# external bytes here too. Imported export resources are separately recorded.
	if not root.begins_with("res://"):
		for entry in manifest.get("files", []):
			var relative: String = entry.path
			if relative.is_absolute_path() or ".." in relative.split("/"):
				errors.append("UNSAFE_ASSET_PATH: " + relative)
				continue
			var target := root.path_join(relative)
			if not FileAccess.file_exists(target) or FileAccess.get_sha256(target) != entry.sha256:
				errors.append("HASH_MISMATCH_OR_MISSING: " + relative)
	if not errors.is_empty():
		return false
	maps = read_json("maps/index.json")
	var loaded_maps: Array = []
	for entry in maps.get("maps", []):
		if maps.get("load_mode", "") == "LAZY_VALIDATED_INDEX":
			var lazy: Dictionary = entry.duplicate(true)
			lazy["lazy_json"] = "maps/" + str(entry.get("json", ""))
			loaded_maps.append(lazy)
			continue
		var value := read_json("maps/"+str(entry.get("json", "")))
		if value.is_empty():
			errors.append("EMPTY_MAP_UNIT")
		else:
			loaded_maps.append(value)
	maps["maps"] = loaded_maps
	kr491 = read_json("kr491/kr491_runtime.json")
	policy = read_json("work_batch_policy.json")
	if manifest.has("priority_index"):
		priority = read_json(str(manifest.priority_index))
	if maps.get("maps",[]).is_empty() or kr491.get("parts",{}).is_empty() or kr491.get("effects",[]).is_empty() or kr491.get("sounds",[]).is_empty():
		errors.append("EMPTY_REQUIRED_UNIT")
	return errors.is_empty()

func map_at(index: int) -> Dictionary:
	var entries: Array = maps.get("maps", [])
	if index < 0 or index >= entries.size():
		errors.append("MAP_INDEX_BOUNDS")
		return {}
	var entry: Dictionary = entries[index]
	if entry.has("lazy_json"):
		var value := read_json(str(entry.lazy_json))
		if value.is_empty(): return {}
		entries[index] = value
		return value
	return entry

func texture(relative: String) -> Texture2D:
	if not safe(relative):
		return null
	if textures.has(relative):
		texture_cache_hits += 1
		texture_order.erase(relative)
		texture_order.append(relative)
		return textures[relative]
	var path := root.path_join(relative)
	var began := Time.get_ticks_usec()
	var result: Texture2D
	if path.begins_with("res://") and ResourceLoader.exists(path):
		result = load(path) as Texture2D
	else:
		var img := Image.new()
		if img.load(path) == OK and not img.is_empty():
			result = ImageTexture.create_from_image(img)
	if result == null:
		errors.append("TEXTURE_DECODE: " + relative)
		return null
	var pixels := result.get_width() * result.get_height()
	if pixels > MAX_TEXTURE_PIXELS:
		errors.append("TEXTURE_PIXEL_LIMIT: " + relative)
		return null
	while texture_pixels + pixels > MAX_TEXTURE_PIXELS and not texture_order.is_empty():
		var evicted: String = texture_order.pop_front()
		var previous: Texture2D = textures[evicted]
		texture_evictions += 1
		texture_pixels -= previous.get_width() * previous.get_height()
		textures.erase(evicted)
	textures[relative] = result
	texture_order.append(relative)
	texture_pixels += pixels
	texture_sizes[relative] = result.get_size()
	texture_decode_count += 1
	texture_decode_usec += Time.get_ticks_usec() - began
	consumed[relative] = true
	return result

func texture_size(relative: String) -> Vector2:
	if texture_sizes.has(relative): return texture_sizes[relative]
	if not safe(relative): return Vector2.ZERO
	# Exported PNG source bytes remain in the frozen runtime. Reading only the
	# 24-byte header avoids synchronous Image/Texture creation during culling.
	var file := FileAccess.open(root.path_join(relative), FileAccess.READ)
	if file != null and file.get_length() >= 24:
		var header := file.get_buffer(24)
		if header[0] == 137 and header[1] == 80 and header[2] == 78 and header[3] == 71:
			var w := int(header[16]) * 16777216 + int(header[17]) * 65536 + int(header[18]) * 256 + int(header[19])
			var h := int(header[20]) * 16777216 + int(header[21]) * 65536 + int(header[22]) * 256 + int(header[23])
			if w > 0 and h > 0 and w * h <= MAX_TEXTURE_PIXELS:
				texture_sizes[relative] = Vector2(w, h)
				return texture_sizes[relative]
	return Vector2.ZERO

func sound(relative: String) -> AudioStream:
	if not safe(relative): return null
	if sound_cache.has(relative): return sound_cache[relative]
	var path := root.path_join(relative)
	var stream: AudioStream
	if path.begins_with("res://") and ResourceLoader.exists(path):
		stream = load(path) as AudioStream
	else:
		stream = AudioStreamWAV.load_from_file(path)
	if stream == null:
		errors.append("AUDIO_DECODE: " + relative)
	else:
		consumed[relative] = true
		sound_cache[relative] = stream
	return stream
