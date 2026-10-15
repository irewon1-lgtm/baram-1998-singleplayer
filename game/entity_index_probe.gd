extends SceneTree
const Navigation=preload("res://navigation.gd")
class TestGame:
    extends "res://main.gd"
    func play_sound(_kind: String):pass
class RangedRules:
    extends RefCounted
    func weapon_attack_profile(_player):return {"kind":"ranged_physical","range_tiles":6,"min_range_tiles":1}
class RangedGame:
    extends RefCounted
    const DIRECTIONS=[Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]
    const Facing=preload("res://facing.gd")
    const Pathfinder=preload("res://pathfinder.gd")
    var rules=RangedRules.new()
    var player={"map":"a","x":1,"y":1,"direction":0}
    var attack_elapsed=-1.0
    var cast_elapsed=-1.0
    var direct_direction=-1
    var selected_target="target"
    var menu=""
    var continuity_blocked=false
    var entities={"target":{"id":"target","map":"a","x":4,"y":1,"alive":true}}
    var entities_by_map={}
    var maps={}
    var attack_calls=0
    var visible=true
    func cell():return Vector2i(player.x,player.y)
    func line_of_sight(_map,_origin,_destination):return visible
    func begin_attack():attack_calls+=1
    func event(_kind,_data):pass
    func notice(_message):pass

var checks=[]
func check(ok: bool, name: String):checks.append({"name":name,"status":"PASS" if ok else "FAIL"})
func map_data(id: String) -> Dictionary:
    var blocked=[];var masks=[]
    for y in range(8):
        blocked.append([false,false,false,false,false,false,false,false])
        masks.append([0,0,0,0,0,0,0,0])
    return {"id":id,"width":8,"height":8,"blocked":blocked,"collision_masks":masks,"npcs":[],"portals":[],"entry":[1,1]}
func actor(id: String,map_id: String,game,alive=true):
    var spec=game.rules.monster("rabbit",{})
    return {"id":id,"kind":"rabbit","map":map_id,"x":4,"y":4,"home_x":4,"home_y":4,"alive":alive,"spec":spec,"hp":int(spec.values.hp) if alive else 0,"hp_max":int(spec.values.hp),"mp":0,"mp_max":0,"statuses":{},"hurt":0.5,"respawn":0.05,"provoked":false,"attack_elapsed":-1.0,"direction":2,"move_timer":30.0,"attack_timer":30.0}
func _initialize():call_deferred("run")
func run():
    var game=TestGame.new()
    game.player=game.rules.new_character("인덱스검사")
    game.player.map="a";game.player.x=1;game.player.y=1;game.menu=""
    game.maps={"a":map_data("a"),"b":map_data("b")}
    game.entities={"local":actor("local","a",game),"remote":actor("remote","b",game),"remote_dead":actor("remote_dead","b",game,false)}
    game.rebuild_entity_index()
    check(game.entities_by_map.a.size()==1 and game.entities_by_map.b.size()==2 and game.respawning_entities.size()==1,"all-map-entities-indexed-and-dead-timer-index-built")
    check(not game.free_cell("a",Vector2i(4,4)) and game.free_cell("a",Vector2i(4,4),"local"),"map-local-occupancy-and-self-exclusion")
    game.entities.local.x=5
    check(game.free_cell("a",Vector2i(4,4)) and not game.free_cell("a",Vector2i(5,4)),"index-shares-mutable-actor-position")
    var remote=game.entities.remote.duplicate(true)
    game.update_monsters(.1)
    check(game.entities.remote==remote,"inactive-living-map-preserves-simulation-state")
    check(is_equal_approx(game.entities.local.hurt,.4) and is_equal_approx(game.entities.local.move_timer,29.9),"active-map-simulates-once")
    check(game.entities.remote_dead.alive and game.entities.remote_dead.hp==int(game.entities.remote_dead.spec.values.hp) and not game.respawning_entities.has("remote_dead"),"inactive-map-dead-actor-respawns-on-world-timer")
    game.entities.local.hp=1
    game.hit_monster(game.entities.local,2,"probe")
    check(not game.entities.local.alive and game.respawning_entities.has("local") and game.free_cell("a",Vector2i(5,4)),"actual-kill-registers-respawn-and-releases-occupancy")
    game.entities.local.respawn=.05
    game.update_monsters(.1)
    check(game.entities.local.alive and not game.respawning_entities.has("local") and not game.free_cell("a",Vector2i(4,4)),"actual-killed-actor-respawns-at-home-with-live-index")
    check(game.line_of_sight("a",Vector2i(1,1),Vector2i(5,1)),"open-ray-passes")
    check(not game.line_of_sight("a",Vector2i(-1,1),Vector2i(5,1)) and not game.line_of_sight("a",Vector2i(1,1),Vector2i(9,1)),"origin-and-target-outside-map-rejected")
    game.maps.a.collision_masks[1][3]=4
    check(not game.line_of_sight("a",Vector2i(1,1),Vector2i(5,1)),"ray-obeys-east-entry-collision-mask")
    game.maps.a.collision_masks[1][3]=8
    check(not game.line_of_sight("a",Vector2i(5,1),Vector2i(1,1)),"ray-obeys-west-entry-collision-mask")
    game.maps.a.collision_masks[1][3]=0;game.maps.a.collision_masks[1][2]=4
    check(not game.line_of_sight("a",Vector2i(1,1),Vector2i(2,1)),"target-cell-entry-mask-is-tested")
    game.maps.a.collision_masks[1][2]=0;game.maps.a.blocked[1][2]=true
    check(not game.line_of_sight("a",Vector2i(1,1),Vector2i(3,3)),"diagonal-shot-cannot-cut-blocked-corner")
    var ranged=RangedGame.new();ranged.maps={"a":map_data("a")};ranged.entities_by_map.a=[ranged.entities.target]
    var nav=Navigation.new(ranged);nav.path=[Vector2i(2,1)]
    nav.attack_selected()
    check(ranged.attack_calls==1 and ranged.player.direction==3 and nav.path.is_empty() and nav.searches==0,"selected-bow-target-in-range-fires-without-adjacent-route")
    ranged.visible=false;nav.attack_selected()
    check(ranged.attack_calls==1 and nav.searches==1,"blocked-bow-line-routes-instead-of-firing-through-wall")
    var options={}
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    var report={"scope":"Controlled actual main.gd entity index/kill/respawn/LOS; navigation ranged attack dispatch.","checks":checks,"status":"FAIL" if checks.any(func(c):return c.status=="FAIL") else "PASS"}
    var out=options.get("out","/tmp/baram-entity-index.json");DirAccess.make_dir_recursive_absolute(out.get_base_dir())
    var file=FileAccess.open(out,FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
    print("ENTITY_INDEX_RESULT "+JSON.stringify(report))
    game.free();quit(0 if report.status=="PASS" else 1)
