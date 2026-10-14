extends RefCounted
## Common atomic player operations. Definitions and runtime instances stay apart.
const Precision = preload("res://precision.gd")
var owner_ref: WeakRef
var rules:
    get:return owner_ref.get_ref()
var last_error = {}

func _init(owner):owner_ref=weakref(owner)

func error(code: String, id: String="", field: String="", value=null) -> Dictionary:
    last_error={"code":code,"content_id":id,"field":field,"value":value,"content_version":rules.content_version}
    return {"ok":false,"error":code}

func item_values(id: String) -> Dictionary:return rules.item(id)

func is_gear(id: String) -> bool:
    var value=item_values(id)
    return int(rules.value_or(value,"damage_max",0))>0 or value.get("slot","") not in ["","none"] or rules.visual_bindings.get(id,{}).get("slot","") in ["weapon","body"]

func ensure(p: Dictionary):
    if not p.has("equipment_instances"):p.equipment_instances={}
    if not p.has("equipment_slots"):p.equipment_slots={}
    if not p.has("next_equipment_serial"):p.next_equipment_serial=1
    if not p.has("committed_actions"):p.committed_actions=[]
    if not p.has("quest_progress"):p.quest_progress={}
    if not p.has("time_us"):p.time_us=0
    if not p.has("statuses"):p.statuses={}
    if not p.has("item_modifiers"):p.item_modifiers={}
    if not p.has("extensions"):p.extensions={}
    if rules.runtime_definitions.has("wk.class.novice"):
        var conversions=[]
        for key in p.inventory.keys():
            var id=rules.find_content("item",key).get("id",key)
            if id==key or not id.begins_with("kr."):continue
            p.inventory[id]=int(p.inventory.get(id,0))+int(p.inventory[key]);p.inventory.erase(key)
            for gear in p.equipment_instances.values():
                if gear.definition_id==key:gear.definition_id=id
            for field in ["equipped","armor_equipped"]:
                if p.get(field,"")==key:p[field]=id
            if p.get("durability",{}).has(key):p.durability[id]=p.durability[key];p.durability.erase(key)
            conversions.append({"previous":key,"id":id})
        if not conversions.is_empty():
            if not p.has("content_migrations"):p.content_migrations=[]
            p.content_migrations.append({"manifest":rules.content_version,"item_id_conversions":conversions})
    p.core_format=1
    # Materialize prior name-keyed gear WITHOUT changing inventory quantities,
    # IDs, durability, money, quests or growth. Unknown gear is left intact.
    for id in p.inventory:
        if not is_gear(id):continue
        var existing=instances(p,id)
        for i in range(maxi(0,int(p.inventory[id])-existing.size())):create_instance(p,id)
    for slot in ["weapon","body"]:
        var legacy=p.get("equipped" if slot=="weapon" else "armor_equipped","")
        if legacy!="" and not p.equipment_slots.has(slot):
            var list=instances(p,legacy)
            if not list.is_empty():p.equipment_slots[slot]=list[0]
    for slot in p.equipment_slots.keys() if rules.runtime_definitions.has("wk.class.novice") else []:
        var instance=p.equipment_instances.get(p.equipment_slots[slot],{})
        if instance.is_empty():continue
        var wanted=item_values(instance.definition_id).get("slot",slot)
        if wanted==slot:continue
        p.equipment_slots.erase(slot)
        if slot in ["weapon","body"]:p["equipped" if slot=="weapon" else "armor_equipped"]=""
        if wanted not in ["","none"] and not p.equipment_slots.has(wanted):
            p.equipment_slots[wanted]=instance.id
            if wanted in ["weapon","body"]:p["equipped" if wanted=="weapon" else "armor_equipped"]=instance.definition_id
        if not p.has("content_migrations"):p.content_migrations=[]
        p.content_migrations.append({"manifest":rules.content_version,"instance_id":instance.id,"old_slot":slot,"new_slot":wanted,"inventory_preserved":true})

func instances(p: Dictionary, definition_id: String) -> Array:
    var found=[]
    for id in p.get("equipment_instances",{}):
        var gear=p.equipment_instances[id]
        if gear.definition_id==definition_id and not gear.get("destroyed",false):found.append(id)
    found.sort()
    return found

func create_instance(p: Dictionary, definition_id: String) -> String:
    var id="gear.instance."+str(int(p.next_equipment_serial))
    p.next_equipment_serial=int(p.next_equipment_serial)+1
    p.equipment_instances[id]={"id":id,"definition_id":definition_id,"enhancement_level":0,"bonuses":{},
        "durability":int(p.get("durability",{}).get(definition_id,rules.value_or(item_values(definition_id),"durability",1000))),"destroyed":false}
    return id

func commit(p: Dictionary, candidate: Dictionary, action_id: String="") -> Dictionary:
    if int(candidate.get("gold",0))<0:return error("NEGATIVE_GOLD")
    if int(candidate.get("gold",0))>Precision.EXACT_MAX:return error("GOLD_EXACT_INTEGER_LIMIT")
    for id in candidate.inventory:
        if int(candidate.inventory[id])<0:return error("NEGATIVE_ITEM",id)
    for type in ["hp","mp"]:
        var field=type+"_max";var previous=int(candidate.get("applied_equipment_"+type,0))
        var bonus=equipped_bonus(candidate,field)
        candidate[field]=maxi(1,int(candidate[field])-previous+bonus)
        candidate[type]=mini(int(candidate[type]),int(candidate[field]));candidate["applied_equipment_"+type]=bonus
    if action_id!="":
        candidate.committed_actions.append(action_id)
        while candidate.committed_actions.size()>128:candidate.committed_actions.pop_front()
    p.clear();p.merge(candidate,true)
    last_error={}
    return {"ok":true,"error":""}

func begin(p: Dictionary, action_id: String="") -> Dictionary:
    var candidate=p.duplicate(true)
    if candidate.get("core_format",0)!=1 or not candidate.has("item_modifiers"):ensure(candidate)
    if action_id!="" and action_id in candidate.committed_actions:return {}
    return candidate

func inventory_change(p: Dictionary, deltas: Dictionary) -> bool:
    if rules.runtime_definitions.has("wk.class.novice"):
        var normalized={}
        for key in deltas:
            var id=rules.find_content("item",key).get("id",key)
            normalized[id]=int(normalized.get(id,0))+deltas[key]
        deltas=normalized
    for id in deltas:
        var amount=int(deltas[id])
        if float(deltas[id])!=float(amount) or item_values(id).is_empty():return false
        var count=int(p.inventory.get(id,0))+amount
        if count<0:return false
        var limit=int(rules.value_or(item_values(id),"stack_limit",99))
        if limit<=0:return false
        # Keep legacy's checked one-kind limit unless Work explicitly supplies
        # independent equipment instances. One sword's upgrade never edits its
        # definition or another instance, regardless of this inventory policy.
        if limit==1 and count>1 and not item_values(id).get("instance_equipment",false):return false
        p.inventory[id]=count
        if p.get("item_modifiers",{}).has(id):
            while p.item_modifiers[id].size()>count:p.item_modifiers[id].pop_back()
    var slots=0
    for id in p.inventory:
        var limit=maxi(1,int(rules.value_or(item_values(id),"stack_limit",99)))
        slots+=ceili(float(p.inventory[id])/limit)
    if slots>52:return false
    for id in deltas:
        if not is_gear(id):continue
        var amount=int(deltas[id])
        if amount>0:
            for i in range(amount):create_instance(p,id)
        elif amount<0:
            var available=instances(p,id).filter(func(g):return g not in p.equipment_slots.values())
            if available.size()<-amount:return false
            for i in range(-amount):p.equipment_instances[available[i]].destroyed=true
    return true

func exchange(p: Dictionary, money_delta: int, deltas: Dictionary, action_id: String="") -> Dictionary:
    var candidate=begin(p,action_id)
    if candidate.is_empty():return {"ok":true,"already_applied":true}
    if int(candidate.gold)+money_delta<0:return error("INSUFFICIENT_GOLD")
    if not inventory_change(candidate,deltas):return error("ITEM_OR_CAPACITY_CONDITION")
    candidate.gold=int(candidate.gold)+money_delta
    return commit(p,candidate,action_id)

func equip_instance(p: Dictionary, gear_id: String) -> Dictionary:
    var candidate=begin(p)
    if not candidate.equipment_instances.has(gear_id):return error("GEAR_INSTANCE_MISSING",gear_id)
    var gear=candidate.equipment_instances[gear_id]
    var values=item_values(gear.definition_id)
    if not is_gear(gear.definition_id):return error("GEAR_DEFINITION_NOT_WEARABLE",gear.definition_id)
    if gear.destroyed or int(gear.durability)<=0:return error("GEAR_UNUSABLE",gear_id)
    if int(candidate.level)<int(rules.value_or(values,"level_required",0)) or int(candidate.strength)<int(rules.value_or(values,"strength_required",0)):
        return error("EQUIP_REQUIREMENT",gear.definition_id)
    if int(candidate.rank)<int(values.get("advancement_rank_required",0)):return error("EQUIP_ADVANCEMENT_RANK",gear.definition_id)
    var jobs=values.get("allowed_jobs",[])
    if not jobs.is_empty() and candidate.job not in jobs:return error("EQUIP_CLASS",gear.definition_id)
    var slot=values.get("slot",rules.visual_bindings.get(gear.definition_id,{}).get("slot","weapon" if int(rules.value_or(values,"damage_max",0))>0 else "body"))
    candidate.equipment_slots[slot]=gear_id
    if slot in ["weapon","body"]:candidate["equipped" if slot=="weapon" else "armor_equipped"]=gear.definition_id
    candidate.durability[gear.definition_id]=int(gear.durability)
    return commit(p,candidate)

func unequip(p: Dictionary, slot: String) -> Dictionary:
    var candidate=begin(p)
    candidate.equipment_slots.erase(slot)
    if slot in ["weapon","body"]:candidate["equipped" if slot=="weapon" else "armor_equipped"]=""
    return commit(p,candidate)

func equipped_bonus(p: Dictionary, field: String) -> int:
    var sum=0
    for id in p.get("equipment_slots",{}).values():
        var gear=p.get("equipment_instances",{}).get(id,{})
        if not gear.get("destroyed",true):
            sum+=int(gear.get("bonuses",{}).get(field,0))
            var stat={"hp_max":"hp_bonus","mp_max":"mp_bonus","strength":"strength_bonus","dexterity":"dexterity_bonus","intelligence":"intelligence_bonus"}.get(field,"")
            if stat!="":sum+=int(rules.value_or(item_values(gear.definition_id),stat,0))
            if field=="armor_class" and p.equipment_slots.find_key(id) not in ["weapon","body"]:sum+=int(rules.value_or(item_values(gear.definition_id),"armor_class",0))
    return sum

func damage(target: Dictionary, amount: int) -> int:
    if amount<0 or not target.has("hp"):error("INVALID_DAMAGE");return 0
    var remaining=amount
    for id in target.get("statuses",{}).keys():
        var state=target.statuses[id]
        if state.type!="shield":continue
        var absorbed=mini(remaining,int(state.amount))
        remaining-=absorbed;state.amount=int(state.amount)-absorbed
        if state.amount<=0:target.statuses.erase(id)
    target.hp=maxi(0,int(target.hp)-remaining)
    return remaining

func status_modifier(target: Dictionary, field: String) -> int:
    var total=0
    for status in target.get("statuses",{}).values():total+=int(status.get("modifiers",{}).get(field,0))
    return total

func recovery(p: Dictionary, hp: int, mp: int):
    p.hp=clampi(int(p.hp)+hp,0,int(p.hp_max))
    p.mp=clampi(int(p.mp)+mp,0,int(p.mp_max))

func rest(p: Dictionary, cost: int) -> Dictionary:
    var candidate=begin(p)
    if cost<0 or int(candidate.gold)<cost:return error("REST_COST")
    candidate.gold-=cost;candidate.hp=candidate.hp_max;candidate.mp=candidate.mp_max
    return commit(p,candidate)

func cast_cost(p: Dictionary, mp: int, hp: int, cooldown_ms: int, skill_id: String) -> bool:
    if mp<0 or hp<0 or cooldown_ms<0 or int(p.mp)<mp or int(p.hp)<=hp or float(p.cooldowns.get(skill_id,0))>0:return false
    var candidate=begin(p)
    candidate.mp-=mp;candidate.hp-=hp;candidate.cooldowns[skill_id]=float(cooldown_ms)/1000.0
    return commit(p,candidate).ok

func consume(p: Dictionary, item_id: String) -> bool:
    var value=item_values(item_id)
    var hp=int(rules.value_or(value,"heal_amount",0));var mp=int(rules.value_or(value,"restore_mp",0))
    if hp<=0 and mp<=0:return false
    var candidate=begin(p)
    var modifiers=candidate.get("item_modifiers",{}).get(item_id,[])
    if not modifiers.is_empty():
        hp*=int(modifiers[0].get("heal_multiplier",1))
        modifiers.pop_front()
    if not inventory_change(candidate,{item_id:-1}):return false
    recovery(candidate,hp,mp)
    return commit(p,candidate).ok

func use_return_item(p: Dictionary, item_id: String, destination: Dictionary) -> Dictionary:
    if not item_values(item_id).get("teleport_safe_return",false) or not destination.has_all(["map","entry"]) or destination.entry.size()!=2:return error("RETURN_ITEM_CONDITION",item_id)
    var candidate=begin(p)
    if not inventory_change(candidate,{item_id:-1}):return error("RETURN_ITEM_MISSING",item_id)
    candidate.map=destination.map;candidate.x=int(destination.entry[0]);candidate.y=int(destination.entry[1])
    return commit(p,candidate)

func damage_gear(p: Dictionary, amount: int):
    ensure(p)
    var id=p.equipment_slots.get("weapon","")
    if id=="" or not p.equipment_instances.has(id):return
    var gear=p.equipment_instances[id]
    gear.durability=maxi(0,int(gear.durability)-amount)
    p.durability[gear.definition_id]=gear.durability
    if gear.durability==0:p.equipment_slots.erase("weapon");p.equipped=""

func repair(p: Dictionary, item_id: String, cost: int, maximum: int) -> bool:
    var candidate=begin(p)
    ensure(candidate)
    if cost<0 or cost>int(candidate.gold):return false
    var id=candidate.equipment_slots.get("weapon","")
    if id=="" or candidate.equipment_instances[id].definition_id!=item_id:
        var available=instances(candidate,item_id)
        if available.is_empty():return false
        id=available[0]
    candidate.gold-=cost;candidate.equipment_instances[id].durability=maximum;candidate.durability[item_id]=maximum
    return commit(p,candidate).ok

func enhance(p: Dictionary, gear_id: String, definition: Dictionary, action_id: String="") -> Dictionary:
    var candidate=begin(p,action_id)
    if candidate.is_empty():return {"ok":true,"already_applied":true}
    if not candidate.equipment_instances.has(gear_id):return error("GEAR_INSTANCE_MISSING",gear_id)
    var gear=candidate.equipment_instances[gear_id]
    if gear.destroyed or gear.definition_id not in definition.get("applicable_item_ids",[]):return error("ENHANCE_ITEM_CONDITION",gear_id)
    if definition.get("default_enabled",true)==false and not candidate.get("extensions",{}).get("optional_enhancement",false):return error("EXTENSION_REQUIRES_OPT_IN",gear_id)
    var stage={}
    for value in definition.get("stages",[]):
        if int(value.get("from_level",int(value.get("level",0))-1))==int(gear.enhancement_level):stage=value;break
    if stage.is_empty():return error("ENHANCE_STAGE_MISSING",gear_id)
    var before_rng=rules.rng.state
    var draw=Precision.draw(rules.rng,"exclusive",stage.get("outcomes",[]))
    if not draw.ok:return error(draw.error,definition.get("id",""))
    var deltas={}
    var costs=stage.get("cost",stage)
    for item in costs.get("materials",[]):deltas[item.item_id]=int(deltas.get(item.item_id,0))-int(item.quantity)
    var gold=int(costs.get("gold",costs.get("gold_cost",-1)))
    if gold<0 or candidate.gold<gold or not inventory_change(candidate,deltas):
        rules.rng.state=before_rng
        return error("ENHANCE_MATERIAL_OR_GOLD",gear_id)
    candidate.gold-=gold
    var outcome=draw.items[0]
    var kind=outcome.get("result","")
    if kind=="success":
        gear.enhancement_level=int(outcome.get("new_level",outcome.get("to_level",int(gear.enhancement_level)+1)))
        for field in outcome.get("bonuses",{}):gear.bonuses[field]=int(gear.bonuses.get(field,0))+int(outcome.bonuses[field])
    elif kind=="downgrade":gear.enhancement_level=maxi(0,int(outcome.get("new_level",int(gear.enhancement_level)-int(outcome.get("levels",1)))))
    elif kind=="destroy":
        gear.destroyed=true;candidate.inventory[gear.definition_id]-=1
        for slot in candidate.equipment_slots.keys():
            if candidate.equipment_slots[slot]==gear_id:
                candidate.equipment_slots.erase(slot);candidate["equipped" if slot=="weapon" else "armor_equipped"]=""
    elif kind not in ["failure","retain"]:rules.rng.state=before_rng;return error("ENHANCE_OUTCOME_UNKNOWN",gear_id,"result",kind)
    if stage.has("stat_modifier") and not gear.destroyed:
        gear.bonuses={}
        for value in definition.stages:
            if int(value.get("level",0))!=int(gear.enhancement_level):continue
            var stats=value.stat_modifier
            gear.bonuses={"damage":int(stats.get("weapon_damage_bonus",0)),"armor_class":int(stats.get("armor_class_delta",0)),"hp_max":int(stats.get("hp_bonus",0))}
    var result=commit(p,candidate,action_id)
    result["outcome"]=kind;result["rng_state"]=str(rules.rng.state)
    return result

func quest_key(objective: Dictionary) -> String:
    return str(objective.get("id",str(objective.get("type",""))+":"+str(objective.get("target_id",objective.get("monster_id",objective.get("npc_id",objective.get("item_id","")))))))

func requirements_met(p: Dictionary, requirements: Dictionary) -> bool:
    if int(p.level)<int(requirements.get("level_min",requirements.get("level",1))):return false
    if int(p.hp_max)<int(requirements.get("max_hp",requirements.get("hp_min",0))) or int(p.mp_max)<int(requirements.get("max_mp",requirements.get("mp_min",0))):return false
    if requirements.has("advancement_rank") and int(p.rank)!=int(requirements.advancement_rank):return false
    if requirements.has("previous_rank") and int(p.rank)!=int(requirements.previous_rank):return false
    var classes=requirements.get("class_ids",[])
    if not classes.is_empty() and not classes.any(func(id):return rules.runtime_definitions.get(id,{}).get("data",{}).get("name",id)==p.job):return false
    return true

func accept_quest(p: Dictionary, id: String, definition: Dictionary) -> Dictionary:
    var candidate=begin(p)
    for prior in definition.get("prerequisites",[]):
        if prior not in candidate.quests:return error("QUEST_PREREQUISITE",id)
    if not requirements_met(candidate,definition.get("requirements",{})):return error("QUEST_REQUIREMENTS",id)
    var previous=candidate.quest_progress.get(id,{})
    if previous.get("state","")=="ACTIVE":return {"ok":true,"already_active":true}
    var repeat=definition.get("repeat",{})
    if previous.get("state","")=="CLAIMED":
        if not repeat.get("enabled",repeat.get("mode","once")!="once"):return error("QUEST_ALREADY_CLAIMED",id)
        if int(candidate.time_us)/1000<int(previous.get("ready_at_ms",0)):return error("QUEST_REPEAT_COOLDOWN",id)
    var counts={}
    for objective in definition.get("objectives",[]):counts[quest_key(objective)]=0
    candidate.quest_progress[id]={"state":"ACTIVE","round":int(previous.get("round",0))+1,"counts":counts,"accepted_manifest":rules.content_version,
        "definition_snapshot":definition.duplicate(true),"claimed_round":int(previous.get("claimed_round",0))}
    return commit(p,candidate)

func quest_event(p: Dictionary, kind: String, target_id: String, amount: int=1):
    ensure(p)
    for progress in p.quest_progress.values():
        if progress.state!="ACTIVE":continue
        for objective in progress.definition_snapshot.get("objectives",[]):
            if objective.get("type","")==kind and objective.get("target_id",objective.get("monster_id",objective.get("npc_id",objective.get("item_id",""))))==target_id:
                if objective.has("map_id") and objective.map_id!=p.map:continue
                if objective.get("after_other_objectives",false):
                    var ready=true
                    for prior in progress.definition_snapshot.objectives:
                        if prior==objective:break
                        var quantity=int(p.inventory.get(prior.get("item_id",""),0)) if prior.type=="collect" else int(progress.counts.get(quest_key(prior),0))
                        if quantity<int(prior.get("count",prior.get("quantity",1))):ready=false
                    if not ready:continue
                var key=quest_key(objective)
                progress.counts[key]=mini(int(objective.get("count",objective.get("quantity",1))),int(progress.counts.get(key,0))+amount)

func claim_quest(p: Dictionary, id: String) -> Dictionary:
    var candidate=begin(p)
    var progress=candidate.quest_progress.get(id,{})
    if progress.get("state","")!="ACTIVE" or int(progress.get("claimed_round",0))==int(progress.get("round",0)):return error("QUEST_NOT_CLAIMABLE",id)
    var definition=progress.definition_snapshot
    for objective in definition.get("objectives",[]):
        var count=int(candidate.inventory.get(objective.get("item_id",objective.get("target_id","")),0)) if objective.type=="collect" else int(progress.counts.get(quest_key(objective),0))
        if count<int(objective.get("count",objective.get("quantity",1))):return error("QUEST_OBJECTIVE",id)
    var deltas={}
    for item in definition.get("consume",[]):deltas[item.item_id]=int(deltas.get(item.item_id,0))-int(item.quantity)
    var rewards=definition.get("rewards",{})
    var advancement_ids=[]
    if typeof(rewards)==TYPE_ARRAY:
        var converted={"items":[],"gold":0,"experience":0}
        for reward in rewards:
            if reward.type=="item":converted.items.append(reward)
            elif reward.type in ["gold","experience"]:converted[reward.type]+=int(reward.amount)
            elif reward.type=="advancement":advancement_ids.append(reward.advancement_id)
            else:return error("QUEST_REWARD_UNKNOWN",id,"rewards.type",reward.type)
        rewards=converted
    for item in rewards.get("items",[]):deltas[item.item_id]=int(deltas.get(item.item_id,0))+int(item.quantity)
    if not inventory_change(candidate,deltas):return error("QUEST_REWARD_OR_CONSUME_CAPACITY",id)
    candidate.gold+=int(rewards.get("gold",0))
    var xp=int(rewards.get("experience",0))
    if xp<0:return error("QUEST_NEGATIVE_XP",id)
    var before_rng=rules.rng.state
    rules.award_xp(candidate,xp)
    progress.state="CLAIMED";progress.claimed_round=progress.round
    progress.ready_at_ms=int(candidate.time_us)/1000+int(definition.get("repeat",{}).get("cooldown_ms",0))
    if id not in candidate.quests:candidate.quests.append(id)
    for advancement_id in advancement_ids:
        var advancement=rules.runtime_definitions.get(advancement_id,{}).get("data",{})
        var advanced=advance(candidate,advancement_id,advancement)
        if not advanced.ok:rules.rng.state=before_rng;return advanced
    var result=commit(p,candidate,"quest:"+id+":"+str(progress.round))
    if not result.ok:rules.rng.state=before_rng
    return result

func advance(p: Dictionary, id: String, definition: Dictionary, action_id: String="") -> Dictionary:
    var candidate=begin(p,action_id)
    if candidate.is_empty():return {"ok":true,"already_applied":true}
    var rank=int(definition.get("rank",0));var conditions=definition.get("conditions",{})
    if rank!=int(candidate.rank)+1:return error("ADVANCEMENT_SEQUENCE",id)
    var job=definition.get("job",rules.runtime_definitions.get(definition.get("class_id",""),{}).get("data",{}).get("name",candidate.job))
    if candidate.job!=job or not requirements_met(candidate,conditions):return error("ADVANCEMENT_STATS",id)
    var quest=definition.get("quest_id","")
    if quest!="" and quest not in candidate.quests:return error("ADVANCEMENT_QUEST",id)
    var costs=conditions.get("consume",[]);var deltas={}
    for item in costs:deltas[item.item_id]=-int(item.quantity)
    var gold=int(conditions.get("gold_cost",0))
    if gold<0 or candidate.gold<gold or not inventory_change(candidate,deltas):return error("ADVANCEMENT_COST",id)
    candidate.gold-=gold;candidate.rank=rank;candidate.rank_name=definition.get("name",id)
    for skill_id in definition.get("granted_skill_ids",[]):
        if skill_id not in candidate.skills:candidate.skills.append(skill_id)
    return commit(p,candidate,action_id)

func learn_skill(p: Dictionary, id: String, definition: Dictionary) -> Dictionary:
    var candidate=begin(p)
    var learn=definition.get("learn",{})
    if id in candidate.skills:return {"ok":true,"already_applied":true}
    var needs={"level":learn.get("level",1),"class_ids":definition.get("class_ids",[])}
    if not requirements_met(candidate,needs) or int(candidate.rank)<int(learn.get("rank",0)):return error("LEARN_CONDITION",id)
    var gold=int(learn.get("money",learn.get("gold",0)));var xp=int(learn.get("experience_cost",0))
    var deltas={}
    for item in learn.get("consume",[]):deltas[item.item_id]=int(deltas.get(item.item_id,0))-int(item.quantity)
    if gold<0 or xp<0 or candidate.gold<gold or int(candidate.xp2)<xp*2 or not inventory_change(candidate,deltas):return error("LEARN_COST",id)
    candidate.gold-=gold;candidate.xp2-=xp*2;candidate.skills.append(id)
    for i in range(candidate.hotbar.size()):
        if candidate.hotbar[i]=="":candidate.hotbar[i]=id;break
    return commit(p,candidate)

func experience_exchange(p: Dictionary, definition: Dictionary, option_index: int) -> Dictionary:
    var candidate=begin(p);var exchange=definition.get("experience_exchange",{})
    var options=exchange.get("options",[])
    if candidate.level<int(exchange.get("level_required",99)) or option_index<0 or option_index>=options.size():return error("EXPERIENCE_EXCHANGE_CONDITION")
    var option=options[option_index];var field={"max_hp":"hp_max","max_mp":"mp_max"}.get(option.stat,"")
    var cost=int(exchange.get("cost_xp",0));var amount=int(option.amount)
    if field=="" or amount<=0 or cost<=0 or int(candidate.xp2)<cost*2 or int(candidate[field])+amount>int(exchange.get("max_stat_cap",2000000)):return error("EXPERIENCE_EXCHANGE_COST_OR_CAP")
    # Total XP never drops below the level-99 start threshold. Exchange uses
    # surplus XP so a later reload cannot produce a level/XP contradiction.
    var last=rules.threshold(candidate.job,98)
    if int(candidate.xp2)-cost*2<maxi(0,last)*2:return error("EXPERIENCE_EXCHANGE_SURPLUS")
    candidate.xp2-=cost*2;candidate[field]+=amount
    return commit(p,candidate)

func recipe(p: Dictionary, definition: Dictionary) -> Dictionary:
    var candidate=begin(p);var deltas={};var cost=int(definition.get("gold_cost",0))
    for item in definition.get("consume",[]):deltas[item.item_id]=int(deltas.get(item.item_id,0))-int(item.quantity)
    if cost<0 or candidate.gold<cost or not inventory_change(candidate,deltas):return error("RECIPE_INGREDIENTS")
    var ratio=definition.get("success_ratio",{})
    if not Precision.valid_ratio(ratio):return error("RECIPE_PROBABILITY")
    var rng_before=rules.rng.state;var success=Precision.roll(rules.rng,ratio)
    if success:
        deltas={}
        for output in definition.get("outputs",[]):deltas[output.item_id]=int(deltas.get(output.item_id,0))+int(output.quantity)
        if not inventory_change(candidate,deltas):rules.rng.state=rng_before;return error("RECIPE_OUTPUT_CAPACITY")
        for output in definition.get("outputs",[]):
            if not output.has("item_instance_modifier"):continue
            if not candidate.get("item_modifiers",{}).has(output.item_id):candidate.item_modifiers[output.item_id]=[]
            for i in range(int(output.quantity)):candidate.item_modifiers[output.item_id].append(output.item_instance_modifier.duplicate(true))
    candidate.gold-=cost
    var result=commit(p,candidate);result.success=success;return result

func legacy_quest(p: Dictionary, definition: Dictionary) -> Dictionary:
    if definition.id in p.quests or int(p.kills)<int(definition.kills):return error("QUEST_NOT_CLAIMABLE",definition.id)
    var candidate=begin(p)
    var before_rng=rules.rng.state
    var levels=rules.award_xp(candidate,float(definition.xp))
    candidate.gold+=int(definition.gold);candidate.quests.append(definition.id)
    var result=commit(p,candidate,"legacy-quest:"+definition.id)
    if not result.ok:rules.rng.state=before_rng
    result["levels"]=levels
    return result
