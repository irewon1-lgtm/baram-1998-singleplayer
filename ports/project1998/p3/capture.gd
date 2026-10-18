extends SceneTree

func _initialize() -> void:
	call_deferred("capture")

func capture() -> void:
	var scene = load("res://main.tscn").instantiate()
	root.add_child(scene)
	for i in range(20):await process_frame
	await RenderingServer.frame_post_draw
	var path := OS.get_environment("P1998_P3_CAPTURE")
	assert(not path.is_empty())
	var error := root.get_texture().get_image().save_png(path)
	print("P3_CAPTURE ",error," ",path)
	quit(error)
