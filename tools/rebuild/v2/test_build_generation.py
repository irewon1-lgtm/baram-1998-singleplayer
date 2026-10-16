#!/usr/bin/env python3
"""Compiler regressions for source omissions, cheap high gear and action collapse."""
import unittest

from build_generation import build_items, item_kind, skill_action


class SourceCompilationTests(unittest.TestCase):
    def source_item(self, values):
        return {'content_id':'source:sword','entity_name_ko':'현철중검','original_value':values,
                'source_ids':['fixture:reviewed-source-fields'],'source_locator':{'line':1}}

    def test_raw_available_damage_and_strength_are_not_discarded(self):
        data={'items':{}};ledger=[]
        row=self.source_item({'item_kind':'weapon','minimum_level':0,'listed_price':20,
            'required_strength':40,'damage_min':None,'damage_max':None,'raw_numeric_cells':{'위력':'60m95'}})
        build_items(data,{'source:sword':('items',row,'fixture')},ledger)
        sword=data['items']['source:sword']
        self.assertGreater(sword['attack'],20)
        self.assertEqual(sword['required_strength'],40)
        self.assertEqual(sword['required_level'],0)  # actual sourced zero stays zero
        self.assertGreaterEqual(sword['buy_price'],sword['attack']*35)
        self.assertEqual(sword['source_value']['raw_numeric_cells']['위력'],'60m95')

    def test_unknown_learning_level_has_reasoned_inference(self):
        data={'items':{}};row=self.source_item({'item_kind':'weapon','damage_min':100,'damage_max':150})
        build_items(data,{'source:sword':('items',row,'fixture')},[])
        self.assertGreater(data['items']['source:sword']['required_level'],1)
        self.assertEqual(data['items']['source:sword']['effective_field_status']['required_level'],'INFERRED')

    def test_acquired_item_effects_reach_runtime_fields(self):
        data={'items':{}};row=self.source_item({'item_kind':'weapon','minimum_level':10,
            'effects':[{'stat_label_documented':'체력','delta':250},{'stat_label_documented':'지력','delta':4},
                       {'stat_label_documented':'재생력','delta':10}]})
        build_items(data,{'source:sword':('items',row,'fixture')},[])
        sword=data['items']['source:sword']
        self.assertEqual((sword['hp_bonus'],sword['intelligence_bonus'],sword['regen_bonus']),(250,4,2))
        self.assertEqual(len(sword['source_effect_adoption']),3)

    def test_multiple_job_restrictions_remain_multiple(self):
        data={'items':{}};row=self.source_item({'item_kind':'weapon','job_restriction_documented':['전사','도적']})
        build_items(data,{'source:sword':('items',row,'fixture')},[])
        self.assertEqual(data['items']['source:sword']['required_jobs'],['전사','도적'])

    def test_actions_keep_distinct_source_roles(self):
        names={'성황령':'shrine','물품감정':'identify','비영사천문':'return','노획':'loot',
               '비영승보':'blink','중독':'status','마비':'status','건곤대나이':'damage',
               '금수':'buff','소환':'summon','반탄공':'buff','부활':'revive'}
        for name,kind in names.items():
            with self.subTest(name=name):self.assertEqual(skill_action(name,70,'도적')['kind'],kind)
        self.assertEqual(skill_action('반탄공',99,'도사')['reflect_fraction'],.25)
        self.assertEqual(skill_action('사중공격',62,'전사')['attack_multiplier'],4.0)
        self.assertEqual(skill_action('금수',14,'도적')['transform_family'],'돼지')
        self.assertEqual(skill_action('경수',25,'도적')['transform_family'],'토끼')

    def test_unknown_action_does_not_silently_become_damage(self):
        with self.assertRaisesRegex(ValueError,'Unclassified'):skill_action('자료에없는임의기술',99,'전사')

    def test_category_slots_are_real_equipment_functions(self):
        self.assertEqual(item_kind('노란비서',{}),('consumable',''))
        self.assertEqual(item_kind('현철장갑',{}),('armor','ring'))
        self.assertEqual(item_kind('녹호박장삼',{}),('armor','armor'))
        self.assertEqual(item_kind('풍의제삼검',{}),('weapon','weapon'))


if __name__=='__main__':unittest.main()
