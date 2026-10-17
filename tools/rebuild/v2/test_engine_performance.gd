extends SceneTree
## Same full G1 inputs through before/after engines. CPU method timings, not FPS,
## physical input latency, natural leveling, saving I/O or a platform release gate.
const Current = preload("res://state/gameplay_state.gd")
const Navigation = preload("res://input/grid_navigation.gd")
var before
var after
var definitions: Dictionary
var original: Dictionary
var checks: Array=[]
var failures := 0
var comparisons := 0
var sequence := 0
var measurements: Dictionary={}
var before_class
var before_navigation

func check(id: String, good: bool, detail: Variant=null) -> void:
	checks.append({"id":id,"status":"PASS" if good else "FAIL","detail":detail})
	if not good: failures+=1

func compare(id: String,a: Dictionary,b: Dictionary) -> void:
	comparisons+=1
	if a!=b or before.state!=after.state:
		var changed: Array=[]
		for key in before.state:
			if before.state[key]!=after.state.get(key): changed.append(key)
		check(id,false,{"old_response":a,"new_response":b,"different_state_keys":changed})

func both_command(type: String, extra: Dictionary={}) -> void:
	sequence+=1
	var cmd: Dictionary={"type":type,"request_id":"differential:"+str(sequence)};cmd.merge(extra)
	var old_prior: Dictionary=before.state;var new_prior: Dictionary=after.state
	var old_frozen: String=JSON.stringify(old_prior);var new_frozen: String=JSON.stringify(new_prior)
	compare("command:"+str(sequence),before.command(cmd),after.command(cmd))
	if old_frozen!=JSON.stringify(old_prior) or new_frozen!=JSON.stringify(new_prior): check("transaction_preserves_prior:"+str(sequence),false)

func both_tick(seconds: float) -> void:
	var prior: Dictionary=after.state;var frozen: String=JSON.stringify(prior)
	compare("tick:"+str(comparisons),before.tick(seconds),after.tick(seconds))
	if frozen!=JSON.stringify(prior): check("tick_preserves_prior:"+str(comparisons),false)

func pair_fixture(payload: Dictionary) -> void:
	before.state=payload.duplicate(true);after.state=payload.duplicate(true)

func find_standing() -> Dictionary:
	for id in original.monsters:
		var m: Dictionary=original.monsters[id]
		for offset in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]:
			var x: int=int(m.x)+offset.x;var y: int=int(m.y)+offset.y
			if after.valid_position(str(m.map_id),x,y) and not after._occupied(str(m.map_id),x,y):
				return {"id":id,"map_id":m.map_id,"x":x,"y":y}
	return {}

func differential() -> void:
	for i in range(120):
		both_tick(1.0/60.0)
		if i%9==0: both_command("move",{"dx":1 if i%18==0 else -1,"dy":0})
	both_command("move",{"dx":0.5,"dy":0})
	both_command("buy",{"npc_id":"missing","item_id":"missing","quantity":1})
	both_command("cancel")
	var standing: Dictionary=find_standing()
	check("target_adjacent_fixture_available",not standing.is_empty())
	if standing.is_empty(): return
	# Explicit fixtures exercise all actual G1 skills against the unchanged oracle.
	for id in definitions.skills:
		var skill: Dictionary=definitions.skills[id]
		var p: Dictionary=original.duplicate(true);var c: Dictionary=p.character
		c.job=str(skill.job) if str(skill.job) in ["전사","도적","주술사","도사"] else "전사"
		c.guardian=skill.get("guardian","주작");c.level=definitions.xp_thresholds.size();c.xp=definitions.xp_thresholds[-1]
		c.hp_max=1000000;c.hp=500000;c.mp_max=1000000;c.mp=500000
		c.map_id=standing.map_id;c.x=standing.x;c.y=standing.y;p.skills=[id]
		for monster in p.monsters.values(): monster.ai_at=100000.0;monster.attack_at=100000.0
		for advancement in definitions.get("advancements",{}).values():
			if str(advancement.job)==str(c.job) and int(advancement.get("rank",1))>int(c.get("advancement_rank",0)):
				c.advancement=advancement.id;c.advancement_rank=advancement.rank;c.title=advancement.get("title",advancement.id)
		var extra: Dictionary={"skill_id":id,"target_id":standing.id,"direction":"east"}
		var kind: String=str(skill.kind)
		if kind in ["revive","shrine"]: c.hp=0;c.dead=true
		if kind=="identify":
			var item_id: String=str(definitions.items.keys()[0]);extra.instance_id="fixture:identify"
			p.inventory.append({"instance_id":extra.instance_id,"item_id":item_id,"quantity":1,"durability":int(definitions.items[item_id].get("durability",0))})
		if kind=="cleanse":
			var status: String=str(skill.get("cleanse_statuses",["poison"])[0])
			p.buffs["fixture:effect"]=after._status_definition({"power":1,"duration":20},status)
		pair_fixture(p)
		both_command("cast",extra)
		for step in range(4): both_tick(0.25)
	# Off-map poison, expiry, already-dead respawn clocks, re-entry and loot retain
	# full state + event + RNG equality with the previous global implementation.
	var p: Dictionary=original.duplicate(true)
	var inactive: String="";var dead_id: String=""
	for id in p.monsters:
		var m: Dictionary=p.monsters[id]
		if str(m.map_id)==str(p.character.map_id): continue
		if inactive.is_empty(): inactive=str(id)
		elif str(m.map_id)==str(p.monsters[inactive].map_id): dead_id=str(id);break
	check("inactive_map_fixture_exists",not inactive.is_empty() and not dead_id.is_empty())
	if not inactive.is_empty() and not dead_id.is_empty():
		var m: Dictionary=p.monsters[inactive]
		m.statuses={"fixture:poison":{"status":"poison","power":1000000,"expires_at":1.5,"next_tick":0.1,"tick_interval":0.2}}
		p.monsters[dead_id].hp=0;p.monsters[dead_id].alive=false;p.monsters[dead_id].respawn_at=0.1
		pair_fixture(p)
		for i in range(10): both_tick(0.25)
		check("inactive_poison_resolved_and_loot_retained",not after.state.monsters[inactive].alive and after.state.loot==before.state.loot)
		check("inactive_respawn_clock_preserved",not after.state.monsters[dead_id].alive and after.state.monsters[dead_id].respawn_at==0.1)
		var reentry: Dictionary=after.snapshot()
		reentry.character.map_id=standing.map_id;reentry.character.x=standing.x;reentry.character.y=standing.y
		pair_fixture(reentry);both_tick(0.1)
		check("reentry_respawns_once",after.state.monsters[dead_id].alive and int(after.state.monsters[dead_id].generation)==1)
	var duplicate_fixture: Dictionary=after.snapshot()
	var known_skill: String=str(definitions.skills.keys()[0]);duplicate_fixture.skills=[known_skill]
	pair_fixture(duplicate_fixture)
	both_command("bind_hotkey",{"slot":"1","skill_id":known_skill})
	var before_duplicate: String=JSON.stringify(after.state)
	var duplicate: Dictionary={"type":"move","request_id":"differential:"+str(sequence),"dx":1,"dy":0}
	compare("duplicate_request",before.command(duplicate),after.command(duplicate))
	check("duplicate_does_not_change_state_or_rng",JSON.stringify(after.state)==before_duplicate)
	check("complete_world_preserved",after.state.monsters.size()==original.monsters.size())
	check("oracle_exact_state_events_rng_equality",failures==0,{"comparisons":comparisons})

func stats(samples: Array) -> Dictionary:
	var ordered: Array=samples.duplicate();ordered.sort()
	var sum: float=0.0
	for value in samples: sum+=float(value)
	return {"samples":samples.size(),"mean_ms":sum/samples.size()/1000.0,"p50_ms":float(ordered[int(ceil(ordered.size()*0.50))-1])/1000.0,"p95_ms":float(ordered[int(ceil(ordered.size()*0.95))-1])/1000.0,"p99_ms":float(ordered[int(ceil(ordered.size()*0.99))-1])/1000.0,"max_ms":float(ordered[-1])/1000.0,"raw_us":samples}

func benchmark(label: String,payload: Dictionary,kind: String,count: int) -> void:
	before.state=payload.duplicate(true);after.state=payload.duplicate(true)
	var old_samples: Array=[];var new_samples: Array=[]
	for i in range(count):
		var routes: Dictionary={}
		# Alternating order reduces a systematic warm-up/scheduling advantage.
		for index in ([0,1] if i%2==0 else [1,0]):
			var game=before if index==0 else after
			var started: int=Time.get_ticks_usec()
			if kind=="tick": game.tick(1.0/60.0)
			elif kind=="command": game.command({"type":"move","request_id":"benchmark:"+str(i+1),"dx":1 if i%2==0 else -1,"dy":0})
			else:
				var nav=before_navigation if index==0 else Navigation
				routes[index]=nav.route(game,Vector2i(57,57),0)
			var elapsed: int=Time.get_ticks_usec()-started
			if index==0: old_samples.append(elapsed)
			else: new_samples.append(elapsed)
		if kind=="route" and routes[0]!=routes[1]: check("same_route:"+str(i),false)
	measurements[label]={"before":stats(old_samples),"after":stats(new_samples),"map_id":payload.character.map_id,"world_monsters":payload.monsters.size(),"current_map_monsters":payload.monsters.values().filter(func(m):return m.map_id==payload.character.map_id).size(),"kind":kind}
	check("benchmark_same_final_state:"+label,before.state==after.state)

func _initialize() -> void:
	var runtime: String=OS.get_environment("BARAM_G1_RUNTIME")
	var baseline: String=OS.get_environment("BARAM_B5_BASELINE_ENGINE")
	var baseline_nav: String=OS.get_environment("BARAM_B5_BASELINE_NAVIGATION")
	before_class=load(baseline);before_navigation=load(baseline_nav)
	definitions=JSON.parse_string(FileAccess.get_file_as_string(runtime.path_join("gameplay_content.json")))
	before=before_class.new();after=Current.new()
	check("full_G1_configures",before.configure(definitions) and after.configure(definitions),after.errors)
	check("same_seed_character_creates",before.create_character("성능비교","fixture:performance",{"seed":41})==after.create_character("성능비교","fixture:performance",{"seed":41}))
	original=after.snapshot()
	differential()
	benchmark("tavern_tick",original,"tick",180)
	benchmark("tavern_move",original,"command",180)
	var standing: Dictionary=find_standing();var hunting: Dictionary=original.duplicate(true)
	hunting.character.map_id=standing.map_id;hunting.character.x=standing.x;hunting.character.y=standing.y
	hunting.character.hp_max=1000000;hunting.character.hp=1000000
	benchmark("hunting_tick",hunting,"tick",180)
	var city: Dictionary=original.duplicate(true)
	var gate: Dictionary=definitions.gates.east
	city.character.map_id=gate.map_id;city.character.x=gate.x;city.character.y=gate.y
	benchmark("city_tick",city,"tick",180)
	benchmark("city_far_route",city,"route",3)
	var result: Dictionary={"schema":"baram.v2.b5-engine-performance/1","status":"PASS" if failures==0 else "FAIL","scope":"CPU function timing + exact full G1 state/event/RNG differential fixtures; no FPS/input/OS/platform or natural progression claim","engine":Engine.get_version_info(),"os":OS.get_name(),"content_sha256":FileAccess.get_sha256(runtime.path_join("gameplay_content.json")),"baseline_engine_sha256":FileAccess.get_sha256(baseline),"engine_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"baseline_navigation_sha256":FileAccess.get_sha256(baseline_nav),"navigation_sha256":FileAccess.get_sha256("res://input/grid_navigation.gd"),"checks":checks,"comparisons":comparisons,"measurements":measurements,"failures":failures}
	var report: String=OS.get_environment("BARAM_B5_PERFORMANCE_REPORT")
	if not report.is_empty(): var file=FileAccess.open(report,FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n")
	print(JSON.stringify({"status":result.status,"failures":failures,"comparisons":comparisons,"measurements":measurements.keys()}))
	quit(0 if failures==0 else 1)
