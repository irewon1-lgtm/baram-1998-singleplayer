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
    return int(rules.value_or(value,"damage_max",0))>0 or value.get("slot","") in ["weapon","body","shield"] or rules.visual_bindings.get(id,{}).get("slot","") in ["weapon","body"]

func ensure(p: Dictionary):
    if not p.has("equipment_instances"):p.equipment_instances={}
    if not p.has("equipment_slots"):p.equipment_slots={}
    if not p.has("next_equipment_serial"):p.next_equipment_serial=1
    if not p.has("committed_actions"):p.committed_actions=[]
    if not p.has("quest_progress"):p.quest_progress={}
    if not p.has("time_us"):p.time_us=0
    if not p.has("statuses"):p.statuses={}
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
    for id in candidate.inventory:
        if int(candidate.inventory[id])<0:return error("NEGATIVE_ITEM",id)
    if action_id!="":
        candidate.committed_actions.append(action_id)
        while candidate.committed_actions.size()>128:candidate.committed_actions.pop_front()
    p.clear();p.merge(candidate,true)
    last_error={}
    return {"ok":true,"error":""}

func begin(p: Dictionary, action_id: String="") -> Dictionary:
    var candidate=p.duplicate(true)
    if candidate.get("core_format",0)!=1:ensure(candidate)
    if action_id!="" and action_id in candidate.committed_actions:return {}
    return candidate

func inventory_change(p: Dictionary, deltas: Dictionary) -> bool:
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
    if gear.destroyed or int(gear.durability)<=0:return error("GEAR_UNUSABLE",gear_id)
    if int(candidate.level)<int(rules.value_or(values,"level_required",0)) or int(candidate.strength)<int(rules.value_or(values,"strength_required",0)):
        return error("EQUIP_REQUIREMENT",gear.definition_id)
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
    candidate["equipped" if slot=="weapon" else "armor_equipped"]=""
    return commit(p,candidate)

func equipped_bonus(p: Dictionary, field: String) -> int:
    var sum=0
    for id in p.get("equipment_slots",{}).values():
        var gear=p.get("equipment_instances",{}).get(id,{})
        if not gear.get("destroyed",true):sum+=int(gear.get("bonuses",{}).get(field,0))
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
    if not inventory_change(candidate,{item_id:-1}):return false
    recovery(candidate,hp,mp)
    return commit(p,candidate).ok

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
    var stage={}
    for value in definition.get("stages",[]):
        if int(value.get("from_level",-1))==int(gear.enhancement_level):stage=value;break
    if stage.is_empty():return error("ENHANCE_STAGE_MISSING",gear_id)
    var before_rng=rules.rng.state
    var draw=Precision.draw(rules.rng,"exclusive",stage.get("outcomes",[]))
    if not draw.ok:return error(draw.error,definition.get("id",""))
    var deltas={}
    for item in stage.get("materials",[]):deltas[item.item_id]=-int(item.quantity)
    var gold=int(stage.get("gold_cost",-1))
    if gold<0 or candidate.gold<gold or not inventory_change(candidate,deltas):
        rules.rng.state=before_rng
        return error("ENHANCE_MATERIAL_OR_GOLD",gear_id)
    candidate.gold-=gold
    var outcome=draw.items[0]
    var kind=outcome.get("result","")
    if kind=="success":
        gear.enhancement_level=int(outcome.get("to_level",int(gear.enhancement_level)+1))
        for field in outcome.get("bonuses",{}):gear.bonuses[field]=int(gear.bonuses.get(field,0))+int(outcome.bonuses[field])
    elif kind=="downgrade":gear.enhancement_level=maxi(0,int(gear.enhancement_level)-int(outcome.get("levels",1)))
    elif kind=="destroy":
        gear.destroyed=true;candidate.inventory[gear.definition_id]-=1
        for slot in candidate.equipment_slots.keys():
            if candidate.equipment_slots[slot]==gear_id:
                candidate.equipment_slots.erase(slot);candidate["equipped" if slot=="weapon" else "armor_equipped"]=""
    elif kind!="failure":rules.rng.state=before_rng;return error("ENHANCE_OUTCOME_UNKNOWN",gear_id,"result",kind)
    var result=commit(p,candidate,action_id)
    result["outcome"]=kind;result["rng_state"]=str(rules.rng.state)
    return result

func quest_key(objective: Dictionary) -> String:
    return str(objective.get("id",str(objective.get("type",""))+":"+str(objective.get("target_id",objective.get("item_id","")))))

func accept_quest(p: Dictionary, id: String, definition: Dictionary) -> Dictionary:
    var candidate=begin(p)
    for prior in definition.get("prerequisites",[]):
        if prior not in candidate.quests:return error("QUEST_PREREQUISITE",id)
    if candidate.level<int(definition.get("requirements",{}).get("level_min",1)):return error("QUEST_LEVEL",id)
    var previous=candidate.quest_progress.get(id,{})
    if previous.get("state","")=="ACTIVE":return {"ok":true,"already_active":true}
    var repeat=definition.get("repeat",{})
    if previous.get("state","")=="CLAIMED":
        if not repeat.get("enabled",false):return error("QUEST_ALREADY_CLAIMED",id)
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
            if objective.get("type","")==kind and objective.get("target_id",objective.get("item_id",""))==target_id:
                var key=quest_key(objective)
                progress.counts[key]=mini(int(objective.get("quantity",1)),int(progress.counts.get(key,0))+amount)

func claim_quest(p: Dictionary, id: String) -> Dictionary:
    var candidate=begin(p)
    var progress=candidate.quest_progress.get(id,{})
    if progress.get("state","")!="ACTIVE" or int(progress.get("claimed_round",0))==int(progress.get("round",0)):return error("QUEST_NOT_CLAIMABLE",id)
    var definition=progress.definition_snapshot
    for objective in definition.get("objectives",[]):
        var count=int(candidate.inventory.get(objective.get("item_id",objective.get("target_id","")),0)) if objective.type=="collect" else int(progress.counts.get(quest_key(objective),0))
        if count<int(objective.get("quantity",1)):return error("QUEST_OBJECTIVE",id)
    var deltas={}
    for item in definition.get("consume",[]):deltas[item.item_id]=int(deltas.get(item.item_id,0))-int(item.quantity)
    var rewards=definition.get("rewards",{})
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
    var result=commit(p,candidate,"quest:"+id+":"+str(progress.round))
    if not result.ok:rules.rng.state=before_rng
    return result

func advance(p: Dictionary, id: String, definition: Dictionary, action_id: String="") -> Dictionary:
    var candidate=begin(p,action_id)
    if candidate.is_empty():return {"ok":true,"already_applied":true}
    var rank=int(definition.get("rank",0));var conditions=definition.get("conditions",{})
    if rank!=int(candidate.rank)+1:return error("ADVANCEMENT_SEQUENCE",id)
    if candidate.job!=definition.get("job",candidate.job) or candidate.level<int(conditions.get("level_min",99)) or candidate.hp_max<int(conditions.get("hp_min",0)) or candidate.mp_max<int(conditions.get("mp_min",0)):return error("ADVANCEMENT_STATS",id)
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
