extends SceneTree
var app: Control
var output: String
var checks: Array=[]

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	assert(not output.is_empty());DirAccess.make_dir_recursive_absolute(output);call_deferred("run")

func check(name: String,ok: bool) -> void:
	checks.append({"name":name,"status":"PASS" if ok else "FAIL"});print("P3_VIEW_CHECK ",name," ",ok)

func touch(index: int,at: Vector2,pressed: bool,canceled: bool=false) -> void:
	var e:=InputEventScreenTouch.new();e.index=index;e.position=at;e.pressed=pressed;e.canceled=canceled;Input.parse_input_event(e)

func tap(at: Vector2) -> void:touch(0,at,true);touch(0,at,false)
func cell_point(cell: Vector2i) -> Vector2:return app.world.global_position+((Vector2(cell)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom
func center(control: Control) -> Vector2:return control.get_global_rect().get_center()

func capture(name: String) -> void:
	for i in range(3):await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name+".png"))

func finish() -> void:
	var passed:=not checks.is_empty()
	for c in checks:if c.status!="PASS":passed=false
	var report: Dictionary={"status":"PASS" if passed else "FAIL","platform":"Linux","scope":"Actual Godot GUI with synthetic ScreenTouch/Drag; original C# in same process. Not physical Android.","checks":checks}
	if app!=null:report.final_state=app.model.snapshot
	var file:=FileAccess.open(output.path_join("VIEW_QA.json"),FileAccess.WRITE);file.store_string(JSON.stringify(report,"\t"));file.close();quit(0 if passed else 1)

func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(20):await process_frame
	app=entry.get_node_or_null("P3World")
	check("Default entry opens the original map and C# player",app!=null)
	if app==null:finish();return
	check("Initial map4711 / source spawn / original render",app.model.position()==Vector2i(3,5) and app.model.map_id()=="4711" and app.world.last_draw_items>100)
	await capture("01-entry")
	tap(cell_point(Vector2i(5,5)));await create_timer(0.8).timeout
	check("Tap navigation commits two original C# moves",app.model.position()==Vector2i(5,5) and int(app.model.snapshot.moves)==2)
	var start: int=app.model.snapshot.moves
	touch(0,Vector2(850,340),true)
	var drag:=InputEventScreenDrag.new();drag.index=0;drag.position=Vector2(930,340);drag.relative=Vector2(80,0);Input.parse_input_event(drag)
	await create_timer(0.25).timeout;touch(0,Vector2(930,340),false,true);await create_timer(0.25).timeout
	check("Drag moves through original Session and canceled touch stops",int(app.model.snapshot.moves)>start and app.held==Vector2i.ZERO and app.stick.finger==-1)
	var stopped: Vector2i=app.model.position();await create_timer(0.3).timeout
	check("No drift after touch cancellation",app.model.position()==stopped)
	tap(cell_point(Vector2i(6,5)));await create_timer(1.2).timeout
	check("Tap reaches cell beside the original rabbit",app.model.position()==Vector2i(6,5))
	touch(0,center(app.pad_buttons[Vector2i.DOWN]),true);await create_timer(0.24).timeout;touch(0,Vector2(1100,200),false);await create_timer(0.24).timeout
	check("C# living-rabbit occupancy blocks actual pad input",app.model.position()==Vector2i(6,5) and int(app.model.snapshot.blocked)>0 and app.model.snapshot.rabbit.alive)
	check("Direction release outside its button is not stuck",app.held==Vector2i.ZERO)
	touch(0,center(app.pad_buttons[Vector2i.LEFT]),true)
	touch(1,center(app.wine),true);await process_frame;touch(1,center(app.wine),false);await process_frame
	check("Second finger uses original Lua wine once while moving",int(app.model.snapshot.uses)==1 and int(app.model.snapshot.hp)==35 and int(app.model.snapshot.mp)==34 and int(app.model.item("wine").charges)==49 and app.held==Vector2i.LEFT)
	touch(0,center(app.pad_buttons[Vector2i.LEFT]),false);await create_timer(0.3).timeout
	tap(center(app.apple));await create_timer(0.1).timeout
	check("Touch apple uses original Lua heal and consumes one",int(app.model.snapshot.hp)==40 and int(app.model.item("apple").amount)==2 and int(app.model.snapshot.uses)==2)
	for direction in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
		touch(0,center(app.pad_buttons[direction]),true);await create_timer(0.23).timeout;touch(0,center(app.pad_buttons[direction]),false);await create_timer(0.23).timeout
		check("Core facing and renderer agree "+str(direction),app.model.facing==[Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT].find(direction))
	app._notification(Control.NOTIFICATION_APPLICATION_FOCUS_OUT);app._notification(Control.NOTIFICATION_APPLICATION_FOCUS_IN)
	stopped=app.model.position();await create_timer(0.3).timeout
	check("Pause/resume saves and clears held input",app.model.position()==stopped and app.held==Vector2i.ZERO and not app.paused)
	tap(center(app.save_button));await create_timer(0.1).timeout
	check("Save button completes and world tick stays stopped",str(app.model.snapshot.message)=="위치와 아이템 저장 완료" and not app.model.snapshot.world_started)
	await capture("02-after-input")
	finish()
