extends SceneTree
## Synthetic saves only: never locate or read a real user's save directory.
const Store=preload("res://storage/gameplay_store.gd")
const Game=preload("res://state/gameplay_state.gd")
const OWNER="local:v2-migration-test"
var checks: Array=[]
var failures:=0
var test_root:=""

func check(id: String, passed: bool, details: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed: failures+=1

func fixture_content() -> Dictionary:
	return {"profile":"V2_MIGRATION_SYNTHETIC","manifest_sha256":"a".repeat(64),"compatibility":{"schema":"1","rules":"baseline-rules","idset":"baseline-ids","map_geometry":"baseline-geometry"},
		"maps":{"map:town":{"width":12,"height":12,"blocked":[[0,0]],"exits":[],"spawns":[{"id":"spawn:rabbit1","monster_id":"monster:rabbit","x":3,"y":2}]}},
		"npcs":{"npc:inn":{"id":"npc:inn","map_id":"map:town","x":3,"y":3,"shop":{}}},
		"items":{"item:sword":{"slot":"weapon","stack_max":1,"durability":100},"item:acorn":{"stack_max":999,"durability":0}},
		"skills":{"skill:heal":{"kind":"heal","job":"도사","learn_level":5,"teacher_ids":["npc:inn"]}},
		"monsters":{"monster:rabbit":{"hp":6,"attack":1,"xp":1,"aggression":"retaliate","move_interval":1000.0,"attack_interval":1.0,"drops":[],"money_min":0,"money_max":0}},
		"start":{"map_id":"map:town","x":2,"y":2,"hp":50,"mp":30,"money":100,"starter_items":[{"item_id":"item:sword","quantity":1},{"item_id":"item:acorn","quantity":3}]},
		"gates":{"north":{"map_id":"map:town","x":2,"y":2}},"respawn":{"map_id":"map:town","x":2,"y":2},"xp_thresholds":[0,10,30,60,100],"config":{"inventory_slots":60}}

func expanded(old: Dictionary) -> Dictionary:
	var content:=old.duplicate(true)
	content.compatibility={"schema":"1","rules":"generation1-rules","idset":"generation1-ids","map_geometry":"generation1-geometry"}
	content.manifest_sha256="b".repeat(64)
	content.accepted_compatibility=[{"profile":old.profile,"compatibility":old.compatibility.duplicate(true),"manifest_sha256":old.manifest_sha256}]
	content.items["item:new"]={"stack_max":99,"durability":0}
	content.maps["map:town"].spawns.append({"id":"spawn:rabbit2","monster_id":"monster:rabbit","x":6,"y":6})
	content.xp_thresholds=[]
	for level in range(99): content.xp_thresholds.append(level*level*100)
	return content

func payload(content: Dictionary) -> Dictionary:
	var engine=Game.new()
	check("fixture_configures",engine.configure(content),engine.errors)
	check("fixture_character_created",engine.create_character("이전시험",OWNER).status=="OK")
	var candidate: Dictionary=engine.snapshot()
	# Deliberately serialize the original legacy top-level schema.
	candidate.erase("summons")
	for monster in candidate.monsters.values(): monster.erase("statuses")
	candidate.character.erase("advancement")
	candidate.character.erase("advancement_rank")
	candidate.character.erase("base_stats")
	candidate.character.erase("equipment_hp_bonus")
	candidate.character.erase("equipment_mp_bonus")
	candidate.loot=[{"loot_id":"loot:old","item_id":"item:acorn","quantity":2,"map_id":"map:town","x":4,"y":4}]
	return candidate

func put(path: String, text: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file:=FileAccess.open(path,FileAccess.WRITE)
	if file: file.store_string(text); file.close()

func archive_has(source: String, original: PackedByteArray) -> bool:
	for filename in DirAccess.get_files_at(source.get_base_dir()):
		if filename.begins_with(source.get_file()+".pre-migration-") and FileAccess.get_file_as_bytes(source.get_base_dir()+"/"+filename)==original: return true
	return false

func source_preserved_before_candidate(phase: String, path: String, original: PackedByteArray) -> void:
	if phase=="after_migration_source_preserved":
		check("source_archived_before_candidate_write",archive_has(path,original) and FileAccess.get_file_as_bytes(path)==original and not FileAccess.file_exists(path+".pending"))

func crash_phase(phase: String, wanted: String) -> void:
	if phase==wanted:
		print("V2_MIGRATION_CRASH="+phase)
		OS.kill(OS.get_process_id())

func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var old:=fixture_content()
	var current:=expanded(old)
	var store=Store.new()
	if "--child-crash" in args:
		var at:=args.find("--child-crash")
		var path: String=args[at+1]
		var read: Dictionary=store.read_game(path,OWNER,current)
		if read.status!="OK": quit(81); return
		var candidate: Dictionary=read.payload
		candidate.revision+=1; candidate.character.money+=1
		store.phase_observer=crash_phase.bind(args[at+2])
		store.write_game(path,candidate,OWNER,current)
		quit(82); return
	test_root="user://gameplay-p3/v2-migration-tests/"+str(Time.get_ticks_usec())+"/"
	var original_payload:=payload(old)
	var path:=test_root+"legacy.json"
	check("legacy_snapshot_saved",store.write_game(path,original_payload,OWNER,old).status=="SAVED")
	var raw:=FileAccess.get_file_as_bytes(path)
	var read: Dictionary=store.read_game(path,OWNER,current)
	check("exact_frozen_generation_allowed",read.status=="OK" and read.get("migration_required",false),read.get("reason"))
	if read.status!="OK": finish(args); return
	check("read_is_non_mutating",FileAccess.get_file_as_bytes(path)==raw and not archive_has(path,raw))
	for key in ["character","inventory","equipment","skills","loot","quests","buffs","cooldowns","stats","request_watermarks"]:
		check("preserve_legacy_"+key,store._canonical(read.payload[key])==store._canonical(original_payload[key]))
	check("preserve_existing_monster_exactly",store._canonical(read.payload.monsters["spawn:rabbit1"])==store._canonical(original_payload.monsters["spawn:rabbit1"]))
	check("new_generation_spawn_added_once",read.added_spawns==["spawn:rabbit2"] and read.payload.monsters.size()==2)
	store.phase_observer=source_preserved_before_candidate.bind(path,raw)
	var saved: Dictionary=store.write_game(path,read.payload,OWNER,current)
	store.phase_observer=Callable()
	check("same_revision_migration_commits",saved.status=="SAVED" and saved.reason=="MIGRATED",saved)
	check("legacy_source_archive_exact",archive_has(path,raw))
	check("ordinary_backup_still_original_bytes",FileAccess.get_file_as_bytes(path+".backup")==raw)
	var reread: Dictionary=store.read_game(path,OWNER,current)
	check("committed_current_envelope_needs_no_migration",reread.status=="OK" and not reread.migration_required and reread.payload.monsters.size()==2)
	check("original_reader_can_read_preserved_archive",store._decode(raw.get_string_from_utf8(),OWNER,old).status=="OK")
	var future: Dictionary=reread.payload.duplicate(true)
	future.revision+=1; future.character.money+=1
	check("later_save_accepts_legacy_backup",store.write_game(path,future,OWNER,current).status=="SAVED")
	check("backup_old_generation_archived_before_rotation",archive_has(path+".backup",raw))
	check("old_source_archive_survives_later_save",archive_has(path,raw))
	var optional: Dictionary=reread.payload.duplicate(true)
	optional["summons"]=[{"id":"summon:fixture","monster_id":"monster:rabbit","map_id":"map:town","x":2,"y":2,"expires_at":20.0,"attack_at":0.2,"power":3,"range":4,"interval":1.0}]
	optional.inventory[0]["identified"]=true
	optional["bank_inventory"]=[optional.inventory.pop_front()]
	optional.bank_inventory[0]["custom_name"]="시험창고검"
	optional.character["base_stats"]={"strength":5,"dexterity":5,"intelligence":5}
	optional.stats["new_counter"]=1
	var optional_path:=test_root+"optional-fields.json"
	check("new_optional_fields_save",store.write_game(optional_path,optional,OWNER,current).status=="SAVED")
	var optional_read: Dictionary=store.read_game(optional_path,OWNER,current)
	check("new_optional_fields_restore_exactly",optional_read.status=="OK" and store._canonical(optional_read.payload)==store._canonical(optional))
	var duplicated: Dictionary=optional.duplicate(true)
	duplicated.inventory.append(duplicated.bank_inventory[0].duplicate(true))
	check("bank_and_bag_duplicate_instance_rejected",store.write_game(test_root+"duplicate-bank.json",duplicated,OWNER,current).status!="SAVED")
	var bank_collision: Dictionary=optional.duplicate(true)
	bank_collision.loot[0].loot_id=bank_collision.bank_inventory[0].instance_id
	check("bank_and_loot_duplicate_instance_rejected",store.write_game(test_root+"bank-loot-collision.json",bank_collision,OWNER,current).status!="SAVED")
	# All refusals must leave the original primary byte-for-byte intact.
	for scenario in ["untrusted_idset","untrusted_manifest","unknown_schema","wrong_owner","bad_checksum","blocked_coordinate","revision_conflict"]:
		var refused_path: String=test_root+scenario+".json"
		put(refused_path,raw.get_string_from_utf8())
		var next:=current.duplicate(true)
		var owner:=OWNER
		var doc: Dictionary=JSON.parse_string(raw.get_string_from_utf8())
		match scenario:
			"untrusted_idset": doc.compatibility.idset="untrusted-idset"
			"untrusted_manifest": doc.manifest_sha256="c".repeat(64)
			"unknown_schema": doc.schema="baram.gameplay-save/999"
			"wrong_owner": owner="local:other"
			"bad_checksum": doc.sha256="0".repeat(64)
			"blocked_coordinate":
				next.maps["map:town"].blocked.append([2,2])
				next.start.x=5; next.respawn.x=5; next.gates.north.x=5
		if scenario in ["untrusted_idset","untrusted_manifest","unknown_schema"]:
			doc.erase("sha256"); put(refused_path,store._encode(doc))
		elif scenario=="bad_checksum": put(refused_path,JSON.stringify(doc))
		var before:=FileAccess.get_file_as_bytes(refused_path)
		var declined: Dictionary=store.read_game(refused_path,owner,next)
		if scenario=="revision_conflict":
			var conflict: Dictionary=declined.payload.duplicate(true)
			conflict.character.money+=1
			declined=store.write_game(refused_path,conflict,OWNER,next)
		var expected: String={"unknown_schema":"UNSUPPORTED_FORMAT","wrong_owner":"OWNER_MISMATCH","bad_checksum":"CHECKSUM_MISMATCH","revision_conflict":"REVISION_CONFLICT"}.get(scenario,"DEFERRED")
		check("refuse_"+scenario,declined.status==expected,declined)
		check("refusal_preserves_"+scenario,FileAccess.get_file_as_bytes(refused_path)==before and not archive_has(refused_path,before))
	# Explicit map transforms are supported; there is no inferred safe cell.
	var moved:=current.duplicate(true)
	moved.maps["map:shifted"]=moved.maps["map:town"]; moved.maps.erase("map:town")
	for spawn in moved.maps["map:shifted"].spawns: spawn.x+=1
	for npc in moved.npcs.values(): npc.map_id="map:shifted"; npc.x+=1
	for point in [moved.start,moved.respawn,moved.gates.north]: point.map_id="map:shifted"; point.x+=1
	moved.accepted_compatibility[0].map_transforms={"map:town":{"to_map_id":"map:shifted","dx":1,"dy":0}}
	var shifted: Dictionary=store._decode(raw.get_string_from_utf8(),OWNER,moved)
	check("explicit_map_transform_applied",shifted.status=="OK" and shifted.payload.character.map_id=="map:shifted" and shifted.payload.character.x==3,shifted.get("reason"))
	if shifted.status=="OK":
		check("explicit_transform_includes_loot_and_monster_home",shifted.payload.loot[0].x==5 and shifted.payload.monsters["spawn:rabbit1"].x==4 and shifted.payload.monsters["spawn:rabbit1"].spawn_x==4)
	# Backup recovery remains read-only, even if the backup itself needs migration.
	var recovery_path:=test_root+"recovery.json"
	store.write_game(recovery_path,original_payload,OWNER,old)
	var two:=original_payload.duplicate(true); two.revision+=1; two.character.money+=1
	store.write_game(recovery_path,two,OWNER,old)
	put(recovery_path,"{broken primary")
	var recovered: Dictionary=store.read_game(recovery_path,OWNER,current)
	check("legacy_backup_recovered_and_migrated_in_memory",recovered.status=="RECOVERED_BACKUP" and recovered.migration_required and recovered.payload.monsters.size()==2)
	check("recovery_read_preserves_broken_primary",FileAccess.get_file_as_string(recovery_path)=="{broken primary")
	var restored: Dictionary=recovered.payload.duplicate(true); restored.revision+=1
	check("explicit_save_repairs_after_backup_recovery",store.write_game(recovery_path,restored,OWNER,current).status=="SAVED")
	check("recovered_old_backup_archived",archive_has(recovery_path+".backup",raw))
	var broken_preserved:=false
	for filename in DirAccess.get_files_at(test_root):
		if filename.begins_with("recovery.json.corrupt-"): broken_preserved=FileAccess.get_file_as_string(test_root+filename)=="{broken primary"
	check("broken_primary_bytes_preserved",broken_preserved)
	# Actual process death, including the two new pre-candidate boundaries.
	for phase in Store.MIGRATION_PHASES+Store.PHASES:
		var crash_path: String=test_root+"crash-"+phase+".json"
		store.write_game(crash_path,original_payload,OWNER,old)
		store.write_game(crash_path,two,OWNER,old)
		var primary_bytes:=FileAccess.get_file_as_bytes(crash_path)
		var backup_bytes:=FileAccess.get_file_as_bytes(crash_path+".backup")
		var output: Array=[]
		var code:=OS.execute(OS.get_executable_path(),["--headless","--path",ProjectSettings.globalize_path("res://"),"--script",get_script().resource_path,"--","--child-crash",crash_path,phase],output,true)
		var after: Dictionary=store.read_game(crash_path,OWNER,current)
		check("actual_process_terminated_"+phase,code!=0 and str(output).contains("V2_MIGRATION_CRASH="+phase),code)
		check("atomic_restart_"+phase,after.status=="OK" and int(after.revision)==(3 if phase=="after_primary_replace" else 2),after.get("status"))
		check("source_archive_retained_"+phase,archive_has(crash_path+".backup",backup_bytes) and (phase=="after_migration_backup_preserved" or archive_has(crash_path,primary_bytes)))
	if "--baseline" in args and "--current" in args:
		test_runtime_definitions(args,store)
	finish(args)

func test_runtime_definitions(args: PackedStringArray, store: RefCounted) -> void:
	# The optional files contain only content definitions. Saved progress below
	# is newly created in this test's private synthetic namespace.
	var baseline_path: String=args[args.find("--baseline")+1]
	var current_path: String=args[args.find("--current")+1]
	var baseline: Variant=JSON.parse_string(FileAccess.get_file_as_string(baseline_path))
	var current: Variant=JSON.parse_string(FileAccess.get_file_as_string(current_path))
	check("runtime_definitions_are_dictionaries",typeof(baseline)==TYPE_DICTIONARY and typeof(current)==TYPE_DICTIONARY)
	if typeof(baseline)!=TYPE_DICTIONARY or typeof(current)!=TYPE_DICTIONARY: return
	var engine=Game.new()
	check("real_baseline_definitions_configure",engine.configure(baseline),engine.errors)
	if not engine.errors.is_empty(): return
	var created: Dictionary=engine.create_character("자료이전",OWNER)
	check("synthetic_character_using_real_baseline",created.status=="OK",created)
	if created.status!="OK": return
	var original: Dictionary=engine.snapshot()
	original.erase("summons"); original.character.erase("advancement"); original.character.erase("advancement_rank")
	original.character.erase("base_stats")
	original.character.erase("equipment_hp_bonus"); original.character.erase("equipment_mp_bonus")
	for monster in original.monsters.values(): monster.erase("statuses")
	var path:=test_root+"real-definitions-synthetic.json"
	var saved: Dictionary=store.write_game(path,original,OWNER,baseline)
	check("real_baseline_synthetic_saved",saved.status=="SAVED",saved)
	if saved.status!="SAVED": return
	var before:=FileAccess.get_file_as_bytes(path)
	var upgraded: Dictionary=store.read_game(path,OWNER,current)
	check("real_G1_accepts_exact_baseline_synthetic",upgraded.status=="OK" and upgraded.get("migration_required",false),upgraded.get("reason"))
	check("real_definition_read_retains_source",FileAccess.get_file_as_bytes(path)==before)
	if upgraded.status!="OK": return
	check("real_G1_character_stable_ID_and_cell",store._canonical(upgraded.payload.character)==store._canonical(original.character))
	var old_instances_preserved:=true
	for id in original.monsters:
		if store._canonical(upgraded.payload.monsters.get(id,{}))!=store._canonical(original.monsters[id]): old_instances_preserved=false
	check("real_G1_all_legacy_monsters_preserved",old_instances_preserved)
	var restored=Game.new()
	check("real_G1_definitions_configure",restored.configure(current),restored.errors)
	check("real_G1_synthetic_payload_restores",restored.restore(upgraded.payload).status=="OK")
	check("real_G1_migration_writes_atomically",store.write_game(path,restored.snapshot(),OWNER,current).status=="SAVED")
	check("real_G1_original_archive_exact",archive_has(path,before))

func finish(args: PackedStringArray) -> void:
	var report:={"schema":"baram.v2.save-migration-evidence/1","status":"PASS" if failures==0 else "FAIL","failures":failures,"checks":checks,"platform":OS.get_name(),"engine":Engine.get_version_info(),"test_root":test_root,"scope":"Synthetic old/new content generations with actual GameState, filesystem writes and process termination; no real user save or Android/Windows/authentication claim"}
	if "--report" in args:
		var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(report,"  ")+"\n"); file.close()
	print(JSON.stringify(report))
	quit(0 if failures==0 else 1)
