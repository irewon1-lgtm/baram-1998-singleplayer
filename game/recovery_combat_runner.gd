extends "res://exercise.gd"
## Controlled real main methods + real source PNG rendering. No natural-play claim.
var packet_items=[]
var actor_assets=[]
var render_jobs=[]
var render_errors=[]
var rendered_jobs=0
var draw_mode=""
var gallery_player={}
var gallery_weapon=""
var gallery_action="walk"
var candidate_mode=false
var source_missing_attack=[]
var attack_fallback_models=[]
var render_canvas

func run(g, _mode: String, directory: String):
    game=g;root=directory;started=Time.get_ticks_msec()
    DirAccess.make_dir_recursive_absolute(root)
    game.set_process(false)
    if game.creation_controls!=null:game.creation_controls.queue_free()
    game.menu="";game.clear_inputs()
    candidate_mode=game.options.has("candidate-packages")
    if candidate_mode:
        for number in ["007","008","009","010"]:
            var folder=str(game.options["candidate-packages"]).path_join("WK-CONTENT-"+number)
            for filename in DirAccess.get_files_at(folder):
                if not filename.begins_with("content") or not filename.ends_with(".jsonl"):continue
                for line in FileAccess.get_file_as_string(folder.path_join(filename)).split("\n",false):
                    var record=JSON.parse_string(line)
                    if record.kind not in ["item","monster","npc"]:continue
                    # Capability proof only, separate from guarded activation.
                    # No source/release files are written by this runner.
                    if record.operation=="add" or not game.content.records.has(record.id):game.content.records[record.id]=record
        game.content.apply_rules(game.rules)
    for id in game.content.by_kind("item"):
        if id.begins_with("wk.item.exp3.source-"):packet_items.append(id)
    for kind in ["monster","npc"]:
        for id in game.content.by_kind(kind):
            if not id.begins_with("wk."+kind+".exp3.source-model.") and not id.begins_with("wk."+kind+".exp3.object-model."):continue
            var asset=game.content.definition(id).get("visual",{}).get("asset_id","")
            if asset!="" and asset not in actor_assets:actor_assets.append(asset)
            if kind=="monster" and asset!="" and not game.content.definition(asset).get("metadata",{}).get("animations",{}).has("attack"):attack_fallback_models.append(asset)
    check(packet_items.size()>=40,"candidate-or-active-source-equipment-present",{"items":packet_items.size(),"candidate_mode":candidate_mode})
    check(actor_assets.size()==174,"candidate-or-active-source-actor-models-present",{"models":actor_assets.size()})
    var bow="wk.item.exp3.source-bow.14"
    check(game.rules.runtime_definitions.has(bow),"actual-bow-runtime-definition-present")
    if not game.rules.runtime_definitions.has(bow):finish();return
    setup_fixture(bow)
    if game.options.has("status-only"):
        await test_source_statuses();finish();return
    await test_combat(bow)
    await test_equipment_and_render()
    await test_work_light()
    finish()

func controlled(job: String="전사") -> Dictionary:
    var p=game.rules.new_character("통제검사캐릭터")
    game.rules.award_xp(p,1200);game.rules.choose_job(p,job)
    p.level=99;p.strength=1000;p.hp_max=100000;p.hp=p.hp_max;p.mp_max=100000;p.mp=p.mp_max;p.gold=100000000
    return p

func setup_fixture(bow: String):
    var ground=[];var blocked=[];var masks=[]
    for y in range(12):
        var row=[];var walls=[];var mask=[]
        for x in range(12):row.append("");walls.append(false);mask.append(0)
        ground.append(row);blocked.append(walls);masks.append(mask)
    var map={"id":"recovery.combat.fixture","name":"통제 전투 검사 공간","width":12,"height":12,"entry":[2,5],"ground":ground,"blocked":blocked,"collision_masks":masks,"portals":[],"spawns":[],"npcs":[],"decorations":[],"kind":"field"}
    game.maps[map.id]=map;game.decoration_rows[map.id]={}
    game.entities={};game.loot=[];game.effects=[];game.floating_text=[]
    game.player=controlled();game.player.map=map.id;game.player.x=2;game.player.y=5;game.player.direction=3
    game.rules.add_item(game.player,bow)
    check(game.rules.equip(game.player,bow),"actual-bow-equips-via-common-atomic-api")
    var spec=game.rules.monster("rabbit",game.world.replacements)
    var target={"id":"recovery.target","kind":spec.content_id,"map":map.id,"x":7,"y":5,"home_x":7,"home_y":5,"direction":1,"hp":100000,"hp_max":100000,"mp":0,"mp_max":0,"alive":true,"respawn":0.0,"move_timer":99999.0,"attack_timer":99999.0,"provoked":false,"hurt":0.0,"statuses":{},"spec":spec}
    game.entities[target.id]=target;game.rebuild_entity_index();game.selected_target=target.id
    game.reset_motion();game.queue_redraw()

func reset_attack():
    game.attack_wait=0;game.attack_elapsed=-1;game.cast_elapsed=-1;game.impact_done=false;game.attack_target=""
    game.player.buffs["신의축복"]=999.0
    # Seed is reset only for controlled deterministic hit verification.
    game.rules.rng.seed=17

func damage_events() -> Array:
    return game.event_log.filter(func(e):return e.event=="damage_applied" and e.details.get("target","")=="recovery.target")

func attack_frames():
    for i in range(5):game._process(0.1)

func test_combat(bow: String):
    var target=game.entities["recovery.target"]
    check(game.rules.weapon_attack_profile(game.player).kind=="ranged_physical" and game.rules.weapon_attack_profile(game.player).range_tiles==6,"bow-uses-authored-six-tile-physical-profile")
    reset_attack();var hp=target.hp;var count=damage_events().size()
    game.Effects.apply(game.rules.actions,game.player,[],[{"type":"status","target":"self","status_id":"controlled-hidden","duration_ms":10000,"modifiers":{"hidden":1}}])
    game.begin_attack();attack_frames()
    check(target.hp<hp and damage_events().size()==count+1,"bow-ranged-impact-applies-exactly-once-through-real-process",{"damage":hp-target.hp,"damage_events":damage_events().size()-count})
    check(game.rules.actions.status_modifier(game.player,"hidden")==0,"actual-damaging-physical-impact-removes-work-hidden-status")
    check(game.pending_attack_profile.kind=="ranged_physical" and game.player.direction==3,"bow-target-controls-facing-and-real-attack-kind")
    reset_attack();target.x=9;hp=target.hp;count=damage_events().size()
    game.begin_attack();attack_frames()
    check(target.hp==hp and damage_events().size()==count,"bow-rejects-target-beyond-six-tiles")
    target.x=7;game.maps[game.player.map].blocked[5][4]=true
    reset_attack();hp=target.hp;game.begin_attack();attack_frames()
    check(target.hp==hp and game.attack_target=="","bow-wall-blocks-target-before-firing")
    game.maps[game.player.map].blocked[5][4]=false
    game.maps[game.player.map].collision_masks[5][4]=4
    reset_attack();hp=target.hp;game.begin_attack();attack_frames()
    check(target.hp==hp and game.attack_target=="","bow-source-directional-collision-bit-blocks-target")
    game.maps[game.player.map].collision_masks[5][4]=0
    reset_attack();game.begin_attack();game.maps[game.player.map].blocked[5][4]=true;hp=target.hp;attack_frames()
    check(target.hp==hp,"bow-rechecks-wall-at-impact-time")
    game.maps[game.player.map].blocked[5][4]=false
    reset_attack();game.begin_attack();target.x=10;hp=target.hp;attack_frames()
    check(target.hp==hp,"bow-rechecks-target-range-at-impact-time")
    target.x=7;game.selected_target="";reset_attack();hp=target.hp;game.begin_attack();attack_frames()
    check(target.hp<hp and game.attack_target==target.id,"bow-without-selection-fires-along-facing-ray")
    game.selected_target=target.id;target.map="village";reset_attack();hp=target.hp;game.begin_attack();attack_frames()
    check(target.hp==hp,"bow-never-hits-target-on-another-map")
    target.map=game.player.map
    check(game.rules.add_item(game.player,"목도") and game.rules.equip(game.player,"목도"),"source-melee-weapon-equipped-after-bow")
    reset_attack();hp=target.hp;game.begin_attack();attack_frames()
    check(target.hp==hp and game.pending_attack_profile.range_tiles==1,"melee-never-inherits-prior-bow-range")

func item_player(id: String) -> Dictionary:
    var data=game.content.definition(id)
    var ids=data.get("requirements",{}).get("class_ids",[])
    var job=game.content.class_title(ids[0],game.rules) if not ids.is_empty() else "전사"
    var p=controlled(job);p.map="recovery.combat.fixture";p.x=2;p.y=5;p.direction=2
    game.rules.add_item(p,id);game.rules.equip(p,id)
    return p

func frame_job(asset: String,action: String,direction: int,frame: int) -> Dictionary:
    var meta=game.content.definition(asset).get("metadata",{})
    var sequence=meta.get("animations",{}).get(action,{})
    return {"asset":asset,"action":action,"direction":direction,"elapsed":frame*int(sequence.get("frame_ms",100))}

func draw_probe(canvas):
    if draw_mode=="frames":
        canvas.draw_rect(Rect2(0,0,960,640),Color(0.12,0.15,0.18))
        for i in range(render_jobs.size()):
            var job=render_jobs[i]
            var index=game.work_assets.frame_index(job.asset,job.action,job.direction,job.elapsed)
            var table=game.work_assets.metadata(job.asset);var frames=table.get("frames",[])
            if index<0 or index>=frames.size():render_errors.append({"asset":job.asset,"index":index,"error":"FRAME_RANGE"});continue
            var frame=frames[index]
            if frame.get("pivot",table.get("foot_pivot",[])).size()!=2 or frame.get("region",[]).size()!=4:render_errors.append({"asset":job.asset,"index":index,"error":"SOURCE_PIVOT_OR_REGION"});continue
            var pos=Vector2(100+(i%8)*105,160+int(i/8)*125)
            if not game.work_assets.draw_animation(canvas,job.asset,job.action,job.direction,job.elapsed,pos):render_errors.append({"asset":job.asset,"index":index,"error":"ACTUAL_DRAW"})
            else:rendered_jobs+=1
    elif draw_mode=="gallery":
        canvas.draw_rect(Rect2(0,0,960,640),Color(0.12,0.15,0.18))
        canvas.label(gallery_weapon+" · "+gallery_action,Vector2(20,28),18)
        canvas.player=gallery_player
        for direction in range(4):
            canvas.label(["북","서","남","동"][direction],Vector2(30,130+direction*150),18)
            for frame in range(3 if gallery_action=="walk" else 2):
                canvas.walk_clock=float(frame)*0.1;canvas.step_progress=0 if gallery_action=="walk" else 1
                canvas.attack_elapsed=float(frame)*0.1 if gallery_action=="attack" else -1.0
                canvas.cast_elapsed=-1;canvas.pickup_elapsed=-1
                if not canvas.draw_work_player(Vector2(240+frame*240,150+direction*150),direction):render_errors.append({"item":gallery_weapon,"error":"MAIN_COMPOSITE_DRAW"})

func rendered_batch(jobs: Array):
    render_jobs=jobs
    render_canvas.queue_redraw()
    await RenderingServer.frame_post_draw
    await get_tree().process_frame

func test_equipment_and_render():
    var shield="wk.item.exp3.source-shield.0"
    var p=item_player(shield)
    game.rules.add_item(p,"목도");game.rules.equip(p,"목도")
    check(p.equipment_slots.has("offhand") and p.equipped!="","offhand-shield-equips-through-independent-slot")
    var armor=game.rules.armor(p)
    var instance=p.equipment_slots.get("offhand","")
    var before=p.duplicate(true)
    var state={"player":p,"world":{},"loot":[],"rng_state":str(game.rules.rng.state),"content_version":game.content.version}
    var save=root.path_join("offhand-save.json")
    check(game.store.write_state(save,state),"offhand-save-writes-through-real-store")
    var loaded=game.store.read_state(save)
    check(not loaded.is_empty() and loaded.player==before and loaded.player.equipment_slots.get("offhand","")==instance and game.rules.armor(loaded.player)==armor,"offhand-equipment-durability-bonuses-roundtrip-exactly")
    render_canvas=load("res://recovery_render_canvas.gd").new()
    render_canvas.content=game.content;render_canvas.rules=game.rules;render_canvas.work_assets=game.work_assets
    render_canvas.assets=game.assets;render_canvas.world=game.world;render_canvas.font=game.font
    render_canvas.probe=self;render_canvas.z_index=1000;game.add_child(render_canvas)
    draw_mode="frames"
    var assets=[]
    for id in packet_items:
        var visual=game.content.definition(id).get("visual",{})
        var asset=visual.get("equipment_asset_id","")
        if asset!="" and asset not in assets:assets.append(asset)
    assets.append_array(actor_assets)
    var expected=0
    for asset in assets:
        var jobs=[]
        var animations=game.content.definition(asset).get("metadata",{}).get("animations",{})
        for action in ["walk","attack"]:
            var sequence=animations.get(action,{})
            if sequence.is_empty() and action=="attack":
                source_missing_attack.append(asset)
                # Retain the full source limitation inventory. NPC/objects
                # don't attack; hostile actors must render the source walk.
                if asset in attack_fallback_models:
                    var walk=animations.get("walk",{})
                    for direction in range(4):
                        for frame in range(int(walk.get("frames_per_direction",0))):jobs.append(frame_job(asset,"attack",direction,frame))
                continue
            if sequence.is_empty():render_errors.append({"asset":asset,"action":action,"error":"MISSING_SEQUENCE"});continue
            for direction in range(4):
                for frame in range(int(sequence.frames_per_direction)):jobs.append(frame_job(asset,action,direction,frame))
        expected+=jobs.size()
        await rendered_batch(jobs)
    check(render_errors.is_empty() and rendered_jobs>=expected,"all-source-item-and-actor-walk-attack-frames-draw-with-original-page-pivots",{"unique_models":assets.size(),"expected_frames":expected,"rendered":rendered_jobs,"errors":render_errors.duplicate(true)})
    check(attack_fallback_models.size()==4 and attack_fallback_models.all(func(asset):return game.work_assets.animation_fallbacks.has(asset+":attack")),"four-original-actors-without-attack-pixels-stay-visible-via-explicit-source-walk-fallback",{"source_missing_attack":source_missing_attack,"hostile_fallback_models":attack_fallback_models,"classification":"SOURCE_ATTACK_UNAVAILABLE_WALK_FALLBACK"})
    for weapon in ["wk.item.exp3.source-sword.85","wk.item.exp3.source-spear.20","wk.item.exp3.source-fan.0",shield,"wk.item.exp3.source-bow.14"]:
        gallery_player=item_player(weapon)
        if weapon==shield:
            game.rules.add_item(gallery_player,"목도");game.rules.equip(gallery_player,"목도")
        gallery_weapon=weapon
        for action in ["walk","attack"]:
            gallery_action=action;draw_mode="gallery";render_canvas.queue_redraw()
            await RenderingServer.frame_post_draw
            var path=root.path_join(weapon.get_file()+"-"+action+".png")
            var img=game.get_viewport().get_texture().get_image()
            var saved=img.save_png(path)==OK
            screenshots.append({"path":path,"status":"PASS_CAPTURE_ONLY" if saved else "FAIL"})
            check(saved,"rendered-main-composite-"+weapon+"-"+action)
            await get_tree().process_frame
    check(render_errors.is_empty(),"sword-spear-fan-shield-bow-main-composites-all-four-directions",{"errors":render_errors})
    draw_mode="";render_canvas.queue_free()

func test_work_light():
    await get_tree().process_frame
    game.player=controlled("도적");game.player.map="recovery.combat.fixture";game.player.x=2;game.player.y=5
    game.player.buffs.clear();game.player.statuses.clear();game.maps[game.player.map].kind="dungeon"
    game.entities={};game.rebuild_entity_index();game.effects.clear();game.floating_text.clear()
    game.attack_elapsed=-1;game.cast_elapsed=-1;game.reset_motion();game.queue_redraw()
    await RenderingServer.frame_post_draw
    var at=Vector2i(game.screen_point(6,1)-Vector2(0,24))
    var dark_image=game.get_viewport().get_texture().get_image()
    var dark=dark_image.get_pixel(at.x,at.y)
    var id="kr.spell.23b1a867d144"
    var source=game.content.definition(id)
    var applied=game.Effects.apply(game.rules.actions,game.player,[],game.Effects.compile_skill(source))
    game.queue_redraw();await RenderingServer.frame_post_draw
    var lit_image=game.get_viewport().get_texture().get_image()
    var lit=lit_image.get_pixel(at.x,at.y)
    check(applied.ok and game.rules.actions.status_modifier(game.player,"light")>0 and lit.r+lit.g+lit.b>dark.r+dark.g+dark.b+0.02,"work-source-light-status-removes-dungeon-darkness-in-actual-render",{"source_skill_id":id,"sample":[at.x,at.y],"dark":[dark.r,dark.g,dark.b],"lit":[lit.r,lit.g,lit.b]})
    dark_image.save_png(root.path_join("dungeon-without-light.png"));lit_image.save_png(root.path_join("dungeon-work-light.png"))

func one_monster_impact(target: Dictionary) -> int:
    target.attack_elapsed=0.0;target.attack_pending=true;target.attack_timer=99999.0;target.move_timer=99999.0
    target.direction=1;target.x=3;target.y=5;target.provoked=true
    game.rules.rng.seed=17
    game.player.hp=game.player.hp_max
    game.update_monsters(0.17)
    return int(game.player.hp_max)-int(game.player.hp)

func test_source_statuses():
    var errors=[]
    for id in game.content.by_kind("skill"):
        var result=game.Effects.validate(game.Effects.compile_skill(game.content.definition(id)))
        if not result.ok:errors.append({"id":id,"result":result})
    check(errors.is_empty(),"all-activated-source-skill-effect-operators-compile-and-validate",{"skills":game.content.by_kind("skill").size(),"errors":errors})
    var target=game.entities["recovery.target"]
    target.spec=target.spec.duplicate(true)
    target.spec.values.attack_min=100;target.spec.values.attack_max=100
    target.spec.values.hit_probability={"numerator":1,"denominator":1}
    target.statuses.clear()
    var ordinary=one_monster_impact(target)
    var id="wk.skill.exp2.rank2.mage.2"
    var definition=game.content.definition(id)
    var result=game.Effects.apply(game.rules.actions,game.player,[target],game.Effects.compile_skill(definition))
    var deadline=int(target.statuses.get("paralyze",{}).get("expires_ms",-1))
    check(result.ok and game.rules.actions.status_modifier(target,"stun")==1,"source-paralyze-maps-to-actual-enemy-stun-flag")
    check(one_monster_impact(target)==0,"source-paralyze-prevents-real-monster-impact")
    game.Effects.tick_at(game.rules.actions,target,deadline-1)
    check(game.rules.actions.status_modifier(target,"stun")==1,"source-paralyze-retains-declared-four-second-duration")
    game.Effects.tick_at(game.rules.actions,target,deadline)
    check(game.rules.actions.status_modifier(target,"stun")==0 and one_monster_impact(target)==ordinary,"source-paralyze-expiry-resumes-same-seed-monster-impact")
    id="wk.skill.exp2.rank3.rogue.2";definition=game.content.definition(id)
    result=game.Effects.apply(game.rules.actions,game.player,[target],game.Effects.compile_skill(definition))
    deadline=int(target.statuses.get("weaken",{}).get("expires_ms",-1))
    var weakened=one_monster_impact(target)
    var expected=game.rules.incoming_damage(game.player,75)
    check(result.ok and game.rules.actions.status_modifier(target,"damage")==-25 and weakened==expected and weakened<ordinary,"source-weaken-reduces-real-monster-attack-with-same-rng-seed",{"ordinary":ordinary,"weakened":weakened,"expected":expected,"adapter":"AUTHORED_ADDITIVE_DAMAGE_MINUS_25_NO_PERCENTAGE_UNIT"})
    game.Effects.tick_at(game.rules.actions,target,deadline-1)
    check(one_monster_impact(target)==weakened,"source-weaken-retains-declared-fifteen-second-duration")
    game.Effects.tick_at(game.rules.actions,target,deadline)
    check(game.rules.actions.status_modifier(target,"damage")==0 and one_monster_impact(target)==ordinary,"source-weaken-expiry-restores-same-seed-real-monster-attack")

func finish():
    var failures=checks.filter(func(c):return c.status!="PASS").size()
    var report={"status":"PASS" if failures==0 else "FAIL","scope":"CONTROLLED_MAIN_GAME_METHODS_AND_REAL_SOURCE_RENDER_NOT_NATURAL_PLAY","candidate_packets_in_memory":candidate_mode,"content_version":game.content.version,"checks":checks,"screenshots":screenshots,"rendered_frame_jobs":rendered_jobs,"source_missing_attack_models":source_missing_attack,"source_animation_fallbacks":game.work_assets.animation_fallbacks,"source_frames_used":game.work_assets.used_frames.keys(),"events":game.event_log,"no_projectile_graphic_created":true,"elapsed_ms":Time.get_ticks_msec()-started}
    var file=FileAccess.open(root.path_join("recovery-combat-report.json"),FileAccess.WRITE)
    file.store_string(JSON.stringify(report,"  "));file.close()
    print("RECOVERY_COMBAT_DONE "+("PASS" if failures==0 else "FAIL"))
    game.get_tree().quit(0 if failures==0 else 1)
