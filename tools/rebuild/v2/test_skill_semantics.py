"""Source-field adoption tests; these do not certify runtime action execution."""
from copy import deepcopy
import unittest

from skill_semantics import adopt_skill_effects


def effect(fields, parent="test:skill", profile="KR_GUIDE_2001_SNAPSHOT"):
    return {"content_id":"test:effect","parent_content_id":parent,"selected_for_build":True,
            "build_profile_id":profile,"selected_original_value":fields}


def base():
    return {"id":"test:skill","name":"synthetic","kind":"damage","power":999,"learn_level":30,
            "delivery":"projectile","target":"monster","range":5,"mp_cost":10}


class SkillEffectAdoption(unittest.TestCase):
    def test_published_heal_and_resource_cost_override_reconstructed_numbers(self):
        out=adopt_skill_effects(base(),[effect({"effect_type.HP_HEAL":True,
            "healing.hp_amount":{"value":100,"unit":"HP"},"cost.mp":{"mode":"flat","value":25,"unit":"MP"}})],{})
        self.assertEqual((out["kind"],out["power"],out["mp_cost"]),("heal",100,25))
        self.assertEqual(out["source_effect_adoption"]["fields"]["healing.hp_amount"]["disposition"],"ADOPTED")

    def test_transformation_uses_an_available_named_form_and_does_not_summon(self):
        source=base();source["kind"]="summon";source["monster_id"]="unrelated:rabbit"
        out=adopt_skill_effects(source,[effect({"effect_type.TRANSFORMATION":True,"transform.forms":["고양이","새끼 돼지","돼지"]})],
            {"monsters":{"native:pig":{"name":"꼬마돼지","level":1},"native:rabbit":{"name":"토끼","level":1}}})
        self.assertEqual((out["kind"],out["form_monster_id"]),("buff","native:pig"))
        self.assertNotIn("monster_id",out)
        self.assertEqual(out["source_effect_adoption"]["fields"]["transform.forms"]["disposition"],"ADAPTED")

    def test_reflection_probability_is_distinct_from_reflected_damage_fraction(self):
        out=adopt_skill_effects(base(),[effect({"effect_type.SPELL_REFLECTION":True,
            "reflection.probability":{"value":0.5,"unit":"fraction"}})],{})
        self.assertEqual(out["reflect_probability"],0.5)
        self.assertEqual(out["reflect_fraction"],1.0)
        self.assertIn("offline",out["source_effect_adoption"]["fields"]["reflection.probability"]["reason"])

    def test_directional_geometry_and_pull_keep_published_distance(self):
        out=adopt_skill_effects(base(),[effect({"area.relative_directions":["front","back"],
            "movement.source_distance":{"value":4,"unit":"칸"},"movement.pull_target_to_caster_front_then_attack":True})],{})
        self.assertEqual(out["directional_pattern"],["front","back"])
        self.assertEqual(out["range"],4)
        self.assertTrue(out["pull_target"])

    def test_evasion_is_not_converted_to_slowing_haste(self):
        source=base();source.update(status="haste",move_multiplier=1.45)
        out=adopt_skill_effects(source,[effect({"effect_type.EVASION_BUFF":True})],{})
        self.assertEqual(out["move_multiplier"],1.0)
        self.assertEqual(out["evasion_chance"],0.25)
        self.assertNotEqual(out["status"],"haste")

    def test_unknown_and_incomplete_formulae_are_preserved_without_implementation_claim(self):
        fields={"damage.stat_scaling":{"coefficient":None,"variable":"caster_HP"},"future.unknown":123}
        out=adopt_skill_effects(base(),[effect(fields)],{})
        ledger=out["source_effect_adoption"]["fields"]
        self.assertEqual(set(ledger),set(fields))
        self.assertEqual(ledger["damage.stat_scaling"]["disposition"],"REFERENCE_RETAINED")
        self.assertEqual(ledger["future.unknown"]["disposition"],"UNSUPPORTED_RETAINED")
        self.assertTrue(all(x["runtime_test"]=="NOT_RUN_IN_ADOPTION_MODULE" for x in ledger.values()))

    def test_parent_ids_prevent_cross_profile_name_guessing_and_inputs_unchanged(self):
        source=base();rows=[effect({"healing.hp_amount":{"value":999,"unit":"HP"}},parent="different:parent")]
        original=deepcopy((source,rows))
        out=adopt_skill_effects(source,rows,{})
        self.assertTrue(out["source_effect_adoption"]["no_published_effect"])
        self.assertEqual((source,rows),original)

    def test_conflicting_original_fields_fail_instead_of_last_row_wins(self):
        rows=[effect({"healing.hp_amount":{"value":100,"unit":"HP"}}),effect({"healing.hp_amount":{"value":200,"unit":"HP"}})]
        with self.assertRaisesRegex(ValueError,"Conflicting acquired effect field"):
            adopt_skill_effects(base(),rows,{})

    def test_blindness_and_vision_cleanse_keep_a_distinct_supported_status(self):
        blind=adopt_skill_effects(base(),[effect({"status.applied":"blindness"})],{})
        vision=adopt_skill_effects(base(),[effect({"dispel.blindness_절망":True})],{})
        self.assertEqual(blind["status"],"blindness")
        self.assertEqual(vision["cleanse_statuses"],["blindness"])

    def test_finisher_only_modifier_does_not_leave_generic_basic_attack_bonus(self):
        source=base();source.update(kind="buff",attack_bonus=30,attack_multiplier=2)
        out=adopt_skill_effects(source,[effect({"damage.conditional_multiplier":{"value":2,"unit":"multiplier"}})],{})
        self.assertEqual((out["finisher_multiplier"],out["attack_bonus"],out["attack_multiplier"]),(2,0,1))


if __name__=="__main__":
    unittest.main()
