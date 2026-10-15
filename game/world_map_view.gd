extends Control
## Read-only map viewer. Every cell, marker and edge comes from the loaded world.
## Opening this view never moves the player or modifies a saved character.
const Pathfinder = preload("res://pathfinder.gd")
const WALKABLE = Color(0.29, 0.34, 0.25)
const WALL = Color(0.075, 0.095, 0.075)
const PARTIAL = Color(0.39, 0.37, 0.25)
var game
var viewed_map = ""
var destination = ""
var route = []
var route_result = {}
var local_route = {}
var local_origin = Vector2i.ZERO
var selected_cell = Vector2i(-1, -1)
var menu_was_open = false
var map_ids = []
var cached_images = {}
var cache_order = []
var frame: PanelContainer
var title: Label
var destination_picker: OptionButton
var canvas: MapCanvas
var route_box: VBoxContainer
var route_scroll: ScrollContainer
var detail: Label
var layout_box: HBoxContainer
var content_box: VBoxContainer
var side: VBoxContainer

class MapCanvas extends Control:
    var owner_view
    var zoom = 1.0
    var pan = Vector2.ZERO
    var down = false
    var dragged = false
    var last_position = Vector2.ZERO

    func _gui_input(event):
        if event is InputEventMouseButton and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] and event.pressed:
            zoom = clampf(zoom * (1.3 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.3), 1, 8)
            queue_redraw();accept_event()
        elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
            if event.pressed:
                down = true;dragged = false;last_position = event.position
            else:
                if down and not dragged:owner_view.pick_cell(event.position)
                down = false
            accept_event()
        elif event is InputEventMouseMotion and down:
            if event.position.distance_to(last_position) > 2:dragged = true
            if dragged:pan += event.position - last_position;queue_redraw()
            last_position = event.position;accept_event()
        elif event is InputEventScreenTouch:
            if event.pressed:
                down = true;dragged = false;last_position = event.position
            else:
                if down and not dragged and not event.canceled:owner_view.pick_cell(event.position)
                down = false
            accept_event()
        elif event is InputEventScreenDrag and down:
            dragged = true;pan += event.position - last_position;last_position = event.position
            queue_redraw();accept_event()

    func _draw():
        if owner_view != null:owner_view.draw_map(self)

func initialize(owner_game):
    game = owner_game
    name = "WorldMapView"
    z_index = 240
    mouse_filter = Control.MOUSE_FILTER_STOP
    set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    hide()
    build_controls()

func label_control(value: String, size_value: int = 18) -> Label:
    var result = Label.new()
    result.text = value
    result.add_theme_font_override("font", game.font)
    result.add_theme_font_size_override("font_size", size_value)
    result.add_theme_color_override("font_color", Color(0.94, 0.91, 0.77))
    return result

func button_control(value: String, callback: Callable) -> Button:
    var result = Button.new()
    result.text = value
    result.custom_minimum_size.y = 48
    result.add_theme_font_override("font", game.font)
    result.add_theme_font_size_override("font_size", 18)
    result.pressed.connect(callback)
    return result

func build_controls():
    var background = ColorRect.new()
    background.color = Color(0.025, 0.035, 0.027, 0.97)
    background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    background.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(background)
    var margin = MarginContainer.new()
    margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    for edge in ["left", "top", "right", "bottom"]:margin.add_theme_constant_override("margin_" + edge, 16)
    add_child(margin)
    content_box = VBoxContainer.new();content_box.add_theme_constant_override("separation", 8);margin.add_child(content_box)
    var heading = HBoxContainer.new();content_box.add_child(heading)
    title = label_control("지도", 23);title.size_flags_horizontal = Control.SIZE_EXPAND_FILL;heading.add_child(title)
    heading.add_child(button_control("내 위치", func():show_map(game.player.map);canvas.zoom = 1;canvas.pan = Vector2.ZERO))
    heading.add_child(button_control("닫기  Esc", close))
    var search = HBoxContainer.new();content_box.add_child(search)
    search.add_child(label_control("목적지"))
    destination_picker = OptionButton.new()
    destination_picker.custom_minimum_size = Vector2(280, 46)
    destination_picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    destination_picker.add_theme_font_override("font", game.font)
    destination_picker.add_theme_font_size_override("font_size", 18)
    destination_picker.get_popup().add_theme_font_override("font", game.font)
    destination_picker.get_popup().add_theme_font_size_override("font_size", 18)
    destination_picker.item_selected.connect(func(index):choose_destination(map_ids[index]))
    search.add_child(destination_picker)
    search.add_child(button_control("−", func():canvas.zoom = maxf(1, canvas.zoom / 1.4);canvas.queue_redraw()))
    search.add_child(button_control("＋", func():canvas.zoom = minf(8, canvas.zoom * 1.4);canvas.queue_redraw()))
    layout_box = HBoxContainer.new();layout_box.size_flags_vertical = Control.SIZE_EXPAND_FILL;layout_box.add_theme_constant_override("separation", 14);content_box.add_child(layout_box)
    canvas = MapCanvas.new();canvas.owner_view = self
    canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL;canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
    canvas.clip_contents = true;canvas.mouse_filter = Control.MOUSE_FILTER_STOP
    canvas.resized.connect(canvas.queue_redraw)
    layout_box.add_child(canvas)
    side = VBoxContainer.new();side.custom_minimum_size.x = 280;layout_box.add_child(side)
    side.add_child(label_control("출구와 이동 경로", 20))
    route_scroll = ScrollContainer.new();route_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL;route_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED;side.add_child(route_scroll)
    route_box = VBoxContainer.new();route_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL;route_box.add_theme_constant_override("separation", 8);route_scroll.add_child(route_box)
    detail = label_control("", 16);detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART;detail.custom_minimum_size.y = 46;content_box.add_child(detail)
    var legend = label_control("하늘색 ● 내 위치   주황 ◇ 출구   초록 ■ NPC   빨강 ● 몬스터 출현   노랑 선: 경로", 15)
    legend.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART;content_box.add_child(legend)

func _process(_delta):
    if game == null or not game.startup_ready or game.player.is_empty():return
    # Supports existing M key callers without retaining the old names-only modal.
    if game.menu == "map":open()
    if visible and game.menu != "world_map":hide();menu_was_open = false
    if visible:
        size = get_viewport_rect().size
        side.custom_minimum_size.x = clampf(size.x * 0.30, 220, 310)

func _input(event):
    if game == null or not game.startup_ready or game.player.is_empty() or game.continuity_blocked:return
    if event is InputEventKey and event.pressed and not event.echo:
        if visible and event.keycode in [KEY_ESCAPE, KEY_M]:
            close();get_viewport().set_input_as_handled()
        elif visible and event.keycode in [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_W, KEY_A, KEY_S, KEY_D, KEY_SPACE, KEY_ENTER, KEY_1, KEY_2, KEY_3]:
            get_viewport().set_input_as_handled()

func open():
    if game.player.is_empty() or game.continuity_blocked:return
    game.clear_inputs()
    game.menu = "world_map"
    menu_was_open = true
    map_ids = game.maps.keys()
    map_ids.sort_custom(func(a, b):return str(game.maps[a].name).naturalnocasecmp_to(str(game.maps[b].name)) < 0)
    destination_picker.clear()
    for id in map_ids:destination_picker.add_item(str(game.maps[id].name))
    destination = game.player.map
    destination_picker.select(map_ids.find(destination))
    route_result = region_route(game.maps, game.player.map, destination, game.world.get("map_aliases", {}))
    route = route_result.path
    show()
    show_map(game.player.map)
    game.event("world_map_opened", {"map":game.player.map,"maps":map_ids.size(),"geometry":"runtime_collision","read_only":true})

func close():
    hide()
    if game != null:
        if game.menu in ["world_map", "map"]:game.menu = ""
        game.clear_inputs()
    menu_was_open = false

static func region_route(maps: Dictionary, source: String, target: String, aliases: Dictionary = {}) -> Dictionary:
    source = aliases.get(source, source);target = aliases.get(target, target)
    if not maps.has(source) or not maps.has(target):return {"status":"MISSING_MAP", "path":[], "edges":[]}
    var queue = [source];var parents = {source:""};var edges = {};var cursor = 0
    while cursor < queue.size():
        var current = queue[cursor];cursor += 1
        if current == target:
            var result = [target];var result_edges = [];var at = target
            while at != source:
                result_edges.push_front(edges[at]);at = parents[at];result.push_front(at)
            return {"status":"FOUND", "path":result, "edges":result_edges, "visited":cursor}
        for portal in map_connections(maps, current, aliases):
            var next = aliases.get(portal.get("target", ""), portal.get("target", ""))
            if maps.has(next) and not parents.has(next):
                parents[next] = current;edges[next] = portal;queue.append(next)
    return {"status":"UNREACHABLE", "path":[], "edges":[], "visited":cursor}

static func map_connections(maps: Dictionary, id: String, aliases: Dictionary = {}) -> Array:
    var result = maps[id].get("portals", []).duplicate()
    for npc in maps[id].get("npcs", []):
        var destinations = npc.get("destinations", []).duplicate() if npc.get("role", "") == "travel" else []
        for service in npc.get("services", []):
            if service.get("type", "") in ["travel", "teleport"]:destinations.append_array(service.get("map_ids", []))
        for destination_id in destinations:
            var target = aliases.get(destination_id, destination_id)
            if maps.has(target):
                result.append({"x":npc.x,"y":npc.y,"target":target,"entry":maps[target].get("entry", []),"label":str(npc.get("name", "길 안내인")),"trigger":"npc_travel","npc_id":npc.get("id", "")})
    return result

static func edge_goals(edge: Dictionary) -> Array:
    var at = Vector2i(edge.x, edge.y)
    if edge.get("trigger", "") == "npc_travel":return [at + Vector2i.UP, at + Vector2i.LEFT, at + Vector2i.DOWN, at + Vector2i.RIGHT]
    return [at]

static func local_path(map: Dictionary, origin: Vector2i, goals: Array, maximum: int = 16384) -> Dictionary:
    var occupied = {}
    for npc in map.get("npcs", []):
        if npc.get("blocking", true):occupied[Vector2i(npc.x, npc.y)] = true
    var passable = func(p, direction):
        return p.x >= 0 and p.y >= 0 and p.x < int(map.width) and p.y < int(map.height) and not map.blocked[p.y][p.x] and not occupied.has(p) and (not map.has("collision_masks") or (int(map.collision_masks[p.y][p.x]) & [1, 8, 2, 4][direction]) == 0)
    return Pathfinder.search_any(origin, goals, passable, maximum)

static func geometry_image(map: Dictionary) -> Image:
    var image = Image.create(int(map.width), int(map.height), false, Image.FORMAT_RGBA8)
    for y in range(int(map.height)):
        for x in range(int(map.width)):
            var color = WALL if map.blocked[y][x] else WALKABLE
            if not map.blocked[y][x] and map.has("collision_masks") and int(map.collision_masks[y][x]) != 0:color = PARTIAL
            image.set_pixel(x, y, color)
    return image

func texture_for(id: String) -> Texture2D:
    if not cached_images.has(id):
        cached_images[id] = ImageTexture.create_from_image(geometry_image(game.maps[id]));cache_order.append(id)
        if cache_order.size() > 4:cached_images.erase(cache_order.pop_front())
    return cached_images[id]

func choose_destination(id: String):
    destination = id
    var picker_index = map_ids.find(id)
    if picker_index >= 0:destination_picker.select(picker_index)
    route_result = region_route(game.maps, game.player.map, id, game.world.get("map_aliases", {}))
    route = route_result.path
    show_map(game.player.map)

func show_map(id: String):
    if not game.maps.has(id):return
    viewed_map = id;selected_cell = Vector2i(-1, -1)
    canvas.zoom = 1;canvas.pan = Vector2.ZERO
    title.text = "지도 · " + str(game.maps[id].name)
    local_origin = game.cell() if id == game.player.map else Vector2i(game.maps[id].entry[0], game.maps[id].entry[1])
    local_route = {}
    var index = route.find(id)
    if index > 0 and index - 1 < route_result.get("edges", []).size():
        var entry = route_result.edges[index - 1].get("entry", [])
        if entry.size() == 2:local_origin = Vector2i(entry[0], entry[1])
    if index >= 0 and index < route_result.get("edges", []).size():
        var portal = route_result.edges[index]
        selected_cell = Vector2i(portal.x, portal.y)
        local_route = local_path(game.maps[id], local_origin, edge_goals(portal))
    rebuild_route_panel()
    update_detail()
    canvas.queue_redraw()

func add_wrapped(value: String, color = Color(0.91, 0.87, 0.72)):
    var label = label_control(value, 16);label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    label.add_theme_color_override("font_color", color);route_box.add_child(label)

func rebuild_route_panel():
    for child in route_box.get_children():route_box.remove_child(child);child.queue_free()
    var m = game.maps[viewed_map]
    add_wrapped("실제 맵 좌표와 출구를 표시합니다. 어두운 칸은 벽입니다.")
    if route_result.get("status", "") == "UNREACHABLE":add_wrapped("현재 지역에서 목적지로 이어진 출구가 없습니다.", Color(1, 0.64, 0.44))
    elif route.size() > 1:
        add_wrapped("목적지까지 %d회 맵 이동" % (route.size() - 1))
        for index in range(route.size()):
            var id = route[index]
            var b = button_control("%d. %s" % [index + 1, game.maps[id].name], show_map.bind(id))
            b.clip_text = true;b.alignment = HORIZONTAL_ALIGNMENT_LEFT;route_box.add_child(b)
            if index < route_result.edges.size():
                var p = route_result.edges[index]
                var action = "걸어서 이동"
                if p.get("trigger", "") == "interact":action = "대화/상호작용"
                elif p.get("trigger", "") == "npc_travel":action = str(p.get("label", "길 안내인")) + "에게 대화"
                add_wrapped("출구 (%d, %d) · %s" % [int(p.x), int(p.y), action])
    add_wrapped("이 지역의 출구", Color(1, 0.74, 0.38))
    if m.get("portals", []).is_empty():add_wrapped("연결된 출구 없음")
    for index in range(m.get("portals", []).size()):
        var p = m.portals[index]
        var target = game.world.get("map_aliases", {}).get(p.get("target", ""), p.get("target", ""))
        var title_value = game.maps[target].name if game.maps.has(target) else "연결 누락: " + str(target)
        var b = button_control("◇ %s  (%d,%d)" % [title_value, int(p.x), int(p.y)], select_portal.bind(index))
        b.clip_text = true;b.alignment = HORIZONTAL_ALIGNMENT_LEFT;route_box.add_child(b)
    for n in m.get("npcs", []):
        if n.get("role", "") == "travel" or n.get("services", []).any(func(s):return s.get("type", "") in ["travel", "teleport"]):
            add_wrapped("■ %s (%d,%d) · 대화로 지역 이동" % [n.get("name", "길 안내인"), int(n.x), int(n.y)])
    var levels = m.get("recommended_level", [])
    if levels.size() == 2:add_wrapped("권장 레벨 %d ~ %d" % [int(levels[0]), int(levels[1])])
    add_wrapped("NPC %d · 몬스터 출현 위치 %d" % [m.get("npcs", []).size(), m.get("spawns", []).size()])

func select_portal(index: int):
    var portal = game.maps[viewed_map].portals[index]
    selected_cell = Vector2i(portal.x, portal.y)
    local_route = local_path(game.maps[viewed_map], local_origin, [selected_cell])
    update_detail();canvas.queue_redraw()

func map_rect() -> Rect2:
    if viewed_map == "":return Rect2()
    var m = game.maps[viewed_map]
    var scale_value = minf((canvas.size.x - 24) / maxf(1, m.width), (canvas.size.y - 24) / maxf(1, m.height)) * canvas.zoom
    var dims = Vector2(m.width, m.height) * scale_value
    return Rect2((canvas.size - dims) / 2 + canvas.pan, dims)

func point_for(position: Vector2) -> Vector2:
    var r = map_rect();var m = game.maps[viewed_map]
    return r.position + (position + Vector2.ONE * 0.5) * (r.size / Vector2(m.width, m.height))

func pick_cell(at: Vector2):
    var r = map_rect()
    if not r.has_point(at):return
    var m = game.maps[viewed_map]
    selected_cell = Vector2i(((at - r.position) / r.size * Vector2(m.width, m.height)).floor())
    local_route = local_path(m, local_origin, [selected_cell])
    update_detail();canvas.queue_redraw()

func update_detail():
    var value = "실제 지형 %d×%d · (%d,%d) 기준 · 확대 후 드래그로 이동" % [int(game.maps[viewed_map].width), int(game.maps[viewed_map].height), local_origin.x, local_origin.y]
    if selected_cell.x >= 0:
        var status = local_route.get("status", "")
        value = "선택 (%d,%d) · " % [selected_cell.x, selected_cell.y]
        value += "%d칸 경로" % local_route.path.size() if status == "FOUND" else {"UNREACHABLE":"걸어서 도달할 수 없음", "BUDGET_EXCEEDED":"경로 탐색 범위 초과"}.get(status, "")
        for n in game.maps[viewed_map].get("npcs", []):
            if Vector2i(n.x, n.y) == selected_cell:value += " · " + str(n.get("name", "NPC"))
        for p in game.maps[viewed_map].get("portals", []):
            if Vector2i(p.x, p.y) == selected_cell:value += " · 출구: " + str(p.get("label", p.get("target", "")))
    detail.text = value + " · 몬스터와 현재 장애물에 따라 실제 통행은 달라질 수 있습니다."

func draw_map(surface: Control):
    surface.draw_rect(Rect2(Vector2.ZERO, surface.size), Color(0.035, 0.05, 0.038))
    if viewed_map == "" or not game.maps.has(viewed_map):return
    var m = game.maps[viewed_map];var r = map_rect()
    surface.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    surface.draw_texture_rect(texture_for(viewed_map), r, false)
    surface.draw_rect(r, Color(0.63, 0.59, 0.38), false, 1)
    var radius = clampf(r.size.x / float(m.width) * 0.7, 3, 8)
    if local_route.get("status", "") == "FOUND":
        var points = PackedVector2Array([point_for(Vector2(local_origin))])
        for position in local_route.path:points.append(point_for(Vector2(position)))
        if points.size() > 1:surface.draw_polyline(points, Color(1, 0.86, 0.25), 2.5)
    for spawn in m.get("spawns", []):surface.draw_circle(point_for(Vector2(spawn.x, spawn.y)), maxf(2, radius * 0.5), Color(0.85, 0.32, 0.24, 0.8))
    for n in m.get("npcs", []):surface.draw_rect(Rect2(point_for(Vector2(n.x, n.y)) - Vector2.ONE * radius * 0.65, Vector2.ONE * radius * 1.3), Color(0.35, 0.91, 0.47))
    for p in m.get("portals", []):
        var at = point_for(Vector2(p.x, p.y))
        surface.draw_polyline(PackedVector2Array([at + Vector2(0, -radius), at + Vector2(radius, 0), at + Vector2(0, radius), at + Vector2(-radius, 0), at + Vector2(0, -radius)]), Color(1, 0.65, 0.16), 2)
    if viewed_map == game.player.map:
        var at = point_for(Vector2(game.player.x, game.player.y))
        surface.draw_circle(at, radius + 2, Color(0.05, 0.12, 0.14));surface.draw_circle(at, radius, Color(0.28, 0.91, 1))
    if selected_cell.x >= 0:surface.draw_arc(point_for(Vector2(selected_cell)), radius + 4, 0, TAU, 24, Color(1, 0.95, 0.65), 2)

func _notification(what):
    if what in [NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED] and canvas != null:canvas.down = false
