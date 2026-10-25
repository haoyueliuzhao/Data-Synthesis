"""Register one fixed-pi1192 low-learning-rate continuation after the static audit.

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

import finqa_v72_binding as binding

ROOT, REPO = binding.ROOT, binding.REPO
SCHEMA = 'v72_one_low_LR_continuation_from_fixed1192.v1'
IMPLEMENTATION_SCHEMA = 'v72_frozen_low_LR_implementation.v1'
PREPARED_SCHEMA = 'v72_low_LR_preparation_complete.v1'
FILES = tuple('finqa_v72_' + name + '.py' for name in (
    'binding', 'registration', 'entry', 'signals', 'resources', 'controller',
    'worker', 'training', 'runtime', 'evaluation', 'failure_analysis',
    'queue_base', 'analysis', 'static_audit'))
MINIMUM_FREE_DISK_BYTES = 24 * 1024 ** 3
require, checked, publish = binding.require, binding.checked, binding.publish
_IMPLEMENTATION = None
_PROTOCOL = None


def scientific_contract():
    return dict(schema='v72_low_LR_actual_fixed1192_contract.v1',
        condition='low_lr_1e-5_from_fixed1192', condition_name='固定1192父点后段低学习率续训',
        initialization=dict(seed=137, source='V71/Fixed894', step=1192, phase='step',
            restore=['theta', 'buffers', 'Adam', 'training_RNG', 'pi', 'prior', 'schedule'],
            exact_parent_before_learning_rate_intervention=True, new_initialization_seed=False),
        distribution='same original actual pi0 throughout; not a new prior/uniform reference',
        original_learning_rate=1e-4, intervention_learning_rate=1e-5,
        change_optimizer_param_groups_only_after_exact_parent_restore=True,
        optimizer_moments_and_cursor_preserved=True, RNG_not_reinitialized=True,
        intervention_pre_and_post_state_digests_distinct=True,
        intervention_is_not_an_optimizer_update=True,
        train_windows=[[1193,1490]], updates_per_window=298,
        new_optimizer_updates=298, new_training_task_exposures=1488,
        new_training_paths=1, new_training_seeds=0, original_outer_history=[298],
        automatic_driver_outer_disabled=True, explicit_outer_commit_forbidden=True,
        new_outer_updates=0, new_feedback_sessions=0, new_class_passes=0,
        new_response_replays=0, new_VJPs=0, new_terminal_probes=0,
        original_task_schedule_package_loss_mask_EOS_Adam_clip_dropout_unchanged=True,
        original_training_consumer_unchanged=True,
        actual_batch_task_count_including_four_task_tail_preserved=True,
        clip_calls_per_batch=1, optimizer_calls_per_batch=1,
        original_schedule_epochs=10, new_epochs_beyond1490=0,
        new_evaluation_sessions=1886, evaluation_counts=[883,883,120],
        evaluation_points=['parent1192/dev883','low_LR1490/dev883','low_LR1490/cal120'],
        parent_dev_generation_may_overlap_training=True,
        new_Full1192_dev=False, old_scores_rescored=False, new_random_test_panels=False,
        high_LR_comparator='completed V71 fixed1192-to1490 window; no retraining',
        matched_window_training_dose=True, equal_total_workflow_wall_claim=False,
        main_dev_delta_LR='(L-377)/883', main_dev_delta_retention='(L-B)/883',
        main_dev_delta_old_window='(377-B)/883', old_path_decomposition='-148=(B-525)+(377-B)',
        all_three_main_deltas_reported=True, full_denominator_I_W_R_UNKNOWN=True,
        invalid_terminal_and_first_failure_separate=True, raw_native_scores_unchanged=True,
        static_supervision_and_submission_contract_PASS_required_before_any_GPU_dispatch=True,
        definite_encoding_conflict_blocks_science=True,
        static_audit_has_fixed_scope_and_no_model_forward=True,
        same_task_package_online_NLL_alignment_from_saved_receipts=True,
        three_condition_joint_states_from_native_rows_not_pair_matrices=True,
        actual1192_to1490_cal_transitions_from_same_tasks=True,
        no_new_per_token_loss_or_layer_gradient_computation=True,
        outcome_posthoc_single_parent_single_rng_development_panel_only=True,
        independent_C_N_or_all894_onward_damage_identified=False,
        learning_rate_optimality_or_unique_root_cause_proved=False,
        significance_advancement_or_equivalence_threshold=None,
        score_based_selection_or_schedule_change=False,
        automatic_followup_or_Full_resume_authorized=False,
        local_Student_provider=True, external_API_calls=0, api_model='deepseek-flash')


def modules():
    binding.install_registered_auxiliary()
    return {name: importlib.import_module('finqa_v72_' + name) for name in
            ('training', 'runtime', 'resources', 'controller', 'evaluation', 'signals', 'analysis')}


def _same_reference(left, right):
    return Path(left['path']).resolve() == Path(right['path']).resolve() and left['sha256'] == right['sha256']


def _v71_protocol():
    value = checked(binding.V71_ROOT / 'protocol/record.json')
    require(value['id'] == binding.V71_PROTOCOL_ID, 'V71 comparator protocol changed')
    return value


def parent_metadata():
    root = binding.V71_ROOT
    directory = root / 'points/step0894/train'
    refs = {name: binding.entry(directory / name / 'record.json')
            for name in ('completed', 'accepted', 'result')}
    completed, accepted, result = (binding.read_ref(refs[name]) for name in ('completed','accepted','result'))
    actual = binding.read_ref(accepted['actual_exit'])
    require(completed['status'] == result['status'] == 'COMPLETE'
            and completed['protocol_id'] == result['protocol_id'] == accepted['protocol_id']
                == actual['protocol_id'] == binding.V71_PROTOCOL_ID
            and accepted['job_id'] == actual['job_id'] == 'step894.train'
            and accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
            and actual['actual_waitpid_observed'] is True and actual['returncode'] == 0
            and accepted['result_id'] == result['id']
            and completed['final_step'] == 1192 and completed['initial_step'] == 894
            and completed['optimizer_updates'] == 298 and completed['outer_updates'] == 0
            and completed['outer_done'] == [298], 'actual accepted V71 fixed1192 parent required')
    report_ref = binding.entry(root / 'report_analysis_01/record.json')
    report = binding.read_ref(report_ref)
    require(report['id'] == 'e3fa64896b83be4e823bdae5bcd15d1464633bf4dd2104973e9d4c3cd61fe751',
            'specified audited V71 machine summary changed')
    checkpoint = completed['final_checkpoint']
    require(checkpoint == report['training_control']['windows']['894']['final_checkpoint']
            and checkpoint == result['final_checkpoint']
            and Path(checkpoint['path']).resolve() == root / 'training/step1192_step'
            and checkpoint['step'] == 1192 and checkpoint['phase'] == 'step'
            and checkpoint['actual_state_digest'] == '2dbeeb60a2eb99c8dac36768faf7eb09c8acdffc2b0ae3f4444a0204fcdaa340'
            and binding.sha(Path(checkpoint['path']) / 'record.json') == checkpoint['record_sha256']
            and (Path(checkpoint['path']) / 'state.pt').is_file(),
            'parent must be the exact audited V71 fixed1192 state, not latest')
    return dict(checkpoint=checkpoint, source_state_digest=checkpoint['actual_state_digest'],
        distribution_digest=completed['fixed_distribution_digest'], step=1192,
        selected_seed=137, source_algorithm='fixed_pi894', target_algorithm='low_lr_1e-5_from_fixed1192',
        original_learning_rate=1e-4, new_learning_rate=1e-5,
        source_refs=dict(refs, actual_exit=accepted['actual_exit'],
            context=binding.entry(root / 'points/step1192/context/record.json'),
            initial_context=binding.entry(root / 'points/step0894/context/record.json'),
            machine_summary=report_ref), original_Tensors_loaded=False)


def baseline_evaluation():
    baseline = _v71_protocol()['baseline_evaluation']
    for role,count,correct in [('calibration',120,67),('development',883,525)]:
        row=binding.read_ref(baseline['model_reports'][role])
        require(row['denominator']==count and row['metrics']['execution_accuracy']['correct']==correct
                and row['metrics']['states']['UNKNOWN']==0,'original894 baseline changed')
    return baseline


def existing_evaluations():
    root=binding.V71_ROOT
    closeout=checked(root / 'closeout/record.json')
    summary=checked(root / 'evaluations/final_summary/record.json')
    accepted=checked(root / 'final_analysis/accepted/record.json')
    actual=binding.read_ref(accepted['actual_exit'])
    require(closeout['status']==summary['status']=='COMPLETE'
            and closeout['protocol_id']==summary['protocol_id']==binding.V71_PROTOCOL_ID
            and actual['actual_waitpid_observed'] and actual['returncode']==0,
            'only complete accepted old V71 native scores may be reused')
    for job,denominator,correct in [('step1192.cal_greedy',120,74),
            ('step1490.cal_greedy',120,56),('step1490.dev_greedy',883,377)]:
        row=binding.read_ref(summary['model_reports'][job])
        require(row['denominator']==denominator and row['metrics']['execution_accuracy']['correct']==correct
                and row['metrics']['states']['UNKNOWN']==0,'prespecified high-LR reference changed')
    shared=dict(rescore=False, final_summary=binding.entry(root / 'evaluations/final_summary/record.json'),
        accepted=binding.entry(root / 'final_analysis/accepted/record.json'), actual_exit=accepted['actual_exit'])
    parent=dict(shared, step=1192, model_reports={'calibration':summary['model_reports']['step1192.cal_greedy']},
        dev_previously_scored=False)
    high=dict(shared, step=1490, learning_rate=1e-4,
        model_reports={key:summary['model_reports'][key] for key in ('step1490.cal_greedy','step1490.dev_greedy')},
        failure_analysis=binding.entry(root / 'mechanism_analysis/paired_invalid/record.json'))
    return parent,high


def historical_source_bindings():
    reference=binding.entry(binding.V71_ROOT / 'implementation/record.json')
    manifest=binding.read_ref(reference)
    require(manifest['id']==binding.V71_IMPLEMENTATION_ID,'frozen V71 sources changed')
    sources=dict(manifest['source_bindings'])
    sources.update({str(binding.V71_ROOT / 'implementation' / filename):expected
                    for filename,expected in manifest['sha256'].items()})
    return dict(manifests=dict(manifest['historical_manifests'],v71=reference),
        source_bindings=sources,frozen_source_root=manifest['frozen_source_root'],
        explicit_V25_byte_identical_alias=manifest['explicit_V25_byte_identical_alias'])


def freeze(source_commit, lineage):
    require(not ROOT.exists(), 'V72 requires its one fresh independent scientific root')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=REPO, text=True).strip()
    sources = {}
    for filename in FILES:
        relative = 'trusted_data_synthesis/scripts/' + filename
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == binding.sha(REPO / relative),
                'uncommitted V72 production source: ' + filename)
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
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V72 implementation root')
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
    failure = importlib.import_module('finqa_v72_failure_analysis')
    return dict(scientific_contract=scientific_contract(),
        evaluation=loaded['evaluation'].evaluation_contract(),
        failure_analysis_policy=failure.policy(),
        static_audit_policy=importlib.import_module('finqa_v72_static_audit').policy(),
        resource_policy=loaded['resources'].resource_policy(),
        resource_recovery_policy=loaded['resources'].resource_recovery_policy(),
        final_analysis_resource_policy=loaded['analysis'].resource_policy(),
        auto_recovery_policy=loaded['controller'].auto_recovery_policy(),
        gpu_isolation_policy=isolation.gpu_isolation_policy(),
        signal_policy=loaded['signals'].signals_policy(),
        signal_source_bindings=loaded['signals'].external_source_bindings())


def checked_protocol(root=ROOT):
    global _PROTOCOL
    require(Path(root).resolve() == ROOT.resolve(), 'foreign V72 scientific root')
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
        validate_static_audit(binding.read_ref(value['static_supervision_gate']),
                              implementation=checked_implementation(root))
        _PROTOCOL = value
    return _PROTOCOL


def checked_prepared(root=ROOT):
    protocol = checked_protocol(root)
    value = checked(ROOT / 'prepared/record.json')
    require(value['schema'] == PREPARED_SCHEMA and value['protocol']['id'] == protocol['id']
            and value['new_feedback_sessions'] == 0 and value['new_optimizer_updates'] == 298
            and value['new_evaluation_sessions'] == 1886
            and value['new_outer_updates'] == 0
            and value['scientific_supervisor_started'] is False and value['CUDA_initialized'] is False,
            'prepared endpoint or fixed new dose changed')
    binding.read_ref(value['initial_point'])
    return value


def validate_static_audit(value, implementation=None):
    audit = importlib.import_module('finqa_v72_static_audit')
    require(value['schema'] == 'v72_actual_encoded_supervision_audit.v1'
            and value['status'] == 'PASS' and value['gate_passed'] is True
            and value['conflicts'] == [] and value['policy'] == audit.policy()
            and value['scope'] == dict(tasks=744, packages=2468, rows=4978, effective_rows=4974)
            and value['parent_V71_protocol_id'] == binding.V71_PROTOCOL_ID
            and value['model_weights_loaded'] is False and value['tokenizer_CPU_only'] is True
            and value['new_model_calls'] == value['new_scoring_calls'] == 0
            and value['CUDA_initialized'] is False,
            'definite encoded supervision/submission conflict blocks V72 scientific dispatch')
    expected = (implementation['sha256']['finqa_v72_static_audit.py'] if implementation
                else binding.sha(REPO / 'trusted_data_synthesis/scripts/finqa_v72_static_audit.py'))
    require(value['analysis_script']['sha256'] == expected,
            'the passed static audit must use the registered unchanged audit implementation')
    return value


def prepare(source_commit, static_audit_path, existing_analysis_path, existing_producer_path=None):
    require(not ROOT.exists(), 'V72 requires its fresh independent scientific root')
    loaded=modules()
    parent,baseline=parent_metadata(),baseline_evaluation()
    parent_eval,high_eval=existing_evaluations()
    audit=checked(static_audit_path)
    analyses=checked(existing_analysis_path)
    validate_static_audit(audit)
    require(analyses['schema'] == 'v72_existing_same_package_and_joint_outcomes.v1'
            and analyses['status'] == 'COMPLETE'
            and analyses['new_model_calls'] == analyses['new_scoring_calls'] == 0
            and analyses['CUDA_initialized'] is False,
            'existing online-loss and outcome analysis must be complete and read-only')
    producer_path = Path(existing_producer_path or (REPO / 'trusted_data_synthesis/scripts/finqa_v72_static_audit.py'))
    producer_raw = producer_path.read_bytes()
    require(hashlib.sha256(producer_raw).hexdigest() == analyses['analysis_script']['sha256'],
            'actual producer bytes of the completed existing analysis must be preserved')
    lineage=historical_source_bindings()
    policies=_policy_fields(loaded)
    free_disk=shutil.disk_usage(ROOT.parent).free
    require(free_disk>=MINIMUM_FREE_DISK_BYTES,'insufficient disk for298 actual checkpoints and1886 generation sessions')
    base=binding.base_protocol()
    source_ref=base['evaluation_source_registration'];binding.read_ref(source_ref)
    implementation=freeze(source_commit,lineage)
    publish(ROOT / 'static_supervision_audit/record.json',audit)
    publish(ROOT / 'existing_analysis/record.json',analyses)
    producer_destination = ROOT / 'existing_analysis/producer.py'
    with producer_destination.open('xb') as stream:
        stream.write(producer_raw); stream.flush(); os.fsync(stream.fileno())
    protocol=publish(ROOT / 'protocol/record.json',dict(schema=SCHEMA,output_root=str(ROOT),
        source_commit=implementation['source_commit'], authorization='参照审计修订并开展后续实验',
        user_plan=binding.file_ref(binding.USER_PLAN), implementation=binding.entry(ROOT / 'implementation/record.json'),
        source_scientific_protocol=binding.entry(binding.V71_ROOT / 'protocol/record.json'),
        initial_parent=parent,baseline_evaluation=baseline,parent_evaluation=parent_eval,high_lr_evaluation=high_eval,
        static_supervision_gate=binding.entry(ROOT / 'static_supervision_audit/record.json'),
        existing_analysis=binding.entry(ROOT / 'existing_analysis/record.json'),
        existing_analysis_producer=binding.file_ref(producer_destination),
        evaluation_source_registration=source_ref,old_evaluation_registration=base['old_evaluation_registration'],
        allowed_gpu_indices=list(range(8)),gpu_uuids=loaded['resources'].GPU_UUIDS,
        cpu_affinity=loaded['resources'].CPU_AFFINITY,gpu_priority=list(binding.GPU_PRIORITY),
        gpu_lease_root=base['gpu_lease_root'],max_gpu_workers=6,max_workers_per_gpu=1,
        initialization_wait_and_draining_count_as_workers=True,no_wallclock_deadlines=True,
        inherited_resource_wait_seconds=0.0,waiting_statistics_are_for_new_independent_experiment=True,
        old_wait_failures_and_authorizations_preserved_not_reset_or_reused=True,
        new_account_cron=False,external_GPU_holders=False,performance_based_branching=False,
        any_new_outer_or_probe_forbidden=True,**policies))
    loaded['training'].prepare_initial(ROOT,protocol['id'])
    point_ref=binding.entry(ROOT / 'points/step1192/context/record.json')
    return publish(ROOT / 'prepared/record.json',dict(schema=PREPARED_SCHEMA,
        protocol=binding.entry(ROOT / 'protocol/record.json'),initial_point=point_ref,
        fixed_jobs=loaded['controller'].planned_jobs(),initial_parent=parent,
        new_feedback_sessions=0,new_optimizer_updates=298,new_evaluation_sessions=1886,
        new_total_sessions=1886,new_outer_updates=0,new_complete_class_tasks=0,new_effective_class_rows=0,
        static_supervision_gate=binding.entry(ROOT / 'static_supervision_audit/record.json'),
        existing_analysis=binding.entry(ROOT / 'existing_analysis/record.json'),
        disk_free_bytes=free_disk,disk_minimum_admission_bytes=MINIMUM_FREE_DISK_BYTES,
        scientific_supervisor_started=False,CUDA_initialized=False,model_loaded=False,scientific_calls=0,
        frozen_entry_check_imports_still_required=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--static-audit',type=Path,required=True)
    parser.add_argument('--existing-analysis',type=Path,required=True)
    parser.add_argument('--existing-producer',type=Path)
    args = parser.parse_args(argv)
    result = prepare(args.source_commit,args.static_audit,args.existing_analysis,args.existing_producer)
    print(json.dumps(dict(id=result['id'], protocol=result['protocol'],
        initial_point=result['initial_point'], scientific_supervisor_started=False), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
