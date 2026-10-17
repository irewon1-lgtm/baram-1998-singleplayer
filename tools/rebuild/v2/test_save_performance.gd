extends SceneTree
## Same-input full G1 persistence microbenchmark, never a device/frame-rate claim.
const Game = preload("res://state/gameplay_state.gd")
var samples: Dictionary={}
var write_phases: Array=[]
var checks: Array=[]
var failures:=0
func check(id: String, passed: bool, details: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed: failures+=1
func measure(key: String, action: Callable) -> Variant:
	var began:=Time.get_ticks_usec()
	var output: Variant=action.call()
	if not samples.has(key): samples[key]=[]
	samples[key].append(float(Time.get_ticks_usec()-began)/1000.0)
	return output
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var content_path: String=args[args.find("--content")+1]
	var content: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	var script_path: String=args[args.find("--store-script")+1] if "--store-script" in args else "res://storage/gameplay_store.gd"
	var store=load(script_path).new()
	var game=Game.new()
	check("full_g1_configures",game.configure(content),game.errors)
	check("full_g1_new_character",game.create_character("저장계측","local:perf").status=="OK")
	var payload: Dictionary=game.snapshot()
	var prepare_ms := 0.0
	var mutable_original: Dictionary=content
	if "--prepared-content" in args:
		var started := Time.get_ticks_usec()
		content = store.prepare_content(content)
		prepare_ms = float(Time.get_ticks_usec()-started)/1000.0
		check("caller_generation_keeps_mutability",not mutable_original.is_read_only() and not mutable_original.maps.is_read_only())
		check("private_generation_prepared",not content.is_empty() and content.is_read_only() and content.maps.is_read_only() and content.maps[payload.character.map_id].blocked.is_read_only())
	var path: String="user://gameplay-p3/save-performance/"+str(Time.get_ticks_usec())+"/candidate.json"
	for iteration in range(4):
		var valid: Dictionary=measure("validate_ms",func() -> Dictionary: return store.validate_payload(payload,"local:perf",content))
		check("validate_"+str(iteration),valid.status=="OK",valid.status)
		payload.revision+=1
		payload.character.money+=1
		var written: Dictionary=measure("write_ms",func() -> Dictionary: return store.write_game(path,payload,"local:perf",content))
		if "last_timings" in store: write_phases.append(store.last_timings.duplicate(true))
		check("write_"+str(iteration),written.status=="SAVED",written.status)
		var read: Dictionary=measure("read_ms",func() -> Dictionary: return store.read_game(path,"local:perf",content))
		check("read_"+str(iteration),read.status=="OK" and store._canonical(read.payload)==store._canonical(payload),read.status)
	var original_money: int=int(payload.character.money)
	var first_read: Dictionary=store.read_game(path,"local:perf",content)
	first_read.payload.character.money+=11
	first_read.document.payload.character.money+=7
	var second_read: Dictionary=store.read_game(path,"local:perf",content)
	check("cached_read_has_no_mutable_payload_alias",int(second_read.payload.character.money)==original_money)
	check("cached_document_has_no_mutable_alias",int(second_read.document.payload.character.money)==original_money)
	var raw := FileAccess.get_file_as_string(path)
	var altered := raw.replace('"money":'+str(original_money), '"money":'+str(original_money+17))
	var altered_file := FileAccess.open(path,FileAccess.WRITE)
	altered_file.store_string(altered);altered_file.close()
	check("changed_disk_bytes_bypass_valid_cache",store._read_one(path,"local:perf",content).status=="CHECKSUM_MISMATCH")
	var restored_file := FileAccess.open(path,FileAccess.WRITE)
	restored_file.store_string(raw);restored_file.close()
	check("cached_owner_is_never_reused_for_other_owner",store.read_game(path,"local:other",content).status=="OWNER_MISMATCH")
	# The exact same mutable Dictionary retains its manifest but changes geometry.
	# A manifest/object-identity cache must never approve stale cells/definitions.
	var changed: Dictionary=content.duplicate(true)
	check("warm_valid_cache",store.validate_payload(payload,"local:perf",changed).status=="OK")
	var c: Dictionary=payload.character
	changed.maps[c.map_id].blocked.append([int(c.x),int(c.y)])
	if changed.start.map_id==c.map_id and int(changed.start.x)==int(c.x) and int(changed.start.y)==int(c.y):
		changed.start.x=int(changed.start.x)+1
	check("same_manifest_nested_mutation_not_approved",store.validate_payload(payload,"local:perf",changed).status!="OK")
	var nested: Dictionary={}
	store.phase_observer=func(phase: String) -> void:
		if phase=="after_pending_write":
			var next: Dictionary=payload.duplicate(true)
			next.revision+=2
			nested.result=store.write_game(path,next,"local:perf",content)
	var outer: Dictionary=payload.duplicate(true)
	outer.revision+=1
	var outer_saved: Dictionary=store.write_game(path,outer,"local:perf",content)
	store.phase_observer=Callable()
	check("nested_save_rejected_before_replacing_newer_revision",outer_saved.status=="SAVED" and nested.get("result",{}).get("status")=="BUSY" and store.read_game(path,"local:perf",content).payload.revision==outer.revision)
	var invalid: Dictionary=payload.duplicate(true)
	invalid.character.hp=int(invalid.character.hp_max)+1
	check("warm_content_still_validates_mutable_state",store.validate_payload(invalid,"local:perf",content).status!="OK")
	var report: Dictionary={"schema":"baram.v2.save-performance/1","platform":OS.get_name(),"engine":Engine.get_version_info(),"scope":"Headless Linux full G1 same-input save pipeline; synthetic newly-created character, no FPS/device/human-play claim","content_file_sha256":FileAccess.get_sha256(content_path),"store_file_sha256":FileAccess.get_sha256(script_path),"engine_file_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"maps":content.maps.size(),"monster_instances":payload.monsters.size(),"items":content.items.size(),"prepared_content": "--prepared-content" in args,"prepare_ms":prepare_ms,"content_configurations":store.get("content_configurations"),"samples":samples,"write_phases":write_phases,"checks":checks,"failures":failures,"status":"PASS" if failures==0 else "FAIL"}
	if "--report" in args:
		var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify(report))
	quit(0 if failures==0 else 1)
