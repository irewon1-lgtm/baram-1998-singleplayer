extends Control
## Fixed reference layout; all text and actions come from the live native core.
var app: Control
var pane:="equipment"
var pane_scroll: ScrollContainer
var pane_box: VBoxContainer
var tabs: HBoxContainer
var content_signature:=""
var mini_lines: Array[String]=[]
var chat_lines: Array[String]=[]
var text_sequence:=-1
var frame: Texture2D
var paper: Texture2D
var crest: Texture2D
var totem: Texture2D
var curls: Dictionary={}
var font: Font
var right:=Rect2()
var sheet:=Rect2()
var mini:=Rect2()
var vital:=Rect2()
var chat:=Rect2()
var world_rect:=Rect2()
var font_size:=17
var title_left: Texture2D
var title_right: Texture2D

func _ready() -> void:
	mouse_filter=Control.MOUSE_FILTER_IGNORE;texture_filter=CanvasItem.TEXTURE_FILTER_LINEAR
	frame=load("res://p6/art/frame.png");paper=load("res://p6/art/paper-tile.png");crest=load("res://p6/art/crest.png");totem=load("res://p6/art/clan-crest.png")
	for key in ["top","left","right","bottom"]:curls[key]=load("res://p6/art/curl-"+key+".png")
	title_left=load("res://p6/art/title-left.png");title_right=load("res://p6/art/title-right.png")
	font=app.theme.default_font
	pane_scroll=ScrollContainer.new();pane_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;add_child(pane_scroll)
	pane_box=VBoxContainer.new();pane_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;pane_box.add_theme_constant_override("separation",3);pane_scroll.add_child(pane_box)
	tabs=HBoxContainer.new();tabs.add_theme_constant_override("separation",2);add_child(tabs)
	for entry in [["소지품","bag"],["장비","equipment"],["기술","spells"],["능력치","stats"]]:
		var b: Button=app.button(entry[0],set_pane.bind(entry[1]),62,38);b.size_flags_horizontal=Control.SIZE_EXPAND_FILL;b.add_theme_font_size_override("font_size",16);tabs.add_child(b)
	resized.connect(layout);layout();refresh()

func layout() -> void:
	var width:=clampf(size.x*0.265,242,340)
	right=Rect2(size.x-width-9,10,width,size.y-20)
	world_rect=Rect2(14,30,right.position.x-25,size.y*0.785-37)
	chat=Rect2(14,size.y*0.835,world_rect.size.x,size.y*0.165-15)
	sheet=Rect2(right.position+Vector2(5,4),Vector2(right.size.x-10,minf(right.size.y*0.635,(right.size.x-10)*1.55)))
	var vital_height:=maxf(156,minf(196,right.size.y*0.19))
	vital=Rect2(right.position.x+5,right.end.y-vital_height,right.size.x-10,vital_height)
	mini=Rect2(right.position.x+5,sheet.end.y+12,right.size.x-10,vital.position.y-sheet.end.y-23)
	pane_scroll.position=sheet.position+Vector2(sheet.size.x*0.115,sheet.size.y*0.115)
	pane_scroll.size=Vector2(sheet.size.x*0.77,sheet.size.y*0.765)
	tabs.position=Vector2(14,size.y*0.787);tabs.size=Vector2(world_rect.size.x,36)
	app.world.position=world_rect.position;app.world.size=world_rect.size
	font_size=16 if size.x<1000 else 17
	content_signature="";refresh();queue_redraw()

func set_pane(value: String) -> void:
	if app.model.snapshot.dialog!=null:return
	app._cancel_input();app._close_panel();pane=value;content_signature="";refresh()

func _label(value: String,dark: bool=false) -> Label:
	var label:=Label.new();label.text=value;label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;label.add_theme_font_size_override("font_size",font_size)
	label.add_theme_color_override("font_color",Color("38230e") if dark else Color("f2dfb6"));pane_box.add_child(label);return label

func _field(caption: String,value: String) -> void:
	var row:=HBoxContainer.new();row.add_theme_constant_override("separation",4);pane_box.add_child(row)
	var label:=Label.new();label.text=caption;label.add_theme_font_size_override("font_size",15);label.add_theme_color_override("font_color",Color("e6c68b"));label.custom_minimum_size.x=50;row.add_child(label)
	var field:=PanelContainer.new();field.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(field)
	var box:=StyleBoxFlat.new();box.bg_color=Color("d3ad68");box.border_color=Color("7d4c22");box.set_border_width_all(2);box.content_margin_left=4;box.content_margin_right=4;field.add_theme_stylebox_override("panel",box)
	var text_label:=Label.new();text_label.text=value;text_label.add_theme_font_size_override("font_size",15);text_label.add_theme_color_override("font_color",Color("3c250d"));field.add_child(text_label)

func _row(value: String,action: Callable,icon: Texture2D=null,dark: bool=false) -> Button:
	var b: Button=app.button(value,action,80,40 if size.y>size.x else 34);b.size_flags_horizontal=Control.SIZE_EXPAND_FILL;b.alignment=HORIZONTAL_ALIGNMENT_LEFT;b.add_theme_font_size_override("font_size",font_size)
	b.icon=icon;b.expand_icon=true;b.add_theme_constant_override("icon_max_width",24)
	for mode in ["normal","hover","pressed"]:
		var box:=StyleBoxFlat.new();box.bg_color=Color("b37d3630") if mode!="pressed" else Color("b37d3690");box.content_margin_left=3;box.content_margin_right=3;b.add_theme_stylebox_override(mode,box)
	for color in ["font_color","font_hover_color","font_pressed_color"]:b.add_theme_color_override(color,Color("36220c") if dark else Color("f5e2be"))
	b.add_theme_constant_override("outline_size",0);pane_box.add_child(b);return b

func refresh() -> void:
	if not is_node_ready() or app.model==null or not app.model.snapshot.get("playing",false):return
	var s: Dictionary=app.model.snapshot
	for event in s.get("texts",[]):
		if int(event.sequence)<=text_sequence:continue
		text_sequence=int(event.sequence)
		var value: String=app.locale.text(str(event.text)).replace(str(s.name),app.model.display_name)
		if event.channel=="mini":mini_lines.append(value);if_trim(mini_lines,32)
		else:chat_lines.append(value);if_trim(chat_lines,48)
	var signature:=pane+JSON.stringify([s.inventory,s.equipment,s.spellbook,s.stats,s.class_name,s.level,s.hp,s.mp,s.get("effects",[])])
	if signature!=content_signature:
		content_signature=signature
		for child in pane_box.get_children():child.queue_free()
		var dark:=pane in ["equipment","stats"]
		if pane=="bag":
			if s.inventory.is_empty():_label("소지품이 없습니다.")
			for item in s.inventory:
				var key:=String.chr(97+int(item.slot)) if int(item.slot)<26 else str(int(item.slot)+1)
				_row(key+": "+app.locale.entity("item",str(item.key),str(item.name))+(" %d개" %int(item.amount) if int(item.amount)>1 else ""),app._item_details.bind(item),app._icon(item))
		elif pane=="spells":
			if s.spellbook.is_empty():_label("배운 기술이 없습니다.\n교습 NPC에게 배울 수 있습니다.")
			for i in range(s.spellbook.size()):
				var spell: Dictionary=s.spellbook[i]
				_row(String.chr(97+i)+": "+app.locale.entity("spell",str(spell.key),str(spell.name)),app._choose_spell.bind(spell))
		elif pane=="equipment":
			for entry in [["CLAN",str(s.character.get("ClanName",""))],["C. T.",str(s.character.get("ClanTitle",""))],["TITLE",str(s.character.get("Title",""))]]:
				_field(entry[0],entry[1])
			_label(app.locale.name_of(str(s.class_name))+"   "+app.model.display_name,true)
			var doll:=preload("res://p6/paperdoll.gd").new();doll.model=app.model;doll.custom_minimum_size=Vector2(160,130 if size.y<size.x else 170);pane_box.add_child(doll)
			if s.equipment.is_empty():_label("장착한 장비가 없습니다.",true)
			for item in s.equipment:_row(app.locale.entity("item",str(item.key),str(item.name)),app._equipped_details.bind(item),app._icon(item),true)
			for fx in s.get("effects",[]):_label(app.locale.name_of(str(fx.name))+"  %d초" %int(fx.seconds),true)
		else:
			_label("능력치  ·  "+app.model.display_name,true)
			for entry in [["체력","%d / %d" %[s.hp,s.stats.max_hp]],["마력","%d / %d" %[s.mp,s.stats.max_mp]],["힘",s.stats.might],["지력",s.stats.will],["민첩",s.stats.grace],["방어",s.stats.ac],["명중",s.stats.hit],["공격",s.stats.dam],["다음 레벨",s.stats.tnl]]:_label(str(entry[0])+"    "+str(entry[1]),true)
	queue_redraw()

func if_trim(lines: Array[String],limit: int) -> void:
	while lines.size()>limit:lines.pop_front()

func _tex(texture: Texture2D,dest: Rect2,source: Rect2) -> void:draw_texture_rect_region(texture,dest,source)

func _text(value: String,at: Vector2,color: Color,fs: int=17,width: float=-1) -> void:
	draw_string(font,at,value,HORIZONTAL_ALIGNMENT_LEFT,width,fs,color)

func _framed(rect: Rect2,paper_inside: bool=true) -> void:
	if paper_inside:draw_texture_rect(paper,rect,true)
	else:draw_rect(rect,Color("251006"))
	draw_rect(rect,Color("d3ad70"),false,2);draw_rect(rect.grow(3),Color("4b200f"),false,3)

func _line_log(lines: Array[String],rect: Rect2,color: Color) -> void:
	var max_lines:=maxi(1,int((rect.size.y-8)/(font_size+3)));var combined: Array[String]=[]
	for line in lines:
		for paragraph in line.split("\n"):
			var rest: String=paragraph
			while font.get_string_size(rest,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x>rect.size.x-12 and rest.length()>1:
				var take:=rest.length()-1
				while take>1 and font.get_string_size(rest.left(take),HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x>rect.size.x-12:take-=1
				combined.append(rest.left(take));rest=rest.substr(take)
			combined.append(rest)
	for i in range(mini(max_lines,combined.size())):
		var text_line: String=combined[maxi(0,combined.size()-max_lines)+i]
		_text(text_line,rect.position+Vector2(5,4+font_size+i*(font_size+3)),color,font_size,rect.size.x-10)

func _draw() -> void:
	if frame==null:return
	# Original dragon rail and corners; never stretch the gameplay screenshot.
	var w:=world_rect.end.x+7;var top:=world_rect.position.y-18
	_tex(frame,Rect2(0,top,14,size.y-top),Rect2(0,12,12,456))
	_tex(frame,Rect2(0,size.y-14,w,14),Rect2(0,468,446,12))
	_tex(frame,Rect2(0,top,w,17),Rect2(0,0,446,12))
	_tex(frame,Rect2(w-8,top,16,size.y-top),Rect2(436,12,12,456))
	_tex(frame,Rect2(0,top,80,78),Rect2(0,0,60,58))
	_tex(frame,Rect2(w-81,top,80,78),Rect2(388,0,60,58))
	_tex(frame,Rect2(right.position-Vector2(0,4),right.size+Vector2(7,9)),Rect2(448,0,192,480))
	# Cover the original English HUD glyphs with clean reference paper/panel.
	draw_rect(Rect2(right.position+Vector2(4,2),right.size-Vector2(5,5)),Color("55270f"))
	var title_rect:=Rect2(maxf(65,w/2-180),top-5,360,27)
	draw_rect(title_rect,Color("100b08"));draw_texture_rect(title_left,Rect2(title_rect.position,Vector2(38,30)),false);draw_texture_rect(title_right,Rect2(title_rect.position+Vector2(title_rect.size.x-38,0),Vector2(38,30)),false)
	var map_name: String=app.locale.entity("maps",app.model.map_id(),str(app.model.definitions[app.model.map_id()].name));var title_width:=font.get_string_size(map_name,HORIZONTAL_ALIGNMENT_LEFT,-1,19).x
	_text(map_name,title_rect.position+Vector2((title_rect.size.x-title_width)/2,21),Color("eadbbd"),19,title_rect.size.x-24)
	var paper_mode:=pane in ["equipment","stats"]
	if paper_mode:draw_texture_rect(paper,sheet.grow(-12),true)
	else:draw_rect(sheet.grow(-12),Color("080605"))
	var cap:=sheet.size.y*0.12
	draw_texture_rect(curls.top,Rect2(sheet.position,Vector2(sheet.size.x,cap)),false)
	draw_texture_rect(curls.left,Rect2(sheet.position+Vector2(0,cap),Vector2(sheet.size.x*0.09,sheet.size.y-cap*2)),false)
	draw_texture_rect(curls.right,Rect2(sheet.position+Vector2(sheet.size.x*0.905,cap),Vector2(sheet.size.x*0.095,sheet.size.y-cap*2)),false)
	draw_texture_rect(curls.bottom,Rect2(sheet.position+Vector2(0,sheet.size.y-cap),Vector2(sheet.size.x,cap)),false)
	_framed(mini);_line_log(mini_lines,mini,Color("60411e"))
	_framed(chat);_line_log(chat_lines,chat,Color("4a321b"))
	if app.ui_message!="":_text(app.ui_message,Vector2(world_rect.position.x+6,world_rect.end.y-74),Color("ffe1a0"),17,world_rect.size.x-15)
	var s: Dictionary=app.model.snapshot
	if not s.get("playing",false):return
	var icon_w:=minf(60,vital.size.x*0.22);var gap:=vital.size.y/8
	draw_texture_rect(crest,Rect2(vital.position,Vector2(icon_w,icon_w)),false)
	draw_texture_rect(totem,Rect2(vital.position+Vector2(0,vital.size.y-icon_w),Vector2(icon_w,icon_w)),false)
	var x:=vital.position.x+icon_w+5;var rw:=vital.end.x-x-3;var y:=vital.position.y+font_size
	_text(app.model.display_name+"   "+app.locale.name_of(str(s.class_name))+" "+str(int(s.level)),Vector2(x,y),Color("f5e2bd"),font_size,rw)
	y+=gap;_text("힘 %d   지 %d   민 %d" %[s.stats.might,s.stats.will,s.stats.grace],Vector2(x,y),Color("ddd6bb"),font_size-1,rw)
	for entry in [["HP",s.hp,s.stats.max_hp,Color("b52d16")],["MP",s.mp,s.stats.max_mp,Color("2454ae")]]:
		y+=gap;var bar:=Rect2(x,y-font_size+2,rw,gap-3);draw_rect(bar,Color("1b0d07"));draw_rect(Rect2(bar.position,Vector2(bar.size.x*clampf(float(entry[1])/maxf(1,float(entry[2])),0,1),bar.size.y)),entry[3]);draw_rect(bar,Color("92603a"),false,1)
		_text("%s %d / %d" %[entry[0],entry[1],entry[2]],Vector2(x+2,y-1),Color("f4e2bd"),font_size-2,rw-4)
	y+=gap;_text("경험  "+str(int(s.exp)),Vector2(x,y),Color("b8d5a8"),font_size-1,rw)
	y+=gap;_text("금전  "+str(int(s.coins)),Vector2(x,y),Color("f8df9e"),font_size-1,rw)
	y+=gap;_text("%04d  %04d" %[s.x,s.y],Vector2(x,y),Color("eee1c8"),font_size,rw)
