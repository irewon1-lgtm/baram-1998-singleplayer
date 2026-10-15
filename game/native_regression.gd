extends "res://work_play_probe.gd"
## Uses the live game's input handlers and timers. A headless PASS is never
## presented as a Windows screen/operator/play/audio PASS.
var native_mode=""
var collecting=false

func run(g,mode,directory):
    native_mode=mode
    game=g;root=directory;started=Time.get_ticks_msec()
    DirAccess.make_dir_recursive_absolute(root)
    if mode=="native-smoke":
        check(game.startup_ready,"exe_enters_game_after_loading")
        check(game.maps.size()>0 and game.assets.tiles.size()>=14835,"content_and_all_tile_ids_registered")
        check(game.menu=="creation" or game.save_loaded,"creation_or_existing_save_reached")
        await get_tree().process_frame
        if DisplayServer.get_name()!="headless":
            await RenderingServer.frame_post_draw
            var frame=game.get_viewport().get_texture().get_image()
            var colors={}
            if not frame.is_empty():
                for y in range(0,frame.get_height(),16):
                    for x in range(0,frame.get_width(),16):
                        colors[frame.get_pixel(x,y).to_rgba32()]=true
            var captured=not frame.is_empty() and colors.size()>=8
            if captured:captured=frame.save_png(root.path_join("windows-startup-frame.png"))==OK
            check(captured,"windowed_game_frame_rendered",{"sampled_colors":colors.size(),"width":frame.get_width(),"height":frame.get_height()})
            await visual_directions()
        finish();return
    await super.run(g,"work-restart" if mode=="native-restart" else "work-core",directory)

func visual_frame(title: String):
    await RenderingServer.frame_post_draw
    var image=game.get_viewport().get_texture().get_image()
    check(not image.is_empty() and image.save_png(root.path_join(title+".png"))==OK,"captured_"+title)

func visual_directions():
    game.name_edit.release_focus()
    await key(KEY_ENTER);await key(KEY_E)
    # Reach a nearby open cross using existing collision data and actual keys.
    var origin=game.cell();var reached=false
    for radius in range(1,7):
        for offset in [Vector2i(radius,0),Vector2i(-radius,0),Vector2i(0,radius),Vector2i(0,-radius)]:
            var at=origin+offset
            if game.free_cell(game.player.map,at) and game.DIRECTIONS.all(func(d):return game.free_cell(game.player.map,at+d)):
                if await route(at):reached=true;break
        if reached:break
    check(reached,"native_visual_reaches_open_cross_by_keyboard")
    await visual_frame("windows-field")
    for d in range(4):
        var code=[KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][d]
        await key(code,.03,true)
        var press=InputEventKey.new();press.keycode=code;press.physical_keycode=code;press.pressed=true;Input.parse_input_event(press)
        await get_tree().create_timer(.06).timeout
        await visual_frame("windows-direction-"+str(d)+"-walk")
        press=InputEventKey.new();press.keycode=code;press.physical_keycode=code;press.pressed=false;Input.parse_input_event(press)
        await get_tree().create_timer(.25).timeout
        await visual_frame("windows-direction-"+str(d)+"-idle")
        await key(KEY_SPACE,.17)
        await visual_frame("windows-direction-"+str(d)+"-attack")
        await get_tree().create_timer(.6).timeout
    await key(KEY_I);await visual_frame("windows-bag");await key(KEY_ESCAPE)

func capture(title: String):
    # Rendering assertions require an independently observed Windows GUI.
    # The GUI capture normally consumes real wall time. Headless capture must
    # explicitly wait for the previous turn/move cooldown before the next key.
    while game.move_wait>0:
        await get_tree().create_timer(0.02).timeout
    await get_tree().process_frame

func finish():
    if native_mode=="native-core" and not collecting and checks.all(func(c):return c.status=="PASS"):
        collecting=true
        call_deferred("collect_actual_drop")
        return
    var failures=checks.filter(func(c):return c.status!="PASS").size()
    var report={"status":"PASS" if failures==0 else "FAIL","checks":checks,
        "platform":OS.get_name(),"scope":"LIVE_GAME_AUTOMATED_INPUT_AND_SAVE_NOT_OPERATOR_GUI",
        "actual_windows_gui":"BLOCKED_NO_OPERATOR_GUI_OBSERVATION",
        "elapsed_ms":Time.get_ticks_msec()-started,"game_build":game.store.game_build,
        "content_version":game.content.version,"registered_tiles":game.assets.tiles.size(),"maps":game.maps.size(),
        "startup_ready":game.startup_ready,"save_loaded":game.save_loaded}
    var file=FileAccess.open(root.path_join(native_mode+"-report.json"),FileAccess.WRITE)
    file.store_string(JSON.stringify(report,"  "));file.close()
    print("BARAM_NATIVE_RESULT "+JSON.stringify(report))
    game.get_tree().quit(0 if failures==0 else 1)

func collect_actual_drop():
    var initial=game.player.inventory.duplicate(true)
    for attempt in range(12):
        if Time.get_ticks_msec()-started>120000:break
        var rabbits=game.entities.values().filter(func(e):return e.map==game.player.map and e.alive and e.spec.name=="토끼")
        if rabbits.is_empty() or game.player.hp<=0:break
        if not await hunt_one(rabbits[0].kind):break
        await key(KEY_G)
        if game.event_log.any(func(e):return e.event=="item_picked_up"):break
    check(game.event_log.any(func(e):return e.event=="item_picked_up"),"actual_random_drop_and_G_pickup")
    var increased=false
    for id in game.player.inventory:
        if int(game.player.inventory[id])>int(initial.get(id,0)):increased=true
    check(increased,"picked_item_increases_inventory")
    await key(KEY_F5)
    var saved=game.store.read_state(game.save_path)
    check(not saved.is_empty() and saved.player.inventory==game.player.inventory,"pickup_save_matches_live_inventory")
    if not saved.is_empty():game.store.write_state(root.path_join("expected-state.json"),saved)
    finish()
