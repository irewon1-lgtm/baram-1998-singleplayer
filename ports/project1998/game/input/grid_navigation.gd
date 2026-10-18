extends RefCounted
## Bounded A* segments; the UI continues the same goal on subsequent frames.
const EXPANSIONS := 2048
var search_game: RefCounted
var destination:=Vector2i.ZERO
var reach:=0
var mid:=""
var start:=Vector2i.ZERO
var heap: Array=[]
var previous: Dictionary={}
var costs: Dictionary={}
var occupied: Dictionary={}
var exits: Dictionary={}
var result: Array[Vector2i]=[]
var finished:=false

func begin(game: RefCounted,target: Vector2i,target_reach: int=0) -> void:
	search_game=game;destination=target;reach=target_reach
	mid=str(game.state.character.map_id);start=Vector2i(game.state.character.x,game.state.character.y)
	occupied=game.occupied_cells(mid);previous={start:start};costs={start:0};heap=[[0.0,0,start]]
	for exit in game.data.maps[mid].get("exits",[]):exits[Vector2i(exit.x,exit.y)]=true
	if not game.valid_position(mid,target.x,target.y):finished=true

func advance(budget: int=96) -> bool:
	if finished:return true
	if str(search_game.state.character.map_id)!=mid:finished=true;return true
	var expanded:=0
	while not heap.is_empty() and expanded<budget:
		var entry: Array=_pop(heap);var cell: Vector2i=entry[2];var cost: int=int(entry[1])
		if cost!=int(costs.get(cell,-1)):continue
		expanded+=1
		if absi(cell.x-destination.x)+absi(cell.y-destination.y)<=reach:
			while cell!=start:result.push_front(cell);cell=previous[cell]
			finished=true;return true
		for delta in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
			var next: Vector2i=cell+delta
			if not search_game.can_step(mid,cell.x,cell.y,next.x,next.y) or occupied.has(next):continue
			if exits.has(next) and next!=destination:continue
			var score:=cost+1
			if score>=int(costs.get(next,2147483647)):continue
			costs[next]=score;previous[next]=cell
			_push(heap,[score+absi(next.x-destination.x)+absi(next.y-destination.y),score,next])
	if heap.is_empty():finished=true
	return finished
static func _push(heap: Array,entry: Array) -> void:
	heap.append(entry);var at:=heap.size()-1
	while at>0:
		var parent: int=(at-1)/2
		if float(heap[parent][0])<=float(entry[0]):break
		heap[at]=heap[parent];at=parent
	heap[at]=entry
static func _pop(heap: Array) -> Array:
	var result: Array=heap[0];var last: Array=heap.pop_back()
	if heap.is_empty():return result
	var at:=0
	while at*2+1<heap.size():
		var child:=at*2+1
		if child+1<heap.size() and float(heap[child+1][0])<float(heap[child][0]):child+=1
		if float(last[0])<=float(heap[child][0]):break
		heap[at]=heap[child];at=child
	heap[at]=last;return result
static func route(game: RefCounted,destination: Vector2i,reach: int=0) -> Array[Vector2i]:
	var path: Array[Vector2i]=[];var c: Dictionary=game.state.character
	var start:=Vector2i(c.x,c.y);var mid:=str(c.map_id)
	if not game.valid_position(mid,destination.x,destination.y):return path
	var occupied: Dictionary=game.occupied_cells(mid);var exits: Dictionary={}
	for exit in game.data.maps[mid].get("exits",[]):exits[Vector2i(exit.x,exit.y)]=true
	var queue: Array=[[0.0,0,start]];var previous: Dictionary={start:start};var costs: Dictionary={start:0}
	var best:=start;var best_distance:=absi(start.x-destination.x)+absi(start.y-destination.y)
	var at:=0;var found:=Vector2i(-1,-1)
	while not queue.is_empty() and at<EXPANSIONS:
		var entry: Array=_pop(queue);var cell: Vector2i=entry[2];var cost: int=int(entry[1])
		if cost!=int(costs.get(cell,-1)):continue
		at+=1
		var distance:=absi(cell.x-destination.x)+absi(cell.y-destination.y)
		if distance<best_distance:best=cell;best_distance=distance
		if distance<=reach:found=cell;break
		for delta in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
			var next: Vector2i=cell+delta
			if not game.can_step(mid,cell.x,cell.y,next.x,next.y) or occupied.has(next):continue
			if exits.has(next) and next!=destination:continue
			var score:=cost+1
			if score>=int(costs.get(next,2147483647)):continue
			costs[next]=score;previous[next]=cell
			_push(queue,[score+absi(next.x-destination.x)+absi(next.y-destination.y),score,next])
	if found==Vector2i(-1,-1):found=best
	if found==start:return path
	while found!=start:path.push_front(found);found=previous[found]
	return path
