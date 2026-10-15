extends SceneTree
## Controlled direct transitions measure stage CPU; this is not a playthrough.
class TimedGame:
    extends "res://main.gd"
    var armed=false
    var draw_observation={}
    func start_exercise():pass
    func _draw():
        var began=Time.get_ticks_usec()
        var builds=work_assets.tile_cache_builds
        var hits=work_assets.tile_cache_hits
        var resets=work_assets.tile_cache_resets
        super._draw()
        if armed:
            draw_observation={"draw_submission_us":Time.get_ticks_usec()-began,"observed_at_us":Time.get_ticks_usec(),"tile_builds":work_assets.tile_cache_builds-builds,"tile_hits":work_assets.tile_cache_hits-hits,"tile_resets_during_draw":work_assets.tile_cache_resets-resets,"cached_work_tiles":work_assets.tile_cache.size()}
            armed=false

var game
var out=""
var rows=[]
var captures=[]

func _initialize():call_deferred("run")
func stage(name_value: String, map_id: String, entry: Array, forced_flush=false) -> Dictionary:
    for frame in range(3):await process_frame
    var before_map=game.player.map
    var before_size=game.work_assets.tile_cache.size()
    if forced_flush:game.work_assets.tile_cache.clear()
    game.draw_observation={};game.armed=true
    var resets=game.work_assets.tile_cache_resets
    var began=Time.get_ticks_usec()
    game.transition(map_id,entry)
    var transition_us=Time.get_ticks_usec()-began
    var clear_count=game.work_assets.tile_cache_resets-resets
    game.queue_redraw()
    if DisplayServer.get_name()=="headless":
        for frame in range(2):await process_frame
    else:await RenderingServer.frame_post_draw
    var frame_us=Time.get_ticks_usec()-began
    var profile=game.draw_observation.duplicate()
    var row={"stage":name_value,"status":"PASS" if not profile.is_empty() and game.player.map==map_id else "FAIL","origin_map":before_map,"target_map":map_id,"actual_map":game.player.map,"forced_flush_proxy":forced_flush,"prior_cached_work_tiles":before_size,"transition_handler_us":transition_us,"tile_resets_in_transition":clear_count,"first_post_draw_wall_us":frame_us,"first_draw":profile}
    rows.append(row)
    if DisplayServer.get_name()!="headless":
        var image=root.get_texture().get_image()
        var path=out.path_join(name_value+".png")
        if not image.is_empty() and image.save_png(path)==OK:captures.append({"path":path,"sha256":FileAccess.get_sha256(path),"width":image.get_width(),"height":image.get_height()})
    print("TRANSITION_STAGE "+JSON.stringify(row))
    return row

func run():
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--out="):out=arg.trim_prefix("--out=")
    if out=="":quit(2);return
    DirAccess.make_dir_recursive_absolute(out)
    if not ProjectSettings.load_resource_pack("res://runtime.pck"):push_error("runtime pack unavailable");quit(2);return
    game=TimedGame.new()
    game.options={"assets":"res://private_assets","content":"res://private_content","save":out.path_join("isolated-save/v2/character.json"),"exercise":"transition-stage-instrumentation"}
    root.add_child(game)
    var deadline=Time.get_ticks_msec()+60000
    while not game.startup_ready and not game.startup_failed and Time.get_ticks_msec()<deadline:await process_frame
    if not game.startup_ready:push_error("main startup blocked");quit(2);return
    if game.menu=="creation":game.name_edit.release_focus();game.create_character()
    for frame in range(5):await process_frame
    var compass_begin=Time.get_ticks_usec();var gate=game.navigation.compass_entry(0)
    var compass_us=Time.get_ticks_usec()-compass_begin
    var compass=game.navigation.last_compass.duplicate()
    await stage("compass-same-village-first-gate","village",[gate.x,gate.y])
    await stage("compass-same-village-repeat-gate","village",[gate.x,gate.y])
    var work_id=""
    for id in game.maps:
        var found=false
        for row in game.maps[id].ground:
            for key in row:
                if "#" in key:found=true;break
            if found:break
        if found:work_id=id;break
    if work_id!="":
        await stage("work-map-cold-entry",work_id,game.maps[work_id].entry)
        var repeat=await stage("work-map-same-map-repeat",work_id,game.maps[work_id].entry)
        repeat.same_map_no_tile_rebuild=repeat.first_draw.get("tile_builds",-1)==0 and repeat.tile_resets_in_transition==0
        await stage("work-map-forced-flush-legacy-proxy",work_id,game.maps[work_id].entry,true)
    var report={"status":"PASS" if rows.size()==5 and rows.all(func(r):return r.status=="PASS") else "FAIL","scope":"Controlled actual main.gd direct transition handler and first desktop draw. No source mutation; not legal-spell gameplay or native-device timing. Forced flush is an explicit cache-lifetime proxy, not the old whole game.","platform":OS.get_name(),"display":DisplayServer.get_name(),"renderer":RenderingServer.get_current_rendering_method(),"commit":game.store.game_build,"content_version":game.content.version,"maps":game.maps.size(),"entities":game.entities.size(),"compass_search":{"outer_call_us":compass_us,"internal":compass},"stages":rows,"captures":captures,"native_first_playable_frame":"NOT_RUN","steady_state_FPS":"NOT_RUN"}
    var f=FileAccess.open(out.path_join("transition-stage-report.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "));f.close()
    print("TRANSITION_STAGE_RESULT "+JSON.stringify({"status":report.status,"stages":rows.size(),"platform":report.platform,"display":report.display,"maps":report.maps,"entities":report.entities}))
    quit(0 if report.status=="PASS" else 1)
