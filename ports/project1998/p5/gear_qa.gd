extends SceneTree
var output: String
var checks: Array=[]
var app: Control
func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func check(name: String,ok: bool) -> void:checks.append({"name":name,"status":"PASS" if ok else "FAIL"});print("P5_GEAR ",name," ",ok)
func tap(at: Vector2) -> void:
	for down in [true,false]:
		var e:=InputEventScreenTouch.new();e.index=0;e.position=at;e.pressed=down;Input.parse_input_event(e)
func equip(prefix: String) -> void:
	app._bag();await process_frame
	var scroll: ScrollContainer=app.modal_box.get_child(1)
	for row in scroll.get_child(0).get_children():
		if not row is HBoxContainer:continue
		var found:=false
		for child in row.get_children():
			if child is Label and child.text.begins_with(prefix):found=true
		if not found:continue
		for child in row.get_children():
			if child is Button and child.text.begins_with("사용 / 착용"):
				scroll.ensure_control_visible(child);await process_frame;tap(child.get_global_rect().get_center());await create_timer(0.2).timeout;app._close_panel();return
func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(10):await process_frame
	app=entry.get_node("P5Play")
	await equip("Staff of Power");check("native mage starter staff equipped",app.model.snapshot.equipment.any(func(i):return i.key=="staff_of_power"))
	await equip("Summer garb");check("native summer armor equipped",app.model.snapshot.equipment.any(func(i):return i.key=="summer_garb"))
	check("spear family source art bound",app.model.source.animations.has("weapon:10000:0-idle-"+str(app.model.facing)))
	check("source armor dye1 applied",int(app.model.snapshot.appearance.armor)==3 and int(app.model.snapshot.appearance.dye)==1)
	app.model.call_core("Save");await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(output.path_join("mage-equipment.png"))
	var ok:=checks.all(func(c):return c.status=="PASS")
	var f:=FileAccess.open(output.path_join("GEAR.json"),FileAccess.WRITE);f.store_string(JSON.stringify({"status":"PASS" if ok else "FAIL","checks":checks,"state":app.model.snapshot},"\t"));f.close();quit(0 if ok else 1)
