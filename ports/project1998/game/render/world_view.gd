extends Control
## Visible tiles only; original object columns and actors share foot-depth order.
var model: RefCounted
var ground: Texture2D
var objects: Texture2D
var actors: Texture2D
var zoom := 2.0
var camera := Vector2.ZERO
var font: Font
var elapsed := 0.0
var draw_ground := true
var draw_objects := true
var draw_actors := true
var label_actors := true
var last_draw_items := 0

func _ready() -> void:
	texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
	clip_contents=true
	mouse_filter=Control.MOUSE_FILTER_PASS
	ground=load("res://assets/ground.png")
	objects=load("res://assets/objects.png")
	actors=load("res://assets/actors.png")
	var face:=FontVariation.new();face.base_font=load("res://fonts/NotoSansKR.ttf");face.variation_opentype={"wght":500.0};font=face

func refresh(delta: float) -> void:
	elapsed+=delta
	if model==null:return
	var m: Dictionary=model.definitions[model.map_id()]
	var map_pixels:=Vector2(int(m.width)*24,int(m.height)*24)
	var desired: Vector2=(model.visual+Vector2(0.5,0.5))*24-size/(2*zoom)
	for axis in range(2):
		camera[axis]=roundf((map_pixels[axis]-size[axis]/zoom)/2) if map_pixels[axis]*zoom<size[axis] else roundf(clampf(desired[axis],0,map_pixels[axis]-size[axis]/zoom))
	queue_redraw()

func screen_cell(point: Vector2) -> Vector2i:
	return Vector2i(((point/zoom+camera)/24).floor())

func _sprite(key: String,anchor: Vector2) -> void:
	var region: Dictionary=model.source.actor_regions[key]
	var r: Array=region.rect
	var offset: Array=region.offset
	draw_texture_rect_region(actors,Rect2((anchor+Vector2(offset[0],offset[1])-camera)*zoom,Vector2(r[2],r[3])*zoom),Rect2(r[0],r[1],r[2],r[3]))
	last_draw_items+=1

func _actor_at(kind: String,cell: Vector2) -> void:
	var key: String
	if kind=="player":
		var seq: Array=model.source.animations[model.animation_key()]
		key=str(seq[model.animation_tick()].key)
	else:
		var seq: Array=model.source.animations["rabbit-2"]
		key=str(seq[0].key)
	var anchor: Vector2=(cell+Vector2(0.5,0.5))*24
	_sprite(key,anchor)
	if label_actors:
		var label:="모험가" if kind=="player" else "토끼"
		var at: Vector2=(anchor-camera)*zoom
		var text_width:=font.get_string_size(label,HORIZONTAL_ALIGNMENT_LEFT,-1,16).x
		draw_string(font,at+Vector2(-text_width/2,-45*zoom),label,HORIZONTAL_ALIGNMENT_LEFT,-1,16,Color(1,0.95,0.76),TextServer.JUSTIFICATION_NONE)

func _draw() -> void:
	last_draw_items=0
	draw_rect(Rect2(Vector2.ZERO,size),Color("171e14"))
	if model==null:return
	var mid: String=model.map_id()
	var m: Dictionary=model.definitions[mid]
	var width:=int(m.width);var height:=int(m.height)
	var gs: PackedInt32Array=model.cells[mid].ground
	var os: PackedInt32Array=model.cells[mid].objects
	var min_x:=maxi(0,int(floor(camera.x/24))-1)
	var max_x:=mini(width-1,int(ceil((camera.x+size.x/zoom)/24))+1)
	var min_y:=maxi(0,int(floor(camera.y/24))-1)
	var max_y:=mini(height-1,int(ceil((camera.y+size.y/zoom)/24))+16)
	if draw_ground:
		for y in range(min_y,mini(height-1,int(ceil((camera.y+size.y/zoom)/24))+1)+1):
			for x in range(min_x,max_x+1):
				var slot:=int(m.ground_lookup[str(gs[y*width+x])])
				draw_texture_rect_region(ground,Rect2((Vector2(x,y)*24-camera)*zoom,Vector2(24,24)*zoom),Rect2((slot%64)*24,(slot/64)*24,24,24))
				last_draw_items+=1
	var pending: Array=[]
	if draw_actors:
		pending.append({"kind":"player","cell":model.visual,"depth":model.visual.y+0.5})
		if mid=="4711":pending.append({"kind":"rabbit","cell":Vector2(6,6),"depth":6.5})
		pending.sort_custom(func(a,b):return float(a.depth)<float(b.depth))
	for y in range(min_y,max_y+1):
		while not pending.is_empty() and float(pending[0].depth)<=float(y+1):
			var a: Dictionary=pending.pop_front();_actor_at(str(a.kind),a.cell)
		if not draw_objects:continue
		for x in range(min_x,max_x+1):
			var object_id:=os[y*width+x]
			if object_id==0:continue
			var column: Array=model.source.objects[str(object_id)].frames
			for k in range(column.size()):
				if int(column[k])==0:continue
				var frame: Dictionary=model.source.object_frames[str(int(column[k]))]
				var r: Array=frame.rect
				if int(r[2])==0 or int(r[3])==0:continue
				var off: Array=frame.offset
				var destination:=Rect2((Vector2(x*24+off[0],(y-k)*24+off[1])-camera)*zoom,Vector2(r[2],r[3])*zoom)
				if not destination.intersects(Rect2(Vector2.ZERO,size)):continue
				draw_texture_rect_region(objects,destination,Rect2(r[0],r[1],r[2],r[3]))
				last_draw_items+=1
	for a in pending:_actor_at(str(a.kind),a.cell)
