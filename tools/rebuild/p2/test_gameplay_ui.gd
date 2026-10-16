extends SceneTree
## Restore the actual completed natural save; no XP/item/money provisioning.
## Godot InputEvent injection exercises production hotkeys, not physical IME.
var checks: Array=[]
var failures:=0
var app
func check(id: String, good: bool, details: Variant=null) -> void:
	checks.append({"id":id,"status":"PASS" if good else "FAIL","details":details})
	if not good: failures+=1
func _initialize() -> void: call_deferred("run")
func key(code: int) -> void:
	for pressed in [true,false]:
		var event:=InputEventKey.new();event.physical_keycode=code;event.keycode=code;event.pressed=pressed
		Input.parse_input_event(event)
		await process_frame
func run() -> void:
	app=load("res://gameplay.tscn").instantiate()
	root.add_child(app)
	await process_frame
	app.smoke=true
	var input_path:=OS.get_environment("BARAM_GAMEPLAY_NATURAL_SAVE")
	var decoded: Dictionary=app.store._decode(FileAccess.get_file_as_string(input_path),"p3-natural-operator",app.content.data)
	check("actual_natural_save_checksum_and_refs",decoded.status=="OK")
	if decoded.status=="OK":
		check("production_restore",app.game.restore(decoded.payload).status=="OK")
		app.save_path="user://gameplay-p3/tests/hotkeys-"+str(Time.get_ticks_usec())+".json"
		app._start_play()
		var c: Dictionary=app.game.state.character
		check("natural_progress_is_reused_without_grants",int(c.level)==10 and int(c.xp)==915 and app.game.state.stats.kills==104 and app.game.state.skills.size()==3)
		check("four_panels_read_same_state",app.panels.get_tab_count()==4 and app.bag.item_count==app.game.state.inventory.size() and app.skills.item_count==app.game.state.skills.size() and str(c.job) in app.attributes.text)
		var hp:=int(c.hp);var mp:=int(c.mp)
		await key(KEY_1)
		c=app.game.state.character
		check("production_hotkey1_spends_exact_MP_before_impact",int(c.mp)==mp-5 and int(c.hp)==hp and not app.game.state.pending_actions.is_empty())
		app._consume_events(app.game.tick(0.5).events)
		check("hotkey_heal_applies_delayed_HP",int(app.game.state.character.hp)>hp)
		var seen: Dictionary={}
		for i in range(4):
			await key(KEY_TAB)
			seen[str(app.panels.current_tab)]=true
		check("tab_key_cycles_four_panels",seen.size()==4)
		# The natural save was made just after its fourth return. Its saved
		# return cooldown is intentionally preserved; wait normal simulation time.
		app._consume_events(app.game.tick(1.5).events)
		mp=int(app.game.state.character.mp)
		await key(KEY_3)
		check("production_hotkey3_spends_return_MP",int(app.game.state.character.mp)==mp-5,{"message":app.message.text,"mp_before":mp,"mp_after":app.game.state.character.mp})
		app._consume_events(app.game.tick(0.7).events)
		var gate: Dictionary=app.content.data.gates.east
		c=app.game.state.character
		check("hotkey_return_uses_selected_direction",c.map_id==gate.map_id and c.x==gate.x and c.y==gate.y)
		var unchanged: String=app.store.base.canonical(app.game.snapshot())
		await key(KEY_2)
		check("insufficient_MP_hotkey_changes_zero",unchanged==app.store.base.canonical(app.game.snapshot()))
		app._refresh_panels();app._render_world()
		await app._capture("actual_natural_save_hotkey_return")
		app.clock+=11.0;app._render_world()
		check("effects_end_no_infinite_overlay",app.active_effects.is_empty())
		check("actual_hotkey_progress_saved",app._save())
		var saved: Dictionary=app.store.read_game(app.save_path,"p3-natural-operator",app.content.data)
		check("hotkey_save_preserves_progress",saved.has("payload") and app.store._canonical(saved.payload)==app.store._canonical(app.game.snapshot()))
		check("no_asset_or_draw_errors",app.content.assets.errors.is_empty() and app.view.draw_errors.is_empty(),app.content.assets.errors)
	var result:={"schema":"baram.gameplay-ui-input-evidence/1","status":"PASS" if failures==0 else "FAIL","scope":"Linux GUI Godot InputEvent injection using actual natural save; no grants, not physical IME or nativeWindows","checks":checks,"failures":failures,"natural_source_sha256":FileAccess.get_sha256(input_path)}
	var file:=FileAccess.open(OS.get_environment("BARAM_GAMEPLAY_REPORT"),FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(result,"  ")+"\n");file.close()
	print("GAMEPLAY_UI_INPUT_RESULT "+JSON.stringify(result))
	quit(0 if failures==0 else 1)
