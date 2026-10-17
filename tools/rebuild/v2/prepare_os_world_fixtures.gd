extends SceneTree
## Isolated QA preconditions only. Never counted as natural progression.
## Production save validation and writer create each initial fixture before GUI starts.
const Store = preload("res://storage/gameplay_store.gd")

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size()!=4:
		printerr("plan seed-save runtime output-index required");quit(2);return
	var plan: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var seed: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var content: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(args[2].path_join("gameplay_content.json")))
	var store=Store.new()
	var definitions: Dictionary=store.prepare_content(content)
	if definitions.is_empty():printerr("INVALID_CONTENT");quit(2);return
	DirAccess.make_dir_recursive_absolute("user://gameplay-p3/characters")
	# First exercise the production old-save coordinate adapter in an isolated
	# copy. Raw old loot/monster positions cannot be relabeled as new geometry.
	var seed_path:="user://gameplay-p3/fixture-seed-source.json"
	var seed_file:=FileAccess.open(seed_path,FileAccess.WRITE)
	seed_file.store_buffer(FileAccess.get_file_as_bytes(args[1]));seed_file.close()
	var migrated: Dictionary=store.read_game(seed_path,str(seed.owner),definitions)
	if migrated.status!="OK":printerr("SEED_MIGRATION_FAILED "+JSON.stringify(migrated));quit(4);return
	var base_payload: Dictionary=migrated.payload
	var records: Array=[]
	for row in plan.cases:
		var payload: Dictionary=base_payload.duplicate(true)
		var character: Dictionary=payload.character
		var prior: Dictionary=character.duplicate(true)
		character.map_id=row.map_id;character.x=row.start[0];character.y=row.start[1]
		character.level=99;character.xp=int(content.xp_thresholds[-1])
		character.hp_max=100000;character.hp=100000;character.dead=false
		if str(row.map_id) not in character.discovered_maps:character.discovered_maps.append(str(row.map_id))
		payload.pending_actions=[];payload.summons=[];payload.buffs={};payload.cooldowns={}
		var filename: String=str(row.case_id)+".json"
		var path: String="user://gameplay-p3/characters/"+filename
		var saved: Dictionary=store.write_game(path,payload,str(seed.owner),definitions)
		var record: Dictionary={"case_id":row.case_id,"save_file":ProjectSettings.globalize_path(path),"receipt":saved,"natural_progression":false,"scope":"OFFLINE_QA_START_FIXTURE_ONLY; subsequent path requires OS input", "seed_character":prior,"fixture_character":character,"other_fixture_changes":["pending_actions cleared","summons cleared","buffs cleared","cooldowns cleared"],"content_sha256":FileAccess.get_file_as_string(args[2].path_join("gameplay_content.json")).sha256_text()}
		if saved.status=="SAVED":
			var hashing:=HashingContext.new();hashing.start(HashingContext.HASH_SHA256);hashing.update(FileAccess.get_file_as_bytes(path));record["sha256"]=hashing.finish().hex_encode()
		records.append(record)
		if saved.status!="SAVED":printerr(JSON.stringify(record));quit(3);return
	var file:=FileAccess.open(args[3],FileAccess.WRITE)
	file.store_string(JSON.stringify({"schema":"baram.os-world-initial-fixtures/1","seed_migration_receipt":{"status":migrated.status,"reason":migrated.get("reason",""),"geometry_changed":migrated.get("geometry_changed",false),"migration_required":migrated.get("migration_required",false)},"records":records},"\t"));file.close()
	print("OFFLINE_QA_FIXTURES "+str(records.size()));quit(0)
