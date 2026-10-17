extends SceneTree
## Rendered storage profiling fixture; direct setup/ticks are not OS gameplay.
var app
var samples: Array=[]
var output:=OS.get_environment("BARAM_STORAGE_GUI_OUT")
func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(output)
	run.call_deferred()
func percentile(values: Array, fraction: float) -> float:
	if values.is_empty(): return -1
	var ordered:=values.duplicate();ordered.sort()
	return float(ordered[mini(ordered.size()-1,int(ceil(fraction*ordered.size()))-1)])
func run() -> void:
	app=load("res://gameplay.tscn").instantiate();root.add_child(app)
	await process_frame;await process_frame
	if not app.startup_error.is_empty():print("PROFILE_STARTUP_FAIL "+str(app.startup_error));quit(2);return
	app.smoke=true
	var created: Dictionary=app.game.create_character("저장실측",app.OWNER,{"nationality":"고구려","guardian":"주작"})
	if created.status!="OK":print("PROFILE_CREATE_FAIL "+str(created));quit(2);return
	app.save_path="user://gameplay-p3/gui-profile/"+str(Time.get_ticks_usec())+".json"
	app._start_play()
	await create_timer(2.0).timeout
	for index in range(96):
		if index==32:
			var map: Dictionary=app.content.data.maps["gp:map:north_field"]
			var point: Dictionary=map.spawns[0]
			app.game.state.character.map_id="gp:map:north_field"
			app.game.state.character.x=int(point.x)+1;app.game.state.character.y=int(point.y)
			if not app.game.valid_position("gp:map:north_field",int(point.x)+1,int(point.y)):
				app.game.state.character.x=int(point.x);app.game.state.character.y=int(point.y)
			app.game.state.revision+=1
			app.map_render_key="";app.panel_dirty=true
			await create_timer(1.0).timeout
		app._consume_events(app.game.tick(0.2).get("events",[]))
		var started:=Time.get_ticks_usec()
		var ok: bool=app._save()
		var elapsed:=float(Time.get_ticks_usec()-started)/1000.0
		samples.append({"index":index,"map_id":app.game.state.character.map_id,"saved":ok,"outer_save_ms":elapsed,"phases":app.store.last_timings.duplicate(true)})
		if not ok:print("PROFILE_SAVE_FAIL "+str(app.save_receipts[-1]));break
		await process_frame;await process_frame
		await create_timer(0.08).timeout
	var durations: Array=[]
	var phase_samples: Dictionary={}
	var over100:=0
	for sample in samples:
		durations.append(sample.outer_save_ms)
		if sample.outer_save_ms>100:over100+=1
		for key in sample.phases:
			if not phase_samples.has(key):phase_samples[key]=[]
			phase_samples[key].append(sample.phases[key])
	var phase_summary: Dictionary={}
	for key in phase_samples:phase_summary[key]={"p50":percentile(phase_samples[key],0.5),"p95":percentile(phase_samples[key],0.95),"max":percentile(phase_samples[key],1.0)}
	var report: Dictionary={"schema":"baram.b5.gui-save-profile/1","scope":"Linux Godot4.6.3 rendered GUI + 1600x1000 Xvfb + ffmpeg15fps; direct character/map/tick fixture and production UI _save, not normal OS input/play/device proof","samples":samples,"count":samples.size(),"outer_save_ms":{"p50":percentile(durations,0.5),"p95":percentile(durations,0.95),"max":percentile(durations,1.0),"over100":over100},"phase_summary":phase_summary,"source_store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd"),"source_engine_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"source_ui_sha256":FileAccess.get_sha256("res://ui/gameplay.gd"),"status":"PASS_PROFILE_COMPLETED" if samples.size()==96 else "FAIL"}
	var file:=FileAccess.open(output.path_join("gui-save-profile.json"),FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	root.get_texture().get_image().save_png(output.path_join("final-frame.png"))
	print(JSON.stringify({"count":samples.size(),"outer_save_ms":report.outer_save_ms,"phases":phase_summary}))
	quit(0 if samples.size()==96 else 1)
