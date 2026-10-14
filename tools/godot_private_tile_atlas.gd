extends RefCounted
class_name BaramPrivateTileAtlas

## Runtime loader for user-supplied, privately stored 24x24 tile atlases.
## No copyrighted image bytes are included in this script.
## Not yet tested inside the final game scene.

const TILE_SIZE := 24
const COLUMNS := 128
const FRAME_COUNTS := {"A": 4897, "B": 2973, "C": 6965}

var _textures: Dictionary = {}
var _tables: Dictionary = {}

func load_directory(folder: String) -> bool:
    _textures.clear()
    _tables.clear()
    for group in ["A", "B", "C"]:
        var image_path := folder.path_join("Tile%s_palette0_atlas.png" % group)
        var table_path := folder.path_join("Tile%s_frame_map.json" % group)
        var image := Image.new()
        if image.load(image_path) != OK:
            push_error("Private atlas not readable: " + image_path)
            return false
        if image.get_width() != TILE_SIZE * COLUMNS:
            push_error("Unexpected atlas width: " + image_path)
            return false
        if not FileAccess.file_exists(table_path):
            push_error("Tile mapping file missing: " + table_path)
            return false
        var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(table_path))
        if typeof(parsed) != TYPE_DICTIONARY:
            push_error("Invalid tile mapping JSON: " + table_path)
            return false
        var table: Dictionary = parsed
        if table.get("group") != group or int(table.get("count", -1)) != int(FRAME_COUNTS[group]):
            push_error("Tile mapping count mismatch: " + table_path)
            return false
        if typeof(table.get("frames")) != TYPE_ARRAY:
            push_error("Tile mapping frame list missing: " + table_path)
            return false
        if table["frames"].size() != int(FRAME_COUNTS[group]):
            push_error("Tile mapping frame list has wrong length: " + table_path)
            return false
        _textures[group] = ImageTexture.create_from_image(image)
        _tables[group] = table
    return true

func texture_for(group: String) -> Texture2D:
    return _textures.get(group) as Texture2D

func region_for(group: String, index: int) -> Rect2:
    if not _tables.has(group):
        return Rect2()
    var frames: Array = _tables[group]["frames"]
    if index < 0 or index >= frames.size():
        return Rect2()
    var frame: Dictionary = frames[index]
    return Rect2(float(frame["x"]), float(frame["y"]), TILE_SIZE, TILE_SIZE)

func configure_sprite(sprite: Sprite2D, group: String, index: int) -> bool:
    var texture := texture_for(group)
    if texture == null or index < 0 or index >= int(FRAME_COUNTS.get(group, 0)):
        return false
    sprite.texture = texture
    sprite.region_enabled = true
    sprite.region_rect = region_for(group, index)
    sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    sprite.centered = false
    return true