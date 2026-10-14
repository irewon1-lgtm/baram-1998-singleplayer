extends SceneTree

func _initialize():
    var args={}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);args[parts[0]]=parts[1]
    if not args.has_all(["assets","content","out"]):quit(2);return
    var content=load("res://content_registry.gd").new()
    if not content.load_directory(args.content):push_error("CACHE_CONTENT_HASH");quit(2);return
    var source=args.assets.path_join("source_maps/world.json")
    var began=Time.get_ticks_msec()
    var world=content.merge_world(JSON.parse_string(FileAccess.get_file_as_string(source)))
    if not content.last_error.is_empty():push_error(JSON.stringify(content.last_error));quit(2);return
    world=load("res://startup.gd").compact_world(world)
    DirAccess.make_dir_recursive_absolute(args.out)
    var target=args.out.path_join("world.bin")
    var file=FileAccess.open(target,FileAccess.WRITE)
    file.store_var(world,false);file.close()
    file=FileAccess.open(target,FileAccess.READ)
    var roundtrip=file.get_var(false);file.close()
    if roundtrip!=world:push_error("CACHE_ROUNDTRIP");quit(2);return
    var manifest={"format":"BARAM_WORLD_CACHE_V1","content_version":content.version,
        "source_world_sha256":FileAccess.get_sha256(source),"sha256":FileAccess.get_sha256(target),
        "maps":world.maps.size(),"compile_ms":Time.get_ticks_msec()-began,"bytes":FileAccess.get_file_as_bytes(target).size()}
    file=FileAccess.open(args.out.path_join("manifest.json"),FileAccess.WRITE)
    file.store_string(JSON.stringify(manifest,"  "));file.close()
    print("WORLD_CACHE "+JSON.stringify(manifest));quit()
