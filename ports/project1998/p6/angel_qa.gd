extends SceneTree
## Real GUI actions. 'journey' continues the untouched natural P4 save.
## 'class' starts an explicitly labelled level-5 fixture, never a normal-play claim.
var app: Control
var output: String
var mode: String
var checks: Array=[]
var failed:=false
var initial: Dictionary={}
func _initialize() -> void:
	mode=OS.get_environment("P1998_P5_CASE")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func check(label: String,ok: bool) -> bool:
	checks.append({"name":label,"status":"PASS" if ok else "FAIL"});print("P5_GUI ",label," ",ok)
	if not ok:failed=true
	return ok
func touch(index: int,at: Vector2,down: bool) -> void:
	var event:=InputEventScreenTouch.new();event.index=index;event.position=at;event.pressed=down;Input.parse_input_event(event)
func tap(at: Vector2) -> void:touch(0,at,true);touch(0,at,false)
func point(cell: Vector2i) -> Vector2:return app.world.global_position+((Vector2(cell)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom
func find_button(node: Node,prefix: String) -> Button:
	if node is Button and node.text.begins_with(app.locale.text(prefix)):return node
	for child in node.get_children():
		var b:=find_button(child,prefix)
		if b!=null:return b
	return null
func press(prefix: String) -> bool:
	var b:=find_button(app.modal if app.modal!=null else app,prefix)
	if not check("touch "+prefix,b!=null):return false
	# Scroll rows into view before generating a real screen touch.
	var parent: Node=b.get_parent()
	while parent!=null:
		if parent is ScrollContainer:parent.ensure_control_visible(b)
		parent=parent.get_parent()
	await process_frame;tap(b.get_global_rect().get_center());await create_timer(0.15).timeout;return true
func pages() -> void:
	for i in range(64):
		var d=app.model.snapshot.get("dialog")
		if d==null or d.kind!="text":return
		await press("다음 / 확인")
	check("text pages terminated",false)
func choose(prefix: String) -> bool:
	await pages()
	var d=app.model.snapshot.get("dialog")
	if not check("native choice "+prefix,d!=null and d.kind=="menu"):return false
	return await press(prefix)
func go(cell: Vector2i,reach: int=0) -> bool:
	for i in range(3):await process_frame
	app._go(cell,reach)
	for i in range(800):
		await create_timer(0.05).timeout
		if app.navigation==null and app.route.is_empty() and not app.model.moving:
			return app.model.position().distance_to(cell)<=reach+0.1
	return false
func cross(cell: Vector2i,to: int) -> bool:
	var from:=int(app.model.snapshot.map)
	for i in range(3):await process_frame
	app._go(cell)
	for i in range(900):
		await create_timer(0.05).timeout
		if int(app.model.snapshot.map)!=from:break
		if app.navigation==null and app.route.is_empty() and not app.model.moving:break
	return check("source exit %d → %d" %[from,to],int(app.model.snapshot.map)==to)
func exit_to(to: int) -> bool:
	for edge in app.model.definitions[app.model.map_id()].warps:
		if int(edge.DestinationMapId)==to:return await cross(Vector2i(edge.SourceX,edge.SourceY),to)
	return check("source return exit present",false)
func npc(key: String) -> bool:
	var found: Dictionary={}
	for a in app.model.snapshot.actors:
		if a.npc and a.key==key:found=a;break
	if not check("NPC present "+key,not found.is_empty()):return false
	await go(Vector2i(found.x,found.y),3)
	tap(point(Vector2i(found.x,found.y)));await create_timer(0.2).timeout
	return check("NPC window "+key,app.model.snapshot.dialog!=null)
func amount(key: String) -> int:
	var total:=0
	for item in app.model.snapshot.inventory:
		if item.key==key:total+=int(item.amount)
	return total
func capture(name: String) -> void:
	await process_frame;await process_frame;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name+".png"))
func finish() -> void:
	if app!=null and app.get("model")!=null:app.model.call_core("Save")
	var report: Dictionary={"status":"FAIL" if failed else "PASS","mode":mode,"platform":OS.get_name(),"input":"synthetic ScreenTouch + same client A* travel API","initial":initial,"checks":checks}
	if app!=null and app.get("model")!=null:report.final=app.model.snapshot;report.locale_observed=app.locale.observed.keys();report.locale_fallback=app.locale.fallback.keys();report.audio_played=app.sounds.played;report.audio_missing=app.sounds.missing.keys()
	var f:=FileAccess.open(output.path_join("GUI.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"\t"));f.close();quit(1 if failed else 0)
func run() -> void:
	root.size=Vector2i(1280,800);var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(8):await process_frame
	app=entry.get_node_or_null("P6Play");mode="Korean-Finish-source-Angel-fixture"
	if not check("explicit stage9 fixture loaded",app!=null and app.model.ready and int(app.model.snapshot.stage)==9):finish();return
	initial=app.model.snapshot.duplicate(true)
	if not await npc("WoodlandAngelNpc"):finish();return
	await capture("angel-korean-dialog");await pages()
	if app.model.snapshot.dialog!=null:await press("대화 닫기")
	await press("말하기")
	for node in app.modal_box.get_children():
		if node is LineEdit:
			node.grab_focus()
			for character in "완료":
				var event:=InputEventKey.new();event.pressed=true;event.unicode=character.unicode_at(0);Input.parse_input_event(event);await process_frame
	await press("말하기");await pages()
	check("Korean Finish speech advances original quest exactly once",int(app.model.snapshot.stage)==10)
	check("original nation home warp follows Korean speech",int(app.model.snapshot.map)==36)
	check("native name remains unchanged",app.model.snapshot.name==initial.name)
	app.model.call_core("Save");check("original reward and warp commit",app.model.snapshot.save_status=="저장 완료")
	await capture("angel-native-home");finish()
