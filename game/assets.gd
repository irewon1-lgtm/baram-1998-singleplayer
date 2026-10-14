extends RefCounted
## Every original tile ID and hash is retained. Decode/verify on a worker;
## create GPU textures on the main thread and regions only when drawn.
var tile_set=TileSet.new()
var tiles={}
var textures={}
var actor_data={}
var used_tiles={}
var used_frames={}
var folder=""
var source_aliases={}
var tile_cache={}
var last_error=""
var loading_thread

func reject(message: String) -> Dictionary:
    last_error=message
    return {"error":message}

func prepare_directory(path: String, progress: Callable=Callable()) -> Dictionary:
    var manifest_path=path.path_join("tiles/MANIFEST.json")
    if not FileAccess.file_exists(manifest_path):return reject("TILE_MANIFEST_MISSING")
    var manifest=JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
    if typeof(manifest)!=TYPE_DICTIONARY or typeof(manifest.get("groups"))!=TYPE_ARRAY:return reject("TILE_MANIFEST_FORMAT")
    var pins={};var groups=[]
    for group in manifest.groups:pins[group.group]=group
    var counts={"A":4897,"B":2973,"C":6965}
    for g in ["A","B","C"]:
        if progress.is_valid():progress.call("Checking tile atlas "+g)
        if not pins.has(g):return reject("TILE_GROUP_MISSING: "+g)
        var png_path=path.path_join("tiles/Tile%s_palette0_atlas.png"%g)
        var map_path=path.path_join("tiles/Tile%s_frame_map.json"%g)
        if not FileAccess.file_exists(png_path) or not FileAccess.file_exists(map_path):return reject("TILE_FILES_MISSING: "+g)
        if FileAccess.get_sha256(png_path)!=pins[g].atlas_sha256 or FileAccess.get_sha256(map_path)!=pins[g].map_sha256:return reject("TILE_HASH: "+g)
        var image=Image.new()
        if image.load(png_path)!=OK:return reject("TILE_DECODE: "+g)
        var table=JSON.parse_string(FileAccess.get_file_as_string(map_path))
        if typeof(table)!=TYPE_DICTIONARY or typeof(table.get("frames"))!=TYPE_ARRAY:return reject("TILE_TABLE: "+g)
        if int(table.get("count",0))!=counts[g] or table.frames.size()!=counts[g]:return reject("TILE_COUNT: "+g)
        if image.get_width()!=3072 or image.get_height()!=ceili(float(counts[g])/128)*24:return reject("TILE_DIMENSIONS: "+g)
        var ids=[]
        for i in range(table.frames.size()):
            var f=table.frames[i]
            if int(f.i)!=i or int(f.x)!=i%128*24 or int(f.y)!=int(i/128)*24:return reject("TILE_FRAME: "+g)
            ids.append(g+":"+str(i))
        groups.append({"image":image,"ids":ids})
    var actors_path=path.path_join("actors.json")
    if not FileAccess.file_exists(actors_path):return reject("ACTORS_MISSING")
    var parsed=JSON.parse_string(FileAccess.get_file_as_string(actors_path))
    if typeof(parsed)!=TYPE_DICTIONARY:return reject("ACTORS_FORMAT")
    var actors=[]
    for key in parsed:
        var spec=parsed[key]
        if typeof(spec)!=TYPE_DICTIONARY or not spec.has("path"):continue
        var member=path.path_join(spec.path)
        if not FileAccess.file_exists(member) or FileAccess.get_sha256(member)!=spec.sha256:return reject("ACTOR_HASH: "+key)
        var image=Image.new()
        if image.load(member)!=OK:return reject("ACTOR_DECODE: "+key)
        for f in spec.frames:
            var r=f.region
            if r[0]<0 or r[1]<0 or r[2]<=0 or r[3]<=0 or r[0]+r[2]>image.get_width() or r[1]+r[3]>image.get_height():return reject("ACTOR_FRAME: "+key)
        actors.append({"key":key,"image":image})
    var aliases={}
    var registry_path=path.path_join("source_tiles/registry.json")
    if FileAccess.file_exists(registry_path):
        if progress.is_valid():progress.call("Checking original tile records")
        var registry=JSON.parse_string(FileAccess.get_file_as_string(registry_path))
        if typeof(registry)!=TYPE_DICTIONARY or registry.get("source_dat_sha256","")!="f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7":return reject("SOURCE_TILE_REGISTRY")
        counts={"A":9922,"B":8938,"C":16409}
        var originals={};var indices={"A":0,"B":0,"C":0}
        for g in registry.groups:
            if not counts.has(g.group) or int(g.count)!=counts[g.group]:return reject("SOURCE_TILE_COUNT")
            var member=path.path_join(g.path)
            if not FileAccess.file_exists(member) or FileAccess.get_sha256(member)!=g.sha256:return reject("SOURCE_TILE_HASH: "+g.group)
            var image=Image.new()
            if image.load(member)!=OK or image.get_width()!=3072 or image.get_height()!=ceili(float(g.count)/128)*24:return reject("SOURCE_TILE_DECODE: "+g.group)
            var row={"image":image,"ids":[]}
            originals[g.group]=row;groups.append(row)
        for f in registry.frames:
            if not originals.has(f.group) or int(f.index)!=indices[f.group]:return reject("SOURCE_TILE_FRAME")
            originals[f.group].ids.append(f.asset_id)
            var equal=f.get("uploaded_equal_ids",[])
            if not equal.is_empty():aliases[f.asset_id]=equal
            indices[f.group]+=1
        if indices!=counts:return reject("SOURCE_TILE_TOTAL")
    return {"groups":groups,"actors":actors,"actor_data":parsed,"aliases":aliases}

func install_source(row: Dictionary):
    var source=TileSetAtlasSource.new()
    source.texture=ImageTexture.create_from_image(row.image)
    source.texture_region_size=Vector2i(24,24)
    tile_set.add_source(source,tile_set.get_source_count())
    return source

func load_directory(path: String) -> bool:
    folder=path
    var data=prepare_directory(path)
    if data.has("error"):return false
    tile_set.tile_size=Vector2i(24,24)
    for row in data.groups:
        var source=install_source(row)
        for i in range(row.ids.size()):tiles[row.ids[i]]=[source,i]
    for row in data.actors:textures[row.key]=ImageTexture.create_from_image(row.image)
    actor_data=data.actor_data;source_aliases=data.aliases
    return tiles.size()>=14835

func load_directory_async(path: String, tree: SceneTree, progress: Callable) -> bool:
    folder=path
    loading_thread=Thread.new()
    if loading_thread.start(prepare_directory.bind(path,progress))!=OK:last_error="ASSET_THREAD";return false
    while loading_thread.is_alive():await tree.process_frame
    var data=loading_thread.wait_to_finish()
    loading_thread=null
    if typeof(data)!=TYPE_DICTIONARY or data.has("error"):return false
    tile_set.tile_size=Vector2i(24,24)
    for row in data.groups:
        progress.call("Preparing graphics",tiles.size(),50104)
        await tree.process_frame
        var source=install_source(row)
        for i in range(row.ids.size()):
            tiles[row.ids[i]]=[source,i]
            if i%512==0:await tree.process_frame
    for row in data.actors:
        textures[row.key]=ImageTexture.create_from_image(row.image)
        await tree.process_frame
    actor_data=data.actor_data;source_aliases=data.aliases
    return tiles.size()>=14835

func tile(id: String) -> Texture2D:
    used_tiles[id]=int(used_tiles.get(id,0))+1
    for alias in source_aliases.get(id,[]):used_tiles[alias]=int(used_tiles.get(alias,0))+1
    if not tiles.has(id):return null
    if not tile_cache.has(id):
        var spec=tiles[id];var index=int(spec[1])
        var at=Vector2i(index%128,int(index/128))
        spec[0].create_tile(at)
        var region=AtlasTexture.new()
        region.atlas=spec[0].texture;region.region=Rect2(at.x*24,at.y*24,24,24)
        tile_cache[id]=region
    return tile_cache[id]

func actor_region(key: String, frame: int) -> Rect2:
    var spec=actor_data.get(key,{})
    var frames=spec.get("frames",[])
    if frame<0 or frame>=frames.size():return Rect2()
    used_frames[key+":"+str(frame)]=true
    var r=frames[frame].region
    return Rect2(r[0],r[1],r[2],r[3])
