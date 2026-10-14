extends SceneTree
## Exercises the actual async Windows bootstrap on the available OS. Does not
## label Linux PCK execution as Windows execution.
var previous=0
var max_gap=0
var frames=0
var started=0
var output=""
var boot
func _initialize():
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--startup-report="):output=arg.trim_prefix("--startup-report=")
    call_deferred("run")
func _process(_delta):
    var now=Time.get_ticks_msec()
    if previous>0:max_gap=maxi(max_gap,now-previous)
    previous=now;frames+=1
    return false
func run():
    started=Time.get_ticks_msec()
    boot=load("res://windows_bootstrap.tscn").instantiate()
    root.add_child(boot)
    while boot.game==null or not boot.game.startup_complete:
        if Time.get_ticks_msec()-started>120000:quit(2);return
        await process_frame
    var game=boot.game
    await process_frame
    if DisplayServer.get_name()!="headless":await RenderingServer.frame_post_draw
    await process_frame
    var checks={"ui_kept_processing":frames>60,"no_five_second_ui_stall":max_gap<5000,"all_tile_ids_preserved":game.assets.tiles.size()==50104,"all_maps_preserved":game.maps.size()==423,"lazy_gpu_regions":game.assets.tile_cache.size()<1000,"flushed_startup_log":FileAccess.file_exists(game.startup_job.trace_path)}
    var result={"scope":"LINUX_GODOT_ASYNC_WINDOWS_BOOTSTRAP_NOT_NATIVE_WINDOWS","display":DisplayServer.get_name(),"status":"PASS" if checks.values().all(func(v):return v) else "FAIL","checks":checks,"elapsed_ms":Time.get_ticks_msec()-started,"frames":frames,"max_frame_gap_ms":max_gap,"memory_bytes":OS.get_static_memory_usage(),"tile_ids":game.assets.tiles.size(),"maps":game.maps.size()}
    var f=FileAccess.open(output,FileAccess.WRITE);f.store_string(JSON.stringify(result,"  "));f.close()
    print("STARTUP_RESULT ",JSON.stringify(result));quit(0 if result.status=="PASS" else 1)
