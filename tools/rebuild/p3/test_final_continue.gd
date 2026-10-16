extends SceneTree
## Separate process resumes the earned live character through the ordinary menu.
func _initialize() -> void:call_deferred("run")
func press(text: String) -> void:
 var pending: Array=[root]
 while not pending.is_empty():
  var node: Node=pending.pop_front();pending.append_array(node.get_children())
  if node is Button and node.is_visible_in_tree() and str(node.text).begins_with(text):
   for down in [true,false]:
    var e:=InputEventMouseButton.new();e.position=node.get_global_rect().get_center();e.button_index=MOUSE_BUTTON_LEFT;e.pressed=down;Input.parse_input_event(e);await process_frame
   return
 push_error("button not found: "+text)
func run() -> void:
 var app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame
 var expected_name:=OS.get_environment("BARAM_REPAIR_CHARACTER")
 if expected_name.is_empty():expected_name="실제동선53623"
 var index:=-1
 for i in range(app.names.item_count):
  if app.names.get_item_text(i).begins_with(expected_name):index=i;break
 if index<0:push_error("ordinary saved character missing");quit(1);return
 app.names.select(index)
 app._continue_character()
 var saved: Dictionary=app.store.read_game(app.save_path,app.OWNER,app.content.data)
 var exact: bool=saved.has("payload") and app.store._canonical(app.game.snapshot())==app.store._canonical(saved.payload)
 var report:={"status":"PASS" if exact else "FAIL","scope":"separate Linux Godot process executing final Windows embedded PCK; ordinary menu continuation of naturally earned save, no fixture grants; not native Windows or manual device","exact_after_menu_load":exact,"character":app.game.state.character,"equipment":app.game.state.equipment,"skills":app.game.state.skills,"stats":app.game.state.stats,"os_process_id":OS.get_process_id()}
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("ordinary_new_process_continued.png"))
 var f:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("CONTINUE.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  ")+"\n")
 await create_timer(2.0).timeout
 for down in [true,false]:
  var e:=InputEventKey.new();e.keycode=KEY_3;e.physical_keycode=KEY_3;e.pressed=down;Input.parse_input_event(e);await process_frame
 await create_timer(3.0).timeout
 await press("저장 · 처음으로");await create_timer(2.0).timeout
 for i in range(app.names.item_count):
  if app.names.get_item_text(i).begins_with(expected_name):app.names.select(i);break
 await press("이어 하기");await create_timer(2.0).timeout
 report["same_character_after_save_and_menu_continue"]=str(app.game.state.character.name)==expected_name
 report["after_return_character"]=app.game.state.character.duplicate()
 var final_report:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("CONTINUE.json"),FileAccess.WRITE);final_report.store_string(JSON.stringify(report,"  ")+"\n")
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("after_return_save_and_menu_continue.png"))
 print("ORDINARY_CONTINUE "+JSON.stringify(report));quit(0 if exact else 1)
