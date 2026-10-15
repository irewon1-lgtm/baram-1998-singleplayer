extends SceneTree
## Geometry/route/UI integration checks; these do not claim natural gameplay.
const MapView = preload("res://world_map_view.gd")
var checks = []
var options = {}

class FakeGame extends Node2D:
    var startup_ready = true
    var continuity_blocked = false
    var font = SystemFont.new()
    var menu = ""
    var maps = {}
    var world = {}
    var player = {"map":"a","x":1,"y":1,"level":1,"inventory":{"목도":1}}
    var events = []
    func clear_inputs():pass
    func cell():return Vector2i(player.x, player.y)
    func event(kind, detail):events.append({"kind":kind,"detail":detail})

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var parts = arg.trim_prefix("--").split("=", true, 1);options[parts[0]] = parts[1]
    call_deferred("run")

func verify(ok: bool, id: String, observed = {}):
    checks.append({"id":id,"status":"PASS" if ok else "FAIL","observed":observed})
    print("MAP_CHECK " + id + " " + ("PASS" if ok else "FAIL"))

func fixture(id: String) -> Dictionary:
    var blocked = [];var masks = [];var ground = []
    for y in range(7):
        var row = [];var mask_row = [];var ground_row = []
        for x in range(9):row.append(x == 0 or y == 0 or x == 8 or y == 6);mask_row.append(0);ground_row.append("A:0")
        blocked.append(row);masks.append(mask_row);ground.append(ground_row)
    return {"id":id,"name":"시험 지도 " + id,"width":9,"height":7,"blocked":blocked,"collision_masks":masks,"ground":ground,"entry":[1,1],"npcs":[],"spawns":[],"portals":[]}

func run():
    var maps = {"a":fixture("a"),"b":fixture("b"),"c":fixture("c"),"isolated":fixture("isolated")}
    maps.a.portals = [{"x":7,"y":1,"target":"b","entry":[1,1],"label":"b"},{"x":1,"y":5,"target":"missing","entry":[1,1]}]
    maps.b.portals = [{"x":7,"y":5,"target":"c","entry":[1,1],"label":"c"}]
    maps.a.npcs = [{"x":3,"y":1,"name":"막는 NPC","blocking":true}]
    maps.a.spawns = [{"x":4,"y":4}]
    maps.a.blocked[2][3] = true
    maps.a.collision_masks[1][2] = 4 # Cannot enter this tile moving right.
    var route = MapView.region_route(maps, "a", "alias-c", {"alias-c":"c"})
    verify(route.status == "FOUND" and route.path == ["a","b","c"] and route.edges.size() == 2, "directed-alias-portal-route", route)
    verify(MapView.region_route(maps, "c", "a").status == "UNREACHABLE", "does-not-invent-reverse-portals")
    verify(MapView.region_route(maps, "a", "isolated").status == "UNREACHABLE", "disconnected-region-reported")
    verify(MapView.region_route(maps, "a", "missing").status == "MISSING_MAP", "missing-destination-reported")
    var local = MapView.local_path(maps.a, Vector2i(1,1), [Vector2i(7,1)])
    var previous = Vector2i(1,1);var respects_geometry = local.status == "FOUND"
    for at in local.path:
        respects_geometry = respects_geometry and not maps.a.blocked[at.y][at.x] and at != Vector2i(3,1)
        if at == Vector2i(2,1):respects_geometry = respects_geometry and previous != Vector2i(1,1)
        previous = at
    verify(respects_geometry and local.path.size() > 6, "local-route-obeys-wall-npc-directional-mask", local)
    verify(MapView.local_path(maps.a, Vector2i(1,1), [Vector2i(3,2)]).status == "UNREACHABLE", "blocked-cell-unreachable")
    var image = MapView.geometry_image(maps.a)
    verify(image.get_size() == Vector2i(9,7) and image.get_pixel(3,2).r < 0.1 and image.get_pixel(2,1).r > 0.38 and image.get_pixel(4,4).r > 0.28 and image.get_pixel(4,4).r < 0.3, "raster-reuses-real-cells-exactly", {"wall":image.get_pixel(3,2),"partial":image.get_pixel(2,1),"walkable":image.get_pixel(4,4)})
    maps.c.npcs = [{"id":"travel","name":"안내인","x":2,"y":2,"role":"travel","destinations":["isolated"]}]
    var npc_route = MapView.region_route(maps, "a", "isolated")
    verify(npc_route.status == "FOUND" and npc_route.edges.back().trigger == "npc_travel" and npc_route.edges.back().entry == [1,1], "travel-npc-is-actual-region-edge", npc_route)
    maps.isolated.npcs = [{"id":"service","name":"이동 서비스","x":2,"y":2,"services":[{"type":"travel","map_ids":["a"]}]}]
    verify(MapView.region_route(maps, "isolated", "a").status == "FOUND", "work-travel-service-is-actual-region-edge")
    verify(not MapView.edge_goals(npc_route.edges.back()).has(Vector2i(2,2)) and MapView.edge_goals(npc_route.edges.back()).size() == 4, "npc-route-stops-adjacent-to-blocking-npc")
    var fake = FakeGame.new();fake.maps = maps;fake.world = {"map_aliases":{}}
    if options.has("assets"):
        var font_path = options.assets.path_join("fonts/NotoSansCJK-Regular.ttc")
        if FileAccess.file_exists(font_path):
            var loaded_font = FontFile.new();loaded_font.data = FileAccess.get_file_as_bytes(font_path);fake.font = loaded_font
    root.add_child(fake)
    var view = MapView.new();fake.add_child(view);view.initialize(fake)
    var original_player = fake.player.duplicate(true)
    view.open();await process_frame;await process_frame
    view.choose_destination("c");view.show_map("b")
    verify(view.visible and view.viewed_map == "b" and view.local_origin == Vector2i(1,1) and view.selected_cell == Vector2i(7,5) and view.local_route.status == "FOUND", "actual-route-step-shows-destination-entry-and-exit")
    view.show_map("a");view.select_portal(0)
    verify(view.selected_cell == Vector2i(7,1) and view.local_route.status == "FOUND", "exit-selection-highlights-local-route")
    view.pick_cell(view.point_for(Vector2(4,4)))
    verify(view.selected_cell == Vector2i(4,4), "touch-picking-uses-actual-grid-coordinate")
    view.canvas.zoom = 2;view.canvas.pan = Vector2(19,-11)
    view.pick_cell(view.point_for(Vector2(5,4)))
    verify(view.selected_cell == Vector2i(5,4), "zoom-pan-preserve-picked-coordinate")
    view.close()
    verify(fake.menu == "" and not view.visible and fake.player == original_player, "open-route-browse-close-preserve-player-save")
    if options.has("content") and options.has("assets"):
        await verify_actual(view, fake)
    else:
        var w = JSON.parse_string(FileAccess.get_file_as_string("res://data/world.json"))
        var public_maps = {}
        for m in w.maps:public_maps[m.id] = m
        var public_route = MapView.region_route(public_maps, "village", "ruins")
        verify(public_route.status == "FOUND", "existing-eight-map-sample-route", public_route)
    fake.queue_free();await process_frame
    var result = {"scope":"map geometry/routes/UI; natural play is NOT_RUN","checks":checks,"failed":checks.filter(func(c):return c.status == "FAIL").size()}
    if options.has("output"):
        var f = FileAccess.open(options.output, FileAccess.WRITE);f.store_string(JSON.stringify(result, "  "));f.close()
    print("MAP_RESULT " + JSON.stringify(result))
    quit(1 if result.failed else 0)

func verify_actual(view, fake):
    var Registry = load("res://content_registry.gd")
    var registry = Registry.new()
    if not registry.load_directory(options.content):verify(false, "actual-content-load", registry.last_error);return
    var world_path = options.assets.path_join("source_maps/world.json")
    var source = JSON.parse_string(FileAccess.get_file_as_string(world_path))
    var world = registry.merge_world(source)
    var maps = {}
    for m in world.maps:maps[m.id] = m
    verify(registry.last_error.is_empty() and maps.size() > 8, "actual-active-world-load", {"maps":maps.size(),"content_version":registry.version,"error":registry.last_error})
    var origin = world.home.map;var reachable = 0;var missing = [];var geometry_ok = true;var longest = []
    for id in maps:
        var route = MapView.region_route(maps, origin, id, world.get("map_aliases", {}))
        if route.status == "FOUND":
            reachable += 1
            if route.path.size() > longest.size():longest = route.path
        var image = MapView.geometry_image(maps[id])
        geometry_ok = geometry_ok and image.get_size() == Vector2i(maps[id].width,maps[id].height)
        for p in maps[id].portals:
            if not maps.has(world.get("map_aliases", {}).get(p.get("target", ""), p.get("target", ""))):missing.append({"map":id,"portal":p})
    verify(geometry_ok, "all-loaded-map-geometry-rasterizes", {"maps":maps.size()})
    verify(missing.is_empty(), "actual-graph-has-no-missing-destination", {"missing":missing})
    verify(reachable == maps.size(), "actual-home-reaches-all-registered-scenes", {"reachable":reachable,"maps":maps.size(),"longest_route":longest})
    fake.maps = maps;fake.world = world;fake.player.map = origin;fake.player.x = maps[origin].entry[0];fake.player.y = maps[origin].entry[1]
    view.open();await process_frame;await process_frame
    if not longest.is_empty():view.choose_destination(longest.back())
    if options.has("screenshot") and DisplayServer.get_name() != "headless":
        await process_frame;await RenderingServer.frame_post_draw
        root.get_texture().get_image().save_png(options.screenshot)
    verify(view.canvas.size.x > 100 and view.canvas.size.y > 100 and view.visible, "actual-world-map-ui-has-visible-layout", {"canvas_size":view.canvas.size,"destination":view.destination,"local_status":view.local_route.get("status", "NO_ROUTE")})
    view.close()
