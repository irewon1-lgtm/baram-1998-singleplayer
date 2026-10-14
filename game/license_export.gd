extends SceneTree

func _initialize():
    var directory=""
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--out="):directory=arg.trim_prefix("--out=")
    DirAccess.make_dir_recursive_absolute(directory)
    for name in ["GODOT-LICENSE.txt","GODOT-THIRD-PARTY.json"]:
        var file=FileAccess.open(directory.path_join(name),FileAccess.WRITE)
        file.store_string(Engine.get_license_text() if name.ends_with(".txt") else JSON.stringify({"components":Engine.get_copyright_info(),"licenses":Engine.get_license_info()},"  "))
        file.close()
    quit()
