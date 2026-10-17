extends Control
## Ordinary offline play. Inspection and automated operators require explicit opt-in.
const Game = preload("res://state/gameplay_state.gd")
const Store = preload("res://storage/gameplay_store.gd")
const Content = preload("res://content/gameplay_content.gd")
const View = preload("res://render/gameplay_view.gd")
const Effect = preload("res://render/effect_preview.gd")
const ClassicList = preload("res://ui/classic_list.gd")
const Paper = preload("res://ui/parchment_panel.gd")
const ClassicSkin = preload("res://ui/classic_skin.gd")
const Stick = preload("res://input/touch_stick.gd")
const Navigation = preload("res://input/grid_navigation.gd")
const OriginalView = preload("res://render/original_view.gd")
const OWNER := "local-profile:default"
var game = Game.new()
var store = Store.new()
var content = Content.new()
var view
var menu: VBoxContainer
var play: VBoxContainer
var creation: VBoxContainer
var names: OptionButton
var name_input: LineEdit
var guardian: OptionButton
var nationality: OptionButton
var appearance: OptionButton
var message: Label
var status: Label
var help_text: Label
var goal_hint: Label
var panels: TabContainer
var bag
var equipment
var skills
var skill_description: Label
var attributes: RichTextLabel
var dialogue: PanelContainer
var dialogue_body: VBoxContainer
var dialogue_scroll: ScrollContainer
var dialogue_title: Label
var dialogue_pager: HBoxContainer
var dialogue_close: Button
var modal_shield: Control
var direction_picker: OptionButton
var audio: Array = []
var active_effects: Array = []
var projectiles: Array = []
var floating: Array = []
var selected_target := ""
var current_npc := ""
var save_path := ""
var clock := 0.0
var autosave := 0.0
var input_repeat := 0.0
var movement := Vector2i.ZERO
var touch_moves: Dictionary = {}
var character_animation := "standing"
var animation_until := 0.0
var actor_animations: Dictionary = {}
var actor_directions: Dictionary = {}
var actor_walk_until: Dictionary = {}
var last_state_revision := -1
var save_failure := false
var last_save_committed := false
var smoke := false
var smoke_request: Dictionary = {}
var smoke_report := ""
var frame_checkpoint := false
var startup_error := ""
var event_log: Array = []
var save_receipts: Array = []
var screenshot_queue: Array = []
var panel_clock := 0.0
var replay_result: Dictionary = {}
var mobile_controls: Control
var body: HBoxContainer
var side: VBoxContainer
var equipment_preview
var character_header: Label
var equipped_icons: Dictionary = {}
var quick_skill_buttons: Array[Button] = []
var skill_icon_cache: Dictionary = {}
var world_column: VBoxContainer
var hud_footer: PanelContainer
var action_dock: HBoxContainer
var hp_bar: ProgressBar
var mp_bar: ProgressBar
var stick
var panel_toggle: Button
var navigation_search: RefCounted
var navigation_goal:=Vector2i(-1,-1)
var navigation_reach:=0
var path: Array[Vector2i] = []
var arrival_action: Dictionary = {}
var tick_accumulator := 0.0
var render_accumulator := 0.0
var panel_dirty := true
var map_render_key := ""
var scenery_cache: Array = []
var visual_positions: Dictionary = {}
var frame_samples: Array[float] = []
var max_process_ms := 0.0
var input_received_ms := 0
var input_latencies: Array[float] = []
var chat_log: Array[String] = []
var last_message := ""
var keyboard_moves: Dictionary = {}
var history: RichTextLabel
var was_portrait:=false
var touch_action_buttons: Array[Button] = []
var dialogue_page := 0
const DIALOGUE_PAGE_SIZE := 10
var dialogue_rows: Array = []
var weapon_name_input: LineEdit
var feedback_pending_usec := 0
var visual_feedback_latencies: Array[float] = []
var profile_timeline: Array = []
var trace_enabled := false
var trace_destination := ""
var os_event_sequence := 0
var os_event_feedback_pending: Array[Dictionary] = []
var last_keyboard_height := 0
var save_definitions: Dictionary = {}
var suppress_emulated_until := 0
var runtime_monster_map := ""
var runtime_monster_ids: Array = []
var runtime_npc_ids: Array = []
var runtime_monster_count := -1
var equipment_slot_names: Array = []
var equipment_preview_look := ""
var position_observation_path := OS.get_environment("BARAM_POSITION_OBSERVATION")

func checkpoint(stage: String, details: Dictionary = {}) -> void:
	var value := {"stage":stage,"ticks_ms":Time.get_ticks_msec(),"pid":OS.get_process_id(),"platform":OS.get_name(),"details":details}
	print("GAMEPLAY_STAGE "+JSON.stringify(value))
	var path := "user://gameplay-checkpoints.jsonl"
	var file := FileAccess.open(path, FileAccess.READ_WRITE if FileAccess.file_exists(path) else FileAccess.WRITE)
	if file:
		file.seek_end()
		file.store_line(JSON.stringify(value))
		file.flush()

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	for arg in args:
		if arg.begins_with("--p2-"):
			get_tree().change_scene_to_file.call_deferred("res://inspection.tscn")
			return
	for feature in ["p2_gui_smoke","p2_priority_smoke","p2_original_smoke"]:
		if OS.has_feature(feature):
			get_tree().change_scene_to_file.call_deferred("res://inspection.tscn")
			return
	get_tree().auto_accept_quit = false
	_adapt_window_scale()
	get_window().size_changed.connect(_adapt_window_scale)
	trace_destination=OS.get_environment("BARAM_PLAYABILITY_TRACE")
	trace_enabled=not trace_destination.is_empty() or "--playability-observe" in args or (OS.has_feature("debug") and FileAccess.file_exists("user://playability-observe.enabled"))
	if trace_enabled and trace_destination.is_empty():trace_destination="user://playability-frame-timeline.jsonl"
	RenderingServer.frame_post_draw.connect(_presented_feedback)
	checkpoint("engine", {"version":Engine.get_version_info(),"user_data":OS.get_user_data_dir()})
	smoke = "--gameplay-smoke" in args
	if OS.has_feature("debug") and FileAccess.file_exists("user://gameplay-test-request.json"):
		var request: Variant = JSON.parse_string(FileAccess.get_file_as_string("user://gameplay-test-request.json"))
		DirAccess.remove_absolute("user://gameplay-test-request.json")
		if typeof(request) == TYPE_DICTIONARY and request.get("mode") == "smoke":
			smoke = true
			smoke_request = request
	smoke_report = OS.get_environment("BARAM_GAMEPLAY_REPORT")
	if smoke_report.is_empty(): smoke_report = "user://gameplay-smoke.json"
	var root := OS.get_environment("BARAM_GAMEPLAY_RUNTIME")
	if root.is_empty(): root = "res://private_runtime"
	if not content.open(root) or not game.configure(content.data):
		startup_error = "필수 게임 자료를 열 수 없습니다.\n"+"\n".join(content.errors)+"\n"+"\n".join(game.errors)
	if startup_error.is_empty():
		save_definitions=store.prepare_content(content.data)
		if save_definitions.is_empty():startup_error="저장용 게임 자료를 검증하지 못했습니다."
	checkpoint("manifest", {"ok":startup_error.is_empty(),"errors":content.errors,"game_errors":game.errors,"generation":content.manifest.get("generation")})
	_build_ui()
	if not startup_error.is_empty():
		message.text = startup_error
		if smoke: _finish_smoke({"status":"FAIL","reason":"INPUT_LOAD","errors":startup_error})
		return
	_refresh_characters()
	checkpoint("scene", {"mode":"ordinary_play" if not smoke else "explicit_smoke"})
	if smoke: _run_smoke.call_deferred()

func _adapt_window_scale() -> void:
	# Expand the canvas to the real surface instead of cropping portrait/odd
	# aspect ratios to a fixed 1100x720 render area. Keep touch sizes readable.
	var physical:=Vector2(get_window().size)
	var ui_scale:=maxf(1.0,minf(physical.x,physical.y)/720.0)
	get_window().content_scale_aspect=Window.CONTENT_SCALE_ASPECT_EXPAND
	get_window().content_scale_size=Vector2i((physical/ui_scale).round())

func _button(parent: Node, title: String, action: Callable, native_multitouch: bool = true) -> Button:
	var button := Button.new()
	button.text = title
	button.custom_minimum_size.y = 34
	button.pressed.connect(func(): _mark_input();action.call())
	if not native_multitouch:
		button.mouse_filter=Control.MOUSE_FILTER_PASS
		parent.add_child(button)
		return button
	# Native Button mouse emulation only covers one finger. Handle each real
	# screen-touch here so a second finger can attack while the stick is held.
	var touches: Dictionary = {}
	button.set_meta("native_touches",touches)
	button.gui_input.connect(func(event: InputEvent):
		if event is InputEventScreenTouch:
			if event.canceled:
				touches.erase(event.index);button.accept_event();return
			if event.pressed:
				touches[event.index]=true
			elif touches.has(event.index):
				touches.erase(event.index)
				if not button.disabled and Rect2(Vector2.ZERO,button.size).has_point(event.position): _mark_input();action.call()
			button.accept_event())
	touch_action_buttons=touch_action_buttons.filter(func(existing): return is_instance_valid(existing))
	touch_action_buttons.append(button)
	parent.add_child(button)
	return button

func _label(parent: Node, title: String) -> Label:
	var label := Label.new()
	label.text = title
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(label)
	return label

func _build_ui() -> void:
	var korean:=SystemFont.new()
	korean.font_names=PackedStringArray(["Malgun Gothic","Noto Sans CJK KR","NanumGothic","sans-serif"])
	ThemeDB.fallback_font=korean
	ClassicSkin.bind_original(content.assets.texture("kr491/images/dlgnew02-00000-baram-0.png"))
	self.theme=ClassicSkin.theme_for(korean)
	texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
	var background:=ColorRect.new();background.color=Color("24140c")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter=Control.MOUSE_FILTER_IGNORE;add_child(background)
	var margin:=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for edge in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_"+edge,5)
	add_child(margin)
	var root:=VBoxContainer.new();root.add_theme_constant_override("separation",3);margin.add_child(root)
	var title:=HBoxContainer.new();root.add_child(title)
	var heading:=_label(title,"바람의나라")
	heading.add_theme_font_size_override("font_size",14)
	heading.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	heading.add_theme_color_override("font_color",Color("dbc292"))
	panel_toggle=_button(title,"물품 · 기술 · 장비 · 능력치",_toggle_panels)
	panel_toggle.hide()
	menu=VBoxContainer.new();root.add_child(menu)
	_label(menu,"오프라인 캐릭터 · 한국 원본 그림을 사용한 개인용 게임")
	names=OptionButton.new();menu.add_child(names)
	_button(menu,"이어 하기",_continue_character)
	_button(menu,"새 캐릭터",_show_creation)
	creation=VBoxContainer.new();menu.add_child(creation)
	_label(creation,"이름 (한글·영문·숫자 2~12자) · 평민 Lv1")
	name_input=LineEdit.new();name_input.placeholder_text="캐릭터 이름";name_input.max_length=12
	name_input.virtual_keyboard_enabled=true;name_input.custom_minimum_size.y=40
	creation.add_child(name_input)
	nationality=OptionButton.new()
	for value in ["고구려","부여"]: nationality.add_item(value)
	creation.add_child(nationality)
	guardian=OptionButton.new()
	for value in ["주작","청룡","백호","현무"]: guardian.add_item(value)
	creation.add_child(guardian)
	appearance=OptionButton.new();appearance.add_item("모습 1");appearance.add_item("모습 2")
	creation.add_child(appearance)
	_button(creation,"만들고 시작",_create_character)
	_button(creation,"취소",func(): creation.hide();name_input.clear();message.text="캐릭터를 만들지 않았습니다.")
	creation.hide()
	play=VBoxContainer.new();play.size_flags_vertical=Control.SIZE_EXPAND_FILL;root.add_child(play);play.hide()
	goal_hint=_label(play,"");goal_hint.add_theme_font_size_override("font_size",13)
	goal_hint.add_theme_color_override("font_color",Color("e9c987"))
	body=HBoxContainer.new();body.add_theme_constant_override("separation",0);body.size_flags_vertical=Control.SIZE_EXPAND_FILL;play.add_child(body)
	world_column=VBoxContainer.new();world_column.add_theme_constant_override("separation",0)
	world_column.size_flags_horizontal=Control.SIZE_EXPAND_FILL;body.add_child(world_column)
	var world_frame:=Paper.new();world_frame.compact=true
	world_frame.size_flags_vertical=Control.SIZE_EXPAND_FILL;world_column.add_child(world_frame)
	view=View.new();view.content=content.assets
	view.custom_minimum_size=Vector2(220,180)
	view.size_flags_horizontal=Control.SIZE_EXPAND_FILL;view.size_flags_vertical=Control.SIZE_EXPAND_FILL
	view.world_pressed.connect(_click_world);world_frame.add_child(view)
	side=VBoxContainer.new();side.custom_minimum_size.x=310;body.add_child(side)
	var paper:=Paper.new();paper.size_flags_vertical=Control.SIZE_EXPAND_FILL;side.add_child(paper)
	var sheet:=VBoxContainer.new();sheet.add_theme_constant_override("separation",3);paper.add_child(sheet)
	character_header=_label(sheet,"");character_header.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	character_header.add_theme_color_override("font_color",Color("402815"))
	character_header.add_theme_font_size_override("font_size",15)
	var portrait:=HBoxContainer.new();portrait.alignment=BoxContainer.ALIGNMENT_CENTER;sheet.add_child(portrait)
	for slot in ["weapon","portrait","armor"]:
		if slot=="portrait":
			equipment_preview=OriginalView.new();equipment_preview.content=content.assets
			equipment_preview.background_color=Color(0,0,0,0)
			equipment_preview.custom_minimum_size=Vector2(112,118)
			equipment_preview.mouse_filter=Control.MOUSE_FILTER_IGNORE;portrait.add_child(equipment_preview)
		else:
			var slot_box:=VBoxContainer.new();slot_box.alignment=BoxContainer.ALIGNMENT_CENTER;portrait.add_child(slot_box)
			var slot_label:=_label(slot_box,"무기" if slot=="weapon" else "갑옷")
			slot_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;slot_label.add_theme_font_size_override("font_size",12)
			slot_label.add_theme_color_override("font_color",Color("67431f"))
			var icon_button:=_button(slot_box,"",func(): panels.current_tab=2)
			icon_button.custom_minimum_size=Vector2(40,46);icon_button.expand_icon=true
			icon_button.add_theme_constant_override("icon_max_width",30)
			equipped_icons[slot]=icon_button
	panels=TabContainer.new();panels.size_flags_vertical=Control.SIZE_EXPAND_FILL
	panels.add_theme_stylebox_override("panel",StyleBoxEmpty.new())
	sheet.add_child(panels)
	panels.tab_changed.connect(func(_index): _stop_motion();panel_dirty=true)
	var bag_box:=VBoxContainer.new();bag_box.name="물품";panels.add_child(bag_box)
	bag=ClassicList.new();bag.size_flags_vertical=Control.SIZE_EXPAND_FILL;bag_box.add_child(bag)
	bag.item_selected.connect(func(_index): _stop_motion())
	var bag_actions:=HBoxContainer.new();bag_box.add_child(bag_actions)
	var use_button:=_button(bag_actions,"장착 / 사용",_use_selected_item);use_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var sell_button:=_button(bag_actions,"판매 (1개)",_sell_selected);sell_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	sell_button.tooltip_text="가까운 상인에게 판매 (1개)"
	var skill_box:=VBoxContainer.new();skill_box.name="기술";panels.add_child(skill_box)
	var skill_scroll:=ScrollContainer.new();skill_scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL
	skill_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;skill_box.add_child(skill_scroll)
	var skill_controls:=VBoxContainer.new();skill_controls.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	skill_controls.size_flags_vertical=Control.SIZE_EXPAND_FILL;skill_scroll.add_child(skill_controls)
	skills=ClassicList.new();skills.custom_minimum_size.y=76;skills.size_flags_vertical=Control.SIZE_EXPAND_FILL;skill_controls.add_child(skills)
	skills.item_selected.connect(func(_index): _stop_motion();_describe_skill())
	skill_description=_label(skill_controls,"")
	skill_description.add_theme_color_override("font_color",Color("302012"))
	skill_description.add_theme_font_size_override("font_size",13)
	direction_picker=OptionButton.new()
	for value in ["동","서","남","북"]: direction_picker.add_item(value)
	skill_controls.add_child(direction_picker)
	_button(skill_controls,"선택 기술 사용",_cast_selected)
	var hotkey:=HBoxContainer.new();skill_controls.add_child(hotkey)
	for slot in [1,2,3]:
		var number:=str(slot)
		_button(hotkey,number+"번 지정",func():
			var id:=_selection(skills)
			if id.is_empty(): message.text="기술을 먼저 고르세요.";return
			_dispatch({"type":"bind_hotkey","slot":number,"skill_id":id}))
	var equip_box:=VBoxContainer.new();equip_box.name="장비";panels.add_child(equip_box)
	equipment=ClassicList.new();equipment.size_flags_vertical=Control.SIZE_EXPAND_FILL;equip_box.add_child(equipment)
	equipment.item_selected.connect(func(_index): _stop_motion())
	var equipment_actions:=HBoxContainer.new();equip_box.add_child(equipment_actions)
	var remove_button:=_button(equipment_actions,"선택 부위 해제",_unequip_selected);remove_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var repair_button:=_button(equipment_actions,"대장장이에게 수리",_repair_selected);repair_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	attributes=RichTextLabel.new();attributes.name="능력치";attributes.scroll_active=true
	attributes.add_theme_color_override("default_color",Color("302012"));panels.add_child(attributes)
	var vitals:=PanelContainer.new();sheet.add_child(vitals)
	var vitals_style:=ClassicSkin.patch(ClassicSkin.wood(),Vector4(5,3,5,3),Vector4(7,7,7,7))
	vitals_style.modulate_color=Color("a38a70");vitals.add_theme_stylebox_override("panel",vitals_style)
	var stats:=VBoxContainer.new();stats.add_theme_constant_override("separation",2);vitals.add_child(stats)
	status=_label(stats,"");status.add_theme_font_size_override("font_size",13)
	status.add_theme_color_override("font_color",Color("f2db9b"))
	for kind in ["체력","마력"]:
		var line:=HBoxContainer.new();line.add_theme_constant_override("separation",5);stats.add_child(line)
		var caption:=_label(line,kind);caption.add_theme_font_size_override("font_size",12)
		caption.custom_minimum_size.x=28;caption.autowrap_mode=TextServer.AUTOWRAP_OFF
		caption.add_theme_color_override("font_color",Color("efd39b"))
		var meter:=ProgressBar.new();meter.custom_minimum_size=Vector2(0,15);meter.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		meter.show_percentage=false;line.add_child(meter)
		var empty:=ClassicSkin.patch(ClassicSkin.wood(),Vector4(4,3,4,3),Vector4.ZERO);empty.modulate_color=Color("6a5044")
		meter.add_theme_stylebox_override("background",empty)
		var fill:=ClassicSkin.patch(ClassicSkin.parchment(),Vector4(2,2,2,2),Vector4.ZERO)
		fill.modulate_color=Color("c83d26") if kind=="체력" else Color("366fbd")
		meter.add_theme_stylebox_override("fill",fill)
		if kind=="체력":hp_bar=meter
		else:mp_bar=meter
	hud_footer=Paper.new();hud_footer.compact=true;world_column.add_child(hud_footer)
	var footer:=VBoxContainer.new();footer.add_theme_constant_override("separation",2);hud_footer.add_child(footer)
	var quick:=HBoxContainer.new();quick.add_theme_constant_override("separation",3);footer.add_child(quick)
	action_dock=quick
	_button(quick,"지도",_show_map);_button(quick,"대화",_talk_nearest);_button(quick,"줍기",_pickup_nearest)
	for slot in ["1","2","3"]:
		var key: String=slot
		var skill_button:=_button(quick,key,func(): _cast_hotkey(key))
		skill_button.expand_icon=true;skill_button.add_theme_constant_override("icon_max_width",23)
		skill_button.custom_minimum_size=Vector2(49,34);quick_skill_buttons.append(skill_button)
	var spacer:=Control.new();spacer.size_flags_horizontal=Control.SIZE_EXPAND_FILL;quick.add_child(spacer)
	_button(quick,"부활",func(): _dispatch({"type":"respawn"}))
	_button(quick,"저장",_return_menu)
	help_text=_label(footer,"지면 탭: 걸어가기 · 드래그: 이동 · Space: 공격 · Enter: 대화 · Z: 줍기 · Tab: 패널")
	help_text.add_theme_font_size_override("font_size",12)
	help_text.add_theme_color_override("font_color",Color("594326"))
	modal_shield=Control.new();modal_shield.name="ModalShield"
	modal_shield.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	modal_shield.mouse_filter=Control.MOUSE_FILTER_STOP;add_child(modal_shield);modal_shield.hide()
	dialogue=Paper.new();dialogue.name="Dialogue";dialogue.custom_minimum_size=Vector2(300,180);add_child(dialogue)
	var dialogue_layout:=VBoxContainer.new();dialogue_layout.add_theme_constant_override("separation",6)
	dialogue.add_child(dialogue_layout)
	var dialogue_header:=HBoxContainer.new();dialogue_layout.add_child(dialogue_header)
	dialogue_title=_label(dialogue_header,"");dialogue_title.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	dialogue_title.add_theme_color_override("font_color",Color("302012"))
	var close_x:=_button(dialogue_header,"X",_close_dialogue)
	close_x.name="CloseX";close_x.tooltip_text="닫기 · Esc / 뒤로가기";close_x.custom_minimum_size=Vector2(48,44)
	dialogue_scroll=ScrollContainer.new();dialogue_scroll.custom_minimum_size=Vector2(0,40)
	dialogue_scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL
	dialogue_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
	dialogue_layout.add_child(dialogue_scroll)
	dialogue_body=VBoxContainer.new();dialogue_body.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	dialogue_scroll.add_child(dialogue_body)
	dialogue_pager=HBoxContainer.new();dialogue_layout.add_child(dialogue_pager)
	dialogue_close=_button(dialogue_layout,"닫기 / 취소",_close_dialogue)
	dialogue_close.name="CloseFooter";dialogue_close.custom_minimum_size.y=44
	dialogue.visibility_changed.connect(func(): modal_shield.visible=dialogue.visible)
	dialogue.hide()
	message=_label(root,"로컬 캐릭터를 선택하거나 새로 만드세요.")
	message.add_theme_color_override("font_color",Color("f1ddae"))
	message.custom_minimum_size.y=25
	history=RichTextLabel.new();history.custom_minimum_size.y=52;history.scroll_following=true
	var chat_style:=ClassicSkin.patch(ClassicSkin.parchment(),Vector4(3,3,3,3),Vector4(5,3,5,3))
	chat_style.modulate_color=Color("7481bf")
	history.add_theme_stylebox_override("normal",chat_style)
	history.add_theme_color_override("default_color",Color("fff1c9"));history.add_theme_font_size_override("normal_font_size",13)
	footer.add_child(history)
	for i in range(8):
		var player:=AudioStreamPlayer.new();player.volume_db=-8;add_child(player);audio.append(player)
	_build_touch();resized.connect(_resize_ui);_resize_ui()

func _build_touch() -> void:
	# Dynamic stick is also mouse-draggable on PC. No permanent arrow grid.
	stick=Stick.new();stick.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	view.add_child(stick)
	stick.direction_changed.connect(func(move):
		path.clear();arrival_action.clear();movement=move
		if move!=Vector2i.ZERO: _mark_input();_advance_movement())
	stick.tapped.connect(func(position):
		var world: Vector2=(position-view.size*0.5)/view.zoom+view.focus
		_click_world(Vector2i(floori(world.x/24),floori(world.y/24))))
	# Keep the two-finger action targets below the map; their hit regions must
	# not hide doors, monsters, or the tile used by ordinary tap navigation.
	var overlay:=HBoxContainer.new();overlay.add_theme_constant_override("separation",3)
	action_dock.add_child(overlay);action_dock.move_child(overlay,6)
	mobile_controls=overlay;overlay.hide()
	var attack:=_button(overlay,"공격",_basic_attack)
	var skill:=_button(overlay,"기술",_cast_selected)
	for button in [attack,skill]:
		button.custom_minimum_size=Vector2(64,48)
		button.focus_mode=Control.FOCUS_NONE

func _begin_touch_move(move: Vector2i) -> void:
	movement=move;path.clear();arrival_action.clear();_advance_movement()

func _mark_input() -> void:
	if game.state.is_empty() or not play.visible: return
	input_received_ms=Time.get_ticks_msec()
	if feedback_pending_usec==0: feedback_pending_usec=Time.get_ticks_usec()
	if trace_enabled: profile_timeline.append({"kind":"input","us":Time.get_ticks_usec()})

func _presented_feedback() -> void:
	if trace_enabled and not os_event_feedback_pending.is_empty():
		var rendered_usec:=Time.get_ticks_usec()
		for received in os_event_feedback_pending:
			profile_timeline.append({"kind":"os_event_frame_post_draw_feedback","us":rendered_usec,"event_id":received.event_id,"event_us":received.us,"elapsed_ms":float(rendered_usec-int(received.us))/1000.0})
		os_event_feedback_pending.clear()
	if feedback_pending_usec==0: return
	var elapsed:=float(Time.get_ticks_usec()-feedback_pending_usec)/1000.0
	visual_feedback_latencies.append(elapsed)
	if trace_enabled: profile_timeline.append({"kind":"frame_post_draw_feedback","us":Time.get_ticks_usec(),"elapsed_ms":elapsed})
	feedback_pending_usec=0

func _observe_os_input(event: InputEvent) -> void:
	# Observe receipt before GUI callbacks without changing input handling. This
	# clock ends at engine post-draw, not at physical OS pixel presentation.
	if not trace_enabled or game.state.is_empty() or not play.visible: return
	var received: Dictionary={"kind":"os_input_received","us":Time.get_ticks_usec(),"event_id":os_event_sequence,"device":event.device}
	if event is InputEventKey:
		received.merge({"event_type":"key","physical_keycode":event.physical_keycode,"physical_key_name":OS.get_keycode_string(event.physical_keycode),"pressed":event.pressed,"echo":event.echo})
	elif event is InputEventMouseButton:
		received.merge({"event_type":"mouse_button","button":event.button_index,"pressed":event.pressed,"x":event.position.x,"y":event.position.y})
	elif event is InputEventScreenTouch:
		received.merge({"event_type":"touch","index":event.index,"pressed":event.pressed,"canceled":event.canceled,"x":event.position.x,"y":event.position.y})
	else: return
	os_event_sequence+=1
	profile_timeline.append(received)
	os_event_feedback_pending.append(received)

func _stop_motion() -> void:
	navigation_search=null
	navigation_goal=Vector2i(-1,-1)
	movement=Vector2i.ZERO;touch_moves.clear();keyboard_moves.clear();path.clear();arrival_action.clear()
	if is_instance_valid(stick): stick.cancel()
	for button in touch_action_buttons:
		if is_instance_valid(button): button.get_meta("native_touches",{}).clear()

func _toggle_panels() -> void:
	_stop_motion();side.visible=not side.visible

func _resize_ui() -> void:
	if panels==null: return
	var portrait:=size.x<760
	panel_toggle.visible=portrait
	if portrait and not was_portrait: side.hide()
	if not portrait: side.show()
	was_portrait=portrait
	side.custom_minimum_size.x=clampf(size.x*0.29,270,330)
	equipment_preview.custom_minimum_size.y=64 if size.y<540 else 82 if size.y<620 else 118
	if not game.state.is_empty():_refresh_equipment_preview();_refresh_vitals()
	history.custom_minimum_size.y=38 if size.y<620 else 52
	for quick_button in quick_skill_buttons:quick_button.visible=size.x>=560
	help_text.visible=size.y>620
	if is_instance_valid(dialogue):
		var keyboard_height:=float(DisplayServer.virtual_keyboard_get_height()) if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD) else 0.0
		var screen_scale_y:=maxf(0.01,float(get_window().size.y)/maxf(1.0,get_viewport_rect().size.y))
		keyboard_height/=screen_scale_y
		var available:=Vector2(size.x,maxf(180,size.y-keyboard_height))
		dialogue.custom_minimum_size=Vector2(minf(300,available.x-16),minf(180,available.y-16))
		dialogue.size=Vector2(minf(540,available.x-16),minf(500,available.y-16))
		dialogue.position=(available-dialogue.size)*0.5

func _close_dialogue() -> void:
	# A modal cancellation only ends interaction; it never rolls back a trade.
	dialogue.hide();current_npc="";_stop_motion();selected_target=""
	suppress_emulated_until=Time.get_ticks_msec()+150
	weapon_name_input=null
	if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):DisplayServer.virtual_keyboard_hide()
	get_viewport().gui_release_focus()
	if trace_enabled:_layout_checkpoint.call_deferred()

func _restore_dialogue_scroll(value: int, npc_id: String, page: int) -> void:
	await get_tree().process_frame
	if dialogue.visible and current_npc==npc_id and dialogue_page==page:
		dialogue_scroll.scroll_vertical=value

func _refresh_characters() -> void:
	names.clear()
	DirAccess.make_dir_recursive_absolute("user://gameplay-p3/characters")
	var directory := DirAccess.open("user://gameplay-p3/characters")
	if directory:
		for file in directory.get_files():
			if not file.ends_with(".json"): continue
			var path := "user://gameplay-p3/characters/"+file
			var saved: Dictionary = store.read_game(path,OWNER,save_definitions)
			if saved.has("payload"):
				var c: Dictionary = saved.payload.character
				names.add_item(str(c.name)+" · Lv"+str(c.level)+" "+_job_name(str(c.job)))
				names.set_item_metadata(names.item_count-1,path)
			else:
				names.add_item("보존된 진행 · 확인 필요 ("+str(saved.status)+")")
				names.set_item_metadata(names.item_count-1,path)
	if names.item_count == 0: names.add_item("아직 캐릭터가 없습니다")

func _create_character() -> void:
	var name := name_input.text.strip_edges()
	var path := "user://gameplay-p3/characters/"+(OWNER+":"+name).sha256_text().substr(0,24)+".json"
	if FileAccess.file_exists(path): message.text="같은 이름의 캐릭터가 있습니다. 이어 하기를 사용하세요."; return
	game.state = {}
	var result: Dictionary = game.create_character(name,OWNER,{"nationality":nationality.get_item_text(nationality.selected),"guardian":guardian.get_item_text(guardian.selected),"appearance":{"variant":appearance.selected}})
	if result.status != "OK": message.text="이름을 확인하세요: "+str(result.reason); return
	save_path = path
	if not _save(): game.state={}; return
	_start_play()
	checkpoint("character_created",{"name":name,"level":1,"job":"commoner","skills":game.state.skills})

func _continue_character() -> void:
	if names.selected < 0: return
	var path: Variant = names.get_item_metadata(names.selected)
	if typeof(path) != TYPE_STRING: return
	var load_started:=Time.get_ticks_usec()
	var loaded: Dictionary = store.read_game(path,OWNER,save_definitions,true)
	if not loaded.has("payload"): message.text="불러오기 보류: "+str(loaded.status); return
	game.state = {}
	var restored: Dictionary = game.restore(loaded.payload)
	if restored.status != "OK": message.text="진행 보존 후 불러오기 보류: "+str(restored.reason); return
	save_path = path
	_start_play()
	checkpoint("loaded",{"revision":game.state.revision,"character":game.state.character,"duration_ms":float(Time.get_ticks_usec()-load_started)/1000.0,"backup_preparation":loaded.get("backup_preparation",{})})

func _start_play() -> void:
	menu.hide(); play.show(); dialogue.hide()
	message.reparent(hud_footer.get_child(0));hud_footer.get_child(0).move_child(message,1)
	message.add_theme_color_override("font_color",Color("4d331d"))
	message.add_theme_font_size_override("font_size",13)
	if is_instance_valid(mobile_controls): mobile_controls.show()
	save_failure = false
	selected_target = ""; current_npc = ""
	frame_samples.clear();visual_feedback_latencies.clear();input_latencies.clear();profile_timeline.clear()
	os_event_feedback_pending.clear();os_event_sequence=0
	max_process_ms=0;runtime_monster_map="";runtime_monster_count=-1;equipment_slot_names.clear();equipment_preview_look="";autosave=0
	if trace_enabled:profile_timeline.append({"kind":"clock_sync","us":Time.get_ticks_usec(),"unix_us":int(Time.get_unix_time_from_system()*1000000.0)})
	get_viewport().gui_release_focus()
	message.text="지면을 누르거나 드래그해서 이동하세요. 공격은 가까운 몬스터를 자동으로 찾습니다."
	_stop_motion();visual_positions.clear();map_render_key="";panel_dirty=true
	_refresh_panels(); _render_world()
	_observe_position("PLAY_STARTED")
	_layout_checkpoint.call_deferred()

func _show_creation() -> void:
	creation.show(); name_input.grab_focus()
	_layout_checkpoint.call_deferred()

func _layout_checkpoint() -> void:
	await get_tree().process_frame
	var controls: Array=[]
	var pending: Array=[self]
	while not pending.is_empty():
		var node: Node=pending.pop_back()
		pending.append_array(node.get_children())
		if (node is Button or node is LineEdit) and node.is_visible_in_tree():
			var rect: Rect2=node.get_global_rect()
			controls.append({"class":node.get_class(),"text":str(node.text) if node is Button else "name_input","rect":[rect.position.x,rect.position.y,rect.size.x,rect.size.y]})
	var scroll_regions: Dictionary={}
	for pair in [["dialogue",dialogue_scroll],["bag",bag],["skills",skills],["equipment",equipment]]:
		var region=pair[1]
		if not is_instance_valid(region): continue
		var rect: Rect2=region.get_global_rect()
		scroll_regions[pair[0]]={"rect":[rect.position.x,rect.position.y,rect.size.x,rect.size.y],"scroll_vertical":region.scroll_vertical,"visible":region.is_visible_in_tree()}
	checkpoint("ui_layout",{"controls":controls,"scroll_regions":scroll_regions,"view_rect":[view.get_global_rect().position.x,view.get_global_rect().position.y,view.size.x,view.size.y],"view_zoom":view.zoom,"view_focus":[view.focus.x,view.focus.y],"character_position":game.state.get("character",{}).duplicate()})

func _save() -> bool:
	if game.state.is_empty() or save_path.is_empty(): return false
	var owner := str(game.state.character.owner_id) if smoke else OWNER
	var save_started:=Time.get_ticks_usec()
	last_save_committed=false
	var snapshot: Dictionary=game.snapshot()
	var receipt: Dictionary = store.write_game(save_path,snapshot,owner,save_definitions)
	if receipt.status=="COMMITTED_ACK_LOST":
		# The atomic rename already committed. Never roll memory back to a
		# revision older than disk merely because acknowledgement was lost.
		last_save_committed=true
		var confirmed: Dictionary=store.read_game(save_path,owner,save_definitions)
		if confirmed.has("payload") and store._canonical(confirmed.payload)==store._canonical(snapshot):
			receipt={"status":"SAVED","reason":"COMMIT_CONFIRMED_BY_READBACK","revision":int(snapshot.revision)}
	save_receipts.append({"status":receipt.status,"revision":game.state.revision,"time":clock,"duration_ms":float(Time.get_ticks_usec()-save_started)/1000.0})
	if trace_enabled: profile_timeline.append({"kind":"save","us":Time.get_ticks_usec(),"status":receipt.status,"revision":game.state.revision,"duration_ms":float(Time.get_ticks_usec()-save_started)/1000.0,"phases":store.last_timings.duplicate()})
	if save_receipts.size()>64: save_receipts.pop_front()
	if receipt.status not in ["SAVED","UNCHANGED","OK"]:
		save_failure = true
		message.text="저장 실패 · 진행을 보존하고 행동을 중지합니다: "+str(receipt.status)+" "+str(receipt.get("reason",""))
		checkpoint("save_failed",receipt)
		return false
	autosave=0
	checkpoint("save",{"revision":game.state.revision,"status":receipt.status,"duration_ms":float(Time.get_ticks_usec()-save_started)/1000.0})
	return true

func _dispatch(command: Dictionary) -> Dictionary:
	if game.state.is_empty() or save_failure: return {"status":"REFUSED","reason":"NO_ACTIVE_OR_SAVED_STATE","events":[]}
	var before: Dictionary = game.state
	command = command.duplicate(true)
	if not smoke or not command.has("request_id"):
		command["request_id"] = "ui:"+str(int(game.state.request_watermarks.get("ui",0))+1)
	var result: Dictionary = game.command(command)
	if result.get("changed",false) and str(command.type) not in ["move","attack","cast"]:
		if not _save():
			if not last_save_committed:game.state=before
			return {"status":"SAVE_FAILED","events":[]}
	_consume_events(result.get("events",[]))
	if result.status not in ["OK","DUPLICATE","CANCELLED"] and (result.reason not in ["ACTION_COOLDOWN","MOVE_COOLDOWN"] or command.type in ["attack","cast"]):
		message.text = _reason(str(result.reason))
	if result.get("changed",false):
		if command.type not in ["move","attack","cast"]: panel_dirty=true
		if command.type in ["move","attack","cast"] and input_received_ms>0:
			input_latencies.append(float(Time.get_ticks_msec()-input_received_ms));input_received_ms=0
	_observe_position(str(result.status))
	return result

func _observe_position(command_status: String) -> void:
	# Optional read-only OS-input telemetry, separate from the save protocol.
	if position_observation_path.is_empty() or game.state.is_empty():return
	var c: Dictionary=game.state.character
	var value: Dictionary={"character":{"map_id":c.map_id,"x":c.x,"y":c.y,"direction":c.direction,"dead":c.dead},"revision":game.state.revision,"last_command_status":command_status,"ticks_usec":Time.get_ticks_usec()}
	var file:=FileAccess.open(position_observation_path,FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(value))

func _consume_events(events: Array) -> void:
	for event in events:
		event_log.append(event)
		if event_log.size()>200: event_log.pop_front()
		var type := str(event.type)
		var event_skill: Dictionary=content.data.skills.get(str(event.get("skill_id","")),{})
		var targeted_summary:=type=="skill_applied" and (str(event.get("kind","")) in ["damage","debuff"] or (str(event.get("kind",""))=="status" and str(event_skill.get("target","monster"))!="self"))
		# Damage already has target-local monster_hit events. The later summary
		# must not spawn the same impact and sound again at the caster's feet.
		if not targeted_summary and event.get("sound_id") != null: _sound(str(event.sound_id))
		if not targeted_summary and event.get("effect_id") != null and type!="projectile_started":
			active_effects.append({"id":str(event.effect_id),"at":clock,"map_id":event.get("map_id",game.state.character.map_id),"x":event.get("x",game.state.character.x),"y":event.get("y",game.state.character.y)})
		if type=="status_applied" and str(event_skill.get("kind",""))!="damage":
			var target: Dictionary=game.state.monsters.get(str(event.get("target_id","")),{})
			if not target.is_empty():
				if event_skill.get("effect_id")!=null:active_effects.append({"id":str(event_skill.effect_id),"at":clock,"map_id":target.map_id,"x":target.x,"y":target.y})
				if event_skill.get("sound_id")!=null:_sound(str(event_skill.sound_id))
		if type=="projectile_started":
			var projectile: Dictionary=event.duplicate(true)
			projectile.at=clock;projectiles.append(projectile)
			if projectiles.size()>64: projectiles.pop_front()
		if type in ["moved","monster_moved"]:
			var visual_id:="player" if type=="moved" else str(event.target_id)
			var from:=Vector2(float(event.from.x),float(event.from.y))
			if visual_positions.has(visual_id): from=_visual_point(visual_id,from.x,from.y)
			visual_positions[visual_id]={"from":from,"to":Vector2(float(event.x),float(event.y)),"at":clock,"duration":float(content.data.config.get("move_interval",0.16)) if type=="moved" else 0.2}
		if type in ["attack_started","cast_started","moved"]:
			character_animation = {"attack_started":"attack","cast_started":"casting","moved":"walking"}[type]
			animation_until = clock + (0.22 if type=="moved" else 0.55)
		if type == "monster_attack_started": actor_animations[str(event.get("target_id",""))] = clock+0.5
		if type == "monster_moved":
			var id:=str(event.target_id)
			var dx:=int(event.x)-int(event.from.x); var dy:=int(event.y)-int(event.from.y)
			actor_directions[id]=1 if dx>0 else 3 if dx<0 else 2 if dy>0 else 0
			actor_walk_until[id]=clock+0.3
		if type=="player_inspected":
			side.show();panels.current_tab=0 if "inventory" in event.get("fields",[]) else 3
			message.text="물품과 능력을 확인했습니다. 오른쪽 패널을 확인하세요."
		if type=="nearby_revealed":
			var found: PackedStringArray=[]
			for point in event.get("positions",[]):
				var monster: Dictionary=game.state.monsters.get(str(point.id),{})
				var definition: Dictionary=content.data.monsters.get(str(monster.get("monster_id","")),{})
				found.append(str(definition.get("name","기척"))+" ("+str(int(point.x))+", "+str(int(point.y))+")")
			message.text="주변 기척: "+(" · ".join(found) if not found.is_empty() else "없음")
		if type == "monster_died" and selected_target==str(event.get("target_id","")): selected_target=""
		if type == "dialogue": _show_dialogue(str(event.npc_id))
		if type == "map_changed":
			selected_target="";_stop_motion();visual_positions.clear();map_render_key="";dialogue.hide();message.text=str(content.data.maps[event.map_id].name)
		if type not in ["moved","monster_moved","attack_started","monster_attack_started"]: panel_dirty=true
		if type=="player_died": _stop_motion()
		if event.get("sound_id")==null and type in ["picked_up","bought","sold","equipped","unequipped","player_died"]:
			var key:=str({"picked_up":"pickup","bought":"transaction","sold":"transaction","equipped":"equip","unequipped":"equip","player_died":"death"}[type])
			_sound(str(content.data.config.get("audio",{}).get(key,{"pickup":2,"transaction":12,"equip":13,"death":10}[key])))
		if type in ["level_up","job_changed","skill_learned","bought","sold","equipped","unequipped","healed","resurrected","player_died","item_used","quest_accepted","quest_completed","crafted","advanced","summoned","item_identified","revived","trained","stored","withdrawn","weapon_named"]:
			message.text = _event_text(event)
		if type == "monster_hit":
			floating.append({"text":"-"+str(event.damage),"x":event.x,"y":event.y,"at":clock})
		if type == "player_died": dialogue.hide()

func _sound(id: String) -> void:
	var definition: Dictionary = content.sounds.get(id,{})
	var path := str(definition.get("wav",definition.get("path","")))
	if path.is_empty(): return
	if not path.begins_with("kr491/"): path="kr491/"+path
	var stream = content.assets.sound(path)
	if stream == null: return
	for player in audio:
		if not player.playing: player.stream=stream; player.play(); return

func _process(delta: float) -> void:
	var started:=Time.get_ticks_usec()
	clock+=delta;panel_clock+=delta;render_accumulator+=delta
	if not game.state.is_empty() and play.visible and frame_samples.size()<180000: frame_samples.append(delta*1000.0)
	if dialogue!=null and dialogue.visible:
		var keyboard_height:=DisplayServer.virtual_keyboard_get_height() if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD) else 0
		if keyboard_height!=last_keyboard_height: last_keyboard_height=keyboard_height;_resize_ui()
	if not frame_checkpoint and is_instance_valid(view) and startup_error.is_empty():
		# A process callback is not evidence that the OS presented a visible frame.
		frame_checkpoint=true;checkpoint("process_ready",{"mode":"menu","viewport":[size.x,size.y],"scope":"process_and_layout_only_not_visible_presentation"})
		_layout_checkpoint.call_deferred()
	if game.state.is_empty() or not play.visible or save_failure: return
	if message.text!=last_message:
		last_message=message.text;chat_log.append(last_message)
		if chat_log.size()>32: chat_log.pop_front()
		history.text="\n".join(chat_log)
	if not smoke:
		autosave+=delta
		tick_accumulator+=minf(delta,0.5)
		if tick_accumulator>=0.05:
			var before: Dictionary=game.state
			var result: Dictionary=game.tick(tick_accumulator)
			tick_accumulator=0
			var critical:=false
			for event in result.get("events",[]):
				if str(event.type) in ["monster_died","skill_applied","player_died","level_up"]: critical=true
			if critical and not _save():
				if not last_save_committed:game.state=before
			else: _consume_events(result.get("events",[]))
			if autosave>=3.0: _save()
			if not dialogue.visible: _advance_movement()
	if panel_clock>=0.2:
		panel_clock=0
		if panel_dirty: _refresh_panels();panel_dirty=false
		else: _refresh_vitals()
	if render_accumulator>=1.0/60.0:
		render_accumulator=0;_render_world()
	var process_ms:=float(Time.get_ticks_usec()-started)/1000.0
	max_process_ms=maxf(max_process_ms,process_ms)
	if trace_enabled: profile_timeline.append({"kind":"frame","us":Time.get_ticks_usec(),"interval_ms":delta*1000.0,"process_ms":process_ms,"memory_bytes":OS.get_static_memory_usage()})

func _advance_movement() -> void:
	if game.state.is_empty() or dialogue.visible or save_failure: return
	if not game._ready("move") or not game._ready("action"): return
	var move:=movement
	if move!=Vector2i.ZERO:
		navigation_search=null;navigation_goal=Vector2i(-1,-1);path.clear();arrival_action.clear()
	if move==Vector2i.ZERO and path.is_empty() and navigation_goal.x>=0:
		var current:=Vector2i(game.state.character.x,game.state.character.y)
		if absi(current.x-navigation_goal.x)+absi(current.y-navigation_goal.y)>navigation_reach:
			if navigation_search==null:
				navigation_search=Navigation.new();navigation_search.begin(game,navigation_goal,navigation_reach)
			if not navigation_search.advance(96):return
			path=navigation_search.result;navigation_search=null
			if path.is_empty():_stop_motion();message.text="가까운 적이나 막힌 길을 피해서 다시 눌러 주세요.";return
		else:navigation_goal=Vector2i(-1,-1)

	if move==Vector2i.ZERO and not path.is_empty():
		var cell:=path[0];var c: Dictionary=game.state.character
		move=cell-Vector2i(c.x,c.y)
		if absi(move.x)+absi(move.y)!=1: path.clear();arrival_action.clear();return
	if move==Vector2i.ZERO: return
	var result:=_dispatch({"type":"move","dx":move.x,"dy":move.y})
	if result.status=="OK":
		if not path.is_empty(): path.pop_front()
		if path.is_empty() and not arrival_action.is_empty() and absi(int(game.state.character.x)-navigation_goal.x)+absi(int(game.state.character.y)-navigation_goal.y)<=navigation_reach:
			var action:=arrival_action.duplicate();arrival_action.clear();_dispatch(action)
	elif result.reason not in ["ACTION_COOLDOWN","MOVE_COOLDOWN"]:
		path.clear();arrival_action.clear()

func _basic_attack() -> void:
	if game.state.is_empty() or dialogue.visible: return
	path.clear();arrival_action.clear()
	_mark_input()
	var target:=""
	if not game._target(selected_target,int(game.derived_stats().attack_range)).is_empty(): target=selected_target
	_dispatch({"type":"attack","target_id":target})

func _input(event: InputEvent) -> void:
	_observe_os_input(event)
	if trace_enabled and event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN] and is_instance_valid(panels):
		_layout_checkpoint.call_deferred()
	# Real touch callbacks above already perform the action. Suppress only their
	# emulated mouse copies, leaving normal mouse, keyboard, tabs and lists intact.
	if event is InputEventMouseButton and event.device==InputEvent.DEVICE_ID_EMULATION:
		if Time.get_ticks_msec()<suppress_emulated_until:get_viewport().set_input_as_handled();return
		for button in touch_action_buttons:
			if is_instance_valid(button) and button.is_visible_in_tree() and button.get_global_rect().has_point(event.position):
				get_viewport().set_input_as_handled();return
	if not event is InputEventKey or not play.visible or game.state.is_empty(): return
	var key: int = event.physical_keycode
	if event.pressed: _mark_input()
	if dialogue.visible:
		if event.pressed and key==KEY_ESCAPE: _close_dialogue();get_viewport().set_input_as_handled()
		return
	if key in [KEY_UP,KEY_W,KEY_DOWN,KEY_S,KEY_LEFT,KEY_A,KEY_RIGHT,KEY_D]:
		if event.pressed:
			keyboard_moves[key]={KEY_UP:Vector2i.UP,KEY_W:Vector2i.UP,KEY_DOWN:Vector2i.DOWN,KEY_S:Vector2i.DOWN,KEY_LEFT:Vector2i.LEFT,KEY_A:Vector2i.LEFT,KEY_RIGHT:Vector2i.RIGHT,KEY_D:Vector2i.RIGHT}[key]
			movement=keyboard_moves.values()[-1];path.clear();arrival_action.clear()
			if not event.echo:
				_advance_movement()
		else:
			keyboard_moves.erase(key);movement=Vector2i.ZERO if keyboard_moves.is_empty() else keyboard_moves.values()[-1]
		get_viewport().set_input_as_handled()
		return
	if not event.pressed or event.echo: return
	if key==KEY_ESCAPE: dialogue.hide();_stop_motion();selected_target=""
	elif key==KEY_SPACE and not dialogue.visible: _basic_attack()
	elif key==KEY_ENTER and not dialogue.visible: _talk_nearest()
	elif key==KEY_Z and not dialogue.visible: _pickup_nearest()
	elif key==KEY_TAB: panels.current_tab=(panels.current_tab+1)%4
	elif key>=KEY_1 and key<=KEY_9:
		var slot := str(key-KEY_0)
		if game.state.hotkeys.has(slot): _cast(str(game.state.hotkeys[slot]))
	get_viewport().set_input_as_handled()

func _notification(what: int) -> void:
	if what in [NOTIFICATION_APPLICATION_FOCUS_OUT,NOTIFICATION_APPLICATION_PAUSED]: _stop_motion()
	if what==NOTIFICATION_APPLICATION_PAUSED and not game.state.is_empty(): _save()
	if what==NOTIFICATION_WM_GO_BACK_REQUEST:
		if is_instance_valid(dialogue) and dialogue.visible: _close_dialogue()
		elif not game.state.is_empty(): _return_menu()
	if what==NOTIFICATION_WM_CLOSE_REQUEST:
		if game.state.is_empty() or _save(): get_tree().quit()

func _return_menu() -> void:
	if not _save(): return
	_stop_motion();_performance_checkpoint();game.state={};play.hide();menu.show();dialogue.hide()
	if is_instance_valid(mobile_controls): mobile_controls.hide()
	message.reparent(menu.get_parent());message.add_theme_color_override("font_color",Color("f1ddae"))
	_refresh_characters(); message.text="저장했습니다. 이어 하기에서 같은 진행을 불러올 수 있습니다."
	if trace_enabled:_layout_checkpoint.call_deferred()

func _nearest_npc() -> String:
	var best := ""; var distance := 999
	var c: Dictionary = game.state.character
	for id in content.data.npcs:
		var npc: Dictionary = content.data.npcs[id]
		if npc.map_id!=c.map_id: continue
		var d := absi(int(npc.x)-int(c.x))+absi(int(npc.y)-int(c.y))
		if d<=int(npc.get("interaction_range",2)) and d<distance: best=id; distance=d
	return best

func _talk_nearest() -> void:
	var id := _nearest_npc()
	if id.is_empty(): message.text="NPC 가까이 걸어가 대화하세요."; return
	_dispatch({"type":"talk","npc_id":id})

func _pickup_nearest() -> void:
	var c: Dictionary = game.state.character
	for loot in game.state.loot:
		if loot.map_id==c.map_id and absi(int(loot.x)-int(c.x))+absi(int(loot.y)-int(c.y))<=1:
			_dispatch({"type":"pickup","loot_id":loot.loot_id}); return
	message.text="가까운 바닥 전리품이 없습니다."

func _navigate(tile: Vector2i, reach: int = 0, action: Dictionary = {}) -> void:
	_stop_motion()
	var c: Dictionary=game.state.character
	if absi(tile.x-int(c.x))+absi(tile.y-int(c.y))<=reach:
		if not action.is_empty(): _dispatch(action)
		return
	navigation_goal=tile;navigation_reach=reach
	navigation_search=Navigation.new();navigation_search.begin(game,tile,reach)
	message.text="길을 찾는 중 · 방향키나 조이스틱으로 취소할 수 있습니다."
	arrival_action=action
	input_received_ms=Time.get_ticks_msec();_advance_movement()

func _click_world(tile: Vector2i) -> void:
	if game.state.is_empty() or dialogue.visible: return
	for node in content.data.maps[game.state.character.map_id].get("gather_nodes",[]):
		if Vector2i(node.x,node.y)==tile:
			_navigate(tile,1,{"type":"gather","node_id":node.id});return
	for id in content.data.npcs:
		var npc: Dictionary=content.data.npcs[id]
		if npc.map_id==game.state.character.map_id and Vector2i(npc.x,npc.y)==tile:
			_navigate(tile,int(npc.get("interaction_range",2)),{"type":"talk","npc_id":id});return
	var nearest:="";var best:=999
	for id in game.state.monsters:
		var monster: Dictionary=game.state.monsters[id]
		if monster.map_id!=game.state.character.map_id or not monster.alive: continue
		var distance:=absi(int(monster.x)-tile.x)+absi(int(monster.y)-tile.y)
		if distance<=1 and distance<best: nearest=id;best=distance
	if not nearest.is_empty():
		selected_target=nearest
		var monster: Dictionary=game.state.monsters[nearest]
		message.text="대상: "+str(content.data.monsters[monster.monster_id].name)
		_navigate(Vector2i(monster.x,monster.y),1,{"type":"attack","target_id":nearest});return
	_navigate(tile)

func _item_title(instance: Dictionary) -> String:
	var original:=str(content.data.items.get(str(instance.item_id),{}).get("name",instance.item_id))
	return str(instance.custom_name)+" ("+original+")" if not str(instance.get("custom_name","")).is_empty() else original

func _material_text(materials: Dictionary) -> String:
	var text := ""
	for item_id in materials:
		text += " "+str(content.data.items.get(item_id,{}).get("name",item_id))+"×"+str(int(materials[item_id]))
	return text

func _quest_objectives(quest_id: String) -> String:
	var quest: Dictionary=content.data.get("quests",{}).get(quest_id,{})
	var progress: Dictionary=game.state.quests.get(quest_id,{}).get("progress",{})
	var parts: PackedStringArray=[]
	for objective in quest.get("objectives",[]):
		var id:=str(objective.id);var kind:=str(objective.kind)
		var collection: Dictionary=content.data.get({"collect":"items","kill":"monsters","visit":"maps","talk":"npcs","craft":"recipes","equip":"items"}.get(kind,""),{})
		var name:=str(collection.get(id,{}).get("name",id))
		var count: int=game.item_count(id) if kind=="collect" else int(progress.get(kind+":"+id,0))
		parts.append(name+" "+str(count)+"/"+str(int(objective.get("count",1))))
	return " · ".join(parts)

func _show_dialogue(id: String, page: int = 0, preserve_scroll: bool = false) -> void:
	if not content.data.npcs.has(id): return
	var previous_scroll:=dialogue_scroll.scroll_vertical if preserve_scroll and current_npc==id else 0
	current_npc=id;_stop_motion()
	dialogue_rows.clear()
	var npc: Dictionary = content.data.npcs[id]
	if "change_job" in npc.get("services",[]):
		dialogue_rows.append({"label":str(npc.get("job",""))+" 전직 · Lv5","command":{"type":"change_job","npc_id":id,"job":npc.job}})
	if "heal" in npc.get("services",[]):
		dialogue_rows.append({"label":"치료 · "+str(npc.get("heal_cost",content.data.config.get("heal_price",5)))+"전","command":{"type":"heal","npc_id":id}})
	for training_id in content.data.get("training_rules",{}):
		var training: Dictionary=content.data.training_rules[training_id]
		if id not in training.get("teacher_ids",[]) or int(game.state.character.level)<int(training.get("minimum_level",90)): continue
		var stat_name:=str({"strength":"힘","dexterity":"민첩","intelligence":"지력","hp_max":"최대 체력","mp_max":"최대 마력"}.get(str(training.stat),str(training.stat)))
		dialogue_rows.append({"label":"단련 · "+stat_name+" +"+str(int(training.get("increase",1)))+" / 경험치 "+str(int(training.get("xp_cost",0)))+" · Lv"+str(int(training.get("minimum_level",90))),"command":{"type":"train","npc_id":id,"training_id":str(training_id)}})
	if "storage" in npc.get("services",[]):
		for instance in game.state.inventory:
			dialogue_rows.append({"label":"맡기기 · "+_item_title(instance)+" ×"+str(int(instance.quantity)),"command":{"type":"store_deposit","npc_id":id,"instance_id":str(instance.instance_id)},"disabled":instance.instance_id in game.state.equipment.values()})
		for instance in game.state.get("bank_inventory",[]):
			dialogue_rows.append({"label":"찾기 · "+_item_title(instance)+" ×"+str(int(instance.quantity)),"command":{"type":"store_withdraw","npc_id":id,"instance_id":str(instance.instance_id)}})
	if "weapon_naming" in npc.get("services",[]):
		for instance in game.state.inventory:
			if content.data.items[instance.item_id].get("slot","")!="weapon": continue
			dialogue_rows.append({"label":"무기 이름 붙이기 · "+_item_title(instance)+" / "+str(int(npc.get("naming_cost",20)))+"전","command":{"type":"rename_weapon","npc_id":id,"instance_id":str(instance.instance_id)}})
	var stock: Array = npc.get("shop",{}).keys()
	stock.sort_custom(func(a,b):
		var x: Dictionary=content.data.items[a];var y: Dictionary=content.data.items[b]
		return int(x.get("required_level",1))<int(y.get("required_level",1)) if int(x.get("required_level",1))!=int(y.get("required_level",1)) else str(x.name)<str(y.name))
	for item_id in stock:
		var trade: Dictionary = npc.shop[item_id]
		if trade.get("buy_price")==null: continue
		var item: Dictionary=content.data.items[item_id]
		dialogue_rows.append({"label":str(item.name)+" 구매 · "+str(int(trade.buy_price))+"전 · Lv"+str(int(item.get("required_level",1))),"command":{"type":"buy","npc_id":id,"item_id":str(item_id),"quantity":1}})
	if "teach_skill" in npc.get("services",[]):
		var offered: Array=[]
		for skill_id in content.data.skills:
			var skill: Dictionary=content.data.skills[skill_id]
			if id in skill.get("teacher_ids",[]): offered.append(skill_id)
		offered.sort_custom(func(a,b):
			var x: Dictionary=content.data.skills[a];var y: Dictionary=content.data.skills[b]
			return int(x.learn_level)<int(y.learn_level) if int(x.learn_level)!=int(y.learn_level) else str(x.name)<str(y.name))
		for skill_id in offered:
			var skill: Dictionary=content.data.skills[skill_id]
			var learned: bool=skill_id in game.state.skills
			var rank := str(skill.get("required_advancement",skill.get("advancement_rank",0)))
			var rank_text := " · 승급 "+rank if rank not in ["0",""] else ""
			dialogue_rows.append({"label":str(skill.name)+(" [배움]" if learned else " 학습")+" · Lv"+str(int(skill.learn_level))+rank_text+" / "+str(int(skill.get("learn_money",0)))+"전"+_material_text(skill.get("ingredients",{})),"command":{"type":"learn","npc_id":id,"skill_id":str(skill_id)},"disabled":learned})
	if "travel" in npc.get("services",[]):
		for map_id in game.state.character.get("discovered_maps",[]):
			if str(map_id)==str(npc.map_id):continue
			var target: Dictionary=content.data.maps[map_id]
			if not content.data.npcs.values().any(func(n):return str(n.map_id)==str(map_id) and "travel" in n.get("services",[])):continue
			dialogue_rows.append({"label":"야영지 이동 · "+str(target.name)+" / "+str(maxi(10,int(target.get("recommended_level",1))*2))+"전","command":{"type":"travel","npc_id":id,"map_id":str(map_id)}})
	for quest_id in content.data.get("quests",{}):
		var quest: Dictionary=content.data.quests[quest_id]
		if str(quest.get("npc_id",quest.get("giver_id","")))!=id: continue
		var progress: Variant=game.state.quests.get(quest_id,{})
		var phase := str(progress.get("status","")) if typeof(progress)==TYPE_DICTIONARY else str(progress)
		var complete: bool=phase in ["complete","completed","COMPLETE","COMPLETED"]
		var active: bool=not phase.is_empty() and phase not in ["available","AVAILABLE"]
		var command_type := "quest_complete" if active else "quest_accept"
		dialogue_rows.append({"label":"의뢰 · "+str(quest.get("name",quest_id))+(" [완료]" if complete else " 보고" if active else " 받기")+"\n"+_quest_objectives(str(quest_id)),"command":{"type":command_type,"npc_id":id,"quest_id":str(quest_id)},"disabled":complete})
	for recipe_id in content.data.get("recipes",{}):
		var recipe: Dictionary=content.data.recipes[recipe_id]
		if str(recipe.get("npc_id",""))!=id: continue
		var out_id := str(recipe.get("output_item",recipe.get("output_item_id",recipe.get("item_id",""))))
		var title := str(recipe.get("name",recipe_id))
		if recipe.has("results"): title=_material_text(recipe.results).strip_edges()
		dialogue_rows.append({"label":"조합 · "+title+" / "+str(int(recipe.get("money",recipe.get("cost",0))))+"전"+_material_text(recipe.get("ingredients",{})),"command":{"type":"craft","npc_id":id,"recipe_id":str(recipe_id)}})
	for advancement_id in content.data.get("advancements",{}):
		var advancement: Dictionary=content.data.advancements[advancement_id]
		if id not in advancement.get("teacher_ids",[]): continue
		dialogue_rows.append({"label":"승급 · "+str(advancement.get("title",advancement.get("name",advancement_id)))+" / Lv"+str(int(advancement.get("minimum_level",99)))+" / "+str(int(advancement.get("money",advancement.get("cost",0))))+"전"+_material_text(advancement.get("ingredients",{})),"command":{"type":"advance","npc_id":id,"advancement_id":str(advancement_id)}})
	dialogue_page=clampi(page,0,maxi(0,int((dialogue_rows.size()-1)/DIALOGUE_PAGE_SIZE)))
	_render_dialogue_page()
	dialogue.show()
	_resize_ui()
	_restore_dialogue_scroll(previous_scroll,id,dialogue_page)
	if trace_enabled:_layout_checkpoint.call_deferred()

func _refresh_open_dialogue(npc_id: String, page: int, preserve_scroll: bool) -> void:
	# Rebuild rows only after the input callback has returned; a queued refresh
	# must not reopen a window the player has already closed.
	if dialogue.visible and current_npc==npc_id and dialogue_page==page:
		_show_dialogue(npc_id,page,preserve_scroll)

func _render_dialogue_page() -> void:
	for child in dialogue_body.get_children(): dialogue_body.remove_child(child);child.queue_free()
	for child in dialogue_pager.get_children(): dialogue_pager.remove_child(child);child.queue_free()
	var npc: Dictionary=content.data.npcs[current_npc]
	dialogue_title.text=str(npc.name)
	_label(dialogue_body,str(npc.get("dialogue",{}).get("greeting",""))).add_theme_color_override("font_color",Color("302012"))
	weapon_name_input=null
	if "weapon_naming" in npc.get("services",[]):
		weapon_name_input=LineEdit.new();weapon_name_input.placeholder_text="새 무기 이름 · 2~12자";weapon_name_input.max_length=12
		weapon_name_input.custom_minimum_size.y=38;dialogue_body.add_child(weapon_name_input)
	var start := dialogue_page*DIALOGUE_PAGE_SIZE
	for index in range(start,mini(start+DIALOGUE_PAGE_SIZE,dialogue_rows.size())):
		var row: Dictionary=dialogue_rows[index]
		var command: Dictionary=row.command.duplicate(true)
		var action:=func():
			if str(command.type)=="rename_weapon" and is_instance_valid(weapon_name_input): command.name=weapon_name_input.text.strip_edges()
			var result: Dictionary=_dispatch(command)
			if result.get("changed",false): _refresh_open_dialogue.call_deferred(current_npc,dialogue_page,true)
		var button:=_button(dialogue_body,str(row.label),action,false)
		button.custom_minimum_size.y=44
		button.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
		button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		button.disabled=bool(row.get("disabled",false))
	if dialogue_rows.size()>DIALOGUE_PAGE_SIZE:
		var pages:=dialogue_pager
		var previous:=_button(pages,"이전",func(): dialogue_page-=1;_refresh_open_dialogue.call_deferred(current_npc,dialogue_page,false))
		previous.disabled=dialogue_page==0
		var page_label:=_label(pages,str(dialogue_page+1)+" / "+str(ceili(float(dialogue_rows.size())/DIALOGUE_PAGE_SIZE)))
		page_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		page_label.add_theme_color_override("font_color",Color("302012"))
		page_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
		page_label.custom_minimum_size.x=90
		var next:=_button(pages,"다음",func(): dialogue_page+=1;_refresh_open_dialogue.call_deferred(current_npc,dialogue_page,false))
		next.disabled=start+DIALOGUE_PAGE_SIZE>=dialogue_rows.size()
	dialogue_scroll.scroll_vertical=0
	if trace_enabled:_layout_checkpoint.call_deferred()

func _show_map() -> void:
	_stop_motion()
	current_npc="";dialogue_title.text="지도 · 길 찾기"
	for child in dialogue_body.get_children(): dialogue_body.remove_child(child);child.queue_free()
	for child in dialogue_pager.get_children(): dialogue_pager.remove_child(child);child.queue_free()
	var c: Dictionary=game.state.character
	var map: Dictionary=content.data.maps[c.map_id]
	_label(dialogue_body,str(map.name)+" · "+str(int(c.x))+", "+str(int(c.y))).add_theme_color_override("font_color",Color("302012"))
	var overview=preload("res://render/world_map.gd").new()
	overview.assets=content.assets;overview.definition=map;overview.character=c
	overview.npcs=content.data.npcs.values().filter(func(n):return str(n.map_id)==str(c.map_id))
	overview.cell_selected.connect(func(cell):_close_dialogue();_navigate(cell))
	dialogue_body.add_child(overview)
	_label(dialogue_body,"초록: 현재 위치 · 파랑: 시설 · 금색: 출구 · 지도를 눌러 이동")
	for exit in map.get("exits",[]):
		var target:=Vector2i(exit.x,exit.y)
		var destination:=str(content.data.maps[exit.to_map].name)
		_button(dialogue_body,destination+" ("+str(target.x)+", "+str(target.y)+")",func(): _close_dialogue();_navigate(target),false)
	for id in content.data.npcs:
		var npc: Dictionary=content.data.npcs[id]
		if npc.map_id!=c.map_id: continue
		var target:=Vector2i(npc.x,npc.y);var npc_id:=str(id)
		_button(dialogue_body,str(npc.name)+" ("+str(target.x)+", "+str(target.y)+")",func(): _close_dialogue();_navigate(target,int(npc.get("interaction_range",2)),{"type":"talk","npc_id":npc_id}),false)
	dialogue_scroll.scroll_vertical=0
	dialogue.show()
	_resize_ui()
	if trace_enabled:_layout_checkpoint.call_deferred()

func _selection(list) -> String:
	var indexes: PackedInt32Array = list.get_selected_items()
	return str(list.get_item_metadata(indexes[0])) if indexes.size()>0 else ""

func _instance(id: String) -> Dictionary:
	for item in game.state.inventory:
		if item.instance_id==id: return item
	return {}

func _use_selected_item() -> void:
	var id := _selection(bag); var instance := _instance(id)
	if instance.is_empty(): return
	var definition: Dictionary = content.data.items[instance.item_id]
	var command := {"type":"equip" if not str(definition.get("slot","")).is_empty() else "use_item","instance_id":id}
	if definition.get("action_type","")=="return": command.direction=direction_picker.get_item_text(direction_picker.selected)
	_dispatch(command)

func _sell_selected() -> void:
	var id := _selection(bag); var npc := _nearest_npc()
	if id.is_empty() or npc.is_empty(): message.text="판매할 물건을 고르고 상인 가까이 가세요."; return
	_dispatch({"type":"sell","npc_id":npc,"instance_id":id,"quantity":1})

func _unequip_selected() -> void:
	var slot := _selection(equipment)
	if not slot.is_empty(): _dispatch({"type":"unequip","slot":slot})

func _repair_selected() -> void:
	var slot := _selection(equipment); var npc := _nearest_npc()
	if game.state.equipment.has(slot) and not npc.is_empty(): _dispatch({"type":"repair","npc_id":npc,"instance_id":game.state.equipment[slot]})

func _cast_selected() -> void:
	if game.state.is_empty() or dialogue.visible: return
	var id := _selection(skills)
	if id.is_empty() and not game.state.skills.is_empty(): id=str(game.state.skills[0])
	if not id.is_empty(): _cast(id)
	else: message.text="아직 배운 기술이 없습니다. Lv5부터 사범에게 전직하세요."

func _cast(id: String) -> void:
	var target:=selected_target
	var definition: Dictionary=content.data.skills[id]
	if definition.kind in ["damage","debuff","status","blink"] and str(definition.get("target","enemy"))!="self" and game._target(target,int(definition.get("range",4))).is_empty(): target=game.attack_target(int(definition.get("range",4)))
	var cmd := {"type":"cast","skill_id":id,"target_id":target}
	if definition.kind=="return": cmd.direction=direction_picker.get_item_text(direction_picker.selected)
	if definition.kind=="identify":
		cmd.instance_id=_selection(bag)
		if str(cmd.instance_id).is_empty(): message.text="물품 패널에서 감정할 물건을 먼저 고르세요.";return
	_dispatch(cmd)

func _describe_skill() -> void:
	if not is_instance_valid(skill_description): return
	var id:=_selection(skills)
	if id.is_empty(): skill_description.text="기술을 선택하면 효과와 소모를 확인할 수 있습니다.";return
	var skill: Dictionary=content.data.skills[id]
	var kind:=str(skill.kind)
	var label:=str({"damage":"공격","heal":"회복","buff":"강화","debuff":"약화","status":"상태이상","return":"귀환","shrine":"성황당 이동","identify":"감정","restore_mp":"마력 회복","summon":"소환","cleanse":"상태 회복","revive":"부활","loot":"전리품 수집","blink":"접근 이동"}.get(kind,kind))
	skill_description.text=label+" · 마력 "+str(int(skill.get("mp_cost",0)))+" / 체력 "+str(int(skill.get("hp_cost",0)))+" · 재사용 "+str(snappedf(float(skill.get("cooldown",0)),0.1))+"초"
	if kind in ["damage","heal","restore_mp"]:skill_description.text+=" · 위력 "+str(int(skill.get("power",0)))
	if not str(skill.get("status","")).is_empty(): skill_description.text+=" · "+str({"stealth":"투명","paralysis":"마비","poison":"중독","slow":"감속","silence":"침묵","blindness":"실명","haste":"가속","protection":"보호"}.get(str(skill.status),str(skill.status)))

func _same_list_members(list, ids: Array) -> bool:
	if list.item_count!=ids.size(): return false
	for index in range(ids.size()):
		if list.get_item_metadata(index)!=ids[index]: return false
	return true

func _refresh_panels() -> void:
	if game.state.is_empty(): return
	var c: Dictionary = game.state.character
	var previous_bag := _selection(bag); var previous_skill := _selection(skills); var previous_equipment := _selection(equipment)
	var bag_ids: Array=[]
	for item in game.state.inventory: bag_ids.append(item.instance_id)
	var rebuild_bag:=not _same_list_members(bag,bag_ids)
	if rebuild_bag: bag.clear()
	for index in range(game.state.inventory.size()):
		var item: Dictionary=game.state.inventory[index]
		var def: Dictionary=content.data.items[item.item_id]
		var title:=_item_title(item)+" ×"+str(int(item.quantity))+(" [착용]" if item.instance_id in game.state.equipment.values() else "")
		var icon: Texture2D=content.icon(str(item.item_id))
		if rebuild_bag:
			bag.add_item(title,icon);bag.set_item_metadata(index,item.instance_id)
		else: bag.update_item(index,title,icon)
		bag.set_item_tooltip(index,str(def.name)+" · 내구 "+str(item.durability)+" · Lv"+str(int(def.get("required_level",1)))+" · 공격 "+str(int(def.get("attack",0)))+" · 방어 "+str(int(def.get("defense",0))))
		if rebuild_bag and item.instance_id==previous_bag: bag.select(index)
	if equipment_slot_names.is_empty():
		equipment_slot_names=["weapon","armor"]
		for item in content.data.items.values():
			var slot_name:=str(item.get("slot",""))
			if not slot_name.is_empty() and slot_name not in equipment_slot_names: equipment_slot_names.append(slot_name)
	var equipment_rows: Array=[]
	var equipment_ids: Array=[]
	var slot_labels := {"weapon":"무기","armor":"갑옷","helmet":"투구","head":"투구","shield":"방패","ring":"반지","accessory":"보조","necklace":"목걸이","boots":"신발","cape":"망토","left_hand":"왼손","right_hand":"오른손"}
	for slot in equipment_slot_names:
		var title:=str(slot_labels.get(slot,slot))+": 없음"
		var icon: Texture2D=null
		if game.state.equipment.has(slot):
			var item:=_instance(str(game.state.equipment[slot]))
			if item.is_empty(): continue
			title=str(slot_labels.get(slot,slot))+": "+_item_title(item)+" · 내구"+str(int(item.durability))
			icon=content.icon(str(item.item_id))
		equipment_ids.append(slot);equipment_rows.append({"title":title,"icon":icon})
	var rebuild_equipment:=not _same_list_members(equipment,equipment_ids)
	if rebuild_equipment: equipment.clear()
	for index in range(equipment_rows.size()):
		var row: Dictionary=equipment_rows[index]
		if rebuild_equipment:
			equipment.add_item(row.title,row.icon);equipment.set_item_metadata(index,equipment_ids[index])
		else: equipment.update_item(index,row.title,row.icon)
		if rebuild_equipment and equipment_ids[index]==previous_equipment: equipment.select(index)
	var skill_ids: Array=[]
	for id in game.state.skills: skill_ids.append(id)
	var rebuild_skills:=not _same_list_members(skills,skill_ids)
	if rebuild_skills: skills.clear()
	for index in range(skill_ids.size()):
		var id: String=str(skill_ids[index])
		var def: Dictionary=content.data.skills[id]
		var key := ""
		for slot in game.state.hotkeys:
			if game.state.hotkeys[slot]==id: key="["+str(slot)+"] "
		var title:=key+str(def.name)+" · MP "+str(def.get("mp_cost",0))
		var skill_icon:=_skill_icon(id)
		if rebuild_skills:
			skills.add_item(title,skill_icon);skills.set_item_metadata(index,id)
		else: skills.update_item(index,title,skill_icon)
		if rebuild_skills and id==previous_skill: skills.select(index)
	_describe_skill()
	var derived: Dictionary=game.derived_stats()
	attributes.text="이름  "+str(c.name)+"\n국적  "+str(c.get("nationality","고구려"))+"\n수호  "+str(c.get("guardian","주작"))+"\n직업  "+_job_name(str(c.job))+"\n레벨  "+str(c.level)+"\n경험치  "+str(c.xp)+"\n체력  "+str(c.hp)+" / "+str(c.hp_max)+"\n마력  "+str(c.mp)+" / "+str(c.mp_max)+"\n공격  "+str(derived.attack)+"\n방어  "+str(derived.defense)+"\n힘 / 민첩 / 지력  "+str(int(derived.get("strength",0)))+" / "+str(int(derived.get("dexterity",0)))+" / "+str(int(derived.get("intelligence",0)))+"\n금전  "+str(c.money)+"전\n사냥  "+str(game.state.stats.kills)+"마리\n좌표  "+str(c.x)+", "+str(c.y)+"\n승급  "+str(c.get("title","없음"))+"\n의뢰  "+str(game.state.quests.size())+"건"
	for quest_id in game.state.quests:
		var quest: Dictionary=content.data.get("quests",{}).get(quest_id,{})
		var completed: bool=str(game.state.quests[quest_id].get("status",""))=="completed"
		attributes.text+="\n\n"+str(quest.get("name",quest_id))+(" [완료]" if completed else "\n"+_quest_objectives(str(quest_id)))
	if not game.state.get("buffs",{}).is_empty():
		attributes.text+="\n\n적용 중인 기술"
		for buff_id in game.state.buffs:
			attributes.text+="\n"+str(content.data.skills.get(str(buff_id),{}).get("name",buff_id))
	_refresh_equipment_preview()
	for slot in equipped_icons:
		var item:=_instance(str(game.state.equipment.get(slot,"")))
		equipped_icons[slot].icon=content.icon(str(item.item_id)) if not item.is_empty() else null
		equipped_icons[slot].tooltip_text=_item_title(item) if not item.is_empty() else "착용 장비 없음"
	for index in range(quick_skill_buttons.size()):
		var id:=str(game.state.hotkeys.get(str(index+1),""))
		quick_skill_buttons[index].icon=_skill_icon(id) if not id.is_empty() else null
		quick_skill_buttons[index].tooltip_text=str(content.data.skills.get(id,{}).get("name","기술창에서 단축키 지정"))
	_refresh_vitals()
	last_state_revision=int(game.state.revision)

func _refresh_vitals() -> void:
	var c: Dictionary=game.state.character
	if c.job=="commoner":
		goal_hint.text="다음 목표 · 남문 밖에서 토끼·다람쥐 사냥 → 5레벨에 네 직업 중 선택" if int(c.level)<5 else "전직할 수 있습니다 · 지도를 열어 원하는 직업의 길드를 찾아가세요."
	elif game.state.skills.is_empty():
		var acorns:=0;var meat:=0
		for item in game.state.inventory:
			if str(item.item_id)=="KRO-ITEM-1ec5d43f9e157e":acorns+=int(item.quantity)
			if str(item.item_id)=="gp:item:rabbit_meat":meat+=int(item.quantity)
		goal_hint.text="다음 목표 · 사범에게 기술 배우기 · 귀환 재료: 도토리 %d/10 · 토끼고기 %d/10" % [acorns,meat]
	else:
		goal_hint.text="다음 목표 · 배운 기술과 새 장비로 사냥터 탐험 · 전리품은 상점 판매·학습·제작에 사용"
	for instance in game.state.inventory:
		if str(instance.instance_id)==str(game.state.equipment.get("weapon","")) and int(instance.durability)<=0:
			goal_hint.text="무기가 부서졌습니다 · 대장간에서 수리하거나 새 무기로 바꾸세요."
			break
	hp_bar.max_value=c.hp_max;hp_bar.value=c.hp;hp_bar.tooltip_text="체력 "+str(int(c.hp))+" / "+str(int(c.hp_max))
	mp_bar.max_value=c.mp_max;mp_bar.value=c.mp;mp_bar.tooltip_text="마력 "+str(int(c.mp))+" / "+str(int(c.mp_max))
	character_header.text=str(c.name)+" · "+_job_name(str(c.job))+" Lv"+str(int(c.level))
	status.text=str(content.data.maps[c.map_id].name)+( " · 귀신" if c.dead else "")+"  "+str(int(c.x))+", "+str(int(c.y))+"\n체력 "+str(int(c.hp))+"/"+str(int(c.hp_max))+"  마력 "+str(int(c.mp))+"/"+str(int(c.mp_max))+"\n경험치 "+str(int(c.xp))+" · "+str(int(c.money))+"전"
	if size.y<540:status.text=str(content.data.maps[c.map_id].name)+" · "+str(int(c.money))+"전"
	last_state_revision=int(game.state.revision)

func _monster_look(monster_id: String) -> String:
	var definition: Dictionary=content.data.monsters.get(monster_id,{})
	var fallback:=str(definition.get("look_id",definition.get("look",definition.get("appearance_id","rabbit"))))
	return str(content.actors.get("actor_aliases",{}).get(monster_id,fallback))

func _look_player() -> String:
	for buff in game.state.get("buffs",{}).values():
		var form_id:=str(buff.get("form_monster_id",""))
		if content.data.monsters.has(form_id): return _monster_look(form_id)
	var armor := false
	var shield := false
	var helmet := false
	var weapon_graphics: Dictionary = {}
	for instance_id in game.state.equipment.values():
		var item := _instance(str(instance_id))
		if item.is_empty(): continue
		var def: Dictionary = content.data.items[item.item_id]
		if int(def.get("durability",0))>0 and int(item.durability)<=0: continue
		if def.get("slot")=="weapon": weapon_graphics=content.actors.get("item_equipment_graphics",{}).get(str(item.item_id),{})
		if def.get("slot")=="armor" and int(def.get("defense",0))>0: armor=str(def.get("look","player_armor"))!="player_base"
		if def.get("slot")=="shield":shield=true
		if def.get("slot") in ["helmet","head"] and content.actors.get("helmet_item_graphics",{}).has(str(item.item_id)):helmet=true
	var look := str(weapon_graphics.get("armored_player_look" if armor else "player_look","player_armor" if armor else "player_base"))
	if int(game.state.character.appearance.get("variant",0))==1: look+="_alt"
	if shield and content.actors.get("looks",{}).has(look+"_shield"):look+="_shield"
	if helmet and content.actors.get("looks",{}).has(look+"_helmet"):look+="_helmet"
	return look

func _skill_icon(id: String) -> Texture2D:
	if skill_icon_cache.has(id): return skill_icon_cache[id]
	var def: Dictionary=content.data.skills.get(id,{})
	var effect: Dictionary=content.effects.get(str(def.get("effect_id","")),{})
	var selected: Dictionary={};var area:=0
	for frame in effect.get("front_frames",[]):
		var candidate: Dictionary=frame.get("image",{})
		var extent: Array=candidate.get("size",[0,0])
		var next_area:=int(extent[0])*int(extent[1])
		if next_area>area and not candidate.get("source_empty_rectangle",false):
			selected=candidate;area=next_area
	var result: Texture2D=null
	if not selected.is_empty():
		var native: Texture2D=content.assets.texture("kr491/"+str(selected.path))
		if native!=null:
			var pixels:=native.get_image()
			var bounds:=pixels.get_used_rect()
			if bounds.size.x>0 and bounds.size.y>0:
				pixels=pixels.get_region(bounds)
				var factor:=minf(1.0,24.0/maxf(pixels.get_width(),pixels.get_height()))
				pixels.resize(maxi(1,int(pixels.get_width()*factor)),maxi(1,int(pixels.get_height()*factor)),Image.INTERPOLATE_NEAREST)
				result=ImageTexture.create_from_image(pixels)
	skill_icon_cache[id]=result
	return result

func _cast_hotkey(slot: String) -> void:
	var id:=str(game.state.get("hotkeys",{}).get(slot,""))
	if id.is_empty():message.text="기술창에서 "+slot+"번 기술을 먼저 지정하세요.";return
	for index in range(skills.item_count):
		if str(skills.get_item_metadata(index))==id:skills.select(index);break
	_cast_selected()

func _cape_player_look() -> String:
	# A polymorph uses its complete monster body and does not wear human parts.
	if not _look_player().contains("player"):return ""
	for instance_id in game.state.equipment.values():
		var item:=_instance(str(instance_id))
		if item.is_empty():continue
		var def: Dictionary=content.data.items[item.item_id]
		if def.get("slot")!="cape":continue
		if int(def.get("durability",0))>0 and int(item.durability)<=0:continue
		return str(content.actors.get("cape_item_graphics",{}).get(str(item.item_id),{}).get("cape_look",""))
	return ""

func _player_frame_layers(look: String, animation: String, direction: int, at_clock: float) -> Array:
	var frame: Dictionary=content.actor(look,animation,direction,at_clock)
	if frame.is_empty():return []
	var cape_look:=_cape_player_look()
	if cape_look.is_empty() or not frame.has("part_layers"):
		return [{"path":"gameplay-assets/"+str(frame.path),"x":float(frame.offset[0]),"y":float(frame.offset[1])}]
	var cape: Dictionary=content.actor(cape_look,animation,direction,at_clock)
	var result: Array=[]
	var cape_layer: Dictionary={}
	if not cape.is_empty():cape_layer={"path":"gameplay-assets/"+str(cape.path),"x":float(cape.offset[0]),"y":float(cape.offset[1])}
	if direction!=0 and not cape_layer.is_empty():result.append(cape_layer)
	for part_id in frame.part_layers:
		var part: Dictionary=content.actors.get("player_part_layers",{}).get(str(part_id),{})
		if part.is_empty():continue
		result.append({"path":"gameplay-assets/"+str(part.path),"x":float(part.offset[0]),"y":float(part.offset[1])})
		if direction==0 and part.kind=="body" and not cape_layer.is_empty():result.append(cape_layer)
	return result

func _refresh_equipment_preview() -> void:
	var look:=_look_player()
	var preview_scale:=1.0 if size.y<540 else 2.0
	var look_key:=look+":"+_cape_player_look()+":"+str(preview_scale)
	if equipment_preview_look==look_key:return
	var layers:=_player_frame_layers(look,"standing",2,0)
	if layers.is_empty():return
	equipment_preview_look=look_key
	equipment_preview.configure(layers,Vector2(100,100),Vector2(0,-23),preview_scale)

func _visual_point(id: String, x: float, y: float) -> Vector2:
	if not visual_positions.has(id): return Vector2(x,y)
	var value: Dictionary=visual_positions[id]
	var progress:=clampf((clock-float(value.at))/maxf(float(value.duration),0.01),0,1)
	return Vector2(value.from).lerp(Vector2(value.to),progress)

func _actor_layer(look: String, animation: String, direction: int, x: float, y: float) -> Dictionary:
	var frame: Dictionary=content.actor(look,animation,direction,clock)
	if frame.is_empty(): return {}
	var path:=str(frame.path)
	if not path.begins_with("gameplay-assets/"): path="gameplay-assets/"+path
	var offset: Array=frame.get("offset",[0,0])
	return {"path":path,"x":x*24+12+float(offset[0]),"y":y*24+24+float(offset[1]),"depth_y":y*24+24}

func _performance_checkpoint() -> void:
	var samples:=frame_samples.duplicate();samples.sort()
	var latency:=input_latencies.duplicate();latency.sort()
	var visual_latency:=visual_feedback_latencies.duplicate();visual_latency.sort()
	var over50:=0;var over100:=0
	for sample in samples:
		if sample>50:over50+=1
		if sample>100:over100+=1
	checkpoint("frame_timing",{"max_ms":samples[-1] if not samples.is_empty() else -1,"over50ms":over50,"over100ms":over100,"render_feedback_p95_ms":_percentile(visual_latency,0.95),"render_feedback_scope":"engine frame_post_draw; OS presentation requires external device/frame correlation","save_receipts":save_receipts})
	if trace_enabled:
		var trace_file:=FileAccess.open(trace_destination,FileAccess.WRITE)
		if trace_file:
			for row in profile_timeline: trace_file.store_line(JSON.stringify(row))
			trace_file.flush()
	checkpoint("performance",{"scope":"observed host only; not Galaxy certification","frames":samples.size(),"p50_ms":_percentile(samples,0.5),"p95_ms":_percentile(samples,0.95),"p99_ms":_percentile(samples,0.99),"input_command_p95_ms":_percentile(latency,0.95),"input_latency_scope":"input to accepted command; presentation requires frame/video correlation","max_process_ms":max_process_ms,"memory_static_bytes":OS.get_static_memory_usage(),"texture_pixels":content.assets.texture_pixels})

func _percentile(values: Array, percentile: float) -> float:
	return float(values[mini(values.size()-1,int(values.size()*percentile))]) if not values.is_empty() else -1.0

func _render_world() -> void:
	if game.state.is_empty(): return
	var c: Dictionary = game.state.character
	var map: Dictionary = content.data.maps[c.map_id]
	# Keep stable IDs only, then read current copy-on-write records every frame.
	if runtime_monster_map!=str(c.map_id) or runtime_monster_count!=game.state.monsters.size():
		runtime_monster_map=str(c.map_id);runtime_monster_count=game.state.monsters.size()
		runtime_monster_ids.clear();runtime_npc_ids.clear()
		for id in game.state.monsters:
			if str(game.state.monsters[id].map_id)==runtime_monster_map: runtime_monster_ids.append(id)
		for id in content.data.npcs:
			if str(content.data.npcs[id].map_id)==runtime_monster_map: runtime_npc_ids.append(id)
	var world_zoom:=1.65 if size.x>=1000 else 1.25
	var player_position:=_visual_point("player",float(c.x),float(c.y))
	var camera:=player_position*24+Vector2(12,12)
	var extent:=Vector2(float(map.width)*24,float(map.height)*24)
	var half_view: Vector2=view.size/(2.0*world_zoom)
	camera.x=clampf(camera.x,half_view.x,extent.x-half_view.x) if extent.x>=2.0*half_view.x else extent.x*0.5
	camera.y=clampf(camera.y,half_view.y,extent.y-half_view.y) if extent.y>=2.0*half_view.y else extent.y*0.5
	var visible_world:=Rect2(camera-view.size/(2*world_zoom),view.size/world_zoom).grow(24)
	var layers: Array = _visible_ground(map,visible_world)
	if layers.is_empty() and map.has("floor_png"): layers.append({"path":map.floor_png,"x":0,"y":0})
	var sorted: Array = []
	var next_key:=str(c.map_id)+":"+str(Vector2i(camera/24))+":"+str(view.size)
	if map_render_key!=next_key:
		map_render_key=next_key;scenery_cache.clear()
		var indices: Dictionary={}
		if map.has("object_buckets"):
			for by in range(maxi(0,floori(visible_world.position.y/384)-1),mini(int(map.height)/16+1,ceili(visible_world.end.y/384)+1)):
				for bx in range(maxi(0,floori(visible_world.position.x/384)-1),mini(int(map.width)/16+1,ceili(visible_world.end.x/384)+1)):
					for i in map.object_buckets.get(str(bx)+","+str(by),[]):indices[int(i)]=true
		else:
			for i in range(map.get("objects",[]).size()):indices[i]=true
		for i in indices:
			var object: Dictionary=map.objects[i]
			var bounds:=Rect2(float(object.x),float(object.y),float(object.get("width_px",24)),maxf(24,float(object.get("height_px",float(object.get("height",6))*24))))
			if not visible_world.grow(48).intersects(bounds):continue
			var entry: Dictionary=object.duplicate()
			if not entry.has("path"):entry.path=entry.get("frame_png","")
			scenery_cache.append(entry)
	sorted.append_array(scenery_cache)
	var labels: Array=[]
	labels.append_array(_readable_landmarks(map,camera,world_zoom))
	for node in map.get("gather_nodes",[]):
		if not visible_world.has_point(Vector2(float(node.x)*24,float(node.y)*24)):continue
		var node_icon: Dictionary=content.actors.icons.get(str(node.item_id),{})
		if not node_icon.is_empty():
			var node_path:=str(node_icon.path)
			if not node_path.begins_with("gameplay-assets/"):node_path="gameplay-assets/"+node_path
			sorted.append({"path":node_path,"x":int(node.x)*24,"y":int(node.y)*24,"depth_y":int(node.y)*24+23})
		labels.append({"x":int(node.x)*24+12,"y":int(node.y)*24+24,"text":str(node.name)+" · 채집","color":"98d787"})
	for id in runtime_npc_ids:
		var npc: Dictionary=content.data.npcs[id]
		var layer := _actor_layer(str(npc.get("look_id",npc.get("appearance_id","tavern"))),"standing",int(npc.get("direction",2)),int(npc.x),int(npc.y))
		if not layer.is_empty(): sorted.append(layer)
		labels.append({"x":int(npc.x)*24+12,"y":int(npc.y)*24+24,"text":npc.name,"color":"f4d58a"})
	for id in runtime_monster_ids:
		var monster: Dictionary=game.state.monsters[id]
		if not monster.alive or not visible_world.grow(72).has_point(Vector2(float(monster.x)*24,float(monster.y)*24)): continue
		var def: Dictionary=content.data.monsters[monster.monster_id]
		var animation := "attack" if clock<float(actor_animations.get(id,0)) else "walking" if clock<float(actor_walk_until.get(id,0)) else "standing"
		var at:=_visual_point(str(id),float(monster.x),float(monster.y))
		var layer := _actor_layer(_monster_look(str(monster.monster_id)),animation,int(actor_directions.get(id,2)),at.x,at.y)
		if not layer.is_empty(): sorted.append(layer)
		labels.append({"x":at.x*24+12,"y":at.y*24+24,"text":str(def.name)+( " ◇" if id==selected_target else ""),"hp":monster.hp,"hp_max":def.hp,"color":"f0e8c7"})
	for summon in game.state.get("summons",[]):
		if str(summon.map_id)!=str(c.map_id): continue
		var definition: Dictionary=content.data.monsters.get(str(summon.monster_id),{})
		var ally:=_actor_layer(_monster_look(str(summon.monster_id)),"standing",int(c.direction),float(summon.x),float(summon.y))
		if not ally.is_empty(): sorted.append(ally)
		labels.append({"x":int(summon.x)*24+12,"y":int(summon.y)*24+24,"text":str(definition.get("name","동료"))+" · 동료","color":"84dfab"})
	for loot in game.state.loot:
		if loot.map_id!=c.map_id: continue
		var icon: Dictionary=content.actors.get("icons",{}).get(str(loot.get("item_id","")),{})
		if not icon.is_empty():
			var path:=str(icon.path)
			if not path.begins_with("gameplay-assets/"): path="gameplay-assets/"+path
			sorted.append({"path":path,"x":int(loot.x)*24+2,"y":int(loot.y)*24+8,"depth_y":int(loot.y)*24+23})
		labels.append({"x":int(loot.x)*24+12,"y":int(loot.y)*24+50,"text":"전리품 · Z","color":"d3c480"})
	var player_layers := _player_frame_layers(_look_player(),character_animation if clock<animation_until else "standing",int(c.direction),clock)
	var stealthed := false
	for buff in game.state.get("buffs",{}).values():
		if str(buff.get("status",""))=="stealth": stealthed=true
	for layer_index in range(player_layers.size()):
		var player: Dictionary=player_layers[layer_index]
		player.x=float(player.x)+player_position.x*24+12
		player.y=float(player.y)+player_position.y*24+24
		player.depth_y=player_position.y*24+24+float(layer_index)*0.001
		player.opacity=0.4 if c.dead or stealthed else 1.0
		sorted.append(player)
	labels.append({"x":player_position.x*24+12,"y":player_position.y*24+24,"text":c.name,"color":"a9e8bd"})
	for i in range(active_effects.size()-1,-1,-1):
		var active: Dictionary=active_effects[i]
		if clock-float(active.at)>10: active_effects.remove_at(i); continue
		if active.map_id!=c.map_id: continue
		var definition: Dictionary=content.effects.get(str(active.id),{})
		if definition.is_empty(): continue
		var sample: Dictionary=Effect.layers(definition,clock-float(active.at),Vector2(float(active.x)*24+12,float(active.y)*24+24))
		if sample.finished: active_effects.remove_at(i)
		else: _append_depth_effect(sorted,sample,float(active.y)*24+24)
	for index in range(projectiles.size()-1,-1,-1):
		var projectile: Dictionary=projectiles[index]
		var elapsed := clock-float(projectile.at)
		var duration := maxf(float(projectile.get("duration",0.2)),0.05)
		if elapsed>duration or str(projectile.map_id)!=str(c.map_id): projectiles.remove_at(index);continue
		var from:=Vector2(float(projectile.from_x)*24+12,float(projectile.from_y)*24+12)
		var to:=Vector2(float(projectile.to_x)*24+12,float(projectile.to_y)*24+12)
		var position:=from.lerp(to,clampf(elapsed/duration,0,1))
		var effect: Dictionary=content.effects.get(str(projectile.get("effect_id","")),{})
		if not effect.is_empty():
			var sample: Dictionary=Effect.layers(effect,0.02,position)
			_append_depth_effect(sorted,sample,position.y)
	sorted.sort_custom(func(a,b): return float(a.get("depth_y",a.y))<float(b.get("depth_y",b.y)))
	layers.append_array(sorted)
	view.labels=labels
	view.configure(layers,Vector2(int(map.width)*24,int(map.height)*24),camera,world_zoom)

func _readable_landmarks(map: Dictionary, camera: Vector2, world_zoom: float) -> Array:
	# Legacy short labels and generated destination labels can share one cell.
	# Keep one authoritative destination label at that real doorway, then keep
	# nearer visible labels when adjacent text rectangles would overlap. This
	# changes drawing only: map IDs, door cells, collision and input stay intact.
	var by_cell: Dictionary={}
	var character: Dictionary=game.state.character
	var player_cell:=Vector2(float(character.x),float(character.y))
	var font:=ThemeDB.fallback_font
	var viewport:=Rect2(Vector2.ZERO,view.size)
	# A service landmark can name the same NPC at the exact same cell.
	# Its actor name already identifies that entity; do not shift a duplicate.
	var npc_names_by_cell: Dictionary={}
	for id in runtime_npc_ids:
		var npc: Dictionary=content.data.npcs[id]
		var cell:=Vector2i(int(npc.x),int(npc.y))
		if not npc_names_by_cell.has(cell):npc_names_by_cell[cell]={}
		npc_names_by_cell[cell][str(npc.name)]=true
	for landmark in map.get("landmarks",[]):
		if not landmark.has("x") or not landmark.has("y"):continue
		var title:=str(landmark.get("name",landmark.get("label","")))
		if title.is_empty():continue
		var cell:=Vector2i(int(landmark.x),int(landmark.y))
		if npc_names_by_cell.get(cell,{}).has(title):continue
		var priority:=2 if str(landmark.get("kind",""))=="exit" else 1 if str(landmark.get("kind",""))=="service" else 0
		if by_cell.has(cell) and int(by_cell[cell].priority)>=priority:continue
		var point:=Vector2(cell)*24+Vector2(12,24)
		var width:=font.get_string_size(title,HORIZONTAL_ALIGNMENT_LEFT,-1,14).x
		var baseline: Vector2=view.size*0.5+(point-camera)*world_zoom+Vector2(-width*0.5,-48*world_zoom-8)
		var bounds:=Rect2(baseline-Vector2(0,font.get_ascent(14)),Vector2(width,font.get_height(14))).grow(4)
		by_cell[cell]={"priority":priority,"distance":Vector2(cell).distance_squared_to(player_cell),"bounds":bounds,"label":{"x":point.x,"y":point.y,"text":title,"color":"ccb78d"}}
	var candidates: Array=by_cell.values()
	candidates.sort_custom(func(a,b):
		if a.distance==b.distance:return float(a.label.x)<float(b.label.x)
		return float(a.distance)<float(b.distance))
	var accepted: Array=[]
	var occupied: Array[Rect2]=[]
	# Names use the same projected baseline as landmarks. Reserve the live
	# player/NPC name rectangles before placing a gate caption, including the
	# player's interpolated position while approaching or leaving a doorway.
	var names: Array=[{"point":_visual_point("player",float(character.x),float(character.y))*24+Vector2(12,24),"text":str(character.name)}]
	for id in runtime_npc_ids:
		var npc: Dictionary=content.data.npcs[id]
		names.append({"point":Vector2(float(npc.x)*24+12,float(npc.y)*24+24),"text":str(npc.name)})
	for name_label in names:
		var width:=font.get_string_size(name_label.text,HORIZONTAL_ALIGNMENT_LEFT,-1,14).x
		var baseline: Vector2=view.size*0.5+(Vector2(name_label.point)-camera)*world_zoom+Vector2(-width*0.5,-48*world_zoom-8)
		occupied.append(Rect2(baseline-Vector2(0,font.get_ascent(14)),Vector2(width,font.get_height(14))).grow(4))
	var caption_step:=font.get_height(14)+10.0
	for candidate in candidates:
		# Prefer the original anchor, then an adjacent row above it. This moves
		# only the text's screen-space height, never the door or landing cell.
		for row in range(3):
			var bounds: Rect2=candidate.bounds
			bounds.position.y-=float(row)*caption_step
			if not viewport.encloses(bounds):continue
			var overlaps:=false
			for reserved in occupied:
				if reserved.intersects(bounds):overlaps=true;break
			if overlaps:continue
			var label: Dictionary=candidate.label.duplicate()
			label.height=48.0+float(row)*caption_step/world_zoom
			accepted.append(label);occupied.append(bounds)
			break
	return accepted

func _append_depth_effect(layers: Array, sample: Dictionary, feet_y: float) -> void:
	# Native back/front frame sets straddle the same foot-depth as the actor.
	# Appending both after all actors made source back effects cover bodies.
	for side_name in ["back","front"]:
		for frame in sample.get(side_name,[]):
			frame["depth_y"]=feet_y+(-0.5 if side_name=="back" else 0.5)
			layers.append(frame)

func _job_name(job: String) -> String:
	return "평민" if job=="commoner" else job

func _event_text(event: Dictionary) -> String:
	match str(event.type):
		"level_up": return "레벨이 올랐습니다! Lv"+str(game.state.character.level)
		"job_changed": return str(event.job)+"로 전직했습니다."
		"skill_learned": return str(content.data.skills[event.skill_id].name)+"을 배웠습니다. 기술 패널과 숫자 단축키에서 사용하세요."
		"player_died": return "귀신이 되었습니다. 부활하면 마을의 유효한 부활 지점으로 돌아갑니다."
		"bought": return "구매했습니다. 가방에서 장착하거나 사용하세요."
		"sold": return "판매하고 금전을 받았습니다."
		"equipped": return "장착했습니다. 능력치와 필드 모습에 반영됩니다."
		"unequipped": return "장비를 해제했습니다."
		"healed": return "치료했습니다."
		"resurrected": return "마을에서 부활했습니다."
		"item_used": return "아이템을 사용했습니다."
		"quest_accepted": return "의뢰를 받았습니다. 목표를 달성한 뒤 다시 대화하세요."
		"quest_completed": return "의뢰를 완료하고 보상을 받았습니다."
		"crafted": return "재료를 조합했습니다. 물품 패널을 확인하세요."
		"advanced": return "승급했습니다. 사범에게 새로운 기술을 배울 수 있습니다."
		"summoned": return "동료를 소환했습니다."
		"item_identified": return "물건을 감정했습니다."
		"revived": return "다시 일어났습니다."
		"trained": return "경험치를 사용해 능력을 단련했습니다."
		"stored": return "물건을 맡겼습니다."
		"withdrawn": return "맡긴 물건을 찾았습니다."
		"weapon_named": return "무기에 이름을 붙였습니다."
	return str(event.type)

func _reason(reason: String) -> String:
	return {"NO_NEARBY_TARGET":"전방이나 바로 옆에 공격할 몬스터가 없습니다.","ACTION_COOLDOWN":"다음 공격을 준비하고 있습니다.","BLOCKED_TILE":"길이 막혔습니다.","NPC_OUT_OF_REACH":"NPC 가까이 걸어가세요.","TARGET_OUT_OF_REACH":"공격할 대상 가까이 가세요.","INSUFFICIENT_MONEY":"금전이 부족합니다.","INSUFFICIENT_MATERIALS":"학습 재료가 부족합니다.","LEVEL_TOO_LOW":"필요한 레벨에 도달하지 않았습니다.","WRONG_JOB_TEACHER":"현재 직업의 사범에게 배우세요.","INSUFFICIENT_HP_MP":"체력 또는 마력이 부족합니다.","SKILL_NOT_LEARNED":"아직 배우지 않은 기술입니다.","JOB_CHANGE_REQUIRED":"먼저 Lv5에 사범에게 전직하세요.","ALREADY_LEARNED":"이미 배운 기술입니다.","BLOCKED":"지나갈 수 없는 곳입니다.","CHARACTER_DEAD":"귀신 상태입니다. 부활하세요.","ADVANCEMENT_REQUIRED":"먼저 사범에게 필요한 승급을 마치세요.","WRONG_JOB":"현재 직업으로 사용할 수 없습니다.","QUEST_NOT_READY":"의뢰 목표를 아직 달성하지 못했습니다.","QUEST_OBJECTIVE_INCOMPLETE":"의뢰 목표를 아직 달성하지 못했습니다.","ADVANCEMENT_ORDER_REQUIRED":"이전 승급부터 차례로 마치세요.","INSUFFICIENT_MONEY_OR_MATERIALS":"금전 또는 재료가 부족합니다.","EXIT_LEVEL_REQUIRED":"이 사냥터에 들어갈 레벨이 부족합니다.","HP_ALREADY_FULL":"이미 체력이 가득합니다.","MP_ALREADY_FULL":"이미 마력이 가득합니다.","WRONG_GUARDIAN":"선택한 수호신의 기술을 배우세요.","INSUFFICIENT_XP":"단련에 사용할 경험치가 부족합니다.","STAT_REQUIREMENT":"장비에 필요한 능력치가 부족합니다.","INVALID_WEAPON_NAME":"무기 이름은 한글·영문·숫자 2~12자로 입력하세요.","INVALID_CUSTOM_NAME":"무기 이름은 한글·영문·숫자 2~12자로 입력하세요.","NAME_UNCHANGED":"이미 같은 이름입니다.","INSUFFICIENT_STATS":"장비에 필요한 능력치가 부족합니다.","BANK_FULL":"맡길 공간이 부족합니다.","UNEQUIP_FIRST":"먼저 장비를 해제하세요.","QUEST_ALREADY_COMPLETED":"이미 마친 의뢰입니다.","RECIPE_MATERIALS_REQUIRED":"조합 재료가 부족합니다.","INVENTORY_FULL":"물품 공간이 부족합니다.","NPC_SERVICE_REQUIRED":"이 서비스를 제공하는 NPC에게 가세요.","INSUFFICIENT_INGREDIENTS":"필요한 재료가 부족합니다.","ADVANCEMENT_LEVEL_REQUIRED":"승급에 필요한 레벨에 도달하지 않았습니다.","QUEST_ALREADY_ACCEPTED":"이미 받은 의뢰입니다.","NOTHING_TO_IDENTIFY":"감정할 물건을 선택하세요.","STATUS_SILENCED":"침묵 상태에서는 기술을 쓸 수 없습니다.","STATUS_PARALYZED":"마비가 풀릴 때까지 기다리세요."}.get(reason,reason)

func _run_smoke() -> void:
	await get_tree().process_frame
	checkpoint("input",{"method":"explicit automated production command operator","not_actual_ime":true})
	game.state={}
	var created: Dictionary=game.create_character("연결시험",OWNER,{"guardian":"주작"})
	save_path="user://gameplay-p3/tests/gui-smoke-"+str(Time.get_ticks_usec())+".json"
	if created.status!="OK": _finish_smoke({"status":"FAIL","reason":created}); return
	_start_play()
	var saved := _save()
	var moves: Array=[]
	for delta in [Vector2i.RIGHT,Vector2i.LEFT,Vector2i.DOWN,Vector2i.UP]:
		moves.append(_dispatch({"type":"move","dx":delta.x,"dy":delta.y}))
		_consume_events(game.tick(0.2).get("events",[]))
		await get_tree().create_timer(0.1).timeout
	var trace_path:=OS.get_environment("BARAM_GAMEPLAY_TRACE")
	var replay: Variant={}
	if not trace_path.is_empty(): replay=JSON.parse_string(FileAccess.get_file_as_string(trace_path))
	if typeof(replay)==TYPE_DICTIONARY and replay.has("commands"):
		# Natural transcript is re-created from its original character metadata, never a state fixture.
		replay_result=await _replay_trace(replay)
	var final_saved:=_save()
	var loaded: Dictionary=store.read_game(save_path,str(game.state.character.owner_id),save_definitions)
	var canonicalizer=preload("res://storage/save_store.gd").new()
	var encoded_snapshot: Variant=JSON.parse_string(store._canonical(game.snapshot()))
	var equality:=loaded.has("payload") and canonicalizer.canonical(loaded.payload)==canonicalizer.canonical(encoded_snapshot)
	checkpoint("report",{"saved":final_saved,"restored_equal":equality})
	await _capture("final")
	_finish_smoke({"status":"PASS" if saved and final_saved and equality and content.assets.errors.is_empty() and view.draw_errors.is_empty() and int(replay_result.get("failures",0))==0 else "FAIL","scope":"actual Linux/Android GUI rendering and production commands; automated strings are not IME; audio calls are not physical listening","moves":moves,"replay":replay_result,"final":game.snapshot(),"asset_errors":content.assets.errors,"draw_errors":view.draw_errors,"events":event_log,"save_receipts":save_receipts,"loaded_status":loaded.status,"restored_equal":equality,"rendered_paths":view.last_drawn,"consumed":content.assets.consumed.keys()})

func _replay_trace(trace: Dictionary) -> Dictionary:
	var creation_data: Dictionary=trace.get("creation",{})
	if creation_data.is_empty(): return {"failures":1,"reason":"TRACE_CREATION_METADATA_REQUIRED"}
	game.state={}
	var created: Dictionary=game.create_character(str(creation_data.name),str(creation_data.owner),creation_data.get("options",{}))
	if created.status!="OK": return {"failures":1,"reason":created}
	save_path="user://gameplay-p3/tests/natural-gui-"+str(Time.get_ticks_usec())+".json"
	active_effects.clear(); selected_target=""
	var result: Dictionary={"failures":0,"commands":0,"ticks":0,"milestones":[],"mismatches":[],"state_injection":false}
	var count:=0
	for entry in trace.get("commands",[]):
		if entry.get("phase","natural")!="natural": continue
		if entry.has("command"):
			var cmd: Dictionary=entry.command.duplicate(true)
			var response: Dictionary=_dispatch(cmd)
			result.commands+=1
			if response.get("status")!=entry.get("result",{}).get("status") or response.get("reason")!=entry.get("result",{}).get("reason"):
				result.failures+=1
				if result.mismatches.size()<20: result.mismatches.append({"sequence":entry.get("sequence"),"observed":response,"expected":entry.get("result")})
		if entry.has("tick"):
			var remaining:=float(entry.tick)
			while remaining>0.00001:
				var step:=minf(0.1,remaining)
				_consume_events(game.tick(step).get("events",[])); remaining-=step
			result.ticks+=1
		if entry.has("milestone"):
			result.milestones.append(entry.milestone)
			_refresh_panels(); _render_world()
			await _capture(str(entry.milestone.name))
			await get_tree().create_timer(0.25).timeout
		count+=1
		if count%12==0: await get_tree().process_frame
	return result

func _capture(name: String) -> void:
	var destination:=OS.get_environment("BARAM_GAMEPLAY_EVIDENCE")
	if destination.is_empty(): return
	DirAccess.make_dir_recursive_absolute(destination)
	await RenderingServer.frame_post_draw
	var image:=get_viewport().get_texture().get_image()
	var error:=image.save_png(destination.path_join(name.validate_filename()+".png"))
	if error!=OK: checkpoint("capture_failed",{"name":name,"error":error})

func _finish_smoke(result: Dictionary) -> void:
	result.schema="baram.gameplay-gui-evidence/1"
	result.platform=OS.get_name(); result.engine=Engine.get_version_info(); result.input_manifest_sha256=content.manifest.get("manifest_sha256","")
	DirAccess.make_dir_recursive_absolute(smoke_report.get_base_dir())
	var file:=FileAccess.open(smoke_report,FileAccess.WRITE)
	if file: file.store_string(JSON.stringify(result,"  ")+"\n"); file.flush()
	print("GAMEPLAY_GUI_RESULT "+JSON.stringify({"status":result.status,"path":smoke_report}))
	get_tree().quit(0 if result.status=="PASS" else 1)

func _visible_ground(map: Dictionary,visible: Rect2) -> Array:
	if not map.has("ground_chunks"):return map.get("ground_layers",[]).duplicate()
	var layers: Array=[]
	for by in range(maxi(0,floori(visible.position.y/384)),mini(ceili(float(map.height)/16),ceili(visible.end.y/384))):
		for bx in range(maxi(0,floori(visible.position.x/384)),mini(ceili(float(map.width)/16),ceili(visible.end.x/384))):
			var key:=str(bx)+","+str(by)
			if map.ground_chunks.has(key):layers.append(map.ground_chunks[key])
	return layers
