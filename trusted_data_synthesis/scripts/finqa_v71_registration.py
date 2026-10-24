"""Register the same-parent fixed-pi894 continuation and saved-product analysis.

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

import finqa_v71_binding as binding

ROOT, REPO = binding.ROOT, binding.REPO
SCHEMA = 'v71_same_parent_fixed_distribution_control.v1'
IMPLEMENTATION_SCHEMA = 'v71_frozen_fixed_distribution_implementation.v1'
PREPARED_SCHEMA = 'v71_fixed_distribution_preparation_complete.v1'
FILES = tuple('finqa_v71_' + name + '.py' for name in (
    'binding', 'registration', 'entry', 'signals', 'resources', 'controller',
    'worker', 'training', 'runtime', 'evaluation', 'failure_analysis',
    'queue_base', 'analysis', 'mechanism_analysis'))
MINIMUM_FREE_DISK_BYTES = 32 * 1024 ** 3
require, checked, publish = binding.require, binding.checked, binding.publish
_IMPLEMENTATION = None
_PROTOCOL = None


def scientific_contract():
    return dict(schema='v71_fixed_actual894_distribution_contract.v1',
        condition='fixed_pi894', condition_name='保持894实际分布续训',
        initialization=dict(seed=137, source='V70_registered_V63/C1/b1', step=894, phase='step',
            restore=['theta', 'buffers', 'Adam', 'training_RNG', 'pi', 'prior', 'schedule'],
            exact_V70_pre_first_outer_state=True, new_initialization_seed=False),
        distribution='same actual parent pi0 at every step; not prior/uniform/frozen reference',
        train_windows=[[895, 1192], [1193, 1490]], updates_per_window=298,
        new_optimizer_updates=596, new_training_task_exposures=2976,
        new_training_paths=1, new_training_seeds=0, original_outer_history=[298],
        automatic_driver_outer_disabled=True, explicit_outer_commit_forbidden=True,
        new_outer_updates=0, new_feedback_sessions=0, new_class_passes=0,
        new_response_replays=0, new_VJPs=0, new_terminal_probes=0,
        original_task_schedule_package_loss_mask_EOS_Adam_clip_dropout_unchanged=True,
        actual_batch_task_count_including_four_task_tail_preserved=True,
        clip_calls_per_batch=1, optimizer_calls_per_batch=1,
        original_schedule_epochs=10, new_epochs_beyond1490=0,
        new_evaluation_sessions=1123, evaluation_counts=[120,120,883],
        evaluation_points=['1192/cal120','1490/cal120','1490/dev883'],
        new_1192_dev=False, old_scores_rescored=False, new_random_test_panels=False,
        full_comparator='only already completed V70 original same-parent path',
        matched_inner_training_dose=True, equal_total_compute_claim=False,
        main_dev_delta_adaptive='(371-H)/883', main_dev_delta_fixed='(H-525)/883',
        both_main_deltas_reported=True, full_denominator_I_W_R_UNKNOWN=True,
        invalid_terminal_and_first_failure_separate=True, raw_native_scores_unchanged=True,
        existing_analysis_not_training_start_gate=True,
        nominal_supervision_not_actual_loss_or_gradient_claim=True,
        saved_actual_training_dynamics_may_be_read=True,
        formal_and_half_draw_direction_support_uses_C_already_containing_mu=True,
        formal_q_half_draw_support_not_independent_validation=True,
        unused1490_contribution_not_cause_of_prior_training=True,
        outcome_posthoc_single_parent_single_rng_development_panel_only=True,
        independent_C_N_or_window_causal_effects_identified=False,
        significance_advancement_or_cosine_threshold=None,
        score_based_selection_or_schedule_change=False,
        automatic_followup_authorized=False,
        local_Student_provider=True, external_API_calls=0, api_model='deepseek-flash')


def modules():
    binding.install_registered_auxiliary()
    return {name: importlib.import_module('finqa_v71_' + name) for name in
            ('training', 'runtime', 'resources', 'controller', 'evaluation', 'signals', 'analysis')}


def _same_reference(left, right):
    return Path(left['path']).resolve() == Path(right['path']).resolve() and left['sha256'] == right['sha256']


def _v70_protocol():
    value = checked(binding.V70_ROOT / 'protocol/record.json')
    require(value['id'] == binding.V70_PROTOCOL_ID, 'V70 comparator protocol changed')
    return value


def parent_metadata():
    """Take the registered V70 parent, never a latest-checkpoint search."""
    parent = dict(_v70_protocol()['initial_parent'])
    checkpoint = parent['checkpoint']
    directory = binding.V63_ROOT / 'branches/seed137/C1/training/step0894_step'
    require(Path(checkpoint['path']).resolve() == directory and checkpoint['step'] == 894
            and checkpoint['phase'] == 'step'
            and binding.sha(directory / 'record.json') == checkpoint['record_sha256']
            and (directory / 'state.pt').is_file()
            and parent['distribution_digest'] == '53ec21e1fe195fce424a5377ea3126429591b24fc3d32820fe8fc46aef8421a5',
            'same actual pre-Full894 parent and pi0 are required')
    accepted = binding.read_ref(parent['source_refs']['accepted'])
    actual = binding.read_ref(parent['source_refs']['actual_exit'])
    require(accepted['actual_exit_zero'] and accepted['resources_passed']
            and actual['actual_waitpid_observed'] and actual['returncode'] == 0,
            'source parent must retain its accepted actual exit')
    parent['target_algorithm'] = 'fixed_pi894'
    parent['same_parent_as_V70'] = binding.entry(binding.V70_ROOT / 'protocol/record.json')
    return parent


def baseline_evaluation():
    baseline = _v70_protocol()['baseline_evaluation']
    for role, count, correct in [('calibration',120,67), ('development',883,525)]:
        report = binding.read_ref(baseline['model_reports'][role])
        require(report['denominator'] == count
                and report['metrics']['execution_accuracy']['correct'] == correct
                and report['metrics']['states']['UNKNOWN'] == 0, 'baseline score contract changed')
    return baseline


def full_evaluation():
    root = binding.V70_ROOT
    closeout = checked(root / 'closeout/record.json')
    summary = checked(root / 'evaluations/final_summary/record.json')
    accepted = checked(root / 'final_analysis/accepted/record.json')
    actual = binding.read_ref(accepted['actual_exit'])
    require(closeout['status'] == summary['status'] == 'COMPLETE'
            and closeout['protocol_id'] == summary['protocol_id'] == binding.V70_PROTOCOL_ID
            and closeout['optimizer_updates'] == 596 and closeout['applied_Full_updates'] == 2
            and closeout['terminal_candidate_applied'] is False
            and actual['actual_waitpid_observed'] is True and actual['returncode'] == 0,
            'Full comparison requires its complete accepted native scores')
    expected = {'step1192.cal_greedy':(120,71), 'step1490.cal_greedy':(120,53),
                'step1490.dev_greedy':(883,371)}
    require(set(summary['model_reports']) == set(expected), 'fixed old Full panels changed')
    for job, (count, correct) in expected.items():
        report = binding.read_ref(summary['model_reports'][job])
        require(report['denominator'] == count and report['metrics']['states']['UNKNOWN'] == 0
                and report['metrics']['execution_accuracy']['correct'] == correct,
                'Full endpoint score or denominator changed')
    return dict(model_reports=summary['model_reports'], rescore=False,
        final_summary=binding.entry(root / 'evaluations/final_summary/record.json'),
        closeout=binding.entry(root / 'closeout/record.json'),
        accepted=binding.entry(root / 'final_analysis/accepted/record.json'), actual_exit=accepted['actual_exit'])


def historical_source_bindings():
    reference = binding.entry(binding.V70_ROOT / 'implementation/record.json')
    manifest = binding.read_ref(reference)
    require(manifest['id'] == binding.V70_IMPLEMENTATION_ID, 'frozen V70 sources changed')
    sources = dict(manifest['source_bindings'])
    sources.update({str(binding.V70_ROOT / 'implementation' / filename): expected
                    for filename, expected in manifest['sha256'].items()})
    return dict(manifests=dict(manifest['historical_manifests'], v70=reference),
        source_bindings=sources, frozen_source_root=manifest['frozen_source_root'],
        explicit_V25_byte_identical_alias=manifest['explicit_V25_byte_identical_alias'])


def freeze(source_commit, lineage):
    require(not ROOT.exists(), 'V71 requires its one fresh independent scientific root')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=REPO, text=True).strip()
    sources = {}
    for filename in FILES:
        relative = 'trusted_data_synthesis/scripts/' + filename
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == binding.sha(REPO / relative),
                'uncommitted V71 production source: ' + filename)
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
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V71 implementation root')
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
    failure = importlib.import_module('finqa_v71_failure_analysis')
    return dict(scientific_contract=scientific_contract(),
        evaluation=loaded['evaluation'].evaluation_contract(),
        failure_analysis_policy=failure.policy(),
        resource_policy=loaded['resources'].resource_policy(),
        resource_recovery_policy=loaded['resources'].resource_recovery_policy(),
        final_analysis_resource_policy=loaded['analysis'].resource_policy(),
        auto_recovery_policy=loaded['controller'].auto_recovery_policy(),
        gpu_isolation_policy=isolation.gpu_isolation_policy(),
        signal_policy=loaded['signals'].signals_policy(),
        signal_source_bindings=loaded['signals'].external_source_bindings())


def checked_protocol(root=ROOT):
    global _PROTOCOL
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V71 scientific root')
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
            and value['new_feedback_sessions'] == 0 and value['new_optimizer_updates'] == 596
            and value['new_evaluation_sessions'] == 1123
            and value['new_outer_updates'] == 0
            and value['scientific_supervisor_started'] is False and value['CUDA_initialized'] is False,
            'prepared endpoint or fixed new dose changed')
    binding.read_ref(value['initial_point'])
    return value


def prepare(source_commit):
    require(not ROOT.exists(), 'V71 may not replace any prepared, running or partially frozen experiment')
    loaded = modules()
    parent, baseline, full = parent_metadata(), baseline_evaluation(), full_evaluation()
    lineage = historical_source_bindings()
    policies = _policy_fields(loaded)
    free_disk = shutil.disk_usage(ROOT.parent).free
    require(free_disk >= MINIMUM_FREE_DISK_BYTES,
            'insufficient disk for the fixed new training checkpoints and evaluation outputs')
    base = binding.base_protocol()
    source_ref = base['evaluation_source_registration']
    binding.read_ref(source_ref)
    implementation = freeze(source_commit, lineage)
    protocol = publish(ROOT / 'protocol/record.json', dict(schema=SCHEMA, output_root=str(ROOT),
        source_commit=implementation['source_commit'],
        authorization='参照审计修订并开展后续实验', user_plan=binding.file_ref(binding.USER_PLAN),
        implementation=binding.entry(ROOT / 'implementation/record.json'),
        source_scientific_protocol=binding.entry(binding.V63_ROOT / 'protocol/record.json'),
        initial_parent=parent, baseline_evaluation=baseline, full_evaluation=full,
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
        performance_based_branching=False, any_new_outer_or_probe_forbidden=True,
        **policies))
    loaded['training'].prepare_initial(ROOT, protocol['id'])
    point_ref = binding.entry(ROOT / 'points/step0894/context/record.json')
    jobs = loaded['controller'].planned_jobs()
    return publish(ROOT / 'prepared/record.json', dict(schema=PREPARED_SCHEMA,
        protocol=binding.entry(ROOT / 'protocol/record.json'), initial_point=point_ref,
        fixed_jobs=jobs, initial_parent=parent, baseline_evaluation=baseline, full_evaluation=full,
        new_feedback_sessions=0, new_optimizer_updates=596, new_evaluation_sessions=1123,
        new_total_sessions=1123, new_outer_updates=0, new_complete_class_tasks=0, new_effective_class_rows=0,
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
