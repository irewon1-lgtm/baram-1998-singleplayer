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
func type_unicode(field: LineEdit,value: String) -> void:
	field.grab_focus();field.clear()
	for character in value:
		var event:=InputEventKey.new();event.pressed=true;event.unicode=character.unicode_at(0);Input.parse_input_event(event)
		await process_frame

func all_nodes(node: Node) -> Array:
	var nodes: Array=[node]
	for child in node.get_children():nodes.append_array(all_nodes(child))
	return nodes

func settle() -> void:
	for i in range(8):await process_frame

func frame_check(label: String) -> void:
	var area:=app.get_global_rect()
	check(label+" world retains useful area",app.world.size.y>200 and app.world.size.x>400)
	for prefix in ["가방 / 장비","저장","지역 안내","설정","공격","기술 / 마법","줍기","말하기"]:
		var b:=find_button(app,prefix)
		check(label+" visible touch "+prefix,b!=null and area.encloses(b.get_global_rect()) and b.size.y>=50)
	if app.modal!=null:check(label+" modal within viewport",area.encloses(app.modal.get_global_rect()))

func run() -> void:
	root.size=Vector2i(1280,800)
	var entry: Control=load("res://main.tscn").instantiate();root.add_child(entry);await settle();app=entry.get_node_or_null("P6Play")
	if not check("P6 model ready",app!=null and app.model.ready):finish();return
	mode=OS.get_environment("P1998_P6_CASE")
	if mode=="cold":
		check("cold original checkpoint loaded",app.model.snapshot.loaded)
		check("Korean display alias survives cold process",app.model.display_name=="한글여행자")
		check("ASCII native name retained",app.model.snapshot.name==app.profile.character_name and app.model.snapshot.name!="한글여행자")
		check("volume survived cold process",is_equal_approx(app.profile.volume,0.35))
		await capture("cold-korean");finish();return
	app.form.text="bad1";await press("여정 시작");check("invalid name does not create character",not app.model.snapshot.playing)
	await type_unicode(app.form,"한글여행자");check("Unicode key commits reach creation field",app.form.text=="한글여행자")
	await capture("01-korean-input");await press("여정 시작");await settle()
	if not check("normal original Level1 zero-coin creation",app.model.snapshot.playing and int(app.model.snapshot.level)==1 and int(app.model.snapshot.coins)==0):finish();return
	check("Korean alias shown without replacing native name",app.model.display_name=="한글여행자" and app.model.snapshot.name!="한글여행자")
	initial=app.model.snapshot.duplicate(true);app.paused=true
	var missing: Dictionary={}
	for value in app.locale.data.names.values():
		for character in str(value):
			var code:=character.unicode_at(0)
			if code>=0xac00 and code<=0xd7a3 and not app.theme.default_font.has_char(code):missing[character]=true
	check("all catalog Hangul codepoints present in actual font",missing.is_empty())
	check("map and class labels are Korean",app.title.text.contains("시작 들판") and app.hud.text.contains("평민"))
	await capture("02-landscape")
	for dimensions in [Vector2i(1920,1200),Vector2i(1000,600),Vector2i(800,1280),Vector2i(540,960)]:
		root.size=dimensions;await settle();frame_check(str(dimensions))
		app._bag();await settle();frame_check(str(dimensions)+" bag");await capture("size-%d-%d" %[dimensions.x,dimensions.y]);app._close_panel();await settle()
	root.size=Vector2i(800,1280);await settle();app._help();await settle()
	check("long Korean help fits scroll container",app.modal_scroll!=null and app.modal_box.size.x<=app.modal_scroll.size.x+1)
	var action_before: int=app.model.snapshot.action_revision;tap(find_button(app,"공격").get_global_rect().get_center());await process_frame
	check("modal shield blocks accidental background action",app.modal_kind=="help" and int(app.model.snapshot.action_revision)==action_before)
	await press("확인");check("help close responds",app.modal==null)
	app._panel("stress");app._text("긴 대사 줄바꿈 검증. 한글·숫자 123·금전·장비·주술사. ".repeat(140));app.modal_box.add_child(app.button("긴 대사 닫기",app._close_panel,200));await settle()
	check("long text is scrollable rather than clipped",app.modal_box.size.y>app.modal_scroll.size.y)
	await capture("03-long-dialog");await press("긴 대사 닫기");check("offscreen close reached through real scroll and touch",app.modal==null)
	app._settings();await settle();var field: LineEdit
	for node in all_nodes(app.modal):
		if node is LineEdit:field=node;break
	field.grab_focus();app.keyboard_height_override=500;app._layout();await settle()
	check("keyboard fixture modal stays above occlusion",app.modal.get_global_rect().end.y<=app.size.y-app._keyboard_height()+1)
	check("keyboard fixture focused field visible",app.modal.get_global_rect().encloses(field.get_global_rect()))
	await capture("04-keyboard-layout");app.keyboard_height_override=-1;app._layout();await settle()
	app.profile.volume=0.35;app.sounds.volume=0.35;await press("닫기")
	var id:=str(app.model.snapshot.name);app._settings();await settle()
	for node in all_nodes(app.modal):
		if node is LineEdit:field=node;break
	await type_unicode(field,"한글여행자");await press("이름 저장");check("Korean rename preserves original identifier",str(app.model.snapshot.name)==id and app.model.display_name=="한글여행자");await press("닫기")
	app.paused=false;root.size=Vector2i(1280,800);await settle()
	app._direction(Vector2i.RIGHT);await create_timer(0.25).timeout
	app._notification(Node.NOTIFICATION_APPLICATION_PAUSED);var at: Vector2i=app.model.position();var tick: int=app.model.snapshot.world.tick if app.model.snapshot.has("world") else 0
	app._direction(Vector2i.LEFT);await create_timer(0.5).timeout
	check("pause handler cancels input and movement",app.paused and app.held==Vector2i.ZERO and app.model.position()==at)
	check("pause handler saves checkpoint",app.model.snapshot.save_status=="저장 완료")
	app._notification(Node.NOTIFICATION_APPLICATION_RESUMED);check("resume handler restores input without held direction",not app.paused and app.held==Vector2i.ZERO)
	check("Korean command aliases retain native values",app.locale.command("완료")=="Finish" and app.locale.command("서쪽")=="west")
	var error_label:=Label.new();check("unknown Hangul answer refused before ASCII wire",app._ascii_input("알수없는답",error_label)=="" and error_label.text!="");error_label.free()
	await capture("05-final");finish()
