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
	print(JSON.stringify(record))

func put(path: String, text: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("fixture output unavailable: " + path)
		check("fixture_output_access", false, path)
		return
	file.store_string(text)
	file.close()

func fresh(name: String) -> String:
	var directory: String = test_root.path_join(name)
	DirAccess.make_dir_recursive_absolute(directory)
	return directory.path_join("character.json")

func subprocess(arguments: Array) -> Dictionary:
	return process_runner.call(arguments)

func skip(label: String, reason: String) -> void:
	var record: Dictionary = {"test": label, "status": "NOT_RUN", "detail": reason}
	records.append(record)
	print(JSON.stringify(record))

func run(output_directory: String, child_runner: Callable = Callable()) -> Dictionary:
	test_root = output_directory
	process_runner = child_runner
	checks = 0
	failures = 0
	records = []
	DirAccess.make_dir_recursive_absolute(test_root)
	run_tests()
	var summary: Dictionary = {"schema": "baram.p2.save-test-results/1", "fixture_kind": "SYNTHETIC_NO_HISTORICAL_ACCURACY_CLAIM", "engine": Engine.get_version_info(), "os": OS.get_name(), "checks": checks, "failures": failures, "status": "PASS" if failures == 0 else "FAIL", "tests": records}
	put(test_root.path_join("results.json"), JSON.stringify(summary, "\t"))
	print("P2_SAVE_SUMMARY=" + JSON.stringify({"checks": checks, "failures": failures, "status": summary.status}))
	return summary

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
	var failure_path: String = fresh("write-failure")
	put(failure_path, "fixture blocks directory")
	var result: Dictionary = store.write_state(failure_path.path_join("child.json"), state, OWNER, cat)
	check("filesystem_write_failure_reported", result.status == "WRITE_FAILED")
	check("filesystem_write_failure_preserves_existing_file", FileAccess.get_file_as_string(failure_path) == "fixture blocks directory")
