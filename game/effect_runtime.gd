extends RefCounted
## Declarative effects; unknown effects fail before resource payment.
const TYPES=["damage","heal","heal_hp","restore_mp","heal_mp","status","remove_status","revive","teleport","transform","shield"]

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
                if amount<0:return {"ok":false,"error":"EFFECT_DAMAGE_RANGE"}
                actions.damage(recipient,amount);damage_events.append({"id":recipient.get("id","player"),"damage":amount})
            elif type in ["heal","heal_hp"]:actions.recovery(recipient,int(effect.amount),0)
            elif type in ["restore_mp","heal_mp"]:actions.recovery(recipient,0,int(effect.amount))
            elif type=="revive":recipient.hp=recipient.hp_max;recipient.mp=recipient.mp_max
            elif type=="remove_status":
                recipient.get("statuses",{}).erase(effect.get("status_id",""));recipient.get("buffs",{}).erase(effect.get("status_id",""))
            elif type=="teleport":movement.append({"map":effect.get("map_id",""),"entry":effect.get("entry",[])})
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
    var now=int(player.time_us)/1000
    for id in player.statuses.keys():
        var state=player.statuses[id]
        if int(state.expires_ms)<=now:player.statuses.erase(id);continue
        var interval=int(state.get("tick_ms",0))
        if interval<=0:continue
        for iteration in range(64):
            if int(state.next_tick_ms)>now:break
            actions.damage(player,maxi(0,int(state.amount)))
            state.next_tick_ms=int(state.next_tick_ms)+interval
