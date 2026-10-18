extends SceneTree
var output: String
func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func run() -> void:
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	var app=entry.get_node_or_null("P4Play")
	if app==null:quit(1);return
	var expected: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(output.path_join("expected.json")))
	var state: Dictionary=app.model.snapshot
	app.paused=true
	var actors: Array=[]
	for a in state.actors:if not a.npc:actors.append({"id":a.id,"key":a.key,"x":a.x,"y":a.y,"hp":a.hp,"max_hp":a.max_hp})
	actors.sort_custom(func(a,b):return int(a.id)<int(b.id))
	var loot: Array=state.loot.duplicate();loot.sort_custom(func(a,b):return int(a.id)<int(b.id))
	var checks: Array=[{"name":"loaded committed revision","ok":state.loaded and int(state.revision)==int(expected.revision)},
		{"name":"complete original character restored","ok":state.character==expected.character},
		{"name":"living mob IDs/HP/coordinates restored without duplication","ok":actors==expected.actors},
		{"name":"natural floor loot IDs/amounts/coordinates restored","ok":loot==expected.loot}]
	var passed:=true
	for c in checks:if not c.ok:passed=false
	var f:=FileAccess.open(output.path_join("COLD.json"),FileAccess.WRITE);f.store_string(JSON.stringify({"status":"PASS" if passed else "FAIL","checks":checks,"state":state,"actors":actors,"loot":loot},"\t"));f.close()
	print("P4_COLD ",passed," ",checks)
	quit(0 if passed else 1)
