extends Control
## Actual preserved map art; marker coordinates are original tile coordinates.
signal navigate(cell: Vector2i)
var model: RefCounted
var locale: RefCounted
var overview:=false
var magnification:=1.0
var pan:=Vector2.ZERO
var texture: Texture2D
var area:=Rect2()
var press_at:=Vector2.ZERO
var last_at:=Vector2.ZERO
var pointer:=-1
var dragged:=false

func _ready() -> void:
	texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST;mouse_filter=Control.MOUSE_FILTER_STOP
	gui_input.connect(_pointer)
	texture=load("res://p6/art/field10.png" if overview else "res://p6/art/map-"+model.map_id()+".png")
	resized.connect(queue_redraw)

func change_zoom(amount: float) -> void:
	magnification=clampf(magnification+amount,1.0,5.0)
	if magnification==1.0:pan=Vector2.ZERO
	queue_redraw()

func _at(cell: Vector2) -> Vector2:
	var m: Dictionary=model.definitions[model.map_id()]
	return area.position+(cell+Vector2(0.5,0.5))/Vector2(m.width,m.height)*area.size

func _draw() -> void:
	if texture==null:return
	clip_contents=true
	draw_rect(Rect2(Vector2.ZERO,size),Color("473c27"))
	var scale:=minf(size.x/texture.get_width(),size.y/texture.get_height())*magnification
	var dimensions:=texture.get_size()*scale
	pan=pan.clamp(-dimensions/2,dimensions/2)
	area=Rect2((size-dimensions)/2+pan,dimensions)
	draw_texture_rect(texture,area,false)
	if overview:return
	var m: Dictionary=model.definitions[model.map_id()]
	for edge in m.warps:
		var at:=_at(Vector2(edge.SourceX,edge.SourceY))
		draw_rect(Rect2(at-Vector2(4,4),Vector2(8,8)),Color("55f58a"))
	for actor in model.snapshot.actors:
		if actor.npc:draw_circle(_at(Vector2(actor.x,actor.y)),4,Color("59caff"))
	var player:=_at(Vector2(model.position()))
	draw_circle(player,7,Color("171a10"));draw_circle(player,5,Color.WHITE)
	draw_arc(player,10,0,TAU,24,Color("ffdf48"),2)

func _pointer(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed and pointer==-1:pointer=event.index;press_at=event.position;last_at=event.position;dragged=false
		elif event.index==pointer:
			if not event.canceled and not dragged:_pick(event.position)
			pointer=-1
	elif event is InputEventScreenDrag and event.index==pointer:
		if event.position.distance_to(press_at)>10:dragged=true
		if dragged:pan+=event.relative;queue_redraw()
	elif event is InputEventMouseButton and event.device!=InputEvent.DEVICE_ID_EMULATION and event.button_index==MOUSE_BUTTON_LEFT:
		if event.pressed:pointer=-2;press_at=event.position;dragged=false
		elif pointer==-2:
			if not dragged:_pick(event.position)
			pointer=-1
	elif event is InputEventMouseMotion and pointer==-2:
		if event.position.distance_to(press_at)>10:dragged=true
		if dragged:pan+=event.relative;queue_redraw()
	accept_event()

func _pick(at: Vector2) -> void:
	if overview or not area.has_point(at):return
	var m: Dictionary=model.definitions[model.map_id()]
	var cell:=Vector2i(((at-area.position)/area.size*Vector2(m.width,m.height)).floor())
	if model.valid_position(model.map_id(),cell.x,cell.y):navigate.emit(cell)
