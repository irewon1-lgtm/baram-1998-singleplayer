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
func measure(label: String,frames: int=180) -> Dictionary:
	for i in range(20):await process_frame
	var values: Array[float]=[];var memory_before:=Performance.get_monitor(Performance.MEMORY_STATIC);var draws: Array[int]=[]
	var started:=Time.get_ticks_usec();var previous:=started
	for i in range(frames):
		await process_frame
		var now:=Time.get_ticks_usec();values.append(float(now-previous)/1000);previous=now;draws.append(int(app.world.last_draw_items))
	var seconds:=float(Time.get_ticks_usec()-started)/1000000;values.sort();draws.sort()
	return {"phase":label,"frames":frames,"seconds":seconds,"average_fps":frames/seconds,"median_frame_ms":values[frames/2],"p95_frame_ms":values[int(frames*0.95)],"worst_frame_ms":values[-1],"engine_static_before":memory_before,"engine_static_after":Performance.get_monitor(Performance.MEMORY_STATIC),"draw_items_median":draws[frames/2],"window_pixels":[root.size.x,root.size.y],"logical_canvas":[app.size.x,app.size.y]}
func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry);app=entry.get_node_or_null("P6Play");mode="P5-update-and-host-performance"
	if not check("P6 loads unchanged P5 save",app!=null and app.model.snapshot.loaded):finish();return
	app.paused=true;initial=app.model.snapshot.duplicate(true)
	var expected: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("P1998_P4_OUTPUT").path_join("EXPECTED_INITIAL.json")))
	check("complete original P5 character preserved before first tick",initial.character==expected.character)
	check("P5 checkpoint revision preserved on load",int(initial.revision)==int(expected.revision))
	var identity_before:=FileAccess.get_sha256(OS.get_environment("P1998_P4_OUTPUT").path_join("v2/identity.json"))
	for i in range(8):await process_frame
	app.paused=false;var records: Array=[]
	records.append(await measure("Kugnae active native ticks"));app._bag();records.append(await measure("Korean inventory open; native ticks active"));app._close_panel()
	root.size=Vector2i(800,1280);records.append(await measure("portrait active native ticks"));root.size=Vector2i(1280,800)
	app._notification(Node.NOTIFICATION_APPLICATION_PAUSED);await create_timer(0.3).timeout;app._notification(Node.NOTIFICATION_APPLICATION_RESUMED);records.append(await measure("resume active native ticks"))
	check("P5 identity bytes retained after UI, rotation fixture and save",identity_before==FileAccess.get_sha256(OS.get_environment("P1998_P4_OUTPUT").path_join("v2/identity.json")))
	check("native save succeeds after update and all UI phases",app.model.snapshot.save_status=="저장 완료")
	var perf:={"status":"MEASURED_LINUX_ONLY","platform":OS.get_name(),"rendering_device":RenderingServer.get_video_adapter_name(),"engine_limit":Engine.max_fps,"process_id":OS.get_process_id(),"whole_process_peak_rss":"see RUNNER.json; engine_static is a narrower measure","phases":records,"device_fps":"NOT_RUN_DEVICE","thermal":"NOT_RUN_DEVICE","battery":"NOT_RUN_DEVICE","claim":"real Linux Godot frames and software rendering; no extrapolation to Galaxy"}
	var f:=FileAccess.open(output.path_join("PERFORMANCE.json"),FileAccess.WRITE);f.store_string(JSON.stringify(perf,"\t"));f.close();await capture("kugnae-update");finish()
