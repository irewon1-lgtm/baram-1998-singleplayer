extends SceneTree
## Targeted production-command regression. The first branch restores an immutable
## real failed-play save without edits. Other branches explicitly seed collision
## fixtures; they do not claim natural progression, OS input or native execution.
const Game=preload("res://state/gameplay_state.gd")
const Store=preload("res://storage/gameplay_store.gd")
const EAST="gp:map:east_field"
const CITY="gp:map:domestic_city"
const RETURN="KRO-972853314e6a"
const SHRINE="KRO-33876779ed3b"
var content: Dictionary={}
var payload: Dictionary={}
var checks: Array=[]
var commands: Array=[]
var sequence:=0
var failures:=0
var report:=""
var source_save:=""
var content_path:=""

func arg(key: String,fallback: String="") -> String:
	var args:=OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i]==key:return args[i+1]
	return fallback

func _initialize() -> void:
	report=arg("--report");source_save=arg("--save");content_path=arg("--content")
	call_deferred("run")

func check(id: String,good: bool,observed: Variant=null) -> bool:
	checks.append({"id":id,"result":"PASS" if good else "FAIL","observed":observed})
	if not good:failures+=1;printerr("ARRIVAL_FAIL "+id+" "+JSON.stringify(observed))
	return good

func fresh(definitions: Dictionary={},saved: Dictionary={}) -> RefCounted:
	var game:=Game.new()
	check("production_definitions_configure",game.configure(content if definitions.is_empty() else definitions),game.errors)
	var restored: Dictionary=game.restore(payload if saved.is_empty() else saved)
	check("production_payload_restore",restored.status=="OK",restored)
	return game

func send(game: RefCounted,cmd: Dictionary,label: String) -> Dictionary:
	sequence+=1;cmd=cmd.duplicate(true);cmd.request_id="arrival-regression:"+str(sequence)
	var result: Dictionary=game.command(cmd)
	commands.append({"label":label,"command":cmd,"result":result,"character":game.state.character.duplicate(true),"revision":game.state.revision})
	return result

func event(result: Dictionary,type: String) -> Dictionary:
	for row in result.get("events",[]):
		if row.get("type")==type:return row
	return {}

func point(map_id: String,x: int,y: int) -> Dictionary:
	return {"map_id":map_id,"x":x,"y":y,"direction":"east"}

func defs_for_arrival(anchor: Dictionary=point(EAST,2,16)) -> Dictionary:
	var defs:=content.duplicate(true)
	defs.gates.east=anchor.duplicate(true)
	defs.nation_gates["고구려"].east=anchor.duplicate(true)
	defs.return_points["고구려"]=anchor.duplicate(true)
	defs.respawn=anchor.duplicate(true)
	defs["shrine"]=anchor.duplicate(true)
	return defs

func fixture(anchor_occupied: bool=true,sealed: bool=false) -> Dictionary:
	var saved:=payload.duplicate(true)
	saved.pending_actions=[];saved.cooldowns={}
	# Keep every world monster/ID. Position copies only create explicit collision
	# fixtures; source save and natural character payload remain immutable.
	var ids: Array=[]
	for id in saved.monsters:
		if saved.monsters[id].alive:ids.append(id)
	ids.sort()
	var target: Dictionary=saved.monsters["gp:spawn:east:2:0"]
	target.x=2 if anchor_occupied else 6;target.y=16 if anchor_occupied else 20
	if sealed:
		var positions:=[Vector2i(2,15),Vector2i(3,16),Vector2i(2,17)]
		for i in range(positions.size()):
			var id: String=str(ids[i])
			if id=="gp:spawn:east:2:0":id=str(ids[positions.size()])
			var monster: Dictionary=saved.monsters[id]
			monster.map_id=EAST;monster.x=positions[i].x;monster.y=positions[i].y
	return saved

func character_unchanged(a: Dictionary,b: Dictionary) -> bool:
	return a.character==b.character and a.inventory==b.inventory and a.monsters==b.monsters and a.cooldowns==b.cooldowns and a.revision==b.revision and a.pending_actions==b.pending_actions and a.request_watermarks==b.request_watermarks

func actual_branch() -> void:
	var game:=fresh()
	check("actual_save_has_original_offmap_anchor_blocker",game.state.character.map_id==CITY and game.state.character.x==61 and game.state.character.y==32 and game.state.monsters["gp:spawn:east:2:0"].alive and game.state.monsters["gp:spawn:east:2:0"].x==2 and game.state.monsters["gp:spawn:east:2:0"].y==16)
	var before: Dictionary=game.snapshot()
	var moved:=send(game,{"type":"move","dx":1,"dy":0},"actual_unmodified_failed_save_exit")
	if arg("--baseline-only")=="yes":
		check("original_engine_reproduces_real_deadlock",moved.status=="REFUSED" and moved.reason=="DESTINATION_UNAVAILABLE" and character_unchanged(before,game.snapshot()),moved)
		return
	var changed:=event(moved,"map_changed")
	check("actual_failed_exit_recovers_without_state_reset",moved.status=="OK" and moved.reason=="MAP_TRANSITION" and game.state.character.map_id==EAST and game.state.character.x==2 and game.state.character.y==15,changed)
	check("actual_recovery_preserves_all_monsters_exactly",before.monsters==game.state.monsters,{"count_before":before.monsters.size(),"count_after":game.state.monsters.size(),"blocker_before":before.monsters["gp:spawn:east:2:0"],"blocker_after":game.state.monsters["gp:spawn:east:2:0"]})
	check("actual_recovery_no_money_xp_item_resource_grants",before.inventory==game.state.inventory and before.character.money==game.state.character.money and before.character.xp==game.state.character.xp and before.character.hp==game.state.character.hp and before.character.mp==game.state.character.mp)
	var store:=Store.new();var path:="user://gameplay-p3/arrival-regression/actual-recovered.json"
	for suffix in ["",".backup",".pending",".backup.pending"]:
		if FileAccess.file_exists(path+suffix):DirAccess.remove_absolute(path+suffix)
	var written: Dictionary=store.write_game(path,game.snapshot(),str(game.state.character.owner_id),content)
	var loaded: Dictionary=store.read_game(path,str(game.state.character.owner_id),content)
	# Store's declared microsecond timer canonicalization is the established
	# roundtrip contract; raw float equality incorrectly rejects binary tails.
	check("actual_recovery_production_save_and_readback",written.status=="SAVED" and loaded.status=="OK" and store._canonical(loaded.payload)==store._canonical(game.snapshot()),{"write":written,"read_status":loaded.status,"path":path,"comparison":"existing_production_microsecond_canonical_contract","memory_move_timer":String.num(float(game.state.cooldowns.move),16),"disk_move_timer":String.num(float(loaded.payload.cooldowns.move),16) if loaded.status=="OK" else ""})
	if loaded.status=="OK":
		var reloaded:=fresh({},loaded.payload)
		check("actual_recovery_new_engine_restores_same_world",store._canonical(reloaded.snapshot())==store._canonical(game.snapshot()))

func exit_fixtures() -> void:
	var clear:=fresh({},fixture(false))
	var moved:=send(clear,{"type":"move","dx":1,"dy":0},"fixture_empty_anchor")
	check("empty_original_anchor_stays_exact",moved.status=="OK" and clear.state.character.x==2 and clear.state.character.y==16,moved)
	var deterministic:=fresh({},fixture())
	var first:=send(deterministic,{"type":"move","dx":1,"dy":0},"fixture_fixed_cardinal_tie_break")
	check("occupied_anchor_fixed_up_first_fallback",first.status=="OK" and deterministic.state.character.x==2 and deterministic.state.character.y==15,first)
	var obstacles:=content.duplicate(true)
	obstacles.maps[EAST].blocked.append([2,15])
	obstacles.npcs["gp:npc:shrine_healer"].map_id=EAST
	obstacles.npcs["gp:npc:shrine_healer"].x=3;obstacles.npcs["gp:npc:shrine_healer"].y=16
	var avoid:=fresh(obstacles,fixture())
	var avoided:=send(avoid,{"type":"move","dx":1,"dy":0},"fixture_fallback_avoids_wall_and_npc")
	check("fallback_skips_wall_and_npc_in_fixed_order",avoided.status=="OK" and avoid.state.character.x==2 and avoid.state.character.y==17,avoided)
	obstacles.npcs["gp:npc:shrine_healer"].x=2;obstacles.npcs["gp:npc:shrine_healer"].y=16
	var overlap:=fresh(obstacles,fixture());var overlap_before: Dictionary=overlap.snapshot()
	var overlap_refused:=send(overlap,{"type":"move","dx":1,"dy":0},"fixture_npc_and_monster_on_anchor")
	check("npc_plus_monster_anchor_refuses_without_relocation",overlap_refused.status=="REFUSED" and character_unchanged(overlap_before,overlap.snapshot()),overlap_refused)
	var sealed:=fresh({},fixture(true,true));var before: Dictionary=sealed.snapshot()
	var refused:=send(sealed,{"type":"move","dx":1,"dy":0},"fixture_exit_sealed")
	check("sealed_exit_refuses_atomically",refused.status=="REFUSED" and refused.reason=="DESTINATION_UNAVAILABLE" and character_unchanged(before,sealed.snapshot()),refused)
	# West neighbor is the live exit trigger (1,16); every other neighbor is
	# occupied. A free cell beyond those blockers must not permit a safe jump.
	check("fallback_never_lands_on_exit_or_crosses_sealed_ring",sealed.state.character.map_id==CITY and sealed.valid_position(EAST,2,14),sealed.state.character)
	var defs:=defs_for_arrival(point(CITY,29,22));defs.maps[CITY].exits[0].to_map=CITY;defs.maps[CITY].exits[0].to_x=29;defs.maps[CITY].exits[0].to_y=22
	var npc:=fresh(defs)
	check("npc_anchor_never_relocated",not npc._transition(CITY,29,22,1,"exit"))
	check("invalid_wall_anchor_never_relocated",not npc._transition(EAST,0,16,1,"exit"))
	var blink:=fresh({},fixture())
	check("blink_occupied_anchor_keeps_original_refusal",not blink._transition(EAST,2,16,1,"blink") and not blink._transition(EAST,2,16,1,"blink_attack"))

func return_fixtures() -> void:
	var game:=fresh(defs_for_arrival(),fixture());var before: Dictionary=game.snapshot()
	var cast:=send(game,{"type":"cast","skill_id":RETURN,"direction":"east"},"fixture_occupied_return_prevalidation")
	check("return_accepts_occupied_anchor_with_safe_neighbor",cast.status=="OK" and game.state.character.mp==int(before.character.mp)-5,cast)
	check("pending_return_retains_original_anchor",cast.status=="OK" and game.state.pending_actions[0].destination.x==2 and game.state.pending_actions[0].destination.y==16,game.state.pending_actions)
	var tick: Dictionary=game.tick(0.55)
	commands.append({"label":"fixture_return_impact","tick":0.55,"result":tick})
	var moved:=event(tick,"map_changed")
	check("return_rechecks_and_resolves_safe_impact",moved.get("map_id")==EAST and moved.get("x")==2 and moved.get("y")==15,moved)
	var sealed:=fresh(defs_for_arrival(),fixture(true,true));before=sealed.snapshot()
	var denied:=send(sealed,{"type":"cast","skill_id":RETURN,"direction":"east"},"fixture_return_sealed_precast")
	check("sealed_precast_return_no_cost_or_pending_or_revision",denied.status=="REFUSED" and denied.reason=="DESTINATION_UNAVAILABLE" and character_unchanged(before,sealed.snapshot()),denied)
	# Collision changes while a cast is pending are an explicit branch fixture.
	# Keep the existing accepted-cast NO_REFUND contract, including paid MP once.
	var late:=fresh(defs_for_arrival(),fixture(false));var mp_before:=int(late.state.character.mp)
	var accepted:=send(late,{"type":"cast","skill_id":RETURN,"direction":"east"},"fixture_late_seal_cast_acceptance")
	var costs: Dictionary=late.snapshot();var occupied:=fixture(true,true)
	late.state.monsters=occupied.monsters.duplicate(true)
	var failed: Dictionary=late.tick(0.55)
	var failure:=event(failed,"cast_failed")
	check("late_sealed_return_keeps_no_refund_contract",accepted.status=="OK" and failure.get("reason")=="DESTINATION_BECAME_UNAVAILABLE_NO_REFUND" and late.state.character.map_id==CITY and late.state.character.mp==mp_before-5,{"event":failure,"mp_before":mp_before,"mp_after":late.state.character.mp})
	check("late_sealed_return_no_partial_transition_or_extra_cost",late.state.character.x==costs.character.x and late.state.character.y==costs.character.y and late.state.inventory==costs.inventory and late.state.pending_actions.is_empty())
	# The destination was clear during prevalidation, then only its anchor became
	# occupied. Impact must search around the ORIGINAL anchor, not an old choice.
	var race:=fresh(defs_for_arrival(),fixture(false))
	var start:=send(race,{"type":"cast","skill_id":RETURN,"direction":"east"},"fixture_anchor_fills_after_prevalidation")
	race.state.monsters=fixture().monsters.duplicate(true)
	var impact: Dictionary=race.tick(0.55);moved=event(impact,"map_changed")
	check("return_anchor_filling_during_delay_recovers",start.status=="OK" and moved.get("map_id")==EAST and moved.get("x")==2 and moved.get("y")==15,moved)
	var provisional:=fresh(defs_for_arrival(),fixture())
	var provisional_start:=send(provisional,{"type":"cast","skill_id":RETURN,"direction":"east"},"fixture_provisional_fallback_fills_after_prevalidation")
	var candidates: Array=provisional.state.monsters.keys();candidates.sort()
	for id in candidates:
		if provisional.state.monsters[id].alive and id!="gp:spawn:east:2:0":
			provisional.state.monsters[id].map_id=EAST;provisional.state.monsters[id].x=2;provisional.state.monsters[id].y=15;break
	var provisional_impact: Dictionary=provisional.tick(0.55);moved=event(provisional_impact,"map_changed")
	check("impact_searches_original_anchor_after_old_fallback_fills",provisional_start.status=="OK" and moved.get("map_id")==EAST and moved.get("x")==3 and moved.get("y")==16,moved)

func respawn_and_item_fixtures() -> void:
	var dead:=fixture();dead.character.dead=true;dead.character.hp=0
	var game:=fresh(defs_for_arrival(),dead)
	var respawn:=send(game,{"type":"respawn"},"fixture_occupied_resurrection")
	check("resurrection_occupied_anchor_recovers",respawn.status=="OK" and not game.state.character.dead and int(game.state.character.hp)>0 and game.state.character.map_id==EAST and game.state.character.x==2 and game.state.character.y==15,respawn)
	var blocked_dead:=fixture(true,true);blocked_dead.character.dead=true;blocked_dead.character.hp=0
	var sealed:=fresh(defs_for_arrival(),blocked_dead);var before: Dictionary=sealed.snapshot()
	var refused:=send(sealed,{"type":"respawn"},"fixture_sealed_resurrection")
	check("sealed_resurrection_preserves_dead_state_atomically",refused.status=="REFUSED" and character_unchanged(before,sealed.snapshot()),refused)
	dead.skills.append(SHRINE)
	var shrine:=fresh(defs_for_arrival(),dead)
	var cast:=send(shrine,{"type":"cast","skill_id":SHRINE},"fixture_occupied_ghost_shrine")
	var applied: Dictionary=shrine.tick(0.5);var moved:=event(applied,"map_changed")
	check("ghost_shrine_recovers_without_reviving",cast.status=="OK" and moved.get("map_id")==EAST and moved.get("x")==2 and moved.get("y")==15 and shrine.state.character.dead,applied)
	var item_id:=""
	for id in content.items:
		if content.items[id].get("action_type")=="return":item_id=str(id);break
	var saved:=fixture();var iid:="arrival-fixture-return-item"
	saved.inventory.append({"instance_id":iid,"item_id":item_id,"quantity":2,"durability":int(content.items[item_id].get("durability",0))})
	var item:=fresh(defs_for_arrival(),saved);var prior_count: int=item.item_count(item_id)
	var used:=send(item,{"type":"use_item","instance_id":iid,"direction":"east"},"fixture_occupied_item_return")
	check("item_return_recovers_consumes_exactly_one",used.status=="OK" and item.item_count(item_id)==prior_count-1 and item.state.character.map_id==EAST and item.state.character.x==2 and item.state.character.y==15,used)
	var sealed_saved:=fixture(true,true);sealed_saved.inventory.append({"instance_id":iid,"item_id":item_id,"quantity":2,"durability":int(content.items[item_id].get("durability",0))})
	var sealed_item:=fresh(defs_for_arrival(),sealed_saved);before=sealed_item.snapshot()
	var denied:=send(sealed_item,{"type":"use_item","instance_id":iid,"direction":"east"},"fixture_sealed_item_return")
	check("sealed_item_return_preserves_item_and_all_state",denied.status=="REFUSED" and character_unchanged(before,sealed_item.snapshot()),denied)

func run() -> void:
	content=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	var document: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(source_save));payload=document.payload
	var initial_sha:=FileAccess.get_sha256(source_save)
	actual_branch()
	if arg("--baseline-only")!="yes":exit_fixtures();return_fixtures();respawn_and_item_fixtures()
	check("immutable_source_save_bytes_preserved",FileAccess.get_sha256(source_save)==initial_sha,initial_sha)
	var result:={"schema":"baram.arrival-occupancy-regression/1","status":"PASS" if failures==0 else "FAIL","checks":checks,"failures":failures,"commands":commands,"source_save_sha256":initial_sha,"content_sha256":FileAccess.get_sha256(content_path),"engine_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd"),"scope":"Linux headless production commands: real unchanged failed-play save recovery plus explicitly seeded collision fixtures. No OS/native/30min play or authenticated sync claim.","baseline_only":arg("--baseline-only")=="yes"}
	DirAccess.make_dir_recursive_absolute(report.get_base_dir())
	var file:=FileAccess.open(report,FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n")
	print("ARRIVAL_RESULT "+JSON.stringify({"status":result.status,"checks":checks.size(),"failures":failures,"report":report}))
	quit(0 if failures==0 else 1)
