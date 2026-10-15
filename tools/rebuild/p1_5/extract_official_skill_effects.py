#!/usr/bin/env python3
"""Decode every acquired official skill description, without runtime defaults.

Preserves the parent core file. Source bytes, row/cell identity and normalized
description hash must match before any published semantic field is selected.
Only objective fields and paraphrased mechanic labels are exported, not prose.
"""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean(text):
    return " ".join(html.unescape(re.sub("<[^>]*>", " ", text)).split())


def leaf_rows(text):
    pattern = r"<tr\b[^>]*>((?:(?!<tr\b|</table>).)*?)(?:</tr>|(?=<tr\b)|(?=</table>))"
    for match in re.finditer(pattern, text, re.S | re.I):
        cells = list(re.finditer(r"<t[dh]\b[^>]*>((?:(?!<t[dh]\b).)*?)(?:</t[dh]>|(?=<t[dh]\b)|$)", match[1], re.S | re.I))
        yield match, cells


def get_description(parent, source):
    data = Path(source["local_private_path"]).read_bytes()
    if sha(data) != parent["input_sha256"] or sha(data) != source["sha256"]:
        raise ValueError("source hash mismatch: " + parent["content_id"])
    text = data.decode("cp949")
    text = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m[0]), text, flags=re.S)
    for row, cells in leaf_rows(text):
        line = text[:row.start()].count("\n") + 1
        if line != parent["source_locator"]["line_start"] or len(cells) < 3:
            continue
        cell = cells[2]
        desc = clean(cell[1])
        if sha(desc.encode()) != parent["original_value"]["source_effect_description_sha256"]:
            raise ValueError("description identity mismatch: " + parent["content_id"])
        if clean(cells[0][1]) != parent["entity_name_ko"]:
            raise ValueError("speaker/skill row mismatch: " + parent["content_id"])
        absolute = row.start(1) + cell.start(1)
        return desc, {"line_start": text[:absolute].count("\n") + 1, "line_end": text[:absolute + len(cell[1])].count("\n") + 1, "html_cell_index": 2, "normalized_description_sha256": sha(desc.encode()), "normalized_description_encoding": "UTF8 after strictCP949 HTML whitespace normalization"}
    raise ValueError("expected skill DOM row not found: " + parent["content_id"])


def decode(desc, name):
    compact = re.sub(r"\s+", "", desc)
    facts = []
    chosen = {}

    def add(path, value, pattern, flags=0):
        match = re.search(pattern, desc, flags)
        if not match:
            raise ValueError("semantic rule lacks source anchor: " + path + ":" + name)
        if path in chosen and chosen[path] == value:
            return
        chosen[path] = value
        facts.append({"field_path": "skill.effect." + path, "value": value, "description_char_start": match.start(), "description_char_end": match.end(), "evidence_fragment_sha256": sha(match[0].encode()), "evidence_scope": "DOCUMENT_PUBLISHED_NOT_RUNTIME_MEASURED"})

    def emit(path, value, pattern):
        if re.search(pattern, desc):
            add(path, value, pattern)

    # Qualitative effect type and constraints are decoded only when the source
    # actually describes them. Similar names do not supply absent mechanics.
    types = []
    type_rules = [(r"체력을\s*(?:약간|\d+)?\s*(?:만큼|씩)?\s*(?:회복|채워)|체력\s*회복(?:만|이)", "HP_HEAL"), (r"마력을\s*(?:완\s*전히\s*)?회복", "MP_RESTORE"), (r"공격 마법|공격 기술|원거리.*공격|피해를 (?:입히|가하)|데미지|일격|제압", "DAMAGE_DEALING"), (r"변신", "TRANSFORMATION"), (r"물건의 정보", "OWN_ITEM_INSPECTION"), (r"능력치.*훔쳐", "PLAYER_INSPECTION"), (r"물건.*가져", "REMOTE_ITEM_PICKUP"), (r"순간.*이동|순간.*날아|입구로 이동|주막으로 이동|불러", "MOVEMENT_OR_SUMMON"), (r"벽", "BARRIER"), (r"소환.*부하", "MONSTER_SUMMON"), (r"모든 마법.*풀어", "DISPEL_ALL_MAGIC"), (r"마법을.*튕겨", "SPELL_REFLECTION"), (r"피해를 무효", "DAMAGE_IMMUNITY"), (r"영혼을 불어", "RESURRECTION"), (r"(?:보이지 않는 것|투명을 걸고).*감지", "HIDDEN_DETECTION"), (r"몸을 숨겨|그룹원 모두에게 투명", "INVISIBILITY"), (r"분신이 사방", "ILLUSION_CLONES"), (r"큰 목소리", "BROADCAST_VOICE"), (r"접근을 막", "MOVEMENT_BLOCKING"), (r"명중률.*높", "ACCURACY_BUFF"), (r"공격을 피하는", "EVASION_BUFF"), (r"힘을.*높", "STRENGTH_BUFF"), (r"방어력을.*낮|AC를 깎", "DEFENSE_DEBUFF"), (r"체력을 흡입", "HP_ABSORPTION"), (r"모든 공격.*피해를 절반", "DAMAGE_REDUCTION")]
    for pattern, label in type_rules:
        if re.search(pattern, desc):
            if label == "DAMAGE_DEALING" and "자신의몸을숨겨" in compact:
                add("effect_type.ATTACK_MODIFIER_FOLLOWUP", True, pattern)
                types.append("ATTACK_MODIFIER_FOLLOWUP")
                continue
            types.append(label)
            add("effect_type." + label, True, pattern)

    emit("target.self_supported", True, r"자신이나|자신 또는|자신과 함께|상대나 자신의 체력|자신의 체력을.{0,15}회복|자신의 체력 (?:회복|만)|자신의 (?:몸|힘)|자신을 보호|시행자")
    emit("target.other_player_supported", True, r"자신이나 타인|자신이나 다른|자신 또는 다른|타인의 체력|다른 사람의 마력|다른 사람의 능력치|여러 사람의 체력|여러 명의 체력")
    emit("target.other_entity_supported", {"entity_class": "UNSPECIFIED"}, r"상대나 자신의 체력")
    emit("target.self_only", True, r"자신의 체력(?:만| 회복만)|자신의 체력만 회복")
    emit("target.multiple_people", True, r"여러 사람|여러 명")
    emit("target.group_members", True, r"그룹원 모두에게|그룹원 전체에게|그룹원들에게")
    emit("target.all_group_members", True, r"그룹원 (?:모두|전체)")
    emit("target.all_nearby_people_and_monsters", True, r"모든 사람들과 몬스터")
    emit("target.all_nearby_enemies", True, r"주위의 모든 적")
    emit("target.monsters_supported", True, r"몬스터가 공격을 잊|많은 몹을 잡|체력이 낮은 몹들의 체력")
    emit("target.monster_hp_condition", {"qualifier": "low_HP", "threshold": None}, r"체력이 낮은 몹들의 체력")
    emit("target.enemies_supported", True, r"(?:^|\s)적(?:들)?(?:을|에게)")
    emit("target.entity_class", "UNSPECIFIED_TARGET", r"대상|상대|희생자")
    emit("target.must_be_strictly_lower_level_player", True, r"자신보다 (?:낮은 레벨의|레벨이 낮은) 사람")
    emit("range.qualitative", "NEARBY", r"근처에 있는")
    emit("range.qualitative", "VISIBLE_PEOPLE", r"시야에 보이는 모든 사람")
    emit("range.qualitative", "UNSPECIFIED_AREA", r"일정범위|일정 범위|일정내")
    emit("range.qualitative", "RANGED_DISTANCE_UNSPECIFIED", r"원거리")
    emit("range.short_explicit", True, r"사정거리(?:가|는) 짧")
    emit("area.relative_directions", ["front", "back", "left", "right"], r"전후좌우|네 방향|사방")
    emit("area.relative_directions", ["front", "back"], r"앞뒤의 적")
    emit("area.relative_directions", ["left", "right"], r"좌우에 있는 적")
    emit("area.simultaneous", True, r"동시에|전후좌우|네 방향|전체 헬파이어")
    emit("area.center", "caster", r"자신의 주변|자신의 주위")
    emit("target.front", True, r"정면의 상대|바로 앞에 있는 물건")
    emit("area.group_immune_to_damage", True, r"그룹원은 안전|그룹원에게는 데미지가 가지 않는다")
    emit("damage.distance_falloff", "DECREASES_WITH_DISTANCE_COEFFICIENT_UNSTATED", r"멀어질수록 감소")

    heal = re.search(r"체력을\s*(\d+)\s*(?:만큼|씩|회복|채워)", desc)
    if heal:
        add("healing.hp_amount", {"value": int(heal[1]), "unit": "HP", "basis": "per_recipient", "measurement": "DOCUMENT_PUBLISHED"}, re.escape(heal[0]))
    emit("healing.qualitative_amount", "SMALL_UNSPECIFIED", r"체력을 약간 회복|약간의 체력을 회복")
    emit("healing.full_mp_restore", True, r"마력을 완\s*전히 회복")
    emit("cost.mp", {"mode": "flat", "value": 100, "unit": "MP", "resource_literal": "마력"}, r"마력\s*100\s*과.*소모")
    emit("cost.mp", {"mode": "all", "value": None, "unit": "MP", "current_or_max": "UNSTATED"}, r"(?:자신의 )?모든 마력을.*소모")
    emit("cost.mp", {"mode": "unspecified_amount", "value": None, "unit": "MP", "basis": "caster"}, r"자신의 마력을 소모, 다른 사람의 마력을 회복")
    emit("cost.hp", {"mode": "unspecified_some", "value": None, "unit": "HP"}, r"일부 체력을 소모")
    emit("cost.hp", {"mode": "majority", "value": None, "unit": "HP", "fraction": None}, r"체력의 대부분을 사용")
    emit("cost.hp", {"mode": "all", "value": None, "unit": "HP", "current_or_max": "UNSTATED"}, r"모든 체력을 사용")
    emit("cost.hp", {"mode": "fraction", "value": 0.5, "unit": "fraction", "basis": "caster_HP_current_or_max_UNSTATED"}, r"체력의\s*50%를 사용")
    emit("consequence.caster_death", True, r"자신도 죽기")
    emit("damage.incoming_multiplier", {"value": 0.5, "unit": "multiplier", "scope": "all_attacks"}, r"모든 공격.*피해를 절반")
    emit("damage.incoming_nullified", True, r"모든 피해를 무효")
    emit("reflection.probability", {"value": 0.5, "unit": "fraction", "scope": "incoming_spell_reflection_not_cast_success"}, r"마법을\s*50%\s*확률로 튕겨")
    emit("damage.periodic_hp_loss", {"fraction": 0.03, "basis": "recipient_max_HP", "interval": 1, "interval_unit": "second", "recipient_identity": "UNSTATED"}, r"매초 최대 체력의\s*3%를 감소")
    emit("absorption.hp_cap", {"multiplier": 2, "basis": "caster_max_HP"}, r"자신의 최대 체력의\s*2배까지 흡수")
    emit("absorption.broken_by", "RECEIVING_HEALING", r"회복 계열의 기술을 받으면 무너")
    emit("damage.conditional_multiplier", {"value": 2, "unit": "multiplier", "scope": "finisher_magic_attack_only"}, r"필살기 마법 공격력을\s*2배")
    emit("damage.rear_basic_attack_multiplier", {"value": 2, "unit": "multiplier", "scope": "documented_rear_basic_attack_not_full_skill_formula"}, r"배후에서의 공격은 일반 공격의\s*2\s*배")
    emit("damage.invisibility_multiplier", {"lower": 7, "upper": 8, "unit": "multiplier", "qualifier": "descriptive_range"}, r"평소의\s*7\s*에서\s*8\s*배")
    emit("damage.combo_multiplier_claim", {"value": 16, "unit": "multiplier", "qualifier": "nearly_approximate", "condition": "with_invisibility", "complete_formula": False}, r"투명과 조합.*거의\s*16\s*배")
    emit("damage.combo_multiplier_claim", {"value": 40, "unit": "multiplier", "qualifier": "approximately_forty_odd", "condition": "with_invisibility_and_biyeongseungbo", "complete_formula": False}, r"투명, 비영승보와.*40여배")
    emit("damage.stat_scaling", {"variables": ["caster_HP", "caster_resource_기력"], "relationship": "increases_with_both", "coefficients": None, "resource_기력_to_MP_binding": "UNRESOLVED"}, r"체력, 기력이 높아질수록 위력이 증가")
    emit("healing.stat_scaling", {"variable": "caster_resource_기력", "relationship": "proportional", "coefficient": None, "resource_기력_to_MP_binding": "UNRESOLVED"}, r"기력에 일정 비례.*체력을 회복")
    emit("damage.stat_scaling", {"variable": "caster_intelligence", "relationship": "proportional", "coefficient": None}, r"지력에 비례하는 공격력")
    emit("damage.stat_scaling", {"variable": "MP_consumed", "relationship": "proportional", "coefficient": None}, r"모든 마력을.*소모, 그에 비례하는 피해")
    emit("damage.poison_scaling", {"variable": "recipient_HP", "relationship": "increases_with_HP", "current_or_max": "UNSTATED", "coefficient": None}, r"상대의 체력이 높으면 높을수록 효과")

    for count, word in [(2, "두"), (3, "세"), (4, "네"), (5, "다섯")]:
        pattern = rf"(?:{word}\s*번|{count}\s*번) 연속 공격"
        emit("attack.hit_count", count, pattern)
    attack_multiplier = re.search(r"기본 공격(?:력이|력을|이)?\s*(약\s*)?(\d+)\s*배(?:로| 정도| 증가|를|의|\s)", desc)
    if attack_multiplier:
        value = int(attack_multiplier[2])
        approximate = "약" in attack_multiplier[0] or "정도" in attack_multiplier[0]
        add("damage.basic_attack_multiplier", {"value": value, "unit": "multiplier", "approximate": approximate}, re.escape(attack_multiplier[0]))
    emit("damage.basic_attack_multiplier", {"value": 2, "unit": "multiplier", "approximate": True}, r"기본 공격력을\s*2배 정도 강화")
    emit("buff.attack_power", "INCREASED_MAGNITUDE_UNSTATED", r"공격력을 (?:강화|가화)|파괴력을 증가|파괴력을 증가|전체 공격력을 향상")
    emit("buff.attack_power", "INCREASED_MAGNITUDE_UNSTATED", r"순간적으로 파괴력을 증가")
    emit("buff.stage", {"ordinal": 1}, r"첫 번째 단계")
    emit("buff.stage", {"ordinal": 2}, r"2번째 단계")
    emit("buff.stage", {"final": True, "ordinal": None}, r"마지막 단계")
    emit("buff.combo_reference", {"with_skill": "사중공격", "magnitude": None}, r"사중 공격과 더불어")
    emit("buff.finisher_damage", {"after_skill": "진백호령", "scope": "warrior_finishers", "coefficient": None}, r"진백호령을 외운 후 전사 필살기.*위력이 증가")
    emit("buff.armor_strength", "INCREASED_MAGNITUDE_UNSTATED", r"갑옷\s*강도를.*높")
    emit("debuff.defense", "DECREASED_MAGNITUDE_UNSTATED", r"방어력을.*낮")
    emit("debuff.armor_class_AC", "DECREASED_MAGNITUDE_UNSTATED", r"AC를 깎")

    # Published duration vocabulary is kept qualitative. It never creates sec/ms.
    emit("duration.qualifier", "UNSPECIFIED_DURATION", r"일정\s*시간")
    emit("duration.qualifier", "SHORT_UNSPECIFIED", r"지속\s*시간이 (?:아주 )?짧|잠시동안|마비시간이 매우 짧")
    emit("restriction.caster_cannot_move_while_active", True, r"지속되는 동안 움직일 수 없|지속되는 동안 움직일 수 없는")
    emit("restriction.ghost_only", True, r"유령이 된 상태에서만 사용")
    emit("movement.destination", {"type": "resurrection_shrine_entrance", "exact_map_id": None, "does_not_auto_revive": "not_claimed_by_description"}, r"성황당의 입구로 이동")
    emit("movement.destination", {"type": "city_four_gates", "cities": ["국내성", "부여성"], "directions": ["east", "west", "south", "north"], "nation_dispatch_rule": None, "exact_map_coordinates": None}, r"국내성 혹은 부여성의 동, 서, 남, 북의 사대문")
    emit("movement.destination", {"type": "own_nation_tavern", "exact_map_coordinates": None}, r"자신의 나라의?\s*주막")
    emit("movement.equivalent_item_reference", "노란비서", r"아이템 노란비서와 동일한 기능")
    emit("movement.caster_to_lower_player", True, r"자신보다 낮은 레벨의 사람에게 순간적으로 날아")
    emit("movement.lower_player_to_caster_front", True, r"자신보다 (?:레벨이 낮은|낮은 레벨의) 사람을 자신의 앞으로 불러")
    emit("movement.source_distance", {"value": 4, "unit": "칸", "direction": "front"}, r"4칸 앞의 적")
    emit("movement.pull_target_to_caster_front_then_attack", True, r"4칸 앞의 적을 자기 앞으로 끌")
    emit("movement.caster_to_target_then_attack", True, r"4칸 앞의 적에게 순간 이동하여 일격")
    emit("range.documented", {"value": 2, "unit": "필드", "normalized_tiles": None}, r"범위를\s*2필드까지 확장")
    emit("movement.obstacles_can_be_crossed", True, r"장애물을 넘어 이동")
    emit("movement.behind_target_candidate", {"value": "behind_target", "literal_source_typo": "배우", "support": "same description explicitly discusses rear attack", "status": "DOCUMENT_CONTEXT_INTERPRETATION"}, r"상대의 배우에 나타나")
    emit("damage.relative_power", {"greater_than": "동귀어진", "ratio": None}, r"데미지는 동귀어진보다 강하다")

    for status, pattern in [("poison", r"중독을 푸는"), ("curse", r"저주를 푸는"), ("paralysis", r"마비를 푸는"), ("blindness_절망", r"절망을 푸는"), ("혼마술", r"혼마술을 푸는")]:
        emit("dispel." + status, True, pattern)
    emit("dispel.all_magic", True, r"모든 마법을 일시에 풀어")
    emit("dispel.removal_skill_reference", "퇴마주", r"해체마법은 퇴마주")
    emit("status.applied", "poison", r"중독상태로 만드는")
    emit("status.applied", "paralysis_movement_block", r"상대를 얼려 움직이지 못하게")
    emit("status.applied", "blindness", r"시력을 일정시간동안 빼앗")
    emit("status.applied", "confusion_attacks_victims_allies", r"아군을 공격하게 만드는")
    emit("status.applied", "invisibility", r"자신의 몸을 숨겨")
    emit("status.applied", "invisibility_to_all_group", r"그룹원 모두에게 투명의 효과")
    emit("status.applied", "mutual_immobilization", r"자신과 함께 상대방을 꼼짝 못하게")
    emit("monster.behavior_change", "FORGET_ATTACK", r"몬스터가 공격을 잊어버리도록")
    emit("barrier.blocked_entity_class", "MONSTERS", r"몬스터들의 접근을 막")
    emit("barrier.blocked_entity_class", "PEOPLE", r"사람들의 접근을 막")
    emit("inspection.fields", ["abilities", "inventory"], r"능력치와 가진 물건")
    emit("inspection.fields", ["abilities"], r"능력치를 훔쳐")
    emit("item_pickup.geometry", "DIRECTLY_IN_FRONT", r"바로 앞에 있는 물건")
    emit("clones.real_identity_visibility", "ONLY_CASTER_CAN_DISTINGUISH", r"자신외의 그 누구도 실체/분신을 구분하지 못")
    emit("reaction.when_attacked", {"effect": "curse_on_attacker", "severity": "severe_unspecified", "requires_active_status": "마기지체"}, r"마기지체를 걸린 상태에서 상대방이 공격하면.*저주")
    emit("protection.body_magic", {"amount": None, "mechanism": "UNSTATED"}, r"자신의 몸을 마법력으로써 보호|자신을 보호하는 마법")
    emit("summon.level_dependent", True, r"레벨에 따라")
    emit("summon.documented_forms", ["평웅", "불여우", "자호", "해골"], r"평웅, 불여우, 자호, 해골")
    emit("summon.form_list_exhaustive", False, r"해골등")
    emit("summon.relationship", "caster_subordinate", r"자신의 부하로 만드는")
    emit("transform.forms", ["고양이", "새끼 돼지", "돼지", "강아지", "누렁이"], r"고양이, 새끼 돼지, 돼지, 강아지, 누렁이")
    emit("transform.forms", ["토끼", "다람쥐"], r"토끼, 다람쥐로 변신")
    emit("transform.forms", ["여우", "늑대"], r"여우, 늑대로 변신")
    emit("transform.forms", ["곰", "호랑이"], r"곰, 호랑이로 변신")
    emit("effect_reference", {"skill": "헬파이어", "dispatch": "FOUR_RELATIVE_DIRECTIONS", "cost_inheritance": None}, r"네 방향으로 헬파이어")
    emit("effect_reference", {"skill": "헬파이어", "dispatch": "AREA_WIDE_UNSPECIFIED", "cost_inheritance": None}, r"전체 헬파이어")
    emit("effect_reference", {"skill": "백호의희원", "dispatch": "ALL_GROUP_MEMBERS", "cost_inheritance": None}, r"그룹원 전체에게 백호의희원")
    emit("effect_reference", {"skill": "보호", "dispatch": "SOURCE_TARGET_SET", "cost_inheritance": None}, r"보호의 효과를 준다")
    emit("resource_transfer", {"spend": "caster_MP_amount_unspecified", "restore": "other_player_MP_amount_unspecified"}, r"자신의 마력을 소모, 다른 사람의 마력을 회복")
    emit("voice.audience", "ALL_PEOPLE_AS_PUBLISHED_SCOPE_UNRESOLVED", r"사람들 모두가 들릴 만한 큰 목소리")

    for guardian, element in [("주작", "fire"), ("현무", "water"), ("백호", "earth"), ("청룡", "wind_lightning")]:
        emit("damage.guardian_element", {"guardian": guardian, "element": element}, guardian + r"의 힘.*속성")
    predecessor = re.search(r"([가-힣]+)보다(?:도)? 한\s*단계 높은", desc)
    if predecessor:
        add("damage.relative_tier", {"higher_than_skill_literal": predecessor[1], "difference": "one_stage_qualitative", "coefficient": None}, re.escape(predecessor[0]))
    emit("damage.relative_tier", {"higher_than_skill_literal": "이기어검", "difference": "one_stage_qualitative", "coefficient": None}, r"이기어검보다 한단계 높은")
    emit("effect_reference", {"skill": "백호참", "dispatch": "SOURCE_TARGET_RANGE_EXTENSION", "cost_inheritance": None}, r"백호참의 위력")
    emit("effect_reference", {"skill": "백호검무", "dispatch": "WITH_AC_REDUCTION", "cost_inheritance": None}, r"백호검무의 위력을 가한다")

    numeric = []
    ignored = []
    for match in re.finditer(r"\d+(?:\.\d+)?", desc):
        anchors = [x["field_path"] for x in facts if x["description_char_start"] <= match.start() < x["description_char_end"]]
        if not anchors and re.match(r"3대 필수", desc[match.start():]):
            ignored.append({"value": int(match[0]), "role": "EDITORIAL_THREE_ESSENTIAL_SKILLS_NOT_MECHANIC", "char_offset": match.start()})
        else:
            numeric.append({"literal_numeric": match[0], "char_offset": match.start(), "mapped_field_paths": anchors, "status": "DECODED" if anchors else "UNDECODED_REQUIRES_SEMANTIC_RULE"})
    # The source says 배우, while the following sentence discusses 배후. Keep
    # that contextual interpretation out of the original-value selection.
    candidates = [f for f in facts if f["field_path"].endswith("_candidate")]
    reconstructed = {}
    for fact in candidates:
        key = fact["field_path"].removeprefix("skill.effect.")
        reconstructed[key] = chosen.pop(key)
        fact["fact_status"] = "CORROBORATED_RECONSTRUCTION"
        fact["evidence_scope"] = "DOCUMENT_CONTEXT_INTERPRETATION_NOT_ORIGINAL_LITERAL"
    facts = [f for f in facts if f not in candidates]
    # All descriptions were reviewed, including prose with no numerical formula.
    # Any wording not represented by a field remains an explicit descriptive
    # gap, not an invented effect default.
    gaps = {"mana_cost": "NOT_PUBLISHED" if "cost.mp" not in chosen else None, "hp_cost": "NOT_PUBLISHED" if "cost.hp" not in chosen else None, "duration_seconds": "NOT_PUBLISHED_NUMERICALLY", "stacking": "NOT_PUBLISHED", "cast_success_probability": "NOT_PUBLISHED", "cast_delay_ms": "NOT_PUBLISHED", "cooldown_seconds": "NOT_PUBLISHED", "exact_target_range": "NOT_PUBLISHED" if not any(k.startswith("range.documented") or k.startswith("movement.source_distance") for k in chosen) else None}
    return {"facts": facts, "selected_fields": chosen, "reconstructed_value": reconstructed or None, "reconstruction_evidence": candidates, "effect_types": types, "numeric_mentions": numeric, "editorial_numbers_excluded": ignored, "remaining_field_gaps": {k: v for k, v in gaps.items() if v is not None}}


def main(args):
    repo = Path(args.repo)
    root = repo / "docs/rebuild/p1_5"
    core = root / "selected_content/kr_official_core.jsonl"
    core_bytes = core.read_bytes()
    core_report = json.loads((root / "research_official_core.json").read_text())
    declared = [item for item in core_report["outputs"] if Path(item["path"]).name == core.name]
    if len(declared) != 1 or sha(core_bytes) != declared[0]["sha256"]:
        raise ValueError("parent core does not match independently declared source artifact fingerprint")
    parents = [row for row in map(json.loads, core_bytes.decode().splitlines()) if row["record_type"] == "skill"]
    expected_skill_rows = core_report["counts_by_type"]["skill"]
    if expected_skill_rows <= 0 or len(parents) != expected_skill_rows or len({row["content_id"] for row in parents}) != expected_skill_rows:
        raise ValueError("required skill parent set missing, duplicated or empty")
    sources = {s["source_id"]: s for s in json.loads(Path(args.source_manifest).read_text())}
    output = []
    descriptions = set()
    for parent in parents:
        desc, locator = get_description(parent, sources[parent["source_ids"][0]])
        descriptions.add(sha(desc.encode()))
        decoded = decode(desc, parent["entity_name_ko"])
        row = {"content_id": "KRO-EFX-" + parent["content_id"][4:], "record_type": "skill_effect", "parent_content_id": parent["content_id"], "entity_name_ko": parent["entity_name_ko"], "field_path": "skill.documented_effect", "original_value": {"job": parent["original_value"]["job"], "published_effect_facts": decoded["facts"], "effect_types": decoded["effect_types"], "mana_cost": decoded["selected_fields"].get("cost.mp"), "hp_cost": decoded["selected_fields"].get("cost.hp"), "duration_seconds": None, "stacking": None, "cast_success_probability": None, "cast_delay_ms": None, "cooldown_seconds": None, "source_description_sha256": sha(desc.encode()), "numeric_mentions": decoded["numeric_mentions"], "editorial_numbers_excluded": decoded["editorial_numbers_excluded"]}, "reconstructed_value": decoded["reconstructed_value"], "reconstruction_evidence": decoded["reconstruction_evidence"], "selected_reconstruction_for_build": False, "selected_original_value": decoded["selected_fields"], "selected_for_build": bool(decoded["selected_fields"]), "selected_for_p2_technical_input": bool(decoded["selected_fields"]), "selected_for_reference": True, "source_ids": parent["source_ids"], "source_family": parent["source_family"], "source_locator": {**parent["source_locator"], "effect_cell": locator}, "input_sha256": parent["input_sha256"], "parent_core_sha256": sha(core_bytes), "parser_version": "official-skill-effects/1.0", "parser_sha256": sha(Path(__file__).read_bytes()), "game_region": "KR", "client_build": parent["client_build"], "archive_capture_at": parent["archive_capture_at"], "source_authored_or_modified_at": parent["source_authored_or_modified_at"], "build_profile_id": parent["build_profile_id"], "require_profile_dispatch": True, "global_default_selected": False, "target_profile_resolution": "UNRESOLVED", "selection_scope": "PROFILE_SCOPED_DOCUMENT_PUBLISHED_EFFECT_FIELDS_ONLY", "profile_is_client_version": False, "gameplay_binding_requires_profile_decision": True, "variant_group_id": parent["variant_group_id"], "fact_status": "ORIGINAL_VERIFIED", "fact_scope": "Published description fields, not measured runtime mechanics; unknown coefficient/current-max basis retained", "use_status": "IDENTIFIED", "new_runtime_binding": "NOT_STARTED", "test_status": "NOT_RUN", "consumer_feature": "skill_effect", "required_implementation": "Consume explicit selected fields only through named archival profile; effect commands/units/conditions require independent binding; no implied costs/delays", "missing_information": decoded["remaining_field_gaps"], "semantic_review_scope": "ALL377_SOURCE_DESCRIPTIONS_180_UNIQUE_FAMILIES_READ"}
        output.append(row)
    if len(output) != len(parents) or len({r["parent_content_id"] for r in output}) != len(parents):
        raise ValueError("required parent input set not fully represented")
    if core.read_bytes() != core_bytes:
        raise ValueError("core changed during extraction; retry with new input fingerprint")
    path = root / "selected_content/kr_official_skill_effects.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in output))
    unresolved_numeric = [{"content_id": r["content_id"], "name": r["entity_name_ko"], "numeric_mentions": [m for m in r["original_value"]["numeric_mentions"] if m["status"].startswith("UNDECODED")]} for r in output if any(m["status"].startswith("UNDECODED") for m in r["original_value"]["numeric_mentions"])]
    counts = {"expected_skill_rows": len(parents), "checked_source_descriptions": len(output), "unique_description_hashes": len(descriptions), "selected_rows": sum(r["selected_for_build"] for r in output), "published_effect_facts": sum(len(r["original_value"]["published_effect_facts"]) for r in output), "numeric_mentions": sum(len(r["original_value"]["numeric_mentions"]) for r in output), "reconstruction_candidates": sum(len(r["reconstruction_evidence"]) for r in output), "unique_description_field_facts": len({(r["original_value"]["source_description_sha256"], f["field_path"], json.dumps(f["value"], ensure_ascii=False, sort_keys=True)) for r in output for f in r["original_value"]["published_effect_facts"]}), "unresolved_numeric_rows": len(unresolved_numeric), "by_field": dict(Counter(f["field_path"] for r in output for f in r["original_value"]["published_effect_facts"]))}
    report = {"task_id": "BARAM_REBUILD_P1_5_001", "status": "PARTIAL_UNDECODED_NUMERIC_TERMS" if unresolved_numeric else "PASS_SOURCE_DESCRIPTION_FIELD_SCOPE", "scope": "all377 existing skill source rows, source hashes+DOM cell+description hashes+published semantic fields; no gameplay", "core_sha256": sha(core_bytes), "parser_sha256": sha(Path(__file__).read_bytes()), "source_manifest_sha256": sha(Path(args.source_manifest).read_bytes()), "counts": counts, "unresolved_numeric_rows": unresolved_numeric, "outputs": [{"path": str(path.relative_to(repo)), "sha256": sha(path.read_bytes()), "bytes": path.stat().st_size, "rows": len(output), "public_republish": False}], "limitations": ["Most descriptions do not state resource cost/duration/range formulas; null retained", "Approximate claims are not exact multiplicative formulas", "Current-vs-max HP basis preserved as unknown when only HP is stated", "기력 literal not silently equated to a runtime MP stat", "2000and2001targetset conflicts kept in parent archival profiles", "No runtime, build, authenticated service or gameplay tests"], "game_tests": "NOT_RUN"}
    (root / "research_official_skill_effects.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": report["status"], "counts": counts, "unresolved_numeric_rows": unresolved_numeric}, ensure_ascii=False))
    return 2 if unresolved_numeric else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--source-manifest", required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(main(args))
    except FileNotFoundError as error:
        print(json.dumps({"result": "BLOCKED", "error": "required source unavailable", "file": Path(error.filename).name}), file=sys.stderr)
        raise SystemExit(2)
    except (ValueError, KeyError, UnicodeError) as error:
        print(json.dumps({"result": "FAIL", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
