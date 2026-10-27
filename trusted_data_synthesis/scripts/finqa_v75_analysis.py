"""V75 paired development analysis and bounded V74 state-stratum description.

All efficacy summaries describe a single shared parent and a repeatedly used
883-task development panel. No statistic creates an automatic training gate.
"""
from __future__ import annotations
from collections import Counter
import importlib

DENOMINATOR = 883


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _binding():
    return importlib.import_module("finqa_v75_binding")


def _stats():
    return _binding().source_module("finqa_v63_statistics")


def statistics_contract():
    return dict(schema="v75_one_parent_paired_development_statistics.v1",
        denominator=883, candidate="S_StateDemo1490", reused_control="B_V72LowLR1490",
        reused_parent="P_Fixed1192", reused_correct=dict(B=431,P=536),
        primary="(S-431)/883", parent_net_gain="(S-536)/883",
        independent_training_parent_count=1, new_candidate_training_branches=1,
        reused_control_is_new_independent_replication=False,
        paired_orientation="old original trajectory -> candidate; candidate minus reference",
        metrics=["execution_accuracy","program_accuracy","I/W/R/UNKNOWN","new_correct","lost_correct"],
        no_call_stages=["initial","post_tool"], no_call_stage_denominator=883,
        UNKNOWN_as_zero=False, UNKNOWN_denominator_reduced=False,
        mechanism_slice="the existing V73 fixed96 F/K48 tasks within this single dev883 run",
        new_slice_generation=0, source_cluster=dict(replicates=10000,seed=20261018,
            implementation="original frozen V54 source_cluster_sensitivity",
            ordered_clusters="lexicographically sorted actual lineage.source_group",
            rng="numpy.random.Generator(numpy.random.PCG64(seed))",
            draw="G uniform source-cluster indices with replacement per replicate",
            same_cluster_weights_all_available_comparisons=True,
            statistic="sum(sampled cluster paired sums)/sum(sampled cluster question counts)",
            task_weighted=True, percentile_interval=[.025,.975],quantile_method="linear",
            uncertainty_scope="source-composition sensitivity conditional on one fixed parent and training realization",
            cross_seed_uncertainty=False, significance_or_stability_confirmation=False),
        development_panel_is_unseen_confirmation=False, intervention_is_combination=True,
        causal_components_identified=False, unit_compute_advantage_claimed=False,
        no_p_values=True, advancement_threshold=None, automatic_followup=False,
        automatic_Full_resume=False)


def no_call_stage(row):
    if row["stop_reason"] != "no_tool_call":
        return None
    tools,calls = row["tool_call_count"],row["actual_model_calls"]
    require(type(tools) is int and tools >= 0 and type(calls) is int and calls > 0,
            "complete no-call path requires actual model/tool counts")
    require((tools == 0 and calls == 1) or (tools > 0 and calls > 1),
            "no-call stage is inconsistent with actual native history")
    return "initial" if tools == 0 else "post_tool"


def no_call_summary(rows, denominator):
    require(len(rows)==denominator,"no-call stages retain the full evaluation denominator")
    counts=Counter(no_call_stage(row) for row in rows)
    return dict(denominator=denominator,total_no_call=counts['initial']+counts['post_tool'],
        initial=dict(count=counts['initial'],denominator=denominator,rate=counts['initial']/denominator),
        post_tool=dict(count=counts['post_tool'],denominator=denominator,rate=counts['post_tool']/denominator),
        conditional_stage_failure_rate_used=False)


def paired_no_call(candidate, reference, denominator, *, stats=None):
    stats=_stats() if stats is None else stats
    require(len(candidate)==len(reference)==denominator
        and [r['task_key'] for r in candidate]==[r['task_key'] for r in reference],"paired no-call roster changed")
    output={}
    for stage in ('initial','post_tool'):
        before=[i for i,row in enumerate(reference) if no_call_stage(row)==stage]
        after=[i for i,row in enumerate(candidate) if no_call_stage(row)==stage]
        ended=Counter(stats.native_state(candidate[i]) for i in before)
        removed=[i for i in before if no_call_stage(candidate[i])!=stage]
        outcome=Counter(stats.native_state(candidate[i]) for i in removed)
        output[stage]=dict(full_denominator=denominator,reference_count=len(before),candidate_count=len(after),
            reduction_count=len(before)-len(after),reduction_rate=(len(before)-len(after))/denominator,
            old_stage_no_call_to_candidate_state={s:ended[s] for s in ('I','W','R','UNKNOWN')},
            no_longer_same_stage_no_call_count=len(removed),
            no_longer_same_stage_no_call_to_state={s:outcome[s] for s in ('I','W','R','UNKNOWN')},
            still_any_no_call=sum(no_call_stage(candidate[i]) is not None for i in before),
            reference_no_call_to_candidate_stop=dict(Counter(candidate[i]['stop_reason'] for i in before)),
            old_source_tasks=[reference[i]['task_key'] for i in before])
    return dict(denominator=denominator,stages=output,
        more_actions_do_not_imply_higher_EA=True,full_denominators=True)


def paired_metrics(candidate,reference,denominator,*,stats=None):
    stats=_stats() if stats is None else stats
    require([r['task_key'] for r in candidate]==[r['task_key'] for r in reference],"paired native roster changed")
    ea=stats.paired_transitions(candidate,reference,denominator)
    transitions=ea['transitions']
    ea.update(new_correct_known_pairs=transitions['I->R']+transitions['W->R'],
        lost_correct_known_pairs=transitions['R->I']+transitions['R->W'],
        net_correct=ea.get('numerator'))
    before=[r['native']['native']['program_accuracy'] for r in reference]
    after=[r['native']['native']['program_accuracy'] for r in candidate]
    require(all(v is None or v in (0,1) for v in before+after),"native PA must be binary/UNKNOWN")
    pairs=list(zip(before,after,strict=True)); known=[(b,a) for b,a in pairs if b is not None and a is not None]
    gain=sum(b==0 and a==1 for b,a in known);loss=sum(b==1 and a==0 for b,a in known)
    pa=dict(denominator=denominator,unknown_pairs=denominator-len(known),
        new_correct_known_pairs=gain,lost_correct_known_pairs=loss,
        numerator=gain-loss if len(known)==denominator else None,
        difference=(gain-loss)/denominator if len(known)==denominator else None,
        transitions={f'{b}->{a}':sum(x==b and y==a for x,y in known) for b in (0,1) for a in (0,1)})
    return dict(execution_accuracy=ea,program_accuracy=pa,
        no_call=paired_no_call(candidate,reference,denominator,stats=stats))


def _validate_reports(reports,denominator=883):
    require(set(reports)=={'S','B','P'},"exact candidate and two fixed reused references required")
    tasks=[r['task_key'] for r in reports['S']['results']]
    require(len(tasks)==len(set(tasks))==denominator,"complete distinct dev roster required")
    for label,report in reports.items():
        require(report['denominator']==denominator and [r['task_key'] for r in report['results']]==tasks,
                "full paired task order changed: "+label)
        require(all(r['source_group']==s['source_group'] for r,s in zip(report['results'],reports['S']['results'],strict=True)),
                "source-cluster mapping differs between paired models")
    return tasks


def compare_reports(candidate,baseline,parent,selection,*,stats=None):
    stats=_stats() if stats is None else stats
    reports=dict(S=candidate,B=baseline,P=parent)
    tasks=_validate_reports(reports)
    metrics={label:stats.native_metrics(report['results'],883) for label,report in reports.items()}
    require(metrics['B']['execution_accuracy']['correct']==431
        and metrics['P']['execution_accuracy']['correct']==536
        and reports['B']['step']==1490 and reports['P']['step']==1192,
        "fixed B431/P536 reference coordinates changed;894 baseline is not P")
    require(all(metrics[label][metric]['unknown']==0 for label in ('B','P') for metric in ('execution_accuracy','program_accuracy')),
            "sealed old comparison has UNKNOWN")
    pairs={f'S-{label}':paired_metrics(candidate['results'],reports[label]['results'],883,stats=stats) for label in ('B','P')}
    vectors={}
    for label in ('B','P'):
        for metric in ('execution_accuracy','program_accuracy'):
            if metrics['S'][metric]['unknown']==0:
                vectors[f'{metric}:S-{label}']=[s['native']['native'][metric]-r['native']['native'][metric]
                    for s,r in zip(candidate['results'],reports[label]['results'],strict=True)]
    groups=[r['source_group']['group'] if isinstance(r['source_group'],dict) else r['source_group'] for r in candidate['results']]
    cluster=stats.source_cluster_sensitivity(vectors,groups)
    # The frozen arithmetic is shared; its old three-parent prose is inapplicable.
    cluster.pop('same_weights_all_seeds_and_arms',None)
    cluster.update(same_weights_all_available_comparisons=True,
        uncertainty_scope=statistics_contract()['source_cluster']['uncertainty_scope'],
        independent_training_parent_count=1,cross_seed_uncertainty=False,
        incomplete_metrics_not_imputed=True)
    require(len(selection['selected'])==96 and Counter(r['group'] for r in selection['selected'])=={'F':48,'K':48},
            "old fixed mechanism slice changed")
    chosen={r['task_key']:r['group'] for r in selection['selected']}
    require(len(chosen)==96 and set(chosen)<=set(tasks),"old96 slice escaped dev883")
    slices={}
    for group in ('F','K'):
        sliced={label:[r for r in report['results'] if chosen.get(r['task_key'])==group] for label,report in reports.items()}
        require(all(len(rows)==48 for rows in sliced.values()),"mechanism slice denominator changed")
        slices[group]=dict(denominator=48,native_metrics={k:stats.native_metrics(v,48) for k,v in sliced.items()},
            paired={f'S-{k}':paired_metrics(sliced['S'],sliced[k],48,stats=stats) for k in ('B','P')},
            no_call={k:no_call_summary(v,48) for k,v in sliced.items()},
            reused_conditional_selection=True,new_episodes=0,independent_validation=False)
    correct=metrics['S']['execution_accuracy']['correct'];known=metrics['S']['execution_accuracy']['unknown']==0
    if not known:case='INCOMPLETE_UNKNOWN'
    elif correct<=431:case='candidate_does_not_exceed_reused_low_lr_control'
    elif correct<536:case='mitigated_decline_but_no_parent_net_gain'
    elif correct==536:case='parent_total_retained_not_per_task_equivalence'
    else:case='observed_recipe_increment_and_parent_net_gain_on_development'
    return dict(schema='v75_candidate_paired_complete_development_analysis.v1',
        status='COMPLETE' if all(metrics['S'][m]['unknown']==0 for m in ('execution_accuracy','program_accuracy')) else 'COMPLETE_WITH_UNKNOWN',
        denominator=883,native_metrics=metrics,paired=pairs,
        estimands=dict(S_correct=correct,B_correct=431,P_correct=536,
            S_minus_B=pairs['S-B']['execution_accuracy'],S_minus_P=pairs['S-P']['execution_accuracy'],
            formulas={'S-B':'(S-431)/883','S-P':'(S-536)/883'},descriptive_count_case=case),
        no_call={k:no_call_summary(report['results'],883) for k,report in reports.items()},
        source_cluster_sensitivity=cluster,fixed_old96_mechanism_slice=slices,
        statistics_contract=statistics_contract(),old_scores_rescored=False,
        new_old96_generations=0,development_is_unseen_confirmation=False,
        inherited_pi_was_never_reweighted=False,new_adaptive_distribution_updates=0,
        combination_recipe_effect_only=True,individual_components_identified=False,
        independent_parent_count=1,independent_seed_replication=False,
        automatic_followup=False,automatic_Full_resume=False)


def v74_state_stratification(final):
    require(final['status']=='COMPLETE' and final['conditional_trajectory_denominator']==192
        and final['distinct_tasks']==96,"V74 fixed complete summary required")
    contexts=final['context_structure']['rows']; rows=final['results']
    mapping={(r['task_key'],r['direction']):r for r in rows}
    require(len(contexts)==96 and len(mapping)==192,"V74 context/results coverage changed")
    stats=_stats(); output={}
    for group in ('F','K'):
        strata={}
        for key,p_test,l_test in (('both_initial',False,False),('parent_post_student_initial',True,False),
                ('both_post_tool',True,True),('parent_initial_student_post',False,True)):
            selected=[c for c in contexts if c['group']==group
                and bool(c['hP']['already_executed_tool_events'])==p_test
                and bool(c['hL']['already_executed_tool_events'])==l_test]
            value=dict(denominator=len(selected),task_keys=[c['task_key'] for c in selected],directions={})
            for direction in ('L_from_P','P_from_L'):
                found=[mapping[(c['task_key'],direction)] for c in selected]
                states=Counter(stats.native_state(r) for r in found)
                value['directions'][direction]=dict(states={s:states[s] for s in ('I','W','R','UNKNOWN')},
                    EA_correct=states['R'],no_call=sum(r['stop_reason']=='no_tool_call' for r in found))
            strata[key]=value
        output[group]=strata
    require([output['F'][k]['denominator'] for k in ('both_initial','parent_post_student_initial','both_post_tool')]==[3,26,19],
            "V74 expected descriptive F stratum counts differ")
    return dict(schema='v75_readonly_V74_state_stratification.v1',status='COMPLETE',strata=output,
        source_final_summary_id=final['id'],posthoc_descriptive_not_independent_test=True,
        original_scores_changed=False,new_model_calls=0,new_tool_calls=0,new_native_scores=0,
        new_raw_episode_reads=0,new_probability_measurements=0)


def prepare_readonly():
    b=_binding()
    path=b.V74_ROOT/'final_summary/record.json'
    result=v74_state_stratification(b.checked(path))
    return dict(result,source=b.entry(path),producer=b.file_ref(b.REPO/'trusted_data_synthesis/scripts/finqa_v75_analysis.py'))
