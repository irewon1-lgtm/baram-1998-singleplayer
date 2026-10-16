extends SceneTree
## Isolated primitive renderer check. No game assets, shaders or save access.
## Set BARAM_RENDERER_PROBE_OUTPUT to a fresh existing output directory.
## A framebuffer PASS does not certify OS presentation or any game platform.

var output := ""

func _initialize() -> void:
	output = OS.get_environment("BARAM_RENDERER_PROBE_OUTPUT")
	if output.is_empty() or not DirAccess.dir_exists_absolute(output):
		printerr("BARAM_RENDERER_PROBE_OUTPUT must be an existing isolated directory")
		quit(2)
		return
	if FileAccess.file_exists(output.path_join("renderer-probe.json")):
		printerr("Refusing to overwrite renderer probe evidence")
		quit(2)
		return
	_run.call_deferred()

func _record(result: Dictionary, code: int) -> void:
	result["schema"] = "baram.renderer-probe/1"
	result["engine"] = Engine.get_version_info().string
	result["os"] = OS.get_name()
	result["display"] = DisplayServer.get_name()
	result["scope"] = "primitive_framebuffer_only_not_OS_presentation_or_game_certification"
	result["OS_visible_presentation"] = "NOT_RUN"
	var file := FileAccess.open(output.path_join("renderer-probe.json"), FileAccess.WRITE)
	if file == null:
		printerr("Cannot write probe receipt")
		quit(2)
		return
	file.store_string(JSON.stringify(result, "\t") + "\n")
	file.close()
	print(JSON.stringify(result))
	quit(code)

func _run() -> void:
	if DisplayServer.get_name() == "headless":
		_record({"status":"BLOCKED_NO_DISPLAY", "reason":"Dummy headless rendering cannot exercise GLES or presentation."}, 2)
		return
	root.size = Vector2i(640, 360)
	root.content_scale_size = Vector2i(640, 360)
	var colors := [Color.RED, Color.GREEN, Color.BLUE]
	for i in range(3):
		var rect := ColorRect.new()
		rect.color = colors[i]
		rect.position = Vector2(20 + i * 200, 100)
		rect.size = Vector2(180, 180)
		root.add_child(rect)
	var label := Label.new()
	label.text = "BARAM primitive renderer probe"
	label.position = Vector2(20, 20)
	root.add_child(label)
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		_record({"status":"FAIL_NO_FRAMEBUFFER"}, 1)
		return
	var checks: Array = []
	for i in range(3):
		var sampled := image.get_pixel(110 + i * 200, 190)
		checks.append({"id":["red", "green", "blue"][i], "pass":sampled.is_equal_approx(colors[i]), "sample":[sampled.r,sampled.g,sampled.b,sampled.a]})
	var screenshot := output.path_join("renderer-probe.png")
	var saved := image.save_png(screenshot)
	var ok := saved == OK
	for check in checks:
		ok = ok and check["pass"]
	_record({"status":"PASS_FRAMEBUFFER_ONLY" if ok else "FAIL_PRIMITIVE_PIXELS", "checks":checks, "image_size":[image.get_width(),image.get_height()], "image":screenshot,"save_error":saved}, 0 if ok else 1)
