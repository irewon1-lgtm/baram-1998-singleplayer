extends SceneTree
## Executes original ASSETS003 timelines with a recording draw sink.
const WorkAssets=preload("res://work_assets.gd")
class Registry:
    extends RefCounted
    var records={}
    func definition(id: String) -> Dictionary:return records.get(id,{})
class Renderer:
    extends WorkAssets
    var frames_drawn=[]
    func draw_frame(_canvas, asset_id: String, index: int, _feet: Vector2, _opacity: float=1.0) -> bool:
        frames_drawn.append({"asset":asset_id,"frame":index});return true

func _initialize():call_deferred("run")
func run():
    var options={}
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--") and "=" in arg:
            var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    if not options.has_all(["source","out"]):push_error("--source and --out required");quit(2);return
    var registry=Registry.new()
    for line in FileAccess.get_file_as_string(options.source).split("\n",false):
        var record=JSON.parse_string(line);registry.records[record.id]=record.data
    var renderer=Renderer.new(registry)
    var checks=[];var blanks=0;var visible=0
    for id in registry.records:
        var meta=registry.records[id].get("metadata",{})
        for layer in ["front","back"]:
            var elapsed=0
            for frame in meta.get(layer,[]):
                var before=renderer.frames_drawn.size()
                var duration=int(frame.delay_ms)
                var first=renderer.effect_frame(id,layer,elapsed,100000)
                var last=renderer.effect_frame(id,layer,elapsed+duration-1,100000)
                var drawn=renderer.draw_effect(null,id,layer,elapsed+duration/2,Vector2.ZERO,100000)
                var blank=int(frame.frame)==-1
                var good=not first.is_empty() and not last.is_empty() and int(first.frame)==int(frame.frame) and int(last.frame)==int(frame.frame) and drawn and renderer.last_error.is_empty()
                good=good and renderer.frames_drawn.size()==before+(0 if blank else 1)
                if blank:blanks+=1
                else:visible+=1
                checks.append({"name":id+":"+layer+":"+str(elapsed),"frame":frame.frame,"delay_ms":duration,"status":"PASS" if good else "FAIL"})
                elapsed+=duration
    var expiry=renderer.draw_effect(null,"wk.asset.kr491.effect.070","back",2000,Vector2.ZERO,2000)
    checks.append({"name":"expired_effect_has_no_draw","status":"PASS" if not expiry else "FAIL"})
    var report={"scope":"Original ASSETS003 timed frame timeline and draw dispatch only; raster appearance is outside this probe.","source_sha256":FileAccess.get_sha256(options.source),"assets":registry.records.size(),"blank_intervals":blanks,"visible_intervals":visible,"checks":checks,"status":"FAIL" if checks.any(func(c):return c.status=="FAIL") else "PASS"}
    DirAccess.make_dir_recursive_absolute(options.out.get_base_dir())
    var output=FileAccess.open(options.out,FileAccess.WRITE);output.store_string(JSON.stringify(report,"  "));output.close()
    print("EFFECT_WAIT_RESULT "+JSON.stringify({"status":report.status,"checks":checks.size(),"assets":report.assets,"blank_intervals":blanks,"visible_intervals":visible}))
    quit(0 if report.status=="PASS" else 1)
