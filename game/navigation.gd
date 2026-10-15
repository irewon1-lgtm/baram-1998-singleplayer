extends RefCounted
## A command owns one bounded path. No background requests or stale callbacks.
var game
var path=[]
var pending={}
var marker=Vector2i(-1,-1)
var marker_time=0.0
var marker_failed=false
var generation=0
var searches=0
var last_search_us=0

func _init(owner):game=owner

func cancel():
    generation+=1;path.clear();pending.clear();marker=Vector2i(-1,-1)

func occupied() -> Dictionary:
    var result={}
    for e in game.entities.values():
        if e.alive and e.map==game.player.map:result[Vector2i(e.x,e.y)]=true
    for n in game.maps[game.player.map].npcs:
        if n.get("blocking",true):result[Vector2i(n.x,n.y)]=true
    return result

func route(goal: Vector2i, action: Dictionary={}) -> bool:
    cancel()
    if game.player.is_empty() or game.menu!="" or game.continuity_blocked:return false
    var begin=Time.get_ticks_usec()
    var m=game.maps[game.player.map];var blockers=occupied()
    for portal in m.portals:
        var at=Vector2i(portal.x,portal.y)
        if portal.get("trigger","walk")=="walk" and not (action.get("kind","")=="portal" and at==goal):blockers[at]=true
    var candidates=[goal]
    if not action.is_empty():
        candidates=[]
        for d in game.DIRECTIONS:candidates.append(goal+d)
        if action.kind=="loot":candidates.append(goal)
        if action.kind=="portal" and action.get("trigger","")=="walk":candidates=[goal]
    var passable=func(p,d):
        return p.x>=0 and p.y>=0 and p.x<int(m.width) and p.y<int(m.height) and not m.blocked[p.y][p.x] and not blockers.has(p) and (not m.has("collision_masks") or (int(m.collision_masks[p.y][p.x])&[1,8,2,4][d])==0)
    var result=game.Pathfinder.search_any(game.cell(),candidates,passable,4096)
    searches+=1;last_search_us=Time.get_ticks_usec()-begin
    marker=goal;marker_failed=result.status!="FOUND";marker_time=0.8
    game.event("navigation_search",{"status":result.status,"visited":result.visited,"microseconds":last_search_us,"generation":generation,"map":game.player.map,"from":game.cell(),"goal":goal,"path_size":result.path.size()})
    if marker_failed:
        game.notice("그곳으로 갈 수 없습니다.");return false
    path=result.path;pending=action.duplicate();pending["map"]=game.player.map
    return true

func valid_target() -> bool:
    if pending.is_empty():return true
    if pending.map!=game.player.map:return false
    match pending.get("kind",""):
        "monster":
            var e=game.entities.get(pending.id,{})
            return not e.is_empty() and e.alive and e.map==game.player.map and Vector2i(e.x,e.y)==pending.position
        "npc":return game.maps[game.player.map].npcs.any(func(n):return n.id==pending.id and Vector2i(n.x,n.y)==pending.position)
        "portal":return game.maps[game.player.map].portals.any(func(p):return Vector2i(p.x,p.y)==pending.position and p.target==pending.target)
        "loot":return game.loot.any(func(n):return n.map==game.player.map and Vector2i(n.x,n.y)==pending.position and n.item==pending.item)
    return true

func tick(delta: float):
    if marker_failed:
        marker_time-=delta
        if marker_time<=0:marker=Vector2i(-1,-1)
    if game.player.is_empty():return
    if game.menu!="" or game.continuity_blocked:
        cancel();return
    if not valid_target():cancel();return
    if game.move_wait>0 or game.step_progress<1 or game.attack_elapsed>=0 or game.cast_elapsed>=0:return
    if not path.is_empty():
        var next:Vector2i=path[0];var direction=game.DIRECTIONS.find(next-game.cell())
        if direction<0 or not game.free_cell(game.player.map,next,"",direction):
            cancel();game.notice("길이 막혔습니다. 목적지를 다시 눌러 주세요.");return
        var old=game.cell();game.move_player(direction)
        if game.cell()!=old and not path.is_empty():path.pop_front()
        return
    if marker_failed:return
    marker=Vector2i(-1,-1)
    if pending.is_empty():return
    var action=pending.duplicate();pending.clear()
    if action.get("kind","")=="":return
    var offset:Vector2i=action.position-game.cell()
    if offset.length()>1.1:return
    if offset!=Vector2i.ZERO:game.player.direction=game.Facing.toward(offset)
    match action.kind:
        "portal":
            for portal in game.maps[game.player.map].portals:
                if Vector2i(portal.x,portal.y)==action.position and portal.target==action.target:game.use_portal(portal);break
        "npc":game.interact(action.id)
        "loot":game.pickup()
        "monster":
            game.selected_target=action.id;game.begin_attack()

func tap(at: Vector2):
    if game.menu!="" or game.continuity_blocked or game.player.is_empty():return
    if not game.field_rect().has_point(at):return
    # Explicit exit marker has tile priority. NPC sprites retain their own hit area.
    for portal in game.maps[game.player.map].portals:
        if Rect2(game.screen_point(portal.x,portal.y)-Vector2(22,44),Vector2(44,44)).has_point(at):
            game.selected_target="";route(Vector2i(portal.x,portal.y),{"kind":"portal","position":Vector2i(portal.x,portal.y),"target":portal.target,"trigger":portal.get("trigger","walk")});return
    # A sprite is above its foot tile; hit test rendered geometry first.
    for n in game.maps[game.player.map].npcs:
        if Rect2(game.screen_point(n.x,n.y)-Vector2(23,82),Vector2(46,82)).has_point(at):
            game.selected_target="";route(Vector2i(n.x,n.y),{"kind":"npc","id":n.id,"position":Vector2i(n.x,n.y)});return
    for e in game.entities.values():
        if e.alive and e.map==game.player.map and Rect2(game.screen_point(e.x,e.y)-Vector2(24,75),Vector2(48,75)).has_point(at):
            cancel();game.selected_target=e.id;game.notice(e.spec.name+" 선택");return
    for drop in game.loot:
        if drop.map==game.player.map and Rect2(game.screen_point(drop.x,drop.y)-Vector2(22,35),Vector2(44,44)).has_point(at):
            game.selected_target="";route(Vector2i(drop.x,drop.y),{"kind":"loot","item":drop.item,"position":Vector2i(drop.x,drop.y)});return
    var own=game.screen_point(game.visual_position().x,game.visual_position().y)
    if Rect2(own-Vector2(21,76),Vector2(42,76)).has_point(at):cancel();return
    game.selected_target=""
    route(Vector2i(((at-game.field_rect().position)/game.STEP+game.camera()).floor()))

func attack_selected():
    if game.attack_elapsed>=0 or game.cast_elapsed>=0:return
    var target=game.entities.get(game.selected_target,{})
    if target.is_empty() or not target.alive or target.map!=game.player.map:
        game.selected_target="";game.begin_attack();return
    var offset=Vector2i(target.x,target.y)-game.cell()
    if absi(offset.x)+absi(offset.y)==1:
        cancel();game.player.direction=game.Facing.toward(offset);game.begin_attack()
    elif game.direct_direction<0 and pending.get("id","")!=target.id:
        route(Vector2i(target.x,target.y),{"kind":"monster","id":target.id,"position":Vector2i(target.x,target.y)})
