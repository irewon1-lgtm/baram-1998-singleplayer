extends SceneTree
## Affected-function UI/engine integration; fixture setup is explicitly isolated.
var app
var checks: Array=[]
var failures:=0
func check(id: String, ok: bool, detail: Variant=null) -> void:
 checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
 if not ok: failures+=1
func _initialize() -> void: call_deferred("run")
func key(code: int, down: bool=true) -> void:
 var e:=InputEventKey.new();e.physical_keycode=code;e.keycode=code;e.pressed=down
 Input.parse_input_event(e);await process_frame
func capture(name: String) -> void:
 await process_frame
 await RenderingServer.frame_post_draw
 var image:=root.get_texture().get_image()
 image.save_png(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join(name+".png"))
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app)
 await process_frame
 app.name_input.text="보수시험"+str(Time.get_ticks_msec()%10000)
 app._create_character();await process_frame
 check("ordinary_creation_Lv1_no_attack_skills",not app.game.state.is_empty() and app.game.state.character.level==1 and app.game.state.skills.is_empty())
 check("four_real_parchment_panels",app.panels.get_tab_count()==4 and app.bag.get_class()=="ScrollContainer" and app.equipment_preview!=null)
 for i in range(4):
  app.panels.current_tab=i;await capture("panel_"+str(i))
 check("equipment_uses_same_original_look",app.equipment_preview.layers.size()==1 and app.equipment_preview.layers[0].path.begins_with("gameplay-assets/"))
 var c: Dictionary=app.game.state.character
 var origin:=Vector2i(c.x,c.y)
 app._click_world(origin+Vector2i(0,5))
 for i in range(170):await process_frame
 c=app.game.state.character
 check("far_ground_tap_walks_multiple_tiles",Vector2i(c.x,c.y)!=origin and app.path.is_empty(),{"from":origin,"to":Vector2i(c.x,c.y),"message":app.message.text})
 app._stop_motion()
 await key(KEY_D);await create_timer(.65).timeout;await key(KEY_D,false)
 var stopped:=Vector2i(app.game.state.character.x,app.game.state.character.y)
 await create_timer(.4).timeout
 check("held_key_release_no_ghost_steps",stopped==Vector2i(app.game.state.character.x,app.game.state.character.y))
 # Real touch events through the production stick, including rotation and cancellation.
 var point: Vector2=app.stick.global_position+app.stick.size*Vector2(.3,.5)
 var touch:=InputEventScreenTouch.new();touch.index=2;touch.position=point;touch.pressed=true
 Input.parse_input_event(touch);await process_frame
 var drag:=InputEventScreenDrag.new();drag.index=2;drag.position=point+Vector2(45,0);drag.relative=Vector2(45,0)
 Input.parse_input_event(drag);await process_frame
 check("touch_drag_sets_east",app.movement==Vector2i.RIGHT)
 drag=InputEventScreenDrag.new();drag.index=2;drag.position=point+Vector2(0,-45);drag.relative=Vector2(-45,-45)
 Input.parse_input_event(drag);await process_frame
 check("same_finger_rotates_north",app.movement==Vector2i.UP)
 touch=InputEventScreenTouch.new();touch.index=2;touch.position=point;touch.pressed=false
 Input.parse_input_event(touch);await process_frame
 check("touch_release_clears_intent",app.movement==Vector2i.ZERO and app.stick.finger==-1)
 app._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
 check("focus_loss_clears_all_intents",app.path.is_empty() and app.keyboard_moves.is_empty() and app.movement==Vector2i.ZERO)
 # Fixture: position next to a real existing spawn. No target ID is supplied to attack.
 app.smoke=true;app.game.state.pending_actions=[];app.game.state.cooldowns={}
 var target_id:=""
 for id in app.game.state.monsters:
  var m: Dictionary=app.game.state.monsters[id]
  if m.map_id=="gp:map:south_field":target_id=id;break
 var m: Dictionary=app.game.state.monsters[target_id]
 c=app.game.state.character;c.map_id=m.map_id;c.x=int(m.x)-1;c.y=m.y;c.direction=1
 app.selected_target="";app.visual_positions.clear();app.map_render_key="";app._render_world()
 app.game.state.monsters[target_id].ai_at=float(app.game.state.sim_time)+5.0
 var hp_before:=int(m.hp)
 await key(KEY_SPACE);await key(KEY_SPACE,false)
 check("space_without_selection_starts_real_attack",app.game.state.pending_actions.size()==1 and int(app.game.state.monsters[target_id].hp)==hp_before)
 app._consume_events(app.game.tick(.2).events)
 check("delayed_attack_decreases_HP",int(app.game.state.monsters[target_id].hp)<hp_before)
 var hp_after:=int(app.game.state.monsters[target_id].hp)
 await key(KEY_SPACE);await key(KEY_SPACE,false)
 check("cooldown_no_double_hit",int(app.game.state.monsters[target_id].hp)==hp_after and app.game.state.pending_actions.filter(func(a): return a.kind=="attack").is_empty(),app.game.state.pending_actions)
 for i in range(12):
  if not app.game.state.monsters[target_id].alive:break
  app._consume_events(app.game.tick(.6).events)
  # Follow only by the production move engine; the target can move while retaliating.
  var target: Dictionary=app.game.state.monsters[target_id]
  if app.game._distance(target,app.game.state.character)>1:
   app._navigate(Vector2i(target.x,target.y),1)
   for j in range(8):app._consume_events(app.game.tick(.2).events);app._advance_movement()
  await key(KEY_SPACE);await key(KEY_SPACE,false)
  app._consume_events(app.game.tick(.2).events)
 check("death_and_XP_chain",not app.game.state.monsters[target_id].alive and int(app.game.state.stats.kills)>=1 and int(app.game.state.character.xp)>0)
 check("no_dead_monster_retarget",app.game._target(target_id,1).is_empty())
 await capture("hunt_damage_and_loot")
 if not app.game.state.loot.is_empty():
  var loot: Dictionary=app.game.state.loot[0]
  app._navigate(Vector2i(loot.x,loot.y),1)
  for j in range(8):app._consume_events(app.game.tick(.2).events);app._advance_movement()
  var count:=int(app.game.state.stats.items_picked_up)
  await key(KEY_Z);await key(KEY_Z,false)
  check("pickup_key_adds_owned_loot",int(app.game.state.stats.items_picked_up)>count)
 else:check("pickup_fixture_drop_available",false,"Seeded first encounter produced no drop; retain observed failure")
 var snapshot: Dictionary=app.game.snapshot()
 app.game.state.character.map_id="gp:map:domestic_city";app.game.state.character.x=32;app.game.state.character.y=36
 app.game.state.cooldowns={};app.selected_target="";app.game.state.pending_actions=[]
 var response: Dictionary=app.game.command({"type":"attack","request_id":"negative:1"})
 check("empty_city_reports_no_target",response.reason=="NO_NEARBY_TARGET")
 response=app.game.command({"type":"attack","target_id":target_id,"request_id":"negative:2"})
 check("explicit_remote_target_refused",response.status=="REFUSED")
 check("exit_directions_not_string_to_zero",app.game._direction_value("east")==1 and app.game._direction_value("west")==3 and app.game._direction_value("south")==2 and app.game._direction_value("north")==0)
 app.game.state=snapshot;app.save_path="user://gameplay-p3/tests/remediation-"+str(Time.get_unix_time_from_system())+".json"
 check("changed_UI_combat_save_writes",app._save())
 var loaded: Dictionary=app.store.read_game(app.save_path,app.OWNER,app.content.data)
 check("changed_UI_combat_roundtrip_exact",loaded.has("payload") and app.store._canonical(loaded.payload)==app.store._canonical(app.game.snapshot()))
 # Old actual natural-save compatibility is read-only; schema is unchanged.
 var old:=OS.get_environment("BARAM_REPAIR_OLD_SAVE")
 if not old.is_empty():
  var copy_path:="user://gameplay-p3/tests/old-p3-readonly-copy.json"
  DirAccess.copy_absolute(old,ProjectSettings.globalize_path(copy_path))
  check("old_save_copy_hash_matches",FileAccess.get_sha256(old)==FileAccess.get_sha256(copy_path))
  var read: Dictionary=app.store.read_game(copy_path,"p3-natural-operator",app.content.data)
  check("old_P3_save_remains_readable",read.has("payload"),read.status)
 app._refresh_panels();app._render_world();await capture("final")
 check("no_asset_reference_errors",app.content.assets.errors.is_empty() and app.view.draw_errors.is_empty(),app.content.assets.errors)
 app._performance_checkpoint()
 var result:={"scope":"Linux GUI real Godot InputEvent injection; explicitly positioned encounter fixture; not human, Galaxy, nativeWindows or OS IME","status":"PASS" if failures==0 else "FAIL","checks":checks,"failures":failures,"generation":app.content.manifest.generation}
 var file:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("RESULTS.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n");file.close()
 print("REPAIR_QA "+JSON.stringify(result));quit(0 if failures==0 else 1)
