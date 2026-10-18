extends SceneTree
## Execute native core and real UI; fixtures are identified in the report.
var app: Control
var output: String
var checks: Array=[]
var failed:=false
var initial: Dictionary={}
var mode:=""

func _initialize() -> void:
	mode=OS.get_environment("P1998_REPAIR_CASE")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")

func check(label: String,ok: bool) -> bool:
	checks.append({"name":label,"status":"PASS" if ok else "FAIL"});print("REPAIR ",label," ",ok)
	if not ok:failed=true
	return ok

func touch(at: Vector2,down: bool) -> void:
	var e:=InputEventScreenTouch.new();e.index=0;e.position=root.get_final_transform()*at;e.pressed=down;Input.parse_input_event(e)

func tap(at: Vector2) -> void:touch(at,true);touch(at,false)

func find_button(node: Node,prefix: String) -> Button:
	if node is Button and node.text.begins_with(prefix):return node
	for child in node.get_children():
		var b:=find_button(child,prefix)
		if b!=null:return b
	return null

func press(prefix: String) -> bool:
	var b:=find_button(app.modal if app.modal!=null else app,prefix)
	if not check("touch "+prefix,b!=null):return false
	var parent: Node=b.get_parent()
	while parent!=null:
		if parent is ScrollContainer:parent.ensure_control_visible(b)
		parent=parent.get_parent()
	await settle();b=find_button(app.modal if app.modal!=null else app,prefix)
	if b==null:return false
	print("TOUCH_AT ",prefix," ",b.get_global_rect()," ",root.get_final_transform()," ",app.modal_kind)
	tap(b.get_global_rect().get_center());await create_timer(0.25).timeout;print("TOUCH_RESULT ",prefix," ",app.modal_kind);return true

func settle() -> void:
	for i in range(8):await process_frame

func capture(name: String) -> void:
	await settle();await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output.path_join(name+".png"))

func finish() -> void:
	var report: Dictionary={"status":"FAIL" if failed else "PASS","platform":OS.get_name(),"mode":mode,"input":"synthetic screen touch in real Godot; not physical Android","initial":initial,"checks":checks}
	if app!=null and app.model!=null:
		app.model.call_core("Save");report.final=app.model.snapshot
	var f:=FileAccess.open(output.path_join("REPAIR.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"\t"));f.close();quit(1 if failed else 0)

func point(cell: Vector2i) -> Vector2:return app.world.global_position+((Vector2(cell)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom

func go(cell: Vector2i) -> void:
	app.paused=false;app._go(cell)
	for i in range(600):
		await create_timer(0.05).timeout
		if app.navigation==null and app.route.is_empty() and not app.model.moving:break

func frame_checks() -> void:
	var label:=str(root.size)
	check(label+" world covers entire canvas",app.world.position.is_equal_approx(Vector2.ZERO) and app.world.size.is_equal_approx(app.size))
	var m: Dictionary=app.model.definitions[app.model.map_id()]
	check(label+" no map letterbox",float(m.width)*24*app.world.zoom>=app.world.size.x-1 and float(m.height)*24*app.world.zoom>=app.world.size.y-1)
	check(label+" no D-pad",find_button(app,"↑")==null and find_button(app,"→")==null)
	for prefix in ["소지품","장비","능력치","지역 안내","설정","공격","기술","줍기","말하기"]:
		var b:=find_button(app,prefix)
		check(label+" controls on screen "+prefix,b!=null and app.get_global_rect().encloses(b.get_global_rect()) and b.size.y>=50)
	check(label+" translucent controls",(app.attack.get_theme_stylebox("normal") as StyleBoxFlat).bg_color.a<0.55)

func run() -> void:
	root.size=Vector2i(960,1536);var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	await settle();app=entry.get_node_or_null("P6Play")
	if not check("core and client loaded",app!=null and app.model.ready):finish();return
	if mode=="windows":
		initial=app.model.snapshot.duplicate(true);app.paused=true
		for dimensions in [Vector2i(1280,800),Vector2i(960,1536)]:
			root.size=dimensions;await settle()
			for entry_window in [["bag",app._bag],["spells",app._spellbook],["equipment",app._equipment],["stats",app._stats]]:
				entry_window[1].call();await settle()
				check(str(dimensions)+" parchment window contained "+entry_window[0],app.get_global_rect().encloses(app.modal.get_global_rect()) and app.modal_box.size.x<=app.modal_scroll.size.x+1)
				var before: int=app.model.snapshot.action_revision
				tap(find_button(app,"공격").get_global_rect().get_center());await settle()
				check(str(dimensions)+" modal shields world action "+entry_window[0],int(app.model.snapshot.action_revision)==before)
				await capture("window-%s-%d-%d" %[entry_window[0],dimensions.x,dimensions.y]);await press("닫기")
		finish();return
	if mode=="p6-update":
		initial=app.model.snapshot.duplicate(true);app.paused=true
		check("actual P6 v2 checkpoint loaded",app.model.snapshot.loaded)
		check("P6 Korean alias retained",app.model.display_name=="한글여행자" and app.model.snapshot.name==app.profile.character_name)
		var earned: Dictionary=app.model.snapshot.character.duplicate(true)
		app._skip_tutorial()
		check("existing P6 character reaches main town",int(app.model.snapshot.map)==0 and int(app.model.snapshot.stage)==10)
		for key in ["Name","Level","Exp","Coins","Inventory","Equipment","Spells"]:check("P6 update preserves "+key,JSON.stringify(earned[key])==JSON.stringify(app.model.snapshot.character[key]))
		await capture("p6-updated-town");finish();return
	if mode=="spells":
		initial=app.model.snapshot.duplicate(true);app.paused=true
		await press("기술")
		var spell: Dictionary=app.model.snapshot.spellbook.filter(func(s):return s.key=="soothe")[0]
		await press(app.locale.entity("spell",spell.key,spell.name))
		check("parchment spell window invokes native Soothe cost/heal",int(app.model.snapshot.mp)==97 and int(app.model.snapshot.hp)>40)
		await create_timer(1.1).timeout;await press("기술")
		spell=app.model.snapshot.spellbook.filter(func(s):return s.key=="gateway")[0]
		await press(app.locale.entity("spell",spell.key,spell.name))
		check("question spell opens answer window",app.modal_kind=="spell-answer")
		for node in app.modal_box.get_children():
			if node is LineEdit:node.text="서쪽"
		await press("사용");check("Korean Gateway answer reaches original town gate",int(app.model.snapshot.x)<30)
		await capture("native-gateway");finish();return
	if mode=="cold":
		check("skip survives cold restore",int(app.model.snapshot.map)==0 and int(app.model.snapshot.stage)>=10)
		initial=app.model.snapshot.duplicate(true);app.paused=true
		var before: String=JSON.stringify(app.model.snapshot.character)
		app.model.call_core("SkipTutorial")
		check("repeat outside tutorial changes no character/reward",before==JSON.stringify(app.model.snapshot.character))
		await capture("cold-main-game");finish();return
	if not app.model.snapshot.get("playing",false):
		app.form.text="RepairHero"
		await press("본게임 시작" if mode=="new-main" else "초보자 수련 시작")
		if not check("native character created",app.model.snapshot.playing):
			print("CREATE_DIAG ",app.create_error.text," ",app.form.text," ",root.size," ",app.size," ",root.get_final_transform());await capture("creation-failed");finish();return
	if mode=="new-main":
		check("new main game starts without tutorial",int(app.model.snapshot.map)==0 and int(app.model.snapshot.stage)==10)
		check("no fabricated starter rewards",int(app.model.snapshot.level)==1 and int(app.model.snapshot.coins)==0 and app.model.snapshot.inventory.is_empty())
		await capture("new-main-game");finish();return
	if mode=="pickup":
		initial=app.model.snapshot.duplicate(true);app.paused=true
		await create_timer(0.5).timeout
		var gold:=int(app.model.snapshot.coins);var loot: Array=app.model.snapshot.loot.duplicate(true)
		await press("줍기")
		check("actual original pickup emits native crouch",app.model.pickup_elapsed<0.4 and app.model.animation_key().begins_with("pickup-"))
		check("actual source floor item picked up",app.model.snapshot.loot.size()<loot.size() and int(app.model.snapshot.coins)>gold)
		await capture("pickup-pose");app.model.advance(0.41)
		check("pickup returns to idle",app.model.animation_key().begins_with("idle-"))
		finish();return
	# A fresh native journey reaches the user's stage1 hunting-field condition.
	if int(app.model.snapshot.map)==4711:
		await go(Vector2i(8,15));check("native exit into hunting field",int(app.model.snapshot.map)==4712)
		await go(Vector2i(12,6))
		for actor in app.model.snapshot.actors:
			if actor.npc and actor.key=="WoodlandSmithNpc":app._world_tap(point(Vector2i(actor.x,actor.y)));break
		await settle()
		if app.model.snapshot.dialog!=null:await press("대화 닫기")
	check("stage1 hunting condition reproduced",int(app.model.snapshot.map)==4712 and int(app.model.snapshot.stage)==1)
	initial=app.model.snapshot.duplicate(true);app.paused=true
	for dimensions in [Vector2i(960,1536),Vector2i(1920,1200),Vector2i(540,960)]:
		root.size=dimensions;await settle();frame_checks();await capture("world-%d-%d" %[dimensions.x,dimensions.y])
	root.size=Vector2i(960,1536);await settle()
	await press("소지품");await settle()
	check("parchment scroll uses original texture",(app.modal.get_theme_stylebox("panel") as StyleBoxTexture).texture.resource_path=="res://p6/art/spellinv.png")
	await capture("inventory")
	var sword: Dictionary={}
	for item in app.model.snapshot.inventory:
		if item.key=="wooden_saber":sword=item;break
	if check("native smith reward in inventory",not sword.is_empty()):
		await press(app.locale.entity("item","wooden_saber",sword.name));await press("사용 / 착용")
		check("native equipment mutation through item window",app.model.snapshot.equipment.any(func(item):return item.key=="wooden_saber"))
	await press("장비");await capture("equipment")
	check("separate equipment window and actual paperdoll",app.modal_kind=="equipment" and not app.model.snapshot.equipment.is_empty())
	await press("벗기");check("native unequip returns item",app.model.snapshot.equipment.is_empty())
	await press("능력치");check("separate effective stats",app.modal_kind=="stats" and app.model.snapshot.stats.has("might"));await capture("stats")
	await press("기술");check("separate spell window",app.modal_kind=="spells");await capture("spells")
	await press("닫기");await press("지역 안내");await settle()
	check("local map raster visible",app.map_view!=null and app.map_view.texture!=null and app.map_view.texture.get_width()>=480)
	check("map position/markers use current native map",not app.map_view.overview and app.map_view.model.map_id()==app.model.map_id())
	await capture("local-map");await press("왕국 전도");await settle()
	check("original kingdom map visible",app.map_view.overview and app.map_view.texture.resource_path=="res://p6/art/field10.png")
	await capture("kingdom-map");await press("현재 지도");await settle()
	var destination: Vector2i=app.model.position()
	for d in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.UP]:
		var candidate: Vector2i=app.model.position()+d
		if app.model.can_step(app.model.map_id(),destination.x,destination.y,candidate.x,candidate.y):destination=candidate;break
	var target: Vector2=app.map_view.global_position+app.map_view._at(Vector2(destination))
	tap(target);await settle();check("map tap starts actual navigation and closes window",app.modal==null and app.goal==destination)
	app._cancel_input()
	# Observe real native wandering, then sample presentation between its tiles.
	var moved:=false
	for attempt in range(45):
		await create_timer(0.34).timeout;app.model.advance(0.25);app.model.call_core("Step")
		for actor in app.model.snapshot.actors:
			var tween: Dictionary=app.model.actor_tweens[str(int(actor.id))]
			if tween.from==tween.to or float(tween.elapsed)>0:continue
			var start: Vector2=app.model.actor_visual(actor);app.model.advance(0.10)
			var mid: Vector2=app.model.actor_visual(actor);var end:=Vector2(actor.x,actor.y)
			check("native rabbit/mob movement interpolates halfway",mid.distance_to(start)>0 and mid.distance_to(end)>0 and mid.is_equal_approx(start.lerp(end,0.5)))
			check("moving actor uses source walking frames",app.model.actor_tick(actor,3)==1)
			app.world.refresh(0);await capture("moving-mobs");moved=true;break
		if moved:break
	check("real native wandering observed",moved)
	app.model.advance(0.25)
	await create_timer(0.5).timeout;app._pickup()
	check("original empty-tile pickup attempt also crouches",app.model.animation_key().begins_with("pickup-"));await capture("pickup-attempt")
	app.model.advance(0.5)
	var earned: Dictionary=app.model.snapshot.character.duplicate(true)
	await press("본게임 시작")
	check("stuck stage1 save can enter main game immediately",int(app.model.snapshot.map)==0 and int(app.model.snapshot.stage)==10)
	for key in ["Name","Level","Exp","Coins","Inventory","Equipment","Spells","Kills","Hp","Mp"]:
		check("skip preserves earned "+key,JSON.stringify(earned[key])==JSON.stringify(app.model.snapshot.character[key]))
	check("skip saves native checkpoint",app.model.snapshot.save_status=="저장 완료")
	check("map change clears actor interpolation ghosts",app.model.actor_tweens.size()==app.model.snapshot.actors.size())
	await capture("main-game");finish()
