extends SceneTree
# External test driver for the exact embedded PCK, not shipped in the player ZIP.
# It only enables recording and sends inputs; game rules and saved RNG stay intact.
func _initialize():
    call_deferred("start")

func start():
    var args = {}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts = arg.trim_prefix("--").split("=",true,1)
            args[parts[0]] = parts[1]
    var boot = load("res://windows_bootstrap.tscn").instantiate()
    root.add_child(boot)
    if boot.get_child_count() != 1:
        push_error("Package bootstrap did not load the fixed game")
        quit(2)
        return
    var game = boot.get_child(0)
    while not game.startup_ready and not game.startup_failed:
        await process_frame
    if game.startup_failed:quit(2);return
    game.test_mode = str(args.get("probe-mode",""))
    game.test_root = str(args.get("evidence",""))
    AudioServer.add_bus_effect(0,game.recorder)
    game.recorder.set_recording_active(true)
    var helper = load(get_script().resource_path.get_base_dir().path_join("windows_loot_probe.gd")).new()
    game.add_child(helper)
    helper.run(game,game.test_mode,game.test_root)
