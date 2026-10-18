extends RefCounted
## Presentation only. Every mutation delegates to the original C# session.
const DIRS := [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]
const STEP_SECONDS := 0.20
var core: RefCounted
var snapshot: Dictionary={}
var source: Dictionary
var definitions: Dictionary={}
var cells: Dictionary={}
var data: Dictionary={"maps":{}}
var state: Dictionary={"character":{"map_id":"4711","x":3,"y":5}}
var visual:=Vector2(3,5)
var step_from:=visual
var step_elapsed:=STEP_SECONDS
var attack_elapsed:=1.0
var moving:=false
var facing:=0
var display_name:=""
var ready:=false
var error:=""
var map_changed:=false
var prior_action:=-1
var prior_pose:=-1
var pickup_elapsed:=1.0
var actor_tweens: Dictionary={}
const ACTOR_STEP_SECONDS:=0.20

func _init(root: String) -> void:
	core=load("res://GameCore.cs").new()
	snapshot=JSON.parse_string(core.Initialize(root))
	if not snapshot.get("ok",false):error=str(snapshot.get("error","코어 시작 실패"));return
	source=JSON.parse_string(FileAccess.get_file_as_string("res://assets/assets.json"))
	var extra: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://p6/art/assets.json"))
	source.actor_regions.merge(extra.actor_regions);source.animations.merge(extra.animations)
	source.item_icons.merge(extra.get("item_icons",{}))
	for entry in source.maps:
		var mid:=str(int(entry.id));definitions[mid]=entry
		var bytes:=FileAccess.get_file_as_bytes("res://assets/"+str(entry.raw_path))
		var hash:=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(bytes)
		if hash.finish().hex_encode()!=entry.source_sha256:error="지도 원본 해시 불일치";return
		var ground:=PackedInt32Array();var objects:=PackedInt32Array()
		for i in range(bytes.size()/4):ground.append(bytes.decode_u16(i*4));objects.append(bytes.decode_u16(i*4+2))
		cells[mid]={"ground":ground,"objects":objects}
		var exits: Array=[]
		for w in entry.warps:exits.append({"x":w.SourceX,"y":w.SourceY})
		data.maps[mid]={"exits":exits}
	ready=true;accept(snapshot);halt()

func accept(next: Dictionary) -> void:
	var before:=map_id();snapshot=next
	if not next.get("playing",false):return
	state.character={"map_id":str(int(next.map)),"x":int(next.x),"y":int(next.y)}
	facing=int(next.facing)
	if before!=map_id():map_changed=true;halt()
	if before!=map_id():actor_tweens.clear();pickup_elapsed=1.0
	var live: Dictionary={}
	for actor in next.actors:
		var id:=str(int(actor.id));live[id]=true
		var target:=Vector2(actor.x,actor.y)
		if not actor_tweens.has(id):actor_tweens[id]={"from":target,"to":target,"elapsed":ACTOR_STEP_SECONDS}
		elif actor_tweens[id].to!=target:
			var current:=actor_visual(actor)
			actor_tweens[id]={"from":current if current.distance_to(target)<=1.1 else target,"to":target,"elapsed":0.0}
	for id in actor_tweens.keys():
		if not live.has(id):actor_tweens.erase(id)
	var width:=int(definitions[map_id()].width)
	for cell in next.cells:
		var at:=int(cell.y)*width+int(cell.x)
		cells[map_id()].objects[at]=int(cell.obj)
	if int(next.action_revision)!=prior_action:
		prior_action=int(next.action_revision);attack_elapsed=0
	for pose in next.get("poses",[]):
		if int(pose.sequence)<=prior_pose:continue
		prior_pose=int(pose.sequence)
		if int(pose.entity)==int(next.character.Id) and int(pose.type)==4:pickup_elapsed=0.0

func call_core(method: String,args: Array=[]) -> void:accept(JSON.parse_string(core.callv(method,args)))
func map_id() -> String:return str(state.character.map_id)
func position() -> Vector2i:return Vector2i(state.character.x,state.character.y)
func valid_position(mid: String,x: int,y: int) -> bool:return mid==map_id() and core.ValidCell(x,y)
func can_step(mid: String,x: int,y: int,nx: int,ny: int) -> bool:return mid==map_id() and core.CanStep(x,y,nx,ny)
func occupied_cells(_mid: String) -> Dictionary:
	# CanStep already asks the original World about live occupancy, including
	# its warp-before-occupancy rule. A second client veto would contradict it.
	return {}

func move(delta: Vector2i) -> bool:
	if moving or not ready:return false
	var direction:=DIRS.find(delta)
	if direction<0:return false
	var at:=position();var mid:=map_id();call_core("Move",[direction])
	if mid!=map_id():halt();return true
	if position()==at:return false
	step_from=Vector2(at);step_elapsed=0;moving=true
	return true

func advance(delta: float) -> void:
	attack_elapsed+=delta
	pickup_elapsed+=delta
	for tween in actor_tweens.values():tween.elapsed=minf(ACTOR_STEP_SECONDS,float(tween.elapsed)+delta)
	if moving:
		step_elapsed=minf(STEP_SECONDS,step_elapsed+delta)
		visual=step_from.lerp(Vector2(position()),step_elapsed/STEP_SECONDS)
		if step_elapsed>=STEP_SECONDS:moving=false
	else:visual=Vector2(position())

func halt() -> void:moving=false;step_elapsed=STEP_SECONDS;visual=Vector2(position());step_from=visual
func animation_key() -> String:
	if pickup_elapsed<0.40:return "pickup-"+str(facing)
	return ("attack-" if attack_elapsed<0.28 else ("walk-" if moving else "idle-"))+str(facing)
func animation_tick() -> int:
	if pickup_elapsed<0.40:return 0
	if attack_elapsed<0.28:return mini(1,int(attack_elapsed/0.14))
	return mini(2,int(step_elapsed/STEP_SECONDS*3)) if moving else 0

func actor_visual(actor: Dictionary) -> Vector2:
	var t: Dictionary=actor_tweens.get(str(int(actor.id)),{})
	if t.is_empty():return Vector2(actor.x,actor.y)
	return (t.from as Vector2).lerp(t.to,float(t.elapsed)/ACTOR_STEP_SECONDS)

func actor_tick(actor: Dictionary,count: int) -> int:
	var t: Dictionary=actor_tweens.get(str(int(actor.id)),{})
	if t.is_empty() or float(t.elapsed)>=ACTOR_STEP_SECONDS:return 0
	return mini(count-1,int(float(t.elapsed)/ACTOR_STEP_SECONDS*count))
