extends RefCounted
## Executable, synthetic-fixture tests; no original saves or historical claims.
const Store = preload("res://storage/save_store.gd")
const OWNER = "local-account:fixture-001"
var checks: int = 0
var failures: int = 0
var records: Array = []
var store = Store.new()
var test_root: String
var process_runner: Callable
var emit_records: bool = true

func catalog() -> Dictionary:
	return {"profile": "synthetic-storage-fixture-v1", "manifest_sha256": "a".repeat(64), "maps": {"fixture-map:plain": {"version": "synthetic-map-v1", "width": 12, "height": 10, "blocked": [[1, 1]]}}, "items": {"fixture-item:sword": {"slot": "weapon"}, "fixture-item:coat": {"slot": "armor"}, "fixture-item:rice": {"slot": ""}}, "skills": {"fixture-skill:display-only": {}}}

func fixture(revision: int = 1) -> Dictionary:
	return {"meta": {"schema_id": Store.SCHEMA_ID, "schema_version": 1, "content_profile": "synthetic-storage-fixture-v1", "content_manifest_sha256": "a".repeat(64), "build_id": "p2-fixture-only-1", "owner_id": OWNER, "character_id": "fixture-character:001", "revision": revision}, "payload": {"character": {"id": "fixture-character:001", "name": "가람하늘", "level": 1, "hp": 25, "hp_max": 25, "position": {"map_id": "fixture-map:plain", "map_version": "synthetic-map-v1", "x": 4, "y": 3}}, "inventory": [{"instance_id": "fixture-instance:sword-01", "item_id": "fixture-item:sword", "quantity": 1}, {"instance_id": "fixture-instance:coat-01", "item_id": "fixture-item:coat", "quantity": 1}], "equipment": {"weapon": "fixture-instance:sword-01", "armor": "fixture-instance:coat-01"}, "skills": ["fixture-skill:display-only"], "loot": [{"loot_id": "fixture-loot:001", "item_id": "fixture-item:rice", "quantity": 7, "position": {"map_id": "fixture-map:plain", "map_version": "synthetic-map-v1", "x": 8, "y": 6}}]}}

func check(label: String, condition: bool, detail: Variant = "") -> void:
	checks += 1
	if not condition:
		failures += 1
	var record: Dictionary = {"test": label, "status": "PASS" if condition else "FAIL", "detail": detail}
	records.append(record)
	if emit_records:
		print(JSON.stringify(record))

func put(path: String, text: String) -> bool:
	if store._path_has_link(path):
		check("fixture_output_path_link", false, path)
		return false
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		check("fixture_output_access", false, path)
		return false
	file.store_string(text)
	file.flush()
	var error: Error = file.get_error()
	file.close()
	if error != OK or FileAccess.get_file_as_string(path) != text:
		check("fixture_output_write_verify", false, path)
		return false
	return true

func fresh(name: String) -> String:
	var directory: String = test_root.path_join(name)
	DirAccess.make_dir_recursive_absolute(directory)
	return directory.path_join("character.json")

func subprocess(arguments: Array) -> Dictionary:
	return process_runner.call(arguments)

func corrupt_written_phase(phase: String, expected_phase: String, path: String) -> void:
	if phase == expected_phase:
		put(path, "{partial write")

func skip(label: String, reason: String) -> void:
	var record: Dictionary = {"test": label, "status": "NOT_RUN", "detail": reason}
	records.append(record)
	if emit_records:
		print(JSON.stringify(record))

func summary_snapshot() -> Dictionary:
	return {"schema": "baram.p2.save-test-results/1", "fixture_kind": "SYNTHETIC_NO_HISTORICAL_ACCURACY_CLAIM", "engine": Engine.get_version_info(), "os": OS.get_name(), "checks": checks, "failures": failures, "status": "PASS" if failures == 0 else "FAIL", "tests": records}

func finalize_results() -> Dictionary:
	var summary: Dictionary = summary_snapshot()
	# Output failure is itself a failed check. Rebuild scalars AFTER the write
	# attempt so returned status/exit count cannot retain the pre-write PASS.
	put(test_root.path_join("results.json"), JSON.stringify(summary, "\t"))
	summary = summary_snapshot()
	if emit_records:
		print("P2_SAVE_SUMMARY=" + JSON.stringify({"checks": checks, "failures": failures, "status": summary.status}))
	return summary

func run(output_directory: String, child_runner: Callable = Callable()) -> Dictionary:
	test_root = output_directory
	process_runner = child_runner
	checks = 0
	failures = 0
	records = []
	DirAccess.make_dir_recursive_absolute(test_root)
	run_tests()
	return finalize_results()

func run_tests() -> void:
	var cat: Dictionary = catalog()
	var state: Dictionary = fixture()
	var original: String = store.canonical(state)
	check("fixture_deep_validation", store.validate(state, OWNER, cat).status == "OK")
	check("canonical_json_independent_key_numeric_example", store.canonical({"z": [1.0, "한글"], "a": 2}) == '{"a":2,"z":[1,"한글"]}')
	var encoded: String = store.encode(state)
	var decoded: Dictionary = store.decode(encoded, OWNER, cat)
	check("korean_ids_equipment_skills_coordinates_loot_roundtrip", decoded.status == "OK" and store.canonical(decoded.state) == original)
	check("checksum_excludes_only_self_field", JSON.parse_string(encoded).sha256 == original.sha256_text())
	check("fixture_decoding_does_not_mutate_source", store.canonical(state) == original)
	var path: String = fresh("roundtrip")
	check("first_save", store.write_state(path, state, OWNER, cat).status == "SAVED")
	var first_bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
	var child: Dictionary = {}
	if process_runner.is_valid():
		child = subprocess(["--child-read", path, 1])
		check("fresh_process_restart_reads_same_state", child.exit_code == 0, child)
	else:
		skip("fresh_process_restart_reads_same_state", "No child process driver supplied on this platform")
	check("second_save", store.write_state(path, fixture(2), OWNER, cat).status == "SAVED")
	check("previous_backup_exact_bytes", FileAccess.get_file_as_bytes(path + ".backup") == first_bytes)
	check("primary_revision2_backup_revision1", store.read_one(path, OWNER, cat).state.meta.revision == 2 and store.read_one(path + ".backup", OWNER, cat).state.meta.revision == 1)
	for key in state.meta:
		var document: Dictionary = JSON.parse_string(encoded)
		if key in ["schema_version", "revision"]:
			document.meta[key] += 1
		else:
			document.meta[key] += "changed"
		check("metadata_tamper_detected_" + key, store.decode(JSON.stringify(document), OWNER, cat).status == "CHECKSUM_MISMATCH")
	var document: Dictionary = JSON.parse_string(encoded)
	document.payload.loot[0].quantity = 8
	check("payload_tamper_detected", store.decode(JSON.stringify(document), OWNER, cat).status == "CHECKSUM_MISMATCH")
	var invalid: Dictionary = fixture()
	invalid.meta.owner_id = "local-account:other"
	check("signed_wrong_owner_rejected", store.decode(store.encode(invalid), OWNER, cat).status == "OWNER_MISMATCH")
	invalid = fixture()
	invalid.meta.schema_version = 2
	check("signed_future_schema_rejected", store.decode(store.encode(invalid), OWNER, cat).status == "UNSUPPORTED_FUTURE")
	var protected_path: String = fresh("future")
	put(protected_path, store.encode(invalid))
	put(protected_path + ".backup", encoded)
	var protected_bytes: PackedByteArray = FileAccess.get_file_as_bytes(protected_path)
	check("future_primary_never_falls_back", store.read_state(protected_path, OWNER, cat).status == "UNSUPPORTED_FUTURE")
	check("future_primary_never_overwritten", store.write_state(protected_path, state, OWNER, cat).status == "EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_bytes(protected_path) == protected_bytes)
	invalid = fixture()
	invalid.meta.owner_id = "local-account:other"
	put(protected_path, store.encode(invalid))
	protected_bytes = FileAccess.get_file_as_bytes(protected_path)
	check("wrong_owner_never_falls_back_or_overwrites", store.read_state(protected_path, OWNER, cat).status == "OWNER_MISMATCH" and store.write_state(protected_path, state, OWNER, cat).status == "EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_bytes(protected_path) == protected_bytes)
	invalid = fixture()
	invalid.meta.content_profile = "synthetic-other-profile"
	check("content_profile_deferred", store.decode(store.encode(invalid), OWNER, cat).status == "DEFERRED")
	invalid = fixture()
	invalid.payload.inventory[0].item_id = "fixture-item:missing"
	check("unknown_item_never_defaulted", store.validate(invalid, OWNER, cat).status == "UNKNOWN_ID")
	invalid = fixture()
	invalid.payload.inventory.append(invalid.payload.inventory[0].duplicate(true))
	check("duplicate_inventory_instance_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid = fixture()
	invalid.payload.equipment.weapon = "fixture-instance:missing"
	check("equipment_missing_instance_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid = fixture()
	invalid.payload.equipment.weapon = "fixture-instance:coat-01"
	check("equipment_wrong_slot_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid = fixture()
	invalid.payload.skills.append("fixture-skill:missing")
	check("unknown_skill_never_defaulted", store.validate(invalid, OWNER, cat).status == "UNKNOWN_ID")
	invalid = fixture()
	invalid.payload.loot.append(invalid.payload.loot[0].duplicate(true))
	check("duplicate_loot_identity_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid = fixture()
	invalid.payload.character.hp = 1.5
	check("fractional_integer_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid.payload.character.hp = 26
	check("health_range_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid = fixture()
	invalid.payload.character.position.x = -1
	check("negative_coordinates_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid.payload.character.position.x = 12
	check("out_of_bounds_coordinates_deferred", store.validate(invalid, OWNER, cat).status == "DEFERRED")
	invalid.payload.character.position.x = 1
	invalid.payload.character.position.y = 1
	check("collision_coordinates_deferred", store.validate(invalid, OWNER, cat).status == "DEFERRED")
	invalid = fixture()
	invalid.payload.character.id = "fixture-character:other"
	check("character_identity_mismatch_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	invalid = fixture()
	invalid.payload.character.name = "한글\n이름"
	check("control_character_name_rejected", store.validate(invalid, OWNER, cat).status == "INVALID_STATE")
	check("oversize_rejected_before_parse", store.decode(" ".repeat(Store.MAX_BYTES + 1), OWNER, cat).status == "SAVE_SIZE_LIMIT")
	check("depth_limit_rejected_before_parse", store.decode("[".repeat(25) + "0" + "]".repeat(25), OWNER, cat).status == "SAVE_DEPTH_LIMIT")
	check("truncated_json_rejected", store.decode(encoded.left(encoded.length() - 1), OWNER, cat).status == "CORRUPT")
	check("json_quote_and_escape_depth_scanner", store.decode(encoded.replace("가람하늘", '가람\\"{[하늘'), OWNER, cat).status == "CHECKSUM_MISMATCH")
	var recovery_path: String = fresh("recovery")
	put(recovery_path, "{broken 원본")
	put(recovery_path + ".backup", encoded)
	var broken_bytes: PackedByteArray = FileAccess.get_file_as_bytes(recovery_path)
	var recovered: Dictionary = store.read_state(recovery_path, OWNER, cat)
	check("corrupt_primary_reads_valid_backup", recovered.status == "RECOVERED_BACKUP" and recovered.state.meta.revision == 1)
	check("recovery_read_preserves_both_files", FileAccess.get_file_as_bytes(recovery_path) == broken_bytes and FileAccess.get_file_as_string(recovery_path + ".backup") == encoded)
	check("explicit_repair_saves_new_state", store.write_state(recovery_path, fixture(2), OWNER, cat).status == "SAVED")
	var preserved_count: int = 0
	for name in DirAccess.get_files_at(recovery_path.get_base_dir()):
		if name.begins_with("character.json.corrupt-") and FileAccess.get_file_as_bytes(recovery_path.get_base_dir().path_join(name)) == broken_bytes:
			preserved_count += 1
	check("repair_preserves_corrupt_exact_bytes_and_valid_backup", preserved_count >= 1 and FileAccess.get_file_as_string(recovery_path + ".backup") == encoded)
	put(recovery_path, "{primarybroken")
	put(recovery_path + ".backup", "{backupbroken")
	check("both_corrupt_never_create_new_character", store.read_state(recovery_path, OWNER, cat).status == "CORRUPT" and store.write_state(recovery_path, fixture(2), OWNER, cat).status == "EXISTING_SAVE_NOT_WRITABLE")
	for phase in ["after_pending_write", "after_backup_write"]:
		var corruption_path: String = fresh("partial-" + phase)
		put(corruption_path, encoded)
		var suffix: String = ".pending" if phase == "after_pending_write" else ".backup.pending"
		store.phase_observer = corrupt_written_phase.bind(phase, corruption_path + suffix)
		var result: Dictionary = store.write_state(corruption_path, fixture(2), OWNER, cat)
		store.phase_observer = Callable()
		check("partial_write_rejected_" + phase, result.status == "VERIFY_FAILED" and FileAccess.get_file_as_string(corruption_path) == encoded, result)
	for phase in Store.PHASES:
		var phase_path: String = fresh("return-fault-" + phase)
		put(phase_path, encoded)
		var result: Dictionary = store.write_state(phase_path, fixture(2), OWNER, cat, phase)
		var expected_revision: int = 2 if phase == "after_primary_replace" else 1
		var current: Dictionary = store.read_state(phase_path, OWNER, cat)
		check("return_fault_" + phase, result.status == ("COMMITTED_ACK_LOST" if expected_revision == 2 else "INJECTED_FAILURE") and current.status == "OK" and current.state.meta.revision == expected_revision, result)
	if process_runner.is_valid():
		for phase in Store.PHASES:
			var phase_path: String = fresh("kill-" + phase)
			put(phase_path, encoded)
			child = subprocess(["--child-crash", phase_path, phase])
			check("process_killed_at_" + phase, child.exit_code != 0 and child.exit_code != 52 and child.output.contains("P2_SAVE_CRASH_BOUNDARY=" + phase), child)
			var expected_revision: int = 2 if phase == "after_primary_replace" else 1
			child = subprocess(["--child-read", phase_path, expected_revision])
			check("restart_after_kill_" + phase, child.exit_code == 0, child)
			check("prior_snapshot_retained_after_kill_" + phase, FileAccess.get_file_as_bytes(phase_path + ".backup") == first_bytes if phase in ["after_backup_replace", "before_primary_replace", "after_primary_replace"] else FileAccess.get_file_as_bytes(phase_path) == first_bytes)
	else:
		for phase in Store.PHASES:
			skip("process_killed_at_" + phase, "No child process driver supplied on this platform")
			skip("restart_after_kill_" + phase, "No child process driver supplied on this platform")
			skip("prior_snapshot_retained_after_kill_" + phase, "No child process driver supplied on this platform")
	var target: Dictionary = cat.duplicate(true)
	target.maps["fixture-map:plain"].version = "synthetic-map-v2"
	target.manifest_sha256 = "b".repeat(64)
	var planned: Dictionary = store.plan_map_update(state, OWNER, cat, target)
	check("map_version_change_ready_with_valid_coordinates", planned.status == "READY")
	check("map_version_preserves_character_and_loot", planned.status == "READY" and planned.state.payload.character.position.x == 4 and planned.state.payload.character.position.y == 3 and planned.state.payload.loot[0].position.x == 8 and planned.state.payload.loot[0].position.y == 6 and planned.state.payload.loot[0].quantity == 7 and planned.state.payload.loot[0].loot_id == "fixture-loot:001")
	check("map_plan_does_not_mutate_source", store.canonical(state) == original)
	target.maps["fixture-map:plain"].blocked.append([4, 3])
	planned = store.plan_map_update(state, OWNER, cat, target)
	check("character_mapping_unavailable_deferred_preserving_source", planned.status == "DEFERRED" and store.canonical(planned.source) == original)
	target.maps["fixture-map:plain"].blocked = [[8, 6]]
	planned = store.plan_map_update(state, OWNER, cat, target)
	check("loot_mapping_unavailable_deferred_preserving_source", planned.status == "DEFERRED" and store.canonical(planned.source) == original)
	target.maps.erase("fixture-map:plain")
	planned = store.plan_map_update(state, OWNER, cat, target)
	check("map_missing_deferred_without_teleport", planned.status == "DEFERRED" and store.canonical(planned.source) == original)
	target = cat.duplicate(true)
	target.items.erase("fixture-item:sword")
	planned = store.plan_map_update(state, OWNER, cat, target)
	check("update_missing_item_deferred_preserving_source", planned.status == "DEFERRED" and store.canonical(planned.source) == original)
	var failure_path: String = fresh("write-failure")
	put(failure_path, "fixture blocks directory")
	var result: Dictionary = store.write_state(failure_path.path_join("child.json"), state, OWNER, cat)
	check("filesystem_write_failure_reported", result.status == "WRITE_FAILED")
	check("filesystem_write_failure_preserves_existing_file", FileAccess.get_file_as_string(failure_path) == "fixture blocks directory")
	var evidence_probe = get_script().new()
	evidence_probe.test_root = fresh("unwritable-results").get_base_dir()
	evidence_probe.emit_records = false
	DirAccess.make_dir_recursive_absolute(evidence_probe.test_root.path_join("results.json"))
	var probe_result: Dictionary = evidence_probe.finalize_results()
	check("unwritable_results_returns_fail_and_nonzero_count", probe_result.status == "FAIL" and probe_result.failures == 1 and probe_result.checks == 1, {"returned_status": probe_result.status, "returned_failures": probe_result.failures})
	for backup_kind in ["other_owner", "future_schema", "deferred_profile"]:
		var backup_path: String = fresh("backup-only-" + backup_kind)
		var backup_state: Dictionary = fixture()
		if backup_kind == "other_owner":
			backup_state.meta.owner_id = "local-account:other"
		elif backup_kind == "future_schema":
			backup_state.meta.schema_version = 2
		else:
			backup_state.meta.content_profile = "deferred-profile"
		var backup_text: String = store.encode(backup_state)
		put(backup_path + ".backup", backup_text)
		var backup_result: Dictionary = store.write_state(backup_path, state, OWNER, cat)
		check("backup_only_preserved_" + backup_kind, backup_result.status == "EXISTING_SAVE_NOT_WRITABLE" and not FileAccess.file_exists(backup_path) and FileAccess.get_file_as_string(backup_path + ".backup") == backup_text, backup_result)
		put(backup_path, encoded)
		backup_result = store.write_state(backup_path, fixture(2), OWNER, cat)
		check("incompatible_backup_preserved_with_primary_" + backup_kind, backup_result.status == "EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_string(backup_path) == encoded and FileAccess.get_file_as_string(backup_path + ".backup") == backup_text, backup_result)
	var backup_only_path: String = fresh("backup-only-valid")
	put(backup_only_path + ".backup", encoded)
	check("valid_backup_only_preserved_when_new_primary_saved", store.write_state(backup_only_path, fixture(2), OWNER, cat).status == "SAVED" and FileAccess.get_file_as_string(backup_only_path + ".backup") == encoded)
	for suffix in [".pending", ".backup.pending", ".backup", ""]:
		var symlink_path: String = fresh("symlink-" + ("primary" if suffix.is_empty() else suffix))
		var unrelated_path: String = symlink_path.get_base_dir().path_join("unrelated-fixture.txt")
		put(unrelated_path, "unrelated synthetic data must remain byte-identical")
		var link_path: String = symlink_path + suffix
		var directory = store.native_directory(symlink_path.get_base_dir())
		if directory == null:
			check("native_userdata_directory_access_" + suffix, false)
			continue
		var absolute_source: String = ProjectSettings.globalize_path(unrelated_path)
		var absolute_link: String = ProjectSettings.globalize_path(link_path)
		var link_result: Error = directory.create_link(absolute_source, absolute_link)
		if link_result != OK:
			skip("symlink_target_rejected_" + suffix, "Platform could not create synthetic symlink: " + str(link_result))
			continue
		if suffix == ".pending":
			var filesystem_directory := DirAccess.open(ProjectSettings.globalize_path(symlink_path.get_base_dir()))
			check("native_userdata_backend_detects_globalized_fixture_link", directory.is_link(absolute_link), {"native_userdata_is_link": directory.is_link(absolute_link), "absolute_filesystem_is_link": filesystem_directory.is_link(absolute_link) if filesystem_directory != null else "UNAVAILABLE"})
		var write_result: Dictionary = store.write_state(symlink_path, state, OWNER, cat)
		check("symlink_target_rejected_" + suffix, write_result.status == "UNSAFE_PATH_LINK", write_result)
		check("symlink_target_preserved_" + suffix, FileAccess.get_file_as_string(unrelated_path) == "unrelated synthetic data must remain byte-identical" and directory.is_link(absolute_link))
	var ancestor_base: String = fresh("symlink-parent").get_base_dir()
	var ancestor_target: String = ancestor_base.path_join("unrelated-directory")
	DirAccess.make_dir_recursive_absolute(ancestor_target)
	var ancestor_link: String = ancestor_base.path_join("linked-parent")
	var ancestor_directory = store.native_directory(ancestor_base)
	var ancestor_result: Error = ancestor_directory.create_link(ProjectSettings.globalize_path(ancestor_target), ProjectSettings.globalize_path(ancestor_link)) if ancestor_directory != null else ERR_CANT_OPEN
	if ancestor_result == OK:
		check("symlink_ancestor_rejected", store.write_state(ancestor_link.path_join("save.json"), state, OWNER, cat).status == "UNSAFE_PATH_LINK")
		check("symlink_ancestor_directory_preserved", DirAccess.get_files_at(ancestor_target).is_empty())
	else:
		skip("symlink_ancestor_rejected", "Platform could not create synthetic directory symlink: " + str(ancestor_result))
	var corrupt_link_path: String = fresh("symlink-corrupt-copy")
	var corrupt_text: String = "{corrupt fixture bytes"
	put(corrupt_link_path, corrupt_text)
	put(corrupt_link_path + ".backup", encoded)
	var corrupt_target: String = corrupt_link_path.get_base_dir().path_join("unrelated-fixture.txt")
	put(corrupt_target, "unrelated corrupt-copy target")
	var corrupt_sidecar: String = corrupt_link_path + ".corrupt-" + corrupt_text.sha256_text()
	var corrupt_directory = store.native_directory(corrupt_link_path.get_base_dir())
	var corrupt_link_result: Error = corrupt_directory.create_link(ProjectSettings.globalize_path(corrupt_target), ProjectSettings.globalize_path(corrupt_sidecar)) if corrupt_directory != null else ERR_CANT_OPEN
	if corrupt_link_result == OK:
		check("corrupt_copy_symlink_rejected", store.write_state(corrupt_link_path, fixture(2), OWNER, cat).status == "UNSAFE_PATH_LINK")
		check("corrupt_copy_symlink_preserves_all_sources", FileAccess.get_file_as_string(corrupt_target) == "unrelated corrupt-copy target" and FileAccess.get_file_as_string(corrupt_link_path) == corrupt_text and FileAccess.get_file_as_string(corrupt_link_path + ".backup") == encoded)
	else:
		skip("corrupt_copy_symlink_rejected", "Platform could not create synthetic symlink: " + str(corrupt_link_result))
