"""V76 paired two-window development analysis and one guarded CPU finish.

This module never constructs a model or scores an episode by itself. New native
scores are produced by evaluation.finish only after the complete scientific DAG
and six generation workers have actually exited successfully.
"""
from __future__ import annotations
import importlib
from pathlib import Path

import finqa_v76_binding as binding

DENOMINATOR = 883
COMPARISONS = {
    'adaptive_A1788_minus_D1788': ('A1788', 'D1788'),
    'fixed_continuation_D1788_minus_S1490': ('D1788', 'S1490'),
    'first_window_A1490_minus_S1490': ('A1490', 'S1490'),
    'final_A1788_minus_P1192': ('A1788', 'P1192'),
    'final_D1788_minus_P1192': ('D1788', 'P1192'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


_STATS = None


def _stats():
    global _STATS
    if _STATS is None:
        import importlib.util
        import sys
        directory=binding.V63_ROOT/'implementation'
        manifest=binding.checked(directory/'record.json')
        require(manifest['id']==binding.BASE_IMPLEMENTATION_ID,'frozen statistics manifest changed')
        path=directory/'finqa_v54_statistics.py'
        require(binding.sha(path)==manifest['sha256'][path.name],'frozen CPU statistics source changed')
        name='_v76_pure_frozen_statistics'
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        _STATS=module
    return _STATS


def _previous():
    return binding.source_v75('analysis')


def statistics_contract():
    return dict(schema='v76_fixed_demo_two_window_paired_statistics.v1',
        denominator=883,primary='EA(A1788)-EA(D1788)',comparisons={k:list(v) for k,v in COMPARISONS.items()},
        initial_parent='P1192',reused_fixed_first_window='V75 S1490',
        historical_low_lr_B1490_is_primary_control=False,
        source_cluster=dict(replicates=10000,seed=20261018,
            ordered_clusters='lexicographically sorted actual lineage.source_group',
            rng='numpy.random.Generator(numpy.random.PCG64(seed))',
            same_draws_all_metrics_and_comparisons=True,task_weighted=True,
            interval=[.025,.975],quantile_method='linear'),
        independent_parent_count=1,new_training_seeds=0,
        uncertainty_scope='source-composition sensitivity conditional on one parent and two fixed training paths',
        cross_seed_uncertainty=False,development_is_unseen_confirmation=False,
        UNKNOWN_as_zero=False,UNKNOWN_denominator_reduced=False,
        no_call_denominator=883,no_p_values=True,success_threshold=None,
        old96_new_generations=0,intermediate_score_based_selection=False,
        real_closed_loop_convergence_proved=False,automatic_followup=False)


def compare_reports(new_reports, reused_reports, *, stats=None, previous=None):
    stats = _stats() if stats is None else stats
    previous = _previous() if previous is None else previous
    require(set(new_reports)=={'A1490','A1788','D1788'},'exact three new endpoint reports required')
    require(set(reused_reports)=={'S','P','B'},'original S/P/B references required')
    reports=dict(new_reports,S1490=reused_reports['S'],P1192=reused_reports['P'],B1490=reused_reports['B'])
    expected_steps={'A1490':1490,'A1788':1788,'D1788':1788,'S1490':1490,'P1192':1192,'B1490':1490}
    keys=[row['task_key'] for row in reports['S1490']['results']]
    require(len(keys)==len(set(keys))==883,'full unique development cohort required')
    source_groups=reports['S1490']['results']
    for label,report in reports.items():
        require(report['denominator']==883 and report['step']==expected_steps[label]
            and [r['task_key'] for r in report['results']]==keys,'paired endpoint coordinate/roster changed: '+label)
        require(all(row['source_group']==source['source_group'] for row,source in zip(report['results'],source_groups,strict=True)),
                'paired source-cluster mapping changed: '+label)
    metrics={key:stats.native_metrics(report['results'],883) for key,report in reports.items()}
    for label,correct in (('S1490',557),('P1192',536),('B1490',431)):
        require(metrics[label]['execution_accuracy']['correct']==correct
            and all(metrics[label][m]['unknown']==0 for m in ('execution_accuracy','program_accuracy')),
            'immutable reused endpoint scores changed: '+label)
    pairs={name:previous.paired_metrics(reports[a]['results'],reports[b]['results'],883,stats=stats)
        for name,(a,b) in COMPARISONS.items()}
    vectors={}
    for name,(a,b) in COMPARISONS.items():
        for metric in ('execution_accuracy','program_accuracy'):
            if metrics[a][metric]['unknown']==metrics[b][metric]['unknown']==0:
                vectors[f'{metric}:{name}']=[x['native']['native'][metric]-y['native']['native'][metric]
                    for x,y in zip(reports[a]['results'],reports[b]['results'],strict=True)]
    groups=[row['source_group']['group'] if isinstance(row['source_group'],dict) else row['source_group'] for row in source_groups]
    cluster=stats.source_cluster_sensitivity(vectors,groups)
    cluster.pop('same_weights_all_seeds_and_arms',None)
    cluster.update(same_weights_all_available_comparisons=True,independent_parent_count=1,
        cross_seed_uncertainty=False,uncertainty_scope=statistics_contract()['uncertainty_scope'])
    unknown=any(metrics[label][m]['unknown'] for label in reports for m in ('execution_accuracy','program_accuracy'))
    return dict(schema='v76_three_endpoint_paired_development_analysis.v1',
        status='COMPLETE_WITH_UNKNOWN' if unknown else 'COMPLETE',denominator=883,
        native_metrics=metrics,paired=pairs,primary_comparison='adaptive_A1788_minus_D1788',
        no_call={k:previous.no_call_summary(v['results'],883) for k,v in reports.items()},
        source_cluster_sensitivity=cluster,statistics_contract=statistics_contract(),
        intermediate_accuracy_used_for_selection=False,new_calibration_or_test=0,
        new_teacher_materials=0,historical_B1490_not_algorithm_control=True,
        causal_Novelty_component_identified=False,across_seed_stability_proved=False,
        real_online_convergence_proved=False,old_scores_rescored=False,
        original_V75_failure_changed=False,automatic_followup=False)


def assemble_final_summary(*, analysis, protocol_id, barrier_ref, reports, reused,
                           train_records, material_ref, materials, diagnostics, tracks):
    """The complete metadata interface is tested with actual field placements.

    Planned dose belongs to materials, never a guessed train-completed key.
    Actual consumption belongs to each of the three new train completions.
    """
    require(set(train_records)=={'A1192','A1490','D1490'},'exact three physical new training windows required')
    expected={ 'A1192':(1192,1490,1),'A1490':(1490,1788,1),'D1490':(1490,1788,0)}
    total_updates=total_exposures=0
    consumption={};plans={}
    for key,entry in train_records.items():
        row=entry['record'];start,end,outer=expected[key]
        require(row['status']=='COMPLETE' and row['protocol_id']==protocol_id
            and row['initial_step']==start and row['final_step']==end
            and row['optimizer_updates']==298 and row['outer_updates']==outer
            and row['learning_rate']==1e-5,'new training window dose/state mismatch: '+key)
        actual=row['actual_demonstration_consumption']
        require(actual['status']=='PASS' and actual['updates']==298 and actual['task_exposures']==1488
            and actual['all298_actual_receipts_match_frozen_slots'] is True
            and actual['student_prefix_target_count']==0 and actual['material_id']==materials['id'],
            'actual fixed demonstration consumption differs: '+key)
        plan=row['planned_demonstration_dose']
        require(plan['start_step']==start and plan['end_step']==end and plan['updates']==298
            and plan['task_exposures']==1488 and plan['fixed_teacher_material_id']==materials['id'],
            'window-specific planned teacher dose is not bound to this interval: '+key)
        total_updates+=row['optimizer_updates'];total_exposures+=actual['task_exposures']
        consumption[key]=actual;plans[key]=plan
    require((total_updates,total_exposures)==(894,4464),'physical added optimizer/task budget changed')
    require(set(diagnostics)=={'1192','1490','1788'} and set(tracks)=={'1192_1490','1490_1788'},
            'three frozen references and two target drifts required')
    return dict(analysis,protocol_id=protocol_id,all_jobs_exit_barrier=barrier_ref,
        model_reports=reports,reused_evaluation=reused,
        training_completed={key:value['reference'] for key,value in train_records.items()},
        demonstration_materials=material_ref,original_V75_planned_demonstration_dose=materials['dose'],
        actual_demonstration_consumption=consumption,planned_demonstration_dose_by_window=plans,
        frozen_point_diagnostics=diagnostics,target_tracking=tracks,
        new_development_sessions=2649,new_native_scores=2649,new_feedback_sessions=2100,
        new_total_logical_sessions=4749,new_optimizer_updates=894,new_task_exposures=4464,
        logical_path_updates_each=596,reused_fixed_first_window_updates=298,
        applied_Full_updates=2,terminal_probe_step=1788,terminal_probe_applied=False,
        fixed_material_slots_and_mass=True,new_teacher_collection=0,external_API_calls=0,
        equal_total_compute_claimed=False,endpoint_selected_in_advance=True,
        original_V75_failure_changed=False,automatic_followup=False)


def resource_policy():
    return dict(schema='v76_final_CPU_analysis_resources.v1',max_cpu_children=1,
        rss_historical_peak_limit_bytes=64*1024**3,effective_host_available_reserve_bytes=96*1024**3,
        startup_required_available_bytes=160*1024**3,GPU_workers_required_exited=30,
        GPU_initialization_allowed=False,actual_exit_zero_required=True,automatic_retry=False,
        explicit_stop_no_auto_restart=True,sample_interval_seconds=1)


def run(root, attempt_root):
    # Rebind the existing bounded CPU guard, without touching its frozen globals.
    source=binding.source_v70('finqa_v70_analysis')
    from types import ModuleType
    import sys
    raw=Path(source.__file__).read_text()
    substitutions=(('import finqa_v70_binding as binding','import finqa_v76_binding as binding'),
                   ('finqa_v70_', 'finqa_v76_'),('v70_', 'v76_'))
    for before,after in substitutions: raw=raw.replace(before,after)
    require(raw.count('== 26,')==1,'inherited CPU all-exit guard changed')
    raw=raw.replace('== 26,','== 30,').replace('all_26_jobs_actual_exits_previously_accepted','all_30_jobs_actual_exits_previously_accepted')
    module=ModuleType('_v76_final_CPU_analysis_guard');module.__file__=source.__file__
    sys.modules[module.__name__]=module
    exec(compile(raw,source.__file__+'::V76_private_CPU_guard','exec'),module.__dict__)
    module.resource_policy=resource_policy
    return module.run(root,attempt_root)
