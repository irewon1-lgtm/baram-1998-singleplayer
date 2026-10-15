extends SceneTree
var checks=[]
var failure=false

func check(name: String, ok: bool, detail={}):
    checks.append({"id":name,"status":"PASS" if ok else "FAIL","detail":detail})
    if not ok:failure=true

func _initialize():
    var args={}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);args[parts[0]]=parts[1]
    if not args.has_all(["assets","content","report"]):quit(2);return
    var registry=load("res://content_registry.gd").new()
    check("active-content-byte-verification",registry.load_directory(args.content),registry.last_error)
    if failure:quit(2);return
    var source=args.assets.path_join("source_maps/world.json")
    var before=FileAccess.get_sha256(source)
    var world=registry.merge_world(JSON.parse_string(FileAccess.get_file_as_string(source)))
    var helper=load("res://world_repairs.gd")
    check("merge-no-content-errors",registry.last_error.is_empty(),registry.last_error)
    check("source-world-unchanged",FileAccess.get_sha256(source)==before)
    var unavailable=[];var empty=[];var spawned=0;var overlevel=[]
    for map in world.maps:
        var cells=helper.reachable(map)
        for spawn in map.spawns:
            spawned+=1
            if not cells.has(Vector2i(int(spawn.x),int(spawn.y))):unavailable.append({"map":map.id,"spawn":spawn.id})
            var bounds=registry.definition(map.get("definition_id",map.id)).get("recommended_level",[])
            if bounds.size()==2 and int(bounds[1])<=10 and int(registry.definition(spawn.kind).get("level",0))>int(bounds[1]):overlevel.append({"map":map.id,"spawn":spawn.id})
        if helper.EMPTY_HUNTS.has(map.id) and map.spawns.is_empty():empty.append(map.id)
    check("all-spawns-in-entry-reachable-terrain",unavailable.is_empty(),{"unavailable":unavailable,"spawns":spawned})
    check("seven-empty-hunts-have-reused-monsters",empty.is_empty(),{"remaining_empty":empty})
    check("starter-regions-match-recommended-level",overlevel.is_empty(),{"overlevel":overlevel})
    var unresolved=world.runtime_repairs.filter(func(r):return r.kind=="empty_hunt_unresolved")
    check("source-monster-pools-available",unresolved.is_empty(),{"unresolved":unresolved})
    var duplicate=world.duplicate(true)
    check("repair-idempotence",helper.apply(duplicate,registry)==world)
    var repairs=world.runtime_repairs
    var relocated=repairs.filter(func(r):return r.kind=="spawn_relocated")
    var portals=repairs.filter(func(r):return r.kind=="portal_relocated")
    check("known-isolated-spawns-repaired",relocated.any(func(r):return r.map_id=="wk.map.exp2.na495.1051"),{"relocated":relocated.size()})
    check("known-inaccessible-portal-repaired",portals.any(func(r):return r.map_id=="wk.map.exp2.na495.3965"),{"relocated":portals.size()})
    var result={"status":"FAIL" if failure else "PASS","scope":"STATIC_RUNTIME_TERRAIN_AND_PLACEMENT_NOT_PLAYTHROUGH","maps":world.maps.size(),"checks":checks,"runtime_repairs":repairs,"content_version":registry.version}
    var file=FileAccess.open(args.report,FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close()
    print("WORLD_REPAIRS "+result.status+" maps="+str(world.maps.size())+" changes="+str(repairs.size()))
    quit(1 if failure else 0)
