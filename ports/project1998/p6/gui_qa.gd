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
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry)
	for i in range(10):await process_frame
	app=entry.get_node_or_null("P6Play")
	if not check("default P5 screen",app!=null):finish();return
	if not check("model ready",app.get("model")!=null and app.model.ready and app.initialization_error==""):finish();return
	initial=app.model.snapshot.duplicate(true)
	if mode=="smoke":
		app.form.text="bad1";await press("여정 시작");check("P6 rejects invalid name before native Create",not app.model.snapshot.playing)
		app.form.text="FifthHero";await press("여정 시작");check("normal new character",app.model.snapshot.playing and int(app.model.snapshot.level)==1 and int(app.model.snapshot.coins)==0)
		await press("기술 / 마법");check("empty book is visible",app.modal_kind=="spells");await press("닫기")
		await press("지역 안내");check("47 map definitions and source exit list",app.model.definitions.size()==47 and app.modal_kind=="region");await press("닫기")
		await capture("new-game");finish();return
	if not check("saved character loaded",app.model.snapshot.playing and app.model.snapshot.loaded):finish();return
	if mode=="journey":await journey()
	elif mode=="class":await class_flow()
	elif mode=="spells":await spell_flow()
	elif mode=="death":await death_flow()
	elif mode=="death-cold":await death_cold_flow()
	elif mode=="death-pickup":await death_pickup_flow()
	elif mode=="cold":check("cold restored",int(app.model.snapshot.revision)>0);await capture("cold")
	else:check("known case",false)
	finish()
func journey() -> void:
	check("P4 natural character continues",int(app.model.snapshot.stage)==10 and app.model.snapshot.name=="Adventurer")
	await capture("01-p4-continued")
	await press("기술 / 마법");check("previous Soothe listed",find_button(app,"Soothe")!=null);await press("닫기")
	if not await cross(Vector2i(40,130),43):return
	if not await npc("ButcherNpc"):return
	var coins:=int(app.model.snapshot.coins)
	if not await choose("Sell"):return
	check("butcher accepts rabbit meat",app.model.snapshot.dialog.kind=="sell")
	var d=app.model.snapshot.dialog
	var label:=""
	for name in d.names:
		if str(name).to_lower().contains("rabbit"):label=str(name)
	if not check("native rabbit meat sell row",label!=""):return
	await press(label);await choose("Yes");await pages();await press("대화 닫기")
	check("butcher gold and meat change exactly once",int(app.model.snapshot.coins)==coins+1 and amount("rabbit_meat")==0)
	await capture("02-butcher")
	if not await exit_to(0):return
	if not await cross(Vector2i(59,121),3):return
	if not await npc("SmithNpc"):return
	await choose("Buy")
	# Smith uses its original category menu before the item grid.
	if app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="menu":await choose("Other items")
	check("smith stock differs from butcher",app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="buy")
	var before:=amount("wooden_saber");coins=int(app.model.snapshot.coins)
	await press("Wooden saber");await pages();await press("대화 닫기")
	check("native smith purchase price",amount("wooden_saber")==before+1 and int(app.model.snapshot.coins)==coins-1)
	await capture("03-smith")
	if not await exit_to(0):return
	# This natural P4 hero is still Lv2. The original cave requires Lv5;
	# successful integration includes the refusal, not an invented level grant.
	for i in range(3):await process_frame
	app._go(Vector2i(46,113))
	for i in range(500):
		await create_timer(0.05).timeout
		if app.model.snapshot.get("move_failure","")=="gate" and app.navigation==null and app.route.is_empty():break
	check("source cave level gate retained",int(app.model.snapshot.map)==0 and app.model.snapshot.get("move_failure","")=="gate")
	var blocked:=int(app.model.snapshot.blocked)
	await create_timer(0.6).timeout
	check("denied gate cancels automatic retry",int(app.model.snapshot.blocked)==blocked and app.navigation==null and app.route.is_empty())
	app.model.call_core("Save");check("normal P5 continuation saved",app.model.snapshot.save_status=="저장 완료")
	await capture("04-level-gate")

func class_flow() -> void:
	var path:=int(OS.get_environment("P1998_P5_PATH"))
	var hall: int=[0,11,15,13,17][path];var sanctum: int=[0,12,16,14,18][path]
	var cls: String=["Peasant","Warrior","Rogue","Mage","Poet"][path]
	var trainer: String=cls+"TrainerNpc"
	var door: Dictionary={}
	for edge in app.model.definitions["0"].warps:
		if int(edge.DestinationMapId)==hall:door=edge;break
	if not await cross(Vector2i(door.SourceX,door.SourceY),hall):return
	if not await cross(Vector2i(8,1),sanctum):return
	if not await npc(trainer):return
	await choose("Become a "+cls);await pages();await choose("Yes");await pages()
	check("native level5 path change "+cls,app.model.snapshot.class_name==cls and int(app.model.snapshot.coins)==500)
	if app.model.snapshot.dialog!=null:await press("대화 닫기")
	await npc(trainer);await choose("Learn Secret")
	var d=app.model.snapshot.dialog
	check("learnable native secret menu",d!=null and d.kind=="menu" and d.options.size()>0)
	if d==null or d.kind!="menu":return
	var secret:="Gateway"
	if not d.options.has(secret):secret=str(d.options[0])
	await choose(secret);await choose("Yes");await choose("Yes");await pages()
	if app.model.snapshot.dialog!=null:await press("대화 닫기")
	check("native paid learning",app.model.snapshot.spellbook.any(func(s):return s.name==secret))
	await press("기술 / 마법");check("learned spell displayed",find_button(app,secret)!=null);await press("닫기")
	await capture("class-"+cls)

func spell_flow() -> void:
	# Explicit Lv5 Mage with three pre-learned spells; NOT a normal journey.
	var hp:=int(app.model.snapshot.hp);var mp:=int(app.model.snapshot.mp)
	await press("기술 / 마법");await press("Soothe")
	check("type5 source Soothe heals and spends3MP",int(app.model.snapshot.hp)>hp and int(app.model.snapshot.mp)==mp-3)
	await create_timer(1.1).timeout
	await press("기술 / 마법");await press("Gateway")
	check("type1 original question visible",app.modal_kind=="spell-answer")
	for node in app.modal_box.get_children():
		if node is LineEdit:node.text="서쪽"
	await press("사용")
	check("prompt answer follows original random gate box",int(app.model.snapshot.map)==0 and int(app.model.snapshot.x)>=14 and int(app.model.snapshot.x)<=19 and int(app.model.snapshot.y)>=104 and int(app.model.snapshot.y)<=111)
	if not await cross(Vector2i(46,113),50):return
	check("new original mouse population",app.model.snapshot.actors.any(func(a):return not a.npc and a.key=="mouse"))
	var candidates: Array=[]
	for a in app.model.snapshot.actors:
		if not a.npc and a.key=="mouse":candidates.append(a)
	candidates.sort_custom(func(a,b):return app.model.position().distance_to(Vector2i(a.x,a.y))<app.model.position().distance_to(Vector2i(b.x,b.y)))
	if not check("source mouse available",not candidates.is_empty()):return
	var target: Dictionary=candidates[0];await go(Vector2i(target.x,target.y),3)
	var before_exp:=int(app.model.snapshot.exp);var hits:=0
	for attempt in range(40):
		if int(app.model.snapshot.hp)<45 and int(app.model.snapshot.mp)>=8:
			await press("기술 / 마법");await press("Soothe");await create_timer(1.1).timeout
		var exists:=false
		for a in app.model.snapshot.actors:
			if int(a.id)==int(target.id):target=a;exists=true
		if not exists:break
		app._face(Vector2i(target.x,target.y))
		var prior_hp:=int(target.hp);mp=int(app.model.snapshot.mp)
		await press("기술 / 마법");await press("Thunder Bolt");await press("화면에서 대상 선택")
		check("type2 waits for target without moving",app.pending_spell=="thunder_bolt_mage" and not app.auto_attack)
		for a in app.model.snapshot.actors:
			if int(a.id)==int(target.id):target=a
		mp=int(app.model.snapshot.mp)
		var prior_tick: float=app.tick_clock
		app.tick_clock=-10.0 # defer only the next world tick during the debit sample
		tap(point(Vector2i(target.x,target.y)))
		await process_frame;await process_frame
		if mp>=5:check("type2 consumes native5MP before next world tick (%d → %d)" %[mp,int(app.model.snapshot.mp)],int(app.model.snapshot.mp)==mp-5)
		else:check("type2 refuses insufficient MP without debit (%d → %d)" %[mp,int(app.model.snapshot.mp)],int(app.model.snapshot.mp)==mp and app.model.snapshot.message=="You do not have enough mana.")
		app.tick_clock=prior_tick
		await create_timer(1.1).timeout
		var hp_after:=0
		for a in app.model.snapshot.actors:
			if int(a.id)==int(target.id):hp_after=int(a.hp)
		if hp_after<prior_hp:hits+=1
	check("targeted original damage and kill reward",hits>0 and int(app.model.snapshot.exp)>before_exp and int(app.model.snapshot.kills.get("mouse",0))>0)
	await capture("spell-mouse-combat")
	await exit_to(0)
	app.model.call_core("Save");check("spell and new cave state saved",app.model.snapshot.save_status=="저장 완료")

func death_flow() -> void:
	var coins:=int(app.model.snapshot.coins)
	var targets: Array=[]
	for a in app.model.snapshot.actors:
		if not a.npc and a.key=="mouse":targets.append(a)
	targets.sort_custom(func(a,b):return app.model.position().distance_to(Vector2i(a.x,a.y))<app.model.position().distance_to(Vector2i(b.x,b.y)))
	if not check("death fixture mouse present",not targets.is_empty()):return
	var target: Dictionary=targets[0];await go(Vector2i(target.x,target.y),1)
	await press("기술 / 마법");await press("Thunder Bolt");await press("화면에서 대상 선택")
	for a in app.model.snapshot.actors:
		if int(a.id)==int(target.id):target=a
	tap(point(Vector2i(target.x,target.y)))
	for i in range(200):
		await create_timer(0.1).timeout
		if int(app.model.snapshot.hp)==0:break
	check("actual source mob attack causes death",int(app.model.snapshot.hp)==0)
	check("death gold sentinel exported without exception",app.model.snapshot.ok and app.model.snapshot.loot.any(func(i):return i.key=="gold" and int(i.item_id)==-1))
	var gold:=0
	for i in app.model.snapshot.loot:
		if i.key=="gold":gold+=int(i.amount)
	check("source gold loss equals floor pile",coins==int(app.model.snapshot.coins)+gold and gold>0)
	app.model.call_core("Save");check("dead character and gold saved",app.model.snapshot.save_status=="저장 완료")
	await capture("death-gold")
func death_cold_flow() -> void:
	check("cold dead character and native gold restored",int(app.model.snapshot.hp)==0 and app.model.snapshot.loot.any(func(i):return i.key=="gold" and int(i.graphic) in [22,72,73]))
	var pile:=Vector2i(-1,-1);var gold:=0
	for i in app.model.snapshot.loot:
		if i.key=="gold":pile=Vector2i(i.x,i.y);gold+=int(i.amount)
	if not await exit_to(0):return
	if not await cross(Vector2i(42,90),8):return
	if not await npc("ShamanNpc"):return
	await choose("Yes");await pages()
	if app.model.snapshot.dialog!=null:await press("대화 닫기")
	check("native shaman revives after cold restart",int(app.model.snapshot.hp)>0)
	await capture("shaman-revival")
	if not await exit_to(0):return
	if not await cross(Vector2i(46,113),50):return
	await go(pile)
	# A live enemy may be standing on the pile. Clear it with the normal
	# selected-target melee flow before asking the native pickup to run.
	for actor in app.model.snapshot.actors:
		if not actor.npc and Vector2i(actor.x,actor.y)==pile:
			tap(point(pile))
			for i in range(500):
				await create_timer(0.05).timeout
				if not app.auto_attack:break
			app._cancel_input()
	await go(pile)
	check("source pile cell reached after clearing occupancy",app.model.position()==pile)
	gold=0
	for item in app.model.snapshot.loot:
		if item.key=="gold" and Vector2i(item.x,item.y)==pile:gold+=int(item.amount)
	var coins:=int(app.model.snapshot.coins)
	await press("줍기")
	check("death gold can be picked up once",int(app.model.snapshot.coins)==coins+gold and not app.model.snapshot.loot.any(func(i):return i.key=="gold" and Vector2i(i.x,i.y)==pile))

	await press("줍기");check("repeated pickup does not duplicate coins",int(app.model.snapshot.coins)==coins+gold)

func death_pickup_flow() -> void:
	check("prior cold revival retained",int(app.model.snapshot.hp)>0)
	var pile:=Vector2i(-1,-1)
	for item in app.model.snapshot.loot:
		if item.key=="gold":pile=Vector2i(item.x,item.y);break
	if not check("death gold pile still present",pile.x>=0):return
	# Draw the hostile off the pile through real walking/AI, then route
	# around it. Picking up from the adjacent occupied cell is not legal.
	app._cancel_input()
	for attempt in range(8):
		if app.model.position()==pile:break
		var at: Vector2i=app.model.position()
		var away:=Vector2i(signi(at.x-pile.x),signi(at.y-pile.y))
		if away==Vector2i.ZERO:away=Vector2i.DOWN
		await go(at+away*2)
		await create_timer(3.1).timeout
		await go(pile)
	check("pile cell reached",app.model.position()==pile)
	var gold:=0
	for item in app.model.snapshot.loot:
		if item.key=="gold" and Vector2i(item.x,item.y)==pile:gold+=int(item.amount)
	var coins:=int(app.model.snapshot.coins)
	await press("줍기")
	check("native death gold recovery",int(app.model.snapshot.coins)==coins+gold)
	await press("줍기");check("no duplicated recovery",int(app.model.snapshot.coins)==coins+gold)
	await capture("death-pile-recovered")
