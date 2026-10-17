extends SceneTree
## Regression fixtures for observed B5 UI/save failures. Full G1 production UI
## is loaded; placement, money and failure phases are explicit test fixtures.
## Input.parse_input_event is Godot GUI injection, NOT human/OS/device input.
const ClassicList = preload("res://ui/classic_list.gd")
var app
var checks: Array = []
var failures := 0
var output := ""
var source_before: Dictionary = {}
var native_actions := 0
var world_taps := 0
var row_selections := 0
var source_files := ["ui/gameplay.gd","storage/gameplay_store.gd","state/gameplay_state.gd","input/touch_stick.gd","ui/classic_list.gd","storage/sequential_sync.gd"]

func check(id: String, passed: bool, detail: Variant = null, scope: String = "PRODUCTION_METHOD_EXPLICIT_FIXTURE") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","scope":scope,"detail":detail})
	if not passed: failures += 1

func fingerprints() -> Dictionary:
	var hashes: Dictionary = {}
	for path in source_files: hashes[path] = FileAccess.get_sha256("res://" + path)
	return hashes

func _initialize() -> void:
	output = OS.get_environment("BARAM_UI_INTEGRITY_OUT")
	var isolated := OS.get_environment("BARAM_UI_INTEGRITY_ISOLATED_ROOT")
	if output.is_empty() or isolated.is_empty() or not OS.get_user_data_dir().begins_with(isolated):
		push_error("Set an isolated XDG_DATA_HOME and matching BARAM_UI_INTEGRITY_ISOLATED_ROOT; existing user saves are never read.")
		quit(2)
		return
	DirAccess.make_dir_recursive_absolute(output)
	source_before = fingerprints()
	run.call_deferred()

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await process_frame
	await RenderingServer.frame_post_draw
	var frame := root.get_texture().get_image()
	if frame != null and not frame.is_empty(): frame.save_png(output.path_join(name + ".png"))

func touch(pressed: bool, at: Vector2, canceled: bool = false) -> void:
	var event := InputEventScreenTouch.new()
	event.index = 0
	event.position = at
	event.pressed = pressed
	event.canceled = canceled
	Input.parse_input_event(event)

func drag(at: Vector2, relative: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = 0
	event.position = at
	event.relative = relative
	event.velocity = relative * 12.0
	Input.parse_input_event(event)

func tap(at: Vector2, canceled: bool = false) -> void:
	touch(true, at)
	await process_frame
	touch(false, at, canceled)
	await process_frame

func first_row(parent: Node) -> Button:
	for child in parent.get_children():
		if child is Button and not child.disabled: return child
	return null

func near(npc: Dictionary) -> bool:
	for direction in [Vector2i.DOWN,Vector2i.UP,Vector2i.LEFT,Vector2i.RIGHT]:
		var x: int = int(npc.x) + direction.x
		var y: int = int(npc.y) + direction.y
		if app.game.valid_position(str(npc.map_id), x, y) and not app.game._occupied(str(npc.map_id), x, y):
			app.game.state.character.map_id = npc.map_id
			app.game.state.character.x = x
			app.game.state.character.y = y
			return true
	return false

func durable_equals_memory() -> bool:
	var loaded: Dictionary = app.store.read_game(app.save_path, app.OWNER, app.save_definitions)
	return loaded.has("payload") and app.store._canonical(loaded.payload) == app.store._canonical(app.game.state)

func modal_closed_without_motion(before_position: Vector2i) -> bool:
	var character: Dictionary = app.game.state.character
	return not app.dialogue.visible and not app.modal_shield.visible and app.path.is_empty() and app.arrival_action.is_empty() and app.movement == Vector2i.ZERO and Vector2i(character.x, character.y) == before_position

func run() -> void:
	root.size = Vector2i(1100,720)
	app = load("res://gameplay.tscn").instantiate()
	root.add_child(app)
	await process_frame
	await process_frame
	app.smoke = true
	app.set_process(false) # No natural play, AI tick or hidden growth in fixtures.
	check("full_G1_production_scene_load", app.startup_error.is_empty(), app.startup_error)
	if not app.startup_error.is_empty(): finish(); return
	check("full_G1_not_reduced_for_test", app.content.data.maps.size() == 76 and app.content.data.items.size() == 593 and app.content.data.skills.size() == 190, {"maps":app.content.data.maps.size(),"items":app.content.data.items.size(),"skills":app.content.data.skills.size()})
	await capture("01-menu")
	var suffix := str(Time.get_ticks_usec() % 1000000)
	app._show_creation()
	app.name_input.text = "검증가" + suffix
	app._create_character()
	check("first_character_immediately_has_verified_save", FileAccess.file_exists(app.save_path) and durable_equals_memory())
	var first_path: String = app.save_path
	var first_revision: int = int(app.game.state.revision)
	app._return_menu()
	app._show_creation()
	app.name_input.text = "검증나" + suffix
	app._create_character()
	check("same_revision_new_character_has_distinct_saved_file", app.save_path != first_path and int(app.game.state.revision) == first_revision and FileAccess.file_exists(app.save_path) and durable_equals_memory(), {"first_path":first_path,"second_path":app.save_path,"revision":app.game.state.revision})
	# A committed rename with lost acknowledgement must preserve the newly
	# equipped state in both memory and disk, not roll one side back.
	var weapon := ""
	for instance in app.game.state.inventory:
		if app.content.data.items[instance.item_id].get("slot", "") == "weapon": weapon = str(instance.instance_id); break
	check("starter_weapon_for_actual_equip_command", not weapon.is_empty())
	if not weapon.is_empty():
		var already_equipped: bool = app.game.state.equipment.get("weapon") == weapon
		var mutation := {"type":"unequip","slot":"weapon"} if already_equipped else {"type":"equip","instance_id":weapon}
		app.store.fault_phase = "after_primary_replace"
		var equip: Dictionary = app._dispatch(mutation)
		check("committed_ack_lost_confirmed_without_old_state_rollback", equip.status == "OK" and not app.save_failure and app.last_save_committed and (app.game.state.equipment.get("weapon") == weapon) != already_equipped and durable_equals_memory(), {"command_status":equip.status,"receipt":app.save_receipts[-1]})
		var committed: String = app.store._canonical(app.game.state)
		app.store.fault_phase = "before_primary_replace"
		var opposite := {"type":"equip","instance_id":weapon} if already_equipped else {"type":"unequip","slot":"weapon"}
		var unequip: Dictionary = app._dispatch(opposite)
		check("precommit_failure_retains_original_memory_and_disk", unequip.status == "SAVE_FAILED" and not app.last_save_committed and committed == app.store._canonical(app.game.state) and durable_equals_memory(), {"command_status":unequip.status,"receipt":app.save_receipts[-1]})
		app.store.fault_phase = ""
		app.save_failure = false
		app.message.text = "명시적 저장 장애 회귀시험 후 정상 저장·상점 입력을 검사합니다."
	# Make an affordable trade fixture near the actual longest-stock G1 NPC.
	var npc_id := ""
	var largest := -1
	for id in app.content.data.npcs:
		var count := 0
		for trade in app.content.data.npcs[id].get("shop", {}).values():
			if trade.get("buy_price") != null: count += 1
		if count > largest: largest = count; npc_id = str(id)
	check("real_shop_fixture_has_accessible_neighbour", not npc_id.is_empty() and near(app.content.data.npcs[npc_id]), npc_id)
	app.game.state.character.money = 1000000
	app.game.state.revision += 1
	check("shop_fixture_saved_before_GUI_input", app._save())
	app._render_world()
	app._show_dialogue(npc_id)
	await process_frame
	await process_frame
	await capture("02-real-shop-before-drag")
	Input.set_emulate_mouse_from_touch(true)
	Input.set_emulate_touch_from_mouse(true)
	var row := first_row(app.dialogue_body)
	check("real_shop_has_visible_production_row", row != null)
	if row != null:
		var before: String = app.store._canonical(app.game.state)
		var at := row.get_global_rect().position + Vector2(row.size.x * 0.5, minf(22.0, row.size.y * 0.5))
		touch(true, at); await process_frame
		drag(at - Vector2(0,15), Vector2(0,-15)); await process_frame
		touch(false, at - Vector2(0,15)); await process_frame
		check("real_shop_row_drag_scrolls_without_purchase", app.dialogue_scroll.scroll_vertical > 0 and before == app.store._canonical(app.game.state), {"scroll_y":app.dialogue_scroll.scroll_vertical,"row_filter":row.mouse_filter}, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
		app.dialogue_scroll.scroll_vertical = 0
		await process_frame
		row = first_row(app.dialogue_body)
		var selected: Dictionary = app.dialogue_rows[0].command
		var price: int = int(app.content.data.npcs[npc_id].shop[selected.item_id].buy_price) if selected.type == "buy" else -1
		var prior_revision: int = int(app.game.state.revision)
		var money: int = int(app.game.state.character.money)
		at = row.get_global_rect().get_center()
		print("UI_INTEGRITY_EVENT real_shop_single_tap_begin")
		await tap(at)
		print("UI_INTEGRITY_EVENT real_shop_single_tap_end")
		check("real_shop_single_tap_executes_exactly_one_transaction", price >= 0 and int(app.game.state.revision) == prior_revision + 1 and int(app.game.state.character.money) == money - price and durable_equals_memory(), {"revision_delta":int(app.game.state.revision)-prior_revision,"money_delta":money-int(app.game.state.character.money)}, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
	await capture("03-shop-after-one-purchase")
	# Cancellation must not activate the fixed close button or start field paths.
	var close_x: Button = app.dialogue.find_child("CloseX", true, false)
	var position := Vector2i(app.game.state.character.x, app.game.state.character.y)
	await tap(close_x.get_global_rect().get_center(), true)
	check("canceled_native_close_touch_keeps_modal_open", app.dialogue.visible and app.modal_shield.visible, null, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
	var close_at := close_x.get_global_rect().get_center()
	await tap(close_at)
	check("fixed_X_closes_and_clears_motion", modal_closed_without_motion(position), null, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
	for pressed in [true,false]:
		var emulated := InputEventMouseButton.new()
		emulated.device = InputEvent.DEVICE_ID_EMULATION
		emulated.position = close_at
		emulated.button_index = MOUSE_BUTTON_LEFT
		emulated.pressed = pressed
		Input.parse_input_event(emulated)
	check("close_emulated_mouse_cannot_leak_to_field", modal_closed_without_motion(position), null, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
	app._show_dialogue(npc_id)
	var escape := InputEventKey.new()
	escape.physical_keycode = KEY_ESCAPE
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	Input.parse_input_event(escape)
	await process_frame
	check("Escape_closes_modal_without_field_action", modal_closed_without_motion(position), null, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
	app._show_dialogue(npc_id)
	app._notification(Node.NOTIFICATION_WM_GO_BACK_REQUEST)
	check("back_notification_closes_modal_first", modal_closed_without_motion(position), null, "PRODUCTION_NOTIFICATION_CALLBACK_NOT_ANDROID_OS")
	app._show_dialogue(npc_id)
	app._refresh_open_dialogue.call_deferred(npc_id, app.dialogue_page, true)
	app._close_dialogue()
	await process_frame
	check("queued_refresh_after_close_cannot_reopen_modal", modal_closed_without_motion(position), null, "PRODUCTION_METHOD_EXPLICIT_DEFERRED_REFRESH_FIXTURE")
	app.stick.tapped.connect(func(_point): world_taps += 1)
	await process_frame
	await tap(app.stick.get_global_rect().get_center(), true)
	check("canceled_field_touch_never_becomes_world_tap", world_taps == 0 and app.stick.finger == -1 and app.path.is_empty(), {"world_taps":world_taps}, "PRODUCTION_G1_UI_GODOT_SYNTHETIC_INPUT")
	app._show_map()
	await process_frame
	var overview: Control
	for child in app.dialogue_body.get_children():
		if child.get_script() == load("res://render/original_view.gd"): overview = child; break
	check("map_overview_passes_scroll_input", overview != null and overview.mouse_filter == Control.MOUSE_FILTER_IGNORE)
	await capture("04-fixed-map-modal")
	app._close_dialogue()
	# Production ClassicList in a minimal control fixture isolates selection from
	# scroll cancellation. No fake inventory item is added to gameplay state.
	var fixture_screen := Control.new()
	fixture_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(fixture_screen)
	var classic := ClassicList.new()
	fixture_screen.add_child(classic)
	classic.position = Vector2(200,150)
	classic.size = Vector2(300,300)
	for index in range(25): classic.add_item("스크롤 취소 검증 " + str(index))
	classic.item_selected.connect(func(_index): row_selections += 1)
	await process_frame
	await process_frame
	var first: Button = classic.rows.get_child(0)
	var point := first.get_global_rect().get_center()
	touch(true, point); await process_frame
	drag(point - Vector2(0,15), Vector2(0,-15)); await process_frame
	touch(false, point - Vector2(0,15)); await process_frame
	check("ClassicList_drag_scrolls_without_selecting", classic.scroll_vertical > 0 and row_selections == 0, {"scroll_y":classic.scroll_vertical,"selections":row_selections}, "PRODUCTION_CONTROL_FIXTURE_GODOT_SYNTHETIC_INPUT")
	fixture_screen.queue_free()
	await process_frame
	# Logical layout evidence only. Actual Android keyboard composition, notch,
	# rotation and native Windows presentation remain separate NOT_RUN gates.
	root.size = Vector2i(2400,1080)
	await process_frame
	await process_frame
	check("scaled_window_uses_logical_1600x720_canvas", root.content_scale_size == Vector2i(1600,720), {"physical":str(root.size),"logical":str(root.content_scale_size)}, "LOGICAL_LAYOUT_ONLY_NO_ANDROID_IME_CLAIM")
	app._show_dialogue(npc_id)
	await process_frame
	var canvas := Rect2(Vector2.ZERO, app.size)
	check("scaled_modal_fixed_close_buttons_inside_canvas", canvas.encloses(close_x.get_global_rect()) and canvas.encloses(app.dialogue_close.get_global_rect()), {"canvas":str(canvas),"X":str(close_x.get_global_rect()),"footer":str(app.dialogue_close.get_global_rect())}, "LOGICAL_LAYOUT_ONLY_NO_ANDROID_IME_CLAIM")
	await capture("05-scaled-modal")
	finish()

func finish() -> void:
	var after := fingerprints()
	check("production_source_unchanged_during_test", source_before == after)
	var runtime := OS.get_environment("BARAM_GAMEPLAY_RUNTIME")
	var report := {"schema":"baram.b5.ui-integrity-regression/1","status":"PASS" if failures == 0 else "FAIL","failures":failures,"checks":checks,"source_sha256":after,"runtime_root":runtime,"runtime_manifest_sha256":FileAccess.get_sha256(runtime.path_join("runtime.json")),"gameplay_content_sha256":FileAccess.get_sha256(runtime.path_join("gameplay_content.json")),"engine":Engine.get_version_info(),"os":OS.get_name(),"display":DisplayServer.get_name(),"user_data":OS.get_user_data_dir(),"limits":{"normal_human_play":"NOT_RUN","OS_input":"NOT_RUN","native_Android_Windows":"NOT_RUN","actual_Korean_IME_and_keyboard":"NOT_RUN","external_account_sync":"NOT_RUN"}}
	var file := FileAccess.open(output.path_join("ui-integrity.json"), FileAccess.WRITE)
	if file: file.store_string(JSON.stringify(report, "\t")); file.close()
	print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size(),"output":output,"scope":"PRODUCTION_UI_AND_EXPLICIT_FIXTURES_GODOT_INPUT_NO_NATIVE_PLATFORM_CLAIM"}))
	quit(0 if failures == 0 else 1)
