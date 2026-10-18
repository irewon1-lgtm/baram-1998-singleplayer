extends Control
var model: RefCounted
var atlas: Texture2D
var paper: Texture2D

func _ready() -> void:
	atlas=load("res://assets/actors.png");texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST;mouse_filter=Control.MOUSE_FILTER_IGNORE
	paper=load("res://p6/art/selflook.png")

func _part(key: String,anchor: Vector2,scale: float) -> void:
	var row: Dictionary=model.source.actor_regions[key];var r: Array=row.rect;var off: Array=row.offset
	draw_texture_rect_region(atlas,Rect2(anchor+Vector2(off[0],off[1])*scale,Vector2(r[2],r[3])*scale),Rect2(r[0],r[1],r[2],r[3]))

func _draw() -> void:
	if atlas==null:return
	var appearance: Dictionary=model.snapshot.appearance
	var key:="armor:%d:%d-idle-2" %[appearance.armor,appearance.dye]
	if not model.source.animations.has(key):key="idle-2"
	var scale:=minf(size.y/60.0,4.0);var anchor:=Vector2(size.x/2,size.y*0.78)
	var positions: Dictionary={4:Vector2(0.50,0.03),7:Vector2(0.16,0.75),8:Vector2(0.78,0.75),3:Vector2(0.08,0.27),5:Vector2(0.80,0.27)}
	for slot in positions:
		var at: Vector2=positions[slot]*size
		draw_rect(Rect2(at-Vector2(16,0),Vector2(32,32)),Color("71421c"),false,2)
		for worn in model.snapshot.equipment:
			if int(worn.slot)!=slot or not model.source.item_icons.has(str(worn.key)):continue
			var region: Dictionary=model.source.actor_regions[model.source.item_icons[str(worn.key)].key];var r: Array=region.rect
			var icon_atlas: Texture2D=load("res://p6/art/extra-icons.png") if region.get("sheet","")=="extra_icons" else atlas
			draw_texture_rect_region(icon_atlas,Rect2(at-Vector2(14,-2),Vector2(28,28)),Rect2(r[0],r[1],r[2],r[3]))
	_shadow(anchor+Vector2(-25,-5),Vector2(50,10))
	_part(str(model.source.animations[key][0].key),anchor,scale)
	for item in model.snapshot.equipment:
		if int(item.type)!=3:continue
		key="weapon:%d:%d-idle-2" %[item.look,item.dye]
		if model.source.animations.has(key):_part(str(model.source.animations[key][0].key),anchor,scale)

func _shadow(at: Vector2,extent: Vector2) -> void:
	# Cosmetic floor shadow only; character pixels are the supplied source art.
	draw_set_transform(at+extent/2,0,extent/2);draw_circle(Vector2.ZERO,1,Color(0.2,0.13,0.06,0.18));draw_set_transform(Vector2.ZERO)
