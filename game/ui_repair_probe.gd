extends Node
## Rendered execution of the real UI and combat, without warps or stat/XP grants.
var game
var root=""
var results=[]
var shots=[]
var begin=0
func check(ok: bool,name: String,detail={}):
    var row={"test":name,"status":"PASS" if ok else "FAIL","observed":detail,"elapsed_ms":Time.get_ticks_msec()-begin}
    results.append(row);print("REPAIR_CHECK "+JSON.stringify(row));write_report()
func write_report():
    var f=FileAccess.open(root.path_join("story.json"),FileAccess.WRITE)
    f.store_string(JSON.stringify({"environment":OS.get_name()+" / "+DisplayServer.get_name(),"source_build":game.store.game_build,"content":game.content.version,"repair_version":game.world.get("repair_version",""),"checks":results,"screens":shots,"current_map":game.player.get("map",""),"normal_route_no_state_grants":true},"  "));f.close()
func wait(seconds: float=.16):await get_tree().create_timer(seconds).timeout
func touch(at: Vector2,pressed: bool,index: int=1):
    var e=InputEventScreenTouch.new();e.index=index;e.pressed=pressed;e.position=game.get_viewport().get_screen_transform()*at
    Input.parse_input_event(e);await get_tree().process_frame
func tap(at: Vector2):await touch(at,true);await touch(at,false);await wait(.14)
func panel(id: String):
    game.right_panel.layout()
    for t in game.right_panel.targets:
        if t.id==id:await tap(t.rect.get_center());return
func capture(name: String):
    if DisplayServer.get_name()=="headless":return
    await RenderingServer.frame_post_draw
    var img=game.get_viewport().get_texture().get_image()
    if not img.is_empty():img.save_png(root.path_join(name+".png"));shots.append(name);write_report()
func idle_path(limit: float=7):
    var until=Time.get_ticks_msec()+int(limit*1000)
    while Time.get_ticks_msec()<until and (not game.navigation.path.is_empty() or not game.navigation.pending.is_empty() or game.step_progress<1):await wait(.03)
func visible(at: Vector2) -> bool:
    return game.field_rect().grow(-24).has_point(at) and not game.touch_controls.targets.any(func(t):return t.rect.has_point(at))
func dismiss_modal():
    if game.menu=="":return
    for target in game.touch_controls.targets:
        if target.id=="close":await tap(target.rect.get_center());return

func approach(goal: Vector2i):
    await dismiss_modal()
    for attempt in range(18):
        var at=game.screen_point(goal.x,goal.y)-Vector2(0,22)
        if visible(at):return true
        var m=game.maps[game.player.map]
        var plan=game.Pathfinder.search_any(game.cell(),[goal+Vector2i.UP,goal+Vector2i.LEFT,goal+Vector2i.DOWN,goal+Vector2i.RIGHT],func(p,d):return game.free_cell(game.player.map,p,"",d),4096)
        if plan.status!="FOUND" or plan.path.is_empty():return false
        var target=game.cell()
        for cell in plan.path:
            if visible(game.screen_point(cell.x,cell.y)-Vector2(0,22)):target=cell
            else:break
        if target==game.cell():return false
        await tap(game.screen_point(target.x,target.y)-Vector2(0,22));await idle_path()
    return false
func exit_to(target: String):
    var candidates=game.maps[game.player.map].portals.filter(func(p):return p.target==target)
    if candidates.is_empty():return false
    candidates.sort_custom(func(a,b):return Vector2i(a.x,a.y).distance_to(game.cell())<Vector2i(b.x,b.y).distance_to(game.cell()))
    var portal=candidates[0]
    if not await approach(Vector2i(portal.x,portal.y)):return false
    for retry in range(4):
        if game.player.map==target:return true
        await tap(game.screen_point(portal.x,portal.y)-Vector2(0,22));await idle_path();await wait(.25)
    return game.player.map==target
func hunt(kind: String):
    await dismiss_modal()
    var list=game.entities.values().filter(func(e):return e.alive and e.map==game.player.map and e.spec.name==kind)
    list.sort_custom(func(a,b):return Vector2i(a.x,a.y).distance_to(game.cell())<Vector2i(b.x,b.y).distance_to(game.cell()))
    if list.is_empty():return false
    var blockers=game.navigation.occupied()
    var m=game.maps[game.player.map]
    list=list.filter(func(e):
        var goals=[Vector2i(e.x,e.y)+Vector2i.UP,Vector2i(e.x,e.y)+Vector2i.LEFT,Vector2i(e.x,e.y)+Vector2i.DOWN,Vector2i(e.x,e.y)+Vector2i.RIGHT]
        var path=game.Pathfinder.search_any(game.cell(),goals,func(p,d):return game.free_cell(game.player.map,p,"",d),4096)
        return path.status=="FOUND")
    if list.is_empty():return false
    var target=list[0]
    if not await approach(Vector2i(target.x,target.y)):return false
    await tap(game.screen_point(target.x,target.y)-Vector2(0,34))
    if game.selected_target!=target.id:
        await tap(game.screen_point(target.x,target.y)-Vector2(0,16))
    if game.selected_target!=target.id:return false
    var attack=Vector2.ZERO
    for t in game.touch_controls.targets:
        if t.id=="attack":attack=t.rect.get_center()
    await touch(attack,true,7)
    var until=Time.get_ticks_msec()+4500
    while target.alive and int(game.player.hp)>0 and Time.get_ticks_msec()<until:await wait(.08)
    await touch(attack,false,7);await wait(.4)
    if not target.alive:
        # The real pickup context action, after approaching a real drop.
        var drops=game.loot.filter(func(d):return d.map==game.player.map)
        for drop in drops:
            if await approach(Vector2i(drop.x,drop.y)):
                await tap(game.screen_point(drop.x,drop.y)-Vector2(0,12));await idle_path()
    return not target.alive
func run(g,mode: String,directory: String):
    game=g;root=directory;begin=Time.get_ticks_msec();DirAccess.make_dir_recursive_absolute(root)
    await wait(.35)
    if mode=="repair-skills":
        await skill_story();get_tree().quit(0 if results.all(func(row):return row.status=="PASS") else 1);return
    if mode=="repair-equipment":
        await equipment_story();get_tree().quit(0 if results.all(func(row):return row.status=="PASS") else 1);return
    if mode=="repair-restore":
        check(game.save_loaded,"saved_character_loaded_in_fresh_process",{"map":game.player.map,"level":game.player.level,"skills":game.player.skills,"inventory":game.player.inventory})
        await capture("restart");game.write_diagnostic("REPAIR_RESTART");get_tree().quit();return
    if game.menu=="creation":
        game.name_edit.release_focus();await tap(Vector2(480,401));await wait(.4)
    check(not game.player.is_empty() and game.player.level==1,"fresh_level_1_created_by_pointer")
    if game.player.is_empty():get_tree().quit(1);return
    check(game.player.skills.is_empty() and game.player.hotbar==["","",""],"no_unearned_starter_skills")
    check(game.player.equipped!="","starter_wood_equipped")
    var initial=game.cell()
    for i in range(4):
        await panel("tab:"+str(i));await wait(.12);await capture(["items","skills","equipment","stats"][i])
        check(game.right_panel.tab==i and game.cell()==initial and game.menu=="","persistent_tab_"+str(i))
    await panel("tab:0")
    check(game.right_panel.missing_icons.is_empty(),"owned_item_icon_drawn",game.right_panel.missing_icons)
    var regex=RegEx.new();regex.compile("[A-Za-z?]");var missing=[]
    for m in game.maps.values():
        if regex.search(game.map_title(m.id))!=null:missing.append(m.id)
        for p in m.portals:
            if regex.search(p.label)!=null:missing.append(p.get("id",m.id))
    check(missing.is_empty(),"all_map_and_portal_display_names_korean",{"missing":missing,"maps":game.maps.size()})
    await panel("map");await wait(.3);await capture("korean-map");await dismiss_modal()
    await capture("korean-start-exit")
    var arrived=await exit_to("field");check(arrived,"pointer_only_normal_town_exit_to_hunting_field",{"map":game.player.map,"position":game.cell()})
    if not arrived:get_tree().quit(1);return
    await capture("hunting-entry")
    var rabbit=false;var squirrel=false;var xp=int(game.player.xp2);var before=game.player.inventory.duplicate()
    for i in range(140):
        if int(game.player.hp)<=0:break
        var kind="토끼" if i%2==0 else "다람쥐"
        var done=await hunt(kind)
        if not done:await wait(1.0)
        if int(game.player.hp)<int(game.player.hp_max)/2:
            await panel("tab:0")
            for j in range(game.right_panel.row_ids.size()):
                var id=str(game.right_panel.row_ids[j])
                if int(game.rules.value_or(game.rules.item(id),"heal_amount",0))>0:
                    game.right_panel.scroll=maxi(0,j-1);game.right_panel.layout();await panel("row:"+str(j));await panel("secondary");break
        if kind=="토끼":rabbit=rabbit or done
        else:squirrel=squirrel or done
        print("REPAIR_HUNT "+JSON.stringify({"attempt":i,"done":done,"hp":game.player.hp,"xp":game.player.xp2/2.0,"kills":game.player.kills,"level":game.player.level}));write_report()
        if i%10==0:await capture("hunt-progress-"+str(i))
        if i==1:await capture("rabbit-squirrel-combat")
        if rabbit and squirrel and game.player.level>1 and game.player.inventory!=before:break
    check(rabbit,"normal_rabbit_defeated");check(squirrel,"normal_squirrel_defeated")
    check(game.player.xp2>xp,"real_experience_increased",{"before":xp,"after":game.player.xp2})
    check(game.player.level>1,"natural_level_increased",{"level":game.player.level,"kills":game.player.kills})
    check(game.player.inventory!=before,"real_drop_acquired",{"before":before,"after":game.player.inventory})
    await capture("level-and-loot")
    var returned=await exit_to("village");check(returned,"pointer_only_normal_exit_back_to_town",{"map":game.player.map,"position":game.cell()})
    # Claim earned, existing hunt quests through the actual NPC, then retain a
    # normal eligible character for the separate learned-skill scenario.
    if returned and int(game.player.kills)>=25:
        var guide=game.maps[game.player.map].npcs.filter(func(n):return n.role=="quest")
        if not guide.is_empty():
            var n=guide[0]
            for claim in range(2):
                if await approach(Vector2i(n.x,n.y)):
                    await tap(game.screen_point(n.x,n.y)-Vector2(0,62));await idle_path();await wait(.3)
    await panel("tab:0");await panel("save");await wait(.7)
    check(FileAccess.file_exists(game.save_path),"pointer_save_written",{"sha256":FileAccess.get_sha256(game.save_path)})
    await capture("returned-and-saved");game.write_diagnostic("REPAIR_STORY");write_report();get_tree().quit(0 if results.all(func(r):return r.status=="PASS") else 1)

func equipment_story():
    check(game.save_loaded,"existing_normal_progress_loaded")
    var p=game.player
    var before=game.cell();var inventory=p.inventory.duplicate()
    await panel("tab:0")
    var rect=game.right_panel.bounds()
    await touch(rect.position+Vector2(100,180),true,3)
    var drag=InputEventScreenDrag.new();drag.index=3;drag.position=game.get_viewport().get_screen_transform()*(rect.position+Vector2(100,320));Input.parse_input_event(drag)
    await touch(rect.position+Vector2(100,320),false,3);await wait(.4)
    check(game.cell()==before and p.inventory==inventory,"sidebar_drag_does_not_move_attack_or_use")
    # These are genuine purchases using earned gold and the store's own prices.
    var sword=game.rules.find_content("item","목검").get("id","")
    var price=int(game.rules.value_or(game.rules.item(sword),"vendor_buy_price",-1))
    var purchased=price>=0 and game.rules.trade(p,sword,1,price,true)
    check(purchased,"normal_gold_purchase_of_comparison_weapon",{"price":price,"gold":p.gold})
    if purchased:
        await choose_item(sword)
        var old=p.equipped;await panel("primary")
        check(p.equipped==sword and p.equipped!=old,"weapon_replaced_through_actual_sidebar")
        await capture("weapon-replaced")
        var stats=game.rules.combat_stats(p)
        check(stats.minimum==int(game.rules.item(sword).damage_min) and stats.maximum==int(game.rules.item(sword).damage_max),"display_attack_uses_same_combat_stat_path",stats)
    var worn=[]
    for slot in ["body","head"]:
        for record in game.rules.contents:
            if record.category!="item":continue
            var item=record.values
            if item.get("slot","")!=slot or int(game.rules.value_or(item,"level_required",0))>int(p.level) or int(game.rules.value_or(item,"strength_required",0))>int(p.strength):continue
            var jobs=item.get("allowed_jobs",[])
            if not jobs.is_empty() and p.job not in jobs:continue
            var cost=int(game.rules.value_or(item,"vendor_buy_price",-1))
            if cost<0 or cost>int(p.gold):continue
            if not game.rules.trade(p,record.id,1,cost,true):continue
            await choose_item(record.id);await panel("primary")
            var gear=p.equipment_instances.get(p.equipment_slots.get(slot,""),{})
            check(gear.get("definition_id","")==record.id,"supported_"+slot+"_equipped_from_real_purchase",{"item":record.id,"price":cost})
            worn.append(record.id);break
    await panel("tab:2");await capture("equipment-after-purchases")
    var current=p.equipped
    await panel("row:0");await panel("primary")
    check(p.equipped=="" and not p.equipment_slots.has("weapon") and int(p.inventory.get(current,0))>0,"unequip_updates_slot_inventory_and_field_state")
    await capture("weapon-removed")
    await choose_item(game.rules.find_content("item","목도").get("id",""));await panel("primary")
    check(game.rules.display_name(p.equipped)=="목도","original_weapon_reequipped")
    await panel("tab:2");await capture("equipment-restored")
    await panel("tab:3");await capture("stats-after-equipment")
    await panel("save");await wait(.5);write_report()

func choose_item(id: String):
    await panel("tab:0");game.right_panel.layout()
    var index=game.right_panel.row_ids.find(id)
    if index<0:return
    game.right_panel.scroll=maxi(0,index-1);game.right_panel.layout()
    await panel("row:"+str(index))

func modal(id: String):
    for target in game.touch_controls.targets:
        if target.id==id:await tap(target.rect.get_center());return true
    return false

func talk_role(role: String):
    var rows=game.maps[game.player.map].npcs.filter(func(n):return n.role==role)
    if rows.is_empty():return false
    var n=rows[0]
    if not await approach(Vector2i(n.x,n.y)):return false
    await tap(game.screen_point(n.x,n.y)-Vector2(0,62));await idle_path();await wait(.3);return true

func skill_story():
    check(game.save_loaded,"naturally_played_character_loaded_for_skill_trial",{"level":game.player.level,"kills":game.player.kills})
    for claim in range(2):await talk_role("quest")
    check(int(game.player.level)>=5,"learn_level_reached_by_real_kills_and_earned_quests",{"level":game.player.level,"quests":game.player.quests,"xp":game.player.xp2/2.0})
    if int(game.player.level)<5:write_report();return
    await talk_role("travel")
    if game.menu=="travel" and "guild" in game.choices:
        var index=game.choices.find("guild");game.touch_controls.scroll_origin=maxi(0,index-1);await wait(.1)
        await modal("row:"+str(index));await modal("key:"+str(KEY_ENTER));await wait(.5)
    check(game.player.map=="guild","normal_guide_service_reaches_trainer")
    await talk_role("trainer")
    check(game.menu=="trainer","normal_trainer_dialogue_opened")
    var index=game.choices.find("비영사천문")
    if index<0:check(false,"compass_offered_by_trainer");return
    game.touch_controls.scroll_origin=maxi(0,index-1);await wait(.15)
    await modal("row:"+str(index))
    var before_mp=int(game.player.mp);var before_gold=int(game.player.gold);var before_inv=game.player.inventory.duplicate()
    await modal("key:"+str(KEY_ENTER));await wait(.2)
    check(game.rules.knows_skill(game.player,"비영사천문"),"compass_learned_through_trainer_with_actual_requirements",{"gold_before":before_gold,"gold_after":game.player.gold,"inventory_before":before_inv,"inventory_after":game.player.inventory})
    if not game.rules.knows_skill(game.player,"비영사천문"):return
    await dismiss_modal();await panel("tab:1")
    var id=game.rules.skill_id(game.player,"비영사천문");index=game.right_panel.row_ids.find(id)
    game.right_panel.scroll=maxi(0,index-1);await panel("row:"+str(index));await panel("secondary")
    check(id in game.player.hotbar,"learned_skill_assigned_to_real_hotbar")
    await capture("learned-compass")
    var used=[]
    for direction in range(4):
        await wait(1.1)
        await panel("tab:1");game.right_panel.selected=game.right_panel.row_ids.find(id)
        var start=Time.get_ticks_msec();var mp=int(game.player.mp)
        await panel("primary");await wait(.5)
        check(game.menu=="compass","compass_direction_selection_"+str(direction),{"mp_before":mp,"mp_after":game.player.mp})
        if game.menu!="compass":break
        await modal("row:"+str(direction));await modal("key:"+str(KEY_ENTER));await wait(.4)
        check(game.player.map=="village" and game.menu=="" and game.navigation.path.is_empty() and game.direct_direction==-1,"bounded_compass_move_"+str(direction),{"elapsed_ms":Time.get_ticks_msec()-start,"position":game.cell()})
        used.append(direction)
    await capture("compass-after-four-directions")
    check(used.size()==4,"compass_repeated_four_directions_without_stale_input")
    await panel("save");await wait(.5);write_report()
