"""Synthetic task-only adjudication, no real source reads or model calls."""

import copy
import json

import cross_market_text_task_adjudication_20260927 as m
import pytest
from test_cross_market_text_table_review_revision import (
    assess,
    financial_documents,
    finding,
    fixture,
    reference,
    replace_payload,
)


def pending():
    values = fixture()
    replace_payload(values, finding=finding(metric="unknown", period_start=None, period_end=None))
    return values, assess(values)


def payload(initial, decision="not_target_concept"):
    return dict(
        task_id=initial["task_id"],
        baseline_review_id=initial["id"],
        decisions=[
            dict(
                item_id=item["item_id"],
                decision=decision,
                reason="Synthetic source identifies a balance, not target flow.",
            )
            for item in m.pending_items(initial)
        ],
    )


def execution(initial, response):
    return dict(
        protocol_id="adjudication-plan",
        protocol_reference=reference({"new": "plan"}),
        task_id=initial["task_id"],
        baseline_review_id=initial["id"],
        provider="DeepSeek",
        model="deepseek-v4-pro",
        request_reference=reference({"request": "synthetic"}),
        raw_response_reference=reference({"response": "synthetic"}),
        payload_sha256=m.base.sha(m.base.encode(response)),
        finish_reason="stop",
        independent_of_Student_and_Q=True,
    )


def revise(record, **changes):
    body = {k: v for k, v in record.items() if k not in {"id", "schema_version"}}
    return m.base.record(m.semantic.REVIEW_KIND, **{**body, **changes})


def test_request_uses_only_saved_source_and_exact_target_no_answers():
    values, initial = pending()
    before = copy.deepcopy((initial, values[3]))
    task = {**values[0], "answer_exact": "PRIVATE_MUST_NOT_APPEAR", "Q": 1}
    request = m.request_for(task, initial, values[3])
    assert request["model"] == "deepseek-v4-pro" and request["max_tokens"] == 16384
    assert request["thinking"] == {"type": "disabled"} and request["stream"] is False
    assert "PRIVATE_MUST_NOT_APPEAR" not in str(request)
    view = json.loads(request["messages"][1]["content"])
    assert view["baseline_review_id"] == initial["id"] and len(view["items"]) == 1
    assert view["target"]["period_start"] == "2021-01-01"
    original = next(iter(values[3].values()))["segments"][0]
    assert view["source_contexts"][0]["original_segment"] == original
    assert (initial, values[3]) == before


@pytest.mark.parametrize("decision", sorted(m.EXCLUDED))
def test_every_explicit_exclusion_can_resolve_but_preserves_old_pending(decision):
    values, initial = pending()
    response = payload(initial, decision)
    result = m.resolve_task(initial, response, execution(initial, response))
    assert result["status"] == m.semantic.PASS and result["passed"] is True
    assert result["protocol_id"] == initial["protocol_id"]
    assert result["adjudication_protocol_id"] == "adjudication-plan"
    assert result["baseline_review"] == initial and initial["passed"] is False
    assert result["packet_review_ids"] == initial["packet_review_ids"]
    assert (
        not result["potential_aggregates"] and result["original_visual_content_reviewed"] is False
    )
    assert (
        m.semantic.require_composition_review(
            values[0], financial_documents(values), {values[0]["task_id"]: result}, "financial-plan"
        )
        == result["id"]
    )


@pytest.mark.parametrize("decision", ["matching_aggregate", "unresolved"])
def test_matching_or_unresolved_never_admitted(decision):
    values, initial = pending()
    response = payload(initial, decision)
    result = m.resolve_task(initial, response, execution(initial, response))
    assert not result["passed"] and result["remaining_pending_item_ids"] == ["I0000"]
    assert result["potential_aggregates"] == initial["potential_aggregates"]
    assert result["matching_aggregate_is_model_judgment_not_financial_fact"]


@pytest.mark.parametrize(
    "changes",
    [
        dict(status="PENDING_TECHNICAL_REVIEW"),
        dict(technical_pending=[{"missing": "packet"}]),
        dict(all_saved_text_semantically_reviewed=False),
        dict(status=m.semantic.PASS, passed=True),
        dict(packet_review_ids=[]),
        dict(evidence_pending=[], potential_aggregates=[]),
    ],
)
def test_no_technical_pending_or_prior_pass_can_enter(changes):
    values, initial = pending()
    invalid = revise(initial, **changes)
    with pytest.raises(ValueError, match="only_complete_saved_text_semantic_pending"):
        m.request_for(values[0], invalid, values[3])
    with pytest.raises(ValueError, match="only_complete_saved_text_semantic_pending"):
        m.resolve_task(invalid, {}, {})


def test_missing_unknown_or_unexplained_decision_rejected():
    _, initial = pending()
    for changes in [
        dict(decisions=[]),
        dict(decisions=[dict(item_id="other", decision="unresolved", reason="x")]),
        dict(decisions=[dict(item_id="I0000", decision="approve", reason="x")]),
        dict(decisions=[dict(item_id="I0000", decision="not_target_concept", reason=" ")]),
    ]:
        response = {**payload(initial), **changes}
        with pytest.raises(ValueError):
            m.resolve_task(initial, response, execution(initial, response))


@pytest.mark.parametrize(
    "change",
    [
        dict(finish_reason="length"),
        dict(provider="other"),
        dict(baseline_review_id="other"),
        dict(raw_response_reference={}),
        dict(payload_sha256="f" * 64),
        dict(independent_of_Student_and_Q=False),
    ],
)
def test_real_execution_and_unchanged_model_required(change):
    _, initial = pending()
    response = payload(initial)
    receipt = {**execution(initial, response), **change}
    with pytest.raises(ValueError, match="actual_complete_saved_adjudication_execution"):
        m.resolve_task(initial, response, receipt)


def test_uncertainty_uses_complete_original_segment_context():
    values = fixture()
    replace_payload(
        values,
        uncertainty=dict(
            segment_key="S000",
            metric="revenue",
            period_start=None,
            period_end=None,
            reason="One segment did not contain the requested statement",
        ),
    )
    initial = assess(values)
    request = m.request_for(values[0], initial, values[3])
    view = json.loads(request["messages"][1]["content"])
    assert view["items"][0]["original_field"] == "evidence_pending"
    assert view["items"][0]["source_item"] == initial["evidence_pending"][0]
    response = payload(initial, "not_target_concept")
    assert m.resolve_task(initial, response, execution(initial, response))["passed"]


def test_changed_original_quote_or_missing_packet_not_replaced():
    values, initial = pending()
    with pytest.raises(ValueError, match="existing_original_packet_only"):
        m.request_for(values[0], initial, {})
    modified = copy.deepcopy(initial["potential_aggregates"])
    modified[0]["source_span"]["fragments"][0]["quote"] = "invented"
    initial = revise(initial, potential_aggregates=modified)
    with pytest.raises(ValueError, match="original_span_exact_quote"):
        m.request_for(values[0], initial, values[3])


def test_all_items_exactly_once_context_deduplicated_and_partial_exclusion_stays_pending():
    values, initial = pending()
    duplicate = copy.deepcopy(initial["potential_aggregates"][0])
    initial = revise(initial, potential_aggregates=[*initial["potential_aggregates"], duplicate])
    request = m.request_for(values[0], initial, values[3])
    view = json.loads(request["messages"][1]["content"])
    assert len(view["items"]) == 2 and len(view["source_contexts"]) == 1
    response = payload(initial)
    response["decisions"][1]["decision"] = "unresolved"
    result = m.resolve_task(initial, response, execution(initial, response))
    assert not result["passed"] and len(result["potential_aggregates"]) == 1
    assert result["resolved_pending_item_ids"] == ["I0000"]
    response["decisions"][1]["item_id"] = "I0000"
    with pytest.raises(ValueError, match="explicit_source_grounded_item_decision"):
        m.resolve_task(initial, response, execution(initial, response))


def test_adjudication_is_not_an_unbounded_recursive_retry():
    _, initial = pending()
    response = payload(initial, "unresolved")
    result = m.resolve_task(initial, response, execution(initial, response))
    with pytest.raises(ValueError, match="no_recursive_adjudication"):
        m.pending_items(result)
