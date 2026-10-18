extends SceneTree
func _initialize() -> void:call_deferred("run")
func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(20):await process_frame
	var app: Control=entry.get_node_or_null("P3World")
	var expected: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("P1998_P3_EXPECTED")))
	var ok:=app!=null
	var actual: Dictionary={} if app==null else app.model.snapshot
	if ok:
		ok=actual.loaded
		for key in ["x","y","map","hp","mp","inventory"]:ok=ok and actual[key]==expected[key]
	var result: Dictionary={"status":"PASS" if ok else "FAIL","platform":"Linux","cold_process":true,"actual":actual,"expected":expected}
	var output:=OS.get_environment("P1998_P3_COLD_OUTPUT")
	var f:=FileAccess.open(output.path_join("COLD_QA.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"\t"));f.close()
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join("03-cold.png"));quit(0 if ok else 1)
