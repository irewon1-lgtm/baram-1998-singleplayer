extends Node2D

const Facing = preload("res://facing.gd")
const Navigation = preload("res://navigation.gd")
const Rules = preload("res://rules.gd")
const Store = preload("res://save_store.gd")
const Assets = preload("res://assets.gd")
const Content = preload("res://content_registry.gd")
const Effects = preload("res://effect_runtime.gd")
const Pathfinder = preload("res://pathfinder.gd")
const WorkAssets = preload("res://work_assets.gd")
const Startup = preload("res://startup.gd")
const STEP = 48
const VIEW = Rect2(0,48,768,480)
const DIRECTIONS = [Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]
var rules = Rules.new()
var store = Store.new()
var assets = Assets.new()
var world = {}
var maps = {}
var decoration_rows = {}
var entities = {}
var loot = []
var player = {}
var save_path = "user://saves/v2/character.json"
var content = Content.new()
var work_assets = WorkAssets.new(content)
var enhancement_instance = ""
var content_folder = ""
var asset_folder = ""
var font = FontFile.new()
var clock = 0.0
var move_wait = 0.0
var from_position = Vector2.ZERO
var step_progress = 1.0
var attack_wait = 0.0
var attack_elapsed = -1.0
var cast_elapsed = -1.0
var pickup_elapsed = -1.0
var pending_spell = {}
var poison_clock = 0.0
var impact_done = false
var attack_target = ""
var selected_target = ""
var hurt_time = 0.0
var effects = []
var floating_text = []
var log_lines = []
var menu = "creation"
var selected = 0
var choices = []
var npc = {}
var creation_job = 0
var name_edit: LineEdit
var creation_controls: Control
var audio_voices = {}
var recorder = AudioEffectRecord.new()
var audio_events = []
var event_log = []
var captures = []
var exercise_path = ""
var test_mode = ""
var test_root = ""
var exercise_started = false
var options = {}
var save_loaded = false
var save_queued = false
var loaded_snapshot = {}
var service_definition = {}
var startup_ready = false
var startup_failed = false
var startup_started = 0
var startup_phases = []
var loading_layer: CanvasLayer
var loading_label: Label
var loading_progress: ProgressBar
var startup_log_path = ""
var continuity
var continuity_blocked=false
var mobile=false
var navigation
var walk_clock=0.0
var direct_direction=-1
var last_menu_state="creation"
var frame_times=PackedFloat64Array()
var last_frame_us=0
var touch_controls

func show_loading():
    loading_layer=CanvasLayer.new();loading_layer.layer=100;add_child(loading_layer)
    var panel=ColorRect.new();panel.color=Color(0.055,0.065,0.055)
    panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);loading_layer.add_child(panel)
    var system_font=SystemFont.new();system_font.font_names=PackedStringArray(["Malgun Gothic","맑은 고딕","Noto Sans CJK KR","Arial"])
    loading_label=Label.new();loading_label.position=Vector2(100,250);loading_label.size=Vector2(760,100)
    loading_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    loading_label.add_theme_font_override("font",system_font);loading_label.add_theme_font_size_override("font_size",24)
    panel.add_child(loading_label)
    loading_progress=ProgressBar.new();loading_progress.position=Vector2(160,370);loading_progress.size=Vector2(640,24)
    panel.add_child(loading_progress)

func startup_phase(name: String, progress: int):
    loading_label.text=name+"\n잠시 기다려 주세요."
    loading_progress.value=progress
    var entry={"stage":name,"elapsed_ms":Time.get_ticks_msec()-startup_started,"static_memory":OS.get_static_memory_usage()}
    startup_phases.append(entry);print("BARAM_STARTUP "+JSON.stringify(entry))
    if startup_log_path!="":
        DirAccess.make_dir_recursive_absolute(startup_log_path.get_base_dir())
        var file=FileAccess.open(startup_log_path,FileAccess.WRITE)
        if file!=null:file.store_string(JSON.stringify({"ready":false,"phases":startup_phases},"  "));file.close()
    await get_tree().process_frame
    await get_tree().process_frame

func fail_startup(message: String):
    startup_failed=true
    loading_label.text="실행 오류\n"+message+"\n자동 오류 로그를 남겼습니다."
    push_error("BARAM_STARTUP_FAILED: "+message)
    if startup_log_path!="":
        var file=FileAccess.open(startup_log_path,FileAccess.WRITE)
        if file!=null:file.store_string(JSON.stringify({"ready":false,"error":message,"phases":startup_phases},"  "));file.close()
    if DisplayServer.get_name()=="headless":get_tree().quit(2)

func _ready():
    startup_started=Time.get_ticks_msec()
    show_loading()
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts = arg.trim_prefix("--").split("=",true,1)
            options[parts[0]] = parts[1]
    mobile=OS.get_name()=="Android" or options.has("touch-test")
    navigation=Navigation.new(self)
    if mobile:
        get_viewport().content_scale_size=Vector2i(960,640)
        get_viewport().content_scale_aspect=Window.CONTENT_SCALE_ASPECT_EXPAND
    asset_folder = options.get("assets",OS.get_environment("BARAM_PRIVATE_ASSETS"))
    if asset_folder == "":
        asset_folder = "res://private_assets" if OS.get_name()=="Android" else ProjectSettings.globalize_path("res://../private_assets")
    save_path = options.get("save",save_path)
    startup_log_path=save_path.get_base_dir().get_base_dir().get_base_dir().path_join("logs/startup.json")
    content_folder=options.get("content",OS.get_environment("BARAM_PRIVATE_CONTENT"))
    if content_folder=="":content_folder="res://private_content" if OS.get_name()=="Android" else ProjectSettings.globalize_path("res://../private_content")
    await startup_phase("콘텐츠와 지도 준비",10)
    var world_path=asset_folder.path_join("source_maps/world.json")
    if not FileAccess.file_exists(world_path):world_path="res://data/world.json"
    var startup=Startup.new()
    var worker=Thread.new()
    var task=worker.start(startup.prepare.bind(content,content_folder,world_path,asset_folder.get_base_dir().path_join("runtime_cache")))
    if task!=OK:fail_startup("BACKGROUND_START");return
    while worker.is_alive():
        await get_tree().create_timer(0.016).timeout
    worker.wait_to_finish()
    if not startup.result.get("ok",false):fail_startup(JSON.stringify(startup.result.get("error",{})));return
    world=startup.result.world
    await startup_phase("게임 규칙 연결",35)
    content.apply_rules(rules)
    store.content_version=content.version
    var build_path="res://data/build_info.json"
    if FileAccess.file_exists(build_path):
        var build_info=JSON.parse_string(FileAccess.get_file_as_string(build_path))
        if typeof(build_info)!=TYPE_DICTIONARY or build_info.get("content_version","")!=content.version:
            fail_startup("PACKAGE_CONTENT_VERSION: build_info.json and ACTIVE content disagree");return
        store.game_build=str(build_info.get("commit","unidentified-package"))
    test_mode = options.get("exercise","")
    test_root = options.get("evidence","")
    await startup_phase("그래픽 준비",50)
    if not assets.load_directory(asset_folder):fail_startup("PRIVATE_ASSET_HASH_OR_FORMAT");return
    await startup_phase("글꼴과 음향 준비",70)
    font.data = FileAccess.get_file_as_bytes(asset_folder.path_join("fonts/NotoSansCJK-Regular.ttc"))
    font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
    await startup_phase("맵과 캐릭터 연결",80)
    for m in world.maps:
        maps[m.id] = m
        var rows={}
        for d in m.get("decorations",[]):
            var y=int(d.y)
            if not rows.has(y):rows[y]=[]
            rows[y].append(d)
        decoration_rows[m.id]=rows
        for spawn in m.spawns:
            var spec = rules.monster(spawn.kind,world.replacements)
            entities[spawn.id] = {"id":spawn.id,"kind":spawn.kind,"map":m.id,"x":spawn.x,"y":spawn.y,
                "home_x":spawn.x,"home_y":spawn.y,"direction":2,"hp":int(spec.values.hp),"alive":true,
                "respawn":0.0,"move_timer":3.0,"attack_timer":0.0,"provoked":false,"hurt":0.0,
                "hp_max":int(spec.values.hp),"mp":int(rules.value_or(spec.values,"mp",0)),"mp_max":int(rules.value_or(spec.values,"mp",0)),"statuses":{},"spec":spec}
    for kind in ["attack","hit","skill","level"]:
        var voice = AudioStreamPlayer.new()
        add_child(voice)
        audio_voices[kind] = voice
    if test_mode != "":
        AudioServer.add_bus_effect(0,recorder)
        recorder.set_recording_active(true)
    await startup_phase("저장 파일 확인",95)
    var requested_save=save_path
    var migrated_path=save_path.get_base_dir().path_join("v2").path_join(save_path.get_file())
    if not save_path.get_base_dir().ends_with("/v2") and FileAccess.file_exists(migrated_path):save_path=migrated_path
    var saved = store.read_state(save_path)
    if saved.is_empty() and store.last_status=="MISSING" and save_path.get_base_dir().ends_with("/v2"):
        var legacy=save_path.get_base_dir().get_base_dir().path_join(save_path.get_file())
        if FileAccess.file_exists(legacy):saved=store.read_state(legacy)
    if not saved.is_empty():
        if saved.get("migrated_from_schema",0)==1 and not save_path.get_base_dir().ends_with("/v2"):save_path=migrated_path
        loaded_snapshot = saved.duplicate(true)
        restore(saved)
        menu = ""
        save_loaded = true
        notice("저장한 여정을 이어갑니다.")
    elif store.last_status=="MISSING" and not FileAccess.file_exists(requested_save):
        setup_creation()
    else:
        menu="save_error"
        notice("저장을 읽지 못했습니다: "+store.last_status+". 원본은 보존했습니다. Q: 종료")
    startup_ready=true
    loading_layer.queue_free()
    var startup_report={"ready":true,"elapsed_ms":Time.get_ticks_msec()-startup_started,"phases":startup_phases,
        "content_ms":startup.result.content_ms,"world_ms":startup.result.world_ms,"cache_used":startup.result.cache_used,
        "registered_tiles":assets.tiles.size(),"maps":maps.size(),"static_memory":OS.get_static_memory_usage()}
    print("BARAM_READY "+JSON.stringify(startup_report))
    var startup_file=FileAccess.open(startup_log_path,FileAccess.WRITE)
    if startup_file!=null:startup_file.store_string(JSON.stringify(startup_report,"  "));startup_file.close()
    event("ready",{"registered_tiles":assets.tiles.size(),"loaded_save":save_loaded,
                   "renderer":RenderingServer.get_current_rendering_method()})
    if test_mode != "":
        if options.has("verification-pack") and not ProjectSettings.load_resource_pack(options["verification-pack"]):
            fail_startup("VERIFICATION_PACK_MISSING");return
        call_deferred("start_exercise")
    else:
        continuity=load("res://continuity.gd").new();add_child(continuity)
        await continuity.initialize(self)
    if OS.get_name()=="Android" or options.has("touch-test"):
        touch_controls=load("res://touch_controls.gd").new();add_child(touch_controls);touch_controls.initialize(self)
    queue_redraw()

func setup_creation():
    creation_controls = Control.new()
    add_child(creation_controls)
    name_edit = LineEdit.new()
    name_edit.position = Vector2(354,243)
    name_edit.size = Vector2(252,36)
    name_edit.text = "바람여행자"
    name_edit.max_length = 12
    name_edit.add_theme_font_override("font",font)
    name_edit.add_theme_font_size_override("font_size",18)
    creation_controls.add_child(name_edit)
    for i in range(4):
        var button = Button.new()
        button.text = Rules.JOBS[i]
        button.position = Vector2(268+i*110,302)
        button.size = Vector2(100,42)
        button.add_theme_font_override("font",font)
        button.pressed.connect(func():creation_job=i;queue_redraw())
        creation_controls.add_child(button)
    var start_button = Button.new()
    start_button.text = "여정 시작"
    start_button.position = Vector2(398,382)
    start_button.size = Vector2(164,40)
    start_button.add_theme_font_override("font",font)
    start_button.pressed.connect(create_character)
    creation_controls.add_child(start_button)

func create_character():
    if menu != "creation":
        return
    var title = name_edit.text.strip_edges()
    if title == "":
        title = "바람여행자"
    player = rules.new_player(Rules.JOBS[creation_job],title)
    var start=world.get("start",{"map":"village","entry":[12,12]})
    player.map=start.map;player.x=int(start.entry[0]);player.y=int(start.entry[1])
    player.world_revision=world.get("revision","authored-1")
    creation_controls.queue_free()
    menu = ""
    reset_motion()
    event("character_created",{"job":player.job,"name":player.name})
    if continuity!=null:save_game()
    notice("장비상에게 Enter로 대화하세요. I: 물품, E: 장착, Space: 공격")
    queue_redraw()

func event(kind: String, info: Dictionary = {}):
    event_log.append({"time":snappedf(clock,0.001),"event":kind,"details":info.duplicate(true)})
    while event_log.size()>512:event_log.pop_front()

func notice(message: String):
    log_lines.append(message)
    while log_lines.size() > 4:
        log_lines.pop_front()

func _input(input):
    if continuity_blocked:return
    if not startup_ready:
        if startup_failed and input is InputEventKey and input.pressed and input.keycode in [KEY_Q,KEY_ESCAPE]:get_tree().quit(2)
        return
    if not input is InputEventKey or not input.pressed or input.echo:
        return
    var key = input.keycode
    if menu=="save_error":
        if key in [KEY_Q,KEY_ESCAPE]:get_tree().quit()
        return
    if key==KEY_F8:
        write_diagnostic("USER_SNAPSHOT")
        return
    if key in [KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT,KEY_W,KEY_A,KEY_S,KEY_D] and menu=="":navigation.cancel()
    if key==KEY_O and menu=="":
        menu="equipment";selected=0;choices=player.get("equipment_instances",{}).keys().filter(func(id):return not player.equipment_instances[id].destroyed)
        return
    if menu == "creation":
        if key == KEY_ENTER:
            create_character()
        elif key in [KEY_1,KEY_2,KEY_3,KEY_4]:
            creation_job = int(key-KEY_1)
        return
    if key == KEY_F5:
        save_game()
        return
    if key == KEY_F6 and (continuity==null or not continuity.playing):
        var saved = store.read_state(save_path)
        if not saved.is_empty():
            restore(saved)
            notice("저장 상태를 복구했습니다.")
        return
    if key == KEY_ESCAPE:
        if menu != "":
            menu = ""
            clear_inputs()
        else:
            clear_inputs()
            save_game()
            menu = "pause"
        return
    if menu != "":
        handle_menu_key(key)
        return
    if key == KEY_I:
        open_inventory()
    elif key==KEY_K:
        menu="skills";selected=0;choices=player.skills.duplicate()
    elif key == KEY_E:
        var title = player.equipped if player.equipped != "" else "목도"
        if rules.equip(player,title):
            event("equipped",{"item":title})
            notice(title + " 장착")
    elif key == KEY_SPACE:
        navigation.attack_selected()
    elif key == KEY_ENTER or key == KEY_F:
        interact()
    elif key == KEY_G or key == KEY_COMMA:
        pickup()
    elif key in [KEY_1,KEY_2,KEY_3]:
        cast_skill(int(key-KEY_1))
    elif key == KEY_TAB:
        cycle_target()
    elif key == KEY_M:
        menu = "map"
        choices = []
        for m in world.maps:
            choices.append(m.name)
    elif key in [KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT,KEY_W,KEY_A,KEY_S,KEY_D]:
        var d = {KEY_UP:0,KEY_LEFT:1,KEY_DOWN:2,KEY_RIGHT:3,KEY_W:0,KEY_A:1,KEY_S:2,KEY_D:3}[key]
        if input.shift_pressed:
            if attack_elapsed >= 0 or cast_elapsed>=0:return
            player.direction = d
            move_wait = 0.18
            event("turned",{"direction":d})
        else:
            move_player(d)
    queue_redraw()

func _process(delta: float):
    if not startup_ready:return
    if continuity_blocked and (continuity==null or not continuity.resolving):return
    var now_us=Time.get_ticks_usec()
    if last_frame_us>0 and frame_times.size()<72000:frame_times.append((now_us-last_frame_us)/1000.0)
    last_frame_us=now_us
    if menu!=last_menu_state:
        clear_inputs();last_menu_state=menu
    clock += delta
    if player.is_empty():
        queue_redraw()
        return
    if menu in ["pause","save_error"] and (continuity==null or not continuity.resolving):queue_redraw();return
    rules.tick(player,delta)
    var alive_before=player.hp>0
    Effects.tick(rules.actions,player,delta)
    if alive_before and player.hp==0:on_player_death()
    if player.buffs.get("독",0)>0 and player.hp>0:
        poison_clock+=delta
        if poison_clock>=1.0:poison_clock-=1.0;hurt_player(2,"poison")
    else:poison_clock=0.0
    var was_moving=step_progress<1.0
    move_wait = maxf(-0.1,move_wait-delta)
    if was_moving:walk_clock+=delta
    attack_wait = maxf(-0.1,attack_wait-delta)
    hurt_time = maxf(0,hurt_time-delta)
    step_progress = minf(1,step_progress + delta/0.18)
    if cast_elapsed>=0:
        cast_elapsed+=delta
        var impact=float(pending_spell.get("profile",{}).get("definition",{}).get("animation",{}).get("impact_delay_ms",180))/1000.0
        if cast_elapsed>=impact and not pending_spell.is_empty():
            resolve_spell(pending_spell)
            pending_spell={}
        if cast_elapsed>=0.42:cast_elapsed=-1.0
    if pickup_elapsed>=0:
        pickup_elapsed+=delta
        if pickup_elapsed>=0.22:pickup_elapsed=-1.0
    if attack_elapsed >= 0:
        attack_elapsed += delta
        if not impact_done and attack_elapsed >= 0.16:
            impact_done = true
            apply_attack()
        if attack_elapsed >= 0.4:
            attack_elapsed = -1.0
    if menu == "" and not continuity_blocked:
        if Input.is_physical_key_pressed(KEY_SPACE):navigation.attack_selected()
        var direction=direct_direction
        for k in [KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT,KEY_W,KEY_A,KEY_S,KEY_D]:
            if Input.is_physical_key_pressed(k):
                navigation.cancel()
                direction={KEY_UP:0,KEY_LEFT:1,KEY_DOWN:2,KEY_RIGHT:3,KEY_W:0,KEY_A:1,KEY_S:2,KEY_D:3}[k]
                break
        if direction>=0:move_player(direction)
        navigation.tick(delta)
        update_monsters(delta)
    for fx in effects:
        fx.time += delta
    effects = effects.filter(func(fx):return fx.time < float(fx.get("lifetime_ms",assets.actor_data.get(fx.get("key",""),{}).get("lifetime_ms",800)))/1000.0)
    for text in floating_text:
        text.time += delta
    floating_text = floating_text.filter(func(t):return t.time < 0.9)
    if save_queued and attack_elapsed<0 and cast_elapsed<0:
        save_queued=false
        save_game()
    queue_redraw()

func cell() -> Vector2i:
    return Vector2i(int(player.x),int(player.y))

func field_rect() -> Rect2:
    return Rect2(Vector2.ZERO,get_viewport_rect().size) if mobile else VIEW

func visual_position() -> Vector2:
    if player.is_empty():return Vector2(4,7)
    return from_position.lerp(Vector2(player.x,player.y),step_progress) if step_progress<1 else Vector2(player.x,player.y)

func camera() -> Vector2:
    if player.is_empty():return Vector2(4,7)
    var m=maps[player.map];var size=field_rect().size/STEP;var p=visual_position()
    return Vector2(clampf(p.x-size.x/2,0,maxf(0,float(m.width)-size.x)),clampf(p.y-size.y/2,0,maxf(0,float(m.height)-size.y))).snapped(Vector2.ONE/STEP)

func screen_point(x: float,y: float) -> Vector2:
    return (field_rect().position + (Vector2(x,y)-camera())*STEP + Vector2(STEP/2,STEP)).round()

func reset_motion():
    if not player.is_empty():from_position=Vector2(player.x,player.y)
    step_progress=1.0;move_wait=0.0
    if navigation!=null:navigation.cancel()

func clear_inputs():
    direct_direction=-1
    if navigation!=null:navigation.cancel()
    if touch_controls!=null:touch_controls.release_all()

func _unhandled_input(input):
    if not startup_ready or continuity_blocked or menu!="" or mobile:return
    if input is InputEventMouseButton and input.pressed and input.button_index==MOUSE_BUTTON_LEFT and field_rect().has_point(input.position):navigation.tap(input.position)

func _notification(what):
    if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:clear_inputs()
    if what==NOTIFICATION_WM_GO_BACK_REQUEST and mobile:
        if continuity!=null and continuity.panel.visible:
            if not continuity.busy:continuity.panel.hide();continuity_blocked=false
        elif menu!="creation":
            var e=InputEventKey.new();e.pressed=true;e.keycode=KEY_ESCAPE;_input(e)
        clear_inputs()

func free_cell(map_id: String, pos: Vector2i, actor_id: String = "",direction: int = -1) -> bool:
    var m = maps[map_id]
    if pos.x < 0 or pos.y < 0 or pos.x >= int(m.width) or pos.y >= int(m.height) or m.blocked[pos.y][pos.x]:
        return false
    if direction>=0 and m.has("collision_masks") and (int(m.collision_masks[pos.y][pos.x]) & [1,8,2,4][direction])!=0:return false
    if actor_id != "":
        for portal in m.portals:
            if pos==Vector2i(portal.x,portal.y):return false
    for id in entities:
        var e = entities[id]
        if id != actor_id and e.alive and e.map == map_id and Vector2i(e.x,e.y) == pos:
            return false
    for n in m.npcs:
        if n.get("blocking",true) and Vector2i(n.x,n.y)==pos:return false
    return true

func move_player(direction: int):
    if move_wait > 0.000001 or attack_elapsed >= 0 or cast_elapsed>=0 or menu != "" or rules.actions.status_modifier(player,"stun")>0:
        return
    player.direction = direction
    var next = cell() + DIRECTIONS[direction]
    if not free_cell(player.map,next,"",direction):
        event("collision",{"map":player.map,"x":next.x,"y":next.y})
        return
    from_position = Vector2(player.x,player.y)
    player.x = next.x
    player.y = next.y
    var carry=maxf(0,-move_wait) if step_progress>=1 and move_wait> -0.09 else 0.0
    step_progress = carry/0.18
    move_wait = 0.18-carry
    event("moved",{"map":player.map,"x":player.x,"y":player.y,"direction":direction})
    for portal in maps[player.map].portals:
        if portal.get("trigger","walk")=="walk" and next == Vector2i(portal.x,portal.y):
            transition(portal.target,portal.entry)
            break

func transition(map_id: String, entry: Array):
    map_id=world.get("map_aliases",{}).get(map_id,map_id)
    if not maps.has(map_id) or entry.size()!=2:
        event("map_transition_error",{"code":"DESTINATION_MISSING","map":map_id,"entry":entry});return
    player.map = map_id
    player.x = int(entry[0])
    player.y = int(entry[1])
    if not player.has("visited"):player.visited=[]
    if map_id not in player.visited:player.visited.append(map_id)
    reset_motion()
    selected_target = ""
    attack_elapsed=-1.0;attack_target="";cast_elapsed=-1.0;pending_spell={};effects.clear()
    work_assets.tile_cache.clear()
    event("map_changed",{"map":map_id,"x":player.x,"y":player.y})
    notice(maps[map_id].name)

func cycle_target():
    var available = []
    for id in entities:
        var e = entities[id]
        if e.map == player.map and e.alive and Vector2i(e.x,e.y).distance_to(cell()) < 7:
            available.append(id)
    if available.is_empty():
        selected_target = ""
    else:
        selected_target = available[(available.find(selected_target)+1)%available.size()]

func begin_attack():
    if attack_wait > 0.000001 or cast_elapsed>=0 or int(player.hp) <= 0 or menu != "" or rules.actions.status_modifier(player,"stun")>0:
        return
    attack_wait = 0.6+minf(0,attack_wait) if attack_wait> -0.09 else 0.6
    attack_elapsed = 0.0
    impact_done = false
    attack_target = ""
    var target_cell = cell()+DIRECTIONS[int(player.direction)]
    for id in entities:
        var e = entities[id]
        if e.map == player.map and e.alive and Vector2i(e.x,e.y) == target_cell:
            attack_target = id
            break
    event("attack_started",{"target":attack_target,"direction":player.direction,"interval_ms":600,"impact_ms":160})

func apply_attack():
    play_sound("attack")
    if attack_target == "" or not entities[attack_target].alive:
        return
    var e = entities[attack_target]
    # A moving target must still occupy the facing tile at the impact instant.
    if e.map != player.map or Vector2i(e.x,e.y) != cell()+DIRECTIONS[int(player.direction)]:
        event("attack_missed_moved_target")
        return
    if not rules.roll(0.99 if player.buffs.get("신의축복",0)>0 else 0.9):
        event("attack_missed_probability")
        return
    var amount = rules.damage(rules.weapon_damage(player),int(e.spec.values.armor_class)+rules.actions.status_modifier(e,"armor_class"))
    player.buffs.erase("무영보법");player.buffs.erase("금수");player.buffs.erase("경수")
    hit_monster(e,amount,"melee")
    for offset in [2,1,3]:
        var enabled=player.buffs.get("후면공격",0)>0 if offset==2 else player.buffs.get("측면공격",0)>0
        if not enabled:continue
        var d=(int(player.direction)+offset)%4
        for other in entities.values():
            if other.alive and other.map==player.map and Vector2i(other.x,other.y)==cell()+DIRECTIONS[d]:hit_monster(other,amount,"directional_buff")
    if player.equipped != "":
        rules.actions.damage_gear(player,1)
        if player.equipped=="":
            notice("무기가 파손되었습니다. 장비상에게 수리하세요.")

func hit_monster(e: Dictionary, amount: int, source: String,skill_name: String = "", already_applied: bool=false):
    if not e.alive:return
    if not already_applied:rules.actions.damage(e,amount)
    e.hurt = 0.18
    e.provoked = true
    floating_text.append({"x":e.x,"y":e.y,"text":str(amount),"time":0.0,"color":Color(1,0.8,0.4)})
    play_sound("hit")
    event("damage_applied",{"target":e.id,"damage":amount,"hp":e.hp,"source":source,"skill":skill_name,"impact_time":cast_elapsed if source=="skill" else attack_elapsed})
    if e.hp <= 0:
        e.alive = false
        e.respawn = float(e.spec.values.respawn_interval_ms)/1000.0
        var reward = rules.reward_kill(player,e.spec,e.kind)
        var gains = reward.levels
        var drop_items = reward.drops
        for drop in drop_items:
            loot.append({"map":player.map,"x":e.x,"y":e.y,"item":drop.item,"quantity":drop.quantity})
        var gold = reward.gold
        event("monster_killed",{"id":e.id,"xp":e.spec.values.experience,"level":player.level,"drops":drop_items,"gold":gold})
        if gains.size() > 0:
            event("level_up",{"levels":gains})
            notice("레벨 %d! 체력과 마력이 회복되었습니다." % player.level)
            play_sound("level")

func hurt_player(amount: int, attacker: String):
    rules.actions.damage(player,amount)
    hurt_time=0.18
    play_sound("hit")
    event("player_hit",{"damage":amount,"hp":player.hp,"attacker":attacker})
    if player.hp==0:
        on_player_death()

func on_player_death():
    event("player_died")
    var home=world.get("home",{"map":"village","entry":[12,12]})
    transition(home.map,home.entry)
    player.buffs.erase("독");player.statuses.clear()
    notice("혼령이 되었습니다. 성황에게 Enter로 부활하세요.")

func update_monsters(delta: float):
    for id in entities:
        var e=entities[id]
        e.hurt=maxf(0,float(e.hurt)-delta)
        if not e.alive:
            e.respawn-=delta
            if e.respawn<=0:
                e.alive=true;e.hp=int(e.spec.values.hp);e.x=e.home_x;e.y=e.home_y;e.provoked=false;e.attack_elapsed=-1.0
            continue
        if e.map!=player.map:continue
        Effects.tick_at(rules.actions,e,int(player.time_us)/1000)
        if e.hp<=0:hit_monster(e,0,"status", "",true);continue
        if rules.actions.status_modifier(e,"stun")>0:continue
        e.move_timer-=delta;e.attack_timer-=delta
        var distance=Vector2i(e.x,e.y).distance_to(cell())
        var hidden=player.buffs.get("무영보법",0)>0 or player.buffs.get("금수",0)>0 or player.buffs.get("경수",0)>0 or rules.actions.status_modifier(player,"hidden")!=0
        var behavior=rules.runtime_definitions.get(e.kind,{}).get("data",{}).get("behavior",{})
        var aggressive=(behavior.get("aggression","passive" if e.kind in ["rabbit","squirrel"] else "hostile")=="hostile" or e.provoked) and (not hidden or e.provoked)
        var elapsed=float(e.get("attack_elapsed",-1))
        if elapsed>=0:
            e.attack_elapsed=elapsed+delta
            if e.get("attack_pending",false) and e.attack_elapsed>=0.16:
                e.attack_pending=false
                var probability=e.spec.values.hit_probability
                var hit=Rules.Precision.roll(rules.rng,probability) if typeof(probability)==TYPE_DICTIONARY else rules.roll(float(probability))
                if rules.actions.status_modifier(e,"blind")>0:hit=hit and rules.rng.randi_range(0,99)>=clampi(rules.actions.status_modifier(e,"blind"),0,100)
                var in_range=Vector2i(e.x,e.y).distance_to(cell())<=int(e.spec.values.get("attack_range_tiles",1))
                var targeting=in_range and line_of_sight(e.map,Vector2i(e.x,e.y),cell()) if e.spec.values.get("attack_kind","melee")=="ranged" else cell()==Vector2i(e.x,e.y)+DIRECTIONS[int(e.direction)]
                if player.hp>0 and targeting and hit:
                    var attack=rules.rng.randi_range(int(e.spec.values.attack_min),int(e.spec.values.attack_max))
                    hurt_player(rules.incoming_damage(player,attack),id)
                    apply_monster_specials(e)
                    if e.kind=="snake" and player.hp>0 and rules.roll(0.15):
                        player.buffs["독"]=8.0
                        event("poison_applied",{"source":"snake","classification":"SINGLEPLAYER_ESTIMATE"})
            var spec=assets.actor_data.get(visual_key(e.kind),{"attack":1,"delay_ms":100})
            if e.attack_elapsed>=maxf(0.28,int(spec.attack)*float(spec.delay_ms)/1000.0):e.attack_elapsed=-1.0
            continue
        var range_tiles=int(e.spec.values.get("attack_range_tiles",1))
        if player.hp>0 and aggressive and distance<=range_tiles and e.attack_timer<=0 and line_of_sight(e.map,Vector2i(e.x,e.y),cell()):
            e.attack_timer=float(e.spec.values.attack_interval_ms)/1000.0
            var offset=cell()-Vector2i(e.x,e.y)
            e.direction=(3 if offset.x>0 else 1) if absi(offset.x)>absi(offset.y) else (2 if offset.y>0 else 0)
            e.attack_elapsed=0.0;e.attack_pending=true
            event("monster_attack_started",{"id":id,"direction":e.direction,"impact_ms":160,"source_attack_frames":assets.actor_data.get(visual_key(e.kind),{}).get("attack",0)})
            continue
        if e.move_timer<=0:
            e.move_timer=float(e.spec.values.move_interval_ms)/1000.0
            var d=rules.rng.randi_range(0,3)
            if aggressive and distance<=float(e.spec.values.aggro_radius_tiles) and player.hp>0:
                var offset=cell()-Vector2i(e.x,e.y)
                d=3 if offset.x>0 else 1
                if absi(offset.y)>absi(offset.x):d=2 if offset.y>0 else 0
            if rules.actions.status_modifier(e,"confuse")>0:d=rules.rng.randi_range(0,3)
            var next=Vector2i(e.x,e.y)+DIRECTIONS[d]
            if aggressive and distance<12 and not free_cell(e.map,next,id,d):
                var destination=cell()-DIRECTIONS[d]
                var plan=Pathfinder.search(Vector2i(e.x,e.y),destination,func(p,dir):return p!=cell() and free_cell(e.map,p,id,dir) and p.distance_to(Vector2i(e.home_x,e.home_y))<=float(e.spec.values.leash_radius_tiles),128)
                if plan.status=="FOUND" and not plan.path.is_empty():next=plan.path[0];d=DIRECTIONS.find(next-Vector2i(e.x,e.y))
            if next!=cell() and free_cell(e.map,next,id,d) and next.distance_to(Vector2i(e.home_x,e.home_y))<=float(e.spec.values.leash_radius_tiles):e.x=next.x;e.y=next.y;e.direction=d

func pickup():
    pickup_elapsed=0.0
    var remaining = []
    for drop in loot:
        if drop.map == player.map and Vector2i(drop.x,drop.y).distance_to(cell()) <= 1.1 and rules.add_item(player,drop.item,int(drop.quantity)):
            notice(drop.item + " 획득")
            event("item_picked_up",drop)
        else:
            remaining.append(drop)
    loot = remaining

func line_of_sight(map_id: String, origin: Vector2i, destination: Vector2i) -> bool:
    var difference=destination-origin;var steps=maxi(absi(difference.x),absi(difference.y))
    if steps>32:return false
    for step in range(1,steps):
        var position=origin+Vector2i(roundi(float(difference.x)*step/steps),roundi(float(difference.y)*step/steps))
        if maps[map_id].blocked[position.y][position.x]:return false
    return true

func apply_monster_specials(e: Dictionary):
    if player.hp<=0:return
    var behavior=rules.runtime_definitions.get(e.kind,{}).get("data",{}).get("behavior",{})
    for special in behavior.get("special",[]):
        if special.get("trigger","")!="attack_hit" or special.get("op","")!="status" or special.get("status","")!="poison":
            event("monster_special_error",{"code":"UNKNOWN_MONSTER_SPECIAL","monster_id":e.kind,"data":special});continue
        if Rules.Precision.roll(rules.rng,special.probability):
            var result=Effects.apply(rules.actions,player,[],[{"type":"status","target":"self","status_id":"poison","duration_ms":special.duration_ms,"tick_ms":special.period_ms,"amount":special.damage}])
            event("monster_status_applied",{"monster_id":e.kind,"result":result,"status":"poison"})

func cast_skill(slot: int):
    if slot>=player.hotbar.size() or player.hotbar[slot]=="" or cast_elapsed>=0 or attack_elapsed>=0:return
    var title=str(player.hotbar[slot])
    var s=rules.skill(player,title)
    var profile=rules.skill_profile(player,title)
    var ghost_allowed=title=="성황령" or profile.get("effects",[]).any(func(e):return e.get("requires_ghost",false) or e.get("type","")=="revive")
    if int(player.hp)<=0 and not ghost_allowed:return
    if profile.type=="work_effects":
        var validated=Effects.validate(profile.effects)
        if not validated.ok:
            event("skill_blocked",{"skill":title,"error":validated});notice("기술 효과 연결 오류: "+validated.error);return
    if profile.type=="unresolved":
        event("skill_blocked",{"skill":title,"reason":"BEHAVIOR_SOURCE_UNRESOLVED"})
        notice(title+"의 효과 자료를 아직 연결하지 못했습니다.")
        return
    var target={}
    if profile.type=="damage" or profile.type=="work_effects" and profile.effects.any(func(e):return e.get("target","self")=="enemy"):
        if entities.has(selected_target) and entities[selected_target].alive and entities[selected_target].map==player.map:target=entities[selected_target]
        else:
            var distance=999.0
            for candidate in entities.values():
                var d=Vector2i(candidate.x,candidate.y).distance_to(cell())
                if candidate.alive and candidate.map==player.map and d<distance:target=candidate;distance=d
        if target.is_empty() or Vector2i(target.x,target.y).distance_to(cell())>float(rules.value_or(s,"range_tiles",6)):
            notice("기술 사거리 안에 대상이 없습니다.");return
        var delta=Vector2i(target.x,target.y)-cell()
        player.direction=(3 if delta.x>0 else 1) if absi(delta.x)>absi(delta.y) else (2 if delta.y>0 else 0)
    var hp_cost=int(rules.value_or(s,"cast_hp",0))+floori(float(player.hp)*float(rules.value_or(s,"cast_hp_fraction",0)))
    if profile.has("definition"):
        var ratio=profile.definition.cost.get("hp_fraction",{"numerator":0,"denominator":1})
        hp_cost=int(profile.definition.cost.hp)+int(player.hp)*int(ratio.numerator)/int(ratio.denominator)
    if player.hp>0 and not rules.cast_resources(player,int(rules.value_or(s,"cast_mp",0)),hp_cost,float(rules.value_or(s,"cooldown_ms",1000))/1000.0,title):
        notice("마력·체력이 부족하거나 기술 준비 중입니다.")
        event("skill_rejected_resources",{"skill":title});return
    cast_elapsed=0.0
    pending_spell={"title":title,"values":s,"profile":profile,"target_id":target.get("id",""),"slot":slot}
    event("skill_started",{"skill":title,"slot":slot,"impact_ms":180,"classification":profile.get("classification","")})

func resolve_spell(cast: Dictionary):
    var title=cast.title
    var s=cast.values
    var profile=cast.profile
    var kind=profile.type
    var at=cell()
    if kind=="work_effects":
        var target=[]
        if entities.has(cast.target_id):
            var e=entities[cast.target_id]
            if e.alive and e.map==player.map and Vector2i(e.x,e.y).distance_to(cell())<=float(rules.value_or(s,"range_tiles",6)):
                target=[e]
                var radius=int(profile.definition.get("aoe_radius_tiles",0))
                if radius>0:
                    target=entities.values().filter(func(other):return other.alive and other.map==player.map and Vector2i(other.x,other.y).distance_to(Vector2i(e.x,e.y))<=radius)
        if not Rules.Precision.roll(rules.rng,profile.definition.get("success_ratio",{"numerator":1,"denominator":1})):
            event("skill_failed_probability",{"skill":title});notice("기술이 실패했습니다.");return
        var result=Effects.apply(rules.actions,player,target,profile.effects)
        if not result.ok:event("skill_effect_error",{"skill":title,"result":result});notice("기술 적용 오류: "+result.error);return
        for action in result.damage_events:
            if entities.has(action.id):hit_monster(entities[action.id],int(action.damage),"skill",title,true)
        for action in result.movement:
            apply_work_action(action)
        var visual=profile.definition.get("animation",{})
        var effect_id=visual.get("effect_asset_id","")
        if effect_id!="":effects.append({"work_asset":effect_id,"x":player.x,"y":player.y,"time":0.0,"lifetime_ms":int(visual.get("effect_duration_ms",2000))})
        if visual.get("sound_asset_id","")!="":play_work_sound(visual.sound_asset_id)
    elif kind=="heal":rules.heal(player,int(rules.value_or(s,"heal_amount",0)))
    elif kind=="damage":
        if entities.has(cast.target_id):
            var target=entities[cast.target_id]
            if target.alive and target.map==player.map and Vector2i(target.x,target.y).distance_to(cell())<=float(rules.value_or(s,"range_tiles",6)):
                at=Vector2i(target.x,target.y)
                var raw=int(rules.value_or(s,"base_damage",0))
                if raw<=0:raw=int(profile.get("damage_fallback",0))
                var radius=float(rules.value_or(s,"aoe_radius_tiles",0))
                for other in entities.values():
                    if other.alive and other.map==player.map and Vector2i(other.x,other.y).distance_to(at)<=radius:
                        hit_monster(other,rules.damage(raw,int(other.spec.values.armor_class)),"skill",title)
                player.buffs.erase("무영보법");player.buffs.erase("금수");player.buffs.erase("경수")
    elif kind in ["return","spirit_return"]:
        var home=world.get("home",{"map":"village","entry":[12,12]})
        transition(home.map,home.entry);at=cell()
    elif kind=="charge":rules.actions.recovery(player,0,maxi(30,int(player.mp_max)*3/4))
    elif kind in ["cure","cleanse"]:
        player.buffs.erase("독")
        if kind=="cleanse":player.buffs.erase("저주")
    elif kind=="inspect":open_inventory()
    elif kind=="compass":
        menu="compass";selected=0;choices=["동쪽","서쪽","남쪽","북쪽"]
    elif kind=="travel":
        menu="travel";selected=0;choices=player.get("visited",["village"]).duplicate()
        if "village" not in choices:choices.append("village")
    elif kind=="summon":
        var m=maps[player.map]
        for d in range(4):
            var p=cell()+DIRECTIONS[d]
            if free_cell(player.map,p):
                var guide={"id":"summoned-guide","kind":"teacher","x":p.x,"y":p.y,"name":"소환된 길잡이","role":"travel","destinations":["village"],"map":player.map}
                m.npcs=m.npcs.filter(func(n):return n.id!="summoned-guide")
                m.npcs.append(guide);player.summoned_guide=guide;break
    else:player.buffs[title]=float(rules.value_or(s,"duration_ms",30000))/1000.0
    if kind!="work_effects":
        effects.append({"key":"fx_"+str(profile.effect),"x":at.x,"y":at.y,"time":0.0})
        play_sound("skill")
    event("skill_cast",{"skill":title,"mp":player.mp,"hp":player.hp,"slot":cast.slot,"behavior":kind,"classification":profile.get("classification","")})

func interact(required_id: String=""):
    for portal in maps[player.map].portals:
        if portal.get("trigger","walk")=="interact" and Vector2i(portal.x,portal.y)==cell():
            transition(portal.target,portal.entry);return
    var nearby = maps[player.map].npcs.duplicate()
    var facing = cell() + DIRECTIONS[int(player.direction)]
    nearby.sort_custom(func(a,b):
        var a_cost = -1.0 if Vector2i(a.x,a.y)==facing else Vector2i(a.x,a.y).distance_to(cell())
        var b_cost = -1.0 if Vector2i(b.x,b.y)==facing else Vector2i(b.x,b.y).distance_to(cell())
        return a_cost < b_cost)
    for n in nearby:
        if required_id!="" and n.id!=required_id:continue
        if Vector2i(n.x,n.y).distance_to(cell()) <= 1.5:
            npc = n
            selected = 0
            rules.actions.quest_event(player,"talk",n.get("definition_id",n.id))
            if n.role=="work_services":
                menu="services";choices=n.get("services",[]).duplicate(true)
                for node in n.get("dialogue",[]):
                    if typeof(node)!=TYPE_DICTIONARY:continue
                    for choice in node.get("choices",[]):
                        var index=int(choice.get("service_index",-1))
                        if index>=0 and index<choices.size():choices[index].name=choice.get("label","서비스")
                if choices.is_empty():
                    menu="dialogue";choices=n.get("dialogue",[]).map(func(node):return node.get("text","") if typeof(node)==TYPE_DICTIONARY else str(node))
                event("npc_dialogue",{"id":n.id,"definition_id":n.get("definition_id",""),"role":n.role})
                return
            if n.role in ["shop","inn"]:
                menu = "shop"
                choices = n.get("shop_items",world.shop_items).duplicate()
                choices.append_array(["초보 회복약","초보 마력약","구운토끼고기"])
            elif n.role == "trainer":
                menu = "trainer"
                choices = []
                for c in rules.contents:
                    if c.category == "spell" and str(c.job) == player.job and c.values.get("learn_level") != null and float(c.values.learn_level) <= 99:
                        choices.append(c.name)
                choices.sort_custom(func(a,b):return int(rules.skill(player,a).learn_level) < int(rules.skill(player,b).learn_level))
            elif n.role == "travel":
                menu="travel"
                choices=n.destinations.duplicate()
                notice("길잡이가 지역 이동을 돕습니다. ↑↓ 선택, Enter 이동")
            elif n.role == "quest":
                for quest in world.generated_quests:
                    if int(player.kills) >= int(quest.kills) and quest.id not in player.quests:
                        var result=rules.actions.legacy_quest(player,quest)
                        if not result.ok:continue
                        var gains=result.levels
                        event("quest_completed",{"id":quest.id,"xp":quest.xp,"levels":gains})
                        notice("사냥 의뢰 완료! 경험치 %d, 금전 %d" % [quest.xp,quest.gold])
                        return
                menu = "dialogue"
                choices = ["5마리와 25마리 사냥 의뢰를 맡깁니다.","남쪽 사냥터 → 쥐굴 → 숲 → 깊은 동굴 → 폐허", "레벨 5부터 직업별 성장이 적용됩니다."]
            elif n.role == "revive":
                rules.actions.recovery(player,player.hp_max,player.mp_max)
                event("revived")
                notice("성황이 체력과 마력을 회복해 주었습니다.")
            event("npc_dialogue",{"id":n.id,"role":n.role})
            return
    for portal in maps[player.map].portals:
        if portal.get("trigger","walk")=="interact" and Vector2i(portal.x,portal.y).distance_to(cell())<=1.5:
            transition(portal.target,portal.entry);return
    pickup()

func open_inventory():
    clear_inputs()
    menu = "inventory"
    selected = 0
    choices = player.inventory.keys().filter(func(k):return int(player.inventory[k]) > 0)

func handle_menu_key(key: int):
    if menu=="experience_exchange" and key in [KEY_ENTER,KEY_F] and not choices.is_empty():
        var result=rules.actions.experience_exchange(player,service_definition,selected)
        event("experience_exchange",{"option":selected,"result":result});notice("경험치를 능력치로 교환했습니다." if result.ok else result.error);return
    if menu=="recipe" and key in [KEY_ENTER,KEY_F] and not choices.is_empty():
        var id=str(choices[selected]);var result=rules.actions.recipe(player,content.definition(id))
        event("recipe",{"id":id,"result":result});notice("제작 완료" if result.ok and result.get("success",false) else result.get("error","제작 실패"));return
    if menu=="services" and key in [KEY_ENTER,KEY_F] and not choices.is_empty():
        work_service(choices[selected]);return
    if menu=="quests" and key in [KEY_ENTER,KEY_F] and not choices.is_empty():
        var id=str(choices[selected]);var progress=player.quest_progress.get(id,{})
        var result=rules.actions.claim_quest(player,id) if progress.get("state","")=="ACTIVE" else rules.actions.accept_quest(player,id,content.definition(id))
        event("work_quest",{"id":id,"result":result});notice("의뢰 상태를 처리했습니다." if result.ok else "의뢰 조건: "+result.error);return
    if menu=="advancement" and key in [KEY_ENTER,KEY_F] and not choices.is_empty():
        var id=str(choices[selected]);var definition=content.definition(id).duplicate(true)
        definition.job=content.class_title(definition.get("class_id",player.job),rules)
        var result=rules.actions.advance(player,id,definition)
        event("work_advancement",{"id":id,"result":result});notice("승급: "+definition.get("name",id) if result.ok else "승급 조건: "+result.error);return
    if menu=="equipment" and key in [KEY_E,KEY_ENTER,KEY_X,KEY_N] and not choices.is_empty():
        var id=str(choices[selected]);var gear=player.equipment_instances[id]
        if key==KEY_X:
            for slot in player.equipment_slots.keys():
                if player.equipment_slots[slot]==id:rules.actions.unequip(player,slot)
        elif key==KEY_N:
            player.extensions["optional_enhancement"]=true
            event("extension_opt_in",{"extension":"optional_enhancement","original_rule":false})
            enhancement_instance=id;menu="enhancement";selected=0
            choices=content.by_kind("enhancement").filter(func(rule):return gear.definition_id in content.definition(rule).get("applicable_item_ids",[]))
            if choices.is_empty():notice("이 장비에 전달된 강화 규칙이 없습니다.")
        else:
            var result=rules.actions.equip_instance(player,id)
            event("equipment_instance_selected",{"instance_id":id,"result":result})
        return
    if menu=="enhancement" and key in [KEY_ENTER,KEY_N] and not choices.is_empty():
        var id=str(choices[selected]);var definition=content.definition(id).duplicate(true);definition.id=id
        var result=rules.actions.enhance(player,enhancement_instance,definition)
        event("work_enhancement",{"rule_id":id,"instance_id":enhancement_instance,"result":result})
        notice("강화 결과: "+result.get("outcome","") if result.ok else "강화 조건: "+result.error);return
    if menu=="compass" and key in [KEY_ENTER,KEY_F]:
        var town=maps.village
        var desired=[Vector2i(int(town.width)-3,int(town.height)/2),Vector2i(2,int(town.height)/2),Vector2i(int(town.width)/2,int(town.height)-3),Vector2i(int(town.width)/2,2)][selected]
        var candidate=Vector2i(town.entry[0],town.entry[1]);var best=99999
        for y in range(int(town.height)):
            for x in range(int(town.width)):
                if free_cell("village",Vector2i(x,y)):
                    var distance=absi(x-desired.x)+absi(y-desired.y)
                    if distance<best:best=distance;candidate=Vector2i(x,y)
        menu="";transition("village",[candidate.x,candidate.y]);return
    if menu=="travel" and key in [KEY_ENTER,KEY_F] and not choices.is_empty():
        var destination=str(choices[selected])
        menu=""
        transition(destination,maps[destination].entry)
        event("guide_travel",{"destination":destination,"classification":"SINGLEPLAYER_COMPLETION"})
        return
    if menu == "pause":
        if key == KEY_ENTER:
            menu = ""
        elif key == KEY_Q:
            if continuity!=null:continuity.save_and_exit()
            else:get_tree().quit()
        return
    if choices.size() > 0:
        if key == KEY_UP:
            selected = (selected-1+choices.size())%choices.size()
        elif key == KEY_DOWN:
            selected = (selected+1)%choices.size()
    if menu == "shop" and choices.size() > 0:
        var title = str(choices[selected])
        if key in [KEY_ENTER,KEY_B,KEY_V]:
            var buy = key != KEY_V
            var price = int(rules.value_or(rules.item(title),"vendor_buy_price" if buy else "vendor_sell_price",5 if buy else 1))
            for offer in npc.get("work_offers",[]):
                if offer.get("item_id","")==title:
                    if buy and int(player.level)<int(offer.get("requirements",{}).get("min_level",0)):notice("구매 레벨 조건을 충족하지 못했습니다.");return
                    price=int(offer.get("price_gold",offer.get("buy_price",offer.get("price",price)))) if buy else int(offer.get("sell_price",price))
            if not buy and rules.item(title).get("flags",{}).get("quest_bound",false):notice("의뢰 전용 물품은 판매할 수 없습니다.");return
            var success = rules.trade(player,title,1,price,buy)
            notice(("구매: " if buy else "판매: ")+title if success else "금전·수량·가방 조건을 확인하세요.")
            event("trade",{"item":title,"buy":buy,"success":success,"gold":player.gold})
        elif key == KEY_R:
            var success = rules.repair(player,player.equipped)
            notice("수리 완료" if success else "수리할 장착 무기 또는 금전이 없습니다.")
            event("repair",{"success":success})
        elif key == KEY_C:
            var success = rules.craft(player,{"토끼고기":1},1,"구운토끼고기")
            notice("토끼고기 요리 완료" if success else "토끼고기 1개와 금전 1전이 필요합니다.")
            event("crafted",{"success":success})
        elif key == KEY_H and npc.role == "inn":
            if rules.actions.rest(player,5).ok:
                notice("주막에서 쉬었습니다.")
                event("rested")
    elif menu == "inventory" and choices.size() > 0:
        var title = str(choices[selected])
        if key in [KEY_E,KEY_ENTER]:
            var success = rules.equip(player,title)
            notice(title+" 장착" if success else "착용 조건 또는 무기 종류를 확인하세요.")
            event("equipped",{"item":title,"success":success})
        elif key == KEY_U:
            if rules.item(title).get("teleport_safe_return",false):
                var result=rules.actions.use_return_item(player,title,world.home)
                if result.ok:menu="";transition(world.home.map,world.home.entry)
                event("return_item",{"id":title,"result":result});return
            var success = rules.consume(player,title)
            notice(title+" 사용" if success else "사용할 수 없는 물품입니다.")
            event("consumed",{"item":title,"success":success})
    elif menu == "trainer" and choices.size() > 0 and key in [KEY_ENTER,KEY_L]:
        var title = str(choices[selected])
        var success = rules.learn(player,title)
        event("skill_learned",{"skill":title,"success":success})
        notice(title+" 습득" if success else "레벨·금전·제물을 확인하세요.")
    elif menu in ["trainer","skills"] and key in [KEY_1,KEY_2,KEY_3] and choices.size() > 0:
        var title = str(choices[selected])
        if title in player.skills:
            player.hotbar[key-KEY_1] = title
            event("hotbar_assigned",{"skill":title,"slot":key-KEY_1})

func play_sound(kind: String):
    var path = assets.folder.path_join(assets.actor_data.sound_bindings[kind])
    var stream = AudioStreamWAV.load_from_file(path)
    if stream != null:
        var voice = audio_voices[kind]
        voice.stream = stream
        voice.play()
        audio_events.append({"time":clock,"kind":kind,"voice":kind,"playing":voice.is_playing(),"file_sha256":FileAccess.get_sha256(path)})

func play_work_sound(id: String):
    var path=work_assets.file_path(id)
    if path=="":event("sound_error",{"code":"SOUND_NOT_ACQUIRED","id":id});return
    var stream=AudioStreamWAV.load_from_file(path)
    if stream==null:event("sound_error",{"code":"SOUND_DECODE","id":id});return
    audio_voices.skill.stream=stream;audio_voices.skill.play()
    audio_events.append({"time":clock,"kind":"work_skill","asset_id":id,"playing":audio_voices.skill.is_playing(),"file_sha256":content.assets[id].sha256})

func snapshot() -> Dictionary:
    player.rng_state = str(rules.rng.state)
    return {"player":player.duplicate(true),"world":entities.duplicate(true),"loot":loot.duplicate(true),
            "rng_state":str(rules.rng.state),"content_version":content.version,"game_build":store.game_build,"save_format_version":Store.VERSION}

func restore(state: Dictionary):
    clear_inputs()
    var fresh_entities=entities.duplicate(true)
    player = state.player
    rules.actions.ensure(player)
    if not player.has("visited"):player.visited=[player.map,"village"]
    entities = state.world
    if player.get("world_revision","authored-1")!=world.get("revision","authored-1"):
        # Preserve progress/inventory/loot; migrate only changed layout positions.
        # Store.read_state does not write the user's original file during loading.
        for id in entities:
            if fresh_entities.has(id):
                var old=entities[id]
                var replacement=fresh_entities[id]
                for field in ["alive","hp","respawn","provoked","hurt","attack_timer","move_timer"]:
                    replacement[field]=old.get(field,replacement[field])
                fresh_entities[id]=replacement
        entities=fresh_entities
        if not maps.has(player.map):player.map=world.get("home",{"map":"village"}).map
        var entry=maps[player.map].entry
        player.x=int(entry[0]);player.y=int(entry[1])
        for drop in state.get("loot",[]):
            if maps.has(drop.map):
                var at=maps[drop.map].entry
                drop.x=int(at[0]);drop.y=int(at[1])
        player.world_revision=world.get("revision","authored-1")
        event("layout_migrated",{"revision":player.world_revision,"progress_preserved":true})
    for id in fresh_entities:
        if not entities.has(id):entities[id]=fresh_entities[id]
    # Migrate our earlier generated spawn layout that overlapped a doorway.
    for id in entities:
        var e=entities[id]
        if fresh_entities.has(id):
            # A saved instance keeps its progress, never an obsolete copy of
            # the monster definition after a guarded content update.
            var current_definition=fresh_entities[id]
            for field in ["kind","spec","hp_max","mp_max"]:e[field]=current_definition[field]
            e.hp=clampi(int(e.hp),0,int(e.hp_max))
            e.mp=clampi(int(e.get("mp",0)),0,int(e.mp_max))
        if not maps.has(e.map):e.retired=true;continue
        for portal in maps[e.map].portals:
            if Vector2i(e.home_x,e.home_y)==Vector2i(portal.x,portal.y):e.home_y+=2
            if Vector2i(e.x,e.y)==Vector2i(portal.x,portal.y):e.y+=2
    loot = state.get("loot",[])
    if not maps.has(player.map):
        var home=world.get("home",{"map":"village","entry":maps.village.entry})
        player.map=home.map;player.x=home.entry[0];player.y=home.entry[1]
        event("safe_position_restored",{"reason":"MAP_UNAVAILABLE","progress_preserved":true})
    var current=maps[player.map]
    if player.x<0 or player.y<0 or player.x>=int(current.width) or player.y>=int(current.height) or current.blocked[int(player.y)][int(player.x)]:
        player.x=int(current.entry[0]);player.y=int(current.entry[1])
        event("safe_position_restored",{"reason":"MAP_BOUNDS_OR_COLLISION_CHANGED","progress_preserved":true})
    rules.rng.state = int(state.rng_state)
    step_progress = 1.0
    selected_target = ""
    attack_elapsed = -1.0
    cast_elapsed=-1.0;pending_spell={}
    if player.has("summoned_guide") and maps.has(player.summoned_guide.map):
        var guide=player.summoned_guide
        var m=maps[guide.map]
        m.npcs=m.npcs.filter(func(n):return n.id!="summoned-guide")
        m.npcs.append(guide)
    menu = ""
    event("save_restored",{"map":player.map,"level":player.level,"equipped":player.equipped})
    reset_motion()

func save_game() -> bool:
    if player.is_empty():return false
    if attack_elapsed>=0 or cast_elapsed>=0:
        save_queued=true
        notice("동작이 끝나면 저장합니다.")
        event("save_queued_until_action_resolves")
        return false
    if continuity!=null and not continuity.before_local_save():return false
    var success = store.write_state(save_path,snapshot())
    notice("저장 완료 · 재실행하면 이어집니다." if success else "저장 실패: 저장 폴더를 확인하세요.")
    event("save_written",{"success":success,"sha256":FileAccess.get_sha256(save_path) if success else ""})
    return success

func write_diagnostic(code: String):
    var path=save_path.get_base_dir().path_join("diagnostics/latest.json")
    DirAccess.make_dir_recursive_absolute(path.get_base_dir())
    var f=FileAccess.open(path,FileAccess.WRITE)
    if f==null:return
    var sorted=frame_times.duplicate();sorted.sort()
    var total=0.0;var over50=0;var over100=0
    for ms in sorted:total+=ms;over50+=int(ms>50);over100+=int(ms>100)
    var performance={"samples":sorted.size(),"mean_ms":total/maxi(1,sorted.size()),"over_50_ms":over50,"over_100_ms":over100,"p99_ms":sorted[int(sorted.size()*.99)] if not sorted.is_empty() else 0}
    # One bounded local file; no full user save or secret is uploaded/packaged.
    f.store_string(JSON.stringify({"code":code,"build":store.game_build,"content_version":content.version,
        "frame_performance":performance,"position":[player.get("x",0),player.get("y",0)],"menu":menu,"direction":player.get("direction",2),"navigation_generation":navigation.generation if navigation!=null else 0,"navigation_path":navigation.path if navigation!=null else [],"camera":[camera().x,camera().y],"viewport":[get_viewport_rect().size.x,get_viewport_rect().size.y],"map_id":player.get("map",""),"rng_state":str(rules.rng.state),"recent_events":event_log.slice(maxi(0,event_log.size()-32)),
        "rules_error":rules.actions.last_error,"save_error":store.last_error},"  "))
    f.close();print("BARAM_DIAGNOSTIC "+JSON.stringify({"build":store.game_build,"frame_performance":performance,"map":player.get("map",""),"position":[player.get("x",0),player.get("y",0)],"menu":menu}))
    notice("오류 재현 기록을 개인 저장 폴더에 남겼습니다.")

func label(text: String, pos: Vector2, size: int = 16, color: Color = Color(0.91,0.86,0.7)):
    draw_string(font,pos,text,HORIZONTAL_ALIGNMENT_LEFT,-1,size,color)

func box(rect: Rect2, color: Color = Color(0.13,0.12,0.1)):
    draw_rect(rect,color)
    if assets.textures.has("ui_border"):
        var side=16.0
        var xx=[rect.position.x,rect.position.x+side,rect.end.x-side]
        var yy=[rect.position.y,rect.position.y+side,rect.end.y-side]
        var ww=[side,maxf(0,rect.size.x-side*2),side]
        var hh=[side,maxf(0,rect.size.y-side*2),side]
        for y in range(3):
            for x in range(3):
                if x==1 and y==1:continue
                draw_texture_rect_region(assets.textures.ui_border,Rect2(xx[x],yy[y],ww[x],hh[y]),assets.actor_region("ui_border",[[0,1,2],[3,8,4],[5,6,7]][y][x]))
        return
    draw_rect(rect,Color(0.52,0.43,0.28),false,2)
    draw_rect(rect.grow(-4),Color(0.29,0.26,0.18),false,1)

func draw_actor(key: String, frame: int, feet: Vector2, opacity: float = 1.0):
    if content.records.has(key) and content.records[key].kind=="asset":
        var meta=content.definition(key).get("metadata",{})
        work_assets.draw_frame(self,key,int(meta.get("starting_frame",0))+frame,feet,opacity)
        return
    var texture = assets.textures.get(key)
    if texture == null:
        return
    var region = assets.actor_region(key,frame)
    if region.size == Vector2.ZERO:
        return
    var spec=assets.actor_data[key]
    draw_texture_rect_region(texture,Rect2(feet-Vector2(spec.origin[0],spec.origin[1])*2,Vector2(spec.canvas[0],spec.canvas[1])*2),region,Color(1,1,1,opacity))

func icon(title: String, at: Vector2):
    var data=rules.runtime_definitions.get(rules.find_content("item",title).get("id",title),{}).get("data",{})
    var visual=data.get("visual",{})
    if visual.has("icon_id"):
        var texture=work_assets.icon(visual.icon_id,int(visual.get("icon_frame",0)))
        if texture!=null:
            var size=texture.get_size()*minf(2,48.0/maxi(texture.get_width(),texture.get_height()))
            draw_texture_rect(texture,Rect2(at-size/2,size),false);return
    var names = assets.actor_data.icons.names
    var index = names.find(title)
    if index < 0:
        index = names.find("토끼고기") if title == "구운토끼고기" else names.find("산삼") if title.ends_with("약") else 0
    var spec=assets.actor_data.icons
    var f=spec.frames[index]
    var r=assets.actor_region("icons",index)
    # Item EPF pivots are positive; icons center their actual opaque rectangle.
    var crop=Rect2(r.position+Vector2(spec.origin[0]+f.left,spec.origin[1]+f.top),Vector2(f.width,f.height))
    var size=Vector2(f.width,f.height)*2
    draw_texture_rect_region(assets.textures.icons,Rect2(at-size/2,crop.size*2),crop)

func _draw():
    if not startup_ready:return
    if assets.tiles.is_empty() or font.data.is_empty():
        return
    work_assets.begin_frame()
    draw_rect(Rect2(Vector2.ZERO,get_viewport_rect().size),Color(0.055,0.065,0.055))
    var map_id = "village" if player.is_empty() else player.map
    var m = maps[map_id]
    var cam = camera()
    var field=field_rect();var span=field.size/STEP
    for y in range(int(cam.y),mini(int(m.height),ceili(cam.y+span.y)+1)):
        for x in range(int(cam.x),mini(int(m.width),ceili(cam.x+span.x)+1)):
            var tile = str(m.ground[y][x])
            var texture=tile_texture(tile)
            if texture!=null:draw_texture_rect(texture,Rect2(field.position+(Vector2(x,y)-cam)*STEP,Vector2(STEP,STEP)),false)
    for portal in m.portals:
        if Rect2(cam,span+Vector2.ONE).has_point(Vector2(portal.x,portal.y)):
            var p = screen_point(portal.x,portal.y)
            draw_rect(Rect2(p-Vector2(22,44),Vector2(44,42)),Color(0.8,0.7,0.3,0.3))
            if not player.is_empty() and Vector2i(portal.x,portal.y).distance_to(cell())<2:label(portal.label,p-Vector2(38,5),12,Color(1,0.95,0.5))
    for drop in loot:
        if drop.map == map_id and Rect2(cam,span+Vector2.ONE).has_point(Vector2(drop.x,drop.y)):
            icon(drop.item,screen_point(drop.x,drop.y))
    for fx in effects:
        if fx.has("work_asset"):work_assets.draw_effect(self,fx.work_asset,"back",int(fx.time*1000),screen_point(fx.x,fx.y),int(fx.lifetime_ms))
    var visible = []
    for row in range(int(cam.y),mini(int(m.height),ceili(cam.y+span.y)+1)):
        for d in decoration_rows.get(map_id,{}).get(row,[]):
            if Rect2(cam,span+Vector2.ONE).has_point(Vector2(d.x,d.y)):
                visible.append({"type":"decoration","y":d.get("anchor_y",d.y),"data":d})
    for n in m.npcs:
        visible.append({"type":"npc","y":n.y,"data":n})
    for id in entities:
        var e = entities[id]
        if e.map == map_id and e.alive:
            visible.append({"type":"monster","y":e.y,"data":e})
    if not player.is_empty():
        visible.append({"type":"player","y":player.y,"data":player})
    visible.sort_custom(func(a,b):return a.y < b.y)
    for v in visible:
        var e = v.data
        if v.type=="decoration":
            var texture=tile_texture(e.tile)
            if texture!=null:draw_texture_rect(texture,Rect2(field.position+(Vector2(e.x,e.y)-cam)*STEP,Vector2(STEP,STEP)),false)
            continue
        if not Rect2(cam-Vector2(1,1),span+Vector2(2,2)).has_point(Vector2(e.x,e.y)):
            continue
        var pos = screen_point(e.x,e.y)
        if v.type == "player":
            if step_progress < 1:
                pos = screen_point(lerpf(from_position.x,float(player.x),step_progress),lerpf(from_position.y,float(player.y),step_progress))
            draw_player(pos)
            label(player.name,pos-Vector2(34,93),13,Color(1,0.95,0.75))
        else:
            var key = visual_key(str(e.kind))
            var spec = assets.actor_data.get(key,{"walk":3,"attack":2,"delay_ms":100})
            var direction = Facing.sprite(int(e.get("direction",2)))
            var frame = direction*int(spec.walk)+int(clock*6)%int(spec.walk)
            if v.type=="monster" and float(e.get("attack_elapsed",-1))>=0 and int(spec.attack)>0:
                frame=4*int(spec.walk)+direction*int(spec.attack)+mini(int(spec.attack)-1,int(float(e.attack_elapsed)*1000/maxi(1,int(spec.delay_ms))))
            var opacity = 0.7 if float(e.get("hurt",0)) > 0 else 1.0
            if content.records.has(key):
                var attacking=float(e.get("attack_elapsed",-1))>=0
                work_assets.draw_animation(self,key,"attack" if attacking else "walk",int(e.get("direction",2)),int((e.attack_elapsed if attacking else clock)*1000),pos,opacity)
            else:draw_actor(key,frame,pos,opacity)
            var title = e.name if v.type == "npc" else e.spec.name
            label(title,pos-Vector2(28,90),13,Color(0.9,0.9,0.65))
            if v.type == "monster" and (e.provoked or selected_target == e.id):
                draw_rect(Rect2(pos-Vector2(16,85),Vector2(32,3)),Color(0.15,0.1,0.1))
                draw_rect(Rect2(pos-Vector2(16,85),Vector2(32*maxf(0,float(e.hp)/float(e.spec.values.hp)),3)),Color(0.75,0.25,0.15))
    for fx in effects:
        if fx.has("work_asset"):
            work_assets.draw_effect(self,fx.work_asset,"front",int(fx.time*1000),screen_point(fx.x,fx.y),int(fx.lifetime_ms))
            continue
        var spec=assets.actor_data.get(fx.key,{})
        var durations=spec.get("delays_ms",[])
        var elapsed=fx.time*1000;var frame=0
        if durations.is_empty():frame=mini(7,int(fx.time*10))
        else:
            while frame<durations.size()-1 and elapsed>=float(durations[frame]):elapsed-=float(durations[frame]);frame+=1
        draw_actor(fx.key,frame,screen_point(fx.x,fx.y))
    for t in floating_text:
        label(t.text,screen_point(t.x,t.y)-Vector2(8,90+t.time*35),18,t.color)
    if m.kind=="dungeon" and not player.is_empty():
        var lit=player.buffs.get("누리의빛",0)>0 or player.buffs.get("대지의빛",0)>0 or player.buffs.get("바다의 빛",0)>0
        var radius=8.0 if lit else 3.0
        for y in range(ceili(span.y)):
            for x in range(ceili(span.x)):
                if (Vector2(x,y)+cam-Vector2(player.x,player.y)).length()>radius:
                    draw_rect(Rect2(field.position+Vector2(x,y)*STEP,Vector2(STEP,STEP)),Color(0,0,0,0.30))
    if navigation!=null and navigation.marker.x>=0:
        var mark=screen_point(navigation.marker.x,navigation.marker.y)-Vector2(0,STEP/2)
        draw_arc(mark,13,0,TAU,24,Color(1,.35,.3,.8) if navigation.marker_failed else Color(.95,.84,.45,.85),2)
    if mobile:
        if menu=="creation":
            box(Rect2(238,152,484,314),Color(.12,.14,.12));label("새로운 여정",Vector2(395,196),25)
            label("이름",Vector2(299,268),18)
        return
    box(Rect2(0,0,960,48))
    label("바람의나라",Vector2(18,32),23,Color(0.96,0.82,0.43))
    label(m.name,Vector2(212,31),17)
    label("개인용 · 오프라인",Vector2(790,30),15)
    box(Rect2(768,48,192,480))
    box(Rect2(0,528,960,112))
    if not player.is_empty():
        draw_hud()
    for i in range(log_lines.size()):
        label(log_lines[i],Vector2(16,552+i*20),14)
    if menu == "creation":
        box(Rect2(238,152,484,314),Color(0.12,0.14,0.12))
        label("새로운 여정",Vector2(395,196),25,Color(1,0.86,0.47))
        label("이름",Vector2(299,268),18)
        label("선택 직업: "+Rules.JOBS[creation_job],Vector2(393,370),16)
        label("레벨 5까지 평민 성장 · 이후 선택 직업 성장",Vector2(267,448),16)
    elif menu != "":
        draw_menu()

func draw_player(pos: Vector2):
    var job = Rules.JOBS.find(player.job)
    if int(player.hp) == 0:
        draw_actor("ghost",Facing.sprite(int(player.direction))*3+int(clock*6)%3,pos)
        return
    var direction = int(player.direction)
    for status in player.statuses.values():
        var replacement=status.get("visual",{}).get("replacement_actor","")
        if replacement!="":
            var spec=assets.actor_data.get(replacement,{})
            if not spec.is_empty():draw_actor(replacement,Facing.sprite(direction)*int(spec.walk)+int(clock*6)%int(spec.walk),pos);return
    if draw_work_player(pos,direction):return
    direction=Facing.sprite(direction)
    if player.buffs.get("금수",0)>0:
        var spec=assets.actor_data.rabbit
        draw_actor("rabbit",direction*int(spec.walk)+int(clock*6)%int(spec.walk),pos)
        return
    if player.buffs.get("경수",0)>0:
        var spec=assets.actor_data.innkeeper
        draw_actor("innkeeper",direction*int(spec.walk)+int(clock*6)%int(spec.walk),pos)
        return
    var binding=rules.visual_bindings.get(player.equipped,assets.actor_data.get("equipment_bindings",{}).get(player.equipped,{"sprite":"wood_weapon","motion":"sword"}))
    var motion=assets.actor_data.get("motion_bindings",{})
    var body_frame = direction*3+(int(walk_clock*10)%3 if step_progress < 1 else 1)
    var weapon_frame = body_frame
    if player.equipped != "": body_frame += int(motion.get("walk_"+str(binding.motion),12))
    if attack_elapsed >= 0:
        body_frame = int(motion.get("attack_"+str(binding.motion),24))+direction*2+mini(1,int(attack_elapsed*5))
        weapon_frame = 12+direction*2+mini(1,int(attack_elapsed*5))
    elif cast_elapsed>=0:body_frame=int(motion.get("cast",72))+direction
    elif pickup_elapsed>=0:body_frame=int(motion.get("pickup",76))+direction
    var order = str(assets.actor_data.draw_order[body_frame])
    var opacity = 0.72 if hurt_time > 0 else 1.0
    if player.buffs.get("무영보법",0)>0:opacity*=0.35
    var body_key="body_"+str(job)
    var worn=rules.visual_bindings.get(player.get("armor_equipped",""),assets.actor_data.get("equipment_bindings",{}).get(player.get("armor_equipped",""),{}))
    if worn.has("sprites"):body_key=worn.sprites[job]
    elif worn.has("sprite"):body_key=worn.sprite
    for layer in order:
        if layer == "b":
            draw_actor(body_key,body_frame,pos,opacity)
        elif layer == "h":
            draw_actor("head_"+str(job),mini(body_frame,99),pos,opacity)
        elif layer == "w" and player.equipped != "":
            draw_actor(binding.sprite,weapon_frame,pos,opacity)

func draw_hud():
    label(player.name,Vector2(784,78),18,Color(1,0.91,0.66))
    label("%s  레벨 %d" % [player.job,player.level],Vector2(784,103),17)
    label("체력 %d / %d" % [player.hp,player.hp_max],Vector2(784,134),14)
    draw_rect(Rect2(784,143,158,12),Color(0.2,0.08,0.06))
    draw_rect(Rect2(784,143,158*float(player.hp)/float(player.hp_max),12),Color(0.65,0.16,0.1))
    if assets.textures.has("ui_bars"):
        var r=assets.actor_region("ui_bars",0)
        r.size.x*=float(player.hp)/float(player.hp_max)
        if r.size.x>0:draw_texture_rect_region(assets.textures.ui_bars,Rect2(784,143,158*float(player.hp)/float(player.hp_max),12),r)
    label("마력 %d / %d" % [player.mp,player.mp_max],Vector2(784,179),14)
    draw_rect(Rect2(784,188,158,12),Color(0.07,0.1,0.22))
    draw_rect(Rect2(784,188,158*float(player.mp)/float(player.mp_max),12),Color(0.18,0.33,0.7))
    if assets.textures.has("ui_bars"):
        var r=assets.actor_region("ui_bars",1)
        r.size.x*=float(player.mp)/float(player.mp_max)
        if r.size.x>0:draw_texture_rect_region(assets.textures.ui_bars,Rect2(784,188,158*float(player.mp)/float(player.mp_max),12),r)
    label("경험치 %s" % str(float(player.xp2)/2.0),Vector2(784,224),14)
    label("금전 %d전" % player.gold,Vector2(784,248),15)
    label("힘 %d · 사냥 %d" % [player.strength,player.kills],Vector2(784,273),14)
    label("무기: "+(rules.display_name(player.equipped) if player.equipped!="" else "맨손"),Vector2(784,302),15)
    if player.equipped != "":
        label("내구 %d" % int(player.durability[player.equipped]),Vector2(784,325),13)
    if player.get("armor_equipped","")!="":label("옷: "+rules.display_name(player.armor_equipped),Vector2(784,342),11)
    for i in range(3):
        box(Rect2(782,346+i*39,166,34))
        label(str(i+1)+"  "+rules.display_name(str(player.hotbar[i])),Vector2(790,368+i*39),13)
    label("화살표  이동",Vector2(784,478),13)
    label("Space  공격 / G  줍기",Vector2(784,500),12)
    label("Enter 대화 · I 물품 · F5 저장",Vector2(668,631),12)

func draw_menu():
    box(Rect2(164,106,536,398),Color(0.12,0.13,0.11))
    var heading = {"shop":"물품 거래","trainer":"기술 수련","inventory":"보유 물품","dialogue":"안내","pause":"여정 저장","travel":"길 안내","map":"지역 목록","compass":"비영사천문","skills":"배운 기술","equipment":"개별 장비 · E 장착 / X 해제 / N 강화","enhancement":"개인용 확장 강화 규칙","services":"NPC 서비스","quests":"의뢰 시작 · 조건 완료 후 보상","advancement":"승급 조건 확인","save_error":"저장 오류 · 원본 보존 · Q 종료"}.get(menu,menu)
    label(heading,Vector2(191,144),22,Color(1,0.88,0.5))
    if menu == "pause":
        label("Enter: 계속하기 · Q: 게임 종료",Vector2(194,205),18)
        return
    var start = maxi(0,selected-4)
    for j in range(start,mini(choices.size(),start+8)):
        var y = 184+(j-start)*31
        var id=str(choices[j])
        if menu in ["shop","inventory"] and rules.runtime_definitions.has("wk.class.novice"):id=rules.find_content("item",id).get("id",id)
        var title = rules.display_name(id)
        if menu=="services":title=choices[j].get("name",{"shop":"물품 거래","learn_skills":"기술 수련","quests":"의뢰 접수와 보상","experience_exchange":"99레벨 경험치 교환","recipe_book":"재료 제작","repair":"장비 수리","rest":"주막에서 쉬기","revive":"성황에게 부활"}.get(choices[j].get("type",""),"서비스"))
        if menu=="equipment":
            var gear=player.equipment_instances[choices[j]]
            title=rules.display_name(gear.definition_id)+" +"+str(int(gear.enhancement_level))+" ("+str(gear.id).trim_prefix("gear.instance.")+")"
        if menu=="travel":title=maps[world.get("map_aliases",{}).get(id,id)].name
        if menu=="quests":title+=" · "+{"ACTIVE":"진행 중","CLAIMED":"보상 받음"}.get(player.quest_progress.get(id,{}).get("state",""),"접수 가능")
        if j == selected:
            draw_rect(Rect2(184,y-21,496,29),Color(0.32,0.29,0.16))
        label(title,Vector2(198,y),15)
        if menu == "shop":
            icon(id,Vector2(445,y-8))
            label("%d전  보유 %d" % [int(rules.value_or(rules.item(id),"vendor_buy_price",5)),int(player.inventory.get(id,0))],Vector2(478,y),14)
        elif menu == "inventory":
            icon(id,Vector2(559,y-8))
            label("%d개" % int(player.inventory[id]),Vector2(596,y),14)
        elif menu == "trainer":
            var s = rules.skill(player,id)
            var cost="미확정" if s.get("learn_money")==null else str(int(s.learn_money))+"전"
            label("Lv.%d / %s %s" % [int(s.learn_level),cost,"습득" if id in player.skills else ""],Vector2(467,y),13)
    var hint = {"shop":"↑↓ 선택 · B 구매 · V 판매 · R 수리 · C 요리 · Esc 닫기",
        "inventory":"↑↓ 선택 · E 장착 · U 사용 · Esc 닫기",
        "trainer":"Enter 습득 · 1~3 단축키 지정 · Esc 닫기",
        "dialogue":"Esc 닫기","skills":"↑↓ 선택 · 1~3 단축키 지정 · Esc 닫기","travel":"↑↓ 선택 · Enter 이동 · Esc 닫기"}.get(menu,"")
    label(hint,Vector2(190,485),13)
    if menu=="services" and not npc.get("dialogue",[]).is_empty():
        draw_multiline_string(font,Vector2(194,439),npc.dialogue[0].get("text",""),HORIZONTAL_ALIGNMENT_LEFT,470,12,2,Color(0.9,0.87,0.7))
    if menu=="inventory" and not choices.is_empty():
        var it=rules.item(str(choices[selected]))
        label("공격 %d~%d · 방어 %d · 필요 힘 %d" % [int(rules.value_or(it,"damage_min",0)),int(rules.value_or(it,"damage_max",0)),int(rules.value_or(it,"armor_class",0)),int(rules.value_or(it,"strength_required",0))],Vector2(194,459),13)

func start_exercise():
    # Implemented in a separate script so validation calls the actual event handlers.
    var script="res://quality_probe.gd" if test_mode.begins_with("quality-") else "res://mobile_smoke_probe.gd" if test_mode.begins_with("mobile-") else "res://native_regression.gd" if test_mode.begins_with("native-") else "res://work_play_probe.gd" if test_mode.begins_with("work-") else "res://exercise.gd"
    var runner = load(script).new()
    add_child(runner)
    await runner.run(self,test_mode,test_root)

func visual_key(id: String) -> String:
    var definition=rules.runtime_definitions.get(id,{}).get("data",{})
    return definition.get("visual",{}).get("asset_id",definition.get("visual",{}).get("legacy_sprite",id))

func work_service(service):
    if typeof(service)!=TYPE_DICTIONARY:
        notice("서비스 정의가 구조화되지 않았습니다.");event("service_error",{"code":"SERVICE_FORMAT"});return
    var kind=service.get("type","")
    selected=0
    if kind=="shop":
        var shop=content.definition(service.get("shop_id",""))
        if shop.get("currency","gold")!="gold":notice("미지원 통화: "+str(shop.currency));return
        npc.work_offers=shop.get("offers",[]);menu="shop";choices=npc.work_offers.map(func(o):return o.item_id)
    elif kind in ["quest","quests"]:menu="quests";choices=service.get("quest_ids",[]).duplicate()
    elif kind in ["trainer","skill","skills","learn_skills"]:
        menu="trainer";choices=service.get("skill_ids",[]).filter(func(id):return content.definition(id).get("variant",{}).get("role","primary")=="primary")
    elif kind=="experience_exchange":
        menu="experience_exchange";service_definition=content.definition(service.get("economy_id",""));choices=service_definition.get("experience_exchange",{}).get("options",[]).map(func(o):return str(o.stat)+" +"+str(o.amount))
    elif kind=="recipe_book":menu="recipe";choices=service.get("recipe_ids",[service.get("recipe_id","")]).filter(func(id):return id!="")
    elif kind=="repair":
        var values=rules.item(player.equipped)
        var cost=rules.repair_cost(int(rules.value_or(values,"vendor_buy_price",0)),int(rules.value_or(values,"durability",0)),int(player.durability.get(player.equipped,0)),float(service.get("price_multiplier",0.001)))
        var success=cost>=0 and rules.actions.repair(player,player.equipped,cost,int(rules.value_or(values,"durability",0)))
        event("repair",{"success":success,"cost":cost});notice("수리 완료" if success else "수리 조건을 확인하세요.")
    elif kind=="revive":
        var result=Effects.apply(rules.actions,player,[],[{"type":"revive","target":"self","hp_fraction":service.get("hp_fraction",{"numerator":1,"denominator":1}),"mp_fraction":service.get("mp_fraction",{"numerator":1,"denominator":1})}])
        event("work_revive",{"result":result});notice("부활했습니다." if result.ok else "혼령 상태에서 부활할 수 있습니다.")
    elif kind=="advancement":menu="advancement";choices=service.get("advancement_ids",[]).duplicate()
    elif kind in ["travel","teleport"]:menu="travel";choices=service.get("map_ids",[]).duplicate()
    elif kind=="enhancement":menu="equipment";choices=player.equipment_instances.keys().filter(func(id):return not player.equipment_instances[id].destroyed)
    elif kind in ["heal","revive","rest"]:
        var result=rules.actions.rest(player,int(service.get("gold_cost",0)))
        event("work_rest",{"result":result});notice("체력과 마력을 회복했습니다." if result.ok else result.error);menu=""
    elif kind=="dialogue":menu="dialogue";choices=service.get("lines",[]).duplicate()
    else:
        event("service_error",{"code":"UNKNOWN_SERVICE","type":kind,"npc_id":npc.get("definition_id",npc.id)})
        notice("아직 연결되지 않은 서비스: "+kind)

func tile_texture(key: String) -> Texture2D:
    if "#" in key:
        var parts=key.split("#");return work_assets.tile(parts[0],int(parts[1]))
    return assets.tile(key) if assets.tiles.has(key) else null

func draw_work_player(pos: Vector2, direction: int) -> bool:
    var classes=content.by_kind("class").filter(func(id):return content.definition(id).get("name","")==player.job)
    if classes.is_empty():return false
    var visual=content.definition(classes[0]).get("visual",{})
    var body=visual.get("body_asset_id","");var head=visual.get("head_asset_id","")
    var head_instance=player.get("equipment_instances",{}).get(player.get("equipment_slots",{}).get("head",""),{})
    var head_data=rules.runtime_definitions.get(head_instance.get("definition_id",""),{}).get("data",{}).get("visual",{})
    head=head_data.get("equipment_asset_id",head)
    var weapon_data=rules.runtime_definitions.get(rules.find_content("item",player.equipped).get("id",player.equipped),{}).get("data",{}).get("visual",{})
    var body_data=rules.runtime_definitions.get(rules.find_content("item",player.get("armor_equipped","")).get("id",""),{}).get("data",{}).get("visual",{})
    body=body_data.get("equipment_asset_id",body_data.get("asset_id",body))
    var weapon=weapon_data.get("equipment_asset_id",weapon_data.get("asset_id",""))
    var motion=weapon_data.get("motion","sword")
    var action="walk_"+motion if weapon!="" else "walk_unarmed"
    var elapsed=int(walk_clock*1000) if step_progress<1 else 100
    var weapon_action="walk"
    if attack_elapsed>=0:action="attack_"+motion;weapon_action="attack";elapsed=int(attack_elapsed*1000)
    elif cast_elapsed>=0:action="cast";elapsed=int(cast_elapsed*1000)
    elif pickup_elapsed>=0:action="pickup";elapsed=int(pickup_elapsed*1000)
    var index=work_assets.frame_index(body,action,direction,elapsed)
    if index<0:return false
    var relative=index-int(content.definition(body).get("metadata",{}).get("starting_frame",0))
    var order=world.get("work_draw_order",[])
    var layers=str(order[relative]) if relative<order.size() else "bhw"
    var opacity=0.35 if rules.actions.status_modifier(player,"hidden")>0 else 0.72 if hurt_time>0 else 1.0
    for layer in layers:
        if layer=="b":work_assets.draw_animation(self,body,action,direction,elapsed,pos,opacity)
        elif layer=="h":work_assets.draw_animation(self,head,action,direction,elapsed,pos,opacity)
        elif layer=="w" and weapon!="":work_assets.draw_animation(self,weapon,weapon_action,direction,elapsed,pos,opacity)
    return true

func apply_work_action(action: Dictionary):
    if action.mode=="inspect_item":open_inventory();notice("선택한 물품의 능력치와 착용 조건을 확인하세요.");return
    if action.mode=="local_message":notice(player.name+"의 사자후가 지역에 울려 퍼집니다.");event("local_message",{"channel":action.channel});return
    if action.mode=="directional_town_gate":menu="compass";choices=["동쪽","서쪽","남쪽","북쪽"];selected=0;return
    if action.mode in ["home_city","revival_npc","safe_region_entry"]:
        if action.get("requires_ghost",false) and player.hp>0:notice("혼령 상태에서 사용할 수 있습니다.");return
        var home=world.home
        var entry=home.entry
        if action.mode=="revival_npc":
            var revival=maps[home.map].npcs.filter(func(n):return n.get("services",[]).any(func(s):return s.type=="revive"))
            if not revival.is_empty():entry=[revival[0].x,revival[0].y]
        transition(home.map,entry);return
    if action.mode=="adjacent_enemy":
        if not entities.has(selected_target):notice("선택한 대상이 없습니다.");return
        var e=entities[selected_target]
        if e.map!=player.map or not e.alive:return
        for offset in DIRECTIONS:
            var destination=Vector2i(e.x,e.y)+offset
            if free_cell(player.map,destination):transition(player.map,[destination.x,destination.y]);return
    if action.get("map","")!="":transition(action.map,action.entry)
