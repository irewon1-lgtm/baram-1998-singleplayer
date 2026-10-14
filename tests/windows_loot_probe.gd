extends "res://exercise.gd"
# Continue a copy of the preceding normal-input save. No seeded rewards or levels.
func run(g,mode,directory):
    game=g;root=directory;started=Time.get_ticks_msec()
    DirAccess.make_dir_recursive_absolute(root)
    check(game.save_loaded,"embedded_pack_loads_previous_normal_play_save")
    if not game.save_loaded:
        finish()
        return
    if mode=="windows-loot-restart":
        var expected=game.store.read_state(root.path_join("expected-state.json"))
        check(not expected.is_empty(),"expected_post_pickup_save_is_readable")
        check(not expected.is_empty() and game.loaded_snapshot.player==expected.player,"pickup_player_and_inventory_survive_fresh_process")
        check(not expected.is_empty() and game.loaded_snapshot.world==expected.world and game.loaded_snapshot.loot==expected.loot,"pickup_world_and_ground_items_survive_fresh_process")
        await capture("Windows-package-pickup-restart-Linux")
        finish()
        return
    var initial=game.player.inventory.duplicate(true)
    # Bound both attempts and elapsed time; only actual space/G input awards items.
    for attempt in range(8):
        if Time.get_ticks_msec()-started>45000:
            break
        var rabbits=game.entities.values().filter(func(e):return e.map==game.player.map and e.alive and e.spec.name=="토끼")
        if rabbits.is_empty() or game.player.hp<=0:
            break
        if not await hunt_one(rabbits[0].kind):
            break
        await key(KEY_G)
        if game.event_log.any(func(e):return e.event=="item_picked_up"):
            break
    var picked=game.event_log.filter(func(e):return e.event=="item_picked_up")
    check(not picked.is_empty(),"real_drop_and_normal_G_pickup",{"pickup_events":picked.size()})
    var increased=false
    for id in game.player.inventory:
        if int(game.player.inventory[id])>int(initial.get(id,0)):
            increased=true
    check(increased,"picked_item_quantity_increases_inventory")
    await capture("Windows-package-actual-pickup-Linux")
    await key(KEY_F5)
    var saved=game.store.read_state(game.save_path)
    check(not saved.is_empty() and saved.player.inventory==game.player.inventory,"picked_inventory_is_saved")
    if not saved.is_empty():
        game.store.write_state(root.path_join("expected-state.json"),saved)
    finish()
