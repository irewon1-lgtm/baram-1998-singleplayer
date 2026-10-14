extends "res://exercise.gd"
## One short normal-input integration pass; no injected levels or rewards.

func run(g, mode: String, directory: String):
    game=g;root=directory;started=Time.get_ticks_msec()
    DirAccess.make_dir_recursive_absolute(root)
    if mode=="work-restart":
        check(game.save_loaded,"Work_fresh_process_loaded_save")
        var expected=game.store.read_state(root.path_join("expected-state.json"))
        check(not expected.is_empty() and game.loaded_snapshot.player==expected.player,"Work_restart_preserves_entire_player")
        check(not expected.is_empty() and game.loaded_snapshot.world==expected.world and game.loaded_snapshot.loot==expected.loot,"Work_restart_preserves_world_and_loot")
        await capture("Work-restart")
        finish();return
    if mode=="work-visual":
        check(game.save_loaded and game.player.map=="wk.map.city.goguryeo","Visual_probe_uses_normally_reached_saved_Work_region")
        await key(KEY_DOWN,0.1,true)
        await capture("Work-corrected-region")
        var viewport=game.get_viewport().get_texture().get_image()
        var white_samples=0
        for y in range(48,528,4):
            for x in range(0,768,4):
                var color=viewport.get_pixel(x,y)
                if color.r==1 and color.g==1 and color.b==1:white_samples+=1
        check(white_samples<100,"Work_actor_pages_render_after_LRU_eviction",{"white_samples":white_samples,"sampled_pixels":23040})
        finish();return
    if mode=="work-package":
        await capture("Package-character-creation")
        game.name_edit.release_focus()
        await key(KEY_ENTER)
        check(not game.player.is_empty() and game.player.level==1,"Package_normal_character_creation")
        await key(KEY_E)
        check(game.player.equipped!="","Package_starter_equipment")
        var initial=game.cell()
        for d in range(4):
            if game.free_cell(game.player.map,initial+game.DIRECTIONS[d],"",d):
                await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][d]);break
        check(game.cell()!=initial,"Package_normal_input_movement")
        await key(KEY_2,0.5)
        check(game.menu=="compass","Package_Work_skill_assets_and_action")
        await capture("Package-Work-skill")
        await key(KEY_ESCAPE)
        await key(KEY_F5)
        var saved=game.store.read_state(game.save_path)
        check(not saved.is_empty(),"Package_save_written")
        if not saved.is_empty():game.store.write_state(root.path_join("expected-state.json"),saved)
        await capture("Package-saved")
        finish();return
    if mode=="work-regions":
        check(game.save_loaded,"Work_region_probe_loads_prior_game_save")
        if game.player.map!=game.world.home.map:
            var portals=game.maps[game.player.map].portals.filter(func(p):return p.target==game.world.home.map)
            if not portals.is_empty():
                check(true,"Work_existing_return_connection")
                check(await route(Vector2i(portals[0].x,portals[0].y)),"Work_normal_input_route_to_return_bridge")
                if game.player.map!=portals[0].target:await key(KEY_ENTER)
                check(game.player.map==game.world.home.map,"Work_return_bridge_reaches_preserved_old_home")
            else:check(await guided(game.world.home.map),"Work_existing_return_guide_connection")
        var bridges=game.maps[game.player.map].portals.filter(func(p):return p.get("id","")=="codex.bridge.Work")
        check(not bridges.is_empty(),"Work_integration_bridge_present")
        if not bridges.is_empty():
            check(await route(Vector2i(bridges[0].x,bridges[0].y)),"Work_normal_input_route_to_new_regions")
            await key(KEY_ENTER)
            check(game.player.map=="wk.map.city.goguryeo","Work_fixed_package_map_is_reached_in_normal_play")
            await capture("Work-connected-region")
            check(await approach("work_services"),"Work_defined_NPC_interaction_from_normal_input")
            check(game.menu in ["services","dialogue"],"Work_actual_package_NPC_services_or_dialogue")
            await capture("Work-connected-NPC")
            await key(KEY_ESCAPE)
        await key(KEY_F5)
        finish();return
    await capture("Work-character-creation")
    game.name_edit.release_focus()
    await key(KEY_ENTER)
    check(not game.player.is_empty() and game.player.level==1,"Work_normal_level1_character_created")
    await key(KEY_E)
    check(game.player.equipped!="","Work_existing_starter_equipment_is_migrated_and_equipped")
    for d in [KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT]:await key(d,0.04,true)
    await capture("Work-town-equipped")
    var initial=game.cell()
    for d in range(4):
        if game.free_cell(game.player.map,initial+game.DIRECTIONS[d],"",d):
            await key([KEY_UP,KEY_LEFT,KEY_DOWN,KEY_RIGHT][d]);break
    check(game.cell()!=initial,"Work_directional_movement_runs")
    var nearest={};var distance=99999.0
    for n in game.maps[game.player.map].npcs:
        var cost=Vector2i(n.x,n.y).distance_to(game.cell())
        if cost<distance:distance=cost;nearest=n
    if not nearest.is_empty():
        var target=Vector2i(nearest.x,nearest.y)
        var reached=false
        for offset in game.DIRECTIONS:
            if game.free_cell(game.player.map,target+offset):
                reached=await route(target+offset)
                if reached:break
        check(reached,"Work_normal_route_to_NPC")
        await key(KEY_ENTER)
        check(game.menu in ["services","dialogue","shop"],"Work_NPC_dialogue_or_services_connected")
        await capture("Work-NPC-services")
        await key(KEY_ESCAPE)
    var portal={}
    for p in game.maps[game.player.map].portals:
        if game.maps[p.target].spawns.any(func(s):return game.rules.monster(s.kind,game.world.replacements).name=="토끼"):
            portal=p;break
    if portal.is_empty():
        check(await guided("field"),"Work_existing_guide_reaches_beginner_original_map")
        await capture("Work-beginner-field")
        var rabbit=game.entities.values().filter(func(e):return e.map==game.player.map and e.alive and e.spec.name=="토끼")
        check(not rabbit.is_empty(),"Work_actual_monster_spawn_connected")
        if not rabbit.is_empty():
            var before=game.player.xp2
            check(await hunt_one(rabbit[0].kind),"Work_real_attack_kill_and_reward")
            check(game.player.xp2>before,"Work_kill_awards_experience")
            await key(KEY_G)
            await capture("Work-combat-and-loot")
    else:
        check(await route(Vector2i(portal.x,portal.y)),"Work_normal_route_to_beginner_portal")
        if game.player.map!=portal.target:await key(KEY_ENTER)
        check(game.player.map==portal.target,"Work_input_portal_transitions_to_original_layout")
        await capture("Work-beginner-field")
        var rabbit=game.entities.values().filter(func(e):return e.map==game.player.map and e.alive and e.spec.name=="토끼")
        check(not rabbit.is_empty(),"Work_actual_monster_spawn_connected")
        if not rabbit.is_empty():
            var before=game.player.xp2
            check(await hunt_one(rabbit[0].kind),"Work_real_attack_kill_and_reward")
            check(game.player.xp2>before,"Work_kill_awards_experience")
            await key(KEY_G)
            await capture("Work-combat-and-loot")
    var hp=game.player.hp
    var mp=game.player.mp
    await key(KEY_1,0.6)
    check(game.player.mp<mp,"Work_skill_hotkey_consumes_resource")
    await key(KEY_2,0.6)
    check(game.menu=="compass","Work_declarative_teleport_skill_opens_gate_selection")
    await capture("Work-original-skill-effect")
    await key(KEY_ESCAPE)
    await key(KEY_F5)
    var saved=game.store.read_state(game.save_path)
    check(not saved.is_empty(),"Work_v2_save_written")
    if not saved.is_empty():game.store.write_state(root.path_join("expected-state.json"),saved)
    await capture("Work-before-restart")
    finish()
