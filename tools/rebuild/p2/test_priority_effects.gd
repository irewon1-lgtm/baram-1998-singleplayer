extends SceneTree
## Executes real GDScript preview selection. This is not a pixel/audio/device test.
const Preview = preload("res://render/effect_preview.gd")
var checks: Array = []

func check(id: String, good: bool, details: Variant = null) -> void:
	checks.append({"id":id, "status":"PASS" if good else "FAIL", "details":details})

func _initialize() -> void:
	var input := OS.get_environment("BARAM_PRIORITY_KR491")
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(input))
	if typeof(data) != TYPE_DICTIONARY:
		push_error("Set BARAM_PRIORITY_KR491 to a fresh priority kr491_runtime.json")
		quit(2)
		return
	var observed: Array = []
	var whole := 0
	var fragments := 0
	for effect in data.get("effects", []):
		var desc := Preview.describe(effect)
		var result := Preview.layers(effect, 0.001)
		var available := bool(desc.get("available", false))
		check("effect_%03d_available_contract" % effect.id, (not result.paths.is_empty()) == available, {"scope":result.scope, "errors":result.errors})
		if not available: continue
		if desc.get("whole_sequence_available", false): whole += 1
		else: fragments += 1
		var source_frames: Array = []
		for side in ["back", "front"]:
			for frame in result[side]: source_frames.append(frame.original_frame)
		check("effect_%03d_no_negative_frame" % effect.id, source_frames.all(func(f: int) -> bool: return f >= 0))
		var finished := Preview.layers(effect, 10.0)
		check("effect_%03d_bounded_finish" % effect.id, finished.paths.is_empty() and finished.finished)
		observed.append({"id":effect.id, "scope":result.scope, "fragment_id":result.fragment_id, "paths":result.paths, "original_frames":source_frames})
	var first: Dictionary = data.effects[0].duplicate(true)
	first.priority_preview.whole.front[0].original_frame = -1
	check("negative_mutation_no_frame_zero_fallback", Preview.layers(first, 0.001).paths.is_empty())
	first = data.effects[0].duplicate(true)
	first.priority_preview.whole.front[0].image.path = ""
	check("empty_path_no_fallback", Preview.layers(first, 0.001).paths.is_empty())
	first = data.effects[0].duplicate(true)
	first.priority_preview.whole.front[0].duration_ms = 0
	check("zero_duration_no_fallback", Preview.layers(first, 0.001).paths.is_empty())
	check("negative_elapsed_rejected", Preview.layers(data.effects[0], -1.0).paths.is_empty())
	var failed := checks.filter(func(c: Dictionary) -> bool: return c.status == "FAIL")
	var result := {"schema":"baram.priority.effects-gdscript-test/1", "platform":OS.get_name(),
		"engine":Engine.get_version_info().string, "checks":checks, "observed_layer_references":observed,
		"whole_previews":whole, "fragment_previews":fragments,
		"scope":"Real engine helper selection, termination and fail-closed execution; pixel rendering NOT_ASSESSED", "pixel_render":"NOT_ASSESSED"}
	var output := OS.get_environment("BARAM_PRIORITY_EFFECT_REPORT")
	if not output.is_empty():
		var f := FileAccess.open(output, FileAccess.WRITE)
		if f != null: f.store_string(JSON.stringify(result, "  ") + "\n")
	print("PRIORITY_EFFECTS checks=%s failures=%s whole=%s fragment=%s" % [checks.size(), failed.size(), whole, fragments])
	quit(0 if failed.is_empty() else 1)
