extends SceneTree
## Regression boundaries for the pre-parse save-depth guard. Uses the prior
## byte scanner as the oracle and malformed inputs remain parser failures.
const Store=preload("res://storage/gameplay_store.gd")
var checks: Array=[]
var failures:=0
func check(id: String,passed: bool,detail: Variant="") -> void:
 checks.append({"id":id,"status":"PASS" if passed else "FAIL","detail":detail})
 if not passed:failures+=1
func prior_guard(text: String) -> bool:
 var depth:=0
 var quoted:=false
 var escaped:=false
 for c in text.to_utf8_buffer():
  if escaped:escaped=false
  elif quoted and c==92:escaped=true
  elif c==34:quoted=not quoted
  elif not quoted:
   if c==123 or c==91:
    depth+=1
    if depth>24:return false
   elif c==125 or c==93:depth-=1
 return true
func _initialize() -> void:
 var store=Store.new()
 for depth in range(29):
  for text in ["문자열{}[]",'"\\[{}]"',"\\\\\\\"{}[[]]", "가".repeat(8000)+"[".repeat(80),"[".repeat(5000),"]".repeat(5000)]:
   var value: Variant=text
   for level in range(depth):value={"nested":value} if level%2==0 else [value]
   var encoded:=JSON.stringify(value)
   check("valid_nested_"+str(depth)+"_"+str(checks.size()),store._json_depth_allowed(encoded)==prior_guard(encoded),{"depth":depth,"bytes":encoded.to_utf8_buffer().size()})
   if depth<=24:check("depth_boundary_allows_"+str(checks.size()),store._json_depth_allowed(encoded))
   else:check("depth_boundary_refuses_"+str(checks.size()),not store._json_depth_allowed(encoded))
 for malformed in ['{"bad":"\\q [ ["}', '{"bad":"\\\n"}', '{"bad":"unterminated'+"[".repeat(26), '{"bad":"quote\\"'+"[".repeat(26)]:
  var parser:=JSON.new()
  check("malformed_never_becomes_accepted_json_"+str(checks.size()),parser.parse(malformed)!=OK)
  var decoded: Dictionary=store._decode_uncached(malformed,"local:depth",{})
  check("malformed_save_is_refused_"+str(checks.size()),decoded.status in ["CORRUPT","SAVE_DEPTH_LIMIT"],decoded.status)
 var max_depth_attack:="[".repeat(Store.MAX_BYTES)
 check("maximum_byte_limit_opening_brackets_refused",not store._json_depth_allowed(max_depth_attack))
 var args:=OS.get_cmdline_user_args()
 var report:={"schema":"baram.b5.save-depth-regression/1","status":"PASS" if failures==0 else "FAIL","failures":failures,"checks":checks,"store_sha256":FileAccess.get_sha256("res://storage/gameplay_store.gd"),"scope":"Headless depth-limit/UTF-8/quoted delimiter/escape regressions; no device performance claim"}
 if "--report" in args:
  var file:=FileAccess.open(args[args.find("--report")+1],FileAccess.WRITE)
  if file:file.store_string(JSON.stringify(report,"  ")+"\n");file.close()
 print(JSON.stringify({"status":report.status,"failures":failures,"checks":checks.size()}));quit(0 if failures==0 else 1)
