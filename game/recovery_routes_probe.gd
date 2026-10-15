extends "res://recovery_play_probe.gd"
## Representative Work routes through real keys, portals and NPC transactions.
## Reads the graph to plan; never assigns character position, stats or rewards.
var route_legs=[]
var reached_maps=[]
var starting_player={}

func run(g, mode: String, directory: String):
    game=g;root=directory;started=Time.get_ticks_msec();deadline=started+900000;recovery_mode=mode
    DirAccess.make_dir_recursive_absolute(root)
    if not game.save_loaded:
        check(game.menu=="creation","representative_route_starts_on_real_creation_screen")
        if game.menu!="creation":finish();return
        game.name_edit.release_focus();await key(KEY_ENTER,.15)
        check(game.player.level==1 and game.player.job=="평민","representative_route_creates_unmodified_commoner")
    else:check(not game.player.is_empty(),"representative_route_uses_isolated_real_saved_character")
    starting_player=game.player.duplicate(true)
    if game.player.equipped=="":await key(KEY_E,.1)
    reached_maps.append(game.player.map)
    if not await visit("wk.map.city.goguryeo","work-city"):finish();return
    if not await visit("wk.map.region.squirrel","work-novice-field"):finish();return
    var live=game.entities_by_map.get(game.player.map,[]).filter(func(e):return e.alive)
    check(not live.is_empty(),"representative_work_field_has_actual_live_monsters",{"live":live.size(),"species":live.map(func(e):return {"id":e.kind,"name":e.spec.name,"hp":e.hp,"x":e.x,"y":e.y})})
    if not await visit("wk.map.exp2.na495.485","forest-supply-hub"):finish();return
    var shop=await npc_service("wk.npc.exp2.forest.1.supplier","shop")
    check(shop and game.menu=="shop","actual_expansion_supplier_opens_shop_by_input")
    if not shop:finish();return
    var potion="wk.item.exp2.potion.0.heal_hp";var potion_index=game.choices.find(potion)
    check(potion_index>=0,"expansion_shop_lists_activated_item")
    if potion_index<0:finish();return
    for i in range(potion_index):await key(KEY_DOWN,.02)
    var before_gold=int(game.player.gold);var before_quantity=int(game.player.inventory.get(potion,0))
    if before_gold>=12:
        await key(KEY_ENTER,.15)
        check(int(game.player.gold)==before_gold-12 and int(game.player.inventory.get(potion,0))==before_quantity+1,"actual_expansion_purchase_transfers_exact_item_and_gold",{"gold_before":before_gold,"gold_after":game.player.gold,"quantity_before":before_quantity,"quantity_after":game.player.inventory.get(potion,0)})
    else:checks.append({"name":"actual_expansion_purchase_transfers_exact_item_and_gold","status":"NOT_RUN","observed":{"reason":"Isolated saved character lacks the legitimate twelve-gold purchase price."}})
    await capture("routes-expansion-shop");await close_menu()
    if not await visit("wk.map.exp2.na495.2544","forest-first-hunting-scene"):finish();return
    var forest_live=game.entities_by_map.get(game.player.map,[]).filter(func(e):return e.alive)
    check(not forest_live.is_empty(),"next_expansion_hunting_scene_has_live_actors",{"live":forest_live.size(),"name":game.maps[game.player.map].name})
    if not await visit("wk.map.exp2.na495.485","forest-return-supply"):finish();return
    if not await visit("wk.map.region.squirrel","novice-return-link"):finish();return
    if not await visit("wk.map.city.goguryeo","return-work-city"):finish();return
    if not await visit("wk.map.facility.6342eaa664db","goguryeo-inn"):finish();return
    var inn=await npc_service("kr.npc.6342eaa664db","rest")
    check(inn and game.player.hp==game.player.hp_max and game.player.mp==game.player.mp_max,"actual_work_inn_rest_service_recovers_character")
    await close_menu()
    if not await visit("wk.map.city.buyeo","buyeo-city"):finish();return
    if not await visit("wk.map.facility.91be45f57bba","buyeo-inn"):finish();return
    var inn_npc=""
    for n in game.maps[game.player.map].npcs:
        if n.get("services",[]).any(func(s):return s.get("type","")=="shop"):inn_npc=n.get("definition_id",n.id);break
    var second_shop=inn_npc!="" and await npc_service(inn_npc,"shop")
    check(second_shop and game.menu=="shop" and not game.choices.is_empty(),"second_city_inn_lists_real_shop_content")
    await capture("routes-buyeo-inn-shop");await close_menu()
    if not await visit("village","return-original-home"):finish();return
    check(reached_maps.size()>=8,"eight_unique_representative_maps_reached_by_input",{"maps":reached_maps})
    check(game.player.hp>0,"representative_round_trip_returns_alive",{"hp":game.player.hp,"max":game.player.hp_max})
    await key(KEY_F5,.2)
    var saved=game.store.read_state(game.save_path)
    check(not saved.is_empty() and saved.player.map=="village" and saved.player.inventory==game.player.inventory,"representative_trip_saved_with_actual_purchases")
    if not saved.is_empty():game.store.write_state(root.path_join("routes-expected-state.json"),saved)
    stage="representative-round-trip-complete";finish()

func close_menu():
    if game.menu!="":await key(KEY_ESCAPE,.04)

func visit(destination: String, title: String) -> bool:
    if Time.get_ticks_msec()>=deadline:
        checks.append({"name":"route_"+title,"status":"BLOCKED","observed":{"reason":"Normal-timer representative-route deadline reached."}});return false
    var origin=game.player.map
    var plan=MapView.region_route(game.maps,origin,destination,game.world.get("map_aliases",{}))
    var before_position=game.cell();var began=Time.get_ticks_msec()
    var arrived=await guided(destination)
    var leg={"title":title,"from":origin,"to":destination,"before":before_position,"after":game.cell(),"actual_map":game.player.map,"elapsed_ms":Time.get_ticks_msec()-began,"plan_status":plan.status,"edges":plan.get("edges",[]),"hp":game.player.hp}
    route_legs.append(leg)
    check(arrived and game.player.map==destination,"route_"+title,leg)
    if not arrived:return false
    for event in game.event_log:
        if event.event=="map_changed":
            var id=event.get("details",{}).get("map","")
            if id!="" and id not in reached_maps:reached_maps.append(id)
    if destination not in reached_maps:reached_maps.append(destination)
    stage=title
    await capture("routes-"+title)
    write_progress()
    return true

func npc_service(definition_id: String, service_type: String) -> bool:
    await close_menu()
    var placement=""
    for n in game.maps[game.player.map].npcs:
        if n.get("definition_id",n.id)==definition_id:placement=n.id;break
    if placement=="" or not await speak_npc(placement):return false
    if game.menu!="services":return false
    var index=game.choices.find_custom(func(service):return service.get("type","")==service_type)
    if index<0:return false
    for i in range(index):await key(KEY_DOWN,.02)
    await key(KEY_ENTER,.12)
    return true

func write_progress():
    var out=FileAccess.open(root.path_join("recovery-routes-progress.json"),FileAccess.WRITE)
    if out!=null:out.store_string(JSON.stringify({"stage":stage,"elapsed_ms":Time.get_ticks_msec()-started,"checks":checks,"route_legs":route_legs,"reached_maps":reached_maps,"player":{"map":game.player.map,"level":game.player.level,"job":game.player.job,"hp":game.player.hp,"gold":game.player.gold}},"  "));out.close()
    print("ROUTES_PROGRESS "+JSON.stringify({"stage":stage,"reached":reached_maps.size(),"elapsed_ms":Time.get_ticks_msec()-started,"map":game.player.map,"hp":game.player.hp}))

func finish():
    if completed:return
    completed=true
    var failures=checks.filter(func(c):return c.status in ["FAIL","BLOCKED"]).size()
    var report={"status":"PASS" if failures==0 else "FAIL","scope":"ACTUAL_NORMAL_INPUT_REPRESENTATIVE_WORK_ROUND_TRIP_AND_NPC_TRANSACTIONS; NOT_ALL_MAPS_NOT_ALL_MONSTER_COMBAT","checks":checks,"route_legs":route_legs,"reached_maps":reached_maps,"platform":OS.get_name(),"display":DisplayServer.get_name(),"content_version":game.content.version,"game_build":game.store.game_build,"elapsed_ms":Time.get_ticks_msec()-started,"stage":stage,"screenshots":screenshots,"events":game.event_log,"starting_player":starting_player,"player":game.player,"time_scale":Engine.time_scale}
    var out=FileAccess.open(root.path_join("recovery-routes-report.json"),FileAccess.WRITE)
    if out!=null:out.store_string(JSON.stringify(report,"  "));out.close()
    print("ROUTES_RESULT "+JSON.stringify({"status":report.status,"checks":checks,"reached_maps":reached_maps,"elapsed_ms":report.elapsed_ms}))
    game.get_tree().quit(0 if failures==0 else 1)
