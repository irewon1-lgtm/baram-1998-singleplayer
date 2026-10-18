extends SceneTree
var app: Control
var checks: Array=[]

func _initialize() -> void:call_deferred("run")

func touch(index: int,point: Vector2,pressed: bool,canceled: bool=false) -> void:
	var e:=InputEventScreenTouch.new();e.index=index;e.position=point;e.pressed=pressed;e.canceled=canceled
	Input.parse_input_event(e)

func drag(index: int,point: Vector2,relative: Vector2) -> void:
	var e:=InputEventScreenDrag.new();e.index=index;e.position=point;e.relative=relative
	Input.parse_input_event(e)

func check(name: String,ok: bool) -> void:
	checks.append({"name":name,"status":"PASS" if ok else "FAIL"})

func run() -> void:
	get_root().size=Vector2i(1280,800)
	app=load("res://main.tscn").instantiate();get_root().add_child(app)
	for i in range(6):await process_frame
	app._select_map("4711")
	var start_moves: int=app.model.completed_moves
	touch(0,Vector2(450,350),true)
	drag(0,Vector2(530,350),Vector2(80,0))
	await create_timer(0.25).timeout
	var before_attacks: int=app.model.attacks
	touch(1,Vector2(1190,730),true)
	touch(1,Vector2(1190,730),false)
	await process_frame
	check("Two-finger attack while dragging is delivered exactly once",app.model.attacks==before_attacks+1 and app.held==Vector2i.RIGHT)
	touch(0,Vector2(530,350),false,true)
	await create_timer(0.3).timeout
	check("Screen drag moves through the actual GUI adapter",app.model.completed_moves>start_moves)
	check("Canceled touch releases held movement",app.held==Vector2i.ZERO and app.stick.finger==-1)
	var at: Vector2i=app.model.position()
	await create_timer(0.4).timeout
	check("Canceled movement does not drift",app.model.position()==at)
	touch(0,Vector2(450,350),true)
	drag(0,Vector2(450,430),Vector2(0,80))
	await create_timer(0.1).timeout
	app._notification(Control.NOTIFICATION_APPLICATION_FOCUS_OUT)
	app._notification(Control.NOTIFICATION_APPLICATION_FOCUS_IN)
	check("Pause/resume clears prior finger and route",app.held==Vector2i.ZERO and app.stick.finger==-1 and app.route.is_empty() and not app.paused)
	at=app.model.position();await create_timer(0.4).timeout
	check("Resumed scene remains stationary without new input",app.model.position()==at)
	var passed:=true
	for c in checks:if c.status!="PASS":passed=false
	var file:=FileAccess.open(OS.get_cmdline_user_args()[0],FileAccess.WRITE)
	file.store_string(JSON.stringify({"status":"PASS" if passed else "FAIL","checks":checks,"scope":"Synthetic InputEventScreenTouch/Drag via running Godot GUI; lifecycle notification fixtures. Not native Android events or physical Galaxy."},"\t"));file.close()
	quit(0 if passed else 1)
