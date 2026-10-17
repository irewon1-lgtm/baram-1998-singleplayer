extends SceneTree
## Explicit geometry-table migration; synthetic progress, actual store/files.
const Store=preload("res://storage/gameplay_store.gd")
const Game=preload("res://state/gameplay_state.gd")
const Fixture=preload("res://../../tools/rebuild/v2/test_migration.gd")
const OWNER="local:v2-migration-test"
var checks: Array=[]
var failures:=0
var test_root:=""
func check(id: String, passed: bool, details: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed:
		failures+=1
		print("FAIL "+id+" "+str(details))
func put(path: String,text: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file:=FileAccess.open(path,FileAccess.WRITE)
	if file: file.store_string(text);file.close()
func archive_has(source: String, original: PackedByteArray) -> bool:
	for filename in DirAccess.get_files_at(source.get_base_dir()):
		if filename.begins_with(source.get_file()+".pre-migration-") and FileAccess.get_file_as_bytes(source.get_base_dir()+"/"+filename)==original: return true
	return false
func geometry(old: Dictionary) -> Dictionary:
	var current: Dictionary=old.duplicate(true)
	current.compatibility.map_geometry="table-geometry-2"
	current.manifest_sha256="c".repeat(64)
	current.require_geometry_migration_contract=true
	current.maps["map:town"].blocked.append([4,4])
	current.accepted_compatibility=[{"profile":old.profile,"compatibility":old.compatibility.duplicate(true),"manifest_sha256":old.manifest_sha256,"map_transforms":{"map:town":{"to_map_id":"map:town","dx":0,"dy":0,"cell_mappings":{"4,4":{"x":4,"y":3}}}}}]
	return current
func payload(old: Dictionary) -> Dictionary:
	var game=Game.new()
	check("fixture_configures",game.configure(old),game.errors)
	check("fixture_creates",game.create_character("좌표이전",OWNER).status=="OK")
	var state: Dictionary=game.snapshot()
	state.character.x=4;state.character.y=4
	var monster: Dictionary=state.monsters["spawn:rabbit1"]
	monster.x=4;monster.y=4;monster.spawn_x=4;monster.spawn_y=4
	state.loot=[{"loot_id":"loot:table","item_id":"item:acorn","quantity":2,"map_id":"map:town","x":4,"y":4}]
	state["summons"]=[{"id":"summon:table","monster_id":"monster:rabbit","map_id":"map:town","x":4,"y":4,"expires_at":20.0,"attack_at":0.2,"power":3,"range":4,"interval":1.0}]
	state.pending_actions=[{"kind":"attack","map_id":"map:town","x":4,"y":4,"due":0.2,"target_id":"spawn:rabbit1","target_generation":0,"destination":{"map_id":"map:town","x":4,"y":4}}]
	return state
func test_real_tables(args: PackedStringArray) -> void:
	var old_path: String=args[args.find("--baseline")+1]
	var new_path: String=args[args.find("--current")+1]
	var old: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(old_path))
	var current: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(new_path))
	var contract: Dictionary={}
	for row in current.get("accepted_compatibility",[]):
		if row.profile==old.profile and row.manifest_sha256==old.manifest_sha256 and row.compatibility==old.compatibility: contract=row
	check("real_exact_old_generation_contract_present",not contract.is_empty() and bool(current.get("require_geometry_migration_contract",false)))
	if contract.is_empty(): return
	var engine=Game.new()
	check("real_old_generation_configures",engine.configure(old),engine.errors)
	check("real_character_created",engine.create_character("전체맵이전",OWNER).status=="OK")
	var base: Dictionary=engine.snapshot()
	var old_store=Store.new()
	var old_definitions: Dictionary=old_store.prepare_content(old)
	var samples: Array=[]
	for map_id in contract.get("map_transforms",{}):
		var cells: Dictionary=contract.map_transforms[map_id].get("cell_mappings",{})
		if cells.is_empty(): continue
		var key: String=str(cells.keys()[0])
		var source: PackedStringArray=key.split(",")
		var target: Dictionary=cells[key]
		var state: Dictionary=base.duplicate(true)
		state.character.map_id=map_id;state.character.x=int(source[0]);state.character.y=int(source[1])
		var monster_id: String=str(state.monsters.keys()[0])
		for id in state.monsters:
			if state.monsters[id].map_id==map_id: monster_id=str(id);break
		var monster: Dictionary=state.monsters[monster_id]
		monster.map_id=map_id;monster.x=int(source[0]);monster.y=int(source[1]);monster.spawn_x=int(source[0]);monster.spawn_y=int(source[1])
		state.loot=[{"loot_id":"loot:real-table","item_id":str(old.items.keys()[0]),"quantity":1,"map_id":map_id,"x":int(source[0]),"y":int(source[1])}]
		state["summons"]=[{"id":"summon:real-table","monster_id":monster.monster_id,"map_id":map_id,"x":int(source[0]),"y":int(source[1]),"expires_at":20.0,"attack_at":0.2,"power":3,"range":4,"interval":1.0}]
		state.pending_actions=[{"kind":"attack","map_id":map_id,"x":int(source[0]),"y":int(source[1]),"due":0.2,"target_id":monster_id,"target_generation":int(monster.generation),"destination":{"map_id":map_id,"x":int(source[0]),"y":int(source[1])}}]
		var path: String=test_root+"real-map-"+str(samples.size())+".json"
		var written: Dictionary=old_store.write_game(path,state,OWNER,old_definitions)
		check("real_old_cell_saved_"+str(map_id),written.status=="SAVED",written)
		if written.status!="SAVED": continue
		samples.append({"map_id":map_id,"path":path,"target":target,"original":FileAccess.get_file_as_bytes(path),"monster_id":monster_id,"revision":state.revision,"money":state.character.money})
	var new_store=Store.new()
	var new_definitions: Dictionary=new_store.prepare_content(current)
	check("real_new_generation_prepares",not new_definitions.is_empty())
	for sample in samples:
		var read: Dictionary=new_store.read_game(sample.path,OWNER,new_definitions)
		check("real_map_table_migration_"+sample.map_id,read.status=="OK" and read.get("migration_required",false),read.get("reason"))
		if read.status!="OK": continue
		var mapped: Dictionary=read.payload
		var positions: Array=[mapped.character,mapped.monsters[sample.monster_id],mapped.loot[0],mapped.summons[0],mapped.pending_actions[0],mapped.pending_actions[0].destination]
		var all_mapped:=true
		for point in positions:
			if point.map_id!=sample.map_id or int(point.x)!=int(sample.target.x) or int(point.y)!=int(sample.target.y): all_mapped=false
		var monster: Dictionary=mapped.monsters[sample.monster_id]
		check("real_all_object_positions_"+sample.map_id,all_mapped and int(monster.spawn_x)==int(sample.target.x) and int(monster.spawn_y)==int(sample.target.y))
		check("real_original_and_progress_retained_"+sample.map_id,FileAccess.get_file_as_bytes(sample.path)==sample.original and mapped.monsters.size()==base.monsters.size() and mapped.revision==sample.revision and mapped.character.money==sample.money)
		# Persist each migrated representative with actual preservation/atomic
		# commit, then reopen without applying any table for a second time.
		var written: Dictionary=new_store.write_game(sample.path,mapped,OWNER,new_definitions)
		var again: Dictionary=new_store.read_game(sample.path,OWNER,new_definitions)
		check("real_map_commit_archive_and_restart_"+sample.map_id,written.status=="SAVED" and archive_has(sample.path,sample.original) and again.status=="OK" and not again.migration_required and new_store._canonical(again.payload.character)==new_store._canonical(mapped.character))
	print("REAL_CELL_MIGRATION_MAPS="+str(samples.size()))

func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var fixture=Fixture.new()
	var old: Dictionary=fixture.fixture_content()
	fixture.free()
	var current:=geometry(old)
	var saved:=payload(old)
	var store=Store.new()
	test_root="user://gameplay-p3/cell-migration-tests/"+str(Time.get_ticks_usec())+"/"
	var path:=test_root+"geometry.json"
	var initial: Dictionary=store.write_game(path,saved,OWNER,old)
	check("legacy_all_object_types_saved",initial.status=="SAVED",initial)
	if initial.status!="SAVED":
		print("INITIAL_FIXTURE_INVALID "+str(initial));quit(1);return
	var original:=FileAccess.get_file_as_bytes(path)
	var read: Dictionary=store.read_game(path,OWNER,current)
	check("geometry_only_exact_contract_applies",read.status=="OK" and read.get("migration_required",false),read.get("reason"))
	if read.status=="OK":
		var value: Dictionary=read.payload
		for row in [value.character,value.monsters["spawn:rabbit1"],value.loot[0],value.summons[0],value.pending_actions[0],value.pending_actions[0].destination]:
			check("same_cell_object_preserved_"+str(checks.size()),row.x==4 and row.y==3 and row.map_id=="map:town",row)
		check("monster_home_explicit_table_mapped",value.monsters["spawn:rabbit1"].spawn_x==4 and value.monsters["spawn:rabbit1"].spawn_y==3)
		check("read_never_modifies_old_primary",FileAccess.get_file_as_bytes(path)==original and not archive_has(path,original))
		check("progress_ids_counts_and_revision_retained",value.character.id==saved.character.id and value.character.money==saved.character.money and value.revision==saved.revision and value.monsters.keys()==saved.monsters.keys() and value.loot.size()==1 and value.summons.size()==1 and value.pending_actions.size()==1)
		check("explicit_save_commits_mapped_same_revision",store.write_game(path,value,OWNER,current).status=="SAVED")
		check("source_archive_and_previous_backup_exact",archive_has(path,original) and FileAccess.get_file_as_bytes(path+".backup")==original)
		var after: Dictionary=store.read_game(path,OWNER,current)
		check("new_generation_never_maps_twice",after.status=="OK" and not after.migration_required and after.payload.character.y==3)
		check("old_reader_never_reverse_maps_or_rewrites",store.read_game(path,OWNER,old).get("payload",{}).get("character",{}).get("y")==3)
	# A table is authoritative, not a nearest-cell guess or broad manifest waiver.
	for scenario in ["missing_contract","wrong_manifest","wrong_profile","wrong_geometry_pin","bad_target_cell","bad_target_map","malformed_unused_mapping","noncanonical_source_cell","unknown_transform_field"]:
		var changed: Dictionary=current.duplicate(true)
		match scenario:
			"missing_contract": changed.accepted_compatibility=[]
			"wrong_manifest": changed.accepted_compatibility[0].manifest_sha256="d".repeat(64)
			"wrong_profile": changed.accepted_compatibility[0].profile="other"
			"wrong_geometry_pin": changed.accepted_compatibility[0].compatibility.map_geometry="not-old"
			"bad_target_cell": changed.accepted_compatibility[0].map_transforms["map:town"].cell_mappings["4,4"]={"x":4,"y":4}
			"bad_target_map": changed.accepted_compatibility[0].map_transforms["map:town"].to_map_id="map:absent"
			"malformed_unused_mapping": changed.accepted_compatibility[0].map_transforms["map:town"].cell_mappings["8,8"]={"x":1}
			"noncanonical_source_cell": changed.accepted_compatibility[0].map_transforms["map:town"].cell_mappings["04,4"]={"x":1,"y":1}
			"unknown_transform_field": changed.accepted_compatibility[0].map_transforms["map:town"].unapproved=true
		var refused: String=test_root+scenario+".json"
		put(refused,original.get_string_from_utf8())
		var result: Dictionary=store.read_game(refused,OWNER,changed)
		check("refused_"+scenario,result.status!="OK" and result.status!="RECOVERED_BACKUP" and FileAccess.get_file_as_bytes(refused)==original and not archive_has(refused,original),result.status)
		var attempted: Dictionary=read.payload.duplicate(true)
		attempted.revision+=1
		var rejected: Dictionary=store.write_game(refused,attempted,OWNER,changed)
		check("refused_writer_preserves_source_"+scenario,rejected.status!="SAVED" and FileAccess.get_file_as_bytes(refused)==original and not archive_has(refused,original),rejected.status)
	var unmapped: Dictionary=saved.duplicate(true)
	unmapped.character.x=5;unmapped.character.y=4
	var unmapped_path:=test_root+"unmapped.json"
	store.write_game(unmapped_path,unmapped,OWNER,old)
	var unchanged: Dictionary=store.read_game(unmapped_path,OWNER,current)
	check("unlisted_safe_cell_keeps_position",unchanged.status=="OK" and unchanged.payload.character.x==5 and unchanged.payload.character.y==4)
	for phase in Store.MIGRATION_PHASES+Store.PHASES:
		var fault_path: String=test_root+phase+".json"
		store.write_game(fault_path,saved,OWNER,old)
		var next: Dictionary=saved.duplicate(true)
		next.revision+=1;next.character.money+=1
		store.write_game(fault_path,next,OWNER,old)
		var before:=FileAccess.get_file_as_bytes(fault_path)
		var backup_before:=FileAccess.get_file_as_bytes(fault_path+".backup")
		var migrated: Dictionary=store.read_game(fault_path,OWNER,current)
		if migrated.status!="OK":
			check("fault_fixture_read_"+phase,false,migrated)
			continue
		store.fault_phase=phase
		var written: Dictionary=store.write_game(fault_path,migrated.payload,OWNER,current)
		store.fault_phase=""
		var recovered: Dictionary=store.read_game(fault_path,OWNER,current)
		check("fault_no_false_ack_"+phase,written.status!="SAVED",written.status)
		check("fault_old_or_new_complete_mapped_snapshot_"+phase,recovered.status=="OK" and recovered.payload.character.y==3 and (archive_has(fault_path,before) or (phase=="after_migration_backup_preserved" and archive_has(fault_path+".backup",backup_before))))
	if "--baseline" in args and "--current" in args: test_real_tables(args)
	var report: Dictionary={"schema":"baram.v2.cell-migration/1","scope":"Synthetic exact geometry migration tables and filesystem boundary faults; no real user save/native-device claim","status":"PASS" if failures==0 else "FAIL","checks":checks,"failures":failures,"platform":OS.get_name(),"store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd")}
	if "--report" in args:
		var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify(report));quit(0 if failures==0 else 1)
