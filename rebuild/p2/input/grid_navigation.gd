extends RefCounted
## Bounded cardinal path. Intermediate exits are excluded; engine rechecks every step.
static func route(game: RefCounted, destination: Vector2i, reach: int = 0) -> Array[Vector2i]:
	var path: Array[Vector2i]=[]
	var c: Dictionary=game.state.character
	var start:=Vector2i(c.x,c.y)
	var queue: Array[Vector2i]=[start]
	var previous: Dictionary={start:start}
	var exits: Dictionary={}
	for exit in game.data.maps[c.map_id].get("exits",[]): exits[Vector2i(exit.x,exit.y)]=true
	var at:=0;var found:=Vector2i(-1,-1)
	while at<queue.size() and at<8192:
		var cell:=queue[at];at+=1
		if absi(cell.x-destination.x)+absi(cell.y-destination.y)<=reach: found=cell;break
		for delta in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
			var next: Vector2i=cell+delta
			if previous.has(next) or not game.valid_position(str(c.map_id),next.x,next.y) or game._occupied(str(c.map_id),next.x,next.y): continue
			if exits.has(next) and next!=destination: continue
			previous[next]=cell;queue.append(next)
	if found==Vector2i(-1,-1): return path
	while found!=start: path.push_front(found);found=previous[found]
	return path
