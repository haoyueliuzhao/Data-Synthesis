"""Freeze the one-point exception and conservative parallel resource scope."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import os
from pathlib import Path
import subprocess
import time

import finqa_v66_binding as b

FILES = tuple('finqa_v66_' + name + '.py' for name in
    ('binding', 'diagnostics', 'temperature', 'runtime', 'worker', 'controller', 'registration', 'entry'))
ROOT = b.ROOT
_IMPLEMENTATION = None
_PROTOCOL = None


def authorization():
    return dict(schema='v66_explicit_single_known_draw_gradient_diagnostic_exception.v1',
        user_request='问题组并行处理，尽快恢复实验',
        user_answer='授权该单点例外并继续',
        seed=389, arm='C05', complete_response_cursor=830,
        allowed_jobs=list(b.JOBS), diagnostic_result_remains_FAIL=True,
        formal_gradient_replaced=False, new_response_replays=0, new_feedback=0,
        raw_C_mean_gate_exception=False, other_numerical_state_resource_gates_relaxed=False,
        accepted_five_branches_read_only=True, generate_or_score=False,
        new_optimizer_updates=298, actual_stage_worker_cap=1,
        peer_V65_worker_cap=5, combined_worker_cap=6,
        extra_host_startup_reservation_for_V65_bytes=240 * 1024 ** 3,
        resource_safe_checkpoint_recovery_inherited=True,
        another_scientific_failure_exception=False)


def initialize():
    b.source_module('finqa_v63_binding').install_scientific_paths()
    b.source_module('finqa_v63_entry').install_registered_auxiliary()


def validate_shared(value):
    b.require(value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
        and value['global_max_gpu_workers'] == 6 and value['max_workers_per_gpu'] == 1
        and value['GPU_indices'] == list(range(8))
        and value['gpu_lease_root'] == b.base_protocol()['gpu_lease_root']
        and value['scientific_owner_lock'] == str(b.SCIENTIFIC_ROOT / 'owner.lock')
        and value['authorized_controls_use_shared_scientific_owner_lock'] is True
        and value['initialization_resource_wait_and_draining_count_in_own_cap'] is True
        and value['scoring_calls_authorized'] == 0
        and value['allowed_controls'][str(b.ROOT)] == dict(max_gpu_workers=1,
            stages=list(b.JOBS), existing_response_cursor=830, additional_response_replay=0,
            remaining_optimizer_updates=298, reserved_other_control_startup_gib=240)
        and value['allowed_controls'][str(b.SCIENTIFIC_ROOT / 'early_generation_01')]['max_gpu_workers'] == 5
        and value['allowed_controls'][str(b.SCIENTIFIC_ROOT / 'early_generation_01')]['reserved_other_control_startup_gib'] == 64
        and set(value['allowed_controls']) == {str(b.ROOT), str(b.SCIENTIFIC_ROOT / 'early_generation_01')},
        'shared parallel authorization/resource scope changed')
    return value


def baseline():
    initialize()
    control = b.checked(b.OLD_CONTROL / 'closeout/record.json')
    journal = b.checked(b.OLD_CONTROL / 'journal/state.json')
    supervisor = b.checked(b.OLD_CONTROL / 'supervisor/closeout/record.json')
    b.require(control['status'] == supervisor['status'] == 'BLOCKED_OPERATOR_REQUIRED'
              and control['active_workers'] == 0 and journal['active_jobs'] == [],
              'old V64 must be settled and stopped, not a live handoff')
    controller = importlib.import_module('finqa_v66_controller')
    runtime = importlib.import_module('finqa_v66_runtime').controller_runtime()
    controller.restore_states(journal)
    for row in journal['attempt_history']:
        controller._controller.audit_attempt_exit(row, b.base_protocol(), runtime)
    for path in (b.OLD_CONTROL / 'supervisor/launch/record.json',
                 b.OLD_CONTROL / 'controllers/attempt0001/launch/record.json'):
        launch = b.checked(path)
        b.require(not controller.inherited._same_live_identity(runtime, launch['pid'], launch['birth']),
                  'old scientific controller/supervisor is still alive')
    failure = b.checked(b.FAILURE)
    b.require(failure['exception_type'] == 'DrawDiagnosticError'
              and failure['error'] == 'diagnostic draw mean failed its registered numerical gate; no tolerance retry'
              and failure['resources']['all_gates_passed'] is True,
              'the approved original diagnostic failure changed')
    return dict(inherited_journal=b.entry(b.OLD_CONTROL / 'journal/state.json'),
        old_closeout=b.entry(b.OLD_CONTROL / 'closeout/record.json'),
        old_supervisor_closeout=b.entry(b.OLD_CONTROL / 'supervisor/closeout/record.json'),
        original_failure=b.entry(b.FAILURE), all_old_actual_exits_observed=True)


def freeze(source_commit):
    b.require(not b.ROOT.exists(), 'V66 requires one fresh independent registration')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=b.REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = 'trusted_data_synthesis/scripts/' + name
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), 'uncommitted V66 source: ' + name)
        sources[name] = raw
    directory = b.ROOT / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return b.publish(directory / 'record.json', dict(schema='v66_frozen_single_point_exception_sources.v1',
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        original_implementation=b.entry(b.SOURCE / 'record.json'),
        protection_implementation=b.entry(b.OLD_CONTROL / 'implementation/record.json'),
        original_frozen_sources_modified=False))


def checked_implementation(root=b.ROOT):
    global _IMPLEMENTATION
    b.require(Path(root).resolve() == b.ROOT, 'foreign implementation root')
    if _IMPLEMENTATION is None:
        value = b.checked(b.ROOT / 'implementation/record.json')
        b.require(value['committed_files'] == list(FILES) and set(value['sha256']) == set(FILES)
                  and b.read_ref(value['original_implementation'])['id'] == b.BASE_IMPLEMENTATION_ID,
                  'V66 frozen implementation scope changed')
        b.read_ref(value['protection_implementation'])
        for name, expected in value['sha256'].items():
            b.require(b.sha(b.ROOT / 'implementation' / name) == expected, 'frozen V66 source changed')
        b.source_module('finqa_v63_registration').checked_implementation(b.SCIENTIFIC_ROOT)
        _IMPLEMENTATION = value
    return _IMPLEMENTATION


def checked_protocol(root=b.ROOT):
    global _PROTOCOL
    b.require(Path(root).resolve() == b.ROOT, 'foreign V66 protocol root')
    if _PROTOCOL is None:
        value = b.checked(b.ROOT / 'protocol/record.json')
        b.require(value['authorization'] == authorization()
                  and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
                  and value['max_gpu_workers'] == 1 and value['max_workers_per_gpu'] == 1
                  and value['implementation']['id'] == checked_implementation()['id'],
                  'single-point scientific/resource authorization changed')
        original = b.base_protocol()
        for key in ('gpu_uuids', 'gpu_priority', 'cpu_affinity', 'gpu_lease_root', 'signal_policy', 'signal_source_bindings'):
            b.require(value[key] == original[key], 'original resource/signal binding changed: ' + key)
        validate_shared(b.read_ref(value['shared_authorization']))
        evidence = b.read_ref(value['diagnostic_evidence'])
        b.require(evidence['status'] == 'FAIL' and evidence['completed_responses'] == 830
                  and evidence['report']['failed_element_count'] == 1, 'bound exception evidence differs')
        _PROTOCOL = value
    return _PROTOCOL


def checked_prepared(root=b.ROOT):
    b.require(Path(root).resolve() == b.ROOT, 'foreign V66 prepared root')
    p = checked_protocol()
    value = b.checked(b.ROOT / 'prepared/record.json')
    b.require(value['control_protocol_id'] == p['id'] and value['all_old_actual_exits_observed'] is True,
              'V66 old-exit inheritance is unprepared')
    return value


def prepare(source_commit, shared_authorization):
    b.require(not b.ROOT.exists(), 'single fresh V66 registration only')
    validate_shared(b.read_ref(shared_authorization))
    baseline_evidence = baseline()
    diagnostics = importlib.import_module('finqa_v66_diagnostics').cpu_evidence()
    implementation = freeze(source_commit)
    b.publish(b.ROOT / 'diagnostic_evidence/record.json', diagnostics)
    original = b.base_protocol()
    resources = importlib.import_module('finqa_v66_runtime')
    protocol = b.publish(b.ROOT / 'protocol/record.json', dict(
        schema='v66_single_diagnostic_exception_control.v1', created_epoch=time.time(),
        control_root=str(b.ROOT), scientific_root=str(b.SCIENTIFIC_ROOT),
        scientific_protocol_id=b.BASE_PROTOCOL_ID, source_commit=implementation['source_commit'],
        implementation=b.entry(b.ROOT / 'implementation/record.json'), authorization=authorization(),
        shared_authorization=shared_authorization,
        diagnostic_evidence=b.entry(b.ROOT / 'diagnostic_evidence/record.json'),
        memory_protection_policy=resources.memory_protection_policy(),
        max_gpu_workers=1, max_workers_per_gpu=1,
        scientific_owner_lock_mode='LOCK_SH', control_owner_lock_mode='LOCK_EX',
        stage_worker_and_GPU_lease_lock_mode='LOCK_EX',
        **{key: original[key] for key in ('gpu_uuids', 'gpu_priority', 'cpu_affinity', 'gpu_lease_root',
                                        'signal_policy', 'signal_source_bindings')}))
    b.publish(b.ROOT / 'prepared/record.json', dict(schema='v66_exact_failed_point_prepared.v1',
        control_protocol_id=protocol['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        new_scientific_calls=0, **baseline_evidence))
    return protocol


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--shared-authorization', type=Path, required=True)
    args = parser.parse_args()
    value = prepare(args.source_commit, b.entry(args.shared_authorization))
    print(value['id'])
