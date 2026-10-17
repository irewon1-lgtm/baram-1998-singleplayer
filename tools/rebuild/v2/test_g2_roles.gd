extends SceneTree
## Each added profile attacks through normal fixed-step AI, then saves/restores.
## Position, large player HP, record selection and time are explicit fixtures.
const Game=preload("res://state/gameplay_state.gd")
const Store=preload("res://storage/gameplay_store.gd")
var checks: Array=[]
var failures:=0
func check(id: String,ok: bool,detail: Variant=null) -> void:
	checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
	if not ok:failures+=1;print("FAIL "+id+" "+str(detail))
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args();var runtime:=args[args.find("--runtime")+1]
	var data: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(runtime.path_join("gameplay_content.json")))
	var semantics: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(runtime.path_join("G2_MONSTER_SEMANTICS.json")))
	var game=Game.new();check("configure",game.configure(data),game.errors)
	game.create_character("전술저장","fixture:roles");var initial: Dictionary=game.snapshot()
	game._spawn_all();var all: Dictionary=game.state.monsters.duplicate(true);var by_id: Dictionary={}
	for id in all:by_id[str(all[id].monster_id)]=str(id)
	var store=Store.new();var ready: Dictionary=store.prepare_content(data)
	var root:="user://gameplay-p3/g2-role-tests/"+str(Time.get_ticks_usec())+"/"
	for id in semantics.added_specialists:
		game.state=initial.duplicate(true);game._indexed_monster_count=-1
		var sid: String=by_id[id];var monster: Dictionary=all[sid].duplicate(true);var definition: Dictionary=data.monsters[id]
		game.state.monsters={sid:monster};var placed:=false
		for delta in [Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT,Vector2i.UP]:
			var x: int=int(monster.x)+delta.x;var y: int=int(monster.y)+delta.y
			if game.can_step(str(monster.map_id),int(monster.x),int(monster.y),x,y) and not game._occupied(str(monster.map_id),x,y):
				game.state.character.map_id=monster.map_id;game.state.character.x=x;game.state.character.y=y;placed=true;break
		check("position:"+str(id),placed)
		game.state.character.hp_max=1000000;game.state.character.hp=1000000
		var hp:=int(game.state.character.hp)
		game.tick(2.0)
		check("AI_hits:"+str(id),int(game.state.character.hp)<hp,{"role":definition.tactical_role,"hp_loss":hp-int(game.state.character.hp)})
		var status: String=str(definition.get("on_hit_status",""))
		if not status.is_empty():check("AI_status:"+str(id),game.state.buffs.has("monster:"+sid) and str(game.state.buffs["monster:"+sid].status)==status,status)
		var path:=root+str(id).sha256_text()+".json"
		var written: Dictionary=store.write_game(path,game.snapshot(),"fixture:roles",ready)
		var read: Dictionary=store.read_game(path,"fixture:roles",ready)
		check("actual_AI_save_restart:"+str(id),written.status=="SAVED" and read.status=="OK" and store._canonical(read.payload)==store._canonical(game.snapshot()),written)
	var report: Dictionary={"status":"PASS" if failures==0 else "FAIL","schema":"baram.g2.regional-role-ai/1","scope":"112 real regional definitions/spawn IDs, fixed-step AI attacks/status effects and actual disk roundtrips under declared position/HP/time fixtures; no natural progression or visual/platform claim.","checks":checks,"failures":failures,"profiles":semantics.added_specialists.size(),"source_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"content_sha256":FileAccess.get_sha256(runtime.path_join("gameplay_content.json"))}
	var out:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE);out.store_string(JSON.stringify(report,"  ")+"\n");out.close()
	print("G2_ROLES "+str(checks.size())+" checks, "+str(failures)+" failures");quit(0 if failures==0 else 1)
