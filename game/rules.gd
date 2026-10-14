extends RefCounted
## Same rules object is called by the interactive game and the balance runner.
## Known numeric facts remain unchanged; fallbacks are explicitly estimated.

const JOBS = ["전사", "도적", "주술사", "도사"]
var contents = []
var drops = []
var rng = RandomNumberGenerator.new()
var by_id = {}
var grow = {}
var visual_bindings = {}
var skill_effects = {}

func _init():
    visual_bindings=JSON.parse_string(FileAccess.get_file_as_string("res://data/runtime_bindings.json")).equipment
    skill_effects=JSON.parse_string(FileAccess.get_file_as_string("res://data/skill_effects.json"))
    var data = JSON.parse_string(FileAccess.get_file_as_string("res://data/numeric.json"))
    contents = data.contents
    drops = data.drops
    rng.seed = 19982001
    for c in contents:
        by_id[c.id] = c
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

func find_content(category: String, title: String, job: String = "") -> Dictionary:
    for c in contents:
        if c.category == category and c.name == title and (job == "" or str(c.job) == job):
            return c
    return {}

func item(title: String) -> Dictionary:
    return find_content("item", title).get("values", {})

func growth(job: String, level: int) -> Dictionary:
    return grow.get(job + ":" + str(level), {}).get("values", {})

func value_or(values: Dictionary, key: String, fallback):
    var v = values.get(key)
    return fallback if v == null else v

func new_player(job: String, title: String) -> Dictionary:
    return {"name":title,"job":job,"level":1,"xp2":0,"hp":50,"hp_max":50,"mp":35,"mp_max":35,
        "gold":30,"strength":5,"inventory":{"목도":1},"equipped":"","durability":{"목도":1000},
        "skills":["기초 회복","비영사천문","성황령","물품감정"],"hotbar":["기초 회복","비영사천문","물품감정"],"cooldowns":{},"buffs":{},
        "map":"village","x":12,"y":12,"direction":2,"kills":0,"quests":[],"rank":0,
        "growth_log":[],"skill_page":0,"rng_state":str(rng.state)}

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
        var used_job = "평민" if int(p.level) < 5 else p.job
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

func weapon_damage(p: Dictionary) -> int:
    var it = item(p.equipped)
    var low = int(value_or(it,"damage_min",2))
    var high = int(value_or(it,"damage_max",4))
    var bonus=(5 if p.buffs.get("누리의힘",0)>0 else 0)+(10 if p.buffs.get("대지의힘",0)>0 else 0)
    return (rng.randi_range(low,high)+bonus)*(2 if p.buffs.get("이중공격",0)>0 else 1)

func incoming_damage(p: Dictionary,raw: float) -> int:
    var amount=damage(raw,armor(p))
    if p.buffs.get("보호",0)>0:amount=maxi(1,floori(amount*0.5))
    if p.buffs.get("차폐",0)>0:amount=maxi(1,floori(amount*0.75))
    return amount

func skill_profile(p: Dictionary,title: String) -> Dictionary:
    if title=="기초 회복":return {"type":"heal","effect":"heal","classification":"GENERATED_TRAINING"}
    var profile=skill_effects.get(p.job+":"+title,skill_effects.get("공통:"+title,skill_effects.get("전직업 공통:"+title,{})))
    if not profile.is_empty():return profile
    var s=skill(p,title)
    if float(value_or(s,"base_damage",0))>0:return {"type":"damage","effect":"fire" if "화" in title else "lightning" if "뢰" in title else "damage","classification":"SOURCE_NUMERIC_UPPER_SKILL_REPLACEMENT_VISUAL_NOT_PLAYTHROUGH_VERIFIED"}
    if float(value_or(s,"heal_amount",0))>0:return {"type":"heal","effect":"heal","classification":"SOURCE_NUMERIC_UPPER_SKILL_REPLACEMENT_VISUAL_NOT_PLAYTHROUGH_VERIFIED"}
    return {"type":"unresolved","effect":"buff"}

func armor(p: Dictionary) -> int:
    var base = int(value_or(growth(p.job,int(p.level)),"base_armor_class",100-int(p.level)))
    return base + int(value_or(item(p.equipped),"armor_class",0)) + int(value_or(item(p.get("armor_equipped","")),"armor_class",0)) - (10 if p.buffs.get("무장",0) > 0 else 0)

func equip(p: Dictionary, title: String) -> bool:
    var it = item(title)
    if it.is_empty() or int(p.inventory.get(title,0)) <= 0 or int(p.strength) < int(value_or(it,"strength_required",0)) or int(p.level) < int(value_or(it,"level_required",0)):
        return false
    if int(value_or(it,"damage_max",0)) <= 0:
        if visual_bindings.get(title,{}).get("slot","")!="body":return false
        p.armor_equipped=title
        return true
    p.equipped = title
    p.durability[title] = p.durability.get(title,int(value_or(it,"durability",1000)))
    return true

func cast_resources(p: Dictionary, mp: int, hp: int, cooldown: float, key: String) -> bool:
    if int(p.mp) < mp or int(p.hp) <= hp or float(p.cooldowns.get(key,0)) > 0:
        return false
    p.mp -= mp
    p.hp -= hp
    p.cooldowns[key] = cooldown
    return true

func heal(p: Dictionary, amount: int):
    p.hp = mini(int(p.hp_max),int(p.hp)+amount)

func skill(p: Dictionary, title: String) -> Dictionary:
    if title == "기초 회복":
        return {"cast_mp":5,"cast_hp":0,"cooldown_ms":1000,"heal_amount":10,"base_damage":0,
                "range_tiles":1,"duration_ms":0,"source_kind":"GENERATED_TRAINING_SKILL_DEV_ESTIMATE"}
    var found=find_content("spell",title,p.job)
    if found.is_empty() and title in ["비영사천문","성황령","물품감정"]:found=find_content("spell",title)
    return found.get("values",{})

func learn(p: Dictionary, title: String) -> bool:
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
    return rng.randf() < probability

func alternate(group: Array, probability: float) -> Array:
    return [group[rng.randi_range(0,group.size()-1)]] if roll(probability) else []

func add_item(p: Dictionary, title: String, quantity: int = 1) -> bool:
    var limit = int(value_or(item(title),"stack_limit",99))
    if quantity<=0 or limit<=0:return false
    if limit==1 and int(p.inventory.get(title,0))+quantity>1:return false
    var slots=0
    for name in p.inventory:
        var count=int(p.inventory[name])+(quantity if name==title else 0)
        slots+=ceili(float(count)/maxi(1,int(value_or(item(name),"stack_limit",99))))
    if not p.inventory.has(title):slots+=ceili(float(quantity)/limit)
    if slots>52:return false # authored capacity; original per-stack limits unchanged
    p.inventory[title] = int(p.inventory.get(title,0)) + quantity
    return true

func trade(p: Dictionary, title: String, quantity: int, price: int, buy: bool) -> bool:
    if quantity <= 0 or price < 0:
        return false
    if buy:
        if int(p.gold) < price*quantity or not add_item(p,title,quantity):
            return false
        p.gold -= price*quantity
    else:
        if int(p.inventory.get(title,0)) < quantity or p.equipped == title or p.get("armor_equipped","")==title:
            return false
        p.inventory[title] -= quantity
        p.gold += price*quantity
    return true

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
    p.gold -= cost
    p.durability[title] = int(it.durability)
    return true

func craft(p: Dictionary, ingredients: Dictionary, gold: int, product: String) -> bool:
    if int(p.gold) < gold:
        return false
    for k in ingredients:
        if int(p.inventory.get(k,0)) < int(ingredients[k]):
            return false
    if not add_item(p,product):
        return false
    p.gold -= gold
    for k in ingredients:
        p.inventory[k] -= ingredients[k]
    return true

func consume(p: Dictionary, title: String) -> bool:
    var it = item(title)
    if int(p.inventory.get(title,0)) <= 0 or (int(value_or(it,"heal_amount",0)) <= 0 and int(value_or(it,"restore_mp",0)) <= 0):
        return false
    p.inventory[title] -= 1
    heal(p,int(value_or(it,"heal_amount",0)))
    p.mp = mini(int(p.mp_max),int(p.mp)+int(value_or(it,"restore_mp",0)))
    return true

func monster(kind: String, aliases: Dictionary) -> Dictionary:
    var name = {"rabbit":"토끼","squirrel":"다람쥐"}.get(kind,aliases.get(kind,"서생원"))
    var c = find_content("monster",name)
    return {"name":name,"content_id":c.id,"values":c.values,
            "binding":"ORIGINAL_REFERENCE" if kind in ["rabbit","squirrel"] else "REPLACEMENT_SPRITE"}

func monster_drops(p: Dictionary, monster_id: String) -> Array:
    var result = []
    for d in drops:
        if d.monster_content_id == monster_id and d.probability != null and roll(float(d.probability)):
            result.append({"item":d.item_name,"quantity":int(d.quantity)})
    return result

func reward_kill(p: Dictionary, spec: Dictionary, kind: String) -> Dictionary:
    p.kills += 1
    var gains = award_xp(p,float(spec.values.experience))
    var dropped = monster_drops(p,spec.content_id)
    var gold = 1 if kind in ["rabbit","squirrel"] else 20 # explicit DEV estimate
    p.gold += gold
    return {"levels":gains,"drops":dropped,"gold":gold}

func tick(p: Dictionary, delta: float):
    for k in p.cooldowns:
        p.cooldowns[k] = maxf(0,float(p.cooldowns[k])-delta)
    for k in p.buffs:
        p.buffs[k] = maxf(0,float(p.buffs[k])-delta)
