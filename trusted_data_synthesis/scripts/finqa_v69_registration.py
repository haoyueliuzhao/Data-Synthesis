"""Register one conditional, durable GPU0-to-GPU6 migration without resampling."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import time

import finqa_v69_binding as b

ROOT = b.ROOT
FILES = tuple('finqa_v69_' + name + '.py' for name in ('binding', 'registration', 'worker_bridge', 'entry'))
SCHEMA = 'v69_single_durable_generation_GPU0_to_GPU6_migration.v1'
_VERIFIED_IMPLEMENTATION = None
_VERIFIED_PROTOCOL = None


def modules():
    b.source_module('finqa_v63_entry').install_registered_auxiliary()
    b.install_scientific_paths()
    return {name: importlib.import_module('finqa_v69_' + name) for name in ('worker_bridge', 'entry')}


def same_live_identity(pid, birth):
    try:
        fields = Path('/proc/%s/stat' % pid).read_text().rsplit(')', 1)[1].split()
    except FileNotFoundError:
        return False
    return fields[19] == birth and fields[0] not in ('Z', 'X', 'x')


def migration_contract():
    return dict(schema='v69_one_target_one_safe_pause_one_continuation.v1',
        target_job_id=b.TARGET_JOB_ID, source_GPU=0, destination_GPU=6,
        source_attempt=1, continuation_attempt=2, new_GPU_worker_limit=1,
        source_generation_control_protocol_id=b.COMPLETION_PROTOCOL_ID,
        original_generation_namespace_preserved=True, original_frozen_worker_entry_unchanged=True,
        wait_for_other_three_C67_GPU_jobs_accepted_and_exited=True,
        wait_for_original_GPU6_job_exit_and_physical_idle=True,
        wait_for_all_twenty_CPU_repairs_not_required=True,
        destination_secondary_exclusive_lease_acquired_before_source_signal=True,
        destination_physical_idle_and_original_capacity_checked_under_lock=True,
        one_identity_bound_owner_SIGTERM_only=True, source_SIGKILL_allowed=False,
        source_current_provider_return_must_be_durable_before_exit=True,
        actual_old_parent_waitpid_required=True, source_HARD_state_preserved=True,
        accepted_pause_causes=['ExplicitStop', 'GenerationPreCallPause'],
        pause_cause_must_match_this_migration_kernel_signal_receipt=True,
        UNKNOWN_calls_authorized=0, settled_response_model_calls_repeated=0,
        original_run_model_checkpoint_tasks_config_draw_and_order_unchanged=True,
        original_episode_and_return_cache_prefix_hashes_preserved=True,
        source_natural_completion_means_no_migration=True,
        explicit_stop_disables_continuation=True, automatic_retry=False,
        old_failures_and_control_journals_rewritten=False,
        append_authorized_target_attempt2_and_final_acceptance_only=True,
        original_C67_may_close_BLOCKED_because_handoff_HARD_remains=True,
        V68_reads_new_target_acceptance_without_rewriting_scoring=True,
        other_worker_or_controller_signals_sent=0, new_sampling_or_scoring_authorized=False,
        original_per_worker_resource_and_signal_gates_unchanged=True,
        original_global_GPU_limit=6, original_per_GPU_limit=2,
        physical_capacity_after_admission_not_guaranteed=True)


def original_evidence():
    protocol = b.checked(b.COMPLETION_ROOT / 'protocol/record.json')
    plan = b.checked(b.COMPLETION_ROOT / 'evaluations/registration/record.json')
    launch = b.checked(b.source_attempt_directory() / 'launch/record.json')
    controller = b.checked(b.COMPLETION_ROOT / 'controllers/attempt0001/launch/record.json')
    destination = b.checked(b.COMPLETION_ROOT / 'evaluations/jobs' / b.DESTINATION_JOB_ID /
                            'attempts/attempt0001/launch/record.json')
    b.require(protocol['id'] == plan['protocol_id'] == launch['protocol_id'] ==
              controller['protocol_id'] == destination['protocol_id'] == b.COMPLETION_PROTOCOL_ID
              and plan['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and len(plan['jobs']) == 4 and b.TARGET_JOB_ID in plan['jobs']
              and b.DESTINATION_JOB_ID in plan['jobs'], 'original fixed generation scope changed')
    b.require((launch['pid'], launch['birth'], launch['gpu_index'], launch['attempt']) ==
              (b.TARGET_PID, b.TARGET_BIRTH, 0, 1)
              and launch['job']['job_id'] == b.TARGET_JOB_ID
              and all(launch['job'].get(key) == value for key, value in plan['jobs'][b.TARGET_JOB_ID].items()),
              'only the identified original GPU0 target attempt may be migrated')
    b.require((controller['pid'], controller['birth'], controller['controller_attempt']) ==
              (b.CONTROLLER_PID, b.CONTROLLER_BIRTH, 1)
              and (destination['pid'], destination['birth'], destination['gpu_index'], destination['attempt']) ==
              (b.DESTINATION_PID, b.DESTINATION_BIRTH, 6, 1)
              and destination['job']['job_id'] == b.DESTINATION_JOB_ID,
              'bound original controller or destination occupant changed')
    b.require(not b.destination_attempt_directory().exists(), 'the one continuation attempt already exists')
    return protocol, plan, dict(
        source_protocol=b.entry(b.COMPLETION_ROOT / 'protocol/record.json'),
        source_plan=b.entry(b.COMPLETION_ROOT / 'evaluations/registration/record.json'),
        source_launch=b.entry(b.source_attempt_directory() / 'launch/record.json'),
        source_controller_launch=b.entry(b.COMPLETION_ROOT / 'controllers/attempt0001/launch/record.json'),
        destination_launch=b.entry(b.COMPLETION_ROOT / 'evaluations/jobs' / b.DESTINATION_JOB_ID /
                                   'attempts/attempt0001/launch/record.json'))


def freeze(source_commit):
    b.require(not ROOT.exists(), 'migration registration must be independently fresh')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=b.REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = 'trusted_data_synthesis/scripts/' + name
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), 'uncommitted migration source: ' + name)
        sources[name] = raw
    directory = ROOT / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return b.publish(directory / 'record.json', dict(schema='v69_frozen_single_migration_control_sources.v1',
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        original_generation_implementation=b.entry(b.COMPLETION_ROOT / 'implementation/record.json'),
        scientific_implementation=b.entry(b.SCIENTIFIC_ROOT / 'implementation/record.json'),
        original_worker_sources_modified=False, original_controller_sources_modified=False))


def checked_implementation(root=ROOT):
    global _VERIFIED_IMPLEMENTATION
    b.require(Path(root).resolve() == ROOT, 'foreign migration implementation root')
    if _VERIFIED_IMPLEMENTATION is not None:
        return _VERIFIED_IMPLEMENTATION
    value = b.checked(ROOT / 'implementation/record.json')
    b.require(value['committed_files'] == list(FILES) and set(value['sha256']) == set(FILES)
              and b.read_ref(value['original_generation_implementation'])['id'] == b.COMPLETION_IMPLEMENTATION_ID
              and b.read_ref(value['scientific_implementation'])['id'] == b.BASE_IMPLEMENTATION_ID,
              'migration implementation lineage changed')
    for name, expected in value['sha256'].items():
        b.require(b.sha(ROOT / 'implementation' / name) == expected, 'frozen migration source changed: ' + name)
    _VERIFIED_IMPLEMENTATION = value
    return value


def checked_protocol(root=ROOT):
    global _VERIFIED_PROTOCOL
    b.require(Path(root).resolve() == ROOT, 'foreign migration protocol root')
    if _VERIFIED_PROTOCOL is not None:
        return _VERIFIED_PROTOCOL
    value = b.checked(ROOT / 'protocol/record.json')
    source = b.read_ref(value['source_protocol'])
    plan = b.read_ref(value['source_plan'])
    b.require(value['schema'] == SCHEMA and value['control_root'] == str(ROOT)
              and value['source_root'] == str(b.COMPLETION_ROOT)
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['source_protocol_id'] == source['id'] == b.COMPLETION_PROTOCOL_ID
              and plan['protocol_id'] == source['id']
              and value['target_job'] == plan['jobs'][b.TARGET_JOB_ID]
              and value['target'] == dict(job_id=b.TARGET_JOB_ID, pid=b.TARGET_PID, birth=b.TARGET_BIRTH,
                  gpu_index=0, attempt=1)
              and value['source_controller'] == dict(pid=b.CONTROLLER_PID, birth=b.CONTROLLER_BIRTH,
                  controller_attempt=1)
              and value['destination'] == dict(gpu_index=6, uuid=source['gpu_uuids']['6'],
                  await_job_id=b.DESTINATION_JOB_ID, await_pid=b.DESTINATION_PID,
                  await_birth=b.DESTINATION_BIRTH, await_attempt=1)
              and value['migration'] == migration_contract()
              and value['max_new_GPU_workers'] == 1 and value['startup_available_gib'] == b.STARTUP_AVAILABLE_GIB == 512
              and value['stop_settle_seconds'] == b.STOP_SETTLE_SECONDS == 600
              and value['implementation']['id'] == checked_implementation()['id'],
              'one-job migration target, destination, scope or resource bound changed')
    for key in ('gpu_lease_root', 'gpu_slot_policy', 'gpu_uuids', 'cpu_affinity',
                'resource_policy', 'resource_recovery_policy', 'memory_protection_policy',
                'signal_policy', 'signal_source_bindings', 'gpu_isolation_policy'):
        b.require(value[key] == source[key], 'original worker hard contract changed: ' + key)
    for key, expected in (
        ('source_protocol', b.COMPLETION_ROOT / 'protocol/record.json'),
        ('source_plan', b.COMPLETION_ROOT / 'evaluations/registration/record.json'),
        ('source_launch', b.source_attempt_directory() / 'launch/record.json'),
        ('source_controller_launch', b.COMPLETION_ROOT / 'controllers/attempt0001/launch/record.json'),
        ('destination_launch', b.COMPLETION_ROOT / 'evaluations/jobs' / b.DESTINATION_JOB_ID /
         'attempts/attempt0001/launch/record.json')):
        b.require(Path(value[key]['path']).resolve() == expected.resolve(), 'migration evidence escaped original identity')
        b.read_ref(value[key])
    _VERIFIED_PROTOCOL = value
    return value


def checked_prepared(root=ROOT):
    value = b.checked(Path(root) / 'prepared/record.json')
    protocol = checked_protocol(root)
    b.require(value['protocol_id'] == protocol['id'] and value['target_job_id'] == b.TARGET_JOB_ID
              and value['signals_sent'] == value['new_model_calls'] == 0
              and value['target_was_running_at_registration'] is True,
              'single conditional migration is not prepared')
    return value


def prepare(source_commit):
    modules()
    b.require(not ROOT.exists(), 'migration may be registered only once')
    source, plan, refs = original_evidence()
    b.require(same_live_identity(b.TARGET_PID, b.TARGET_BIRTH)
              and same_live_identity(b.CONTROLLER_PID, b.CONTROLLER_BIRTH),
              'target and bound original controller must still be live at registration')
    journal = b.checked(b.COMPLETION_ROOT / 'journal/state.json')
    b.require(journal['protocol_id'] == b.COMPLETION_PROTOCOL_ID
              and any(row['job_id'] == b.TARGET_JOB_ID and row['pid'] == b.TARGET_PID
                  and row['birth'] == b.TARGET_BIRTH and row['gpu_index'] == 0 for row in journal['active_jobs']),
              'the bound source generation is not currently active on GPU0')
    implementation = freeze(source_commit)
    b.publish(ROOT / 'source_journal_at_registration/record.json', journal)
    body = dict(schema=SCHEMA, control_root=str(ROOT), source_root=str(b.COMPLETION_ROOT),
        scientific_root=str(b.SCIENTIFIC_ROOT), scientific_protocol_id=b.BASE_PROTOCOL_ID,
        source_protocol_id=b.COMPLETION_PROTOCOL_ID, target_job=plan['jobs'][b.TARGET_JOB_ID],
        target=dict(job_id=b.TARGET_JOB_ID, pid=b.TARGET_PID, birth=b.TARGET_BIRTH, gpu_index=0, attempt=1),
        source_controller=dict(pid=b.CONTROLLER_PID, birth=b.CONTROLLER_BIRTH, controller_attempt=1),
        destination=dict(gpu_index=6, uuid=source['gpu_uuids']['6'], await_job_id=b.DESTINATION_JOB_ID,
            await_pid=b.DESTINATION_PID, await_birth=b.DESTINATION_BIRTH, await_attempt=1),
        migration=migration_contract(), max_new_GPU_workers=1, startup_available_gib=512,
        stop_settle_seconds=600, source_commit=implementation['source_commit'],
        implementation=b.entry(ROOT / 'implementation/record.json'),
        authorization='GPU0有其他任务，GPU6空闲后将任务迁移至6',
        source_journal_at_registration=b.entry(ROOT / 'source_journal_at_registration/record.json'),
        new_model_calls=0, signals_sent=0, created_epoch=time.time(), **refs)
    for key in ('gpu_lease_root', 'gpu_slot_policy', 'gpu_uuids', 'cpu_affinity',
                'resource_policy', 'resource_recovery_policy', 'memory_protection_policy',
                'signal_policy', 'signal_source_bindings', 'gpu_isolation_policy'):
        body[key] = source[key]
    protocol = b.publish(ROOT / 'protocol/record.json', body)
    command = [str(b.PYTHON), '-c',
        'import finqa_v69_registration as r; r.modules(); r.prepare_frozen(); print("V69_CONDITIONAL_MIGRATION_PREPARED")']
    subprocess.run(command, cwd=b.REPO, env=dict(os.environ,
        PYTHONPATH=str(ROOT / 'implementation'), CUDA_VISIBLE_DEVICES=''), check=True)
    return protocol


def prepare_frozen():
    b.require(Path(__file__).resolve().parent == ROOT / 'implementation', 'prepare only from frozen migration sources')
    protocol = checked_protocol()
    return b.publish(ROOT / 'prepared/record.json', dict(schema='v69_conditional_migration_prepared.v1',
        protocol_id=protocol['id'], target_job_id=b.TARGET_JOB_ID,
        target_was_running_at_registration=True, signals_sent=0, new_model_calls=0,
        GPU6_capacity_not_preclaimed=True, source_frozen_worker_unchanged=True, prepared_epoch=time.time()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = prepare(args.source_commit)
    print(json.dumps(dict(id=result['id'], schema=result['schema']), sort_keys=True))
