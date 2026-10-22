"""One append-only, same-point generation continuation on physical GPU6.

This bridge never sends a signal, starts a process or changes a frozen source.
The coordinator owns GPU6 admission, the sole authorized pause and real waitpid.
Only the existing target's new attempt0002 and final acceptance are appended;
the legacy controller's HARD_BLOCKED state is historical and is not rewritten.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
import fcntl
import os
from pathlib import Path
import signal
import stat

import finqa_v69_binding as b

GIB = 1024 ** 3
require = b.require


def _live(pid, birth):
    try:
        values = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return values[19] == str(birth) and values[0] not in ('Z', 'X', 'x')


def _at(reference, path):
    require(Path(reference['path']).resolve() == Path(path).resolve(),
            'migration reference escaped its exact registered source')
    return b.read_ref(reference)


def _context(root):
    root = Path(root).resolve()
    require(root == Path(b.ROOT).resolve(), 'one-job bridge requires its independent migration root')
    protocol = b.checked(root / 'protocol/record.json')
    source = _at(protocol['source_protocol'], b.COMPLETION_ROOT / 'protocol/record.json')
    plan = _at(protocol['source_plan'], b.COMPLETION_ROOT / 'evaluations/registration/record.json')
    launch = _at(protocol['source_launch'], b.source_attempt_directory() / 'launch/record.json')
    job = plan['jobs'][b.TARGET_JOB_ID]
    target = protocol['target']
    require(source['id'] == protocol['source_protocol_id'] == b.COMPLETION_PROTOCOL_ID
            and plan['protocol_id'] == source['id']
            and plan['scientific_protocol_id'] == protocol['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
            and protocol['target_job'] == job
            and target['job_id'] == b.TARGET_JOB_ID
            and (target['pid'], target['birth'], target['gpu_index'], target['attempt'])
                == (b.TARGET_PID, b.TARGET_BIRTH, b.SOURCE_GPU, b.SOURCE_ATTEMPT)
            and protocol['destination']['gpu_index'] == b.DEST_GPU == 6
            and protocol['destination']['uuid'] == source['gpu_uuids']['6']
            and (job['seed'], job['arm'], job['feedback_batch'], job['step'], job['denominator'])
                == (389, 'C05', 1, 894, 883)
            and job['stage'] == 'generate',
            'only the registered seed389/C05 dev883 task may move once from GPU0 to GPU6')
    require(launch['protocol_id'] == source['id'] and launch['attempt'] == b.SOURCE_ATTEMPT
            and (launch['pid'], launch['birth'], launch['gpu_index'])
                == (b.TARGET_PID, b.TARGET_BIRTH, b.SOURCE_GPU)
            and all(launch['job'].get(key) == value for key, value in job.items()),
            'source dispatch no longer names the authorized actual worker and model point')
    expected = b.completion_module('finqa_v67_evaluation').planned_jobs()[b.TARGET_JOB_ID]
    require(all(job.get(key) == value for key, value in expected.items()),
            'migration cannot change the original panel, task dose, seed or decoding')
    generation = b.target_directory() / 'shards' / job['panel'] / 'generation'
    run = b.checked(generation / 'run.json')
    require(run['config'] == job['config'] and run['provider'] == job['model_identity']
            and run['tasks'] == plan['cohorts'][job['role']]['tasks']
            and run['role'] == job['role'] and run['snapshot_id'] == plan['snapshot_id']
            and run['runtime_binding'] == plan['runtime_binding']
            and run['registered_denominator'] == 883,
            'same native run, model, original task order and source binding are mandatory')
    return root, protocol, source, plan, job, generation, run


def _pause_resources(closed, failure, actual, source_id):
    resources = closed['resources']
    require(closed['status'] == 'FAILED_OR_STOPPED'
            and closed['protocol_id'] == source_id and closed['job_id'] == b.TARGET_JOB_ID
            and (closed['pid'], closed['birth'], closed['gpu_index'])
                == (actual['pid'], actual['birth'], b.SOURCE_GPU)
            and closed['error']['type'] in ('ExplicitStop', 'GenerationPreCallPause')
            and failure['resources'] == resources
            and resources['all_gates_passed'] is True
            and resources['single_process_lifetime_includes_loading'] is True
            and resources.get('observed_violation') is None
            and resources.get('deferred_observation') is None
            and resources['peak_allocated_bytes'] <= 76 * GIB
            and resources['peak_rss_bytes'] <= 192 * GIB
            and resources['minimum_boundary_free_bytes'] >= 2 * GIB
            and resources['minimum_host_available_bytes'] >= 96 * GIB
            and [row['signal'] for row in resources['received_signals']] == [int(signal.SIGTERM)],
            'only the authorized graceful signal stop with all original hard gates passed is migratable')
    return resources


def _signal_evidence(root, protocol, actual):
    path = root / 'signal/record.json'
    sent = b.checked(path)
    require(sent['protocol_id'] == protocol['id']
            and sent['target_pid'] == b.TARGET_PID and sent['target_birth'] == b.TARGET_BIRTH
            and sent['signal'] == int(signal.SIGTERM)
            and sent['sender_uid'] == b.OWNER_UID == 1004
            and type(sent['sender_pid']) is int and sent['sender_pid'] > 0,
            'one recorded owner-UID migration signal is required')
    receipts, files = [], []
    for log in sorted((b.source_attempt_directory() / 'signals').glob('received.jsonl*')):
        require(log.is_file() and not log.is_symlink(), 'source signal receipt must be an ordinary file')
        files.append(b.file_ref(log))
        for line in log.read_text().splitlines():
            row = json.loads(line)
            if (row.get('schema') == 'v59_received_signal_kernel_receipt.v1'
                    and row.get('decision', {}).get('dispatch_original_stop') is True):
                receipts.append(row)
    require(len(receipts) == 1, 'migration requires one unambiguous original-stop kernel receipt')
    receipt = receipts[0]
    require(receipt['pid'] == b.TARGET_PID and receipt['signal'] == int(signal.SIGTERM)
            and receipt['si_pid'] == sent['sender_pid'] and receipt['si_uid'] == sent['sender_uid']
            and receipt['si_code'] == 0 and receipt['provenance'] == 'kernel_sigwaitinfo'
            and receipt['decision']['action'] == 'DISPATCH_ORIGINAL_STOP'
            and receipt['decision']['filtered'] is False
            and sent['sent_epoch'] - 1 <= receipt['at_epoch'] <= actual['observed_epoch'],
            'the stop must match this coordinator signal, not an inferred or unrelated sender')
    return dict(sent=b.entry(path), kernel_receipt=receipt, receipt_files=files)


def _prefix(generation):
    files, complete, returned, intents = {}, [], [], []
    patterns = ('episodes/*/episode.json', 'complete_candidates/*/record.json',
                'durable_returns/*/turn*/record.json', 'durable_tools/*/tool*/record.json',
                'call_attempts/*/turn*/*/*/record.json')
    for pattern in patterns:
        for path in sorted(generation.glob(pattern)):
            require(path.is_file() and not path.is_symlink(), 'native prefix file may not alias another target')
            relative = path.relative_to(generation).as_posix()
            files[relative] = b.file_ref(path)
            if relative.startswith(('episodes/', 'complete_candidates/')):
                complete.append(path.parent.name)
            elif relative.startswith('durable_returns/'):
                row = b.checked(path)
                returned.append(dict(episode_key=path.parent.parent.name, turn_index=row['turn_index'],
                                     reference=files[relative]))
            elif relative.startswith('call_attempts/') and path.parent.name == 'intent':
                intents.append(relative)
    return dict(files=files, complete_episode_keys=sorted(set(complete)), returned_turns=returned,
                existing_call_intents=intents, prefix_files_digest=b.digest(files))


def _probe_source_locks(generation):
    """Read-only handles; never create, truncate or keep a legacy worker lock."""
    paths = [b.target_directory() / 'worker.lock', generation / 'generation.lock']
    with ExitStack() as stack:
        for path in paths:
            require(path.is_file() and not path.is_symlink(), 'original generation lock is missing or aliased')
            handle = stack.enter_context(path.open('r'))
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('original job or native generation lock is still owned') from error
    return [str(path) for path in paths]


def audit_paused_source(root):
    """Called only after the old controller observed the real stopped exit."""
    root, protocol, source, plan, job, generation, run = _context(root)
    attempt = b.source_attempt_directory()
    actual = b.checked(attempt / 'actual_exit/record.json')
    require(actual['protocol_id'] == source['id'] and actual['job_id'] == b.TARGET_JOB_ID
            and actual['attempt'] == 1 and actual['returncode'] == 1
            and actual['actual_waitpid_observed'] is True
            and (actual['pid'], actual['birth'], actual['gpu_index'])
                == (b.TARGET_PID, b.TARGET_BIRTH, b.SOURCE_GPU)
            and not _live(actual['pid'], actual['birth']),
            'source must have its own real graceful exit one; no live or killed process may migrate')
    journal = b.checked(b.COMPLETION_ROOT / 'journal/state.json')
    require(journal['protocol_id'] == source['id']
            and journal['job_states'][b.TARGET_JOB_ID]['status'] == 'HARD_BLOCKED'
            and all(row['job_id'] != b.TARGET_JOB_ID for row in journal['active_jobs']),
            'the old controller must settle this explicit stop without rewriting its terminal disposition')
    require(not (b.target_directory() / 'result/record.json').exists()
            and not (b.target_directory() / 'accepted/record.json').exists()
            and not b.destination_attempt_directory().exists(),
            'complete work or a previous destination attempt must never be regenerated')
    source_locks = _probe_source_locks(generation)
    failure = b.checked(attempt / 'failure/record.json')
    chain = {row['type'] for row in failure['exception_chain']}
    require(failure['protocol_id'] == source['id'] and failure['pid'] == b.TARGET_PID
            and failure['attempt_root'] == str(attempt)
            and failure['exception_type'] in ('ExplicitStop', 'GenerationPreCallPause')
            and chain <= {'ExplicitStop', 'GenerationPreCallPause'}
            and all(failure['job'].get(key) == value for key, value in job.items()),
            'only this known graceful stop, not a resource, numeric, binding or UNKNOWN failure, may migrate')
    close_path = b.COMPLETION_ROOT / 'resources' / b.TARGET_JOB_ID / f'pid{b.TARGET_PID}' / 'closeout/record.json'
    closed = _at(failure['resource_closeout'], close_path)
    resources = _pause_resources(closed, failure, actual, source['id'])
    signal_evidence = _signal_evidence(root, protocol, actual)
    worker = b.completion_module('finqa_v67_worker')
    audit = worker.audit_job_resume(b.COMPLETION_ROOT, dict(job, kind='generate'))
    native_audit = audit['details']['feedback_audit']
    require(audit['resume_allowed'] is True and audit['unknown_calls'] == 0
            and native_audit['resume_allowed'] is True and native_audit['unknown_calls'] == 0
            and native_audit['complete_generation'] is False,
            'UNKNOWN or already complete generation cannot enter a new migration attempt')
    prefix = _prefix(generation)
    if failure['exception_type'] == 'GenerationPreCallPause':
        zero = []
        for relative, reference in prefix['files'].items():
            if relative.startswith('call_attempts/') and '/settlement/' in relative:
                row = b.read_ref(reference)
                if row.get('settlement') == 'pre_call_rejected' and row.get('actual_model_calls') == 0:
                    detail = row.get('evidence', {}).get('evidence', {})
                    if detail.get('exception_type') == 'ExplicitStop':
                        zero.append(reference)
        require(zero, 'pre-call pause must retain actual zero-call ExplicitStop settlement evidence')
    else:
        zero = []
    body = dict(schema='v69_actual_stopped_same_point_prefix_baseline.v1',
        protocol_id=protocol['id'], source_protocol_id=source['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        status='READY_FOR_ONE_GPU6_CONTINUATION', job_id=b.TARGET_JOB_ID, job=job,
        generation_root=str(generation), native_run=b.entry(generation / 'run.json'),
        original_generation_registration=protocol['source_plan'], source_launch=protocol['source_launch'],
        source_actual_exit=b.entry(attempt / 'actual_exit/record.json'), source_failure=b.entry(attempt / 'failure/record.json'),
        source_resource_closeout=failure['resource_closeout'], source_resources=resources,
        signal_evidence=signal_evidence, zero_call_pause_evidence=zero,
        complete_episodes=native_audit['complete_episodes'], actual_returned_turns=native_audit['actual_returned_turns'],
        durable_progress_digest=audit['durable_progress_digest'], unknown_calls=0, prefix=prefix,
        source_job_status='HARD_BLOCKED', source_job_status_not_rewritten=True,
        source_worker_and_generation_locks_observed_released=source_locks,
        source_gpu=0, destination_gpu=6, source_attempt=1, destination_attempt=2,
        existing_outputs_copied=False, existing_returned_turns_replayed=False,
        scientific_task_order_model_seed_and_config_unchanged=True)
    return b.publish(root / 'baseline/record.json', body)


def _checked_baseline(root, baseline):
    current = b.checked(Path(root) / 'baseline/record.json')
    require(current == baseline and baseline['status'] == 'READY_FOR_ONE_GPU6_CONTINUATION'
            and baseline['job_id'] == b.TARGET_JOB_ID and baseline['unknown_calls'] == 0,
            'only this immutable post-exit baseline authorizes the single continuation')
    return current


def _verify_prefix(baseline, generation, *, after=False):
    b.read_ref(baseline['native_run'])
    for reference in baseline['prefix']['files'].values():
        require(b.sha(reference['path']) == reference['sha256'],
                'an existing complete episode, returned turn or original call record changed')
    if after:
        returned = {(row['episode_key'], row['turn_index']) for row in baseline['prefix']['returned_turns']}
        complete = set(baseline['prefix']['complete_episode_keys'])
        old = set(baseline['prefix']['existing_call_intents'])
        for path in generation.glob('call_attempts/*/turn*/*/intent/record.json'):
            if path.relative_to(generation).as_posix() in old:
                continue
            intent = b.checked(path)
            require(intent['episode_key'] not in complete
                    and (intent['episode_key'], intent['turn_index']) not in returned,
                    'destination attempted a new provider call for an already complete episode or returned turn')


def _lease(fd, source):
    require(type(fd) is int and fd >= 0, 'one real inherited GPU6 lease descriptor required')
    expected = Path(source['gpu_lease_root']) / ('gpu-' + b.digest(source['gpu_uuids']['6']) + '.lock')
    actual, target = os.fstat(fd), expected.stat()
    require(Path(os.readlink(f'/proc/self/fd/{fd}')).resolve() == expected.resolve()
            and stat.S_ISREG(actual.st_mode) and (actual.st_dev, actual.st_ino) == (target.st_dev, target.st_ino),
            'destination must inherit the exact original GPU6 secondary-lane inode')
    lines = [line.split() for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()
             if line.startswith('lock:')]
    require(any('FLOCK' in line and 'WRITE' in line for line in lines),
            'GPU6 secondary-lane descriptor does not hold its exclusive flock')
    return dict(path=str(expected.resolve()), descriptor=fd, device=actual.st_dev, inode=actual.st_ino,
                held_exclusive_flock=True, lane='registered_V67_secondary')


def worker_invocation(root, baseline, lease_fd):
    root, protocol, source, plan, job, generation, run = _context(root)
    _checked_baseline(root, baseline)
    _verify_prefix(baseline, generation)
    require(not _live(b.TARGET_PID, b.TARGET_BIRTH) and not b.destination_attempt_directory().exists(),
            'only one cold destination attempt is authorized after the actual source exit')
    lease = _lease(lease_fd, source)
    attempt = b.destination_attempt_directory()
    worker_job = dict(job, kind='generate')
    authorization = b.entry(root / 'protocol/record.json')
    baseline_ref = b.entry(root / 'baseline/record.json')
    b.append_target_record(attempt / 'migration_binding/record.json', dict(
        schema='v69_one_authorized_append_only_generation_attempt.v1', protocol_id=source['id'],
        job_id=b.TARGET_JOB_ID, attempt=2, migration_authorization=authorization,
        migration_baseline=baseline_ref, original_source_actual_exit=baseline['source_actual_exit'],
        original_failure_and_controller_HARD_state_preserved=True, GPU6_lease=lease))
    b.append_target_record(attempt / 'dispatch_intent/record.json', dict(
        schema='v63_cold_attempt_dispatch_intent.v1', protocol_id=source['id'], job=worker_job,
        attempt=2, gpu_index=6, gpu_uuid=source['gpu_uuids']['6'],
        migration_authorization=authorization, migration_baseline=baseline_ref,
        original_completed_prefix_not_replayed=True))
    runtime = b.completion_module('finqa_v67_runtime')
    row = dict(index=6, uuid=source['gpu_uuids']['6'])
    environment = runtime.worker_environment(row)
    environment.update(CUDA_VISIBLE_DEVICES=row['uuid'], V54_GPU_LEASE_FD=str(lease_fd),
        V54_JOB_ID=b.TARGET_JOB_ID, V67_CONTROL_ROOT=str(b.COMPLETION_ROOT),
        V67_CONTROL_PROTOCOL_ID=source['id'],
        PYTHONPATH=os.pathsep.join((str(b.COMPLETION_ROOT / 'implementation'),
                                  b.install_scientific_paths()['frozen_source_root'])))
    for version in ('V67', 'V63', 'V56'):
        environment[version + '_ATTEMPT_DIR'] = str(attempt)
        environment[version + '_ATTEMPT_ID'] = attempt.name
    # Remove a parent alias that could otherwise override this exact attempt.
    environment['V56_JOB_ATTEMPT_ROOT'] = str(attempt)
    command = ['/usr/bin/taskset', '--cpu-list', source['cpu_affinity']['6'], str(b.PYTHON), '-u',
        str(b.COMPLETION_ROOT / 'implementation/finqa_v67_entry.py'), '--mode', 'generate',
        '--root', str(b.COMPLETION_ROOT), '--job', b.TARGET_JOB_ID, '--gpu', '6',
        '--attempt-root', str(attempt)]
    return dict(command=command, environment=environment, attempt_root=str(attempt), job=worker_job,
                gpu_index=6, gpu_uuid=row['uuid'], lease=lease, migration_baseline=baseline_ref,
                migration_authorization=authorization)


def publish_launch(root, baseline, pid, birth, command, admission):
    root, protocol, source, plan, job, generation, run = _context(root)
    _checked_baseline(root, baseline)
    require(type(pid) is int and pid > 0 and isinstance(birth, str) and birth.isdigit(),
            'actual destination PID and birth identity are required')
    require('--gpu' in command and command[command.index('--gpu') + 1] == '6'
            and str(b.COMPLETION_ROOT / 'implementation/finqa_v67_entry.py') in command
            and command[-1] == str(b.destination_attempt_directory()),
            'launch must use the original frozen V67 entry and only the GPU6 second attempt')
    return b.append_target_record(b.destination_attempt_directory() / 'launch/record.json', dict(
        schema='v63_actual_attempt_launch.v1', protocol_id=source['id'], job=dict(job, kind='generate'),
        attempt=2, pid=pid, birth=birth, gpu_index=6, gpu_uuid=source['gpu_uuids']['6'], command=command,
        admission=admission, inherited_gpu_lease=True,
        migration_authorization=b.entry(root / 'protocol/record.json'),
        migration_baseline=b.entry(root / 'baseline/record.json')))


def accept_resumed_target(root, baseline, actual_exit_ref):
    """Consume coordinator waitpid evidence; never manufacture an old success."""
    root, protocol, source, plan, job, generation, run = _context(root)
    _checked_baseline(root, baseline)
    require(Path(actual_exit_ref['path']).resolve().is_relative_to(root),
            'destination actual waitpid must be observed by this migration coordinator')
    actual = b.read_ref(actual_exit_ref)
    attempt = b.destination_attempt_directory()
    launch = b.checked(attempt / 'launch/record.json')
    require(actual['protocol_id'] == protocol['id'] and actual['job_id'] == b.TARGET_JOB_ID
            and actual['actual_waitpid_observed'] is True and type(actual['returncode']) is int
            and (actual['pid'], actual['birth']) == (launch['pid'], launch['birth'])
            and actual['gpu_index'] == launch['gpu_index'] == 6
            and launch['protocol_id'] == source['id'] and launch['attempt'] == 2
            and not _live(actual['pid'], actual['birth']),
            'destination acceptance requires this actual child exit and unchanged launch identity')
    b.append_target_record(attempt / 'actual_exit/record.json', dict(
        schema='v63_actual_attempt_worker_exit.v1', protocol_id=source['id'], job_id=b.TARGET_JOB_ID,
        attempt=2, pid=actual['pid'], birth=actual['birth'], gpu_index=6,
        returncode=actual['returncode'], actual_waitpid_observed=True, observed_epoch=actual['observed_epoch'],
        migration_authorization=b.entry(root / 'protocol/record.json'),
        migration_controller_actual_exit=actual_exit_ref))
    require(actual['returncode'] == 0, 'destination attempt failed: retain actual exit; no automatic retry')
    require(not (attempt / 'failure/record.json').exists(), 'failed destination cannot be accepted')
    _verify_prefix(baseline, generation, after=True)
    worker = b.completion_module('finqa_v67_worker')
    audit = worker.audit_job_resume(b.COMPLETION_ROOT, dict(job, kind='generate'))
    native = audit['details']['feedback_audit']
    require(audit['resume_allowed'] is True and audit['unknown_calls'] == 0 and audit['complete_stage'] is True
            and native['complete_generation'] is True and native['complete_episodes'] == 883,
            'destination requires every original episode and no UNKNOWN calls')
    result_path = b.target_directory() / 'result/record.json'
    result = b.checked(result_path)
    resources = result['resources']
    closed_path = b.COMPLETION_ROOT / 'resources' / b.TARGET_JOB_ID / f"pid{actual['pid']}" / 'closeout/record.json'
    closed = b.checked(closed_path)
    protection = resources.get('resource_protection', {})
    require(result['schema'] == 'v67_generation_only_job_result.v1'
            and result['registration_id'] == plan['id'] and result['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
            and result['job_id'] == b.TARGET_JOB_ID and result['status'] == 'COMPLETE'
            and result['sessions'] == 883 and result['feedback_batch'] == 1
            and result['scoring_calls'] == 0 and result['private_references_read'] is False
            and closed['status'] == 'COMPLETE' and closed['protocol_id'] == source['id']
            and closed['job_id'] == b.TARGET_JOB_ID and closed['resources'] == resources
            and (closed['pid'], closed['birth'], closed['gpu_index']) == (actual['pid'], actual['birth'], 6)
            and resources['all_gates_passed'] is True and resources['single_process_lifetime_includes_loading'] is True
            and resources['received_signals'] == [] and resources.get('observed_violation') is None
            and resources.get('deferred_observation') is None
            and resources['peak_allocated_bytes'] <= 76 * GIB and resources['peak_rss_bytes'] <= 192 * GIB
            and resources['minimum_boundary_free_bytes'] >= 2 * GIB
            and resources['minimum_host_available_bytes'] >= 96 * GIB
            and resources['control_protocol_id'] == source['id']
            and protection['policy'] == source['memory_protection_policy']
            and protection['future_capacity_or_exclusivity_guaranteed'] is False
            and protection['warm_attempted'] is False,
            'destination must pass the unchanged same-process generation resource and no-scoring contracts')
    require(type(result['actual_new_response_calls']) is int and result['actual_new_response_calls'] >= 0
            and native['actual_returned_turns'] - baseline['actual_returned_turns']
                == result['actual_new_response_calls'],
            'physical destination calls must exactly equal new durable returns, not a reconstructed saved prefix')
    for reference in (baseline['source_launch'], baseline['source_actual_exit'], baseline['source_failure'],
                      baseline['source_resource_closeout']):
        b.read_ref(reference)
    acceptance_path = b.target_directory() / 'accepted/record.json'
    accepted = b.append_target_record(acceptance_path, dict(
        schema='v63_actual_attempt_exit_and_result_accepted.v1', protocol_id=source['id'],
        job_id=b.TARGET_JOB_ID, attempt=2, result=b.file_ref(result_path), result_id=result['id'],
        actual_exit=b.file_ref(attempt / 'actual_exit/record.json'), actual_exit_zero=True, resources_passed=True,
        migration_authorization=b.entry(root / 'protocol/record.json'),
        migration_baseline=b.entry(root / 'baseline/record.json'),
        source_actual_exit_one_preserved=True, original_controller_HARD_BLOCKED_not_rewritten=True))
    proof = b.publish(root / 'result/record.json', dict(
        schema='v69_one_job_same_point_GPU6_migration_complete.v1', protocol_id=protocol['id'],
        status='COMPLETE', job_id=b.TARGET_JOB_ID, source_gpu=0, destination_gpu=6,
        baseline=b.entry(root / 'baseline/record.json'), actual_destination_exit=actual_exit_ref,
        accepted_generation=b.entry(acceptance_path), result=b.entry(result_path),
        destination_resources=b.entry(closed_path), complete_original_episodes=883,
        preserved_prefix_file_count=len(baseline['prefix']['files']),
        all_original_episode_and_return_hashes_unchanged=True,
        new_provider_calls_for_saved_episodes_or_returned_turns=0,
        original_source_exit_one_and_failure_preserved=True,
        legacy_controller_HARD_BLOCKED_not_rewritten=True,
        legacy_global_control_may_close_BLOCKED=True,
        global_scoring_uses_separately_verified_per_job_acceptance=True,
        new_scoring_calls=0, automatic_further_migration_or_retry_authorized=False))
    return dict(result=proof, result_ref=b.entry(root / 'result/record.json'), accepted=accepted)
