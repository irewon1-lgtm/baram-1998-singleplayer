extends SceneTree
const Store=preload("res://save_store.gd")
var options={}
func _initialize():
    for arg in OS.get_cmdline_user_args():
        var parts=arg.trim_prefix("--").split("=",true,1);options[parts[0]]=parts[1]
    call_deferred("run")
func run():
    var store=Store.new();var start=Time.get_ticks_msec()
    print("SAVE_PERF before_read")
    var state=store.read_state(options.input)
    print("SAVE_PERF read_ms=",Time.get_ticks_msec()-start," entities=",state.get("world",{}).size())
    start=Time.get_ticks_msec()
    var ok=store.write_state(options.output,state)
    print("SAVE_PERF write_ms=",Time.get_ticks_msec()-start," ok=",ok," error=",store.last_error)
    quit(0 if ok else 1)
