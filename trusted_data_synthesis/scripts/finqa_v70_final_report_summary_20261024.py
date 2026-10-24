"""Summarize accepted V70 JSON evidence without reopening scientific execution.

Only saved scores, diagnostics, lifecycle/resource closeouts and frozen reward
JSON are read. No model, Tensor, original Episode, private-reference file,
native scorer, optimizer, bootstrap or frozen-map execution is imported.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
ROOT = V18 / 'v70_full_closed_loop_01'
OUTPUT_ROOT = ROOT / 'report_analysis_01'
PUBLISHED_SUMMARY = REPO / 'trusted_data_synthesis/docs/report_data/finqa_v70_report_summary_20261024.json'
PROTOCOL_ID = 'a5ca2c859c88db4b5b4db84a1c3afc2aa4feccd193b098a2b5d5174322cf9c78'
IMPLEMENTATION_ID = '7ba22615a08cc7763bb30ff4a6da9c5930e3747be2eabfa4a1253213baa82589'
CLOSEOUT_ID = '1c247ed079c09ec570c839aa5591531c396eb18a4ea42313c9dce13a9bf3bd81'
FINAL_SUMMARY_ID = '89843fcd8abcc731ce657fe2d9bd3114327e968dcbaaf48924ac71901324c91e'
POINTS = (894, 1192, 1490)
GIB = 1024 ** 3
BJT = timezone(timedelta(hours=8))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def bjt(epoch):
    return datetime.fromtimestamp(epoch, BJT).isoformat()


def pick(value, names):
    return {name: value[name] for name in names if name in value}


class Reader:
    """Cache each small immutable JSON once; never follow a Tensor reference."""

    def __init__(self):
        self.cache = {}

    def read(self, path, *, immutable=True):
        path = Path(path).resolve()
        require(path.suffix == '.json', 'report input must be an explicitly selected JSON record')
        if path not in self.cache:
            raw = path.read_bytes()
            self.cache[path] = (json.loads(raw), hashlib.sha256(raw).hexdigest())
        value, sha = self.cache[path]
        if immutable:
            require(value.get('id') == digest({key: row for key, row in value.items() if key != 'id'}),
                    'immutable saved record changed: ' + str(path))
        return value

    def reference(self, path, *, immutable=True):
        path = Path(path).resolve()
        value = self.read(path, immutable=immutable)
        return dict(path=str(path), sha256=self.cache[path][1], **({'id': value['id']} if immutable else {}))

    def read_ref(self, reference, *, expected=None):
        path = Path(reference['path']).resolve()
        require(expected is None or path == Path(expected).resolve(), 'saved report reference escaped its original location')
        value = self.read(path)
        require(self.cache[path][1] == reference['sha256']
                and ('id' not in reference or value['id'] == reference['id']),
                'bound saved JSON bytes or identity changed: ' + str(path))
        return value


def expected_jobs():
    result = {}
    for step in POINTS:
        for stage in (*[f'shard{i:02d}' for i in range(4)], 'virtual_point', 'replay', 'distribution'):
            result[f'step{step}.{stage}'] = ROOT / 'points' / f'step{step:04d}' / stage
        if step != 1490:
            result[f'step{step}.train'] = ROOT / 'points' / f'step{step:04d}' / 'train'
    for key in ('step1192.cal_greedy', 'step1490.cal_greedy', 'step1490.dev_greedy'):
        result[key] = ROOT / 'evaluations/jobs' / key
    return result


def completion_gate(protocol, implementation, closeout, summary):
    require(protocol['id'] == PROTOCOL_ID and implementation['id'] == IMPLEMENTATION_ID
            and closeout['id'] == CLOSEOUT_ID and summary['id'] == FINAL_SUMMARY_ID
            and closeout['protocol_id'] == summary['protocol_id'] == protocol['id'],
            'only the completed, originally registered V70 experiment may be summarized')
    require(closeout['status'] == summary['status'] == 'COMPLETE'
            and closeout['active_workers'] == 0 and closeout['accepted_jobs'] == 26
            and closeout['new_feedback_sessions'] == 2100 and closeout['optimizer_updates'] == 596
            and closeout['new_evaluation_sessions'] == summary['new_evaluation_sessions'] == 1123
            and closeout['applied_Full_updates'] == 2 and closeout['terminal_candidate_probes'] == 1
            and closeout['terminal_candidate_applied'] is summary['terminal_probe_applied'] is False
            and closeout['automatic_followup_started'] is False
            and summary['intermediate_accuracy_used_for_selection'] is False,
            'full fixed dose, unapplied terminal probe and actual completion are required')


def compact_distance(value):
    if value is None:
        return None
    return dict(pick(value, ('all_tasks', 'adjustable', 'adjustable_mu')),
                task_count=len(value['per_task']), adjustable_task_count=len(value['adjustable_tasks']))


def compact_mapping(value):
    """Extract already recorded iteration summaries; do not iterate a map."""
    result = pick(value, ('status', 'numeric_convergence', 'iterations', 'feedback_all_zero',
        'first_step_match', 'certificate', 'reference_is_training_distribution',
        'real_closed_loop_convergence_proved',
        'residual_bound_is_theory_plus_registered_roundoff_not_interval_arithmetic'))
    result.update(R=compact_distance(value['R']), G=compact_distance(value['G']))
    trace = value['trace']
    result['saved_iteration_trace_summary'] = dict(rows=len(trace),
        first=trace[0] if trace else None, last=trace[-1] if trace else None,
        maximum_recorded_per_task_contraction_excess=max(
            (row['maximum_per_task_contraction_excess'] for row in trace
             if row['maximum_per_task_contraction_excess'] is not None), default=None))
    frozen = value.get('frozen_inputs')
    if frozen is not None:
        temperature = frozen['temperature']
        result['saved_smoothing_summary'] = dict(
            parameters=frozen['parameters'], control_task_count=len(frozen['control_tasks']),
            **pick(temperature, ('global_weighted_RMS', 'global_scale_after_floor', 'RMS_floor',
                'empirical_proxy_all_zero', 'information_status', 'noncontrol_total_mu', 'weighting')))
    for key in ('fixed_point_residual_upper_bound', 'distance_to_exact_fixed_point_upper_bound'):
        values = value.get(key)
        result['maximum_' + key] = max(values.values()) if values else None
    return result


def _diagnostics(reader, summary):
    points, tracking = {}, {}
    for step in POINTS:
        reference = summary['frozen_point_diagnostics'][str(step)]
        value = reader.read_ref(reference, expected=ROOT / 'points' / f'step{step:04d}' /
                                'distribution/frozen_diagnostics/record.json')
        require(value['new_model_calls'] == value['new_backward_passes'] == 0
                and value['scientific_distribution_mutated'] is False,
                'saved frozen diagnostics must not mutate the formal training distribution')
        points[str(step)] = dict(source=reference, binding=value['binding'], policy=value['policy'],
            formal=compact_mapping(value['formal']),
            draws={key: compact_mapping(row) for key, row in value['draws'].items()},
            draw_sensitivity=dict(pick(value['draw_sensitivity'], ('status', 'confidence_interval',
                'variance_estimate', 'formal_q_averaged', 'independent_feedback_draws',
                'independence_is_caller_provenance_not_estimated')),
                one_step=compact_distance(value['draw_sensitivity']['one_step']),
                reference=compact_distance(value['draw_sensitivity']['reference'])))
    for previous, current in ((894, 1192), (1192, 1490)):
        key = f'{previous}_{current}'
        reference = summary['target_tracking'][key]
        value = reader.read_ref(reference, expected=ROOT / 'points' / f'step{current:04d}' /
                                'distribution/tracking_diagnostics/record.json')
        require(value['previous_binding'] == points[str(previous)]['binding']
                and value['current_binding'] == points[str(current)]['binding'],
                'saved reference drift must bind the consecutive actual parameter points')
        tracking[key] = dict(source=reference,
            **pick(value, ('status', 'rho', 'relation', 'tracking_metric', 'TV_contraction_claim')),
            D=compact_distance(value['D']),
            tracking=None if value['tracking'] is None else {
                name: row for name, row in value['tracking'].items() if name != 'per_task'})
    return dict(points=points, target_tracking=tracking,
                source_maps_recomputed=False, new_VJP_or_gradient_computations=0)


def _metric_summary(report):
    require(report['denominator'] == len(report['results'])
            and sum(report['metrics']['states'].values()) == report['denominator'],
            'saved native score denominator or known/unknown state counts changed')
    return dict(denominator=report['denominator'], metrics=report['metrics'],
        cumulative_model_calls_in_saved_episodes=sum(row['actual_model_calls'] for row in report['results']),
        generated_tokens_in_saved_episodes=sum(row['generated_token_count'] for row in report['results']),
        tool_calls_in_saved_episodes=sum(row['tool_call_count'] for row in report['results']))


def _evaluation(reader, summary):
    baseline = {}
    for role, reference in summary['baseline']['model_reports'].items():
        report = reader.read_ref(reference)
        require(report['coordinate'] == 'seed137/C1' and report['feedback_batch'] == 1,
                'only the specified old C1/b1 baseline may be reused')
        baseline[role] = dict(source=reference, step=894, **_metric_summary(report))
    reports = {}
    for key, reference in summary['model_reports'].items():
        report = reader.read_ref(reference, expected=ROOT / 'evaluations/jobs' / key / 'native_scores/record.json')
        require(report['status'] == 'COMPLETE' and report['protocol_id'] == PROTOCOL_ID
                and report['job_id'] == key and report['seed'] == 137 and report['arm'] == 'Full'
                and report['baseline_rescored'] is False and report['checkpoint_selection'] is False,
                'fixed endpoint result or baseline separation changed')
        base = baseline[report['role']]
        require(report['baseline'] == base['source'] and report['denominator'] == base['denominator'],
                'endpoint metrics require the same baseline and whole denominator')
        changes = {}
        for name in ('execution_accuracy', 'program_accuracy'):
            new, old = report['metrics'][name], base['metrics'][name]
            require(new['unknown'] == old['unknown'] == 0,
                    'UNKNOWN cannot be silently converted to a complete report')
            net = new['correct'] - old['correct']
            changes[name] = dict(net_correct=net, difference_pp=100 * net / report['denominator'])
        reports[key] = dict(source=reference, step=report['step'], role=report['role'],
            status=report['status'], **_metric_summary(report),
            paired_to_894=report['paired_to_894'], arithmetic_change_from_894=changes)
    require(sum(row['denominator'] for row in reports.values()) == 1123,
            'the three original evaluation jobs must retain all 1123 sessions')
    return dict(baseline=baseline, new_model_reports=reports,
        new_native_scoring_calls=0, old_rescoring_calls=0, new_bootstrap_calls=0,
        counts_from_saved_score_rows_only=True,
        new_episode_model_calls=sum(row['cumulative_model_calls_in_saved_episodes'] for row in reports.values()),
        new_episode_generated_tokens=sum(row['generated_tokens_in_saved_episodes'] for row in reports.values()))


def _resource_summary(value):
    return pick(value, ('all_gates_passed', 'peak_allocated_bytes', 'peak_rss_bytes',
        'minimum_boundary_free_bytes', 'minimum_host_available_bytes', 'resource_wait_seconds',
        'preflight_shortages', 'observed_violation', 'deferred_observation')) | dict(
        cache_protection=pick(value.get('resource_protection', {}), ('status', 'warm_attempted',
            'actual_warm_allocation_bytes', 'cache_release_count', 'cache_retained_wait_count',
            'protection_degraded', 'future_capacity_or_exclusivity_guaranteed', 'receipt')))


def _aggregate_resources(rows):
    result = dict(attempts=len(rows), resource_pass_count=sum(r['all_gates_passed'] is True for r in rows),
        resource_fail_count=sum(r['all_gates_passed'] is False for r in rows))
    for name, reducer in (('peak_allocated_bytes', max), ('peak_rss_bytes', max),
                          ('minimum_boundary_free_bytes', min), ('minimum_host_available_bytes', min)):
        values = [row[name] for row in rows if row.get(name) is not None]
        result[name] = reducer(values) if values else None
    return result


def _operations(reader, closeout, summary):
    barrier = reader.read_ref(summary['all_jobs_exit_barrier'], expected=ROOT / 'all_jobs_exit_barrier/record.json')
    expected, jobs, attempts, resource_groups = expected_jobs(), {}, [], defaultdict(list)
    require(set(barrier['accepted_jobs']) == set(barrier['actual_exits']) == set(expected)
            and barrier['active_workers'] == [], 'all 26 original jobs must have actually exited')
    for key, directory in expected.items():
        accepted = reader.read_ref(barrier['accepted_jobs'][key], expected=directory / 'accepted/record.json')
        result = reader.read_ref(accepted['result'], expected=directory / 'result/record.json')
        actual = reader.read_ref(accepted['actual_exit'])
        require(accepted['protocol_id'] == result['protocol_id'] == actual['protocol_id'] == PROTOCOL_ID
                and accepted['job_id'] == result['job_id'] == actual['job_id'] == key
                and accepted['actual_exit'] == barrier['actual_exits'][key]
                and accepted['result_id'] == result['id'] and result['status'] == 'COMPLETE'
                and accepted['actual_exit_zero'] is accepted['resources_passed'] is True
                and actual['returncode'] == 0 and actual['actual_waitpid_observed'] is True
                and result['resources']['all_gates_passed'] is True,
                'accepted job must retain its actual successful exit and resource proof')
        jobs[key] = dict(accepted=barrier['accepted_jobs'][key], result=accepted['result'],
            actual_exit=accepted['actual_exit'], accepted_attempt=accepted['attempt'],
            **pick(result, ('seed', 'step', 'stage', 'gpu_index', 'initial_step', 'final_step',
                'optimizer_updates', 'new_optimizer_updates', 'outer_updates', 'applied', 'probe_only',
                'new_complete_tasks', 'reused_complete_tasks', 'new_effective_rows',
                'complete_class_tasks', 'complete_class_rows', 'denominator', 'responses',
                'restored_completed_responses', 'total_feedback_sessions', 'new_feedback_sessions',
                'new_actual_response_calls', 'actual_new_response_calls', 'cohort_cumulative_response_calls',
                'new_feedback_sessions_is_logical_condition_total_not_new_attempt',
                'draw_diagnostics_passed', 'draw_C_diagnostics_passed', 'feedback_all_zero',
                'started_epoch', 'finished_epoch', 'final_checkpoint', 'condition_id')))
    for item in closeout['actual_attempts']:
        directory, key = Path(item['directory']), item['job_id']
        require(directory == expected[key] / 'attempts' / f"attempt{item['attempt']:04d}",
                'historical actual attempt directory changed')
        launch = reader.read(directory / 'launch/record.json')
        actual = reader.read(directory / 'actual_exit/record.json')
        resource_path = ROOT / 'resources' / key / f"pid{launch['pid']}" / 'closeout/record.json'
        resource = reader.read(resource_path)
        require(actual['actual_waitpid_observed'] is True
                and (actual['pid'], actual['birth']) == (launch['pid'], launch['birth'])
                and resource['pid'] == launch['pid'] and resource['protocol_id'] == PROTOCOL_ID,
                'attempt exit/resource evidence must retain its launched process identity')
        kind = launch['job']['kind']
        values = _resource_summary(resource['resources'])
        resource_groups[('accepted_' if actual['returncode'] == 0 else 'failed_') + kind].append(values)
        row = dict(job_id=key, attempt=item['attempt'], kind=kind, gpu_index=launch['gpu_index'],
            pid=launch['pid'], birth=launch['birth'], returncode=actual['returncode'],
            launch_epoch=launch['started_epoch'], launch_BJT=bjt(launch['started_epoch']),
            actual_exit_observed_epoch=actual['observed_epoch'], actual_exit_observed_BJT=bjt(actual['observed_epoch']),
            process_wall_seconds=actual['observed_epoch'] - launch['started_epoch'],
            resource_guard_elapsed_seconds=resource['elapsed_slot_seconds'],
            resource_closeout_status=resource['status'], resources=values,
            sources=dict(launch=reader.reference(directory / 'launch/record.json'),
                actual_exit=reader.reference(directory / 'actual_exit/record.json'),
                resource_closeout=reader.reference(resource_path)))
        warm_reference = resource['resources'].get('resource_protection', {}).get('receipt')
        if warm_reference is not None:
            warm = reader.read_ref(warm_reference)
            row['cache_warm'] = dict(source=warm_reference, **pick(warm, ('status',
                'actual_reserved_growth_bytes', 'actual_warm_allocation_bytes', 'requested_warm_bytes',
                'cache_releases_during_warm', 'live_warm_tensor_remaining', 'model_or_rng_call',
                'extra_scientific_response', 'original_peak_stats_not_reset',
                'contiguous_reuse_or_future_free_guaranteed')))
        if actual['returncode'] != 0:
            failure = reader.read(directory / 'failure/record.json')
            decisions = []
            for path in sorted((directory / 'recovery_decisions').glob('decision*/record.json')):
                value = reader.read(path)
                decisions.append(dict(source=reader.reference(path), **pick(value, ('decision', 'automatic_sampling_override')),
                    failure=pick(value.get('failure', {}), ('classification', 'reason', 'unknown_calls')),
                    before=pick(value.get('durable_before', {}), ('progress_units', 'unknown_calls',
                        'resume_allowed', 'durable_progress_digest', 'complete_episodes', 'actual_returned_turns')),
                    after=pick(value.get('durable_after', {}), ('progress_units', 'unknown_calls',
                        'resume_allowed', 'durable_progress_digest', 'complete_episodes', 'actual_returned_turns'))))
            row.update(failure=pick(failure, ('exception_type', 'error', 'exception_chain',
                'CUDA_initialized', 'automatic_retry_in_worker')),
                failure_source=reader.reference(directory / 'failure/record.json'), recovery_decisions=decisions)
        attempts.append(row)
    events = sorted([(row['launch_epoch'], 1) for row in attempts]
                    + [(row['actual_exit_observed_epoch'], -1) for row in attempts])
    current, peak = 0, 0
    for _epoch, change in events:
        current += change
        peak = max(peak, current)
    require(current == 0, 'all actually launched worker attempts must have observed exits')
    for key, job in jobs.items():
        rows = [row for row in attempts if row['job_id'] == key]
        first, last = min(row['launch_epoch'] for row in rows), max(row['actual_exit_observed_epoch'] for row in rows)
        job.update(first_actual_launch_epoch=first, final_actual_exit_epoch=last,
            first_actual_launch_BJT=bjt(first), final_actual_exit_BJT=bjt(last),
            whole_job_span_seconds=last - first, actual_attempts=len(rows))
    point_times = {}
    for step in POINTS:
        rows = [jobs[f'step{step}.shard{i:02d}'] for i in range(4)]
        first, last = min(r['first_actual_launch_epoch'] for r in rows), max(r['final_actual_exit_epoch'] for r in rows)
        point_times[str(step)] = dict(class_first_launch_BJT=bjt(first), class_last_actual_exit_BJT=bjt(last),
            class_wall_span_seconds=last - first, class_shards=4,
            complete_tasks=sum(r['complete_class_tasks'] for r in rows),
            complete_effective_rows=sum(r['complete_class_rows'] for r in rows))
    return dict(jobs=jobs, actual_attempts=attempts, point_class_spans=point_times,
        attempt_returncode_counts=dict(Counter(str(r['returncode']) for r in attempts)),
        observed_maximum_concurrent_worker_processes=peak,
        physical_GPU_indices_used=sorted({row['gpu_index'] for row in attempts}),
        per_phase_resource_aggregates={key: _aggregate_resources(rows) for key, rows in resource_groups.items()},
        summed_process_wall_seconds=sum(r['process_wall_seconds'] for r in attempts),
        summed_process_wall_is_not_GPU_compute_hours=True,
        process_wall_includes_initialization_wait_compute_and_draining=True,
        resource_guard_wall_is_not_entire_process_lifetime=True,
        controller_cumulative_resource_wait_seconds=closeout['resource_wait_seconds'],
        queue_wait_must_not_be_added_again_to_elapsed_experiment_wall=True)


def feedback_counts(roster, rewards):
    require(len(roster) == len(rewards) == 700 and all(type(r) in (int, float) and r in (0, 1) for r in rewards),
            'each feedback point must retain all 700 known frozen binary rewards')
    seeds = (101, 103)
    tasks = {seed: {row['task_id'] for row in roster if row['seed'] == seed} for seed in seeds}
    require(all(sum(row['seed'] == seed for row in roster) == 350 and len(tasks[seed]) == 350 for seed in seeds)
            and tasks[101] == tasks[103], 'the two draws must retain the same 350 unique tasks')
    success = {row['task_id'] for row, reward in zip(roster, rewards, strict=True) if reward == 1}
    return dict(session_denominator=700, unique_task_denominator=350,
        successful_sessions=int(sum(rewards)), distinct_successful_tasks=len(success),
        successful_sessions_by_draw={str(seed): sum(reward == 1 for row, reward in zip(roster, rewards, strict=True)
            if row['seed'] == seed) for seed in seeds}, all_zero_feedback=not any(rewards),
        zero_reward_sessions_retained=True)


def _feedback(reader, operations):
    rows = {}
    for step in POINTS:
        job = operations['jobs'][f'step{step}.virtual_point']
        result = reader.read_ref(job['result'])
        base = ROOT / 'points' / f'step{step:04d}' / 'virtual_point/feedback' / result['condition_id']
        intent = reader.read(base / 'intent/record.json')
        reward = reader.read(base / 'native_rewards/record.json', immutable=False)
        require(intent['id'] == reward['condition_id'] == result['condition_id']
                and intent['temperature'] == 1.0 and intent['denominator'] == 700,
                'frozen rewards must bind this actual point and T1 condition')
        accounting = reader.read_ref(result['actual_response_call_accounting'])
        require(accounting['feedback_condition_id'] == intent['id']
                and accounting['cohort_cumulative_response_calls'] == result['cohort_cumulative_response_calls'],
                'saved feedback call accounting changed')
        rows[str(step)] = dict(**feedback_counts(intent['ordered_episode_roster'], reward['rewards']),
            condition_id=intent['id'], cumulative_complete_cohort_model_calls=result['cohort_cumulative_response_calls'],
            gradient_replay_responses=operations['jobs'][f'step{step}.replay']['responses'],
            sources=dict(intent=reader.reference(base / 'intent/record.json'),
                native_rewards=reader.reference(base / 'native_rewards/record.json', immutable=False),
                call_accounting=result['actual_response_call_accounting']))
    return dict(points=rows, total_feedback_sessions=2100,
        total_complete_cohort_model_calls=sum(row['cumulative_complete_cohort_model_calls'] for row in rows.values()),
        total_gradient_replay_responses=sum(row['gradient_replay_responses'] for row in rows.values()),
        native_rewards_rescored=False, feedback_tokens_not_rescanned_or_inferred=True,
        successful_feedback_sessions_are_not_replay_responses=True)


def build_report():
    reader = Reader()
    protocol = reader.read(ROOT / 'protocol/record.json')
    implementation = reader.read(ROOT / 'implementation/record.json')
    closeout = reader.read(ROOT / 'closeout/record.json')
    summary = reader.read(ROOT / 'evaluations/final_summary/record.json')
    completion_gate(protocol, implementation, closeout, summary)
    supervisor = reader.read(ROOT / 'supervisor/closeout/record.json')
    supervisor_launch = reader.read(ROOT / 'supervisor/launch/record.json')
    controller_exit = reader.read(ROOT / 'supervisor/attempts/attempt0001/actual_exit/record.json')
    cpu_accepted = reader.read(ROOT / 'final_analysis/accepted/record.json')
    cpu_result = reader.read_ref(cpu_accepted['result'])
    cpu_exit = reader.read_ref(cpu_accepted['actual_exit'])
    cpu_resources = reader.read_ref(cpu_accepted['resources'])
    require(supervisor['status'] == 'COMPLETE' and controller_exit['returncode'] == 0
            and controller_exit['actual_waitpid_observed'] is True
            and cpu_exit['returncode'] == 0 and cpu_exit['actual_waitpid_observed'] is True
            and cpu_result['analysis'] == summary and cpu_result['status'] == cpu_resources['status'] == 'COMPLETE'
            and cpu_resources['all_gates_passed'] is True and cpu_resources['CUDA_initialized'] is False
            and cpu_resources['failures'] == cpu_resources['received_signals'] == [],
            'actual successful control and final CPU exits are required, not stale queue status')
    require(not (ROOT / 'training/step1490_outer').exists(), 'the terminal candidate must not have been applied')
    operations = _operations(reader, closeout, summary)
    observations = cpu_resources['observations']
    operations['final_CPU_analysis'] = dict(accepted=reader.reference(ROOT / 'final_analysis/accepted/record.json'),
        result=cpu_accepted['result'], actual_exit=cpu_accepted['actual_exit'], resources=cpu_accepted['resources'],
        started_BJT=bjt(cpu_resources['started_epoch']), finished_BJT=bjt(cpu_resources['finished_epoch']),
        wall_seconds=cpu_resources['finished_epoch'] - cpu_resources['started_epoch'],
        peak_rss_bytes=max(row['process']['peak_rss_bytes'] for row in observations),
        minimum_host_available_bytes=min(row['host']['available_bytes'] for row in observations),
        all_gates_passed=True, CUDA_initialized=False, actual_exit_zero=True)
    operations['experiment_timeline'] = dict(started_BJT=bjt(supervisor_launch['started_epoch']),
        scientific_closeout_BJT=bjt(closeout['finished_epoch']), supervisor_closeout_BJT=bjt(supervisor['finished_epoch']),
        wall_to_scientific_closeout_seconds=closeout['finished_epoch'] - supervisor_launch['started_epoch'],
        wall_to_supervisor_closeout_seconds=supervisor['finished_epoch'] - supervisor_launch['started_epoch'],
        supervisor_launch=reader.reference(ROOT / 'supervisor/launch/record.json'),
        supervisor_closeout=reader.reference(ROOT / 'supervisor/closeout/record.json'),
        controller_actual_exit=reader.reference(ROOT / 'supervisor/attempts/attempt0001/actual_exit/record.json'))
    body = dict(schema='v70_saved_evidence_final_report_summary_20261024.v1', status='READ_ONLY_REPORT_SUMMARY_COMPLETE',
        protocol_id=PROTOCOL_ID, scientific_experiment_status='COMPLETE',
        source_refs=dict(protocol=reader.reference(ROOT / 'protocol/record.json'),
            implementation=reader.reference(ROOT / 'implementation/record.json'),
            closeout=reader.reference(ROOT / 'closeout/record.json'),
            final_summary=reader.reference(ROOT / 'evaluations/final_summary/record.json')),
        scientific_contract=protocol['scientific_contract'], source_commit=implementation['source_commit'],
        initial_parent=protocol['initial_parent'], evaluation=_evaluation(reader, summary),
        frozen_diagnostics=_diagnostics(reader, summary), feedback=_feedback(reader, operations), operations=operations,
        analysis_script=dict(path=str(Path(__file__).resolve()), sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        new_native_scores=0, new_old_baseline_scores=0, new_model_or_GPU_or_API_calls=0,
        new_frozen_map_iterations=0, new_VJPs=0, new_optimizer_updates=0,
        private_references_or_original_episodes_or_Tensors_opened=False,
        historical_scientific_records_written=False, old_failures_reclassified=False,
        complete_training_checkpoint_tree_or_class_cache_rescanned=False,
        independent_parent_count=1, parallel_control_paths=0, causal_Full_or_Novelty_benefit_identified=False,
        new_significance_tests_or_confidence_intervals=False, online_convergence_proved=False,
        endpoint_selection_changed=False, automatic_followup_authorized=False)
    return dict(body, id=digest(body))


def _publish_exact(path, value, raw):
    require(not path.is_symlink(), 'derived report cannot overwrite a symlink')
    if path.exists():
        require(path.read_bytes() == raw, 'existing derived report is immutable')
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.v70-report-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def publish_report(value, output_root=OUTPUT_ROOT, *, published_summary=None):
    require(Path(output_root).resolve() == OUTPUT_ROOT.resolve() and not Path(output_root).is_symlink(),
            'report publication is restricted to the independent report_analysis_01 directory')
    require(value.get('id') == digest({k: v for k, v in value.items() if k != 'id'}),
            'derived report changed before publication')
    if published_summary is not None:
        require(Path(published_summary).resolve() == PUBLISHED_SUMMARY.resolve(),
                'published mirror must retain its exact report_data destination')
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    reference = _publish_exact(Path(output_root) / 'record.json', value, raw)
    if published_summary is not None:
        mirror = _publish_exact(Path(published_summary), value, raw)
        require(reference['sha256'] == mirror['sha256'], 'report mirror must be byte-identical')
    return reference


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_ROOT)
    parser.add_argument('--published-summary', type=Path)
    parser.add_argument('--no-write', action='store_true')
    args = parser.parse_args(argv)
    require(args.output_root.resolve() == OUTPUT_ROOT.resolve(), 'foreign derived output directory')
    value = build_report()
    reference = None if args.no_write else publish_report(value, args.output_root, published_summary=args.published_summary)
    print(json.dumps(dict(id=value['id'], status=value['status'], output=reference,
        new_scientific_operations=0, original_scientific_records_written=0), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
