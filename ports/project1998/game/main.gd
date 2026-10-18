extends Control
const Model = preload("res://model.gd")
const World = preload("res://render/world_view.gd")
const Stick = preload("res://input/touch_stick.gd")
const Navigation = preload("res://input/grid_navigation.gd")
var model: RefCounted
var world: Control
var stick: Control
var navigation: RefCounted
var route: Array[Vector2i]=[]
var held := Vector2i.ZERO
var keyboard_direction := Vector2i.ZERO
var paused := false
var title: Label
var position_label: Label
var status: Label
var fps: Label
var save_clock := 0.0
var telemetry_clock := 0.0
var hud_clock := 0.0
var elapsed := 0.0
var frames: Array[float]=[]
var lifecycle: Array=[]
var captures := 0
var touch_events := 0
var last_tap: Dictionary={}
var route_plan: Array=[]
var route_stop: Dictionary={}
var last_message := "빈 곳을 눌러 이동 · 누른 채 끌면 방향 이동"

func _ready() -> void:
	get_tree().auto_accept_quit=false
	var face:=FontVariation.new();face.base_font=load("res://fonts/NotoSansKR.ttf");face.variation_opentype={"wght":500.0}
	var t:=Theme.new();t.default_font=face;t.default_font_size=20;theme=t
	model=Model.new()
	var backdrop:=ColorRect.new();backdrop.color=Color("171e14");backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);backdrop.mouse_filter=Control.MOUSE_FILTER_IGNORE;add_child(backdrop)
	world=World.new();world.model=model;world.anchor_right=1;world.anchor_bottom=1
	world.offset_top=100;world.offset_bottom=-136;add_child(world)
	stick=Stick.new();stick.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);world.add_child(stick)
	stick.direction_changed.connect(_stick_direction)
	stick.tapped.connect(_world_tap)
	var top:=PanelContainer.new();top.anchor_right=1;top.offset_bottom=100;top.add_theme_stylebox_override("panel",_panel(Color("252b20"),Color("657246")));add_child(top)
	var top_margin:=MarginContainer.new();_margins(top_margin,22,14,22,14);top.add_child(top_margin)
	var top_row:=HBoxContainer.new();top_row.add_theme_constant_override("separation",18);top_margin.add_child(top_row)
	var identity:=VBoxContainer.new();identity.size_flags_horizontal=Control.SIZE_EXPAND_FILL;identity.add_theme_constant_override("separation",1);top_row.add_child(identity)
	var brand:=Label.new();brand.text="PROJECT1998  ·  P2";brand.add_theme_font_size_override("font_size",17);brand.add_theme_color_override("font_color",Color("b7c48f"));identity.add_child(brand)
	title=Label.new();title.add_theme_font_size_override("font_size",25);identity.add_child(title)
	for item in [["4711","시작 들판"],["0","국내성"],["2","주막"]]:
		var b:=_button(str(item[1]),Vector2(120,64));top_row.add_child(b)
		b.pressed.connect(_select_map.bind(str(item[0])))
	var footer:=PanelContainer.new();footer.anchor_top=1;footer.anchor_bottom=1;footer.anchor_right=1;footer.offset_top=-136;footer.add_theme_stylebox_override("panel",_panel(Color("252b20"),Color("657246")));add_child(footer)
	var margin:=MarginContainer.new();_margins(margin,22,12,22,12);footer.add_child(margin)
	var row:=HBoxContainer.new();row.add_theme_constant_override("separation",18);margin.add_child(row)
	var information:=VBoxContainer.new();information.size_flags_horizontal=Control.SIZE_EXPAND_FILL;information.add_theme_constant_override("separation",3);row.add_child(information)
	status=Label.new();status.add_theme_font_size_override("font_size",20);status.add_theme_color_override("font_color",Color("edf0df"));information.add_child(status)
	position_label=Label.new();position_label.add_theme_font_size_override("font_size",17);position_label.add_theme_color_override("font_color",Color("b4bd9f"));information.add_child(position_label)
	fps=Label.new();fps.add_theme_font_size_override("font_size",15);fps.add_theme_color_override("font_color",Color("9ea88e"));information.add_child(fps)
	var zoom_out:=_button("−",Vector2(66,76));row.add_child(zoom_out);zoom_out.pressed.connect(_zoom.bind(-0.5))
	var zoom_in:=_button("+",Vector2(66,76));row.add_child(zoom_in);zoom_in.pressed.connect(_zoom.bind(0.5))
	var save_button:=_button("위치 저장",Vector2(130,76));row.add_child(save_button);save_button.pressed.connect(_save)
	var attack_button:=_button("공격 동작",Vector2(145,76));row.add_child(attack_button);attack_button.pressed.connect(_attack)
	# ScreenTouch is handled separately, so a second finger can attack while
	# the first continues dragging the stick; emulated mouse is not duplicated.
	attack_button.gui_input.connect(func(event):
		if event is InputEventScreenTouch and event.pressed:
			_attack();attack_button.accept_event())
	_update_hud()
	world.refresh(0)
	if not model.loaded and model.allow_write:_save()

func _panel(fill: Color,border: Color) -> StyleBoxFlat:
	var box:=StyleBoxFlat.new();box.bg_color=fill
	box.border_color=border;box.border_width_top=1;box.border_width_bottom=1
	return box

func _button(text: String,minimum: Vector2) -> Button:
	var b:=Button.new();b.text=text;b.custom_minimum_size=minimum;b.focus_mode=Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size",20)
	for mode in ["normal","hover","pressed"]:
		var box:=StyleBoxFlat.new();box.bg_color=Color("3c4930") if mode=="pressed" else Color("303a29")
		box.border_color=Color("899467");box.set_border_width_all(1);box.set_corner_radius_all(10)
		box.content_margin_left=14;box.content_margin_right=14
		b.add_theme_stylebox_override(mode,box)
	return b

func _margins(m: MarginContainer,left: int,top: int,right: int,bottom: int) -> void:
	for pair in [["left",left],["top",top],["right",right],["bottom",bottom]]:m.add_theme_constant_override("margin_"+str(pair[0]),int(pair[1]))

func _stick_direction(value: Vector2i) -> void:
	held=value
	if value!=Vector2i.ZERO:keyboard_direction=Vector2i.ZERO;navigation=null;route.clear()

func _world_tap(point: Vector2) -> void:
	if paused:return
	var target: Vector2i=world.screen_cell(point)
	last_tap={"local_point":[point.x,point.y],"target":[target.x,target.y],"at_ms":Time.get_ticks_msec()}
	# Latest input wins. A tap must not lose its remaining route to an older
	# polled keyboard state, and focus loss must not leave a held key behind.
	held=Vector2i.ZERO;keyboard_direction=Vector2i.ZERO
	navigation=Navigation.new();navigation.begin(model,target);route.clear()

func _select_map(mid: String) -> void:
	_cancel_input();model.switch_map(mid);world.refresh(0);_save()
	last_message="빈 곳을 눌러 이동 · 누른 채 끌면 방향 이동";_update_hud()

func _zoom(amount: float) -> void:
	world.zoom=clampf(world.zoom+amount,1.0,4.0);world.refresh(0)

func _attack() -> void:
	if paused:return
	model.attack();last_message="원본 기본 공격 동작";_update_hud()

func _save() -> void:
	var result: Dictionary=model.save()
	last_message=model.save_status
	if result.status!="SAVED":push_warning("P1998 local tech save: "+str(result.status))
	_update_hud()

func _cancel_input() -> void:
	held=Vector2i.ZERO;keyboard_direction=Vector2i.ZERO;route.clear();navigation=null
	if stick!=null:stick.cancel()
	if model!=null:model.halt()

func _update_hud() -> void:
	var mid: String=model.map_id()
	title.text="시작 들판" if mid=="4711" else str(model.definitions[mid].name_ko)
	position_label.text="모험가  ·  위치 %d, %d  ·  %s" %[model.position().x,model.position().y,model.save_status]
	status.text=last_message
	fps.text="%d FPS  ·  오프라인  ·  터치 이동 / 방향키" %Engine.get_frames_per_second()

func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:touch_events+=1
	if event is InputEventKey and not event.echo:
		var directions: Dictionary={KEY_UP:Vector2i.UP,KEY_RIGHT:Vector2i.RIGHT,KEY_DOWN:Vector2i.DOWN,KEY_LEFT:Vector2i.LEFT}
		if directions.has(event.keycode):
			if event.pressed:
				keyboard_direction=directions[event.keycode];held=Vector2i.ZERO;route.clear();navigation=null
			elif keyboard_direction==directions[event.keycode]:keyboard_direction=Vector2i.ZERO
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_SPACE:_attack();accept_event()
		elif event.keycode==KEY_ESCAPE:_cancel_input();_save();accept_event()
		elif event.keycode==KEY_F12 and OS.is_debug_build():_capture()

func _process(delta: float) -> void:
	if model==null:return
	elapsed+=delta;frames.append(delta*1000)
	if frames.size()>3600:frames.pop_front()
	if not paused:
		model.advance(minf(delta,0.25))
		if navigation!=null:
			if navigation.advance(96):
				route=navigation.result.duplicate();route_plan=[]
				for cell in route:route_plan.append([cell.x,cell.y])
				navigation=null
		if not model.moving:
			var direction:=keyboard_direction if keyboard_direction!=Vector2i.ZERO else held
			if direction!=Vector2i.ZERO:route.clear();navigation=null;model.move(direction)
			elif not route.is_empty():
				var next: Vector2i=route.pop_front()
				if not model.move(next-model.position()):
					route_stop={"next":[next.x,next.y],"at":[model.position().x,model.position().y],"moving":model.moving};route.clear()
	world.refresh(delta)
	hud_clock+=delta;save_clock+=delta;telemetry_clock+=delta
	if hud_clock>=0.2:hud_clock=0;_update_hud()
	if save_clock>=3 and model.dirty and not model.moving:save_clock=0;_save()
	if telemetry_clock>=0.5 and OS.is_debug_build():telemetry_clock=0;_telemetry()

func _notification(what: int) -> void:
	if model==null:return
	if what in [NOTIFICATION_APPLICATION_PAUSED,NOTIFICATION_APPLICATION_FOCUS_OUT]:
		paused=true;_cancel_input();_save();lifecycle.append({"event":"pause_or_focus_out","at_ms":Time.get_ticks_msec()})
	elif what in [NOTIFICATION_APPLICATION_RESUMED,NOTIFICATION_APPLICATION_FOCUS_IN]:
		# Focus-in can arrive just AFTER the first legitimate click. Old input was
		# already cleared on pause/focus-out; clearing it again here discards a
		# fresh tap's remaining path after its first step.
		paused=false;lifecycle.append({"event":"resume_or_focus_in","at_ms":Time.get_ticks_msec()})
	elif what in [NOTIFICATION_WM_GO_BACK_REQUEST,NOTIFICATION_WM_CLOSE_REQUEST]:
		_cancel_input();_save();get_tree().quit()

func _telemetry() -> void:
	var record: Dictionary={"map_id":model.map_id(),"position":[model.position().x,model.position().y],"facing":model.facing,
		"moving":model.moving,"held":[held.x,held.y],"paused":paused,"completed_moves":model.completed_moves,
		"blocked_moves":model.blocked_moves,"attacks":model.attacks,"revision":model.revision,
		"loaded_save":model.loaded,"save_status":model.save_status,"draw_items":world.last_draw_items,
		"fps":Engine.get_frames_per_second(),"memory_static_bytes":Performance.get_monitor(Performance.MEMORY_STATIC),
		"frame_ms":frames,"lifecycle":lifecycle,"touch_events":touch_events,
		"device_name":OS.get_name(),"elapsed_seconds":elapsed,"godot_version":Engine.get_version_info(),
		"last_tap":last_tap,"route_left":route.size(),"route_plan":route_plan,"route_stop":route_stop,"world_rect":[world.position.x,world.position.y,world.size.x,world.size.y],
		"camera":[world.camera.x,world.camera.y],"zoom":world.zoom,"viewport_size":[get_viewport_rect().size.x,get_viewport_rect().size.y],
		"window_position":[get_window().position.x,get_window().position.y],"window_size":[get_window().size.x,get_window().size.y],
		"scope":"P2 tech only; host/emulator metrics never Galaxy device results"}
	var file:=FileAccess.open("user://p2/diagnostics.json",FileAccess.WRITE)
	if file!=null:file.store_string(JSON.stringify(record));file.close()

func _capture() -> void:
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute("user://captures")
	get_viewport().get_texture().get_image().save_png("user://captures/%03d.png" %captures)
	captures+=1
