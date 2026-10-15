extends RefCounted
## Pure file/JSON work runs off the window thread. Cached maps are generated
## from the same merge_world() code at build time and are never hand edited.
var result = {}

static func compact_world(world):
    # Packed rows preserve each cell while avoiding a Variant allocation per
    # tile/collision cell across 423 maps. Saves do not serialize map layouts.
    for map in world.maps:
        for y in range(map.ground.size()):map.ground[y]=PackedStringArray(map.ground[y])
        for y in range(map.blocked.size()):
            var row=map.blocked[y];var packed=PackedByteArray();packed.resize(row.size())
            for x in range(row.size()):packed[x]=1 if row[x] else 0
            map.blocked[y]=packed
        if map.has("collision_masks"):
            for y in range(map.collision_masks.size()):map.collision_masks[y]=PackedByteArray(map.collision_masks[y])
    return world

func prepare(content, content_folder: String, world_path: String, cache_root: String):
    var began = Time.get_ticks_msec()
    if not content.load_directory(content_folder):
        result = {"ok":false,"error":content.last_error};return
    var content_ms = Time.get_ticks_msec()-began
    var world_hash = FileAccess.get_sha256(world_path)
    var cache = cache_root.path_join("manifest.json")
    var world = {}
    var cached = false
    if FileAccess.file_exists(cache):
        var manifest = JSON.parse_string(FileAccess.get_file_as_string(cache))
        var binary = cache_root.path_join("world.bin")
        if typeof(manifest)!=TYPE_DICTIONARY or manifest.get("format","")!="BARAM_WORLD_CACHE_V1" or manifest.get("content_version","")!=content.version or manifest.get("source_world_sha256","")!=world_hash or not FileAccess.file_exists(binary) or FileAccess.get_sha256(binary)!=manifest.get("sha256",""):
            result={"ok":false,"error":{"code":"WORLD_CACHE_MISMATCH"}};return
        if manifest.get("compression","") not in ["","zstd"]:
            result={"ok":false,"error":{"code":"WORLD_CACHE_COMPRESSION"}};return
        var file = FileAccess.open_compressed(binary,FileAccess.READ) if manifest.get("compression","")=="zstd" else FileAccess.open(binary,FileAccess.READ)
        if file==null:result={"ok":false,"error":{"code":"WORLD_CACHE_READ"}};return
        world = file.get_var(false) # Never deserialize executable objects.
        cached = true
    else:
        var source = JSON.parse_string(FileAccess.get_file_as_string(world_path))
        if typeof(source)!=TYPE_DICTIONARY:
            result={"ok":false,"error":{"code":"WORLD_JSON"}};return
        world = compact_world(content.merge_world(source))
    if typeof(world)!=TYPE_DICTIONARY or not world.has("maps") or world.maps.is_empty():
        result={"ok":false,"error":{"code":"WORLD_FORMAT"}};return
    result={"ok":true,"world":world,"content_ms":content_ms,
        "world_ms":Time.get_ticks_msec()-began-content_ms,"cache_used":cached}
