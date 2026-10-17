extends SceneTree
## Asset fidelity only. Actual scenes and native execution remain separate tests.
func option(args: PackedStringArray, name: String) -> String:
	var index := args.find(name)
	return args[index + 1] if index >= 0 and index + 1 < args.size() else ""

func normalized_rgba(image: Image) -> PackedByteArray:
	var result := Image.create_empty(image.get_width(), image.get_height(), false, Image.FORMAT_RGBA8)
	result.fill(Color(0, 0, 0, 0))
	# Native blit copies exact RGBA where mask alpha>0; only invisible RGB is zeroed.
	result.blit_rect_mask(image, image, Rect2i(Vector2i.ZERO, image.get_size()), Vector2i.ZERO)
	return result.get_data()

func texture_check(relative: String, original: String, expected_sha: String) -> Dictionary:
	var source_sha := FileAccess.get_sha256(original)
	var row := {"path": relative, "source_sha256": source_sha, "source_hash_matches_freeze": source_sha == expected_sha, "status": "FAIL"}
	if source_sha != expected_sha:
		row["failure"] = "Source bytes differ from freeze"
		return row
	var texture := ResourceLoader.load("res://private_runtime/" + relative, "Texture2D", ResourceLoader.CACHE_MODE_IGNORE) as Texture2D
	if texture == null:
		row["failure"] = "Packed logical PNG cannot load as Texture2D"
		return row
	var packed := texture.get_image()
	var source := Image.new()
	if packed == null or packed.is_empty() or source.load(original) != OK:
		row["failure"] = "Source/packed image decode failed"
		return row
	if packed.is_compressed() and packed.decompress() != OK:
		row["failure"] = "Packed texture decompression failed"
		return row
	if source.is_compressed() and source.decompress() != OK:
		row["failure"] = "Original image decompression failed"
		return row
	row["width"] = source.get_width()
	row["height"] = source.get_height()
	row["packed_width"] = packed.get_width()
	row["packed_height"] = packed.get_height()
	if source.get_size() != packed.get_size():
		row["failure"] = "Texture dimensions differ"
		return row
	source.clear_mipmaps()
	packed.clear_mipmaps()
	source.convert(Image.FORMAT_RGBA8)
	packed.convert(Image.FORMAT_RGBA8)
	var source_bytes := source.get_data()
	var packed_bytes := packed.get_data()
	var equal: bool = source_bytes == packed_bytes
	row["comparison"] = "EXACT_RAW_RGBA8" if equal else "EXACT_RGBA8_WITH_ALPHA0_RGB_ZEROED_BY_NATIVE_MASK_BLIT"
	if not equal:
		equal = normalized_rgba(source) == normalized_rgba(packed)
	row["compared_rgba_bytes"] = source_bytes.size()
	row["all_alpha_and_nonzero_alpha_RGB_preserved"] = equal
	row["status"] = "PASS" if equal else "FAIL"
	if not equal:
		row["failure"] = "Visible RGBA or alpha differs"
	return row

func _initialize() -> void:
	call_deferred("run_checks")

func run_checks() -> void:
	var args := OS.get_cmdline_user_args()
	var freeze: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(option(args, "--freeze")))
	var expected: Dictionary = freeze.get("runtime_snapshot", {})
	var checks: Array = []
	var failures: Array = []
	var compared_bytes := 0
	var native_normalized := 0
	var started := Time.get_ticks_msec()
	for relative in expected:
		if not str(relative).ends_with(".png"):
			continue
		var row := texture_check(str(relative), option(args, "--runtime").path_join(str(relative)), str(expected[relative]))
		checks.append(row)
		compared_bytes += int(row.get("compared_rgba_bytes", 0))
		if str(row.get("comparison", "")).contains("NATIVE_MASK_BLIT"):
			native_normalized += 1
		if row.status != "PASS":
			failures.append({"path": relative, "failure": row.get("failure", "Unknown failure")})
		if checks.size() % 1000 == 0:
			print("R16_TEXTURE_PROGRESS ", checks.size(), " failures=", failures.size())
		if checks.size() % 64 == 0:
			await process_frame
	var report := {"schema": "baram.g2.r16.packed-texture-fidelity/1", "status": "PASS" if failures.is_empty() and checks.size() == 27791 else "FAIL", "source_commit": freeze.get("source_commit", ""), "embedded_pck_sha256": FileAccess.get_sha256(option(args, "--pck")), "runtime_manifest_sha256": expected.get("runtime.json", ""), "content_sha256": expected.get("gameplay_content.json", ""), "png_files": checks.size(), "compared_rgba_bytes": compared_bytes, "native_alpha0_normalized_files": native_normalized, "seconds": float(Time.get_ticks_msec() - started) / 1000.0, "failures": failures, "checks": checks, "scope": "Each frozen original PNG hash and dimensions are checked against its actual Windows PCK Texture2D decoded RGBA8. Exact alpha and every nonzero-alpha RGB are preserved; only fully transparent RGB is normalized with a verified native mask blit. This is resource fidelity, not whole-scene visual approval or native Windows execution.", "native_execution": "NOT_RUN"}
	var output := FileAccess.open(option(args, "--report"), FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  ") + "\n")
	output.close()
	print("R16_TEXTURE_FIDELITY ", report.status, " files=", checks.size(), " failures=", failures.size(), " seconds=", report.seconds)
	quit(0 if report.status == "PASS" else 1)
