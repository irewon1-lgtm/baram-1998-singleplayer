extends RefCounted
## Caller supplies actual directional collision/occupancy; search always ends.
const DIRECTIONS=[Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]

static func search(start: Vector2i, target: Vector2i, passable: Callable, maximum: int=256) -> Dictionary:
    var queue=[start];var parents={start:null};var cursor=0
    while cursor<queue.size() and cursor<maximum:
        var at=queue[cursor];cursor+=1
        if at==target:
            var path=[];var position=target
            while position!=start:path.push_front(position);position=parents[position]
            return {"status":"FOUND","path":path,"visited":cursor}
        for direction in range(4):
            var next=at+DIRECTIONS[direction]
            if not parents.has(next) and passable.call(next,direction):parents[next]=at;queue.append(next)
    return {"status":"BUDGET_EXCEEDED" if cursor>=maximum else "UNREACHABLE","path":[],"visited":cursor}

static func search_any(start: Vector2i, targets: Array, passable: Callable, maximum: int=4096) -> Dictionary:
    var queue=[start];var parents={start:null};var cursor=0
    while cursor<queue.size() and cursor<maximum:
        var at=queue[cursor];cursor+=1
        if at in targets:
            var path=[];var position=at
            while position!=start:path.push_front(position);position=parents[position]
            return {"status":"FOUND","path":path,"visited":cursor}
        for direction in range(4):
            var next=at+DIRECTIONS[direction]
            if not parents.has(next) and passable.call(next,direction):parents[next]=at;queue.append(next)
    return {"status":"BUDGET_EXCEEDED" if cursor>=maximum else "UNREACHABLE","path":[],"visited":cursor}
