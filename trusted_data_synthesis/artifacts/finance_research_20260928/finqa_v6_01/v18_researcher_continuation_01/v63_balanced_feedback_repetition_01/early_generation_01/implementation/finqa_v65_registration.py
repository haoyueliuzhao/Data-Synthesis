"""Register twenty unscored jobs and their disjoint five-plus-one resource split."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import time

import finqa_v65_binding as b

ROOT = b.ROOT
FILES = tuple('finqa_v65_' + item + '.py' for item in
              ('binding', 'registration', 'runtime', 'evaluation', 'worker', 'controller', 'entry'))
SCHEMA = 'v65_five_accepted_endpoints_unscored_generation_protocol.v1'
PREPARED_SCHEMA = 'v65_exact_twenty_public_generation_jobs_prepared.v1'
_VERIFIED_IMPLEMENTATION = None
_VERIFIED_PROTOCOL = None


def modules():
    b.source_module('finqa_v63_entry').install_registered_auxiliary()
    b.install_scientific_paths()
    return {name: importlib.import_module('finqa_v65_' + name) for name in
            ('runtime', 'evaluation', 'worker', 'controller', 'entry')}


def same_live_identity(pid, birth):
    try:
        fields = Path('/proc/%s/stat' % pid).read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return fields[19] == birth and fields[0] not in ('Z', 'X', 'x')


def old_terminal_evidence():
    root = b.PREDECESSOR_ROOT
    control = b.checked(root / 'closeout/record.json')
    supervisor = b.checked(root / 'supervisor/closeout/record.json')
    journal = b.checked(root / 'journal/state.json')
    b.require(control['status'] == supervisor['status'] == 'BLOCKED_OPERATOR_REQUIRED'
              and supervisor['automatic_restart_stopped'] is True and journal['active_jobs'] == []
              and journal['protocol_id'] == b.BASE_PROTOCOL_ID and len(journal['accepted']) == 21,
              'only the actual settled V64 terminal state may be inherited')
    launches = [root / 'supervisor/launch/record.json', root / 'controllers/attempt0001/launch/record.json']
    for path in launches:
        value = b.checked(path)
        b.require(not same_live_identity(value['pid'], value['birth']), 'old controller or supervisor remains alive')
    for row in journal['attempt_history']:
        directory = Path(row['directory'])
        launch = b.checked(directory / 'launch/record.json')
        actual = b.checked(directory / 'actual_exit/record.json')
        b.require(actual['actual_waitpid_observed'] is True and type(actual['returncode']) is int
                  and (actual['pid'], actual['birth']) == (launch['pid'], launch['birth'])
                  and actual['job_id'] == row['job_id'] and actual['attempt'] == row['attempt']
                  and not same_live_identity(launch['pid'], launch['birth']),
                  'old scientific attempt must have its actual settled exit')
    return dict(parent_control_closeout=b.entry(root / 'closeout/record.json'),
        parent_supervisor_closeout=b.entry(root / 'supervisor/closeout/record.json'),
        inherited_journal=b.entry(root / 'journal/state.json'),
        all_old_control_and_worker_identities_exited=True, old_actual_worker_exits=len(journal['attempt_history']))


def parallel_scopes():
    return {str(ROOT): dict(max_gpu_workers=5, stages=['generate'],
        generation_jobs=20, sessions=6215, excluded_coordinate='seed389/C05',
        reserved_other_control_startup_gib=64),
        str(b.PEER_ROOT): dict(max_gpu_workers=1,
            stages=['seed389.replay_C05', 'seed389.distribution_C05', 'seed389.train_C05'],
            existing_response_cursor=830, additional_response_replay=0,
            remaining_optimizer_updates=298, reserved_other_control_startup_gib=240)}


def validate_parallel_authorization(value):
    b.require(value['schema'] == 'v65_v66_authorized_disjoint_parallel_continuation.v1'
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['scientific_root'] == str(b.SCIENTIFIC_ROOT)
              and value['global_max_gpu_workers'] == 6 and value['max_workers_per_gpu'] == 1
              and value['allowed_controls'] == parallel_scopes()
              and value['GPU_indices'] == list(range(8))
              and value['gpu_lease_root'] == b.base_protocol()['gpu_lease_root']
              and value['scientific_owner_lock'] == str(b.SCIENTIFIC_ROOT / 'owner.lock')
              and value['scoring_calls_authorized'] == value['new_feedback_or_class_passes_authorized'] == 0
              and value['original_global_scientific_budget'] == dict(generation_jobs=24, sessions=7458)
              and all(value[key] is True for key in (
                  'authorized_controls_use_shared_scientific_owner_lock',
                  'historical_exclusive_scientific_controller_is_excluded',
                  'each_control_has_exclusive_local_owner_and_supervisor_locks',
                  'initialization_resource_wait_and_draining_count_in_own_cap',
                  'caps_not_reallocated_automatically_when_other_control_idle',
                  'other_control_RAM_reservation_not_reduced_by_its_actual_RSS'))
              and value['completed_responses_or_training_repeated'] is False
              and value['old_failures_and_protocols_rewritten'] is False,
              'shared disjoint scopes, resource reservations, or no-scoring contract changed')
    return value


def parallel_authorization(prior=None):
    """One shared immutable scope; caps sum to six even if all GPUs become free."""
    path = b.COMMON_ROOT / 'record.json'
    if path.exists():
        return validate_parallel_authorization(b.checked(path))
    prior = old_terminal_evidence() if prior is None else prior
    return b.publish(path, dict(schema='v65_v66_authorized_disjoint_parallel_continuation.v1',
        scientific_root=str(b.SCIENTIFIC_ROOT), scientific_protocol_id=b.BASE_PROTOCOL_ID,
        predecessor_root=str(b.PREDECESSOR_ROOT),
        authorization=dict(early_generation_question='五组先行生成并封存，暂不评分', early_generation_answer='同意',
            parallel_request='问题组并行处理，尽快恢复实验',
            exception_question='仅seed389-C05这一次已知梯度均值诊断失败的继续执行例外；保留FAIL和原始误差，不改正式梯度、不重放830条，其他状态、资源及数值检查不放宽',
            exception_answer='授权该单点例外并继续'),
        allowed_controls=parallel_scopes(),
        global_max_gpu_workers=6, max_workers_per_gpu=1, GPU_indices=list(range(8)),
        gpu_lease_root=b.base_protocol()['gpu_lease_root'],
        scientific_owner_lock=str(b.SCIENTIFIC_ROOT / 'owner.lock'),
        authorized_controls_use_shared_scientific_owner_lock=True,
        historical_exclusive_scientific_controller_is_excluded=True,
        each_control_has_exclusive_local_owner_and_supervisor_locks=True,
        initialization_resource_wait_and_draining_count_in_own_cap=True,
        caps_not_reallocated_automatically_when_other_control_idle=True,
        other_control_RAM_reservation_not_reduced_by_its_actual_RSS=True,
        original_global_scientific_budget=dict(generation_jobs=24, sessions=7458),
        scoring_calls_authorized=0, new_feedback_or_class_passes_authorized=0,
        completed_responses_or_training_repeated=False, old_failures_and_protocols_rewritten=False,
        created_epoch=time.time(), **prior))


def eligible_training_branches():
    values = {}
    for seed, arm in b.ELIGIBLE_COORDINATES:
        stage = b.SCIENTIFIC_ROOT / f'stages/seed{seed}/train_{arm}'
        accepted = b.checked(stage / 'accepted/record.json')
        exit_path = Path(accepted['actual_exit']['path'])
        values[f'seed{seed}/{arm}'] = dict(
            branch=b.entry(b.SCIENTIFIC_ROOT / f'branches/seed{seed}/{arm}/completed/record.json'),
            result=b.entry(stage / 'result/record.json'), accepted=b.entry(stage / 'accepted/record.json'),
            actual_exit=b.entry(exit_path), launch=b.entry(exit_path.parent.parent / 'launch/record.json'))
    return values


def freeze(source_commit):
    b.require(not ROOT.exists(), 'one fresh independent early-generation registration only')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=b.REPO, text=True).strip()
    source = {}
    for name in FILES:
        relative = 'trusted_data_synthesis/scripts/' + name
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), 'uncommitted V65 source: ' + name)
        source[name] = raw
    directory = ROOT / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in source.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return b.publish(directory / 'record.json', dict(schema='v65_frozen_unscored_generation_sources.v1',
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in source.items()},
        scientific_implementation=b.entry(b.SCIENTIFIC_ROOT / 'implementation/record.json'),
        predecessor_implementation=b.entry(b.PREDECESSOR_ROOT / 'implementation/record.json'),
        original_sources_modified=False, private_root_resource_lifecycle_adapters_explicit=True))


def checked_implementation(root=ROOT):
    global _VERIFIED_IMPLEMENTATION
    b.require(Path(root).resolve() == ROOT, 'foreign early-generation implementation root')
    if _VERIFIED_IMPLEMENTATION is not None:
        return _VERIFIED_IMPLEMENTATION
    value = b.checked(ROOT / 'implementation/record.json')
    b.require(value['committed_files'] == list(FILES) and set(value['sha256']) == set(FILES)
              and b.read_ref(value['scientific_implementation'])['id'] == b.BASE_IMPLEMENTATION_ID
              and b.read_ref(value['predecessor_implementation'])['id'] == b.PREDECESSOR_IMPLEMENTATION_ID,
              'early-generation source package or lineage differs')
    for name, expected in value['sha256'].items():
        b.require(b.sha(ROOT / 'implementation' / name) == expected, 'frozen V65 source changed: ' + name)
    _VERIFIED_IMPLEMENTATION = value
    return value


def checked_protocol(root=ROOT):
    global _VERIFIED_PROTOCOL
    b.require(Path(root).resolve() == ROOT, 'foreign early-generation protocol root')
    if _VERIFIED_PROTOCOL is not None:
        return _VERIFIED_PROTOCOL
    value = b.checked(ROOT / 'protocol/record.json')
    runtime = importlib.import_module('finqa_v65_runtime')
    evaluation = importlib.import_module('finqa_v65_evaluation')
    original = b.base_protocol()
    shared = validate_parallel_authorization(b.read_ref(value['parallel_authorization']))
    b.require(value['schema'] == SCHEMA and value['control_root'] == str(ROOT)
              and value['scientific_root'] == str(b.SCIENTIFIC_ROOT)
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['max_gpu_workers'] == 5 and value['max_workers_per_gpu'] == 1
              and value['global_total_limit'] == 6 and value['reserved_other_control_startup_gib'] == 64
              and shared['allowed_controls'][str(ROOT)]['max_gpu_workers'] == 5
              and shared['allowed_controls'][str(b.PEER_ROOT)]['max_gpu_workers'] == 1
              and value['resource_policy'] == runtime.resource_policy()
              and value['resource_recovery_policy'] == runtime.resource_recovery_policy()
              and value['memory_protection_policy'] == runtime.memory_protection_policy()
              and value['evaluation'] == evaluation.evaluation_contract()
              and value['implementation']['id'] == checked_implementation()['id'],
              'registered public-only generation or resource partition changed')
    for key in ('gpu_uuids', 'gpu_priority', 'cpu_affinity', 'gpu_lease_root', 'gpu_isolation_policy',
                'signal_policy', 'signal_source_bindings', 'auto_recovery_policy', 'allowed_gpu_indices'):
        b.require(value[key] == original[key], 'original operational hard contract changed: ' + key)
    b.require(b.read_ref(value['science_protocol_ref'])['id'] == b.BASE_PROTOCOL_ID
              and set(value['eligible_training_branches']) == {f'seed{s}/{a}' for s, a in b.ELIGIBLE_COORDINATES},
              'early-generation scientific roster changed')
    _VERIFIED_PROTOCOL = value
    return value


def checked_prepared(root=ROOT):
    b.require(Path(root).resolve() == ROOT, 'foreign generation preparation root')
    protocol = checked_protocol()
    value = b.checked(ROOT / 'prepared/record.json')
    b.require(value['schema'] == PREPARED_SCHEMA and value['protocol_id'] == protocol['id']
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['all_old_control_and_worker_identities_exited'] is True
              and value['generation_jobs'] == 20 and value['sessions'] == 6215
              and value['scoring_calls'] == 0 and value['private_references_read'] is False,
              'twenty-job public generation is not prepared')
    b.read_ref(value['inherited_journal'])
    b.read_ref(value['generation_plan'])
    return value


def prepare(source_commit):
    loaded = modules()
    b.require(not ROOT.exists(), 'early generation may only be freshly registered once')
    prior = old_terminal_evidence()
    shared = parallel_authorization(prior)
    original = b.base_protocol()
    implementation = freeze(source_commit)
    body = dict(schema=SCHEMA, control_root=str(ROOT), scientific_root=str(b.SCIENTIFIC_ROOT),
        scientific_protocol_id=b.BASE_PROTOCOL_ID, science_protocol_ref=b.entry(b.SCIENTIFIC_ROOT / 'protocol/record.json'),
        source_commit=implementation['source_commit'], implementation=b.entry(ROOT / 'implementation/record.json'),
        parallel_authorization=b.entry(b.COMMON_ROOT / 'record.json'),
        eligible_training_branches=eligible_training_branches(),
        max_gpu_workers=5, max_workers_per_gpu=1, global_total_limit=6,
        reserved_other_control_startup_gib=64, memory_protection_policy=loaded['runtime'].memory_protection_policy(),
        resource_policy=loaded['runtime'].resource_policy(),
        resource_recovery_policy=loaded['runtime'].resource_recovery_policy(),
        evaluation=loaded['evaluation'].evaluation_contract(),
        inherited_resource_wait_seconds=b.read_ref(prior['inherited_journal'])['resource_wait_seconds'],
        created_epoch=time.time(), scoring_calls_authorized=0, CPU_registration_only=True,
        predecessor_terminal_evidence=prior, original_protocols_and_failures_unchanged=True)
    for key in ('gpu_uuids', 'gpu_priority', 'cpu_affinity', 'gpu_lease_root', 'gpu_isolation_policy',
                'signal_policy', 'signal_source_bindings', 'auto_recovery_policy', 'allowed_gpu_indices'):
        body[key] = original[key]
    protocol = b.publish(ROOT / 'protocol/record.json', body)
    # Plan and actual snapshot validation execute from the frozen package, not
    # from the preparation process's already imported workspace modules.
    command = [str(b.PYTHON), '-c',
        'import finqa_v65_registration as r; r.modules(); r.prepare_plan(); print("V65_PUBLIC_PLAN_PREPARED")']
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'implementation'), CUDA_VISIBLE_DEVICES='')
    subprocess.run(command, cwd=b.REPO, env=environment, check=True)
    return protocol


def prepare_plan():
    b.require(Path(__file__).resolve().parent == ROOT / 'implementation', 'prepare only through frozen V65 source')
    protocol = checked_protocol()
    plan = importlib.import_module('finqa_v65_evaluation').prepare_jobs(ROOT)
    prior = protocol['predecessor_terminal_evidence']
    return b.publish(ROOT / 'prepared/record.json', dict(schema=PREPARED_SCHEMA,
        protocol_id=protocol['id'], control_protocol_id=protocol['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        generation_plan=b.entry(ROOT / 'evaluations/registration/record.json'),
        generation_jobs=len(plan['jobs']), sessions=sum(v['denominator'] for v in plan['jobs'].values()),
        private_references_read=False, scoring_calls=0, new_scientific_calls=0,
        prepared_epoch=time.time(), **prior))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = prepare(args.source_commit)
    print(json.dumps(dict(id=result['id'], schema=result['schema']), sort_keys=True))
