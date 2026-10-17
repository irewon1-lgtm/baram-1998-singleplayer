extends SceneTree
## Differential scanner and full decoder fixtures. Does not modify app/input
## files. Source hashes identify the exact reference/candidate actually run.
const MAX_BYTES := 4*1024*1024
var checks: Array=[]
var failures:=0
func check(id: String, passed: bool, details: Variant="") -> void:
	checks.append({"id":id,"status":"PASS" if passed else "FAIL","details":details})
	if not passed:failures+=1;print("FAIL "+id+" "+str(details))
func reference_guard(text: String) -> Dictionary:
	if text.to_utf8_buffer().size()>MAX_BYTES:return {"status":"SAVE_SIZE_LIMIT"}
	var depth:=0
	var quoted:=false
	var escaped:=false
	for c in text:
		if escaped:escaped=false
		elif quoted and c=="\\":escaped=true
		elif c=='"':quoted=not quoted
		elif not quoted:
			if c in ["{","["]:
				depth+=1
				if depth>24:return {"status":"SAVE_DEPTH_LIMIT"}
			elif c in ["}","]"]:depth-=1
	return {"status":"OK","depth":depth,"quoted":quoted,"escaped":escaped}
func byte_guard(text: String) -> Dictionary:
	var utf8:=text.to_utf8_buffer()
	if utf8.size()>MAX_BYTES:return {"status":"SAVE_SIZE_LIMIT"}
	var depth:=0
	var quoted:=false
	var escaped:=false
	for c in utf8:
		if escaped:escaped=false
		elif quoted and c==92:escaped=true
		elif c==34:quoted=not quoted
		elif not quoted:
			if c==123 or c==91:
				depth+=1
				if depth>24:return {"status":"SAVE_DEPTH_LIMIT"}
			elif c==125 or c==93:depth-=1
	return {"status":"OK","depth":depth,"quoted":quoted,"escaped":escaped}
func cases() -> Array:
	var rows: Array=[]
	for value in [{},[],{"한글🙂":"따옴표\" 역슬래시\\ 중괄호{[}] 끝"},{"text":"{".repeat(100)+"[".repeat(100)}, {"nested":[{"x":[1,true,null,1.25]}]}]:
		rows.append({"id":"valid-json-"+str(rows.size()),"text":JSON.stringify(value)})
	for depth in [0,1,23,24,25,26]:rows.append({"id":"array-depth-"+str(depth),"text":"[".repeat(depth)+"0"+"]".repeat(depth)})
	for text in ["", "}", "]", "}{", "][]", "[}", "{[", '"unclosed', '"trailing'+"\\", '"한글🙂'+"\\"+'끝"', '{"text":"\\uD83D\\uDE42"}', "true false", "{}{}", '{"a":1,}']:
		rows.append({"id":"malformed-or-edge-"+str(rows.size()),"text":text})
	for slash_count in range(10):
		rows.append({"id":"backslash-parity-"+str(slash_count),"text":'"left'+"\\".repeat(slash_count)+'"'+"[{한글🙂}]"+'"tail"'})
	rows.append({"id":"exact-4MiB","text":" ".repeat(MAX_BYTES-2)+"{}"})
	rows.append({"id":"above-4MiB","text":" ".repeat(MAX_BYTES-1)+"{}"})
	rows.append({"id":"UTF8-size-not-character-count","text":"한".repeat(int(MAX_BYTES/3))+"{}"})
	# Deterministic bounded malformed/quoted mixes cover state transitions;
	# corpus generation never shares the game's RNG or changes saved progress.
	var alphabet: Array=['"',"\\","{","}","[","]","a"," ","한","🙂","0",":",","]
	var seed_value: int=18777
	for index in range(128):
		var text: String=""
		for position in range(index%97):
			seed_value=(seed_value*1103515245+12345)&0x7fffffff
			text+=alphabet[seed_value%alphabet.size()]
		rows.append({"id":"deterministic-state-mix-"+str(index),"text":text})
	return rows
func _initialize() -> void:
	var args:=OS.get_cmdline_user_args()
	for required in ["--reference-store","--candidate-store","--content","--primary","--backup","--report"]:
		if required not in args or args.find(required)+1>=args.size():push_error("Missing "+required);quit(2);return
	var reference_path: String=args[args.find("--reference-store")+1]
	var candidate_path: String=args[args.find("--candidate-store")+1]
	var content_path: String=args[args.find("--content")+1]
	var original: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(content_path))
	var reference=load(reference_path).new()
	var candidate=load(candidate_path).new()
	var reference_content: Dictionary=reference.prepare_content(original)
	var candidate_content: Dictionary=candidate.prepare_content(original)
	check("both_private_generations_prepared",not reference_content.is_empty() and not candidate_content.is_empty())
	var primary_path: String=args[args.find("--primary")+1]
	var backup_path: String=args[args.find("--backup")+1]
	var owner: String=JSON.parse_string(FileAccess.get_file_as_string(primary_path)).owner
	var corpus:=cases()
	for item in [{"id":"actual-earned-primary","path":primary_path},{"id":"actual-earned-backup","path":backup_path}]:
		corpus.append({"id":item.id,"text":FileAccess.get_file_as_string(item.path),"expected_decode":"OK"})
	var outcomes: Array=[]
	for row in corpus:
		var text: String=row.text
		var expected:=reference_guard(text)
		var observed:=byte_guard(text)
		check("guard_state_"+row.id,expected==observed,{"reference":expected,"candidate":observed})
		var before: Dictionary=reference._decode_uncached(text,owner,reference_content)
		var after: Dictionary=candidate._decode_uncached(text,owner,candidate_content)
		check("full_decode_result_"+row.id,reference._canonical(before)==candidate._canonical(after),{"reference_status":before.status,"candidate_status":after.status,"reference_reason":before.get("reason"),"candidate_reason":after.get("reason")})
		if row.has("expected_decode"):check("actual_save_semantics_"+row.id,after.status==row.expected_decode)
		outcomes.append({"id":row.id,"utf8_bytes":text.to_utf8_buffer().size(),"characters":text.length(),"text_sha256":text.sha256_text(),"guard":observed,"decode_status":after.status,"decode_reason":after.get("reason")})
	var report: Dictionary={"schema":"baram.b5.store-depth-equivalence/1","status":"PASS" if failures==0 else "FAIL","checks":checks,"failures":failures,"corpus":outcomes,"source_reference_sha256":FileAccess.get_sha256(reference_path),"source_candidate_sha256":FileAccess.get_sha256(candidate_path),"test_source_sha256":FileAccess.get_sha256(get_script().resource_path),"source_game_state_sha256":FileAccess.get_sha256("res://state/gameplay_state.gd"),"content_sha256":FileAccess.get_sha256(content_path),"primary_sha256":FileAccess.get_sha256(primary_path),"backup_sha256":FileAccess.get_sha256(backup_path),"engine":Engine.get_version_info(),"scope":"Exact original String-state depth guard versus UTF8 ASCII-byte guard and both complete production _decode_uncached results. Quoted braces, odd/even escapes, Korean/emoji, malformed JSON, 24/25 depth and 4MiB UTF8 boundaries retained. Negative/final depth and unfinished strings remain JSON-parser decisions. Actual earned files are read-only. This is not rendered/device or first-save performance proof."}
	var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
	if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
	print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size(),"cases":corpus.size()}))
	quit(0 if failures==0 else 1)
