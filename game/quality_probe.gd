extends "res://work_play_probe.gd"
var captured=[]
var quality_mode=""
var elapsed_start=0

func capture(title: String):
    if DisplayServer.get_name()=="headless":return
    await RenderingServer.frame_post_draw
    var image=game.get_viewport().get_texture().get_image()
    if not image.is_empty():
        image.save_png(root.path_join(title+".png"));captured.append(title)

func finish():pass

func touch(at: Vector2, down: bool, id: int=1):
    var e=InputEventScreenTouch.new();e.position=game.get_viewport().get_screen_transform()*at;e.index=id;e.pressed=down
    Input.parse_input_event(e)
    await get_tree().process_frame

func drag(at: Vector2, id: int=1):
    var e=InputEventScreenDrag.new();e.position=game.get_viewport().get_screen_transform()*at;e.index=id
    Input.parse_input_event(e)
    await get_tree().process_frame

func tap(at: Vector2):
    await touch(at,true);await touch(at,false);await get_tree().create_timer(.15).timeout

func wait_path(limit=8.0):
    var until=Time.get_ticks_msec()+int(limit*1000)
    while (not game.navigation.path.is_empty() or game.step_progress<1 or not game.navigation.pending.is_empty()) and Time.get_ticks_msec()<until:
        await get_tree().create_timer(.03).timeout

func nearby_goal(distance=3) -> Vector2i:
    var m=game.maps[game.player.map]
    for offset in [Vector2i(distance,0),Vector2i(-distance,0),Vector2i(0,distance),Vector2i(0,-distance),Vector2i(distance,2),Vector2i(-distance,-2)]:
        var to=game.cell()+offset
        var result=game.Pathfinder.search(game.cell(),to,func(p,d):return game.free_cell(game.player.map,p,"",d),512)
        if result.status!="FOUND":continue
        if result.path.any(func(p):return m.portals.any(func(portal):return Vector2i(portal.x,portal.y)==p)):continue
        var point=game.screen_point(to.x,to.y)-Vector2(0,20)
        if game.touch_controls.targets.any(func(t):return t.rect.has_point(point)):continue
        if m.npcs.any(func(n):return Rect2(game.screen_point(n.x,n.y)-Vector2(23,82),Vector2(46,82)).has_point(point)):continue
        if game.entities.values().any(func(e):return e.alive and e.map==game.player.map and Rect2(game.screen_point(e.x,e.y)-Vector2(24,75),Vector2(48,75)).has_point(point)):continue
        return to
    return game.cell()

func run(g, mode: String, directory: String):
    quality_mode=mode;elapsed_start=Time.get_ticks_msec()
    game=g;root=directory;started=Time.get_ticks_msec();DirAccess.make_dir_recursive_absolute(root)
    if mode in ["quality-core","quality-soak"]:
        await super.run(g,"work-core",directory)
        check(await guided(game.world.home.map),"return_to_town_through_existing_travel_service")
    else:
        game.name_edit.release_focus();await key(KEY_ENTER);await key(KEY_E)
    await get_tree().create_timer(.2).timeout
    if game.touch_controls==null:
        check(false,"mobile_overlay_exists");complete();return
    check(game.field_rect()==game.get_viewport_rect(),"field_uses_entire_mobile_viewport")
    await capture("mobile-field")
    # Visual direction evidence: actual layered render for idle/walk/attack.
    for d in range(4):
        await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][d],.2,true)
        await capture("direction-"+str(d)+"-idle")
        if game.free_cell(game.player.map,game.cell()+game.DIRECTIONS[d],"",d):
            game.move_wait=0;game.move_player(d)
            await get_tree().create_timer(.06).timeout
            await capture("direction-"+str(d)+"-walk")
        game.attack_wait=0;game.begin_attack()
        await get_tree().create_timer(.17).timeout
        await capture("direction-"+str(d)+"-attack")
        await get_tree().create_timer(.5).timeout
    var start=game.cell();var goal=nearby_goal()
    await tap(game.screen_point(goal.x,goal.y)-Vector2(0,22));await wait_path()
    check(game.cell()==goal and goal!=start,"actual_touch_route_reaches_floor",{"before":start,"goal":goal,"after":game.cell(),"events":game.event_log.slice(-12)})
    var changed=0;var latest=game.cell()
    for i in range(24):
        latest=nearby_goal(2+i%3)
        await tap(game.screen_point(latest.x,latest.y)-Vector2(0,20));changed+=1
    await wait_path()
    check(game.cell()==latest and game.navigation.path.is_empty(),"24_retargets_keep_latest_only",{"commands":changed,"after":game.cell(),"latest":latest})
    var searches=game.navigation.searches
    game.navigation.route(Vector2i(-5,-5))
    await get_tree().create_timer(.3).timeout
    check(game.navigation.searches==searches+1 and game.navigation.path.is_empty(),"unreachable_terminates_without_retry")
    goal=nearby_goal(4);game.navigation.route(goal)
    var bag=game.touch_controls.center_for(KEY_I)
    await tap(bag);var stopped=game.cell();await get_tree().create_timer(.4).timeout
    check(game.menu=="inventory" and game.navigation.path.is_empty() and game.cell()==stopped,"bag_consumes_touch_and_cancels_route")
    await capture("mobile-bag")
    await tap(Vector2(game.get_viewport_rect().size.x*.5,250))
    check(game.cell()==stopped,"modal_touch_does_not_reach_field")
    game._notification(NOTIFICATION_WM_GO_BACK_REQUEST);await get_tree().create_timer(.2).timeout
    check(game.menu=="" and game.navigation.path.is_empty(),"Android_back_closes_modal_without_old_input")
    await tap(game.touch_controls.safe.position+Vector2(70,40))
    check(game.menu=="status","status_opens_on_portrait");await capture("mobile-status")
    await key(KEY_ESCAPE)
    var origin=Vector2(140,game.get_viewport_rect().size.y-130)
    var before_searches=game.navigation.searches
    await touch(origin,true,1);await drag(origin+Vector2(70,0),1)
    check(game.touch_controls.joystick_id==1 and game.navigation.searches==before_searches,"joystick_drag_never_starts_tap_route")
    var attack=game.touch_controls.center_for(KEY_SPACE)
    await touch(attack,true,2);await get_tree().create_timer(.7).timeout
    await touch(attack,false,2)
    check(game.touch_controls.joystick_id==1 and game.direct_direction==3,"right_finger_release_preserves_left_stick")
    await touch(origin+Vector2(70,0),false,1)
    check(game.direct_direction==-1 and game.touch_controls.joystick_id==-1,"left_release_clears_only_left_input")
    await touch(attack,true,2);await drag(Vector2(450,250),2)
    check(not game.touch_controls.pointers.has(2),"leaving_attack_button_releases_hold")
    await touch(origin,true,1);await drag(origin+Vector2(-65,0),1)
    game._notification(NOTIFICATION_APPLICATION_FOCUS_OUT)
    check(game.direct_direction==-1 and game.touch_controls.pointers.is_empty() and game.navigation.path.is_empty(),"focus_loss_cancels_all_input")
    # Test real NPC target selection/path/range, no teleport or remote dialogue.
    var candidates=game.maps[game.player.map].npcs.duplicate()
    candidates.sort_custom(func(a,b):return Vector2i(a.x,a.y).distance_to(game.cell())<Vector2i(b.x,b.y).distance_to(game.cell()))
    if not candidates.is_empty():
        var n=candidates[0]
        if game.navigation.route(Vector2i(n.x,n.y),{"kind":"npc","id":n.id,"position":Vector2i(n.x,n.y)}):
            var distant=Vector2i(n.x,n.y).distance_to(game.cell())>1.5
            check(not distant or game.menu=="","distant_NPC_does_not_open_immediately")
            await wait_path(20)
            check(game.menu!="" and game.npc.get("id","")==n.id and Vector2i(n.x,n.y).distance_to(game.cell())<=1.5,"NPC_approach_then_correct_dialogue")
            await key(KEY_ESCAPE)
    game.save_game();await capture("mobile-final")
    if mode=="quality-soak":
        game.frame_times.clear();game.last_frame_us=0
        var measured_start=Time.get_ticks_msec()
        while Time.get_ticks_msec()-elapsed_start<610000:
            if game.menu!="":await key(KEY_ESCAPE)
            var to=nearby_goal(3)
            await tap(game.screen_point(to.x,to.y)-Vector2(0,20));await wait_path(2)
            if int((Time.get_ticks_msec()-elapsed_start)/1000)%30<2:
                await tap(game.touch_controls.center_for(KEY_I));await key(KEY_ESCAPE);game.save_game()
            await get_tree().create_timer(.2).timeout
        check(true,"600_seconds_continuous_live_process",{"elapsed_ms":Time.get_ticks_msec()-elapsed_start})
        check(game.frame_times.size()>0,"post_capture_frame_timing_collected",{"duration_ms":Time.get_ticks_msec()-measured_start,"scope":"software_rendered_source_after_screenshots_not_Android_FPS"})
    complete()

func complete():
    var times=game.frame_times.duplicate();times.sort()
    var sum=0.0;var long50=0;var long100=0
    for t in times:sum+=t;long50+=int(t>50);long100+=int(t>100)
    var report={"status":"PASS" if checks.all(func(c):return c.status=="PASS") else "FAIL","checks":checks,"platform":OS.get_name(),"display":DisplayServer.get_name(),"scope":"LIVE_RENDERED_SYNTHETIC_TOUCH_NOT_HUMAN_NOT_GALAXY","elapsed_ms":Time.get_ticks_msec()-elapsed_start,"screenshots":captured,"frame_count":times.size(),"frame_ms_mean":sum/maxi(1,times.size()),"over_50ms":long50,"over_100ms":long100,"p99_ms":times[int(times.size()*.99)] if not times.is_empty() else 0}
    var f=FileAccess.open(root.path_join("quality-report.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "));f.close()
    print("BARAM_QUALITY "+JSON.stringify(report));get_tree().quit(0 if report.status=="PASS" else 1)
