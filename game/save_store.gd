extends RefCounted
## Atomic replacement with a checksum, schema version, backup and RNG state.

func write_state(path: String, state: Dictionary) -> bool:
    DirAccess.make_dir_recursive_absolute(path.get_base_dir())
    var payload = JSON.stringify(state)
    var document = {"schema":1,"payload":payload,"sha256":payload.sha256_text()}
    var file = FileAccess.open(path + ".pending",FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(JSON.stringify(document))
    file.flush()
    file.close()
    if FileAccess.file_exists(path):
        if DirAccess.copy_absolute(path,path + ".backup") != OK:
            return false
    return DirAccess.rename_absolute(path + ".pending",path) == OK

func read_one(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var doc = JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(doc) != TYPE_DICTIONARY or doc.get("schema") != 1 or typeof(doc.get("payload")) != TYPE_STRING:
        return {}
    if doc.payload.sha256_text() != doc.get("sha256"):
        return {}
    var state = JSON.parse_string(doc.payload)
    if typeof(state) != TYPE_DICTIONARY or not state.has_all(["player","world","rng_state"]):
        return {}
    # JSON numbers are floats; restore integers defined by the save schema.
    var p = state.player
    for key in ["level","xp2","hp","hp_max","mp","mp_max","gold","strength","x","y","direction","kills","rank","skill_page"]:
        if p.has(key):p[key] = int(p[key])
    for key in ["inventory","durability"]:
        for name in p.get(key,{}):p[key][name] = int(p[key][name])
    for entry in p.get("growth_log",[]):
        for key in ["from","hp_gain","mp_gain"]:entry[key] = int(entry[key])
    return state

func read_state(path: String) -> Dictionary:
    var result = read_one(path)
    if result.is_empty():
        result = read_one(path + ".backup")
    return result
