extends SceneTree
## Byte equality of delivered containers. Native execution is a separate gate.
func sha256_bytes(bytes: PackedByteArray) -> String:
	var ctx:=HashingContext.new();ctx.start(HashingContext.HASH_SHA256);ctx.update(bytes);return ctx.finish().hex_encode()
func indexed(args: PackedStringArray) -> void:
	var manifest_path: String=args[args.find("--apk-manifest")+1]
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	var blob_info: Dictionary=manifest.get("comparison_blob",{})
	var blob_bytes:=FileAccess.get_file_as_bytes(str(blob_info.get("path","")))
	var bound: bool=manifest.get("status")=="PASS_MANIFEST_ONLY" and FileAccess.get_sha256(args[args.find("--apk")+1])==manifest.get("artifact",{}).get("sha256","") and blob_bytes.size()==int(blob_info.get("bytes",-1)) and sha256_bytes(blob_bytes)==blob_info.get("sha256","")
	var checks: Array=[];var failures:=0;var total:=0
	if bound:
		for path in manifest.get("files",{}):
			var name: String=str(path)
			if not name.begins_with("assets/"):continue
			var relative: String=name.trim_prefix("assets/")
			if not relative.begins_with("private_runtime/") and not relative.ends_with(".gdc"):continue
			if relative.ends_with("/"):continue
			var row: Dictionary=manifest.files[path]
			var android:=PackedByteArray()
			if row.has("comparison_blob_offset"):
				android=blob_bytes.slice(int(row.comparison_blob_offset),int(row.comparison_blob_offset)+int(row.bytes))
			var windows:=FileAccess.get_file_as_bytes("res://"+relative)
			var same: bool=not android.is_empty() and windows==android and sha256_bytes(android)==row.sha256
			checks.append({"path":relative,"status":"PASS" if same else "FAIL","bytes":android.size(),"sha256":sha256_bytes(android)})
			if not same:failures+=1
			total+=android.size()
			if checks.size()%5000==0:print("G2_PACK_PROGRESS ",checks.size()," failures=",failures)
	var result: Dictionary={"status":"PASS" if bound and failures==0 and checks.size()>8800 else "FAIL","scope":"Exact decompressed actual signed-APK private-runtime and compiled-script bytes versus actual Windows embedded PCK. APK, indexed stream and every member SHA-256 verified. Linux Godot resource comparison only; no native execution claim.","method":"INDEXED_ACTUAL_APK_BYTE_STREAM_DIRECT_EQUALITY","apk_sha256":manifest.get("artifact",{}).get("sha256",""),"apk_member_manifest_sha256":FileAccess.get_sha256(manifest_path),"comparison_blob_sha256":blob_info.get("sha256",""),"files":checks.size(),"bytes":total,"failures":failures,"checks":checks}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n");file.close()
	print("G2_PACK_INDEXED "+str(checks.size())+" files, "+str(failures)+" failures");quit(0 if result.status=="PASS" else 1)
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args();var zip:=ZIPReader.new()
	if args.has("--apk-manifest"):
		indexed(args);return
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
			checks.append({"path":relative,"status":"PASS" if same else "FAIL","bytes":android.size(),"sha256":sha256_bytes(android)})
			if not same:failures+=1
			total+=android.size()
			if checks.size()%5000==0:print("G2_PACK_PROGRESS ",checks.size()," failures=",failures)
	var result: Dictionary={"status":"PASS" if opened and failures==0 and checks.size()>8800 else "FAIL","scope":"All raw private-runtime resources and compiled scripts in actual APK versus final Windows embedded PCK, read by Linux Godot. No native Windows/Android execution claim.","files":checks.size(),"bytes":total,"failures":failures,"checks":checks}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE);file.store_string(JSON.stringify(result,"  ")+"\n");file.close()
	print("G2_PACK "+str(checks.size())+" files, "+str(failures)+" failures");quit(0 if result.status=="PASS" else 1)
