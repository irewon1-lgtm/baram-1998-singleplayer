extends RefCounted
## Deterministic runtime placement repairs. Published Work/source data remains
## immutable; saves continue to identify the same scenes and monsters.
const DIRECTIONS=[Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]
const EMPTY_HUNTS={
    "kr.map.1bdd29d4c6a9":["도깨비"],
    "kr.map.265e87c6b6fe":["소왕","황소","흑우","흰소"],
    "kr.map.4c325291323a":["토끼왕","왕토끼","토끼"],
    "kr.map.785a69f25595":["토끼","다람쥐"],
    "kr.map.c259c06d60f5":["뱀"],
    "kr.map.dfbac64f3b70":["쥐"],
    "kr.map.e6dc988ce05e":["해골"]}

static func reachable(map: Dictionary) -> Dictionary:
    var entry=Vector2i(int(map.entry[0]),int(map.entry[1]))
    var blockers={}
    for npc in map.npcs:
        if npc.get("blocking",true):blockers[Vector2i(int(npc.x),int(npc.y))]=true
    var queue=[entry];var found={entry:true};var cursor=0
    while cursor<queue.size():
        var cell=queue[cursor];cursor+=1
        for direction in range(4):
            var next=cell+DIRECTIONS[direction]
            if next.x<0 or next.y<0 or next.x>=int(map.width) or next.y>=int(map.height):continue
            if found.has(next) or blockers.has(next) or map.blocked[next.y][next.x]:continue
            if map.has("collision_masks") and (int(map.collision_masks[next.y][next.x])&[1,8,2,4][direction])!=0:continue
            found[next]=true;queue.append(next)
    return found

static func nearest(map: Dictionary, cells: Dictionary, desired: Vector2i, occupied: Dictionary, interior: bool=true) -> Vector2i:
    var best=Vector2i(-1,-1);var distance=2147483647
    # Row-major iteration supplies a stable tie break on every platform.
    for y in range(int(map.height)):
        for x in range(int(map.width)):
            if interior and (x==0 or y==0 or x==int(map.width)-1 or y==int(map.height)-1):continue
            var cell=Vector2i(x,y)
            if not cells.has(cell) or occupied.has(cell):continue
            var score=absi(x-desired.x)+absi(y-desired.y)
            if score<distance:distance=score;best=cell
    return best

static func monster_pool(content, needles: Array) -> Array:
    var pool=[]
    for id in content.by_kind("monster"):
        var spec=content.definition(id);var name=str(spec.get("name","")).replace(" ","")
        if needles.any(func(needle):return str(needle) in name):pool.append(id)
    pool.sort()
    # Use already authored creature identities and stats. Prefer the lowest
    # defined level for a new hunt, with permanent ID as a stable tie break.
    pool.sort_custom(func(a,b):return int(content.definition(a).get("level",content.definition(a).get("values",{}).get("level",0)))<int(content.definition(b).get("level",content.definition(b).get("values",{}).get("level",0))))
    return pool

static func move_overlevel_starter_spawns(world: Dictionary, content, repairs: Array):
    for source in world.maps:
        var bounds=content.definition(source.get("definition_id",source.id)).get("recommended_level",[])
        if bounds.size()!=2 or int(bounds[1])>10:continue
        var remaining=[]
        for spawn in source.spawns:
            var spec=content.definition(spawn.kind);var level=int(spec.get("level",0))
            if level<=int(bounds[1]):remaining.append(spawn);continue
            var family=spec.get("family","");var candidates=[]
            for target in world.maps:
                if target.id==source.id:continue
                var levels=content.definition(target.get("definition_id",target.id)).get("recommended_level",[])
                if levels.size()!=2 or int(levels[0])<=10 or level<int(levels[0]) or level>int(levels[1]):continue
                if target.spawns.any(func(s):return content.definition(s.kind).get("family","")==family):candidates.append(target)
            candidates.sort_custom(func(a,b):return str(a.id)<str(b.id))
            if candidates.is_empty():
                remaining.append(spawn)
                repairs.append({"kind":"starter_overlevel_unresolved","map_id":source.id,"placement_id":spawn.id,"monster_id":spawn.kind,"source_mode":"BLOCKED_NO_APPROPRIATE_FAMILY_REGION"})
                continue
            var target=candidates[0];var occupied={}
            for npc in target.npcs:occupied[Vector2i(int(npc.x),int(npc.y))]=true
            for portal in target.portals:occupied[Vector2i(int(portal.x),int(portal.y))]=true
            for existing in target.spawns:occupied[Vector2i(int(existing.x),int(existing.y))]=true
            occupied[Vector2i(int(target.entry[0]),int(target.entry[1]))]=true
            var position=nearest(target,reachable(target),Vector2i(int(target.width)/2,int(target.height)/2),occupied)
            if position.x<0:
                remaining.append(spawn)
                repairs.append({"kind":"starter_overlevel_unresolved","map_id":source.id,"placement_id":spawn.id,"monster_id":spawn.kind,"source_mode":"BLOCKED_NO_REACHABLE_DESTINATION_CELL"})
                continue
            var old=[int(spawn.x),int(spawn.y)]
            spawn.x=position.x;spawn.y=position.y;target.spawns.append(spawn)
            repairs.append({"kind":"spawn_map_relocated","map_id":source.id,"original_map":source.id,"current_map":target.id,"placement_id":spawn.id,"monster_id":spawn.kind,"monster_level":level,"original":old,"current":[position.x,position.y],"source_mode":"INFERRED_RUNTIME_PLACEMENT","note":"Existing high-level creature moved to an already authored same-family region matching its level; identity, stats and instance ID preserved"})
        source.spawns=remaining

static func apply(world: Dictionary, content) -> Dictionary:
    if world.get("runtime_repairs_version","")=="20261015-v1":return world
    var repairs=[]
    for map in world.maps:
        var cells=reachable(map)
        var occupied={}
        for npc in map.npcs:occupied[Vector2i(int(npc.x),int(npc.y))]=true
        for portal in map.portals:occupied[Vector2i(int(portal.x),int(portal.y))]=true
        for spawn in map.spawns:occupied[Vector2i(int(spawn.x),int(spawn.y))]=true
        occupied[Vector2i(int(map.entry[0]),int(map.entry[1]))]=true
        for portal in map.portals:
            var old=Vector2i(int(portal.x),int(portal.y));var accessible=cells.has(old)
            if not accessible and portal.get("trigger","walk")=="interact":
                accessible=DIRECTIONS.any(func(d):return cells.has(old+d))
            if accessible:continue
            var replacement=nearest(map,cells,old,occupied)
            if replacement.x<0:continue
            occupied.erase(old);occupied[replacement]=true
            portal.x=replacement.x;portal.y=replacement.y
            repairs.append({"kind":"portal_relocated","map_id":map.id,"placement_id":portal.get("id",""),"original":[old.x,old.y],"current":[replacement.x,replacement.y],"target":portal.target,"source_mode":"DERIVED_RUNTIME_REPAIR"})
        for spawn in map.spawns:
            var old=Vector2i(int(spawn.x),int(spawn.y))
            if cells.has(old):continue
            var replacement=nearest(map,cells,old,occupied)
            if replacement.x<0:continue
            occupied.erase(old);occupied[replacement]=true
            spawn.x=replacement.x;spawn.y=replacement.y
            repairs.append({"kind":"spawn_relocated","map_id":map.id,"placement_id":spawn.id,"monster_id":spawn.kind,"original":[old.x,old.y],"current":[replacement.x,replacement.y],"source_mode":"DERIVED_RUNTIME_REPAIR"})
        if not map.spawns.is_empty() or not EMPTY_HUNTS.has(map.id):continue
        var pool=monster_pool(content,EMPTY_HUNTS[map.id])
        if pool.is_empty():
            repairs.append({"kind":"empty_hunt_unresolved","map_id":map.id,"source_mode":"BLOCKED_NO_EXISTING_MONSTER"});continue
        var origin=Vector2i(int(map.entry[0]),int(map.entry[1]))
        for offset in [Vector2i(3,0),Vector2i(0,3),Vector2i(-3,0),Vector2i(0,-3)]:
            var replacement=nearest(map,cells,origin+offset,occupied)
            if replacement.x<0:continue
            var monster=pool[map.spawns.size()%mini(2,pool.size())]
            var id="codex.recovery."+str(map.id)+"/spawn/"+str(map.spawns.size())
            var spawn={"id":id,"kind":monster,"x":replacement.x,"y":replacement.y,"source_mode":"INFERRED_RUNTIME_PLACEMENT"}
            map.spawns.append(spawn);occupied[replacement]=true
            repairs.append({"kind":"empty_hunt_populated","map_id":map.id,"placement_id":id,"monster_id":monster,"current":[replacement.x,replacement.y],"source_mode":"INFERRED_RUNTIME_PLACEMENT","note":"Existing creature identity and stats reused; placement is authored, not a historical coordinate claim"})
    move_overlevel_starter_spawns(world,content,repairs)
    world.runtime_repairs=repairs
    world.runtime_repairs_version="20261015-v1"
    return world
