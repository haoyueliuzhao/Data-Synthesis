"""Report-only checks of fixed dose, paired orientation and immutable publication."""
from __future__ import annotations

import json

import pytest

import finqa_v71_final_report_summary_20261025 as report


def complete_values():
    protocol, implementation = {'id': report.PROTOCOL_ID}, {'id': report.IMPLEMENTATION_ID}
    closeout = dict(id=report.CLOSEOUT_ID, protocol_id=report.PROTOCOL_ID,
        status='COMPLETE', active_workers=0, accepted_jobs=5, optimizer_updates=596,
        task_exposures=2976, new_evaluation_sessions=1123, new_feedback_sessions=0,
        applied_Full_updates=0, terminal_candidate_probes=0,
        terminal_candidate_applied=False, automatic_followup_started=False)
    summary = dict(id=report.FINAL_SUMMARY_ID, protocol_id=report.PROTOCOL_ID,
        status='COMPLETE', optimizer_updates=596, task_exposures=2976, new_evaluation_sessions=1123,
        new_outer_updates=0, feedback_sessions=0, class_passes=0, replay_responses=0, VJP=0,
        automatic_followup=False, dev1192_evaluated=False, baseline_rescored=False, Full_rescored=False)
    return protocol, implementation, closeout, summary


def test_complete_fixed_dose_cannot_hide_outer_or_partial_job():
    values = complete_values()
    report.completion_gate(*values)
    values[3]['new_outer_updates'] = 1
    with pytest.raises(ValueError, match='complete fixed'):
        report.completion_gate(*values)
    values = complete_values()
    values[2]['accepted_jobs'] = 4
    with pytest.raises(ValueError, match='complete fixed'):
        report.completion_gate(*values)
    assert len(report.expected_jobs()) == 5
    assert set(report.expected_jobs()) == {'step894.train', 'step1192.train', *report.PANELS}


def pair_fixture():
    transitions = {a + '->' + b: 0 for a in report.STATES for b in report.STATES}
    transitions.update({'I->R': 1, 'W->I': 1, 'R->I': 1, 'R->R': 1})
    reference = dict(states={'I': 1, 'W': 1, 'R': 2, 'UNKNOWN': 0}, execution_accuracy={'correct': 2})
    candidate = dict(states={'I': 2, 'W': 0, 'R': 2, 'UNKNOWN': 0}, execution_accuracy={'correct': 2})
    pair = dict(status='COMPLETE', denominator=4, unknown_pair_count=0, transitions=transitions,
        new_correct=1, lost_correct=1, net_correct=0, numerator=0, difference=0,
        decomposition={'invalid_correct_net_count': 0, 'wrong_correct_net_count': 0})
    return pair, candidate, reference


def test_saved_paired_matrix_keeps_reference_to_candidate_orientation():
    pair, candidate, reference = pair_fixture()
    report.validate_paired(pair, candidate, reference, 4)
    with pytest.raises(ValueError, match='orientation'):
        report.validate_paired(pair, reference, candidate, 4)
    pair['new_correct'] = 2
    with pytest.raises(ValueError, match='new/lost'):
        report.validate_paired(pair, candidate, reference, 4)


def test_both_primary_differences_keep_full_denominator_and_sign():
    adaptive, fixed = report.delta(371, 377, 883), report.delta(377, 525, 883)
    assert adaptive['numerator'] == -6 and fixed['numerator'] == -148
    assert adaptive['difference_pp'] == pytest.approx(-0.6795016987542469)
    assert fixed['difference_pp'] == pytest.approx(-16.761041902604756)
    assert adaptive['denominator'] == fixed['denominator'] == 883


def test_resource_aggregation_retains_worker_wait_and_failure():
    rows = [dict(all_gates_passed=True, peak_allocated_bytes=8, peak_rss_bytes=12,
                 minimum_boundary_free_bytes=6, minimum_host_available_bytes=30,
                 resource_wait_seconds=2.5, preflight_shortages=0),
            dict(all_gates_passed=False, peak_allocated_bytes=4, peak_rss_bytes=10,
                 minimum_boundary_free_bytes=2, minimum_host_available_bytes=25,
                 resource_wait_seconds=3.5, preflight_shortages=1)]
    result = report.aggregate_resources(rows)
    assert result['resource_pass_count'] == result['resource_fail_count'] == 1
    assert result['worker_resource_wait_seconds'] == 6 and result['preflight_shortages'] == 1
    assert result['peak_allocated_bytes'] == 8 and result['minimum_boundary_free_bytes'] == 2


def test_terminal_missing_submission_is_not_never_submit():
    rows = [dict(terminal_category='missing_terminal_submission', stop_reason='no_tool_call',
                 native_reason='missing_or_invalid_submission'),
            dict(terminal_category='missing_terminal_submission', stop_reason='final_answer',
                 native_reason='missing_or_invalid_submission')]
    result = report.invalid_detail_counts(rows)
    assert result['terminal_counts']['missing_terminal_submission'] == 2
    assert result['terminal_by_stop_reason']['missing_terminal_submission'] == {
        'no_tool_call': 1, 'final_answer': 1}


def test_reader_reuses_one_saved_json_read_and_rejects_changed_reference(tmp_path, monkeypatch):
    path = tmp_path / 'record.json'
    body = dict(schema='test', old_scores_changed=False)
    value = dict(body, id=report.digest(body))
    path.write_text(json.dumps(value))
    original, calls = type(path).read_bytes, []
    def counted(self):
        calls.append(self)
        return original(self)
    monkeypatch.setattr(type(path), 'read_bytes', counted)
    reader = report.Reader()
    assert reader.read(path) == value
    reference = reader.reference(path)
    assert reader.read_ref(reference) == value and calls == [path.resolve()]
    with pytest.raises(ValueError, match='bound saved JSON'):
        reader.read_ref(dict(reference, sha256='changed'))
    with pytest.raises(ValueError, match='explicitly selected JSON'):
        reader.read(tmp_path / 'state.pt')


def test_publication_stays_new_root_only_and_mirror_is_identical(tmp_path, monkeypatch):
    root, mirror = tmp_path / 'report_analysis_01', tmp_path / 'report_data/summary.json'
    monkeypatch.setattr(report, 'OUTPUT_ROOT', root)
    monkeypatch.setattr(report, 'PUBLISHED_SUMMARY', mirror)
    body = dict(schema='CPU-test', new_native_scores=0, new_outer_updates=0)
    value = dict(body, id=report.digest(body))
    first = report.publish_report(value, root, published_summary=mirror)
    assert (root / 'record.json').read_bytes() == mirror.read_bytes()
    assert report.publish_report(value, root, published_summary=mirror) == first
    with pytest.raises(ValueError, match='independent report_analysis_01'):
        report.publish_report(value, tmp_path / 'science')
    with pytest.raises(ValueError, match='exact report_data'):
        report.publish_report(value, root, published_summary=tmp_path / 'foreign.json')
    changed = dict(body, new_native_scores=1)
    with pytest.raises(ValueError, match='existing derived report is immutable'):
        report.publish_report(dict(changed, id=report.digest(changed)), root)
