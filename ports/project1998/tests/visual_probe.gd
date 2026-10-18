extends SceneTree
var output: String
var app: Control
var records: Array=[]

func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	output=args[0]
	DirAccess.make_dir_recursive_absolute(output)
	call_deferred("run")

func capture(name: String) -> void:
	for i in range(3):await process_frame
	await RenderingServer.frame_post_draw
	get_root().get_texture().get_image().save_png(output.path_join(name+".png"))

func run() -> void:
	get_root().size=Vector2i(1280,800)
	app=load("res://main.tscn").instantiate();get_root().add_child(app)
	for i in range(6):await process_frame
	for mid in ["4711","0","2"]:
		app._select_map(mid)
		app.world.draw_actors=false
		app.world.label_actors=false
		app.world.refresh(0)
		await capture("map-"+mid+"-terrain")
		records.append({"map_id":mid,"camera":[app.world.camera.x,app.world.camera.y],"zoom":app.world.zoom,
			"world_rect":[app.world.position.x,app.world.position.y,app.world.size.x,app.world.size.y],
			"position":[app.model.position().x,app.model.position().y],"draw_items":app.world.last_draw_items})
		app.world.draw_actors=true;app.world.label_actors=true
		await capture("map-"+mid+"-actors")
	# Two real source-tree scenes, on each side of its base. These are explicit
	# visual fixtures, separate from ordinary mouse/keyboard execution.
	app._select_map("4711")
	for item in [["north",Vector2i(5,9)],["south",Vector2i(5,11)]]:
		app.model.state.character.x=item[1].x;app.model.state.character.y=item[1].y;app.model.halt();app.world.refresh(0)
		await capture("depth-"+str(item[0]))
	var file:=FileAccess.open(output.path_join("VISUAL_SCENES.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify({"status":"EXECUTED_HOST_FIXTURES","scenes":records,"device":"Linux Xvfb/OpenGL; not Galaxy"},"\t"));file.close()
	quit()
