extends SceneTree
func digest(bytes: PackedByteArray) -> String:
 var ctx:=HashingContext.new();ctx.start(HashingContext.HASH_SHA256);ctx.update(bytes);return ctx.finish().hex_encode()
func _initialize() -> void:
 var archive:=ZIPReader.new()
 var path:=OS.get_environment("BARAM_PARITY_APK")
 var opened:=archive.open(path)==OK
 var checks: Array=[]
 for relative in ["ui/gameplay.gdc","state/gameplay_state.gdc","render/original_view.gdc","input/touch_stick.gdc","input/grid_navigation.gdc","ui/classic_list.gdc","ui/parchment_panel.gdc","storage/gameplay_store.gdc","storage/save_store.gdc","private_runtime/runtime.json","private_runtime/gameplay_content.json"]:
  var windows:=FileAccess.get_file_as_bytes("res://"+relative)
  var android: PackedByteArray=archive.read_file("assets/"+relative) if opened else PackedByteArray()
  var equal: bool=not windows.is_empty() and windows==android
  checks.append({"path":relative,"status":"PASS" if equal else "FAIL","windows_bytes":windows.size(),"android_bytes":android.size(),"windows_sha256":digest(windows),"android_sha256":digest(android)})
 var result:={"status":"PASS" if opened and checks.all(func(c): return c.status=="PASS") else "FAIL","scope":"Byte equality of actual APK ZIP and final Windows embedded PCK compiled scripts + input manifests. Not Android runtime or native Windows execution.","checks":checks}
 var f:=FileAccess.open(OS.get_environment("BARAM_PARITY_OUTPUT"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n");print("PACK_PARITY "+JSON.stringify(result));quit(0 if result.status=="PASS" else 1)
