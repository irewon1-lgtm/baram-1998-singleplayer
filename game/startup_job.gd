extends RefCounted
## File verification and map construction own no scene/GPU objects. Run them
## off the UI thread; a mutex protects the small progress/log state only.
var mutex=Mutex.new()
var phase="Starting game"
var current=0
var total=0
var started=Time.get_ticks_msec()
var trace_path=""
var trace

func configure(path: String):
    trace_path=path
    DirAccess.make_dir_recursive_absolute(path.get_base_dir())
    trace=FileAccess.open(path,FileAccess.WRITE)
    report("Startup log opened")

func report(title: String, done: int=0, count: int=0):
    mutex.lock()
    phase=title;current=done;total=count
    var row={"elapsed_ms":Time.get_ticks_msec()-started,"phase":title,"current":done,"total":count,"memory_bytes":OS.get_static_memory_usage()}
    if trace!=null:trace.store_line(JSON.stringify(row));trace.flush()
    mutex.unlock()
    print("BARAM_STARTUP ",JSON.stringify(row))

func status() -> Dictionary:
    mutex.lock()
    var state={"phase":phase,"current":current,"total":total,"elapsed_ms":Time.get_ticks_msec()-started,"log":trace_path}
    mutex.unlock()
    return state

func prepare(content, rules, asset_folder: String, content_folder: String) -> Dictionary:
    report("Checking game files")
    if not content.load_directory(content_folder,report):return {"error":content.last_error}
    report("Preparing items and skills")
    content.apply_rules(rules)
    var path=asset_folder.path_join("source_maps/world.json")
    report("Reading maps")
    var world=JSON.parse_string(FileAccess.get_file_as_string(path if FileAccess.file_exists(path) else "res://data/world.json"))
    if typeof(world)!=TYPE_DICTIONARY or typeof(world.get("maps"))!=TYPE_ARRAY:return {"error":{"code":"WORLD_FORMAT","file":path}}
    world=content.merge_world(world,report)
    if not content.last_error.is_empty():return {"error":content.last_error}
    report("Preparing characters")
    var maps={};var decoration_rows={};var entities={}
    for m in world.maps:
        maps[m.id]=m
        var rows={}
        for d in m.get("decorations",[]):
            var y=int(d.y)
            if not rows.has(y):rows[y]=[]
            rows[y].append(d)
        decoration_rows[m.id]=rows
        for spawn in m.spawns:
            var spec=rules.monster(spawn.kind,world.replacements)
            entities[spawn.id]={"id":spawn.id,"kind":spawn.kind,"map":m.id,"x":spawn.x,"y":spawn.y,
                "home_x":spawn.x,"home_y":spawn.y,"direction":2,"hp":int(spec.values.hp),"alive":true,
                "respawn":0.0,"move_timer":3.0,"attack_timer":0.0,"provoked":false,"hurt":0.0,
                "hp_max":int(spec.values.hp),"mp":int(rules.value_or(spec.values,"mp",0)),"mp_max":int(rules.value_or(spec.values,"mp",0)),"statuses":{},"spec":spec}
    return {"world":world,"maps":maps,"decorations":decoration_rows,"entities":entities}
