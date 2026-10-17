extends SceneTree
## Read actual containers through Linux Godot; this does not execute native builds.
func digest_bytes(bytes: PackedByteArray) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(bytes)
	return ctx.finish().hex_encode()

func option(args: PackedStringArray, name: String) -> String:
	var index := args.find(name)
	return args[index + 1] if index >= 0 and index + 1 < args.size() else ""

func member_matches_pck(member: Dictionary, path: String) -> bool:
	return int(member.get("bytes", 0)) > 0 and FileAccess.file_exists(path) and FileAccess.get_sha256(path) == member.get("sha256", "")

func sound_fidelity(relative: String, original: String, expected: String) -> Dictionary:
	var raw := FileAccess.get_file_as_bytes(original)
	var source_sha := digest_bytes(raw)
	var options := {"force/8_bit": false, "force/mono": false, "force/max_rate": false, "force/max_rate_hz": 44100, "edit/trim": false, "edit/normalize": false, "edit/loop_mode": 0, "edit/loop_begin": 0, "edit/loop_end": -1, "compress/mode": 2}
	var source := AudioStreamWAV.load_from_buffer(raw, options)
	var packed := ResourceLoader.load("res://private_runtime/" + relative, "AudioStreamWAV", ResourceLoader.CACHE_MODE_IGNORE) as AudioStreamWAV
	var passed: bool = source_sha == expected and source != null and packed != null
	if passed:
		passed = source.data == packed.data and source.format == packed.format and source.mix_rate == packed.mix_rate and source.stereo == packed.stereo and source.loop_mode == packed.loop_mode and source.loop_begin == packed.loop_begin and source.loop_end == packed.loop_end
	return {"path": relative, "status": "PASS" if passed else "FAIL", "source_sha256": source_sha, "import_recipe": options, "packed_format": packed.format if packed != null else -1, "packed_rate": packed.mix_rate if packed != null else -1, "packed_stereo": packed.stereo if packed != null else false, "packed_encoded_data_sha256": digest_bytes(packed.data) if packed != null else "", "scope": "Exact same-version Godot QOA import reproduced from frozen WAV; encoded sample data/rate/channels/loop metadata equal actual PCK. No hardware listening claim."}

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var freeze: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(option(args, "--freeze")))
	var failures: Array = []
	var raw_checks: Array = []
	var script_checks: Array = []
	var sound_checks: Array = []
	# Python hashes every actual APK member using indexed ZIP reads. Godot then
	# independently hashes each corresponding actual PCK member. This avoids
	# repeated linear ZIPReader name searches over tens of thousands of entries.
	var apk_manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(option(args, "--apk-manifest")))
	var files: Dictionary = apk_manifest.get("files", {})
	if apk_manifest.get("status") != "PASS_MANIFEST_ONLY" or apk_manifest.get("source_commit") != freeze.get("source_commit") or apk_manifest.get("artifact", {}).get("sha256", "") != FileAccess.get_sha256(option(args, "--apk")):
		failures.append("Indexed member manifest must bind the exact signed APK")
	var expected: Dictionary = freeze.get("runtime_snapshot", {})
	var fidelity: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(option(args, "--texture-fidelity-report")))
	var fidelity_rows: Dictionary = {}
	for row in fidelity.get("checks", []):
		fidelity_rows[str(row.path)] = row
	if fidelity.get("status") != "PASS" or fidelity.get("png_files") != 27791 or fidelity.get("source_commit") != freeze.get("source_commit") or fidelity.get("embedded_pck_sha256") != FileAccess.get_sha256(option(args, "--pck")):
		failures.append("Complete exact-PCK/frozen-source texture fidelity proof is required")
	var raw_found: Dictionary = {}
	var total_bytes := 0
	var verbatim_count := 0
	var imported_only_png_count := 0
	var windows_extra_verbatim_count := 0
	for apk_path in files:
		if not str(apk_path).begins_with("assets/private_runtime/"):
			continue
		var relative: String = str(apk_path).trim_prefix("assets/private_runtime/")
		if relative.get_extension().to_lower() in ["png", "json", "wav"]:
			raw_found[relative] = true
		if relative.get_extension().to_lower() in ["dat", "cab", "keystore", "jks", "pem", "sql"]:
			failures.append("Forbidden private/raw payload: " + relative)
	for relative in expected:
		var apk_path: String = "assets/private_runtime/" + str(relative)
		var windows_path: String = "res://private_runtime/" + str(relative)
		var present := files.has(apk_path)
		var member: Dictionary = files.get(apk_path, {})
		var actual: String = str(member.get("sha256", ""))
		var passed: bool = present and member_matches_pck(member, windows_path) and actual == expected[relative]
		var binding := "PACKED_VERBATIM_FREEZE_SHA256_AND_BOTH_CONTAINERS_EQUAL"
		if str(relative).ends_with(".png"):
			var texture_row: Dictionary = fidelity_rows.get(str(relative), {})
			var texture_pass: bool = texture_row.get("status") == "PASS" and texture_row.get("source_sha256") == expected[relative] and texture_row.get("all_alpha_and_nonzero_alpha_RGB_preserved") == true
			if not present:
				passed = texture_pass
				binding = "IMPORTED_TEXTURE_EXACT_VISIBLE_RGBA_AND_ALPHA_MATCH_FROZEN_PNG"
				imported_only_png_count += 1
			else:
				passed = passed and texture_pass
		if str(relative).ends_with(".wav"):
			var sound := sound_fidelity(str(relative), option(args, "--runtime").path_join(str(relative)), str(expected[relative]))
			sound_checks.append(sound)
			passed = sound.status == "PASS" and (passed if present else true)
			binding = "FROZEN_WAV_EXACT_GODOT_QOA_IMPORT_DATA_AND_METADATA" if not present else binding
		if not present and FileAccess.file_exists(windows_path):
			windows_extra_verbatim_count += 1
			passed = passed and FileAccess.get_sha256(windows_path) == expected[relative]
		if present:
			verbatim_count += 1
		if not passed:
			failures.append("Frozen runtime asset binding mismatch: " + str(relative))
		raw_checks.append({"path": relative, "packed_verbatim": present, "binding": binding, "bytes": member.get("bytes", 0), "packed_verbatim_sha256": actual, "freeze_source_sha256": expected[relative], "status": "PASS" if passed else "FAIL"})
		total_bytes += int(member.get("bytes", 0))
	if raw_found.size() != verbatim_count:
		failures.append("APK verbatim runtime member count differs from bound subset")
	for relative in raw_found:
		if not expected.has(relative):
			failures.append("Unexpected raw runtime member: " + str(relative))
	var sources: Dictionary = freeze.get("source_snapshot", {})
	for relative in sources:
		if not str(relative).ends_with(".gd"):
			continue
		var remap_name: String = str(relative) + ".remap"
		var remap := FileAccess.get_file_as_bytes("res://" + remap_name) if FileAccess.file_exists("res://" + remap_name) else PackedByteArray()
		var config := ConfigFile.new()
		var parsed := config.parse(remap.get_string_from_utf8()) == OK
		var compiled_path: String = str(config.get_value("remap", "path", "")) if parsed else ""
		if compiled_path.is_empty():
			compiled_path = "res://" + str(relative).trim_suffix(".gd") + ".gdc"
		var packed_path := compiled_path.trim_prefix("res://")
		var compiled_member: Dictionary = files.get("assets/" + packed_path, {})
		var passed: bool = member_matches_pck(compiled_member, compiled_path)
		if not remap.is_empty():
			passed = passed and member_matches_pck(files.get("assets/" + remap_name, {}), "res://" + remap_name)
		if not passed:
			failures.append("Compiled source/container mismatch: " + str(relative))
		script_checks.append({"source_path": relative, "source_freeze_sha256": sources[relative], "compiled_path": packed_path, "compiled_sha256": compiled_member.get("sha256", ""), "compiled_bytes": compiled_member.get("bytes", 0), "status": "PASS" if passed else "FAIL"})
	var gdc_count := 0
	var imported_count := 0
	var imported_bytes := 0
	var import_remap_count := 0
	for apk_path in files:
		var path: String = str(apk_path)
		var member: Dictionary = files[apk_path]
		if path.begins_with("assets/") and path.ends_with(".gdc"):
			gdc_count += 1
			if not member_matches_pck(member, "res://" + path.trim_prefix("assets/")):
				failures.append("Additional compiled-script container mismatch: " + path)
		if path.begins_with("assets/.godot/imported/") and not path.ends_with("/"):
			imported_count += 1
			imported_bytes += int(member.get("bytes", 0))
			if not member_matches_pck(member, "res://" + path.trim_prefix("assets/")):
				failures.append("Imported-resource container mismatch: " + path)
		if path.begins_with("assets/private_runtime/") and path.ends_with(".import"):
			import_remap_count += 1
			if not member_matches_pck(member, "res://" + path.trim_prefix("assets/")):
				failures.append("Import-remap container mismatch: " + path)
	var identity := {"custom_user_dir": ProjectSettings.get_setting("application/config/custom_user_dir_name", ""), "uses_custom_user_dir": ProjectSettings.get_setting("application/config/use_custom_user_dir", false), "main_scene": ProjectSettings.get_setting("application/run/main_scene", "")}
	if identity.custom_user_dir != "baram_rebuild_p3repair_001" or not identity.uses_custom_user_dir:
		failures.append("Windows PCK retained save identity differs")
	var report := {"schema": "baram.g2.r16.expanded-pack-parity/1", "status": "PASS" if failures.is_empty() and expected.size() == 28167 and script_checks.size() > 20 and imported_count >= 27807 and import_remap_count == 27807 else "FAIL", "source_commit": freeze.get("source_commit", ""), "frozen_source_assets_bound": raw_checks.size(), "packed_verbatim_files": verbatim_count, "packed_verbatim_bytes": total_bytes, "imported_only_pngs": imported_only_png_count, "texture_fidelity_files": fidelity.get("png_files", 0), "texture_fidelity_report_sha256": FileAccess.get_sha256(option(args, "--texture-fidelity-report")), "expected_source_scripts": script_checks.size(), "all_apk_compiled_scripts": gdc_count, "imported_resource_files": imported_count, "imported_resource_bytes": imported_bytes, "import_remap_files": import_remap_count, "identity": identity, "failures": failures, "asset_binding_checks": raw_checks, "script_checks": script_checks, "scope": "All frozen runtime sources bind to actual packaged resources. Verbatim PNG/JSON/WAV bytes equal freeze and both containers. Imported-only PNGs have full frozen-source hash/dimensions/exact visible RGBA and alpha fidelity proof. All compiled scripts, remaps and imported resource bytes equal across APK and Windows PCK. Source-to-compiled provenance is bound by exact staged source receipts. Linux resource integrity only; whole-scene visual quality, native Windows/Android execution and update remain separate.", "native_execution": "NOT_RUN", "native_update": "NOT_RUN"}
	report["apk_member_manifest_sha256"] = FileAccess.get_sha256(option(args, "--apk-manifest"))
	report["windows_additional_verbatim_source_files"] = windows_extra_verbatim_count
	report["windows_additional_verbatim_source_policy"] = "Windows retains some original PNG/WAV bytes that Android legitimately omits; retained bytes must match freeze, while every actual imported resource matches both containers and frozen-source fidelity."
	report["sound_fidelity_checks"] = sound_checks
	report["sound_fidelity_files"] = sound_checks.size()
	report["container_equality_method"] = "Every actual signed APK member decompressed/hashed once with Python indexed ZIP reads; Godot independently hashes actual PCK members and compares exact SHA-256 plus nonempty presence. A separate standard check compares every indexed actual APK private-runtime/script byte directly against PCK bytes. Legacy ZIPReader driver timeout is retained separately."
	var output := FileAccess.open(option(args, "--report"), FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  ") + "\n")
	output.close()
	print("R16_EXPANDED_PACK ", report.status, " raw=", raw_checks.size(), " scripts=", script_checks.size(), " failures=", failures.size())
	quit(0 if report.status == "PASS" else 1)
