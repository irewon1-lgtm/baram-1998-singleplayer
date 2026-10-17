extends "res://../../tools/rebuild/v2/test_g2_closure.gd"
## Every quest objective is produced by an authoritative action. Companion
## materials, character level/money and positioning are labelled prerequisites.
var quests_completed:=0
var recipes_crafted:=0
func fulfill(objective: Dictionary) -> bool:
	var id:=str(objective.id);var kind:=str(objective.kind)
	if kind=="collect":return add_materials({id:int(objective.get("count",1))})
	if kind=="talk":return near_npc(id) and command("talk",{"npc_id":id}).status=="OK"
	if kind=="visit":
		for source in game.data.maps:
			for exit in game.data.maps[source].get("exits",[]):
				if str(exit.to_map)!=id:continue
				for delta in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
					var x: int=int(exit.x)-delta.x;var y: int=int(exit.y)-delta.y
					if not game.can_step(str(source),x,y,int(exit.x),int(exit.y)) or game._occupied(str(source),x,y):continue
					game.state.character.map_id=source;game.state.character.x=x;game.state.character.y=y;game.state.cooldowns={}
					return command("move",{"dx":delta.x,"dy":delta.y}).status=="OK"
		return false
	if kind=="craft":
		var recipe: Dictionary=game.data.recipes[id]
		return near_npc(str(recipe.npc_id)) and add_materials(recipe.ingredients) and command("craft",{"npc_id":recipe.npc_id,"recipe_id":id}).status=="OK"
	if kind=="equip":
		var item: Dictionary=game.data.items[id];job_fixture(str(item.get("required_job","전사")))
		return game._add_item(id,1) and command("equip",{"instance_id":first_instance(id)}).status=="OK"
	if kind=="kill":
		for n in range(int(objective.get("count",1))):
			var spawn:=near_spawn(id)
			if spawn.is_empty():return false
			if not bool(game.state.monsters[spawn].alive):
				# Advance the actual respawn timer, preserving the same instance ID.
				for step in range(30):
					game.tick(5)
					if bool(game.state.monsters[spawn].alive):break
			game.state.cooldowns={}
			if not kill_command(spawn):return false
		return true
	return false
func _initialize() -> void:
	var runtime:=OS.get_environment("BARAM_G1_RUNTIME")
	var raw: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(runtime.path_join("gameplay_content.json")))
	game=Game.new();check("G2_configure",game.configure(raw),game.errors)
	if failures==0:
		check("G2_create",game.create_character("의뢰검증","fixture:closure").status=="OK")
		game._spawn_all();original=game.snapshot()
		for id in original.monsters:
			var mid:=str(original.monsters[id].monster_id)
			if not spawn_by_monster.has(mid):spawn_by_monster[mid]=[]
			spawn_by_monster[mid].append(id)
		for id in raw.quests:
			context();var q: Dictionary=raw.quests[id];job_fixture(str(q.get("required_job","전사")))
			for prior in q.get("requires_quests",[]):game.state.quests[prior]={"status":"completed","progress":{}}
			check("accept:"+str(id),near_npc(str(q.npc_id)) and command("quest_accept",{"npc_id":q.npc_id,"quest_id":id}).status=="OK")
			for objective in q.objectives:check("objective:"+str(id)+":"+str(objective.kind)+":"+str(objective.id),fulfill(objective))
			var completed: Dictionary=command("quest_complete",{"npc_id":q.npc_id,"quest_id":id}) if near_npc(str(q.npc_id)) else {}
			check("complete:"+str(id),completed.get("status")=="OK",completed.get("reason"))
			check("save:"+str(id),game.validate_payload(game.snapshot()).status=="OK")
			if completed.get("status")=="OK":quests_completed+=1
		for id in raw.recipes:
			context();var r: Dictionary=raw.recipes[id];job_fixture(str(r.get("required_job","전사")))
			var ok: bool=near_npc(str(r.npc_id)) and add_materials(r.ingredients) and command("craft",{"npc_id":r.npc_id,"recipe_id":id}).status=="OK"
			check("recipe:"+str(id),ok)
			if ok:recipes_crafted+=1
	var report={"schema":"baram.g2.quest-actions/1","status":"PASS"if failures==0 else"FAIL","scope":"Level/money/companion-material/position fixtures; actual accept, talk, move, attack, timed respawn, equip, craft, complete and payload validation. Not natural progression.","quests_completed":quests_completed,"recipes_crafted":recipes_crafted,"checks":checks,"failures":failures}
	var f=FileAccess.open(OS.get_environment("BARAM_G2_REPORT"),FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "))
	print(JSON.stringify({"quests":quests_completed,"recipes":recipes_crafted,"checks":checks.size(),"failures":failures}));quit(0 if failures==0 else 1)
