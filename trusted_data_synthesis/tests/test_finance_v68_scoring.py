"""Mock-only native scoring controls, using the original frozen statistics."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v68_binding as binding
import finqa_v68_scoring as scoring
import finqa_v68_adoption as adoption


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != 'id'}
    value = dict(body, id=binding.digest(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def outcome(state):
    return dict(status={'I': 'invalid_prediction', 'W': 'scored', 'R': 'scored', 'UNKNOWN': 'unknown'}[state],
        program_executable=False if state == 'I' else None if state == 'UNKNOWN' else True,
        native=dict(execution_accuracy=None if state == 'UNKNOWN' else int(state == 'R'),
                    program_accuracy=None if state == 'UNKNOWN' else int(state == 'R')))


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    science = tmp_path / 'science'
    root, old, completion = science / 'partial_scoring_01', science / 'early_generation_01', science / 'evaluation_completion_01'
    monkeypatch.setattr(binding, 'ROOT', root)
    monkeypatch.setattr(binding, 'SCIENTIFIC_ROOT', science)
    monkeypatch.setattr(binding, 'SOURCE_GENERATION_ROOT', old)
    monkeypatch.setattr(binding, 'COMPLETION_ROOT', completion)
    scientific = rewrite(science / 'protocol/record.json', dict(evaluation=scoring.original.evaluation_contract()))
    cohorts = {role: dict(tasks=[f'finqa/{role}{i}' for i in range(n)],
                         source_groups={f'finqa/{role}{i}': f'group{i % 5}' for i in range(n)})
               for role, n in (('calibration', 120), ('development', 883))}
    all_jobs = {key: dict(job, checkpoint={'state_sha256': 'actual-state'},
                         model_identity={'point_id': 'unchanged-original-point'})
                for key, job in scoring.original.planned_jobs().items()}
    base = dict(scientific_protocol_id=scientific['id'], feedback_batch=1,
        private_references_read=False, scoring_calls=0, snapshot='/mock/snapshot',
        snapshot_id='original-public-snapshot', runtime_binding={'native': 'actual-frozen'}, cohorts=cohorts)
    old_plan = rewrite(old / 'evaluations/registration/record.json', dict(base,
        schema='v65_generation_only_registration.v1', jobs={key: job for key, job in all_jobs.items()
            if (job['seed'], job['arm']) != (389, 'C05')}))
    new_plan = rewrite(completion / 'evaluations/registration/record.json', dict(base,
        schema='v67_generation_only_registration.v1', jobs={key: job for key, job in all_jobs.items()
            if (job['seed'], job['arm']) == (389, 'C05')}))
    protocol = rewrite(root / 'protocol/record.json', dict(scoring=scoring.scoring_contract(),
        allowed_groups=[f'seed{seed}/{arm}' for seed, arm in scoring.ELIGIBLE_COORDINATES],
        science_protocol_ref=binding.entry(science / 'protocol/record.json'),
        source_generation_registration=binding.entry(old / 'evaluations/registration/record.json'),
        completion_generation_registration=binding.entry(completion / 'evaluations/registration/record.json')))
    native, events, private_calls, score_calls = {}, [], [], []

    def group(seed=137, arm='C1'):
        coordinate = f'seed{seed}/{arm}'
        kind = 'V67_GPU_EXIT_ZERO' if (seed, arm) == (389, 'C05') else 'V65_CPU_COMPOSITE'
        plan = new_plan if kind == 'V67_GPU_EXIT_ZERO' else old_plan
        source_ref = protocol['completion_generation_registration' if kind == 'V67_GPU_EXIT_ZERO'
                              else 'source_generation_registration']
        jobs = {}
        for key, job in plan['jobs'].items():
            if (job['seed'], job['arm']) != (seed, arm):
                continue
            jobs[key] = dict(job_id=key, job=job, source_kind=kind,
                source_refs=dict(plan=source_ref), generation_root='/mock/generation/' + key)
            native[key] = dict(run={}, seal={}, episodes=[SimpleNamespace(i=i, stop_reason='final_answer',
                actual_model_calls=1, tool_events=(), turns=()) for i in range(job['denominator'])])
        return rewrite(root / 'eligibility' / coordinate / 'record.json', dict(
            schema='v68_complete_original_model_group_eligibility.v1', coordinate=coordinate,
            seed=seed, arm=arm, feedback_batch=1, step=894, sessions=1243,
            scientific_protocol_id=scientific['id'], job_ids=list(jobs), jobs=jobs))

    def validate(value, *, include_episodes=False):
        events.append('validated_all_four')
        return dict(group=value, native={key: native[key] for key in value['jobs']}) if include_episodes else value

    def load_snapshot(_path):
        events.append('public_read')
        return dict(id='original-public-snapshot'), [], []

    def private(*args):
        events.append('private_read')
        wanted = args[-1]
        private_calls.append(wanted)
        return {key: key for key in wanted}

    def native_score(bundle, episode):
        score_calls.append((bundle, episode.i))
        return outcome(('I', 'W', 'R', 'UNKNOWN')[episode.i % 4])

    monkeypatch.setattr(adoption, 'validate_group_evidence', validate)
    monkeypatch.setattr(scoring.original, '_panel_private_bundles', private)
    final = SimpleNamespace(runtime_binding=lambda: base['runtime_binding'],
                            load_public_snapshot=load_snapshot, score_public_reasoning_program=native_score)
    return SimpleNamespace(root=root, science=science, old=old, completion=completion,
        protocol=protocol, group=group, native=native, final=final, events=events,
        private_calls=private_calls, score_calls=score_calls, old_plan=old_plan, new_plan=new_plan)


def test_contract_allows_only_six_original_complete_groups_without_inference():
    contract = scoring.scoring_contract()
    assert contract['model_groups'] == 6 and contract['scoring_jobs'] == 24
    assert contract['scoring_sessions'] == 7458
    assert not contract['unknown_as_zero'] and not contract['unknown_denominator_reduction']
    assert not contract['promotion_or_research_decision'] and not contract['cross_seed_confidence_intervals']
    assert not contract['old_batch_or_Hold_rescoring'] and not contract['old_summary_reads']
    assert contract['new_generation_calls'] == contract['new_provider_calls'] == 0
    for forbidden in ('paired_summary', 'score_model', 'load_final_provider', 'prepare_jobs'):
        assert not hasattr(scoring, forbidden)


def test_native_math_is_the_original_I_W_R_UNKNOWN_function():
    original = binding.source_module('finqa_v63_statistics')
    assert scoring.stats.native_metrics is original.native_metrics
    rows = [{'native': outcome(state)} for state in ('I', 'W', 'R', 'UNKNOWN')]
    metrics = scoring.stats.native_metrics(rows, 4)
    assert metrics['states'] == dict(I=1, W=1, R=1, UNKNOWN=1)
    assert metrics['execution_accuracy'] == dict(denominator=4, scored=3, unknown=1, correct=1,
                                                complete_dataset_mean=None)


def test_complete_old_group_scores_four_jobs_and_three_panels_with_no_old_writes(environment):
    e = environment
    group = e.group()
    source = e.old / 'evaluations/registration/record.json'
    old_bytes = source.read_bytes()
    callbacks = []
    result = scoring.score_group(e.root, group['coordinate'], final=e.final, check=callbacks.append)
    report = result['result']
    assert report['status'] == 'PARTIAL_GROUP_SCORED' and report['scoring_execution_complete']
    assert report['sessions'] == report['native_scores_present'] == result['new_native_scoring_calls'] == 1243
    assert len(report['job_scores']) == 4 and len(report['model_reports']) == 3
    assert e.events[:3] == ['validated_all_four', 'public_read', 'private_read']
    assert len(e.private_calls) == 1 and len(e.private_calls[0]) == 1003
    assert len(e.score_calls) == 1243
    assert sum(label.startswith('before_native_score:') for label in callbacks) == 1243
    assert source.read_bytes() == old_bytes
    assert not (e.old / 'evaluations/panels').exists()
    assert not report['original_all_24_barrier_claimed_passed']
    random_panel = next(ref for name, ref in report['model_reports'].items() if 'random' in name)
    panel = binding.read_ref(random_panel)
    assert panel['denominator'] == 240 and panel['original_draw_order'] == [11, 29]
    assert panel['results'][0]['draw_seed'] == 11 and panel['results'][120]['draw_seed'] == 29
    assert panel['metrics']['states'] == dict(I=60, W=60, R=60, UNKNOWN=60)
    assert panel['metrics']['execution_accuracy']['complete_dataset_mean'] is None
    assert panel['cross_seed_confidence_intervals'] is panel['promotion_decision'] is None


def test_saved_complete_scores_reused_without_private_read_or_native_calls(environment, monkeypatch):
    e = environment
    group = e.group()
    first = scoring.score_group(e.root, group['coordinate'], final=e.final)
    monkeypatch.setattr(scoring.original, '_panel_private_bundles', lambda *_: pytest.fail('no repeat label read'))
    final = SimpleNamespace(load_public_snapshot=lambda *_: pytest.fail('no repeat snapshot read'),
                            score_public_reasoning_program=lambda *_: pytest.fail('no native rescore'))
    reused = scoring.score_group(e.root, group['coordinate'], final=final)
    assert reused['result'] == first['result'] and reused['new_native_scoring_calls'] == 0
    assert len(e.score_calls) == 1243


def test_final_group_uses_its_four_new_GPU_exit_zero_jobs(environment):
    e = environment
    group = e.group(389, 'C05')
    report = scoring.score_group(e.root, group['coordinate'], final=e.final)['result']
    assert report['source_generation_kinds'] == ['V67_GPU_EXIT_ZERO']
    assert report['final_group_requires_GPU_actual_exit_zero']
    assert report['original_generation_registration_id'] == e.new_plan['id']
    assert report['sessions'] == 1243


@pytest.mark.parametrize('change', ['missing', 'config', 'source', 'batch', 'coordinate'])
def test_incomplete_or_changed_groups_never_open_private_reference(environment, change):
    e = environment
    group = deepcopy(e.group())
    key = next(iter(group['jobs']))
    if change == 'missing':
        group['jobs'].pop(key)
    elif change == 'config':
        group['jobs'][key]['job']['config']['max_new_tokens'] += 1
    elif change == 'source':
        group['jobs'][key]['source_kind'] = 'V67_GPU_EXIT_ZERO'
    elif change == 'batch':
        group['feedback_batch'] = 0
    else:
        group['coordinate'] = 'seed251/C1'
    rewrite(e.root / 'eligibility/seed137/C1/record.json', group)
    with pytest.raises(ValueError):
        scoring.score_group(e.root, 'seed137/C1', final=e.final)
    assert not e.private_calls and not e.score_calls


def test_adoption_failure_precedes_all_private_reads(environment, monkeypatch):
    e = environment
    group = e.group()
    def fail(*args, **kwargs):
        raise ValueError('actual CPU exit not zero')
    monkeypatch.setattr(adoption, 'validate_group_evidence', fail)
    with pytest.raises(ValueError, match='actual CPU exit'):
        scoring.score_group(e.root, group['coordinate'], final=e.final)
    assert not e.private_calls and not e.score_calls


@pytest.mark.parametrize('label', ['before_selected_private_reference_read', 'before_native_score:'])
def test_resource_or_stop_callback_prevents_next_private_or_score_operation(environment, label):
    e = environment
    group = e.group()
    def stop(value):
        if value.startswith(label):
            raise RuntimeError('explicit stop or actual RSS limit')
    with pytest.raises(RuntimeError, match='explicit stop'):
        scoring.score_group(e.root, group['coordinate'], final=e.final, check=stop)
    assert not e.score_calls
    if label == 'before_selected_private_reference_read':
        assert not e.private_calls
    assert not (e.root / 'groups' / group['coordinate'] / 'result/record.json').exists()


def test_no_visible_GPU_and_no_scientific_root_writes(environment, monkeypatch):
    e = environment
    group = e.group()
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '0')
    with pytest.raises(ValueError, match='hide all CUDA'):
        scoring.score_group(e.root, group['coordinate'], final=e.final)
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    with pytest.raises(ValueError, match='new registered root'):
        scoring.score_group(e.science, group['coordinate'], final=e.final)
    with pytest.raises(ValueError, match='unregistered group'):
        scoring.score_group(e.root, 'seed137/Hold', final=e.final)
    assert not e.private_calls


def test_cpu_runtime_uses_actual_frozen_native_scorer_without_provider_api():
    final = scoring._runtime()
    task = __import__('trusted_synthesis.finance_research.v6_task', fromlist=['score_public_reasoning_program'])
    storage = __import__('trusted_synthesis.finance_research.storage', fromlist=['load_public_snapshot'])
    assert final.score_public_reasoning_program is task.score_public_reasoning_program
    assert final.load_public_snapshot is storage.load_public_snapshot
    frozen = Path(binding.install_scientific_paths()['frozen_source_root']).resolve()
    assert Path(task.__file__).resolve().is_relative_to(frozen)
    assert not hasattr(final, 'load_final_provider') and not hasattr(final, 'execute_run')
