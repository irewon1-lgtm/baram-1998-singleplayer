extends SceneTree
func _initialize():
    var args={}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var p=arg.trim_prefix("--").split("=",true,1);args[p[0]]=p[1]
    if not args.has_all(["cache","out"]):quit(2);return
    var manifest=JSON.parse_string(FileAccess.get_file_as_string(str(args.cache).path_join("manifest.json")))
    var input=str(args.cache).path_join("world.bin")
    if typeof(manifest)!=TYPE_DICTIONARY or FileAccess.get_sha256(input)!=manifest.get("sha256",""):quit(2);return
    var source=FileAccess.open_compressed(input,FileAccess.READ) if manifest.get("compression","")=="zstd" else FileAccess.open(input,FileAccess.READ)
    if source==null:quit(2);return
    var world=source.get_var(false);source.close()
    DirAccess.make_dir_recursive_absolute(args.out)
    var output=str(args.out).path_join("world.bin")
    var target=FileAccess.open_compressed(output,FileAccess.WRITE,FileAccess.COMPRESSION_ZSTD)
    if target==null:quit(2);return
    target.store_var(world,false);target.close()
    var test=FileAccess.open_compressed(output,FileAccess.READ)
    if test==null or test.get_var(false)!=world:quit(2);return
    test.close()
    manifest.compression="zstd";manifest.sha256=FileAccess.get_sha256(output)
    manifest.bytes=FileAccess.get_file_as_bytes(output).size()
    var file=FileAccess.open(str(args.out).path_join("manifest.json"),FileAccess.WRITE)
    file.store_string(JSON.stringify(manifest));file.close()
    print("CACHE_LOSSLESS_ZSTD "+JSON.stringify({"bytes":manifest.bytes,"maps":world.maps.size()}));quit()
