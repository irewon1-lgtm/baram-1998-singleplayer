extends RefCounted
## Presentation state and interpolation only; C# owns all game mutations.
const DIRS := [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]
const STEP_SECONDS := 0.20
var core: RefCounted
var snapshot: Dictionary={}
var source: Dictionary
var definitions: Dictionary={}
var cells: Dictionary={}
var data: Dictionary={"maps":{"4711":{"exits":[]}}}
var state: Dictionary={"character":{"map_id":"4711","x":3,"y":5}}
var visual:=Vector2(3,5)
var step_from:=visual
var step_elapsed:=STEP_SECONDS
var moving:=false
var facing:=0
var dirty:=false
var ready:=false
var error:=""

func _init(root: String) -> void:
	core=load("res://InteractiveCore.cs").new()
	snapshot=JSON.parse_string(core.Initialize(root))
	if not snapshot.get("ok",false):error=str(snapshot.get("error","코어 시작 실패"));return
	source=JSON.parse_string(FileAccess.get_file_as_string("res://assets/assets.json"))
	for entry in source.maps:
		var mid:=str(int(entry.id));definitions[mid]=entry
		var bytes:=FileAccess.get_file_as_bytes("res://assets/"+str(entry.raw_path))
		var hash:=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(bytes)
		if hash.finish().hex_encode()!=entry.source_sha256:error="지도 원본 해시 불일치";return
		var ground:=PackedInt32Array();var objects:=PackedInt32Array()
		for i in range(bytes.size()/4):ground.append(bytes.decode_u16(i*4));objects.append(bytes.decode_u16(i*4+2))
		cells[mid]={"ground":ground,"objects":objects}
	ready=true;_accept(snapshot);halt()

func _accept(next: Dictionary) -> void:
	snapshot=next
	state.character={"map_id":str(int(next.map)),"x":int(next.x),"y":int(next.y)}
	facing=int(next.facing)

func map_id() -> String:return str(state.character.map_id)
func position() -> Vector2i:return Vector2i(state.character.x,state.character.y)
func valid_position(_mid: String,x: int,y: int) -> bool:return core.ValidCell(x,y)
func can_step(_mid: String,x: int,y: int,nx: int,ny: int) -> bool:return core.CanStep(x,y,nx,ny)
func occupied_cells(_mid: String) -> Dictionary:
	return {Vector2i(int(snapshot.rabbit.x),int(snapshot.rabbit.y)):true} if snapshot.rabbit.alive else {}

func move(delta: Vector2i) -> bool:
	if moving or not ready:return false
	var direction:=DIRS.find(delta)
	if direction<0:return false
	var at:=position();_accept(JSON.parse_string(core.Move(direction)))
	if position()==at:return false
	step_from=Vector2(at);step_elapsed=0;moving=true;dirty=true
	return true

func advance(delta: float) -> void:
	if moving:
		step_elapsed=minf(STEP_SECONDS,step_elapsed+delta)
		visual=step_from.lerp(Vector2(position()),step_elapsed/STEP_SECONDS)
		if step_elapsed>=STEP_SECONDS:moving=false
	else:visual=Vector2(position())

func halt() -> void:moving=false;step_elapsed=STEP_SECONDS;visual=Vector2(position());step_from=visual
func animation_key() -> String:return ("walk-" if moving else "idle-")+str(facing)
func animation_tick() -> int:return mini(2,int(step_elapsed/STEP_SECONDS*3)) if moving else 0
func use_item(key: String) -> void:_accept(JSON.parse_string(core.UseItem(key)))
func save() -> void:_accept(JSON.parse_string(core.Save()));dirty=false
func item(key: String) -> Dictionary:
	for entry in snapshot.inventory:
		if entry.key==key:return entry
	return {"amount":0,"charges":0}
