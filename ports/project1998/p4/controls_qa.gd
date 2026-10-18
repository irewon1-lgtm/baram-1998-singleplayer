extends SceneTree
var app: Control
var output: String
var checks: Array=[]
var failed:=false
func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func check(name: String,ok: bool) -> void:
	checks.append({"name":name,"status":"PASS" if ok else "FAIL"});print("P4_CONTROL ",name," ",ok)
	if not ok:failed=true
func touch(index: int,at: Vector2,pressed: bool,canceled: bool=false) -> void:
	var e:=InputEventScreenTouch.new();e.index=index;e.position=at;e.pressed=pressed;e.canceled=canceled;Input.parse_input_event(e)
func tap(at: Vector2) -> void:touch(0,at,true);touch(0,at,false)
func find_button(n: Node,text: String) -> Button:
	if n is Button and n.text.begins_with(text):return n
	for child in n.get_children():
		var b:=find_button(child,text)
		if b!=null:return b
	return null
func press(text: String) -> void:
	var b:=find_button(app,text);check("touch "+text,b!=null)
	if b!=null:tap(b.get_global_rect().get_center());await create_timer(0.15).timeout
func point(cell: Vector2i) -> Vector2:return app.world.global_position+((Vector2(cell)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom
func go(cell: Vector2i) -> void:
	for i in range(3):await process_frame
	app._go(cell)
	for i in range(300):
		await create_timer(0.1).timeout
		if not app.model.moving and app.navigation==null and app.route.is_empty():return
func report() -> void:
	var f:=FileAccess.open(output.path_join("CONTROLS.json"),FileAccess.WRITE)
	f.store_string(JSON.stringify({"status":"FAIL" if failed else "PASS","checks":checks,"final_state":app.model.snapshot},"\t"));f.close()
func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(30):await process_frame
	app=entry.get_node_or_null("P4Play")
	if app==null:quit(1);return
	app.form.text="bad1";await press("여정 시작")
	check("original name gate rejects digit, no character created",not app.model.snapshot.playing)
	app.form.text="ControlHero";await press("여정 시작")
	check("valid creation opens game",app.model.snapshot.playing)
	var right:=find_button(app,"→");var up:=find_button(app,"↑")
	touch(0,right.get_global_rect().get_center(),true);await create_timer(0.24).timeout
	touch(1,up.get_global_rect().get_center(),true);touch(1,Vector2(1100,200),false,true)
	check("second direction finger does not steal movement",app.held==Vector2i.RIGHT and app.pad_finger==0)
	var save:=find_button(app,"저장");touch(1,save.get_global_rect().get_center(),true);touch(1,save.get_global_rect().get_center(),false)
	check("second finger can save while movement is held",app.held==Vector2i.RIGHT and app.model.snapshot.save_status=="저장 완료")
	touch(0,Vector2(1100,200),false,true);await create_timer(0.3).timeout
	var stopped: Vector2i=app.model.position();await create_timer(0.35).timeout
	check("release outside pad and cancellation stop without drift",app.held==Vector2i.ZERO and app.model.position()==stopped)
	touch(0,Vector2(850,360),true)
	var drag:=InputEventScreenDrag.new();drag.index=0;drag.position=Vector2(930,360);drag.relative=Vector2(80,0);Input.parse_input_event(drag)
	await create_timer(0.25).timeout;touch(0,Vector2(930,360),false,true);await process_frame
	check("drag cancellation releases touch stick",app.stick.finger==-1 and app.held==Vector2i.ZERO)
	app._notification(Control.NOTIFICATION_APPLICATION_FOCUS_OUT);app._notification(Control.NOTIFICATION_APPLICATION_FOCUS_IN)
	check("pause/resume clears input and saves",not app.paused and app.held==Vector2i.ZERO and app.model.snapshot.save_status=="저장 완료")
	await go(Vector2i(8,15));check("real exit into field",int(app.model.snapshot.map)==4712)
	await go(Vector2i(3,0));check("original return exit into Welcome",int(app.model.snapshot.map)==4711)
	await go(Vector2i(8,15));check("field reentry",int(app.model.snapshot.map)==4712)
	# A source NPC click is allowed from its original viewport, without a new adjacency gate.
	await go(Vector2i(12,6))
	var blocked_before:=int(app.model.snapshot.blocked)
	app._go(Vector2i(14,6));app.navigation=null;app.route.assign([Vector2i(13,6)])
	for i in range(80):
		await create_timer(0.1).timeout
		if app.model.position()==Vector2i(14,6) and not app.model.moving:break
	check("stale route rejects occupied NPC tile then replans to goal",int(app.model.snapshot.blocked)>blocked_before and app.model.position()==Vector2i(14,6))
	var npc: Dictionary={}
	for a in app.model.snapshot.actors:if a.npc:npc=a
	tap(point(Vector2i(npc.x,npc.y)));await create_timer(0.2).timeout
	check("original NPC window opens",app.model.snapshot.dialog!=null)
	await press("대화 닫기")
	var saber:=0
	for item in app.model.snapshot.inventory:if item.key=="wooden_saber":saber+=int(item.amount)
	check("closing text finishes original stage, no abandoned grant",app.model.snapshot.dialog==null and int(app.model.snapshot.stage)==1 and saber==1)
	tap(point(Vector2i(npc.x,npc.y)));await create_timer(0.2).timeout;await press("대화 닫기")
	var after:=0
	for item in app.model.snapshot.inventory:if item.key=="wooden_saber":after+=int(item.amount)
	check("reopening/closing NPC does not duplicate reward",after==1 and app.model.snapshot.dialog==null)
	await press("가방 / 장비");await press("사용 / 착용");await press("닫기")
	check("touch equips original sword",app.model.snapshot.equipment.size()==1)
	await press("가방 / 장비");await press("벗기");await press("닫기")
	check("touch unequips sword into bag",app.model.snapshot.equipment.is_empty())
	await press("가방 / 장비");await press("사용 / 착용");await press("닫기")
	# Leave a natural source loot roll on the floor for the kill/cold test.
	for attempt in range(8):
		if not app.model.snapshot.loot.is_empty():break
		var mobs: Array=[]
		for a in app.model.snapshot.actors:if not a.npc:mobs.append(a)
		mobs.sort_custom(func(a,b):return app.model.position().distance_to(Vector2i(a.x,a.y))<app.model.position().distance_to(Vector2i(b.x,b.y)))
		if mobs.is_empty():break
		var target: Dictionary=mobs[0];app._go(Vector2i(target.x,target.y),1)
		for i in range(100):
			await create_timer(0.1).timeout
			if app.navigation==null and app.route.is_empty() and not app.model.moving:break
		for a in app.model.snapshot.actors:if int(a.id)==int(target.id):target=a
		tap(point(Vector2i(target.x,target.y)))
		for i in range(200):
			await create_timer(0.1).timeout
			if not app.auto_attack:break
		app.auto_attack=false
	check("natural floor loot available for force-kill checkpoint",not app.model.snapshot.loot.is_empty())
	app.paused=true;app.model.call_core("Save");report()
	await process_frame;await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(output.path_join("controls.png"))
	if failed:quit(1);return
	var ready:=FileAccess.open(output.path_join("KILL_READY"),FileAccess.WRITE);ready.store_string("SQLite save loop follows");ready.close()
	# The parent sends SIGKILL while the app performs real full SQLite saves.
	while true:app.model.call_core("Save");await process_frame
