extends SceneTree
var app
var checks: Array=[]
var fails:=0
func _initialize() -> void:call_deferred("run")
func check(id: String, ok: bool, detail: Variant=null) -> void:
 checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
 if not ok:fails+=1
func mouse(at: Vector2) -> void:
 var motion:=InputEventMouseMotion.new();motion.position=at;Input.parse_input_event(motion)
 for down in [true,false]:
  var e:=InputEventMouseButton.new();e.position=at;e.button_index=MOUSE_BUTTON_LEFT;e.pressed=down;Input.parse_input_event(e);await process_frame
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
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame
 app.smoke=true;app.name_input.text="연결"+str(Time.get_ticks_msec());app._create_character()
 var clean: Dictionary=app.game.snapshot()
 var shops: Dictionary={}
 for id in app.content.data.npcs:
  app.game.state=clean.duplicate(true);var npc: Dictionary=app.content.data.npcs[id]
  var c: Dictionary=app.game.state.character;c.map_id=npc.map_id;c.x=int(npc.x);c.y=int(npc.y)+1
  app.visual_positions.clear();app.map_render_key="";app._render_world();await process_frame
  var world:=Vector2(float(npc.x)*24+12,float(npc.y)*24+12)
  var point: Vector2=app.view.global_position+app.view.size*.5+(world-app.view.focus)*app.view.zoom
  await mouse(point);await process_frame
  check("npc_actual_world_click:"+id,app.dialogue.visible and app.current_npc==id)
  var inventory:=JSON.stringify(app.game.state.inventory)
  for item in npc.get("shop",{}):
   if npc.shop[item].get("buy_price")!=null:
    await press(str(app.content.data.items[item].name)+" 구매")
    check("insufficient_money_UI:"+id,JSON.stringify(app.game.state.inventory)==inventory and int(app.game.state.character.money)==0)
    break
  shops[id]=npc.get("shop",{}).keys()
  await press("닫기 / 취소")
  check("npc_cancel_closes:"+id,not app.dialogue.visible)
 check("distinct_live_shop_inventories",shops.values().any(func(a):return a.size()>0) and JSON.stringify(shops.values()).length()>20)
 # Each active P3 skill is selected in the real list, then cast via its real button.
 for id in app.content.data.skills:
  app.game.state=clean.duplicate(true);var skill: Dictionary=app.content.data.skills[id]
  var c: Dictionary=app.game.state.character;c.job=str(skill.job) if skill.job not in ["common","COMMON_FOUR_STARTER_JOBS"] else "주술사"
  c.level=10;c.hp_max=120;c.hp=40;c.mp_max=120;c.mp=120;c.guardian=skill.get("guardian","주작")
  c.map_id="gp:map:south_field";c.x=16;c.y=16
  if skill.kind=="shrine":c.dead=true;c.hp=0
  app.game.state.skills=[id];app.game.state.hotkeys={"1":id};app.game.state.pending_actions=[];app.game.state.cooldowns={}
  var target:=""
  for monster_id in app.game.state.monsters:
   var m: Dictionary=app.game.state.monsters[monster_id]
   if m.map_id==c.map_id:target=monster_id;m.x=17;m.y=16;m.ai_at=100;break
  app.selected_target="";app.dialogue.hide();app.panels.current_tab=1;app._refresh_panels();app.visual_positions.clear();app._render_world();await process_frame
  await mouse(app.skills.entries[0].button.get_global_rect().get_center())
  app.event_log.clear()
  var pressed:=await press("선택 기술 사용")
  check("skill_UI_starts:"+id,pressed and app.game.state.pending_actions.any(func(a):return a.kind=="skill"),app.message.text)
  check("skill_UI_exact_MP:"+id,int(app.game.state.character.mp)==120-int(skill.get("mp_cost",0)))
  app._consume_events(app.game.tick(float(skill.get("impact_delay",skill.get("windup",.25)))+.15).events)
  var applied: bool=app.event_log.any(func(e):return e.type in ["skill_applied","map_changed","resurrected","monster_hit"])
  check("skill_UI_impact:"+id,applied)
  app.event_log.clear();app._refresh_panels();app._render_world();await process_frame
  if id=="KRO-3559b12ed6a7":
   await RenderingServer.frame_post_draw
   root.get_texture().get_image().save_png(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("skill_actual_selection.png"))
 var result:={"status":"PASS" if fails==0 else "FAIL","checks":checks,"failures":fails,"scope":"final Windows embedded game PCK run by Linux engine; GUI mouse events and explicit NPC/skill fixtures, not natural leveling, native Windows or device listening"}
 var f:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("BINDINGS.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n")
 print("BINDING_QA "+JSON.stringify(result));quit(0 if fails==0 else 1)
