"""Freeze a separate resource-protection control plane, never rewrite V63."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import time

import finqa_v64_binding as b

ROOT, SCIENTIFIC_ROOT = b.ROOT, b.SCIENTIFIC_ROOT
FILES = tuple('finqa_v64_' + name + '.py' for name in
              ('binding', 'registration', 'runtime', 'worker', 'controller', 'entry', 'handoff'))
SCHEMA = 'v64_bounded_native_cache_protection_control.v1'
IMPLEMENTATION_SCHEMA = 'v64_frozen_protection_control_sources.v1'
PREPARED_SCHEMA = 'v64_verified_complete_response_maintenance_inheritance.v1'
_VERIFIED_IMPLEMENTATION = None
_VERIFIED_PROTOCOL = None


def maintenance_authorization():
    body = dict(schema='v64_explicit_same_experiment_protection_authorization.v1',
        user_request='提供保护，防止再次被挤占',
        selected_handoff='完整断点受控切换（推荐）',
        additional_question='是否可以提前预留显存以供使用',
        scope='same V63 remaining jobs, same scientific data and dose; own processes only',
        owner_uid=1004, same_scientific_protocol_id=b.BASE_PROTOCOL_ID,
        cold_new_workers_only=True, active_frozen_workers_modified=False,
        direct_maintenance_signal_target='exact registered old controller PID and birth',
        old_supervisor_exit='natural observation of its controller STOP and actual exit',
        only_active_replay_jobs_may_be_interrupted=True,
        complete_feedback_required_before_handoff=4200,
        own_complete_response_checkpoint_required=True,
        returned_feedback_or_committed_gradient_prefix_repeated=False,
        uncommitted_work_may_be_recomputed_as_maintenance_overhead=True,
        one_handoff_only=True, old_STOP_and_failure_records_rewritten=False,
        unrelated_stop_or_UNKNOWN_or_numeric_failure_override=False,
        global_worker_limit=6, workers_per_GPU=1,
        GPU_indices=list(range(8)), GPU_compute_mode_or_privileges_modified=False,
        other_project_processes_or_files_modified=False,
        automatic_new_experiment_or_extra_sampling=False)
    return dict(**body, id=b.digest(body))


def control_contract():
    return dict(schema='v64_operational_override_without_scientific_identity_change.v1',
        scientific_root=str(SCIENTIFIC_ROOT), control_root=str(ROOT),
        scientific_protocol_id=b.BASE_PROTOCOL_ID,
        unchanged_conditions_parents_points_draws_rewards_and_checkpoint_IDs=True,
        total_new_feedback_target=4200, feedback_reexecution=0,
        total_optimizer_target=1788, evaluation_sessions=7458, evaluation_jobs=24,
        original_class_passes_added=0, response_replay_budget_expanded=False,
        cache_protection_is_not_OS_device_exclusivity=True,
        protection_may_be_partial_or_zero_if_capacity_unavailable=True,
        physical_free_checks_not_replaced_by_cached_bytes=True,
        no_new_allocator_or_MemPool_or_cudaMallocAsync=True,
        no_sidecar_GPU_holder=True, no_new_cron_or_machine_wide_observer=True,
        no_scientific_or_resource_wait_deadline=True,
        original_resource_wait_and_attempt_ordinals_inherited=True,
        original_resource_hard_gates_and_UNKNOWN_rules_unchanged=True,
        legal_stop_prevents_automatic_relaunch=True,
        scientific_results_append_to_original_root=True,
        operational_status_STOP_and_closeout_in_new_root=True,
        no_hot_patch_of_old_implementation=True,
        no_same_GPU_double_worker=True)


def effective_resource_overrides():
    return dict(schema='v64_explicit_operational_resource_overrides.v1',
        replaced_original_field='resource_policy.warm_allocation_bytes=0 for runtime R3 only',
        runtime_R3_maximum_incremental_warm_bytes=16 * 1024 ** 3,
        inherited_pre_model_warm_bytes=0,
        feedback_generation_warm_bytes=0,
        routine_cleanup_retains_native_cache=True,
        capacity_shortage_cache_release_only_if_physical_free_predicate_failed=True,
        original_76GiB_peak_2GiB_boundary_RSS_host_and_exact_R3_gates_unchanged=True,
        original_V63_protocol_rewritten=False,
        effective_policy_is_original_hard_gates_plus_this_registered_override=True)


def modules():
    original_entry = b.source_module('finqa_v63_entry')
    original_entry.install_registered_auxiliary()
    b.source_module('finqa_v63_binding').install_scientific_paths()
    return {name: importlib.import_module('finqa_v64_' + name)
            for name in ('runtime', 'worker', 'controller', 'entry')}


def _same_identity(pid, expected_birth):
    try:
        fields = Path('/proc/%s/stat' % pid).read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return fields[19] == expected_birth and fields[0] not in ('Z', 'X', 'x')


def baseline():
    protocol = b.base_protocol()
    implementation = b.checked(b.SOURCE / 'record.json')
    b.require(implementation['id'] == b.BASE_IMPLEMENTATION_ID,
              'original V63 implementation changed')
    supervisor = b.checked(SCIENTIFIC_ROOT / 'supervisor/launch/record.json')
    queue = json.loads((SCIENTIFIC_ROOT / 'supervisor/queue/status.json').read_bytes())
    controller_attempt = queue['controller_attempt']
    controller_path = SCIENTIFIC_ROOT / 'controllers' / ('attempt%04d' % controller_attempt) / 'launch/record.json'
    controller = b.checked(controller_path)
    b.require(_same_identity(supervisor['pid'], supervisor['birth'])
              and _same_identity(controller['pid'], controller['birth']),
              'the exact old supervisor/controller must still be alive before preparation')
    b.require(not (SCIENTIFIC_ROOT / 'STOP').exists()
              and not (SCIENTIFIC_ROOT / 'control/stop_requested/record.json').exists()
              and not (SCIENTIFIC_ROOT / 'closeout/record.json').exists(),
              'an unrelated old terminal state is not a protection-handoff allowance')
    return dict(scientific_protocol=b.entry(SCIENTIFIC_ROOT / 'protocol/record.json'),
        scientific_implementation=b.entry(b.SOURCE / 'record.json'),
        original_supervisor=b.entry(SCIENTIFIC_ROOT / 'supervisor/launch/record.json'),
        original_controller=b.entry(controller_path), old_controller_attempt=controller_attempt,
        gpu_uuids=protocol['gpu_uuids'], gpu_lease_root=protocol['gpu_lease_root'],
        gpu_priority=protocol['gpu_priority'], cpu_affinity=protocol['cpu_affinity'])


def freeze(source_commit, evidence):
    b.require(not ROOT.exists(), 'V64 protection requires its one fresh independent control root')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'],
                                    cwd=b.REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = 'trusted_data_synthesis/scripts/' + name
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative),
                  'uncommitted protection implementation: ' + name)
        sources[name] = raw
    directory = ROOT / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return b.publish(directory / 'record.json', dict(schema=IMPLEMENTATION_SCHEMA,
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        original_implementation=evidence['scientific_implementation'],
        original_scientific_sources_modified=False,
        canonical_original_source_root=str(b.SOURCE),
        private_resource_adapters_are_registered_not_new_math=True))


def checked_implementation(root=ROOT):
    global _VERIFIED_IMPLEMENTATION
    b.require(Path(root).resolve() == ROOT, 'foreign V64 implementation root')
    if _VERIFIED_IMPLEMENTATION is not None:
        return _VERIFIED_IMPLEMENTATION
    v = b.checked(ROOT / 'implementation/record.json')
    original = b.read_ref(v['original_implementation'])
    b.require(v['schema'] == IMPLEMENTATION_SCHEMA and v['committed_files'] == list(FILES)
              and set(v['sha256']) == set(FILES)
              and original['id'] == b.BASE_IMPLEMENTATION_ID,
              'protection execution package differs from its source registration')
    for name, expected in v['sha256'].items():
        b.require(b.sha(ROOT / 'implementation' / name) == expected,
                  'frozen V64 source changed: ' + name)
    b.source_module('finqa_v63_registration').checked_implementation(SCIENTIFIC_ROOT)
    _VERIFIED_IMPLEMENTATION = v
    return v


def checked_protocol(root=ROOT):
    global _VERIFIED_PROTOCOL
    b.require(Path(root).resolve() == ROOT, 'foreign protection control root')
    if _VERIFIED_PROTOCOL is not None:
        return _VERIFIED_PROTOCOL
    p = b.checked(ROOT / 'protocol/record.json')
    resources = importlib.import_module('finqa_v64_runtime')
    signals = b.source_module('finqa_v63_signals')
    original = b.base_protocol()
    b.require(p['schema'] == SCHEMA and p['control_root'] == str(ROOT)
              and p['scientific_root'] == str(SCIENTIFIC_ROOT)
              and p['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and p['implementation']['id'] == checked_implementation()['id']
              and p['maintenance_authorization'] == maintenance_authorization()
              and p['control_contract'] == control_contract()
              and p['effective_resource_overrides'] == effective_resource_overrides()
              and p['memory_protection_policy'] == resources.memory_protection_policy()
              and p['signal_policy'] == signals.signals_policy()
              and p['signal_source_bindings'] == signals.external_source_bindings()
              and p['max_gpu_workers'] == 6 and p['max_workers_per_gpu'] == 1,
              'registered operational protection contract changed')
    for name in ('gpu_uuids', 'gpu_priority', 'cpu_affinity', 'gpu_lease_root', 'auto_recovery_policy'):
        b.require(p[name] == original[name], 'protection cannot change original policy: ' + name)
    b.require(b.read_ref(p['baseline']['scientific_protocol'])['id'] == b.BASE_PROTOCOL_ID,
              'foreign scientific lineage')
    _VERIFIED_PROTOCOL = p
    return p


def checked_prepared(root=ROOT):
    b.require(Path(root).resolve() == ROOT, 'foreign protection prepared root')
    p = checked_protocol()
    v = b.checked(ROOT / 'prepared/record.json')
    b.require(v['schema'] == PREPARED_SCHEMA and v['control_protocol_id'] == p['id']
              and v['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and v['authorization_id'] == p['maintenance_authorization']['id']
              and v['all_old_scientific_workers_actual_exits_observed'] is True
              and v['old_controller_and_supervisor_identities_gone'] is True
              and v['new_scientific_calls'] == 0,
              'controlled complete-response inheritance has not passed')
    b.read_ref(v['pre_stop_journal'])
    final = b.read_ref(v['inherited_journal'])
    b.require(final['active_jobs'] == [] and final['protocol_id'] == b.BASE_PROTOCOL_ID,
              'unsettled old worker prevents inheritance')
    return v


def prepare(source_commit):
    b.require(not ROOT.exists(), 'one fresh V64 registration only')
    loaded = modules()
    evidence = baseline()
    original = b.base_protocol()
    signals = b.source_module('finqa_v63_signals')
    policy = loaded['runtime'].memory_protection_policy()
    implementation = freeze(source_commit, evidence)
    return b.publish(ROOT / 'protocol/record.json', dict(schema=SCHEMA,
        created_epoch=time.time(), control_root=str(ROOT), scientific_root=str(SCIENTIFIC_ROOT),
        scientific_protocol_id=b.BASE_PROTOCOL_ID, implementation=b.entry(ROOT / 'implementation/record.json'),
        source_commit=implementation['source_commit'], baseline=evidence,
        maintenance_authorization=maintenance_authorization(), control_contract=control_contract(),
        effective_resource_overrides=effective_resource_overrides(),
        memory_protection_policy=policy, signal_policy=signals.signals_policy(),
        signal_source_bindings=signals.external_source_bindings(),
        max_gpu_workers=6, max_workers_per_gpu=1,
        auto_recovery_policy=original['auto_recovery_policy'],
        gpu_uuids=original['gpu_uuids'], gpu_priority=original['gpu_priority'],
        cpu_affinity=original['cpu_affinity'], gpu_lease_root=original['gpu_lease_root'],
        original_numeric_resource_policy=original['resource_policy'],
        no_hot_modification=True, CPU_preparation_only=True,
        new_worker_launched=False, protection_not_yet_active=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = prepare(args.source_commit)
    print(json.dumps(dict(id=result['id'], schema=result['schema'],
                          implementation_id=result['implementation']['id']), sort_keys=True))
