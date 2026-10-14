extends SceneTree
func _initialize():
    var folder=""
    var report=""
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--assets="):folder=arg.trim_prefix("--assets=")
        if arg.begins_with("--report="):report=arg.trim_prefix("--report=")
    var assets=load("res://assets.gd").new()
    var accepted=assets.load_directory(folder)
    var file=FileAccess.open(report,FileAccess.WRITE)
    file.store_string(JSON.stringify({"accepted":accepted,"registered":assets.tiles.size()}));file.close()
    quit()
