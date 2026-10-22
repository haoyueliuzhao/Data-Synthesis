"""CPU-only native scoring of explicitly frozen, fully sealed model groups.

All four original jobs in a group must pass composite generation acceptance
before any private reference is opened. Native scoring and I/W/R/UNKNOWN
mathematics are reused from the frozen scientific implementation; no provider,
GPU model, old report scoring, cross-seed inference or promotion path exists.
"""
from __future__ import annotations

from collections import Counter
import fcntl
import importlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import finqa_v68_binding as binding

original = binding.source_module('finqa_v63_evaluation')
stats = original.stats
require = binding.require
ELIGIBLE_COORDINATES = tuple((seed, arm) for seed in original.SEEDS for arm in original.ARMS)


def scoring_contract():
    return dict(schema='v68_completed_group_automatic_partial_native_scoring.v1',
        eligible_coordinates=[stats.coordinate(seed, arm) for seed, arm in ELIGIBLE_COORDINATES],
        model_groups=6, original_jobs_per_group=4, sessions_per_group=1243,
        scoring_jobs=24, scoring_sessions=7458, feedback_batch=1, snapshot_step=894,
        required_all_four_original_jobs_complete_before_private_read=True,
        explicit_completed_group_early_scoring_authorization=True,
        original_global_24_job_barrier_not_claimed_passed=True,
        native_scorer='frozen_v6_task.score_public_reasoning_program',
        native_metrics='frozen_v63_statistics.native_metrics',
        metric_tier='native_program_metric_not_trace_quality',
        fixed_original_denominators=True, unknown_as_zero=False,
        unknown_denominator_reduction=False, native_I_W_R_UNKNOWN_unchanged=True,
        calibration_random_draw_order=[11, 29],
        source_generation_bytes_and_old_exits_read_only=True,
        original_GPU_exit_one_and_separate_CPU_exit_zero_preserved_for_adopted_jobs=True,
        new_final_group_requires_its_own_GPU_actual_exit_zero=True,
        private_references_only_for_registered_calibration_and_development=True,
        original_model_task_draw_decoding_and_source_group_bindings_unchanged=True,
        new_generation_calls=0, new_provider_calls=0, new_API_calls=0,
        CUDA_initialized=False, new_training_or_optimizer_updates=0,
        old_batch_or_Hold_rescoring=False, old_summary_reads=False,
        cross_seed_confidence_intervals=False, all_seed_comparisons=False,
        promotion_or_research_decision=False,
        partial_results_must_not_change_remaining_generation_or_training=True,
        automatically_score_only_registered_six_groups_when_all_four_jobs_ready=True,
        eligibility_published_before_each_group_dispatch=True,
        already_scored_jobs_not_rescored=True)


def _runtime():
    """Expose only frozen CPU readers and the native scorer, not model APIs."""
    binding.install_scientific_paths()
    storage = importlib.import_module('trusted_synthesis.finance_research.storage')
    contracts = importlib.import_module('trusted_synthesis.finance_research.contracts')
    planning = importlib.import_module('trusted_synthesis.finance_research.planning')
    task = importlib.import_module('trusted_synthesis.finance_research.v6_task')
    return SimpleNamespace(load_public_snapshot=storage.load_public_snapshot,
        runtime_binding=storage.runtime_binding, PrivateReference=contracts.PrivateReference,
        TaskBundle=contracts.TaskBundle, task_key=planning.task_key,
        score_public_reasoning_program=task.score_public_reasoning_program)


def _assert_cpu_only():
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '',
            'partial native scoring must explicitly hide all CUDA devices')
    torch = sys.modules.get('torch')
    require(torch is None or not torch.cuda.is_initialized(),
            'partial native scoring may not initialize CUDA')


def _same_ref(left, right):
    return (Path(left['path']).resolve(), left['sha256']) == (
        Path(right['path']).resolve(), right['sha256'])


def _protocol(root, protocol=None):
    root = Path(root).resolve()
    require(root == Path(binding.ROOT).resolve(), 'partial scoring requires its new registered root')
    actual = binding.checked(root / 'protocol/record.json')
    require(protocol is None or protocol == actual, 'partial scoring protocol argument changed')
    require(actual['scoring'] == scoring_contract()
            and set(actual['allowed_groups']) == {
                stats.coordinate(seed, arm) for seed, arm in ELIGIBLE_COORDINATES},
            'only the six prospectively registered groups may be scored when complete')
    return actual


def _context(root, coordinate, protocol=None):
    protocol = _protocol(root, protocol)
    require(coordinate in protocol['allowed_groups'], 'incomplete or unregistered group cannot be scored')
    eligibility_path = Path(root).resolve() / 'eligibility' / coordinate / 'record.json'
    group_ref = binding.entry(eligibility_path)
    group = binding.read_ref(group_ref)
    science_ref = protocol['science_protocol_ref']
    require(Path(science_ref['path']).resolve() == Path(binding.SCIENTIFIC_ROOT).resolve() / 'protocol/record.json',
            'partial scoring cannot replace the original scientific protocol')
    science = binding.read_ref(science_ref)
    require(science['evaluation'] == original.evaluation_contract(),
            'original prospective scientific panel definitions changed')
    source_refs = {
        'V65_CPU_COMPOSITE': protocol['source_generation_registration'],
        'V67_GPU_EXIT_ZERO': protocol['completion_generation_registration'],
    }
    source_paths = {
        'V65_CPU_COMPOSITE': Path(binding.SOURCE_GENERATION_ROOT).resolve(),
        'V67_GPU_EXIT_ZERO': Path(binding.SCIENTIFIC_ROOT).resolve() / 'evaluation_completion_01',
    }
    require(group['schema'] == 'v68_complete_original_model_group_eligibility.v1'
            and group['coordinate'] == coordinate
            and (group['seed'], group['arm']) in ELIGIBLE_COORDINATES
            and coordinate == stats.coordinate(group['seed'], group['arm'])
            and type(group['feedback_batch']) is int and group['feedback_batch'] == 1
            and group['step'] == 894 and group['sessions'] == 1243
            and group['scientific_protocol_id'] == science['id'],
            'complete group evidence differs from its authorized original scientific identity')
    expected = {key: job for key, job in original.planned_jobs().items()
                if (job['seed'], job['arm']) == (group['seed'], group['arm'])}
    require(len(expected) == 4 and set(group['jobs']) == set(group['job_ids']) == set(expected),
            'all four original group jobs, with no duplicate or alternate panel, are mandatory')
    require(len({proof['source_kind'] for proof in group['jobs'].values()}) == 1,
            'one original model group cannot mix unrelated generation registrations')
    kind = next(iter(group['jobs'].values()))['source_kind']
    require(kind in source_refs, 'unregistered generation acceptance provenance')
    source_ref = source_refs[kind]
    require(Path(source_ref['path']).resolve() == source_paths[kind] / 'evaluations/registration/record.json',
            'partial scores must use their exact original V65 or V67 generation registration')
    plan = binding.read_ref(source_ref)
    require(plan['schema'] == ('v65_generation_only_registration.v1' if kind == 'V65_CPU_COMPOSITE'
                              else 'v67_generation_only_registration.v1')
            and plan['scientific_protocol_id'] == science['id']
            and plan['feedback_batch'] == 1 and plan['private_references_read'] is False
            and plan['scoring_calls'] == 0,
            'partial scoring requires unchanged, originally unscored native generations')
    for key, planned in expected.items():
        proof = group['jobs'][key]
        job = proof['job']
        require(proof['job_id'] == key and job == plan['jobs'][key]
                and all(job.get(field) == value for field, value in planned.items())
                and proof['source_kind'] == kind
                and _same_ref(proof['source_refs']['plan'], source_ref),
                'partial scoring source, exact task configuration or repaired generation identity changed')
    return protocol, group_ref, group, science, plan


def _native_rows(job, cohort, episodes, bundles, final, check):
    require(len(episodes) == job['denominator'] == len(cohort['tasks']),
            'native scoring must preserve each complete original denominator')
    rows = []
    for task, episode in zip(cohort['tasks'], episodes, strict=True):
        check('before_native_score:' + job['job_id'] + ':' + task)
        rows.append(dict(task_key=f"draw{job['draw_seed']}/{task}", original_task_key=task,
            draw_seed=job['draw_seed'], native=final.score_public_reasoning_program(bundles[task], episode),
            stop_reason=episode.stop_reason, actual_model_calls=episode.actual_model_calls,
            tool_call_count=len(episode.tool_events),
            generated_token_count=sum(len(turn.receipt.raw_generated_token_ids)
                for turn in episode.turns if turn.receipt is not None),
            source_group=cohort['source_groups'][task]))
    # The original metric function validates UNKNOWN status and binary scores;
    # unknown rows retain the full denominator and suppress incomplete means.
    stats.native_metrics(rows, job['denominator'])
    return rows


def _validate_rows(report, *, tasks, groups, denominator):
    rows = report['results']
    require(report['denominator'] == denominator
            and [row['task_key'] for row in rows] == tasks
            and all(row['source_group'] == groups[row['task_key']] for row in rows)
            and report['metrics'] == stats.native_metrics(rows, denominator)
            and report['unknown_as_zero'] is False,
            'saved partial native report changed its fixed task order, denominator or UNKNOWN semantics')


def _job_report(root, protocol, group_ref, group, plan, key, episodes, bundles, final, check):
    proof, job = group['jobs'][key], group['jobs'][key]['job']
    cohort = plan['cohorts'][job['role']]
    path = root / 'groups' / group['coordinate'] / 'jobs' / key / 'record.json'
    tasks = [f"draw{job['draw_seed']}/{task}" for task in cohort['tasks']]
    groups = {f"draw{job['draw_seed']}/{task}": cohort['source_groups'][task] for task in cohort['tasks']}
    if path.exists():
        report = binding.checked(path)
        require(report['schema'] == 'v68_partial_original_job_native_scores.v1'
                and report['protocol_id'] == protocol['id'] and report['job_id'] == key
                and report['scientific_protocol_id'] == group['scientific_protocol_id']
                and report['eligibility'] == group_ref and report['source_job_proof'] == proof
                and report['original_generation_registration_id'] == plan['id']
                and report['feedback_batch'] == 1 and report['new_provider_calls'] == 0,
                'saved partial score does not belong to this accepted original job')
        _validate_rows(report, tasks=tasks, groups=groups, denominator=job['denominator'])
        return report, binding.entry(path), 0
    rows = _native_rows(job, cohort, episodes, bundles, final, check)
    report = binding.publish(path, dict(schema='v68_partial_original_job_native_scores.v1',
        protocol_id=protocol['id'], scientific_protocol_id=group['scientific_protocol_id'],
        original_generation_registration_id=plan['id'], eligibility=group_ref,
        coordinate=group['coordinate'], job_id=key, panel=job['panel'], seed=job['seed'], arm=job['arm'],
        feedback_batch=1, step=894, draw_seed=job['draw_seed'], source_job_proof=proof,
        denominator=job['denominator'], results=rows, metrics=stats.native_metrics(rows, job['denominator']),
        native_status_counts=dict(Counter(row['native']['status'] for row in rows)),
        native_scoring_calls=job['denominator'], unknown_as_zero=False,
        new_provider_calls=0, new_generation_calls=0, new_API_calls=0, CUDA_initialized=False,
        old_generation_exit_rewritten=False, old_results_rescored=False,
        partial_completed_group_only=True, original_all_24_barrier_claimed_passed=False))
    return report, binding.entry(path), job['denominator']


def _panel_report(root, protocol, group_ref, group, science, plan, panel, jobs, reports, references):
    spec = science['evaluation']['panels'][panel]
    cohort, draws = plan['cohorts'][spec['role']], spec['draw_seeds']
    require(len(jobs) == len(draws)
            and {job['draw_seed'] for job in jobs.values()} == set(draws),
            'native model panel must retain all original draws')
    keys = [next(key for key, job in jobs.items() if job['draw_seed'] == draw) for draw in draws]
    rows = [row for key in keys for row in reports[key]['results']]
    tasks = [f'draw{draw}/{task}' for draw in draws for task in cohort['tasks']]
    groups = {f'draw{draw}/{task}': cohort['source_groups'][task]
              for draw in draws for task in cohort['tasks']}
    denominator = len(tasks)
    path = root / 'groups' / group['coordinate'] / 'panels' / panel / 'record.json'
    report = binding.publish(path, dict(schema='v68_partial_fixed_panel_native_model_report.v1',
        protocol_id=protocol['id'], scientific_protocol_id=group['scientific_protocol_id'],
        original_generation_registration_id=plan['id'], eligibility=group_ref,
        coordinate=group['coordinate'], seed=group['seed'], arm=group['arm'], feedback_batch=1,
        panel=panel, primary=panel == original.PRIMARY_PANEL,
        original_panel_config=spec, original_draw_order=draws,
        denominator=denominator, results=rows, metrics=stats.native_metrics(rows, denominator),
        job_score_refs={key: references[key] for key in keys},
        unknown_as_zero=False, fixed_original_denominator=True,
        independent_parent_count=1, partial_completed_group_only=True,
        cross_seed_confidence_intervals=None, promotion_decision=None,
        original_all_24_barrier_claimed_passed=False))
    _validate_rows(report, tasks=tasks, groups=groups, denominator=denominator)
    return report, binding.entry(path)


def _saved_group(root, protocol, group_ref, group, science, plan):
    """Reuse sealed native scores without reading labels or invoking the scorer."""
    directory = root / 'groups' / group['coordinate']
    path = directory / 'result/record.json'
    if not path.exists():
        return None
    result = binding.checked(path)
    require(result['schema'] == 'v68_partial_complete_group_native_scores.v1'
            and result['protocol_id'] == protocol['id']
            and result['scientific_protocol_id'] == group['scientific_protocol_id']
            and result['coordinate'] == group['coordinate'] and result['eligibility'] == group_ref
            and result['original_generation_registration_id'] == plan['id']
            and result['status'] == 'PARTIAL_GROUP_SCORED'
            and result['scoring_execution_complete'] is True
            and result['original_jobs'] == 4 and result['native_scores_present'] == result['sessions'] == 1243
            and set(result['job_scores']) == set(group['jobs'])
            and set(result['model_reports']) == set(science['evaluation']['panels']),
            'saved complete group score belongs to another authorization or cohort')
    for key, reference in result['job_scores'].items():
        require(Path(reference['path']).resolve() == directory / 'jobs' / key / 'record.json',
                'saved job score escaped its original partial group')
        report = binding.read_ref(reference)
        job = group['jobs'][key]['job']
        cohort = plan['cohorts'][job['role']]
        tasks = [f"draw{job['draw_seed']}/{task}" for task in cohort['tasks']]
        groups = {f"draw{job['draw_seed']}/{task}": cohort['source_groups'][task] for task in cohort['tasks']}
        require(report['protocol_id'] == protocol['id'] and report['job_id'] == key
                and report['eligibility'] == group_ref and report['source_job_proof'] == group['jobs'][key],
                'saved job score is not bound to the same complete public generation')
        _validate_rows(report, tasks=tasks, groups=groups, denominator=job['denominator'])
    for panel, reference in result['model_reports'].items():
        require(Path(reference['path']).resolve() == directory / 'panels' / panel / 'record.json',
                'saved model panel escaped its original partial group')
        report = binding.read_ref(reference)
        spec = science['evaluation']['panels'][panel]
        cohort = plan['cohorts'][spec['role']]
        tasks = [f'draw{draw}/{task}' for draw in spec['draw_seeds'] for task in cohort['tasks']]
        groups = {f'draw{draw}/{task}': cohort['source_groups'][task]
                  for draw in spec['draw_seeds'] for task in cohort['tasks']}
        require(report['protocol_id'] == protocol['id'] and report['eligibility'] == group_ref
                and report['coordinate'] == group['coordinate'] and report['panel'] == panel
                and report['original_draw_order'] == spec['draw_seeds'],
                'saved model panel changed its original coordinate or draw order')
        _validate_rows(report, tasks=tasks, groups=groups, denominator=len(tasks))
    return dict(result=result, new_native_scoring_calls=0, result_ref=binding.entry(path))


def score_group(root, coordinate, *, protocol=None, final=None, check=None):
    """Score one complete four-job group; never launch or modify generation."""
    _assert_cpu_only()
    check = check or (lambda _label: None)
    check('before_partial_group_binding')
    root = Path(root).resolve()
    protocol, group_ref, group, science, plan = _context(root, coordinate, protocol)
    directory = root / 'groups' / coordinate
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'score.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        adoption = importlib.import_module('finqa_v68_adoption')
        if (directory / 'result/record.json').exists():
            require(adoption.validate_group_evidence(group, include_episodes=False) == group,
                    'saved scores still require the original accepted generation evidence')
            saved = _saved_group(root, protocol, group_ref, group, science, plan)
            check('after_complete_native_score_reuse_without_private_read')
            return saved
        check('before_all_four_native_generation_validation')
        validated = adoption.validate_group_evidence(group, include_episodes=True)
        require(validated['group'] == group and set(validated['native']) == set(group['jobs']),
                'all four accepted native generations must validate before private scoring')
        check('after_all_four_native_generation_validation')
        final = final or _runtime()
        require(final.runtime_binding() == plan['runtime_binding'],
                'frozen native scoring/reading source binding changed')
        # Only after every original job has been fully checked may any private
        # row be parsed. This excludes unselected/test cohorts and all old scores.
        check('before_public_snapshot_read')
        manifest, public, lineages = final.load_public_snapshot(plan['snapshot'])
        require(manifest['id'] == plan['snapshot_id'], 'original scoring snapshot changed')
        wanted = {task for proof in group['jobs'].values()
                  for task in plan['cohorts'][proof['job']['role']]['tasks']}
        check('before_selected_private_reference_read')
        bundles = original._panel_private_bundles(final, plan, manifest, public, lineages, wanted)
        check('after_selected_private_reference_read')
        reports, references, new_calls = {}, {}, 0
        for key, proof in group['jobs'].items():
            report, reference, calls = _job_report(root, protocol, group_ref, group, plan, key,
                validated['native'][key]['episodes'], bundles, final, check)
            reports[key], references[key] = report, reference
            new_calls += calls
        panels = {}
        for panel in science['evaluation']['panels']:
            jobs = {key: proof['job'] for key, proof in group['jobs'].items()
                    if proof['job']['panel'] == panel}
            if jobs:
                _, panels[panel] = _panel_report(root, protocol, group_ref, group, science,
                    plan, panel, jobs, reports, references)
        require(len(references) == 4 and len(panels) == 3
                and sum(report['denominator'] for report in reports.values()) == 1243,
                'partial scoring cannot add or omit an original panel/draw')
        _assert_cpu_only()
        check('before_partial_group_result_publication')
        result_path = directory / 'result/record.json'
        body = dict(schema='v68_partial_complete_group_native_scores.v1',
            protocol_id=protocol['id'], scientific_protocol_id=group['scientific_protocol_id'],
            coordinate=coordinate, seed=group['seed'], arm=group['arm'], feedback_batch=1, step=894,
            eligibility=group_ref, original_generation_registration_id=plan['id'],
            status='PARTIAL_GROUP_SCORED', original_jobs=4, native_scores_present=1243,
            sessions=1243, scoring_execution_complete=True,
            job_scores=references, model_reports=panels,
            new_generation_calls=0, new_provider_calls=0, new_API_calls=0,
            CUDA_initialized=False, old_results_rescored=False, original_files_modified=False,
            source_generation_kinds=sorted({proof['source_kind'] for proof in group['jobs'].values()}),
            original_generation_exit_records_preserved=True,
            composite_CPU_exit_zero_distinct_for_adopted_jobs=True,
            final_group_requires_GPU_actual_exit_zero=True,
            unknown_as_zero=False, partial_result_not_full_experiment=True,
            cross_seed_confidence_intervals=None, all_seed_promotion_decision=None,
            original_all_24_barrier_claimed_passed=False)
        # The immutable aggregate records scores present, not process-dependent
        # retry counts. A caller may separately record its actual child exit.
        result = binding.publish(result_path, body)
        check('after_partial_group_result_publication')
        return dict(result=result, new_native_scoring_calls=new_calls,
                    result_ref=binding.entry(result_path))
