extends RefCounted
## Same rules object is called by the interactive game and the balance runner.
## Known numeric facts remain unchanged; fallbacks are explicitly estimated.

const JOBS = ["전사", "도적", "주술사", "도사"]
const Core = preload("res://core_actions.gd")
const Precision = preload("res://precision.gd")
var contents = []
var drops = []
var rng = RandomNumberGenerator.new()
var by_id = {}
var grow = {}
var visual_bindings = {}
var skill_effects = {}
var content_version = "legacy-base"
var actions
var runtime_definitions = {}
var name_index = {}
var legacy_aliases = {}

func _init():
    visual_bindings=JSON.parse_string(FileAccess.get_file_as_string("res://data/runtime_bindings.json")).equipment
    skill_effects=JSON.parse_string(FileAccess.get_file_as_string("res://data/skill_effects.json"))
    var data = JSON.parse_string(FileAccess.get_file_as_string("res://data/numeric.json"))
    contents = data.contents
    drops = data.drops
    rng.seed = 19982001
    for c in contents:
        by_id[c.id] = c
        if not legacy_aliases.has(c.category+":"+c.name):legacy_aliases[c.category+":"+c.name]=c.id
        if c.category == "growth":
            grow[str(c.job) + ":" + str(int(c.level))] = c
    for entry in [
        {"name":"구운토끼고기","values":{"heal_amount":30,"restore_mp":0,"stack_limit":99,"vendor_buy_price":5,"vendor_sell_price":2}},
        {"name":"초보 회복약","values":{"heal_amount":50,"restore_mp":0,"stack_limit":99,"vendor_buy_price":10,"vendor_sell_price":5}},
        {"name":"초보 마력약","values":{"heal_amount":0,"restore_mp":30,"stack_limit":99,"vendor_buy_price":10,"vendor_sell_price":5}}]:
        entry["id"] = "generated.item." + entry.name
        entry["category"] = "item"
        entry["job"] = null
        entry["source_kind"] = "GENERATED_COMPLETION_DEV_ESTIMATE"
        contents.append(entry)
        by_id[entry.id]=entry
    rebuild_indexes()
    actions=Core.new(self)

func rebuild_indexes():
    name_index.clear()
    for c in contents:
        var key=c.category+":"+c.name
        if not name_index.has(key):name_index[key]=[]
        name_index[key].append(c)

func find_content(category: String, title: String, job: String = "") -> Dictionary:
    if by_id.has(title) and by_id[title].category==category:return by_id[title]
    for c in name_index.get(category+":"+title,[]):
        if job == "" or str(c.job) == job:
            return c
        if category=="spell":
            var data=runtime_definitions.get(c.id,{}).get("data",{})
            if data.get("class_ids",[]).any(func(id):return runtime_definitions.get(id,{}).get("data",{}).get("name","")==job):return c
    var id=legacy_aliases.get(category+":"+title,"")
    if id!="" and by_id.has(id):return by_id[id]
    return {}

func display_name(id: String) -> String:
    if by_id.has(id):return by_id[id].name
    if runtime_definitions.has(id):return runtime_definitions[id].data.get("name",id)
    return id

func item(title: String) -> Dictionary:
    return find_content("item", title).get("values", {})

func growth(job: String, level: int) -> Dictionary:
    return grow.get(job + ":" + str(level), {}).get("values", {})

func value_or(values: Dictionary, key: String, fallback):
    var v = values.get(key)
    return fallback if v == null else v

func new_player(job: String, title: String) -> Dictionary:
    var result={"name":title,"job":job,"level":1,"xp2":0,"hp":50,"hp_max":50,"mp":35,"mp_max":35,
        "gold":30,"strength":5,"inventory":{"목도":1},"equipped":"","durability":{"목도":1000},
        "skills":[],"hotbar":["","",""],"cooldowns":{},"buffs":{},
        "map":"village","x":12,"y":12,"direction":2,"kills":0,"quests":[],"rank":0,
        "growth_log":[],"skill_page":0,"rng_state":str(rng.state)}
    actions.ensure(result)
    equip(result,"목도")
    return result

func threshold(job: String, level: int) -> int:
    if level >= 99:
        return -1
    return int(value_or(growth(job,level), "cumulative_exp_to_next", -1))

func award_xp(p: Dictionary, amount: float) -> Array:
    p.xp2 += roundi(amount * 2.0) # preserves 7.5 exactly; display divides by two.
    var gained = []
    while int(p.level) < 99:
        var limit = threshold(p.job, int(p.level))
        if limit < 0 or int(p.xp2) < limit * 2:
            break
        var used_job = "평민" if int(p.level) < (6 if runtime_definitions.has("wk.class.novice") else 5) else p.job
        var g = growth(used_job,int(p.level))
        var hp_gain = rng.randi_range(int(g.hp_gain_min),int(g.hp_gain_max_inclusive))
        var mp_gain = rng.randi_range(int(g.mp_gain_min),int(g.mp_gain_max_inclusive))
        p.growth_log.append({"from":p.level,"job":used_job,"hp_gain":hp_gain,"mp_gain":mp_gain})
        p.level += 1
        p.hp_max += hp_gain
        p.mp_max += mp_gain
        p.hp = p.hp_max
        p.mp = p.mp_max
        p.strength = 5 + int(p.level) - 1 # DEV_ESTIMATE, original strength growth unavailable.
        gained.append(p.level)
    p.rng_state = str(rng.state)
    return gained

func integer_learn(average: float) -> int:
    return ceili(average)

func integer_armor(average: float) -> int:
    return floori(average)

func damage(raw: float, armor: int) -> int:
    # Explicit NA replacement formula, floor only after multiplication.
    return maxi(1, floori(raw * float(100 + maxi(-95, armor)) / 100.0))

func combat_stats(p: Dictionary) -> Dictionary:
    var it=item(p.equipped)
    var low=int(value_or(it,"damage_min",2));var high=int(value_or(it,"damage_max",4))
    var bonus=(5 if p.buffs.get("누리의힘",0)>0 else 0)+(10 if p.buffs.get("대지의힘",0)>0 else 0)
    bonus+=actions.equipped_bonus(p,"damage")+actions.status_modifier(p,"damage")+actions.status_modifier(p,"strength")
    var multiplier=maxi(1,actions.status_modifier(p,"attack_multiplier"))*(2 if p.buffs.get("이중공격",0)>0 else 1)
    return {"minimum":(low+bonus)*multiplier,"maximum":(high+bonus)*multiplier,"raw_min":low,"raw_max":high,"bonus":bonus,"multiplier":multiplier}

func weapon_damage(p: Dictionary) -> int:
    var stats=combat_stats(p)
    return (rng.randi_range(stats.raw_min,stats.raw_max)+stats.bonus)*stats.multiplier

func incoming_damage(p: Dictionary,raw: float) -> int:
    var amount=damage(raw,armor(p))
    if p.buffs.get("보호",0)>0:amount=maxi(1,floori(amount*0.5))
    if p.buffs.get("차폐",0)>0:amount=maxi(1,floori(amount*0.75))
    amount=maxi(1,amount*(100-clampi(actions.status_modifier(p,"damage_reduction"),0,100))/100)
    return amount

func skill_profile(p: Dictionary,title: String) -> Dictionary:
    var record=find_content("spell",title,p.job)
    var id=record.get("id",title)
    if runtime_definitions.has(id) and runtime_definitions[id].kind=="skill":
        var definition=runtime_definitions[id].data
        return {"type":"work_effects","effect":"","effects":preload("res://effect_runtime.gd").compile_skill(definition),"classification":runtime_definitions[id].source_mode,"definition_id":id,"definition":definition}
    if title=="기초 회복":return {"type":"heal","effect":"heal","classification":"GENERATED_TRAINING"}
    var profile=skill_effects.get(p.job+":"+title,skill_effects.get("공통:"+title,skill_effects.get("전직업 공통:"+title,{})))
    if not profile.is_empty():return profile
    var s=skill(p,title)
    if float(value_or(s,"base_damage",0))>0:return {"type":"damage","effect":"fire" if "화" in title else "lightning" if "뢰" in title else "damage","classification":"SOURCE_NUMERIC_UPPER_SKILL_REPLACEMENT_VISUAL_NOT_PLAYTHROUGH_VERIFIED"}
    if float(value_or(s,"heal_amount",0))>0:return {"type":"heal","effect":"heal","classification":"SOURCE_NUMERIC_UPPER_SKILL_REPLACEMENT_VISUAL_NOT_PLAYTHROUGH_VERIFIED"}
    return {"type":"unresolved","effect":"buff"}

func armor(p: Dictionary) -> int:
    var base = int(value_or(growth(p.job,int(p.level)),"base_armor_class",100-int(p.level)))
    return base + int(value_or(item(p.equipped),"armor_class",0)) + int(value_or(item(p.get("armor_equipped","")),"armor_class",0)) + actions.equipped_bonus(p,"armor_class") + actions.status_modifier(p,"armor_class") - (10 if p.buffs.get("무장",0) > 0 else 0)

func equip(p: Dictionary, title: String) -> bool:
    actions.ensure(p)
    if p.equipment_instances.has(title):return actions.equip_instance(p,title).ok
    if runtime_definitions.has("wk.class.novice"):title=find_content("item",title).get("id",title)
    var choices=actions.instances(p,title)
    return not choices.is_empty() and actions.equip_instance(p,choices[0]).ok

func cast_resources(p: Dictionary, mp: int, hp: int, cooldown: float, key: String) -> bool:
    return actions.cast_cost(p,mp,hp,Precision.half_away(cooldown*1000),key)

func heal(p: Dictionary, amount: int):
    actions.recovery(p,amount,0)

func skill(p: Dictionary, title: String) -> Dictionary:
    if title == "기초 회복":
        return {"cast_mp":5,"cast_hp":0,"cooldown_ms":1000,"heal_amount":10,"base_damage":0,
                "range_tiles":1,"duration_ms":0,"source_kind":"GENERATED_TRAINING_SKILL_DEV_ESTIMATE"}
    var found=find_content("spell",title,p.job)
    if found.is_empty() and title in ["비영사천문","성황령","물품감정"]:found=find_content("spell",title)
    return found.get("values",{})

func learn(p: Dictionary, title: String) -> bool:
    var definition=find_content("spell",title,p.job)
    if runtime_definitions.has(definition.get("id","")):
        return actions.learn_skill(p,definition.id,runtime_definitions[definition.id].data).ok
    var s = skill(p,title)
    if s.is_empty() or title in p.skills or int(p.level) < integer_learn(float(value_or(s,"learn_level",1))) or int(p.gold) < int(value_or(s,"learn_money",0)):
        return false
    for key in s:
        if key.begins_with("learn_materials."):
            var material = key.trim_prefix("learn_materials.").trim_suffix(".quantity")
            if int(p.inventory.get(material,0)) < int(s[key]):
                return false
    p.gold -= int(value_or(s,"learn_money",0))
    for key in s:
        if key.begins_with("learn_materials."):
            var material = key.trim_prefix("learn_materials.").trim_suffix(".quantity")
            p.inventory[material] -= int(s[key])
    p.skills.append(title)
    for i in range(3):
        if p.hotbar[i] == "":
            p.hotbar[i] = title
            break
    return true

func roll(probability: float) -> bool:
    var ratio=Precision.decimal_ratio(probability)
    if ratio.is_empty():actions.error("PROBABILITY_NOT_REPRESENTABLE","","probability",probability);return false
    return Precision.roll(rng,ratio)

func alternate(group: Array, probability: float) -> Array:
    return [group[rng.randi_range(0,group.size()-1)]] if roll(probability) else []

func add_item(p: Dictionary, title: String, quantity: int = 1) -> bool:
    return quantity>0 and actions.exchange(p,0,{title:quantity}).ok

func trade(p: Dictionary, title: String, quantity: int, price: int, buy: bool) -> bool:
    if quantity<=0 or price<0:return false
    var flags=item(title).get("flags",{})
    if not flags.get("buyable" if buy else "sellable",true) or (not buy and flags.get("quest_bound",false)):return false
    if not buy and (p.equipped==title or p.get("armor_equipped","")==title):return false
    return actions.exchange(p,(-1 if buy else 1)*price*quantity,{title:(1 if buy else -1)*quantity}).ok

func repair_cost(buy_price: int, maximum: int, current: int, coefficient: float = 0.5) -> int:
    if maximum <= 0:
        return -1
    return ceili(float(buy_price) * coefficient * float(maxi(0,maximum-current)) / maximum)

func repair(p: Dictionary, title: String) -> bool:
    var it = item(title)
    if not p.durability.has(title) or it.get("repair_multiplier") == null:
        return false
    var cost = repair_cost(int(value_or(it,"vendor_buy_price",0)),int(value_or(it,"durability",0)),int(p.durability[title]),float(it.repair_multiplier))
    if cost < 0 or cost > int(p.gold):
        return false
    return actions.repair(p,title,cost,int(it.durability))

func craft(p: Dictionary, ingredients: Dictionary, gold: int, product: String) -> bool:
    var deltas={product:1}
    for k in ingredients:deltas[k]=int(deltas.get(k,0))-int(ingredients[k])
    return gold>=0 and actions.exchange(p,-gold,deltas).ok

func consume(p: Dictionary, title: String) -> bool:
    return actions.consume(p,title)

func monster(kind: String, aliases: Dictionary) -> Dictionary:
    if by_id.has(kind) and by_id[kind].category=="monster":return {"name":by_id[kind].name,"content_id":kind,"values":by_id[kind].values,"binding":"WORK_RUNTIME_ID"}
    var name = {"rabbit":"토끼","squirrel":"다람쥐"}.get(kind,aliases.get(kind,"서생원"))
    var c = find_content("monster",name)
    return {"name":name,"content_id":c.id,"values":c.values,
            "binding":"ORIGINAL_REFERENCE" if kind in ["rabbit","squirrel"] else "REPLACEMENT_SPRITE"}

func monster_drops(p: Dictionary, monster_id: String) -> Array:
    if runtime_definitions.has(monster_id):
        var group_id=runtime_definitions[monster_id].data.get("drop_group_id","")
        if runtime_definitions.has(group_id):
            var group=runtime_definitions[group_id].data
            var picks=Precision.draw(rng,group.mode,group.rolls)
            if not picks.ok:actions.error(picks.error,group_id);return []
            var selected=[]
            for entry in picks.items:
                var quantity=entry.get("quantity",1)
                if typeof(quantity)==TYPE_DICTIONARY:quantity=rng.randi_range(int(quantity.min),int(quantity.max))
                if entry.get("item_id","")!="":selected.append({"item":entry.item_id,"quantity":int(quantity)})
            return selected
    var result = []
    for d in drops:
        if d.monster_content_id == monster_id and d.probability != null and roll(float(d.probability)):
            result.append({"item":d.item_name,"quantity":int(d.quantity)})
    return result

func reward_kill(p: Dictionary, spec: Dictionary, kind: String) -> Dictionary:
    var candidate=p.duplicate(true)
    if candidate.get("core_format",0)!=1:actions.ensure(candidate)
    candidate.kills+=1
    var gains=award_xp(candidate,float(spec.values.experience))
    var dropped=monster_drops(candidate,spec.content_id)
    var gold=int(value_or(spec.values,"gold",1 if kind in ["rabbit","squirrel"] else 20))
    candidate.gold+=gold
    actions.quest_event(candidate,"kill",spec.content_id)
    actions.commit(p,candidate)
    return {"levels":gains,"drops":dropped,"gold":gold}

func tick(p: Dictionary, delta: float):
    for k in p.cooldowns:
        p.cooldowns[k] = maxf(0,float(p.cooldowns[k])-delta)
    for k in p.buffs:
        p.buffs[k] = maxf(0,float(p.buffs[k])-delta)

func skill_id(p: Dictionary,title: String) -> String:
    return str(find_content("spell",title,p.job).get("id",title))

func knows_skill(p: Dictionary,title: String) -> bool:
    if title in p.skills:return true
    var canonical=skill_id(p,title)
    return p.skills.any(func(id):return skill_id(p,str(id))==canonical)
