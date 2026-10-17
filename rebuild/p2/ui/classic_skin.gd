extends RefCounted
## Korean DLGNEW02:0 pixel regions, reused in the live game. The original
## create-character controls are NOT misrepresented as historical HUD masks.
static var source: Texture2D
static var original_source: Texture2D
const COLOR_ADAPTATION:="SOURCE_LUMINANCE_WARM_HONEY_RECONSTRUCTION"
static var cache: Dictionary = {}

static func bind_original(texture: Texture2D) -> void:
	original_source=texture
	cache.clear()
	if texture==null:source=null;return
	# The original general palette has pink/green dither in its parchment.
	# Preserve source linework, wood grain and alpha, but explicitly adapt its
	# luminance to the selected warm HUD palette rather than showing RGB noise.
	var pixels:=texture.get_image()
	pixels.convert(Image.FORMAT_RGBA8)
	var warm: Array[Color]=[Color("29170d"),Color("56311a"),Color("805028"),Color("a37139"),Color("bf914f"),Color("d6ad68"),Color("ebcc91")]
	for y in range(pixels.get_height()):
		for x in range(pixels.get_width()):
			var original:=pixels.get_pixel(x,y)
			if original.a<=0:continue
			var light:=clampf(original.r*0.299+original.g*0.587+original.b*0.114,0,1)
			var cursor:=light*6.0
			var index:=mini(5,int(cursor))
			var adapted:=warm[index].lerp(warm[index+1],cursor-index)
			adapted.a=original.a;pixels.set_pixel(x,y,adapted)
	source=ImageTexture.create_from_image(pixels)

static func region(key: String, rect: Rect2) -> Texture2D:
	if cache.has(key): return cache[key]
	if source==null: return null
	var atlas:=AtlasTexture.new();atlas.atlas=source;atlas.region=rect
	cache[key]=atlas
	return atlas

static func parchment() -> Texture2D:
	if cache.has("paper"):return cache.paper
	if source==null:return null
	# AtlasTexture does not support a repeated subregion. Use the exact native
	# source pixels as a tiny standalone repeat texture (one draw per panel).
	var tile:=ImageTexture.create_from_image(source.get_image().get_region(Rect2i(333,196,16,16)))
	cache.paper=tile
	return tile

static func wood() -> Texture2D:
	return region("wood",Rect2(125,308,70,15))

static func patch(texture: Texture2D, margins: Vector4, content: Vector4=Vector4(7,4,7,4)) -> StyleBoxTexture:
	var value:=StyleBoxTexture.new();value.texture=texture
	value.texture_margin_left=margins.x;value.texture_margin_top=margins.y
	value.texture_margin_right=margins.z;value.texture_margin_bottom=margins.w
	value.axis_stretch_horizontal=StyleBoxTexture.AXIS_STRETCH_MODE_STRETCH if texture==wood() else StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	value.axis_stretch_vertical=StyleBoxTexture.AXIS_STRETCH_MODE_STRETCH if texture==wood() else StyleBoxTexture.AXIS_STRETCH_MODE_TILE
	value.content_margin_left=content.x;value.content_margin_top=content.y
	value.content_margin_right=content.z;value.content_margin_bottom=content.w
	return value

static func theme_for(font: Font) -> Theme:
	var value:=Theme.new();value.default_font=font;value.default_font_size=15
	var normal:=patch(wood(),Vector4(5,3,5,3))
	var hover:=normal.duplicate();hover.modulate_color=Color(1.2,1.13,0.94)
	var pressed:=normal.duplicate();pressed.modulate_color=Color(0.73,0.65,0.54)
	var disabled:=normal.duplicate();disabled.modulate_color=Color(0.62,0.59,0.5)
	for cls in ["Button","OptionButton"]:
		value.set_stylebox("normal",cls,normal);value.set_stylebox("hover",cls,hover)
		value.set_stylebox("pressed",cls,pressed);value.set_stylebox("disabled",cls,disabled)
		value.set_stylebox("focus",cls,StyleBoxEmpty.new())
		value.set_color("font_color",cls,Color("ffdf99"))
		value.set_color("font_hover_color",cls,Color("fff3c8"))
		value.set_color("font_pressed_color",cls,Color("ffebac"))
		value.set_color("font_disabled_color",cls,Color("a79571"))
		value.set_constant("outline_size",cls,1);value.set_color("font_outline_color",cls,Color("3e2515"))
	value.set_stylebox("tab_unselected","TabContainer",normal)
	var selected:=patch(parchment(),Vector4(3,3,3,3),Vector4(9,6,9,5))
	value.set_stylebox("tab_selected","TabContainer",selected)
	value.set_stylebox("tab_hovered","TabContainer",hover)
	value.set_stylebox("panel","TabContainer",StyleBoxEmpty.new())
	value.set_color("font_selected_color","TabContainer",Color("392311"))
	value.set_color("font_unselected_color","TabContainer",Color("f4d28b"))
	value.set_constant("side_margin","TabContainer",0)
	var entry:=patch(parchment(),Vector4(3,3,3,3),Vector4(8,5,8,5))
	value.set_stylebox("normal","LineEdit",entry)
	value.set_color("font_color","LineEdit",Color("392311"))
	value.set_color("font_placeholder_color","LineEdit",Color("745735"))
	for cls in ["VScrollBar","HScrollBar"]:
		var track:=normal.duplicate();track.modulate_color=Color("6d5038")
		value.set_stylebox("scroll",cls,track)
		value.set_stylebox("grabber",cls,normal);value.set_stylebox("grabber_highlight",cls,hover)
		value.set_stylebox("grabber_pressed",cls,pressed)
	return value
