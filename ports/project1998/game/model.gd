extends RefCounted
## P2 original-map inspection/movement, not the C# gameplay core (P3).
const Store = preload("res://storage/save_store.gd")
const STEP_SECONDS := 0.20
const OWNER := "p1998:owner:local"
const CHARACTER := "p1998:character:tech"
const SAVE_PATH := "user://p2/tech-save.json"
const DIRS := [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]
const BITS := [1,4,2,8]
var source: Dictionary
var definitions: Dictionary = {}
var cells: Dictionary = {}
var data: Dictionary = {"maps":{}}
var catalog: Dictionary = {"profile":"project1998.p2.tech","maps":{},"items":{},"skills":{}}
var state: Dictionary = {"character":{"map_id":"4711","x":3,"y":5}}
var storage = Store.new()
var revision := 0
var facing := 2
var visual := Vector2(3,5)
var step_from := Vector2(3,5)
var step_elapsed := STEP_SECONDS
var attacking := 0.0
var moving := false
var dirty := false
var loaded := false
var save_status := "아직 저장하지 않음"
var blocked_moves := 0
var completed_moves := 0
var attacks := 0
var allow_write := true

func _init() -> void:
	var raw := FileAccess.get_file_as_bytes("res://assets/assets.json")
	source = JSON.parse_string(raw.get_string_from_utf8())
	assert(source.get("schema","")=="project1998.p2.assets.v1")
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256);hash.update(raw)
	catalog.manifest_sha256 = hash.finish().hex_encode()
	for entry in source.maps:
		var mid := str(int(entry.id))
		definitions[mid] = entry
		data.maps[mid] = {"exits":[]}
		var bytes := FileAccess.get_file_as_bytes("res://assets/"+str(entry.raw_path))
		var check := HashingContext.new()
		check.start(HashingContext.HASH_SHA256);check.update(bytes)
		assert(check.finish().hex_encode()==entry.source_sha256)
		assert(bytes.size()==int(entry.width)*int(entry.height)*4)
		var ground := PackedInt32Array()
		var objects := PackedInt32Array()
		var blocked: Array=[]
		for i in range(bytes.size()/4):
			var word := bytes.decode_u16(i*4)
			var obj := bytes.decode_u16(i*4+2)
			ground.append(word);objects.append(obj)
			if (word>>14)!=0 or (obj!=0 and int(source.objects[str(obj)].collision_flags_4x)==15):
				blocked.append([i%int(entry.width),i/int(entry.width)])
		cells[mid] = {"ground":ground,"objects":objects}
		catalog.maps["p1998:map:"+mid] = {"width":int(entry.width),"height":int(entry.height),"version":str(entry.source_sha256),"blocked":blocked}
	var saved: Dictionary = storage.read_state(ProjectSettings.globalize_path(SAVE_PATH),OWNER,catalog)
	if saved.status in ["OK","RECOVERED_BACKUP"]:
		var ch: Dictionary=saved.state.payload.character
		state.character={"map_id":str(ch.position.map_id).get_slice(":",2),"x":int(ch.position.x),"y":int(ch.position.y)}
		revision=int(saved.state.meta.revision);loaded=true;save_status="저장 위치 이어하기"
	elif saved.status!="MISSING":
		allow_write=false;save_status="저장 보호: "+str(saved.status)
	visual=Vector2(state.character.x,state.character.y);step_from=visual

func map_id() -> String:
	return str(state.character.map_id)

func position() -> Vector2i:
	return Vector2i(int(state.character.x),int(state.character.y))

func valid_position(mid: String,x: int,y: int) -> bool:
	var m: Dictionary=definitions[mid]
	if x<0 or y<0 or x>=int(m.width) or y>=int(m.height):return false
	var n:=y*int(m.width)+x
	var ground: PackedInt32Array=cells[mid].ground
	var objects: PackedInt32Array=cells[mid].objects
	if (ground[n]>>14)!=0:return false
	return objects[n]==0 or int(source.objects[str(objects[n])].collision_flags_4x)!=15

func can_step(mid: String,x: int,y: int,nx: int,ny: int) -> bool:
	var delta:=Vector2i(nx-x,ny-y)
	var direction:=DIRS.find(delta)
	if direction<0:return false
	var m: Dictionary=definitions[mid]
	if nx<0 or ny<0 or nx>=int(m.width) or ny>=int(m.height):return false
	var n:=ny*int(m.width)+nx
	var ground: PackedInt32Array=cells[mid].ground
	var objects: PackedInt32Array=cells[mid].objects
	if (ground[n]>>14)!=0:return false
	if objects[n]!=0 and (int(source.objects[str(objects[n])].collision_flags_4x)&int(BITS[direction]))!=0:return false
	return true

func occupied_cells(mid: String) -> Dictionary:
	# One real fixed spawn, SpnId 5: map 4711, (6,6), MobId 1. No synthetic placements.
	return {Vector2i(6,6):true} if mid=="4711" else {}

func move(delta: Vector2i) -> bool:
	if moving or delta==Vector2i.ZERO:return false
	var direction:=DIRS.find(delta)
	if direction<0:return false
	facing=direction
	var at:=position();var target:=at+delta
	if not can_step(map_id(),at.x,at.y,target.x,target.y) or occupied_cells(map_id()).has(target):
		blocked_moves+=1;return false
	step_from=Vector2(at);step_elapsed=0;moving=true;attacking=0
	state.character.x=target.x;state.character.y=target.y
	dirty=true;completed_moves+=1
	return true

func advance(delta: float) -> void:
	if moving:
		step_elapsed=minf(STEP_SECONDS,step_elapsed+delta)
		visual=step_from.lerp(Vector2(position()),step_elapsed/STEP_SECONDS)
		if step_elapsed>=STEP_SECONDS:moving=false
	else:visual=Vector2(position())
	attacking=maxf(0,attacking-delta)

func halt() -> void:
	moving=false;step_elapsed=STEP_SECONDS;visual=Vector2(position());step_from=visual;attacking=0

func attack() -> void:
	attacking=0.32;attacks+=1

func switch_map(mid: String) -> void:
	assert(definitions.has(mid))
	halt()
	var start: Array=definitions[mid].tech_start
	state.character={"map_id":mid,"x":int(start[0]),"y":int(start[1])}
	visual=Vector2(position());step_from=visual;dirty=true

func animation_key() -> String:
	if attacking>0:return "attack-"+str(facing)
	return ("walk-" if moving else "idle-")+str(facing)

func animation_tick() -> int:
	if attacking>0:return mini(1,int((0.32-attacking)/0.16))
	return mini(2,int(step_elapsed/STEP_SECONDS*3)) if moving else 0

func save() -> Dictionary:
	if not allow_write:return {"status":"EXISTING_SAVE_PROTECTED"}
	var mid:=map_id()
	var p:=position()
	var next:=revision+1
	var document: Dictionary={"meta":{"schema_id":Store.SCHEMA_ID,"schema_version":Store.SCHEMA_VERSION,
		"content_profile":catalog.profile,"content_manifest_sha256":catalog.manifest_sha256,"build_id":"project1998-p2-20261018",
		"owner_id":OWNER,"character_id":CHARACTER,"revision":next},
		"payload":{"character":{"id":CHARACTER,"name":"모험가","level":1,"hp":1,"hp_max":1,
		"position":{"map_id":"p1998:map:"+mid,"map_version":str(definitions[mid].source_sha256),"x":p.x,"y":p.y}},
		"inventory":[],"equipment":{},"skills":[],"loot":[]}}
	var result: Dictionary=storage.write_state(ProjectSettings.globalize_path(SAVE_PATH),document,OWNER,catalog)
	if result.status=="SAVED":revision=next;dirty=false;save_status="위치 저장 완료"
	else:save_status="저장 확인 필요: "+str(result.status)
	return result
