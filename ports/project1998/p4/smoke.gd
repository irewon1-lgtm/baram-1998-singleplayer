extends SceneTree
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(30):await process_frame
	var app=entry.get_node_or_null("P4Play")
	if app==null:push_error("P4 default startup failed");quit(1);return
	print("P4_INITIAL ",JSON.stringify(app.model.snapshot))
	if not app.model.snapshot.get("playing",false):
		app.model.call_core("Create",["Adventurer"])
		if not app.model.snapshot.get("playing",false):push_error("P4 create failed "+JSON.stringify(app.model.snapshot));quit(1);return
	print("P4_CREATED ",JSON.stringify(app.model.snapshot))
	app.model.call_core("Save")
	print("P4_SAVE ",app.model.snapshot.save_status)
	quit()
