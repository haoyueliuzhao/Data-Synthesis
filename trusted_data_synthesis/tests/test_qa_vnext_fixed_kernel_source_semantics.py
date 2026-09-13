"""Offline execution-domain controls; zero provider or model operations."""

import copy

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.assessment import assess_session
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import generate
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.semantic_mapping import (
    assess_new_semantics,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.source_boundary import (
    prepare_fixture,
)


def session_with(extra=(), *, final=True):
    f = fixture()
    script = script_for_witness(f["bundle"], f["native_bindings"], "movement")
    script = [*script[:-1], *extra, *script[-1:]] if final else script[:-1]
    session = generate(f["messages"], f["identity"], scripted=script, requested_basis="movement")
    old = assess_session(session, f["bundle"], f["native_bindings"])
    return f, session, old


def test_new_clean_class_preserves_original_financial_method_and_assessment():
    f, session, old = session_with()
    result = assess_new_semantics(session, prepare_fixture(f), old)
    assert result["financial_valid"] and result["actual_method"] == "movement"
    assert result["full_mapping_status"] == old["full_mapping_status"] == "MAPPED"
    assert result["original_semantic_assessment"] == old
    assert result["full_class"] != old["full_class"]
    assert not result["training_eligible"]


def test_rejected_tool_and_format_recovery_retained_without_invented_revision():
    f, session, old = session_with(
        [
            {"tool": "read_source", "arguments": {"source_id": "not_public"}},
            "not a JSON object",
        ]
    )
    original = copy.deepcopy(session)
    result = assess_new_semantics(session, prepare_fixture(f), old)
    assert old["financial_valid"] and old["full_mapping_status"] == "PENDING_REVIEW"
    assert result["full_mapping_status"] == "MAPPED"
    assert session == original
    signature = result["full_signature"]
    assert len(signature["rejected_tool_events"]) == len(signature["protocol_rejections"]) == 1
    assert signature["rejected_tool_events"][0]["numeric_result_created"] is False
    assert signature["rejected_tool_events"][0]["implicit_repair_or_revision_edge"] is False
    assert not signature["revision_edges"]
    assert result["failure_responses_are_positive_training_targets"] is False


def test_side_calculation_is_executed_non_dependency_not_guessed_intent():
    f, session, old = session_with(
        [
            {
                "tool": "calculate",
                "arguments": {
                    "expression": "x*2",
                    "variables": {"x": {"result_id": "tool:1"}},
                    "unit": "million USD",
                },
            }
        ]
    )
    assert old["full_mapping_status"] == "PENDING_REVIEW"
    result = assess_new_semantics(session, prepare_fixture(f), old)
    assert result["full_mapping_status"] == "MAPPED"
    sides = [
        row
        for row in result["full_signature"]["events"]
        if row.get("role") == "executed_side_calculation_not_in_final_dependency_closure"
    ]
    assert len(sides) == 1 and sides[0]["inferred_cognitive_intent"] is None
    assert sides[0]["implicit_revision"] is False
    assert not result["full_signature"]["revision_edges"]


def test_unknown_failure_domain_remains_pending_not_blanket_pass():
    f, session, old = session_with(
        [
            {
                "tool": "calculate",
                "arguments": {"expression": "unknown", "variables": {}, "unit": "million USD"},
            }
        ]
    )
    result = assess_new_semantics(session, prepare_fixture(f), old)
    assert result["financial_valid"]
    assert result["full_mapping_status"] == "PENDING_REVIEW"
    assert any(
        "unknown_failed_tool_execution_semantics" in reason
        for reason in result["full_mapping_pending_reasons"]
    )
    assert result["full_class"] is None


def test_no_final_not_rescued_by_new_representation():
    f, session, old = session_with(final=False)
    result = assess_new_semantics(session, prepare_fixture(f), old)
    assert not result["financial_valid"] and result["full_class"] is None
    assert result["reason"] == old["reason"] == "no_final"


def test_prepared_mapping_hash_and_original_assessment_are_checked():
    f, session, old = session_with()
    prepared = prepare_fixture(f)
    corrupted = copy.deepcopy(prepared)
    corrupted["enriched_native_bindings"]["p"]["record"]["val"] += 1
    with pytest.raises(ValueError, match="frozen_private_source_boundary"):
        assess_new_semantics(session, corrupted)
    with pytest.raises(ValueError, match="original_regression_unchanged"):
        assess_new_semantics(session, prepared, {**old, "financial_valid": False})


def test_json_public_sources_all_retained_and_no_gold_used_by_preparation():
    f = fixture()
    before = copy.deepcopy(f)
    result = prepare_fixture(f)
    f["bundle"]["private"]["answer_exact"] = "999999999999"
    other = prepare_fixture(f)
    assert result["source_boundary"] == other["source_boundary"]
    assert result["messages"] == before["messages"]
    assert result["source_boundary"]["counts"] == {"ORIGINAL_JSON_BOUND": 6}
    assert result["source_boundary"]["added_occurrences"] == []
    assert result["source_boundary"]["unknown_sources_removed"] is False
