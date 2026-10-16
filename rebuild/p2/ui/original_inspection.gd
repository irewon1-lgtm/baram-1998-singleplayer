extends Control
## Original assets in the inherited P2 project; this is an inspection, not P3.
const Content = preload("res://content/private_content.gd")
const Canvas = preload("res://render/original_view.gd")
const Store = preload("res://storage/save_store.gd")
var content = Content.new()
var state: RefCounted
var canvas: Control
var preview: Control
var status: Label
var info: Label
var panel_labels: Array[Label] = []
var selector: OptionButton
var mode_selector: OptionButton
var mode := 0
var selection := 0
var direction := 0
var action := "standing"
var variant_index := 0
var equipment_enabled := true
var tick := 0
var elapsed := 0.0
var probe := Vector2i(32, 32)
var events: Array = []
var checks: Array = []
var runtime_path := ""
var player: AudioStreamPlayer
var capture: AudioEffectCapture
var output := ""
var smoke := false
var timers: Array[float] = []
var start_us := 0
var audio_peak := 0.0
var audio_samples := PackedVector2Array()
var effect_elapsed := 0.0
var effect_drawn_paths: Array[String] = []
var source_frame_paths: Dictionary = {}
var save_catalog: Dictionary = {}
var test_save: Dictionary = {}
var test_save_path := ""
var save_result: Dictionary = {}
var map_tests: Array = []

func setup(path: String, shared_state: RefCounted) -> void:
	runtime_path = path
	state = shared_state

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	start_us = Time.get_ticks_usec()
	var loaded: bool = content.open_generation(runtime_path)
	state.profile_id = "KR125_KR491_DIAGNOSTIC_SEPARATE_PROFILES"
	state.original_input_status = "SCOPED_ORIGINAL_BYTES" if loaded else "BLOCKED_INVALID_GENERATION"
	var box := VBoxContainer.new()
	box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(box)
	var heading := Label.new()
	heading.text = "한국 원본 P2 검수 · 판본별 독립 표시"
	box.add_child(heading)
	var row := HBoxContainer.new()
	box.add_child(row)
	mode_selector = OptionButton.new()
	for title in ["한국 1.25 지도", "한국 4.91 캐릭터", "한국 4.91 효과", "한국 4.91 생성 화면"]:
		mode_selector.add_item(title)
	mode_selector.item_selected.connect(_select_mode)
	row.add_child(mode_selector)
	selector = OptionButton.new()
	selector.item_selected.connect(_select_item)
	row.add_child(selector)
	var sound_button := Button.new()
	sound_button.text = "원본 WAV 별도 재생"
	sound_button.pressed.connect(_play_sound)
	row.add_child(sound_button)
	var columns := HBoxContainer.new()
	columns.size_flags_vertical = SIZE_EXPAND_FILL
	box.add_child(columns)
	canvas = Canvas.new()
	canvas.content = content
	canvas.size_flags_horizontal = SIZE_EXPAND_FILL
	columns.add_child(canvas)
	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 330
	columns.add_child(right)
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = SIZE_EXPAND_FILL
	tabs.tab_changed.connect(state.switch_panel)
	right.add_child(tabs)
	for title in ["물품", "기술", "장비", "능력치"]:
		var scroll := ScrollContainer.new()
		scroll.name = title
		tabs.add_child(scroll)
		var label := Label.new()
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.custom_minimum_size.x = 300
		scroll.add_child(label)
		panel_labels.append(label)
	preview = Canvas.new()
	preview.content = content
	preview.custom_minimum_size = Vector2(280, 140)
	right.add_child(preview)
	var controls := HBoxContainer.new()
	box.add_child(controls)
	for i in range(4):
		var b := Button.new()
		b.text = ["북", "동", "남", "서"][i]
		b.pressed.connect(_set_direction.bind(i))
		controls.add_child(b)
	for name in ["standing", "walking", "attack", "casting"]:
		var b := Button.new()
		b.text = {"standing":"정지", "walking":"걷기", "attack":"공격 외형", "casting":"시전 외형"}[name]
		b.pressed.connect(_set_action.bind(name))
		controls.add_child(b)
	var swap := Button.new()
	swap.text = "장비 교체"
	swap.pressed.connect(_swap_equipment)
	controls.add_child(swap)
	var unequip := Button.new()
	unequip.text = "장착 / 해제"
	unequip.pressed.connect(_toggle_equipment)
	controls.add_child(unequip)
	info = Label.new()
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(info)
	status = Label.new()
	status.text = "평민 Lv1 · 미학습 공격기술 0 · 희망직업 미선택 · 오프라인 검수"
	box.add_child(status)
	player = AudioStreamPlayer.new()
	add_child(player)
	AudioServer.add_bus()
	var bus := AudioServer.bus_count - 1
	AudioServer.set_bus_name(bus, "P2OriginalCapture")
	capture = AudioEffectCapture.new()
	capture.buffer_length = 4.0
	AudioServer.add_bus_effect(bus, capture)
	player.bus = "P2OriginalCapture"
	_sync_equipment()
	_select_mode(0)
	_log("generation_open", {"loaded":loaded, "generation":content.manifest.get("generation"), "errors":content.errors})
	smoke = "--p2-original-smoke" in OS.get_cmdline_user_args() or OS.has_feature("p2_original_smoke")
	if smoke:
		_run_original_smoke.call_deferred()

func _log(kind: String, details: Dictionary = {}) -> void:
	events.append({"event":kind, "us":Time.get_ticks_usec()-start_us, "details":details})

func _check(id: String, good: bool, details: Variant = "") -> void:
	checks.append({"id":id, "status":"PASS" if good else "FAIL", "details":details})

func _list() -> Array:
	match mode:
		0: return content.maps.get("maps", [])
		1: return content.kr491.get("character_variants", [])
		2: return content.kr491.get("effects", []).filter(func(e: Dictionary) -> bool: return e.get("preview_supported",false))
		3: return content.kr491.get("ui", [])
	return []

func _select_mode(index: int) -> void:
	mode = index
	selection = 0
	effect_elapsed = 0.0
	if player != null: player.stop()
	mode_selector.select(index)
	selector.clear()
	for entry in _list():
		selector.add_item(str(entry.get("native_id", entry.get("id", entry.get("name", "UNKNOWN")))))
	_center_map()
	_render()

func _center_map() -> void:
	if mode==0 and not _list().is_empty():
		var bounds: Array = _list()[selection % _list().size()].get("occupied_ground_bounds",[0,0,63,63])
		if bounds.size()==4: probe=Vector2i(int((bounds[0]+bounds[2])/2),int((bounds[1]+bounds[3])/2))

func _select_item(index: int) -> void:
	selection = index
	effect_elapsed = 0.0
	if player != null: player.stop()
	if mode == 1:
		variant_index = index
		_sync_equipment()
	tick = 0
	_center_map()
	_render()

func _set_direction(index: int) -> void:
	direction = index
	tick = 0
	_log("direction", {"direction":index})
	_render()

func _set_action(name: String) -> void:
	action = name
	tick = 0
	_log("inspection_motion", {"action":action, "historical_mapping":"VISUALLY_INFERRED", "inspection_frame_ms":130})
	_render()

func _swap_equipment() -> void:
	var variants: Array = content.kr491.get("character_variants", [])
	if variants.size() > 1:
		variant_index = (variant_index+1) % variants.size()
		equipment_enabled = true
		_sync_equipment()
	_log("equipment_swap", {"variant":variant_index})
	_render()

func _toggle_equipment() -> void:
	equipment_enabled = not equipment_enabled
	_sync_equipment()
	_log("equipment_toggle", state.equipment)
	_render()

func _asset(path: String, unit: String) -> String:
	if path.begins_with(unit+"/"):
		return path
	return unit.path_join(path)

func _part(kind: String, id: int) -> Dictionary:
	for entry in content.kr491.get("parts", {}).get(kind, []):
		if int(entry.get("id", -999)) == id:
			return entry
	return {}

func _sync_equipment() -> void:
	state.equipment = {"variant_index":variant_index,"enabled":equipment_enabled}

func _character_layers(center: Vector2 = Vector2(256, 256)) -> Array:
	var current_variant := int(state.equipment.get("variant_index",0))
	var current_enabled := bool(state.equipment.get("enabled",true))
	var variants: Array = content.kr491.get("character_variants", [])
	if variants.is_empty():
		return []
	var variant: Dictionary = variants[current_variant % variants.size()]
	var motion_name := "armed_walking" if action in ["walking","standing"] and current_enabled else action
	var motion: Dictionary = content.kr491.get("motion_inspection", {}).get(motion_name, {})
	var chosen: Dictionary = {}
	var body_frame := -1
	for kind in ["body", "head", "sword", "shield"]:
		if kind in ["sword", "shield"] and not current_enabled:
			continue
		var directions: Array = motion.get(kind, [])
		if direction >= directions.size() or typeof(directions[direction]) != TYPE_ARRAY:
			continue
		var sequence: Array = directions[direction]
		if sequence.is_empty():
			continue
		var index := int(sequence[(0 if action=="standing" else tick) % sequence.size()])
		if index < 0:
			continue
		var part: Dictionary = _part(kind, int(variant.get(kind, -999)))
		var frames: Array = part.get("frames", [])
		if index >= frames.size():
			content.errors.append("FRAME_BOUNDS: "+kind+":"+str(index))
			continue
		chosen[kind] = frames[index]
		if kind == "body":
			body_frame = index
	var order: Variant = content.kr491.get("motion_inspection", {}).get("draw_order", [])
	var tokens := ""
	if typeof(order) == TYPE_ARRAY and body_frame >= 0 and body_frame < order.size():
		tokens = str(order[body_frame])
	elif typeof(order) == TYPE_DICTIONARY:
		tokens = str(order.get(str(body_frame), ""))
	var layers: Array = []
	for token in tokens:
		var kind: String = {"b":"body", "h":"head", "w":"sword", "s":"shield"}.get(token, "")
		if not chosen.has(kind):
			continue
		var frame: Dictionary = chosen[kind]
		var offset: Array = frame.get("offset", [0,0])
		var path := _asset(str(frame.get("path", "")), "kr491")
		layers.append({"path":path, "x":center.x+float(offset[0]), "y":center.y+float(offset[1])})
		source_frame_paths[path] = {"part":kind, "original_frame":frame.get("frame"), "source_id":frame.get("source_id"), "order":tokens}
	return layers

func _render() -> void:
	if canvas == null:
		return
	var layers: Array = []
	var current: Dictionary = {}
	var items: Array = _list()
	if not items.is_empty():
		current = items[selection % items.size()]
	if mode == 0 and not current.is_empty():
		var floor_path := _asset(str(current.get("floor_png", "")), "maps")
		layers.append({"path":floor_path, "x":0, "y":0})
		var objects: Array = current.get("objects", []).duplicate()
		objects.sort_custom(func(a: Dictionary,b: Dictionary) -> bool: return float(a.get("depth_y",0))<float(b.get("depth_y",0)))
		for obj in objects:
			layers.append({"path":_asset(str(obj.get("frame_png", "")), "maps"), "x":obj.get("x",0), "y":obj.get("y",0)})
		var tw := float(current.get("tile_width",24))
		var th := float(current.get("tile_height",24))
		canvas.configure(layers, Vector2(current.get("pixel_width",1536),current.get("pixel_height",1536)),Vector2(probe.x*tw,probe.y*th),1.0)
		info.text = "KR1.25 native MAP %s · 저장격자 %s×%s · 1998~2001 지형일치 미확정 · 출구/도시귀환 미확정" % [current.get("native_id"),current.get("grid_width"),current.get("grid_height")]
	elif mode == 1:
		layers = _character_layers()
		canvas.configure(layers, Vector2(512,512),Vector2(256,250),3.0)
		info.text = "KR4.91 원본 부품 · 방향/동작은 시각추론 · 검수속도 130ms/프레임(원작시간 아님)"
	elif mode == 2:
		var back: Array = []
		var front: Array = []
		effect_drawn_paths.clear()
		for key in ["back_frames", "front_frames"]:
			var sequence: Array = current.get(key, [])
			if sequence.is_empty():
				continue
			var frame_index := _effect_index(sequence)
			if frame_index < 0:
				continue
			var frame: Dictionary = sequence[frame_index]
			if frame.get("sentinel", true):
				content.errors.append("UNSUPPORTED_SENTINEL_SELECTED")
				continue
			var img: Variant = frame.get("image")
			if typeof(img) != TYPE_DICTIONARY or img.is_empty():
				continue
			var off: Array = img.get("offset", [0,0])
			var layer := {"path":_asset(str(img.get("path","")),"kr491"), "x":256+float(off[0]), "y":256+float(off[1])}
			effect_drawn_paths.append(layer.path)
			if key == "back_frames": back.append(layer)
			else: front.append(layer)
		layers = back + _character_layers() + front
		canvas.configure(layers, Vector2(512,512),Vector2(256,250),2.0)
		info.text = "Effect %s 프레임검수 · Delay/Alpha/Light/반복/기술명중/소리ID 미확정 · 전투기술 아님" % current.get("id")
	elif mode == 3:
		var img: Variant = current.get("image",{})
		if typeof(img) == TYPE_DICTIONARY and not img.is_empty():
			layers.append({"path":_asset(str(img.get("path","")),"kr491"), "x":0,"y":0})
			var extent: Array = img.get("size",[640,480])
			canvas.configure(layers,Vector2(extent[0],extent[1]),Vector2(extent[0],extent[1])*0.5,minf(canvas.size.x/float(extent[0]),canvas.size.y/float(extent[1])))
		info.text = "원본 생성UI %s · 정상 해독 프레임만 · 원본 마스크 3개 실패 보존 · 한국 IME/선택순서 미확정" % current.get("name")
	preview.configure(_character_layers(),Vector2(512,512),Vector2(256,250),2.0)
	panel_labels[0].text = "물품\n원본 이름↔아이콘 대응은 미확정\n다른 아이콘으로 대체하지 않음"
	panel_labels[1].text = "기술\n평민 Lv1\n미학습 공격기술 0\n공격/시전 버튼은 원본 외형 검수"
	panel_labels[2].text = "장비 검수\n원본 부품 조합: %s\n장착: %s\n필드·미리보기: 같은 상태/합성기\n능력치/아이템 의미 미확정" % [variant_index,equipment_enabled]
	panel_labels[3].text = "능력치\n실제직업: 평민\n희망직업: 미선택\n레벨: 1\n외형검수가 능력치를 바꾸지 않음"

func _process(delta: float) -> void:
	if timers.size()<10000: timers.append(delta)
	if mode==2: effect_elapsed += delta
	elapsed += delta
	if capture != null and capture.get_frames_available()>0:
		var samples := capture.get_buffer(capture.get_frames_available())
		if audio_samples.size()<int(AudioServer.get_mix_rate()*4): audio_samples.append_array(samples)
		for sample in samples:
			audio_peak = maxf(audio_peak,maxf(absf(sample.x),absf(sample.y)))
	if elapsed >= 0.13:
		elapsed -= 0.13
		tick += 1
		if mode in [1,2]:
			_render()

func _effect_index(sequence: Array) -> int:
	var time_ms := effect_elapsed*1000.0
	for i in range(sequence.size()):
		var duration := float(sequence[i].get("inspection_duration_ms",0))
		if duration <= 0:
			content.errors.append("UNSUPPORTED_EFFECT_DELAY")
			return -1
		if time_ms < duration: return i
		time_ms -= duration
	return -1

func _save_audio() -> void:
	var bytes := PackedByteArray()
	bytes.resize(audio_samples.size()*4)
	for i in range(audio_samples.size()):
		bytes.encode_s16(i*4,int(clampf(audio_samples[i].x,-1.0,1.0)*32767.0))
		bytes.encode_s16(i*4+2,int(clampf(audio_samples[i].y,-1.0,1.0)*32767.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.stereo = true
	wav.mix_rate = int(AudioServer.get_mix_rate())
	wav.data = bytes
	var error := wav.save_to_wav(output+"-audio.wav")
	_check("captured_output_wav_written",error==OK,{"frames":audio_samples.size(),"result":error})

func _play_sound() -> void:
	var sounds: Array = content.kr491.get("sounds", [])
	if sounds.is_empty():
		return
	var entry: Dictionary = sounds[selection % sounds.size()]
	audio_samples.clear()
	audio_peak = 0.0
	capture.clear_buffer()
	player.stream = content.sound(_asset(str(entry.get("path","")),"kr491"))
	player.play()
	_log("original_wav_preview", {"member":entry.get("member"), "effect_binding":"UNKNOWN", "play_call_us":Time.get_ticks_usec()-start_us})

func _capture(suffix: String) -> void:
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		var target := output+suffix+".png"
		get_viewport().get_texture().get_image().save_png(target)
		_log("screenshot", {"path":target.get_file(),"drawn":canvas.last_drawn})

func _run_original_smoke() -> void:
	await get_tree().process_frame
	output = OS.get_environment("BARAM_P2_REPORT")
	if output.is_empty(): output = "user://work-original-smoke.json"
	_check("frozen_original_generation_loaded",content.errors.is_empty(),content.errors)
	_check("nonempty_original_maps",not content.maps.get("maps",[]).is_empty())
	_check("original_character_variants",content.kr491.get("character_variants",[]).size()>=2)
	_check("effect128_records_present",content.kr491.get("effects",[]).size()==128)
	var safe_effects: Array = content.kr491.get("effects",[]).filter(func(e: Dictionary) -> bool: return e.get("preview_supported",false))
	var safe_contract := not safe_effects.is_empty()
	for e in safe_effects:
		if not e.get("unsupported_commands",[]).is_empty(): safe_contract=false
		for f in e.get("front_frames",[])+e.get("back_frames",[]):
			if f.get("sentinel",true) or typeof(f.get("image"))!=TYPE_DICTIONARY: safe_contract=false
	_check("unsupported_effects_not_silently_selected",safe_contract,{"safe_slideshows":safe_effects.size(),"full_effect_semantics":"BLOCKED_UNKNOWN"})
	if not content.errors.is_empty() or content.maps.get("maps",[]).is_empty() or content.kr491.get("character_variants",[]).is_empty():
		_finish_original_smoke()
		return
	_check("wav163_present",content.kr491.get("sounds",[]).size()==163)
	var policy_ids: Array = []
	var policy_ok := true
	for guard in content.policy.get("observations",[]):
		if guard.get("P2_selection","")!="INSPECTION_GUARD": continue
		policy_ids.append(guard.candidate_id)
		var value: Dictionary = guard.get("candidate_value",{})
		if guard.candidate_id=="WD-MS-001":
			policy_ok = policy_ok and value.get("client_delay_unit","")=="UNKNOWN"
		if guard.candidate_id=="WD-MN-001":
			policy_ok = policy_ok and value.get("no_global_profile_selection",false) and content.manifest.get("historical_profile_default")==null
	_check("work_batch_guard_policy_consumed",policy_ok and policy_ids.size()==6,{"candidate_ids":policy_ids,"global_timing_or_map_adoption":false})
	_log("work_batch_policy_enforced",{"guards":policy_ids,"historical_timing":"UNKNOWN","map_profile_default":null})
	_run_map_checks()
	_run_original_save()
	await get_tree().create_timer(0.4).timeout
	await _capture("-map")
	for m in range(1,content.maps.maps.size()):
		_select_item(m)
		await get_tree().create_timer(0.15).timeout
		await _capture("-map-"+str(m))
	_select_mode(1)
	for a in ["standing","walking","attack","casting"]:
		_set_action(a)
		for d in range(4):
			_set_direction(d)
			await get_tree().create_timer(0.25).timeout
			var expected_count := 2 if a=="casting" else 4
			_check("original_parts_"+a+"_"+str(d),canvas.last_drawn.size()==expected_count and canvas.last_drawn==preview.last_drawn,{"drawn":canvas.last_drawn,"preview":preview.last_drawn,"expected_parts":expected_count,"historical_direction":"VISUALLY_INFERRED"})
			if a=="standing": await _capture("-character-"+str(d))
	_set_action("standing")
	var before: Array = _character_layers()
	_swap_equipment()
	_check("equipment_swap_changes_original_parts",before!=_character_layers())
	await get_tree().create_timer(0.2).timeout
	await _capture("-equipment-swap")
	_toggle_equipment()
	_check("equipment_unequip_hides_actual_weapon",_character_layers().size()==2)
	await _capture("-equipment-off")
	_toggle_equipment()
	_select_mode(2)
	await get_tree().create_timer(0.5).timeout
	await _capture("-effect")
	_check("safe_effect_actual_frame_observed",not effect_drawn_paths.is_empty(),effect_drawn_paths)
	await get_tree().create_timer(1.2).timeout
	_check("oneshot_effect_finishes_without_residue",effect_drawn_paths.is_empty())
	_select_item(0)
	await get_tree().create_timer(0.2).timeout
	_select_mode(0)
	_check("mode_change_cancels_effect_and_audio",not player.playing)
	_select_mode(2)
	_play_sound()
	await get_tree().create_timer(1.2).timeout
	_check("original_wav_decoded",player.stream!=null)
	_check("audio_mix_nonzero",audio_peak>0.0001,{"peak":audio_peak,"hardware_listening":"NOT_RUN"})
	_save_audio()
	_select_mode(3)
	await get_tree().create_timer(0.3).timeout
	await _capture("-creation")
	_check("no_selected_asset_decode_errors",content.errors.is_empty(),content.errors)
	_finish_original_smoke()

func _finish_original_smoke() -> void:
	var result := {"schema":"baram.work.p2.original-smoke/1","platform":OS.get_name(),"engine":Engine.get_version_info().string,"generation":content.manifest.get("generation"),"checks":checks,"events":events,"consumed_files":content.consumed.keys(),"source_frames":source_frame_paths,"audio_mix_peak":audio_peak,"audio_captured_frames":audio_samples.size(),"map_runtime_test":map_tests,"save_original_id_test":save_result,"historical_timing":"UNKNOWN","hardware_listening":"NOT_RUN","IME":"NOT_RUN","authentication":"BLOCKED_ENVIRONMENT","originality":"Original bitmaps; motion meanings visually inferred; no target-era map equivalence claim"}
	var file := FileAccess.open(output,FileAccess.WRITE)
	if file==null:
		get_tree().quit(2)
		return
	file.store_string(JSON.stringify(result,"  ")+"\n")
	file.close()
	var failures := checks.filter(func(c: Dictionary) -> bool: return c.status=="FAIL")
	print("P2_WORK_ORIGINAL checks=%s failures=%s" % [checks.size(),failures.size()])
	get_tree().quit(0 if failures.is_empty() else 1)

func _can_step(map: Dictionary, from: Vector2i, name: String) -> bool:
	var rules: Dictionary = map.get("collisions", {})
	if rules.get("status", "") != "STATIC_EXE_DERIVED": return false
	var rule: Dictionary = rules.get("direction_bits", {}).get(name, {})
	if rule.is_empty(): return false
	var target := from+Vector2i(int(rule.dx),int(rule.dy))
	var width := int(map.grid_width)
	var height := int(map.grid_height)
	if from.x<0 or from.y<0 or from.x>=width or from.y>=height or target.x<0 or target.y<0 or target.x>=width or target.y>=height: return false
	var src := from.y*width+from.x
	var dst := target.y*width+target.x
	var ground: Array = rules.ground_ids
	var masks: Array = rules.edge_masks
	return not ((int(masks[src]) & int(rule.source_edge_bit))!=0 or (int(masks[dst]) & int(rule.target_edge_bit))!=0 or (int(ground[dst])>=1024 and int(ground[dst])<2048))

func _run_map_checks() -> void:
	for map in content.maps.get("maps",[]):
		var outcomes := {"allowed":0,"blocked":0}
		for y in range(int(map.grid_height)):
			for x in range(int(map.grid_width)):
				for d in ["north","east","south","west"]:
					var ok := _can_step(map,Vector2i(x,y),d)
					outcomes["allowed" if ok else "blocked"] += 1
		map_tests.append({"native_map_id":map.native_id,"scope":"Godot native MAP storage grid probe using independently disassembled EXE rules; active server dimensions unknown","outcomes":outcomes,"historical_exits":"BLOCKED_UNRESOLVED","historical_returns":"BLOCKED_UNRESOLVED"})
		_check("map_"+str(map.native_id)+"_both_free_and_blocked_steps",outcomes.allowed>0 and outcomes.blocked>0,outcomes)
		_check("map_"+str(map.native_id)+"_bounds_rejected",not _can_step(map,Vector2i(0,0),"north") and not _can_step(map,Vector2i(0,0),"west"))
		_check("map_"+str(map.native_id)+"_no_fabricated_exits",map.get("exits",{}).get("status","")=="UNKNOWN" and map.get("exits",{}).get("items",[]).is_empty() and map.get("return_points",{}).get("status","")=="UNKNOWN" and map.get("return_points",{}).get("items",[]).is_empty())

func _run_original_save() -> void:
	var map: Dictionary = content.maps.maps[0]
	var map_id := "kr125:map-"+str(map.native_id)
	var version: String = map.source_map_sha256
	var owner := "local-account:work-p2-fixture"
	var manifest_sha: String = content.manifest.get("fingerprint","")
	var maps: Dictionary = {}
	maps[map_id] = {"version":version,"width":map.grid_width,"height":map.grid_height,"blocked":[]}
	save_catalog = {"profile":"work-p2-original-assets-inspection-only","manifest_sha256":manifest_sha,"maps":maps,"items":{"kr491:sword-0":{"slot":"weapon","meaning":"Original sprite ID only; game item binding UNKNOWN"},"kr491:body-0":{"slot":"armor","meaning":"Original sprite ID only; game item binding UNKNOWN"}},"skills":{}}
	# Controlled new fixture, not an old save or historical HP/item stat claim.
	test_save = {"meta":{"schema_id":Store.SCHEMA_ID,"schema_version":1,"content_profile":save_catalog.profile,"content_manifest_sha256":manifest_sha,"build_id":"work-p2-original-inspection","owner_id":owner,"character_id":"kr-inspection:001","revision":1},"payload":{"character":{"id":"kr-inspection:001","name":"원본검수","level":1,"hp":25,"hp_max":25,"position":{"map_id":map_id,"map_version":version,"x":probe.x,"y":probe.y}},"inventory":[{"instance_id":"inspect-instance:sword","item_id":"kr491:sword-0","quantity":1},{"instance_id":"inspect-instance:body","item_id":"kr491:body-0","quantity":1}],"equipment":{"weapon":"inspect-instance:sword","armor":"inspect-instance:body"},"skills":[],"loot":[{"loot_id":"inspect-loot:001","item_id":"kr491:sword-0","quantity":1,"position":{"map_id":map_id,"map_version":version,"x":probe.x,"y":probe.y}}]}}
	var store = Store.new()
	var run_id := str(OS.get_process_id())+"-"+Crypto.new().generate_random_bytes(8).hex_encode()
	test_save_path = ProjectSettings.globalize_path("user://original-inspection-fixtures/"+run_id+"/character.json")
	var written: Dictionary = store.write_state(test_save_path,test_save,owner,save_catalog)
	var loaded: Dictionary = store.read_one(test_save_path,owner,save_catalog)
	_check("original_native_ids_save_roundtrip",written.status=="SAVED" and loaded.status=="OK" and store.canonical(loaded.get("state",{}))==store.canonical(test_save))
	_check("unlearned_new_character_skills_empty",test_save.payload.skills.is_empty() and test_save.payload.character.level==1)
	var newer_catalog: Dictionary = save_catalog.duplicate(true)
	newer_catalog.maps[map_id].version = "inspection-map-version-only-change"
	var plan: Dictionary = store.plan_map_update(test_save,owner,save_catalog,newer_catalog)
	_check("map_version_only_keeps_character_and_loot_coordinates",plan.status=="READY" and plan.state.payload.character.position.x==probe.x and plan.state.payload.character.position.y==probe.y and plan.state.payload.loot[0].position.x==probe.x and plan.state.payload.loot[0].position.y==probe.y)
	var invalid_catalog: Dictionary = newer_catalog.duplicate(true)
	invalid_catalog.maps[map_id].width=1
	invalid_catalog.maps[map_id].height=1
	var deferred: Dictionary = store.plan_map_update(test_save,owner,save_catalog,invalid_catalog)
	_check("unmapped_coordinate_change_defers_and_preserves_source",deferred.status=="DEFERRED" and store.canonical(deferred.get("source",{}))==store.canonical(test_save))
	var old_bytes := FileAccess.get_file_as_bytes(test_save_path)
	test_save.meta.revision = 2
	_check("original_native_id_backup_created",store.write_state(test_save_path,test_save,owner,save_catalog).status=="SAVED" and FileAccess.get_file_as_bytes(test_save_path+".backup")==old_bytes)
	var result: Dictionary = store.read_one(test_save_path,owner,save_catalog)
	save_result = {"status":result.status,"path_kind":"NEW_ISOLATED_TEST_FIXTURE","schema":Store.SCHEMA_ID,"native_ids":[map_id,"kr491:sword-0","kr491:body-0"],"item_meanings":"UNKNOWN; asset IDs in controlled fixture","checksum":FileAccess.get_sha256(test_save_path),"revision":result.get("state",{}).get("meta",{}).get("revision"),"actual_user_save":"NOT_OPENED","authentication":"NOT_RUN"}
