"""CPU-only same-point handoff tests; no signals, subprocesses or CUDA."""
from __future__ import annotations

from copy import deepcopy
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v69_binding as b
import finqa_v69_worker_bridge as bridge


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != 'id'}
    value = dict(body, id=b.digest(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


@pytest.fixture
def environment(tmp_path, monkeypatch):
    original_job = b.completion_module('finqa_v67_evaluation').planned_jobs()[b.TARGET_JOB_ID]
    root, source = tmp_path / 'migration', tmp_path / 'completion'
    monkeypatch.setattr(b, 'ROOT', root)
    monkeypatch.setattr(b, 'COMPLETION_ROOT', source)
    monkeypatch.setattr(b, 'SOURCE_ROOT', source)
    monkeypatch.setattr(b, 'TARGET_PID', 111111)
    monkeypatch.setattr(b, 'TARGET_BIRTH', 'original-birth')
    monkeypatch.setattr(b, 'BASE_PROTOCOL_ID', 'original-science-id')
    monkeypatch.setattr(bridge, '_live', lambda *_: False)
    job = dict(original_job, checkpoint={'path': '/actual894', 'state_sha256': 'same-state'},
               model_identity={'point_id': 'same-original-scientific-point'})
    scientific = rewrite(source / 'protocol/record.json', dict(
        gpu_uuids={'6': 'GPU-six', '0': 'GPU-zero'}, cpu_affinity={'6': '16-23'},
        gpu_lease_root=str(tmp_path / 'secondary'), memory_protection_policy={'original': 'unchanged'}))
    monkeypatch.setattr(b, 'COMPLETION_PROTOCOL_ID', scientific['id'])
    tasks = [f'finqa/t{i}' for i in range(883)]
    plan = rewrite(source / 'evaluations/registration/record.json', dict(
        protocol_id=scientific['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        jobs={b.TARGET_JOB_ID: job}, cohorts={'development': {'tasks': tasks}},
        snapshot_id='same-snapshot', runtime_binding={'runtime': 'same'}))
    source_attempt = b.source_attempt_directory()
    rewrite(source_attempt / 'launch/record.json', dict(protocol_id=scientific['id'],
        job=dict(job, kind='generate'), attempt=1, pid=b.TARGET_PID, birth=b.TARGET_BIRTH, gpu_index=0))
    generation = b.target_directory() / 'shards' / job['panel'] / 'generation'
    rewrite(generation / 'run.json', dict(config=job['config'], provider=job['model_identity'],
        tasks=tasks, role='development', snapshot_id='same-snapshot', runtime_binding={'runtime': 'same'},
        registered_denominator=883))
    (b.target_directory() / 'worker.lock').touch()
    (generation / 'generation.lock').touch()
    rewrite(generation / 'episodes/episode0/episode.json', {'unchanged_episode': True})
    rewrite(generation / 'durable_returns/episode0/turn0000/record.json', {'turn_index': 0})
    rewrite(generation / 'call_attempts/episode0/turn0000/source/intent/record.json',
            {'episode_key': 'episode0', 'turn_index': 0})
    actual = rewrite(source_attempt / 'actual_exit/record.json', dict(protocol_id=scientific['id'],
        job_id=b.TARGET_JOB_ID, attempt=1, returncode=1, actual_waitpid_observed=True,
        pid=b.TARGET_PID, birth=b.TARGET_BIRTH, gpu_index=0, observed_epoch=103.0))
    resources = dict(all_gates_passed=True, single_process_lifetime_includes_loading=True,
        observed_violation=None, deferred_observation=None, peak_allocated_bytes=22 * bridge.GIB,
        peak_rss_bytes=12 * bridge.GIB, minimum_boundary_free_bytes=5 * bridge.GIB,
        minimum_host_available_bytes=400 * bridge.GIB,
        received_signals=[{'signal': 15, 'received_at_epoch': 101.0}])
    closed_path = source / 'resources' / b.TARGET_JOB_ID / f'pid{b.TARGET_PID}' / 'closeout/record.json'
    rewrite(closed_path, dict(status='FAILED_OR_STOPPED', protocol_id=scientific['id'], job_id=b.TARGET_JOB_ID,
        pid=b.TARGET_PID, birth=b.TARGET_BIRTH, gpu_index=0, error={'type': 'ExplicitStop'}, resources=resources))
    failure = rewrite(source_attempt / 'failure/record.json', dict(protocol_id=scientific['id'],
        pid=b.TARGET_PID, job=dict(job, kind='generate'), attempt_root=str(source_attempt),
        exception_type='ExplicitStop', exception_chain=[{'type': 'ExplicitStop'}],
        resources=resources, resource_closeout=b.entry(closed_path)))
    rewrite(source / 'journal/state.json', dict(protocol_id=scientific['id'],
        job_states={b.TARGET_JOB_ID: {'status': 'HARD_BLOCKED'}}, active_jobs=[]))
    protocol = rewrite(root / 'protocol/record.json', dict(
        source_protocol=b.entry(source / 'protocol/record.json'),
        source_plan=b.entry(source / 'evaluations/registration/record.json'),
        source_launch=b.entry(source_attempt / 'launch/record.json'), target_job=job,
        source_protocol_id=scientific['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        target={'job_id': b.TARGET_JOB_ID, 'pid': b.TARGET_PID, 'birth': b.TARGET_BIRTH, 'gpu_index': 0, 'attempt': 1},
        destination={'gpu_index': 6, 'uuid': 'GPU-six'}))
    rewrite(root / 'signal/record.json', dict(protocol_id=protocol['id'], target_pid=b.TARGET_PID,
        target_birth=b.TARGET_BIRTH, signal=15, sender_uid=1004, sender_pid=222222,
        sender_birth='sender-birth', sent_epoch=100.0))
    receipt = dict(schema='v59_received_signal_kernel_receipt.v1', pid=b.TARGET_PID, signal=15,
        si_pid=222222, si_uid=1004, si_code=0, provenance='kernel_sigwaitinfo', at_epoch=101.0,
        decision={'dispatch_original_stop': True, 'action': 'DISPATCH_ORIGINAL_STOP', 'filtered': False})
    log = source_attempt / 'signals/received.jsonl'
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(receipt) + '\n')
    audits = dict(resume_allowed=True, unknown_calls=0, complete_stage=False,
        durable_progress_digest='actual-prefix', details={'feedback_audit': dict(
            resume_allowed=True, unknown_calls=0, complete_generation=False,
            complete_episodes=1, actual_returned_turns=1)})
    worker = SimpleNamespace(audit_job_resume=lambda *_: deepcopy(audits))
    runtime = SimpleNamespace(worker_environment=lambda row: {
        'OMP_NUM_THREADS': '8', 'CUBLAS_WORKSPACE_CONFIG': ':4096:8', 'old-env': 'preserved'})
    modules = {'finqa_v67_evaluation': SimpleNamespace(planned_jobs=lambda: {b.TARGET_JOB_ID: original_job}),
               'finqa_v67_worker': worker, 'finqa_v67_runtime': runtime}
    monkeypatch.setattr(b, 'completion_module', lambda name: modules[name])
    monkeypatch.setattr(b, 'install_scientific_paths', lambda: {'frozen_source_root': '/actual/frozen-source'})
    appended = []
    def append(path, body):
        path = Path(path)
        allowed = {b.destination_attempt_directory() / part / 'record.json'
                   for part in ('migration_binding', 'dispatch_intent', 'launch', 'actual_exit')}
        allowed.add(b.target_directory() / 'accepted/record.json')
        assert path in allowed and not path.exists()
        appended.append(path)
        return rewrite(path, body)
    monkeypatch.setattr(b, 'append_target_record', append)
    return SimpleNamespace(root=root, source=source, scientific=scientific, protocol=protocol,
        job=job, plan=plan, generation=generation, resources=resources, audits=audits,
        failure=failure, actual=actual, log=log, receipt=receipt, appended=appended)


def test_post_exit_baseline_preserves_actual_failure_and_full_prefix(environment):
    e = environment
    original = b.source_attempt_directory() / 'failure/record.json'
    before = original.read_bytes()
    baseline = bridge.audit_paused_source(e.root)
    assert baseline['unknown_calls'] == 0 and baseline['complete_episodes'] == 1
    assert baseline['source_job_status'] == 'HARD_BLOCKED'
    assert len(baseline['prefix']['files']) == 3
    assert baseline['prefix']['complete_episode_keys'] == ['episode0']
    assert baseline['prefix']['returned_turns'][0]['turn_index'] == 0
    assert baseline['signal_evidence']['kernel_receipt']['si_pid'] == 222222
    assert original.read_bytes() == before and not e.appended


@pytest.mark.parametrize('change', ['unknown', 'hardgate', 'foreign_signal', 'source_live', 'nonsettled', 'failure_type'])
def test_unsafe_or_unrelated_source_stop_never_authorizes_migration(environment, monkeypatch, change):
    e = environment
    if change == 'unknown':
        e.audits['unknown_calls'] = 1
    elif change == 'hardgate':
        failure = deepcopy(e.failure)
        failure['resources']['peak_allocated_bytes'] = 77 * bridge.GIB
        path = Path(failure['resource_closeout']['path'])
        closed = b.checked(path)
        rewrite(path, {**closed, 'resources': failure['resources']})
        failure['resource_closeout'] = b.entry(path)
        rewrite(b.source_attempt_directory() / 'failure/record.json', failure)
    elif change == 'foreign_signal':
        e.log.write_text(json.dumps({**e.receipt, 'si_pid': 333333}) + '\n')
    elif change == 'source_live':
        monkeypatch.setattr(bridge, '_live', lambda *_: True)
    elif change == 'nonsettled':
        rewrite(e.source / 'journal/state.json', dict(protocol_id=e.scientific['id'],
            job_states={b.TARGET_JOB_ID: {'status': 'SETTLING_EXIT'}}, active_jobs=[]))
    else:
        rewrite(b.source_attempt_directory() / 'failure/record.json', {**e.failure,
            'exception_type': 'ResourceDeferred', 'exception_chain': [{'type': 'ResourceDeferred'}]})
    with pytest.raises(ValueError):
        bridge.audit_paused_source(e.root)
    assert not (e.root / 'baseline/record.json').exists() and not e.appended


def test_known_zero_call_stop_can_resume_but_other_pre_call_pause_cannot(environment):
    e = environment
    closed_path = Path(e.failure['resource_closeout']['path'])
    closed = b.checked(closed_path)
    rewrite(closed_path, {**closed, 'error': {'type': 'GenerationPreCallPause'}})
    rewrite(b.source_attempt_directory() / 'failure/record.json', {**e.failure,
        'exception_type': 'GenerationPreCallPause', 'exception_chain': [{'type': 'GenerationPreCallPause'}],
        'resource_closeout': b.entry(closed_path)})
    with pytest.raises(ValueError, match='zero-call'):
        bridge.audit_paused_source(e.root)
    rewrite(e.generation / 'call_attempts/episode1/turn0000/source/settlement/record.json', dict(
        settlement='pre_call_rejected', actual_model_calls=0,
        evidence={'evidence': {'exception_type': 'ExplicitStop'}}))
    assert bridge.audit_paused_source(e.root)['zero_call_pause_evidence']


def test_original_native_lock_must_be_released_without_creating_or_rewriting_it(environment):
    e = environment
    lock_path = e.generation / 'generation.lock'
    with lock_path.open('r') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='lock is still owned'):
            bridge.audit_paused_source(e.root)
    assert not (e.root / 'baseline/record.json').exists()
    assert lock_path.read_bytes() == b''


def invoke(e):
    baseline = bridge.audit_paused_source(e.root)
    lease_path = Path(e.scientific['gpu_lease_root']) / ('gpu-' + b.digest('GPU-six') + '.lock')
    lease_path.parent.mkdir(parents=True)
    lease = lease_path.open('a')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    invocation = bridge.worker_invocation(e.root, baseline, lease.fileno())
    return baseline, invocation, lease


def test_launch_reuses_exact_frozen_worker_and_all_original_aliases(environment):
    e = environment
    baseline, launch, lease = invoke(e)
    try:
        assert launch['gpu_index'] == 6 and launch['gpu_uuid'] == 'GPU-six'
        assert launch['command'][:3] == ['/usr/bin/taskset', '--cpu-list', '16-23']
        assert str(e.source / 'implementation/finqa_v67_entry.py') in launch['command']
        env = launch['environment']
        assert env['V67_CONTROL_PROTOCOL_ID'] == e.scientific['id'] != e.protocol['id']
        assert env['CUDA_VISIBLE_DEVICES'] == 'GPU-six' and env['OMP_NUM_THREADS'] == '8'
        for version in ('V67', 'V63', 'V56'):
            assert env[version + '_ATTEMPT_DIR'] == str(b.destination_attempt_directory())
            assert env[version + '_ATTEMPT_ID'] == 'attempt0002'
        assert env['V56_JOB_ATTEMPT_ROOT'] == str(b.destination_attempt_directory())
        assert len(e.appended) == 2
        with pytest.raises(ValueError, match='one cold destination'):
            bridge.worker_invocation(e.root, baseline, lease.fileno())
    finally:
        lease.close()


def test_missing_exclusive_GPU6_lease_and_changed_prefix_rejected(environment):
    e = environment
    baseline = bridge.audit_paused_source(e.root)
    lease_path = Path(e.scientific['gpu_lease_root']) / ('gpu-' + b.digest('GPU-six') + '.lock')
    lease_path.parent.mkdir(parents=True)
    with lease_path.open('a') as lease:
        with pytest.raises(ValueError, match='exclusive flock'):
            bridge.worker_invocation(e.root, baseline, lease.fileno())
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rewrite(e.generation / 'episodes/episode0/episode.json', {'changed': True})
        with pytest.raises(ValueError, match='changed'):
            bridge.worker_invocation(e.root, baseline, lease.fileno())
    assert not e.appended


def prepare_complete(e, baseline, invocation):
    bridge.publish_launch(e.root, baseline, 444444, '22222', invocation['command'], {'actual_admission': True})
    actual_path = e.root / 'worker/actual_exit/record.json'
    rewrite(actual_path, dict(protocol_id=e.protocol['id'], job_id=b.TARGET_JOB_ID, pid=444444,
        birth='22222', gpu_index=6, returncode=0, actual_waitpid_observed=True, observed_epoch=200.0))
    protection = dict(policy=e.scientific['memory_protection_policy'],
                      future_capacity_or_exclusivity_guaranteed=False, warm_attempted=False)
    resources = dict(e.resources, received_signals=[], control_protocol_id=e.scientific['id'],
                     resource_protection=protection)
    rewrite(e.source / 'resources' / b.TARGET_JOB_ID / 'pid444444/closeout/record.json', dict(
        status='COMPLETE', protocol_id=e.scientific['id'], job_id=b.TARGET_JOB_ID, resources=resources,
        pid=444444, birth='22222', gpu_index=6))
    rewrite(b.target_directory() / 'result/record.json', dict(schema='v67_generation_only_job_result.v1',
        registration_id=e.plan['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID, job_id=b.TARGET_JOB_ID,
        status='COMPLETE', sessions=883, feedback_batch=1, scoring_calls=0, private_references_read=False,
        resources=resources, actual_new_response_calls=882))
    e.audits['complete_stage'] = True
    e.audits['details']['feedback_audit'].update(complete_generation=True, complete_episodes=883,
                                               actual_returned_turns=883)
    return actual_path


def test_real_new_exit_acceptance_preserves_legacy_HARD_and_old_actual_exit(environment):
    e = environment
    baseline, invocation, lease = invoke(e)
    try:
        old_exit = (b.source_attempt_directory() / 'actual_exit/record.json').read_bytes()
        journal = (e.source / 'journal/state.json').read_bytes()
        actual_path = prepare_complete(e, baseline, invocation)
        done = bridge.accept_resumed_target(e.root, baseline, b.entry(actual_path))
        accepted = done['accepted']
        assert accepted['attempt'] == 2 and accepted['actual_exit_zero']
        assert accepted['protocol_id'] == e.scientific['id']
        assert accepted['migration_authorization']['id'] == e.protocol['id']
        assert done['result']['all_original_episode_and_return_hashes_unchanged']
        assert done['result']['new_provider_calls_for_saved_episodes_or_returned_turns'] == 0
        assert (b.source_attempt_directory() / 'actual_exit/record.json').read_bytes() == old_exit
        assert (e.source / 'journal/state.json').read_bytes() == journal
    finally:
        lease.close()


def test_new_call_for_existing_return_is_rejected_before_acceptance(environment):
    e = environment
    baseline, invocation, lease = invoke(e)
    try:
        actual_path = prepare_complete(e, baseline, invocation)
        rewrite(e.generation / 'call_attempts/episode0/turn0000/destination/intent/record.json',
                {'episode_key': 'episode0', 'turn_index': 0})
        with pytest.raises(ValueError, match='already complete episode or returned turn'):
            bridge.accept_resumed_target(e.root, baseline, b.entry(actual_path))
        assert not (b.target_directory() / 'accepted/record.json').exists()
        assert b.checked(b.destination_attempt_directory() / 'actual_exit/record.json')['returncode'] == 0
    finally:
        lease.close()


def test_failed_actual_new_exit_is_recorded_but_never_accepted_or_retried(environment):
    e = environment
    baseline, invocation, lease = invoke(e)
    try:
        actual_path = prepare_complete(e, baseline, invocation)
        actual = b.checked(actual_path)
        rewrite(actual_path, {**actual, 'returncode': 1})
        with pytest.raises(ValueError, match='no automatic retry'):
            bridge.accept_resumed_target(e.root, baseline, b.entry(actual_path))
        assert b.checked(b.destination_attempt_directory() / 'actual_exit/record.json')['returncode'] == 1
        assert not (b.target_directory() / 'accepted/record.json').exists()
    finally:
        lease.close()
