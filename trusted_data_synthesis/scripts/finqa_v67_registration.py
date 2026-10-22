"""Freeze CPU-only repair and four final unscored generations independently."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import time

import finqa_v67_binding as b

ROOT = b.ROOT
FILES = tuple('finqa_v67_' + item + '.py' for item in
              ('binding', 'registration', 'runtime', 'evaluation', 'worker', 'sealing', 'controller', 'entry'))
SCHEMA = 'v67_serialization_repair_and_final_generation_protocol.v1'
PREPARED_SCHEMA = 'v67_twenty_CPU_adoptions_and_four_final_jobs_prepared.v1'
_VERIFIED_IMPLEMENTATION = None
_VERIFIED_PROTOCOL = None


def modules():
    b.source_module('finqa_v63_entry').install_registered_auxiliary()
    b.install_scientific_paths()
    return {name: importlib.import_module('finqa_v67_' + name) for name in
            ('runtime', 'evaluation', 'worker', 'sealing', 'controller', 'entry')}


def same_live_identity(pid, birth):
    try:
        fields = Path('/proc/%s/stat' % pid).read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return fields[19] == birth and fields[0] not in ('Z', 'X', 'x')


def training_terminal_evidence():
    root = b.RECOVERY_ROOT
    control = b.checked(root / 'closeout/record.json')
    supervisor = b.checked(root / 'supervisor/closeout/record.json')
    barrier = b.checked(b.SCIENTIFIC_ROOT / 'training_barrier/record.json')
    b.require(control['status'] == supervisor['status'] == 'COMPLETE'
              and control['active_workers'] == 0
              and barrier['protocol_id'] == b.BASE_PROTOCOL_ID
              and all(barrier[key] is True for key in ('all_six_new_branches_complete',
                  'all_six_894_snapshots_sealed', 'all_dispatched_training_workers_exited'))
              and barrier['active_children'] == [], 'all six training branches must already be complete')
    for path in (root / 'supervisor/launch/record.json', root / 'controllers/attempt0001/launch/record.json'):
        value = b.checked(path)
        b.require(not same_live_identity(value['pid'], value['birth']), 'completed training control remains alive')
    return dict(training_closeout=b.entry(root / 'closeout/record.json'),
        training_supervisor_closeout=b.entry(root / 'supervisor/closeout/record.json'),
        six_branch_training_barrier=b.entry(b.SCIENTIFIC_ROOT / 'training_barrier/record.json'),
        training_controls_actual_exited=True)


def eligible_training_branches():
    stage = b.SCIENTIFIC_ROOT / 'stages/seed389/train_C05'
    accepted = b.checked(stage / 'accepted/record.json')
    exit_path = Path(accepted['actual_exit']['path'])
    return {'seed389/C05': dict(
        branch=b.entry(b.SCIENTIFIC_ROOT / 'branches/seed389/C05/completed/record.json'),
        result=b.entry(stage / 'result/record.json'), accepted=b.entry(stage / 'accepted/record.json'),
        actual_exit=b.entry(exit_path), launch=b.entry(exit_path.parent.parent / 'launch/record.json'))}


def peer_evidence():
    protocol = b.checked(b.SOURCE_GENERATION_ROOT / 'protocol/record.json')
    plan = b.checked(b.SOURCE_GENERATION_ROOT / 'evaluations/registration/record.json')
    journal = b.checked(b.SOURCE_GENERATION_ROOT / 'journal/state.json')
    b.require(protocol['id'] == plan['protocol_id'] == journal['protocol_id'] == b.EARLY_PROTOCOL_ID
              and plan['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and protocol['max_workers_per_gpu'] == 1 and len(plan['jobs']) == 20
              and sum(row['denominator'] for row in plan['jobs'].values()) == 6215,
              'original twenty-job roster, identity or legacy one-slot bound changed')
    prepared = dict(peer_job_roster=plan['jobs'], peer_residual_roster=list(b.RESIDUAL_PEER_JOBS),
                    peer_protocol_id=b.EARLY_PROTOCOL_ID)
    terminal_path = b.SOURCE_GENERATION_ROOT / 'closeout/record.json'
    terminal = b.checked(terminal_path) if terminal_path.exists() else None
    receipt = importlib.import_module('finqa_v67_controller').checked_peer_snapshot(journal, prepared, terminal=terminal)
    b.require(receipt is not None, 'peer journal must be freshly observed before registration')
    return prepared, journal, dict(peer_source_protocol=b.entry(b.SOURCE_GENERATION_ROOT / 'protocol/record.json'),
        peer_source_plan=b.entry(b.SOURCE_GENERATION_ROOT / 'evaluations/registration/record.json'),
        peer_observed_capacity_bound=receipt)


def freeze(source_commit):
    b.require(not ROOT.exists(), 'one fresh independent final-generation registration only')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=b.REPO, text=True).strip()
    source = {}
    for name in FILES:
        relative = 'trusted_data_synthesis/scripts/' + name
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), 'uncommitted V67 source: ' + name)
        source[name] = raw
    directory = ROOT / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in source.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return b.publish(directory / 'record.json', dict(schema='v67_frozen_generation_and_CPU_repair_sources.v1',
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in source.items()},
        scientific_implementation=b.entry(b.SCIENTIFIC_ROOT / 'implementation/record.json'),
        predecessor_implementation=b.entry(b.PREDECESSOR_ROOT / 'implementation/record.json'),
        early_generation_implementation=b.entry(b.SOURCE_GENERATION_ROOT / 'implementation/record.json'),
        original_sources_modified=False, private_root_resource_lifecycle_adapters_explicit=True))


def checked_implementation(root=ROOT):
    global _VERIFIED_IMPLEMENTATION
    b.require(Path(root).resolve() == ROOT, 'foreign completion implementation root')
    if _VERIFIED_IMPLEMENTATION is not None:
        return _VERIFIED_IMPLEMENTATION
    value = b.checked(ROOT / 'implementation/record.json')
    b.require(value['committed_files'] == list(FILES) and set(value['sha256']) == set(FILES)
              and b.read_ref(value['scientific_implementation'])['id'] == b.BASE_IMPLEMENTATION_ID
              and b.read_ref(value['predecessor_implementation'])['id'] == b.PREDECESSOR_IMPLEMENTATION_ID
              and b.read_ref(value['early_generation_implementation'])['id'] == b.EARLY_IMPLEMENTATION_ID,
              'completion source package or frozen lineage differs')
    for name, expected in value['sha256'].items():
        b.require(b.sha(ROOT / 'implementation' / name) == expected, 'frozen V67 source changed: ' + name)
    _VERIFIED_IMPLEMENTATION = value
    return value


def checked_protocol(root=ROOT):
    global _VERIFIED_PROTOCOL
    b.require(Path(root).resolve() == ROOT, 'foreign completion protocol root')
    if _VERIFIED_PROTOCOL is not None:
        return _VERIFIED_PROTOCOL
    value = b.checked(ROOT / 'protocol/record.json')
    runtime = importlib.import_module('finqa_v67_runtime')
    evaluation = importlib.import_module('finqa_v67_evaluation')
    original = b.base_protocol()
    b.require(value['schema'] == SCHEMA and value['control_root'] == str(ROOT)
              and value['scientific_root'] == str(b.SCIENTIFIC_ROOT)
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['max_gpu_workers'] == 3 and value['max_workers_per_gpu'] == 2
              and value['own_max_workers_per_gpu'] == 1
              and value['global_total_limit'] == 6 and value['reserved_cross_control_startup_gib'] == 208
              and value['reserved_peer_gpu_workers'] == 3 and value['reserved_peer_worker_startup_gib'] == 48
              and value['cpu_seal_rss_limit_gib'] == 64 and value['max_cpu_sealing_workers'] == 1
              and value['gpu_priority'] == list(b.GPU_PRIORITY)
              and value['gpu_lease_root'] == b.gpu_slot_policy()['second_slot_lease_root']
              and value['legacy_gpu_lease_root'] == original['gpu_lease_root']
              and value['gpu_slot_policy'] == b.gpu_slot_policy()
              and value['resource_policy'] == runtime.resource_policy()
              and value['resource_recovery_policy'] == runtime.resource_recovery_policy()
              and value['memory_protection_policy'] == runtime.memory_protection_policy()
              and value['evaluation'] == evaluation.evaluation_contract()
              and value['implementation']['id'] == checked_implementation()['id']
              and value['scoring_calls_authorized'] == value['new_training_or_feedback_calls_authorized'] == 0,
              'registered generation, slot policy or CPU resource partition changed')
    for key in ('gpu_uuids', 'cpu_affinity', 'gpu_isolation_policy', 'signal_policy',
                'signal_source_bindings', 'auto_recovery_policy', 'allowed_gpu_indices'):
        b.require(value[key] == original[key], 'original hard operational contract changed: ' + key)
    b.require(b.read_ref(value['science_protocol_ref'])['id'] == b.BASE_PROTOCOL_ID
              and b.read_ref(value['peer_source_protocol'])['id'] == b.EARLY_PROTOCOL_ID
              and set(value['eligible_training_branches']) == {'seed389/C05'},
              'scientific identity or generation roster changed')
    _VERIFIED_PROTOCOL = value
    return value


def checked_prepared(root=ROOT):
    b.require(Path(root).resolve() == ROOT, 'foreign completion preparation root')
    protocol = checked_protocol()
    value = b.checked(ROOT / 'prepared/record.json')
    b.require(value['schema'] == PREPARED_SCHEMA and value['protocol_id'] == protocol['id']
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['generation_jobs'] == 4 and value['sessions'] == 1243
              and value['adopted_jobs'] == 20 and value['adopted_sessions'] == 6215
              and value['peer_protocol_id'] == b.EARLY_PROTOCOL_ID
              and value['peer_residual_roster'] == list(b.RESIDUAL_PEER_JOBS)
              and value['scoring_calls'] == 0 and value['private_references_read'] is False,
              'twenty adoptions and four final public jobs are not prepared')
    old_plan = b.read_ref(protocol['peer_source_plan'])
    b.require(value['peer_job_roster'] == old_plan['jobs'], 'original repair roster changed')
    b.read_ref(value['inherited_journal'])
    b.read_ref(value['generation_plan'])
    return value


def prepare(source_commit):
    loaded = modules()
    b.require(not ROOT.exists(), 'completion may only be freshly registered once')
    training = training_terminal_evidence()
    peer, journal, peer_refs = peer_evidence()
    original = b.base_protocol()
    implementation = freeze(source_commit)
    b.publish(ROOT / 'inherited_peer_journal/record.json', journal)
    body = dict(schema=SCHEMA, control_root=str(ROOT), scientific_root=str(b.SCIENTIFIC_ROOT),
        scientific_protocol_id=b.BASE_PROTOCOL_ID, science_protocol_ref=b.entry(b.SCIENTIFIC_ROOT / 'protocol/record.json'),
        source_commit=implementation['source_commit'], implementation=b.entry(ROOT / 'implementation/record.json'),
        eligible_training_branches=eligible_training_branches(), training_terminal_evidence=training,
        max_gpu_workers=3, max_workers_per_gpu=2, own_max_workers_per_gpu=1, global_total_limit=6,
        max_cpu_sealing_workers=1, cpu_seal_rss_limit_gib=64,
        reserved_cross_control_startup_gib=208, reserved_peer_gpu_workers=3, reserved_peer_worker_startup_gib=48,
        gpu_priority=list(b.GPU_PRIORITY), gpu_slot_policy=b.gpu_slot_policy(),
        gpu_lease_root=b.gpu_slot_policy()['second_slot_lease_root'], legacy_gpu_lease_root=original['gpu_lease_root'],
        memory_protection_policy=loaded['runtime'].memory_protection_policy(),
        resource_policy=loaded['runtime'].resource_policy(), resource_recovery_policy=loaded['runtime'].resource_recovery_policy(),
        evaluation=loaded['evaluation'].evaluation_contract(),
        inherited_resource_wait_seconds=journal['resource_wait_seconds'],
        inherited_journal=b.entry(ROOT / 'inherited_peer_journal/record.json'),
        created_epoch=time.time(), scoring_calls_authorized=0, new_training_or_feedback_calls_authorized=0,
        CPU_registration_only=True, original_protocols_and_failures_unchanged=True,
        authorization=dict(repair_and_generate='修复问题，此外最后一组是否可以开始生成了',
            priority='优先GPU0/6/7，忙时允许使用其他空卡',
            two_slots='解除每卡一个worker的限制，当前三卡利用率较低，允许两个任务'),
        **peer, **peer_refs)
    for key in ('gpu_uuids', 'cpu_affinity', 'gpu_isolation_policy', 'signal_policy',
                'signal_source_bindings', 'auto_recovery_policy', 'allowed_gpu_indices'):
        body[key] = original[key]
    protocol = b.publish(ROOT / 'protocol/record.json', body)
    command = [str(b.PYTHON), '-c',
        'import finqa_v67_registration as r; r.modules(); r.prepare_plan(); print("V67_PUBLIC_PLAN_PREPARED")']
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'implementation'), CUDA_VISIBLE_DEVICES='')
    subprocess.run(command, cwd=b.REPO, env=environment, check=True)
    return protocol


def prepare_plan():
    b.require(Path(__file__).resolve().parent == ROOT / 'implementation', 'prepare only through frozen V67 source')
    protocol = checked_protocol()
    plan = importlib.import_module('finqa_v67_evaluation').prepare_jobs(ROOT)
    return b.publish(ROOT / 'prepared/record.json', dict(schema=PREPARED_SCHEMA,
        protocol_id=protocol['id'], control_protocol_id=protocol['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        generation_plan=b.entry(ROOT / 'evaluations/registration/record.json'),
        generation_jobs=len(plan['jobs']), sessions=sum(v['denominator'] for v in plan['jobs'].values()),
        adopted_jobs=20, adopted_sessions=6215, private_references_read=False, scoring_calls=0,
        new_scientific_calls=0, prepared_epoch=time.time(),
        **{key: protocol[key] for key in ('peer_job_roster', 'peer_residual_roster', 'peer_protocol_id', 'inherited_journal')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = prepare(args.source_commit)
    print(json.dumps(dict(id=result['id'], schema=result['schema']), sort_keys=True))
