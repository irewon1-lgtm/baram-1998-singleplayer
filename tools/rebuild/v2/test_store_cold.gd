extends SceneTree
## Prepared for the cold metadata proposal; do not confuse a saved test script
## with execution evidence. Timing inputs are byte-identical earned primary /
## backup copies. Only production restore/tick advances timing candidates.
## Negative safety cases deliberately alter isolated fixtures, never originals.
const Game = preload("res://state/gameplay_state.gd")
var checks: Array=[]
var timings: Array=[]
var failures:=0
var root_path: String
var source: String
var content: Dictionary
var primary_bytes: PackedByteArray
var backup_bytes: PackedByteArray
var primary_document: Dictionary
var backup_document: Dictionary
var owner: String

func check(id: String, passed: bool, details: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed:
		failures+=1
		print("FAIL "+id+" "+str(details))

func put(path: String, bytes: PackedByteArray) -> bool:
	if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK: return false
	var file:=FileAccess.open(path,FileAccess.WRITE)
	if file==null:return false
	file.store_buffer(bytes);file.close()
	return FileAccess.get_file_as_bytes(path)==bytes

func pair(label: String) -> String:
	var path: String=root_path+label+".json"
	check(label+"_exact_primary_copy",put(path,primary_bytes))
	check(label+"_exact_prior_backup_copy",put(path+".backup",backup_bytes))
	return path

func context(definitions: Dictionary) -> Dictionary:
	var store=load(source).new()
	var prepared: Dictionary=store.prepare_content(definitions)
	check("private_generation_prepared",not prepared.is_empty())
	return {"store":store,"content":prepared}

func cached_text(store, text: String) -> bool:
	for entry in store._decoded_cache:
		if entry.owner==owner and entry.text==text:return true
	return false

func restored(payload: Dictionary, definitions: Dictionary):
	var game=Game.new()
	check("production_game_configures",game.configure(definitions),game.errors)
	var result: Dictionary=game.restore(payload)
	check("production_restore",result.status=="OK",result)
	return game

func next_tick(game) -> Dictionary:
	var previous: int=int(game.state.revision)
	var result: Dictionary=game.tick(0.05)
	check("production_50ms_tick_advances_revision",result.status=="OK" and int(game.state.revision)>previous,result)
	return game.snapshot()

func timed_pair(iteration: int) -> void:
	var path:=pair("timing-"+str(iteration))
	var setup:=context(content)
	var store=setup.store
	var prepared: Dictionary=setup.content
	var began:=Time.get_ticks_usec()
	var loaded: Dictionary=store.read_game(path,owner,prepared)
	var load_ms:=float(Time.get_ticks_usec()-began)/1000.0
	check("timing_primary_loaded",loaded.status=="OK" and not loaded.get("migration_required",true),loaded.status)
	if loaded.status!="OK":return
	check("timing_primary_warm_backup_still_cold",cached_text(store,primary_bytes.get_string_from_utf8()) and not cached_text(store,backup_bytes.get_string_from_utf8()))
	var game=restored(loaded.payload,prepared)
	for phase in ["first_cold_backup","next_warm_backup"]:
		var snapshot_started:=Time.get_ticks_usec()
		var payload:=next_tick(game)
		var tick_and_snapshot_ms:=float(Time.get_ticks_usec()-snapshot_started)/1000.0
		# _canonical is read-only and does not warm the monster/decode caches.
		var input_sha: String=store._canonical(payload).sha256_text()
		began=Time.get_ticks_usec()
		var saved: Dictionary=store.write_game(path,payload,owner,prepared)
		var elapsed:=float(Time.get_ticks_usec()-began)/1000.0
		timings.append({"iteration":iteration,"phase":phase,"outer_write_ms":elapsed,"tick_and_snapshot_ms":tick_and_snapshot_ms,"initial_primary_load_ms":load_ms,"candidate_canonical_sha256":input_sha,"revision":payload.revision,"result":saved,"store_phases":store.last_timings.duplicate(true)})
		check("timing_saved_"+phase,saved.status=="SAVED",saved)
		check("timing_backup_exact_previous_primary_"+phase,FileAccess.get_file_as_bytes(path+".backup")==primary_bytes if phase=="first_cold_backup" else store._read_one(path+".backup",owner,prepared).status=="OK")
	var read: Dictionary=store.read_game(path,owner,prepared)
	check("timing_full_roundtrip",read.status=="OK" and store._canonical(read.payload)==store._canonical(game.snapshot()))
	check("timing_cache_bounded",store._decoded_cache.size()<=store.DECODE_CACHE_LIMIT)

func ownership_and_revisions() -> void:
	var path:=pair("ownership")
	var setup:=context(content)
	var store=setup.store
	var prepared: Dictionary=setup.content
	var loaded: Dictionary=store.read_game(path,owner,prepared)
	check("ownership_primary_loaded",loaded.status=="OK")
	if loaded.status!="OK":return
	var metadata: Dictionary=store._read_one(path+".backup",owner,prepared,false,true)
	check("cold_metadata_omits_private_full_payload",metadata.status=="OK" and not metadata.has("payload") and not metadata.has("document"))
	var count: int=store._decoded_cache.size()
	metadata.revision=-17
	var again: Dictionary=store._read_one(path+".backup",owner,prepared,false,true)
	check("metadata_return_has_no_private_mutable_alias",again.status=="OK" and int(again.revision)==int(backup_document.revision))
	check("warm_full_decode_cache_not_reparsed_or_duplicated",store._decoded_cache.size()==count)
	var read: Dictionary=store.read_game(path+".backup",owner,prepared)
	var expected_money: int=int(read.payload.character.money)
	read.payload.character.money+=31;read.document.payload.character.money+=29
	read=store.read_game(path+".backup",owner,prepared)
	check("owned_cold_decode_public_payload_document_isolated",int(read.payload.character.money)==expected_money and int(read.document.payload.character.money)==expected_money)
	check("owner_gate_not_reused",store._read_one(path+".backup","local:cold-other",prepared,false,true).status=="OWNER_MISMATCH")
	var before:=FileAccess.get_file_as_bytes(path)
	var identical: Dictionary=store.write_game(path,loaded.payload,owner,prepared)
	check("same_revision_identical_materializes_and_compares_full_payload",identical.status=="SAVED" and identical.reason=="IDENTICAL_SNAPSHOT" and FileAccess.get_file_as_bytes(path)==before,identical)
	var conflicting: Dictionary=loaded.payload.duplicate(true)
	conflicting.character.money+=1 # Intentional same-revision negative fixture.
	var refused: Dictionary=store.write_game(path,conflicting,owner,prepared)
	check("same_revision_conflict_preserves_primary",refused.status=="REVISION_CONFLICT" and FileAccess.get_file_as_bytes(path)==before,refused)
	var stale: Dictionary=backup_document.payload.duplicate(true)
	refused=store.write_game(path,stale,owner,prepared)
	check("real_prior_backup_revision_stays_stale",int(stale.revision)<int(loaded.revision) and refused.status=="STALE_REVISION" and FileAccess.get_file_as_bytes(path)==before,refused)

func external_backups() -> void:
	for variation in ["bad_json","bad_checksum","valid_checksum_invalid_hp","wrong_owner"]:
		var path:=pair("external-"+variation)
		var setup:=context(content)
		var store=setup.store
		var prepared: Dictionary=setup.content
		var loaded: Dictionary=store.read_game(path,owner,prepared)
		if loaded.status!="OK":check("external_primary_load_"+variation,false,loaded);continue
		check("external_backup_warmed_"+variation,store._read_one(path+".backup",owner,prepared,false,true).status=="OK")
		var altered: Dictionary=backup_document.duplicate(true)
		var bytes: PackedByteArray
		match variation:
			"bad_json":bytes="{torn backup".to_utf8_buffer()
			"bad_checksum":altered.sha256="0".repeat(64);bytes=JSON.stringify(altered).to_utf8_buffer()
			"valid_checksum_invalid_hp":
				altered.erase("sha256");altered.payload.character.hp=int(altered.payload.character.hp_max)+1
				bytes=store._encode(altered).to_utf8_buffer()
			"wrong_owner":
				altered.erase("sha256");altered.owner="local:cold-other";altered.payload.character.owner_id=altered.owner
				bytes=store._encode(altered).to_utf8_buffer()
		check("external_backup_written_"+variation,put(path+".backup",bytes))
		var game=restored(loaded.payload,prepared)
		var refused: Dictionary=store.write_game(path,next_tick(game),owner,prepared)
		check("unknown_external_backup_fully_rechecked_"+variation,refused.status=="EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_bytes(path)==primary_bytes and FileAccess.get_file_as_bytes(path+".backup")==bytes and not FileAccess.file_exists(path+".pending"),refused)

func generation_and_eviction() -> void:
	var path:=pair("generation")
	var setup:=context(content)
	var store=setup.store
	var prepared: Dictionary=setup.content
	var loaded: Dictionary=store.read_game(path,owner,prepared)
	if loaded.status!="OK":check("generation_primary_load",false,loaded);return
	check("generation_backup_warm",store._read_one(path+".backup",owner,prepared,false,true).status=="OK")
	var changed: Dictionary=content.duplicate(true)
	var character: Dictionary=loaded.payload.character
	changed.maps[character.map_id].blocked.append([int(character.x),int(character.y)])
	# Same declared fingerprint is deliberate: content value/generation matching
	# must prevent a stale exact-text cache approval after nested definition edit.
	var prior_configurations: int=store.content_configurations
	var refused: Dictionary=store._read_one(path,owner,changed,false,true)
	check("same_manifest_changed_generation_never_approves_cached_cell",refused.status!="OK" and store.content_configurations>prior_configurations and FileAccess.get_file_as_bytes(path)==primary_bytes,refused)
	check("original_generation_can_revalidate",store.read_game(path,owner,prepared).status=="OK")
	var game=restored(loaded.payload,prepared)
	for index in range(6):
		var payload:=next_tick(game)
		var document: Dictionary=primary_document.duplicate(true)
		document.erase("sha256");document.payload=payload;document.revision=payload.revision
		var separate:=root_path+"eviction-"+str(index)+".json"
		check("eviction_fixture_written_"+str(index),put(separate,store._encode(document).to_utf8_buffer()))
		check("eviction_fixture_verified_"+str(index),store.read_game(separate,owner,prepared).status=="OK")
	check("full_decode_cache_remains_bounded_after_eviction",store._decoded_cache.size()<=store.DECODE_CACHE_LIMIT and not cached_text(store,primary_bytes.get_string_from_utf8()))
	var metadata: Dictionary=store._read_one(path,owner,prepared,false,true)
	check("evicted_original_revalidated_as_isolated_metadata",metadata.status=="OK" and int(metadata.revision)==int(primary_document.revision) and not metadata.has("payload") and not metadata.has("document"))

func archive_has(path: String, bytes: PackedByteArray) -> bool:
	for filename in DirAccess.get_files_at(path.get_base_dir()):
		if filename.begins_with(path.get_file()+".pre-migration-") and FileAccess.get_file_as_bytes(path.get_base_dir()+"/"+filename)==bytes:return true
	return false

func migration_metadata() -> void:
	var path:=pair("migration")
	var current: Dictionary=content.duplicate(true)
	current.compatibility.rules="cold_metadata_test_generation"
	current.manifest_sha256="9".repeat(64)
	current.accepted_compatibility.append({"profile":content.profile,"compatibility":content.compatibility.duplicate(true),"manifest_sha256":content.manifest_sha256})
	var setup:=context(current)
	var store=setup.store
	var prepared: Dictionary=setup.content
	var loaded: Dictionary=store.read_game(path,owner,prepared)
	check("exact_pinned_generation_migrates_without_grants",loaded.status=="OK" and loaded.get("migration_required",false),loaded.get("reason"))
	if loaded.status!="OK":return
	var metadata: Dictionary=store._read_one(path+".backup",owner,prepared,false,true)
	check("cold_backup_metadata_preserves_migration_flag",metadata.status=="OK" and metadata.get("migration_required",false) and not metadata.has("payload"),metadata)
	var saved: Dictionary=store.write_game(path,loaded.payload,owner,prepared)
	check("same_revision_migration_not_misclassified_identical",saved.status=="SAVED" and saved.reason=="MIGRATED",saved)
	check("both_exact_original_sources_archived",archive_has(path,primary_bytes) and archive_has(path+".backup",backup_bytes))
	var read: Dictionary=store.read_game(path,owner,prepared)
	check("migrated_public_read_no_longer_requires_migration",read.status=="OK" and not read.get("migration_required",true) and store._canonical(read.payload)==store._canonical(loaded.payload))
	var game=restored(read.payload,prepared)
	saved=store.write_game(path,next_tick(game),owner,prepared)
	check("later_legacy_backup_rotation_keeps_migration_archive",saved.status=="SAVED" and archive_has(path+".backup",primary_bytes) and archive_has(path+".backup",backup_bytes),saved)

func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	for required in ["--content","--primary","--backup","--report"]:
		if required not in args or args.find(required)+1>=args.size():push_error("Missing "+required);quit(2);return
	var content_path: String=args[args.find("--content")+1]
	var primary_path: String=args[args.find("--primary")+1]
	var backup_path: String=args[args.find("--backup")+1]
	source=args[args.find("--store-script")+1] if "--store-script" in args else "res://storage/gameplay_store.gd"
	content=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	primary_bytes=FileAccess.get_file_as_bytes(primary_path);backup_bytes=FileAccess.get_file_as_bytes(backup_path)
	primary_document=JSON.parse_string(primary_bytes.get_string_from_utf8());backup_document=JSON.parse_string(backup_bytes.get_string_from_utf8())
	owner=str(primary_document.owner)
	root_path="user://gameplay-p3/store-cold-tests/"+str(Time.get_ticks_usec())+"/"
	check("full_g1_source_pair",content.maps.size()==76 and primary_document.payload.monsters.size()==752 and backup_document.payload.monsters.size()==752 and primary_document.owner==backup_document.owner)
	check("untouched_pair_has_distinct_prior_backup",primary_bytes!=backup_bytes and int(backup_document.revision)<int(primary_document.revision))
	var original_primary_sha: String=FileAccess.get_sha256(primary_path)
	var original_backup_sha: String=FileAccess.get_sha256(backup_path)
	var repeats: int=int(args[args.find("--repetitions")+1]) if "--repetitions" in args else 5
	check("repetition_count_bounded",repeats>=1 and repeats<=20,repeats)
	if failures==0:
		for iteration in range(repeats):timed_pair(iteration)
		if "--timing-only" not in args:
			ownership_and_revisions();external_backups();generation_and_eviction();migration_metadata()
	check("original_primary_never_modified",FileAccess.get_sha256(primary_path)==original_primary_sha)
	check("original_backup_never_modified",FileAccess.get_sha256(backup_path)==original_backup_sha)
	var report: Dictionary={"schema":"baram.b5.store-cold-metadata/1","status":"PASS_OBSERVED_STORE_FIXTURE" if failures==0 else "FAIL","failures":failures,"checks":checks,"timings":timings,"timing_only":"--timing-only" in args,"source_store_sha256":FileAccess.get_sha256(source),"source_game_state_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"test_script_sha256":FileAccess.get_sha256(get_script().resource_path),"content_sha256":FileAccess.get_sha256(content_path),"original_primary_sha256":original_primary_sha,"original_backup_sha256":original_backup_sha,"isolated_test_root":root_path,"engine":Engine.get_version_info(),"platform":OS.get_name(),"scope":"Headless full-G1 isolated persistence fixtures. Timing uses exact supplied earned primary/backup bytes, production restore+50ms ticks, no state grants or edited timing payloads. Fresh store caches each repetition, existing primary is loaded while backup is cold. File-system/process CPU caches are not reset. Negative revision/corruption/migration cases intentionally change isolated fixture copies. No OS/rendered frame, native-device or completed30minute performance claim; no first-save latency threshold is inferred from fixture completion."}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size(),"timed_writes":timings.size()}))
	quit(0 if failures==0 else 1)
