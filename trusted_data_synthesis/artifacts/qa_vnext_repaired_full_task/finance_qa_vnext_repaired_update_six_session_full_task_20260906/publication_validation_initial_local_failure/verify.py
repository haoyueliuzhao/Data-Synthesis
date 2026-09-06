"""Publication accounting of completed six-session evidence; no model calls."""

import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import public_share_answer
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record, require, sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import load_panel, seal_directory, verify_source_snapshot
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential

ROOT = Path('/data1/zhuxinrui/projects/Data-Synthesis')
RUN = ROOT / 'trusted_data_synthesis/artifacts/qa_vnext_repaired_full_task/finance_qa_vnext_repaired_update_six_session_full_task_20260906'
report = read_json((RUN / 'execution/report.json').read_bytes())
implementation = read_json((RUN / 'preparation/implementation.json').read_bytes())
verify_source_snapshot(ROOT, implementation)
subprocess.run(['git', 'diff', '--exit-code', implementation['source_commit'], '--',
                'trusted_data_synthesis/src', 'trusted_data_synthesis/tests'], cwd=ROOT, check=True)
store = DurableStore(RUN / 'publication_validation')
store.write('verify.py', Path(__file__).read_bytes())
tests = []
for name, provenance in [
    ('qa_six_initial_tests.xml', 'development: four pass, six failures before Final field and test-operation-name fixes'),
    ('qa_six_second_tests.xml', 'development: ten wiring tests pass'),
    ('qa_six_actual_prepared_tests.xml', '611d2c47: actual preparation and synthetic six-session roundtrip pass'),
    ('qa_six_actual_cli_tests.xml', '1d4a7c87: actual CLI preparation and synthetic six-session roundtrip pass'),
    ('qa_six_final_tests.xml', '1d4a7c87: ten wiring regressions pass; synthetic HTTP only'),
]:
    data = (Path('/tmp') / name).read_bytes()
    store.write('tests/' + name, data)
    suites = ET.fromstring(data).findall('.//testsuite')
    tests.append({'name': name, 'provenance': provenance, 'sha256': sha(data),
                  **{key: sum(int(s.get(key, 0)) for s in suites)
                     for key in ['tests', 'failures', 'errors', 'skipped']}})
require(tests[-1]['tests'] == 10 and tests[-1]['failures'] == tests[-1]['errors'] == 0,
        'publication.final_wiring_tests')
require(tests[-2]['tests'] == 1 and tests[-2]['failures'] == tests[-2]['errors'] == 0,
        'publication.actual_cli_roundtrip')
panel = load_panel(ROOT)
share = panel.adapter('S')
observations, sessions, branch_errors, share_finals = [], [], [], []
usage = Counter()
raw_status, raw_models, schema_counts, event_kinds = Counter(), Counter(), Counter(), Counter()
reserves = []
for row in report['session_rows']:
    directory = RUN / 'execution/sessions' / row['label']
    session = read_json((directory / 'runtime/session.json').read_bytes())
    q = read_json((directory / 'qualification.json').read_bytes())
    current_usage = Counter()
    ledger = read_json((directory / 'transport/ledger.json').read_bytes())
    for attempt in ledger['attempts']:
        outcome = read_json((directory / 'transport' / attempt['paths']['outcome']).read_bytes())
        reservation = read_json((directory / 'transport' / attempt['paths']['reservation']).read_bytes())
        reserves.append(reservation['reserved_at_utc'])
        raw_status[outcome['status']] += 1
        raw_models[outcome['observed_model']] += 1
        require(outcome['host_repairs'] == outcome['automatic_retries'] == 0, 'publication.no_repair_or_retry')
        for key, value in outcome['usage'].items():
            if type(value) is int:
                usage[key] += value
                current_usage[key] += value
    for obs in row['progress']['observations']:
        observations.append({'label': row['label'], **obs})
    for event in session['events']:
        raw = event['parsed']
        schema_counts['parsed' if raw else 'unparsed'] += 1
        if raw:
            event_kinds[(raw['kind'], str(event['receipt']['admitted']))] += 1
        if row['label'].startswith('B') and event['receipt']['error_code'] == 'admission.alternative_set':
            available = [a['id'] for a in event['request']['available_actions']]
            declared = raw['decision']['candidate_action_ids']
            branch_errors.append({
                'label': row['label'], 'sequence': event['sequence'],
                'request_id': event['request']['id'], 'submission_id': event['submission']['id'],
                'receipt_id': event['receipt']['id'], 'offered': available, 'declared': declared,
                'missing': sorted(set(available) - set(declared)),
                'extra': sorted(set(declared) - set(available)),
                'duplicate_count': len(declared) - len(set(declared)),
                'public_candidate_field_schema': event['request']['response_schemas']['action']['$defs']['Decision']['properties']['candidate_action_ids'],
                'update_rules_present': 'public_update_contract' in event['request'],
            })
        if row['label'].startswith('S') and raw and raw['kind'] == 'final':
            claims = event['request']['state']['accepted_claims']
            claim = next(c for c in claims if c['id'] == raw['answer_claim_id'])
            validation = share.verify_final(raw, claims)
            share_finals.append({
                'label': row['label'], 'sequence': event['sequence'],
                'request_id': event['request']['id'], 'receipt_id': event['receipt']['id'],
                'admitted': event['receipt']['admitted'], 'submitted': raw,
                'expected_projection_readonly': public_share_answer(share.context, claim),
                'validation': validation,
            })
    sessions.append({'label': row['label'], 'status': row['status'], 'usage': dict(current_usage),
                     'qualification_reason': q['reason'], 'action_count': session['terminal_state']['action_count'],
                     'update_count': session['terminal_state']['update_count'], 'claims': len(session['claims']),
                     'submissions': row['submissions'], 'final': session['final']})
require(len(observations) == 13 and all(o['first_typed_update_admitted']
        and o['pending_model_submission_count'] == 1 and o['eventual_disposition'] == 'accept'
        and o['committed_claim_id'] for o in observations), 'publication.actual_update_accounting')
require(len(branch_errors) == 54 and all(e['missing'] and not e['extra']
        and not e['duplicate_count'] for e in branch_errors), 'publication.branch_missing_alternatives')
require(usage['prompt_tokens'] + usage['completion_tokens'] == usage['total_tokens']
        and usage['prompt_cache_hit_tokens'] + usage['prompt_cache_miss_tokens'] == usage['prompt_tokens'],
        'publication.actual_usage_arithmetic')
store.json('observation_rows.json', record('repaired_observation_rows', rows=observations))
store.json('new_blocker_diagnostics.json', record('repaired_new_blocker_diagnostics',
            branch_rejections=branch_errors, share_final_checks=share_finals,
            changed_runtime_or_standards=False, provider_calls=0, task_operation_executions=0,
            diagnostic_expected_projection_never_sent_to_model=True))
store.json('usage_and_events.json', record('repaired_usage_and_events', rows=sessions,
            observed_usage=dict(usage), response_status_counts=dict(raw_status),
            response_models=dict(raw_models), schema_counts=dict(schema_counts),
            event_counts=[{'kind': k[0], 'admitted': k[1] == 'True', 'count': n}
                          for k, n in sorted(event_kinds.items())],
            first_reservation_utc=min(reserves), last_reservation_utc=max(reserves),
            reservation_times_are_not_exact_session_start_end=True))
key = _credential(ROOT / 'trusted_data_synthesis/.env').encode()
paths = [p for p in RUN.rglob('*') if p.is_file()]
hits = [p.relative_to(RUN).as_posix() for p in paths if key in p.read_bytes()]
require(not hits and not any(p.name == '.env' or p.suffix == '.safetensors' for p in paths),
        'publication.excluded_credentials_and_weights')
result = record('repaired_publication_validation', source_commit=implementation['source_commit'],
                execution_report_id=report['id'], tests=tests,
                final_distinct_wiring_tests=11, tests_are_not_model_samples=True,
                source_and_tests_unchanged_since_freeze=True, exact_credential_byte_matches=0,
                scanned_artifact_files_before_this_report=len(paths),
                no_env_or_weights_in_new_artifacts=True, provider_calls=0,
                action_executions=0, observation_count=len(observations),
                first_update_accepts=len(observations), known_failed_session_count=2,
                complete_success_session_count=4, new_online_calls_after_six_sessions=0,
                branch_missing_alternative_rejections=len(branch_errors), passed=True)
store.json('report.json', result)
seal_directory(store, kind='six_publication_validation_manifest', report_id=result['id'])
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
for name in ['preparation', 'execution', 'reanalysis', 'guarded_reanalysis', 'readonly_verification', 'publication_validation']:
    files = [p for p in (RUN / name).rglob('*') if p.is_file()]
    print(name, len(files), sum(p.stat().st_size for p in files))
all_files = [p for p in RUN.rglob('*') if p.is_file()]
print('TOTAL', len(all_files), sum(p.stat().st_size for p in all_files),
      'MAX', max((p.stat().st_size, p.relative_to(RUN).as_posix()) for p in all_files))
