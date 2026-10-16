extends PanelContainer
## Reconstructed parchment geometry from the user's layout references.
## Not a decoded original UI mask or a historical pixel-identical claim.
func _ready() -> void:
	var blank := StyleBoxEmpty.new()
	for side in [SIDE_LEFT,SIDE_RIGHT]: blank.set_content_margin(side,18)
	for side in [SIDE_TOP,SIDE_BOTTOM]: blank.set_content_margin(side,24)
	add_theme_stylebox_override("panel",blank)
	resized.connect(queue_redraw)

func _draw() -> void:
	var outer := Rect2(Vector2.ZERO,size)
	draw_style_box(_style(Color("382010"),Color("97602c"),18,3),outer)
	var paper := outer.grow(-10)
	draw_style_box(_style(Color("bd965b"),Color("70431f"),25,4),paper)
	draw_style_box(_style(Color("d4b477"),Color("ddbc7e"),18,1),paper.grow(-7))
	for y in range(20,int(size.y)-18,5):
		draw_line(Vector2(24,y),Vector2(size.x-24,y+1),Color(0.37,0.22,0.08,0.035),1)
	for x in [26.0,size.x-26.0]:
		for y in [16.0,size.y-16.0]:
			draw_arc(Vector2(x,y),11,0.2,TAU-0.4,20,Color("774822"),3,true)
	for y in [8.0,size.y-8.0]:
		draw_line(Vector2(30,y),Vector2(size.x-30,y),Color("68401d"),7,true)
		draw_line(Vector2(32,y-2),Vector2(size.x-32,y-2),Color("e2bd78"),2,true)

func _style(bg: Color, border: Color, radius: int, width: int) -> StyleBoxFlat:
	var s:=StyleBoxFlat.new();s.bg_color=bg;s.border_color=border
	s.set_border_width_all(width);s.set_corner_radius_all(radius)
	return s
