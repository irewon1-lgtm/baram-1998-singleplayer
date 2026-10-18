extends SceneTree
var output: String
func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func run() -> void:
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	var app=entry.get_node_or_null("P5Play")
	var error:=""
	if app!=null:error=app.initialization_error
	else:
		var failure: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("P1998_P4_OUTPUT").path_join("failure.json")))
		error=str(failure.get("error",""))
	var passed: bool="EXISTING_SAVE_PROTECTED" in error
	var f:=FileAccess.open(output.path_join("GUARD.json"),FileAccess.WRITE);f.store_string(JSON.stringify({"status":"PASS" if passed else "FAIL","error":error}));f.close()
	print("P4_GUARD ",passed," ",error);quit(0 if passed else 1)
