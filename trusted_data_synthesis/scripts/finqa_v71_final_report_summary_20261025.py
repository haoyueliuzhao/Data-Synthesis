"""Extract the complete V71 report from immutable, already computed JSON only.

No scientific runtime, model, Tensor, native scorer, original Episode, private
reference, distribution-map routine, VJP, bootstrap or optimizer is imported.
Each explicitly selected JSON input is read once and retained in a local cache.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
PREPARATION_ROOT = V18 / 'v71_fixed_distribution_control_01'
ROOT = PREPARATION_ROOT / 'execution_revision_01'
OUTPUT_ROOT = ROOT / 'report_analysis_01'
PUBLISHED_SUMMARY = REPO / 'trusted_data_synthesis/docs/report_data/finqa_v71_report_summary_20261025.json'
PROTOCOL_ID = '1b69496f9fe3a1617eab1d6a34739c60305c63d00229924c0edbdb507b9d6d80'
IMPLEMENTATION_ID = 'ae5ea266872c9f269ad39c2adeb8f2566fa922adfa0f5f82bb3bd20f47a00244'
CLOSEOUT_ID = '712a98f7c929c72f880d12f2167644ec8ab89984d30507899fefb0512a86e5d1'
FINAL_SUMMARY_ID = '26b12679b173af15687613ac3454f3b0b48438484adeb1cfd4001cdc8a59ffe4'
GIB = 1024 ** 3
BJT = timezone(timedelta(hours=8))
PANELS = ('step1192.cal_greedy', 'step1490.cal_greedy', 'step1490.dev_greedy')
STATES = ('I', 'W', 'R', 'UNKNOWN')


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


def without(value, names):
    return {name: row for name, row in value.items() if name not in names}


class Reader:
    """Only selected JSON records; Tensor and original Episode refs are not followed."""

    def __init__(self):
        self.cache = {}

    def read(self, path, *, immutable=True):
        path = Path(path).resolve()
        require(path.suffix == '.json', 'report input must be explicitly selected JSON')
        if path not in self.cache:
            raw = path.read_bytes()
            self.cache[path] = (json.loads(raw), hashlib.sha256(raw).hexdigest())
        value, _sha = self.cache[path]
        if immutable:
            require(value.get('id') == digest(without(value, ('id',))),
                    'immutable saved JSON changed: ' + str(path))
        return value

    def reference(self, path, *, immutable=True):
        path = Path(path).resolve()
        value = self.read(path, immutable=immutable)
        return dict(path=str(path), sha256=self.cache[path][1],
                    **({'id': value['id']} if immutable else {}))

    def read_ref(self, reference, *, expected=None):
        path = Path(reference['path']).resolve()
        require(expected is None or path == Path(expected).resolve(),
                'saved JSON reference escaped its registered location')
        value = self.read(path)
        require(self.cache[path][1] == reference['sha256']
                and ('id' not in reference or value['id'] == reference['id']),
                'bound saved JSON bytes or identity changed: ' + str(path))
        return value

    def sources(self):
        return [dict(path=str(path), sha256=sha, **({'id': value['id']} if 'id' in value else {}))
                for path, (value, sha) in sorted(self.cache.items())]


def expected_jobs():
    return {**{f'step{step}.train': ROOT / 'points' / f'step{step:04d}' / 'train'
               for step in (894, 1192)},
            **{key: ROOT / 'evaluations/jobs' / key for key in PANELS}}


def completion_gate(protocol, implementation, closeout, summary):
    require(protocol['id'] == PROTOCOL_ID and implementation['id'] == IMPLEMENTATION_ID
            and closeout['id'] == CLOSEOUT_ID and summary['id'] == FINAL_SUMMARY_ID
            and closeout['protocol_id'] == summary['protocol_id'] == protocol['id'],
            'only the registered complete V71 control may be summarized')
    require(closeout['status'] == summary['status'] == 'COMPLETE'
            and closeout['active_workers'] == 0 and closeout['accepted_jobs'] == 5
            and closeout['optimizer_updates'] == summary['optimizer_updates'] == 596
            and closeout['task_exposures'] == summary['task_exposures'] == 2976
            and closeout['new_evaluation_sessions'] == summary['new_evaluation_sessions'] == 1123
            and closeout['new_feedback_sessions'] == closeout['applied_Full_updates']
                == closeout['terminal_candidate_probes'] == 0
            and all(summary[name] == 0 for name in ('new_outer_updates', 'feedback_sessions',
                'class_passes', 'replay_responses', 'VJP'))
            and closeout['terminal_candidate_applied'] is False
            and closeout['automatic_followup_started'] is summary['automatic_followup'] is False
            and summary['dev1192_evaluated'] is summary['baseline_rescored'] is summary['Full_rescored'] is False,
            'complete fixed 596/2976/1123 dose and zero new outer/scientific feedback are required')


def metric_summary(report):
    count = report['denominator']
    require(count == len(report['results']) and sum(report['metrics']['states'].values()) == count,
            'saved whole native denominator changed')
    require(report['metrics']['states']['UNKNOWN'] == 0, 'UNKNOWN cannot be imputed as a complete score')
    for name in ('execution_accuracy', 'program_accuracy'):
        metric = report['metrics'][name]
        require(metric['denominator'] == metric['scored'] == count and metric['unknown'] == 0
                and math.isclose(metric['complete_dataset_mean'], metric['correct'] / count, abs_tol=1e-15),
                'saved native accuracy numerator or full denominator changed')
    return dict(denominator=count, metrics=report['metrics'],
        actual_model_calls=sum(row['actual_model_calls'] for row in report['results']),
        generated_tokens=sum(row['generated_token_count'] for row in report['results']),
        tool_calls=sum(row['tool_call_count'] for row in report['results']))


def delta(candidate, reference, denominator):
    count = candidate - reference
    return dict(numerator=count, denominator=denominator,
                difference=count / denominator, difference_pp=100 * count / denominator)


def validate_paired(pair, candidate, reference, denominator):
    """Check saved transition orientation and exact counts; never rescore a row."""
    transitions = pair['transitions']
    require(pair['status'] == 'COMPLETE' and pair['denominator'] == denominator
            and pair['unknown_pair_count'] == 0 and sum(transitions.values()) == denominator,
            'paired complete denominator changed')
    require(set(transitions) == {left + '->' + right for left in STATES for right in STATES},
            'complete I/W/R/UNKNOWN transition matrix required')
    for state in STATES:
        require(sum(transitions[state + '->' + right] for right in STATES) == reference['states'][state]
                and sum(transitions[left + '->' + state] for left in STATES) == candidate['states'][state],
                'paired orientation must be reference rows to candidate columns')
    gained = transitions['I->R'] + transitions['W->R']
    lost = transitions['R->I'] + transitions['R->W']
    net = candidate['execution_accuracy']['correct'] - reference['execution_accuracy']['correct']
    require(pair['new_correct'] == gained and pair['lost_correct'] == lost
            and pair['net_correct'] == pair['numerator'] == gained - lost == net,
            'paired new/lost counts must retain the same full-denominator net effect')
    parts = pair['decomposition']
    require(parts['invalid_correct_net_count'] == transitions['I->R'] - transitions['R->I']
            and parts['wrong_correct_net_count'] == transitions['W->R'] - transitions['R->W']
            and parts['invalid_correct_net_count'] + parts['wrong_correct_net_count'] == net
            and math.isclose(pair['difference'], net / denominator, abs_tol=1e-15),
            'saved state decomposition must equal the whole-panel net difference')


def evaluation_summary(reader, summary):
    baseline, full, fixed, source_reports = {}, {}, {}, {}
    for role, reference in summary['baseline']['model_reports'].items():
        value = reader.read_ref(reference)
        require(value['coordinate'] == 'seed137/C1' and value['feedback_batch'] == 1,
                'only the common C1/b1/894 baseline may be reused')
        baseline[role] = dict(source=reference, step=894, **metric_summary(value))
        source_reports['baseline_' + role] = value
    for key in PANELS:
        for label, references, target in (('Fixed894', summary['model_reports'], fixed),
                ('Full', summary['Full']['model_reports'], full)):
            reference = references[key]
            value = reader.read_ref(reference)
            require(value['status'] == 'COMPLETE' and value['job_id'] == key
                    and value['seed'] == 137 and value['arm'] == label
                    and value['baseline_rescored'] is value['checkpoint_selection'] is False,
                    'fixed preselected endpoint and read-only baseline required')
            if label == 'Fixed894':
                require(value['protocol_id'] == PROTOCOL_ID
                        and Path(reference['path']) == ROOT / 'evaluations/jobs' / key / 'native_scores/record.json',
                        'new control report belongs to another protocol or job')
            target[key] = dict(source=reference, step=value['step'], role=value['role'],
                **metric_summary(value))
            source_reports[label + '_' + key] = value
    comparisons = summary['comparisons']
    for key in PANELS:
        comp, current = comparisons[key], fixed[key]
        role, denominator = current['role'], current['denominator']
        reports = {'Fixed894': source_reports['Fixed894_' + key],
                   'Full': source_reports['Full_' + key], 'baseline894': source_reports['baseline_' + role]}
        order = [row['task_key'] for row in reports['Fixed894']['results']]
        require(all([row['task_key'] for row in row['results']] == order for row in reports.values())
                and all(comp['native_metrics'][name] == row['metrics'] for name, row in reports.items()),
                'paired reports must use exactly the same ordered tasks and saved scores')
        for label, left, right in (('Full_minus_Fixed894', 'Full', 'Fixed894'),
                ('Fixed894_minus_baseline894', 'Fixed894', 'baseline894'),
                ('Full_minus_baseline894', 'Full', 'baseline894')):
            validate_paired(comp['paired_execution'][label], reports[left]['metrics'], reports[right]['metrics'], denominator)
            pa = delta(reports[left]['metrics']['program_accuracy']['correct'],
                       reports[right]['metrics']['program_accuracy']['correct'], denominator)
            require(comp['paired_program_accuracy'][label] == pa, 'saved paired PA arithmetic changed')
    primary = summary['primary_estimands']
    H = fixed['step1490.dev_greedy']['metrics']['execution_accuracy']['correct']
    require(primary['Fixed894_correct'] == H and primary['Full_correct'] == 371
            and primary['baseline894_correct'] == 525
            and primary['delta_adaptive']['numerator'] == 371 - H
            and primary['delta_fixed']['numerator'] == H - 525,
            'both preregistered primary quantities must retain the same fixed endpoint')
    cal_changes = {}
    for label, values in (('Full', full), ('Fixed894', fixed)):
        cal_changes[label] = {name: delta(values['step1490.cal_greedy']['metrics'][name]['correct'],
            values['step1192.cal_greedy']['metrics'][name]['correct'], 120)
            for name in ('execution_accuracy', 'program_accuracy')}
    require(sum(row['denominator'] for row in fixed.values()) == 1123, 'new evaluation dose changed')
    return dict(baseline=baseline, Full=full, Fixed894=fixed, comparisons=comparisons,
        primary_estimands=primary, calibration1192_to1490=cal_changes,
        calibration_window_change_is_not_independent_second_outer_effect=True,
        fixed_generation_totals={name: sum(row[name] for row in fixed.values())
            for name in ('actual_model_calls', 'generated_tokens', 'tool_calls')},
        reused_Full_generation_totals={name: sum(row[name] for row in full.values())
            for name in ('actual_model_calls', 'generated_tokens', 'tool_calls')},
        rescore_calls=0, new_significance_tests=0, new_bootstrap_calls=0,
        metrics_from_saved_complete_native_rows_only=True)


def resource_summary(value):
    return dict(pick(value, ('all_gates_passed', 'peak_allocated_bytes', 'peak_rss_bytes',
        'minimum_boundary_free_bytes', 'minimum_host_available_bytes', 'resource_wait_seconds',
        'preflight_shortages', 'observed_violation', 'deferred_observation',
        'single_process_lifetime_includes_loading', 'peak_resets_after_loading', 'received_signals')),
        cache_protection=pick(value.get('resource_protection', {}), ('status', 'warm_attempted',
            'actual_warm_allocation_bytes', 'cache_release_count', 'cache_retained_wait_count', 'protection_degraded')))


def aggregate_resources(rows):
    out = dict(attempts=len(rows), resource_pass_count=sum(row['all_gates_passed'] is True for row in rows),
        resource_fail_count=sum(row['all_gates_passed'] is False for row in rows),
        worker_resource_wait_seconds=sum(row['resource_wait_seconds'] for row in rows),
        preflight_shortages=sum(row['preflight_shortages'] for row in rows))
    for name, reducer in (('peak_allocated_bytes', max), ('peak_rss_bytes', max),
            ('minimum_boundary_free_bytes', min), ('minimum_host_available_bytes', min)):
        out[name] = reducer(row[name] for row in rows)
    return out


def execution_summary(reader, closeout, summary):
    barrier = reader.read_ref(summary['all_jobs_exit_barrier'], expected=ROOT / 'all_jobs_exit_barrier/record.json')
    expected, jobs, attempts, groups = expected_jobs(), {}, [], defaultdict(list)
    require(set(barrier['accepted_jobs']) == set(barrier['actual_exits']) == set(expected)
            and barrier['active_workers'] == [], 'all five fixed jobs require accepted actual exits')
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
                'actual successful exits and full-lifetime resource results are required')
        jobs[key] = dict(accepted=barrier['accepted_jobs'][key], result=accepted['result'],
            actual_exit=accepted['actual_exit'], accepted_attempt=accepted['attempt'],
            **pick(result, ('seed', 'step', 'stage', 'gpu_index', 'initial_step', 'final_step',
                'optimizer_updates', 'new_optimizer_updates', 'outer_updates', 'applied',
                'fixed_distribution', 'fixed_distribution_digest', 'new_feedback_sessions',
                'new_class_passes', 'new_response_replay', 'new_VJP', 'sessions',
                'started_epoch', 'finished_epoch', 'final_checkpoint')))
    for item in closeout['actual_attempts']:
        directory, key = Path(item['directory']), item['job_id']
        require(directory == expected[key] / 'attempts' / f"attempt{item['attempt']:04d}",
                'actual attempt escaped its registered fixed job')
        launch = reader.read(directory / 'launch/record.json')
        actual = reader.read(directory / 'actual_exit/record.json')
        path = ROOT / 'resources' / key / f"pid{launch['pid']}" / 'closeout/record.json'
        resource = reader.read(path)
        require(actual['actual_waitpid_observed'] is True
                and (actual['pid'], actual['birth']) == (launch['pid'], launch['birth'])
                and resource['pid'] == launch['pid'] and resource['protocol_id'] == PROTOCOL_ID,
                'actual process identity must bind the observed exit and resource closeout')
        values = resource_summary(resource['resources'])
        groups[launch['job']['kind']].append(values)
        attempts.append(dict(job_id=key, attempt=item['attempt'], kind=launch['job']['kind'],
            gpu_index=launch['gpu_index'], pid=launch['pid'], birth=launch['birth'],
            returncode=actual['returncode'], actual_waitpid_observed=True,
            launch_epoch=launch['started_epoch'], launch_BJT=bjt(launch['started_epoch']),
            actual_exit_observed_epoch=actual['observed_epoch'], actual_exit_observed_BJT=bjt(actual['observed_epoch']),
            process_wall_seconds=actual['observed_epoch'] - launch['started_epoch'],
            resource_guard_elapsed_seconds=resource['elapsed_slot_seconds'],
            resource_closeout_status=resource['status'], resources=values,
            sources=dict(launch=reader.reference(directory / 'launch/record.json'),
                actual_exit=reader.reference(directory / 'actual_exit/record.json'),
                resource_closeout=reader.reference(path))))
    require(len(attempts) == 5 and all(row['attempt'] == 1 and row['returncode'] == 0 for row in attempts),
            'this final report describes five actual first-attempt successes')
    events = sorted([(row['launch_epoch'], 1) for row in attempts]
                    + [(row['actual_exit_observed_epoch'], -1) for row in attempts])
    current, peak = 0, 0
    for _, change in events:
        current += change
        peak = max(peak, current)
    require(current == 0, 'all actually launched GPU worker attempts must have observed exits')
    for key, value in jobs.items():
        row = next(row for row in attempts if row['job_id'] == key)
        value.update(pick(row, ('launch_BJT', 'actual_exit_observed_BJT', 'process_wall_seconds')))
    supervisor = reader.read(ROOT / 'supervisor/closeout/record.json')
    supervisor_launch = reader.read(ROOT / 'supervisor/launch/record.json')
    controller_launch = reader.read(ROOT / 'controllers/attempt0001/launch/record.json')
    controller_exit = reader.read(ROOT / 'supervisor/attempts/attempt0001/actual_exit/record.json')
    cpu = reader.read(ROOT / 'final_analysis/accepted/record.json')
    cpu_result, cpu_exit, cpu_resource = (reader.read_ref(cpu[key]) for key in ('result', 'actual_exit', 'resources'))
    cpu_launch = reader.read(ROOT / 'final_analysis/attempt0001/launch/record.json')
    require(supervisor['status'] == 'COMPLETE' and supervisor['controller_attempts'] == 1
            and controller_exit['returncode'] == 0 and controller_exit['actual_waitpid_observed'] is True
            and (controller_exit['pid'], controller_exit['birth']) == (controller_launch['pid'], controller_launch['birth'])
            and cpu_exit['returncode'] == 0 and cpu_exit['actual_waitpid_observed'] is True
            and (cpu_exit['pid'], cpu_exit['birth']) == (cpu_launch['pid'], cpu_launch['birth'])
            and cpu_result['analysis'] == summary
            and cpu_result['status'] == cpu_resource['status'] == 'COMPLETE'
            and cpu_resource['all_gates_passed'] is True and cpu_resource['CUDA_initialized'] is False
            and cpu_resource['failures'] == cpu_resource['received_signals'] == [],
            'final CPU and controller actual exit zero required, not a stale RUNNING snapshot')
    observations = cpu_resource['observations']
    return dict(jobs=jobs, actual_attempts=attempts,
        attempt_returncode_counts=dict(Counter(str(row['returncode']) for row in attempts)),
        actual_maximum_concurrent_GPU_workers=peak, registered_GPU_worker_limit=6,
        physical_GPU_indices_used=sorted({row['gpu_index'] for row in attempts}),
        per_kind_resources={key: aggregate_resources(rows) for key, rows in groups.items()},
        all_GPU_worker_resources=aggregate_resources([row['resources'] for row in attempts]),
        summed_process_wall_seconds=sum(row['process_wall_seconds'] for row in attempts),
        summed_training_process_wall_seconds=sum(row['process_wall_seconds'] for row in attempts if row['kind'] == 'train'),
        process_wall_includes_initialization_wait_compute_and_draining=True,
        summed_process_wall_is_not_GPU_compute_hours=True,
        controller_resource_wait_seconds=closeout['resource_wait_seconds'],
        worker_resource_wait_different_from_controller_queue_wait=True,
        resource_wait_already_within_elapsed_wall_do_not_add_twice=True,
        final_CPU_analysis=dict(accepted=reader.reference(ROOT / 'final_analysis/accepted/record.json'),
            result=cpu['result'], actual_exit=cpu['actual_exit'], resources=cpu['resources'],
            started_BJT=bjt(cpu_resource['started_epoch']), finished_BJT=bjt(cpu_resource['finished_epoch']),
            wall_seconds=cpu_resource['finished_epoch'] - cpu_resource['started_epoch'],
            peak_rss_bytes=max(row['process']['peak_rss_bytes'] for row in observations),
            minimum_host_available_bytes=min(row['host']['available_bytes'] for row in observations),
            observations=len(observations), all_gates_passed=True, CUDA_initialized=False, actual_exit_zero=True),
        experiment_timeline=dict(started_BJT=bjt(supervisor_launch['started_epoch']),
            scientific_closeout_BJT=bjt(closeout['finished_epoch']), supervisor_closeout_BJT=bjt(supervisor['finished_epoch']),
            wall_to_scientific_closeout_seconds=closeout['finished_epoch'] - supervisor_launch['started_epoch'],
            wall_to_supervisor_closeout_seconds=supervisor['finished_epoch'] - supervisor_launch['started_epoch'],
            supervisor_launch=reader.reference(ROOT / 'supervisor/launch/record.json'),
            supervisor_closeout=reader.reference(ROOT / 'supervisor/closeout/record.json'),
            controller_actual_exit=reader.reference(ROOT / 'supervisor/attempts/attempt0001/actual_exit/record.json'),
            supervisor_self_closeout_is_not_own_waitpid_exitcode=True,
            supervisor_own_waitpid_exitcode=None))


def training_summary(reader, protocol):
    contexts, windows = {}, {}
    for start in (894, 1192):
        directory = ROOT / 'points' / f'step{start:04d}'
        context = reader.read(directory / 'context/record.json')
        completed = reader.read(directory / 'train/completed/record.json')
        binding_record = reader.read_ref(completed['training_binding'])
        require(context['protocol_id'] == completed['protocol_id'] == PROTOCOL_ID
                and context['automatic_outer_disabled'] is True
                and context['outer_done'] == completed['outer_done'] == [298]
                and completed['checkpoint_arm'] == 'C-only' and completed['condition'] == 'fixed_pi894'
                and completed['fixed_distribution'] is True and completed['outer_updates'] == 0
                and completed['optimizer_updates'] == completed['new_optimizer_updates'] == 298
                and completed['task_exposures'] == 1488 and completed['next_outer_automatically_executed'] is False
                and completed['initial_step'] == start and completed['final_step'] == start + 298,
                'accepted training must retain its exact fixed pi, no outer, and original inner dose')
        receipts, batches = completed['update_receipts'], context['window_task_batches']
        require([row['step'] for row in receipts] == list(range(start + 1, start + 299))
                and len(batches) == 298 and sum(len(row['task_ids']) for row in batches) == 1488
                and Counter(len(row['task_ids']) for row in batches) == {4: 2, 5: 296},
                'saved completion receipt sequence and original four-task tails changed')
        require(completed['distribution_digest'] == completed['fixed_distribution_digest']
                == context['fixed_pi_digest'] == protocol['initial_parent']['distribution_digest'],
                'native state tree digest must retain exact pi0 across both training windows')
        contexts[str(start)] = context
        windows[str(start)] = dict(context=reader.reference(directory / 'context/record.json'),
            completed=reader.reference(directory / 'train/completed/record.json'),
            training_binding=completed['training_binding'], binding_contract=binding_record,
            **pick(completed, ('initial_step', 'final_step', 'optimizer_updates', 'new_optimizer_updates',
                'task_exposures', 'outer_updates', 'outer_done', 'fixed_distribution', 'fixed_distribution_digest',
                'initial_checkpoint', 'final_checkpoint', 'updates_in_final_worker')),
            original_schedule_sha256=context['original_schedule_sha256'],
            receipt_count=len(receipts), first_receipt=receipts[0], last_receipt=receipts[-1],
            actual_batch_size_counts={'4': 2, '5': 296}, receipt_Tensors_or_full_tree_reopened=False)
    require(contexts['894']['parent_checkpoint'] == protocol['initial_parent']['checkpoint']
            and contexts['1192']['parent_checkpoint'] == windows['894']['final_checkpoint']
            and contexts['894']['fixed_pi'] == contexts['1192']['fixed_pi']
            and contexts['894']['fixed_component_digests'] == contexts['1192']['fixed_component_digests']
            and contexts['894']['original_schedule_sha256'] == contexts['1192']['original_schedule_sha256'],
            'second fixed window must inherit the first actual endpoint and unchanged fixed components')
    return dict(windows=windows, initial_parent=protocol['initial_parent'],
        native_distribution_tree_digest=contexts['894']['fixed_pi_digest'],
        actual_fixed_components=contexts['894']['fixed_component_digests'],
        total_optimizer_updates=596, total_task_exposures=2976, new_outer_updates=0,
        original_outer_done=[298], original_execution_plan_not_fabricated=True,
        exact_pi_preservation_verified_by_original_execution=True,
        this_report_reloads_model_Adam_RNG_Tensors=False), contexts['894']


def compact_support(value):
    return without(value, ('per_task',))


def compact_direction(value):
    return dict(without(value, ('actual_direction_support', 'draw_candidate_support')),
        actual_direction_support={key: compact_support(row) for key, row in value['actual_direction_support'].items()},
        draw_candidate_support={key: {evaluator: compact_support(row) for evaluator, row in candidate.items()}
                                for key, candidate in value['draw_candidate_support'].items()})


def compact_dynamics(value):
    steps = value['steps']
    require(len(steps) == 298, 'saved dynamics must describe one complete 298-step window')
    return dict(without(value, ('steps',)), first_step=steps[0]['step'], last_step=steps[-1]['step'],
        saved_steps=len(steps), batch_size_counts=dict(Counter(str(row['batch_size']) for row in steps)),
        summed_actual_sequence_tokens=sum(row['sequence_tokens'] for row in steps),
        summed_actual_target_tokens=sum(row['target_tokens'] for row in steps),
        new_forward_or_backward_for_this_summary=False)


def compact_movement(value):
    return dict(without(value, ('states', 'tasks', 'top20_gaining_states', 'top20_losing_states')),
        task_count=len(value['tasks']), state_count=len(value['states']),
        top5_gaining_states=value['top20_gaining_states'][:5],
        top5_losing_states=value['top20_losing_states'][:5],
        full_per_state_and_top20_tables_retained_in_source=True)


def compact_nominal(value):
    return dict(without(value, ('Full', 'fixed_pi0')),
        Full=without(value['Full'], ('package_coefficients', 'state_coefficients', 'task_coefficients')),
        fixed_pi0=without(value['fixed_pi0'], ('package_coefficients', 'state_coefficients', 'task_coefficients')),
        original_per_package_state_task_coefficients_retained_in_source=True)


def invalid_detail_counts(rows):
    """Summarize already assigned explanatory labels, without parsing raw text."""
    return dict(invalid_count=len(rows), terminal_counts=dict(Counter(row['terminal_category'] for row in rows)),
        terminal_by_stop_reason={category: dict(Counter(row['stop_reason'] for row in rows
            if row['terminal_category'] == category)) for category in sorted({row['terminal_category'] for row in rows})},
        native_reasons=dict(Counter(row['native_reason'] for row in rows)))


def mechanism_summary(reader, summary, initial_context):
    existing = reader.read_ref(summary['existing_distribution_and_supervision'],
        expected=ROOT / 'existing_mechanism_analysis/record.json')
    dynamics = reader.read_ref(summary['fixed_training_dynamics'],
        expected=ROOT / 'mechanism_analysis/fixed_training_dynamics/record.json')
    invalid = reader.read_ref(summary['failure_mechanisms'],
        expected=ROOT / 'mechanism_analysis/paired_invalid/record.json')
    old_invalid = reader.read_ref(invalid['existing_Full'])
    observations = reader.read_ref(invalid['example_reading_observations'])
    require(existing['status'] == 'COMPLETE_EXISTING_PRODUCT_ANALYSIS'
            and not any(existing['scientific_operations'].values()) and existing['original_artifacts_written'] == 0
            and existing['distributions']['pi0'] == initial_context['fixed_pi']
            and existing['actual_pi0_digest'] == digest(existing['distributions']['pi0'])
            and dynamics['protocol_id'] == PROTOCOL_ID and dynamics['new_model_computation'] is False
            and invalid['native_scores_unchanged'] is True
            and invalid['new_model_calls'] == invalid['new_scoring_calls'] == 0
            and observations['pair_count'] == 24 and observations['episode_count'] == 48
            and observations['reading_selection_changed'] is observations['native_score_repair_or_rescore'] is False,
            'saved explanation must retain exact pi0, fixed examples and original native scores')
    summary_keys = ('invalid_count', 'terminal_counts', 'first_failure_counts', 'source_transition_counts', 'terminal_by_source')
    require(invalid['Full_summary'] == pick(old_invalid, summary_keys)
            and invalid['fixed_summary']['invalid_count'] == len(invalid['fixed_rows']) == 317
            and old_invalid['invalid_count'] == len(old_invalid['rows']) == 325,
            'paired full-population explanatory classifications changed')
    decompositions = {}
    for point, value in existing['applied_log_odds_decomposition'].items():
        rows = value['rows']
        decompositions[point] = dict(without(value, ('rows',)), row_count=len(rows),
            top5_absolute_recorded_log_odds_changes=sorted(rows,
                key=lambda row: (-abs(row['observed_log_odds_change']), row['task_id'], row['state_id']))[:5])
    return dict(existing_source=summary['existing_distribution_and_supervision'],
        fixed_dynamics_source=summary['fixed_training_dynamics'], invalid_source=summary['failure_mechanisms'],
        actual_parent_state_digest=existing['actual_parent_state_digest'], pi0_definition=existing['pi0_definition'],
        pi0_digest_representations=dict(canonical_JSON_sha256=existing['actual_pi0_digest'],
            native_checkpoint_tree_digest=initial_context['fixed_pi_digest'],
            different_serialization_algorithms=True, distribution_values_equal=True),
        movement={key: compact_movement(value) for key, value in existing['movement'].items()},
        original_package_feature_count=len(existing['package_features']),
        nominal_supervision_by_window={key: compact_nominal(value)
            for key, value in existing['nominal_supervision_by_window'].items()},
        applied_direction_diagnostics={key: compact_direction(value)
            for key, value in existing['applied_direction_diagnostics'].items()},
        applied_log_odds_decomposition=decompositions,
        saved_training_dynamics=dict(Full={key: compact_dynamics(value)
                for key, value in existing['existing_Full_training_dynamics'].items()},
            Fixed894={key: compact_dynamics(value) for key, value in dynamics['windows'].items()},
            layerwise_actual_loss_or_gradient_attribution_available=False),
        invalid=dict(Full=invalid['Full_summary'], Fixed894=invalid['fixed_summary'],
            overlap=without(invalid['invalid_overlap'], ('both_task_keys',)),
            Full_recorded_details=invalid_detail_counts(old_invalid['rows']),
            Fixed894_recorded_details=invalid_detail_counts(invalid['fixed_rows']),
            policy=invalid['policy'], state_membership_and_category_are_distinct=True,
            subtype_causality_identified=False),
        fixed_example_reading=dict(source=invalid['example_reading_observations'],
            selection=observations['example_selection'], raw_packet=observations['reading_packet'],
            pair_count=24, episode_count=48, observed_patterns=observations['observed_patterns'],
            observations=[pick(row, ('pair_index', 'task_key', 'transition', 'observation', 'basis'))
                          for row in observations['pairs']],
            historical_hypotheses_not_established_at_reading_time=observations['hypotheses_not_established'],
            reading_preceded_new_fixed_results=True, population_frequency_estimated_from24pairs=False),
        interpretation_limits=existing['interpretation_limits'],
        original_input_records_reopened=False, original_encoded_packages_reopened=False,
        original_episodes_reopened=False, contribution_or_map_recomputed=False)


def build_report():
    reader = Reader()
    protocol = reader.read(ROOT / 'protocol/record.json')
    implementation = reader.read(ROOT / 'implementation/record.json')
    closeout = reader.read(ROOT / 'closeout/record.json')
    summary = reader.read(ROOT / 'evaluations/final_summary/record.json')
    completion_gate(protocol, implementation, closeout, summary)
    preparation = reader.read_ref(protocol['unlaunched_preparation'])
    require(preparation['status'] == 'PREPARATION_REJECTED_BEFORE_SCIENTIFIC_LAUNCH'
            and preparation['supervisor_launched'] is False
            and preparation['new_scientific_calls'] == preparation['new_optimizer_updates']
                == preparation['new_generation_sessions'] == preparation['new_scoring_calls'] == 0,
            'preserve the unlaunched preparation separately from the successful scientific execution')
    comparator_closeout = reader.read_ref(protocol['full_evaluation']['closeout'])
    train, initial_context = training_summary(reader, protocol)
    evaluation = evaluation_summary(reader, summary)
    execution = execution_summary(reader, closeout, summary)
    mechanisms = mechanism_summary(reader, summary, initial_context)
    body = dict(schema='v71_saved_evidence_final_report_summary_20261025.v1',
        status='READ_ONLY_REPORT_SUMMARY_COMPLETE', scientific_experiment_status='COMPLETE',
        protocol_id=PROTOCOL_ID, implementation_id=IMPLEMENTATION_ID,
        source_commit=implementation['source_commit'],
        source_refs={name: reader.reference(ROOT / directory / 'record.json') for name, directory in (
            ('protocol', 'protocol'), ('implementation', 'implementation'),
            ('closeout', 'closeout'), ('final_summary', 'evaluations/final_summary'))},
        scientific_contract=protocol['scientific_contract'], evaluation_contract=protocol['evaluation'],
        resource_policy=protocol['resource_policy'], final_analysis_resource_policy=protocol['final_analysis_resource_policy'],
        training_control=train, evaluation=evaluation, execution=execution, mechanisms=mechanisms,
        unlaunched_preparation=dict(source=protocol['unlaunched_preparation'], record=preparation,
            preserved_not_reclassified_as_scientific_retry=True),
        V70_comparator=dict(source=protocol['full_evaluation']['closeout'],
            **pick(comparator_closeout, ('status', 'new_training_paths', 'new_feedback_sessions',
                'optimizer_updates', 'task_exposures', 'applied_Full_updates', 'terminal_candidate_probes',
                'terminal_candidate_applied', 'new_evaluation_sessions', 'new_logical_sessions',
                'accepted_jobs', 'scientific_jobs', 'evaluation_jobs')),
            inner_training_dose_matched=True, total_compute_matched=False),
        sources=reader.sources(), source_JSON_count=len(reader.cache),
        source_read_policy='each explicitly selected saved JSON read once; cached references reused',
        analysis_script=dict(path=str(Path(__file__).resolve()), sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        new_native_scores=0, new_model_or_GPU_or_API_calls=0, new_map_iterations=0, new_VJPs=0,
        new_optimizer_updates=0, new_bootstrap_or_significance_tests=0,
        private_references_or_original_episodes_or_Tensors_opened=False,
        full_training_checkpoint_tree_or_original3073mechanism_inputs_rescanned=False,
        historical_scientific_records_written=False, old_failures_reclassified=False,
        independent_new_training_seeds=0, controlled_new_paths=1,
        independent_C_N_or_outer_causal_effects_identified=False,
        cross_seed_generalization_proved=False, endpoint_selection_changed=False,
        automatic_followup_authorized=False)
    return dict(body, id=digest(body))


def _publish_exact(path, raw):
    require(not path.is_symlink(), 'derived report cannot overwrite a symlink')
    if path.exists():
        require(path.read_bytes() == raw, 'existing derived report is immutable')
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.v71-report-', dir=path.parent)
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
            'report publication is restricted to independent report_analysis_01')
    require(value.get('id') == digest(without(value, ('id',))), 'derived report changed before publication')
    if published_summary is not None:
        require(Path(published_summary).resolve() == PUBLISHED_SUMMARY.resolve(),
                'published mirror must retain exact report_data destination')
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    reference = _publish_exact(Path(output_root) / 'record.json', raw)
    if published_summary is not None:
        mirror = _publish_exact(Path(published_summary), raw)
        require(reference['sha256'] == mirror['sha256'], 'report mirror must be byte-identical')
    return reference


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_ROOT)
    parser.add_argument('--published-summary', type=Path)
    args = parser.parse_args(argv)
    require(args.output_root.resolve() == OUTPUT_ROOT.resolve(), 'foreign derived output directory')
    value = build_report()
    reference = publish_report(value, args.output_root, published_summary=args.published_summary)
    print(json.dumps(dict(id=value['id'], status=value['status'], output=reference,
        source_JSON_count=value['source_JSON_count'], new_scientific_operations=0,
        original_scientific_records_written=0), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
