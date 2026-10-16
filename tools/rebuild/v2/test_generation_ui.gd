extends SceneTree
## Real viewport + production UI actions. Mid/late characters are explicit fixtures.
var app
var checks: Array=[]
var failures:=0
var output: String
func check(id: String, ok: bool, detail: Variant=null) -> void:
 checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
 if not ok: failures+=1
func _initialize() -> void:
 output=OS.get_environment("BARAM_V2_UI_EVIDENCE")
 if output.is_empty() or not DirAccess.dir_exists_absolute(output):quit(2);return
 run.call_deferred()
func capture(name: String) -> void:
 await process_frame
 await RenderingServer.frame_post_draw
 var image:=root.get_texture().get_image()
 check(name+":framebuffer",image!=null and not image.is_empty())
 if image!=null and not image.is_empty():image.save_png(output.path_join(name+".png"))
func near(npc: Dictionary) -> bool:
 for offset in [Vector2i.DOWN,Vector2i.UP,Vector2i.LEFT,Vector2i.RIGHT]:
  var x: int=int(npc.x)+offset.x;var y: int=int(npc.y)+offset.y
  if app.game.valid_position(str(npc.map_id),x,y) and not app.game._occupied(str(npc.map_id),x,y):
   app.game.state.character.map_id=npc.map_id;app.game.state.character.x=x;app.game.state.character.y=y
   return true
 return false
func find_button(parent: Node, needle: String) -> Button:
 if parent is Button and needle in parent.text:return parent
 for child in parent.get_children():
  var found:=find_button(child,needle)
  if found:return found
 return null
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app)
 await process_frame;await process_frame
 check("content_and_engine_load",app.startup_error.is_empty(),app.startup_error)
 if not app.startup_error.is_empty():finish();return
 await capture("01-menu")
 app._show_creation();app.name_input.text="모험검증"+str(Time.get_ticks_msec()%10000)
 app._create_character();await process_frame
 check("ordinary_new_character_level1_no_skills",not app.game.state.is_empty() and int(app.game.state.character.level)==1 and app.game.state.skills.is_empty())
 var first_character: Dictionary=app.game.snapshot()
 check("ordinary_starter_saves",app.store.read_game(app.save_path,app.OWNER,app.content.data).has("payload"))
 await capture("02-start")
 # New content teacher list is data-driven, paged and uses real learning command.
 app.smoke=true
 for job in app.game.JOBS:
  var teacher_id: String=str(app.content.data.jobs[job].teacher_id)
  var npc: Dictionary=app.content.data.npcs[teacher_id]
  app.game.state=first_character.duplicate(true)
  app.save_failure=false
  app.save_path="user://gameplay-p3/v2-ui-fixtures/"+str(job).sha256_text().substr(0,12)+".json"
  var c: Dictionary=app.game.state.character
  c.job=job;c.level=99;c.xp=app.content.data.xp_thresholds[98] if app.content.data.xp_thresholds.size()>=99 else app.content.data.xp_thresholds[-1]
  c.money=1000000000;c.hp_max=5000;c.hp=5000;c.mp_max=5000;c.mp=5000
  check(job+":teacher_reachable_fixture",near(npc))
  app._show_dialogue(teacher_id);await process_frame
  check(job+":teacher_list_uses_data",app.dialogue_rows.size()>0)
  var learned: String=""
  for row in app.dialogue_rows:
   if row.command.type!="learn":continue
   var id:=str(row.command.skill_id);var definition: Dictionary=app.content.data.skills[id]
   if int(definition.get("required_advancement",0))>0 or definition.get("guardian")!=null and str(definition.guardian)!=str(c.guardian):continue
   for ingredient in definition.ingredients:app.game._add_item(str(ingredient),int(definition.ingredients[ingredient]))
   var result: Dictionary=app._dispatch(row.command)
   check(job+":real_UI_learning",result.status=="OK" and id in app.game.state.skills,result)
   learned=id;break
  check(job+":eligible_skill_exists",not learned.is_empty())
  app._show_dialogue(teacher_id);await process_frame
  if app.dialogue_rows.size()>app.DIALOGUE_PAGE_SIZE:
   var next:=find_button(app.dialogue_body,"다음")
   check(job+":pagination_next",next!=null and not next.disabled)
   if next:next.pressed.emit();await process_frame;check(job+":pagination_changes_page",app.dialogue_page==1)
  await capture("teacher-"+job)
  app.dialogue.hide()
  app.panels.current_tab=1;app._refresh_panels()
  check(job+":learned_skill_visible",app.skills.item_count>0)
 # All new service commands are exposed by their actual contracted NPC.
 for kind in ["recipes","advancements","quests"]:
  var collection: Dictionary=app.content.data.get(kind,{})
  check(kind+":available",not collection.is_empty())
  if collection.is_empty():continue
  var definition: Dictionary=collection.values()[0]
  var npc_id:=str(definition.get("npc_id",""))
  if kind=="advancements":npc_id=str(definition.get("teacher_ids",[""])[0])
  app._show_dialogue(npc_id);await process_frame
  var wanted: String={"recipes":"craft","advancements":"advance","quests":"quest_accept"}[kind]
  var count:=0
  for row in app.dialogue_rows:
   if str(row.command.type)==wanted:count+=1
  check(kind+":visible_UI_command",count>0)
 # Added facilities use actual production commands and disk persistence.
 app.dialogue.hide()
 var c: Dictionary=app.game.state.character
 c.level=99;c.xp=int(app.content.data.xp_thresholds[-1])+100000;c.money=1000000
 c.base_stats={"strength":20,"dexterity":20,"intelligence":20}
 for service in ["training","storage","weapon_naming"]:
  var npc_id: String=""
  for id in app.content.data.npcs:
   if service in app.content.data.npcs[id].get("services",[]):npc_id=str(id);break
  check(service+":NPC_exists",not npc_id.is_empty())
  if npc_id.is_empty():continue
  check(service+":near_NPC",near(app.content.data.npcs[npc_id]))
  if service=="storage":
   for slot in app.game.state.equipment.keys(): app._dispatch({"type":"unequip","slot":str(slot)})
  app._show_dialogue(npc_id);await process_frame
  var kind: String={"training":"train","storage":"store_deposit","weapon_naming":"rename_weapon"}[service]
  var row: Dictionary={}
  for candidate in app.dialogue_rows:
   if candidate.command.type==kind and not candidate.get("disabled",false):row=candidate;break
  check(service+":UI_command_present",not row.is_empty())
  if not row.is_empty():
   if service=="weapon_naming":
    check("naming:input_exists",is_instance_valid(app.weapon_name_input))
    app.weapon_name_input.text="모험의검"
    var button:=find_button(app.dialogue_body,str(row.label))
    check("naming:real_button_present",button!=null)
    if button:button.pressed.emit();await process_frame
    check("naming:persisted_custom_name",app.game.state.inventory.any(func(i):return i.get("custom_name","")=="모험의검"))
   else:
    var result: Dictionary=app._dispatch(row.command)
    check(service+":actual_command_and_save",result.status=="OK",result)
    if service=="storage":
     check("storage:bank_nonempty",not app.game.state.get("bank_inventory",[]).is_empty())
     app._show_dialogue(npc_id);await process_frame
     for withdraw in app.dialogue_rows:
      if withdraw.command.type=="store_withdraw":
       var taken: Dictionary=app._dispatch(withdraw.command)
       check("storage:withdraw_and_save",taken.status=="OK",taken);break
  await capture("service-"+service)
  app.dialogue.hide()
 # Representative region screenshots are explicit location fixtures.
 for region in ["부여성","쥐굴","극지방","일본"]:
  var map_id: String=""
  for id in app.content.data.maps:
   if region in str(app.content.data.maps[id].name):map_id=str(id);break
  check(region+":map_present",not map_id.is_empty())
  if map_id.is_empty():continue
  var definition: Dictionary=app.content.data.maps[map_id]
  var position: Vector2i=Vector2i(16,16)
  for spawn in definition.get("spawns",[]):position=Vector2i(spawn.x,spawn.y);break
  if not app.game.valid_position(map_id,position.x,position.y):
   var exit: Dictionary=definition.exits[0];position=Vector2i(exit.x,exit.y)
  var current: Dictionary=app.game.state.character
  current.map_id=map_id;current.x=position.x;current.y=position.y
  check(region+":actual_location_fixture",str(app.game.state.character.map_id)==map_id)
  app.visual_positions.clear();app.map_render_key="";app._refresh_panels();app._render_world()
  await capture("region-"+region)
 app.dialogue.hide()
 for extent in [Vector2i(1100,720),Vector2i(1600,900),Vector2i(600,960)]:
  root.size=extent;app.size=extent;app._resize_ui();await process_frame;await process_frame
  if extent.x<760 and not app.side.visible:app._toggle_panels();await process_frame
  for index in range(4):
   app.panels.current_tab=index;app._refresh_panels();app._render_world();await process_frame
   var rect: Rect2=app.panels.get_global_rect()
   check("layout:"+str(extent)+":"+str(index),rect.position.x>=0 and rect.position.y>=0 and rect.end.x<=float(app.size.x)+1 and rect.end.y<=float(app.size.y)+1 and app.view.size.x>=200 and app.view.size.y>=150,{"panel":rect,"view":app.view.size})
   if index==0:await capture("layout-"+str(extent.x)+"-"+str(extent.y))
 finish()
func finish() -> void:
 var result:={"status":"PASS" if failures==0 else "FAIL","checks":checks,"failures":failures,"runtime_generation":app.content.manifest.get("generation"),"scope":"Linux software OpenGL real GUI viewport and production commands; explicit mid/late fixtures, no natural1-99 or Android/Windows claim"}
 var file:=FileAccess.open(output.path_join("UI_RESULTS.json"),FileAccess.WRITE)
 file.store_string(JSON.stringify(result,"  ")+"\n");file.close()
 print("V2_UI "+JSON.stringify(result));quit(0 if failures==0 else 1)
