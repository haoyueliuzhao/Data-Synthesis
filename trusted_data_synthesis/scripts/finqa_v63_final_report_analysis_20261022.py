"""Derive the final V63 report from already accepted native score rows only.

No model, provider, native scorer, private reference, generation output or
checkpoint is opened. Original V63 statistics and old bound report readers
are reused unchanged. Publishing is a separate, new-root-only operation and
does not convert an excepted original numerical failure into a passed contract.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
SCIENTIFIC_ROOT = V18 / 'v63_balanced_feedback_repetition_01'
SCORING_ROOT = SCIENTIFIC_ROOT / 'partial_scoring_01'
OUTPUT_ROOT = SCIENTIFIC_ROOT / 'report_analysis_01'
PUBLISHED_SUMMARY = REPO / 'trusted_data_synthesis/docs/report_data/finqa_v63_v69_report_summary_20261022.json'
BASE_PROTOCOL_ID = 'a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db'
IMPLEMENTATION_ID = '4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8'
SCORING_PROTOCOL_ID = '761831993c8c25c3db2584d896984c86ec82794f189539aa776c04eca9a8ff90'
GIB = 1024 ** 3


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 ** 2), b''):
            result.update(chunk)
    return result.hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value.get('id') == digest({key: row for key, row in value.items() if key != 'id'}),
            'immutable saved report identity changed: ' + str(path))
    return value


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def read_ref(reference, expected=None):
    path = Path(reference['path']).resolve()
    require(expected is None or path == Path(expected).resolve(), 'report reference escaped its registered path')
    require(sha(path) == reference['sha256'], 'bound saved report bytes changed: ' + str(path))
    value = checked(path)
    require('id' not in reference or value['id'] == reference['id'], 'bound report ID changed')
    return value


def _frozen():
    """Select the actual immutable V63 statistics, not workspace alternatives."""
    directory = SCIENTIFIC_ROOT / 'implementation'
    manifest = checked(directory / 'record.json')
    require(manifest['id'] == IMPLEMENTATION_ID, 'original scientific implementation changed')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    binding = importlib.import_module('finqa_v63_binding')
    require(Path(binding.__file__).resolve() == directory / 'finqa_v63_binding.py',
            'report analysis cannot load a workspace scientific binding')
    binding.install_scientific_paths()
    evaluation = importlib.import_module('finqa_v63_evaluation')
    statistics = importlib.import_module('finqa_v63_statistics')
    sources = {}
    for module in (binding, evaluation, statistics, statistics.original):
        path = Path(module.__file__).resolve()
        require(path.parent == directory and sha(path) == manifest['sha256'][path.name],
                'report calculation must use exact frozen scientific readers and mathematics')
        sources[path.name] = file_ref(path)
    return evaluation, statistics, sources


def _complete_scoring_gate(closeout, protocol, coordinates):
    require(closeout['status'] == 'ALL_SIX_GROUPS_SCORED_AWAITING_GLOBAL_ANALYSIS'
            and closeout['protocol_id'] == protocol['id'] == SCORING_PROTOCOL_ID
            and closeout['scientific_protocol_id'] == BASE_PROTOCOL_ID
            and closeout['active_workers'] == 0 and closeout['accepted_native_scores'] == 7458
            and closeout['total_registered_groups'] == 6
            and set(closeout['accepted_groups']) == set(coordinates)
            and all(closeout['group_states'][key]['status'] == 'COMPLETE' for key in coordinates),
            'derive the final report only after all six real CPU scoring attempts are accepted')


def _load_scored_groups(evaluation):
    science = checked(SCIENTIFIC_ROOT / 'protocol/record.json')
    protocol = checked(SCORING_ROOT / 'protocol/record.json')
    closeout = checked(SCORING_ROOT / 'closeout/record.json')
    require(science['id'] == BASE_PROTOCOL_ID and science['evaluation'] == evaluation.evaluation_contract(),
            'original prospective scientific evaluation contract changed')
    coordinates = [evaluation.stats.coordinate(seed, arm) for seed in evaluation.SEEDS for arm in evaluation.ARMS]
    _complete_scoring_gate(closeout, protocol, coordinates)
    old_plan = read_ref(protocol['source_generation_registration'])
    final_plan = read_ref(protocol['completion_generation_registration'])
    require(old_plan['scientific_protocol_id'] == final_plan['scientific_protocol_id'] == science['id']
            and old_plan['cohorts'] == final_plan['cohorts']
            and old_plan['snapshot_id'] == final_plan['snapshot_id'],
            'original twenty-plus-four generation registrations must retain one evaluation cohort')
    jobs = {**old_plan['jobs'], **final_plan['jobs']}
    planned = evaluation.planned_jobs()
    require(len(old_plan['jobs']) == 20 and len(final_plan['jobs']) == 4
            and not (set(old_plan['jobs']) & set(final_plan['jobs']))
            and set(jobs) == set(planned)
            and all(all(jobs[key].get(field) == value for field, value in job.items())
                    for key, job in planned.items()), 'saved scoring dose must remain the original 24 jobs/7458 sessions')
    reports = {panel: {} for panel in science['evaluation']['panels']}
    evidence, seen_jobs = {}, set()
    for coordinate in coordinates:
        directory = SCORING_ROOT / 'groups' / coordinate
        accepted_ref = closeout['accepted_groups'][coordinate]
        accepted = read_ref(accepted_ref, directory / 'accepted/record.json')
        result = read_ref(accepted['group_result'], directory / 'result/record.json')
        actual = read_ref(accepted['actual_exit'])
        attempt = Path(accepted['actual_exit']['path']).resolve().parent.parent
        require(attempt == SCORING_ROOT / 'attempts' / coordinate.replace('/', '_') / 'attempt0001',
                'CPU score acceptance points outside its registered attempt')
        launch = checked(attempt / 'launch/record.json')
        resources = read_ref(accepted['resource_closeout'], attempt / 'resource_closeout/record.json')
        require(accepted['schema'] == 'v68_actual_complete_group_score_accepted.v1'
                and accepted['protocol_id'] == actual['protocol_id'] == launch['protocol_id']
                    == resources['protocol_id'] == result['protocol_id'] == protocol['id']
                and accepted['coordinate'] == actual['coordinate'] == launch['coordinate']
                    == resources['coordinate'] == result['coordinate'] == coordinate
                and accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
                and accepted['group_result_id'] == result['id']
                and actual['returncode'] == 0 and actual['actual_waitpid_observed'] is True
                and (actual['pid'], actual['birth']) == (launch['pid'], launch['birth'])
                and resources['all_gates_passed'] is True and resources['CUDA_initialized'] is False
                and resources['pid'] == actual['pid'] and resources['peak_rss_bytes'] <= 32 * GIB
                and resources['minimum_host_available_bytes'] >= 96 * GIB
                and result['scoring_execution_complete'] is True
                and result['sessions'] == result['native_scores_present'] == accepted['complete_original_sessions'] == 1243
                and result['scientific_protocol_id'] == science['id'] and result['feedback_batch'] == 1,
                'saved score result requires its exact actual successful CPU exit and original resource acceptance')
        eligibility = read_ref(result['eligibility'], SCORING_ROOT / 'eligibility' / coordinate / 'record.json')
        expected = {key for key, job in jobs.items() if coordinate == f"seed{job['seed']}/{job['arm']}"}
        require(len(expected) == 4 and set(result['job_scores']) == set(eligibility['jobs']) == expected
                and eligibility['coordinate'] == coordinate and eligibility['feedback_batch'] == 1
                and eligibility['sessions'] == 1243 and eligibility['scientific_protocol_id'] == science['id']
                and launch['eligibility'] == result['eligibility']
                and set(result['model_reports']) == set(reports),
                'saved accepted four-job source provenance or panel coverage changed')
        for key in expected:
            proof = eligibility['jobs'][key]
            require(proof['job'] == jobs[key]
                    and proof['source_kind'] == ('V67_GPU_EXIT_ZERO' if key in final_plan['jobs'] else 'V65_CPU_COMPOSITE'),
                    'generation provenance must retain old GPU1/CPU0 or new actual GPU0 acceptance as registered')
            reference = result['job_scores'][key]
            require(Path(reference['path']).resolve() == directory / 'jobs' / key / 'record.json'
                    and sha(reference['path']) == reference['sha256'],
                    'saved per-job score bytes changed after accepted group scoring')
        require(not (seen_jobs & expected), 'a generation job cannot be counted in two groups')
        seen_jobs.update(expected)
        for panel, reference in result['model_reports'].items():
            report = read_ref(reference, directory / 'panels' / panel / 'record.json')
            require(report['protocol_id'] == protocol['id'] and report['eligibility'] == result['eligibility']
                    and report['coordinate'] == coordinate and report['panel'] == panel
                    and report['scientific_protocol_id'] == science['id']
                    and report['feedback_batch'] == 1
                    and all(reference == result['job_scores'][key]
                            for key, reference in report['job_score_refs'].items()),
                    'saved model-panel report changed its accepted original job source chain')
            reports[panel][coordinate] = report
        evidence[coordinate] = dict(accepted=accepted_ref, actual_CPU_exit=accepted['actual_exit'],
            CPU_resources=accepted['resource_closeout'], group_result=accepted['group_result'],
            generation_eligibility=result['eligibility'], job_scores=result['job_scores'],
            model_reports=result['model_reports'])
    require(len(seen_jobs) == 24 and sum(jobs[key]['denominator'] for key in seen_jobs) == 7458,
            'full accepted native scoring dose changed')
    # This in-memory read-only view supplies the original panel contract to the
    # frozen old-report reader. No registration, run, summary or source is saved.
    view = dict(old_plan, contract=science['evaluation'])
    return science, protocol, closeout, view, reports, evidence


def _panel_layout(spec, cohort):
    require(len(cohort['tasks']) == len(set(cohort['tasks'])) == spec['tasks_per_draw'],
            'panel unique-task denominator changed')
    draws = spec['draw_seeds']
    tasks = [f'draw{draw}/{task}' for draw in draws for task in cohort['tasks']]
    groups = {f'draw{draw}/{task}': cohort['source_groups'][task]
              for draw in draws for task in cohort['tasks']}
    return tasks, groups, dict(unique_tasks=spec['tasks_per_draw'], draws_per_task=len(draws),
        draw_order=draws, paired_session_denominator=len(tasks),
        repeated_draws_are_not_additional_unique_questions=len(draws) > 1)


def _model_metrics(reports, references):
    return {key: dict(seed=report['seed'], arm=report['arm'], feedback_batch=report.get('feedback_batch'),
        denominator=report['denominator'], metrics=report['metrics'], saved_model_report=references[key])
        for key, report in reports.items()}


def _arm_means(reports, arms, seeds):
    result = {}
    for arm in arms:
        members = [reports[f'seed{seed}/{arm}'] for seed in seeds]
        denominator = members[0]['denominator']
        metrics = {}
        for name in ('execution_accuracy', 'program_accuracy'):
            values = [member['metrics'][name] for member in members]
            unknown = sum(value['unknown'] for value in values)
            correct = sum(value['correct'] for value in values)
            metrics[name] = dict(per_parent_denominator=denominator, parent_repeats=len(seeds),
                total_correct=correct, total_unknown=unknown,
                equal_weight_parent_mean=correct / (len(seeds) * denominator) if unknown == 0 else None,
                pooled_denominator_is_not_independent_question_count=True)
        result[arm] = dict(metrics=metrics,
            state_counts_across_parent_repeats={state: sum(member['metrics']['states'][state] for member in members)
                                              for state in ('I', 'W', 'R', 'UNKNOWN')})
    return result


def _numerical_gates(summary, statistics):
    require(summary['denominator'] == statistics.PRIMARY_DENOMINATOR
            and summary['independent_parent_count'] == 3, 'numerical gates apply only to dev883 across three parents')
    names = ('C05-C1', 'C05-Hold', 'C1-Hold')
    complete = all(summary['comparisons'][name]['status'] == 'COMPLETE' for name in names)
    totals = ({name: sum(summary['comparisons'][name]['per_seed'][str(seed)]['numerator']
                         for seed in statistics.SEEDS) for name in names} if complete else None)
    if totals is not None:
        require(totals['C05-Hold'] == totals['C05-C1'] + totals['C1-Hold'],
                'exact paired contrasts do not add up')
    temperature = None if totals is None else totals['C05-C1'] >= statistics.MINIMUM_TEMPERATURE_NET_CORRECT
    hold = None if totals is None else totals['C05-Hold'] >= statistics.MINIMUM_HOLD_NET_CORRECT
    return dict(comparison_scores_complete=complete, total_paired_denominator=3 * statistics.PRIMARY_DENOMINATOR,
        net_correct_totals=totals, minimum_temperature_net_correct=statistics.MINIMUM_TEMPERATURE_NET_CORRECT,
        minimum_hold_net_correct=statistics.MINIMUM_HOLD_NET_CORRECT,
        temperature_numerical_gate_passed=temperature, hold_numerical_gate_passed=hold,
        both_numerical_gates_passed=None if totals is None else temperature and hold,
        raw_predeclared_numbers_only=True, original_all_contracts_passed=False,
        formal_advancement_function_called=False, automatic_followup_authorized=False,
        retained_contract_failure='seed389/C05 draw-gradient-mean diagnostic FAIL, accepted only under the V66 single-point exception')


def _feedback_support_counts(roster, rewards, groups):
    """Describe already frozen binary rewards; this is not a scorer."""
    require(len(roster) == len(rewards) == 700
            and all(type(value) in (int, float) and value in (0, 1) for value in rewards),
            'feedback support keeps all 700 frozen known binary rewards')
    draws = {seed: [row['task_id'] for row in roster if row['seed'] == seed] for seed in (101, 103)}
    require(all(len(tasks) == len(set(tasks)) == 350 for tasks in draws.values())
            and set(draws[101]) == set(draws[103]) and set(draws[101]) <= set(groups)
            and all(row['seed'] in (101, 103) for row in roster),
            'feedback support must retain the original two draws of the same 350 tasks')
    successful_tasks = {row['task_id'] for row, value in zip(roster, rewards, strict=True) if value == 1}
    available_groups = {groups[task] for task in draws[101]}
    return dict(session_denominator=700, unique_task_denominator=350,
        source_group_denominator=len(available_groups), successful_feedback_sessions=int(sum(rewards)),
        successful_sessions_by_draw={str(seed): sum(value == 1 for row, value in zip(roster, rewards, strict=True)
                                                       if row['seed'] == seed) for seed in (101, 103)},
        distinct_successful_tasks=len(successful_tasks),
        distinct_successful_source_groups=len({groups[task] for task in successful_tasks}),
        zero_reward_sessions_retained=True)


def _feedback_support(statistics):
    group_path = SCIENTIFIC_ROOT / 'diagnostics/inputs/feedback_source_groups/record.json'
    groups = checked(group_path)['groups']
    rows = {}
    for seed in statistics.SEEDS:
        for arm in statistics.ARMS:
            key = statistics.coordinate(seed, arm)
            stage = SCIENTIFIC_ROOT / f'stages/seed{seed}/feedback_{arm}'
            stage_path = stage / 'result/record.json'
            stage_result = checked(stage_path)
            condition = stage_result['condition_id']
            directory = stage / 'feedback' / condition
            intent_path, reward_path = directory / 'intent/record.json', directory / 'native_rewards/record.json'
            intent = checked(intent_path)
            raw = reward_path.read_bytes()
            reward = json.loads(raw)  # This original artifact has no generic immutable-record id field.
            require(stage_result['status'] == 'COMPLETE' and reward['condition_id'] == condition
                    and intent['id'] == condition, 'feedback support must use the same already sealed condition')
            replay_path = SCIENTIFIC_ROOT / f'stages/seed{seed}/replay_{arm}/result/record.json'
            replay = checked(replay_path)
            require(replay['status'] == 'COMPLETE' and type(replay['responses']) is int,
                    'reported replay response count must come from its saved complete stage result')
            rows[key] = dict(seed=seed, arm=arm, feedback_batch=1, condition_id=condition,
                **_feedback_support_counts(intent['ordered_episode_roster'], reward['rewards'], groups),
                gradient_replay_response_count=replay['responses'],
                source_refs=dict(feedback_result=file_ref(stage_path), feedback_intent=file_ref(intent_path),
                    frozen_native_rewards=dict(path=str(reward_path), sha256=hashlib.sha256(raw).hexdigest()),
                    replay_result=file_ref(replay_path)))
    return dict(schema='v63_derived_read_only_feedback_support_counts.v1', rows=rows,
        source_group_mapping=file_ref(group_path), total_feedback_sessions=4200,
        total_gradient_replay_responses=sum(row['gradient_replay_response_count'] for row in rows.values()),
        total_successful_feedback_sessions=sum(row['successful_feedback_sessions'] for row in rows.values()),
        feedback_success_is_not_final_evaluation_accuracy=True,
        replay_response_count_is_not_successful_session_count=True,
        native_rewards_rescored=False, new_postrun_diagnostic_computed=False,
        C_q_TV_KL_coefficient_or_gradient_calculations=0)


def build_report():
    """Read-only derivation: saved native scores in, original paired statistics out."""
    evaluation, statistics, frozen_sources = _frozen()
    science, scoring, closeout, view, new_by_panel, accepted = _load_scored_groups(evaluation)
    panels = {}
    for panel, spec in science['evaluation']['panels'].items():
        tasks, groups, denominator = _panel_layout(spec, view['cohorts'][spec['role']])
        new = new_by_panel[panel]
        for report in new.values():
            require(report['original_panel_config'] == spec and report['original_draw_order'] == spec['draw_seeds']
                    and all(row['source_group'] == groups[row['task_key']] for row in report['results']),
                    'new report source groups, draw order or original panel config changed')
        old_summary, old = evaluation.reused_old_reports(SCIENTIFIC_ROOT, panel, view, tasks, groups)
        holds = {statistics.original.coordinate(seed, 'Hold'): old[statistics.original.coordinate(seed, 'Hold')]
                 for seed in statistics.SEEDS}
        paired = statistics.paired_summary(new, tasks, groups, denominator=len(tasks), old_hold_reports=holds)
        replication = statistics.batch_replication_diagnostics(new, old, tasks, denominator=len(tasks))
        new_refs = {key: accepted[key]['model_reports'][panel] for key in new}
        panels[panel] = dict(panel=panel, primary=panel == evaluation.PRIMARY_PANEL, role=spec['role'],
            denominator=denominator, new_b1_model_metrics=_model_metrics(new, new_refs),
            old_b0_and_Hold_model_metrics=_model_metrics(old, old_summary['model_reports']),
            new_b1_arm_mean_metrics=_arm_means(new, statistics.ARMS, statistics.SEEDS),
            old_b0_and_Hold_arm_mean_metrics=_arm_means(old, statistics.original.ARMS, statistics.SEEDS),
            paired_new_batch=paired, same_temperature_batch_replication=replication,
            reused_old_summary=science['old_evaluation_summaries'][panel],
            reused_old_batch_comparisons=old_summary['comparisons'],
            reused_old_source_cluster_sensitivity=old_summary['source_cluster_sensitivity'],
            old_results_rescored=False, old_bootstrap_recomputed=False)
    numerical = _numerical_gates(panels[evaluation.PRIMARY_PANEL]['paired_new_batch'], statistics)
    body = dict(schema='v63_saved_score_final_report_analysis_20261022.v1',
        status='DERIVED_ANALYSIS_COMPLETE_ORIGINAL_EXCEPTION_RETAINED',
        scientific_protocol_id=science['id'], scoring_protocol_id=scoring['id'],
        scientific_protocol=file_ref(SCIENTIFIC_ROOT / 'protocol/record.json'),
        all_six_scoring_closeout=file_ref(SCORING_ROOT / 'closeout/record.json'),
        accepted_scoring_groups=accepted, score_sessions=7458, generation_jobs=24,
        independent_parent_count=3, new_feedback_batch=1, reused_old_feedback_batch=0,
        primary_panel=evaluation.PRIMARY_PANEL, panels=panels,
        feedback_support_summary=_feedback_support(statistics),
        statistics_contract=statistics.statistics_contract(), primary_numerical_gates=numerical,
        computation_sources=frozen_sources, report_script=file_ref(__file__),
        retained_single_point_exception_protocol=file_ref(SCIENTIFIC_ROOT / 'single_diagnostic_exception_01/protocol/record.json'),
        original_native_generation_and_private_references_not_reopened=True,
        native_generation_reaudit_performed=False,
        provenance_basis='accepted V68 real CPU exits and byte-bound four-job source eligibility; immutable saved score reports',
        new_native_scoring_calls=0, old_native_rescoring_calls=0, new_generation_calls=0,
        new_GPU_or_API_calls=0, new_optimizer_updates=0,
        original_scientific_experiment_marked_complete=False,
        original_all_contracts_passed=False, formal_advancement_computed=False,
        automatic_followup_authorized=False,
        uncertainty_caveats=dict(three_parents_only=True, seed_t_interval_strong_untestable_normality_assumption=True,
            source_cluster_bootstrap_conditional_on_fixed_parents=True,
            source_cluster_bootstrap_does_not_replace_seed_uncertainty=True,
            repeated_calibration_draws_do_not_double_unique_tasks=True,
            no_multiplicity_adjustment=True, no_p_values=True, no_significance_or_stability_claim=True,
            old_new_feedback_batches_not_pooled_or_selected=True))
    return dict(body, id=digest(body))


def _publish_exact(path, report, encoded):
    require(not path.is_symlink(), 'derived report may not replace a symlink')
    if path.exists():
        require(checked(path) == report and path.read_bytes() == encoded, 'existing derived report is immutable')
        return file_ref(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.report-analysis-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return file_ref(path)


def publish_report(report, output_root=OUTPUT_ROOT, *, published_summary=None):
    """Publish this derived JSON only, never an old experiment summary."""
    root = Path(output_root).resolve()
    require(root == Path(OUTPUT_ROOT).resolve() and not Path(output_root).is_symlink(),
            'derived report publication is restricted to the new report_analysis_01 root')
    require(report['id'] == digest({key: value for key, value in report.items() if key != 'id'}),
            'derived report identity changed before publication')
    if published_summary is not None:
        require(Path(published_summary).resolve() == PUBLISHED_SUMMARY.resolve(),
                'the optional published summary must use its one exact repository report path')
    path = root / 'record.json'
    encoded = (json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    reference = _publish_exact(path, report, encoded)
    if published_summary is not None:
        mirror = _publish_exact(Path(published_summary), report, encoded)
        require(mirror['sha256'] == reference['sha256'], 'published summary must match the derived record byte for byte')
    return reference


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_ROOT)
    parser.add_argument('--no-write', action='store_true')
    parser.add_argument('--published-summary', type=Path)
    args = parser.parse_args(argv)
    require(args.output_root.resolve() == OUTPUT_ROOT.resolve(), 'only the registered derived-report output root is allowed')
    report = build_report()
    output = None if args.no_write else publish_report(report, args.output_root,
                                                     published_summary=args.published_summary)
    print(json.dumps(dict(id=report['id'], status=report['status'], output=output,
        primary_numerical_gates=report['primary_numerical_gates'],
        native_scores_recomputed=0, old_experiment_records_written=0), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
