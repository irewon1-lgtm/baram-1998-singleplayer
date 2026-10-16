extends "res://ui/original_inspection.gd"
## Additional source-bound inspection. No P3 world, transactions or learned skills.
const Effects = preload("res://render/effect_preview.gd")
const Rules = preload("res://content/priority_rules.gd")
var contracts = Rules.new()
var icons: Array = []
var rules: Dictionary = {}
var sound_selector: OptionButton
var sound_filter: LineEdit
var sound_selection := 0
var selected_icon: Dictionary = {}
var effect_scope := ""
var priority_ready := false

func _ready() -> void:
	super._ready()
	if content.priority.is_empty(): return
	var icon_index: Dictionary = content.read_json(str(content.priority.get("icons", "")))
	icons = icon_index.get("entries", [])
	rules = content.read_json(str(content.priority.get("rules", "")))
	if not contracts.open_rules(runtime_path.path_join(str(content.priority.get("rules", "")))):
		content.errors.append("PRIORITY_RULE_CONTRACT_LOAD")
	for title in ["공식 물품 아이콘", "직업별 학습 조건", "NPC별 서비스·재고"]:
		mode_selector.add_item(title)
	var row := HBoxContainer.new()
	var box: VBoxContainer = mode_selector.get_parent().get_parent()
	box.add_child(row)
	box.move_child(row, 2)
	sound_filter = LineEdit.new()
	sound_filter.placeholder_text = "WAV ID 검색 (효과번호와 독립)"
	sound_filter.custom_minimum_size.x = 250
	sound_filter.text_changed.connect(_filter_sounds)
	row.add_child(sound_filter)
	sound_selector = OptionButton.new()
	sound_selector.item_selected.connect(_select_sound)
	row.add_child(sound_selector)
	var stop := Button.new()
	stop.text = "소리 중지"
	stop.pressed.connect(func() -> void: player.stop())
	row.add_child(stop)
	var equip := Button.new()
	equip.text = "현재 물품을 검수 장비로 선택"
	equip.pressed.connect(_select_inspection_item)
	row.add_child(equip)
	_filter_sounds("")
	priority_ready = true
	_select_mode(0)
	if "--p2-priority-smoke" in OS.get_cmdline_user_args():
		_run_priority_smoke.call_deferred()

func _list() -> Array:
	if mode == 0:
		var result: Array = content.maps.get("maps", [])
		if not result.is_empty(): content.map_at(selection % result.size())
		return result
	if mode == 2 and not content.priority.is_empty(): return content.kr491.get("effects", [])
	if mode == 4: return icons
	if mode == 5: return rules.get("skills", [])
	if mode == 6: return rules.get("npcs", [])
	return super._list()

func _select_mode(index: int) -> void:
	super._select_mode(index)
	for i in range(_list().size()):
		var entry: Dictionary = _list()[i]
		selector.set_item_text(i, str(entry.get("inspection_id", entry.get("name_ko", entry.get("name", entry.get("native_id", entry.get("id", "?")))))))

func _center_map() -> void:
	if mode != 0 or _list().is_empty(): return
	var current: Dictionary = content.map_at(selection % _list().size())
	var bounds: Variant = current.get("occupied_ground_bounds")
	probe = Vector2i(32,32)
	if typeof(bounds) == TYPE_ARRAY and bounds.size() == 4:
		probe = Vector2i(int((bounds[0]+bounds[2])/2),int((bounds[1]+bounds[3])/2))

func _filter_sounds(query: String) -> void:
	sound_selector.clear()
	var all_sounds: Array = content.kr491.get("sounds", [])
	for i in range(all_sounds.size()):
		var entry: Dictionary = all_sounds[i]
		var label := str(entry.get("member", entry.get("id", i)))
		if query.is_empty() or query.to_lower() in label.to_lower():
			sound_selector.add_item(label)
			sound_selector.set_item_metadata(sound_selector.item_count - 1, i)
	if sound_selector.item_count > 0: _select_sound(0)

func _select_sound(index: int) -> void:
	sound_selection = int(sound_selector.get_item_metadata(index))
	if player != null: player.stop()

func _play_sound() -> void:
	var all_sounds: Array = content.kr491.get("sounds", [])
	if all_sounds.is_empty() or sound_selection < 0 or sound_selection >= all_sounds.size(): return
	var entry: Dictionary = all_sounds[sound_selection]
	audio_samples.clear()
	audio_peak = 0.0
	capture.clear_buffer()
	player.stream = content.sound(_asset(str(entry.get("path", "")), "kr491"))
	if player.stream == null: return
	player.play()
	_log("priority_wav_preview", {"sound_index":sound_selection,"member":entry.get("member"),"effect_binding":"UNKNOWN"})

func _select_inspection_item() -> void:
	if mode != 4 or icons.is_empty(): return
	var entry: Dictionary = icons[selection % icons.size()]
	if not entry.get("working_profile_eligible", false): return
	selected_icon = entry
	state.equipment["inspection_item_id"] = entry.item_id
	_log("priority_item_selected", {"item_id":entry.item_id,"icon_id":entry.id,"sprite_binding":"UNKNOWN"})
	_render()

func _render() -> void:
	if canvas == null: return
	if mode == 2 and not content.priority.is_empty():
		var entries: Array = _list()
		if entries.is_empty(): return
		var current: Dictionary = entries[selection % entries.size()]
		var frame: Dictionary = Effects.layers(current, effect_elapsed)
		effect_drawn_paths.assign(frame.paths)
		effect_scope = str(frame.scope)
		canvas.configure(frame.back + _character_layers() + frame.front, Vector2(512,512), Vector2(256,250),2.0)
		preview.configure(_character_layers(),Vector2(512,512),Vector2(256,250),2.0)
		info.text = "Effect %s · %s · Light 끔/Alpha 일반 합성·한 번 재생 · 원작 기술·음향·시간 대응 미확정" % [current.id,frame.scope]
		if frame.scope == "BLOCKED": info.text += " · " + str(frame.errors)
	elif mode == 4:
		var entry: Dictionary = icons[selection % icons.size()] if not icons.is_empty() else {}
		var layers: Array = []
		if not entry.is_empty():
			var path := "icons/" + str(entry.image_path)
			# One source ID feeds field, inventory and equipment-thumbnail inspection.
			for point in [Vector2(100,180),Vector2(240,180),Vector2(380,180)]:
				layers.append({"path":path,"x":point.x,"y":point.y,"scale":2.0})
		canvas.configure(layers,Vector2(512,512),Vector2(256,220),1.1)
		if not selected_icon.is_empty():
			preview.configure([{"path":"icons/"+str(selected_icon.image_path),"x":240,"y":240,"scale":3.0}],Vector2(512,512),Vector2(256,250),1.0)
		info.text = "%s · %s · 세 위치는 같은 공식 문서 이미지 ID · 착용 스프라이트 대응 미확정" % [entry.get("name_ko",""),entry.get("fact_status","")]
	elif mode in [5,6]:
		var entries: Array = _list()
		var current: Dictionary = entries[selection % entries.size()] if not entries.is_empty() else {}
		canvas.configure([],Vector2(512,512),Vector2(256,250),1.0)
		var contract: Dictionary = contracts.learning_contract(str(current.get("id","")), str(state.character.actual_job),int(state.character.level)) if mode == 5 else contracts.npc_contract(str(current.get("id","")))
		info.text = "%s\n%s\n현재 검수 상태의 조건: %s\n2001 공식 가이드 작업용 프로필 · 실제 전투/거래/배치는 P3 미구현" % [current.get("name",""),JSON.stringify(current.get("value",{})),JSON.stringify(contract)]
	else:
		super._render()
	if priority_ready:
		panel_labels[0].text = "물품 · 공식 원본 이미지\n대응 후보 %s / 2001 작업용 %s\n아이템 선택은 검수 상태에만 적용" % [icons.size(),icons.filter(func(e: Dictionary) -> bool: return e.get("working_profile_eligible",false)).size()]
		panel_labels[1].text = "기술 · 2001 가이드 %s행\n직업별 학습 조건은 별도 규칙으로 검수\n평민 Lv1 미학습 상태 유지" % rules.get("skills",[]).size()
		panel_labels[2].text = "검수 장비 ID: %s\n원본 몸/무기 합성과 아이템 썸네일은 대응 미확정\n%s" % [selected_icon.get("item_id","미선택"),JSON.stringify(selected_icon.get("stats",{}))]
		panel_labels[3].text = "평민 Lv1 · 미학습\n선택 장비와 같은 item_id: %s\n표시 수치: %s" % [selected_icon.get("item_id","미선택"),JSON.stringify(selected_icon.get("stats",{}))]

func _run_priority_smoke() -> void:
	await get_tree().process_frame
	output = OS.get_environment("BARAM_P2_REPORT")
	if output.is_empty(): output = "user://priority-smoke.json"
	_check("priority_generation_loaded",content.errors.is_empty(),content.errors)
	_check("independent_wav_selector_163",sound_selector.item_count == 163)
	_filter_sounds("412")
	_check("sound_id_search",sound_selector.item_count > 0)
	_filter_sounds("")
	# Load every WAV ID using the real Godot decoder. Playback/output is sampled below.
	for i in range(content.kr491.sounds.size()):
		var entry: Dictionary = content.kr491.sounds[i]
		var stream: AudioStream = content.sound(_asset(str(entry.path),"kr491"))
		_check("wav_decode_"+str(i),stream != null and stream.get_length() > 0,entry.get("member"))
	for i in [0,81,162]:
		sound_selection = i
		_play_sound()
		await get_tree().create_timer(0.25).timeout
		_check("wav_mix_"+str(i),audio_peak > 0.0001,{"peak":audio_peak,"hardware_listening":"NOT_RUN"})
		player.stop()
	_select_mode(2)
	for id in [0,1,70,72,91,127]:
		_select_item(id)
		effect_elapsed = 0.0
		_render()
		await get_tree().create_timer(0.04).timeout
		_check("effect_render_"+str(id),not effect_drawn_paths.is_empty() if id != 72 else effect_scope == "BLOCKED",{"scope":effect_scope,"paths":effect_drawn_paths})
		await _capture("-effect-"+str(id))
		effect_elapsed = 10.1
		_render()
		_check("effect_finished_"+str(id),effect_drawn_paths.is_empty())
	_select_mode(4)
	for i in range(icons.size()):
		_select_item(i)
		await get_tree().process_frame
		_check("icon_render_"+str(icons[i].id),canvas.last_drawn.size() == 3,{"item_id":icons[i].item_id,"drawn":canvas.last_drawn})
	_select_item(0)
	_select_inspection_item()
	await get_tree().process_frame
	_check("same_item_state_equipment_stats",not selected_icon.is_empty() and state.equipment.get("inspection_item_id") == selected_icon.get("item_id"))
	await _capture("-items")
	_select_mode(5)
	await get_tree().process_frame
	_check("skills_bound",_list().size() == 188)
	await _capture("-skills")
	_select_mode(6)
	await get_tree().process_frame
	_check("npcs_bound_distinct_stocks",_list().size() == 22)
	await _capture("-npcs")
	_select_mode(0)
	for i in [0, 15, 48, min(54,_list().size()-1),_list().size()-1]:
		_select_item(i)
		await get_tree().create_timer(0.1).timeout
		_check("map_render_"+str(i),not canvas.last_drawn.is_empty(),_list()[i].get("inspection_id"))
		await _capture("-map-"+str(i))
	_run_original_save()
	_check("all_consumed_assets_decode",content.errors.is_empty(),content.errors)
	_finish_original_smoke()
