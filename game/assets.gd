extends RefCounted
## Builds real AtlasTexture and TileSet resources for all 14,835 uploaded tiles.
## Pixels are always external to the public checkout.

var tile_set = TileSet.new()
var tiles = {}
var textures = {}
var actor_data = {}
var used_tiles = {}
var used_frames = {}
var folder = ""

func load_directory(path: String) -> bool:
    folder = path
    tile_set.tile_size = Vector2i(24,24)
    var manifest_path=folder.path_join("tiles/MANIFEST.json")
    if not FileAccess.file_exists(manifest_path):return false
    var manifest=JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
    if typeof(manifest)!=TYPE_DICTIONARY or typeof(manifest.get("groups"))!=TYPE_ARRAY:return false
    var pins={}
    for group in manifest.groups:pins[group.group]=group
    var source_id = 0
    for g in ["A","B","C"]:
        if not pins.has(g):return false
        var png_path=folder.path_join("tiles/Tile%s_palette0_atlas.png" % g)
        var map_path=folder.path_join("tiles/Tile%s_frame_map.json" % g)
        if not FileAccess.file_exists(png_path) or not FileAccess.file_exists(map_path):return false
        if FileAccess.get_sha256(png_path)!=pins[g].atlas_sha256 or FileAccess.get_sha256(map_path)!=pins[g].map_sha256:return false
        var image = Image.new()
        if image.load(folder.path_join("tiles/Tile%s_palette0_atlas.png" % g)) != OK:
            return false
        var texture = ImageTexture.create_from_image(image)
        var table = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("tiles/Tile%s_frame_map.json" % g)))
        if typeof(table)!=TYPE_DICTIONARY or typeof(table.get("frames"))!=TYPE_ARRAY:return false
        var counts={"A":4897,"B":2973,"C":6965}
        if int(table.get("count",0))!=counts[g] or table.frames.size()!=counts[g]:return false
        if image.get_width()!=3072 or image.get_height()!=ceili(float(counts[g])/128)*24:return false
        var source = TileSetAtlasSource.new()
        source.texture = texture
        source.texture_region_size = Vector2i(24,24)
        tile_set.add_source(source,source_id)
        var index=0
        for f in table.frames:
            if int(f.i)!=index or int(f.x)!=index%128*24 or int(f.y)!=int(index/128)*24:return false
            var coordinates = Vector2i(int(f.i)%128,int(f.i)/128)
            source.create_tile(coordinates)
            var region = AtlasTexture.new()
            region.atlas = texture
            region.region = Rect2(f.x,f.y,24,24)
            tiles[g + ":" + str(int(f.i))] = region
            index+=1
        source_id += 1
    if not FileAccess.file_exists(folder.path_join("actors.json")):return false
    var parsed=JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("actors.json")))
    if typeof(parsed)!=TYPE_DICTIONARY:return false
    actor_data = parsed
    for key in actor_data:
        var spec = actor_data[key]
        if typeof(spec) == TYPE_DICTIONARY and spec.has("path"):
            if not FileAccess.file_exists(folder.path_join(spec.path)) or FileAccess.get_sha256(folder.path_join(spec.path))!=spec.sha256:return false
            var image = Image.new()
            if image.load(folder.path_join(spec.path)) != OK:
                return false
            for f in spec.frames:
                var r=f.region
                if r[0]<0 or r[1]<0 or r[2]<=0 or r[3]<=0 or r[0]+r[2]>image.get_width() or r[1]+r[3]>image.get_height():return false
            textures[key] = ImageTexture.create_from_image(image)
    return tiles.size() == 14835

func tile(id: String) -> Texture2D:
    used_tiles[id] = int(used_tiles.get(id,0)) + 1
    return tiles.get(id)

func actor_region(key: String, frame: int) -> Rect2:
    var spec = actor_data.get(key,{})
    var frames = spec.get("frames",[])
    if frame < 0 or frame >= frames.size():
        return Rect2()
    used_frames[key + ":" + str(frame)] = true
    var r = frames[frame].region
    return Rect2(r[0],r[1],r[2],r[3])
