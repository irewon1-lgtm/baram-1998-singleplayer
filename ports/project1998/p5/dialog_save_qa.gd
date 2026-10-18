extends SceneTree
var app: Control
var output: String
func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func button(n: Node,text: String) -> Button:
	if n is Button and n.text.begins_with(text):return n
	for child in n.get_children():
		var b:=button(child,text)
		if b!=null:return b
	return null
func tap(p: Vector2) -> void:
	for pressed in [true,false]:
		var e:=InputEventScreenTouch.new();e.position=p;e.pressed=pressed;Input.parse_input_event(e)
func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(25):await process_frame
	app=entry.get_node("P5Play")
	if OS.get_cmdline_user_args().has("--dialog-cold"):
		var before: Dictionary=app.model.snapshot
		var ok: bool=before.loaded and int(before.stage)==0 and before.inventory.is_empty() and int(before.map)==4712
		app.model.call_core("Talk",[int(before.actors.filter(func(a):return a.npc)[0].id)])
		app.model.call_core("CloseDialog")
		var after: Dictionary=app.model.snapshot
		ok=ok and int(after.stage)==1 and after.inventory.size()==1 and after.inventory[0].key=="wooden_saber" and int(after.inventory[0].amount)==1
		var f:=FileAccess.open(output.path_join("DIALOG_COLD.json"),FileAccess.WRITE);f.store_string(JSON.stringify({"status":"PASS" if ok else "FAIL","before":before,"after":after},"\t"));f.close();quit(0 if ok else 1);return
	app.form.text="DialogHero";tap(button(app,"여정 시작").get_global_rect().get_center());await create_timer(0.3).timeout
	app._go(Vector2i(8,15))
	for i in range(150):
		await create_timer(0.1).timeout
		if int(app.model.snapshot.map)==4712:break
	await create_timer(0.3).timeout
	var npc: Dictionary=app.model.snapshot.actors.filter(func(a):return a.npc)[0]
	var point: Vector2=app.world.global_position+((Vector2(npc.x,npc.y)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom
	tap(point);await create_timer(0.2).timeout
	for i in range(2):tap(button(app,"다음 / 확인").get_global_rect().get_center());await create_timer(0.15).timeout
	await create_timer(3.2).timeout
	var state: Dictionary=app.model.snapshot
	var partial: bool=int(state.stage)==0 and state.inventory.size()==1 and state.inventory[0].key=="wooden_saber" and state.dialog!=null
	var f:=FileAccess.open(output.path_join("DIALOG_PARTIAL.json"),FileAccess.WRITE);f.store_string(JSON.stringify({"source_partial_grant_reproduced":partial,"state":state},"\t"));f.close()
	if not partial:quit(1);return
	app.paused=true
	var ready:=FileAccess.open(output.path_join("KILL_READY"),FileAccess.WRITE);ready.store_string("pending source dialog");ready.close()
