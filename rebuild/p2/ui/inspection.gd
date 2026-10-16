extends Control
const State = preload("res://state/inspection_state.gd")
const InputAdapter = preload("res://input/inspection_input.gd")
const View = preload("res://render/inspection_view.gd")
const SaveTests = preload("res://storage/save_self_test.gd")
var state = State.new()
var input_adapter = InputAdapter.new(state)
var tabs: TabContainer
var name_entry: LineEdit
var bottom: Label
var frame_us: Array[int] = []
var started_us := Time.get_ticks_usec()
var ready_us := 0
var completed := false

func _ready() -> void:
	# Use installed system fonts only; no font is bundled in EXE/APK/artifacts.
	var system_font := SystemFont.new()
	system_font.font_names = PackedStringArray(["Noto Sans CJK KR", "Malgun Gothic", "sans-serif"])
	var inspection_theme := Theme.new()
	inspection_theme.default_font = system_font
	inspection_theme.default_font_size = 19
	theme = inspection_theme
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	add_child(margin)
	var layout := VBoxContainer.new()
	margin.add_child(layout)
	var title := Label.new()
	title.text = "P2 기술 검수 · 원작·완성 게임 판정 없음"
	layout.add_child(title)
	var columns := HBoxContainer.new()
	columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	layout.add_child(columns)
	var view := View.new()
	view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	columns.add_child(view)
	var right := VBoxContainer.new()
	right.custom_minimum_size.x = 350
	columns.add_child(right)
	tabs = TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.tab_changed.connect(state.switch_panel)
	right.add_child(tabs)
	var names := ["물품", "기술", "장비", "능력치"]
	for panel_name in names:
		var scroll := ScrollContainer.new()
		scroll.name = panel_name
		tabs.add_child(scroll)
		var label := Label.new()
		label.text = "실제 콘텐츠 미수신\n아이콘·외형 대체 없음"
		scroll.add_child(label)
	name_entry = LineEdit.new()
	name_entry.placeholder_text = "IME 검수 입력 (저장·인증 없음)"
	right.add_child(name_entry)
	bottom = Label.new()
	bottom.text = "오프라인 검수 | G0 BLOCKED | Windows/Android IME NOT_RUN"
	layout.add_child(bottom)
	ready_us = Time.get_ticks_usec()
	if "--p2-smoke" in OS.get_cmdline_user_args() or OS.has_feature("p2_smoke"):
		_run_smoke.call_deferred()

func _unhandled_input(event: InputEvent) -> void:
	if input_adapter.consume(event):
		get_viewport().set_input_as_handled()

func _notification(what: int) -> void:
	if what in [NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_WM_GO_BACK_REQUEST]:
		state.clear_input()

func _process(delta: float) -> void:
	if not completed:
		frame_us.append(int(delta * 1000000.0))

func _run_smoke() -> void:
	# Synthetic input/structure checks: these are not physical keyboard/IME tests.
	await get_tree().process_frame
	var checks: Array[Dictionary] = []
	checks.append({"id":"four_panels", "pass":tabs.get_tab_count() == 4})
	for index in range(4):
		tabs.current_tab = index
		checks.append({"id":"panel_%s" % index, "pass":state.active_panel == index})
	var movement := InputEventKey.new()
	movement.physical_keycode = KEY_RIGHT
	movement.pressed = true
	input_adapter.consume(movement)
	checks.append({"id":"input_adapter_synthetic_key", "pass":state.held_actions.has("right")})
	var action_event := InputEventKey.new()
	action_event.physical_keycode = KEY_SPACE
	action_event.pressed = true
	input_adapter.consume(action_event)
	checks.append({"id":"synthetic_simultaneous_actions", "pass":state.held_actions.has("right") and state.held_actions.has("inspect_action")})
	movement.pressed = false
	input_adapter.consume(movement)
	checks.append({"id":"release_one_action_keeps_other", "pass":not state.held_actions.has("right") and state.held_actions.has("inspect_action")})
	_notification(NOTIFICATION_APPLICATION_FOCUS_OUT)
	checks.append({"id":"focus_loss_clears_held", "pass":state.held_actions.is_empty()})
	checks.append({"id":"missing_original_visible", "pass":state.original_input_status.begins_with("BLOCKED")})
	# Direct string injection proves UI storage only, never IME composition.
	name_entry.text = "한글 검수"
	checks.append({"id":"unicode_direct_injection_only", "pass":name_entry.text == "한글 검수"})
	# Same storage implementation and synthetic contract on every exported target.
	# Process-kill cases are explicitly NOT_RUN here; the standalone runner adds them.
	# Preserve every earlier run. Native symlink targets must receive real paths,
	# not a user:// URI that the operating system could store literally.
	var run_id := "%s-%s" % [OS.get_process_id(), Crypto.new().generate_random_bytes(8).hex_encode()]
	var fixture_root := ProjectSettings.globalize_path("user://p2-save-fixture-tests/run-" + run_id)
	var save_report: Dictionary = SaveTests.new().run(fixture_root)
	for index in range(180):
		tabs.current_tab = index % 4
		await get_tree().process_frame
	completed = true
	var ordered := frame_us.duplicate()
	ordered.sort()
	var rendering := str(ProjectSettings.get_setting("rendering/renderer/rendering_method"))
	var report := {"schema":"baram.p2.ui_smoke/1", "platform":OS.get_name(), "engine":Engine.get_version_info().string, "profile":state.profile_id, "rendering":rendering, "checks":checks, "script_ready_us":ready_us-started_us, "smoke_elapsed_us":Time.get_ticks_usec()-started_us, "sampled_frames":ordered.size(), "frame_us_p95":ordered[int((ordered.size()-1)*0.95)], "frame_us_p99":ordered[int((ordered.size()-1)*0.99)], "memory_static_bytes":OS.get_static_memory_usage(), "original_assets_consumed":0, "IME":"NOT_RUN", "physical_input":"NOT_RUN", "authentication":"NOT_RUN"}
	var output := OS.get_environment("BARAM_P2_REPORT")
	report["save_tests"] = save_report
	report["fixture_root"] = fixture_root
	if output.is_empty():
		output = "user://ui-smoke.json"
	var file := FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write inspection result: " + output)
		get_tree().quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(output + ".png")
	var failures := checks.filter(func(check: Dictionary) -> bool: return not check["pass"])
	print("P2_UI_SYNTHETIC checks=%s failures=%s report=%s" % [checks.size(), failures.size(), output])
	get_tree().quit(0 if failures.is_empty() and save_report.get("failures", 1) == 0 else 1)
