extends "res://../../tools/rebuild/v2/test_store_cold.gd"
## Reuse the original cold-store safety/timing cases with the exact G2
## 111-map, 1296-retained-monster earned save pair; G1 criteria are unchanged.
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
	check("full_g2_source_pair",content.maps.size()==111 and primary_document.payload.monsters.size()==1296 and backup_document.payload.monsters.size()==1296 and primary_document.owner==backup_document.owner)
	check("untouched_pair_has_distinct_prior_backup",primary_bytes!=backup_bytes and int(backup_document.revision)<int(primary_document.revision))
	var original_primary_sha: String=FileAccess.get_sha256(primary_path)
	var original_backup_sha: String=FileAccess.get_sha256(backup_path)
	var repeats: int=int(args[args.find("--repetitions")+1]) if "--repetitions" in args else 5
	check("repetition_count_bounded",repeats>=1 and repeats<=20,repeats)
	if failures==0:
		for iteration in range(repeats):timed_pair(iteration)
		if "--warm-backup-load" in args:explicit_load_warmup()
		if "--timing-only" not in args:
			ownership_and_revisions();external_backups();generation_and_eviction();migration_metadata()
	check("original_primary_never_modified",FileAccess.get_sha256(primary_path)==original_primary_sha)
	check("original_backup_never_modified",FileAccess.get_sha256(backup_path)==original_backup_sha)
	var report: Dictionary={"schema":"baram.b5.g2-store-cold/1","status":"PASS_OBSERVED_STORE_FIXTURE" if failures==0 else "FAIL","failures":failures,"checks":checks,"timings":timings,"timing_only":"--timing-only" in args,"source_store_sha256":FileAccess.get_sha256(source),"source_game_state_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"test_script_sha256":FileAccess.get_sha256(get_script().resource_path),"content_sha256":FileAccess.get_sha256(content_path),"original_primary_sha256":original_primary_sha,"original_backup_sha256":original_backup_sha,"isolated_test_root":root_path,"engine":Engine.get_version_info(),"platform":OS.get_name(),"scope":"Headless full-G2 isolated persistence fixtures. Timing uses exact supplied earned primary/backup bytes, production restore+50ms ticks, no state grants or edited timing payloads. Fresh store caches each repetition, existing primary is loaded while backup is cold. File-system/process CPU caches are not reset. Negative revision/corruption/migration cases intentionally change isolated fixture copies. No OS/rendered frame, native-device or completed30minute performance claim; no first-save latency threshold is inferred from fixture completion."}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size(),"timed_writes":timings.size()}))
	quit(0 if failures==0 else 1)

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
	var mask:=Marshalls.base64_to_raw(str(changed.maps[character.map_id].blocked_base64))
	mask[int(character.y)*int(changed.maps[character.map_id].width)+int(character.x)]=1
	changed.maps[character.map_id].blocked_base64=Marshalls.raw_to_base64(mask)
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


func explicit_load_warmup() -> void:
	for index in range(5):
		var path:=pair("explicit-load-"+str(index))
		var setup:=context(content)
		var store=setup.store
		var prepared: Dictionary=setup.content
		var began:=Time.get_ticks_usec()
		var loaded: Dictionary=store.read_game(path,owner,prepared,true)
		var load_ms:=float(Time.get_ticks_usec()-began)/1000.0
		check("explicit_load_succeeds_"+str(index),loaded.status=="OK",loaded.status)
		if loaded.status!="OK":continue
		var preparation: Dictionary=loaded.get("backup_preparation",{})
		check("explicit_load_reports_preparation_cost_"+str(index),preparation.get("status")=="OK" and float(preparation.get("duration_ms",-1))>=0 and load_ms>=float(preparation.get("duration_ms",-1)),preparation)
		check("explicit_load_warms_prior_backup_"+str(index),cached_text(store,backup_bytes.get_string_from_utf8()))
		check("explicit_load_preserves_exact_sources_"+str(index),FileAccess.get_file_as_bytes(path)==primary_bytes and FileAccess.get_file_as_bytes(path+".backup")==backup_bytes)
		var game=restored(loaded.payload,prepared)
		var payload:=next_tick(game)
		var input_sha: String=store._canonical(payload).sha256_text()
		began=Time.get_ticks_usec()
		var saved: Dictionary=store.write_game(path,payload,owner,prepared)
		var elapsed:=float(Time.get_ticks_usec()-began)/1000.0
		timings.append({"iteration":index,"phase":"explicit_load_warmed_backup","outer_write_ms":elapsed,"initial_primary_and_backup_load_ms":load_ms,"backup_preparation":preparation,"candidate_canonical_sha256":input_sha,"revision":payload.revision,"result":saved,"store_phases":store.last_timings.duplicate(true)})
		check("explicit_load_next_save_succeeds_"+str(index),saved.status=="SAVED",saved)
		check("explicit_load_next_save_exact_backup_"+str(index),FileAccess.get_file_as_bytes(path+".backup")==primary_bytes)
		if preparation.get("migration_required",false):check("explicit_load_does_not_skip_migration_archive_"+str(index),archive_has(path+".backup",backup_bytes))
		# Re-read the actual external backup bytes even after load prevalidated it.
		check("explicit_load_external_corruption_fixture_"+str(index),put(path+".backup","{torn backup".to_utf8_buffer()))
		var before:=FileAccess.get_file_as_bytes(path)
		var refused: Dictionary=store.write_game(path,next_tick(game),owner,prepared)
		check("explicit_load_never_trusts_changed_external_backup_"+str(index),refused.status=="EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_bytes(path)==before,refused)
