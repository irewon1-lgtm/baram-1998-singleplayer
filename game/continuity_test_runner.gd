extends SceneTree
const State=preload("res://continuity_state.gd")
const Store=preload("res://save_store.gd")
const Client=preload("res://continuity.gd")
const Touch=preload("res://touch_controls.gd")
var checks=[]
var folder=""
func check(condition: bool, title: String):
    checks.append({"name":title,"status":"PASS" if condition else "FAIL"})
    print(("PASS " if condition else "FAIL ")+title)
func _initialize():call_deferred("run")
func run():
    folder=OS.get_cache_dir().path_join("baram-journal-"+State.uuid())
    DirAccess.make_dir_recursive_absolute(folder)
    var a=State.new();a.root=folder.path_join("pc")
    var owner=State.uuid();var device=State.uuid()
    check(a.select_account(owner,"schema2:test-content",device),"select account")
    var original=folder.path_join("original.json");var store=Store.new();store.content_version="test-content"
    var value={"player":{"level":1,"hp":50,"hp_max":50,"mp":10,"mp_max":10,"gold":7,"inventory":{}},"world":{},"rng_state":"123"}
    check(store.write_state(original,value),"original schema2 saved")
    var original_sha=FileAccess.get_sha256(original)
    check(a.accept_open({"status":"OK","version":0,"document":null,"last_request":null},original),"PC copy migration")
    check(FileAccess.get_sha256(original)==original_sha and FileAccess.get_sha256(a.path+".original-pc")==original_sha,"original bytes preserved")
    check(a.meta.dirty and a.mark_dirty(),"dirty journal before local writes")
    var body=a.upload_request();check(not body.is_empty(),"upload request checksummed and journaled")
    var retry=a.upload_request();check(body.p_request==retry.p_request,"retry is idempotent")
    var resumed=State.new();resumed.root=a.root
    check(resumed.select_account(owner,a.compatibility,device) and resumed.meta.dirty,"force stop retains pending state")
    check(resumed.accept_open({"status":"OK","version":1,"document":body.p_document,"last_request":body.p_request},original),"lost upload response reconciled")
    check(not resumed.meta.dirty and resumed.meta.version==1,"recovered acknowledgement version")
    var b=State.new();b.root=folder.path_join("android")
    check(b.select_account(owner,a.compatibility,State.uuid()) and b.accept_open({"status":"OK","version":1,"document":body.p_document},""),"second device loads same character document")
    check(store.read_one(b.path).player.gold==7,"common save parser on second device")
    var state=store.read_one(b.path);state.player.gold=9
    check(b.mark_dirty() and store.write_state(b.path,state),"second device local progress")
    check(b.accept_upload({"status":"OK","version":2}) and not b.meta.leased,"ack releases local lease")
    check(resumed.mark_dirty(),"first device stale local candidate")
    var latest=FileAccess.get_file_as_string(b.path)
    check(not resumed.accept_open({"status":"OK","version":2,"document":latest},original) and resumed.error=="CONFLICT_PRESERVED","stale overwrite blocked, both snapshots preserved")
    var before=FileAccess.get_sha256(b.path)
    check(not b.accept_open({"status":"UPDATE_REQUIRED"},original) and before==FileAccess.get_sha256(b.path),"version mismatch leaves file untouched")
    check(not b.accept_open({"status":"BUSY"},original) and before==FileAccess.get_sha256(b.path),"other device blocks import")
    check(not b.mark_dirty(),"unleased device cannot write account save")
    var evil=State.new();evil.root=folder.path_join("invalid")
    check(evil.select_account(owner,a.compatibility,State.uuid()) and not evil.accept_open({"status":"OK","version":5,"document":"{\"schema\":3}"},""),"future remote refused")
    var all_pass=checks.all(func(c):return c.status=="PASS")
    print("BARAM_JOURNAL_RESULT "+JSON.stringify({"status":"PASS" if all_pass else "FAIL","checks":checks,"scope":"LOCAL_JOURNAL_NOT_DEPLOYED_CLOUD","platform":OS.get_name()}))
    quit(0 if all_pass else 1)
