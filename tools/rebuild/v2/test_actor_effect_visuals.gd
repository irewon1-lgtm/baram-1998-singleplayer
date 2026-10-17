extends SceneTree
## Explicit production-render fixtures. No OS play, native device, historical exactness or art PASS.
const Effect = preload("res://render/effect_preview.gd")
var app
var out := OS.get_environment("BARAM_ACTOR_EFFECT_OUTPUT")
var checks: Array=[]
var captures: Array=[]
var sequence:=0
func _initialize(): run.call_deferred()
func check(id: String,ok: bool,detail: Variant=null):
 checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
 if not ok: printerr("FAIL "+id+" "+JSON.stringify(detail))
func capture(name: String,detail: Dictionary={}):
 if OS.get_environment("BARAM_ACTOR_EFFECT_PEAK_ONLY")=="1" and not name.ends_with("effect-peak"):return
 app._refresh_panels();app._render_world()
 await process_frame;await process_frame
 app._render_world() # Refresh camera/culling after the first UI layout, before evidence capture.
 await process_frame;await RenderingServer.frame_post_draw
 var image=root.get_texture().get_image()
 var file=name+".png"
 check(name+":framebuffer",image.save_png(out.path_join(file))==OK and app.view.draw_errors.is_empty(),app.view.draw_errors)
 var layers:Array=[]
 for entry in app.view.layers:
  if entry.get("path","") in app.view.last_drawn:
   layers.append({"runtime_path":entry.path,"world_top_left":[entry.get("x",0),entry.get("y",0)],"depth_y":entry.get("depth_y"),"original_frame":entry.get("original_frame"),"source_index":entry.get("source_index")})
 for entry in app.bag.entries:
  var button:Button=entry.button
  if not button.is_visible_in_tree() or button.icon==null or not button.get_global_rect().intersects(app.bag.get_global_rect()):continue
  var instance:Dictionary=app._instance(str(entry.metadata))
  if instance.is_empty():continue
  var icon:Dictionary=app.content.actors.icons.get(str(instance.item_id),{})
  if not icon.is_empty():layers.append({"runtime_path":"gameplay-assets/"+str(icon.path),"world_top_left":null,"screen_rect":[button.global_position.x,button.global_position.y,button.size.x,button.size.y],"consumer":"visible_bag_icon","item_id":instance.item_id,"original_frame":null})
 for layer in app.equipment_preview.layers:
  if layer.get("path","") in app.equipment_preview.last_drawn:layers.append({"runtime_path":layer.path,"world_top_left":null,"screen_rect":[app.equipment_preview.global_position.x,app.equipment_preview.global_position.y,app.equipment_preview.size.x,app.equipment_preview.size.y],"consumer":"visible_equipment_portrait","original_frame":null})
 captures.append({"file":file,"method":"Production gameplay.tscn rendered with explicit fixture state","map_id":app.game.state.character.map_id,"cell":[app.game.state.character.x,app.game.state.character.y],"character":app.game.state.character.duplicate(true),"look":app._look_player(),"visible_layers":layers,"detail":detail})
func base_fixture(job: String,weapon: String):
 app.game.state={};app.game.create_character("외형검수", "fixture:actor", {"seed":12})
 var c:Dictionary=app.game.state.character
 c.job=job;c.level=99;c.xp=app.content.data.xp_thresholds[98];c.hp_max=20000;c.mp_max=20000;c.hp=10000;c.mp=10000;c.dead=false;c.money=100000
 c.map_id="gp:map:south_field";c.x=25;c.y=25;c.direction=1
 app.game.state.skills=[]
 for id in app.content.data.skills:
  if app.content.data.skills[id].get("job")==job:app.game.state.skills.append(id)
 app.game.state.buffs={};app.game.state.monsters={};app.game.state.pending_actions=[]
 app.game.state.inventory.append({"instance_id":"fixture:weapon","item_id":weapon,"quantity":1,"durability":int(app.content.data.items[weapon].get("durability",100))})
 app.game.state.equipment.weapon="fixture:weapon"
 app.active_effects.clear();app.projectiles.clear();app.clock=0;app.visual_positions.clear();app.equipment_preview_look="";app.map_render_key="";app.runtime_monster_map="";app.runtime_monster_count=-1
 app._start_play();app.set_process(false)
func run():
 if out.is_empty():quit(2);return
 DirAccess.make_dir_recursive_absolute(out)
 if DisplayServer.get_name()=="headless":printerr("Display is required");quit(2);return
 root.size=Vector2i(1280,800)
 app=load("res://gameplay.tscn").instantiate();root.add_child(app)
 await process_frame;await process_frame
 check("runtime_open",app.startup_error.is_empty(),app.startup_error)
 if not app.startup_error.is_empty():finish();return
 app.set_process(false)
 var jobs=[{"job":"전사","weapon":"KRO-ITEM-064babaf513bd0","skill":"KRO-e5c1e3e5f6c4","label":"warrior"},{"job":"도적","weapon":"KRO-ITEM-99362a13fd3a63","skill":"KRO-21fea0f07142","label":"rogue"},{"job":"주술사","weapon":"KRO-ITEM-1626587b0529e5","skill":"KRO-3559b12ed6a7","label":"mage"},{"job":"도사","weapon":"KRO-ITEM-1b372e7e78b543","skill":"KRO-cce452629337","label":"poet"}]
 if OS.get_environment("BARAM_ACTOR_EFFECT_PEAK_ONLY")=="1":jobs=[jobs[0],jobs[2]]
 if OS.get_environment("BARAM_ACTOR_EFFECT_POISON_ONLY")=="1":jobs=[]
 if OS.get_environment("BARAM_ACTOR_EFFECT_REFRESH_FIRST")=="1":jobs=[jobs[0]]
 for row in jobs:
  base_fixture(row.job,row.weapon)
  for direction in ([0] if OS.get_environment("BARAM_ACTOR_EFFECT_REFRESH_FIRST")=="1" else range(4)):
   app.game.state.character.direction=direction
   app.character_animation="standing";app.animation_until=0;app.clock=0
   await capture(str(row.label)+"-direction-"+str(direction),{"job":row.job,"fixture":"Lv99/equipment/location, not natural progression","direction":direction})
  if OS.get_environment("BARAM_ACTOR_EFFECT_REFRESH_FIRST")=="1":break
  if not app.content.actors.get("shield_item_graphics",{}).is_empty():
   var shield_id:String=app.content.actors.shield_item_graphics.keys()[0]
   var base_look:String=app._look_player()
   app.game.state.inventory.append({"instance_id":"fixture:shield","item_id":shield_id,"quantity":1,"durability":int(app.content.data.items[shield_id].get("durability",100))})
   app.game.state.equipment.shield="fixture:shield"
   app.equipment_preview_look=""
   check(str(row.label)+":shield_selected",app._look_player()==base_look+"_shield",app._look_player())
   for direction in range(4):
    app.game.state.character.direction=direction
    await capture(str(row.label)+"-shield-direction-"+str(direction),{"fixture":"native Shield0 composed into player; exact item-to-part identity reconstructed","direction":direction})
    var frame:Dictionary=app.content.actor(app._look_player(),"standing",direction,0)
    check(str(row.label)+":shield_source_frame:"+str(direction),frame.source_frames.any(func(src):return src.get("epf")=="Shield.epf"),frame.source_frames)
   app.game.state.equipment.erase("shield");app.equipment_preview_look=""
   check(str(row.label)+":shield_unequip_restores_avatar",app._look_player()==base_look)
  app.game.state.character.direction=1
  app.character_animation="attack";app.animation_until=1;app.clock=0.14
  await capture(str(row.label)+"-attack",{"fixture":"attack animation sample at second native frame"})
  var monster_id=""
  for mid in app.content.data.monsters:
   if app.content.data.monsters[mid].get("look_id")=="rabbit":monster_id=mid;break
  if monster_id.is_empty():monster_id=app.content.data.monsters.keys()[0]
  app.game.state.monsters["fixture:target"]={"id":"fixture:target","generation":0,"aggro":false,"spawn_x":28,"spawn_y":25,"respawn_seconds":15,"monster_id":monster_id,"map_id":"gp:map:south_field","x":26 if row.job=="전사" else 28,"y":25,"hp":int(app.content.data.monsters[monster_id].hp),"alive":true,"ai_at":10000,"attack_at":10000,"respawn_at":0,"home_x":28,"home_y":25,"statuses":{}}
  app.active_effects.clear();app.projectiles.clear();app.clock=1
  var cmd={"type":"cast","skill_id":row.skill,"target_id":"fixture:target","request_id":"actorfixture:1"}
  var response:Dictionary=app.game.command(cmd)
  check(str(row.label)+":production_cast",response.status=="OK",response)
  app._consume_events(response.get("events",[]))
  await capture(str(row.label)+"-cast-start",{"command":cmd,"response":response,"fixture":"real skill definition under declared character and target fixtures"})
  var events:Array=[]
  var applied_capture:=false
  for step in range(16):
   app.clock+=0.05
   var tick:Dictionary=app.game.tick(0.05);events.append_array(tick.get("events",[]));app._consume_events(tick.get("events",[]))
   app._render_world()
   if not applied_capture and tick.get("events",[]).any(func(e):return e.get("type")=="skill_applied"):
    applied_capture=true
    if row.job in ["전사","주술사"]:
     check(str(row.label)+":impact_only_at_target",app.active_effects.size()==1 and int(app.active_effects[0].x)==int(app.game.state.monsters["fixture:target"].x),app.active_effects)
    await capture(str(row.label)+"-applied",{"events":tick.events,"active_effects":app.active_effects.duplicate(true)})
    app.clock+=0.12
    await capture(str(row.label)+"-effect-visible",{"fixture":"native effect sampled 120ms after actual applied event","active_effects":app.active_effects.duplicate(true)})
   if step==5:await capture(str(row.label)+"-impact",{"elapsed_after_cast":0.3,"events_so_far":events.duplicate(true)})
  check(str(row.label)+":skill_applied",events.any(func(e):return e.get("type")=="skill_applied") or response.events.any(func(e):return e.get("type")=="skill_applied"),events)
  if row.job=="도적":
   check("rogue:stealth_actual_opacity",app.view.layers.any(func(layer):return float(layer.get("opacity",1))==0.4))
  if row.job in ["전사","주술사"] and not app.active_effects.is_empty():
   app.clock=maxf(app.clock,float(app.active_effects[0].at)+(0.75 if row.job=="주술사" else 0.65))
   await capture(str(row.label)+"-effect-peak",{"fixture":"later native effect frame sampled after actual impact; no historical timing claim","active_effects":app.active_effects.duplicate(true)})
  app.clock+=10.1;app._render_world()
  check(str(row.label)+":effect_cleanup",app.active_effects.is_empty() and app.projectiles.is_empty(),{"active":app.active_effects.size(),"projectiles":app.projectiles.size()})
  await capture(str(row.label)+"-finished",{"fixture":"render clock advanced beyond native sequence duration","effects":app.active_effects.size(),"projectiles":app.projectiles.size()})
 # Targeted poison regression: visual feedback belongs to the affected monster.
 base_fixture("주술사","KRO-ITEM-1626587b0529e5")
 var poison_target_id:String="KRO-505b83a56a47"
 app.game.state.monsters["fixture:poison"]={"id":"fixture:poison","generation":0,"aggro":false,"spawn_x":28,"spawn_y":25,"respawn_seconds":15,"monster_id":poison_target_id,"map_id":"gp:map:south_field","x":28,"y":25,"hp":int(app.content.data.monsters[poison_target_id].hp),"alive":true,"ai_at":10000,"attack_at":10000,"respawn_at":0,"statuses":{}}
 app.game._indexed_monster_count=-1 # Explicit fixture directly changed the monster keyset without restore().
 var poison_response:Dictionary=app.game.command({"type":"cast","skill_id":"KRO-1ced02adeb42","target_id":"fixture:poison","request_id":"actorfixture:1"})
 check("poison:production_cast",poison_response.status=="OK",poison_response)
 app._consume_events(poison_response.get("events",[]))
 var poison_applied:=false
 for step in range(20):
  app.clock+=0.05
  var tick:Dictionary=app.game.tick(0.05);app._consume_events(tick.get("events",[]));app._render_world()
  if tick.get("events",[]).any(func(e):return e.get("type")=="status_applied"):
   poison_applied=true
   check("poison:only_target_effect",app.active_effects.size()==1 and int(app.active_effects[0].x)==28,app.active_effects)
   app.clock+=0.12
   await capture("mage-poison-target-effect",{"fixture":"real targeted poison skill under declared state; visual belongs to monster cell28,25"})
   break
 check("poison:status_applied",poison_applied)
 # Every loaded effect must select nonempty valid frames then finish, independent of historical skill binding.
 for eid in app.content.effects:
  var effect:Dictionary=app.content.effects[eid]
  var first:Dictionary=Effect.layers(effect,0.02)
  var last:Dictionary=Effect.layers(effect,10.1)
  check("effect:"+str(eid)+":bounded_frame",not first.finished and first.errors.is_empty() and last.finished,{"first_paths":first.paths,"scope":first.scope,"errors":first.errors})
 var ordering:Array=[{"fixture_role":"actor","depth_y":624.0}]
 app._append_depth_effect(ordering,{"back":[{"fixture_role":"back"}],"front":[{"fixture_role":"front"}]},624.0)
 ordering.sort_custom(func(a,b):return float(a.depth_y)<float(b.depth_y))
 check("synthetic_back_actor_front_depth_contract",ordering.map(func(row):return row.fixture_role)==["back","actor","front"],{"scope":"explicit synthetic layer-order contract; retained production effect set is front-only","order":ordering})
 finish()
func finish():
 var failed:=checks.filter(func(c):return c.status=="FAIL").size()
 var report={"schema":"baram.actor-effect.production-render-fixtures/1","status":"PASS_RENDER_FIXTURES_ONLY" if failed==0 else "FAIL","scope":"Production renderer/UI and real content under declared character/equipment/location/target/time fixtures; no OS input, natural progression, native platform or visual approval claim.","engine":Engine.get_version_info().string,"display":DisplayServer.get_name(),"checks":checks,"captures":captures,"failures":failed,"content_sha256":FileAccess.get_sha256(OS.get_environment("BARAM_GAMEPLAY_RUNTIME").path_join("gameplay_content.json")),"actor_index_sha256":FileAccess.get_sha256(OS.get_environment("BARAM_GAMEPLAY_RUNTIME").path_join("gameplay-assets/actors.json")),"ui_sha256":FileAccess.get_sha256("res://ui/gameplay.gd"),"visual_review":"NOT_RUN","ordinary_input":"NOT_RUN","native_platform":"NOT_RUN"}
 var f=FileAccess.open(out.path_join("ACTOR_EFFECT_FIXTURE.json"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  ")+"\n");f.close()
 print(JSON.stringify({"checks":checks.size(),"failures":failed,"captures":captures.size(),"output":out}));quit(0 if failed==0 else 1)
