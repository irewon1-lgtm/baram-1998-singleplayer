extends "test_gameplay_journey.gd"
## Actual compiled-world traversal, normal movement only; no teleport fixture.
func run() -> void:
	var parsed: Variant=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	if not check("load_actual_world",typeof(parsed)==TYPE_DICTIONARY): finish();return
	content=parsed
	game=load("res://state/gameplay_state.gd").new()
	if not check("configure_actual_world",game.configure(content),game.errors): finish();return
	check("world_operator_created",game.create_character("자연육성",owner,{"guardian":"주작","desired_job":"주술사"}).status=="OK")
	natural_start=game.snapshot()
	var city:=str(content.start.map_id)
	for id in content.maps:
		if not check("walk_into_"+str(id),travel_to(str(id)),brief()): continue
		mark("world_"+str(id).replace(":","_"))
		check("walk_back_from_"+str(id),travel_to(city),brief())
	var greetings: Dictionary={}
	for id in content.npcs:
		if not check("walk_to_npc_"+str(id),approach_npc(str(id)),brief()): continue
		var talk:=send({"type":"talk","npc_id":id})
		check("individual_npc_dialogue_"+str(id),ok(talk) and talk.events.size()==1 and talk.events[0].get("npc_id")==id,talk)
		greetings[str(id)]=talk.events[0].get("text","") if not talk.events.is_empty() else ""
		mark("npc_"+str(id).replace(":","_"))
	var distinct: Dictionary={}
	for text in greetings.values(): distinct[str(text)]=true
	check("all_npc_greetings_distinct",greetings.size()==content.npcs.size() and distinct.size()==greetings.size())
	check("no_walk_grants_or_attack_skills",int(char_state().level)==1 and int(char_state().xp)==0 and int(char_state().money)==0 and game.state.skills.is_empty(),brief())
	check("return_to_city_after_tour",travel_to(city),brief())
	natural_end=game.snapshot()
	finish()
