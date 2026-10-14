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
    var source_id = 0
    for g in ["A","B","C"]:
        var image = Image.new()
        if image.load(folder.path_join("tiles/Tile%s_palette0_atlas.png" % g)) != OK:
            return false
        var texture = ImageTexture.create_from_image(image)
        var table = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("tiles/Tile%s_frame_map.json" % g)))
        var source = TileSetAtlasSource.new()
        source.texture = texture
        source.texture_region_size = Vector2i(24,24)
        tile_set.add_source(source,source_id)
        for f in table.frames:
            var coordinates = Vector2i(int(f.i)%128,int(f.i)/128)
            source.create_tile(coordinates)
            var region = AtlasTexture.new()
            region.atlas = texture
            region.region = Rect2(f.x,f.y,24,24)
            tiles[g + ":" + str(int(f.i))] = region
        source_id += 1
    actor_data = JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("actors.json")))
    for key in actor_data:
        var spec = actor_data[key]
        if typeof(spec) == TYPE_DICTIONARY and spec.has("path"):
            var image = Image.new()
            if image.load(folder.path_join(spec.path)) != OK:
                return false
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
