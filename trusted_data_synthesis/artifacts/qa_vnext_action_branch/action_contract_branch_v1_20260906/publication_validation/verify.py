"""Account for actual branch evidence and length-limited exports; never call a model."""

import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record, require, sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory, verify_source_snapshot
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential

ROOT = Path('/data1/zhuxinrui/projects/Data-Synthesis')
RUN = ROOT / 'trusted_data_synthesis/artifacts/qa_vnext_action_branch/action_contract_branch_v1_20260906'
EXEC = RUN / 'execution'
report = read_json((EXEC / 'report.json').read_bytes())
implementation = read_json((RUN / 'preparation/implementation.json').read_bytes())
verify_source_snapshot(ROOT, implementation)
subprocess.run(['git', 'diff', '--exit-code', implementation['source_commit'], '--',
                'trusted_data_synthesis/src', 'trusted_data_synthesis/tests'], cwd=ROOT, check=True)
store = DurableStore(RUN / 'publication_validation')
store.write('verify.py', Path(__file__).read_bytes())
tests = []
for name, provenance in [
    ('qa_action_branch_initial_tests.xml', '23 new local tests pass before source freeze; synthetic HTTP only'),
    ('qa_action_branch_related_tests.xml', '110 pass, 11 hand-authored Request fixtures lack new publication before repair'),
    ('qa_action_branch_related_fixed_tests.xml', '121 related tests pass after updating only hand-authored Request publication'),
    ('qa_action_branch_actual_cli_tests.xml', '1cf4d520 actual committed CLI preparation and two-session synthetic HTTP roundtrip pass'),
    ('qa_action_branch_final_tests.xml', '1cf4d520 final 23 new tests pass; synthetic HTTP only'),
]:
    data = (Path('/tmp') / name).read_bytes()
    store.write('tests/' + name, data)
    suites = ET.fromstring(data).findall('.//testsuite')
    tests.append({'name': name, 'provenance': provenance, 'sha256': sha(data),
                  **{key: sum(int(s.get(key, 0)) for s in suites)
                     for key in ['tests', 'failures', 'errors', 'skipped']}})
require([t['tests'] for t in tests] == [23, 121, 121, 1, 23], 'publication.test_inventory')
require(all(t['failures'] == t['errors'] == 0 for t in tests[2:]), 'publication.final_test_outcomes')
sessions, observations, candidate_sets, attempts, reservations = [], [], [], [], []
usage = Counter()
for row in report['session_rows']:
    directory = EXEC / 'sessions' / row['label']
    session = read_json((directory / 'runtime/session.json').read_bytes())
    local_usage = Counter()
    ledger = read_json((directory / 'transport/ledger.json').read_bytes())
    for attempt in ledger['attempts']:
        outcome = read_json((directory / 'transport' / attempt['paths']['outcome']).read_bytes())
        reservation = read_json((directory / 'transport' / attempt['paths']['reservation']).read_bytes())
        http = read_json((directory / 'transport' / attempt['paths']['http_response']).read_bytes())
        reservations.append(reservation['reserved_at_utc'])
        require(outcome['host_repairs'] == [] and outcome['automatic_retries'] == 0,
                'publication.no_response_repair_or_retry')
        for key, value in outcome['usage'].items():
            if type(value) is int:
                usage[key] += value
                local_usage[key] += value
        attempts.append({'label': row['label'], 'attempt_index': attempt['attempt_index'],
                         'outcome_id': outcome['id'], 'status': outcome['status'],
                         'model': outcome['observed_model'], 'http_status': http['status_code'],
                         'condition_flags': outcome['condition_flags']})
    for obs in row['progress']['observations']:
        observations.append({'label': row['label'], **obs})
    candidate_sets.extend({'label': row['label'], **r} for r in row['progress']['candidate_set_rows'])
    require(all(e['receipt']['admitted'] and e['parsed'] for e in session['events']),
            'publication.actual_all_submissions_admitted')
    sessions.append({'label': row['label'], 'session_id': session['id'], 'status': row['status'],
                     'usage': dict(local_usage), 'action_count': session['terminal_state']['action_count'],
                     'update_count': session['terminal_state']['update_count'], 'claim_count': len(session['claims']),
                     'submission_count': row['submissions'], 'final': session['final'],
                     'actual_operation_order': [e['observation']['obligation_id'] for e in session['events'] if e.get('observation')],
                     'actual_numeric_outputs': {c['obligation_id']: c['proposition']['output'] for c in session['claims']},
                     'growth_and_merge': {key: row['progress'][key] for key in ['first_nontransparent_operation', 'first_branch_merge', 'first_absolute_operation']}})
require(len(attempts) == 34 and len(observations) == len(candidate_sets) == 16, 'publication.actual_counts')
require(all(r['admitted'] and r['full_set_and_unique'] and r['selected_current'] for r in candidate_sets), 'publication.actual_candidate_sets')
require(all(o['first_typed_update_admitted'] and o['pending_model_submission_count'] == 1
            and o['eventual_disposition'] == 'accept' and o['later_consumers'] for o in observations),
        'publication.actual_commits_and_consumption')
require(all(a['status'] == 'public_content' and a['http_status'] == 200 and not a['condition_flags'] for a in attempts),
        'publication.actual_transport')
require(usage['prompt_tokens'] + usage['completion_tokens'] == usage['total_tokens']
        and usage['prompt_cache_hit_tokens'] + usage['prompt_cache_miss_tokens'] == usage['prompt_tokens'],
        'publication.actual_usage_arithmetic')
raw = read_json((EXEC / 'analysis/supervision_candidates.json').read_bytes())
tokenized = read_json((EXEC / 'analysis/token_representations.json').read_bytes())
raw_by_id = {r['id']: r for r in raw['rows']}
labels = {s['session_id']: s['label'] for s in sessions}
lengths = []
for item in tokenized['records']:
    original = raw_by_id[item['row_id']]
    require(item['truncated'] is False and item['raw_candidate_and_qualification_retained'], 'publication.no_truncation')
    lengths.append({'label': labels[original['session_id']], 'turn_index': original['turn_index'],
                    'submission_kind': original['submission_kind'], 'candidate_id': original['id'],
                    'sequence_length': item['sequence_length'], 'prompt_token_count': item['prompt_token_count'],
                    'target_token_count': item['target_token_count'], 'consumable': item['consumable_token_representation'],
                    'reason': item['reason'], 'truncated': item['truncated'],
                    'exceeds_by': max(0, item['sequence_length'] - item['maximum_sequence_length'])})
require(len(raw_by_id) == len(lengths) == 34 and tokenized['fit_count'] == 32
        and tokenized['not_fit_count'] == 2 and tokenized['status'] == 'contains_not_fit'
        and tokenized['positive_representation_validated'] is False, 'publication.bounded_representation_not_all_pass')
store.json('session_accounting.json', record('action_branch_actual_accounting', rows=sessions,
            attempts=attempts, observed_usage=dict(usage), first_reservation_utc=min(reservations),
            last_reservation_utc=max(reservations), reservation_times_are_not_exact_session_start_end=True))
store.json('observation_and_candidates.json', record('action_branch_observation_and_candidate_accounting',
            observations=observations, candidate_sets=candidate_sets))
store.json('token_lengths.json', record('action_branch_token_lengths', rows=lengths,
            raw_candidate_count=34, token_fit_count=32, token_not_fit_count=2,
            all_raw_and_token_records_preserved=True, no_qualification_rewritten=True))
key = _credential(ROOT / 'trusted_data_synthesis/.env').encode()
paths = [p for p in RUN.rglob('*') if p.is_file()]
require(all(key not in p.read_bytes() for p in paths), 'publication.no_key_bytes')
require(not any(p.name == '.env' or p.suffix == '.safetensors' for p in paths), 'publication.no_env_or_weights')
result = record('action_branch_publication_validation', execution_report_id=report['id'],
                source_commit=implementation['source_commit'], source_and_tests_unchanged=True,
                tests=tests, distinct_final_tests=145, control_samples_are_not_provider_samples=True,
                complete_success_sessions=2, actual_provider_attempts=34, actual_actions=16,
                actual_update_commits=16, actual_valid_finals=2, actual_rejections=0,
                candidate_full_set_passes=16, first_update_accepts=16,
                actual_raw_positive_candidates=34, token_fit_count=32, token_not_fit_count=2,
                model_workflow_not_gated_on_all_token_candidates_fitting=True,
                credential_byte_matches=0, scanned_artifact_files_before_this_report=len(paths),
                no_env_or_weights=True, provider_calls_by_publication=0, operation_executions_by_publication=0,
                additional_online_calls_after_two_sessions=0, passed=True)
store.json('report.json', result)
seal_directory(store, kind='action_branch_publication_validation_manifest', report_id=result['id'])
print(json.dumps(result, sort_keys=True), flush=True)
for directory in sorted(RUN.iterdir()):
    if directory.is_dir():
        files = [p for p in directory.rglob('*') if p.is_file()]
        print(directory.name, len(files), sum(p.stat().st_size for p in files))
files = [p for p in RUN.rglob('*') if p.is_file()]
print('TOTAL', len(files), sum(p.stat().st_size for p in files),
      'MAX', max((p.stat().st_size, p.relative_to(RUN).as_posix()) for p in files))
