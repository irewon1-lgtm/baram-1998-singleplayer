extends SceneTree
## Explicit source-art fixture, not OS play/progression.
var app
var out:=OS.get_environment("BARAM_ANIMAL_OUTPUT")
var checks:Array=[]
var captures:Array=[]
func _initialize():run.call_deferred()
func check(id:String,ok:bool,detail:Variant=null):
 checks.append({"id":id,"status":"PASS"if ok else"FAIL","detail":detail})
 if not ok:printerr("FAIL "+id+" "+JSON.stringify(detail))
func capture(name:String):
 app._refresh_panels();app._render_world();await process_frame;await process_frame;app._render_world();await process_frame;await RenderingServer.frame_post_draw
 var err=root.get_texture().get_image().save_png(out.path_join(name+".png"));check(name,err==OK and app.view.draw_errors.is_empty(),app.view.draw_errors)
 var mapped:Array=[]
 for layer in app.view.layers:
  if not layer.get("path","") in app.view.last_drawn:continue
  var pos:=Vector2(float(layer.get("x",0)),float(layer.get("y",0)))
  var screen:Vector2=app.view.global_position+app.view.size*0.5-app.view.focus*app.view.zoom+pos*app.view.zoom
  var extent:Vector2=app.view.content.texture_size(str(layer.path))*app.view.zoom*float(layer.get("scale",1.0))
  mapped.append({"runtime_path":layer.path,"world_top_left":[pos.x,pos.y],"screen_rect":[screen.x,screen.y,extent.x,extent.y],"consumer":"visible_world_layer"})
 captures.append({"file":name+".png","method":"Production gameplay.tscn; explicit Lv99/location/direction/animation/monster fixtures","map_id":app.game.state.character.map_id,"cell":[app.game.state.character.x,app.game.state.character.y],"visible_layers":mapped})
func run():
 if out.is_empty():quit(2);return
 DirAccess.make_dir_recursive_absolute(out);root.size=Vector2i(1280,800);app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame;await process_frame;check("startup",app.startup_error.is_empty(),app.startup_error)
 if not app.startup_error.is_empty():finish();return
 app.game.create_character("동물외형검수","fixture:animals",{"seed":12});app.set_process(false)
 var c:Dictionary=app.game.state.character;c.job="주술사";c.level=99;c.xp=app.content.data.xp_thresholds[98];c.hp=1000;c.hp_max=1000;c.mp=500;c.mp_max=500;c.map_id="gp:map:south_field";c.x=25;c.y=25;c.direction=2;app.game.state.buffs={};app.game.state.monsters={};app.game._indexed_monster_count=-1
 for row in [["bear","KRO-041db4baede3",23,25],["tiger","KRO-50723002e976",28,25],["fox","KRO-250e75d268a9",23,28],["rabbit","KRO-06cd08f5f573",28,28]]:
  var def:Dictionary=app.content.data.monsters[row[1]];app.game.state.monsters[row[0]]={"id":row[0],"monster_id":row[1],"generation":0,"aggro":false,"spawn_x":row[2],"spawn_y":row[3],"map_id":c.map_id,"x":row[2],"y":row[3],"hp":def.hp,"alive":true,"ai_at":10000,"attack_at":10000,"respawn_at":0,"statuses":{}}
 app._start_play();app.set_process(false);app.clock=0
 for direction in range(4):
  for key in app.game.state.monsters:app.actor_directions[key]=direction
  await capture("animals-standing-"+str(direction))
 for action in ["walking","attack"]:
  for direction in range(4):
   for key in app.game.state.monsters:
    app.actor_directions[key]=direction
    if action=="attack":app.actor_animations[key]=100;app.actor_walk_until[key]=0
    else:app.actor_animations[key]=0;app.actor_walk_until[key]=100
   app.clock=0.14;await capture("animals-"+action+"-"+str(direction))
 for row in [["KRO-f0736521bc85","_color0"],["KRO-fd3d2a8837c3","_color4"],["KRO-06cd08f5f573","_color10"],["KRO-a95162808c08","_color11"]]:check("alias:"+row[0],app._monster_look(row[0]).ends_with(row[1]),app._monster_look(row[0]))
 var unresolved:Array=[]
 for id in app.content.data.monsters:
  var result:=str(app._monster_look(str(id)))
  if not app.content.actors.looks.has(result):unresolved.append({"id":id,"look":result})
 check("all-monster-alias-fallbacks",unresolved.is_empty(),{"definitions":app.content.data.monsters.size(),"unresolved":unresolved})
 app.game.state.buffs={"fixture:polymorph":{"form_monster_id":"KRO-06cd08f5f573"}}
 app.game.state.summons=[{"id":"fixture:white-fox-summon","monster_id":"KRO-a95162808c08","map_id":app.game.state.character.map_id,"x":25,"y":28}]
 check("polymorph-uses-entity-alias",app._look_player()==app._monster_look("KRO-06cd08f5f573"),app._look_player())
 for key in app.game.state.monsters:app.actor_animations[key]=0;app.actor_walk_until[key]=0;app.actor_directions[key]=2
 app.game.state.character.direction=2;app.clock=0
 await capture("animal-polymorph-and-summon-alias")
 finish()
func finish():
 var failed:=checks.filter(func(c):return c.status=="FAIL").size();var report={"schema":"baram.common-animals.render-fixtures/1","status":"PASS_RENDER_FIXTURES_ONLY"if failed==0 else"FAIL","scope":"Explicit character/location/monster/direction/time fixtures; production renderer, not OS input/natural/native platform/historical species identity.","captures":captures,"checks":checks,"failures":failed,"content_sha256":FileAccess.get_sha256(OS.get_environment("BARAM_GAMEPLAY_RUNTIME").path_join("gameplay_content.json")),"actor_sha256":FileAccess.get_sha256(OS.get_environment("BARAM_GAMEPLAY_RUNTIME").path_join("gameplay-assets/actors.json")),"ui_sha256":FileAccess.get_sha256("res://ui/gameplay.gd"),"human_visual_review":"NOT_RUN"};var f=FileAccess.open(out.path_join("COMMON_ANIMAL_FIXTURE.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  ")+"\n");f.close();print(JSON.stringify({"checks":checks.size(),"failures":failed,"captures":captures.size()}));quit(0 if failed==0 else 1)
