extends SceneTree
## Runtime asset render fixture; not native device/gameplay certification.
const Content = preload("res://content/gameplay_content.gd")
const View = preload("res://render/original_view.gd")
var content = Content.new()
var output := ""
var checks: Array = []
var captures: Array = []
func _initialize():
	output=OS.get_environment("BARAM_MAP_RENDER_OUTPUT")
	if output.is_empty() or not DirAccess.dir_exists_absolute(output): quit(2);return
	_run.call_deferred()
func check(id:String,pass_value:bool,detail:Dictionary={}):
	checks.append({"id":id,"pass":pass_value,"detail":detail})
	if not pass_value:printerr("FAIL "+id+" "+JSON.stringify(detail))
func _run():
	root.size=Vector2i(1000,760);root.content_scale_size=Vector2i(1000,760)
	check("runtime_open",content.open(OS.get_environment("BARAM_GAMEPLAY_RUNTIME")),{"errors":content.errors})
	if not checks[0].pass:quit(1);return
	var view=View.new();view.content=content.assets;view.position=Vector2(0,40);view.size=Vector2(1000,720);root.add_child(view)
	var title=Label.new();title.position=Vector2(14,5);title.add_theme_font_size_override("font_size",20);root.add_child(title)
	# An absent off-screen asset must never trigger a decoder/missing-file error.
	view.configure([{"path":"never-load-offscreen.png","x":4000,"y":4000,"width_px":100,"height_px":100}],Vector2(5000,5000),Vector2.ZERO,1)
	await process_frame;await process_frame;await RenderingServer.frame_post_draw
	check("offscreen_asset_culled_before_decode",content.assets.texture_decode_count==0 and content.assets.errors.is_empty())
	var edge_path="gameplay/world/objects/object-86.png"
	view.configure([{"path":edge_path,"x":-510,"y":0,"width_px":24,"height_px":96}],Vector2(1000,720),Vector2.ZERO,1)
	await process_frame;await process_frame;await RenderingServer.frame_post_draw
	check("partial_left_sprite_retained",edge_path in view.last_drawn and content.assets.texture_decode_count==1)
	# Header dimensions must agree with the decoded source, with no second decode.
	check("png_header_dimensions",content.assets.texture_size(edge_path)==Vector2(24,96) and content.assets.texture_decode_count==1)
	var index:=0
	for mid in content.data.maps:
		var m:Dictionary=content.data.maps[mid];var extent=Vector2(m.width*24,m.height*24)
		var layers:Array=m.get("ground_layers",[]).duplicate(true);var objects:Array=m.objects.duplicate(true)
		for object in objects:if not object.has("path"):object.path=object.frame_png
		# Place the existing NPC sprites in their real saved/runtime coordinates.
		for npc in content.data.npcs.values():
			if npc.map_id!=mid:continue
			var sample:Dictionary=content.actor(str(npc.get("look_id",npc.get("appearance_id","tavern"))),"standing",int(npc.get("direction",2)),0)
			if not sample.is_empty():
				var p=str(sample.path);if not p.begins_with("gameplay-assets/"):p="gameplay-assets/"+p
				objects.append({"path":p,"x":npc.x*24+12+sample.offset[0],"y":npc.y*24+24+sample.offset[1],"depth_y":(npc.y+1)*24})
		objects.sort_custom(func(a,b):return float(a.depth_y)<float(b.depth_y))
		layers.append_array(objects)
		title.text=str(m.name)+" · "+str(mid)+" · runtime render fixture"
		view.configure(layers,extent,extent*.5,minf(960/extent.x,680/extent.y))
		await process_frame;await process_frame;await RenderingServer.frame_post_draw
		var image=root.get_texture().get_image();var relative="map-%02d.png"%index;var saved=image.save_png(output.path_join(relative))
		check(str(mid)+":render",saved==OK and view.draw_errors.is_empty() and not view.last_drawn.is_empty(),{"layers":view.last_drawn.size(),"errors":view.draw_errors})
		captures.append({"map_id":mid,"name":m.name,"file":relative,"size":[image.get_width(),image.get_height()],"method":"Godot OriginalView frozen G1 real asset render fixture"});index+=1
	check("all_frozen_maps_rendered",captures.size()==76)
	var fail_count:=0
	for c in checks:if not c.pass:fail_count+=1
	var result={"status":"PASS_RUNTIME_RENDER_FIXTURE" if fail_count==0 else "FAIL","scope":"76 real runtime map/structure PNG frames through production OriginalView; no gameplay or native device claim","engine":Engine.get_version_info().string,"display":DisplayServer.get_name(),"checks":checks,"captures":captures,"decode_count":content.assets.texture_decode_count,"decode_usec":content.assets.texture_decode_usec,"cache_evictions":content.assets.texture_evictions,"native_platform":"NOT_RUN","normal_play":"NOT_RUN"}
	var f=FileAccess.open(output.path_join("map-render.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"\t")+"\n");f.close();print(JSON.stringify({"status":result.status,"maps":captures.size(),"failures":fail_count,"output":output}));quit(0 if fail_count==0 else 1)
