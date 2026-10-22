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

import finqa_v70_binding as binding

ROOT, REPO = binding.ROOT, binding.REPO
SCHEMA = 'v70_two_applied_Full_updates_and_terminal_probe.v1'
IMPLEMENTATION_SCHEMA = 'v70_frozen_continuous_Full_implementation.v1'
PREPARED_SCHEMA = 'v70_continuous_Full_preparation_complete.v1'
FILES = tuple('finqa_v70_' + name + '.py' for name in (
    'binding', 'registration', 'entry', 'signals', 'resources', 'controller',
    'worker', 'training', 'temperature', 'runtime', 'diagnostics', 'evaluation',
    'queue_base', 'analysis'))
MINIMUM_FREE_DISK_BYTES = 128 * 1024 ** 3
require, checked, publish = binding.require, binding.checked, binding.publish
_IMPLEMENTATION = None
_PROTOCOL = None


def scientific_contract():
    return dict(schema='v70_single_path_fixed_dose_scientific_contract.v1',
        selection_rule='fixed smallest existing parent seed137; not best-score selection',
        initialization=dict(seed=137, source='V63/C1/b1', step=894, phase='step',
            source_algorithm='C-only', restore=['theta', 'Adam', 'training_RNG', 'pi'],
            real_parent_not_virtual=True, new_initialization_seed=False),
        algorithm='Full', C_only_to_Full_transition_step=894,
        contribution_exponent=0.8, novelty_exponent=0.2,
        lambda_current=4.0, lambda_prior=1.0, epsilon=0.05,
        novelty_temperature=1.0, rms_floor=1e-8, prior_never_reset=True,
        feedback_temperature=1.0, feedback_draw_seeds=[101, 103],
        feedback_tasks_per_draw=350, feedback_denominator_per_point=700,
        zero_reward_sessions_remain_in_denominator=True,
        actual_parameter_points=[894, 1192, 1490], applied_outer_steps=[894, 1192],
        terminal_probe_step=1490, terminal_probe_applied=False,
        train_windows=[[895, 1192], [1193, 1490]], updates_per_window=298,
        new_optimizer_updates=596, task_exposures_per_window=1488,
        new_training_task_exposures=2976, new_training_paths=1,
        independent_parent_count=1, new_training_seeds=0,
        fixed_own_once_updated_q_within_each_window=True,
        automatic_old_driver_outer_disabled=True, exactly_once_explicit_outer_commit=True,
        old_outer_history_not_fabricated=True, new_epochs_beyond1490=0,
        new_complete_class_passes=3, tasks_per_pass=744, states_per_pass=1360,
        packages_per_pass=2468, effective_rows_per_pass=4974,
        new_complete_class_tasks=2232, new_effective_class_rows=14922,
        class_shards_per_point=4, task_atomic_gradient_checkpoints=True,
        aggregate_gradient_in_original_task_state_parameter_order=True,
        historical596_gradients_G_theta_bar_or_C_reused=False,
        new_feedback_sessions=2100, new_evaluation_sessions=1123,
        new_total_logical_sessions=3223,
        original_Adam_pullback_loss_mask_clip_rng_and_schedule_unchanged=True,
        original_probability='softmax(raw_logits/T); full trajectory including EOS',
        derivative='log_softmax(raw_logits/T); complete reward/700 response accumulation',
        trajectory_length_normalized=False, feedback_gradient_uses_SFT_mask=False,
        draw_components=[101, 103], draw_diagnostic_denominator=350,
        draw_mean_tolerances=dict(atol=1e-7, rtol=2e-4,
            source='V54_CPU_full_autograd_gradient_comparison'),
        total_and_draw_gradients_share_atomic_response_checkpoint=True,
        formal_q_uses_complete_700_feedback_only=True,
        mean_of_normalized_draw_q_forbidden=True,
        diagnostic_extra_VJPs_per_point=2, diagnostic_extra_VJPs_total=6,
        diagnostic_extra_centered_inner_products_per_point=2,
        diagnostic_extra_centered_inner_products_total=6,
        legacy_single_point_exception_inherited=False,
        legacy_unknown_request_reexecution_permission_inherited=False,
        all_zero_feedback='preserve actual pi; UNINFORMATIVE, not convergence',
        no_performance_based_early_stop_or_checkpoint_selection=True,
        evaluation_baseline_reused_not_rescored=True,
        new_random_evaluation=0, new_test_evaluation=0, new_step1192_dev=0,
        full_path_causal_gain_over_ordinary_continuation_identifiable=False,
        Novelty_increment_over_C_only_identifiable=False,
        dev_cal_are_unseen_confirmation_sets=False,
        cross_seed_inference=False, new_cluster_bootstrap=False,
        full_online_convergence_proved=False, automatic_followup_authorized=False,
        no_temperature_weight_material_or_seed_search=True,
        local_Student_provider=True, external_API_calls=0, api_model='deepseek-flash')


def modules():
    binding.install_registered_auxiliary()
    return {name: importlib.import_module('finqa_v70_' + name) for name in
            ('training', 'runtime', 'resources', 'controller', 'evaluation', 'diagnostics', 'signals', 'analysis')}


def _same_reference(left, right):
    return Path(left['path']).resolve() == Path(right['path']).resolve() and left['sha256'] == right['sha256']


def parent_metadata():
    """Accept just the required complete source endpoint, not all old branches."""
    source = binding.V63_ROOT
    paths = dict(branch=source / 'branches/seed137/C1/completed/record.json',
        training_binding=source / 'branches/seed137/C1/binding/record.json',
        result=source / 'stages/seed137/train_C1/result/record.json',
        accepted=source / 'stages/seed137/train_C1/accepted/record.json',
        replay=source / 'stages/seed137/replay_C1/result/record.json',
        distribution=source / 'stages/seed137/distribution_C1/result/record.json',
        original_parent=source / 'parents/seed137/record.json')
    refs = {key: binding.entry(path) for key, path in paths.items()}
    values = {key: binding.read_ref(ref) for key, ref in refs.items()}
    branch, result, accepted = (values[key] for key in ('branch', 'result', 'accepted'))
    actual_ref = accepted['actual_exit']
    actual_path = Path(actual_ref['path']).resolve()
    require(actual_path.is_relative_to(source / 'stages/seed137/train_C1/attempts')
            and actual_path.name == 'record.json' and actual_path.parent.name == 'actual_exit',
            'source endpoint needs its own actual training exit')
    actual = binding.read_ref(actual_ref)
    launch_ref = binding.entry(actual_path.parent.parent / 'launch/record.json')
    launch = binding.read_ref(launch_ref)
    require(branch['protocol_id'] == result['protocol_id'] == accepted['protocol_id']
            == actual['protocol_id'] == launch['protocol_id'] == binding.BASE_PROTOCOL_ID
            and branch['status'] == result['status'] == 'COMPLETE'
            and (branch['seed'], branch['arm'], branch['feedback_batch']) == (137, 'C1', 1)
            and branch['optimizer_updates'] == branch['new_optimizer_updates'] == 298
            and branch['end_step'] == result['final_step'] == 894
            and branch['next_outer894_executed'] is False
            and result['resources']['all_gates_passed'] is True
            and accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
            and actual['returncode'] == 0 and actual['actual_waitpid_observed'] is True
            and (actual['pid'], actual['birth']) == (launch['pid'], launch['birth'])
            and actual['job_id'] == accepted['job_id'] == 'seed137.train_C1'
            and accepted['result_id'] == result['id']
            and _same_reference(accepted['result'], refs['result'])
            and _same_reference(result['branch_result'], refs['branch']),
            'only the actually accepted source C1/b1/894 endpoint may initialize V70')
    require(values['replay']['status'] == values['distribution']['status'] == 'COMPLETE'
            and values['replay']['draw_diagnostics_passed'] is True
            and not values['replay'].get('draw_diagnostics_accepted_by_exception', False),
            'the selected source must not borrow the seed389/C05 single-point numerical exception')
    checkpoint = branch['snapshots']['894']
    directory = Path(checkpoint['path']).resolve()
    require(directory == source / 'branches/seed137/C1/training/step0894_step'
            and binding.sha(directory / 'record.json') == checkpoint['record_sha256']
            and (directory / 'state.pt').is_file()
            and checkpoint['actual_state_digest'] and checkpoint['state_sha256'],
            'source actual checkpoint bytes and metadata binding are required')
    # Full state loading/hash validation occurs at actual checkpoint consumption.
    return dict(source_refs=dict(refs, actual_exit=actual_ref, launch=launch_ref),
        checkpoint=checkpoint, distribution_digest=branch['distribution_digest'],
        selected_seed=137, selected_arm='C1', feedback_batch=1, step=894,
        source_state_digest=checkpoint['actual_state_digest'],
        source_algorithm='C-only', target_algorithm='Full',
        original_Tensors_loaded=False, original_other_branch_diagnostics_required=False)


def baseline_evaluation():
    group = binding.V63_ROOT / 'partial_scoring_01/groups/seed137/C1'
    accepted_ref, result_ref = binding.entry(group / 'accepted/record.json'), binding.entry(group / 'result/record.json')
    accepted, result = binding.read_ref(accepted_ref), binding.read_ref(result_ref)
    actual = binding.read_ref(accepted['actual_exit'])
    require(accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
            and actual['returncode'] == 0 and actual['actual_waitpid_observed'] is True
            and result['coordinate'] == 'seed137/C1' and result['feedback_batch'] == 1
            and result['scoring_execution_complete'] is True
            and result['native_scores_present'] == 1243
            and _same_reference(accepted['group_result'], result_ref),
            'baseline requires original accepted complete CPU scores, not a newly selected model')
    reports = {}
    for role, panel, denominator, correct in (
            ('calibration', 'step894_calibration120_greedy', 120, 67),
            ('development', 'step894_dev883_greedy', 883, 525)):
        reference = result['model_reports'][panel]
        report = binding.read_ref(reference)
        require(Path(reference['path']).resolve() == group / 'panels' / panel / 'record.json'
                and report['coordinate'] == 'seed137/C1' and report['feedback_batch'] == 1
                and report['denominator'] == denominator
                and report['metrics']['execution_accuracy']['correct'] == correct
                and report['metrics']['states']['UNKNOWN'] == 0,
                'baseline score identity, complete denominator or specified value changed')
        reports[role] = reference
    return dict(accepted=accepted_ref, result=result_ref, actual_exit=accepted['actual_exit'],
        model_reports=reports, step=894, rescore=False, source_coordinate='seed137/C1')


def historical_source_bindings():
    manifests = {
        'v63': binding.entry(binding.V63_ROOT / 'implementation/record.json'),
        'v64': binding.entry(binding.V64_ROOT / 'implementation/record.json'),
        'v54_automatic': binding.entry(binding.OLD_ROOT / 'implementation/record.json'),
    }
    source_bindings = {}
    frozen_source = None
    for name, reference in manifests.items():
        manifest = binding.read_ref(reference)
        if name == 'v63':
            require(manifest['id'] == binding.BASE_IMPLEMENTATION_ID, 'V63 source lineage changed')
            frozen_source = manifest['frozen_source_root']
        if name == 'v64':
            require(manifest['id'] == binding.V64_IMPLEMENTATION_ID, 'V64 source lineage changed')
        directory = Path(reference['path']).parent
        additions = {str(directory / filename): expected for filename, expected in manifest['sha256'].items()}
        additions.update(manifest.get('external_frozen_source_sha256', {}))
        for path, expected in additions.items():
            require(path not in source_bindings or source_bindings[path] == expected,
                    'historical dependency has conflicting frozen byte identities')
            source_bindings[path] = expected
    auxiliary = binding.source_module('finqa_v63_entry')
    registered = str(auxiliary.AUXILIARY_CANONICAL.resolve())
    alias = str(auxiliary.AUXILIARY_WORKSPACE_ALIAS.resolve())
    require(registered in source_bindings, 'original V25 auxiliary must retain an explicit frozen source')
    source_bindings[alias] = source_bindings[registered]
    signals = importlib.import_module('finqa_v70_signals')
    for reference in signals.external_source_bindings().values():
        source_bindings[str(Path(reference['path']).resolve())] = reference['sha256']
    return dict(manifests=manifests, source_bindings=source_bindings,
        frozen_source_root=frozen_source, explicit_V25_byte_identical_alias=alias)


def freeze(source_commit, lineage):
    require(not ROOT.exists(), 'V70 requires its one fresh independent scientific root')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=REPO, text=True).strip()
    sources = {}
    for filename in FILES:
        relative = 'trusted_data_synthesis/scripts/' + filename
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == binding.sha(REPO / relative),
                'uncommitted V70 production source: ' + filename)
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
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V70 implementation root')
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
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V70 scientific root')
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
                and value['no_wallclock_deadlines'] is True,
                'new scientific dose, resources, diagnostics, recovery or signal contract changed')
        _PROTOCOL = value
    return _PROTOCOL


def checked_prepared(root=ROOT):
    protocol = checked_protocol(root)
    value = checked(ROOT / 'prepared/record.json')
    require(value['schema'] == PREPARED_SCHEMA and value['protocol']['id'] == protocol['id']
            and value['new_feedback_sessions'] == 2100 and value['new_optimizer_updates'] == 596
            and value['new_evaluation_sessions'] == 1123
            and value['new_complete_class_tasks'] == 2232
            and value['scientific_supervisor_started'] is False and value['CUDA_initialized'] is False,
            'prepared endpoint or fixed new dose changed')
    binding.read_ref(value['initial_point'])
    return value


def prepare(source_commit):
    require(not ROOT.exists(), 'V70 may not replace any prepared, running or partially frozen experiment')
    loaded = modules()
    parent, baseline = parent_metadata(), baseline_evaluation()
    lineage = historical_source_bindings()
    policies = _policy_fields(loaded)
    free_disk = shutil.disk_usage(ROOT.parent).free
    require(free_disk >= MINIMUM_FREE_DISK_BYTES,
            'insufficient disk for the fixed new class caches and durable training/response checkpoints')
    base = binding.base_protocol()
    source_ref = base['evaluation_source_registration']
    binding.read_ref(source_ref)
    implementation = freeze(source_commit, lineage)
    protocol = publish(ROOT / 'protocol/record.json', dict(schema=SCHEMA, output_root=str(ROOT),
        source_commit=implementation['source_commit'],
        authorization='参照方案修订并开展后续实验', user_plan=binding.file_ref(binding.USER_PLAN),
        implementation=binding.entry(ROOT / 'implementation/record.json'),
        source_scientific_protocol=binding.entry(binding.V63_ROOT / 'protocol/record.json'),
        initial_parent=parent, baseline_evaluation=baseline,
        evaluation_source_registration=source_ref,
        old_evaluation_registration=base['old_evaluation_registration'],
        allowed_gpu_indices=list(range(8)), gpu_uuids=loaded['resources'].GPU_UUIDS,
        cpu_affinity=loaded['resources'].CPU_AFFINITY, gpu_priority=list(binding.GPU_PRIORITY),
        gpu_lease_root=base['gpu_lease_root'], max_gpu_workers=6, max_workers_per_gpu=1,
        initialization_wait_and_draining_count_as_workers=True,
        no_wallclock_deadlines=True, inherited_resource_wait_seconds=0.0,
        waiting_statistics_are_for_new_independent_experiment=True,
        old_wait_failures_and_authorizations_preserved_not_reset_or_reused=True,
        new_account_cron=False, external_GPU_holders=False,
        performance_based_branching=False, terminal_probe_never_committed=True,
        **policies))
    loaded['training'].prepare_point(ROOT, 894, protocol['id'], parent['checkpoint'])
    point_ref = binding.entry(ROOT / 'points/step0894/context/record.json')
    jobs = loaded['controller'].planned_jobs()
    return publish(ROOT / 'prepared/record.json', dict(schema=PREPARED_SCHEMA,
        protocol=binding.entry(ROOT / 'protocol/record.json'), initial_point=point_ref,
        fixed_jobs=jobs, initial_parent=parent, baseline_evaluation=baseline,
        new_feedback_sessions=2100, new_optimizer_updates=596, new_evaluation_sessions=1123,
        new_total_sessions=3223, new_complete_class_tasks=2232, new_effective_class_rows=14922,
        historical_other_diagnostics_not_prerequisites=True,
        historical_Tensor_checks_at_actual_consumption=True,
        disk_free_bytes=free_disk, disk_minimum_admission_bytes=MINIMUM_FREE_DISK_BYTES,
        scientific_supervisor_started=False, CUDA_initialized=False, model_loaded=False,
        scientific_calls=0, frozen_entry_check_imports_still_required=True))


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
