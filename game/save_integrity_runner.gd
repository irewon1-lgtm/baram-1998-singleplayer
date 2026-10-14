extends SceneTree
const Rules = preload("res://rules.gd")
const Store = preload("res://save_store.gd")

func _initialize():
    var directory=""
    var report=""
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--out="):directory=arg.trim_prefix("--out=")
        if arg.begins_with("--report="):report=arg.trim_prefix("--report=")
    DirAccess.make_dir_recursive_absolute(directory)
    var path=directory.path_join("scratch.json")
    var store=Store.new()
    var p=Rules.new().new_player("전사","저장무결성")
    var state={"player":p,"world":{},"rng_state":"1998"}
    var results=[]
    var first=store.write_state(path,state)
    p.gold=77
    var second=store.write_state(path,state)
    results.append({"name":"atomic_replace_and_read","status":"PASS" if first and second and store.read_state(path).player.gold==77 else "FAIL"})
    var file=FileAccess.open(path+".pending",FileAccess.WRITE)
    file.store_string("unfinished");file.close()
    results.append({"name":"unfinished_pending_does_not_replace_valid_save","status":"PASS" if store.read_state(path).player.gold==77 else "FAIL"})
    file=FileAccess.open(path,FileAccess.WRITE)
    file.store_string("{broken");file.close()
    results.append({"name":"corrupt_primary_restores_previous_backup","status":"PASS" if store.read_state(path).player.gold==30 else "FAIL"})
    file=FileAccess.open(path+".backup",FileAccess.WRITE)
    file.store_string("{broken");file.close()
    results.append({"name":"corrupt_primary_and_backup_rejected","status":"PASS" if store.read_state(path).is_empty() else "FAIL"})
    var ok=results.all(func(r):return r.status=="PASS")
    file=FileAccess.open(report,FileAccess.WRITE)
    file.store_string(JSON.stringify({"status":"PASS_EXECUTED_SAVE_INTEGRITY" if ok else "FAIL","results":results,
        "save_module_sha256":FileAccess.get_sha256("res://save_store.gd")},"  "));file.close()
    quit(0 if ok else 1)
