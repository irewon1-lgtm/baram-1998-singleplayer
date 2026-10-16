"""Adopt acquired Korean effect fields into the offline executor contract.

Every selected source field receives an explicit disposition. Exact published
numbers are kept where their units are clear; ambiguous formulae and online
target scopes remain recorded. This module does not claim runtime verification.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json


def _clean(value):
    return "".join(str(value or "").split())


def _number(value, default=None):
    if isinstance(value, dict):
        value = value.get("value")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _find_monster(forms, data):
    aliases = {"새끼돼지":"꼬마돼지", "돼지":"꼬마돼지", "여우":"흑여우", "늑대":"운랑"}
    result = []
    for form in forms:
        name = aliases.get(_clean(form), _clean(form))
        matches = [(int(m.get("level", 1)), str(i)) for i,m in data.get("monsters", {}).items() if _clean(m.get("name")) == name]
        if matches:
            chosen = min(matches)[1]
            if chosen not in result:
                result.append(chosen)
    return result


def adopt_skill_effects(skill: dict, effect_rows: list, data: dict) -> dict:
    """Return a new skill; match original parent IDs, never fuzzy skill names.

    The caller passes the acquired effect table. IDs already encode the source
    profile. A duplicate conflicting field is an error, rather than selecting
    whichever source happens to be last. The returned field ledger is evidence
    of compilation, not a completed execution test.
    """
    result = deepcopy(skill)
    matches = [r for r in effect_rows if r.get("parent_content_id") == skill["id"] and r.get("selected_for_build")]
    facts, owners = {}, {}
    for row in matches:
        for field, value in (row.get("selected_original_value") or {}).items():
            if field in facts and facts[field] != value:
                raise ValueError("Conflicting acquired effect field: " + skill["id"] + ":" + field)
            facts[field], owners[field] = deepcopy(value), row
    ledger = {}

    def adopt(field, params=None, reason="Published field applied to the supported offline executor.", disposition="ADOPTED"):
        if params:
            result.update(params)
        row = owners[field]
        ledger[field] = {"source_value":facts[field], "disposition":disposition, "runtime_fields":deepcopy(params or {}),
                         "reason":reason, "source_record_id":row.get("content_id"), "runtime_test":"NOT_RUN_IN_ADOPTION_MODULE"}

    def adapted(field, params=None, reason="Undocumented coefficient or online target adapted to bounded offline behavior."):
        adopt(field, params, reason, "ADAPTED")

    def reference(field, reason):
        adopt(field, None, reason, "REFERENCE_RETAINED")

    # Semantic family must precede numeric/context handling, independent of the
    # source JSON field order. Names are not used to override published effects.
    if facts.get("effect_type.TRANSFORMATION"):
        forms = _find_monster(facts.get("transform.forms", []), data)
        if not forms:
            raise ValueError("No acquired monster form for transformation " + skill["id"])
        result.update(kind="buff", delivery="melee", target="self", range=0, power=0, status="", form_monster_id=forms[0])
        result.pop("monster_id", None)
    if facts.get("effect_type.HP_HEAL"):
        result.update(kind="heal", target="self", range=0)
    if facts.get("effect_type.MP_RESTORE"):
        result.update(kind="restore_mp", target="self", range=0)
    if facts.get("effect_type.SPELL_REFLECTION"):
        result.update(kind="buff", target="self", range=0, status="protection", reflect_fraction=1.0,
                      reflect_probability=0.5, damage_multiplier=1.0)
    if facts.get("effect_type.DAMAGE_IMMUNITY"):
        result.update(kind="buff", target="self", range=0, status="protection", damage_multiplier=0.0, duration=5.0)
    if facts.get("effect_type.EVASION_BUFF"):
        result.update(kind="buff", target="self", range=0, status="", evasion_chance=0.25, move_multiplier=1.0)
    if facts.get("effect_type.INVISIBILITY"):
        result.update(kind="buff", target="self", range=0, status="stealth", move_multiplier=1.0)
    if facts.get("effect_type.DEFENSE_DEBUFF"):
        # A source-described damage attack may additionally lower defense.
        if result.get("kind") != "damage":
            result.update(kind="debuff", target="monster", power=0)
        result.update(on_hit_status="slow", defense_bonus=-max(3,int(result.get("learn_level",1))//6))
    if facts.get("effect_type.BARRIER"):
        result.update(kind="buff", target="self", range=0, status="protection", barrier_radius=1, rooted=True,
                      damage_multiplier=0.85, duration=min(12.0,float(result.get("duration",10))))
    if facts.get("effect_type.ILLUSION_CLONES"):
        result.update(kind="buff", target="self", range=0, status="", attack_multiplier=2.0)
    if facts.get("effect_type.HP_ABSORPTION"):
        result.update(kind="damage", delivery="melee", target="monster", range=1, heal_fraction=0.5)
    if facts.get("effect_type.HIDDEN_DETECTION"):
        result.update(kind="buff", target="self", range=0, status="", reveal_hidden=True, attack_bonus=0)
    if facts.get("effect_type.PLAYER_INSPECTION"):
        result.update(kind="buff", target="self", range=0, status="", inspect_self_fields=facts.get("inspection.fields",["abilities"]), attack_bonus=0)
    if facts.get("effect_type.MONSTER_SUMMON"):
        forms = _find_monster(facts.get("summon.documented_forms",[]),data)
        if forms:
            result.update(kind="summon", monster_id=forms[0], summon_form_options=forms)
    if facts.get("effect_type.STRENGTH_BUFF"):
        result.update(kind="buff", target="self", range=0, attack_bonus=max(3,int(result.get("learn_level",1))//3))
    if facts.get("effect_type.ACCURACY_BUFF"):
        result.update(kind="buff", target="self", range=0, accuracy_bonus=0.15)

    for field, value in facts.items():
        if field == "healing.hp_amount":
            amount = _number(value)
            if amount is not None and value.get("unit") == "HP":
                adopt(field,{"power":int(amount),"kind":"heal"})
            else: reference(field,"Published healing amount has no supported numeric HP unit; reconstructed base amount retained.")
        elif field == "healing.full_mp_restore":
            adopt(field,{"restore_full_mp":bool(value),"kind":"restore_mp"})
        elif field in ("cost.hp","cost.mp"):
            resource = "hp" if field.endswith("hp") else "mp"
            mode = value.get("mode") if isinstance(value,dict) else None
            amount = _number(value)
            if mode == "flat" and amount is not None:
                adopt(field,{resource+"_cost":int(amount)})
            elif mode == "all":
                params={resource+"_cost_all":True}
                if resource=="hp":params["allow_lethal_hp_cost"]=bool(facts.get("consequence.caster_death"))
                adapted(field,params,"All current resource is consumed; current/max basis is unpublished, current resource chosen explicitly.")
            elif resource=="hp" and mode in ("fraction","majority"):
                fraction=amount if amount is not None else 0.6
                adapted(field,{"hp_cost_fraction":fraction},"Published fraction retained when available; unpublished majority=60% and ambiguous basis=current HP, explicitly reconstructed.")
            else: reference(field,"Unquantified source resource cost retained; existing bounded reconstructed cost remains, without inventing source precision.")
        elif field == "consequence.caster_death":
            adopt(field,{"hp_cost_all":True,"allow_lethal_hp_cost":True})
        elif field == "damage.incoming_nullified":
            adopt(field,{"damage_multiplier":0.0})
        elif field == "damage.incoming_multiplier":
            adopt(field,{"damage_multiplier":_number(value,1.0)})
        elif field == "reflection.probability":
            adapted(field,{"reflect_probability":_number(value,0.5),"reflect_fraction":1.0},"Published incoming-spell probability retained. Current offline enemies use melee; reflection applies to hostile hits as the explicit offline adaptation.")
        elif field in ("damage.basic_attack_multiplier","attack.hit_count"):
            multiplier=_number(facts.get("damage.basic_attack_multiplier"),_number(value,1.0))
            adapted(field,{"attack_multiplier":multiplier},"Published hit count/total multiplier represented by equivalent total basic-attack damage; separate hit animations not claimed.")
        elif field == "damage.invisibility_multiplier":
            multiplier=(float(value["lower"])+float(value["upper"]))/2
            adapted(field,{"next_hit_multiplier":multiplier},"Published 7–8 descriptive range represented by midpoint7.5 on next basic attack; exact original formula unknown.")
        elif field == "area.relative_directions":
            params={"directional_pattern":list(value)}
            if result.get("kind")=="damage":params.update(delivery="area",range=max(1,int(result.get("range",1))))
            adopt(field,params)
        elif field == "movement.pull_target_to_caster_front_then_attack":
            adopt(field,{"pull_target":True,"delivery":"melee","range":int(_number(facts.get("movement.source_distance"),4))})
        elif field == "movement.caster_to_target_then_attack":
            adapted(field,{"blink_to_target":True,"range":int(_number(facts.get("movement.source_distance"),4))},"Caster moves to a free adjacent target cell and attacks; exact original path is reconstructed.")
        elif field == "movement.source_distance":
            adopt(field,{"range":int(_number(value,4))})
        elif field == "movement.destination":
            shrine = isinstance(value,dict) and value.get("type")=="resurrection_shrine_entrance"
            adapted(field,{"kind":"shrine" if shrine else "return","target":"self","range":0},"Published shrine/gates/tavern destination family retained. Available offline shrine/home gate coordinates used; original nation/tavern dispatch and server coordinates are not proven.")
        elif field == "movement.equivalent_item_reference" or field == "dispel.removal_skill_reference":
            reference(field,"Named related item/removal skill retained as cross-reference; its equivalent family is already bound, without guessing undocumented shared costs.")
        elif field == "movement.obstacles_can_be_crossed":
            reference(field,"Existing blink uses a valid destination instead of continuous walking; obstacle crossing is handled by that action, not a new unrestricted teleport.")
        elif field == "damage.periodic_hp_loss":
            adopted_fraction=float(value.get("fraction",0.03))
            adapted(field,{"kind":"status","status":"poison","power":0,"status_power":0,"poison_hp_fraction":adopted_fraction,"tick_interval":float(value.get("interval",1.0))},"Published max-HP loss and interval adopted; unpublished recipient identity resolved to the selected hostile monster.")
        elif field == "monster.behavior_change":
            adapted(field,{"kind":"status","status":"slow","forget_aggro":True,"power":0},"Forgetting clears aggression and temporarily prevents hostile pursuit; source duration remains reconstructed.")
        elif field == "restriction.caster_cannot_move_while_active":
            adopt(field,{"rooted":True})
        elif field.startswith("dispel.") and value is True:
            mapping={"dispel.poison":["poison"],"dispel.paralysis":["paralysis"],"dispel.blindness_절망":["blindness"],"dispel.curse":["slow"],"dispel.혼마술":["slow"],"dispel.all_magic":["poison","paralysis","slow","silence","blindness"]}
            adapted(field,{"kind":"cleanse","target":"self","cleanse_statuses":mapping.get(field,[])},"Published dispel scope mapped to current offline status aliases; blindness has a distinct status and defense curses use the current slow-plus-defense container.")
        elif field == "transform.forms":
            forms=_find_monster(value,data)
            adapted(field,{"form_monster_id":forms[0],"form_options":forms},"Acquired named creature forms reused; first available form is selected. Other published forms preserved as options; exact historical client look IDs unknown.")
        elif field == "summon.documented_forms":
            forms=_find_monster(value,data)
            if forms: adapted(field,{"monster_id":forms[0],"summon_form_options":forms},"Available documented subordinate creature selected; variants and level-dependent choice remain explicit reconstruction.")
            else: reference(field,"No exact named available monster; existing companion adaptation retained and published forms preserved.")
        elif field == "inspection.fields":
            adapted(field,{"inspect_self_fields":list(value)},"Online other-player inspection becomes useful inspection of this offline character and owned inventory.")
        elif field == "item_pickup.geometry":
            adopt(field,{"pickup_front_only":True,"range":max(1,int(result.get("range",1)))})
        elif field == "target.front" and result.get("kind")=="damage":
            adopt(field,{"directional_pattern":["front"]})
        elif field == "barrier.blocked_entity_class":
            adapted(field,{"barrier_radius":1},"Monster movement barrier is supported. PEOPLE-only barrier adapts to hostile creatures because offline game has no competing player entities.")
        elif field == "damage.conditional_multiplier":
            adapted(field,{"finisher_multiplier":_number(value,2.0),"attack_bonus":0,"attack_multiplier":1.0},"Published twofold finisher-only multiplier retained for damage skills; unrelated healing/basic attacks receive no generic attack bonus.")
        elif field == "damage.guardian_element":
            adopt(field,{"guardian":value.get("guardian"),"element":value.get("element")},"Documented guardian learning restriction and elemental identity retained; elemental resistance system is not invented.")
        elif field == "debuff.defense" or field == "debuff.armor_class_AC":
            adapted(field,{"on_hit_status":"slow","defense_bonus":-max(3,int(result.get("learn_level",1))//6)},"Published defense decrease retained with bounded reconstructed coefficient; slow tag is current executable debuff container.")
        elif field == "buff.armor_strength":
            adapted(field,{"defense_bonus":max(3,int(result.get("learn_level",1))//3)},"Published armor improvement receives bounded offline coefficient because no numeric amount was published.")
        elif field == "buff.attack_power":
            adapted(field,{"attack_bonus":max(3,int(result.get("learn_level",1))//3)},"Published attack increase retained with level-scaled reconstructed magnitude.")
        elif field == "effect_reference":
            reference(field,"Referenced skill's conceptual family retained. Exact cost/coefficient inheritance is explicitly unpublished and is not assumed.")
        elif field == "status.applied" and value == "blindness":
            adapted(field,{"status":"blindness","kind":"status"},"Published blindness becomes reduced outgoing damage in this offline all-hit model; exact source miss probability is not claimed.")
        elif field == "effect_type.ACCURACY_BUFF":
            adapted(field,{"accuracy_bonus":0.15},"Published accuracy benefit uses a reconstructed15% precision damage bonus because offline basic attacks always hit; no source hit probability is claimed.")
        elif field == "effect_type.EVASION_BUFF":
            adapted(field,{"evasion_chance":0.25,"move_multiplier":1.0},"Published evasion benefit retained with reconstructed25% evasion. This is not haste and does not slow movement.")
        elif field in ("effect_type.HIDDEN_DETECTION","effect_type.ILLUSION_CLONES"):
            adapted(field,None,"Hidden detection reveals nearby offline entities; illusion clones provide a bounded attack modifier. Original multiplayer identity/deception rules and exact coefficients are not claimed.")
        elif field.startswith("effect_type."):
            if field in ("effect_type.PLAYER_INSPECTION","effect_type.BROADCAST_VOICE","effect_type.MOVEMENT_OR_SUMMON"):
                adapted(field,None,"Online player/audience scope adapted to self inspection, local narration or home/companion behavior; no multiplayer implementation claimed.")
            else:
                adopt(field,None,"Semantic family selected before field-specific numeric adoption; executor parameters and separate runtime tests determine functional verification.")
        elif field in ("target.other_player_supported","target.multiple_people","target.all_group_members","target.group_members","target.must_be_strictly_lower_level_player","movement.caster_to_lower_player","movement.lower_player_to_caster_front","voice.audience","target.all_nearby_people_and_monsters","clones.real_identity_visibility","area.group_immune_to_damage","resource_transfer"):
            adapted(field,None,"Other online players/groups are unavailable in the offline scope. Existing self/companion/hostile-only or local narration action is the explicit substitute; original field preserved.")
        elif field.startswith(("target.","range.","area.","status.")):
            reference(field,"Published target/range/status qualifier retained alongside executable family. Unspecified units, online recipient identity and original geometry are not falsely converted to exact tiles.")
        elif field.startswith(("damage.","healing.","absorption.","buff.","duration.","summon.","protection.","reaction.")):
            reference(field,"Published contextual scaling, limit, relation or qualitative modifier retained. Complete server formula is unavailable; bounded offline base action remains explicit reconstruction and this field is not claimed as exactly implemented.")
        elif field == "restriction.ghost_only":
            adopt(field,None,"Existing shrine action refuses living characters; source dead-only restriction retained.")
        else:
            adopt(field,None,"Acquired field retained without a compatible executor binding; requires a concrete adaptation before claiming this particular field implemented.","UNSUPPORTED_RETAINED")

    result["source_effect_adoption"]={"schema":"baram.v2.skill-effect-adoption/1",
        "source_records":[{"content_id":r.get("content_id"),"profile":r.get("build_profile_id"),"sha256":hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()}for r in matches],
        "fields":ledger,"dispositions":dict(Counter(r["disposition"] for r in ledger.values())),
        "no_published_effect":not bool(matches),"runtime_test":"NOT_RUN_IN_ADOPTION_MODULE"}
    return result
