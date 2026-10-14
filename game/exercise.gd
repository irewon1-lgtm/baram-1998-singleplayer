extends Node
## Sends real Godot input events to the live window; never calls damage/level-up directly.
## Captures rendered frames and checks outcomes, preserving failures before restart.
var game
var root = ""
var checks = []
var screenshots = []
var started = 0

func check(ok: bool, name: String, info = {}):
    checks.append({"name":name,"status":"PASS" if ok else "FAIL","observed":info})
    print("SCREEN_CHECK "+name+" "+("PASS" if ok else "FAIL"))

func pause(seconds: float):
    await get_tree().create_timer(seconds).timeout

func key(code: int, delay: float = 0.23, turn: bool = false):
    var event = InputEventKey.new()
    event.keycode = code
    event.physical_keycode = code
    event.shift_pressed = turn
    event.pressed = true
    Input.parse_input_event(event)
    await get_tree().process_frame
    var release = InputEventKey.new()
    release.keycode = code
    release.physical_keycode = code
    release.pressed = false
    Input.parse_input_event(release)
    await pause(delay)

func capture(title: String):
    await RenderingServer.frame_post_draw
    var path = root.path_join(title+".png")
    var image = game.get_viewport().get_texture().get_image()
    var ok = image.save_png(path) == OK
    screenshots.append({"name":title,"path":path,"width":image.get_width(),"height":image.get_height(),
        "sha256":FileAccess.get_sha256(path) if ok else "","status":"PASS_CAPTURE_ONLY" if ok else "FAIL"})
    check(ok and image.get_width()==960 and image.get_height()==640,"rendered_"+title)
    print("SCREEN_CAPTURE_READY "+title)
    await pause(0.25) # external runner independently captures the actual X11 window

func route(target: Vector2i) -> bool:
    # BFS plans keys around actual collision/spawn data. The game still decides every step.
    for attempt in range(40):
        if game.player.hp<=0:return false
        if game.player.hp < game.player.hp_max*0.5 and int(game.player.inventory.get("초보 회복약",0))>0:
            await use_potion()
        if game.cell()==target:return true
        var current = game.cell()
        var queue=[current]
        var parents={current:null}
        var directions={}
        var found=false
        for index in range(int(game.maps[game.player.map].width)*int(game.maps[game.player.map].height)):
            if index>=queue.size():break
            var at=queue[index]
            if at==target:found=true;break
            for d in range(4):
                var next=at+game.DIRECTIONS[d]
                if parents.has(next) or not game.free_cell(game.player.map,next,"",d):continue
                var portal_here=false
                for portal in game.maps[game.player.map].portals:
                    # Interact-only doors do not change maps when crossed.
                    # Excluding them invented walls in Work's dense hubs.
                    if portal.get("trigger","walk")=="walk" and next==Vector2i(portal.x,portal.y) and next!=target:
                        portal_here=true
                        break
                if portal_here:continue
                parents[next]=at
                directions[next]=d
                queue.append(next)
        if not found:return false
        var steps=[]
        var next=target
        while next!=current:
            steps.push_front(next)
            next=parents[next]
        for step in steps:
            if game.player.hp<=0:return false
            if game.player.hp<game.player.hp_max*0.5 and game.player.inventory.get("초보 회복약",0)>0:await use_potion()
            var expected_map=game.player.map
            if not game.free_cell(expected_map,step,"",directions[step]):break
            await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][directions[step]])
            if game.player.map!=expected_map:return true
            if game.cell()!=step:break
        if game.cell()==target:return true
    return false

func hunt_one(kind: String = "") -> bool:
    var target={}
    var nearest=999.0
    for id in game.entities:
        var e=game.entities[id]
        var dist=Vector2i(e.x,e.y).distance_to(game.cell())
        if e.map==game.player.map and e.alive and (kind=="" or e.kind==kind) and dist<nearest:
            target=e;nearest=dist
    if target.is_empty():return false
    for attempt in range(20):
        if game.player.hp<=0:return false
        if not target.alive:return true
        var adjacent=[]
        for d in range(4):
            var at=Vector2i(target.x,target.y)-game.DIRECTIONS[d]
            var portal_here=false
            for portal in game.maps[game.player.map].portals:
                if at==Vector2i(portal.x,portal.y):
                    portal_here=true
                    break
            if not portal_here and (at==game.cell() or game.free_cell(game.player.map,at)):adjacent.append({"at":at,"direction":d})
        adjacent.sort_custom(func(a,b):return a.at.distance_to(game.cell())<b.at.distance_to(game.cell()))
        if adjacent.is_empty():return false
        var reached=false
        for option in adjacent:
            if await route(option.at):reached=true;break
        if not reached:return false
        var offset=Vector2i(target.x,target.y)-game.cell()
        var direction=game.DIRECTIONS.find(offset)
        if direction<0:continue
        await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][direction],0.03,true)
        # Facing a blocked enemy is a real arrow key action; then space starts animation.
        await key(KEY_SPACE,0.7)
        await key(KEY_G,0.03)
        if int(game.player.hp)==0:return false
    return not target.alive

func use_potion():
    await key(KEY_I,0.02)
    var index=game.choices.find("초보 회복약")
    if index>=0:
        for i in range(index):await key(KEY_DOWN,0.02)
        await key(KEY_U,0.02)
    await key(KEY_ESCAPE,0.02)

func run(g, mode: String, directory: String):
    game=g;root=directory;started=Time.get_ticks_msec()
    DirAccess.make_dir_recursive_absolute(root)
    if mode=="source-core":
        await source_core()
        return
    if mode.begins_with("skills-"):
        await source_skills(int(mode.trim_prefix("skills-")))
        return
    if mode=="tour-resume":
        await tour_resume()
        return
    if mode in ["content-actions","cure-actions"]:
        await content_actions(mode)
        return
    if mode=="town-all":
        await town_all()
        return
    if mode=="natural-progress":
        await natural_progress()
        return
    if mode=="gear-guide":
        await gear_guide()
        return
    if mode in ["restart","source-restart","actions-restart","gear-restart"]:
        check(game.save_loaded,"fresh_process_loaded_save")
        var before=game.store.read_state(root.path_join("expected-state.json"))
        check(game.loaded_snapshot.player==before.player,"restart_preserves_entire_player",{"level":game.player.level,"gold":game.player.gold,"equipped":game.player.equipped})
        check(game.loaded_snapshot.world==before.world and game.loaded_snapshot.loot==before.loot,"restart_preserves_world_and_loot")
        check(str(game.loaded_snapshot.rng_state)==str(before.rng_state),"restart_preserves_rng")
        await capture("restart")
        finish()
        return
    if mode=="resume":
        check(game.save_loaded and game.player.level>=5 and game.player.kills>=25,"resume_verified_25_kill_checkpoint")
        await dungeon_tour()
        return
    check(not game.save_loaded and game.menu=="creation","fresh_character_creation_screen")
    await capture("creation")
    var job_index=int(mode.trim_prefix("class-")) if mode.begins_with("class-") else 0
    await key(KEY_1+job_index)
    await key(KEY_ENTER)
    check(game.player.job==game.Rules.JOBS[job_index] and game.player.level==1,"character_created_via_input")
    await key(KEY_ENTER)
    check(game.menu=="shop","npc_dialogue_via_input")
    await key(KEY_DOWN)
    await key(KEY_B)
    check(int(game.player.inventory.get("목검",0))==1 and game.player.gold==10,"shop_purchase_via_input")
    await capture("shop")
    await key(KEY_ESCAPE)
    await key(KEY_I)
    await key(KEY_DOWN)
    await key(KEY_E)
    check(game.player.equipped=="목검","inventory_weapon_equipped_via_input")
    await key(KEY_ESCAPE)
    await capture("village-equipped")
    # Merchant is a blocked tile. Up changes facing without walking through it.
    var before=game.cell()
    await key(KEY_UP)
    check(game.cell()==before and game.player.direction==0,"collision_and_facing_direction")
    var mp=int(game.player.mp)
    await key(KEY_1,0.08)
    check(game.player.mp==mp-5,"skill_hotkey_deducts_mp")
    await capture("skill-effect")
    await pause(0.6)
    check(await route(Vector2i(15,12)) and game.player.map=="field","village_to_field_by_walking")
    var xp_before=int(game.player.xp2)
    check(await hunt_one("rabbit"),"directional_animated_attack_kills_rabbit")
    check(int(game.player.xp2)>xp_before,"combat_awards_actual_xp")
    await capture("field-combat")
    if mode.begins_with("class-"):
        await key(KEY_F5)
        check(FileAccess.file_exists(game.save_path),"class_save_written")
        game.store.write_state(root.path_join("expected-state.json"),game.store.read_state(game.save_path))
        finish()
        return
    var deadline=Time.get_ticks_msec()+160000
    while int(game.player.kills)<25 and game.player.hp>0 and Time.get_ticks_msec()<deadline:
        if not await hunt_one():await pause(0.3)
    check(game.player.kills>=25,"25_actual_input_driven_kills",{"kills":game.player.kills})
    if game.player.kills<25:
        finish()
        return
    var picked=game.event_log.filter(func(e):return e.event=="item_picked_up").size()
    check(picked>0,"actual_random_drop_pickup",{"pickups":picked})
    # Return and claim the two authored quest rewards through the NPC interaction.
    check(await route(Vector2i(11,12)) and game.player.map=="village","field_to_village_by_walking")
    check(await route(Vector2i(12,10)),"walk_to_quest_npc")
    await key(KEY_UP)
    await key(KEY_ENTER)
    await key(KEY_ENTER)
    check(int(game.player.level)>=5 and game.player.quests.size()==2,"quest_xp_causes_real_levelups",{"level":game.player.level})
    if int(game.player.level)<5 or game.player.quests.size()!=2:
        finish()
        return
    await capture("level-up")
    # Supply exploration through real NPC transactions, not grants or HP edits.
    check(await route(Vector2i(12,12)),"return_to_merchant")
    await key(KEY_UP)
    await key(KEY_ENTER)
    var potion_index=game.choices.find("초보 회복약")
    for i in range(potion_index):await key(KEY_DOWN,0.03)
    for i in range(10):await key(KEY_B,0.03)
    await key(KEY_R,0.03)
    await key(KEY_C,0.03)
    check(int(game.player.inventory.get("초보 회복약",0))==10,"generated_potions_bought_through_actual_shop")
    await key(KEY_ESCAPE)
    check(await route(Vector2i(6,8)) and game.player.map=="inn","village_to_interior_by_walking")
    await key(KEY_UP)
    await key(KEY_ENTER)
    await capture("inn")
    await key(KEY_ESCAPE)
    check(await route(Vector2i(11,12)) and game.player.map=="village","inn_exit_by_walking")
    check(await route(Vector2i(24,8)) and game.player.map=="guild","enter_training_interior")
    await key(KEY_UP)
    await key(KEY_ENTER)
    check(game.menu=="trainer","actual_class_skill_catalogue")
    await capture("trainer")
    await key(KEY_ESCAPE)
    check(await route(Vector2i(11,12)) and game.player.map=="village","guild_exit_by_walking")
    await dungeon_tour()

func approach(role: String) -> bool:
    for n in game.maps[game.player.map].npcs:
        if n.role!=role:continue
        for d in range(4):
            var at=Vector2i(n.x,n.y)-game.DIRECTIONS[d]
            if not game.free_cell(game.player.map,at):continue
            if await route(at):
                await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][d],0.03,true)
                await key(KEY_ENTER,0.05)
                return true
    return false

func guided(destination: String) -> bool:
    if game.player.map==destination:return true
    if game.menu!="":await key(KEY_ESCAPE,0.01)
    if not await approach("travel") or game.menu!="travel":return false
    var index=game.choices.find(destination)
    if index<0:await key(KEY_ESCAPE,0.01);return false
    for i in range(index):await key(KEY_DOWN,0.02)
    await key(KEY_ENTER,0.06)
    return game.player.map==destination

func source_core():
    check(game.maps.size()==int(game.world.original_map_count) and game.maps.size()>=15,"declared_original_maps_loaded")
    check(game.assets.tiles.size()==50104,"source_and_uploaded_tiles_registered_separately")
    await key(KEY_ENTER)
    check(game.cell()==Vector2i(59,152),"creation_uses_reachable_source_town_entry")
    await capture("source-village-before-gear")
    check(await approach("shop") and game.menu=="shop","source_town_actual_shop")
    if game.menu!="shop":finish();return
    var index=game.choices.find("목검")
    for i in range(index):await key(KEY_DOWN,0.02)
    await key(KEY_B,0.03)
    check(game.player.inventory.get("목검",0)==1,"source_town_purchase")
    await key(KEY_ESCAPE,0.03)
    await key(KEY_I,0.03)
    index=game.choices.find("목검")
    for i in range(index):await key(KEY_DOWN,0.02)
    await key(KEY_E,0.03)
    check(game.player.equipped=="목검","source_town_equip")
    await key(KEY_ESCAPE,0.03)
    await capture("source-village-equipped")
    check(await route(Vector2i(59,149)) and game.player.map=="inn","original_tavern_doorway_by_movement")
    if game.player.map!="inn":finish();return
    await capture("source-inn")
    check(await approach("inn") and game.menu=="shop","source_inn_functional_keeper")
    await key(KEY_H,0.03)
    check(game.event_log.any(func(e):return e.event=="rested"),"source_inn_rest_transaction")
    await key(KEY_ESCAPE,0.03)
    check(await route(Vector2i(21,13)) and game.player.map=="village","original_tavern_exit_by_movement")
    check(await guided("field"),"guide_connects_original_hunting_field")
    if game.player.map!="field":finish();return
    await capture("source-field")
    var xp=int(game.player.xp2)
    check(await hunt_one("rabbit"),"original_field_normal_combat")
    check(game.player.xp2>xp,"original_field_real_xp_reward")
    await capture("source-field-combat")
    await key(KEY_1,0.03)
    await capture("source-field-skill")
    check(await guided("village"),"source_field_return_guide")
    check(await guided("guild"),"source_warrior_guild_reached")
    await capture("source-guild")
    check(await approach("trainer") and game.menu=="trainer","source_guild_training_role")
    await key(KEY_ESCAPE,0.03)
    await key(KEY_F5,0.03)
    var expected=game.store.read_state(game.save_path)
    game.store.write_state(root.path_join("expected-state.json"),expected)
    await capture("source-saved")
    finish()

func go_portal(target: Vector2i,destination: String,title: String) -> bool:
    var ok=await route(target) and game.player.map==destination
    check(ok,title,{"actual_map":game.player.map,"target":destination})
    if not ok:
        finish()
    return ok

func dungeon_tour():
    if not await go_portal(Vector2i(15,12),"field","reenter_field"):return
    if not await go_portal(Vector2i(22,12),"cave","field_to_dungeon_by_walking"):return
    check(await hunt_one("rat"),"dungeon_combat")
    await capture("cave")
    if not await go_portal(Vector2i(35,12),"deep","deep_dungeon_transition"):return
    await capture("deep")
    if not await go_portal(Vector2i(35,12),"ruins","ruins_transition"):return
    await capture("ruins")
    if not await go_portal(Vector2i(11,12),"deep","ruins_return"):return
    if not await go_portal(Vector2i(11,12),"cave","deep_return"):return
    if not await go_portal(Vector2i(11,12),"field","cave_return"):return
    if not await go_portal(Vector2i(35,12),"forest","forest_transition"):return
    await capture("forest")
    var impacts=game.event_log.filter(func(e):return e.event=="damage_applied" and e.details.source=="melee")
    check(impacts.size()>0 and impacts.all(func(e):return e.details.impact_time>=0.16),"damage_occurs_after_animation_impact_time")
    check(game.audio_events.size()>0,"original_wav_events_played",{"events":game.audio_events.size()})
    await key(KEY_F5)
    check(FileAccess.file_exists(game.save_path),"save_via_f5_input")
    var expected=game.store.read_state(game.save_path)
    game.store.write_state(root.path_join("expected-state.json"),expected)
    await capture("saved-forest")
    finish()

func choose_menu(title: String) -> bool:
    var index=game.choices.find(title)
    if index<0:return false
    for i in range(game.choices.size()):
        if game.selected==index:return true
        await key(KEY_DOWN,0.01)
    return false

func wear(title: String) -> bool:
    await key(KEY_I,0.01)
    if not await choose_menu(title):await key(KEY_ESCAPE,0.01);return false
    await key(KEY_E,0.01);await key(KEY_ESCAPE,0.01)
    return game.player.get("armor_equipped","")==title or game.player.equipped==title

func bind_skill(title: String) -> bool:
    await key(KEY_K,0.01)
    if not await choose_menu(title):await key(KEY_ESCAPE,0.01);return false
    await key(KEY_1,0.01);await key(KEY_ESCAPE,0.01)
    return game.player.hotbar[0]==title

func source_skills(job: int):
    check(game.save_loaded and game.player.get("validation_fixture","")=="CONTROLLED_LEVEL30_NOT_NATURAL_PLAYTHROUGH","labeled_fixture_not_natural_progress")
    check(game.player.job==game.Rules.JOBS[job] and game.player.level==30,"controlled_job_level30")
    await capture("outfit-before")
    check(await approach("shop"),"source_shop_reachable")
    for item in ["연두색 남자도복","철검"]:
        check(await choose_menu(item),"shop_contains_"+item)
        await key(KEY_B,0.02)
        check(game.player.inventory.get(item,0)==1,"actual_purchase_"+item)
    await key(KEY_ESCAPE,0.01)
    check(await wear("연두색 남자도복"),"actual_armor_equipped")
    check(await wear("철검"),"actual_iron_weapon_equipped")
    await capture("outfit-after")
    var guild=["guild","rogue_guild","mage_guild","poet_guild"][job]
    check(await guided(guild),"own_source_guild_reached")
    check(await approach("trainer") and game.menu=="trainer","own_class_trainer_dialogue")
    if game.menu!="trainer":finish();return
    var learned=[]
    for title in game.choices.duplicate():
        var s=game.rules.skill(game.player,title)
        if float(s.learn_level)>30:continue
        if title in game.player.skills:learned.append(title);continue
        check(await choose_menu(title),"select_source_skill_"+title)
        await key(KEY_ENTER,0.02)
        check(title in game.player.skills,"npc_learned_"+title)
        if title in game.player.skills:learned.append(title)
    await capture("source-class-training")
    await key(KEY_ESCAPE,0.01)
    check(await route(Vector2i(8,23)) and game.player.map=="village","source_class_guild_door_exit")
    check(await guided("field"),"source_class_hunting_field")
    if game.player.map!="field":finish();return
    for title in learned:
        var profile=game.rules.skill_profile(game.player,title)
        if profile.type=="damage" and game.player.map!="field":check(await guided("field"),"return_to_targets_"+title)
        if profile.type=="damage":
            var nearest=999.0;var target={}
            for e in game.entities.values():
                var d=Vector2i(e.x,e.y).distance_to(game.cell())
                if e.alive and e.map==game.player.map and d<nearest:target=e;nearest=d
            if target.is_empty():
                var wait_for=30.0
                for e in game.entities.values():
                    if e.map==game.player.map and not e.alive:wait_for=minf(wait_for,float(e.respawn))
                await pause(maxf(0.2,wait_for)+0.3)
                for e in game.entities.values():
                    if e.alive and e.map==game.player.map:target=e;nearest=Vector2i(e.x,e.y).distance_to(game.cell());break
                if target.is_empty():check(false,"no_respawned_spell_target_"+title);continue
            if nearest>5:
                for d in range(4):
                    var at=Vector2i(target.x,target.y)-game.DIRECTIONS[d]
                    if game.free_cell(game.player.map,at) and await route(at):break
        check(await bind_skill(title),"hotbar_"+title)
        var count=game.event_log.filter(func(e):return e.event=="skill_cast" and e.details.skill==title).size()
        var mp=int(game.player.mp);var hp=int(game.player.hp)
        await key(KEY_1,0.08)
        if title==learned[0] or profile.type in ["damage","stealth","animal","disguise"]:await capture("cast-"+str(learned.find(title)))
        await pause(0.48)
        var events=game.event_log.filter(func(e):return e.event=="skill_cast" and e.details.skill==title)
        check(events.size()==count+1,"source_skill_resolves_"+title,{"hp_before":hp,"hp_after":game.player.hp,"mp_before":mp,"mp_after":game.player.mp,"behavior":profile.type})
        if profile.type in ["buff","light","stealth","animal","disguise"]:check(game.player.buffs.get(title,0)>0,"active_state_"+title)
        if profile.type=="damage":check(game.event_log.any(func(e):return e.event=="damage_applied" and e.details.get("skill","")==title),"live_spell_damage_"+title)
        if profile.type in ["compass","travel","inspect"] and game.menu!="":await key(KEY_ESCAPE,0.01)
    if job==0:
        # Source maps are actual progression regions, with combat NPCs and exits.
        # This tour uses the labeled level-30 fixture and is not leveling evidence.
        for destination in ["village","inn","source_smith","rogue_guild","mage_guild","poet_guild","field"]:
            if game.player.map!=destination:
                if game.player.map!="village":
                    if game.maps[game.player.map].kind=="interior":
                        var portal=game.maps[game.player.map].portals[0]
                        check(await route(Vector2i(portal.x,portal.y)),"tour_interior_exit")
                    else:check(await guided("village"),"tour_return_guide")
                if destination!="village":check(await guided(destination),"tour_"+destination)
            await capture("tour-"+destination)
        for destination in ["cave","bat_den","cave","field","forest","deep","ruins"]:
            var portals=game.maps[game.player.map].portals.filter(func(p):return p.target==destination)
            if portals.is_empty():check(false,"missing_connected_region_"+destination);continue
            check(await route(Vector2i(portals[0].x,portals[0].y)) and game.player.map==destination,"walk_source_region_"+destination)
            await capture("tour-"+destination)
        check(await guided("village"),"tour_return_from_advanced_region")
        check(await guided("field"),"tour_return_field_for_rabbit_region")
        for destination in ["rabbit_depth","foraged"]:
            var portals=game.maps[game.player.map].portals.filter(func(p):return p.target==destination)
            check(not portals.is_empty() and await route(Vector2i(portals[0].x,portals[0].y)) and game.player.map==destination,"walk_source_region_"+destination)
            await capture("tour-"+destination)
    await key(KEY_F5,0.05)
    var expected=game.store.read_state(game.save_path)
    game.store.write_state(root.path_join("expected-state.json"),expected)
    await capture("content-saved")
    finish()

func clear_route(target: Vector2i) -> bool:
    for attempt in range(10):
        if await route(target):return true
        if not await hunt_one():return false
        await key(KEY_G,0.02)
    return false

func tour_resume():
    check(game.save_loaded and game.player.get("validation_fixture","")!="","tour_reuses_labeled_saved_fixture")
    check(await guided("village"),"tour_resume_return_home")
    check(await guided("field"),"tour_resume_field")
    for destination in ["cave","bat_den","cave","field","forest","deep","ruins"]:
        var portals=game.maps[game.player.map].portals.filter(func(p):return p.target==destination)
        if portals.is_empty():check(false,"no_source_exit_"+destination);break
        check(await clear_route(Vector2i(portals[0].x,portals[0].y)) and game.player.map==destination,"cleared_walk_source_region_"+destination)
        await capture("tour-"+destination)
        if game.player.map!=destination:break
    check(game.event_log.any(func(e):return e.event=="monster_killed"),"actual_dungeon_combat_clears_path")
    check(game.event_log.any(func(e):return e.event=="monster_attack_started"),"source_monster_attack_motion_triggered")
    await key(KEY_F5,0.04)
    var expected=game.store.read_state(game.save_path)
    game.store.write_state(root.path_join("expected-state.json"),expected)
    await capture("content-saved")
    finish()

func content_actions(mode: String):
    check(game.save_loaded and game.player.has("validation_fixture"),"controlled_action_fixture_labeled")
    check(await guided("village"),"action_return_to_city")
    for room in ["town-room-5","town-room-43","town-room-10"]:
        check(await guided(room),"native_town_door_room_"+room)
        await capture("native-"+room)
        var role="revive" if room=="town-room-10" else "shop"
        check(await approach(role),"native_room_service_"+room)
        if role=="shop":
            var title="초록색 도포" if room=="town-room-5" else "토끼고기"
            check(await choose_menu(title),"specialized_stock_"+title)
            await key(KEY_B,0.03)
            check(game.player.inventory.get(title,0)>0,"native_room_actual_purchase_"+title)
            await key(KEY_ESCAPE,0.03)
        var portal=game.maps[game.player.map].portals[0]
        check(await route(Vector2i(portal.x,portal.y)) and game.player.map=="village","native_room_exit_"+room)
    check(await bind_skill("비영사천문"),"common_compass_hotkey")
    await key(KEY_1,0.06)
    await key(KEY_F5,0.03)
    check(game.event_log.any(func(e):return e.event=="save_queued_until_action_resolves"),"save_waits_for_inflight_cast")
    await pause(0.5)
    check(game.menu=="compass" and game.event_log.any(func(e):return e.event=="save_written" and e.details.success),"compass_resolved_and_save_written")
    await key(KEY_DOWN,0.02)
    await key(KEY_DOWN,0.02)
    await key(KEY_ENTER,0.03)
    check(game.player.map=="village" and game.player.y>100,"common_compass_reaches_south_city")
    await capture("original-city-south")
    # Return through the actual common spell and town guide, not state edits.
    check(await bind_skill("비영사천문"),"common_compass_rebind")
    await key(KEY_1,0.05);await pause(1.0)
    # A repeated key inside the still-open menu is not a cast; choose then return.
    if game.menu=="compass":await key(KEY_ESCAPE,0.01)
    # Actor can use the common spirit-return spell while alive too.
    check(await bind_skill("성황령"),"common_spirit_return_hotkey")
    await key(KEY_1,0.04);await pause(0.5)
    check(game.cell()==Vector2i(game.maps.village.entry[0],game.maps.village.entry[1]),"common_spirit_return_home_entry")
    if mode=="content-actions":
        check(await guided("field"),"light_action_field")
        var portal=game.maps.field.portals.filter(func(p):return p.target=="cave")[0]
        check(await clear_route(Vector2i(portal.x,portal.y)) and game.player.map=="cave","light_action_enters_dungeon")
        # Fixture light buffs were deliberately zeroed before launch.
        await capture("light-before")
        check(await bind_skill("누리의빛"),"light_spell_hotkey")
        await key(KEY_1,0.03);await pause(0.5)
        check(game.player.buffs.get("누리의빛",0)>0,"light_spell_active_visibility")
        await capture("light-after")
    else:
        # Active poison was included in this labeled input fixture.
        check(game.player.buffs.get("독",0)>0,"active_poison_fixture_remains")
        var hp=int(game.player.hp);await pause(1.1)
        check(game.player.hp<hp,"actual_poison_tick_lowers_hp")
        check(await bind_skill("해독"),"cure_hotkey")
        await key(KEY_1,0.03);await pause(0.5)
        check(not game.player.buffs.has("독"),"actual_cure_removes_poison")
        hp=int(game.player.hp);await pause(1.1)
        check(game.player.hp==hp,"poison_damage_stops_after_cure")
        await capture("cured")
    check(await bind_skill("물품감정"),"common_item_inspection_hotkey")
    await key(KEY_1,0.03);await pause(0.5)
    check(game.menu=="inventory","inspection_opens_actual_item_stats")
    await capture("item-inspection")
    await key(KEY_ESCAPE,0.02)
    await key(KEY_F5,0.03)
    game.store.write_state(root.path_join("expected-state.json"),game.store.read_state(game.save_path))
    await capture("action-saved")
    finish()

func town_all():
    check(game.player.has("validation_fixture"),"town_room_fixture_labeled")
    check(await guided("village"),"town_room_start")
    for m in game.world.maps:
        if not str(m.id).begins_with("town-room-"):continue
        if game.player.has("town_verified") and m.id in game.player.town_verified:continue
        check(await guided(m.id),"town_room_enter_"+m.id)
        if game.player.map!=m.id:break
        await capture("room-"+m.id)
        var n=m.npcs[0]
        check(await approach(n.role),"town_room_service_"+m.id)
        if n.role=="shop":
            var title="초보 회복약"
            var quantity=int(game.player.inventory.get(title,0))
            check(await choose_menu(title),"town_room_shop_stock_"+m.id)
            await key(KEY_B,0.02)
            check(game.player.inventory.get(title,0)==quantity+1,"town_room_shop_transaction_"+m.id)
        elif n.role=="inn":
            var gold=int(game.player.gold)
            await key(KEY_H,0.02)
            check(game.player.gold==gold-5 and game.player.hp==game.player.hp_max,"town_room_actual_rest_"+m.id)
        elif n.role=="revive":check(game.player.hp==game.player.hp_max,"town_room_actual_healer_"+m.id)
        elif n.role=="travel":check(game.menu=="travel","town_room_functional_return_guide_"+m.id)
        if game.menu!="":await key(KEY_ESCAPE,0.02)
        check(await clear_route(Vector2i(m.portals[0].x,m.portals[0].y)) and game.player.map=="village","town_room_exit_"+m.id)
        if game.player.map!="village":break
        if not game.player.has("town_verified"):game.player.town_verified=[]
        game.player.town_verified.append(m.id)
        await key(KEY_F5,0.03)
        var partial=FileAccess.open(root.path_join("partial-checks.json"),FileAccess.WRITE)
        partial.store_string(JSON.stringify({"status":"PARTIAL_EXECUTED","checks":checks,"completed_rooms":game.player.town_verified,
            "rendered_tile_ids":game.assets.used_tiles.keys(),"rendered_actor_frames":game.assets.used_frames.keys(),
            "events":game.event_log,"audio_events":game.audio_events}));partial.close()
    await key(KEY_F5,0.03)
    game.store.write_state(root.path_join("expected-state.json"),game.store.read_state(game.save_path))
    await capture("town-saved")
    finish()

func gear_guide():
    check(game.save_loaded and game.player.has("validation_fixture"),"gear_fixture_not_natural_growth")
    check(await guided("village"),"gear_return_city")
    check(await approach("shop"),"gear_actual_shop")
    for item in ["초록색 도포","보라 남자갑옷","장창"]:
        check(await choose_menu(item),"gear_shop_stock_"+item)
        await key(KEY_B,0.02)
        check(game.player.inventory.get(item,0)>0,"gear_shop_purchase_"+item)
    await key(KEY_ESCAPE,0.02)
    for item in ["초록색 도포","보라 남자갑옷","장창"]:
        check(await wear(item),"gear_actual_equip_"+item)
        await capture("gear-"+str(["초록색 도포","보라 남자갑옷","장창"].find(item)))
    check(await guided("field"),"gear_source_field")
    check(await hunt_one("rabbit"),"source_spear_actual_combat")
    check(game.player.equipped=="장창" and game.assets.used_frames.keys().any(func(k):return str(k).begins_with("spear_weapon:")),"source_spear_frames_actually_drawn")
    await capture("spear-combat")
    check(await guided("village") and await guided("town-room-50"),"corrected_source_room_entry")
    await capture("corrected-guide-position")
    check(await approach("travel") and game.menu=="travel","corrected_guide_reachable_in_normal_room")
    await key(KEY_ESCAPE,0.02)
    var portal=game.maps[game.player.map].portals[0]
    check(await clear_route(Vector2i(portal.x,portal.y)) and game.player.map=="village","corrected_room_normal_exit")
    await key(KEY_F5,0.03)
    game.store.write_state(root.path_join("expected-state.json"),game.store.read_state(game.save_path))
    await capture("gear-saved")
    finish()

func natural_progress():
    check(game.save_loaded and not game.player.has("validation_fixture") and game.player.level==5 and game.player.kills>=25,"resume_previous_actual_level5_not_fixture")
    var old_inventory=game.loaded_snapshot.player.inventory.duplicate(true)
    check(game.player.inventory==old_inventory,"old_save_inventory_preserved_on_new_layout")
    check(await guided("village"),"natural_return_home")
    check(await approach("shop"),"natural_shop")
    check(await choose_menu("초보 회복약"),"natural_potion_stock")
    var budget=mini(15,int(game.player.gold)/10)
    for i in range(budget):await key(KEY_B,0.02)
    await key(KEY_ESCAPE,0.02)
    check(await guided("field"),"natural_field")
    var portal=game.maps.field.portals.filter(func(p):return p.target=="cave")[0]
    check(await clear_route(Vector2i(portal.x,portal.y)) and game.player.map=="cave","natural_rat_cave")
    var deadline=Time.get_ticks_msec()+360000
    while game.player.level<10 and game.player.hp>0 and Time.get_ticks_msec()<deadline:
        if game.player.hp<game.player.hp_max*0.60 and game.player.inventory.get("초보 회복약",0)>0:await use_potion()
        if not await hunt_one("rat"):await pause(0.3)
        if game.player.level>=6:break # Resume milestone; no fabricated level-30 completion.
    check(game.player.level>=6,"natural_growth_beyond_old_level5",{"level":game.player.level,"kills":game.player.kills})
    await capture("natural-level-progress")
    await key(KEY_F5,0.04);await pause(0.5)
    game.store.write_state(root.path_join("expected-state.json"),game.store.read_state(game.save_path))
    finish()

func finish():
    print("SCREEN_STAGE finish_audio elapsed_ms="+str(Time.get_ticks_msec()-started))
    if game.recorder.is_recording_active():
        game.recorder.set_recording_active(false)
        var stream=game.recorder.get_recording()
        if stream!=null:
            var path=root.path_join("mixed-audio.wav")
            var ok=stream.save_to_wav(path)==OK
            check(ok,"engine_audio_mix_recorded")
    print("SCREEN_STAGE finish_report elapsed_ms="+str(Time.get_ticks_msec()-started))
    var failures=checks.filter(func(c):return c.status!="PASS").size()
    var report={"status":"PASS_EXECUTED_SCREEN_INPUT" if failures==0 else "FAIL","checks":checks,
        "elapsed_ms":Time.get_ticks_msec()-started,"screenshots":screenshots,"events":game.event_log,
        "registered_tiles":game.assets.tiles.size(),"registered_tile_sources":game.assets.tile_set.get_source_count(),
        "rendered_tile_ids":game.assets.used_tiles.keys(),"rendered_actor_frames":game.assets.used_frames.keys(),
        "Work_rendered_sheet_frame_ids":game.work_assets.used_frames.keys(),"content_version":game.content.version,
        "game_build":game.store.game_build,"Work_frame_texture_pages":game.work_assets.frame_textures.size(),
        "Work_cached_texture_bytes":game.work_assets.texture_bytes,
        "audio_events":game.audio_events,"player":game.player,"save_loaded":game.save_loaded,
        "scope":"REAL_X11_GODOT_VIEWPORT_WITH_INPUT_EVENTS_NOT_FULL_1_TO_99_PLAYTHROUGH"}
    var file=FileAccess.open(root.path_join(game.test_mode+"-report.json"),FileAccess.WRITE)
    file.store_string(JSON.stringify(report,"  "));file.close()
    print("SCREEN_STAGE quit elapsed_ms="+str(Time.get_ticks_msec()-started))
    game.get_tree().quit(0 if failures==0 else 1)
