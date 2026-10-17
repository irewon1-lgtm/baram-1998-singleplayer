extends SceneTree
## Earned G2 save copies only. Independently checks explicit coordinate contract
## application, conservation and atomic archives while timing production loads.
const Store=preload("res://storage/gameplay_store.gd")
const Game=preload("res://state/gameplay_state.gd")
var checks: Array=[]
var timings: Array=[]
var failures:=0
var root_path: String
func check(id: String,passed: bool,detail: Variant="") -> void:
 checks.append({"id":id,"status":"PASS" if passed else "FAIL","detail":detail})
 if not passed:failures+=1;print("FAIL "+id+" "+str(detail))
func put(path: String,bytes: PackedByteArray) -> bool:
 if DirAccess.make_dir_recursive_absolute(path.get_base_dir())!=OK:return false
 var file:=FileAccess.open(path,FileAccess.WRITE)
 if file==null:return false
 file.store_buffer(bytes);file.close()
 return FileAccess.get_file_as_bytes(path)==bytes
func archive_has(path: String,bytes: PackedByteArray) -> bool:
 for filename in DirAccess.get_files_at(path.get_base_dir()):
  if filename.begins_with(path.get_file()+".pre-migration-") and FileAccess.get_file_as_bytes(path.get_base_dir()+"/"+filename)==bytes:return true
 return false
func contract(document: Dictionary,content: Dictionary,store) -> Dictionary:
 for row in content.get("accepted_compatibility",[]):
  if row.profile==document.profile and row.manifest_sha256==document.manifest_sha256 and store._canonical(row.compatibility)==store._canonical(document.compatibility):return row
 return {}
func expected_point(position: Dictionary,transforms: Dictionary,x_key: String="x",y_key: String="y") -> Dictionary:
 var mid: String=str(position.map_id)
 var point:={"map_id":mid,"x":int(position[x_key]),"y":int(position[y_key])}
 if not transforms.has(mid):return point
 var row: Dictionary=transforms[mid]
 var key:=str(point.x)+","+str(point.y)
 var explicit: Dictionary=row.get("cell_mappings",{}).get(key,{})
 point.map_id=str(row.to_map_id)
 point.x=int(explicit.x) if not explicit.is_empty() else int(point.x)+int(row.dx)
 point.y=int(explicit.y) if not explicit.is_empty() else int(point.y)+int(row.dy)
 return point
func compare_progress(old: Dictionary,new: Dictionary,transforms: Dictionary,store,label: String) -> void:
 for key in old:
  if key not in ["character","monsters","loot","pending_actions","summons"]:
   check(label+"_unchanged_"+str(key),new.has(key) and store._canonical(old[key])==store._canonical(new[key]))
 var expected_character: Dictionary=old.character.duplicate(true)
 var point:=expected_point(old.character,transforms)
 for key in point:expected_character[key]=point[key]
 if expected_character.has("discovered_maps"):
  for index in range(expected_character.discovered_maps.size()):
   var mid: String=str(expected_character.discovered_maps[index])
   if transforms.has(mid):expected_character.discovered_maps[index]=str(transforms[mid].to_map_id)
 check(label+"_character_only_explicit_position_changes",store._canonical(new.character)==store._canonical(expected_character))
 check(label+"_all_retained_monster_ids",old.monsters.size()<=new.monsters.size())
 var all_records_exact:=true
 for id in old.monsters:
  if not new.monsters.has(id):all_records_exact=false;break
  var expected: Dictionary=old.monsters[id].duplicate(true)
  point=expected_point(old.monsters[id],transforms)
  var home:=expected_point(old.monsters[id],transforms,"spawn_x","spawn_y")
  for key in point:expected[key]=point[key]
  expected.spawn_x=home.x;expected.spawn_y=home.y
  if store._canonical(new.monsters[id])!=store._canonical(expected):all_records_exact=false;break
 check(label+"_retained_monster_fields_and_explicit_cells_exact",all_records_exact)
 for key in ["loot","summons"]:
  var expected: Array=old.get(key,[]).duplicate(true)
  for row in expected:
   point=expected_point(row,transforms)
   for field in point:row[field]=point[field]
  check(label+"_"+key+"_only_explicit_position_changes",store._canonical(new.get(key,[]))==store._canonical(expected))
 check(label+"_earned_pair_has_no_pending_actions",old.pending_actions.is_empty())
 check(label+"_empty_pending_actions_preserved",new.pending_actions.is_empty())
func _initialize() -> void:
 var args:=OS.get_cmdline_user_args()
 for required in ["--content","--primary","--backup","--report"]:
  if required not in args:push_error("Missing "+required);quit(2);return
 var cp: String=args[args.find("--content")+1]
 var pp: String=args[args.find("--primary")+1]
 var bp: String=args[args.find("--backup")+1]
 var content: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(cp))
 var primary:=FileAccess.get_file_as_bytes(pp)
 var backup:=FileAccess.get_file_as_bytes(bp)
 var pd: Dictionary=JSON.parse_string(primary.get_string_from_utf8())
 var bd: Dictionary=JSON.parse_string(backup.get_string_from_utf8())
 var original_primary_sha:=FileAccess.get_sha256(pp)
 var original_backup_sha:=FileAccess.get_sha256(bp)
 check("exact_g2_content_counts",content.maps.size()==111 and content.items.size()==1105 and content.skills.size()==262 and content.monsters.size()==644 and content.npcs.size()==84)
 check("earned_pair_retains1296_monsters",pd.payload.monsters.size()==1296 and bd.payload.monsters.size()==1296)
 check("same_owner_prior_backup",pd.owner==bd.owner and int(pd.revision)>int(bd.revision) and primary!=backup)
 root_path="user://gameplay-p3/g2-world-save-migration/"+str(Time.get_ticks_usec())+"/"
 var repeats:=3
 if "--repetitions" in args:repeats=int(args[args.find("--repetitions")+1])
 check("bounded_repetitions",repeats>=1 and repeats<=10)
 if failures==0:
  for iteration in range(repeats):
   var path:=root_path+"pair-"+str(iteration)+".json"
   check("exact_primary_copy_"+str(iteration),put(path,primary))
   check("exact_backup_copy_"+str(iteration),put(path+".backup",backup))
   var store=Store.new()
   var prepared: Dictionary=store.prepare_content(content)
   check("private_generation_ready_"+str(iteration),not prepared.is_empty())
   var pinned:=contract(pd,prepared,store)
   var backup_pinned:=contract(bd,prepared,store)
   if "--require-migration" in args:check("both_old_source_generations_explicitly_pinned_"+str(iteration),not pinned.is_empty() and not backup_pinned.is_empty())
   var began:=Time.get_ticks_usec()
   var loaded: Dictionary=store.read_game(path,str(pd.owner),prepared,true)
   var load_ms:=float(Time.get_ticks_usec()-began)/1000.0
   check("explicit_load_succeeds_"+str(iteration),loaded.status=="OK",loaded.get("reason"))
   if loaded.status!="OK":continue
   var prep: Dictionary=loaded.get("backup_preparation",{})
   check("backup_prevalidation_is_reported_"+str(iteration),prep.get("status")=="OK" and float(prep.get("duration_ms",-1))>=0,prep)
   if "--require-migration" in args:check("both_sources_need_explicit_migration_"+str(iteration),loaded.get("migration_required",false) and prep.get("migration_required",false))
   check("load_is_nonmutating_"+str(iteration),FileAccess.get_file_as_bytes(path)==primary and FileAccess.get_file_as_bytes(path+".backup")==backup)
   compare_progress(pd.payload,loaded.payload,pinned.get("map_transforms",{}),store,"source"+str(iteration))
   var game=Game.new()
   check("production_game_configures_"+str(iteration),game.configure(prepared),game.errors)
   var restored: Dictionary=game.restore(loaded.payload)
   check("production_game_restores_"+str(iteration),restored.status=="OK",restored.get("reason"))
   for phase in ["first_after_explicit_load","next_save"]:
    var ticked: Dictionary=game.tick(0.05)
    check("production_tick_"+str(iteration)+phase,ticked.status=="OK")
    var payload: Dictionary=game.snapshot()
    began=Time.get_ticks_usec()
    var saved: Dictionary=store.write_game(path,payload,str(pd.owner),prepared)
    var save_ms:=float(Time.get_ticks_usec()-began)/1000.0
    timings.append({"iteration":iteration,"phase":phase,"explicit_load_ms":load_ms,"backup_preparation":prep,"write_ms":save_ms,"result":saved,"store_phases":store.last_timings.duplicate(true)})
    check("save_succeeds_"+str(iteration)+phase,saved.status=="SAVED",saved)
    var read: Dictionary=store.read_game(path,str(pd.owner),prepared)
    check("committed_candidate_roundtrips_"+str(iteration)+phase,read.status=="OK" and not read.get("migration_required",true) and store._canonical(read.payload)==store._canonical(payload))
    if phase=="first_after_explicit_load":check("backup_exact_old_primary_"+str(iteration),FileAccess.get_file_as_bytes(path+".backup")==primary)
   if loaded.get("migration_required",false):check("primary_original_archived_"+str(iteration),archive_has(path,primary))
   if prep.get("migration_required",false):check("backup_original_archived_"+str(iteration),archive_has(path+".backup",backup))
   for variation in ["unknown_discovery","invalid_discovery_type","unknown_character_map","missing_character"]:
    var malformed: Dictionary=loaded.payload.duplicate(true)
    match variation:
     "unknown_discovery":malformed.character.discovered_maps.append("map:missing-migration-fixture")
     "invalid_discovery_type":malformed.character.discovered_maps=17
     "unknown_character_map":malformed.character.map_id="map:missing-migration-fixture"
     "missing_character":malformed.erase("character")
    var prior_private_state: Dictionary=store._validation_engine.state.duplicate(true)
    var rejected: Dictionary=store._migrate_payload(malformed,{},prepared)
    check("malformed_lazy_migration_refused_"+str(iteration)+variation,rejected.status in ["INVALID_STATE","DEFERRED"],rejected)
    check("malformed_migration_preserves_private_scratch_state_"+str(iteration)+variation,store._canonical(store._validation_engine.state)==store._canonical(prior_private_state))
   var before:=FileAccess.get_file_as_bytes(path)
   var stale: Dictionary=loaded.payload.duplicate(true)
   check("stale_revision_refused_"+str(iteration),store.write_game(path,stale,str(pd.owner),prepared).status=="STALE_REVISION" and FileAccess.get_file_as_bytes(path)==before)
   var conflicting: Dictionary=game.snapshot();conflicting.character.money+=1
   check("same_revision_conflict_refused_"+str(iteration),store.write_game(path,conflicting,str(pd.owner),prepared).status=="REVISION_CONFLICT" and FileAccess.get_file_as_bytes(path)==before)
   check("external_backup_corrupted_"+str(iteration),put(path+".backup","{torn backup".to_utf8_buffer()))
   game.tick(0.05)
   var refused: Dictionary=store.write_game(path,game.snapshot(),str(pd.owner),prepared)
   check("changed_external_backup_rechecked_"+str(iteration),refused.status=="EXISTING_SAVE_NOT_WRITABLE" and FileAccess.get_file_as_bytes(path)==before,refused)
 check("original_primary_untouched",FileAccess.get_sha256(pp)==original_primary_sha)
 check("original_backup_untouched",FileAccess.get_sha256(bp)==original_backup_sha)
 var report:={"schema":"baram.b5.g2-earned-world-save-migration/1","status":"PASS_OBSERVED_STORE_FIXTURE" if failures==0 else "FAIL","failures":failures,"checks":checks,"timings":timings,"store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd"),"test_sha256":FileAccess.get_sha256(get_script().resource_path),"content_sha256":FileAccess.get_sha256(cp),"original_primary_sha256":original_primary_sha,"original_backup_sha256":original_backup_sha,"isolated_test_root":root_path,"engine":Engine.get_version_info(),"platform":OS.get_name(),"scope":"Headless byte-identical earned G2 save copies; independent explicit-coordinate contract and retained progress conservation checks, production restore/ticks/atomic saves. Complete primary+backup load duration is reported separately from later writes. Not rendered frame/native platform/authenticated synchronization proof."}
 var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
 if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
 print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size(),"writes":timings.size()}));quit(0 if failures==0 else 1)
