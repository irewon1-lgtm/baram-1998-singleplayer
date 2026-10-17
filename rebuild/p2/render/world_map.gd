extends Control
## Small overview with logical-cell markers; no world-sized GPU texture.
signal cell_selected(cell: Vector2i)
var assets: RefCounted
var definition: Dictionary={}
var character: Dictionary={}
var npcs: Array=[]
func _ready() -> void:
	custom_minimum_size=Vector2(280,250)
	gui_input.connect(func(event):
		if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:
			var r:=_rect();var point: Vector2=(event.position-r.position)/r.size
			if point.x>=0 and point.y>=0 and point.x<1 and point.y<1:cell_selected.emit(Vector2i(int(point.x*int(definition.width)),int(point.y*int(definition.height)))))
func _rect() -> Rect2:
	var extent:=Vector2(float(definition.get("width",1)),float(definition.get("height",1)))
	var scale:=minf(size.x/extent.x,size.y/extent.y)
	return Rect2((size-extent*scale)*0.5,extent*scale)
func _point(x: float,y: float,r: Rect2) -> Vector2:
	return r.position+Vector2((x+0.5)/float(definition.width),(y+0.5)/float(definition.height))*r.size
func _draw() -> void:
	if definition.is_empty() or assets==null:return
	var r:=_rect();draw_rect(r,Color("18221e"))
	var path:=str(definition.get("overview_png",definition.get("floor_png","")))
	if not path.is_empty():
		var tex: Texture2D=assets.texture(path)
		if tex!=null:draw_texture_rect(tex,r,false)
	for exit in definition.get("exits",[]):draw_circle(_point(exit.x,exit.y,r),3,Color("e2bf72"))
	for npc in npcs:draw_circle(_point(npc.x,npc.y,r),3,Color("7cd9ed"))
	if not character.is_empty():
		var p:=_point(character.x,character.y,r)
		draw_circle(p,5,Color.BLACK);draw_circle(p,3,Color("97ffac"));draw_line(p-Vector2(7,0),p+Vector2(7,0),Color.WHITE);draw_line(p-Vector2(0,7),p+Vector2(0,7),Color.WHITE)
