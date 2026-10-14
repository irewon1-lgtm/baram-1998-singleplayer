#!/usr/bin/env python3
"""Audit frozen NPC proposals and emit a DATA-ONLY integration plan, never game data."""
import copy
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'content-work'
OUT = WORK / 'catalog/content010-resume'
PINS = {
    '008': ('2935c1f7cebed5a673dca1660d6bb0fbff0ae35d', 'd9f69210a63b0cdcd6013561cdbc83d2976bb9fcdcd65437f170bb40433dfa4b'),
    '010': ('f7a85eee9615db2d2f977ae5796a867a096bce07', '59e352d2c2b34bdab160380e2dd00aade99c86b18cfe35ab3b3873f8aec1bb4f'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def load_package(number):
    path = WORK / 'packages' / ('WK-CONTENT-' + number)
    assert digest(path / 'manifest.json') == PINS[number][1]
    manifest = json.loads((path / 'manifest.json').read_text())
    for f in manifest['files']:
        assert digest(path / f['path']) == f['sha256']
    rows = [json.loads(line) for f in sorted(path.glob('content-*.jsonl')) for line in f.read_text().splitlines()]
    return rows


def expected_state(record, side):
    return {c['path']: copy.deepcopy(c['before']['value'] if side == 'before' else c['after']) for c in record['changes']}


def select_exact_state(current, states, merged):
    # Used only for the audit simulation. No runtime or saved state is accessed.
    if not any(current == value for value in states.values()):
        raise ValueError('UNRECOGNIZED_CURRENT_FIELDS: reject complete transaction')
    return copy.deepcopy(merged)


def main():
    rows = {n: load_package(n) for n in PINS}
    npcs = {n: {r['target_id']: r for r in data if r['kind'] == 'npc'} for n, data in rows.items()}
    overlap = sorted(npcs['008'].keys() & npcs['010'].keys())
    assert overlap == ['wk.npc.exp2.dry.51.smith', 'wk.npc.exp2.forest.11.smith']
    plans, observations = [], []
    checks = {'npc_pairs': 0, 'original_guard_conflicts_each_order': 0, 'recognized_state_cases': 0, 'unexpected_state_rejections': 0, 'menu_service_pairs_preserved': 0}
    for target in overlap:
        a, b = npcs['008'][target], npcs['010'][target]
        base, left, right = expected_state(a, 'before'), expected_state(a, 'after'), expected_state(b, 'after')
        assert base == expected_state(b, 'before')
        assert set(base) == {'services', 'dialogue'}
        conflicts = [k for k in base if left[k] != base[k] and right[k] != base[k] and left[k] != right[k]]
        assert conflicts == ['services', 'dialogue']
        checks['original_guard_conflicts_each_order'] += len(conflicts)
        merged = copy.deepcopy(left)
        count = len(base['services'])
        assert left['services'][:count] == right['services'][:count] == base['services']
        assert len(left['services']) == len(right['services']) == count + 1
        for service in right['services'][count:]:
            assert service not in merged['services']
            merged['services'].append(copy.deepcopy(service))
        assert len(base['dialogue']) == len(left['dialogue']) == len(right['dialogue']) == 1
        base_dialogue, ld, rd = base['dialogue'][0], left['dialogue'][0], right['dialogue'][0]
        for dialogue in (ld, rd):
            assert {k: v for k, v in dialogue.items() if k != 'choices'} == {k: v for k, v in base_dialogue.items() if k != 'choices'}
            assert dialogue['choices'][:len(base_dialogue['choices'])] == base_dialogue['choices']
        additions = []
        for choice in rd['choices'][len(base_dialogue['choices']):]:
            new_choice = copy.deepcopy(choice)
            source_service = right['services'][choice['service_index']]
            new_choice['service_index'] = merged['services'].index(source_service)
            merged['dialogue'][0]['choices'].append(new_choice)
            additions.append({'label': choice['label'], 'old_index': choice['service_index'], 'merged_index': new_choice['service_index'], 'recipe_id': source_service['recipe_id']})
        for original in (left, right):
            for choice in original['dialogue'][0]['choices']:
                matches = [c for c in merged['dialogue'][0]['choices'] if c['label'] == choice['label']]
                assert len(matches) == 1
                assert merged['services'][matches[0]['service_index']] == original['services'][choice['service_index']]
                checks['menu_service_pairs_preserved'] += 1
        states = {'common_baseline': base, 'content008_only': left, 'content010_only': right, 'already_reconciled': merged}
        for current in states.values():
            assert select_exact_state(current, states, merged) == merged
            checks['recognized_state_cases'] += 1
        for mode in ('unknown_service', 'changed_text', 'wrong_menu_index', 'mixed_fields'):
            bad = copy.deepcopy(left)
            if mode == 'unknown_service': bad['services'].append({'type': 'unexpected'})
            elif mode == 'changed_text': bad['dialogue'][0]['text'] += ' changed'
            elif mode == 'wrong_menu_index': bad['dialogue'][0]['choices'][0]['service_index'] = 999
            else: bad['dialogue'] = copy.deepcopy(right['dialogue'])
            try:
                select_exact_state(bad, states, merged)
            except ValueError:
                checks['unexpected_state_rejections'] += 1
            else:
                raise AssertionError('Unexpected state accepted')
        checks['npc_pairs'] += 1
        plans.append({'target_id': target, 'source_proposal_ids': [a['id'], b['id']], 'field_paths': list(base), 'accepted_exact_field_sets': states, 'merged_fields': merged, 'bow_menu_index_changes': additions})
        observations.append({'target_id': target, 'conflicting_fields': conflicts, 'baseline_services': count, 'content008_services': len(left['services']), 'content010_services': len(right['services']), 'merged_services': len(merged['services']), 'bow_menu_index_changes': additions})
    # Immutable input verification after the analysis.
    for number in PINS: load_package(number)
    pins = [{'batch_id': 'WK-CONTENT-' + n, 'package_commit': p[0], 'manifest_sha256': p[1]} for n, p in PINS.items()]
    plan = {'schema_id': 'WORK_NPC_RECONCILIATION_PROPOSAL_V1', 'scope': 'DATA_ONLY_NOT_A_RUNTIME_PACKAGE', 'source_packages': pins,
            'consumer_status': 'NOT_IMPLEMENTED_OR_EXECUTED_HERE', 'game_import': 'NOT_RUN', 'gameplay': 'NOT_RUN',
            'requirements': ['Verify both immutable source packages and all dependency pins before staging.', 'Require both optional equipment capabilities before activating both menu families.', 'This is an explicit per-target resolution, never disable generic field guards or overwrite changed Codex fields.', 'Stage both package definitions and these two field-pair resolutions in one atomic consumer transaction, or apply to a verified single-package state. Every unrelated original guard still applies.', 'Compare the complete services/dialogue pair with one accepted exact field set; reject unknown or mixed states. Preserve every other NPC field.', 'Preserve existing service order, append shield then bow, and reindex the bow choice to its corresponding recipe service.', 'Record both original proposals and this resolution provenance. Roll back the complete batch on error; do not falsely receipt the original failing patch as a plain success.', 'Already reconciled state must be idempotent. Produce real importer/runtime receipts before marking imported or played.'], 'npc_resolutions': plans}
    dump('npc-merge-proposal.json', plan)
    report = {'executed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'command': 'python content-work/tools/reconcile_content008_010.py', 'script_sha256': digest(Path(__file__)), 'source_packages': pins, 'scope': 'STATIC_DATA_RECONCILIATION_SIMULATION', 'conflict_detection': 'PASS_CONFIRMED', 'unmodified_combined_import': 'BLOCKED_GUARD_CONFLICT', 'proposal_checks': 'PASS', 'checks': checks, 'npcs': observations, 'game_import': 'NOT_RUN', 'gameplay': 'NOT_RUN', 'frozen_source_hashes_unchanged': True}
    dump('npc-conflict-validation.json', report)
    print(json.dumps({'conflict_npcs': len(overlap), 'checks': checks, 'proposal_checks': 'PASS', 'game_import': 'NOT_RUN', 'gameplay': 'NOT_RUN'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
