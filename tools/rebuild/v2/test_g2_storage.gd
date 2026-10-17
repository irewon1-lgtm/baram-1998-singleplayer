extends SceneTree
## Explicit G1/G2 fixtures, real files/commands. No private player data is modified.
const Game=preload("res://state/gameplay_state.gd")
const Store=preload("res://storage/gameplay_store.gd")
const Nav=preload("res://input/grid_navigation.gd")
const OWNER="local:g2-storage-fixture"
var checks: Array=[]
var failures:=0
var timings: Dictionary={}
var folder:=""

func check(id: String,ok: bool,detail: Variant=null) -> void:
	checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
	if not ok: failures+=1;print("FAIL "+id+" "+str(detail))
func put(path: String,bytes: PackedByteArray) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file:=FileAccess.open(path,FileAccess.WRITE)
	file.store_buffer(bytes);file.close()
func archived(path: String,bytes: PackedByteArray) -> bool:
	for name in DirAccess.get_files_at(path.get_base_dir()):
		if name.begins_with(path.get_file()+".pre-migration-") and FileAccess.get_file_as_bytes(path.get_base_dir()+"/"+name)==bytes:return true
	return false
func expected(point: Dictionary,contract: Dictionary) -> Dictionary:
	var result: Dictionary=point.duplicate(true)
	if contract.map_transforms.has(str(point.map_id)):
		var transform: Dictionary=contract.map_transforms[str(point.map_id)]
		result.map_id=transform.to_map_id;result.x=int(point.x)+int(transform.dx);result.y=int(point.y)+int(transform.dy)
	return result
func near(game: RefCounted,npc: Dictionary) -> bool:
	for d in [Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT,Vector2i.UP]:
		var p: Vector2i=Vector2i(npc.x,npc.y)+d
		if game.valid_position(str(npc.map_id),p.x,p.y) and not game._occupied(str(npc.map_id),p.x,p.y):
			game.state.character.map_id=npc.map_id;game.state.character.x=p.x;game.state.character.y=p.y;return true
	return false
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	var old: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(args[args.find("--baseline")+1]))
	var current: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(args[args.find("--current")+1]))
	folder="user://gameplay-p3/g2-storage-tests/"+str(Time.get_ticks_usec())+"/"
	var contract: Dictionary={}
	for row in current.accepted_compatibility:
		if row.profile==old.profile and row.manifest_sha256==old.manifest_sha256 and row.compatibility==old.compatibility:contract=row
	check("exact_g1_contract",not contract.is_empty())
	if contract.is_empty():finish(args);return
	var legacy=Game.new();check("baseline_configure",legacy.configure(old),legacy.errors)
	check("baseline_create",legacy.create_character("이전확인",OWNER).status=="OK")
	legacy._spawn_all()
	var baseline: Dictionary=legacy.snapshot()
	var first: String=str(baseline.monsters.keys()[0])
	baseline.monsters[first].hp=0;baseline.monsters[first].alive=false;baseline.monsters[first].respawn_at=1234.5
	baseline.loot=[{"loot_id":"loot:prior","item_id":str(old.items.keys()[0]),"quantity":1,"map_id":baseline.character.map_id,"x":baseline.character.x,"y":baseline.character.y}]
	baseline["summons"]=[{"id":"summon:prior","monster_id":baseline.monsters[first].monster_id,"map_id":baseline.character.map_id,"x":baseline.character.x,"y":baseline.character.y,"expires_at":20.0,"attack_at":0.2,"power":3,"range":4,"interval":1.0}]
	baseline.pending_actions=[{"kind":"attack","map_id":baseline.character.map_id,"x":baseline.character.x,"y":baseline.character.y,"due":0.2,"target_id":first,"target_generation":0,"destination":{"map_id":baseline.character.map_id,"x":baseline.character.x,"y":baseline.character.y}}]
	var store=Store.new();var old_ready: Dictionary=store.prepare_content(old)
	var path:=folder+"g1.json"
	var legacy_write: Dictionary=store.write_game(path,baseline,OWNER,old_ready)
	check("real_g1_file_written",legacy_write.status=="SAVED",legacy_write)
	var original:=FileAccess.get_file_as_bytes(path)
	var current_ready: Dictionary=store.prepare_content(current)
	var started:=Time.get_ticks_usec()
	var read: Dictionary=store.read_game(path,OWNER,current_ready)
	timings.g1_migration_read_ms=float(Time.get_ticks_usec()-started)/1000.0
	check("g1_file_migrates",read.status=="OK" and read.get("migration_required",false),read.get("reason"))
	if read.status!="OK":finish(args);return
	var migrated: Dictionary=read.payload
	check("read_preserves_original_bytes",FileAccess.get_file_as_bytes(path)==original and not archived(path,original))
	for key in ["inventory","equipment","skills","quests","buffs","cooldowns","stats","revision","request_watermarks","rng_state","sim_time"]:
		check("progress_retained_"+key,store._canonical(migrated[key])==store._canonical(baseline[key]))
	var prior_character:=expected(baseline.character,contract)
	check("character_all_fields_only_explicit_offset",store._canonical(migrated.character)==store._canonical(prior_character))
	for id in baseline.monsters:
		var before: Dictionary=baseline.monsters[id];var after:=expected(before,contract)
		var home:=expected({"map_id":before.map_id,"x":before.spawn_x,"y":before.spawn_y},contract)
		after.spawn_x=home.x;after.spawn_y=home.y
		check("monster_current_home_hp_timers_"+str(id),store._canonical(after)==store._canonical(migrated.monsters[id]))
	check("loot_offset",store._canonical(expected(baseline.loot[0],contract))==store._canonical(migrated.loot[0]))
	check("summon_offset",store._canonical(expected(baseline.summons[0],contract))==store._canonical(migrated.summons[0]))
	var action:=expected(baseline.pending_actions[0],contract);action.destination=expected(action.destination,contract)
	check("pending_and_destination_offsets",store._canonical(action)==store._canonical(migrated.pending_actions[0]))
	for mid in old.maps:
		var probe: Dictionary=baseline.duplicate(true)
		for exit in old.maps[mid].get("exits",[]):
			probe.character.map_id=mid;probe.character.x=exit.x;probe.character.y=exit.y;break
		if str(probe.character.map_id)!=str(mid):continue
		var mapped: Dictionary=store._migrate_payload(probe,contract,current_ready)
		check("map_coordinate_offset_"+str(mid),mapped.status=="OK" and store._canonical(mapped.payload.character)==store._canonical(expected(probe.character,contract)))
	check("migration_commit",store.write_game(path,migrated,OWNER,current_ready).status=="SAVED")
	check("archive_and_backup_exact",archived(path,original) and FileAccess.get_file_as_bytes(path+".backup")==original)
	var again: Dictionary=store.read_game(path,OWNER,current_ready)
	check("restart_no_double_offset",again.status=="OK" and not again.migration_required and store._canonical(again.payload)==store._canonical(migrated))
	for phase in Store.MIGRATION_PHASES+Store.PHASES:
		var fault: String=folder+phase+".json";put(fault,original)
		put(fault+".backup",original)
		var before: Dictionary=store.read_game(fault,OWNER,current_ready)
		store.fault_phase=phase
		var written: Dictionary=store.write_game(fault,before.payload,OWNER,current_ready)
		store.fault_phase=""
		var recovered: Dictionary=store.read_game(fault,OWNER,current_ready)
		check("fault_no_false_ack_"+phase,written.status!="SAVED",written.status)
		check("fault_complete_snapshot_"+phase,recovered.status=="OK" and store._canonical(recovered.payload.character)==store._canonical(migrated.character) and (archived(fault,original) or archived(fault+".backup",original)),recovered.get("status"))
	var game=Game.new();check("g2_configure",game.configure(current),game.errors)
	check("g2_create",game.create_character("확장저장",OWNER).status=="OK")
	check("lazy_city_has_no_global_spawns",game.state.monsters.is_empty())
	var field: String="gp:map:south_field";var landing: Dictionary={}
	for exit in current.maps["gp:map:domestic_city"].exits:
		if str(exit.to_map)==field:landing=exit;break
	check("normal_transition_spawn",not landing.is_empty() and game._transition(field,int(landing.to_x),int(landing.to_y),0,"fixture_transition") and game.state.monsters.size()==current.maps[field].spawns.size())
	var spawn: String=str(game.state.monsters.keys()[0]);game.state.monsters[spawn].alive=false;game.state.monsters[spawn].hp=0;game.state.monsters[spawn].respawn_at=1000.0
	var dead: Dictionary=game.state.monsters[spawn].duplicate(true)
	game._spawn_map(field);check("map_reentry_retains_dead_timer",store._canonical(dead)==store._canonical(game.state.monsters[spawn]))
	game.state.character.level=99;game.state.character.xp=current.xp_thresholds[-1]
	var node: Dictionary=current.maps[field].gather_nodes[0]
	check("gather_near_fixture",near(game,{"map_id":field,"x":node.x,"y":node.y}))
	var gather_cmd: Dictionary={"type":"gather","node_id":node.id,"request_id":"gather:1"}
	var gather: Dictionary=game.command(gather_cmd)
	var amount: int=game.item_count(str(node.item_id));var revision: int=int(game.state.revision)
	check("gather_actual_award",gather.status=="OK" and amount==int(node.get("quantity",1)))
	check("gather_request_duplicate",game.command(gather_cmd).status=="DUPLICATE" and game.item_count(str(node.item_id))==amount and game.state.revision==revision)
	check("gather_cooldown_rollback",game.command({"type":"gather","node_id":node.id,"request_id":"gather:2"}).reason=="GATHER_NOT_READY" and game.item_count(str(node.item_id))==amount and game.state.revision==revision)
	var gather_path:=folder+"gather.json";var gathered_save: Dictionary=store.write_game(gather_path,game.snapshot(),OWNER,current_ready)
	check("gather_save",gathered_save.status=="SAVED",gathered_save)
	var gather_read: Dictionary=store.read_game(gather_path,OWNER,current_ready)
	check("gather_restart_cooldown",gather_read.status=="OK" and gather_read.payload.gathered_nodes[node.id]==game.state.gathered_nodes[node.id])
	var guides: Array=[]
	for npc in current.npcs.values():
		if "travel" in npc.get("services",[]):guides.append(npc)
	var guide: Dictionary=guides[0];var destination: Dictionary=guides[-1]
	check("travel_near_fixture",near(game,guide))
	game.state.character.discovered_maps=[str(guide.map_id)]
	var cmd: Dictionary={"type":"travel","npc_id":guide.id,"map_id":destination.map_id,"request_id":"travel:1"}
	var before_money: int=int(game.state.character.money)
	check("travel_unseen_refused",game.command(cmd).reason=="DESTINATION_NOT_DISCOVERED" and game.state.character.money==before_money)
	game.state.character.discovered_maps.append(str(destination.map_id));game.state.character.money=0
	check("travel_unaffordable_refused",game.command(cmd).reason=="INSUFFICIENT_MONEY" and game.state.character.money==0)
	game.state.character.money=100000
	var travel: Dictionary=game.command(cmd)
	check("travel_actual_command",travel.status=="OK" and str(game.state.character.map_id)==str(destination.map_id) and int(game.state.character.money)<100000,travel)
	var paid: int=int(game.state.character.money)
	check("travel_duplicate_no_charge",game.command(cmd).status=="DUPLICATE" and int(game.state.character.money)==paid)
	var full=Game.new();full.configure(current);full.create_character("세계보존",OWNER);full._spawn_all()
	var full_path:=folder+"all-visited.json";started=Time.get_ticks_usec()
	var full_write: Dictionary=store.write_game(full_path,full.snapshot(),OWNER,current_ready)
	timings.full_world_write_ms=float(Time.get_ticks_usec()-started)/1000.0
	timings.full_world_file_bytes=FileAccess.get_file_as_bytes(full_path).size();timings.full_world_monsters=full.state.monsters.size()
	started=Time.get_ticks_usec();var full_read: Dictionary=store.read_game(full_path,OWNER,current_ready)
	timings.full_world_read_ms=float(Time.get_ticks_usec()-started)/1000.0
	var expected_monsters:=0
	for map in current.maps.values():expected_monsters+=map.get("spawns",[]).size()
	check("all_defined_monsters_saved_restored",full_write.status=="SAVED" and full_read.status=="OK" and full_read.payload.monsters.size()==expected_monsters and expected_monsters==2026 and store._canonical(full_read.payload)==store._canonical(full.snapshot()),expected_monsters)
	check("full_world_below_4MiB",timings.full_world_file_bytes<4194304,timings)
	var poison_id:=""
	for id in full.state.monsters:
		if str(current.monsters[full.state.monsters[id].monster_id].get("on_hit_status",""))=="poison":poison_id=str(id);break
	var poison: Dictionary=full.state.monsters[poison_id]
	check("poison_position_fixture",near(full,poison))
	full.state.character.hp=1000000;full.state.character.hp_max=1000000
	full.state.pending_actions=[{"kind":"monster_attack","map_id":poison.map_id,"target_id":poison_id,"target_generation":poison.generation,"due":0.0}]
	full.tick(0.05)
	var poison_key:="monster:"+poison_id
	check("actual_monster_hit_status",full.state.buffs.has(poison_key) and str(full.state.buffs[poison_key].status)=="poison")
	var poisoned_path:=folder+"poisoned.json"
	var poison_write: Dictionary=store.write_game(poisoned_path,full.snapshot(),OWNER,current_ready)
	var poison_read: Dictionary=store.read_game(poisoned_path,OWNER,current_ready)
	check("enemy_status_save_restart",poison_write.status=="SAVED" and poison_read.status=="OK" and poison_read.payload.buffs.has(poison_key),poison_write)
	var forged: Dictionary=full.snapshot();forged.buffs["monster:unknown"]=forged.buffs[poison_key].duplicate(true)
	check("unknown_enemy_status_refused",store.validate_payload(forged,OWNER,current_ready).status!="OK")
	full.state.buffs={};full.state.pending_actions=[]
	full.state.character.map_id=current.start.map_id;full.state.character.x=current.start.x;full.state.character.y=current.start.y
	# Incremental navigation must yield within its supplied expansion budget.
	var nav=Nav.new();var target:=Vector2i(140,276);nav.begin(full,target)
	var frames:=0;var max_ms:=0.0
	while not nav.finished and frames<10000:
		started=Time.get_ticks_usec();nav.advance(96);max_ms=maxf(max_ms,float(Time.get_ticks_usec()-started)/1000.0);frames+=1
	check("city_incremental_path_finishes",nav.finished and not nav.result.is_empty() and nav.result[-1]==target,{"frames":frames,"path_cells":nav.result.size(),"max_step_ms":max_ms})
	var valid:=true;var prior:=Vector2i(full.state.character.x,full.state.character.y)
	for cell in nav.result:
		if not full.can_step(str(full.state.character.map_id),prior.x,prior.y,cell.x,cell.y):valid=false
		prior=cell
	check("city_path_respects_edges",valid)
	finish(args)
func finish(args: PackedStringArray) -> void:
	var report: Dictionary={"schema":"baram.g2.storage/1","status":"PASS" if failures==0 else "FAIL","scope":"Explicit test state; real G1/G2 store writes, migration archives, interruption hooks and commands. No native platform or natural-all-world claim.","failures":failures,"checks":checks,"timings":timings,"store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd")}
	put(args[args.find("--report")+1],(JSON.stringify(report,"  ")+"\n").to_utf8_buffer())
	print("G2_STORAGE "+str(checks.size())+" checks, "+str(failures)+" failures");quit(0 if failures==0 else 1)
