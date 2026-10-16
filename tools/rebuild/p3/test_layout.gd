extends SceneTree
var app
var checks: Array=[]
var failures:=0
func _initialize() -> void:call_deferred("run")
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame
 app.name_input.text="화면"+str(Time.get_ticks_msec());app._create_character();app.smoke=true
 for extent in [Vector2i(1100,720),Vector2i(1280,800),Vector2i(600,960)]:
  root.size=extent;app.size=extent;app._resize_ui();await process_frame;await process_frame
  if extent.x<760:app._toggle_panels();await process_frame
  for index in range(4):
   app.panels.current_tab=index;app._refresh_panels();app._render_world();await process_frame
   var rect: Rect2=app.panels.get_global_rect()
   var okay: bool=rect.position.x>=0 and rect.position.y>=0 and rect.end.x<=float(app.size.x)+1 and rect.end.y<=float(app.size.y)+1 and app.view.size.x>=200 and app.view.size.y>=150
   checks.append({"size":extent,"panel":index,"status":"PASS" if okay else "FAIL","rect":rect,"view":app.view.size})
   if not okay:failures+=1
   await RenderingServer.frame_post_draw
   root.get_texture().get_image().save_png(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("layout_"+str(extent.x)+"_"+str(extent.y)+"_"+str(index)+".png"))
 var result:={"status":"PASS" if failures==0 else "FAIL","checks":checks,"failures":failures,"scope":"Linux GUI viewport simulations, not physical phone/tablet"}
 var f:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("LAYOUT.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n")
 print("LAYOUT_QA "+JSON.stringify(result));quit(0 if failures==0 else 1)
