extends SceneTree
const Game=preload("res://state/gameplay_state.gd")
const Content=preload("res://content/gameplay_content.gd")
const Store=preload("res://storage/gameplay_store.gd")
var game=Game.new()
var content=Content.new()
var checks: Array=[]
var fails:=0
var seq:=0
func _initialize() -> void:call_deferred("run")
func check(id: String, ok: bool,detail: Variant=null) -> void:
 checks.append({"id":id,"status":"PASS" if ok else "FAIL","detail":detail})
 if not ok:fails+=1
func command(value: Dictionary) -> Dictionary:
 seq+=1;value.request_id="contract:"+str(seq);return game.command(value)
func run() -> void:
 var path:=OS.get_environment("BARAM_GAMEPLAY_RUNTIME")
 if path.is_empty():path="res://private_runtime"
 check("input",content.open(path) and game.configure(content.data))
 game.create_character("계약시험","fixture")
 var clean: Dictionary=game.snapshot()
 var ids: Array=[]
 for id in game.state.monsters:
  if game.state.monsters[id].map_id=="gp:map:south_field":ids.append(id)
 ids.sort()
 var c: Dictionary=game.state.character;c.map_id="gp:map:south_field";c.x=16;c.y=16;c.direction=1
 var a: Dictionary=game.state.monsters[ids[0]];a.x=17;a.y=16;a.ai_at=100
 var b: Dictionary=game.state.monsters[ids[1]];b.x=16;b.y=17;b.ai_at=100
 check("auto_target_prefers_facing",game.attack_target()==ids[0])
 check("no_diagonal_range1",game._target(ids[0],1).size()>0)
 var hp:=int(a.hp);var r:=command({"type":"attack"})
 game.state.monsters[ids[0]].generation+=1
 game.tick(.2)
 check("stale_generation_cannot_take_delayed_damage",int(game.state.monsters[ids[0]].hp)==hp)
 game.state=clean.duplicate(true);game.state.cooldowns={}
 r=command({"type":"bind_hotkey","slot":"1","skill_id":"KRO-3559b12ed6a7"})
 check("unlearned_hotkey_binding_refused",r.reason=="SKILL_NOT_LEARNED" and game.state.hotkeys.is_empty())
 r=command({"type":"bind_hotkey","slot":"0","skill_id":"KRO-3559b12ed6a7"})
 check("invalid_hotkey_binding_refused",r.reason=="INVALID_HOTKEY")
 # All affected exit direction paths, including interiors, use real movement commands.
 for map_id in content.data.maps:
  for exit in content.data.maps[map_id].get("exits",[]):
   game.state=clean.duplicate(true);game.state.cooldowns={}
   var step:=Vector2i.ZERO
   for d in [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]:
    var at: Vector2i=Vector2i(exit.x,exit.y)-d
    if game.valid_position(map_id,at.x,at.y) and not game._occupied(map_id,at.x,at.y):step=d;break
   if step==Vector2i.ZERO:check("exit_approach:"+str(exit.id),false);continue
   c=game.state.character;c.map_id=map_id;c.x=int(exit.x)-step.x;c.y=int(exit.y)-step.y;c.level=10
   r=command({"type":"move","dx":step.x,"dy":step.y})
   c=game.state.character
   check("exit_actual_command:"+str(exit.id),r.status=="OK" and c.map_id==exit.to_map and int(c.x)==int(exit.to_x) and int(c.y)==int(exit.to_y) and int(c.direction)==game._direction_value(exit.get("direction",2)),r)
 # Compatibility through the unchanged storage validator, adding actual learned hotkey assignment.
 var old:=OS.get_environment("BARAM_REPAIR_OLD_SAVE")
 if not old.is_empty():
  var store=Store.new();var source: Variant=JSON.parse_string(FileAccess.get_file_as_string(old))
  var read: Dictionary=store._decode(FileAccess.get_file_as_string(old),str(source.owner),content.data)
  check("legacy_natural_save_decodes_unchanged",read.status=="OK")
  if read.has("payload"):
   game.state={};r=game.restore(read.payload);check("legacy_natural_save_restores",r.status=="OK")
   if not game.state.skills.is_empty():
    r=command({"type":"bind_hotkey","slot":"2","skill_id":game.state.skills[0]})
    check("learned_hotkey_binding_uses_same_command",r.status=="OK" and game.state.hotkeys["2"]==game.state.skills[0])
    var save_path:="user://gameplay-p3/tests/hotkey-"+str(Time.get_unix_time_from_system())+".json"
    var write: Dictionary=store.write_game(save_path,game.snapshot(),str(source.owner),content.data)
    var loaded: Dictionary=store.read_game(save_path,str(source.owner),content.data)
    check("reassigned_hotkey_persists_exactly",write.status in ["SAVED","OK"] and loaded.has("payload") and loaded.payload.hotkeys==game.state.hotkeys,write)
 var result:={"schema":"baram.repair.affected-contract/1","status":"PASS" if fails==0 else "FAIL","checks":checks,"failures":fails,"scope":"affected engine functions and unchanged save safety; fixtures and read-only legacy natural save, no platform claims"}
 var output:=OS.get_environment("BARAM_CONTRACT_REPORT")
 if not output.is_empty():var f:=FileAccess.open(output,FileAccess.WRITE);f.store_string(JSON.stringify(result,"  ")+"\n")
 print("REPAIR_CONTRACT "+JSON.stringify(result));quit(0 if fails==0 else 1)
