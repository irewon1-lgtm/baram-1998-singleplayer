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
func approach(goal: Vector2i):
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
    var list=game.entities.values().filter(func(e):return e.alive and e.map==game.player.map and e.spec.name==kind)
    list.sort_custom(func(a,b):return Vector2i(a.x,a.y).distance_to(game.cell())<Vector2i(b.x,b.y).distance_to(game.cell()))
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
    var until=Time.get_ticks_msec()+12000
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
    await capture("korean-start-exit")
    var arrived=await exit_to("field");check(arrived,"pointer_only_normal_town_exit_to_hunting_field",{"map":game.player.map,"position":game.cell()})
    if not arrived:get_tree().quit(1);return
    await capture("hunting-entry")
    var rabbit=false;var squirrel=false;var xp=int(game.player.xp2);var before=game.player.inventory.duplicate()
    for i in range(12):
        if int(game.player.hp)<=0:break
        var kind="토끼" if i%2==0 else "다람쥐"
        var done=await hunt(kind)
        if kind=="토끼":rabbit=rabbit or done
        else:squirrel=squirrel or done
        if i==1:await capture("rabbit-squirrel-combat")
        if rabbit and squirrel and game.player.level>1 and game.player.inventory!=before:break
    check(rabbit,"normal_rabbit_defeated");check(squirrel,"normal_squirrel_defeated")
    check(game.player.xp2>xp,"real_experience_increased",{"before":xp,"after":game.player.xp2})
    check(game.player.level>1,"natural_level_increased",{"level":game.player.level,"kills":game.player.kills})
    check(game.player.inventory!=before,"real_drop_acquired",{"before":before,"after":game.player.inventory})
    await capture("level-and-loot")
    var returned=await exit_to("village");check(returned,"pointer_only_normal_exit_back_to_town",{"map":game.player.map,"position":game.cell()})
    await panel("tab:0");await panel("save");await wait(.7)
    check(FileAccess.file_exists(game.save_path),"pointer_save_written",{"sha256":FileAccess.get_sha256(game.save_path)})
    await capture("returned-and-saved");game.write_diagnostic("REPAIR_STORY");write_report();get_tree().quit(0 if results.all(func(r):return r.status=="PASS") else 1)
