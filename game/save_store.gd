extends RefCounted
## Versioned, verified replacement. Future saves never fall back to old backups.
const VERSION = 2
const MAX_BYTES = 16777216
var last_status = "NOT_RUN"
var last_error = {}
var content_version = "legacy-base"
var game_build = "codex-core-1"

func normalize_numbers(value):
    if typeof(value)==TYPE_FLOAT and is_finite(value) and absf(value)<=9007199254740991 and value==float(int(value)):return int(value)
    if typeof(value)==TYPE_DICTIONARY:
        for key in value:value[key]=normalize_numbers(value[key])
    elif typeof(value)==TYPE_ARRAY:
        for index in range(value.size()):value[index]=normalize_numbers(value[index])
    return value

func reject(code: String, path: String, field: String="") -> Dictionary:
    last_status=code
    last_error={"code":code,"path":path,"field":field,"reader_version":VERSION}
    return {}

func validate(state: Dictionary) -> bool:
    if not state.has_all(["player","world","rng_state"]) or typeof(state.player)!=TYPE_DICTIONARY or typeof(state.world)!=TYPE_DICTIONARY:return false
    var p=state.player
    if not p.has_all(["level","hp","hp_max","mp","mp_max","gold","inventory"]):return false
    if int(p.level)<1 or int(p.level)>99 or int(p.hp_max)<=0 or int(p.mp_max)<0 or int(p.hp)<0 or int(p.hp)>int(p.hp_max) or int(p.mp)<0 or int(p.mp)>int(p.mp_max) or int(p.gold)<0:return false
    if typeof(p.inventory)!=TYPE_DICTIONARY:return false
    for value in p.inventory.values():
        if float(value)!=float(int(value)) or int(value)<0:return false
    if typeof(p.get("equipment_instances",{}))!=TYPE_DICTIONARY or typeof(p.get("quest_progress",{}))!=TYPE_DICTIONARY:return false
    return true

func read_one(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):return reject("MISSING",path)
    var f=FileAccess.open(path,FileAccess.READ)
    if f==null:return reject("READ_FAILED",path)
    if f.get_length()>MAX_BYTES:f.close();return reject("SAVE_SIZE_LIMIT",path)
    var text=f.get_as_text();f.close()
    var parser=JSON.new()
    if parser.parse(text)!=OK:return reject("CORRUPT",path,"json_line_"+str(parser.get_error_line()))
    var doc=parser.data
    if typeof(doc)!=TYPE_DICTIONARY:return reject("CORRUPT",path)
    var version=int(doc.get("schema",0))
    if version>VERSION:return reject("UNSUPPORTED_FUTURE",path,"schema")
    if version not in [1,2] or typeof(doc.get("payload"))!=TYPE_STRING:return reject("UNSUPPORTED_FORMAT",path,"schema")
    if doc.payload.sha256_text()!=doc.get("sha256"):return reject("CHECKSUM_MISMATCH",path,"sha256")
    parser=JSON.new()
    if parser.parse(doc.payload)!=OK:return reject("CORRUPT",path,"payload")
    var state=normalize_numbers(parser.data)
    if typeof(state)!=TYPE_DICTIONARY or not validate(state):return reject("INVALID_STATE",path,"payload")
    var p=state.player
    for key in ["level","xp2","hp","hp_max","mp","mp_max","gold","strength","x","y","direction","kills","rank","skill_page","next_equipment_serial","time_us","core_format"]:
        if p.has(key):p[key]=int(p[key])
    for key in ["inventory","durability"]:
        for name in p.get(key,{}):p[key][name]=int(p[key][name])
    for entry in p.get("growth_log",[]):
        for key in ["from","hp_gain","mp_gain"]:entry[key]=int(entry[key])
    for gear in p.get("equipment_instances",{}).values():
        for key in ["enhancement_level","durability"]:
            if gear.has(key):gear[key]=int(gear[key])
    state.save_format_version=VERSION
    if version==1:state.migrated_from_schema=1
    state.content_version=doc.get("content_version",state.get("content_version","legacy-base"))
    state.game_build=doc.get("game_build",state.get("game_build","legacy-schema1"))
    last_status="MIGRATED_V1_IN_MEMORY" if version==1 else "OK"
    last_error={}
    return state

func read_state(path: String) -> Dictionary:
    var result=read_one(path)
    var initial=last_status
    if not result.is_empty():return result
    if initial in ["UNSUPPORTED_FUTURE","UNSUPPORTED_FORMAT","SAVE_SIZE_LIMIT"]:return {}
    var backup=read_one(path+".backup")
    if not backup.is_empty():last_status="RECOVERED_BACKUP";return backup
    return reject(initial,path)

func document(state: Dictionary) -> String:
    var copy=state.duplicate(true)
    copy.save_format_version=VERSION
    copy.content_version=state.get("content_version",content_version)
    copy.game_build=state.get("game_build",game_build)
    var payload=JSON.stringify(copy)
    return JSON.stringify({"schema":VERSION,"payload":payload,"sha256":payload.sha256_text(),"content_version":copy.content_version,"game_build":copy.game_build})

func write_bytes(path: String, text: String) -> bool:
    var f=FileAccess.open(path,FileAccess.WRITE)
    if f==null:return false
    f.store_string(text);f.flush();f.close()
    return true

func write_state(path: String, state: Dictionary) -> bool:
    if not validate(state):reject("INVALID_STATE",path);return false
    var text=document(state)
    if text.to_utf8_buffer().size()>MAX_BYTES:reject("SAVE_SIZE_LIMIT",path);return false
    var previous={}
    if FileAccess.file_exists(path):
        previous=read_one(path)
        if previous.is_empty():reject("EXISTING_SAVE_NOT_WRITABLE",path);return false
    if DirAccess.make_dir_recursive_absolute(path.get_base_dir())!=OK:return false
    if not write_bytes(path+".pending",text):return false
    if read_one(path+".pending").is_empty():return false
    if not previous.is_empty():
        var old=JSON.parse_string(FileAccess.get_file_as_string(path))
        if int(old.schema)==1 and not FileAccess.file_exists(path+".legacy-v1.backup"):
            if DirAccess.copy_absolute(path,path+".legacy-v1.backup")!=OK:return false
        if not write_bytes(path+".backup.pending",document(previous)):return false
        if read_one(path+".backup.pending").is_empty():return false
        if DirAccess.rename_absolute(path+".backup.pending",path+".backup")!=OK:return false
    if DirAccess.rename_absolute(path+".pending",path)!=OK:return false
    last_status="SAVED_V2";last_error={}
    return true
