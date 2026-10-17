extends SceneTree
## Real gameplay serialization + deterministic service-response fixtures.
## NO external auth, HTTP, real device or Windows→Android→Windows claim.
const Sync = preload("res://storage/sequential_sync.gd")
const Game = preload("res://state/gameplay_state.gd")
const Store = preload("res://storage/gameplay_store.gd")
const OWNER := "local:sequential-sync-fixture"
const SUBJECT := "authenticated-provider-subject:fixture"
const TOKEN := "SESSION_SECRET_FIXTURE_NEVER_PERSIST"
var checks: Array = []
var failures := 0
var path := ""
var character_id := ""
var content: Dictionary = {}

func check(id: String, passed: bool, details: Variant = "") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed: failures += 1

func fixture_content() -> Dictionary:
	return {"profile":"SYNC_REAL_GAMEPLAY_FIXTURE","manifest_sha256":"a".repeat(64),"compatibility":{"schema":"1","rules":"rules1","idset":"ids1","map_geometry":"geo1"},
		"maps":{"map:town":{"width":12,"height":12,"blocked":[[0,0]],"exits":[],"spawns":[]}},"npcs":{},
		"items":{"item:sword":{"slot":"weapon","stack_max":1,"durability":100},"item:acorn":{"stack_max":999,"durability":0}},"skills":{},"monsters":{},
		"start":{"map_id":"map:town","x":2,"y":2,"hp":50,"mp":30,"money":100,"starter_items":[{"item_id":"item:sword","quantity":1},{"item_id":"item:acorn","quantity":3}]},
		"gates":{"north":{"map_id":"map:town","x":2,"y":2}},"respawn":{"map_id":"map:town","x":2,"y":2},"xp_thresholds":[0,10,30,60,100],"config":{"inventory_slots":60}}

func new_adapter(suffix: String = ""):
	var adapter = Sync.new()
	adapter.configure(content, OWNER, character_id, "https://sync.invalid/fixture", path + suffix)
	return adapter

func envelope(adapter, payload: Dictionary, revision: int, subject: String = SUBJECT, character: String = "") -> String:
	var encoded: Dictionary = adapter._snapshot_text(payload)
	return JSON.stringify({"schema":Sync.SCHEMA,"owner_id":subject,"character_id":character_id if character.is_empty() else character,"server_revision":revision,"snapshot":encoded.get("text", "")})

func response(adapter, status_code: int, payload: Dictionary, revision: int) -> Dictionary:
	var request: Dictionary = adapter.begin_pull()
	return adapter.accept_response(int(request.get("id", -1)), status_code, envelope(adapter, payload, revision))

func _initialize() -> void:
	content = fixture_content()
	var engine = Game.new()
	check("game_fixture_configured", engine.configure(content), engine.errors)
	check("game_fixture_created", engine.create_character("이어시험", OWNER).status == "OK")
	var original: Dictionary = engine.snapshot()
	character_id = original.character.id
	path = "user://gameplay-p3/tests/sync-" + str(Time.get_ticks_usec()) + "/"
	var adapter = Sync.new()
	check("no_endpoint_explicitly_blocked", adapter.configure(content, OWNER, character_id, "", path).status == "BLOCKED")
	check("offline_queue_independent_of_service", adapter.queue_local(original).status == "QUEUED")
	check("no_endpoint_request_blocked", adapter.begin_pull().status == "BLOCKED")
	check("original_payload_not_mutated", original == engine.snapshot())
	adapter = new_adapter()
	check("offline_pending_survives_restart", adapter.status().pending and adapter.begin_pull().status == "AUTH_REQUIRED")
	check("unverified_local_owner_not_session", adapter.metadata.subject.is_empty())
	check("credential_url_rejected", Sync.new().configure(content, OWNER, character_id, "https://user:password@example.test", path + "unsafe/").status == "INVALID_ENDPOINT")
	check("insecure_http_rejected", Sync.new().configure(content, OWNER, character_id, "http://example.test", path + "unsafe/").status == "INVALID_ENDPOINT")
	check("token_header_injection_rejected", adapter.bind_session(SUBJECT, "bad\r\nHeader: value").status == "AUTH_REQUIRED")
	check("provider_session_bound", adapter.bind_session(SUBJECT, TOKEN).status == "SESSION_BOUND")
	check("different_account_cannot_adopt_pending", adapter.bind_session("other-subject", TOKEN).status == "ACCOUNT_MISMATCH")
	check("push_requires_server_baseline", adapter.begin_push().status == "PULL_REQUIRED")
	var pull: Dictionary = adapter.begin_pull()
	check("one_request_at_a_time", adapter.begin_pull().status == "BUSY")
	check("new_remote_cas_starts_at_zero", adapter.accept_response(int(pull.id), 404, "").status == "OK" and adapter.metadata.remote_revision == 0)
	var push: Dictionary = adapter.begin_push()
	check("cas_header_present_token_absent_from_evidence", 'If-Match: "0"' in push.headers and TOKEN not in JSON.stringify(push))
	check("first_upload_acknowledged", adapter.accept_response(int(push.id), 201, envelope(adapter, original, 1)).status == "SYNCED" and not adapter.status().pending)
	var second := original.duplicate(true)
	second.revision = int(original.revision) + 1
	second.character.money = int(original.character.money) + 7
	check("local_next_revision_queued", adapter.queue_local(second).status == "QUEUED")
	push = adapter.begin_push()
	var third := second.duplicate(true)
	third.revision = int(second.revision) + 1
	third.character.money += 11
	check("new_local_save_while_http_in_flight", adapter.queue_local(third).status == "QUEUED")
	check("old_ack_does_not_clear_new_pending", adapter.accept_response(int(push.id), 200, envelope(adapter, second, 2)).status == "SYNCED" and adapter.status().pending and adapter.metadata.pending_hash == adapter._snapshot_text(third).hash)
	adapter = new_adapter()
	check("restart_requires_fresh_provider_session", adapter.begin_pull().status == "AUTH_REQUIRED")
	adapter.bind_session(SUBJECT, TOKEN)
	check("unchanged_remote_retains_offline_progress", response(adapter, 200, second, 2).status == "OK" and adapter.metadata.pending_hash == adapter._snapshot_text(third).hash)
	var divergent := second.duplicate(true)
	divergent.revision = int(third.revision) + 3
	divergent.character.money = 999
	var conflict: Dictionary = response(adapter, 200, divergent, 3)
	check("divergent_progress_preserves_both", conflict.status == "CONFLICT" and adapter.store._canonical(adapter._read_snapshot(adapter.metadata.conflict.local_hash).payload) == adapter.store._canonical(third) and adapter.store._canonical(adapter._read_snapshot(adapter.metadata.conflict.remote_hash).payload) == adapter.store._canonical(divergent), {"result":conflict,"preserved":adapter.metadata.conflict})
	check("conflict_blocks_automatic_push", adapter.begin_push().status == "CONFLICT")
	check("local_authoritative_save_never_written_by_adapter", not FileAccess.file_exists(path + "actual-game-save.json"))
	adapter = new_adapter()
	adapter.bind_session(SUBJECT, TOKEN)
	check("conflict_survives_restart", adapter.status().conflict and adapter.metadata.history.size() == 1)
	check("explicit_keep_local_retains_remote_archive", adapter.resolve_keep_local().status == "OK" and adapter.metadata.history.size() == 1 and adapter.metadata.remote_revision == 3 and adapter.status().pending)
	push = adapter.begin_push()
	check("resolved_push_uses_exact_remote_revision", 'If-Match: "3"' in push.get("headers", []), push.get("headers", []))
	check("cas_failure_keeps_local_pending", adapter.accept_response(int(push.id), 412, "").status == "CONFLICT_PULL_REQUIRED" and adapter.status().pending)
	check("old_server_revision_never_applied", response(adapter, 200, original, 1).status == "STALE_REMOTE" and adapter.status().pending)
	pull = adapter.begin_pull()
	check("forged_owner_response_rejected", adapter.accept_response(int(pull.id), 200, envelope(adapter, divergent, 4, "other-subject")).status == "OWNER_MISMATCH")
	pull = adapter.begin_pull()
	check("other_character_response_rejected", adapter.accept_response(int(pull.id), 200, envelope(adapter, divergent, 4, SUBJECT, "character:other")).status == "CHARACTER_MISMATCH")
	push = adapter.begin_push()
	check("transport_failure_is_offline_pending", adapter.accept_response(int(push.id), 0, "", false).status == "OFFLINE_PENDING" and adapter.status().pending)
	push = adapter.begin_push()
	adapter.clear_session()
	check("logout_invalidates_late_response", adapter.accept_response(int(push.id), 200, envelope(adapter, third, 4)).status == "STALE_RESPONSE" and adapter.status().pending)
	adapter.bind_session(SUBJECT, TOKEN)
	push = adapter.begin_push()
	check("unauthorized_response_keeps_pending", adapter.accept_response(int(push.id), 401, "").status == "AUTH_REQUIRED" and adapter.status().pending)
	adapter.bind_session(SUBJECT, TOKEN)
	var prior: Dictionary = adapter.metadata.duplicate(true)
	var fourth := third.duplicate(true)
	fourth.revision += 1
	fourth.character.money += 1
	adapter.fault_phase = "before_checkpoint_replace"
	check("failed_queue_does_not_advance_memory_checkpoint", adapter.queue_local(fourth).status == "INJECTED_FAILURE" and adapter.metadata == prior)
	adapter = new_adapter()
	check("failed_queue_does_not_replace_confirmed_disk_pending", adapter.metadata.pending_hash == prior.pending_hash)
	adapter.bind_session(SUBJECT, TOKEN)
	var bad := third.duplicate(true)
	bad.character.id = "character:other"
	check("queued_character_bound_separately_from_owner", adapter.queue_local(bad).status == "CHARACTER_MISMATCH")
	bad = third.duplicate(true)
	bad.revision -= 1
	check("old_local_revision_cannot_replace_newer_pending", adapter.queue_local(bad).status == "STALE_LOCAL")
	var all_text := ""
	for filename in DirAccess.get_files_at(path):
		all_text += FileAccess.get_file_as_string(path + filename)
	check("tokens_never_persist_in_checkpoint_or_backups", TOKEN not in all_text)
	# Clean secondary device starts without a local save: remote is offered but
	# not acknowledged until the caller has safely saved/read back its payload.
	var clean = new_adapter("clean/")
	clean.bind_session(SUBJECT, TOKEN)
	var offer: Dictionary = response(clean, 200, divergent, 3)
	check("remote_needs_explicit_local_durable_confirmation", offer.status == "REMOTE_AVAILABLE" and clean.metadata.base_hash.is_empty() and clean.begin_push().status == "REMOTE_AWAITING_LOCAL_SAVE")
	check("wrong_remote_confirmation_rejected", clean.confirm_remote_saved(original).status == "REMOTE_CONFIRM_MISMATCH")
	var local_store = Store.new()
	var local_path := path + "clean/actual-game-save.json"
	var write: Dictionary = local_store.write_game(local_path, offer.payload, OWNER, content)
	var read: Dictionary = local_store.read_game(local_path, OWNER, content)
	check("real_store_remote_payload_roundtrip_then_confirm", write.status == "SAVED" and read.status == "OK" and clean.confirm_remote_saved(read.payload).status == "OK" and clean.metadata.remote_revision == 3)
	check("older_gameplay_revision_cannot_hide_behind_new_server_revision", response(clean, 200, original, 4).status == "STALE_REMOTE")
	var moving = new_adapter("moving/")
	moving.bind_session(SUBJECT, TOKEN)
	offer = response(moving, 200, divergent, 3)
	check("progress_while_remote_offer_open_stays_pending", moving.queue_local(third).status == "QUEUED" and moving.confirm_remote_saved(offer.payload).status == "LOCAL_ADVANCED" and moving.status().pending)
	var report := {"schema":"baram.sequential-sync-fixture-evidence/1","scope":"ACTUAL_GODOT_LOCAL_SERIALIZATION_AND_RESPONSE_FIXTURES_ONLY","external_auth_http_roundtrip":"NOT_RUN_NO_ENDPOINT","Windows_Android_Windows":"BLOCKED_NO_APPROVED_AUTHENTICATED_ENDPOINT","engine":Engine.get_version_info(),"os":OS.get_name(),"status":"PASS" if failures == 0 else "FAIL","failures":failures,"checks":checks}
	var output := "/tmp/baram-sequential-sync-fixtures.json"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--sync-report="): output = arg.trim_prefix("--sync-report=")
	var file := FileAccess.open(output, FileAccess.WRITE)
	if file: file.store_string(JSON.stringify(report, "\t")); file.close()
	print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size(),"report":output,"external_roundtrip":"NOT_RUN"}))
	quit(0 if failures == 0 else 1)
