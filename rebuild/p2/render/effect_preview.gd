extends RefCounted
## Bounded inspection only. Original graph and unresolved command evidence stay intact.
const SCHEMA := "baram.priority.effect-preview/1"
const MAX_DURATION_MS := 10000.0
const MAX_FRAME_MS := 1000.0
const MAX_FRAMES := 4096

static func describe(effect: Dictionary) -> Dictionary:
	return effect.get("priority_preview", {})

static func _safe_frame(frame: Dictionary) -> bool:
	var img: Variant = frame.get("image")
	if int(frame.get("original_frame", -1)) < 0 or typeof(img) != TYPE_DICTIONARY:
		return false
	if int(img.get("frame", -1)) != int(frame.get("original_frame", -2)) or img.get("source_empty_rectangle", true):
		return false
	var path: String = str(img.get("path", ""))
	if path.is_empty() or path.is_absolute_path() or ".." in path.split("/") or "\\" in path:
		return false
	var extent: Variant = img.get("size")
	var offset: Variant = img.get("offset")
	if typeof(extent) != TYPE_ARRAY or extent.size() != 2 or typeof(offset) != TYPE_ARRAY or offset.size() != 2:
		return false
	for value in extent:
		if not is_finite(float(value)) or float(value) <= 0 or float(value) > 4096:
			return false
	for value in offset:
		if not is_finite(float(value)) or absf(float(value)) > 8192:
			return false
	var duration := float(frame.get("duration_ms", 0))
	return is_finite(duration) and duration > 0 and duration <= MAX_FRAME_MS

static func _sequence_layer(sequence: Array, elapsed_ms: float, center: Vector2, errors: Array) -> Dictionary:
	if sequence.size() > MAX_FRAMES:
		errors.append("EFFECT_FRAME_COUNT_LIMIT")
		return {}
	var total := 0.0
	for frame in sequence:
		if typeof(frame) != TYPE_DICTIONARY or not _safe_frame(frame):
			errors.append("EFFECT_INVALID_FRAME_NO_FALLBACK")
			return {}
		total += float(frame.duration_ms)
	if total > MAX_DURATION_MS:
		errors.append("EFFECT_DURATION_LIMIT")
		return {}
	var cursor := elapsed_ms
	for frame in sequence:
		var duration := float(frame.duration_ms)
		if cursor < duration:
			var img: Dictionary = frame.image
			var off: Array = img.offset
			var path := str(img.path)
			if not path.begins_with("kr491/"): path = "kr491/" + path
			return {"path": path, "x": center.x + float(off[0]), "y": center.y + float(off[1]),
				"opacity": 1.0, "original_frame": frame.original_frame, "source_index": frame.source_index}
		cursor -= duration
	return {}

static func layers(effect: Dictionary, elapsed_seconds: float, center: Vector2 = Vector2(256, 256), fragment_index: int = -1) -> Dictionary:
	var result := {"back": [], "front": [], "paths": [], "finished": true, "errors": [], "scope": "BLOCKED", "fragment_id": null}
	var chosen := describe(effect)
	if chosen.get("schema", "") != SCHEMA or not chosen.get("available", false):
		result.errors.append("EFFECT_PREVIEW_NOT_SELECTED")
		return result
	if not is_finite(elapsed_seconds) or elapsed_seconds < 0:
		result.errors.append("EFFECT_INVALID_ELAPSED")
		return result
	var time_ms := elapsed_seconds * 1000.0
	if time_ms >= MAX_DURATION_MS:
		result.scope = "BOUNDED_FINISHED"
		return result
	var sequences: Dictionary = {}
	if chosen.get("whole_sequence_available", false) and fragment_index < 0:
		sequences = chosen.get("whole", {})
		result.scope = "RECONSTRUCTED_NEUTRAL_SINGLE_TRAVERSAL"
	else:
		var fragments: Array = chosen.get("fragments", [])
		var index := maxi(0, fragment_index)
		if index >= fragments.size():
			result.errors.append("EFFECT_FRAGMENT_UNAVAILABLE")
			return result
		var fragment: Dictionary = fragments[index]
		var side: String = str(fragment.get("side", ""))
		if side not in ["front", "back"]:
			result.errors.append("EFFECT_INVALID_FRAGMENT_SIDE")
			return result
		sequences[side] = fragment.get("frames", [])
		result.scope = "RECONSTRUCTED_VALID_FRAGMENT_ONLY"
		result.fragment_id = fragment.get("id")
	for side in ["back", "front"]:
		var layer := _sequence_layer(sequences.get(side, []), time_ms, center, result.errors)
		if not layer.is_empty():
			result[side].append(layer)
			result.paths.append(layer.path)
	if not result.errors.is_empty():
		result.back.clear()
		result.front.clear()
		result.paths.clear()
	result.finished = result.paths.is_empty()
	return result
