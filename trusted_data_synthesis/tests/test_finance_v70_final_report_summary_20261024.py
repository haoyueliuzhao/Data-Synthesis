"""Focused report-only checks; no real report publish or scientific execution."""
from __future__ import annotations

import json

import pytest

import finqa_v70_final_report_summary_20261024 as report


def _complete_values():
    protocol = {'id': report.PROTOCOL_ID}
    implementation = {'id': report.IMPLEMENTATION_ID}
    closeout = dict(id=report.CLOSEOUT_ID, protocol_id=report.PROTOCOL_ID,
        status='COMPLETE', active_workers=0, accepted_jobs=26, new_feedback_sessions=2100,
        optimizer_updates=596, new_evaluation_sessions=1123, applied_Full_updates=2,
        terminal_candidate_probes=1, terminal_candidate_applied=False, automatic_followup_started=False)
    summary = dict(id=report.FINAL_SUMMARY_ID, protocol_id=report.PROTOCOL_ID, status='COMPLETE',
        new_evaluation_sessions=1123, terminal_probe_applied=False, intermediate_accuracy_used_for_selection=False)
    return protocol, implementation, closeout, summary


def test_completion_gate_preserves_fixed_dose_and_unapplied_terminal_probe():
    values = _complete_values()
    report.completion_gate(*values)
    values[2]['terminal_candidate_applied'] = True
    with pytest.raises(ValueError, match='unapplied terminal probe'):
        report.completion_gate(*values)


def test_partial_queue_cannot_be_promoted_by_report():
    values = _complete_values()
    values[2]['accepted_jobs'] = 25
    with pytest.raises(ValueError, match='full fixed dose'):
        report.completion_gate(*values)


def test_feedback_counts_keep_700_sessions_and_350_unique_tasks():
    roster = [dict(seed=seed, task_id=f'task{i}') for seed in (101, 103) for i in range(350)]
    rewards = [int(row['task_id'] in ('task0', 'task1')) for row in roster]
    result = report.feedback_counts(roster, rewards)
    assert result['session_denominator'] == 700 and result['unique_task_denominator'] == 350
    assert result['successful_sessions'] == 4 and result['distinct_successful_tasks'] == 2
    assert result['successful_sessions_by_draw'] == {'101': 2, '103': 2}
    assert result['all_zero_feedback'] is False and result['zero_reward_sessions_retained']
    rewards[0] = None
    with pytest.raises(ValueError, match='known frozen binary rewards'):
        report.feedback_counts(roster, rewards)


def test_compact_distance_retains_aggregate_scope_not_per_task_table():
    value = dict(per_task={'a': {}, 'b': {}}, adjustable_tasks=['a'], adjustable_mu=.5,
                 all_tasks={'TV': .05}, adjustable={'TV': .1})
    result = report.compact_distance(value)
    assert result['task_count'] == 2 and result['adjustable_task_count'] == 1
    assert result['all_tasks']['TV'] == .05 and result['adjustable']['TV'] == .1
    assert 'per_task' not in result and 'adjustable_tasks' not in result
    assert report.compact_distance(None) is None


def test_failed_resource_attempts_stay_failed_in_aggregate():
    rows = [dict(all_gates_passed=True, peak_allocated_bytes=8, peak_rss_bytes=12,
                 minimum_boundary_free_bytes=6, minimum_host_available_bytes=30),
            dict(all_gates_passed=False, peak_allocated_bytes=4, peak_rss_bytes=10,
                 minimum_boundary_free_bytes=2, minimum_host_available_bytes=25)]
    result = report._aggregate_resources(rows)
    assert result['resource_pass_count'] == result['resource_fail_count'] == 1
    assert result['peak_allocated_bytes'] == 8 and result['minimum_boundary_free_bytes'] == 2


def test_publication_is_new_root_only_immutable_and_byte_identical(tmp_path, monkeypatch):
    root, mirror = tmp_path / 'report_analysis_01', tmp_path / 'report_data/summary.json'
    monkeypatch.setattr(report, 'OUTPUT_ROOT', root)
    monkeypatch.setattr(report, 'PUBLISHED_SUMMARY', mirror)
    body = dict(schema='CPU-test', new_native_scores=0, terminal_probe_applied=False)
    value = dict(body, id=report.digest(body))
    first = report.publish_report(value, root, published_summary=mirror)
    assert (root / 'record.json').read_bytes() == mirror.read_bytes()
    assert report.publish_report(value, root, published_summary=mirror) == first
    with pytest.raises(ValueError, match='independent report_analysis_01'):
        report.publish_report(value, tmp_path / 'old-science')
    with pytest.raises(ValueError, match='exact report_data'):
        report.publish_report(value, root, published_summary=tmp_path / 'other.json')
    changed = dict(body, new_native_scores=1)
    with pytest.raises(ValueError, match='existing derived report is immutable'):
        report.publish_report(dict(changed, id=report.digest(changed)), root)


def test_expected_roster_is_exactly_two_train_windows_and_three_evaluations():
    jobs = report.expected_jobs()
    assert len(jobs) == 26
    assert 'step1490.train' not in jobs
    assert sum(key.endswith('.train') for key in jobs) == 2
    assert sum('greedy' in key for key in jobs) == 3
