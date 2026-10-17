extends SceneTree
## Isolated production-UI fixture from a preserved earned save. Direct fixture
## mutations below are not natural play, OS input or player progression proof.
var app
var checks: Array=[]
var failures:=0
var durations: Array=[]

func check(id: String, okay: bool, details: Variant=null) -> void:
	checks.append({"id":id,"status":"PASS" if okay else "FAIL","details":details})
	if not okay: failures+=1

func _initialize() -> void:
	run.call_deferred()

func members(list) -> Array:
	var result: Array=[]
	for index in range(list.item_count): result.append(list.get_item_metadata(index))
	return result

func buttons(list) -> Array:
	var result: Array=[]
	for entry in list.entries: result.append(entry.button.get_instance_id())
	return result

func run() -> void:
	var isolated:=OS.get_environment("BARAM_UI_REUSE_ISOLATED_ROOT")
	var input:=OS.get_environment("BARAM_UI_REUSE_INPUT")
	var output:=OS.get_environment("BARAM_UI_REUSE_OUT")
	if isolated.is_empty() or input.is_empty() or output.is_empty() or not OS.get_user_data_dir().begins_with(isolated):
		push_error("Explicit isolated root, read-only earned input and evidence output required")
		quit(2);return
	root.size=Vector2i(1100,720)
	app=load("res://gameplay.tscn").instantiate();root.add_child(app)
	await process_frame
	app.smoke=true;app.set_process(false)
	check("production_full_G1_scene",app.startup_error.is_empty() and app.content.data.maps.size()==76,app.startup_error)
	if not app.startup_error.is_empty(): finish(output);return
	var original_bytes:=FileAccess.get_file_as_bytes(input)
	var document: Dictionary=JSON.parse_string(original_bytes.get_string_from_utf8())
	var restored: Dictionary=app.game.restore(document.payload)
	check("preserved_earned_save_restores",restored.status=="OK",restored)
	if restored.status!="OK":finish(output);return
	app._start_play()
	await process_frame
	var expected: Array=[]
	for item in app.game.state.inventory: expected.append(item.instance_id)
	check("all_earned_inventory_rows_and_order",members(app.bag)==expected,{"rows":app.bag.item_count})
	app.bag.select(1)
	var selected: String=str(app.bag.get_item_metadata(1))
	var bag_buttons:=buttons(app.bag);var gear_buttons:=buttons(app.equipment);var skill_buttons:=buttons(app.skills)
	for count in range(24):
		app.game.state.character.hp=maxi(1,int(app.game.state.character.hp)-1)
		var started:=Time.get_ticks_usec();app._refresh_panels();durations.append(float(Time.get_ticks_usec()-started)/1000.0)
		await process_frame
	check("vital_only_refresh_preserves_bag_controls",buttons(app.bag)==bag_buttons)
	check("vital_only_refresh_preserves_equipment_controls",buttons(app.equipment)==gear_buttons)
	check("vital_only_refresh_preserves_skill_controls",buttons(app.skills)==skill_buttons)
	check("selected_instance_preserved",app._selection(app.bag)==selected)
	var changed_index:=0
	for index in range(app.game.state.inventory.size()):
		if int(app.game.state.inventory[index].durability)>1:changed_index=index;break
	app.game.state.inventory[changed_index].durability=maxi(0,int(app.game.state.inventory[changed_index].durability)-1)
	app._refresh_panels()
	check("durability_refresh_preserves_controls",buttons(app.bag)==bag_buttons)
	check("durability_tooltip_is_current",("내구 "+str(app.game.state.inventory[changed_index].durability)) in app.bag.entries[changed_index].button.tooltip_text)
	var extra: Dictionary=app.game.state.inventory[changed_index].duplicate(true)
	extra.instance_id="instance:"+str(app.game.state.next_instance_id);app.game.state.next_instance_id+=1
	app.game.state.inventory.append(extra);app._refresh_panels()
	check("membership_change_adds_visible_row",app.bag.item_count==expected.size()+1 and app.bag.get_item_metadata(app.bag.item_count-1)==extra.instance_id)
	check("membership_change_keeps_selected_instance",app._selection(app.bag)==selected)
	app.game.state.inventory.remove_at(0);app._refresh_panels()
	check("removed_row_does_not_leave_stale_callback_index",app.bag.get_item_metadata(0)==selected)
	app.bag.entries[0].button.pressed.emit()
	check("rebuilt_row_selects_its_current_metadata",app._selection(app.bag)==selected)
	app.game.state.character.map_id="gp:map:east_field";app.game.state.character.x=2;app.game.state.character.y=15
	app._render_world()
	var expected_monsters: Array=[]
	for id in app.game.state.monsters:
		if app.game.state.monsters[id].map_id=="gp:map:east_field":expected_monsters.append(id)
	check("current_map_ID_cache_contains_all_current_records",app.runtime_monster_ids==expected_monsters,{"cached":app.runtime_monster_ids.size(),"world":app.game.state.monsters.size()})
	var id: String=str(expected_monsters[0])
	var record: Dictionary=app.game.state.monsters[id].duplicate(true)
	record.hp=1;app.game.state.monsters[id]=record;app.selected_target=id;app._render_world()
	check("cached_ID_reads_replaced_COW_record",app.view.labels.any(func(label):return str(label.get("text","")).ends_with(" ◇") and int(label.get("hp",-1))==1))
	app._start_play();app._render_world()
	check("new_play_resets_and_rebuilds_cache",app.runtime_monster_map=="gp:map:east_field" and app.runtime_monster_ids==expected_monsters)
	check("read_only_earned_source_bytes_unchanged",FileAccess.get_file_as_bytes(input)==original_bytes)
	if DisplayServer.get_name()!="headless":
		await process_frame;await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(output.get_basename()+".png")
	finish(output)

func finish(output: String) -> void:
	var sources: Dictionary={}
	for file in ["ui/gameplay.gd","ui/classic_list.gd","state/gameplay_state.gd","storage/gameplay_store.gd"]:sources[file]=FileAccess.get_sha256("res://"+file)
	var report: Dictionary={"status":"PASS" if failures==0 else "FAIL","scope":"PRODUCTION_UI_ISOLATED_EARNED_SAVE_FIXTURE; direct local fixture changes, not natural play or OS/native input; CPU refresh method timing is not rendered frame latency","checks":checks,"failures":failures,"refresh_method_ms":durations,"source_sha256":sources}
	var file:=FileAccess.open(output,FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
	print(JSON.stringify({"status":report.status,"checks":checks.size(),"failures":failures,"output":output}));quit(0 if failures==0 else 1)
