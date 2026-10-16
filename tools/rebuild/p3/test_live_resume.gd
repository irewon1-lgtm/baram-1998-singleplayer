extends SceneTree
## Ten minutes of unaccelerated production ticking and ordinary GUI controls.
## The automatic operator reads state to choose inputs, never grants XP/items/skills.
var app
var started:=0
var milestones: Array=[]
var failures: Array=[]
var last_report:=-60.0
func _initialize() -> void:call_deferred("run")
func mouse(at: Vector2) -> void:
 var motion:=InputEventMouseMotion.new();motion.position=at;Input.parse_input_event(motion)
 for down in [true,false]:
  var e:=InputEventMouseButton.new();e.position=at;e.button_index=MOUSE_BUTTON_LEFT;e.pressed=down;Input.parse_input_event(e);await process_frame
func key(code: int) -> void:
 for down in [true,false]:
  var e:=InputEventKey.new();e.physical_keycode=code;e.keycode=code;e.pressed=down;Input.parse_input_event(e);await process_frame
func press(text: String) -> bool:
 var pending: Array=[app]
 while not pending.is_empty():
  var node: Node=pending.pop_front();pending.append_array(node.get_children())
  if node is Button and node.is_visible_in_tree() and str(node.text).begins_with(text):
   var ancestor: Node=node.get_parent()
   while ancestor!=null:
    if ancestor is ScrollContainer:ancestor.ensure_control_visible(node)
    ancestor=ancestor.get_parent()
   await process_frame;await process_frame
   await mouse(node.get_global_rect().get_center());return true
 return false
func tap_world(tile: Vector2i) -> void:
 var world:=Vector2(tile)*24+Vector2(12,12)
 var at: Vector2=app.view.global_position+app.view.size*.5+(world-app.view.focus)*app.view.zoom
 var bounds: Rect2=app.view.get_global_rect().grow(-40)
 at=at.clamp(bounds.position,bounds.end)
 await mouse(at)
func route(text: String) -> bool:
 await press("지도");await process_frame
 var okay:=await press(text)
 if not okay:
  await press("닫기");failures.append("Route button absent: "+text);return false
 var timeout:=Time.get_ticks_msec()+30000
 while not app.path.is_empty() and Time.get_ticks_msec()<timeout:await create_timer(.1).timeout
 return true
func note(name: String) -> void:
 var entry:={"name":name,"elapsed_s":float(Time.get_ticks_msec()-started)/1000.0,"character":app.game.state.character.duplicate(),"stats":app.game.state.stats.duplicate()}
 milestones.append(entry);print("LIVE_MILESTONE "+JSON.stringify(entry))
func screenshot(name: String) -> void:
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join(name+".png"))
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame
 var found:=-1
 for i in range(app.names.item_count):
  if app.names.get_item_text(i).begins_with("실제동선53623"):
   found=i;break
 if found<0:print("RESUME_FAIL expected actual live character missing");quit(1);return
 app.names.select(found);app._continue_character();await process_frame
 started=Time.get_ticks_msec();note("new_process_resumed_real_earned_progress");await screenshot("journey_start")
 if not str(app.game.state.character.map_id).ends_with("domestic_city") and not str(app.game.state.character.map_id).ends_with("south_field"):await route("국내성")
 await route("남문 왕초보")
 note("entered_hunting_field_through_map_UI")
 var trained:=str(app.game.state.character.job)!="commoner";var traded:=true
 var return_learned: bool="KRO-972853314e6a" in app.game.state.skills
 var damage_cast:=false
 while Time.get_ticks_msec()-started<420000:
  var elapsed:=float(Time.get_ticks_msec()-started)/1000.0
  if elapsed-last_report>=60:
   last_report=elapsed;note("minute_"+str(int(elapsed/60)));app._performance_checkpoint()
  var c: Dictionary=app.game.state.character
  if c.dead:
   await press("부활");await create_timer(.3).timeout;await route("남문 왕초보");continue
  if not str(c.map_id).ends_with("south_field"):
   if app.dialogue.visible:await press("닫기 / 취소")
   if not str(c.map_id).ends_with("domestic_city"):await route("국내성")
   await route("남문 왕초보");await create_timer(.2).timeout;continue
  # Seek only by pointer taps; distant targets require normal visible ground steps.
  var nearest:="";var distance:=999
  for id in app.game.state.monsters:
   var m: Dictionary=app.game.state.monsters[id]
   if m.map_id!=c.map_id or not m.alive:continue
   var d:=absi(int(m.x)-int(c.x))+absi(int(m.y)-int(c.y))
   if d<distance:nearest=id;distance=d
  if not nearest.is_empty():
   var target: Dictionary=app.game.state.monsters[nearest]
   if distance>1:await tap_world(Vector2i(target.x,target.y));await create_timer(.35).timeout
   else:
    await key(KEY_ESCAPE) # User can clear selection, then use the basic attack key.
    await key(KEY_SPACE);await create_timer(.6).timeout
    await key(KEY_Z)
  else:await create_timer(.4).timeout
  # A learned attack is cast by its real row/button, with no skill grant.
  if not damage_cast and "KRO-3559b12ed6a7" in app.game.state.skills and not app.game.attack_target(4).is_empty():
   app.panels.current_tab=1;app._refresh_panels();await process_frame
   for i in range(app.skills.item_count):
    if app.skills.get_item_metadata(i)=="KRO-3559b12ed6a7":
     await mouse(app.skills.entries[i].button.get_global_rect().get_center());await press("선택 기술 사용");await create_timer(.5).timeout;note("earned_damage_skill_cast");damage_cast=true;break
  if not return_learned:
   var acorns:=0;var meat:=0
   for item in app.game.state.inventory:
    if item.item_id=="KRO-ITEM-1ec5d43f9e157e":acorns+=int(item.quantity)
    if item.item_id=="gp:item:rabbit_meat":meat+=int(item.quantity)
   if acorns>=10 and meat>=10:
    await route("국내성");await route("주술사길드");await route("해두")
    if app.dialogue.visible:await press("비영사천문 학습");await press("닫기 / 취소")
    return_learned="KRO-972853314e6a" in app.game.state.skills
    app.panels.current_tab=1;app._refresh_panels();await process_frame
    if return_learned:
     for i in range(app.skills.item_count):
      if app.skills.get_item_metadata(i)=="KRO-972853314e6a":
       await mouse(app.skills.entries[i].button.get_global_rect().get_center());await press("선택 기술 사용");await create_timer(.8).timeout;note("earned_return_skill_cast_to_gate");await screenshot("natural_return");break
    if not str(app.game.state.character.map_id).ends_with("domestic_city"):await route("국내성")
    await route("남문 왕초보")
  # Trade and job/skill learning only after resources have been earned normally.
  if not traded and int(c.level)>=6 and int(app.game.state.stats.kills)>=55:
   note("earned_resources_before_trade")
   await route("국내성")
   await route("장터 식재료상")
   if app.dialogue.visible:await press("닫기 / 취소")
   app.panels.current_tab=0;await process_frame
   for i in range(app.bag.item_count):
    var instance: Dictionary=app._instance(str(app.bag.get_item_metadata(i)))
    if instance.item_id=="gp:item:rabbit_meat" and int(instance.quantity)>10:
     await mouse(app.bag.entries[i].button.get_global_rect().get_center())
     for j in range(mini(5,int(instance.quantity)-10)):await press("가까운 상인에게 판매");await create_timer(.1).timeout
     break
   note("sold_earned_loot")
   await route("대장간")
   await route("털보")
   if app.dialogue.visible:
    await press("목검 구매");await press("닫기 / 취소")
   app.panels.current_tab=0;app._refresh_panels();await process_frame
   for i in range(app.bag.item_count):
    var item: Dictionary=app._instance(str(app.bag.get_item_metadata(i)))
    if item.item_id=="KRO-ITEM-89a184f51172c1":await mouse(app.bag.entries[i].button.get_global_rect().get_center());await press("장착 / 사용");break
   note("equipment_trade_after_earned_money");app.panels.current_tab=2;await screenshot("journey_equipment")
   await route("국내성");await route("주술사길드");await route("해두")
   if app.dialogue.visible:
    await press("주술사 전직")
    await press("누리의기원 학습")
    await press("화염주(화) 학습")
    await press("비영사천문 학습")
    await press("닫기 / 취소")
   note("job_and_skill_learning_after_natural_requirements")
   app.panels.current_tab=1;app._refresh_panels();await screenshot("journey_skills")
   # Cast only actually learned skills through the same UI.
   if not app.game.state.skills.is_empty():
    for i in range(app.skills.item_count):
     var id:=str(app.skills.get_item_metadata(i))
     if app.content.data.skills[id].kind=="return":
      await mouse(app.skills.entries[i].button.get_global_rect().get_center());await press("선택 기술 사용");await create_timer(.7).timeout;break
   traded=true;trained=str(app.game.state.character.job)!="commoner";note("actual_learned_cast_or_pending_requirements")
 if app.dialogue.visible:await press("닫기 / 취소")
 note("seven_minute_resume_end");await screenshot("journey_final")
 app._performance_checkpoint()
 var final: Dictionary=app.game.snapshot();var path: String=app.save_path
 await press("저장 · 처음으로")
 var saved: Dictionary=app.store.read_game(path,app.OWNER,app.content.data)
 var save_equal: bool=saved.has("payload")
 if save_equal:
  for field in ["character","inventory","equipment","skills","hotkeys","stats","loot","quests"]:
   if app.store._canonical(saved.payload[field])!=app.store._canonical(final[field]):save_equal=false
 var restored=load("res://state/gameplay_state.gd").new();restored.configure(app.content.data)
 var restored_result: Dictionary=restored.restore(saved.get("payload",{}))
 save_equal=save_equal and restored_result.status=="OK" and app.store._canonical(restored.snapshot())==app.store._canonical(saved.get("payload",{}))
 var result:={"scope":"Final Windows embedded game PCK on Linux; unaccelerated 420s continuation automatic GUI operator, no XP/item/skill grants; not human or native Windows","status":"PASS_PLAY_SAVE" if save_equal and int(final.stats.kills)>0 and int(final.stats.items_picked_up)>0 and app.content.assets.errors.is_empty() else "FAIL","wall_seconds":float(Time.get_ticks_msec()-started)/1000.0,"milestones":milestones,"operator_failures":failures,"save_equal":save_equal,"save_path":path,"final":final,"trained":trained,"traded":traded,"return_learned":return_learned,"damage_cast":damage_cast,"asset_errors":app.content.assets.errors,"draw_errors":app.view.draw_errors}
 var f:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("LIVE_RESUME.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n")
 print("LIVE_JOURNEY "+JSON.stringify({"status":result.status,"wall_seconds":result.wall_seconds,"kills":final.stats.kills,"level":final.character.level,"skills":final.skills,"traded":traded,"trained":trained}));quit(0 if result.status=="PASS_PLAY_SAVE" else 1)
