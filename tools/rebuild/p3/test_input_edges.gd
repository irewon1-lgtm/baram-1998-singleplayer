extends SceneTree
## Additional changed-input edge cases; fixture setup never presented as natural play.
var app
var checks: Array=[]
func _initialize() -> void:call_deferred("run")
func check(id: String,ok: bool,details: Variant=null) -> void:checks.append({"id":id,"status":"PASS" if ok else "FAIL","details":details})
func touch(index: int,position: Vector2,down: bool) -> void:
 var e:=InputEventScreenTouch.new();e.index=index;e.position=position;e.pressed=down;Input.parse_input_event(e);await process_frame
func drag(index: int,position: Vector2) -> void:
 var e:=InputEventScreenDrag.new();e.index=index;e.position=position;e.relative=Vector2(30,0);Input.parse_input_event(e);await process_frame
func button(text: String):
 var pending: Array=[app]
 while not pending.is_empty():
  var n: Node=pending.pop_front();pending.append_array(n.get_children())
  if n is Button and n.text==text and n.is_visible_in_tree():return n
 return null
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame
 app.name_input.text="경계"+str(Time.get_ticks_msec());app._create_character();await process_frame
 app.smoke=true
 var c: Dictionary=app.game.state.character;c.map_id="gp:map:south_field";c.x=16;c.y=16;c.direction=1
 var target:=""
 for id in app.game.state.monsters:
  var m: Dictionary=app.game.state.monsters[id];m.ai_at=100
  if target.is_empty() and m.map_id==c.map_id:target=id
 app.game.state.monsters[target].x=18;app.game.state.monsters[target].y=16
 app.selected_target="";app.visual_positions.clear();app.map_render_key="";app._render_world();await process_frame
 var start: Vector2=app.stick.global_position+app.stick.size*Vector2(.3,.5)
 await touch(0,start,true);await drag(0,start+Vector2(40,0))
 check("first_finger_keeps_east_intent",app.movement==Vector2i.RIGHT)
 var before: int=app.event_log.filter(func(e):return e.type=="attack_started").size()
 var attack=button("공격");var at: Vector2=attack.get_global_rect().get_center()
 await touch(1,at,true);await touch(1,at,false)
 var after: int=app.event_log.filter(func(e):return e.type=="attack_started").size()
 check("second_finger_attack_while_dragging",after>before,{"before":before,"after":after,"message":app.message.text})
 check("second_finger_release_does_not_cancel_first",app.stick.finger==0 and app.movement==Vector2i.RIGHT)
 await touch(0,start,false)
 check("both_fingers_release_stops",app.movement==Vector2i.ZERO and app.stick.finger==-1)
 await touch(3,start,true);await drag(3,start+Vector2(0,-40))
 await touch(4,start+Vector2(15,0),true);await drag(4,start+Vector2(-40,0))
 check("extra_world_finger_cannot_steer_active_stick",app.stick.finger==3 and app.movement==Vector2i.UP)
 await touch(4,start,false);await touch(3,start,false)
 for i in range(12):app.panels.current_tab=i%4;await process_frame
 check("rapid_tab_switch_keeps_game_state",not app.game.state.is_empty() and app.movement==Vector2i.ZERO)
 await touch(0,start,true);await drag(0,start+Vector2(40,0));app._show_map();await process_frame
 check("dialogue_open_cancels_held_motion",app.movement==Vector2i.ZERO and app.stick.finger==-1 and app.path.is_empty())
 await touch(0,start,false);app.dialogue.hide();await process_frame
 check("release_after_dialogue_has_no_world_tap",app.path.is_empty() and app.movement==Vector2i.ZERO)
 app._notification(Node.NOTIFICATION_APPLICATION_PAUSED);check("pause_clears_input",app.keyboard_moves.is_empty() and app.stick.finger==-1)
 var counts: Array=[0]
 var duplicate_button=app._button(app,"중복 시험",func(): counts[0]+=1)
 duplicate_button.position=Vector2(420,650);duplicate_button.size=Vector2(100,38);await process_frame
 var pos: Vector2=duplicate_button.get_global_rect().get_center()
 await touch(5,pos,true);await touch(5,pos,false)
 check("native_touch_action_once",counts[0]==1,counts[0])
 for down in [true,false]:
  var e:=InputEventMouseButton.new();e.device=InputEvent.DEVICE_ID_EMULATION;e.button_index=MOUSE_BUTTON_LEFT;e.position=pos;e.pressed=down;Input.parse_input_event(e);await process_frame
 check("emulated_mouse_does_not_duplicate_touch",counts[0]==1,counts[0])
 for down in [true,false]:
  var e:=InputEventMouseButton.new();e.button_index=MOUSE_BUTTON_LEFT;e.position=pos;e.pressed=down;Input.parse_input_event(e);await process_frame
 check("ordinary_mouse_action_still_works",counts[0]==2,counts[0])
 await touch(6,pos,true);app._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT);await touch(6,pos,false)
 check("focus_loss_cancels_pending_touch_action",counts[0]==2,counts[0])
 var result:={"status":"PASS" if checks.all(func(x):return x.status=="PASS") else "FAIL","scope":"final embedded PCK Linux Godot InputEvent screen-touch injection; explicit encounter fixture; not Android OS or fingers on hardware","checks":checks}
 var f:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("INPUT_EDGES.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n")
 print("INPUT_EDGES "+JSON.stringify(result));quit(0 if result.status=="PASS" else 1)
