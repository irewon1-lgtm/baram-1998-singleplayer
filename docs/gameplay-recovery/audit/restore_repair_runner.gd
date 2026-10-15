extends SceneTree
## Main.restore regression against exact baseline topology and current world.
## In-memory copied snapshots only; no user save file is written.
var options={}
var checks=[]

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var pair=arg.trim_prefix("--").split("=",true,1);options[pair[0]]=pair[1]
    call_deferred("run")

func check(ok: bool,id: String,detail={}):
    checks.append({"id":id,"result":"PASS" if ok else "FAIL","details":detail})
    print("RESTORE_AUDIT "+id+" "+("PASS" if ok else "FAIL"))

func run():
    var game=load("res://main.gd").new()
    check(game.content.load_directory(options.content),"actual-active-content-load",game.content.last_error)
    if not game.content.last_error.is_empty():finish(game);return
    game.content.apply_rules(game.rules)
    game.world=game.content.merge_world(JSON.parse_string(FileAccess.get_file_as_string(options.assets.path_join("source_maps/world.json"))))
    check(game.content.last_error.is_empty(),"actual-repaired-world-load",game.content.last_error)
    for map in game.world.maps:game.maps[map.id]=map
    for map in game.world.maps:
        for spawn in map.spawns:
            var spec=game.rules.monster(spawn.kind,game.world.replacements)
            game.entities[spawn.id]={"id":spawn.id,"kind":spawn.kind,"map":map.id,"x":spawn.x,"y":spawn.y,"home_x":spawn.x,"home_y":spawn.y,"direction":2,"hp":int(spec.values.hp),"hp_max":int(spec.values.hp),"mp":int(game.rules.value_or(spec.values,"mp",0)),"mp_max":int(game.rules.value_or(spec.values,"mp",0)),"alive":true,"respawn":0.0,"move_timer":3.0,"attack_timer":0.0,"provoked":false,"hurt":0.0,"statuses":{},"spec":spec}
    var fresh=game.entities.duplicate(true)
    var old=JSON.parse_string(FileAccess.get_file_as_string(options.baseline))
    var old_spawn={}
    for map in old.maps:
        for spawn in map.spawns:old_spawn[spawn.id]={"map":map.id,"x":spawn.x,"y":spawn.y}
    var snapshot_world={}
    for id in old_spawn:
        if not fresh.has(id):continue
        var entity=fresh[id].duplicate(true);var position=old_spawn[id]
        entity.map=position.map;entity.x=position.x;entity.y=position.y;entity.home_x=position.x;entity.home_y=position.y
        snapshot_world[id]=entity
    var repair_ids=[];var map_moves=0;var dead_ids=[]
    for repair in game.world.get("runtime_repairs",[]):
        if repair.kind not in ["spawn_relocated","spawn_map_relocated"] or not snapshot_world.has(repair.placement_id):continue
        var id=repair.placement_id
        repair_ids.append(id)
        if repair.kind=="spawn_map_relocated":map_moves+=1
        snapshot_world[id].hp=maxi(1,int(snapshot_world[id].hp)/2)
        snapshot_world[id].alive=repair_ids.size()%2==0
        snapshot_world[id].respawn=13.0
        if not snapshot_world[id].alive:dead_ids.append(id)
    var player=game.rules.new_player("전사","보존검사")
    player.level=37;player.rank=2;player.gold=777
    player.skills=["기초 회복","비영사천문"];player.hotbar=["기초 회복","비영사천문",""]
    player.map=game.world.home.map;player.x=game.world.home.entry[0];player.y=game.world.home.entry[1]
    player.world_revision=game.world.get("revision","authored-1")
    var before_player=player.duplicate(true)
    var snapshot={"player":player,"world":snapshot_world,"loot":[],"rng_state":str(game.rules.rng.state)}
    var before_snapshot=snapshot.duplicate(true)
    game.restore(snapshot.duplicate(true))
    check(repair_ids.size()>0 and map_moves>0,"actual-baseline-placement-repairs-exercised",{"repairs":repair_ids.size(),"between_map_moves":map_moves})
    check(game.player.job==before_player.job and game.player.level==before_player.level and game.player.rank==before_player.rank and game.player.skills==before_player.skills and game.player.hotbar==before_player.hotbar and game.player.gold==before_player.gold,"existing-player-class-level-rank-skills-money-preserved")
    check(game.player.map==before_player.map and game.player.x==before_player.x and game.player.y==before_player.y,"existing-player-location-preserved")
    var errors=[]
    for id in repair_ids:
        var actual=game.entities[id];var original=before_snapshot.world[id];var wanted=fresh[id]
        if actual.map!=wanted.map or actual.home_x!=wanted.home_x or actual.home_y!=wanted.home_y or actual.x!=wanted.x or actual.y!=wanted.y:errors.append({"id":id,"reason":"PLACEMENT","actual_map":actual.map,"wanted_map":wanted.map})
        if actual.hp!=original.hp or actual.alive!=original.alive or actual.respawn!=original.respawn:errors.append({"id":id,"reason":"PROGRESS"})
        if not game.entities_by_map.get(actual.map,[]).has(actual):errors.append({"id":id,"reason":"INDEX"})
        if (not actual.alive)!=game.respawning_entities.has(id):errors.append({"id":id,"reason":"RESPAWN_INDEX"})
    check(errors.is_empty(),"old-baseline-spawns-relocate-and-retain-HP-alive-respawn-with-correct-index",{"checked":repair_ids.size(),"errors":errors})
    check(snapshot==before_snapshot,"input-copied-old-snapshot-remains-unchanged")
    finish(game)

func finish(game):
    var report={"result":"FAIL" if checks.any(func(c):return c.result=="FAIL") else "PASS","scope":"CONTROLLED_REAL_MAIN_RESTORE_OF_EXACT_BASELINE_PLACEMENT_SNAPSHOT_NOT_NATURAL_GAMEPLAY","content_version":game.content.version,"checks":checks,"main_sha256":FileAccess.get_sha256("res://main.gd")}
    var file=FileAccess.open(options.out,FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
    game.free()
    quit(0 if report.result=="PASS" else 2)
