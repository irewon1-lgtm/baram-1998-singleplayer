extends Control
const Model=preload("res://play/core_model.gd")
const World=preload("res://render/world_view.gd")
const Stick=preload("res://input/touch_stick.gd")
const Navigation=preload("res://input/grid_navigation.gd")
var model: RefCounted
var world: Control
var stick: Control
var navigation: RefCounted
var route: Array[Vector2i]=[]
var held:=Vector2i.ZERO
var pad_finger:=-1
var keyboard_direction:=Vector2i.ZERO
var paused:=false
var initialization_error:=""
var status: Label
var vitals: Label
var position_label: Label
var apple: Button
var wine: Button
var save_button: Button
var pad_buttons: Dictionary={}
var save_clock:=0.0

func initialize(root: String) -> bool:
	model=Model.new(root);initialization_error=model.error;return model.ready

func _button(text: String,width: float=102,height: float=64) -> Button:
	var button:=Button.new();button.text=text;button.custom_minimum_size=Vector2(width,height);button.focus_mode=Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size",20)
	for mode in ["normal","hover","pressed"]:
		var box:=StyleBoxFlat.new();box.bg_color=Color("536444") if mode=="pressed" else Color("303e2b")
		box.border_color=Color("8f9b71");box.set_border_width_all(1);box.set_corner_radius_all(8)
		button.add_theme_stylebox_override(mode,box)
	return button

func _ready() -> void:
	get_tree().auto_accept_quit=false
	var face:=FontVariation.new();face.base_font=load("res://fonts/NotoSansKR.ttf");face.variation_opentype={"wght":500.0}
	var t:=Theme.new();t.default_font=face;t.default_font_size=20;theme=t
	var backdrop:=ColorRect.new();backdrop.color=Color("171e14");backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);backdrop.mouse_filter=Control.MOUSE_FILTER_IGNORE;add_child(backdrop)
	world=World.new();world.model=model;world.anchor_right=1;world.anchor_bottom=1;world.offset_top=96;world.offset_bottom=-160;add_child(world)
	stick=Stick.new();stick.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);world.add_child(stick)
	stick.direction_changed.connect(_stick_direction);stick.tapped.connect(_world_tap)
	var top:=PanelContainer.new();top.anchor_right=1;top.offset_bottom=96;add_child(top)
	var top_row:=HBoxContainer.new();top_row.add_theme_constant_override("separation",28);top.add_child(top_row)
	var title:=Label.new();title.text="  PROJECT1998 · P3\n  시작 들판";title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;top_row.add_child(title)
	vitals=Label.new();vitals.custom_minimum_size.x=320;top_row.add_child(vitals)
	var help:=_button("조작 안내",128,72);top_row.add_child(help)
	help.pressed.connect(func():
		var dialog:=AcceptDialog.new();dialog.title="시작 들판";dialog.dialog_text="빈 곳을 누르면 이동합니다. 누른 채 끌거나 방향 버튼으로도 움직일 수 있습니다.\n사과는 체력을 회복합니다. 음료는 체력 5를 소모해 마력을 회복합니다.\n위치와 아이템은 자동 저장됩니다.\n현재 P3 범위는 이 들판의 이동·아이템·저장입니다. 지역 이동·NPC·전투는 아직 없습니다.";dialog.ok_button_text="확인";add_child(dialog);dialog.confirmed.connect(dialog.queue_free);dialog.popup_centered(Vector2i(850,250)))
	var footer:=PanelContainer.new();footer.anchor_top=1;footer.anchor_bottom=1;footer.anchor_right=1;footer.offset_top=-160;add_child(footer)
	var margin:=MarginContainer.new();margin.add_theme_constant_override("margin_left",16);margin.add_theme_constant_override("margin_right",16);margin.add_theme_constant_override("margin_top",12);margin.add_theme_constant_override("margin_bottom",12);footer.add_child(margin)
	var row:=HBoxContainer.new();row.add_theme_constant_override("separation",14);margin.add_child(row)
	var pad:=GridContainer.new();pad.columns=3;row.add_child(pad)
	for value in [Vector2i.ZERO,Vector2i.UP,Vector2i.ZERO,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]:
		if value==Vector2i.ZERO:
			var blank:=Control.new();blank.custom_minimum_size=Vector2(58,58);pad.add_child(blank)
		else:
			var labels: Dictionary={Vector2i.UP:"↑",Vector2i.RIGHT:"→",Vector2i.DOWN:"↓",Vector2i.LEFT:"←"}
			var b:=_button(labels[value],58,58);pad.add_child(b);pad_buttons[value]=b
			b.gui_input.connect(_pad_input.bind(value,b))
	var info:=VBoxContainer.new();info.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(info)
	status=Label.new();status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;status.size_flags_vertical=Control.SIZE_EXPAND_FILL;info.add_child(status)
	position_label=Label.new();position_label.add_theme_font_size_override("font_size",17);info.add_child(position_label)
	apple=_button("사과 먹기",112,84);row.add_child(apple);apple.gui_input.connect(_action_input.bind(_use.bind("apple"),apple))
	wine=_button("음료 마시기",120,84);row.add_child(wine);wine.gui_input.connect(_action_input.bind(_use.bind("wine"),wine))
	save_button=_button("저장",90,84);row.add_child(save_button);save_button.gui_input.connect(_action_input.bind(_save,save_button))
	var zooms:=VBoxContainer.new();row.add_child(zooms)
	for value in [0.5,-0.5]:
		var z:=_button("+" if value>0 else "−",52,56);zooms.add_child(z);z.pressed.connect(_zoom.bind(value))
	_update_hud();world.refresh(0)

func _update_hud() -> void:
	var s: Dictionary=model.snapshot
	vitals.text="체력 %d / %d\n마력 %d / %d" %[s.hp,s.max_hp,s.mp,s.max_mp]
	status.text=str(s.message)
	position_label.text="위치 %d, %d  ·  토끼 체력 %d" %[s.x,s.y,s.rabbit.hp]
	apple.text="사과 먹기\n%d개" %int(model.item("apple").amount)
	wine.text="음료 마시기\n%d회 남음" %int(model.item("wine").charges)
	apple.disabled=int(model.item("apple").amount)==0;wine.disabled=int(model.item("wine").amount)==0

func _pad_input(event: InputEvent,direction: Vector2i,button: Button) -> void:
	if event is InputEventScreenTouch:
		if event.pressed:pad_finger=event.index;_stick_direction(direction)
		elif event.index==pad_finger:pad_finger=-1;_stick_direction(Vector2i.ZERO)
		button.accept_event()
	elif event is InputEventMouseButton and event.button_index==MOUSE_BUTTON_LEFT and event.device!=InputEvent.DEVICE_ID_EMULATION:
		if event.pressed:pad_finger=-2;_stick_direction(direction)
		elif pad_finger==-2:pad_finger=-1;_stick_direction(Vector2i.ZERO)
		button.accept_event()

func _action_input(event: InputEvent,action: Callable,button: Button) -> void:
	if event is InputEventScreenTouch and event.pressed and not event.canceled:
		action.call();button.accept_event()
	elif event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT and event.device!=InputEvent.DEVICE_ID_EMULATION:
		action.call();button.accept_event()

func _stick_direction(value: Vector2i) -> void:
	held=value
	if value!=Vector2i.ZERO:keyboard_direction=Vector2i.ZERO;navigation=null;route.clear()

func _world_tap(point: Vector2) -> void:
	if paused:return
	held=Vector2i.ZERO;keyboard_direction=Vector2i.ZERO;navigation=Navigation.new();navigation.begin(model,world.screen_cell(point));route.clear()

func _zoom(value: float) -> void:world.zoom=clampf(world.zoom+value,1.0,4.0);world.refresh(0)
func _use(key: String) -> void:model.use_item(key);_update_hud()
func _save() -> void:model.save();_update_hud()
func _cancel_input() -> void:
	held=Vector2i.ZERO;pad_finger=-1;keyboard_direction=Vector2i.ZERO;route.clear();navigation=null
	if stick!=null:stick.cancel()
	if model!=null:model.halt()

func _input(event: InputEvent) -> void:
	if event is InputEventKey and not event.echo:
		var directions: Dictionary={KEY_UP:Vector2i.UP,KEY_RIGHT:Vector2i.RIGHT,KEY_DOWN:Vector2i.DOWN,KEY_LEFT:Vector2i.LEFT}
		if directions.has(event.keycode):
			if event.pressed:keyboard_direction=directions[event.keycode];held=Vector2i.ZERO;route.clear();navigation=null
			elif keyboard_direction==directions[event.keycode]:keyboard_direction=Vector2i.ZERO
	# Finger release outside a direction button must still release held motion.
	if event is InputEventScreenTouch and not event.pressed and event.index==pad_finger:held=Vector2i.ZERO;pad_finger=-1
	if event is InputEventMouseButton and not event.pressed and pad_finger==-2:held=Vector2i.ZERO;pad_finger=-1

func _process(delta: float) -> void:
	if model==null or not model.ready:return
	if not paused:
		model.advance(minf(delta,0.25))
		if navigation!=null and navigation.advance(96):route=navigation.result.duplicate();navigation=null
		if not model.moving:
			var direction:=keyboard_direction if keyboard_direction!=Vector2i.ZERO else held
			if direction!=Vector2i.ZERO:model.move(direction);route.clear();navigation=null;_update_hud()
			elif not route.is_empty():
				var next: Vector2i=route.pop_front()
				if not model.move(next-model.position()):route.clear()
				_update_hud()
	world.refresh(delta);save_clock+=delta
	if save_clock>=3 and model.dirty and not model.moving:save_clock=0;_save()

func _notification(what: int) -> void:
	if model==null or not model.ready or status==null:return
	if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:paused=true;_cancel_input();_save()
	elif what in [NOTIFICATION_APPLICATION_RESUMED,NOTIFICATION_APPLICATION_FOCUS_IN]:paused=false
	elif what in [NOTIFICATION_WM_GO_BACK_REQUEST,NOTIFICATION_WM_CLOSE_REQUEST]:_cancel_input();_save();get_tree().quit()
