extends Node
## Sends real Godot input events to the live window; never calls damage/level-up directly.
## Captures rendered frames and checks outcomes, preserving failures before restart.
var game
var root = ""
var checks = []
var screenshots = []
var started = 0

func check(ok: bool, name: String, info = {}):
    checks.append({"name":name,"status":"PASS" if ok else "FAIL","observed":info})
    print("SCREEN_CHECK "+name+" "+("PASS" if ok else "FAIL"))

func pause(seconds: float):
    await get_tree().create_timer(seconds).timeout

func key(code: int, delay: float = 0.23, turn: bool = false):
    var event = InputEventKey.new()
    event.keycode = code
    event.physical_keycode = code
    event.shift_pressed = turn
    event.pressed = true
    Input.parse_input_event(event)
    await get_tree().process_frame
    var release = InputEventKey.new()
    release.keycode = code
    release.physical_keycode = code
    release.pressed = false
    Input.parse_input_event(release)
    await pause(delay)

func capture(title: String):
    await RenderingServer.frame_post_draw
    var path = root.path_join(title+".png")
    var image = game.get_viewport().get_texture().get_image()
    var ok = image.save_png(path) == OK
    screenshots.append({"name":title,"path":path,"width":image.get_width(),"height":image.get_height(),
        "sha256":FileAccess.get_sha256(path) if ok else "","status":"PASS_CAPTURE_ONLY" if ok else "FAIL"})
    check(ok and image.get_width()==960 and image.get_height()==640,"rendered_"+title)
    print("SCREEN_CAPTURE_READY "+title)
    await pause(0.25) # external runner independently captures the actual X11 window

func route(target: Vector2i) -> bool:
    # BFS plans keys around actual collision/spawn data. The game still decides every step.
    for attempt in range(120):
        if game.player.hp<=0:return false
        if game.player.hp < game.player.hp_max*0.5 and int(game.player.inventory.get("초보 회복약",0))>0:
            await use_potion()
        if game.cell()==target:return true
        var current = game.cell()
        var queue=[current]
        var parents={current:null}
        var directions={}
        var found=false
        for index in range(1120):
            if index>=queue.size():break
            var at=queue[index]
            if at==target:found=true;break
            for d in range(4):
                var next=at+game.DIRECTIONS[d]
                if parents.has(next) or not game.free_cell(game.player.map,next):continue
                var portal_here=false
                for portal in game.maps[game.player.map].portals:
                    if next==Vector2i(portal.x,portal.y) and next!=target:
                        portal_here=true
                        break
                if portal_here:continue
                parents[next]=at
                directions[next]=d
                queue.append(next)
        if not found:return false
        var next=target
        while parents[next]!=current:next=parents[next]
        var expected_map=game.player.map
        await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][directions[next]])
        if game.player.map!=expected_map:return true # portal completed by real movement
    return false

func hunt_one(kind: String = "") -> bool:
    var target={}
    var nearest=999.0
    for id in game.entities:
        var e=game.entities[id]
        var dist=Vector2i(e.x,e.y).distance_to(game.cell())
        if e.map==game.player.map and e.alive and (kind=="" or e.kind==kind) and dist<nearest:
            target=e;nearest=dist
    if target.is_empty():return false
    for attempt in range(20):
        if game.player.hp<=0:return false
        if not target.alive:return true
        var adjacent=[]
        for d in range(4):
            var at=Vector2i(target.x,target.y)-game.DIRECTIONS[d]
            var portal_here=false
            for portal in game.maps[game.player.map].portals:
                if at==Vector2i(portal.x,portal.y):
                    portal_here=true
                    break
            if not portal_here and (at==game.cell() or game.free_cell(game.player.map,at)):adjacent.append({"at":at,"direction":d})
        adjacent.sort_custom(func(a,b):return a.at.distance_to(game.cell())<b.at.distance_to(game.cell()))
        if adjacent.is_empty():return false
        if not await route(adjacent[0].at):return false
        var offset=Vector2i(target.x,target.y)-game.cell()
        var direction=game.DIRECTIONS.find(offset)
        if direction<0:continue
        await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][direction],0.03,true)
        # Facing a blocked enemy is a real arrow key action; then space starts animation.
        await key(KEY_SPACE,0.7)
        await key(KEY_G,0.03)
        if int(game.player.hp)==0:return false
    return not target.alive

func use_potion():
    await key(KEY_I,0.02)
    var index=game.choices.find("초보 회복약")
    if index>=0:
        for i in range(index):await key(KEY_DOWN,0.02)
        await key(KEY_U,0.02)
    await key(KEY_ESCAPE,0.02)

func run(g, mode: String, directory: String):
    game=g;root=directory;started=Time.get_ticks_msec()
    DirAccess.make_dir_recursive_absolute(root)
    if mode=="restart":
        check(game.save_loaded,"fresh_process_loaded_save")
        var before=game.store.read_state(root.path_join("expected-state.json"))
        check(game.loaded_snapshot.player==before.player,"restart_preserves_entire_player",{"level":game.player.level,"gold":game.player.gold,"equipped":game.player.equipped})
        check(game.loaded_snapshot.world==before.world and game.loaded_snapshot.loot==before.loot,"restart_preserves_world_and_loot")
        check(str(game.loaded_snapshot.rng_state)==str(before.rng_state),"restart_preserves_rng")
        await capture("restart")
        finish()
        return
    check(not game.save_loaded and game.menu=="creation","fresh_character_creation_screen")
    await capture("creation")
    var job_index=int(mode.trim_prefix("class-")) if mode.begins_with("class-") else 0
    await key(KEY_1+job_index)
    await key(KEY_ENTER)
    check(game.player.job==game.Rules.JOBS[job_index] and game.player.level==1,"character_created_via_input")
    await key(KEY_ENTER)
    check(game.menu=="shop","npc_dialogue_via_input")
    await key(KEY_DOWN)
    await key(KEY_B)
    check(int(game.player.inventory.get("목검",0))==1 and game.player.gold==10,"shop_purchase_via_input")
    await capture("shop")
    await key(KEY_ESCAPE)
    await key(KEY_I)
    await key(KEY_DOWN)
    await key(KEY_E)
    check(game.player.equipped=="목검","inventory_weapon_equipped_via_input")
    await key(KEY_ESCAPE)
    await capture("village-equipped")
    # Merchant is a blocked tile. Up changes facing without walking through it.
    var before=game.cell()
    await key(KEY_UP)
    check(game.cell()==before and game.player.direction==0,"collision_and_facing_direction")
    var mp=int(game.player.mp)
    await key(KEY_1,0.08)
    check(game.player.mp==mp-5,"skill_hotkey_deducts_mp")
    await capture("skill-effect")
    await pause(0.6)
    check(await route(Vector2i(15,12)) and game.player.map=="field","village_to_field_by_walking")
    var xp_before=int(game.player.xp2)
    check(await hunt_one("rabbit"),"directional_animated_attack_kills_rabbit")
    check(int(game.player.xp2)>xp_before,"combat_awards_actual_xp")
    await capture("field-combat")
    if mode.begins_with("class-"):
        await key(KEY_F5)
        check(FileAccess.file_exists(game.save_path),"class_save_written")
        finish()
        return
    var deadline=Time.get_ticks_msec()+160000
    while int(game.player.kills)<25 and game.player.hp>0 and Time.get_ticks_msec()<deadline:
        if not await hunt_one():await pause(0.3)
    check(game.player.kills>=25,"25_actual_input_driven_kills",{"kills":game.player.kills})
    if game.player.kills<25:
        finish()
        return
    var picked=game.event_log.filter(func(e):return e.event=="item_picked_up").size()
    check(picked>0,"actual_random_drop_pickup",{"pickups":picked})
    # Return and claim the two authored quest rewards through the NPC interaction.
    check(await route(Vector2i(11,12)) and game.player.map=="village","field_to_village_by_walking")
    check(await route(Vector2i(12,10)),"walk_to_quest_npc")
    await key(KEY_UP)
    await key(KEY_ENTER)
    await key(KEY_ENTER)
    check(int(game.player.level)>=5 and game.player.quests.size()==2,"quest_xp_causes_real_levelups",{"level":game.player.level})
    if int(game.player.level)<5 or game.player.quests.size()!=2:
        finish()
        return
    await capture("level-up")
    # Supply exploration through real NPC transactions, not grants or HP edits.
    check(await route(Vector2i(12,12)),"return_to_merchant")
    await key(KEY_UP)
    await key(KEY_ENTER)
    var potion_index=game.choices.find("초보 회복약")
    for i in range(potion_index):await key(KEY_DOWN,0.03)
    for i in range(10):await key(KEY_B,0.03)
    await key(KEY_R,0.03)
    await key(KEY_C,0.03)
    check(int(game.player.inventory.get("초보 회복약",0))==10,"generated_potions_bought_through_actual_shop")
    await key(KEY_ESCAPE)
    check(await route(Vector2i(6,8)) and game.player.map=="inn","village_to_interior_by_walking")
    await key(KEY_UP)
    await key(KEY_ENTER)
    await capture("inn")
    await key(KEY_ESCAPE)
    check(await route(Vector2i(11,12)) and game.player.map=="village","inn_exit_by_walking")
    check(await route(Vector2i(24,8)) and game.player.map=="guild","enter_training_interior")
    await key(KEY_UP)
    await key(KEY_ENTER)
    check(game.menu=="trainer","actual_class_skill_catalogue")
    await capture("trainer")
    await key(KEY_ESCAPE)
    check(await route(Vector2i(11,12)) and game.player.map=="village","guild_exit_by_walking")
    check(await route(Vector2i(15,12)) and game.player.map=="field","reenter_field")
    check(await route(Vector2i(22,12)) and game.player.map=="cave","field_to_dungeon_by_walking")
    check(await hunt_one("rat"),"dungeon_combat")
    await capture("cave")
    check(await route(Vector2i(35,12)) and game.player.map=="deep","deep_dungeon_transition")
    await capture("deep")
    check(await route(Vector2i(35,12)) and game.player.map=="ruins","ruins_transition")
    await capture("ruins")
    check(await route(Vector2i(11,12)) and game.player.map=="deep","ruins_return")
    check(await route(Vector2i(11,12)) and game.player.map=="cave","deep_return")
    check(await route(Vector2i(11,12)) and game.player.map=="field","cave_return")
    check(await route(Vector2i(35,12)) and game.player.map=="forest","forest_transition")
    await capture("forest")
    var impacts=game.event_log.filter(func(e):return e.event=="damage_applied" and e.details.source=="melee")
    check(impacts.size()>0 and impacts.all(func(e):return e.details.impact_time>=0.16),"damage_occurs_after_animation_impact_time")
    check(game.audio_events.size()>0,"original_wav_events_played",{"events":game.audio_events.size()})
    await key(KEY_F5)
    check(FileAccess.file_exists(game.save_path),"save_via_f5_input")
    var expected=game.store.read_state(game.save_path)
    game.store.write_state(root.path_join("expected-state.json"),expected)
    await capture("saved-forest")
    finish()

func finish():
    if game.recorder.is_recording_active():
        game.recorder.set_recording_active(false)
        var stream=game.recorder.get_recording()
        if stream!=null:
            var path=root.path_join("mixed-audio.wav")
            var ok=stream.save_to_wav(path)==OK
            check(ok,"engine_audio_mix_recorded")
    var failures=checks.filter(func(c):return c.status!="PASS").size()
    var report={"status":"PASS_EXECUTED_SCREEN_INPUT" if failures==0 else "FAIL","checks":checks,
        "elapsed_ms":Time.get_ticks_msec()-started,"screenshots":screenshots,"events":game.event_log,
        "registered_tiles":game.assets.tiles.size(),"registered_tile_sources":game.assets.tile_set.get_source_count(),
        "rendered_tile_ids":game.assets.used_tiles.keys(),"rendered_actor_frames":game.assets.used_frames.keys(),
        "audio_events":game.audio_events,"player":game.player,"save_loaded":game.save_loaded,
        "scope":"REAL_X11_GODOT_VIEWPORT_WITH_INPUT_EVENTS_NOT_FULL_1_TO_99_PLAYTHROUGH"}
    var file=FileAccess.open(root.path_join(game.test_mode+"-report.json"),FileAccess.WRITE)
    file.store_string(JSON.stringify(report,"  "));file.close()
    game.get_tree().quit(0 if failures==0 else 1)
