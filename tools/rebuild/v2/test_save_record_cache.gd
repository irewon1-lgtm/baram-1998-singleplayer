extends SceneTree
## Cached JSON type/serialization proofs; semantics remain authoritative.
const Store=preload("res://storage/gameplay_store.gd")
const Game=preload("res://state/gameplay_state.gd")
const Fixture=preload("res://../../tools/rebuild/v2/test_migration.gd")
const OWNER="local:record-cache-test"
var checks: Array=[]
var failures:=0
func check(id: String, passed: bool, detail: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","detail":detail})
	if not passed:failures+=1
func document(payload: Dictionary,content: Dictionary) -> Dictionary:
	return {"schema":Store.SCHEMA,"owner":OWNER,"revision":payload.revision,"profile":content.profile,"compatibility":content.compatibility,"manifest_sha256":content.manifest_sha256,"payload":payload}
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var fixture=Fixture.new()
	var content: Dictionary=fixture.fixture_content();fixture.free()
	var game=Game.new();game.configure(content);game.create_character("문자캐시",OWNER)
	var payload: Dictionary=game.snapshot()
	var store=Store.new()
	var prepared: Dictionary=store.prepare_content(content)
	check("prewarm_does_not_change_created_payload",store._plain(payload) and store.validate_payload(payload,OWNER,prepared).status=="OK")
	var id: String=str(payload.monsters.keys()[0])
	for variation in ["initial","integral_float","fractional_timer","nested_metadata","reordered_keys","post_warm_mutation"]:
		var state: Dictionary=payload.duplicate(true)
		match variation:
			"integral_float": state.monsters[id].x=float(state.monsters[id].x);state.monsters[id].hp=float(state.monsters[id].hp)
			"fractional_timer": state.monsters[id].ai_at=21.310000000000166;state.monsters[id].respawn_at=0.123456789
			"nested_metadata": state.monsters[id]["codec_fixture"]={"한글":"줄바꿈\n따옴표\"\\","array":[true,null,1,1.0,1.0000002,-0.00000001]}
			"reordered_keys":
				var old: Dictionary=state.monsters[id];var reordered: Dictionary={};var keys: Array=old.keys();keys.reverse()
				for key in keys:reordered[key]=old[key]
				state.monsters[id]=reordered
			"post_warm_mutation": state.monsters[id].generation+=1;state.monsters[id].ai_at+=0.2
		var doc:=document(state,content)
		check("cached_encoding_matches_full_canonical_"+variation,store._canonical_save_document(doc)==store._canonical(doc))
		check("cached_plain_matches_full_plain_"+variation,store._plain_game_payload(state)==store._plain(state))
		var encoded: Dictionary=JSON.parse_string(store._encode(doc));var digest: String=encoded.sha256;encoded.erase("sha256")
		check("encoded_checksum_uses_original_numeric_contract_"+variation,store._canonical(encoded).sha256_text()==digest)
	for variation in ["nan","infinity","stringname_key","stringname_existing_key","stringname_existing_value","object","depth"]:
		var state: Dictionary=payload.duplicate(true)
		store._plain_game_payload(state)
		match variation:
			"nan": state.monsters[id].hp=NAN
			"infinity": state.monsters[id].ai_at=INF
			"stringname_key": state.monsters[id][StringName("invalid_key")]=true
			"stringname_existing_key": state.monsters[id].erase("hp");state.monsters[id][StringName("hp")]=6
			"stringname_existing_value": state.monsters[id]["monster_id"]=StringName("monster:rabbit")
			"object": state.monsters[id]["not_json"]=RefCounted.new()
			"depth":
				var nested: Array=[]
				for index in range(26):nested=[nested]
				state.monsters[id]["deep"]=nested
		check("warm_cache_rechecks_changed_invalid_type_"+variation,not store._plain_game_payload(state) and not store._plain(state))
	var invalid: Dictionary=payload.duplicate(true)
	store._plain_game_payload(invalid)
	invalid.monsters[id].hp=999999
	check("plain_reuse_never_approves_invalid_hp",store.validate_payload(invalid,OWNER,prepared).status!="OK")
	invalid=payload.duplicate(true);store._plain_game_payload(invalid);invalid.monsters[id].respawn_at=-1.0
	check("plain_reuse_never_approves_invalid_timer",store.validate_payload(invalid,OWNER,prepared).status!="OK")
	var many: Dictionary=payload.duplicate(true)
	many.monsters={}
	for index in range(1100):
		var row: Dictionary=payload.monsters[id].duplicate(true);row.id="spawn:bounded"+str(index)
		many.monsters[row.id]=row
	var large_doc:=document(many,content)
	check("cache_eviction_preserves_full_canonical",store._canonical_save_document(large_doc)==store._canonical(large_doc))
	check("monster_value_cache_is_bounded",store._monster_record_cache.size()<=Store.MONSTER_RECORD_CACHE_LIMIT,store._monster_record_cache.size())
	check("oversized_world_still_rejected",store.validate_payload(many,OWNER,prepared).status!="OK")
	var report: Dictionary={"schema":"baram.b5.save-record-cache/1","status":"PASS" if failures==0 else "FAIL","failures":failures,"checks":checks,"scope":"Synthetic cache equivalence/invalid type/range/alias-change fixtures; no device performance claim","store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd")}
	if "--report" in args:
		var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
		if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify(report));quit(0 if failures==0 else 1)
