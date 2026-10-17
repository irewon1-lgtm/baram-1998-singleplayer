extends SceneTree
var app
var checks: Array=[]
var failures:=0
var out:=OS.get_environment("BARAM_G2_UI_OUTPUT")
func check(id: String,ok: bool,detail: Variant=null) -> void:
 checks.append({"id":id,"status":"PASS"if ok else"FAIL","detail":detail})
 if not ok:failures+=1
func _initialize():run.call_deferred()
func run():
 DirAccess.make_dir_recursive_absolute(out)
 root.size=Vector2i(1100,720)
 app=load("res://gameplay.tscn").instantiate();root.add_child(app)
 await process_frame;await process_frame
 check("startup",app.startup_error.is_empty(),app.startup_error)
 if not app.startup_error.is_empty():finish();return
 app._show_creation();app.name_input.text="확장화면시험";app._create_character();app.set_process(false)
 check("level1_plain_no_skills",int(app.game.state.character.level)==1 and app.game.state.skills.is_empty())
 var targets: Array=[]
 for mid in app.content.data.g2_world.city_maps:targets.append({"mid":mid,"point":Vector2i(110,176)});targets.append({"mid":mid,"point":Vector2i(60,45)})
 for mid in app.content.data.g2_world.fields:targets.append({"mid":mid,"point":Vector2i(22,20)})
 for ids in app.content.data.g2_world.dungeon_families:targets.append({"mid":ids[-1],"point":Vector2i(70,65)})
 targets.append({"mid":"gp:map:tavern","point":Vector2i(10,14)})
 var n:=0
 for row in targets:
  var mid:=str(row.mid);var c: Dictionary=app.game.state.character
  c.map_id=mid;c.x=row.point.x;c.y=row.point.y
  app.game._spawn_map(mid);app.runtime_monster_map="";app.map_render_key="";app._close_dialogue();app._render_world()
  await process_frame;await process_frame;await RenderingServer.frame_post_draw
  check(mid+":render",app.view.draw_errors.is_empty() and not app.view.last_drawn.is_empty() and app.content.assets.errors.is_empty(),app.view.draw_errors)
  if n<6 or n%4==0:root.get_texture().get_image().save_png(out.path_join("world-%02d.png"%n))
  if n<2 or mid=="gp:map:tavern":
   app._show_map();await process_frame;await process_frame;await RenderingServer.frame_post_draw
   root.get_texture().get_image().save_png(out.path_join("map-%02d.png"%n))
   var map: Dictionary=app.content.data.maps[mid]
   var path:=str(map.get("overview_png",map.get("floor_png","")))
   check(mid+":map_texture_present",not path.is_empty() and path in app.content.assets.textures)
   app._close_dialogue()
  check(mid+":bounded_texture_cache",app.content.assets.texture_pixels<=app.content.assets.MAX_TEXTURE_PIXELS,app.content.assets.texture_pixels)
  n+=1
 finish()
func finish():
 var d={"status":"PASS"if failures==0 else"FAIL","scope":"Production UI and renderer with explicit location fixtures; not OS play, physical Windows/Android or visual perfection.","checks":checks,"failures":failures,"source_ui_sha256":FileAccess.get_sha256("res://ui/gameplay.gd")}
 var f=FileAccess.open(out.path_join("GUI.json"),FileAccess.WRITE);f.store_string(JSON.stringify(d,"  "))
 print(JSON.stringify({"checks":checks.size(),"failures":failures}));quit(0 if failures==0 else 1)
