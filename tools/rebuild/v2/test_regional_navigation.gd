extends SceneTree
## Accelerated explicit location fixture through production GridNavigation/move.
## Monster records retained, but marked dead so this isolates passage geometry.
const State=preload("res://state/gameplay_state.gd")
const Nav=preload("res://input/grid_navigation.gd")
var checks:Array=[]
var steps:=0
var failures:=0
func check(id:String,good:bool,detail:Variant=null):
	checks.append({"id":id,"pass":good,"detail":detail})
	if not good:failures+=1;printerr("FAIL "+id+" "+str(detail))
func _initialize():run.call_deferred()
func run():
	var runtime=OS.get_environment("BARAM_GAMEPLAY_RUNTIME")
	var data:Dictionary=JSON.parse_string(FileAccess.get_file_as_string(runtime.path_join("gameplay_content.json")))
	var game=State.new();check("production_engine_configure",game.configure(data),game.errors)
	if not game.errors.is_empty():finish();return
	check("create_character",game.create_character("지형시험","fixture:regional",{"seed":471}).status=="OK")
	for monster in game.state.monsters.values():monster.alive=false
	for mid in data.maps:
		var m:Dictionary=data.maps[mid]
		if not m.has("regional_layout"):continue
		var starts:Array=m.spawns.duplicate()
		if starts.is_empty():
			for other in data.maps.values():
				for exit in other.exits:
					if exit.to_map==mid:starts.append({"x":exit.to_x,"y":exit.to_y});break
				if not starts.is_empty():break
		if starts.is_empty():check(str(mid)+":fixture_start",false);continue
		for e in m.exits:
			var c:Dictionary=game.state.character;c.map_id=mid;c.x=starts[0].x;c.y=starts[0].y;c.level=99
			var route:Array=Nav.route(game,Vector2i(e.x,e.y))
			check(str(mid)+":"+str(e.id)+":route",not route.is_empty(),{"from":[c.x,c.y],"to":[e.x,e.y],"length":route.size()})
			if route.is_empty():continue
			var ok:=true;var reason:Dictionary={}
			for next in route:
				game.state.cooldowns.clear()
				var cmd={"type":"move","dx":next.x-int(game.state.character.x),"dy":next.y-int(game.state.character.y),"request_id":"regional:"+str(steps+1)}
				steps+=1;reason=game.command(cmd)
				if reason.status!="OK":ok=false;break
			check(str(mid)+":"+str(e.id)+":production_move_and_transition",ok and game.state.character.map_id==e.to_map and int(game.state.character.x)==int(e.to_x) and int(game.state.character.y)==int(e.to_y),reason)
	finish()
func finish():
	var result={"status":"PASS" if failures==0 else "FAIL","scope":"Accelerated location fixture, production route/move/exit. Monsters explicitly dead; not natural combat or GUI play.","checks":checks,"failures":failures,"accepted_move_steps":steps,"native_platform":"NOT_RUN"}
	var out=OS.get_environment("BARAM_MAP_NAV_OUTPUT")
	if not out.is_empty():var f=FileAccess.open(out,FileAccess.WRITE);f.store_string(JSON.stringify(result,"\t")+"\n");f.close()
	print(JSON.stringify({"status":result.status,"failures":failures,"checks":checks.size(),"steps":steps}));quit(0 if failures==0 else 1)
