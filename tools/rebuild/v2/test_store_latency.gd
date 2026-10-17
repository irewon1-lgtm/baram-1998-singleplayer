extends SceneTree
## Same naturally earned save, full G1, synchronous persistence CPU probe.
## This isolates store cost; it is not OS play or a frame/device acceptance test.
var checks: Array=[]
var failures:=0
func check(id: String, passed: bool, detail: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","detail":detail})
	if not passed: failures+=1
func pct(values: Array, fraction: float) -> float:
	var ordered:=values.duplicate();ordered.sort()
	return float(ordered[mini(ordered.size()-1,int(ceil(fraction*ordered.size()))-1)]) if not ordered.is_empty() else -1.0
func put(path: String, value: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file:=FileAccess.open(path,FileAccess.WRITE)
	if file:file.store_string(value);file.close()
func safety(store, content: Dictionary, original: Dictionary, owner: String, path: String) -> void:
	var payload: Dictionary=original.duplicate(true)
	var id: String=str(payload.monsters.keys()[0])
	check("semantic_cache_warm",store.validate_payload(payload,owner,content).status=="OK")
	for variation in ["spawn_x","generation","alive","aggro","id","timer_negative","timer_string","hp","status","stringname_key","stringname_value"]:
		var changed: Dictionary=payload.duplicate(true)
		match variation:
			"spawn_x": changed.monsters[id].spawn_x=999999
			"generation": changed.monsters[id].generation=-1
			"alive": changed.monsters[id].alive=1
			"aggro": changed.monsters[id].aggro=0
			"id": changed.monsters[id].id="spawn:other"
			"timer_negative": changed.monsters[id].respawn_at=-0.01
			"timer_string": changed.monsters[id].ai_at="0"
			"hp": changed.monsters[id].hp=9999999
			"status": changed.monsters[id].statuses={"bad":{"expires_at":-1}}
			"stringname_key": changed.monsters[id].erase("hp");changed.monsters[id][StringName("hp")]=payload.monsters[id].hp
			"stringname_value": changed.monsters[id].monster_id=StringName(changed.monsters[id].monster_id)
		check("warm_record_rejects_"+variation,store.validate_payload(changed,owner,content).status!="OK")
		check("valid_record_after_rejected_"+variation,store.validate_payload(payload,owner,content).status=="OK")
	var changed_content: Dictionary=content.duplicate(true)
	changed_content.monsters[payload.monsters[id].monster_id].hp=1
	var hp_changed: Dictionary=payload.duplicate(true)
	hp_changed.monsters[id].hp=2;hp_changed.monsters[id].alive=true
	check("warm_semantics_invalidated_by_definition_generation",store.validate_payload(hp_changed,owner,changed_content).status!="OK")
	check("original_generation_remains_valid",store.validate_payload(payload,owner,content).status=="OK")
	payload.revision+=1
	check("lazy_first_committed",store.write_game(path,payload,owner,content).status=="SAVED")
	check("committed_cache_defers_full_parse",store._decoded_cache[0].decoded.is_empty())
	payload.revision+=1;payload.character.money+=1
	check("lazy_metadata_next_revision",store.write_game(path,payload,owner,content).status=="SAVED")
	check("rotation_does_not_materialize_previous_payload",store._decoded_cache[0].decoded.is_empty() and store._decoded_cache[1].decoded.is_empty())
	var read: Dictionary=store.read_game(path,owner,content)
	check("lazy_read_materializes_full_canonical_payload",read.status=="OK" and store._canonical(read.payload)==store._canonical(payload))
	read.payload.character.money+=19;read.document.payload.character.money+=27
	read=store.read_game(path,owner,content)
	check("lazy_read_payload_and_document_isolated",read.payload.character.money==payload.character.money and read.document.payload.character.money==payload.character.money)
	check("same_revision_exact_snapshot_still_identical",store.write_game(path,payload,owner,content).get("reason")=="IDENTICAL_SNAPSHOT")
	var unchanged:=FileAccess.get_file_as_bytes(path)
	var conflict: Dictionary=payload.duplicate(true);conflict.character.money+=1
	check("same_revision_changed_payload_still_conflicts",store.write_game(path,conflict,owner,content).status=="REVISION_CONFLICT" and FileAccess.get_file_as_bytes(path)==unchanged)
	var corrupt_document: Dictionary=JSON.parse_string(unchanged.get_string_from_utf8());corrupt_document.erase("sha256")
	corrupt_document.payload.monsters[id].hp=9999999
	put(path,store._encode(corrupt_document))
	check("external_rechecks_semantics_even_with_valid_checksum",store._read_one(path,owner,content).status=="INVALID_STATE")
	put(path,unchanged.get_string_from_utf8())
	check("external_other_owner_never_reuses_trust",store.read_game(path,"local:other",content).status=="OWNER_MISMATCH")
	payload.revision+=1
	var pinned_revision: int=payload.revision
	store.phase_observer=func(phase: String) -> void:
		if phase=="after_pending_write":payload.revision+=10;payload.character.money+=100
	var saved: Dictionary=store.write_game(path,payload,owner,content)
	store.phase_observer=Callable()
	var pinned: Dictionary=store.read_game(path,owner,content)
	check("observer_mutation_cannot_change_committed_revision_metadata",saved.status=="SAVED" and saved.revision==pinned_revision and pinned.status=="OK" and pinned.revision==pinned_revision and pinned.payload.revision==pinned_revision)
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var content_path: String=args[args.find("--content")+1]
	var source: String=args[args.find("--store-script")+1]
	var save_path: String=args[args.find("--earned-save")+1]
	var content: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	var document: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(save_path))
	var payload: Dictionary=document.payload
	var owner: String=document.owner
	var store=load(source).new()
	content=store.prepare_content(content)
	check("full_g1_prepared",not content.is_empty() and content.maps.size()==76 and payload.monsters.size()==752)
	check("earned_save_semantically_valid",store.validate_payload(payload,owner,content).status=="OK")
	var path: String="user://gameplay-p3/store-latency/"+str(Time.get_ticks_usec())+".json"
	if "--safety-only" in args:
		safety(store,content,payload,owner,path)
		var report: Dictionary={"schema":"baram.b5.store-latency-cache-safety/1","scope":"Full G1 earned-save fixture copied to isolated test namespace; warm-record mutation, definition invalidation, deferred parse, read isolation, revision conflict, external checksum/semantic verification and observer mutation; no OS/device proof","status":"PASS" if failures==0 else "FAIL","failures":failures,"checks":checks,"store_sha256":FileAccess.get_sha256(source)}
		var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
		if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
		print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size()}));quit(0 if failures==0 else 1);return
	var ids: Array=payload.monsters.keys()
	var samples: Array=[]
	for iteration in range(67):
		payload.revision+=1
		# Exact same controlled small activity in both candidates. No state is
		# imported back to the real earned-save directory or used as play proof.
		for index in range(16):payload.monsters[ids[index]].ai_at+=0.05
		var began:=Time.get_ticks_usec()
		var saved: Dictionary=store.write_game(path,payload,owner,content)
		var elapsed:=float(Time.get_ticks_usec()-began)/1000.0
		check("saved_"+str(iteration),saved.status=="SAVED",saved.status)
		if iteration>=3:samples.append({"outer_ms":elapsed,"phases":store.last_timings.duplicate(true)})
	var loaded: Dictionary=store.read_game(path,owner,content)
	check("full_payload_roundtrip",loaded.status=="OK" and store._canonical(loaded.payload)==store._canonical(payload))
	var durations: Array=[]
	var phase_values: Dictionary={}
	for sample in samples:
		durations.append(sample.outer_ms)
		for key in sample.phases:
			if not phase_values.has(key):phase_values[key]=[]
			phase_values[key].append(sample.phases[key])
	var phases: Dictionary={}
	for key in phase_values:phases[key]={"p50":pct(phase_values[key],0.5),"p95":pct(phase_values[key],0.95),"max":pct(phase_values[key],1.0)}
	var report: Dictionary={"schema":"baram.b5.store-latency/1","status":"PASS_PROBE_COMPLETED" if failures==0 else "FAIL","scope":"Linux headless Godot same full G1 naturally earned-save fixture, 3 warmup+64 synchronous writes, 16 monster timer mutations per iteration; store causal CPU comparison only, no frame/OS/device acceptance","failures":failures,"checks":checks,"platform":OS.get_name(),"engine":Engine.get_version_info(),"store_sha256":FileAccess.get_sha256(source),"game_state_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"content_sha256":FileAccess.get_sha256(content_path),"earned_save_sha256":FileAccess.get_sha256(save_path),"samples":samples,"outer_ms":{"p50":pct(durations,0.5),"p95":pct(durations,0.95),"max":pct(durations,1.0)},"phase_summary":phases}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify({"status":report.status,"failures":failures,"outer_ms":report.outer_ms,"phases":phases}))
	quit(0 if failures==0 else 1)
