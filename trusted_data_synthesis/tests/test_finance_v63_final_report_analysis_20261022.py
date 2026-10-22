"""Small derived-report checks; no scoring, model work or real report writes."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import finqa_v63_final_report_analysis_20261022 as report


def summary(temperature, hold, *, unknown=False):
    counts = {'C05-C1': temperature, 'C05-Hold': hold,
              'C1-Hold': [b - a for a, b in zip(temperature, hold, strict=True)]}
    return dict(denominator=883, independent_parent_count=3,
        comparisons={name: dict(status='INCOMPLETE' if unknown else 'COMPLETE',
            per_seed={str(seed): dict(numerator=value) for seed, value in zip((137, 251, 389), values, strict=True)})
            for name, values in counts.items()})


@pytest.mark.parametrize('temperature,expected', [([9, 9, 9], True), ([8, 9, 9], False)])
def test_exact_integer_numerical_gate_does_not_claim_formal_contract_pass(temperature, expected):
    statistics = SimpleNamespace(PRIMARY_DENOMINATOR=883, SEEDS=(137, 251, 389),
        MINIMUM_TEMPERATURE_NET_CORRECT=27, MINIMUM_HOLD_NET_CORRECT=1)
    result = report._numerical_gates(summary(temperature, [1, 0, 0]), statistics)
    assert result['temperature_numerical_gate_passed'] is expected
    assert result['hold_numerical_gate_passed'] is True
    assert result['both_numerical_gates_passed'] is expected
    assert result['total_paired_denominator'] == 2649
    assert result['original_all_contracts_passed'] is False
    assert result['formal_advancement_function_called'] is False
    assert result['automatic_followup_authorized'] is False


def test_unknown_remains_incomplete_not_zero_or_denominator_reduction():
    statistics = SimpleNamespace(PRIMARY_DENOMINATOR=883, SEEDS=(137, 251, 389),
        MINIMUM_TEMPERATURE_NET_CORRECT=27, MINIMUM_HOLD_NET_CORRECT=1)
    value = report._numerical_gates(summary([100, 100, 100], [100, 100, 100], unknown=True), statistics)
    assert value['net_correct_totals'] is None and value['both_numerical_gates_passed'] is None
    assert value['comparison_scores_complete'] is False and value['total_paired_denominator'] == 2649


def test_random_panel_retains_unique_tasks_and_original_draw_order():
    cohort = dict(tasks=['task_a', 'task_b'], source_groups={'task_a': 'issuer1', 'task_b': 'issuer2'})
    tasks, groups, denominator = report._panel_layout(dict(tasks_per_draw=2, draw_seeds=[11, 29]), cohort)
    assert tasks == ['draw11/task_a', 'draw11/task_b', 'draw29/task_a', 'draw29/task_b']
    assert denominator == dict(unique_tasks=2, draws_per_task=2, draw_order=[11, 29],
        paired_session_denominator=4, repeated_draws_are_not_additional_unique_questions=True)
    assert groups['draw11/task_a'] == groups['draw29/task_a'] == 'issuer1'


def test_all_six_score_gate_rejects_partial_or_unaccepted_status():
    coordinates = [f'seed{s}/{a}' for s in (137, 251, 389) for a in ('C1', 'C05')]
    closeout = dict(status='ALL_SIX_GROUPS_SCORED_AWAITING_GLOBAL_ANALYSIS',
        protocol_id=report.SCORING_PROTOCOL_ID, scientific_protocol_id=report.BASE_PROTOCOL_ID,
        active_workers=0, accepted_native_scores=7458, total_registered_groups=6,
        accepted_groups={key: {} for key in coordinates},
        group_states={key: {'status': 'COMPLETE'} for key in coordinates})
    report._complete_scoring_gate(closeout, {'id': report.SCORING_PROTOCOL_ID}, coordinates)
    closeout['accepted_groups'].pop(coordinates[-1])
    with pytest.raises(ValueError, match='all six'):
        report._complete_scoring_gate(closeout, {'id': report.SCORING_PROTOCOL_ID}, coordinates)


def test_publication_is_new_root_only_and_published_mirror_is_identical(tmp_path, monkeypatch):
    output, mirror = tmp_path / 'report_analysis_01', tmp_path / 'report_data/report.json'
    monkeypatch.setattr(report, 'OUTPUT_ROOT', output)
    monkeypatch.setattr(report, 'PUBLISHED_SUMMARY', mirror)
    body = dict(schema='test-derived-only', new_native_scoring_calls=0,
                original_all_contracts_passed=False, panels={})
    value = dict(body, id=report.digest(body))
    reference = report.publish_report(value, output, published_summary=mirror)
    assert (output / 'record.json').read_bytes() == mirror.read_bytes()
    assert reference == report.publish_report(value, output, published_summary=mirror)
    with pytest.raises(ValueError, match='new report_analysis_01'):
        report.publish_report(value, tmp_path / 'original-science')
    with pytest.raises(ValueError, match='exact repository report path'):
        report.publish_report(value, output, published_summary=tmp_path / 'old-summary.json')


def test_analysis_uses_original_frozen_functions_without_scoring_api():
    evaluation, statistics, sources = report._frozen()
    assert statistics.paired_summary.__module__ == 'finqa_v63_statistics'
    assert statistics.batch_replication_diagnostics.__module__ == 'finqa_v63_statistics'
    assert statistics.BOOTSTRAP_REPLICATES == 10000 and statistics.BOOTSTRAP_SEED == 20261018
    assert statistics.T95_DF2 == 4.3026527299
    assert evaluation.reused_old_reports.__module__ == 'finqa_v63_evaluation'
    assert set(sources) == {'finqa_v63_binding.py', 'finqa_v63_evaluation.py',
                            'finqa_v63_statistics.py', 'finqa_v54_statistics.py'}


def test_frozen_feedback_support_counts_do_not_confuse_sessions_and_unique_tasks():
    roster = [dict(task_id=f'task{i}', seed=seed) for seed in (101, 103) for i in range(350)]
    groups = {f'task{i}': f'source{i % 5}' for i in range(350)}
    rewards = [int(row['task_id'] in ('task0', 'task1')) for row in roster]
    value = report._feedback_support_counts(roster, rewards, groups)
    assert value['session_denominator'] == 700 and value['unique_task_denominator'] == 350
    assert value['successful_feedback_sessions'] == 4 and value['distinct_successful_tasks'] == 2
    assert value['successful_sessions_by_draw'] == {'101': 2, '103': 2}
    assert value['source_group_denominator'] == 5 and value['distinct_successful_source_groups'] == 2
    assert value['zero_reward_sessions_retained']
