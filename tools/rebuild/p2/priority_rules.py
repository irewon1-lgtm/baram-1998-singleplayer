#!/usr/bin/env python3
"""Compile a private, provisional Korean 2001 inspection rules overlay.

Inputs are the immutable P1.5 core and Work B001/B002. This never modifies the
source records, enables P3 transactions, or treats a capture year as a client
version. Numeric prices are guide columns, not inferred vendor buy/sell prices.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from work_batch_adapter import Core, adapt, canonical_hash, PINS

PROFILE = 'KR_GUIDE_2001_WORKING_PROVISIONAL'
SOURCE_PROFILE = 'KR_GUIDE_2001_SNAPSHOT'
PREFIX = 'docs/rebuild/p1_5/'
TABLES = {
    'skills': 'kr_official_core.jsonl',
    'npcs': 'kr_official_services.jsonl',
    'facilities': 'kr_official_facility_rules.jsonl',
    'crafting_facts': 'kr_official_crafting_facts.jsonl',
    'growth_and_transport': 'kr_official_flow.jsonl',
}


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def eligible(row):
    return (row.get('build_profile_id') == SOURCE_PROFILE and row.get('game_region') == 'KR'
            and row.get('selected_for_build') is True and row.get('selected_original_value') is not None)


def entry(row, table, index):
    return {'id': row['content_id'], 'name': row['entity_name_ko'],
            'value': copy.deepcopy(row['selected_original_value']),
            'source_id': row['source_ids'], 'source_pointer': row['source_locator'],
            'source_table': table, 'source_record_sha256': canonical_hash(row),
            'source_line': index, 'fact_status': 'ORIGINAL_VERIFIED',
            'fact_scope': 'Published guide field; actual client/server value not independently established',
            'profile': PROFILE, 'source_profile': SOURCE_PROFILE,
            'runtime_status': 'SELECTED', 'runtime_test': 'NOT_RUN'}


def evaluate_learning(skill, job, level):
    """Read-only P2 contract: no inventory/currency/save mutation or skill grant."""
    value = skill['value']
    if job == '평민' or job == 'commoner':
        return {'eligible': False, 'job_level_eligible': False, 'status': 'REFUSED', 'reason': 'JOB_CHANGE_REQUIRED'}
    if (value['job'] != job and value['job'] != 'COMMON_FOUR_STARTER_JOBS') or (value['job'] == 'COMMON_FOUR_STARTER_JOBS' and job not in ['전사','도적','주술사','도사','COMMON_FOUR_STARTER_JOBS']):
        return {'eligible': False, 'job_level_eligible': False, 'status': 'REFUSED', 'reason': 'WRONG_JOB'}
    if level < value['learn_level']:
        return {'eligible': False, 'job_level_eligible': False, 'status': 'REFUSED', 'reason': 'LEVEL_TOO_LOW'}
    return {'eligible': False, 'job_level_eligible': True, 'status': 'BLOCKED',
            'reason': 'P3_TRANSACTION_NOT_IMPLEMENTED',
            'transaction_enabled': False, 'resource_check': 'NOT_RUN'}


def compile_rules(core_zip, batches, private_output, ledger_path, conflicts_path):
    core = Core(core_zip)
    ledger, source_rows = [], {}
    result = {'schema': 'baram.work.priority_rules/1', 'profile': PROFILE,
              'source_profile': SOURCE_PROFILE, 'historical_default_profile': None,
              'profile_scope': 'Provisional inspection choice inside 1998-2001 target; not a historical client freeze',
              'source_core_sha256': digest(core_zip.read_bytes()),
              'compiler_sha256': digest(Path(__file__).read_bytes()),
              'new_character_policy': {'level': 1, 'actual_job': 'commoner', 'desired_job': None,
                  'learned_attack_skills': [], 'minimum_job_change_level': 5,
                  'fact_status': 'RECONSTRUCTED', 'source_id': 'USER_TASK_20261016',
                  'scope': 'Explicit required product behavior; not new historical evidence'},
              'p3_transactions_enabled': False}
    for target, table in TABLES.items():
        rows = [json.loads(x) for x in core.read(PREFIX+'selected_content/'+table).splitlines()]
        source_rows.update({r['content_id']: r for r in rows})
        result[target] = [entry(r, table, i) for i, r in enumerate(rows, 1)
                          if eligible(r) and (target != 'skills' or r['record_type'] == 'skill')
                          and (target != 'growth_and_transport' or r['record_type'] != 'account')]
        for i, selected in enumerate(result[target]):
            ledger.append({'field_id': selected['id']+':'+source_rows[selected['id']]['field_path'],
                'content_id': selected['id'], 'profile': PROFILE,
                'field_path': source_rows[selected['id']]['field_path'],
                'selected_value': {'private_json_pointer': '/'+target+'/'+str(i)+'/value'},
                'selected_value_sha256': canonical_hash(selected['value']), 'unit': 'source_declared_fields',
                'source_tier': 1, 'source_id': selected['source_id'],
                'source_pointer': {'table': table, 'line': selected['source_line'],
                                   'record_sha256': selected['source_record_sha256']},
                'era_match': '2001_OFFICIAL_DOCUMENT; EXECUTABLE_BUILD_UNKNOWN',
                'selection_reason': 'Explicit KR2001 guide fields; no cross-year average and no unknown-field defaults',
                'alternatives': {'source_corpus_preserved': True, 'source_profile': 'KR_GUIDE_2000_SNAPSHOT'},
                'fact_status': 'ORIGINAL_VERIFIED', 'runtime_status': 'SELECTED', 'test_evidence': []})
    npcs = {r['id']: r for r in result['npcs']}
    for npc in result['npcs']:
        value = npc['value']
        target = value.get('stock_alias_content_id')
        if target:
            if target not in npcs or npcs[target]['source_id'] != npc['source_id']:
                raise ValueError('Same-capture stock alias is not closed: '+npc['id'])
            original = npcs[target]['value']
            npc['resolved_stock_reference'] = {'target_npc_id': target, 'sale_tokens': original['sale_tokens'],
                'buy_only_tokens': original['buy_only_tokens'], 'scope': 'Explicit same-capture inventory alias; face and NPC instance not aliased',
                'fact_status': 'ORIGINAL_VERIFIED'}
        # A guild table coordinate is a reference point, never automatic NPC placement.
        npc['map_placement_enabled'] = False
        npc['dialogue'] = None
        npc['buy_price'] = None
        npc['sell_price'] = None

    review = json.loads(core.read(PREFIX+'official_independent_review.json'))
    scoped = review['cross_era_conflicts']
    if len(scoped) != 15:
        raise ValueError('Prior scoped skill conflict set changed')
    result['conflicts'] = []
    csv_rows = []
    for number, conflict in enumerate(scoped, 1):
        candidates = conflict['candidates']
        for candidate in candidates:
            row = core.known[candidate['content_id']]
            if row['selected_original_value'][conflict['field']] != candidate['value']:
                raise ValueError('Independent-review conflict value does not match original normalized row')
        matching = [c for c in candidates if core.known[c['content_id']]['build_profile_id'] == SOURCE_PROFILE]
        if len(matching) != 1:
            raise ValueError('Conflict lacks unique target-profile candidate')
        chosen = matching[0]
        original = core.known[chosen['content_id']]
        resolution = {'conflict_id': 'P15-SKILL-CONFLICT-%02d'%number, 'entity': conflict['name_key'],
                      'job': conflict['job'], 'field': conflict['field'], 'profile': PROFILE,
                      'content_id': chosen['content_id'], 'selected_value': chosen['value'],
                      'source_id': original['source_ids'], 'source_pointer': original['source_locator'],
                      'fact_status': 'ORIGINAL_VERIFIED', 'resolution': 'SELECTED_FOR_PROVISIONAL_PROFILE',
                      'alternatives': [c for c in candidates if c['content_id'] != chosen['content_id']],
                      'historical_truth_resolved': False, 'runtime_test': 'NOT_RUN'}
        result['conflicts'].append(resolution)
        csv_rows.append({k: dump(v) if isinstance(v, (dict, list)) else v for k, v in resolution.items()})
        ledger.append({'field_id': resolution['conflict_id'], 'content_id': chosen['content_id'],
            'profile': PROFILE, 'field_path': 'skill.learning.'+conflict['field'],
            'selected_value': chosen['value'], 'unit': '전' if conflict['field']=='learn_money' else 'item quantities',
            'source_tier': 1, 'source_id': original['source_ids'], 'source_pointer': original['source_locator'],
            'era_match': '2001_OFFICIAL_DOCUMENT; EXECUTABLE_BUILD_UNKNOWN',
            'selection_reason': 'One 2001 candidate chosen for provisional coherent profile; historical alternatives retained',
            'alternatives': resolution['alternatives'], 'fact_status': 'ORIGINAL_VERIFIED',
            'runtime_status': 'SELECTED', 'test_evidence': [], 'overlaps_source_row_selection': True})
    all_conflicts = json.loads(core.read(PREFIX+'research_official_core.json'))['epoch_conflicts']
    result['supplemental_epoch_differences'] = all_conflicts
    result['conflict_scope'] = {'prior_skill_numeric_or_material_fields': len(scoped),
        'all_core_epoch_differences': len(all_conflicts),
        'all_core_difference_fields': dict(Counter(x['field'] for x in all_conflicts)),
        'meaning': '15 is one independently reviewed subset, not all differences or full original population'}

    # Read the actual immutable batches using the existing byte/reference guard.
    result['relations'], result['work_batch_decisions'] = [], []
    for path in batches:
        batch_ledgers, observations = adapt(path, core, set())
        for record, observed in zip(batch_ledgers, observations):
            private = observed.get('private_record') or {}
            decision = {'candidate_id': record['candidate_id'], 'batch_id': record['batch_id'],
                        'field': record['field'], 'source_profile': record['profile_id'],
                        'status': 'REFERENCE_ONLY', 'reason': 'NOT_RULE_VALUE_IN_THIS_COMPILER'}
            if record['profile_id'] == 'NA_REFERENCE_ONLY':
                decision.update(status='REFERENCE_ONLY', reason='WRONG_REGION_PRESERVE_NA_FAIL154')
            elif record['profile_id'] == 'KR_GUIDE_2000_SNAPSHOT':
                decision.update(status='NOT_SELECTED_OUT_PROFILE', reason='2000_VARIANT_PRESERVED')
            elif private and record['profile_id'] == SOURCE_PROFILE:
                value = copy.deepcopy(private.get('candidate_value'))
                if private.get('certainty') == 'EXPLICIT_CONFLICT_HOLD':
                    decision.update(status='CONFLICT_UNSELECTED', reason='SAME_PROFILE_PRICE_CONFLICT_NO_INDEPENDENT_TIE_BREAK')
                elif private.get('certainty') == 'LOCATION_INFERENCE':
                    decision.update(status='HYPOTHESIS_ONLY', reason='FACILITY_LOCATION_DOES_NOT_ESTABLISH_RECIPE_NPC')
                elif value is not None:
                    # Prose is in the immutable source; runtime retains only the bounded semantic/ID contract.
                    value.pop('documented_original', None)
                    r = {'id': record['candidate_id'], 'content_id': private['content_id'],
                         'name': private['entity_name_ko'], 'field': private['field'], 'value': value,
                         'fact_status': 'RECONSTRUCTED', 'source_id': [e['source_id'] for e in private['source_evidence']],
                         'source_pointer': private['source_evidence'], 'profile': PROFILE,
                         'remaining_unknowns': private['remaining_unknowns'], 'runtime_status': 'SELECTED',
                         'p3_behavior_implemented': False}
                    result['relations'].append(r)
                    decision.update(status='SELECTED', reason='BOUNDED_DERIVED_RELATION_FROM_SAME_PROFILE_SOURCE',
                                    relation_index=len(result['relations'])-1)
                    ledger.append({'field_id': r['id'], 'content_id': r['content_id'], 'profile': PROFILE,
                        'field_path': r['field'], 'selected_value': {'private_json_pointer': '/relations/'+str(len(result['relations'])-1)+'/value'},
                        'selected_value_sha256': canonical_hash(value), 'unit': private['original_unit'],
                        'source_tier': 7, 'source_id': r['source_id'],
                        'source_pointer': {'batch_id': record['batch_id'], 'candidate_id': r['id']},
                        'era_match': '2001_OFFICIAL_DOCUMENT_DERIVATIVE; BUILD_UNKNOWN',
                        'selection_reason': 'Derived bounded semantic or identity relation; original quoted/unknown fields preserved upstream',
                        'alternatives': [], 'fact_status': 'RECONSTRUCTED', 'runtime_status': 'SELECTED', 'test_evidence': []})
            result['work_batch_decisions'].append(decision)

    # Include only actual item IDs required by selected relations, not a new bulk item import.
    used_ids = set()
    for relation in result['relations']:
        for e in relation['source_pointer']:
            if e['content_id'].startswith('KRO-ITEM-'):
                used_ids.add(e['content_id'])
    item_rows = [json.loads(x) for x in core.read(PREFIX+'selected_content/kr_official_items.jsonl').splitlines()]
    item_lines = {r['content_id']: i for i, r in enumerate(item_rows, 1)}
    result['referenced_items'] = [entry(core.known[rid], 'kr_official_items.jsonl', item_lines[rid]) for rid in sorted(used_ids)]
    for item in result['referenced_items']:
        item.update(runtime_status='REFERENCE_ONLY', active_trade_price=None)
        if item['name'] == '진마반지':
            item['listed_price_status'] = 'CONFLICT_SAME_PROFILE_PRESERVED_NOT_ACTIVE_TRADE_PRICE'
    result['counts'] = {k: len(result[k]) for k in list(TABLES)+['relations','referenced_items','conflicts','work_batch_decisions']}
    result['counts']['row_selections_excluding_conflict_overlap'] = len(ledger)-len(scoped)
    result['counts']['original_row_selections'] = sum(len(result[k]) for k in TABLES)
    result['counts']['reconstructed_relation_selections'] = len(result['relations'])
    result['counts']['work_candidate_status'] = dict(Counter(x['status'] for x in result['work_batch_decisions']))
    result['validation'] = validate_rules(result)
    for path in (private_output, ledger_path, conflicts_path):
        if path.exists():
            raise ValueError('Choose a fresh generation/output; do not overwrite '+str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
    private_output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    private_output.chmod(0o600)
    ledger_path.write_text(''.join(dump(r)+'\n' for r in ledger))
    with conflicts_path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
        writer.writeheader();writer.writerows(csv_rows)
    return result['counts'], result['validation']


def validate_rules(data):
    checks = []
    def check(name, condition):
        checks.append({'id': name, 'result': 'PASS' if condition else 'FAIL'})
        if not condition:
            raise ValueError('Rules integrity failed: '+name)
    skills = data['skills']
    check('unique_skill_ids', len(skills)==len({x['id'] for x in skills}))
    check('one_source_profile', all(x['source_profile']==SOURCE_PROFILE for k in TABLES for x in data[k]))
    check('explicit_15_selected_once', len(data['conflicts'])==15 and len({x['conflict_id'] for x in data['conflicts']})==15)
    byid = {x['id']:x for x in skills}
    check('selected_conflicts_match_consumed_rules', all(byid[x['content_id']]['value'][x['field']]==x['selected_value'] for x in data['conflicts']))
    check('commoner_level1_no_attack_skills', data['new_character_policy']['level']==1 and data['new_character_policy']['actual_job']=='commoner' and data['new_character_policy']['learned_attack_skills']==[])
    check('level5_job_change_policy', data['new_character_policy']['minimum_job_change_level']==5)
    check('all_skills_refuse_commoner', all(not evaluate_learning(x,'commoner',1)['eligible'] for x in skills))
    check('all_job_skills_wrong_job_refused', all(not evaluate_learning(x,'invalid_job',99)['eligible'] for x in skills))
    check('all_positive_levels_refuse_one_lower', all(not evaluate_learning(x,x['value']['job'],x['value']['learn_level']-1)['eligible'] for x in skills if x['value']['learn_level']>0))
    check('all_same_job_levels_accept_readonly_contract', all(evaluate_learning(x,x['value']['job'],x['value']['learn_level'])['job_level_eligible'] for x in skills))
    check('p3_transactions_disabled', data['p3_transactions_enabled'] is False)
    check('different_npc_stock', len({dump(x.get('resolved_stock_reference',x['value']).get('sale_tokens',[])) for x in data['npcs']})>2)
    check('guild_coordinates_not_auto_placed', all(x['map_placement_enabled'] is False for x in data['npcs']))
    check('all_159_work_candidates_retained', len(data['work_batch_decisions'])==159)
    check('all_82_epoch_differences_retained', len(data['supplemental_epoch_differences'])==82)
    check('same_profile_jinma_price_still_held', any(x['status']=='CONFLICT_UNSELECTED' and x['field']=='item.listed_price.same_profile_conflict' for x in data['work_batch_decisions']))
    return {'scope': 'Actual pinned data, explicit profile, references, read-only job/level and vendor contracts; no native gameplay',
            'result': 'PASS', 'checks': checks, 'native_platform_status': 'NOT_RUN', 'runtime_ui_status': 'NOT_RUN'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core-zip', type=Path, required=True)
    p.add_argument('--batch-zip', type=Path, action='append', required=True)
    p.add_argument('--private-output', type=Path, required=True)
    p.add_argument('--ledger', type=Path, required=True)
    p.add_argument('--conflicts', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[3]
    if a.private_output.resolve().is_relative_to(repo):
        raise ValueError('Private rule values must stay outside public checkout')
    counts, validation = compile_rules(a.core_zip,a.batch_zip,a.private_output,a.ledger,a.conflicts)
    print(json.dumps({'counts':counts, 'validation':validation},ensure_ascii=False))


if __name__ == '__main__':
    main()
