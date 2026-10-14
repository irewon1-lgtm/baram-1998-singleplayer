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
var source_aliases = {}
var tile_sources = {}
var tile_cache = {}

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
            var id = g + ":" + str(int(f.i))
            tiles[id] = Rect2(f.x,f.y,24,24)
            tile_sources[id] = source
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
    if FileAccess.file_exists(folder.path_join("source_tiles/registry.json")):
        if not load_source_tiles():return false
    return tiles.size() >= 14835

func load_source_tiles() -> bool:
    var registry=JSON.parse_string(FileAccess.get_file_as_string(folder.path_join("source_tiles/registry.json")))
    if typeof(registry)!=TYPE_DICTIONARY or registry.get("source_dat_sha256","")!="f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7":return false
    var counts={"A":9922,"B":8938,"C":16409}
    var originals={}
    var next_source=tile_set.get_source_count()
    for g in registry.groups:
        if not counts.has(g.group) or int(g.count)!=counts[g.group]:return false
        var path=folder.path_join(g.path)
        if not FileAccess.file_exists(path) or FileAccess.get_sha256(path)!=g.sha256:return false
        var im=Image.new()
        if im.load(path)!=OK or im.get_width()!=3072 or im.get_height()!=ceili(float(g.count)/128)*24:return false
        var source=TileSetAtlasSource.new()
        source.texture=ImageTexture.create_from_image(im)
        source.texture_region_size=Vector2i(24,24)
        tile_set.add_source(source,next_source)
        next_source+=1
        originals[g.group]=source
    var indices={"A":0,"B":0,"C":0}
    for f in registry.frames:
        if not originals.has(f.group) or int(f.index)!=indices[f.group]:return false
        var i=int(f.index)
        var source=originals[f.group]
        tiles[f.asset_id]=Rect2(i%128*24,int(i/128)*24,24,24)
        tile_sources[f.asset_id]=source
        source_aliases[f.asset_id]=f.get("uploaded_equal_ids",[])
        indices[f.group]+=1
    return indices==counts

func tile(id: String) -> Texture2D:
    # Keep every original frame registered. Build TileSet entries when used;
    # eager create_tile() repeatedly rebuilds atlas bookkeeping for 50k frames.
    if tile_sources.has(id):
        var source = tile_sources[id]
        var coordinates = Vector2i(tiles[id].position/24)
        if not source.has_tile(coordinates):source.create_tile(coordinates)
    used_tiles[id] = int(used_tiles.get(id,0)) + 1
    for alias in source_aliases.get(id,[]):
        used_tiles[alias]=int(used_tiles.get(alias,0))+1 # exact RGBA equivalence, not guessed index conversion
    if not tiles.has(id):return null
    if not tile_cache.has(id):
        var region=AtlasTexture.new()
        region.atlas=tile_sources[id].texture;region.region=tiles[id]
        tile_cache[id]=region
    return tile_cache[id]

func actor_region(key: String, frame: int) -> Rect2:
    var spec = actor_data.get(key,{})
    var frames = spec.get("frames",[])
    if frame < 0 or frame >= frames.size():
        return Rect2()
    used_frames[key + ":" + str(frame)] = true
    var r = frames[frame].region
    return Rect2(r[0],r[1],r[2],r[3])
