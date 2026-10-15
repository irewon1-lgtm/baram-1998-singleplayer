extends SceneTree
## Measures CPU simulation/draw submission separately. No device FPS claim.
var game
var opts={}
func _initialize():call_deferred("run")
func stats(values: Array) -> Dictionary:
    if values.is_empty():return {"samples":0,"mean_us":0,"p95_us":0,"maximum_us":0}
    values.sort();var total=0
    for value in values:total+=value
    return {"samples":values.size(),"mean_us":float(total)/values.size(),"p95_us":values[mini(values.size()-1,int(values.size()*.95))],"maximum_us":values.back()}
func sample(map_id: String) -> Dictionary:
    game.profile_enabled=false
    game.transition(map_id,game.maps[map_id].entry)
    for frame in range(20):await process_frame
    game.cpu_process.clear();game.cpu_draw.clear();game.profile_enabled=true
    var elapsed=[];var previous=Time.get_ticks_usec()
    for frame in range(180):
        await process_frame
        var now=Time.get_ticks_usec();elapsed.append(now-previous);previous=now
    game.profile_enabled=false
    if DisplayServer.get_name()!="headless":
        await RenderingServer.frame_post_draw
        root.get_texture().get_image().save_png(opts.out.get_base_dir().path_join(opts.out.get_file().get_basename()+"-"+map_id.replace(".","-")+".png"))
    return {"map":map_id,"entities_in_map":game.maps[map_id].spawns.size(),"process":stats(game.cpu_process),"draw_submission":stats(game.cpu_draw),"frame_interval":stats(elapsed)}
func run():
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);opts[parts[0]]=parts[1]
    if not opts.has_all(["assets","content","out","save"]):push_error("--assets --content --out --save required");quit(2);return
    var script=GDScript.new()
    script.source_code="extends \"res://main.gd\"\nvar profile_enabled=false\nvar cpu_process=[]\nvar cpu_draw=[]\nfunc _process(delta):\n    var began=Time.get_ticks_usec()\n    super._process(delta)\n    if profile_enabled:cpu_process.append(Time.get_ticks_usec()-began)\nfunc _draw():\n    var began=Time.get_ticks_usec()\n    super._draw()\n    if profile_enabled:cpu_draw.append(Time.get_ticks_usec()-began)\n"
    if script.reload()!=OK:quit(2);return
    game=script.new();game.options=opts.duplicate();root.add_child(game)
    var limit=Time.get_ticks_msec()+60000
    while not game.startup_ready and not game.startup_failed and Time.get_ticks_msec()<limit:await process_frame
    if not game.startup_ready:push_error("startup failed/timed out");quit(2);return
    if game.menu=="creation":game.name_edit.release_focus();game.create_character()
    game.menu="";game.continuity_blocked=false
    var phases=[await sample("village")]
    var hunt=""
    for map_id in game.maps:
        if not game.maps[map_id].spawns.is_empty():hunt=map_id;break
    if hunt!="":phases.append(await sample(hunt))
    var report={"scope":"Headless CPU simulation/draw submission; no rendered FPS claim." if DisplayServer.get_name()=="headless" else "Desktop software OpenGL rendered simulation/draw submission and frame intervals; no Android device performance claim.","renderer":DisplayServer.get_name(),"content_version":game.content.version,"maps":game.maps.size(),"entities":game.entities.size(),"phases":phases}
    DirAccess.make_dir_recursive_absolute(opts.out.get_base_dir())
    var file=FileAccess.open(opts.out,FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
    print("FRAME_CPU_RESULT "+JSON.stringify(report));quit()
