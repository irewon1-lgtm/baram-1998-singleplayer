#!/usr/bin/env python3
"""Executable planning-policy model, NOT a game/Android/Windows test.

Exhaustive Boolean states and source availability masks are synthetic inputs.
Repository baseline counts are observations from the pinned handoff, not
measurements of work completed by this model. No time/token estimates.
Run: python3 tools/rebuild/simulate_plan.py --output docs/rebuild/PLAN_SIMULATION.json
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import platform
from pathlib import Path

PLAN_ID = 'BARAM_REBUILD_V2_RESOURCE_FIRST_20261016'
BASE_SHA = 'd124aa6c23c753f1fa1edd810b0b0386e3b80315'
TIERS = ('LEGACY_VERIFIED', 'LEGACY_RECONSTRUCTED', 'MODERN_BARAM_ADAPTED',
         'OTHER_GAME_ADAPTED', 'INFERRED')
SOURCES = {
 'AGENTS.md': 'be3d85b4e287040bd758c0fe086092173e7b6800',
 'docs/rebuild/STATE.json': '8db17a2bc2a66d7ee42b6ca145e62ad4bed49044',
 'docs/rebuild/MASTER_PLAN.md': 'd4116a5321bffa149873bce5456d0f1ca913a392',
 'docs/rebuild/p3-remediation/P4_HANDOFF.json': '98f7d8d826ce5aee4cc6dce4ffb4be17db071a7d',
 'docs/rebuild/p3-remediation/RESULTS.md': '374d479af6c59b1dadd3d4d8b4eca80ff1739362',
}


def select_source(mask: tuple[bool, ...]) -> str:
    """Availability means usable evidence within scope/budget, not just a URL."""
    if len(mask) != 4:
        raise ValueError('Exactly four evidence tiers precede inference')
    return next((tier for tier, available in zip(TIERS, mask) if available), 'INFERRED')


def proof(implemented: bool, run: bool, passed: bool) -> str:
    if not implemented:
        return 'NOT_IMPLEMENTED'
    if not run:
        return 'NOT_RUN'
    return 'PASS' if passed else 'FAIL'


def platform_proof(available: bool, run: bool, passed: bool) -> str:
    if not available:
        return 'BLOCKED_ENVIRONMENT'
    return 'NOT_RUN' if not run else ('PASS' if passed else 'FAIL')


def retry_action(previous_failures: int, changed: bool, transient: bool) -> str:
    if changed:
        return 'TEST_NEW_FINGERPRINT'
    if transient and previous_failures < 2:
        return 'ONE_BOUNDED_RETRY'
    return 'CHANGE_METHOD_OR_SCOPE_BLOCK'


def evidence_reuse(old: tuple, new: tuple, passed: bool) -> bool:
    # source, implementation, settings, environment, test scope
    return passed and len(old) == 5 and old == new


def resolve_policy(documents: list[dict]) -> str:
    active = [d for d in documents if d.get('path') == 'docs/rebuild/MASTER_PLAN.md' and d.get('status') == 'CURRENT']
    if len(active) != 1:
        raise ValueError('One current master is required')
    return active[0]['plan_id']


def release_allowed(function: str, native: str, migration_verified: bool, fatal_errors: int) -> bool:
    return function == 'PASS' and native == 'PASS' and migration_verified and fatal_errors == 0


def resume(done: set[str], order: tuple[str, ...]) -> str:
    return next((step for step in order if step not in done), 'COMPLETE')


def migration(old: dict, new: dict, validated: bool, conflict: bool) -> dict:
    # Model of copy-first promotion, not a real save-file migration.
    return dict(new if validated and not conflict else old)


def simulate() -> dict:
    # Four availability bits + implemented/test + Android availability/test +
    # Windows availability/test = 12 Boolean bits, 4096 abstract states.
    names = ('legacy_exact', 'legacy_basis', 'modern', 'other',
             'implemented', 'function_test_run', 'function_test_passed',
             'android_available', 'android_test_run', 'android_test_passed',
             'windows_available', 'windows_test_run')
    violations: list[dict] = []
    policy = {name: {'avoidable_source_stalls': 0,
                     'higher_priority_source_ignored': 0,
                     'independent_content_blocked_by_android': 0,
                     'false_platform_pass': 0}
              for name in ('WAIT_EXACT', 'INFER_IMMEDIATELY',
                           'FALLBACK_GLOBAL_PLATFORM_GATE', 'BOUNDED_DEPENDENCY')}
    selected_counts = dict.fromkeys(TIERS, 0)
    function_counts: dict[str, int] = {}
    for bits in itertools.product((False, True), repeat=len(names)):
        x = dict(zip(names, bits))
        tier = select_source(bits[:4])
        selected_counts[tier] += 1
        function = proof(x['implemented'], x['function_test_run'], x['function_test_passed'])
        function_counts[function] = function_counts.get(function, 0) + 1
        android = platform_proof(x['android_available'], x['android_test_run'], x['android_test_passed'])
        # Windows result is intentionally UNKNOWN here; no pass bit is supplied.
        windows = 'BLOCKED_ENVIRONMENT' if not x['windows_available'] else 'NOT_RUN' if not x['windows_test_run'] else 'AWAIT_RESULT'
        if function == 'PASS' and not all((x['implemented'], x['function_test_run'], x['function_test_passed'])):
            violations.append({'case': x, 'error': 'false_function_pass'})
        if android == 'PASS' and not all((x['android_available'], x['android_test_run'], x['android_test_passed'])):
            violations.append({'case': x, 'error': 'false_android_pass'})
        if windows == 'PASS':
            violations.append({'case': x, 'error': 'unobserved_windows_pass'})
        if tier == 'INFERRED' and any(bits[:4]):
            violations.append({'case': x, 'error': 'source_priority'})
        # Metrics describe policy rules under synthetic states; they are not
        # probabilities, runtime counts, developer productivity, or token costs.
        policy['WAIT_EXACT']['avoidable_source_stalls'] += int(not x['legacy_exact'])
        policy['INFER_IMMEDIATELY']['higher_priority_source_ignored'] += int(any(bits[:4]))
        policy['FALLBACK_GLOBAL_PLATFORM_GATE']['independent_content_blocked_by_android'] += int(not x['android_available'])

    tests: list[dict] = []
    def check(name: str, condition: bool) -> None:
        tests.append({'id': name, 'passed': bool(condition)})
    # Independent, explicit expected routing outcomes.
    for mask, expected in [((1,1,1,1), TIERS[0]), ((0,1,1,1), TIERS[1]),
                           ((0,0,1,1), TIERS[2]), ((0,0,0,1), TIERS[3]),
                           ((0,0,0,0), TIERS[4])]:
        check('tier_' + expected, select_source(tuple(bool(v) for v in mask)) == expected)
    check('missing_original_is_not_runtime_pass', proof(False, False, False) == 'NOT_IMPLEMENTED')
    check('unrun_test_stays_not_run', proof(True, False, True) == 'NOT_RUN')
    check('failed_runtime_stays_fail', proof(True, True, False) == 'FAIL')
    check('android_black_screen_not_pass', platform_proof(True, True, False) == 'FAIL')
    check('no_galaxy_not_pass', platform_proof(False, True, True) == 'BLOCKED_ENVIRONMENT')
    check('same_failure_not_infinite', retry_action(2, False, True) == 'CHANGE_METHOD_OR_SCOPE_BLOCK')
    check('deterministic_failure_change_method', retry_action(1, False, False) == 'CHANGE_METHOD_OR_SCOPE_BLOCK')
    check('changed_input_retested', retry_action(99, True, False) == 'TEST_NEW_FINGERPRINT')
    check('transient_retry_bounded', retry_action(1, False, True) == 'ONE_BOUNDED_RETRY')
    f = ('source', 'code', 'config', 'environment', 'scope')
    check('identical_success_reusable', evidence_reuse(f, f, True))
    check('identical_failure_not_reusable_as_pass', not evidence_reuse(f, f, False))
    for i in range(5):
        g = list(f); g[i] += '_changed'
        check('fingerprint_change_' + f[i], not evidence_reuse(f, tuple(g), True))
    order = ('B0', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6')
    for i in range(len(order) + 1):
        check('resume_after_' + str(i), resume(set(order[:i]), order) == (order[i] if i < len(order) else 'COMPLETE'))
    old = {'map': 'old', 'x': 10, 'revision': 9}
    new = {'map': 'new', 'x': 12, 'revision': 10}
    for validated, conflict in itertools.product((False, True), repeat=2):
        expected = new if validated and not conflict else old
        check(f'migration_{validated}_{conflict}', migration(old, new, validated, conflict) == expected)
    check('old_save_not_mutated', old == {'map': 'old', 'x': 10, 'revision': 9})
    docs = [{'path':'docs/rebuild/history/v1/MASTER_PLAN.md','status':'HISTORICAL','plan_id':'V1'},
            {'path':'docs/rebuild/MASTER_PLAN.md','status':'CURRENT','plan_id':PLAN_ID}]
    for ordering in itertools.permutations(docs):
        check('authority_order_' + ordering[0]['plan_id'], resolve_policy(list(ordering)) == PLAN_ID)
    try:
        resolve_policy(docs + [docs[1]])
        check('multiple_current_masters_rejected', False)
    except ValueError:
        check('multiple_current_masters_rejected', True)
    check('black_screen_blocks_android_release', not release_allowed('PASS','FAIL',True,0))
    check('native_unrun_blocks_release', not release_allowed('PASS','NOT_RUN',True,0))
    check('migration_unverified_blocks_replacement', not release_allowed('PASS','PASS',False,0))
    check('fatal_error_blocks_release', not release_allowed('PASS','PASS',True,1))
    check('all_required_evidence_allows_release', release_allowed('PASS','PASS',True,0))
    # Exhaustive ordering constraints; no invented durations or success rates.
    tasks = ('authority', 'platform_diagnosis', 'source_route', 'contracts',
             'shared_actions', 'bulk_import', 'integration_test', 'deliver')
    deps = [('authority','platform_diagnosis'), ('authority','source_route'),
            ('source_route','contracts'), ('contracts','shared_actions'),
            ('shared_actions','bulk_import'), ('bulk_import','integration_test'),
            ('platform_diagnosis','integration_test'), ('integration_test','deliver')]
    admissible = []
    for seq in itertools.permutations(tasks):
        pos = {task:i for i,task in enumerate(seq)}
        if all(pos[a] < pos[b] for a,b in deps):
            admissible.append(seq)
    # Select earliest diagnosis to discover platform risk early; a failed
    # environment blocks delivery, not independent source/action work.
    chosen = min(admissible, key=lambda s: s.index('platform_diagnosis'))
    check('chosen_diagnoses_platform_early', chosen.index('platform_diagnosis') == 1)
    check('no_admissible_bulk_before_contracts', all(s.index('contracts') < s.index('bulk_import') for s in admissible))
    check('no_admissible_release_before_integration', all(s.index('integration_test') < s.index('deliver') for s in admissible))
    # Mutation checks: known-bad variants must have counterexamples.
    mutations = {
       'always_infer': sum(select_source(m) != 'INFERRED' for m in itertools.product((False,True), repeat=4)),
       'always_platform_pass': sum(platform_proof(*b) != 'PASS' for b in itertools.product((False,True), repeat=3)),
       'always_reuse_changed_evidence': sum(not evidence_reuse(f, tuple(v + '_changed' if j == i else v for j,v in enumerate(f)), True) for i in range(5)),
       'always_restart_from_B0': sum(resume(set(order[:i]), order) != 'B0' for i in range(1,len(order)+1)),
       'always_promote_invalid_save': sum(migration(old,new,v,c) != new for v,c in itertools.product((False,True), repeat=2)),
    }
    for name, counterexamples in mutations.items():
        check('mutation_rejected_' + name, counterexamples > 0)
    return {
      'schema': 'baram.plan.policy-simulation/2', 'plan_id': PLAN_ID,
      'scope': 'EXECUTED_ABSTRACT_POLICY_MODEL_NOT_GAME_TEST',
      'basis': {'source_commit': BASE_SHA, 'git_blob_inputs': SOURCES,
                'observed_active_counts': {'maps':11,'npcs':9,'items':8,'monsters':2,'skills':10},
                'observed_deferred_counts': {'skill_rows':178,'npc_contract_rows':15},
                'note': 'Counts from handoff. No claim that simulated routes implement these entities.'},
      'execution': {'python': platform.python_version(), 'state_space_size':2**len(names),
                    'boolean_dimensions':names, 'selected_source_counts':selected_counts,
                    'function_verdict_distribution':function_counts,
                    'policy_comparison':policy, 'violations':violations,
                    'scenario_tests':tests, 'scenario_passed':sum(t['passed'] for t in tests),
                    'scenario_total':len(tests), 'mutation_counterexamples':mutations,
                    'permutations_checked':40320, 'admissible_orders':admissible,
                    'selected_order':chosen},
      'limitations': [
        'No APK/EXE/gameplay, real save files, IME, audio or device benchmarks executed.',
        'Availability and pass bits are synthetic states, not observed probabilities.',
        'A fallback route is a work decision; it is not source acquisition or feature completion.',
        'No real token/cost/time measurements; no global or empirical optimality claim.',
        'Selection is a risk-ordering preference among dependency-valid plans, not a speed proof.'
      ],
      'model_result':'PASS' if not violations and all(t['passed'] for t in tests) else 'FAIL',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/rebuild/PLAN_SIMULATION.json'))
    args = parser.parse_args()
    result = simulate()
    root = Path(__file__).resolve().parents[2]
    state_path = root / 'docs/rebuild/STATE.json'
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        master = (root / 'docs/rebuild/MASTER_PLAN.md').read_text(encoding='utf-8')
        agents = (root / 'AGENTS.md').read_text(encoding='utf-8')
        checks = {
          'plan_id_equal': state['plan_id'] == PLAN_ID and PLAN_ID in master and PLAN_ID in agents,
          'single_entrypoint': state['entrypoint'] == 'AGENTS.md',
          'single_current_master': state['master_plan'] == 'docs/rebuild/MASTER_PLAN.md',
          'exactness_not_gate': state['goal']['exact_historical_match_required'] is False,
          'fallback_order_equal': tuple(state['goal']['source_ladder']) == TIERS,
          'preserve_game_partial': state['implementation_status'] == 'EXISTING_P3_PARTIAL',
          'no_game_test_claim': state['simulation']['game_tests_performed'] == 0,
          'old_restrictions_archived': state['historical']['archive_directory'] in agents,
          'next_step_B1': state['current_phase'] == state['next_action']['phase'] == 'B1',
          'bulk_scope_not_deferred': state['defect_policy_changes']['P3-FIX-22']['current_work'] == 'ACTIVE_SCOPE_B3_B4',
          'map_not_fake_fixed': state['defect_policy_changes']['P3-FIX-09']['closed'] is False,
          'platform_unrun_retained': state['retained_actual_status']['Galaxy'] == state['retained_actual_status']['Windows_native'] == 'NOT_RUN',
          'main_not_authorized': state['authorization']['main_merge_or_production_publish'] is False,
          'phase_ids_present': all('B' + str(i) in master for i in range(7)),
        }
        result['active_document_checks'] = checks
        result['active_document_hashes'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'AGENTS.md', root/'docs/rebuild/MASTER_PLAN.md', state_path)}
        if not all(checks.values()):
            result['model_result'] = 'FAIL'
    result['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'model_result':result['model_result'],
                      'states': result['execution']['state_space_size'],
                      'scenario_tests':f"{result['execution']['scenario_passed']}/{result['execution']['scenario_total']}",
                      'permutations':40320, 'admissible':len(result['execution']['admissible_orders'])}, ensure_ascii=False))
    if result['model_result'] != 'PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
