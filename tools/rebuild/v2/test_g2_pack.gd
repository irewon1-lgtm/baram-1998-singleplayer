extends SceneTree
## Byte equality of delivered containers. Native execution is a separate gate.
func hash(bytes: PackedByteArray) -> String:
	var ctx:=HashingContext.new();ctx.start(HashingContext.HASH_SHA256);ctx.update(bytes);return ctx.finish().hex_encode()
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args();var zip:=ZIPReader.new()
	var opened:=zip.open(args[args.find("--apk")+1])==OK
	var checks: Array=[];var failures:=0;var total:=0
	if opened:
		for path in zip.get_files():
			if not path.begins_with("assets/"):continue
			var relative:=path.trim_prefix("assets/")
			if not relative.begins_with("private_runtime/") and not relative.ends_with(".gdc"):continue
			if relative.ends_with("/"):continue
			var android:=zip.read_file(path);var windows:=FileAccess.get_file_as_bytes("res://"+relative)
			var same:=not android.is_empty() and windows==android
			checks.append({"path":relative,"status":"PASS" if same else "FAIL","bytes":android.size(),"sha256":hash(android)})
			if not same:failures+=1
			total+=android.size()
	var result: Dictionary={"status":"PASS" if opened and failures==0 and checks.size()>8800 else "FAIL","scope":"All raw private-runtime resources and compiled scripts in actual APK versus final Windows embedded PCK, read by Linux Godot. No native Windows/Android execution claim.","files":checks.size(),"bytes":total,"failures":failures,"checks":checks}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n");file.close()
	print("G2_PACK "+str(checks.size())+" files, "+str(failures)+" failures");quit(0 if result.status=="PASS" else 1)
