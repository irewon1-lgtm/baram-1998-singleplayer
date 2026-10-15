extends RefCounted
const Facing=preload("res://facing.gd")
## Work schema 1 renderer. Metadata stays separate; PNG pages load on demand.
var content
var metadata_cache={}
var texture_cache={}
var frame_textures={}
var previous_frame_textures={}
var texture_bytes=0
var soft_limit=268435456
var used_frames={}
var tile_cache={}
var icon_cache={}
var last_error={}

func _init(registry):content=registry

func begin_frame():
    # Canvas draw commands retain a texture RID, not its Resource lifetime.
    # Keep pages alive until Godot clears these commands for the next draw,
    # even when another page evicts them from the bounded reuse cache.
    previous_frame_textures=frame_textures
    frame_textures={}

func file_path(asset_id: String, member: String="") -> String:
    var info=content.assets.get(asset_id,{})
    if member!="":
        var bundle=content.definition(asset_id).get("acquisition",{}).get("bundle_id","")
        info=content.assets.get("bundle_file:"+bundle+":"+member,info if member==content.definition(asset_id).get("acquisition",{}).get("member","") else {})
    return "" if info.is_empty() else content.release_root.path_join("files").path_join(info.stored_path)

func metadata(asset_id: String) -> Dictionary:
    var data=content.definition(asset_id)
    var sheet_id=data.get("metadata",{}).get("sheet_id",asset_id)
    var path=file_path(sheet_id)
    if path=="":return {}
    if not metadata_cache.has(path):
        var parser=JSON.new()
        if parser.parse(FileAccess.get_file_as_string(path))!=OK:last_error={"code":"WORK_FRAME_METADATA","asset_id":asset_id,"file":path};return {}
        metadata_cache[path]=parser.data
    return metadata_cache[path]

func texture(asset_id: String, member: String) -> Texture2D:
    var path=file_path(asset_id,member)
    if path=="":last_error={"code":"WORK_PAGE_NOT_ACQUIRED","asset_id":asset_id,"member":member};return null
    var bundle=content.definition(asset_id).get("acquisition",{}).get("bundle_id","")
    var info=content.assets.get("bundle_file:"+bundle+":"+member,{})
    var hash=info.get("sha256","")
    if hash=="":return null
    if frame_textures.has(hash):return frame_textures[hash]
    if previous_frame_textures.has(hash):
        # A visible page may exceed the reuse budget together with other
        # visible actors. Reuse last draw's live resource instead of decoding
        # it again each frame; unrequested pages expire on the following draw.
        frame_textures[hash]=previous_frame_textures[hash]
        return frame_textures[hash]
    if texture_cache.has(hash):
        texture_cache[hash].used=Time.get_ticks_msec()
        frame_textures[hash]=texture_cache[hash].texture
        return frame_textures[hash]
    var image=Image.new()
    if image.load(path)!=OK:last_error={"code":"WORK_PAGE_DECODE","asset_id":asset_id,"file":path};return null
    var bytes=image.get_width()*image.get_height()*4
    while texture_bytes+bytes>soft_limit and not texture_cache.is_empty():
        var keys=texture_cache.keys();keys.sort_custom(func(a,b):return texture_cache[a].used<texture_cache[b].used)
        texture_bytes-=int(texture_cache[keys[0]].bytes);texture_cache.erase(keys[0])
    var result=ImageTexture.create_from_image(image)
    texture_cache[hash]={"texture":result,"bytes":bytes,"used":Time.get_ticks_msec()};texture_bytes+=bytes
    frame_textures[hash]=result
    return result

func frame_index(asset_id: String, action: String, direction: int, elapsed_ms: int) -> int:
    var data=content.definition(asset_id)
    var meta=data.get("metadata",{})
    var sequence=meta.get("animations",{}).get(action,{})
    if sequence.is_empty():return -1
    var count=int(sequence.get("frames_per_direction",0));var step=int(sequence.get("frame_ms",0))
    if count<=0 or step<=0 or direction<0 or direction>=int(sequence.get("directions",4)):return -1
    return int(meta.get("starting_frame",0))+int(sequence.get("offset",0))+Facing.sprite(direction)*count+(int(elapsed_ms/step)%count)

func draw_frame(canvas, asset_id: String, index: int, feet: Vector2, opacity: float=1.0) -> bool:
    var data=content.definition(asset_id);var meta=data.get("metadata",{})
    var sheet_id=meta.get("sheet_id",asset_id)
    var table=metadata(asset_id)
    var frames=table.get("frames",[])
    if index<0 or index>=frames.size():last_error={"code":"WORK_FRAME_RANGE","asset_id":asset_id,"frame":index};return false
    var frame=frames[index];var region=frame.get("region",[]);var pivot=frame.get("pivot",table.get("foot_pivot",[]))
    if region.size()!=4 or pivot.size()!=2:last_error={"code":"WORK_FRAME_PIVOT","asset_id":asset_id,"frame":index};return false
    var page=texture(sheet_id,frame.path)
    if page==null:return false
    canvas.draw_texture_rect_region(page,Rect2(feet-Vector2(pivot[0],pivot[1])*2,Vector2(region[2],region[3])*2),Rect2(region[0],region[1],region[2],region[3]),Color(1,1,1,opacity))
    used_frames[sheet_id+":"+str(index)]=true
    return true

func draw_animation(canvas, asset_id: String, action: String, direction: int, elapsed_ms: int, feet: Vector2, opacity: float=1.0) -> bool:
    var index=frame_index(asset_id,action,direction,elapsed_ms)
    return index>=0 and draw_frame(canvas,asset_id,index,feet,opacity)

func effect_frame(asset_id: String, layer: String, elapsed_ms: int, lifetime_ms: int=2000) -> Dictionary:
    var meta=content.definition(asset_id).get("metadata",{})
    var sequence=meta.get(layer,[])
    if sequence.is_empty() or elapsed_ms>=lifetime_ms:return {}
    var repeat=meta.get("repeat",{})
    var from=int(repeat.get("RepeatFrontFrom" if layer=="front" else "RepeatBackFrom",-1))
    var to=int(repeat.get("RepeatFrontTo" if layer=="front" else "RepeatBackTo",-1))
    var index=0;var remaining=elapsed_ms
    # A declared game lifetime bounds original repeat windows; no permanent
    # effect timer or per-frame event connection is created.
    for step in range(4096):
        if index>=sequence.size():return {}
        var duration=int(sequence[index].delay_ms)
        if duration<=0:return {}
        if remaining<duration:return sequence[index]
        remaining-=duration;index+=1
        if from>=0 and to>=from and to<sequence.size() and index>to:index=from
    last_error={"code":"WORK_EFFECT_BUDGET","asset_id":asset_id};return {}

func draw_effect(canvas, asset_id: String, layer: String, elapsed_ms: int, feet: Vector2, lifetime_ms: int) -> bool:
    var frame=effect_frame(asset_id,layer,elapsed_ms,lifetime_ms)
    if frame.is_empty():return false
    var sheet=content.definition(asset_id).get("metadata",{}).get("sheet_id","")
    # EPF stencil alpha remains in the PNG. Unknown original Alpha/Light
    # parameters remain metadata; they are not guessed to be opacity 0.
    return draw_frame(canvas,sheet,int(frame.frame),feet)

func tile(asset_id: String, index: int) -> Texture2D:
    var key=asset_id+":"+str(index)
    if tile_cache.has(key):used_frames[key]=true;return tile_cache[key]
    var table=metadata(asset_id);var frames=table.get("frames",[])
    if index<0 or index>=frames.size():return null
    var frame=frames[index];var page=texture(asset_id,frame.path)
    if page==null:return null
    var result=AtlasTexture.new();result.atlas=page
    var r=frame.region;result.region=Rect2(r[0],r[1],r[2],r[3])
    used_frames[asset_id+":"+str(index)]=true
    tile_cache[key]=result
    return result

func icon(asset_id: String, index: int) -> Texture2D:
    var key=asset_id+":"+str(index)
    if icon_cache.has(key):used_frames[key]=true;return icon_cache[key]
    var frames=metadata(asset_id).get("frames",[])
    if index<0 or index>=frames.size():return null
    var frame=frames[index];var rect=frame.get("original_rect",[]);var region=frame.region;var pivot=frame.pivot
    if rect.size()!=4 or rect[2]<=0 or rect[3]<=0:return null
    var page=texture(asset_id,frame.path)
    if page==null:return null
    var result=AtlasTexture.new();result.atlas=page
    result.region=Rect2(region[0]+pivot[0]+rect[0],region[1]+pivot[1]+rect[1],rect[2],rect[3])
    icon_cache[key]=result;used_frames[key]=true;return result
