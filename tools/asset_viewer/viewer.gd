extends Control
## Only inspects explicit exported frames. Does not infer actions or animation speed.

var records: Array = []
var images: Array[Image] = []
var current := 0
var manifest: Dictionary = {}
var options: Dictionary = {}
var sprite := Sprite2D.new()
var details := Label.new()
var report := {"screen_status": "NOT_RUN", "key_navigation_status": "NOT_RUN"}


func _ready() -> void:
	for argument in OS.get_cmdline_user_args():
		var split := argument.split("=", true, 1)
		options[split[0]] = split[1] if split.size() == 2 else "true"
	if not options.has("--report"):
		fail("Usage: -- --report=/private/decode.json [--capture=/private/view.png --exercise --exit]")
		return
	var source := FileAccess.open(str(options["--report"]), FileAccess.READ)
	if source == null:
		fail("Cannot open frame report")
		return
	var parsed: Variant = JSON.parse_string(source.get_as_text())
	if not parsed is Dictionary:
		fail("Frame report is not a JSON object")
		return
	manifest = parsed
	if manifest.get("decoded_render_status") != "PASS_SELECTED_PIXELS_PNG_ONLY":
		fail("Frame report does not describe a successful selected-pixel decode")
		return
	for row in manifest.get("frames", []):
		if row.get("status") != "PASS_PIXEL_DECODE_PNG_ONLY":
			continue
		var path := str(row["png_path"])
		var bytes := FileAccess.get_file_as_bytes(path)
		if digest(bytes) != row["png_sha256"]:
			fail("PNG hash mismatch: " + path)
			return
		var decoded := Image.load_from_file(path)
		if decoded == null or decoded.is_empty():
			fail("Godot cannot decode PNG: " + path)
			return
		decoded.convert(Image.FORMAT_RGBA8)
		if decoded.get_width() != int(row["width"]) or decoded.get_height() != int(row["height"]) or digest(decoded.get_data()) != row["rgba_sha256"]:
			fail("Godot PNG pixels/dimensions differ from the EPF decode")
			return
		records.append(row)
		images.append(decoded)
	if records.is_empty():
		fail("No nonempty frames selected")
		return
	var title := Label.new()
	title.position = Vector2(24, 24)
	title.text = "Frame inspector · %s · palette %s" % [manifest.get("version", "?"), manifest.get("palette_index", "?")]
	title.add_theme_font_size_override("font_size", 24)
	add_child(title)
	var scope := Label.new()
	scope.position = Vector2(24, 68)
	scope.text = "Pixel decode only. Entity/action/direction and original fidelity remain NOT_RUN."
	add_child(scope)
	details.position = Vector2(24, 100)
	add_child(details)
	sprite.centered = false
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sprite.scale = Vector2(8, 8)
	add_child(sprite)
	var previous := Button.new()
	previous.position = Vector2(24, 540)
	previous.text = "← Previous frame"
	previous.pressed.connect(func(): show_frame(posmod(current - 1, records.size())))
	add_child(previous)
	var following := Button.new()
	following.position = Vector2(220, 540)
	following.text = "Next frame →"
	following.pressed.connect(func(): show_frame((current + 1) % records.size()))
	add_child(following)
	show_frame(0)
	report["version"] = manifest.get("version")
	report["engine"] = Engine.get_version_info()["string"]
	report["loaded_png_count"] = records.size()
	report["pixel_load_status"] = "PASS_GODOT_RGBA_HASH_MATCH_ONLY"
	report["semantic_identification_status"] = "NOT_RUN"
	report["original_game_play_status"] = "NOT_RUN"
	if options.has("--exercise"):
		await get_tree().process_frame
		var event := InputEventKey.new()
		event.pressed = true
		event.keycode = KEY_RIGHT
		Input.parse_input_event(event)
		await get_tree().process_frame
		var advanced := current == 1
		event = InputEventKey.new()
		event.pressed = true
		event.keycode = KEY_LEFT
		Input.parse_input_event(event)
		await get_tree().process_frame
		if records.size() < 2 or not advanced or current != 0:
			fail("Frame navigation did not respond to right/left input events")
			return
		report["key_navigation_status"] = "PASS_INSPECTOR_RIGHT_LEFT_INPUT_ONLY"
	if options.has("--capture"):
		var capture_path := str(options["--capture"]).simplify_path()
		var checkout := ProjectSettings.globalize_path("res://../../").simplify_path().trim_suffix("/")
		if not capture_path.is_absolute_path() or capture_path == checkout or capture_path.begins_with(checkout + "/"):
			fail("Viewport captures must use an absolute private path outside the public checkout")
			return
		var current_path := capture_path
		while current_path != current_path.get_base_dir():
			var parent := DirAccess.open(current_path.get_base_dir())
			if parent == null or parent.is_link(current_path.get_file()):
				fail("Viewport capture parent is absent or uses a symbolic link")
				return
			current_path = current_path.get_base_dir()
		if FileAccess.file_exists(capture_path):
			fail("Existing viewport capture preserved; select a fresh private output path")
			return
		if DisplayServer.get_name() == "headless":
			fail("Headless PNG loading cannot validate screen rendering; use an X display")
			return
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var screenshot := get_viewport().get_texture().get_image()
		var path := str(options["--capture"])
		if screenshot == null or screenshot.is_empty() or screenshot.save_png(path) != OK:
			fail("Viewport capture failed")
			return
		report["screen_status"] = "PASS_INSPECTOR_VIEWPORT_CAPTURE_ONLY"
		report["display_driver"] = DisplayServer.get_name()
		report["screenshot_path"] = path
		report["screenshot_sha256"] = digest(FileAccess.get_file_as_bytes(path))
		report["frame_position"] = [sprite.position.x, sprite.position.y]
		report["frame_scale"] = 8
		report["frame_index"] = records[current]["index"]
	write_report()
	if options.has("--exit"):
		get_tree().quit(0)


func show_frame(index: int) -> void:
	current = index
	var row: Dictionary = records[index]
	sprite.texture = ImageTexture.create_from_image(images[index])
	sprite.position = Vector2(160 + int(row["left"]) * 8, 200 + int(row["top"]) * 8)
	details.text = "Frame %d · %dx%d · pivot (%d,%d) · opaque pixels %d" % [int(row["index"]), int(row["width"]), int(row["height"]), int(row["left"]), int(row["top"]), int(row["opaque_pixels"])]


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not records.is_empty():
		if event.keycode == KEY_RIGHT:
			show_frame((current + 1) % records.size())
		elif event.keycode == KEY_LEFT:
			show_frame(posmod(current - 1, records.size()))


func digest(bytes: PackedByteArray) -> String:
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(bytes)
	return hashing.finish().hex_encode()


func write_report() -> void:
	report["executed_at_utc"] = Time.get_datetime_string_from_system(true)
	if options.has("--screen-report"):
		var destination := FileAccess.open(str(options["--screen-report"]), FileAccess.WRITE)
		if destination == null:
			push_error("Cannot write screen report")
			get_tree().quit(1)
			return
		destination.store_string(JSON.stringify(report, "\t") + "\n")
	print(JSON.stringify(report))


func fail(message: String) -> void:
	report["screen_status"] = "FAIL"
	report["error"] = message
	push_error(message)
	write_report()
	get_tree().quit(1)
