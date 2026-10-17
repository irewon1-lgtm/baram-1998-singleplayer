extends SceneTree
## Explicit UI fixtures and injected events; never physical device certification.
var app
var results: Array=[]
var failures:=0
var output:=OS.get_environment("BARAM_PLAYABILITY_UI_OUT")
func check(id: String, ok: bool, detail: Variant=null) -> void:
	results.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
	if not ok:failures+=1
func _initialize() -> void:
	if output.is_empty():quit(2);return
	DirAccess.make_dir_recursive_absolute(output)
	run.call_deferred()
func buttons(node: Node, text: String) -> Array:
	var found: Array=[]
	if node is Button and node.text==text:found.append(node)
	for child in node.get_children():found.append_array(buttons(child,text))
	return found
func capture(name: String) -> void:
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name+".png"))
func fixed_close(id: String) -> void:
	var viewport:=Rect2(Vector2.ZERO,app.size)
	var x: Button=buttons(app.dialogue,"X")[0]
	check(id+":fixed_x_in_view",viewport.encloses(x.get_global_rect()),x.get_global_rect())
	check(id+":fixed_footer_in_view",viewport.encloses(app.dialogue_close.get_global_rect()),app.dialogue_close.get_global_rect())
	check(id+":close_outside_scroll",not app.dialogue_scroll.is_ancestor_of(x) and not app.dialogue_scroll.is_ancestor_of(app.dialogue_close))
	check(id+":shield_visible",app.modal_shield.visible)
func run() -> void:
	app=load("res://gameplay.tscn").instantiate();root.add_child(app)
	await process_frame;await process_frame
	check("full_G1_load",app.startup_error.is_empty(),app.startup_error)
	if not app.startup_error.is_empty():finish();return
	app.smoke=true
	var created: Dictionary=app.game.create_character("대화검수",app.OWNER,{"desired_job":"전사","nationality":"고구려","guardian":"주작"})
	check("fixture_created",created.status=="OK",created)
	if created.status!="OK":finish();return
	app.save_path="user://gameplay-p3/b5-ui-fixture/"+str(Time.get_ticks_usec())+".json"
	app._start_play()
	var initial: Dictionary=app.game.snapshot()
	for npc_id in app.content.data.npcs:
		app._show_dialogue(str(npc_id));await process_frame;await process_frame
		fixed_close(str(npc_id)+":first_page")
		app.dialogue_scroll.scroll_vertical=100000
		await process_frame
		fixed_close(str(npc_id)+":scrolled")
		if app.dialogue_rows.size()>app.DIALOGUE_PAGE_SIZE:
			app.dialogue_page=ceili(float(app.dialogue_rows.size())/app.DIALOGUE_PAGE_SIZE)-1
			app._render_dialogue_page();await process_frame;fixed_close(str(npc_id)+":last_page")
		app.movement=Vector2i.RIGHT;app.path.append(Vector2i(9,9));app.keyboard_moves[KEY_D]=Vector2i.RIGHT
		app._close_dialogue()
		check(str(npc_id)+":close_clears_motion",app.movement==Vector2i.ZERO and app.path.is_empty() and app.keyboard_moves.is_empty() and not app.dialogue.visible and not app.modal_shield.visible)
		check(str(npc_id)+":cancel_no_state_change",app.game.state==initial)
	for requested in [Vector2i(1100,720),Vector2i(960,540),Vector2i(600,960),Vector2i(1280,800)]:
		root.size=requested;DisplayServer.window_set_size(requested)
		await process_frame;await process_frame;app._resize_ui()
		app._show_dialogue(str(app.content.data.npcs.keys()[0]));await process_frame;await process_frame
		var actual:=root.get_texture().get_image().get_size()
		check("physical_surface:"+str(requested),actual==requested,{"requested":requested,"framebuffer":actual,"window":DisplayServer.window_get_size()})
		fixed_close("size:"+str(requested))
		await capture("dialogue-"+str(requested.x)+"x"+str(requested.y))
		var escape:=InputEventKey.new();escape.physical_keycode=KEY_ESCAPE;escape.pressed=true
		Input.parse_input_event(escape);await process_frame
		check("escape_closes:"+str(requested),not app.dialogue.visible)
		app._show_map();await process_frame;await process_frame
		fixed_close("map:"+str(requested));await capture("map-"+str(requested.x)+"x"+str(requested.y))
		app._notification(Node.NOTIFICATION_WM_GO_BACK_REQUEST)
		check("back_closes_map:"+str(requested),not app.dialogue.visible and not app.game.state.is_empty())
	# Every scrollable command uses the engine's native mouse/touch scroll path,
	# rather than the fixed-action multi-touch handler that accepts press events.
	app._show_dialogue(str(app.content.data.npcs.keys()[0]));await process_frame
	for child in app.dialogue_body.get_children():
		if child is Button:check("scrollable_button_uses_native_scrolling",not child.has_meta("native_touches"))
	app._close_dialogue()
	finish()
func finish() -> void:
	var report:={"schema":"baram.b5.playability-ui/1","status":"PASS" if failures==0 else "FAIL","scope":"Linux rendered viewport, explicit fixture and injected InputEvents; OS touch/IME/native platforms NOT_RUN","checks":results,"failures":failures,"source_ui_sha256":FileAccess.get_sha256("res://ui/gameplay.gd")}
	var file:=FileAccess.open(output.path_join("UI_PLAYABILITY.json"),FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(report,"  ")+"\n")
	print("B5_UI_RESULT "+JSON.stringify({"failures":failures,"checks":results.size()}))
	quit(0 if failures==0 else 1)
