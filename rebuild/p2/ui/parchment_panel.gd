extends PanelContainer
## Live nine-part assembly of the already decoded Korean DLGNEW02 scroll.
## These are original pixels, not smoothed rounded Godot geometry. Missing HUD
## layout is reconstructed around the source parchment/wood material.
const ClassicSkin=preload("res://ui/classic_skin.gd")
@export var compact:=false
func _ready() -> void:
	texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
	var blank:=StyleBoxEmpty.new()
	for edge in [SIDE_LEFT,SIDE_RIGHT]:blank.set_content_margin(edge,13 if compact else 20)
	for edge in [SIDE_TOP,SIDE_BOTTOM]:blank.set_content_margin(edge,9 if compact else 22)
	add_theme_stylebox_override("panel",blank)
	resized.connect(queue_redraw)

func _piece(destination: Rect2, source: Rect2) -> void:
	if destination.size.x>0 and destination.size.y>0:
		draw_texture_rect_region(ClassicSkin.source,destination,source)

func _draw() -> void:
	if ClassicSkin.source==null:
		draw_rect(Rect2(Vector2.ZERO,size),Color("ad894d"))
		return
	var edge:=12.0 if compact else 20.0
	# Keep border thickness fixed; stretch long strips, never the full source UI
	# with its character-creation text and unrelated guardians.
	var inner:=Rect2(Vector2(edge-3,edge-3),size-Vector2.ONE*(edge-3)*2)
	draw_texture_rect(ClassicSkin.parchment(),inner,true)
	_piece(Rect2(0,edge,edge,size.y-edge*2),Rect2(7,28,18,300))
	_piece(Rect2(size.x-edge,edge,edge,size.y-edge*2),Rect2(377,28,18,300))
	_piece(Rect2(edge,0,size.x-edge*2,edge),Rect2(27,0,346,22))
	_piece(Rect2(edge,size.y-edge,size.x-edge*2,edge),Rect2(27,350,346,23))
	_piece(Rect2(0,0,edge,edge),Rect2(0,0,28,25))
	_piece(Rect2(size.x-edge,0,edge,edge),Rect2(374,0,28,25))
	_piece(Rect2(0,size.y-edge,edge,edge),Rect2(0,348,28,25))
	_piece(Rect2(size.x-edge,size.y-edge,edge,edge),Rect2(374,348,28,25))
