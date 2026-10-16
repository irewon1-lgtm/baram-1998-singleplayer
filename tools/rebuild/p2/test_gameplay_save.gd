extends SceneTree
## Actual gameplay payload persistence tests; independent of natural-play claims.
const Store = preload("res://storage/gameplay_store.gd")
const Game = preload("res://state/gameplay_state.gd")
const OWNER := "local:save-test"
var checks: Array=[]
var test_root := ""
var failures := 0

func check(id: String, passed: bool, details: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed: failures+=1

func fixture_content() -> Dictionary:
	return {"profile":"KR_GUIDE_2001_WORKING_P3_TEST","manifest_sha256":"a".repeat(64),"compatibility":{"schema":"1","rules":"rules1","idset":"ids1","map_geometry":"geo1"},
		"maps":{"map:town":{"width":12,"height":12,"blocked":[[0,0]],"exits":[],"spawns":[{"id":"spawn:rabbit1","monster_id":"monster:rabbit","x":3,"y":2}]}},
		"npcs":{"npc:inn":{"id":"npc:inn","map_id":"map:town","x":3,"y":3,"shop":{}}},
		"items":{"item:sword":{"slot":"weapon","stack_max":1,"durability":100},"item:acorn":{"stack_max":999,"durability":0}},
		"skills":{"skill:heal":{"kind":"heal","job":"도사","learn_level":5,"teacher_ids":["npc:inn"]}},"monsters":{"monster:rabbit":{"hp":6,"attack":1,"xp":1,"aggression":"retaliate","move_interval":1000.0,"attack_interval":1.0,"drops":[],"money_min":0,"money_max":0}},
		"start":{"map_id":"map:town","x":2,"y":2,"hp":50,"mp":30,"money":100,"starter_items":[{"item_id":"item:sword","quantity":1},{"item_id":"item:acorn","quantity":3}]},
		"gates":{"north":{"map_id":"map:town","x":2,"y":2}},"respawn":{"map_id":"map:town","x":2,"y":2},"xp_thresholds":[0,10,30,60,100],"config":{"inventory_slots":60}}

func fixture(content: Dictionary) -> Dictionary:
	var game=Game.new()
	check("configure_real_game_state",game.configure(content),game.errors)
	check("create_real_game_payload",game.create_character("저장시험",OWNER).status=="OK")
	return game.snapshot()

func put(path: String,text: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file:=FileAccess.open(path,FileAccess.WRITE)
	if file: file.store_string(text);file.close()

func corrupt_phase(phase: String,wanted: String,path: String) -> void:
	if phase==wanted: put(path,"{torn write")

func crash_phase(phase: String,wanted: String) -> void:
	if phase==wanted:
		print("GAMEPLAY_CRASH_BOUNDARY="+phase)
		OS.kill(OS.get_process_id())

func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var content:=fixture_content()
	var store=Store.new()
	if "--child-crash" in args:
		var at:=args.find("--child-crash")
		var payload:=fixture(content)
		payload.revision=2
		payload.character.money=101
		store.phase_observer=crash_phase.bind(args[at+2])
		store.write_game(args[at+1],payload,OWNER,content)
		quit(82)
		return
	test_root="user://gameplay-p3/tests/"+str(Time.get_ticks_usec())+"/"
	var payload:=fixture(content)
	var before: String=store.base.canonical(payload)
	var path:=test_root+"actual.json"
	var first: Dictionary=store.write_game(path,payload,OWNER,content)
	check("first_snapshot_saved",first.status=="SAVED",first)
	check("writer_never_mutates_state",store.base.canonical(payload)==before)
	var read: Dictionary=store.read_game(path,OWNER,content)
	check("full_game_payload_roundtrip",read.status=="OK" and store.base.canonical(read.get("payload",{}))==before,read.status)
	check("actual_game_payload_size_bounded",first.get("bytes",Store.MAX_BYTES)>0 and first.get("bytes",Store.MAX_BYTES)<Store.MAX_BYTES,first.get("bytes"))
	var tick_game=Game.new()
	tick_game.configure(content)
	tick_game.create_character("시간시험",OWNER)
	tick_game.tick(0.05)
	var tick_snapshot: Dictionary=tick_game.snapshot()
	var tick_path:=test_root+"fractional-tick.json"
	check("fractional_actual_tick_snapshot_saved",store.write_game(tick_path,tick_snapshot,OWNER,content).status=="SAVED")
	var tick_read: Dictionary=store.read_game(tick_path,OWNER,content)
	check("fractional_actual_tick_exact_roundtrip",tick_read.status=="OK" and store.base.canonical(tick_read.get("payload",{}))==store.base.canonical(tick_snapshot))
	# Exact value observed in the first real GUI natural-journey save failure.
	# This is a serialization fixture, not a natural-progression state grant.
	var long_timer:=tick_snapshot.duplicate(true)
	long_timer.cooldowns["move"]=21.310000000000166
	var long_path:=test_root+"long-fractional-timer.json"
	var long_written: Dictionary=store.write_game(long_path,long_timer,OWNER,content)
	check("observed_long_fractional_timer_save_regression",long_written.status=="SAVED",long_written)
	var long_read: Dictionary=store.read_game(long_path,OWNER,content)
	check("microsecond_timer_representation_stable",long_read.status=="OK" and store._canonical(long_read.get("payload",{}))==store._canonical(long_timer))
	var changed_timer:=FileAccess.get_file_as_string(long_path).replace("21.31","21.32")
	put(long_path,changed_timer)
	check("changed_timer_checksum_rejected",store.read_game(long_path,OWNER,content).status=="CHECKSUM_MISMATCH")
	var pending_game=Game.new()
	pending_game.configure(content)
	pending_game.create_character("명중저장",OWNER)
	var attack: Dictionary=pending_game.command({"type":"attack","target_id":"spawn:rabbit1","request_id":"pending:1"})
	check("normal_command_creates_pending_attack",attack.status=="OK" and pending_game.state.pending_actions.size()==1)
	var pending_path:=test_root+"pending-action.json"
	check("pending_attack_snapshot_disk_saved",store.write_game(pending_path,pending_game.snapshot(),OWNER,content).status=="SAVED")
	var pending_read: Dictionary=store.read_game(pending_path,OWNER,content)
	var restored_game=Game.new()
	restored_game.configure(content)
	check("pending_attack_snapshot_disk_restored",pending_read.status=="OK" and restored_game.restore(pending_read.payload).status=="OK")
	restored_game.tick(0.3)
	var hit_hp: int=int(restored_game.state.monsters["spawn:rabbit1"].hp)
	check("saved_windup_applies_one_real_impact",hit_hp<6 and restored_game.state.pending_actions.filter(func(entry: Dictionary) -> bool: return entry.kind=="attack").is_empty(),{"monster_hp":hit_hp,"remaining_actions":restored_game.state.pending_actions})
	restored_game.tick(0.3)
	check("saved_windup_never_replays_second_impact",int(restored_game.state.monsters["spawn:rabbit1"].hp)==hit_hp)
	check("idempotent_snapshot_ack",store.write_game(path,payload,OWNER,content).reason=="IDENTICAL_SNAPSHOT")
	var original:=FileAccess.get_file_as_bytes(path)
	check("other_owner_read_refused",store.read_game(path,"local:other",content).status=="OWNER_MISMATCH")
	var other:=payload.duplicate(true);other.character.owner_id="local:other"
	check("other_owner_cannot_overwrite",store.write_game(path,other,"local:other",content).status=="EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_bytes(path)==original)
	var two:=payload.duplicate(true);two.revision=2;two.character.money=101
	check("second_revision_saved",store.write_game(path,two,OWNER,content).status=="SAVED")
	check("prior_backup_exact",FileAccess.get_file_as_bytes(path+".backup")==original)
	check("stale_revision_blocked",store.write_game(path,payload,OWNER,content).status=="STALE_REVISION")
	var conflicting:=two.duplicate(true);conflicting.character.money=102
	check("same_revision_conflict_blocked",store.write_game(path,conflicting,OWNER,content).status=="REVISION_CONFLICT")
	var cosmetic:=content.duplicate(true);cosmetic.manifest_sha256="b".repeat(64)
	check("icon_only_manifest_update_allowed",store.read_game(path,OWNER,cosmetic).status=="OK")
	for key in ["schema","rules","idset"]:
		var changed:=content.duplicate(true);changed.compatibility[key]="changed"
		check("incompatible_"+key+"_deferred",store.read_game(path,OWNER,changed).status=="DEFERRED")
	var geometry:=content.duplicate(true);geometry.compatibility.map_geometry="geo2"
	check("geometry_version_only_valid_coordinates_preserved",store.read_game(path,OWNER,geometry).status=="OK")
	geometry.maps["map:town"].blocked.append([2,2])
	geometry.start.x=3
	geometry.respawn.x=3
	geometry.gates.north.x=3
	var saved_bytes:=FileAccess.get_file_as_bytes(path)
	check("invalid_character_coordinate_deferred_no_teleport",store.read_game(path,OWNER,geometry).status=="DEFERRED" and FileAccess.get_file_as_bytes(path)==saved_bytes)
	var loot_payload:=two.duplicate(true)
	loot_payload.loot=[{"loot_id":"loot:test1","item_id":"item:acorn","quantity":7,"map_id":"map:town","x":4,"y":4}]
	var loot_path:=test_root+"geometry-loot.json"
	store.write_game(loot_path,payload,OWNER,content)
	store.write_game(loot_path,loot_payload,OWNER,content)
	var loot_geometry:=content.duplicate(true)
	loot_geometry.compatibility.map_geometry="geo2"
	loot_geometry.maps["map:town"].blocked.append([4,4])
	var loot_bytes:=FileAccess.get_file_as_bytes(loot_path)
	check("invalid_loot_coordinate_deferred_no_backup_rollback",store.read_game(loot_path,OWNER,loot_geometry).status=="DEFERRED" and FileAccess.get_file_as_bytes(loot_path)==loot_bytes)
	put(path,"{corrupted primary")
	read=store.read_game(path,OWNER,content)
	check("corrupt_primary_recovers_backup",read.status=="RECOVERED_BACKUP" and int(read.payload.revision)==1)
	check("recovery_does_not_rewrite_corrupt_source",FileAccess.get_file_as_string(path)=="{corrupted primary")
	check("explicit_save_repairs_preserving_corrupt_bytes",store.write_game(path,two,OWNER,content).status=="SAVED")
	var corrupt_exists:=false
	for filename in DirAccess.get_files_at(test_root):
		if filename.begins_with("actual.json.corrupt-"): corrupt_exists=FileAccess.get_file_as_string(test_root+filename)=="{corrupted primary"
	check("corrupt_copy_retained",corrupt_exists)
	for change in ["bad_item","bad_equipment","bad_owner","bad_hp","bad_hotkey","bad_spawn","bad_cooldown","bad_watermark","duplicate_request","bad_loot_collision","bad_pending_target"]:
		var candidate:=payload.duplicate(true)
		match change:
			"bad_item": candidate.inventory[0].item_id="item:absent"
			"bad_equipment": candidate.equipment.weapon="instance:absent"
			"bad_owner": candidate.character.owner_id="local:other"
			"bad_hp": candidate.character.hp=9999999
			"bad_hotkey": candidate.hotkeys["1"]="skill:missing"
			"bad_spawn": candidate.monsters["spawn:rabbit1"].spawn_x=99
			"bad_cooldown": candidate.cooldowns.attack=INF
			"bad_watermark": candidate.request_watermarks.stream=-1
			"duplicate_request": candidate.applied_request_ids=["test:1","test:1"]
			"bad_loot_collision": candidate.loot=[{"loot_id":candidate.inventory[0].instance_id,"item_id":"item:acorn","quantity":1,"map_id":"map:town","x":4,"y":4}]
			"bad_pending_target": candidate.pending_actions=[{"kind":"attack","target_id":"spawn:absent","map_id":"map:town","due":0.2}]
		check("invalid_"+change+"_not_saved",store.write_game(test_root+change+".json",candidate,OWNER,content).status!="SAVED")
	for phase in Store.PHASES:
		var fault_path: String=test_root+phase+".json"
		store.write_game(fault_path,payload,OWNER,content)
		store.fault_phase=phase
		var failed: Dictionary=store.write_game(fault_path,two,OWNER,content)
		store.fault_phase=""
		read=store.read_game(fault_path,OWNER,content)
		check("fault_not_falsely_saved_"+phase,failed.status!="SAVED",failed.status)
		check("fault_atomic_snapshot_"+phase,read.status=="OK" and int(read.payload.revision)==(2 if phase=="after_primary_replace" else 1))
	for phase in ["after_pending_write","after_backup_write"]:
		var torn_path: String=test_root+"torn-"+phase+".json"
		store.write_game(torn_path,payload,OWNER,content)
		var suffix: String=".pending" if phase=="after_pending_write" else ".backup.pending"
		store.phase_observer=corrupt_phase.bind(phase,torn_path+suffix)
		var failed: Dictionary=store.write_game(torn_path,two,OWNER,content)
		store.phase_observer=Callable()
		check("torn_write_verify_rejected_"+phase,failed.status=="VERIFY_FAILED" and store.read_game(torn_path,OWNER,content).payload.revision==1)
	put(test_root+"directory-blocker","ordinary file")
	check("filesystem_failure_is_not_saved",store.write_game(test_root+"directory-blocker/child.json",payload,OWNER,content).status=="WRITE_FAILED")
	check("outside_gameplay_root_rejected",store.write_game("user://not-gameplay/save.json",payload,OWNER,content).status=="UNSAFE_PATH")
	var oversize_path:=test_root+"oversize.json"
	put(oversize_path," ".repeat(Store.MAX_BYTES+1))
	check("oversize_file_rejected_before_json",store.read_game(oversize_path,OWNER,content).status=="SAVE_SIZE_LIMIT")
	check("deep_json_rejected_before_parse",store._decode("[".repeat(25)+"]".repeat(25),OWNER,content).status=="SAVE_DEPTH_LIMIT")
	for suffix in ["",".pending",".backup",".backup.pending"]:
		var link_path:=test_root+"link"+str(suffix.length())+".json"
		var target:=test_root+"unrelated"+str(suffix.length())+".txt"
		put(target,"never alter")
		var directory=store.base.native_directory(test_root)
		var linked: Error=directory.create_link(ProjectSettings.globalize_path(target),ProjectSettings.globalize_path(link_path+suffix))
		if linked==OK and directory.is_link(ProjectSettings.globalize_path(link_path+suffix)):
			check("symlink_refused_"+suffix,store.write_game(link_path,payload,OWNER,content).status=="UNSAFE_PATH" and FileAccess.get_file_as_string(target)=="never alter")
		else:
			checks.append({"id":"symlink_refused_"+suffix,"status":"NOT_RUN","details":"Platform cannot create actual link fixture; never count protection PASS"})
	# Separate child-process termination verifies the same pending/replace boundaries.
	for phase in Store.PHASES:
		var crash_path: String=test_root+"crash-"+phase+".json"
		store.write_game(crash_path,payload,OWNER,content)
		var output: Array=[]
		var exit_code:=OS.execute(OS.get_executable_path(),["--headless","--path",ProjectSettings.globalize_path("res://"),"--script",get_script().resource_path,"--","--child-crash",crash_path,phase],output,true)
		read=store.read_game(crash_path,OWNER,content)
		check("process_terminated_at_"+phase,exit_code!=0 and str(output).contains("GAMEPLAY_CRASH_BOUNDARY="+phase),exit_code)
		check("restart_after_termination_"+phase,read.status=="OK" and int(read.payload.revision)==(2 if phase=="after_primary_replace" else 1))
	var receipt:={"schema":"baram.gameplay-save-evidence/1","platform":OS.get_name(),"engine":Engine.get_version_info(),"checks":checks,"failures":failures,"status":"PASS" if failures==0 else "FAIL","actual_initial_save_bytes":first.get("bytes",0),"cap_bytes":Store.MAX_BYTES,"test_root":test_root,"scope":"Actual GameState payload using fixture definitions; not natural progression, nativeWindows, Android or authentication proof"}
	var output_path:=""
	if "--report" in args: output_path=args[args.find("--report")+1]
	if not output_path.is_empty():
		var file:=FileAccess.open(output_path,FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(receipt,"  ")+"\n");file.close()
	print(JSON.stringify(receipt))
	quit(0 if failures==0 else 1)
