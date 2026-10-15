extends RefCounted
## Fail-closed local journal. Character schema/path remains usable offline.
const Store = preload("res://save_store.gd")
var root = "user://continuity"
var owner = ""
var device = ""
var compatibility = ""
var meta = {}
var path = ""
var error = ""

static func uuid() -> String:
    var b=Crypto.new().generate_random_bytes(16)
    b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128
    var h=b.hex_encode()
    return h.substr(0,8)+"-"+h.substr(8,4)+"-"+h.substr(12,4)+"-"+h.substr(16,4)+"-"+h.substr(20)

func atomic(file: String, text: String) -> bool:
    if DirAccess.make_dir_recursive_absolute(file.get_base_dir())!=OK:return false
    var f=FileAccess.open(file+".pending",FileAccess.WRITE)
    if f==null:return false
    f.store_string(text);f.flush();f.close()
    return DirAccess.rename_absolute(file+".pending",file)==OK

func persist() -> bool:
    if not atomic(path+".sync.json",JSON.stringify(meta)):
        error="LOCAL_JOURNAL_FAILED";return false
    return true

func select_account(id: String, compat: String, device_id: String) -> bool:
    if not id.is_valid_identifier() and id.replace("-","").length()!=32:return false
    if not id.replace("-","").is_valid_hex_number(false) or id.length()!=36:return false
    owner=id;compatibility=compat;device=device_id
    path=root.path_join(owner).path_join("character.json")
    meta={"version":0,"dirty":false,"leased":false,"request":"","pending_sha":"","compatibility":compat}
    if FileAccess.file_exists(path+".sync.json"):
        var doc=JSON.parse_string(FileAccess.get_file_as_string(path+".sync.json"))
        if typeof(doc)!=TYPE_DICTIONARY or not doc.has_all(meta.keys()):error="CORRUPT_JOURNAL";return false
        meta=doc
        if meta.compatibility!=compat:error="UPDATE_REQUIRED";return false
    elif FileAccess.file_exists(path):error="MISSING_JOURNAL";return false
    return true

func mark_dirty() -> bool:
    if meta.get("conflict",false):error="CONFLICT_PRESERVED";return false
    if not meta.get("leased",false):error="NO_SESSION";return false
    meta.dirty=true
    return persist()

func compatible_document(text: String) -> bool:
    var doc=JSON.parse_string(text)
    return typeof(doc)==TYPE_DICTIONARY and int(doc.get("schema",0))==2 and "schema2:"+str(doc.get("content_version",""))==compatibility

func preserve_conflict(remote: String) -> bool:
    if meta.get("conflict",false):error="CONFLICT_PRESERVED";return false
    var folder=path.get_base_dir().path_join("conflicts").path_join(uuid())
    if DirAccess.make_dir_recursive_absolute(folder)!=OK:return false
    if FileAccess.file_exists(path) and DirAccess.copy_absolute(path,folder.path_join("local.json"))!=OK:return false
    if remote!="" and not atomic(folder.path_join("server.json"),remote):return false
    error="CONFLICT_PRESERVED";meta.conflict=true
    return persist()

func accept_open(reply: Dictionary, legacy: String) -> bool:
    error=str(reply.get("status","NETWORK"))
    if error!="OK":return false
    var remote=str(reply.document) if reply.get("document")!=null else ""
    if remote!="" and not compatible_document(remote):error="UPDATE_REQUIRED";return false
    if meta.get("conflict",false):error="CONFLICT_PRESERVED";return false
    if meta.dirty and int(reply.version)!=int(meta.version):
        if str(reply.get("last_request",""))==meta.request and remote.sha256_text()==meta.pending_sha and FileAccess.get_sha256(path)==meta.pending_sha:
            meta.dirty=false;meta.request="";meta.pending_sha=""
        else:
            preserve_conflict(remote);return false
    var store=Store.new()
    # Establish the lease journal before first import so a killed migration can
    # restart using the original copy rather than an untracked playable file.
    meta.leased=true
    if not persist():return false
    if not meta.dirty and remote!="":
        # Validate a separate file before touching the playable local copy.
        if not atomic(path+".download",remote) or store.read_one(path+".download").is_empty():error="INVALID_REMOTE_SAVE";return false
        if FileAccess.file_exists(path) and DirAccess.copy_absolute(path,path+".before-cloud.backup")!=OK:error="LOCAL_BACKUP_FAILED";return false
        if not atomic(path,remote):error="LOCAL_SAVE_FAILED";return false
    elif remote=="" and not FileAccess.file_exists(path) and FileAccess.file_exists(legacy):
        var state=store.read_one(legacy)
        if state.is_empty():error="LEGACY_SAVE_"+store.last_status;return false
        if str(state.get("content_version",""))!=compatibility.trim_prefix("schema2:"):error="UPDATE_REQUIRED";return false
        if not atomic(path+".original-pc",FileAccess.get_file_as_string(legacy)):error="LEGACY_COPY_FAILED";return false
        if not store.write_state(path,state):error="LEGACY_COPY_FAILED";return false
        meta.dirty=true
    meta.version=int(reply.version);meta.leased=true
    error="OK"
    return persist()

func upload_request() -> Dictionary:
    if meta.get("conflict",false):error="CONFLICT_PRESERVED";return {}
    if not meta.get("leased",false) or not FileAccess.file_exists(path):return {}
    var store=Store.new()
    if store.read_one(path).is_empty():error="INVALID_LOCAL_SAVE";return {}
    var text=FileAccess.get_file_as_string(path)
    if not compatible_document(text):error="UPDATE_REQUIRED";return {}
    if meta.request=="" or meta.pending_sha!=text.sha256_text():meta.request=uuid();meta.pending_sha=text.sha256_text()
    meta.dirty=true
    if not persist():return {}
    return {"p_device":device,"p_compatibility":compatibility,"p_base":int(meta.version),"p_request":meta.request,"p_document":text,"p_release":true}

func accept_upload(reply: Dictionary) -> bool:
    error=str(reply.get("status","NETWORK"))
    if error=="CONFLICT":preserve_conflict(str(reply.get("document","")));return false
    if error!="OK":return false
    meta.version=int(reply.version);meta.dirty=false;meta.leased=false;meta.request="";meta.pending_sha=""
    return persist()
