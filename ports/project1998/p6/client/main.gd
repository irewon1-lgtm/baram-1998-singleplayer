extends Control
const Locale=preload("res://p6/locale.gd")
const Profile=preload("res://p6/profile.gd")
const Sound=preload("res://p6/audio.gd")
const Model=preload("res://p6/model.gd")
const World=preload("res://p6/world.gd")
const Stick=preload("res://input/touch_stick.gd")
const MapView=preload("res://p6/map.gd")
const PaperDoll=preload("res://p6/paperdoll.gd")
const Classic=preload("res://p6/classic.gd")
const Navigation=preload("res://input/grid_navigation.gd")
var classic: Control
var action_row: HBoxContainer
var utility_row: HBoxContainer
var talking_actor: Dictionary={}
var locale:=Locale.new()
var profile: RefCounted
var sounds: Node
var top_panel: PanelContainer
var footer_panel: PanelContainer
var hp_bar: ProgressBar
var mp_bar: ProgressBar
var skip_button: Button
var map_view: Control
var modal_scroll: ScrollContainer
var creation_scroll: ScrollContainer
var keyboard_height_override:=-1
var keyboard_last:=-1
var ui_message:=""
var model: RefCounted
var world: Control
var stick: Control
var navigation: RefCounted
var route: Array[Vector2i]=[]
var goal:=Vector2i(-1,-1)
var goal_reach:=0
var goal_map:=""
var held:=Vector2i.ZERO
var pad_finger:=-1
var paused:=false
var game_visible:=false
var initialization_error:=""
var hud: Label
var guide: Label
var status: Label
var title: Label
var skill: Button
var attack: Button
var modal: PanelContainer
var modal_backdrop: ColorRect
var modal_box: VBoxContainer
var modal_revision:=-1
var modal_kind:=""
var bag_open:=false
var selected_id:=0
var pending_npc:=0
var pending_loot:=false
var auto_attack:=false
var save_clock:=0.0
var tick_clock:=0.0
var action_clock:=0.0
var status_clock:=0.0
var pending_spell:=""
var form: LineEdit
var create_error: Label

func initialize(root: String) -> bool:
	profile=Profile.new(root);model=Model.new(root);initialization_error=model.error
	if model.snapshot.get("playing",false):model.display_name=profile.shown(str(model.snapshot.name))
	return model.ready

func button(text: String,action: Callable,width: float=98,height: float=54) -> Button:
	var limit:=modal.size.x-110 if modal!=null else size.x-100
	var b:=Button.new();b.text=text;b.custom_minimum_size=Vector2(minf(width,maxf(64,limit)),height);b.focus_mode=Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size",20)
	b.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	for mode in ["normal","hover","pressed"]:
		var box:=StyleBoxFlat.new();box.bg_color=(Color("b47a35") if mode=="pressed" else Color("d4ad6fe8")) if modal!=null else (Color("995a29cc") if mode=="pressed" else Color("49250e82"))
		box.border_color=Color("b17b42");box.set_border_width_all(1);box.set_corner_radius_all(7);b.add_theme_stylebox_override(mode,box)
	if modal!=null:
		for state in ["font_color","font_hover_color","font_pressed_color"]:b.add_theme_color_override(state,Color("382819"))
	else:b.add_theme_color_override("font_color",Color("fff1d3"));b.add_theme_color_override("font_outline_color",Color("151a12"));b.add_theme_constant_override("outline_size",2)
	b.gui_input.connect(func(event: InputEvent):
		if event is InputEventScreenTouch and event.pressed and not event.canceled:action.call();b.accept_event()
		elif event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT and event.device!=InputEvent.DEVICE_ID_EMULATION:action.call();b.accept_event())
	return b

func _ready() -> void:
	get_tree().auto_accept_quit=false;Engine.max_fps=60
	get_window().size_changed.connect(_configure_viewport);resized.connect(_layout);_configure_viewport()
	sounds=Sound.new();sounds.volume=profile.volume;add_child(sounds)
	var face:=FontVariation.new();face.base_font=load("res://fonts/NotoSansKR.ttf");face.variation_opentype={"wght":700.0};face.variation_embolden=0.65
	var t:=Theme.new();t.default_font=face;t.default_font_size=20;theme=t
	if not model.ready:
		var fail:=Label.new();fail.text="P6 시작 실패\n"+initialization_error;fail.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;fail.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(fail);return
	if not model.snapshot.get("playing",false):_creation()
	else:_build_game()

func _creation() -> void:
	var bg:=ColorRect.new();bg.color=Color("2b160b");bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var scroll:=ScrollContainer.new();creation_scroll=scroll;scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);scroll.set_offsets_preset(Control.PRESET_FULL_RECT);scroll.offset_left=32;scroll.offset_right=-32;scroll.offset_top=32;scroll.offset_bottom=-32;add_child(scroll)
	var center:=CenterContainer.new();center.size_flags_horizontal=Control.SIZE_EXPAND_FILL;center.size_flags_vertical=Control.SIZE_EXPAND_FILL;scroll.add_child(center)
	var box:=VBoxContainer.new();box.custom_minimum_size=Vector2(minf(680,size.x-80),400);box.add_theme_constant_override("separation",20);center.add_child(box)
	var heading:=Label.new();heading.text="PROJECT1998   /   P6";heading.add_theme_font_size_override("font_size",34);box.add_child(heading)
	var intro:=Label.new();intro.text="국내성에서 모험을 시작합니다.\n원하면 초보자 수련부터 진행할 수도 있습니다.";intro.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(intro)
	form=LineEdit.new();form.text="여행자";form.placeholder_text="한글 2~12자 또는 영문 3~16자";form.max_length=16;form.custom_minimum_size.y=64;form.virtual_keyboard_enabled=true;box.add_child(form)
	create_error=Label.new();create_error.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;create_error.modulate=Color("edbf93");box.add_child(create_error)
	box.add_child(button("본게임 시작",_create_character.bind(true),240,64))
	box.add_child(button("초보자 수련 시작",_create_character.bind(false),240,64))
	form.text_submitted.connect(func(_value: String):_create_character(true))
	var note:=Label.new();note.text="오프라인 · 자동 저장\n초보자 구간 · 국내성 상점 · 네 직업 교습소 · 쥐굴과 지하 동굴";note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;note.modulate=Color("d0b17c");box.add_child(note)

func _create_character(skip: bool=false) -> void:
	var nickname:=form.text.strip_edges()
	if not profile.valid_name(nickname):create_error.text="한글 2~12자 또는 영문 3~16자로 입력해 주세요.";return
	model.call_core("Create",[profile.native_name(nickname)])
	if not model.snapshot.get("playing",false):create_error.text=locale.text(str(model.snapshot.error));return
	if not profile.save(str(model.snapshot.name),nickname):ui_message="이름 설정을 저장하지 못했습니다."
	model.display_name=profile.shown(str(model.snapshot.name))
	if skip:model.call_core("SkipTutorial")
	creation_scroll=null
	for child in get_children():
		if child!=sounds:child.queue_free()
	_build_game()

func _meter(color: String) -> ProgressBar:
	var bar:=ProgressBar.new();bar.custom_minimum_size=Vector2(100,19);bar.size_flags_horizontal=Control.SIZE_EXPAND_FILL;bar.show_percentage=false
	var back:=StyleBoxFlat.new();back.bg_color=Color("111b1770");back.set_corner_radius_all(4);bar.add_theme_stylebox_override("background",back)
	var fill:=StyleBoxFlat.new();fill.bg_color=Color(color);fill.bg_color.a=0.72;fill.set_corner_radius_all(4);bar.add_theme_stylebox_override("fill",fill);return bar

func _overlay(panel: PanelContainer) -> void:
	var skin:=StyleBoxFlat.new();skin.bg_color=Color(0.06,0.09,0.06,0.12);panel.add_theme_stylebox_override("panel",skin)
	panel.mouse_filter=Control.MOUSE_FILTER_IGNORE

func _caption(label: Label) -> void:
	label.mouse_filter=Control.MOUSE_FILTER_IGNORE
	label.add_theme_color_override("font_color",Color("fff0ca"));label.add_theme_color_override("font_outline_color",Color("10180e"));label.add_theme_constant_override("outline_size",3)

func _build_game() -> void:
	game_visible=true
	world=World.new();world.model=model;world.locale=locale;add_child(world)
	stick=Stick.new();stick.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);world.add_child(stick)
	stick.direction_changed.connect(_direction);stick.tapped.connect(_world_tap)
	classic=Classic.new();classic.app=self;classic.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(classic)
	action_row=HBoxContainer.new();action_row.add_theme_constant_override("separation",5);add_child(action_row)
	action_row.add_child(button("말하기",_talk_nearest,92,52))
	action_row.add_child(button("줍기",_pickup,72,52))
	attack=button("공격",_attack,80,52);action_row.add_child(attack)
	utility_row=HBoxContainer.new();utility_row.add_theme_constant_override("separation",4);add_child(utility_row)
	for entry in [["지역 안내",_region],["채팅",_speech],["F1",_central],["설정",_settings]]:utility_row.add_child(button(entry[0],entry[1],82 if entry[0]=="지역 안내" else 56,42))
	skip_button=button("본게임 시작",_skip_tutorial,125,42);utility_row.add_child(skip_button)
	_update_hud();_sync_dialog();world.refresh(0);call_deferred("_layout")

func _pickup() -> void:
	_cancel_input();model.call_core("Pickup");_update_hud()

func _skip_tutorial() -> void:
	_cancel_input();_close_panel();model.call_core("SkipTutorial");_update_hud();world.refresh(0)

func _configure_viewport() -> void:
	var pixels:=get_window().size
	var reference:=Vector2i(800,1280) if pixels.y>pixels.x else Vector2i(1280,800)
	if get_window().content_scale_size!=reference:get_window().content_scale_size=reference
	call_deferred("_layout")

func _keyboard_height() -> float:
	var actual:=keyboard_height_override if keyboard_height_override>=0 else DisplayServer.virtual_keyboard_get_height() if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD) else 0
	return float(actual)*size.y/maxf(1,get_window().size.y)

func _layout() -> void:
	if creation_scroll!=null:
		creation_scroll.offset_bottom=-32-_keyboard_height()
		if form!=null and form.has_focus():creation_scroll.ensure_control_visible(form)
	if game_visible and classic!=null:
		classic.layout()
		action_row.position=classic.world_rect.end-Vector2(action_row.get_combined_minimum_size().x+10,62)
		utility_row.position=classic.world_rect.position+Vector2(8,8)

	if modal!=null:
		var available:=size-Vector2(32,32+_keyboard_height())
		modal.size=Vector2(minf(680,available.x),maxf(180,minf(660 if modal_kind=="npc" else 900 if size.y>size.x else 720,available.y)))
		modal.position=Vector2((size.x-modal.size.x)/2,maxf(16,(size.y-_keyboard_height()-modal.size.y)/2))
		if get_viewport().gui_get_focus_owner()!=null and modal.is_ancestor_of(get_viewport().gui_get_focus_owner()):modal_scroll.ensure_control_visible(get_viewport().gui_get_focus_owner())

func quest_text() -> String:
	var s: Dictionary=model.snapshot;var stage:=int(s.stage)
	var hints: Array=["아래쪽 출구 (8~11, 15) → 열린 들판의 대장장이 (13, 6)",
		"대장장이의 부탁: 토끼 10마리 사냥 후 다시 대화 · 고기를 모으세요",
		"남쪽 출구 → 숲길의 방어구 장인 (9, 7)에게 대화",
		"방어구 장인의 부탁: 다람쥐 10마리 사냥 · 도토리를 모으세요",
		"남쪽 출구 → 깊은 숲의 교관 (11, 9)에게 대화",
		"깊은 숲 (21, 20) → 농장 교관 (11, 9)에게 대화",
		"미그녹의 집: 농장 (17, 5) · 도토리 5개와 토끼고기 5개로 회복 배우기",
		"농장의 교관 (11, 9)에게 돌아가 대화",
		"농장 동쪽 출구 → 도시 경계의 경비병 (11, 17)에게 대화",
		"천사 (10, 6)와 대화한 뒤, 근처에서 ‘완료’라고 말하기",
		"아이언하트와 두 번 대화해 원본 지원금 받기 → 국내성 주막 입구 (56, 149)"]
	if stage>=10:
		return "  지역 안내로 출구 찾기 · 전리품 판매는 정육점 · 5레벨부터 직업 교습소에서 전직"
	return "  "+str(hints[mini(stage,10)])

func _update_hud() -> void:
	if not game_visible:return
	var s: Dictionary=model.snapshot
	skip_button.visible=int(s.map)>=4711 and int(s.map)<=4718
	attack.text="사냥 중지" if auto_attack else "공격"
	if sounds!=null:sounds.consume(s.get("media",[]))
	if pending_spell!="":ui_message="기술을 사용할 대상을 누르세요."
	if int(s.hp)==0:ui_message="쓰러졌습니다. NPC 또는 신당 무녀에게 말해 부활하세요."
	if classic!=null:classic.refresh()

func bar_label(bar: ProgressBar) -> Label:return bar.get_child(0) as Label

func _direction(value: Vector2i) -> void:
	if paused or modal!=null:return
	held=value
	if value!=Vector2i.ZERO:pending_spell="";navigation=null;route.clear();goal=Vector2i(-1,-1);pending_npc=0;pending_loot=false;selected_id=0;auto_attack=false

func _pad_input(event: InputEvent,direction: Vector2i,b: Button) -> void:
	if paused or modal!=null:return
	if event is InputEventScreenTouch:
		if event.pressed and not event.canceled:
			if pad_finger==-1:pad_finger=event.index;_direction(direction)
		elif event.index==pad_finger:pad_finger=-1;held=Vector2i.ZERO
		b.accept_event()
	elif event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_LEFT and event.device!=InputEvent.DEVICE_ID_EMULATION:
		if event.pressed:pad_finger=-2;_direction(direction)
		elif pad_finger==-2:pad_finger=-1;held=Vector2i.ZERO
		b.accept_event()

func _go(cell: Vector2i,reach: int=0) -> void:
	goal=cell;goal_reach=reach;goal_map=model.map_id()
	held=Vector2i.ZERO;navigation=Navigation.new();navigation.begin(model,cell,reach);route.clear()

func _world_tap(point: Vector2) -> void:
	if paused or modal!=null:return
	var cell: Vector2i=world.screen_cell(point)
	var hit: Dictionary=world.actor_at_screen(point)
	if pending_spell!="":
		for actor in model.snapshot.actors:
			if (not hit.is_empty() and int(actor.id)==int(hit.id)) or (hit.is_empty() and Vector2i(actor.x,actor.y)==cell):
				var key:=pending_spell;pending_spell="";model.call_core("CastSpell",[key,int(actor.id),""]);_update_hud();return
		if cell==model.position():
			var key:=pending_spell;pending_spell="";model.call_core("CastSpell",[key,int(model.snapshot.character.Id),""]);_update_hud()
		return
	selected_id=0;pending_npc=0;pending_loot=false;auto_attack=false
	for a in model.snapshot.actors:
		if (not hit.is_empty() and int(a.id)==int(hit.id)) or (hit.is_empty() and Vector2i(int(a.x),int(a.y))==cell):
			if a.npc:
				_approach_npc(a);return
			else:selected_id=int(a.id);auto_attack=true
			_go(cell,1);return
	for i in model.snapshot.loot:
		if Vector2i(int(i.x),int(i.y))==cell:pending_loot=true
	_go(cell)

func _cancel_input() -> void:
	pending_spell=""
	held=Vector2i.ZERO;pad_finger=-1;route.clear();navigation=null;goal=Vector2i(-1,-1);goal_map="";pending_npc=0;pending_loot=false;auto_attack=false
	if stick!=null:stick.cancel()
	if model!=null:model.halt()

func _face(cell: Vector2i) -> void:
	var d: Vector2i=cell-model.position();var direction:=1 if d.x>0 else 3
	if absi(d.y)>absi(d.x):direction=2 if d.y>0 else 0
	model.core.Turn(direction);model.call_core("ReadState")

func _attack() -> void:
	if selected_id!=0:auto_attack=not auto_attack
	else:model.call_core("Attack")
	_update_hud()

func _save() -> void:model.call_core("Save");_update_hud()

func _panel(kind: String) -> void:
	_cancel_input();_close_panel();modal_kind=kind;ui_message=""
	modal_backdrop=ColorRect.new();modal_backdrop.color=Color(0,0,0,0.42);modal_backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);modal_backdrop.mouse_filter=Control.MOUSE_FILTER_STOP;add_child(modal_backdrop)
	modal=PanelContainer.new()
	var style:=StyleBoxTexture.new();style.texture=load("res://p6/art/classic-window.png")
	style.texture_margin_left=35;style.texture_margin_right=36;style.texture_margin_top=72;style.texture_margin_bottom=72
	style.content_margin_left=46;style.content_margin_right=46;style.content_margin_top=78;style.content_margin_bottom=78
	modal.texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST;modal.add_theme_stylebox_override("panel",style)
	var paper:=theme.duplicate();paper.set_color("font_color","Label",Color("392b1c"));paper.set_color("font_color","LineEdit",Color("fff1d2"));modal.theme=paper;add_child(modal)
	modal_scroll=ScrollContainer.new();modal_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;modal.add_child(modal_scroll)
	modal_box=VBoxContainer.new();modal_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;modal_box.add_theme_constant_override("separation",14);modal_scroll.add_child(modal_box);_layout()

func _close_panel() -> void:
	if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):DisplayServer.virtual_keyboard_hide()
	if modal!=null:modal.queue_free();modal=null
	if modal_backdrop!=null:modal_backdrop.queue_free();modal_backdrop=null
	modal_kind="";bag_open=false;map_view=null

func _text(value: String) -> Label:
	var label:=Label.new();label.text=locale.text(value);label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;modal_box.add_child(label);return label

func _list(height: float=290) -> VBoxContainer:
	var scroll:=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;scroll.custom_minimum_size=Vector2(0,height);scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;modal_box.add_child(scroll)
	var list:=VBoxContainer.new();list.size_flags_horizontal=Control.SIZE_EXPAND_FILL;list.add_theme_constant_override("separation",10);scroll.add_child(list);return list

func _ascii_input(value: String,error_label: Label) -> String:
	var answer:=locale.command(value)
	for c in answer:
		if c.unicode_at(0)>127:error_label.text="이 답은 한글로 보낼 수 없습니다. 안내된 영문 답이나 동·서·남·북을 입력해 주세요.";return ""
	return answer

func _sync_dialog() -> void:
	var d=model.snapshot.get("dialog")
	if d==null:
		if modal_kind=="npc":_close_panel()
		modal_revision=-1;return
	if int(d.revision)==modal_revision:return
	modal_revision=int(d.revision);_panel("npc")
	var speaker:=""
	for actor in model.snapshot.actors:
		if int(actor.id)==int(d.npc):talking_actor=actor;speaker=_npc_name(actor);break
	if speaker!="":_heading(speaker)
	_text(str(d.text))
	var scroll:=ScrollContainer.new();scroll.custom_minimum_size.y=150;scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;modal_box.add_child(scroll)
	var options:=VBoxContainer.new();options.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(options)
	if d.kind=="menu":
		for i in range(d.options.size()):options.add_child(button(locale.text(str(d.options[i])),func():model.call_core("Reply",[2,i+1,""]);_sync_dialog(),700,52))
	elif d.kind=="buy":
		for i in range(d.names.size()):options.add_child(button("%s   ·   %d전" %[locale.name_of(str(d.names[i])),d.prices[i]],func():model.call_core("ShopReply",[2,str(d.names[i]),0,"1"]);_sync_dialog(),700,50))
	elif d.kind=="sell":
		for i in range(d.slots.size()):options.add_child(button(locale.text(str(d.names[i])),func():model.call_core("ShopReply",[4,"",int(d.slots[i]),"1"]);_sync_dialog(),700,50))
	elif d.kind in ["input","amount"]:
		var input:=LineEdit.new();input.custom_minimum_size=Vector2(0,64);input.size_flags_horizontal=Control.SIZE_EXPAND_FILL;input.text="1" if d.kind=="amount" else "";options.add_child(input)
		var input_error:=_text("")
		if d.kind=="amount":options.add_child(button("수량 확인 (최대 %d)" %int(d.max),func():model.call_core("ShopReply",[3,str(d.names[0]),0,input.text]);_sync_dialog()))
		else:options.add_child(button("확인",func():
			var value:=_ascii_input(input.text,input_error)
			if value=="":return
			model.call_core("Reply",[4,0,value]);_sync_dialog()))
	else:options.add_child(button("다음 / 확인",func():model.call_core("Reply",[1,0,""]);_sync_dialog(),280,62))
	if talking_actor.get("key","")=="WoodlandAngelNpc":modal_box.add_child(button("완료라고 말하기",func():model.call_core("CloseDialog");_close_panel();model.call_core("Say",["Finish"]);_sync_dialog();_update_hud(),300,52))
	modal_box.add_child(button("대화 닫기",func():model.call_core("CloseDialog");_close_panel();modal_revision=-1;_update_hud(),160,52))

func _window_tabs() -> void:
	var tabs:=HBoxContainer.new();tabs.add_theme_constant_override("separation",6);modal_box.add_child(tabs)
	for entry in [["소지품",_bag],["기술",_spellbook],["장비",_equipment],["능력치",_stats]]:
		var tab:=button(entry[0],entry[1],120,52);tab.size_flags_horizontal=Control.SIZE_EXPAND_FILL;tabs.add_child(tab)

func _heading(value: String) -> void:
	var label:=_text(value);label.add_theme_font_size_override("font_size",26)

func _icon(item: Dictionary) -> AtlasTexture:
	if not model.source.item_icons.has(item.key):return null
	var texture:=AtlasTexture.new();texture.atlas=load("res://p6/art/extra-icons.png") if model.source.actor_regions[model.source.item_icons[item.key].key].get("sheet","")=="extra_icons" else world.actors
	var r: Array=model.source.actor_regions[model.source.item_icons[item.key].key].rect
	texture.region=Rect2(r[0],r[1],r[2],r[3]);return texture

func _bag() -> void:
	classic.set_pane("bag")

func _item_details(item: Dictionary) -> void:
	_panel("item");_window_tabs();_heading(locale.entity("item",str(item.key),str(item.name)))
	var icon:=TextureRect.new();icon.texture=_icon(item);icon.custom_minimum_size=Vector2(100,120);icon.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED;modal_box.add_child(icon)
	_text("수량 %d    내구도 %d / %d" %[item.amount,item.durability,item.max_durability])
	modal_box.add_child(button("사용 / 착용",func():model.call_core("UseItem",[int(item.slot),false]);_bag();_update_hud(),300,60))
	modal_box.add_child(button("먹기",func():model.call_core("UseItem",[int(item.slot),true]);_bag();_update_hud(),300,60))
	modal_box.add_child(button("하나 내려놓기",func():model.call_core("DropItem",[int(item.slot),false]);_close_panel();_update_hud(),300,52))
	modal_box.add_child(button("모두 내려놓기",func():model.call_core("DropItem",[int(item.slot),true]);_close_panel();_update_hud(),300,52))
	modal_box.add_child(button("소지품으로",_bag,240))
	modal_box.add_child(button("닫기",_close_panel))

func _equipment() -> void:
	classic.set_pane("equipment")

func _stats() -> void:
	classic.set_pane("stats")

func _npc_name(actor: Dictionary) -> String:
	return locale.entity("npcs",str(int(actor.npc_def)),str(actor.name))

func _talk_nearest() -> void:
	if model.snapshot.dialog!=null:_sync_dialog();return
	var npcs: Array=model.snapshot.actors.filter(func(a):return a.npc)
	npcs.sort_custom(func(a,b):return model.position().distance_squared_to(Vector2i(a.x,a.y))<model.position().distance_squared_to(Vector2i(b.x,b.y)))
	if npcs.is_empty():ui_message="이 지역에는 대화할 NPC가 없습니다.";_update_hud();return
	if npcs.size()==1 or model.position().distance_to(Vector2i(npcs[0].x,npcs[0].y))<=3.0:_approach_npc(npcs[0]);return
	_panel("npc-select");_heading("대화할 NPC")
	_text("선택한 NPC에게 다가가 대화합니다.")
	for actor in npcs:modal_box.add_child(button("%s  (%d, %d)" %[_npc_name(actor),actor.x,actor.y],_approach_npc.bind(actor),600,52))
	modal_box.add_child(button("닫기",_close_panel))

func _approach_npc(actor: Dictionary) -> void:
	_close_panel();_cancel_input();talking_actor=actor.duplicate();ui_message=_npc_name(actor)+"에게 이동 중"
	pending_npc=int(actor.id)
	var target:=Vector2i(actor.x,actor.y)
	if model.position().distance_to(target)<=1.1:_open_npc(actor)
	else:_go(target,1)
	_update_hud()

func _open_npc(actor: Dictionary) -> void:
	_cancel_input();talking_actor=actor.duplicate();_face(Vector2i(actor.x,actor.y));ui_message=""
	model.call_core("Talk",[int(actor.id)]);_sync_dialog()
	if model.snapshot.dialog==null:
		_panel("npc-voice");_heading(_npc_name(actor));_text("이 NPC는 말에 반응합니다.")
		for entry in [["이름 묻기","your name"],["파는 물건 묻기","what do you sell"],["사는 물건 묻기","what do you buy"]]:
			modal_box.add_child(button(entry[0],func():_close_panel();model.call_core("Say",[entry[1]]);_sync_dialog();_update_hud(),500,52))
		modal_box.add_child(button("직접 말하기",_speech,240,52));modal_box.add_child(button("닫기",_close_panel))
	_update_hud()

func _central() -> void:
	_cancel_input();model.call_core("Talk",[4294967295]);talking_actor={};_sync_dialog()

func _speech() -> void:
	if model.snapshot.dialog!=null:return
	_panel("speech");_heading("말할 내용")
	if not talking_actor.is_empty() and model.position().distance_to(Vector2i(talking_actor.x,talking_actor.y))<=3.0:_text(_npc_name(talking_actor)+" 근처에서 말합니다.")
	var input:=LineEdit.new();input.custom_minimum_size=Vector2(0,64);input.placeholder_text="내용 입력";modal_box.add_child(input)
	var error_label:=_text("")
	modal_box.add_child(button("말하기",func():
		var value:=_ascii_input(input.text,error_label)
		if value=="":return
		model.call_core("Say",[value]);_close_panel();_sync_dialog();_update_hud()))
	modal_box.add_child(button("닫기",_close_panel))

func _equipped_details(item: Dictionary) -> void:
	_panel("equipped");_heading(locale.entity("item",str(item.key),str(item.name)))
	_text("내구도 %d / %d" %[item.durability,item.max_durability])
	modal_box.add_child(button("벗기",func():model.call_core("Unequip",[int(item.slot)]);_close_panel();_update_hud(),200,58))
	modal_box.add_child(button("닫기",_close_panel))

func _settings() -> void:
	if model.snapshot.dialog!=null:return
	_panel("settings");_heading("설정")
	modal_box.add_child(button("저장",_save,160))
	if int(model.snapshot.map)>=4711 and int(model.snapshot.map)<=4718:modal_box.add_child(button("본게임 시작 · 수련 건너뛰기",_skip_tutorial,500,60))
	_text("이름과 소리")
	var nickname:=LineEdit.new();nickname.text=model.display_name;nickname.placeholder_text="한글 2~12자 또는 영문 3~16자";nickname.custom_minimum_size.y=64;modal_box.add_child(nickname)
	var feedback:=_text(profile.error)
	modal_box.add_child(button("이름 저장",func():
		if not profile.valid_name(nickname.text.strip_edges()):feedback.text="한글 2~12자 또는 영문 3~16자로 입력해 주세요.";return
		if profile.save(str(model.snapshot.name),nickname.text.strip_edges()):model.display_name=profile.shown(str(model.snapshot.name));feedback.text="이름을 저장했습니다.";_update_hud()
		else:feedback.text="이름 설정을 저장하지 못했습니다."))
	_text("효과음 크기")
	var slider:=HSlider.new();slider.min_value=0;slider.max_value=1;slider.step=0.05;slider.value=profile.volume;slider.custom_minimum_size.y=56;modal_box.add_child(slider)
	slider.value_changed.connect(func(value: float):
		profile.volume=value;sounds.volume=value
		if value==0:sounds.stop_all())
	modal_box.add_child(button("조작 도움말",_help,240,56))
	modal_box.add_child(button("닫기",func():profile.save(str(model.snapshot.name),model.display_name);_close_panel()))

func _spellbook() -> void:
	classic.set_pane("spells")

func _choose_spell(spell: Dictionary) -> void:
	if int(spell.type)==1:
		_panel("spell-answer");_text(locale.name_of(str(spell.name))+"\n"+locale.text(str(spell.question)))
		var answer:=LineEdit.new();answer.custom_minimum_size=Vector2(0,64);answer.max_length=200;modal_box.add_child(answer)
		var answer_error:=_text("")
		modal_box.add_child(button("사용",func():
			var value:=_ascii_input(answer.text,answer_error)
			if value=="":return
			_close_panel();model.call_core("CastSpell",[str(spell.key),0,value]);_sync_dialog();_update_hud()))
		modal_box.add_child(button("취소",_close_panel))
	elif int(spell.type)==2:
		_panel("spell-target");_text(locale.name_of(str(spell.name))+" · 대상 선택")
		modal_box.add_child(button("화면에서 대상 선택",func():_close_panel();pending_spell=str(spell.key);_update_hud(),400,70))
		modal_box.add_child(button("자신에게 사용",func():_close_panel();model.call_core("CastSpell",[str(spell.key),int(model.snapshot.character.Id),""]);_update_hud(),400,70))
		modal_box.add_child(button("취소",_close_panel))
	else:
		_close_panel();model.call_core("CastSpell",[str(spell.key),0,""]);_sync_dialog();_update_hud()

func _region(overview: bool=false) -> void:
	if model.snapshot.dialog!=null:return
	_panel("region");_heading("지역 안내 · "+locale.entity("maps",model.map_id(),str(model.definitions[model.map_id()].name)))
	var tabs:=HBoxContainer.new();modal_box.add_child(tabs)
	tabs.add_child(button("현재 지도",_region.bind(false),180,52));tabs.add_child(button("왕국 전도",_region.bind(true),180,52))
	map_view=MapView.new();map_view.model=model;map_view.locale=locale;map_view.overview=overview;map_view.custom_minimum_size=Vector2(0,370 if size.y>size.x else 290);map_view.size_flags_horizontal=Control.SIZE_EXPAND_FILL;modal_box.add_child(map_view)
	map_view.navigate.connect(func(cell: Vector2i):_close_panel();_go(cell))
	var zooms:=HBoxContainer.new();modal_box.add_child(zooms)
	zooms.add_child(button("축소",func():map_view.change_zoom(-0.5),110,52));zooms.add_child(button("확대",func():map_view.change_zoom(0.5),110,52))
	_text("왕국의 전체 지도입니다. 현재 지도에서 길과 출구를 선택할 수 있습니다." if overview else "흰 점: 나 · 파란 점: NPC · 초록 점: 출구\n지도를 누르면 이동합니다. 확대 후 끌어서 살펴볼 수 있습니다.")
	if not overview:
		var list:=_list(150)
		var entries: Array=model.definitions[model.map_id()].warps.duplicate()
		entries.append_array(model.definitions[model.map_id()].get("scripted_exits",[]))
		var shown: Dictionary={}
		for edge in entries:
			var dest:=str(int(edge.DestinationMapId));var cell:=Vector2i(int(edge.SourceX),int(edge.SourceY))
			var key:=dest+":"+str(cell)
			if shown.has(key):continue
			shown[key]=true
			var current: Dictionary=model.definitions[model.map_id()]
			var included: bool=model.definitions.has(dest) and cell.x>=0 and cell.y>=0 and cell.x<int(current.width) and cell.y<int(current.height)
			var label:=locale.entity("maps",dest,str(model.definitions[dest].name)) if included else "아직 열리지 않은 지역"
			var b:=button("%s  ← 출구 (%d, %d)" %[label,cell.x,cell.y],func():_close_panel();_go(cell),600,54)
			b.disabled=not included;list.add_child(b)
	modal_box.add_child(button("닫기",_close_panel))

func _help() -> void:
	if model.snapshot.dialog!=null:return
	_panel("help");_text("조작 안내\n\n바닥을 누르면 이동합니다. 화면을 누른 채 끌어서도 이동할 수 있습니다.\nNPC를 누르면 다가가 대화합니다. 몬스터를 누르면 추적하며 사냥합니다.\n공격 버튼으로 사냥을 중지할 수 있습니다. 전리품을 누르면 다가가 줍습니다.\n소지품에서 무기·옷을 착용하고 먹을 것을 사용할 수 있습니다.\n기술 / 마법 창에서 배운 능력을 선택합니다. 대상 기술은 대상을 누르고, 질문형 기술은 답을 입력합니다.\n진행은 자동 저장됩니다. 말하기 버튼으로 NPC를 고르면 가까이 이동한 뒤 대화를 엽니다.\n지역 안내에서 실제 지도와 왕국 전도를 볼 수 있습니다.\n초보자 수련 중에는 본게임 시작으로 국내성에 바로 갈 수 있습니다.\n직업별 기술·비용·장비 조건은 교습소에서 확인할 수 있습니다.")
	modal_box.add_child(button("확인",_close_panel))

func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch and (not event.pressed or event.canceled) and event.index==pad_finger:held=Vector2i.ZERO;pad_finger=-1
	if event is InputEventMouseButton and not event.pressed and pad_finger==-2:held=Vector2i.ZERO;pad_finger=-1
	if event is InputEventKey and not event.echo and game_visible and not paused and modal==null:
		var directions: Dictionary={KEY_UP:Vector2i.UP,KEY_RIGHT:Vector2i.RIGHT,KEY_DOWN:Vector2i.DOWN,KEY_LEFT:Vector2i.LEFT}
		if directions.has(event.keycode):_direction(directions[event.keycode] if event.pressed else Vector2i.ZERO)
		if event.pressed and event.keycode==KEY_SPACE:_attack()

func _process(delta: float) -> void:
	var kb:=int(_keyboard_height())
	if kb!=keyboard_last:keyboard_last=kb;_layout()
	if not game_visible:return
	if not paused:
		model.advance(minf(delta,0.25));tick_clock+=delta;action_clock+=delta;save_clock+=delta
		if tick_clock>=0.333:tick_clock-=0.333;model.call_core("Step");_sync_dialog();_update_hud()
		if model.map_changed:
			# A tap may already have started a NEW route after the warp was
			# rendered. Only discard input belonging to the map we left.
			if goal_map!=model.map_id() or goal.x<0:_cancel_input()
			model.map_changed=false;model.call_core("Save")
		if modal==null:
			if navigation!=null and navigation.advance(128):
				route=navigation.result.duplicate();navigation=null
				if route.is_empty() and model.position().distance_to(goal)>goal_reach+0.1:
					ui_message="갈 수 있는 길을 찾지 못했습니다. 지역 안내에서 위치를 확인하세요.";pending_npc=0;pending_loot=false;auto_attack=false;_update_hud()
			if not model.moving and navigation==null:
				if held!=Vector2i.ZERO:model.move(held)
				elif not route.is_empty():
					var next: Vector2i=route.pop_front()
					if not model.move(next-model.position()):
						route.clear()
						# A living mob can enter a planned cell before the step.
						# Let the original handler reject it, then plan again.
						if model.snapshot.get("move_failure","")=="occupied" and goal.x>=0 and goal_map==model.map_id():_go(goal,goal_reach)
						else:_cancel_input()
				elif pending_npc!=0:
					for a in model.snapshot.actors:
						if int(a.id)==pending_npc and model.position().distance_to(Vector2i(a.x,a.y))<=1.1:_open_npc(a)
					pending_npc=0
				elif pending_loot and action_clock>0.4:model.call_core("Pickup");pending_loot=false
			if auto_attack and action_clock>=0.25:
				action_clock=0;var found:=false
				for a in model.snapshot.actors:
					if int(a.id)!=selected_id:continue
					found=true;var target:=Vector2i(a.x,a.y)
					if model.position().distance_to(target)<=1.1:_face(target);model.call_core("Attack")
					elif navigation==null and route.is_empty():_go(target,1)
				if not found:auto_attack=false;selected_id=0;model.call_core("Save")
		if save_clock>=3:save_clock=0;_save()
	world.refresh(delta)

func _notification(what: int) -> void:
	if not game_visible:
		if what in [NOTIFICATION_WM_GO_BACK_REQUEST,NOTIFICATION_WM_CLOSE_REQUEST]:get_tree().quit()
		return
	if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:paused=true;_cancel_input();_save();sounds.stop_all()
	elif what in [NOTIFICATION_APPLICATION_RESUMED,NOTIFICATION_APPLICATION_FOCUS_IN]:paused=false
	elif what==NOTIFICATION_WM_GO_BACK_REQUEST:
		if _keyboard_height()>0:DisplayServer.virtual_keyboard_hide()
		elif modal!=null:model.call_core("CloseDialog");_close_panel();modal_revision=-1
		else:_save();get_tree().quit()
	elif what==NOTIFICATION_WM_CLOSE_REQUEST:_cancel_input();_save();get_tree().quit()
