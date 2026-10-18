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
	if model==null or not model.snapshot.get("playing",false):return
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

func _actor_at(actor: Dictionary,cell: Vector2) -> void:
	var key: String
	var player: bool=actor.get("player",false)
	if player:
		var animation: String=model.animation_key()
		if int(model.snapshot.character.Armor)==3:animation="armor:3-"+animation
		var seq: Array=model.source.animations[animation]
		key=str(seq[model.animation_tick()].key)
	else:
		var prefix: String=("npc:" if actor.npc else "mob:")+str(actor.key)+"-"+str(int(actor.facing))
		if not model.source.animations.has(prefix):return
		var seq: Array=model.source.animations[prefix]
		key=str(seq[int(elapsed*5)%seq.size()].key)
	var anchor: Vector2=(cell+Vector2(0.5,0.5))*24
	var weapon:=""
	if player:
		for item in model.snapshot.equipment:
			if item.key in ["wooden_saber","novice_sword"]:
				var look:=1 if item.key=="wooden_saber" else 0
				var sequence: Array=model.source.animations["weapon:"+str(look)+"-"+model.animation_key()]
				weapon=str(sequence[model.animation_tick()].key)
	if weapon!="" and model.facing==0:_sprite(weapon,anchor)
	_sprite(key,anchor)
	if weapon!="" and model.facing!=0:_sprite(weapon,anchor)
	if label_actors:
		var aliases: Dictionary={"rabbit":"토끼","squirrel":"다람쥐","WoodlandSmithNpc":"대장장이","WoodlandArmorerNpc":"방어구 장인","TutorialNpc1":"숲의 교관","TutorialNpc2":"농장 교관","MignokNpc":"미그녹","WoodlandGuardNpc":"경비병","WoodlandAngelNpc":"천사","MainTutorialNpc":"아이언하트","InnNpc":"주막 주인"}
		var label: String=str(model.snapshot.name) if player else str(aliases.get(actor.key,actor.name))
		var at: Vector2=(anchor-camera)*zoom
		var text_width:=font.get_string_size(label,HORIZONTAL_ALIGNMENT_LEFT,-1,16).x
		draw_string(font,at+Vector2(-text_width/2,-40*zoom),label,HORIZONTAL_ALIGNMENT_LEFT,-1,16,Color(1,0.95,0.76),TextServer.JUSTIFICATION_NONE)
		if not player and not actor.npc and int(actor.hp)<int(actor.max_hp):
			draw_rect(Rect2(at+Vector2(-22,-30*zoom),Vector2(44,4)),Color("442c2a"))
			draw_rect(Rect2(at+Vector2(-22,-30*zoom),Vector2(44*float(actor.hp)/maxf(1,actor.max_hp),4)),Color("d98c73"))

func _draw() -> void:
	last_draw_items=0
	draw_rect(Rect2(Vector2.ZERO,size),Color("171e14"))
	if model==null or not model.snapshot.get("playing",false):return
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
	# Floor loot precedes actors and object columns in the same source cell.
	for item in model.snapshot.loot:
		if not model.source.item_icons.has(item.key):continue
		_sprite(str(model.source.item_icons[item.key].key),(Vector2(item.x,item.y)+Vector2(0.5,0.5))*24)
	var pending: Array=[]
	if draw_actors:
		pending.append({"actor":{"player":true},"cell":model.visual,"depth":model.visual.y+0.5})
		for actor in model.snapshot.actors:
			if int(actor.x)<min_x or int(actor.x)>max_x or int(actor.y)<min_y or int(actor.y)>max_y:continue
			pending.append({"actor":actor,"cell":Vector2(actor.x,actor.y),"depth":float(actor.y)+0.5})
		pending.sort_custom(func(a,b):return float(a.depth)<float(b.depth))
	for y in range(min_y,max_y+1):
		while not pending.is_empty() and float(pending[0].depth)<=float(y+1):
			var a: Dictionary=pending.pop_front();_actor_at(a.actor,a.cell)
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
	for a in pending:_actor_at(a.actor,a.cell)
