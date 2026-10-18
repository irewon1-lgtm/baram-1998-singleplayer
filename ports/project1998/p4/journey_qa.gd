extends SceneTree
## No item grants, stage edits, map teleports or random replacement in this run.
## GUI touch events plus the same client A* goal API for off-screen travel.
var app: Control
var output: String
var checks: Array=[]
var failed:=false
func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func check(name: String,ok: bool) -> bool:
	checks.append({"name":name,"status":"PASS" if ok else "FAIL"});print("P4_CHECK ",name," ",ok)
	if not ok:failed=true
	return ok
func touch(index: int,at: Vector2,pressed: bool,canceled: bool=false) -> void:
	var e:=InputEventScreenTouch.new();e.index=index;e.position=at;e.pressed=pressed;e.canceled=canceled;Input.parse_input_event(e)
func tap(at: Vector2) -> void:touch(0,at,true);touch(0,at,false)
func cell_point(cell: Vector2i) -> Vector2:return app.world.global_position+((Vector2(cell)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom
func find_button(node: Node,text: String) -> Button:
	if node is Button and node.text.begins_with(text):return node
	for child in node.get_children():
		var found:=find_button(child,text)
		if found!=null:return found
	return null
func press(text: String) -> bool:
	var b:=find_button(app,text)
	if not check("touch button: "+text,b!=null):return false
	tap(b.get_global_rect().get_center());await create_timer(0.12).timeout;return true
func capture(name: String) -> void:
	await process_frame;await process_frame;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name+".png"))
func finish() -> void:
	if app!=null and app.get("model")!=null:app.model.call_core("Save")
	var report: Dictionary={"status":"FAIL" if failed else "PASS","scope":"Linux Godot GUI synthetic touch + client A* travel. Natural source RNG/quests, no grants/teleports/stage edits. Not Android hardware.","checks":checks}
	if app!=null and app.get("model")!=null:report.final_state=app.model.snapshot
	var f:=FileAccess.open(output.path_join("JOURNEY.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"\t"));f.close();quit(1 if failed else 0)
func go(cell: Vector2i,mid: int,reach: int=0) -> bool:
	# Let the scene consume its map-change cancellation before a new goal.
	for i in range(3):await process_frame
	app._go(cell,reach)
	for i in range(400):
		await create_timer(0.1).timeout
		if int(app.model.snapshot.map)!=mid:return true
		if not app.model.moving and app.navigation==null and app.route.is_empty():return app.model.position().distance_to(cell)<=reach+0.1
	return false
func cross(cell: Vector2i,from_map: int,to_map: int) -> bool:
	await go(cell,from_map)
	await create_timer(0.3).timeout
	return check("source warp %d → %d" %[from_map,to_map],int(app.model.snapshot.map)==to_map)
func npc(key: String) -> bool:
	var found: Dictionary={}
	for a in app.model.snapshot.actors:
		if a.npc and a.key==key:found=a;break
	if not check("source NPC present: "+key,not found.is_empty()):return false
	# Counters/fences surround some original NPCs. A nearby visible cell is
	# sufficient for their source click handler; adjacency is not a source rule.
	await go(Vector2i(found.x,found.y),int(app.model.snapshot.map),3)
	tap(cell_point(Vector2i(found.x,found.y)))
	await create_timer(0.5).timeout
	return check("touch NPC opens Lua dialog: "+key,app.model.snapshot.dialog!=null)
func pages(choices: Array=[]) -> void:
	var choice:=0
	for i in range(90):
		await create_timer(0.06).timeout
		var d=app.model.snapshot.dialog
		if d==null:return
		if d.kind=="text":
			var b:=find_button(app.modal,"다음 / 확인")
			if b==null:check("dialog next exists",false);return
			tap(b.get_global_rect().get_center())
		elif d.kind=="menu" and choice<choices.size():
			var b:=find_button(app.modal,str(d.options[int(choices[choice])-1]));choice+=1
			tap(b.get_global_rect().get_center())
		else:return
	check("dialog chain terminates",false)
func item_amount(key: String) -> int:
	for item in app.model.snapshot.inventory:
		if item.key==key:return int(item.amount)
	return 0
func hunt(key: String,count: int) -> bool:
	var initial:=int(app.model.snapshot.kills.get(key,0));var deadline:=Time.get_ticks_msec()+240000
	while int(app.model.snapshot.kills.get(key,0))-initial<count and Time.get_ticks_msec()<deadline:
		var candidates: Array=[]
		for a in app.model.snapshot.actors:
			if not a.npc and a.key==key:candidates.append(a)
		if candidates.is_empty():await create_timer(1.0).timeout;continue
		candidates.sort_custom(func(a,b):return app.model.position().distance_to(Vector2i(a.x,a.y))<app.model.position().distance_to(Vector2i(b.x,b.y)))
		var a: Dictionary=candidates[0];var id:=int(a.id)
		await go(Vector2i(a.x,a.y),int(app.model.snapshot.map),1)
		# Locate the moved animal again before the synthetic screen tap.
		for next in app.model.snapshot.actors:
			if int(next.id)==id:a=next
		tap(cell_point(Vector2i(a.x,a.y)))
		for i in range(180):
			await create_timer(0.1).timeout
			if not app.auto_attack:break
		app.auto_attack=false
		var loot: Array=app.model.snapshot.loot.duplicate()
		for drop in loot:
			await go(Vector2i(drop.x,drop.y),int(app.model.snapshot.map))
			await create_timer(0.4).timeout
			tap(cell_point(Vector2i(drop.x,drop.y)));await create_timer(0.6).timeout
		print("P4_HUNT ",key," ",app.model.snapshot.kills," hp=",app.model.snapshot.hp," loot=",app.model.snapshot.inventory)
	return check("natural combat + kill experience: %s ×%d" %[key,count],int(app.model.snapshot.kills.get(key,0))-initial>=count and int(app.model.snapshot.exp)>0)
func equip(key: String) -> void:
	await press("가방 / 장비")
	var use: Button
	for item in app.model.snapshot.inventory:
		if item.key==key:
			# Button lives in the row displaying the source item name.
			for row in app.modal_box.get_child(1).get_child(0).get_children():
				if row is HBoxContainer:
					for child in row.get_children():
						if child is Label and child.text.begins_with(item.name):
							use=find_button(row,"사용 / 착용")
	if use!=null:tap(use.get_global_rect().get_center());await create_timer(0.15).timeout
	await press("닫기")
	var worn:=false
	for item in app.model.snapshot.equipment:if item.key==key:worn=true
	check("source equip: "+key,worn)

func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(30):await process_frame
	app=entry.get_node_or_null("P4Play")
	if not check("default P4 entry",app!=null):finish();return
	if OS.get_cmdline_user_args().has("--continue-journey"):
		if int(app.model.snapshot.stage)==10:
			check("cold continuation at original town stage10",app.model.snapshot.loaded)
			if int(app.model.snapshot.map)==2:
				if not await cross(Vector2i(3,13),2,0):finish();return
			if int(app.model.snapshot.map)==0:
				if not await cross(Vector2i(87,146),0,36):finish();return
			await complete_trade();return
		if int(app.model.snapshot.stage)==9:
			check("cold continuation at original Angel stage9",app.model.snapshot.loaded)
			await complete_town();return
		if not check("cold continuation at original Mignok stage6",app.model.snapshot.get("loaded",false) and int(app.model.snapshot.stage)==6):finish();return
		await complete_route();return
	if not app.model.snapshot.get("playing",false):
		await capture("01-create");await press("여정 시작")
	if not check("original new character spawn and random HP/MP range",app.model.snapshot.playing and int(app.model.snapshot.map)==4711 and app.model.position()==Vector2i(3,5) and int(app.model.snapshot.hp)>=45 and int(app.model.snapshot.hp)<=55 and int(app.model.snapshot.mp)>=32 and int(app.model.snapshot.mp)<=36):finish();return
	await capture("02-welcome")
	tap(cell_point(Vector2i(5,5)));await create_timer(0.9).timeout
	check("touch ground moves via C#",app.model.position()==Vector2i(5,5))
	if not await cross(Vector2i(8,15),4711,4712):finish();return
	if not await npc("WoodlandSmithNpc"):finish();return
	await capture("03-smith");await pages()
	if not check("source smith gives wooden saber and quest stage1",int(app.model.snapshot.stage)==1 and item_amount("wooden_saber")==1):finish();return
	await equip("wooden_saber")
	await capture("04-field")
	if not await hunt("rabbit",10):finish();return
	while item_amount("rabbit_meat")<5:
		if not await hunt("rabbit",1):finish();return
	check("original rabbit loot acquired",item_amount("rabbit_meat")>0)
	await npc("WoodlandSmithNpc");await pages()
	if not check("original rabbit quest unlocks next map",int(app.model.snapshot.stage)==2):finish();return
	if not await cross(Vector2i(13,19),4712,4713):finish();return
	await npc("WoodlandArmorerNpc");await pages()
	check("original armor reward and stage3",int(app.model.snapshot.stage)==3 and item_amount("spring_garb")==1)
	if not await hunt("squirrel",10):finish();return
	await npc("WoodlandArmorerNpc");await pages()
	if not check("original squirrel quest reaches stage4",int(app.model.snapshot.stage)==4):finish();return
	await equip("spring_garb")
	if not await cross(Vector2i(3,19),4713,4714):finish();return
	await npc("TutorialNpc1");await pages()
	if not await cross(Vector2i(21,20),4714,4715):finish();return
	await npc("TutorialNpc2");await pages()
	if not await cross(Vector2i(17,5),4715,4716):finish();return
	await complete_route()

func complete_route() -> void:
	await npc("MignokNpc");await pages();await npc("MignokNpc");await pages()
	if not check("original payment teaches Soothe",app.model.snapshot.spells.has("soothe") and int(app.model.snapshot.stage)==7):finish();return
	var mp:=int(app.model.snapshot.mp);await press("Soothe");await create_timer(0.3).timeout
	check("known Soothe executes original cast",int(app.model.snapshot.mp)<mp)
	await capture("05-soothe")
	if not await cross(Vector2i(6,15),4716,4715):finish();return
	await npc("TutorialNpc2");await pages()
	if not await cross(Vector2i(23,12),4715,4717):finish();return
	await npc("WoodlandGuardNpc");await pages([2,2,2,1,2])
	if not check("original guard quiz warps to Angel",int(app.model.snapshot.map)==4718 and int(app.model.snapshot.stage)==9):finish();return
	await complete_town()

func complete_town() -> void:
	await npc("WoodlandAngelNpc");await pages()
	await press("말하기")
	for child in app.modal_box.get_children():if child is LineEdit:child.text="Finish"
	var say:=find_button(app.modal,"말하기");tap(say.get_global_rect().get_center());await create_timer(0.2).timeout;await pages()
	if not check("Finish source speech reaches Koguryo tutor",int(app.model.snapshot.map)==36 and int(app.model.snapshot.stage)==10):finish();return
	await complete_trade()

func complete_trade() -> void:
	await npc("MainTutorialNpc");await pages([1])
	await npc("MainTutorialNpc");await pages([1])
	if not check("original tutor grants initial 20 gold",int(app.model.snapshot.coins)==20):finish();return
	if not await cross(Vector2i(5,11),36,0):finish();return
	await capture("06-koguryo")
	if not await cross(Vector2i(56,149),0,2):finish();return
	await npc("InnNpc")
	await capture("07-inn")
	var d=app.model.snapshot.dialog;var buy_option:=""
	for option in d.options:if "Buy" in str(option):buy_option=str(option)
	var b:=find_button(app.modal,buy_option);tap(b.get_global_rect().get_center());await create_timer(0.2).timeout
	d=app.model.snapshot.dialog;var coins:=int(app.model.snapshot.coins)
	if not check("native buy grid",d!=null and d.kind=="buy"):finish();return
	b=find_button(app.modal,"Apple");tap(b.get_global_rect().get_center());await create_timer(0.2).timeout;await pages()
	if app.model.snapshot.dialog!=null:await press("대화 닫기")
	check("native purchase spends original 10 gold and adds apple",int(app.model.snapshot.coins)==coins-10 and item_amount("apple")==1)
	await npc("InnNpc");d=app.model.snapshot.dialog;var sell_option:=""
	for option in d.options:if "Sell" in str(option):sell_option=str(option)
	b=find_button(app.modal,sell_option);tap(b.get_global_rect().get_center());await create_timer(0.2).timeout
	d=app.model.snapshot.dialog
	if not check("native sell grid only offers accepted goods",d!=null and d.kind=="sell" and d.slots.size()>0 and d.names.size()==1 and str(d.names[0]).begins_with("Apple")):finish();return
	coins=int(app.model.snapshot.coins)
	b=find_button(app.modal,str(d.names[0]));tap(b.get_global_rect().get_center());await create_timer(0.2).timeout
	await pages([1])
	if app.model.snapshot.dialog!=null:await press("대화 닫기")
	check("native confirmed sale pays original 5 gold and removes apple",int(app.model.snapshot.coins)==coins+5 and item_amount("apple")==0)
	if not await cross(Vector2i(3,13),2,0):finish();return
	check("source level progression",int(app.model.snapshot.level)>1)
	await press("저장");await capture("08-saved")
	check("canonical checkpoint saved",app.model.snapshot.save_status=="저장 완료")
	finish()
