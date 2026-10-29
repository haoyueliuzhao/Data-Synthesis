"""Register one C-only initialized T1/Full path with two updates and one probe.

Only this experiment's new directory is written. Original model checkpoints,
scores, failures and frozen sources are immutable inputs, not resume targets.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import finqa_v76_binding as binding

ROOT, REPO = binding.ROOT, binding.REPO
SCHEMA = 'v76_fixed_demonstration_two_window_paired_protocol.v1'
IMPLEMENTATION_SCHEMA = 'v76_frozen_continuous_Full_implementation.v1'
PREPARED_SCHEMA = 'v76_continuous_Full_preparation_complete.v1'
FILES = tuple('finqa_v76_' + name + '.py' for name in (
    'binding', 'registration', 'entry', 'signals', 'resources', 'controller', 'worker',
    'training', 'temperature', 'runtime', 'diagnostics', 'evaluation', 'queue_base',
    'analysis', 'preflight', 'prepare_cpu', 'mixed_math', 'task_cache'))
MINIMUM_FREE_DISK_BYTES = 128 * 1024 ** 3
require, checked, publish = binding.require, binding.checked, binding.publish
_IMPLEMENTATION = None
_PROTOCOL = None


def scientific_contract():
    return dict(schema='v76_fixed_teacher_two_window_paired_Full_contract.v1',
        parent='original complete P1192',seed=137,independent_parent_count=1,
        initial_learning_rate=1e-4,learning_rate=1e-5,restore_before_only_LR_change=True,
        branches=['A_Full','D_fixed'],actual_parameter_points=[1192,1490,1788],
        applied_outer_steps=[1192,1490],terminal_probe_step=1788,terminal_probe_applied=False,
        Full_windows=[[1193,1490],[1491,1788]],fixed_new_window=[1491,1788],
        fixed_first_window='read-only V75 S1490',new_optimizer_updates=894,
        new_Full_optimizer_updates=596,new_fixed_optimizer_updates=298,
        logical_updates_per_branch=596,reused_optimizer_updates=298,new_task_exposures=4464,
        updates_per_window=298,task_exposures_per_window=1488,four_task_tail_batches_per_window=2,
        new_schedule_epochs=[11,12],same_new_window_schedule_both_branches=True,
        old_schedule_prefix_unchanged=True,old_execution_plans_modified=False,
        automatic_old_driver_outer_disabled=True,exactly_once_explicit_outer_commit=True,
        teacher_source='V75 admitted179 complete teacher suffixes at111 tasks',
        teacher_initial_count=101,teacher_post_count=78,new_teacher_sessions=0,
        teacher_support_or_slot_weights_changed=False,teacher_added_to1360_adjustable_states=False,
        initial_teacher_weight=0.25,post_teacher_weight=0.25,missing_slot_mass_returns_to_old=True,
        training_loss='sum mu_x[c_x sum pi_xz old_loss_xz + w0_x teacher0_loss_x + w1_x teacher1_loss_x]',
        full_G='sum mu_x[c_x sum pi_xz old_g_xz + w0_x teacher0_g_x + w1_x teacher1_g_x]',
        contribution='mu_x*c_x*inner(Adam_pullback_on_full_mixed_G(-gJ),old_g_xz-sum_pi_old_g_x)',
        c_x_counted_once=True,teacher_gradient_enters_virtual_Adam_and_pullback=True,
        historical_C_G_theta_bar_pullback_reused=False,analysis_RNG_restored=True,
        contribution_exponent=0.8,novelty_exponent=0.2,lambda_current=4.0,lambda_prior=1.0,
        epsilon=0.05,novelty_temperature=1.0,rms_floor=1e-8,prior_never_reset=True,
        feedback_temperature=1.0,feedback_draw_seeds=[101,103],feedback_tasks_per_draw=350,
        feedback_denominator_per_point=700,new_feedback_sessions=2100,
        zero_reward_sessions_remain_in_denominator=True,
        formal_q_uses_complete700=True,mean_of_normalized_draw_q_forbidden=True,
        draw_diagnostic_denominator=350,diagnostic_extra_VJPs_per_point=2,
        diagnostic_extra_VJPs_total=6,diagnostic_extra_centered_inner_products_total=6,
        new_complete_class_passes=3,tasks_per_pass=744,states_per_pass=1360,
        packages_per_pass=2468,effective_old_rows_per_pass=4974,class_shards_per_point=4,
        new_complete_class_tasks=2232,new_effective_old_class_rows=14922,
        task_atomic_old_and_fixed_teacher_gradients=True,
        new_evaluation_endpoints=['A1490','A1788','D1788'],new_evaluation_sessions=2649,
        new_logical_sessions=4749,new_calibration_sessions=0,new_test_sessions=0,
        new_special96_sessions=0,main_effect='EA(A1788)-EA(D1788)',
        fixed_maintenance='EA(D1788)-EA(S1490)',first_window_effect='EA(A1490)-EA(S1490)',
        final_parent_comparisons=['A1788-P1192','D1788-P1192'],
        all_training_probe_and_generation_actual_exits_before_scoring=True,
        no_midpoint_score_dependent_schedule=True,full_denominator_I_W_R_UNKNOWN=True,
        no_call_stage_denominator=883,UNKNOWN_as_zero=False,
        source_cluster_replicates=10000,source_cluster_seed=20261018,
        source_cluster_scope='fixed paths and reused development panel, not seed uncertainty',
        diagnostics_primary='adjustable-task-normalized mu',diagnostics_secondary='all-task mu',
        diagnostics=['R=current_to_q','G=current_to_frozen_fixed_point','D=successive_frozen_targets','two_draw_C_q','EA_and_no_call'],
        full_online_convergence_proved=False,new_independent_seeds=0,
        total_compute_equal=False,equal_inner_training_dose=True,
        no_performance_advancement_gate=True,no_material_LR_lambda_temperature_or_seed_search=True,
        external_API_calls=0,automatic_followup_authorized=False,
        V75_failure_reclassified=False,old_scientific_sources_modified=False)


def modules():
    binding.install_registered_auxiliary()
    return {name: importlib.import_module('finqa_v76_' + name) for name in
            ('training', 'runtime', 'resources', 'controller', 'evaluation', 'diagnostics', 'signals', 'analysis')}


def _same_reference(left, right):
    return Path(left['path']).resolve() == Path(right['path']).resolve() and left['sha256'] == right['sha256']


def parent_metadata():
    old=binding.checked(binding.V75_ROOT/'protocol/record.json')
    result=binding.checked(binding.V75_ROOT/'points/step1192/train/result/record.json')
    accepted=binding.checked(binding.V75_ROOT/'points/step1192/train/accepted/record.json')
    actual=binding.read_ref(accepted['actual_exit'])
    require(result['status']=='COMPLETE' and result['final_step']==1490 and result['new_optimizer_updates']==298
        and result['outer_updates']==0 and actual['returncode']==0 and actual['actual_waitpid_observed']
        and accepted['result_id']==result['id'],'V75 fixed first window must be actually accepted')
    return dict(old['initial_parent'], fixed_checkpoint=result['final_checkpoint'],
        V75_fixed_result=binding.entry(binding.V75_ROOT/'points/step1192/train/result/record.json'),
        V75_fixed_actual_exit=accepted['actual_exit'],old_first_window_retrained=False)


def historical_source_bindings():
    reference=binding.entry(binding.V75_ROOT/'implementation/record.json')
    manifest=binding.read_ref(reference)
    require(manifest['id']==binding.V75_IMPLEMENTATION_ID,'V75 implementation identity differs')
    sources=dict(manifest['source_bindings'])
    sources.update({str(binding.V75_ROOT/'implementation'/name):sha for name,sha in manifest['sha256'].items()})
    return dict(manifests={'V75':reference},source_bindings=sources,
        frozen_source_root=manifest['frozen_source_root'],
        explicit_V25_byte_identical_alias=str(binding.source_module('finqa_v63_entry').AUXILIARY_WORKSPACE_ALIAS.resolve()))


def prepare_cpu():
    from finqa_v76_prepare_cpu import policy
    from finqa_v76_resources import controller_runtime
    rt=controller_runtime();directory=ROOT/'preflight_execution/attempt0001'
    require(not directory.exists(),'CPU preparation is single-use; previous failure is not retried')
    while rt.host_memory()['available_bytes']<policy()['startup_required_available_bytes']:
        require(not (ROOT/'STOP').exists(),'explicit stop before preparation CPU');time.sleep(5)
    publish(directory/'intent/record.json',dict(only_one_attempt=True,resource_policy=policy()))
    command=[str(binding.PYTHON),'-u',str(ROOT/'implementation/finqa_v76_prepare_cpu.py')]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONUNBUFFERED='1',
        PYTHONPATH=os.pathsep.join((str(ROOT/'implementation'),binding.install_scientific_paths()['frozen_source_root'])))
    with (directory/'output.log').open('xb') as log:
        process=subprocess.Popen(command,cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT)
    birth=rt.birth(process.pid)
    publish(directory/'launch/record.json',dict(pid=process.pid,birth=birth,command=command))
    code=process.wait()
    publish(directory/'actual_exit/record.json',dict(pid=process.pid,birth=birth,
        returncode=code,actual_waitpid_observed=True))
    require(code==0,'independent V75 CPU repair/source overlap failed; do not restart automatically')
    result=checked(directory/'result/record.json');resources=binding.read_ref(result['resources'])
    require(result['status']==resources['status']=='COMPLETE' and resources['all_gates_passed']
        and resources['CUDA_initialized'] is False and resources['pid']==result['pid']==process.pid
        and resources['birth']==birth,'CPU preparation evidence/identity differs')
    publish(ROOT/'preflight_execution/accepted/record.json',dict(status='COMPLETE',
        result=binding.entry(directory/'result/record.json'),resources=result['resources'],
        actual_exit=binding.entry(directory/'actual_exit/record.json'),
        actual_exit_zero=True,resources_passed=True,analysis=result['analysis']))
    return result['analysis']


def freeze(source_commit, lineage):
    require(not ROOT.exists(), 'V76 requires its one fresh independent scientific root')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=REPO, text=True).strip()
    sources = {}
    for filename in FILES:
        relative = 'trusted_data_synthesis/scripts/' + filename
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == binding.sha(REPO / relative),
                'uncommitted V76 production source: ' + filename)
        sources[filename] = raw
    # The original immutable manifests bind historical bytes. The mandatory
    # cold-entry audit hashes every source actually imported by this workflow;
    # do not rescan unrelated registered historical modules during preparation.
    destination = ROOT / 'implementation'
    destination.mkdir(parents=True, exist_ok=False)
    for filename, raw in sources.items():
        with (destination / filename).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return publish(destination / 'record.json', dict(schema=IMPLEMENTATION_SCHEMA,
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        historical_manifests=lineage['manifests'], source_bindings=lineage['source_bindings'],
        frozen_source_root=lineage['frozen_source_root'],
        explicit_V25_byte_identical_alias=lineage['explicit_V25_byte_identical_alias'],
        historical_source_verification='immutable manifests plus mandatory actual imported-source audit',
        original_scientific_sources_modified=False, historical_roots_writable=False))


def checked_implementation(root=ROOT):
    global _IMPLEMENTATION
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V76 implementation root')
    if _IMPLEMENTATION is None:
        value = checked(ROOT / 'implementation/record.json')
        require(value['schema'] == IMPLEMENTATION_SCHEMA and value['committed_files'] == list(FILES)
                and set(value['sha256']) == set(FILES)
                and value['original_scientific_sources_modified'] is False,
                'new registered implementation set changed')
        for filename, expected in value['sha256'].items():
            require(binding.sha(ROOT / 'implementation' / filename) == expected,
                    'new frozen source bytes changed: ' + filename)
        for reference in value['historical_manifests'].values():
            binding.read_ref(reference)
        _IMPLEMENTATION = value
    return _IMPLEMENTATION


def allowed_import_sources(root=ROOT):
    implementation = checked_implementation(root)
    return dict(implementation['source_bindings'], **{
        str(ROOT / 'implementation' / name): expected for name, expected in implementation['sha256'].items()})


def _policy_fields(loaded):
    isolation = binding.source_module('finqa_v63_gpu_isolation')
    return dict(scientific_contract=scientific_contract(),
        training_contract=loaded['training'].training_contract(),
        evaluation=loaded['evaluation'].evaluation_contract(),
        diagnostics_policy=loaded['diagnostics'].policy(),
        resource_policy=loaded['resources'].resource_policy(),
        resource_recovery_policy=loaded['resources'].resource_recovery_policy(),
        final_analysis_resource_policy=loaded['analysis'].resource_policy(),
        auto_recovery_policy=loaded['controller'].auto_recovery_policy(),
        gpu_isolation_policy=isolation.gpu_isolation_policy(),
        signal_policy=loaded['signals'].signals_policy(),
        signal_source_bindings=loaded['signals'].external_source_bindings())


def checked_protocol(root=ROOT):
    global _PROTOCOL
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V76 scientific root')
    if _PROTOCOL is None:
        value = checked(ROOT / 'protocol/record.json')
        loaded = modules()
        require(value['schema'] == SCHEMA and value['output_root'] == str(ROOT)
                and value['implementation']['id'] == checked_implementation(root)['id']
                and all(value[key] == row for key, row in _policy_fields(loaded).items())
                and value['allowed_gpu_indices'] == list(range(8))
                and value['gpu_uuids'] == loaded['resources'].GPU_UUIDS
                and value['cpu_affinity'] == loaded['resources'].CPU_AFFINITY
                and value['gpu_priority'] == list(binding.GPU_PRIORITY)
                and value['max_gpu_workers'] == 6 and value['max_workers_per_gpu'] == 1
                and value['inherited_resource_wait_seconds'] == 0.0
                and value['no_wallclock_deadlines'] is True
                and value['jobs']==loaded['controller'].planned_jobs(),
                'new scientific dose, resources, diagnostics, recovery or signal contract changed')
        _PROTOCOL = value
    return _PROTOCOL


def checked_prepared(root=ROOT):
    protocol = checked_protocol(root)
    value = checked(ROOT / 'prepared/record.json')
    require(value['schema'] == PREPARED_SCHEMA and value['protocol']['id'] == protocol['id']
            and value['new_feedback_sessions'] == 2100 and value['new_optimizer_updates'] == 894
            and value['new_evaluation_sessions'] == 2649
            and value['new_complete_class_tasks'] == 2232
            and value['scientific_supervisor_started'] is False and value['CUDA_initialized'] is False,
            'prepared endpoint or fixed new dose changed')
    binding.read_ref(value['initial_point'])
    binding.read_ref(value['fixed_initial_point'])
    return value


def inherited_CPU_preparation():
    old=binding.PREPARATION_ROOT
    failure=checked(old/'activation_failure_01/record.json')
    manifest=checked(old/'implementation/record.json')
    require(failure['status']=='ACTIVATION_PRECONDITION_FAILED_ZERO_DISPATCH'
        and failure['activation_intent_created'] is False and failure['new_GPU_workers']==0
        and manifest['id']=='c05c1a17cc7f2e36b10ffd230babe92979e8d64c73fb50cc9e7e7b878b0215cf'
        and not (old/'activation/intent/record.json').exists()
        and not (old/'supervisor/launch/record.json').exists(),
        'only the untouched zero-dispatch preparation may be inherited')
    allowed_changes={'finqa_v76_binding.py','finqa_v76_controller.py','finqa_v76_registration.py'}
    for name,sha in manifest['sha256'].items():
        if name not in allowed_changes:
            require(binding.sha(ROOT/'implementation'/name)==sha,'scientific/CPU preparation source changed: '+name)
    accepted_ref=binding.entry(old/'preflight_execution/accepted/record.json')
    accepted=binding.read_ref(accepted_ref);actual=binding.read_ref(accepted['actual_exit'])
    result=binding.read_ref(accepted['result']);resources=binding.read_ref(accepted['resources'])
    require(accepted['status']=='COMPLETE' and actual['actual_waitpid_observed'] and actual['returncode']==0
        and result['status']==resources['status']=='COMPLETE' and resources['all_gates_passed']
        and resources['CUDA_initialized'] is False,'prior independent CPU preparation did not succeed')
    require(checked(old/'protocol/record.json')['scientific_contract']==scientific_contract(),
        'zero-dispatch entry repair may not change the scientific dose or objective')
    publish(ROOT/'inherited_preparation/record.json',dict(schema='v76_zero_dispatch_preparation_inheritance.v1',
        status='COMPLETE',original_failure=binding.entry(old/'activation_failure_01/record.json'),
        previous_prepared=binding.entry(old/'prepared/record.json'),preflight_accepted=accepted_ref,
        allowed_operational_source_changes=sorted(allowed_changes),scientific_sources_unchanged=True,
        CPU_repair_or_source_overlap_reexecuted=False,new_model_calls=0,new_native_scores=0,
        new_bootstrap=0,new_GPU_workers=0))
    return result['analysis'],accepted_ref


def prepare(source_commit):
    require(not ROOT.exists(),'V76 requires one fresh independent experiment directory')
    loaded=modules();parent=parent_metadata();lineage=historical_source_bindings()
    policies=_policy_fields(loaded);free_disk=shutil.disk_usage(ROOT.parent).free
    require(free_disk>=MINIMUM_FREE_DISK_BYTES,'insufficient disk for three fresh mixed-gradient points and894 checkpoints')
    implementation=freeze(source_commit,lineage)
    cpu,preflight_ref=inherited_CPU_preparation()
    old=binding.checked(binding.V75_ROOT/'protocol/record.json');jobs=loaded['controller'].planned_jobs()
    protocol=publish(ROOT/'protocol/record.json',dict(schema=SCHEMA,output_root=str(ROOT),
        source_commit=implementation['source_commit'],authorization='参照审计修订并开展后续实验',
        user_plan=binding.file_ref(binding.USER_PLAN),implementation=binding.entry(ROOT/'implementation/record.json'),
        source_scientific_protocol=binding.entry(binding.V63_ROOT/'protocol/record.json'),
        initial_parent=parent,demonstration_materials=binding.entry(binding.V75_ROOT/'materials/record.json'),
        reused_evaluation=cpu['reused_evaluation'],evaluation_source_registration=cpu['evaluation_source_registration'],
        old_evaluation_registration=old['old_evaluation_registration'],
        v75_cpu_revision=cpu['v75_cpu_revision'],source_overlap=cpu['source_overlap'],
        preflight_accepted=preflight_ref,prior_zero_dispatch_failure=binding.entry(binding.PREPARATION_ROOT/'activation_failure_01/record.json'),
        jobs=jobs,allowed_gpu_indices=list(range(8)),gpu_uuids=loaded['resources'].GPU_UUIDS,
        cpu_affinity=loaded['resources'].CPU_AFFINITY,gpu_priority=list(binding.GPU_PRIORITY),
        gpu_lease_root=old['gpu_lease_root'],max_gpu_workers=6,max_workers_per_gpu=1,
        initialization_wait_and_draining_count_as_workers=True,no_wallclock_deadlines=True,
        inherited_resource_wait_seconds=0.0,waiting_statistics_are_for_new_independent_experiment=True,
        historical_failures_authorizations_and_wait_stats_unchanged=True,
        new_account_cron=False,external_GPU_holders=False,performance_based_branching=False,
        terminal_probe_never_committed=True,**policies))
    loaded['resources'].validate_registered_contract(protocol)
    loaded['training'].prepare_point(ROOT,1192,protocol['id'],parent['checkpoint'])
    loaded['training'].prepare_point(ROOT,1490,protocol['id'],parent['fixed_checkpoint'],arm='D')
    return publish(ROOT/'prepared/record.json',dict(schema=PREPARED_SCHEMA,
        protocol=binding.entry(ROOT/'protocol/record.json'),initial_point=binding.entry(ROOT/'points/step1192/context/record.json'),
        fixed_initial_point=binding.entry(ROOT/'fixed/points/step1490/context/record.json'),
        fixed_jobs=jobs,initial_parent=parent,new_feedback_sessions=2100,
        new_optimizer_updates=894,new_evaluation_sessions=2649,new_total_sessions=4749,
        new_complete_class_tasks=2232,new_effective_class_rows=14922,
        disk_free_bytes=free_disk,disk_minimum_admission_bytes=MINIMUM_FREE_DISK_BYTES,
        scientific_supervisor_started=False,CUDA_initialized=False,model_loaded=False,
        preparation_actual_parent_state_tensors_read=True,new_optimizer_calls=0,
        frozen_entry_check_imports_still_required=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args(argv)
    result = prepare(args.source_commit)
    print(json.dumps(dict(id=result['id'], protocol=result['protocol'],
        initial_point=result['initial_point'], scientific_supervisor_started=False), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
