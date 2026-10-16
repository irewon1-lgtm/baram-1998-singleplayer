extends Control
## The same original-asset canvas is used by inspection, equipment preview and capture.
var content: RefCounted
var layers: Array = []
var source_size := Vector2(512, 512)
var focus := Vector2(256, 256)
var zoom := 1.0
var last_drawn: Array[String] = []

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
	if content == null:
		return
	var offset := size * 0.5 - focus * zoom
	for entry in layers:
		var path: String = entry.get("path", "")
		var tex: Texture2D = content.texture(path)
		if tex == null:
			continue
		var pos := Vector2(float(entry.get("x", 0)), float(entry.get("y", 0)))
		var s := float(entry.get("scale", 1.0)) * zoom
		draw_texture_rect(tex, Rect2(offset + pos * zoom, tex.get_size() * s), false)
		last_drawn.append(path)
