extends SceneTree
## Real merged-world compass benchmark. Does not create or mutate a save.
const Navigation=preload("res://navigation.gd")
const Content=preload("res://content_registry.gd")
const WorkAssets=preload("res://work_assets.gd")

class World:
    extends RefCounted
    var maps={}
    var entities={}
    var entities_by_map={}
    var player={"map":"village"}
    var entity_visits=0
    var cell_checks=0
    func free_cell(map_id: String, pos: Vector2i) -> bool:
        cell_checks+=1
        var m=maps[map_id]
        if pos.x<0 or pos.y<0 or pos.x>=int(m.width) or pos.y>=int(m.height) or m.blocked[pos.y][pos.x]:return false
        for id in entities:
            entity_visits+=1
            var e=entities[id]
            if e.alive and e.map==map_id and Vector2i(e.x,e.y)==pos:return false
        for n in m.npcs:
            if n.get("blocking",true) and Vector2i(n.x,n.y)==pos:return false
        return true

func legacy_entry(game, direction: int) -> Vector2i:
    var town=game.maps.village
    var desired=[Vector2i(int(town.width)-3,int(town.height)/2),Vector2i(2,int(town.height)/2),Vector2i(int(town.width)/2,int(town.height)-3),Vector2i(int(town.width)/2,2)][direction]
    var candidate=Vector2i(town.entry[0],town.entry[1]);var best=99999
    for y in range(int(town.height)):
        for x in range(int(town.width)):
            if game.free_cell("village",Vector2i(x,y)):
                var distance=absi(x-desired.x)+absi(y-desired.y)
                if distance<best:best=distance;candidate=Vector2i(x,y)
    return candidate

func reference_entry(game, direction: int) -> Vector2i:
    var town=game.maps.village;var blockers=Navigation.new(game).occupied("village")
    var desired=[Vector2i(int(town.width)-3,int(town.height)/2),Vector2i(2,int(town.height)/2),Vector2i(int(town.width)/2,int(town.height)-3),Vector2i(int(town.width)/2,2)][direction]
    var candidate=Vector2i(town.entry[0],town.entry[1]);var best=99999
    for y in range(int(town.height)):
        for x in range(int(town.width)):
            if town.blocked[y][x] or blockers.has(Vector2i(x,y)):continue
            var distance=absi(x-desired.x)+absi(y-desired.y)
            if distance<best:best=distance;candidate=Vector2i(x,y)
    return candidate

func _initialize():call_deferred("run")

func run():
    var options={}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    if not options.has_all(["cache","out"]):push_error("--cache and --out required");quit(2);return
    var root=options.cache
    var manifest=JSON.parse_string(FileAccess.get_file_as_string(root.path_join("manifest.json")))
    var file=FileAccess.open_compressed(root.path_join("world.bin"),FileAccess.READ) if manifest.get("compression","")=="zstd" else FileAccess.open(root.path_join("world.bin"),FileAccess.READ)
    var world=file.get_var(false);var game=World.new()
    for m in world.maps:
        game.maps[m.id]=m
        game.entities_by_map[m.id]=[]
        for spawn in m.spawns:
            var entity={"id":spawn.id,"x":spawn.x,"y":spawn.y,"map":m.id,"alive":true}
            game.entities[spawn.id]=entity;game.entities_by_map[m.id].append(entity)
    print("COMPASS_WORLD "+JSON.stringify({"maps":game.maps.size(),"entities":game.entities.size(),"town_size":[game.maps.village.width,game.maps.village.height]}))
    var before
    var legacy={}
    if options.has("legacy-evidence"):
        legacy=JSON.parse_string(FileAccess.get_file_as_string(options["legacy-evidence"])).legacy
        before=legacy.destination
    else:
        var began=Time.get_ticks_usec();before=legacy_entry(game,0);var before_us=Time.get_ticks_usec()-began
        legacy={"microseconds":before_us,"entity_visits":game.entity_visits,"candidate_checks":game.cell_checks,"destination":before,"path_searches":0}
    print("COMPASS_LEGACY "+JSON.stringify(legacy))
    var nav=Navigation.new(game);var after=nav.compass_entry(0)
    var optimized=nav.last_compass.duplicate();optimized.destination=after
    var checks=[{"name":"same_real_world_destination","status":"PASS" if str(before)==str(after) else "FAIL"}]
    var directions=[]
    for direction in range(4):
        var expected=reference_entry(game,direction);var found=nav.compass_entry(direction)
        directions.append({"direction":direction,"expected":expected,"actual":found,"metrics":nav.last_compass.duplicate()})
        checks.append({"name":"row_major_equivalence_direction_"+str(direction),"status":"PASS" if expected==found else "FAIL"})
    # Force the intended gate occupied, then blocked, to exercise ring fallback.
    var normal=nav.compass_entry(0)
    game.entities["probe-gate-blocker"]={"id":"probe-gate-blocker","map":"village","x":normal.x,"y":normal.y,"alive":true}
    game.entities_by_map.village.append(game.entities["probe-gate-blocker"])
    var fallback=nav.compass_entry(0);var expected_fallback=reference_entry(game,0)
    checks.append({"name":"occupied_gate_fallback_preserves_tie_break","status":"PASS" if fallback==expected_fallback and fallback!=normal else "FAIL"})
    game.entities_by_map.village.erase(game.entities["probe-gate-blocker"])
    game.entities.erase("probe-gate-blocker")
    var samples=[]
    for iteration in range(30):nav.compass_entry(iteration%4);samples.append(nav.last_compass.microseconds)
    samples.sort()
    var cache_result={"status":"NOT_RUN"}
    if options.has("content"):
        var content=Content.new()
        if content.load_directory(options.content):
            var renderer=WorkAssets.new(content)
            var tile_map=""
            var keys={}
            for map_id in game.maps:
                for row in game.maps[map_id].ground:
                    for key in row:
                        if "#" in key:keys[key]=true
                if not keys.is_empty():tile_map=map_id;break
            renderer.enter_map(tile_map)
            var load_begin=Time.get_ticks_usec();var successful=0
            for key in keys:
                var parts=key.split("#")
                if renderer.tile(parts[0],int(parts[1]))!=null:successful+=1
            var initial_us=Time.get_ticks_usec()-load_begin
            var builds=renderer.tile_cache_builds
            load_begin=Time.get_ticks_usec()
            renderer.enter_map(tile_map)
            for key in keys:
                var parts=key.split("#");renderer.tile(parts[0],int(parts[1]))
            var repeat_us=Time.get_ticks_usec()-load_begin
            checks.append({"name":"same_map_teleport_keeps_all_immutable_tile_frames","status":"PASS" if successful>0 and renderer.tile_cache_builds==builds and renderer.tile_cache_resets==0 else "FAIL"})
            renderer.enter_map("different-map")
            checks.append({"name":"real_map_change_releases_old_map_tile_frames","status":"PASS" if renderer.tile_cache.is_empty() and renderer.tile_cache_resets==1 else "FAIL"})
            cache_result={"status":"PASS" if successful>0 else "NOT_RUN","map":tile_map,"unique_work_tiles":keys.size(),"loaded":successful,"initial_build_us":initial_us,"repeat_lookup_us":repeat_us,"repeat_rebuilds":renderer.tile_cache_builds-builds,"resets_after_real_map_change":renderer.tile_cache_resets}
    var report={"world":{"maps":game.maps.size(),"entities":game.entities.size(),"town_width":game.maps.village.width,"town_height":game.maps.village.height},"legacy":legacy,"optimized":optimized,"directions":directions,"optimized_30_runs":{"median_us":samples[15],"p95_us":samples[28],"maximum_us":samples[29]},"tile_cache":cache_result,"checks":checks,"frame_rate":{"status":"NOT_RUN","reason":"Headless CPU benchmark does not establish device FPS."}}
    DirAccess.make_dir_recursive_absolute(options.out.get_base_dir())
    var output=FileAccess.open(options.out,FileAccess.WRITE);output.store_string(JSON.stringify(report,"  "));output.close()
    print("COMPASS_RESULT "+JSON.stringify(report))
    quit(1 if checks.any(func(c):return c.status=="FAIL") else 0)
