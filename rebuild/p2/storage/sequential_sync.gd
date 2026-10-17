extends RefCounted
## Optional local-first sequential continuation. No endpoint/session is bundled.
## The auth provider must verify a session before bind_session(). The server MUST
## derive owner_id from its verified bearer session and atomically enforce
## If-Match, owner_id and character_id. A local owner string/checksum is NOT auth.
## This adapter never logs/persists tokens and never merges divergent saves.
const Store = preload("res://storage/gameplay_store.gd")
const SCHEMA := "baram.sequential-sync/1"
const META_SCHEMA := "baram.sequential-sync-checkpoint/1"
const MAX_RESPONSE := Store.MAX_BYTES * 2
var store = Store.new()
var content: Dictionary = {}
var metadata: Dictionary = {}
var endpoint := ""
var root := ""
var fault_phase := ""
var _token := ""
var _flight: Dictionary = {}
var _serial := 0

func _result(status: String, reason: String = "") -> Dictionary:
	return {"status":status,"reason":reason}

func configure(catalog: Dictionary, owner: String, character_id: String, service_url: String = "", checkpoint_root: String = "") -> Dictionary:
	metadata = {}
	_token = ""
	_flight = {}
	endpoint = ""
	if not store._id(owner) or not store._id(character_id): return _result("INVALID_IDENTITY")
	if not service_url.is_empty():
		var authority := service_url.trim_prefix("https://").split("/")[0]
		if service_url.length() > 2048 or not service_url.begins_with("https://") or authority.is_empty() or "@" in authority or "?" in service_url or "#" in service_url or "\\" in service_url:
			return _result("INVALID_ENDPOINT", "https_without_credentials_query_or_fragment_required")
		for c in service_url:
			if c.unicode_at(0) <= 32 or c.unicode_at(0) == 127: return _result("INVALID_ENDPOINT", "control_or_whitespace")
	content = catalog
	endpoint = service_url.trim_suffix("/")
	root = checkpoint_root if not checkpoint_root.is_empty() else Store.ROOT + "sync/" + (owner + "/" + character_id).sha256_text() + "/"
	if not root.ends_with("/") or not store._path(root + "checkpoint.json"): return _result("UNSAFE_PATH")
	_token = ""
	_flight = {}
	metadata = {"schema":META_SCHEMA,"local_owner":owner,"character_id":character_id,"subject":"","remote_revision":-1,"base_hash":"","pending_hash":"","offer":{},"conflict":{},"history":[]}
	if FileAccess.file_exists(root + "checkpoint.json"):
		var loaded := _read_checkpoint(root + "checkpoint.json")
		if loaded.status == "UNSUPPORTED_CHECKPOINT":
			metadata = {}
			return loaded
		if loaded.status != "OK":
			loaded = _read_checkpoint(root + "checkpoint.json.backup")
			if loaded.status != "OK":
				metadata = {}
				return _result("CHECKPOINT_INVALID", "original_and_backup_preserved")
		if loaded.document.local_owner != owner or loaded.document.character_id != character_id:
			metadata = {}
			return _result("OWNER_MISMATCH")
		metadata = loaded.document
	return _result("READY" if not endpoint.is_empty() else "BLOCKED", "NO_APPROVED_ENDPOINT" if endpoint.is_empty() else "")

func bind_session(verified_subject: String, access_token: String) -> Dictionary:
	if metadata.is_empty() or not store._id(verified_subject) or access_token.is_empty() or access_token.length() > 16384 or "\r" in access_token or "\n" in access_token:
		return _result("AUTH_REQUIRED")
	if not metadata.subject.is_empty() and metadata.subject != verified_subject: return _result("ACCOUNT_MISMATCH", "pending_save_remains_bound_to_original_account")
	var next := metadata.duplicate(true)
	next.subject = verified_subject
	var saved := _commit(next)
	if saved.status != "OK": return saved
	_token = access_token
	_flight = {}
	return _result("SESSION_BOUND", "provider_verification_and_server_authorization_required")

func clear_session() -> void:
	_token = ""
	_flight = {}

func status() -> Dictionary:
	return {"status":"BLOCKED" if endpoint.is_empty() else ("AUTH_REQUIRED" if _token.is_empty() else "READY"),"pending":not metadata.get("pending_hash", "").is_empty(),"conflict":not metadata.get("conflict", {}).is_empty(),"remote_revision":metadata.get("remote_revision", -1),"external_roundtrip":"NOT_RUN"}

func _snapshot_text(payload: Dictionary) -> Dictionary:
	if metadata.is_empty(): return _result("NOT_CONFIGURED")
	var valid: Dictionary = store.validate_payload(payload, str(metadata.local_owner), content)
	if valid.status != "OK": return valid
	if payload.character.id != metadata.character_id: return _result("CHARACTER_MISMATCH")
	var document := {"schema":Store.SCHEMA,"owner":metadata.local_owner,"revision":payload.revision,"profile":content.get("profile", ""),"compatibility":store._compat(content),"manifest_sha256":content.get("manifest_sha256", ""),"payload":payload.duplicate(true)}
	var text := store._encode(document)
	if text.to_utf8_buffer().size() > Store.MAX_BYTES: return _result("SAVE_SIZE_LIMIT")
	return {"status":"OK","text":text,"hash":text.sha256_text()}

func _read_snapshot(digest: String) -> Dictionary:
	if not _hash(digest): return _result("INVALID_HASH")
	var path := root + "snapshots/" + digest + ".json"
	if not store._path(path) or not FileAccess.file_exists(path): return _result("MISSING_SNAPSHOT")
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > Store.MAX_BYTES: return _result("SAVE_SIZE_LIMIT")
	var text := file.get_as_text()
	file.close()
	if text.sha256_text() != digest: return _result("CHECKSUM_MISMATCH")
	var decoded: Dictionary = store._decode(text, str(metadata.local_owner), content)
	if decoded.status != "OK": return decoded
	if decoded.payload.character.id != metadata.character_id: return _result("CHARACTER_MISMATCH")
	return {"status":"OK","text":text,"hash":digest,"payload":decoded.payload}

func _preserve(text: String) -> Dictionary:
	var digest := text.sha256_text()
	var path := root + "snapshots/" + digest + ".json"
	if not store._path(path): return _result("UNSAFE_PATH")
	if FileAccess.file_exists(path):
		if FileAccess.get_file_as_string(path) != text: return _result("PRESERVATION_CONFLICT")
	else:
		if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK or not store.base._write(path + ".pending", text): return _result("WRITE_FAILED")
		if FileAccess.get_file_as_string(path + ".pending") != text: return _result("VERIFY_FAILED")
		if DirAccess.rename_absolute(path + ".pending", path) != OK: return _result("REPLACE_FAILED")
	return {"status":"OK","hash":digest}

func queue_local(payload: Dictionary) -> Dictionary:
	# Caller invokes after the existing atomic local save confirms success. The
	# game remains playable while endpoint/auth/network is unavailable.
	if metadata.is_empty(): return _result("NOT_CONFIGURED")
	var encoded := _snapshot_text(payload)
	if encoded.status != "OK": return encoded
	var previous_hash: String = metadata.pending_hash if not metadata.pending_hash.is_empty() else metadata.base_hash
	if not previous_hash.is_empty():
		var previous := _read_snapshot(previous_hash)
		if previous.status != "OK": return previous
		if int(payload.revision) < int(previous.payload.revision): return _result("STALE_LOCAL")
		if int(payload.revision) == int(previous.payload.revision) and encoded.hash != previous_hash: return _result("LOCAL_REVISION_CONFLICT")
	var preserved := _preserve(encoded.text)
	if preserved.status != "OK": return preserved
	var next := metadata.duplicate(true)
	next.pending_hash = "" if encoded.hash == next.base_hash else encoded.hash
	var committed := _commit(next)
	if committed.status != "OK": return committed
	return _result("QUEUED" if not metadata.pending_hash.is_empty() else "UNCHANGED")

func begin_pull() -> Dictionary:
	return _begin("pull")

func begin_push() -> Dictionary:
	if metadata.is_empty(): return _result("NOT_CONFIGURED")
	if not metadata.conflict.is_empty(): return _result("CONFLICT", "explicit_resolution_required")
	if not metadata.offer.is_empty(): return _result("REMOTE_AWAITING_LOCAL_SAVE")
	if int(metadata.remote_revision) < 0: return _result("PULL_REQUIRED")
	if metadata.pending_hash.is_empty(): return _result("UNCHANGED")
	return _begin("push")

func _begin(operation: String) -> Dictionary:
	if endpoint.is_empty(): return _result("BLOCKED", "NO_APPROVED_ENDPOINT")
	if _token.is_empty(): return _result("AUTH_REQUIRED")
	if not _flight.is_empty(): return _result("BUSY")
	_serial += 1
	_flight = {"id":_serial,"operation":operation,"subject":metadata.subject,"character_id":metadata.character_id,"revision":metadata.remote_revision,"hash":metadata.pending_hash}
	var request := {"status":"REQUEST","id":_serial,"method":HTTPClient.METHOD_GET,"url":endpoint + "/characters/" + str(metadata.character_id).uri_encode(),"headers":PackedStringArray(["Accept: application/json"]),"body":""}
	if operation == "push":
		var snapshot := _read_snapshot(metadata.pending_hash)
		if snapshot.status != "OK":
			_flight = {}
			return snapshot
		request.method = HTTPClient.METHOD_PUT
		request.headers.append("Content-Type: application/json")
		request.headers.append('If-Match: "' + str(int(metadata.remote_revision)) + '"')
		request.body = JSON.stringify({"schema":SCHEMA,"owner_id":metadata.subject,"character_id":metadata.character_id,"expected_revision":int(metadata.remote_revision),"snapshot":snapshot.text})
	# Authorization is added only inside perform_request; request evidence is safe
	# to inspect without copying bearer credentials into logs or save metadata.
	_flight.request_hash = store._canonical(request).sha256_text()
	return request

func accept_response(request_id: int, http_status: int, body: String, transport_ok: bool = true) -> Dictionary:
	if _flight.is_empty() or int(_flight.id) != request_id: return _result("STALE_RESPONSE")
	var flight := _flight
	_flight = {}
	if not transport_ok: return _result("OFFLINE_PENDING")
	if http_status in [401, 403]:
		_token = ""
		return _result("AUTH_REQUIRED")
	if http_status == 404 and flight.operation == "pull":
		if int(metadata.remote_revision) > 0 or not metadata.base_hash.is_empty(): return _result("REMOTE_MISSING", "local_save_preserved")
		var next := metadata.duplicate(true)
		next.remote_revision = 0
		return _commit(next)
	if http_status in [409, 412]: return _result("CONFLICT_PULL_REQUIRED", "pending_preserved")
	if http_status not in [200, 201]: return _result("OFFLINE_PENDING", "http_" + str(http_status))
	var remote := _decode_remote(body)
	if remote.status != "OK": return remote
	if flight.operation == "push":
		if remote.hash != flight.hash or int(remote.revision) != int(flight.revision) + 1: return _result("INVALID_ACK", "local_pending_preserved")
		var next := metadata.duplicate(true)
		next.remote_revision = remote.revision
		next.base_hash = remote.hash
		if next.pending_hash == flight.hash: next.pending_hash = ""
		var saved := _commit(next)
		return _result("SYNCED") if saved.status == "OK" else saved
	return _accept_pull(remote)

func _decode_remote(body: String) -> Dictionary:
	if body.to_utf8_buffer().size() > MAX_RESPONSE: return _result("RESPONSE_SIZE_LIMIT")
	var parser := JSON.new()
	if parser.parse(body) != OK or typeof(parser.data) != TYPE_DICTIONARY: return _result("INVALID_RESPONSE")
	var doc: Dictionary = parser.data
	if not store.base._keys(doc, ["schema","owner_id","character_id","server_revision","snapshot"]): return _result("INVALID_RESPONSE")
	if doc.schema != SCHEMA or doc.owner_id != metadata.subject: return _result("OWNER_MISMATCH")
	if doc.character_id != metadata.character_id: return _result("CHARACTER_MISMATCH")
	if not store._int(doc.server_revision, 1) or typeof(doc.snapshot) != TYPE_STRING: return _result("INVALID_RESPONSE")
	var decoded: Dictionary = store._decode(doc.snapshot, str(metadata.local_owner), content)
	if decoded.status != "OK": return decoded
	if decoded.payload.character.id != metadata.character_id: return _result("CHARACTER_MISMATCH")
	var preserved := _preserve(doc.snapshot)
	if preserved.status != "OK": return preserved
	if decoded.get("migration_required", false): return {"status":"REMOTE_MIGRATION_REQUIRED","preserved_hash":preserved.hash,"reason":"source_snapshot_preserved_no_automatic_overwrite"}
	return {"status":"OK","hash":preserved.hash,"revision":int(doc.server_revision),"payload":decoded.payload}

func _accept_pull(remote: Dictionary) -> Dictionary:
	if int(remote.revision) < int(metadata.remote_revision): return _result("STALE_REMOTE", "newer_local_preserved")
	if not metadata.base_hash.is_empty():
		var baseline := _read_snapshot(metadata.base_hash)
		if baseline.status != "OK": return baseline
		if int(remote.payload.revision) < int(baseline.payload.revision): return _result("STALE_REMOTE", "older_gameplay_revision_preserved")
	if int(remote.revision) == int(metadata.remote_revision) and not metadata.base_hash.is_empty() and remote.hash != metadata.base_hash:
		return _result("INVALID_RESPONSE", "same_server_revision_different_snapshot")
	var next := metadata.duplicate(true)
	if remote.hash == metadata.pending_hash or remote.hash == metadata.base_hash:
		next.remote_revision = remote.revision
		next.base_hash = remote.hash
		if next.pending_hash == remote.hash: next.pending_hash = ""
		next.offer = {}
		return _commit(next)
	if not metadata.pending_hash.is_empty():
		next.conflict = {"local_hash":metadata.pending_hash,"remote_hash":remote.hash,"remote_revision":remote.revision}
		if next.history.size() >= 256: return _result("CONFLICT_HISTORY_LIMIT", "both_snapshots_preserved")
		next.history.append(next.conflict.duplicate(true))
		var saved := _commit(next)
		return _result("CONFLICT", "both_snapshots_preserved_no_merge") if saved.status == "OK" else saved
	next.offer = {"hash":remote.hash,"revision":remote.revision}
	var saved := _commit(next)
	return {"status":"REMOTE_AVAILABLE","payload":remote.payload,"hash":remote.hash} if saved.status == "OK" else saved

func conflict_remote() -> Dictionary:
	if metadata.conflict.is_empty(): return _result("NO_CONFLICT")
	var snapshot := _read_snapshot(metadata.conflict.remote_hash)
	if snapshot.status != "OK": return snapshot
	return {"status":"REMOTE_AVAILABLE","payload":snapshot.payload,"hash":snapshot.hash}

func confirm_remote_saved(payload: Dictionary) -> Dictionary:
	# Invoke ONLY after write_game + read-back succeed, before creating new local
	# progress. This method never writes/overwrites the authoritative game save.
	var encoded := _snapshot_text(payload)
	if encoded.status != "OK": return encoded
	var offer: Dictionary = metadata.offer
	if not offer.is_empty() and not metadata.pending_hash.is_empty() and metadata.pending_hash != encoded.hash: return _result("LOCAL_ADVANCED", "pending_preserved_remote_not_confirmed")
	if offer.is_empty() and not metadata.conflict.is_empty():
		if metadata.pending_hash != metadata.conflict.local_hash: return _result("LOCAL_ADVANCED", "reselect_conflict_before_confirming_remote")
		offer = {"hash":metadata.conflict.remote_hash,"revision":metadata.conflict.remote_revision}
	if offer.is_empty() or encoded.hash != offer.hash: return _result("REMOTE_CONFIRM_MISMATCH")
	var next := metadata.duplicate(true)
	next.base_hash = offer.hash
	next.remote_revision = offer.revision
	next.pending_hash = ""
	next.offer = {}
	next.conflict = {}
	return _commit(next)

func resolve_keep_local() -> Dictionary:
	# Explicit caller/user choice only. The archived remote snapshot remains in
	# history; the next PUT still uses its exact revision as the CAS condition.
	if metadata.conflict.is_empty(): return _result("NO_CONFLICT")
	var next := metadata.duplicate(true)
	next.base_hash = next.conflict.remote_hash
	next.remote_revision = next.conflict.remote_revision
	next.conflict = {}
	next.offer = {}
	return _commit(next)

func perform_request(parent: Node, request: Dictionary) -> Dictionary:
	if request.get("status") != "REQUEST": return request
	if _flight.is_empty() or request.get("id") != _flight.id or _token.is_empty(): return _result("STALE_RESPONSE")
	if store._canonical(request).sha256_text() != _flight.request_hash: return _result("INVALID_REQUEST", "prepared_request_was_modified")
	var http := HTTPRequest.new()
	http.timeout = 15.0
	http.body_size_limit = MAX_RESPONSE
	http.max_redirects = 0 # Never forward Authorization to a redirected origin.
	parent.add_child(http)
	var headers: PackedStringArray = request.headers.duplicate()
	headers.append("Authorization: Bearer " + _token)
	var error := http.request(request.url, headers, int(request.method), request.body)
	if error != OK:
		http.queue_free()
		return accept_response(int(request.id), 0, "", false)
	var response: Array = await http.request_completed
	http.queue_free()
	return accept_response(int(request.id), int(response[1]), response[3].get_string_from_utf8(), int(response[0]) == HTTPRequest.RESULT_SUCCESS)

func _hash(value: Variant, allow_empty: bool = false) -> bool:
	if typeof(value) != TYPE_STRING: return false
	if value.is_empty(): return allow_empty
	if value.length() != 64: return false
	for c in value:
		if c not in "0123456789abcdef": return false
	return true

func _valid_metadata(doc: Dictionary) -> bool:
	if not store.base._keys(doc, ["schema","local_owner","character_id","subject","remote_revision","base_hash","pending_hash","offer","conflict","history"]): return false
	if not store._plain(doc) or doc.schema != META_SCHEMA or not store._id(doc.local_owner) or not store._id(doc.character_id): return false
	if typeof(doc.subject) != TYPE_STRING or (not doc.subject.is_empty() and not store._id(doc.subject)): return false
	if not store._int(doc.remote_revision, -1) or not _hash(doc.base_hash, true) or not _hash(doc.pending_hash, true): return false
	if typeof(doc.offer) != TYPE_DICTIONARY or typeof(doc.conflict) != TYPE_DICTIONARY or typeof(doc.history) != TYPE_ARRAY or doc.history.size() > 256: return false
	if not doc.offer.is_empty() and (not store.base._keys(doc.offer, ["hash","revision"]) or not _hash(doc.offer.hash) or not store._int(doc.offer.revision, 1)): return false
	for row in doc.history + ([] if doc.conflict.is_empty() else [doc.conflict]):
		if not store.base._keys(row, ["local_hash","remote_hash","remote_revision"]) or not _hash(row.local_hash) or not _hash(row.remote_hash) or not store._int(row.remote_revision, 1): return false
	return true

func _read_checkpoint(path: String) -> Dictionary:
	if not store._path(path) or not FileAccess.file_exists(path): return _result("MISSING")
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 128 * 1024: return _result("CHECKPOINT_INVALID")
	var text := file.get_as_text()
	file.close()
	var parser := JSON.new()
	if parser.parse(text) != OK or typeof(parser.data) != TYPE_DICTIONARY: return _result("CHECKPOINT_INVALID")
	var doc: Dictionary = parser.data
	if doc.get("schema") != META_SCHEMA: return _result("UNSUPPORTED_CHECKPOINT", "original_and_backup_preserved")
	var digest: Variant = doc.get("sha256")
	doc.erase("sha256")
	if not _valid_metadata(doc) or typeof(digest) != TYPE_STRING or store._canonical(doc).sha256_text() != digest: return _result("CHECKPOINT_INVALID")
	return {"status":"OK","document":doc}

func _commit(next: Dictionary) -> Dictionary:
	if not _valid_metadata(next): return _result("CHECKPOINT_INVALID")
	var path := root + "checkpoint.json"
	if not store._path(path + ".pending") or not store._path(path + ".backup.pending"): return _result("UNSAFE_PATH")
	if DirAccess.make_dir_recursive_absolute(root) != OK or not store.base._write(path + ".pending", store._encode(next)): return _result("WRITE_FAILED")
	if _read_checkpoint(path + ".pending").status != "OK": return _result("VERIFY_FAILED")
	if FileAccess.file_exists(path):
		var original := FileAccess.get_file_as_bytes(path)
		if _read_checkpoint(path).status != "OK":
			var archive := path + ".corrupt-" + original.hex_encode().sha256_text()
			if not store._path(archive) or (not FileAccess.file_exists(archive) and DirAccess.copy_absolute(path, archive) != OK): return _result("PRESERVATION_FAILED")
		if not store.base._write(path + ".backup.pending", store._encode(metadata)) or _read_checkpoint(path + ".backup.pending").status != "OK": return _result("BACKUP_FAILED")
		if DirAccess.rename_absolute(path + ".backup.pending", path + ".backup") != OK: return _result("BACKUP_FAILED")
	if fault_phase == "before_checkpoint_replace": return _result("INJECTED_FAILURE")
	if DirAccess.rename_absolute(path + ".pending", path) != OK: return _result("REPLACE_FAILED")
	metadata = next
	return _result("OK")
