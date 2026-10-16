extends SceneTree
## Run via Linux --main-pack final Windows EXE. This is inclusion, not native execution.
func _initialize() -> void:
	var root:="res://private_runtime/"
	var manifest: Variant=JSON.parse_string(FileAccess.get_file_as_string(root+"runtime.json"))
	var failures: Array=[]
	var count:=0
	var args:=OS.get_cmdline_user_args()
	var expected: Dictionary={}
	if "--expected" in args: expected=JSON.parse_string(FileAccess.get_file_as_string(args[args.find("--expected")+1]))
	if typeof(manifest)!=TYPE_DICTIONARY or manifest.get("schema")!="baram.work.p3.runtime/1": failures.append("MISSING_P3_MANIFEST")
	else:
		for entry in manifest.get("files",[]):
			var path:=str(entry.path)
			if path.is_absolute_path() or ".." in path.split("/"):
				failures.append("UNSAFE_PATH:"+path);continue
			var spec: Dictionary=expected.get(path,{})
			if spec.get("kind")=="image":
				var texture=load(root+path) as Texture2D
				if texture==null: failures.append("MISSING_TEXTURE:"+path)
				else:
					var image: Image=texture.get_image()
					image.convert(Image.FORMAT_RGBA8)
					var bytes:=image.get_data()
					for at in range(0,bytes.size(),4):
						if bytes[at+3]==0: bytes[at]=0;bytes[at+1]=0;bytes[at+2]=0
					var hash:=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(bytes)
					if image.get_width()!=int(spec.width) or image.get_height()!=int(spec.height) or hash.finish().hex_encode()!=spec.rgba_sha256: failures.append("VISIBLE_PIXEL_MISMATCH:"+path)
			elif spec.get("kind")=="audio":
				var stream=load(root+path) as AudioStreamWAV
				if stream==null: failures.append("MISSING_WAV:"+path)
				else:
					var hash:=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(stream.data)
					var data_hash:=hash.finish().hex_encode()
					var valid: bool=stream.mix_rate==int(spec.rate) and roundi(stream.get_length()*stream.mix_rate)==int(spec.frames) and stream.stereo==(int(spec.channels)==2) and not stream.data.is_empty()
					# Godot4.6.3's default WAV importer stores QOA (format3), so
					# compressed bytes cannot be compared to original source PCM.
					# Preserve this distinction instead of calling lossy PCM exact.
					if stream.format==AudioStreamWAV.FORMAT_16_BITS: valid=valid and data_hash==spec.pcm_sha256
					elif stream.format==AudioStreamWAV.FORMAT_QOA: valid=valid and stream.data.slice(0,4).get_string_from_ascii()=="qoaf"
					else: valid=false
					if not valid: failures.append("AUDIO_RESOURCE_MISMATCH:"+path)
			elif FileAccess.get_sha256(root+path)!=entry.sha256: failures.append("MISSING_OR_HASH:"+path)
			count+=1
	var result:={"schema":"baram.gameplay.pack-inclusion/1","status":"PASS" if count>0 and failures.is_empty() else "FAIL","platform":OS.get_name(),"scope":"Linux imported-resource inclusion; never native Windows execution. PNG visible RGBA exact; source WAV PCM preserved in input, default imported QOA rate/channels/framecount validated, not PCM-byte equality.","files_checked":count,"failures":failures,"runtime_manifest_sha256":FileAccess.get_sha256(root+"runtime.json")}
	if "--report" in args:
		var f:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
		if f:f.store_string(JSON.stringify(result,"  ")+"\n")
	print(JSON.stringify(result))
	quit(0 if result.status=="PASS" else 1)
