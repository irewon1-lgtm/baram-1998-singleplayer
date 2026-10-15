extends "res://exercise.gd"
## Normal-timer playthrough: only keyboard actions choose movement/combat/NPCs.
## No levels, rewards, damage, resources, target positions or time scale are injected.
var recovery_mode = ""
var deadline = 0
var completed = false
var stage = ""
var potion_uses = 0
const MapView = preload("res://world_map_view.gd")

func check(ok: bool, name_value: String, info = {}):
    checks.append({"name":name_value,"status":"PASS" if ok else "FAIL","observed":info.duplicate(true) if info is Dictionary or info is Array else info,"elapsed_ms":Time.get_ticks_msec()-started})
    print("SCREEN_CHECK " + name_value + " " + ("PASS" if ok else "FAIL"))

func capture(title: String):
    if DisplayServer.get_name() == "headless":return
    await RenderingServer.frame_post_draw
    var image = game.get_viewport().get_texture().get_image()
    if image.is_empty():return
    var path = root.path_join(title + ".png")
    var ok = image.save_png(path) == OK
    screenshots.append({"name":title,"path":path,"width":image.get_width(),"height":image.get_height(),"status":"PASS" if ok else "FAIL","sha256":FileAccess.get_sha256(path) if ok else ""})

func run(g, mode: String, directory: String):
    game = g;root = directory;started = Time.get_ticks_msec();deadline = started + 1150000;recovery_mode = mode
    DirAccess.make_dir_recursive_absolute(root)
    if mode == "recovery-core" and game.save_loaded:
        mode = "recovery-restart";recovery_mode = mode
    if mode == "recovery-restart":
        check(game.save_loaded, "fresh_process_read_saved_character")
        var expected = game.store.read_state(root.path_join("expected-state.json"))
        check(not expected.is_empty() and game.loaded_snapshot.player == expected.get("player", {}), "fresh_process_preserves_entire_character")
        check(not expected.is_empty() and game.loaded_snapshot.world == expected.get("world", {}) and game.loaded_snapshot.loot == expected.get("loot", []), "fresh_process_preserves_monsters_and_drops")
        check(not expected.is_empty() and str(game.loaded_snapshot.rng_state) == str(expected.get("rng_state", "")), "fresh_process_preserves_rng")
        await capture("recovery-restarted");finish();return
    if mode == "recovery-attack":
        check(game.save_loaded and game.player.job == "주술사" and game.player.level >= 5, "resume_previously_earned_mage_save_without_fixture")
        if not game.save_loaded or game.player.job != "주술사" or game.player.level < 5:finish();return
        await natural_attack_spell_extension()
        checkpoint("attack-extension-complete")
        await key(KEY_F5, 0.2)
        var extended_save = game.store.read_state(game.save_path)
        if not extended_save.is_empty() and checks.any(func(c):return c.name == "natural_level6_attack_spell_use" and c.status == "PASS"):game.store.write_state(root.path_join("expected-state.json"), extended_save)
        finish();return
    check(not game.save_loaded and game.menu == "creation", "fresh_creation_screen")
    if game.save_loaded or game.menu != "creation":finish();return
    await capture("recovery-creation")
    game.name_edit.release_focus()
    await key(KEY_ENTER, 0.2)
    check(not game.player.is_empty() and game.player.level == 1 and game.player.job == "평민", "new_character_is_level1_commoner")
    check(game.player.skills.is_empty() and game.player.hotbar == ["", "", ""], "level1_has_no_unlearned_attack_or_teleport_skills")
    check(game.player.map == game.world.start.map, "new_character_starts_in_actual_village")
    await key(KEY_E, 0.1)
    check(game.player.equipped != "", "starter_weapon_equipped_by_normal_key")
    var initial_position = game.cell()
    for d in range(4):
        if game.free_cell(game.player.map, initial_position + game.DIRECTIONS[d], "", d):
            await key([KEY_UP, KEY_LEFT, KEY_DOWN, KEY_RIGHT][d], 0.24);break
    check(game.cell() != initial_position, "normal_direction_key_moves_character")
    await key(KEY_M, 0.15)
    check(game.menu == "world_map" and game.world_map_view.visible, "map_key_opens_actual_geometry_view")
    await capture("recovery-world-map")
    await key(KEY_ESCAPE, 0.1)
    check(game.menu == "" and not game.world_map_view.visible, "map_closes_without_consuming_movement")
    checkpoint("village-created")
    var arrived = await guided("field")
    check(arrived and game.player.map == "field", "actual_village_guide_reaches_hunting_field")
    if not arrived:finish();return
    await capture("recovery-field")
    var initial_xp = int(game.player.xp2)
    var initial_kills = int(game.player.kills)
    var killed = await hunt_normal_kind("토끼")
    check(killed and int(game.player.kills) > initial_kills, "normal_animated_attack_kills_actual_monster")
    check(int(game.player.xp2) > initial_xp, "normal_kill_awards_experience")
    if not killed:finish();return
    var last_checkpoint = int(game.player.kills)
    var failed_hunts = 0
    while int(game.player.kills) < 25 and Time.get_ticks_msec() < deadline and int(game.player.hp) > 0:
        if int(game.player.kills) >= 5 and "first_steps" not in game.player.quests:
            if not await claim_hunt_quests():break
            check(game.player.level >= 2 and "first_steps" in game.player.quests, "five_kill_quest_rewards_real_levelup")
            if not await guided("field"):break
        if int(game.player.hp) < int(game.player.hp_max) * 0.35:
            if not await recover_at_priest():break
        var name_value = "다람쥐" if item_count("도토리") < 10 else "토끼"
        if not await hunt_normal_kind(name_value):
            failed_hunts += 1
            await pause(0.35)
            if failed_hunts > 20:break
        else:failed_hunts = 0
        if int(game.player.kills) >= last_checkpoint + 5:
            last_checkpoint = int(game.player.kills);checkpoint("hunting-" + str(last_checkpoint))
    check(int(game.player.kills) >= 25, "25_normal_input_monster_kills", {"kills":game.player.kills,"hp":game.player.hp})
    check(game.event_log.any(func(e):return e.event == "item_picked_up"), "actual_random_drop_picked_up_via_key", {"inventory":game.player.inventory})
    if int(game.player.kills) < 25 or int(game.player.hp) <= 0:finish();return
    var claimed = await claim_hunt_quests()
    check(claimed and "hunter" in game.player.quests and game.player.level == 5 and game.player.job == "평민", "hunt_quests_reach_commoner5_without_auto_job", {"level":game.player.level,"job":game.player.job,"xp2":game.player.xp2,"quests":game.player.quests})
    if not claimed or int(game.player.level) != 5:finish();return
    checkpoint("commoner-level5")
    await capture("recovery-commoner-level5")
    check(await guided("mage_guild"), "guide_reaches_actual_mage_training_map")
    var trainer = await approach("trainer")
    check(trainer and game.menu == "job_selection", "commoner5_trainer_opens_explicit_job_choice")
    if not trainer or game.menu != "job_selection":finish();return
    var job_index = game.choices.find("주술사")
    for i in range(job_index):await key(KEY_DOWN, 0.03)
    await key(KEY_ENTER, 0.15)
    check(game.player.job == "주술사" and game.player.level == 5, "explicit_normal_NPC_choice_changes_job_at5")
    if game.player.job != "주술사":finish();return
    checkpoint("mage-level5")
    # Source learning costs are paid with actual random drops from normal hunting.
    if not await guided("field"):check(false, "return_field_for_skill_materials");finish();return
    failed_hunts = 0
    while (item_count("도토리") < 10 or item_count("토끼고기") < 10) and Time.get_ticks_msec() < deadline and int(game.player.hp) > 0:
        if int(game.player.hp) < int(game.player.hp_max) * 0.35:
            if not await recover_at_priest():break
        var name_value = "다람쥐" if item_count("도토리") < 10 else "토끼"
        if not await hunt_normal_kind(name_value):
            failed_hunts += 1;await pause(0.35)
            if failed_hunts > 20:break
        else:failed_hunts = 0
        if int(game.player.kills) >= last_checkpoint + 5:
            last_checkpoint = int(game.player.kills);checkpoint("materials-" + str(last_checkpoint))
    check(item_count("도토리") >= 10 and item_count("토끼고기") >= 10, "normal_random_drops_supply_real_skill_learning_cost", {"acorns":item_count("도토리"),"rabbit_meat":item_count("토끼고기"),"kills":game.player.kills})
    if item_count("도토리") < 10 or item_count("토끼고기") < 10:finish();return
    if not await guided("village") or not await guided("mage_guild") or not await approach("trainer"):
        check(false, "return_to_actual_skill_trainer");finish();return
    check(game.menu == "trainer", "assigned_job_opens_actual_skill_catalogue")
    var skill = "kr.spell.914bee820a84"
    var skill_index = game.choices.find(skill)
    check(skill_index >= 0, "level5_compass_present_in_real_catalogue")
    if skill_index < 0:finish();return
    var before_materials = [item_count("도토리"), item_count("토끼고기")]
    for i in range(skill_index):await key(KEY_DOWN, 0.02)
    await key(KEY_ENTER, 0.15)
    var learned = game.rules.knows_skill(game.player, skill)
    check(learned and item_count("도토리") == before_materials[0] - 10 and item_count("토끼고기") == before_materials[1] - 10, "compass_learned_with_exact_source_item_cost", {"skill":skill,"materials_before":before_materials,"materials_after":[item_count("도토리"),item_count("토끼고기")]})
    if not learned:finish();return
    await key(KEY_1, 0.06)
    await key(KEY_ESCAPE, 0.1)
    var mp_before = int(game.player.mp)
    await key(KEY_1, 0.7)
    check(game.menu == "compass" and int(game.player.mp) == mp_before - 3, "normally_learned_skill_casts_and_spends_source_MP")
    await capture("recovery-compass-choice")
    if game.menu == "compass":
        await key(KEY_ENTER, 0.35)
        check(game.player.map == "village" and game.event_log.any(func(e):return e.event == "compass_search"), "compass_gate_selection_changes_actual_map", game.navigation.last_compass)
    else:check(false, "compass_gate_selection_changes_actual_map")
    await natural_attack_spell_extension()
    checkpoint("playthrough-complete")
    await capture("recovery-before-restart")
    await key(KEY_F5, 0.15)
    await pause(0.25)
    var saved = game.store.read_state(game.save_path)
    var attack_completed = checks.any(func(c):return c.name == "natural_level6_attack_spell_use" and c.status == "PASS")
    check(not saved.is_empty() and saved.player.job == "주술사" and saved.player.level >= 6 and attack_completed, "complete_playthrough_saved_to_normal_save_format")
    if not saved.is_empty() and attack_completed:
        game.store.write_state(root.path_join("expected-state.json"), saved)
        check(game.store.read_state(root.path_join("expected-state.json")).player == saved.player, "restart_expected_state_written_and_reread")
    else:check(false, "restart_expected_state_written_and_reread", {"reason":"Required natural level6 attack did not complete; expected state was not overwritten."})
    finish()

func hunt_normal_kind(name_value: String) -> bool:
    if game.menu != "":await key(KEY_ESCAPE, 0.05)
    var candidates = game.entities.values().filter(func(e):return e.map == game.player.map and e.alive and e.spec.name == name_value)
    if candidates.is_empty():
        # Keep playing while the desired source spawn waits for its real timer.
        if await hunt_one():return true
        await pause(0.75);return false
    if await hunt_one(str(candidates[0].kind)):return true
    # A desired monster can be behind another living actor in a narrow passage.
    # Defeat an actually reachable nearby blocker with normal attacks, then retry.
    if await hunt_one():return true
    await pause(0.75);return false

func item_count(title: String) -> int:
    var id = game.rules.find_content("item", title).get("id", title)
    return int(game.player.inventory.get(id, 0)) + (int(game.player.inventory.get(title, 0)) if id != title else 0)

func claim_hunt_quests() -> bool:
    if not await guided("village"):return false
    for i in range(2):
        if game.menu != "":await key(KEY_ESCAPE, 0.03)
        if not await approach("quest"):return false
        if game.menu != "":await key(KEY_ESCAPE, 0.03)
    return true

func recover_at_priest() -> bool:
    if not await guided("village") or not await approach("revive"):return false
    var restored = int(game.player.hp) == int(game.player.hp_max)
    if game.menu != "":await key(KEY_ESCAPE, 0.03)
    return restored and await guided("field")

func guided(destination: String) -> bool:
    if game.player.map == destination:return true
    if game.menu != "":await key(KEY_ESCAPE, 0.03)
    var plan = MapView.region_route(game.maps, game.player.map, destination, game.world.get("map_aliases", {}))
    if plan.status != "FOUND":return false
    for edge in plan.edges:
        if Time.get_ticks_msec() >= deadline:return false
        if edge.get("trigger", "") == "npc_travel":
            if not await speak_npc(str(edge.npc_id)):return false
            if game.menu == "services":
                var service_index = game.choices.find_custom(func(s):return s.get("type", "") in ["travel", "teleport"] and edge.target in s.get("map_ids", []))
                if service_index < 0:return false
                for i in range(service_index):await key(KEY_DOWN, 0.02)
                await key(KEY_ENTER, 0.05)
            if game.menu != "travel":return false
            var index = game.choices.find(edge.target)
            if index < 0:return false
            for i in range(index):await key(KEY_DOWN, 0.02)
            await key(KEY_ENTER, 0.12)
        else:
            var before = game.player.map
            if not await route(Vector2i(edge.x, edge.y)):return false
            if game.player.map == before:await key(KEY_ENTER, 0.12)
        if game.player.map != edge.target:return false
    return game.player.map == destination

func speak_npc(id: String) -> bool:
    for npc in game.maps[game.player.map].npcs:
        if npc.id != id:continue
        for direction in range(4):
            var at = Vector2i(npc.x, npc.y) - game.DIRECTIONS[direction]
            if not game.free_cell(game.player.map, at):continue
            if await route(at):
                await key([KEY_UP, KEY_LEFT, KEY_DOWN, KEY_RIGHT][direction], 0.03, true)
                await key(KEY_ENTER, 0.08)
                return game.npc.get("id", "") == id
    return false

func natural_attack_spell_extension():
    # Continue with actual level-appropriate source rats, never grant an early spell.
    var extension_deadline = deadline - 60000
    if extension_deadline <= Time.get_ticks_msec():
        optional_not_run("natural_level6_attack_spell_use", "Core consumed the available natural-play deadline.");return
    if not await guided("field"):
        optional_not_run("natural_level6_attack_spell_use", "Could not naturally return to hunting field.");return
    var attempts = 0
    while item_count("도토리") < 10 and Time.get_ticks_msec() < extension_deadline and game.player.hp > 0:
        await normalize_health()
        if not await hunt_normal_kind("다람쥐"):
            attempts += 1
            if attempts > 20:break
        else:attempts = 0
    if item_count("도토리") < 10:
        optional_not_run("natural_level6_attack_spell_use", "Ten additional acorns were not earned within the bounded extension.");return
    if not await buy_healing_supplies():
        optional_not_run("natural_level6_attack_spell_use", "Earned gold could not buy normal healing supplies.");return
    if not await guided("cave"):
        optional_not_run("natural_level6_attack_spell_use", "Actual cave connection could not be traversed.");return
    attempts = 0
    while game.player.level < 6 and Time.get_ticks_msec() < extension_deadline and game.player.hp > 0:
        await normalize_health()
        if game.player.hp < game.player.hp_max * 0.4 and item_count("초보 회복약") == 0:
            if not await recover_at_priest() or not await guided("cave"):break
        if not await hunt_normal_kind("병든쥐"):
            attempts += 1
            if attempts > 15:break
        else:attempts = 0
        checkpoint("natural-attack-training-" + str(game.player.kills))
    if game.player.level < 6:
        optional_not_run("natural_level6_attack_spell_use", "Level6 was not naturally reached within the bounded extension.");return
    check(game.player.job == "주술사" and game.player.level >= 6, "normal_rat_rewards_reach_mage6", {"level":game.player.level,"kills":game.player.kills,"xp2":game.player.xp2})
    if not await guided("village") or not await guided("mage_guild") or not await approach("trainer"):
        optional_not_run("natural_level6_attack_spell_use", "Actual mage trainer could not be reached after level6.");return
    var spell = "kr.spell.cdc9baba76f2"
    var index = game.choices.find(spell)
    if game.menu != "trainer" or index < 0:
        check(false, "mage6_attack_spell_present_in_actual_catalogue");return
    for i in range(index):await key(KEY_DOWN, 0.02)
    var before_acorns = item_count("도토리")
    await key(KEY_ENTER, 0.1)
    var learned = game.rules.knows_skill(game.player, spell)
    check(learned and item_count("도토리") == before_acorns - 10, "attack_spell_learned_at6_with_real_acorn_cost")
    if not learned:return
    await key(KEY_2, 0.03)
    await key(KEY_ESCAPE, 0.03)
    if not await guided("field"):
        optional_not_run("natural_level6_attack_spell_use", "No target field reached after learning the attack spell.");return
    var before_damage = game.event_log.filter(func(e):return e.event == "damage_applied" and e.get("details", {}).get("source", "") == "skill").size()
    var kills_before = int(game.player.kills)
    var xp_before = int(game.player.xp2)
    var mp_before = int(game.player.mp)
    var casted = false
    for attempt in range(12):
        await key(KEY_TAB, 0.05)
        var target = game.entities.get(game.selected_target, {})
        if target.is_empty() or not target.alive or target.map != game.player.map:continue
        if Vector2i(target.x, target.y).distance_to(game.cell()) > 6 or not game.line_of_sight(game.player.map, game.cell(), Vector2i(target.x,target.y)):continue
        await key(KEY_2, 0.65);casted = true
        if game.event_log.filter(func(e):return e.event == "damage_applied" and e.get("details", {}).get("source", "") == "skill").size() > before_damage:break
    var hit = game.event_log.filter(func(e):return e.event == "damage_applied" and e.get("details", {}).get("source", "") == "skill").size() > before_damage
    if casted:check(hit and int(game.player.kills) > kills_before and int(game.player.xp2) > xp_before and int(game.player.mp) < mp_before, "natural_level6_attack_spell_use", {"spell":spell,"level":game.player.level,"skill_damage_events":game.event_log.filter(func(e):return e.event == "damage_applied" and e.get("details", {}).get("source", "") == "skill")})
    else:optional_not_run("natural_level6_attack_spell_use", "No visible live target was available for a legal spell cast.")
    await capture("recovery-legal-attack-spell")

func optional_not_run(name_value: String, reason: String):
    check(false, name_value, {"reason":reason,"level":game.player.level,"kills":game.player.kills,"required_for_native_core":true})

func use_potion():
    var count_before = item_count("초보 회복약")
    var hp_before = int(game.player.hp)
    if count_before <= 0 or hp_before >= int(game.player.hp_max):return
    if game.menu != "":await key(KEY_ESCAPE, 0.03)
    await key(KEY_I, 0.03)
    var index = game.choices.find_custom(func(id):return game.rules.display_name(str(id)) == "초보 회복약")
    if index >= 0:
        for i in range(index):await key(KEY_DOWN, 0.02)
        await key(KEY_U, 0.05)
        potion_uses += 1
        check(item_count("초보 회복약") == count_before - 1 and int(game.player.hp) > hp_before, "normal_potion_consumption_" + str(potion_uses), {"count_before":count_before,"count_after":item_count("초보 회복약"),"hp_before":hp_before,"hp_after":game.player.hp})
    else:check(false, "normal_potion_inventory_entry_exists")
    await key(KEY_ESCAPE, 0.03)

func normalize_health():
    for i in range(10):
        if int(game.player.hp) >= int(game.player.hp_max) * 0.85 or item_count("초보 회복약") <= 0:return
        await use_potion()

func buy_healing_supplies() -> bool:
    if not await guided("village") or not await approach("shop"):return false
    var index = game.choices.find_custom(func(id):return game.rules.display_name(str(id)) == "초보 회복약")
    if index < 0:return false
    for i in range(index):await key(KEY_DOWN, 0.02)
    var gold_before = int(game.player.gold)
    var count_before = item_count("초보 회복약")
    var unit_price = int(game.rules.item(str(game.choices[game.selected])).get("vendor_buy_price", 10))
    var count = mini(45, int(gold_before / maxi(1, unit_price)))
    if count <= 0:await key(KEY_ESCAPE, 0.03);return false
    for i in range(count):await key(KEY_B, 0.02)
    await key(KEY_ESCAPE, 0.03)
    var bought = item_count("초보 회복약") == count_before + count and int(game.player.gold) == gold_before - count * unit_price
    check(bought, "healing_supplies_bought_with_earned_hunting_gold", {"gold_before":gold_before,"gold_after":game.player.gold,"purchase_count":count,"unit_price":unit_price,"potions":item_count("초보 회복약"),"budget_limited":count < 45})
    await normalize_health()
    return bought

func checkpoint(name_value: String):
    stage = name_value
    game.save_game()
    if game.player.job == "주술사" and int(game.player.level) == 5:
        var earned = game.store.read_state(game.save_path)
        if not earned.is_empty():game.store.write_state(root.path_join("earned-level5-checkpoint.json"), earned)
    var progress = {"stage":stage,"elapsed_ms":Time.get_ticks_msec()-started,"checks":checks,"player":{"map":game.player.map,"level":game.player.level,"job":game.player.job,"kills":game.player.kills,"hp":game.player.hp,"xp2":game.player.xp2,"inventory":game.player.inventory},"game_build":game.store.game_build,"platform":OS.get_name()}
    var file = FileAccess.open(root.path_join("recovery-core-progress.json"), FileAccess.WRITE)
    if file != null:file.store_string(JSON.stringify(progress, "  "));file.close()
    print("RECOVERY_CHECKPOINT " + JSON.stringify(progress))

func finish():
    if completed:return
    completed = true
    var failures = checks.filter(func(c):return c.status != "PASS").size()
    var report = {"status":"PASS" if failures == 0 else "FAIL","checks":checks,"platform":OS.get_name(),"game_build":game.store.game_build,"elapsed_ms":Time.get_ticks_msec()-started,"stage":stage,"scope":"ACTUAL_INPUT_NORMAL_TIMERS_NOVICE_JOB_LEARNED_SKILLS; inspect individual checks for level6 extension; NOT_FULL_CONTENT_NOT_LEVEL1_TO99","display":DisplayServer.get_name(),"screenshots":screenshots,"events":game.event_log,"player":game.player,"content_version":game.content.version,"save_loaded":game.save_loaded,"time_scale":Engine.time_scale}
    report["harness_base_sha256"] = "7a4f1fae1a38818ff8b4d4e1c021288ba4ef13d5d69f2d7d4a0856b4057d283b"
    report["harness_patch_scope"] = "TEST_ONLY_NORMAL_ITEM_HEALING_AND_STRICT_REQUIRED_LEVEL6_ATTACK_AND_SAME_MODE_RESTART"
    report["production_source_modified_by_harness"] = false
    var file = FileAccess.open(root.path_join(recovery_mode + "-report.json"), FileAccess.WRITE)
    if file != null:file.store_string(JSON.stringify(report, "  "));file.close()
    print("RECOVERY_RESULT " + JSON.stringify({"status":report.status,"checks":checks,"platform":report.platform,"game_build":report.game_build,"stage":stage,"elapsed_ms":report.elapsed_ms}))
    print("BARAM_RECOVERY_RESULT " + JSON.stringify({"status":report.status,"checks":checks.size(),"report":recovery_mode + "-report.json"}))
    game.get_tree().quit(0 if failures == 0 else 1)
