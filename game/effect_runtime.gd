extends RefCounted
## Declarative effects; unknown effects fail before resource payment.
const TYPES=["damage","heal","heal_hp","restore_mp","heal_mp","status","remove_status","revive","teleport","transform","shield","inspect_item","local_message"]

static func compile_skill(definition: Dictionary) -> Array:
    var result=[]
    for original in definition.get("effects",[]):
        var effect=original.duplicate(true)
        effect.type=effect.get("op",effect.get("type",""))
        effect.target="enemy" if definition.get("target","self")=="enemy" else "self"
        if effect.type=="apply_status":
            effect.type="status";effect.status_id=effect.status;effect.duration_ms=definition.get("duration_ms",0)
            effect.amount=int(effect.get("magnitude",0));effect.modifiers={}
            var amount=int(effect.amount)
            match effect.status:
                "armor":effect.modifiers.armor_class=-amount
                "armor_debuff":effect.modifiers.armor_class=amount
                "strength":effect.modifiers.strength=amount
                "attack_multiplier":effect.modifiers.attack_multiplier=amount
                "damage_reduction":effect.modifiers.damage_reduction=amount
                "invisibility":effect.modifiers.hidden=1
                "stun","paralyze":effect.modifiers.stun=1
                # Authored extension has magnitude 25 with no percentage unit.
                # Reuse the existing additive damage modifier explicitly.
                "weaken":effect.modifiers.damage=-amount
                "blind":effect.modifiers.blind=amount
                "confuse":effect.modifiers.confuse=1
                "poison":effect.tick_ms=1000
                "transform":effect.visual={"replacement_actor":"rabbit" if definition.get("name","")=="금수" else "innkeeper"}
                "light":effect.modifiers.light=amount
                _:effect.type="UNKNOWN_STATUS:"+str(effect.status)
        elif effect.type=="remove_status":effect.status_id=effect.get("status","")
        if effect.type in ["heal_hp","restore_mp"] and not effect.has("amount"):effect.amount=0
        result.append(effect)
    return result

static func validate(effects: Array) -> Dictionary:
    for effect in effects:
        var type=effect.get("type","")
        if type not in TYPES:return {"ok":false,"error":"UNKNOWN_EFFECT","field":"effects.type","value":type}
        if type in ["damage","heal","heal_hp","restore_mp","heal_mp"] and not effect.has("amount"):
            return {"ok":false,"error":"EFFECT_AMOUNT_MISSING","field":"effects.amount"}
        if type in ["status","transform","shield"] and not effect.has("duration_ms"):
            return {"ok":false,"error":"EFFECT_DURATION_MISSING","field":"effects.duration_ms"}
    return {"ok":true}

static func apply(actions, player: Dictionary, targets: Array, effects: Array) -> Dictionary:
    var check=validate(effects)
    if not check.ok:return check
    var candidate=player.duplicate(true)
    actions.ensure(candidate)
    var clones=targets.map(func(t):return t.duplicate(true))
    var damage_events=[];var movement=[]
    for effect in effects:
        var type=effect.type
        var recipients=[candidate] if effect.get("target","self")=="self" else clones
        if recipients.is_empty():return {"ok":false,"error":"EFFECT_TARGET_MISSING"}
        for recipient in recipients:
            if type=="damage":
                var amount=int(effect.amount)
                if effect.get("scale","flat")=="flat_plus_current_hp_fraction":
                    var ratio=effect.get("hp_fraction",{})
                    amount+=int(candidate.hp)*int(ratio.get("numerator",0))/maxi(1,int(ratio.get("denominator",1)))
                var armor=int(recipient.get("spec",{}).get("values",{}).get("armor_class",0))+actions.status_modifier(recipient,"armor_class")
                amount=actions.rules.damage(amount,armor)
                if amount<0:return {"ok":false,"error":"EFFECT_DAMAGE_RANGE"}
                var dealt=actions.damage(recipient,amount);damage_events.append({"id":recipient.get("id","player"),"damage":dealt})
            elif type in ["heal","heal_hp","restore_mp","heal_mp"]:
                var field="hp_max" if type in ["heal","heal_hp"] else "mp_max"
                var ratio=effect.get("fraction",{})
                var amount=int(effect.get("amount",0))
                if not ratio.is_empty():amount+=int(recipient.get(field,0))*int(ratio.numerator)/int(ratio.denominator)
                actions.recovery(recipient,amount if field=="hp_max" else 0,amount if field=="mp_max" else 0)
            elif type=="revive":
                if recipient.hp>0:return {"ok":false,"error":"REVIVE_REQUIRES_DEAD_TARGET"}
                var hp=effect.get("hp_fraction",{"numerator":1,"denominator":1});var mp=effect.get("mp_fraction",{"numerator":1,"denominator":1})
                recipient.hp=maxi(1,int(recipient.hp_max)*int(hp.numerator)/int(hp.denominator));recipient.mp=int(recipient.mp_max)*int(mp.numerator)/int(mp.denominator)
            elif type=="remove_status":
                recipient.get("statuses",{}).erase(effect.get("status_id",""));recipient.get("buffs",{}).erase(effect.get("status_id",""))
            elif type=="teleport":movement.append({"map":effect.get("map_id",""),"entry":effect.get("entry",[]),"mode":effect.get("mode",""),"requires_ghost":effect.get("requires_ghost",false)})
            elif type in ["inspect_item","local_message"]:movement.append({"mode":type,"channel":effect.get("channel","")})
            else:
                if not recipient.has("statuses"):recipient.statuses={}
                var id=effect.get("status_id",type)
                recipient.statuses[id]={"type":type,"expires_ms":int(candidate.time_us)/1000+int(effect.duration_ms),
                    "amount":effect.get("amount",0),"tick_ms":effect.get("tick_ms",0),"next_tick_ms":int(candidate.time_us)/1000+int(effect.get("tick_ms",0)),
                    "modifiers":effect.get("modifiers",{}),"visual":effect.get("visual",{})}
    actions.commit(player,candidate)
    for index in range(targets.size()):targets[index].clear();targets[index].merge(clones[index],true)
    return {"ok":true,"damage_events":damage_events,"movement":movement}

static func tick(actions, player: Dictionary, delta: float):
    if not player.has("time_us"):actions.ensure(player)
    player.time_us=int(player.time_us)+roundi(delta*1000000)
    tick_at(actions,player,int(player.time_us)/1000)

static func tick_at(actions, player: Dictionary, now: int):
    if not player.has("statuses"):return
    for id in player.statuses.keys():
        var state=player.statuses[id]
        if int(state.expires_ms)<=now:player.statuses.erase(id);continue
        var interval=int(state.get("tick_ms",0))
        if interval<=0:continue
        for iteration in range(64):
            if int(state.next_tick_ms)>now:break
            actions.damage(player,maxi(0,int(state.amount)))
            state.next_tick_ms=int(state.next_tick_ms)+interval
