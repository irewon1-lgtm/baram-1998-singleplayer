extends "res://render/original_view.gd"
## World images and actors share foot-depth ordering. Text never replaces an actor.
signal world_pressed(tile: Vector2i)
var labels: Array = []
var tile_size := 24.0

func _ready() -> void:
	super._ready()
	mouse_filter = Control.MOUSE_FILTER_STOP
	gui_input.connect(_world_input)

func _world_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var world: Vector2 = (event.position - size * 0.5) / zoom + focus
		world_pressed.emit(Vector2i(floori(world.x / tile_size), floori(world.y / tile_size)))

func _draw() -> void:
	super._draw()
	var offset := size * 0.5 - focus * zoom
	var font := ThemeDB.fallback_font
	for label in labels:
		var pos := offset + Vector2(float(label.x), float(label.y)) * zoom
		var title := str(label.get("text", ""))
		var width := font.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
		# Actor offsets are source pixels around their feet. Label anchors must
		# follow that world scale too, otherwise names sit across faces at zoom>1.
		var head_height := float(label.get("height",34.0 if label.has("hp") else 48.0))
		var baseline := pos + Vector2(-width/2, -head_height*zoom-8)
		draw_string_outline(font, baseline, title, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, 3, Color.BLACK)
		draw_string(font, baseline, title, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(label.get("color", "white")))
		if label.has("hp"):
			var bar := pos + Vector2(-16,-head_height*zoom-3)
			draw_rect(Rect2(bar,Vector2(32,4)),Color("4a2121"))
			draw_rect(Rect2(bar,Vector2(32*clampf(float(label.hp)/maxf(float(label.get("hp_max",1)),1),0,1),4)),Color("82c260"))
