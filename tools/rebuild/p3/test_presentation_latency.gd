extends SceneTree
var app
func _initialize() -> void:call_deferred("run")
func run() -> void:
 app=load("res://gameplay.tscn").instantiate();root.add_child(app);await process_frame
 app.name_input.text="표출"+str(Time.get_ticks_msec());app._create_character();await create_timer(.5).timeout
 var samples: Array=[]
 for i in range(6):
  await create_timer(.35).timeout;await RenderingServer.frame_post_draw
  var rect:=Rect2i(app.view.get_global_rect())
  var before: PackedByteArray=root.get_texture().get_image().get_region(rect).get_data()
  var old: int=app.game.state.character.x
  var key:=KEY_D if i%2==0 else KEY_A
  var event:=InputEventKey.new();event.keycode=key;event.physical_keycode=key;event.pressed=true
  var started:=Time.get_ticks_usec();Input.parse_input_event(event)
  var found:=-1.0
  for frame in range(12):
   await RenderingServer.frame_post_draw
   var pixels: PackedByteArray=root.get_texture().get_image().get_region(rect).get_data()
   if pixels!=before and int(app.game.state.character.x)!=old:
    found=float(Time.get_ticks_usec()-started)/1000.0;break
  event=InputEventKey.new();event.keycode=key;event.physical_keycode=key;event.pressed=false;Input.parse_input_event(event)
  samples.append(found)
 var sorted:=samples.duplicate();sorted.sort()
 var result:={"status":"PASS_CAPTURED_HOST_RENDER_LATENCY" if samples.all(func(x):return x>=0.0) else "FAIL","scope":"Final ZIP embedded PCK, Linux GUI keyboard InputEvent injection to first changed world render-buffer readback while logical tile moves; includes readback overhead. Not OS touch, physical presentation/photons or Galaxy. Six samples only, not certification.","samples_ms":samples,"p50_ms":sorted[2],"p95_ms":sorted[5],"p99_ms":sorted[5]}
 var f:=FileAccess.open(OS.get_environment("BARAM_REPAIR_EVIDENCE").path_join("PRESENTATION_LATENCY.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n");print("PRESENTATION_LATENCY "+JSON.stringify(result));quit(0 if str(result.status).begins_with("PASS") else 1)
