extends SceneTree
## Isolated production-source wardrobe preview. Explicit fixtures, not OS play.
var app
var out:=OS.get_environment("BARAM_WARDROBE_OUTPUT")
var checks:Array=[]
var captures:Array=[]
var sequence:=0
func _initialize():run.call_deferred()
func check(id:String,ok:bool,detail:Variant=null):
 checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
 if not ok:printerr("FAIL "+id+" "+JSON.stringify(detail))
func capture(name:String):
 app._refresh_panels();app._render_world()
 await process_frame;await process_frame
 app._render_world()
 await process_frame;await RenderingServer.frame_post_draw
 check(name+":render",app.view.draw_errors.is_empty() and not app.view.last_drawn.is_empty(),app.view.draw_errors)
 var error=root.get_texture().get_image().save_png(out.path_join(name+".png"))
 check(name+":saved",error==OK,error)
 var mapped:Array=[]
 for layer in app.view.layers:
  if not layer.get("path","") in app.view.last_drawn:continue
  var pos:=Vector2(float(layer.get("x",0)),float(layer.get("y",0)))
  var screen:Vector2=app.view.global_position+app.view.size*0.5-app.view.focus*app.view.zoom+pos*app.view.zoom
  var extent:Vector2=app.view.content.texture_size(str(layer.path))*app.view.zoom*float(layer.get("scale",1.0))
  mapped.append({"runtime_path":layer.path,"world_top_left":[pos.x,pos.y],"screen_rect":[screen.x,screen.y,extent.x,extent.y],"consumer":"visible_world_layer"})
 for layer in app.equipment_preview.layers:
  if layer.get("path","") in app.equipment_preview.last_drawn:mapped.append({"runtime_path":layer.path,"world_top_left":null,"screen_rect":[app.equipment_preview.global_position.x,app.equipment_preview.global_position.y,app.equipment_preview.size.x,app.equipment_preview.size.y],"consumer":"visible_equipment_portrait"})
 captures.append({"file":name+".png","look":app._look_player(),"equipment":app.game.state.equipment.duplicate(true),"direction":app.game.state.character.direction,"fixture":"Lv99/equipment/location/time preconditions; production command, renderer and UI","method":"Production gameplay.tscn rendered with explicit wardrobe fixture state","map_id":app.game.state.character.map_id,"cell":[app.game.state.character.x,app.game.state.character.y],"visible_layers":mapped,"cape_look":app._cape_player_look()})
func command(type:String,extra:Dictionary):
 sequence+=1;var cmd:Dictionary={"type":type,"request_id":"wardrobe:"+str(sequence)};cmd.merge(extra);var r:Dictionary=app.game.command(cmd);app._consume_events(r.get("events",[]));app.equipment_preview_look="";check(type+":"+str(sequence),r.status=="OK",r);return r
func run():
 if out.is_empty():quit(2);return
 DirAccess.make_dir_recursive_absolute(out);root.size=Vector2i(1280,800)
 app=load("res://gameplay.tscn").instantiate();root.add_child(app)
 await process_frame;await process_frame
 check("startup",app.startup_error.is_empty(),app.startup_error)
 if not app.startup_error.is_empty():finish();return
 app.game.create_character("착용검수","fixture:wardrobe",{"seed":12});app.set_process(false)
 var c:Dictionary=app.game.state.character;c.job="전사";c.level=99;c.xp=app.content.data.xp_thresholds[98];c.base_stats={"strength":500,"dexterity":500,"intelligence":500};c.hp=1000;c.hp_max=1000;c.mp=500;c.mp_max=500;c.map_id="gp:map:south_field";c.x=25;c.y=25;c.direction=2
 app.game.state.monsters={};app.game._indexed_monster_count=-1;app.game.state.buffs={}
 for row in [["weapon","KRO-ITEM-064babaf513bd0"],["helmet","KRO-ITEM-8882b1b86ef50d"],["cape","KRO-ITEM-7c62b24d0dd205"]]:
  app.game.state.inventory.append({"instance_id":"fixture:"+row[0],"item_id":row[1],"quantity":1,"durability":int(app.content.data.items[row[1]].get("durability",100))})
 command("equip",{"instance_id":"fixture:weapon"});app._start_play();app.set_process(false)
 await capture("wardrobe-before")
 var starter_look:=str(app._look_player())
 for direction in range(4):
  app.game.state.character.direction=direction;await capture("starter-clothes-direction-"+str(direction))
 app.game.state.inventory.append({"instance_id":"fixture:armor","item_id":"gp:item:novice_armor","quantity":1,"durability":int(app.content.data.items["gp:item:novice_armor"].get("durability",100))})
 command("equip",{"instance_id":"fixture:armor"});check("armor-bound-look-changes",app._look_player()!=starter_look,{"starter":starter_look,"armor":app._look_player()});await capture("novice-armor-equipped")
 for direction in range(4):
  app.game.state.character.direction=direction;await capture("novice-armor-direction-"+str(direction))
 command("unequip",{"slot":"armor"});check("armor-unequip-look-returns",app._look_player()==starter_look);await capture("armor-unequipped")
 var starter_id:=""
 for item in app.game.state.inventory:
  if item.item_id=="gp:item:starter_clothes":starter_id=str(item.instance_id)
 if not starter_id.is_empty():command("equip",{"instance_id":starter_id})
 command("equip",{"instance_id":"fixture:helmet"});check("helmet-look-selected",app._look_player().ends_with("_helmet"),app._look_player())
 for direction in range(4):
  c=app.game.state.character;c.direction=direction;app.character_animation="standing";app.animation_until=0;app.clock=0
  await capture("helmet-direction-"+str(direction))
 command("equip",{"instance_id":"fixture:cape"});check("cape-visual-selected",not app._cape_player_look().is_empty(),app._cape_player_look())
 for direction in range(4):
  c=app.game.state.character;c.direction=direction;app.clock=0
  await capture("helmet-cape-direction-"+str(direction))
 for animation in ["walking","attack","casting"]:
  for direction in range(4):
   c=app.game.state.character;c.direction=direction;app.character_animation=animation;app.animation_until=100;app.clock=0.14
   await capture("helmet-cape-"+animation+"-"+str(direction))
 command("unequip",{"slot":"helmet"});check("helmet-unequip",not app._look_player().ends_with("_helmet"));await capture("cape-only-after-helmet-unequip")
 command("unequip",{"slot":"cape"});check("cape-unequip",not app.game.state.equipment.has("cape") and app._cape_player_look().is_empty());await capture("wardrobe-after-unequip")
 finish()
func finish():
 var failed:=checks.filter(func(c):return c.status=="FAIL").size();var report={"status":"PASS_ISOLATED_RENDER_FIXTURES"if failed==0 else"FAIL","scope":"Isolated production UI source and full runtime; explicit character/equipment/location/time fixtures, production equip/unequip commands; not OS input/native device/exact item history.","checks":checks,"captures":captures,"failures":failed,"actor_sha256":FileAccess.get_sha256(OS.get_environment("BARAM_GAMEPLAY_RUNTIME").path_join("gameplay-assets/actors.json")),"content_sha256":FileAccess.get_sha256(OS.get_environment("BARAM_GAMEPLAY_RUNTIME").path_join("gameplay_content.json")),"ui_sha256":FileAccess.get_sha256("res://ui/gameplay.gd"),"visual_approval":"NOT_RUN"};var f=FileAccess.open(out.path_join("WARDROBE_FIXTURE.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  ")+"\n");f.close();print(JSON.stringify({"checks":checks.size(),"captures":captures.size(),"failures":failed,"output":out}));quit(0 if failed==0 else 1)
