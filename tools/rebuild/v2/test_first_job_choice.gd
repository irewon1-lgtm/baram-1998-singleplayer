extends "res://../../tools/rebuild/v2/test_progression.gd"
## Fresh seed1 characters, production actions/ticks and earned loot only.
## No fixture/restore/state assignment/XP or item grants; time accelerated.
var selected_skills := {"전사":"KRO-2baeab06ad4c","도적":"KRO-a6afe4d113cf","주술사":"KRO-3559b12ed6a7","도사":"KRO-62769e97ce90"}
var progress: Array=[]
const FastNavigation=preload("res://input/grid_navigation.gd")
func path_to(_map_id: String,target: Vector2i,near: int=0,_allow_exit: bool=false) -> Array:
 return FastNavigation.route(game,target,near)

func event_slice(from: int) -> Array:
 var found: Array=[]
 for row in transcript.slice(from):
  found.append_array(row.get("events",[]))
  found.append_array(row.get("result",{}).get("events",[]))
 return found
func fund_and_materials(definition: Dictionary) -> bool:
 var wanted: Dictionary=definition.get("ingredients",{}).duplicate(true)
 var required_money:=int(definition.get("learn_money",0))
 var acorn:=item_id("도토리")
 var npc:=merchant_for(acorn,"sell_price")
 var price:=int(record("npcs",npc).shop[acorn].sell_price)
 var missing:=maxi(0,required_money-int(char_state().money))
 var quantity:=int(ceil(float(missing)/float(price)))
 wanted[acorn]=int(wanted.get(acorn,0))+quantity
 if not hunt_until(int(definition.learn_level),wanted,0):return false
 if quantity>0:
  if not approach_npc(npc):return false
  while quantity>0:
   var instance:=instance_for(acorn)
   var amount:=mini(quantity,int(instance.get("quantity",0)))
   if amount<=0:return false
   var before:=int(char_state().money)
   var sold:=send({"type":"sell","npc_id":npc,"instance_id":instance.instance_id,"quantity":amount})
   if not check(active_phase+"_earned_excess_material_sale_exact",sold.status=="OK" and int(char_state().money)==before+amount*price,sold):return false
   quantity-=amount
 for id in definition.get("ingredients",{}):
  if item_count(str(id))<int(definition.ingredients[id]):return false
 return int(char_state().money)>=required_money
func cast_observation(job: String,id: String,definition: Dictionary) -> Dictionary:
 advance_time(1.0)
 var before: Dictionary=game.snapshot()
 var derived: Dictionary=game.derived_stats().duplicate(true)
 if job=="주술사":
  if not travel_to(hunting_map()):return {"status":"FAIL","reason":"no_field"}
  var attempts: Array=[]
  for retry in range(6):
   advance_time(1.1)
   var target_id:=nearest_monster()
   var target: Dictionary=game.state.monsters.get(target_id,{})
   if target.is_empty() or not walk_to(str(target.map_id),int(target.x),int(target.y),1):return {"status":"FAIL","reason":"no_projectile_target","attempts":attempts}
   before=game.snapshot()
   var at:=transcript.size()
   var cast:=send({"type":"cast","skill_id":id,"target_id":target_id})
   var mp_after_accept:=int(char_state().mp)
   advance_time(1.5)
   var events:=event_slice(at)
   var applied:=events.any(func(e):return e.get("type")=="skill_applied" and e.get("skill_id")==id)
   var damaged:=int(game.state.monsters[target_id].hp)<int(before.monsters[target_id].hp)
   var success: bool=cast.status=="OK" and applied and damaged and mp_after_accept==int(before.character.mp)-int(definition.mp_cost)
   attempts.append({"cast":cast,"target_id":target_id,"before_target_hp":before.monsters[target_id].hp,"after_target_hp":game.state.monsters[target_id].hp,"accepted_mp":mp_after_accept,"before_mp":before.character.mp,"events":events,"resolved_damage":success})
   if success:return {"status":"PASS","semantics":"guardian_fire_projectile_damage","attempts":attempts,"ordinary_retry_policy":"At most6casts, reapproachnormallyaftertargetmotion; every miss andpaidMP retained, no targetfreezing/stateseeding."}
  return {"status":"FAIL","semantics":"guardian_fire_projectile_damage","attempts":attempts,"reason":"no_resolved_hit_after6ordinarycasts"}
 if job=="도사":
  if not travel_to(hunting_map()):return {"status":"FAIL","reason":"no_field"}
  # Unequipping through real command is an intentional ordinary choice;
  # provoke a living novice to obtain real damage, never edit HP.
  var weapon:=str(game.state.equipment.get("weapon",""))
  if not weapon.is_empty():send({"type":"unequip","slot":"weapon"})
  var attempts:=0
  while int(char_state().hp)>=int(char_state().hp_max) and attempts<8:
   var target_id:=nearest_monster()
   var target: Dictionary=game.state.monsters.get(target_id,{})
   if target.is_empty() or not walk_to(str(target.map_id),int(target.x),int(target.y),1):return {"status":"FAIL","reason":"no_natural_wounding_target"}
   send({"type":"attack","target_id":target_id},1.3)
   attempts+=1
  if int(char_state().hp)>=int(char_state().hp_max):return {"status":"FAIL","reason":"no_natural_wound_after8attacks","stats":game.state.stats.duplicate(true)}
  before=game.snapshot()
  var at:=transcript.size()
  var cast:=send({"type":"cast","skill_id":id})
  var mp_after_accept:=int(char_state().mp)
  advance_time(float(definition.impact_delay)+0.1)
  var events:=event_slice(at)
  var heal: Array=events.filter(func(e):return e.get("type")=="skill_applied" and e.get("skill_id")==id)
  var applied:=not heal.is_empty() and int(heal[0].hp)>int(before.character.hp)
  if not weapon.is_empty():send({"type":"equip","instance_id":weapon})
  return {"status":"PASS" if cast.status=="OK" and applied and mp_after_accept==int(before.character.mp)-int(definition.mp_cost) else "FAIL","semantics":"self_heal_after_real_enemy_hit","cast":cast,"natural_wounding_attacks":attempts,"before_hp":before.character.hp,"before_hp_max":before.character.hp_max,"after_hp":char_state().hp,"before_mp":before.character.mp,"accepted_mp":mp_after_accept,"events":events}
 var at:=transcript.size()
 var cast:=send({"type":"cast","skill_id":id})
 var mp_after_accept:=int(char_state().mp)
 advance_time(float(definition.impact_delay)+0.1)
 var events:=event_slice(at)
 var after: Dictionary=game.derived_stats().duplicate(true)
 var buff: Dictionary=game.state.buffs.get(id,{})
 var meaningful:=float(after.get("attack_multiplier",1.0))>float(derived.get("attack_multiplier",1.0)) if job=="전사" else int(after.attack)>int(derived.attack) and str(buff.get("form_monster_id",""))==str(definition.form_monster_id)
 return {"status":"PASS" if cast.status=="OK" and meaningful and mp_after_accept==int(before.character.mp)-int(definition.mp_cost) else "FAIL","semantics":"double_basic_attack_multiplier" if job=="전사" else "animal_transformation_and_attack_defense_buff","cast":cast,"derived_before":derived,"derived_after":after,"buff":buff,"before_mp":before.character.mp,"accepted_mp":mp_after_accept,"events":events}
func probe(job: String) -> Dictionary:
 active_phase=job;sequence=0
 game=Game.new()
 if not check(job+"_production_configures",game.configure(content),game.errors):return {"job":job,"status":"FAIL"}
 var created: Dictionary=game.create_character("선택"+job,"natural:choice-"+str(job.hash()),{"guardian":"주작","desired_job":job,"seed":1})
 if not check(job+"_fresh_Lv1_zero_xp_money_skills",created.status=="OK" and char_state().level==1 and char_state().xp==0 and char_state().money==0 and game.state.skills.is_empty(),brief()):return {"job":job,"status":"FAIL"}
 var initial: Dictionary=game.snapshot()
 var teacher: String=str(content.jobs[job].get("teacher_id",teacher_for(job)))
 if not check(job+"_earned_Lv5",hunt_until(5,{},0),brief()):return {"job":job,"status":"FAIL"}
 if not check(job+"_walk_teacher",approach_npc(teacher),brief()):return {"job":job,"status":"FAIL"}
 var changed:=send({"type":"change_job","npc_id":teacher,"job":job})
 if not check(job+"_earned_actual_job_change",changed.status=="OK" and char_state().job==job,changed):return {"job":job,"status":"FAIL"}
 # Earn the already-tested inexpensive weapon upgrade before longer novice work.
 var upgrade:=affordable_upgrade()
 if not check(job+"_upgrade_available",not upgrade.is_empty(),upgrade):return {"job":job,"status":"FAIL"}
 var funding:={"learn_level":5,"ingredients":{},"learn_money":upgrade.price}
 if not check(job+"_earned_upgrade_funding",fund_and_materials(funding),brief()):return {"job":job,"status":"FAIL"}
 if not approach_npc(upgrade.npc_id):return {"job":job,"status":"FAIL","reason":"upgrade_route"}
 var buy:=send({"type":"buy","npc_id":upgrade.npc_id,"item_id":upgrade.item_id,"quantity":1})
 if not check(job+"_earned_upgrade_purchase",buy.status=="OK",buy):return {"job":job,"status":"FAIL"}
 var owned:=instance_for(upgrade.item_id)
 var equipped:=send({"type":"equip","instance_id":owned.instance_id})
 if not check(job+"_earned_upgrade_equipped",equipped.status=="OK",equipped):return {"job":job,"status":"FAIL"}
 var id: String=selected_skills[job]
 var definition: Dictionary=content.skills[id]
 if not check(job+"_earned_documented_level_material_money",fund_and_materials(definition),brief()):return {"job":job,"status":"FAIL","reason":"natural_learning_funding"}
 if not check(job+"_walk_actual_skill_teacher",approach_npc(teacher),brief()):return {"job":job,"status":"FAIL"}
 var before: Dictionary=game.snapshot()
 var learned:=send({"type":"learn","npc_id":teacher,"skill_id":id})
 var exact:=int(char_state().money)==int(before.character.money)-int(definition.learn_money)
 for item in definition.ingredients:
  var count:=0
  for row in before.inventory:
   if row.item_id==item:count+=int(row.quantity)
  exact=exact and item_count(str(item))==count-int(definition.ingredients[item])
 if not check(job+"_learn_consumes_exact_earned_requirements",learned.status=="OK" and id in game.state.skills and exact,learned):return {"job":job,"status":"FAIL"}
 var observation:=cast_observation(job,id,definition)
 check(job+"_meaningful_job_skill_actual_cast",observation.status=="PASS",observation)
 var store=Store.new()
 var definitions: Dictionary=store.prepare_content(content)
 var file: String="user://gameplay-p3/first-job-choice/"+str(run_started)+"/"+str(job.hash())+".json"
 var saved: Dictionary=store.write_game(file,game.snapshot(),str(char_state().owner_id),definitions)
 var read: Dictionary=store.read_game(file,str(char_state().owner_id),definitions)
 check(job+"_natural_progress_and_buff_disk_roundtrip",saved.status=="SAVED" and read.status=="OK" and store._canonical(read.payload)==store._canonical(game.snapshot()),saved)
 return {"job":job,"status":observation.status,"initial":initial.character,"final":brief(),"kills":game.state.stats.kills,"stats":game.state.stats.duplicate(true),"commands":sequence,"simulation_seconds":game.state.sim_time,"chosen_skill":{"id":id,"name":definition.name,"job":definition.job,"learn_level":definition.learn_level,"learn_money":definition.learn_money,"ingredients":definition.ingredients},"before_learning":before.character,"cast_observation":observation,"save":file,"save_status":saved.status}
func run() -> void:
 run_started=Time.get_ticks_msec()
 content=JSON.parse_string(FileAccess.get_file_as_string(content_path))
 initial_content_sha=FileAccess.get_sha256(content_path)
 initial_engine_sha=FileAccess.get_sha256("res://state/gameplay_state.gd")
 initial_store_sha=FileAccess.get_sha256("res://storage/gameplay_store.gd")
 limits={"commands":50000,"kills":1200,"path_nodes":8192}
 for job in ["전사","도적","주술사","도사"]:
  var result:=probe(job)
  progress.append(result)
  print("FIRST_JOB_CHOICE "+JSON.stringify({"job":job,"status":result.status,"kills":result.get("kills"),"final":result.get("final")}))
 check("content_engine_store_unchanged",initial_content_sha==FileAccess.get_sha256(content_path) and initial_engine_sha==FileAccess.get_sha256("res://state/gameplay_state.gd") and initial_store_sha==FileAccess.get_sha256("res://storage/gameplay_store.gd"))
 finish()
func finish() -> void:
 var report:={"schema":"baram.b5.first-meaningful-job-choice/1","status":"PASS" if failures==0 and progress.size()==4 and progress.all(func(p):return p.status=="PASS") else "FAIL","failures":failures,"checks":checks,"jobs":progress,"wall_seconds":float(Time.get_ticks_msec()-run_started)/1000.0,"scope":"Fourseed1 freshcharacters; productionearnedXP,loot,sale,upgrade,documentedlearningrequirementsandactualcast; timeaccelerated,noXP/money/item/skillgrants,nofixturerestore/stateedits; notGUI/realtimehuman/nativeplatform/natural1–99proof.","content_sha256":initial_content_sha,"source_fingerprints":{"engine":initial_engine_sha,"store":initial_store_sha,"operator":FileAccess.get_sha256(get_script().resource_path),"parent_progression":FileAccess.get_sha256("res://../../tools/rebuild/v2/test_progression.gd")}}
 for pair in [[report_path,report],[trace_path,{"schema":"baram.b5.first-job-choice-command-trace/1","commands":transcript}]]:
  DirAccess.make_dir_recursive_absolute(str(pair[0]).get_base_dir())
  var file:=FileAccess.open(str(pair[0]),FileAccess.WRITE)
  if file:file.store_string(JSON.stringify(pair[1],"  ")+"\n");file.close()
 print("FIRST_JOB_CHOICE_RESULT "+JSON.stringify({"status":report.status,"failures":failures,"jobs":progress.size()}));quit(0 if report.status=="PASS" else 1)
