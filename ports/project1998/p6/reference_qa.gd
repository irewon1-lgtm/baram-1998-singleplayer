extends SceneTree
## Real window and synthetic touch, original core; fixtures explicitly labelled.
var app: Control
var output:=""
var mode:=""
var checks: Array=[]
var failed:=false
var initial: Dictionary={}
func _initialize() -> void:
	mode=OS.get_environment("P1998_REFERENCE_CASE")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-output="):output=arg.trim_prefix("--qa-output=")
	call_deferred("run")
func check(label: String,ok: bool) -> bool:
	checks.append({"name":label,"status":"PASS" if ok else "FAIL"});print("REFERENCE ",label," ",ok)
	if not ok:failed=true
	return ok
func settle() -> void:
	for i in range(8):await process_frame
func tap(at: Vector2) -> void:
	for down in [true,false]:
		var e:=InputEventScreenTouch.new();e.index=0;e.position=root.get_final_transform()*at;e.pressed=down;Input.parse_input_event(e)
func find_button(node: Node,prefix: String) -> Button:
	if node is Button and node.text.begins_with(app.locale.text(prefix)):return node
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
	tap(b.get_global_rect().get_center());await create_timer(0.25).timeout;return true
func capture(name: String) -> void:
	await settle();await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png(output.path_join(name+".png"))
func pages() -> void:
	for i in range(64):
		var d=app.model.snapshot.get("dialog")
		if d==null or d.kind!="text":return
		await press("다음 / 확인")
	check("dialog pages terminate",false)
func wait_path() -> void:
	app.paused=false
	for i in range(600):
		await create_timer(0.05).timeout
		if app.navigation==null and app.route.is_empty() and app.pending_npc==0 and not app.model.moving:break
func go(cell: Vector2i) -> void:
	app._go(cell);await wait_path()
func npc(key: String) -> void:
	await press("말하기")
	if app.modal_kind=="npc-select":
		for a in app.model.snapshot.actors:
			if a.npc and str(a.key)==key:await press(app._npc_name(a));break
	await wait_path();await settle()
	check("ordinary talk opens original NPC "+key,app.model.snapshot.dialog!=null)
	if app.model.snapshot.dialog!=null:
		var d: Dictionary=app.model.snapshot.dialog
		for a in app.model.snapshot.actors:
			if int(a.id)==int(d.npc):check("NPC approached by native movement",app.model.position().distance_to(Vector2i(a.x,a.y))<=1.1)
func choose(value: String) -> void:
	await pages();await press(value);await settle()
func cross(cell: Vector2i,destination: int) -> bool:
	await go(cell);return check("source map transition "+str(destination),int(app.model.snapshot.map)==destination)
func finish() -> void:
	var report: Dictionary={"status":"FAIL" if failed else "PASS","mode":mode,"platform":OS.get_name(),"input":"synthetic screen touch through actual GUI; not Android physical input","initial":initial,"checks":checks}
	if app!=null and app.model!=null:
		app.model.call_core("Save");report.final=app.model.snapshot
		if app.model.snapshot.get("playing",false):report.npc_placements=JSON.parse_string(app.model.core.NpcPlacementAudit())
	var f:=FileAccess.open(output.path_join("REFERENCE.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"\t"));f.close();quit(1 if failed else 0)
func run() -> void:
	root.size=Vector2i(1280,800);var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry);await settle();app=entry.get_node_or_null("P6Play")
	if not check("core and reference client ready",app!=null and app.model.ready):finish();return
	if not app.model.snapshot.get("playing",false):
		app.form.text="ReferenceHero";await press("초보자 수련 시작")
		if not check("native character created",app.model.snapshot.get("playing",false)):await capture("failed");finish();return
	initial=app.model.snapshot.duplicate(true)
	if mode.begins_with("class-"):
		var path:=int(mode.trim_prefix("class-"));var hall: int=[0,11,15,13,17][path];var sanctum: int=[0,12,16,14,18][path];var cls: String=["Peasant","Warrior","Rogue","Mage","Poet"][path]
		for edge in app.model.definitions["0"].warps:
			if int(edge.DestinationMapId)==hall:
				if not await cross(Vector2i(edge.SourceX,edge.SourceY),hall):finish();return
				break
		if not await cross(Vector2i(8,1),sanctum):finish();return
		await npc(cls+"TrainerNpc");await choose("Become a "+cls);await pages();await choose("Yes");await pages()
		check("native level5 class admission "+cls,app.model.snapshot.class_name==cls and int(app.model.snapshot.coins)==500)
		if app.model.snapshot.dialog!=null:await press("대화 닫기")
		await npc(cls+"TrainerNpc");await choose("Learn Secret")
		var d=app.model.snapshot.dialog
		if check("native learnable secrets",d!=null and d.kind=="menu" and not d.options.is_empty()):
			var secret: String="Gateway" if d.options.has("Gateway") else str(d.options[0])
			await choose(secret);await choose("Yes");await choose("Yes");await pages()
			if app.model.snapshot.dialog!=null:await press("대화 닫기")
			check("native paid spell learning",app.model.snapshot.spellbook.any(func(s):return s.name==secret))
			await press("기술");check("learned secret in fixed right pane",app.classic.pane=="spells" and app.model.snapshot.spellbook.any(func(s):return s.name==secret))
		await capture("class-"+cls);finish();return
	if mode=="icons":
		await press("소지품");await capture("restored-icons")
		for key in ["small_amber_ring","large_amber_ring","luxury_amber_bracelet"]:
			var item: Dictionary=app.model.snapshot.inventory.filter(func(it):return str(it.key)==key)[0]
			var icon: AtlasTexture=app._icon(item);check("source icon visible "+key,icon!=null and icon.atlas.resource_path=="res://p6/art/extra-icons.png" and icon.region.size.x>0)
		var item: Dictionary=app.model.snapshot.inventory[0];var might:=int(app.model.snapshot.stats.might)
		await press("a: "+app.locale.entity("item",str(item.key),str(item.name)));await press("사용 / 착용")
		check("source restored ring actually equips",app.model.snapshot.equipment.any(func(it):return it.key=="small_amber_ring"))
		check("native ring stat bonus",int(app.model.snapshot.stats.might)==might+1)
		await press("장비");await capture("restored-ring-equipment");await press(app.locale.entity("item",str(item.key),str(item.name)));await press("벗기")
		await press("소지품");await press("a: "+app.locale.entity("item",str(item.key),str(item.name)));await press("하나 내려놓기")
		check("source new icon on actual floor item",app.model.snapshot.loot.any(func(it):return str(it.key)=="small_amber_ring"));await capture("restored-ring-floor")
		await create_timer(0.6).timeout;await press("줍기");check("native new icon pickup",app.model.snapshot.inventory.any(func(it):return str(it.key)=="small_amber_ring"));finish();return
	if mode=="cold":
		check("existing checkpoint cold restored",app.model.snapshot.loaded)
		check("cold main town and source stage",int(app.model.snapshot.map)==0 and int(app.model.snapshot.stage)>=10)
		await capture("cold");finish();return
	if mode=="rogue":
		await npc("RogueGuildShamanNpc");await capture("rogue-native-dialog")
		check("generic tutorial speech window absent",app.modal_kind=="npc")
		await pages();await capture("rogue-reply");finish();return
	if mode=="shop":
		await npc("SmithNpc");await pages();await capture("smith-menu")
		await press("Buy");await settle();await capture("smith-buy")
		if app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="menu":
			await press(str(app.model.snapshot.dialog.options[0]));await settle()
		check("original buy grid opens",app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="buy")
		if app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="buy":
			var d: Dictionary=app.model.snapshot.dialog;var gold:=int(app.model.snapshot.coins);var chosen:=str(d.names[0]);var price:=int(d.prices[0])
			await press(app.locale.name_of(chosen));await settle()
			if app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="amount":await press("수량 확인")
			await pages();check("buy debits original price",int(app.model.snapshot.coins)==gold-price)
			check("purchase adds original item",app.model.snapshot.inventory.any(func(it):return str(it.name)==chosen))
		await capture("smith-purchase");await press("대화 닫기")
		await npc("SmithNpc");await pages();await press("Sell");await settle();await capture("smith-sell")
		check("original sell list opens",app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="sell")
		if app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="sell" and not app.model.snapshot.dialog.names.is_empty():
			var gold:=int(app.model.snapshot.coins);var name:=str(app.model.snapshot.dialog.names[0]);await press(app.locale.text(name));await pages()
			if app.model.snapshot.dialog!=null and app.model.snapshot.dialog.kind=="menu":await press("Yes");await pages()
			check("sale returns native coins",int(app.model.snapshot.coins)>gold)
		await capture("smith-sale");finish();return
	if mode=="spells":
		await press("기술");await settle()
		var spell: Dictionary=app.model.snapshot.spellbook.filter(func(s):return s.key=="soothe")[0]
		await press(String.chr(97+app.model.snapshot.spellbook.find(spell))+": "+app.locale.entity("spell",spell.key,spell.name));check("right pane invokes native heal",int(app.model.snapshot.mp)==97 and int(app.model.snapshot.hp)>40)
		await capture("spell-heal");finish();return
	if mode=="fresh":
		await go(Vector2i(8,15));check("original field exit",int(app.model.snapshot.map)==4712)
		await npc("WoodlandSmithNpc");await capture("smith-tutorial-dialog")
		await press("대화 닫기");check("native tutorial stage advances",int(app.model.snapshot.stage)==1)
		check("original reward present",app.model.snapshot.inventory.any(func(it):return it.key=="wooden_saber"))
		for actor in app.model.snapshot.actors:
			if actor.npc and actor.key=="WoodlandSmithNpc":
				var local_point: Vector2=((Vector2(actor.x,actor.y)+Vector2(0.5,0.5))*24-app.world.camera)*app.world.zoom+Vector2(0,-14*app.world.zoom)
				tap(app.world.global_position+local_point);await create_timer(0.5).timeout;check("actual NPC sprite touch opens dialog",app.model.snapshot.dialog!=null)
				if app.model.snapshot.dialog!=null:await press("대화 닫기")
				break
		# This NPC speaks through the original outgoing Speech packet, which the
		# old presentation silently discarded. Exercise that event explicitly.
		app.model.call_core("Say",["your name"]);app._update_hud();await settle()
		check("native NPC speech reaches chat pane",not app.classic.chat_lines.is_empty())
	# The common UI/update path starts with an earned or explicit fixture save.
	var placements: Array=JSON.parse_string(app.model.core.NpcPlacementAudit())
	check("all 36 NPC definitions inspected",placements.size()==36)
	for n in placements:check("native accessible floor NPC %d" %int(n.npc),n.accessible)
	for dimensions in [Vector2i(1280,800),Vector2i(1536,864),Vector2i(960,1536)]:
		root.size=dimensions;await settle();var c: Control=app.classic
		check(str(dimensions)+" fixed right pane",c.sheet.position.x>=app.world.get_rect().end.x and app.get_global_rect().encloses(c.right))
		check(str(dimensions)+" world and chat separated",app.world.get_rect().end.y<c.chat.position.y and c.chat.end.x<c.right.position.x)
		check(str(dimensions)+" controls contained",app.world.get_global_rect().encloses(app.action_row.get_global_rect()) and app.world.get_global_rect().encloses(app.utility_row.get_global_rect()))
		for pane in ["소지품","장비","기술","능력치"]:
			await press(pane);check(str(dimensions)+" persistent "+pane,app.modal==null and c.pane_scroll.size.x>100);await capture("%s-%d-%d" %[c.pane,dimensions.x,dimensions.y])
	root.size=Vector2i(1280,800);await settle()
	await press("소지품")
	if app.model.snapshot.inventory.any(func(it):return it.key=="wooden_saber"):
		var item: Dictionary=app.model.snapshot.inventory.filter(func(it):return it.key=="wooden_saber")[0]
		await press("a: "+app.locale.entity("item",item.key,item.name));await press("사용 / 착용");check("equipment actually changes",app.model.snapshot.equipment.any(func(it):return it.key=="wooden_saber"))
		await press("장비");await capture("equipped")
		await press(app.locale.entity("item",item.key,item.name));await press("벗기");check("right equipment unequip",not app.model.snapshot.equipment.any(func(it):return it.key=="wooden_saber"))
		await press("소지품");await press("a: "+app.locale.entity("item",item.key,item.name));await press("하나 내려놓기");check("native drop removes bag item",not app.model.snapshot.inventory.any(func(it):return it.key=="wooden_saber"))
		await create_timer(0.5).timeout;await press("줍기");check("native pickup restores dropped item",app.model.snapshot.inventory.any(func(it):return it.key=="wooden_saber"));check("pickup source crouch pose",app.model.pickup_elapsed<0.4);await capture("pickup")
	await press("지역 안내");check("native map raster present",app.map_view!=null and app.map_view.texture!=null);await capture("map");await press("닫기")
	await press("F1");check("central native menu available",app.model.snapshot.dialog!=null);await capture("central");await press("대화 닫기")
	if int(app.model.snapshot.map)>=4711 and int(app.model.snapshot.map)<=4718:
		var earned: Dictionary=app.model.snapshot.character.duplicate(true);await press("본게임 시작")
		check("main game bypass",int(app.model.snapshot.map)==0)
		for key in ["Name","Level","Exp","Coins","Inventory","Equipment","Spells"]:check("update preserves "+key,JSON.stringify(earned[key])==JSON.stringify(app.model.snapshot.character[key]))
	app.model.call_core("Say",["hello"]);app._update_hud();await capture("main-game");check("source text history captured",not app.model.snapshot.texts.is_empty());finish()
