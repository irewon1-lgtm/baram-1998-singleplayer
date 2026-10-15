extends SceneTree
func _initialize():
    var args={}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var p=arg.trim_prefix("--").split("=",true,1);args[p[0]]=p[1]
    if not args.has_all(["root","manifest","out"]):quit(2);return
    var rows=JSON.parse_string(FileAccess.get_file_as_string(args.manifest))
    var pack=PCKPacker.new()
    if typeof(rows)!=TYPE_ARRAY or pack.pck_start(args.out)!=OK:quit(2);return
    for row in rows:
        var path=str(row.path) if typeof(row)==TYPE_DICTIONARY else str(row)
        var source=str(row.source) if typeof(row)==TYPE_DICTIONARY else str(args.root).path_join(path)
        if pack.add_file("res://"+path,source)!=OK:quit(2);return
    if pack.flush()!=OK:quit(2);return
    print("PACKED_FILES "+str(rows.size()));quit()
