extends SceneTree
const Model=preload("res://model.gd")
var checks: Array=[]
var output: String

func _initialize() -> void:
	call_deferred("run")

func check(name: String,ok: bool,detail: Variant=null) -> void:
	checks.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})
	if not ok:push_error(name)

func run() -> void:
	var args:=OS.get_cmdline_user_args();output=args[0]
	var fixtures: Array=JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var m=Model.new()
	check("Fresh model uses source CharacterFactory (4711,3,5)",m.position()==Vector2i(3,5) and m.map_id()=="4711")
	var mismatch: Array=[]
	for f in fixtures:
		var from: Vector2i=Vector2i(int(f.x),int(f.y))-Model.DIRS[int(f.direction)]
		var actual: bool=m.can_step(str(int(f.map_id)),from.x,from.y,int(f.x),int(f.y))
		if actual!=bool(f.allowed):mismatch.append(f)
	check("Real source ground/directional object collision parity",mismatch.is_empty(),{"vectors":fixtures.size(),"mismatches":mismatch})
	check("Exact fixed rabbit spawn is occupied",m.occupied_cells("4711").has(Vector2i(6,6)))
	check("First Korean save succeeds",m.save().status=="SAVED")
	check("Source cell move succeeds",m.move(Vector2i.RIGHT));m.advance(0.3)
	check("Second position save succeeds",m.save().status=="SAVED")
	var path:=ProjectSettings.globalize_path(Model.SAVE_PATH)
	var before:=FileAccess.get_file_as_bytes(path)
	var document: Dictionary=m.storage.read_one(path,Model.OWNER,m.catalog).state.duplicate(true)
	document.meta.revision+=1;document.payload.character.position.x=5
	var failed: Dictionary=m.storage.write_state(path,document,Model.OWNER,m.catalog,"before_primary_replace")
	check("Interrupted replace leaves primary byte-identical",failed.status=="INJECTED_FAILURE" and FileAccess.get_file_as_bytes(path)==before)
	var reloaded=Model.new()
	check("Pending interrupted write is not promoted on reload",reloaded.position()==Vector2i(4,5))
	var file:=FileAccess.open(path,FileAccess.WRITE);file.store_string("damaged fixture");file.close()
	var recovered=Model.new()
	# before_primary_replace already archived the previous PRIMARY (4,5).
	# Expect that last valid snapshot, rather than the older initial (3,5).
	check("Corrupt primary recovers last valid backup",recovered.loaded and recovered.position()==Vector2i(4,5) and recovered.allow_write)
	check("Recovered model repairs through protected store",recovered.save().status=="SAVED")
	check("Broken original bytes are archived",FileAccess.get_file_as_string(path+".corrupt-"+"damaged fixture".sha256_text())=="damaged fixture")
	var future: Dictionary=recovered.storage.read_one(path,Model.OWNER,recovered.catalog).state.duplicate(true)
	future.meta.schema_version=99
	file=FileAccess.open(path,FileAccess.WRITE);file.store_string(recovered.storage.encode(future));file.close()
	var future_bytes:=FileAccess.get_file_as_bytes(path)
	var guarded=Model.new()
	check("Future schema blocks writes without falling back or resetting",not guarded.allow_write and guarded.save().status=="EXISTING_SAVE_PROTECTED" and FileAccess.get_file_as_bytes(path)==future_bytes)
	var passed:=true
	for c in checks:if c.status!="PASS":passed=false
	var result: Dictionary={"status":"PASS" if passed else "FAIL","checks":checks,"scope":"Fresh isolated synthetic save fixtures + actual source collision vectors. Not Galaxy or full C# gameplay parity."}
	file=FileAccess.open(output,FileAccess.WRITE);file.store_string(JSON.stringify(result,"\t"));file.close()
	print(JSON.stringify(result));quit(0 if passed else 1)
