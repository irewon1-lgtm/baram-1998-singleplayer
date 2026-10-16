extends Control
## The same original-asset canvas is used by inspection, equipment preview and capture.
var content: RefCounted
var layers: Array = []
var source_size := Vector2(512, 512)
var focus := Vector2(256, 256)
var zoom := 1.0
var last_drawn: Array[String] = []
var last_layer_metadata: Array = []
var draw_errors: Array[String] = []

func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	clip_contents = true
	custom_minimum_size = Vector2(380, 380)
	resized.connect(queue_redraw)

func configure(next_layers: Array, extent: Vector2, center: Vector2, scale_factor: float = 1.0) -> void:
	layers = next_layers
	source_size = extent
	focus = center
	zoom = scale_factor
	queue_redraw()

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("171d21"))
	last_drawn.clear()
	last_layer_metadata.clear()
	draw_errors.clear()
	if content == null:
		return
	if not is_finite(zoom) or zoom <= 0 or zoom > 16 or layers.size() > 4096:
		draw_errors.append("UNSAFE_CANVAS_SCALE_OR_LAYER_COUNT")
		return
	var offset := size * 0.5 - focus * zoom
	for entry in layers:
		var path: String = entry.get("path", "")
		if path.is_empty():
			draw_errors.append("EMPTY_ASSET_REFERENCE_NO_FALLBACK")
			continue
		var pos := Vector2(float(entry.get("x", 0)), float(entry.get("y", 0)))
		var layer_scale := float(entry.get("scale", 1.0))
		var opacity := float(entry.get("opacity", 1.0))
		if not pos.is_finite() or not is_finite(layer_scale) or layer_scale <= 0 or layer_scale > 16 or not is_finite(opacity) or opacity < 0 or opacity > 1:
			draw_errors.append("UNSAFE_LAYER_GEOMETRY_OR_OPACITY: " + path)
			continue
		var tex: Texture2D = content.texture(path)
		if tex == null:
			continue
		var s := layer_scale * zoom
		draw_texture_rect(tex, Rect2(offset + pos * zoom, tex.get_size() * s), false, Color(1, 1, 1, opacity))
		last_drawn.append(path)
		last_layer_metadata.append({"path":path, "opacity":opacity, "original_frame":entry.get("original_frame"), "source_index":entry.get("source_index")})
