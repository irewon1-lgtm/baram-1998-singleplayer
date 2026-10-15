extends SceneTree
## Controlled direct transitions measure stage CPU; this is not a playthrough.
class TimedGame:
    extends "res://main.gd"
    var armed=false
    var draw_observation={}
    var profile_enabled=false
    var process_samples=[]
    var draw_samples=[]
    func _process(delta):
        var began=Time.get_ticks_usec()
        super._process(delta)
        if profile_enabled:process_samples.append(Time.get_ticks_usec()-began)
    func start_exercise():pass
    func _draw():
        var began=Time.get_ticks_usec()
        var builds=work_assets.tile_cache_builds
        var hits=work_assets.tile_cache_hits
        var resets=work_assets.tile_cache_resets
        super._draw()
        if profile_enabled:draw_samples.append(Time.get_ticks_usec()-began)
        if armed:
            draw_observation={"draw_submission_us":Time.get_ticks_usec()-began,"observed_at_us":Time.get_ticks_usec(),"tile_builds":work_assets.tile_cache_builds-builds,"tile_hits":work_assets.tile_cache_hits-hits,"tile_resets_during_draw":work_assets.tile_cache_resets-resets,"cached_work_tiles":work_assets.tile_cache.size()}
            armed=false

var game
var out=""
var rows=[]
var captures=[]

func _initialize():call_deferred("run")
func stats(samples: Array) -> Dictionary:
    if samples.is_empty():return {"samples":0}
    samples.sort();var total=0
    for v in samples:total+=v
    return {"samples":samples.size(),"mean_us":float(total)/samples.size(),"p95_us":samples[mini(samples.size()-1,int(samples.size()*.95))],"maximum_us":samples.back()}

func sample(map_id: String) -> Dictionary:
    game.profile_enabled=false
    game.transition(map_id,game.maps[map_id].entry)
    for frame in range(20):await process_frame
    game.process_samples.clear();game.draw_samples.clear();game.profile_enabled=true
    var intervals=[];var previous=Time.get_ticks_usec()
    for frame in range(180):
        await process_frame
        var now=Time.get_ticks_usec();intervals.append(now-previous);previous=now
    game.profile_enabled=false
    return {"map":map_id,"entities_in_map":game.maps[map_id].spawns.size(),"process":stats(game.process_samples),"draw_submission":stats(game.draw_samples),"frame_interval":stats(intervals)}

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
    var phases=[await sample("village")]
    var hunt=""
    for map_id in game.maps:
        if not game.maps[map_id].spawns.is_empty():hunt=map_id;break
    if hunt!="":phases.append(await sample(hunt))
    var report={"status":"PASS" if phases.size()==2 else "FAIL","scope":"Controlled idle actual main.gd Linux X11 software OpenGL process/draw CPU samples; cold entry excluded with20warmupframes; no native FPS claim.","platform":OS.get_name(),"display":DisplayServer.get_name(),"renderer":RenderingServer.get_current_rendering_method(),"commit":game.store.game_build,"content_version":game.content.version,"maps":game.maps.size(),"entities":game.entities.size(),"phases":phases,"native_steady_state_FPS":"NOT_RUN"}
    var f=FileAccess.open(out.path_join("ordinary-frame-report.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "));f.close()
    print("ORDINARY_FRAME_RESULT "+JSON.stringify(report))
    quit(0 if report.status=="PASS" else 1)
