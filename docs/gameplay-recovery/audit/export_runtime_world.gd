extends SceneTree
## Read-only exact registry merger, reduced to gameplay topology for independent audit.
func _initialize():
    var args={}
    for arg in OS.get_cmdline_user_args():
        if "=" in arg:
            var pair=arg.trim_prefix("--").split("=",true,1);args[pair[0]]=pair[1]
    var content=load("res://content_registry.gd").new()
    if not content.load_directory(args.content):push_error(JSON.stringify(content.last_error));quit(2);return
    var world=content.merge_world(JSON.parse_string(FileAccess.get_file_as_string(args.assets.path_join("source_maps/world.json"))))
    if not content.last_error.is_empty():push_error(JSON.stringify(content.last_error));quit(2);return
    for map in world.maps:
        map.erase("ground");map.erase("decorations")
    world["audit_content_version"]=content.version
    world["audit_registry_sha256"]=FileAccess.get_sha256("res://content_registry.gd")
    if FileAccess.file_exists("res://world_repairs.gd"):world["audit_world_repairs_sha256"]=FileAccess.get_sha256("res://world_repairs.gd")
    var out=FileAccess.open(args.out,FileAccess.WRITE);out.store_string(JSON.stringify(world));out.close()
    print("AUDIT_EXPORTED "+str(world.maps.size()));quit()
