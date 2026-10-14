extends SceneTree
## Observe the real main node immediately after _ready, before simulation time advances.
## This supplements the native-window restart test and does not use its cached payload.
var output=""
var save_path=""
var game

func _initialize():
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--restore-report="):output=arg.trim_prefix("--restore-report=")
        if arg.begins_with("--save="):save_path=arg.trim_prefix("--save=")
    game=load("res://main.gd").new()
    game.ready.connect(observe)
    root.add_child.call_deferred(game)

func observe():
    var expected=load("res://save_store.gd").new().read_state(save_path)
    var checks={"actual_player":game.player==expected.player,"actual_entities":game.entities==expected.world,
        "actual_loot":game.loot==expected.loot,"actual_rng":str(game.rules.rng.state)==str(expected.rng_state),
        "loaded_from_disk":game.save_loaded}
    var source_counts={}
    var total=0
    for i in range(game.assets.tile_set.get_source_count()):
        var id=game.assets.tile_set.get_source_id(i)
        var count=game.assets.tile_set.get_source(id).get_tiles_count()
        source_counts[str(id)]=count
        total+=count
    checks["actual_tileset_resource_count"]=total==14835
    var passed=checks.values().all(func(v):return v)
    var file=FileAccess.open(output,FileAccess.WRITE)
    file.store_string(JSON.stringify({"status":"PASS_ACTUAL_MAIN_NODE_STATE" if passed else "FAIL",
        "checks":checks,"tileset_source_counts":source_counts,"actual_tileset_tiles":total,
        "scope":"PACKAGED_MAIN_NODE_AFTER_READY_BEFORE_FIRST_TICK_NOT_CACHED_SAVE_PAYLOAD",
        "main_sha256":FileAccess.get_sha256("res://main.gd"),"save_sha256":FileAccess.get_sha256(save_path)},"  "))
    file.close()
    quit(0 if passed else 1)
