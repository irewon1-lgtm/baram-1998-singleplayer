extends Control
## Ordinary offline play. Inspection and automated operators require explicit opt-in.
const Game = preload("res://state/gameplay_state.gd")
const Store = preload("res://storage/gameplay_store.gd")
const Content = preload("res://content/gameplay_content.gd")
const View = preload("res://render/gameplay_view.gd")
const Effect = preload("res://render/effect_preview.gd")
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
var appearance: OptionButton
var message: Label
var status: Label
var help_text: Label
var panels: TabContainer
var bag: ItemList
var equipment: ItemList
var skills: ItemList
var attributes: RichTextLabel
var dialogue: PanelContainer
var dialogue_body: VBoxContainer
var direction_picker: OptionButton
var audio: Array = []
var active_effects: Array = []
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
	checkpoint("manifest", {"ok":startup_error.is_empty(),"errors":content.errors,"game_errors":game.errors,"generation":content.manifest.get("generation")})
	_build_ui()
	if not startup_error.is_empty():
		message.text = startup_error
		if smoke: _finish_smoke({"status":"FAIL","reason":"INPUT_LOAD","errors":startup_error})
		return
	_refresh_characters()
	checkpoint("scene", {"mode":"ordinary_play" if not smoke else "explicit_smoke"})
	if smoke: _run_smoke.call_deferred()

func _button(parent: Node, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.custom_minimum_size.y = 34
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func _label(parent: Node, title: String) -> Label:
	var label := Label.new()
	label.text = title
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(label)
	return label

func _build_ui() -> void:
	var background := ColorRect.new()
	background.color = Color("162321")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(background)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","top","right","bottom"]: margin.add_theme_constant_override("margin_"+side, 12)
	add_child(margin)
	var root := VBoxContainer.new()
	margin.add_child(root)
	var heading := _label(root, "바람의나라 · 첫 걸음")
	heading.add_theme_font_size_override("font_size", 24)
	menu = VBoxContainer.new()
	root.add_child(menu)
	_label(menu, "로컬 프로필 · 이 기기의 캐릭터\n한국 2001 자료를 우선한 작업 규칙과 한국 원본 그림을 사용합니다. 지역 배치·스폰·확률·일부 외형은 재구성 실행값입니다.")
	names = OptionButton.new()
	menu.add_child(names)
	_button(menu, "이어 하기", _continue_character)
	_button(menu, "새 캐릭터", _show_creation)
	creation = VBoxContainer.new()
	menu.add_child(creation)
	_label(creation, "이름 (한글·영문·숫자 2~12자) · 고구려 평민 Lv1")
	name_input = LineEdit.new()
	name_input.placeholder_text = "캐릭터 이름"
	name_input.max_length = 12
	creation.add_child(name_input)
	guardian = OptionButton.new()
	for value in ["주작","청룡","백호","현무"]: guardian.add_item(value)
	creation.add_child(guardian)
	appearance = OptionButton.new()
	appearance.add_item("모습 1")
	appearance.add_item("모습 2")
	creation.add_child(appearance)
	_button(creation, "만들고 시작", _create_character)
	_button(creation, "취소", func(): creation.hide(); name_input.clear(); message.text="캐릭터를 만들지 않았습니다.")
	creation.hide()
	play = VBoxContainer.new()
	play.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(play)
	play.hide()
	status = _label(play, "")
	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	play.add_child(body)
	view = View.new()
	view.content = content.assets
	view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	view.world_pressed.connect(_click_world)
	body.add_child(view)
	panels = TabContainer.new()
	panels.custom_minimum_size.x = 280
	body.add_child(panels)
	var bag_box := VBoxContainer.new()
	bag_box.name = "가방"
	panels.add_child(bag_box)
	bag = ItemList.new()
	bag.size_flags_vertical = Control.SIZE_EXPAND_FILL
	bag.custom_minimum_size.y = 150
	bag.fixed_icon_size = Vector2i(24,24)
	bag_box.add_child(bag)
	_button(bag_box, "장착 / 사용", _use_selected_item)
	_button(bag_box, "가까운 NPC에 판매 (1개)", _sell_selected)
	var skill_box := VBoxContainer.new()
	skill_box.name = "기술"
	panels.add_child(skill_box)
	skills = ItemList.new()
	skills.size_flags_vertical = Control.SIZE_EXPAND_FILL
	skill_box.add_child(skills)
	direction_picker = OptionButton.new()
	for value in ["동","서","남","북"]: direction_picker.add_item(value)
	skill_box.add_child(direction_picker)
	_button(skill_box, "선택 기술 사용", _cast_selected)
	var equip_box := VBoxContainer.new()
	equip_box.name = "장비"
	panels.add_child(equip_box)
	equipment = ItemList.new()
	equipment.size_flags_vertical = Control.SIZE_EXPAND_FILL
	equipment.fixed_icon_size = Vector2i(24,24)
	equip_box.add_child(equipment)
	_button(equip_box, "선택 장비 해제", _unequip_selected)
	_button(equip_box, "대장장이에게 수리", _repair_selected)
	attributes = RichTextLabel.new()
	attributes.name = "능력치"
	attributes.custom_minimum_size.x = 280
	panels.add_child(attributes)
	help_text = _label(play, "방향키/WASD 이동 · Space 공격 · Enter 대화 · Z 줍기 · 숫자 1~9 기술 · Tab 패널\n지도를 누르면 가까운 대상과 대화하거나 공격합니다. 마을 길 끝의 네 문으로 초보 사냥터에 갑니다.")
	var actions := HBoxContainer.new()
	play.add_child(actions)
	_button(actions, "대화", _talk_nearest)
	_button(actions, "줍기", _pickup_nearest)
	_button(actions, "귀신 → 부활", func(): _dispatch({"type":"respawn"}))
	_button(actions, "저장하고 처음으로", _return_menu)
	dialogue = PanelContainer.new()
	dialogue.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	dialogue.position = Vector2(100,100)
	dialogue.custom_minimum_size = Vector2(480,280)
	add_child(dialogue)
	var dialogue_scroll := ScrollContainer.new()
	dialogue_scroll.custom_minimum_size=Vector2(480,330)
	dialogue_scroll.size=Vector2(480,330)
	dialogue.add_child(dialogue_scroll)
	dialogue_body = VBoxContainer.new()
	dialogue_body.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	dialogue_scroll.add_child(dialogue_body)
	dialogue.hide()
	message = _label(root, "로컬 캐릭터를 선택하거나 새로 만드세요.")
	message.custom_minimum_size.y = 46
	for i in range(8):
		var player := AudioStreamPlayer.new()
		player.volume_db = -8
		add_child(player)
		audio.append(player)
	_build_touch()
	resized.connect(_resize_ui)
	_resize_ui()

func _build_touch() -> void:
	if OS.get_name() not in ["Android","iOS"]: return
	var overlay := Control.new()
	mobile_controls=overlay
	overlay.hide()
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	view.add_child(overlay)
	for entry in [["↑",Vector2(72,-190),Vector2i(0,-1)],["←",Vector2(12,-130),Vector2i(-1,0)],["↓",Vector2(72,-70),Vector2i(0,1)],["→",Vector2(132,-130),Vector2i(1,0)]]:
		var button := Button.new()
		button.text = entry[0]
		button.anchor_top = 1; button.anchor_bottom = 1
		button.position = entry[1]; button.size = Vector2(56,56)
		var move: Vector2i = entry[2]
		button.button_down.connect(func(): _begin_touch_move(move))
		button.button_up.connect(func(): touch_moves.erase(str(move)))
		overlay.add_child(button)
	var attack := _button(overlay,"공격",func(): _dispatch({"type":"attack","target_id":selected_target}))
	attack.anchor_left = 1; attack.anchor_right = 1; attack.anchor_top = 1; attack.anchor_bottom = 1
	attack.offset_left=-100; attack.offset_top=-140; attack.offset_right=-16; attack.offset_bottom=-70
	var skill := _button(overlay,"기술",_cast_selected)
	skill.anchor_left = 1; skill.anchor_right = 1; skill.anchor_top = 1; skill.anchor_bottom = 1
	skill.offset_left=-100; skill.offset_top=-220; skill.offset_right=-16; skill.offset_bottom=-160
	if DisplayServer.has_feature(DisplayServer.FEATURE_ORIENTATION): DisplayServer.screen_set_orientation(DisplayServer.SCREEN_LANDSCAPE)

func _begin_touch_move(move: Vector2i) -> void:
	touch_moves[str(move)]=move
	if game.state.is_empty() or not play.visible or dialogue.visible: return
	# A press/release can arrive in one slow Android render frame. Commit the
	# initial step on press; _process continues repeat movement while held.
	var result: Dictionary=_dispatch({"type":"move","dx":move.x,"dy":move.y})
	input_repeat=0.15
	checkpoint("touch_direction",{"dx":move.x,"dy":move.y,"status":result.status,"reason":result.get("reason"),"x":game.state.character.x,"y":game.state.character.y})

func _resize_ui() -> void:
	if panels == null: return
	panels.custom_minimum_size.x = 260 if size.x < 1000 else 300
	help_text.visible = size.y > 600
	if is_instance_valid(dialogue): dialogue.position = Vector2(maxf(12,(size.x-500)/2),maxf(60,(size.y-350)/2))

func _refresh_characters() -> void:
	names.clear()
	DirAccess.make_dir_recursive_absolute("user://gameplay-p3/characters")
	var directory := DirAccess.open("user://gameplay-p3/characters")
	if directory:
		for file in directory.get_files():
			if not file.ends_with(".json"): continue
			var path := "user://gameplay-p3/characters/"+file
			var saved: Dictionary = store.read_game(path,OWNER,content.data)
			if saved.has("payload"):
				var c: Dictionary = saved.payload.character
				names.add_item(str(c.name)+" · Lv"+str(c.level)+" "+_job_name(str(c.job)))
				names.set_item_metadata(names.item_count-1,path)
	if names.item_count == 0: names.add_item("아직 캐릭터가 없습니다")

func _create_character() -> void:
	var name := name_input.text.strip_edges()
	var path := "user://gameplay-p3/characters/"+(OWNER+":"+name).sha256_text().substr(0,24)+".json"
	if FileAccess.file_exists(path): message.text="같은 이름의 캐릭터가 있습니다. 이어 하기를 사용하세요."; return
	game.state = {}
	var result: Dictionary = game.create_character(name,OWNER,{"guardian":guardian.get_item_text(guardian.selected),"appearance":{"variant":appearance.selected}})
	if result.status != "OK": message.text="이름을 확인하세요: "+str(result.reason); return
	save_path = path
	if not _save(): game.state={}; return
	_start_play()
	checkpoint("character_created",{"name":name,"level":1,"job":"commoner","skills":game.state.skills})

func _continue_character() -> void:
	if names.selected < 0: return
	var path: Variant = names.get_item_metadata(names.selected)
	if typeof(path) != TYPE_STRING: return
	var loaded: Dictionary = store.read_game(path,OWNER,content.data)
	if not loaded.has("payload"): message.text="불러오기 보류: "+str(loaded.status); return
	game.state = {}
	var restored: Dictionary = game.restore(loaded.payload)
	if restored.status != "OK": message.text="진행 보존 후 불러오기 보류: "+str(restored.reason); return
	save_path = path
	_start_play()
	checkpoint("loaded",{"revision":game.state.revision,"character":game.state.character})

func _start_play() -> void:
	menu.hide(); play.show(); dialogue.hide()
	if is_instance_valid(mobile_controls): mobile_controls.show()
	save_failure = false
	selected_target = ""; current_npc = ""
	get_viewport().gui_release_focus()
	message.text="마을의 네 길을 따라 사냥터로 걸어가세요. 평민 Lv5가 되면 원하는 사범에게 전직할 수 있습니다."
	_refresh_panels(); _render_world()
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
	checkpoint("ui_layout",{"controls":controls})

func _save() -> bool:
	if game.state.is_empty() or save_path.is_empty(): return false
	var owner := str(game.state.character.owner_id) if smoke else OWNER
	var receipt: Dictionary = store.write_game(save_path,game.snapshot(),owner,content.data)
	save_receipts.append({"status":receipt.status,"revision":game.state.revision,"time":clock})
	if save_receipts.size()>64: save_receipts.pop_front()
	if receipt.status not in ["SAVED","UNCHANGED","OK"]:
		save_failure = true
		message.text="저장 실패 · 진행을 보존하고 행동을 중지합니다: "+str(receipt.status)+" "+str(receipt.get("reason",""))
		checkpoint("save_failed",receipt)
		return false
	checkpoint("save",{"revision":game.state.revision,"status":receipt.status})
	return true

func _dispatch(command: Dictionary) -> Dictionary:
	if game.state.is_empty() or save_failure: return {"status":"REFUSED","reason":"NO_ACTIVE_OR_SAVED_STATE","events":[]}
	var before: Dictionary = game.snapshot()
	command = command.duplicate(true)
	if not smoke or not command.has("request_id"):
		command["request_id"] = "ui:"+str(int(game.state.request_watermarks.get("ui",0))+1)
	var result: Dictionary = game.command(command)
	if result.get("changed",false) and str(command.type) not in ["move","attack","cast"]:
		if not _save(): game.restore(before); return {"status":"SAVE_FAILED","events":[]}
	_consume_events(result.get("events",[]))
	if result.status not in ["OK","DUPLICATE","CANCELLED"] and result.reason not in ["ACTION_COOLDOWN","MOVE_COOLDOWN"]:
		message.text = _reason(str(result.reason))
	if result.get("changed",false): _refresh_panels()
	return result

func _consume_events(events: Array) -> void:
	for event in events:
		event_log.append(event)
		if event_log.size()>200: event_log.pop_front()
		var type := str(event.type)
		if event.get("sound_id") != null: _sound(str(event.sound_id))
		if event.get("effect_id") != null:
			active_effects.append({"id":str(event.effect_id),"at":clock,"map_id":event.get("map_id",game.state.character.map_id),"x":event.get("x",game.state.character.x),"y":event.get("y",game.state.character.y)})
		if type in ["attack_started","cast_started","moved"]:
			character_animation = {"attack_started":"attack","cast_started":"casting","moved":"walking"}[type]
			animation_until = clock + (0.22 if type=="moved" else 0.55)
		if type == "monster_attack_started": actor_animations[str(event.get("target_id",""))] = clock+0.5
		if type == "monster_moved":
			var id:=str(event.target_id)
			var dx:=int(event.x)-int(event.from.x); var dy:=int(event.y)-int(event.from.y)
			actor_directions[id]=1 if dx>0 else 3 if dx<0 else 2 if dy>0 else 0
			actor_walk_until[id]=clock+0.3
		if type == "monster_died" and selected_target==str(event.get("target_id","")): selected_target=""
		if type == "dialogue": _show_dialogue(str(event.npc_id))
		if type == "map_changed": selected_target=""; movement=Vector2i.ZERO; touch_moves.clear(); dialogue.hide(); message.text=str(content.data.maps[event.map_id].name)
		if event.get("sound_id")==null and type in ["picked_up","bought","sold","equipped","unequipped","player_died"]:
			var key:=str({"picked_up":"pickup","bought":"transaction","sold":"transaction","equipped":"equip","unequipped":"equip","player_died":"death"}[type])
			_sound(str(content.data.config.get("audio",{}).get(key,{"pickup":2,"transaction":12,"equip":13,"death":10}[key])))
		if type in ["level_up","job_changed","skill_learned","bought","sold","equipped","unequipped","healed","resurrected","player_died","item_used"]:
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
	clock += delta
	panel_clock += delta
	if not frame_checkpoint and is_instance_valid(view) and startup_error.is_empty():
		frame_checkpoint = true
		checkpoint("first_frame",{"mode":"menu","viewport":[size.x,size.y]})
		_layout_checkpoint.call_deferred()
	if game.state.is_empty() or not play.visible or save_failure: return
	if not smoke:
		var before: Dictionary = game.snapshot()
		var result: Dictionary = game.tick(minf(delta,0.2))
		var critical := false
		for event in result.get("events",[]):
			if str(event.type) in ["monster_died","skill_applied","player_died","level_up"]: critical=true
		if critical and not _save(): game.restore(before)
		else: _consume_events(result.get("events",[]))
		autosave += delta
		if autosave>=3.0: autosave=0; _save()
		input_repeat -= delta
		if input_repeat<=0 and not dialogue.visible:
			var move := movement
			if not touch_moves.is_empty(): move=touch_moves.values()[-1]
			if move!=Vector2i.ZERO:
				_dispatch({"type":"move","dx":move.x,"dy":move.y}); input_repeat=0.15
	if int(game.state.revision)!=last_state_revision and panel_clock>=0.2: panel_clock=0; _refresh_panels()
	_render_world()

func _input(event: InputEvent) -> void:
	if not event is InputEventKey or not play.visible or game.state.is_empty(): return
	var key: int = event.physical_keycode
	if dialogue.visible:
		if event.pressed and key==KEY_ESCAPE: dialogue.hide(); movement=Vector2i.ZERO; get_viewport().set_input_as_handled()
		return
	if key in [KEY_UP,KEY_W,KEY_DOWN,KEY_S,KEY_LEFT,KEY_A,KEY_RIGHT,KEY_D]:
		if event.pressed:
			movement={KEY_UP:Vector2i.UP,KEY_W:Vector2i.UP,KEY_DOWN:Vector2i.DOWN,KEY_S:Vector2i.DOWN,KEY_LEFT:Vector2i.LEFT,KEY_A:Vector2i.LEFT,KEY_RIGHT:Vector2i.RIGHT,KEY_D:Vector2i.RIGHT}[key]
			if not event.echo:
				_dispatch({"type":"move","dx":movement.x,"dy":movement.y}); input_repeat=0.15
		else: movement=Vector2i.ZERO
		get_viewport().set_input_as_handled()
		return
	if not event.pressed or event.echo: return
	if key==KEY_ESCAPE: dialogue.hide(); movement=Vector2i.ZERO
	elif key==KEY_SPACE and not dialogue.visible: _dispatch({"type":"attack","target_id":selected_target})
	elif key==KEY_ENTER and not dialogue.visible: _talk_nearest()
	elif key==KEY_Z and not dialogue.visible: _pickup_nearest()
	elif key==KEY_TAB: panels.current_tab=(panels.current_tab+1)%4
	elif key>=KEY_1 and key<=KEY_9:
		var slot := str(key-KEY_0)
		if game.state.hotkeys.has(slot): _cast(str(game.state.hotkeys[slot]))
	get_viewport().set_input_as_handled()

func _notification(what: int) -> void:
	if what==NOTIFICATION_APPLICATION_FOCUS_OUT: movement=Vector2i.ZERO; touch_moves.clear()
	if what==NOTIFICATION_APPLICATION_PAUSED and not game.state.is_empty(): _save()
	if what==NOTIFICATION_WM_GO_BACK_REQUEST:
		if is_instance_valid(dialogue) and dialogue.visible: dialogue.hide()
		elif not game.state.is_empty(): _return_menu()
	if what==NOTIFICATION_WM_CLOSE_REQUEST:
		if game.state.is_empty() or _save(): get_tree().quit()

func _return_menu() -> void:
	if not _save(): return
	game.state={}; play.hide(); menu.show(); dialogue.hide(); touch_moves.clear(); movement=Vector2i.ZERO
	if is_instance_valid(mobile_controls): mobile_controls.hide()
	_refresh_characters(); message.text="저장했습니다. 이어 하기에서 같은 진행을 불러올 수 있습니다."

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

func _click_world(tile: Vector2i) -> void:
	if game.state.is_empty() or dialogue.visible: return
	for id in content.data.npcs:
		var npc: Dictionary = content.data.npcs[id]
		if npc.map_id==game.state.character.map_id and Vector2i(npc.x,npc.y)==tile:
			_dispatch({"type":"talk","npc_id":id}); return
	for id in game.state.monsters:
		var monster: Dictionary = game.state.monsters[id]
		if monster.map_id==game.state.character.map_id and monster.alive and Vector2i(monster.x,monster.y)==tile:
			selected_target=id; message.text="대상: "+str(content.data.monsters[monster.monster_id].name)
			_dispatch({"type":"attack","target_id":id}); return
	var delta := tile-Vector2i(game.state.character.x,game.state.character.y)
	if absi(delta.x)+absi(delta.y)==1: _dispatch({"type":"move","dx":delta.x,"dy":delta.y})

func _show_dialogue(id: String) -> void:
	current_npc=id; movement=Vector2i.ZERO; touch_moves.clear()
	for child in dialogue_body.get_children(): child.queue_free()
	var npc: Dictionary = content.data.npcs[id]
	_label(dialogue_body,str(npc.name)+"\n"+str(npc.get("dialogue",{}).get("greeting","")))
	for item_id in npc.get("shop",{}):
		var trade: Dictionary = npc.shop[item_id]
		if trade.get("buy_price")==null: continue
		var bound_id := str(item_id)
		var price := str(trade.buy_price)
		_button(dialogue_body,str(content.data.items[item_id].name)+" 구매 · "+price+"전",func(): _dispatch({"type":"buy","npc_id":id,"item_id":bound_id,"quantity":1}))
	if "change_job" in npc.get("services",[]):
		_button(dialogue_body,str(npc.get("job",""))+" 전직 · Lv5",func(): _dispatch({"type":"change_job","npc_id":id,"job":npc.job}))
	if "teach_skill" in npc.get("services",[]):
		for skill_id in content.data.skills:
			var skill: Dictionary = content.data.skills[skill_id]
			if id not in skill.get("teacher_ids",[]): continue
			var bound_skill := str(skill_id)
			var costs := ""
			for material in skill.get("ingredients",{}): costs += " "+str(content.data.items[material].name)+"×"+str(skill.ingredients[material])
			_button(dialogue_body,str(skill.name)+" 학습 · Lv"+str(skill.learn_level)+" / "+str(skill.get("learn_money",0))+"전"+costs,func(): _dispatch({"type":"learn","npc_id":id,"skill_id":bound_skill}))
	if "heal" in npc.get("services",[]): _button(dialogue_body,"치료 · "+str(npc.get("heal_cost",content.data.config.get("heal_price",5)))+"전",func(): _dispatch({"type":"heal","npc_id":id}))
	_button(dialogue_body,"닫기 / 취소",func(): _dispatch({"type":"cancel"}); dialogue.hide())
	dialogue.show()

func _selection(list: ItemList) -> String:
	var indexes := list.get_selected_items()
	return str(list.get_item_metadata(indexes[0])) if indexes.size()>0 else ""

func _instance(id: String) -> Dictionary:
	for item in game.state.inventory:
		if item.instance_id==id: return item
	return {}

func _use_selected_item() -> void:
	var id := _selection(bag); var instance := _instance(id)
	if instance.is_empty(): return
	var definition: Dictionary = content.data.items[instance.item_id]
	_dispatch({"type":"equip" if not str(definition.get("slot","")).is_empty() else "use_item","instance_id":id})

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
	var id := _selection(skills)
	if id.is_empty() and not game.state.skills.is_empty(): id=str(game.state.skills[0])
	if not id.is_empty(): _cast(id)

func _cast(id: String) -> void:
	var cmd := {"type":"cast","skill_id":id,"target_id":selected_target}
	if content.data.skills[id].kind=="return": cmd.direction=direction_picker.get_item_text(direction_picker.selected)
	_dispatch(cmd)

func _refresh_panels() -> void:
	if game.state.is_empty(): return
	var c: Dictionary = game.state.character
	var previous_bag := _selection(bag); var previous_skill := _selection(skills); var previous_equipment := _selection(equipment)
	bag.clear(); equipment.clear(); skills.clear()
	for item in game.state.inventory:
		var def: Dictionary = content.data.items[item.item_id]
		bag.add_item(str(def.name)+" ×"+str(item.quantity),content.icon(str(item.item_id)))
		var index := bag.item_count-1
		bag.set_item_metadata(index,item.instance_id)
		bag.set_item_tooltip(index,str(def.name)+" · 내구 "+str(item.durability)+" · "+str(def.get("fact_status","RECONSTRUCTED")))
		if item.instance_id==previous_bag: bag.select(index)
	for slot in game.state.equipment:
		var item := _instance(str(game.state.equipment[slot]))
		if item.is_empty(): continue
		equipment.add_item(str(slot)+": "+str(content.data.items[item.item_id].name)+" ("+str(item.durability)+")",content.icon(str(item.item_id)))
		equipment.set_item_metadata(equipment.item_count-1,slot)
		if slot==previous_equipment: equipment.select(equipment.item_count-1)
	for id in game.state.skills:
		var def: Dictionary=content.data.skills[id]
		var key := ""
		for slot in game.state.hotkeys:
			if game.state.hotkeys[slot]==id: key="["+str(slot)+"] "
		skills.add_item(key+str(def.name)+" · MP "+str(def.get("mp_cost",0)))
		skills.set_item_metadata(skills.item_count-1,id)
		if id==previous_skill: skills.select(skills.item_count-1)
	var derived: Dictionary = game.derived_stats()
	attributes.text="이름  "+str(c.name)+"\n국적  "+str(c.get("nationality","고구려"))+"\n수호  "+str(c.get("guardian","주작"))+"\n직업  "+_job_name(str(c.job))+"\n레벨  "+str(c.level)+"\n경험치  "+str(c.xp)+"\n체력  "+str(c.hp)+" / "+str(c.hp_max)+"\n마력  "+str(c.mp)+" / "+str(c.mp_max)+"\n공격  "+str(derived.attack)+"\n방어  "+str(derived.defense)+"\n금전  "+str(c.money)+"전\n사냥  "+str(game.state.stats.kills)+"마리\n좌표  "+str(c.x)+", "+str(c.y)+"\n\n오프라인 로컬 진행\n원작 미확정 실행값은 재구성 규칙입니다."
	status.text=str(c.name)+" · "+_job_name(str(c.job))+" Lv"+str(c.level)+"  HP "+str(c.hp)+"/"+str(c.hp_max)+"  MP "+str(c.mp)+"/"+str(c.mp_max)+"  XP "+str(c.xp)+"  "+str(c.money)+"전  · "+str(content.data.maps[c.map_id].name)+( " · 귀신" if c.dead else "")
	last_state_revision=int(game.state.revision)

func _look_player() -> String:
	var armor := false
	var weapon_graphics: Dictionary = {}
	for instance_id in game.state.equipment.values():
		var item := _instance(str(instance_id))
		if item.is_empty(): continue
		var def: Dictionary = content.data.items[item.item_id]
		if int(def.get("durability",0))>0 and int(item.durability)<=0: continue
		if def.get("slot")=="weapon": weapon_graphics=content.actors.get("item_equipment_graphics",{}).get(str(item.item_id),{})
		if str(item.item_id)=="gp:item:novice_armor": armor=true
	var look := str(weapon_graphics.get("armored_player_look" if armor else "player_look","player_armor" if armor else "player_base"))
	if int(game.state.character.appearance.get("variant",0))==1: look+="_alt"
	return look

func _actor_layer(look: String, animation: String, direction: int, x: int, y: int) -> Dictionary:
	var frame: Dictionary = content.actor(look,animation,direction,clock)
	if frame.is_empty(): return {}
	var path := str(frame.path)
	if not path.begins_with("gameplay-assets/"): path="gameplay-assets/"+path
	var offset: Array = frame.get("offset",[0,0])
	return {"path":path,"x":x*24+12+float(offset[0]),"y":y*24+24+float(offset[1]),"depth_y":y*24+24}

func _render_world() -> void:
	if game.state.is_empty(): return
	var c: Dictionary = game.state.character
	var map: Dictionary = content.data.maps[c.map_id]
	var world_zoom:=1.65 if size.x>=1000 else 1.25
	var camera:=Vector2(int(c.x)*24+12,int(c.y)*24+12)
	var visible_world:=Rect2(camera-view.size/(2*world_zoom),view.size/world_zoom).grow(24)
	var layers: Array = map.get("ground_layers",[]).duplicate(true)
	if layers.is_empty() and map.has("floor_png"): layers.append({"path":map.floor_png,"x":0,"y":0})
	var sorted: Array = []
	for object in map.get("objects",[]):
		# Korean SOBJECT columns are exactly 24 pixels wide, height is in tiles.
		# Cull offscreen columns before texture lookup; foot-depth order survives.
		var bounds:=Rect2(float(object.x),float(object.y),24,maxf(24,float(object.get("height",6))*24))
		if not visible_world.intersects(bounds): continue
		var entry: Dictionary = object.duplicate(true)
		if not entry.has("path"): entry.path=entry.get("frame_png","")
		sorted.append(entry)
	var labels: Array=[]
	for landmark in map.get("landmarks",[]):
		if landmark.has("x") and landmark.has("y"):
			labels.append({"x":int(landmark.x)*24+12,"y":int(landmark.y)*24+24,"text":str(landmark.get("name",landmark.get("label",""))),"color":"ccb78d"})
	for id in content.data.npcs:
		var npc: Dictionary=content.data.npcs[id]
		if npc.map_id!=c.map_id: continue
		var layer := _actor_layer(str(npc.get("look_id",npc.get("appearance_id","tavern"))),"standing",int(npc.get("direction",2)),int(npc.x),int(npc.y))
		if not layer.is_empty(): sorted.append(layer)
		labels.append({"x":int(npc.x)*24+12,"y":int(npc.y)*24+24,"text":npc.name,"color":"f4d58a"})
	for id in game.state.monsters:
		var monster: Dictionary=game.state.monsters[id]
		if monster.map_id!=c.map_id or not monster.alive: continue
		var def: Dictionary=content.data.monsters[monster.monster_id]
		var animation := "attack" if clock<float(actor_animations.get(id,0)) else "walking" if clock<float(actor_walk_until.get(id,0)) else "standing"
		var layer := _actor_layer(str(def.get("look_id",def.get("appearance_id","rabbit"))),animation,int(actor_directions.get(id,2)),int(monster.x),int(monster.y))
		if not layer.is_empty(): sorted.append(layer)
		labels.append({"x":int(monster.x)*24+12,"y":int(monster.y)*24+24,"text":str(def.name)+( " ◇" if id==selected_target else ""),"hp":monster.hp,"hp_max":def.hp,"color":"f0e8c7"})
	for loot in game.state.loot:
		if loot.map_id!=c.map_id: continue
		var icon: Dictionary=content.actors.get("icons",{}).get(str(loot.get("item_id","")),{})
		if not icon.is_empty():
			var path:=str(icon.path)
			if not path.begins_with("gameplay-assets/"): path="gameplay-assets/"+path
			sorted.append({"path":path,"x":int(loot.x)*24+2,"y":int(loot.y)*24+8,"depth_y":int(loot.y)*24+23})
		labels.append({"x":int(loot.x)*24+12,"y":int(loot.y)*24+50,"text":"전리품 · Z","color":"d3c480"})
	var player := _actor_layer(_look_player(),character_animation if clock<animation_until else "standing",int(c.direction),int(c.x),int(c.y))
	if not player.is_empty(): player.opacity=0.4 if c.dead else 1.0; sorted.append(player)
	labels.append({"x":int(c.x)*24+12,"y":int(c.y)*24+24,"text":c.name,"color":"a9e8bd"})
	sorted.sort_custom(func(a,b): return float(a.get("depth_y",a.y))<float(b.get("depth_y",b.y)))
	layers.append_array(sorted)
	for i in range(active_effects.size()-1,-1,-1):
		var active: Dictionary=active_effects[i]
		if clock-float(active.at)>10: active_effects.remove_at(i); continue
		if active.map_id!=c.map_id: continue
		var definition: Dictionary=content.effects.get(str(active.id),{})
		if definition.is_empty(): continue
		var sample: Dictionary=Effect.layers(definition,clock-float(active.at),Vector2(float(active.x)*24+12,float(active.y)*24+24))
		if sample.finished: active_effects.remove_at(i)
		else: layers.append_array(sample.back); layers.append_array(sample.front)
	view.labels=labels
	view.configure(layers,Vector2(int(map.width)*24,int(map.height)*24),camera,world_zoom)

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
	return str(event.type)

func _reason(reason: String) -> String:
	return {"NPC_OUT_OF_REACH":"NPC 가까이 걸어가세요.","TARGET_OUT_OF_REACH":"공격할 대상 가까이 가세요.","INSUFFICIENT_MONEY":"금전이 부족합니다.","INSUFFICIENT_MATERIALS":"학습 재료가 부족합니다.","LEVEL_TOO_LOW":"필요한 레벨에 도달하지 않았습니다.","WRONG_JOB_TEACHER":"현재 직업의 사범에게 배우세요.","INSUFFICIENT_HP_MP":"체력 또는 마력이 부족합니다.","SKILL_NOT_LEARNED":"아직 배우지 않은 기술입니다.","JOB_CHANGE_REQUIRED":"먼저 Lv5에 사범에게 전직하세요.","ALREADY_LEARNED":"이미 배운 기술입니다.","BLOCKED":"지나갈 수 없는 곳입니다.","CHARACTER_DEAD":"귀신 상태입니다. 부활하세요."}.get(reason,reason)

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
	var loaded: Dictionary=store.read_game(save_path,str(game.state.character.owner_id),content.data)
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
