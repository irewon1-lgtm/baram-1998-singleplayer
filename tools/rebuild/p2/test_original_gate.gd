extends SceneTree
## Failure-gate tests for the new original consumer. No historical fixtures.
const Content = preload("res://content/private_content.gd")
var records: Array = []

func put(path: String, text: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path,FileAccess.WRITE)
	assert(file!=null)
	file.store_string(text)
	file.close()

func trial(root: String, name: String, manifest: Dictionary) -> void:
	var dir := root.path_join(name)
	put(dir.path_join("runtime.json"),JSON.stringify(manifest))
	var consumer = Content.new()
	var accepted: bool = consumer.open_generation(dir)
	records.append({"id":name,"status":"FAIL" if accepted else "PASS","rejection_errors":consumer.errors,"meaning":"Invalid generation was refused; not a data PASS"})

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size()!=2:
		quit(2)
		return
	var root := args[0]
	var output := args[1]
	var schema := "baram.work.p2.runtime/1"
	trial(root,"zero_required_inputs",{"schema":schema,"files":[]})
	trial(root,"wrong_schema",{"schema":"wrong","files":[{}]})
	trial(root,"missing_hash_target",{"schema":schema,"files":[{"path":"absent.png","sha256":"a".repeat(64)}]})
	put(root.path_join("tampered/maps/index.json"),"{}")
	trial(root,"tampered",{"schema":schema,"files":[{"path":"maps/index.json","sha256":"b".repeat(64)}]})
	trial(root,"path_traversal",{"schema":schema,"files":[{"path":"../elsewhere.png","sha256":"a".repeat(64)}]})
	var empty := root.path_join("empty_map_graph")
	put(empty.path_join("maps/index.json"),'{"maps":[]}')
	put(empty.path_join("kr491/kr491_runtime.json"),'{"parts":{},"effects":[],"sounds":[]}')
	put(empty.path_join("work_batch_policy.json"),"{}")
	var files: Array = []
	for path in ["maps/index.json","kr491/kr491_runtime.json","work_batch_policy.json"]:
		files.append({"path":path,"sha256":FileAccess.get_sha256(empty.path_join(path))})
	trial(root,"empty_map_graph",{"schema":schema,"files":files})
	var consumer = Content.new()
	var traversal_texture: Texture2D = consumer.texture("../missing.png")
	records.append({"id":"selected_texture_traversal","status":"PASS" if traversal_texture==null and not consumer.errors.is_empty() else "FAIL"})
	var failures := records.filter(func(r: Dictionary) -> bool: return r.status=="FAIL")
	put(output,JSON.stringify({"schema":"baram.work.p2.original-gates/1","checks":records,"failures":failures.size(),"real_original_runtime_scope":"Separate platform receipts"},"  ")+"\n")
	print("P2_ORIGINAL_GATE checks=%s failures=%s" % [records.size(),failures.size()])
	quit(0 if failures.is_empty() else 1)
