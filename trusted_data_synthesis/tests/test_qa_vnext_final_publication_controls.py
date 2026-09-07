"""Authorized Final-ready local controls, never continuations of old sessions.

The twelve saved states are read from their sealed source cohort. All responses
constructed here are explicitly controls and are tested only by the unchanged
strict Final verifier through a non-Runtime admission view.
"""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    public_final_contract,
    public_final_schema,
    publish_final_contract,
    rejection_feedback,
)
from trusted_synthesis.domains.finance.qa_vnext.final_published_share_adapter import (
    FinalPublishedShareTaskAdapter,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import source as original_source
from trusted_synthesis.experiments.finance_qa_vnext_final_publication.controls import (
    FAMILIES,
    public_control_response,
    readonly_final_admission,
    run_controls,
)
from trusted_synthesis.experiments.finance_qa_vnext_final_publication.source import load_inputs
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender

ROOT = Path(__file__).resolve().parents[2]


def forbidden(*args, **kwargs):
    pytest.fail("Final controls may not scan sources, construct/execute Runtime, or requalify")


@pytest.fixture(scope="module")
def inputs():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(original_source, "load_sources", forbidden)
        patch.setattr(original_source, "source_report", forbidden)
        patch.setattr(original_source, "contamination_registry", forbidden)
        patch.setattr(original_source, "_witnesses", forbidden)
        patch.setattr(PublicQARuntime, "__init__", forbidden)
        patch.setattr(PublicQARuntime, "run", forbidden)
        patch.setattr(PublicQARuntime, "step", forbidden)
        patch.setattr(PublicQARuntime, "_consume", forbidden)
        patch.setattr(BoundShareTaskAdapter, "prepare", forbidden)
        patch.setattr(BoundShareTaskAdapter, "execute", forbidden)
        patch.setattr(qualification, "qualify_session", forbidden)
        patch.setattr(HttpxSender, "send", forbidden)
        yield load_inputs(ROOT)


@pytest.fixture(scope="module")
def result(inputs):
    return run_controls(inputs)


def test_frozen_sources_restore_without_scanning_and_keep_context_registry_verifier(inputs):
    assert tuple(inputs["sources"]) == tuple(inputs["adapters"]) == ("T01", "T02", "T03")
    checks = inputs["source_checks"]
    assert checks["task_context_evidence_registry_semantic_contracts_unchanged"]
    assert checks["source_adapter_and_verifier_files_byte_unchanged"]
    assert len(checks["protected_source_files"]) == 3
    assert FinalPublishedShareTaskAdapter.verify_final is BoundShareTaskAdapter.verify_final
    assert inputs["evaluation_policy"]["evaluation_readiness"] == "not_ready"
    assert inputs["evaluation_policy"]["clean_evaluation_task_count"] == 0
    assert inputs["source_report"]["contamination_registry"] == inputs["evaluation_policy"]
    assert checks["archive_scans"] == checks["source_reselection_calls"] == 0


def test_exactly_twelve_first_percent_accept_then_first_final_states_are_selected(inputs):
    ready = inputs["ready_states"]
    assert len(ready) == len({row["old_registration_id"] for row in ready}) == 12
    assert len({row["old_qualification_id"] for row in ready}) == 12
    assert Counter(row["prefix_support"] for row in ready) == {
        "disclosed_total": 7,
        "reconstructed_total": 5,
    }
    for row in ready:
        assert row["percent_accept_sequence"] < row["source_event_sequence"]
        assert row["request"]["state"]["id"] == row["source_state_id"]
        assert row["request"]["state"]["pending_observation"] is None
        assert row["percent_claim_id"] in row["request"]["final_claim_ids"]
        assert row["source_event_sha256"] and row["percent_accept_event_sha256"]
        proof = row["actual_prefix_support_proof"]
        assert not proof["support_inferred_from_action_count"]
        assert not proof["complete_session_success_claimed"]
        assert (proof["total_claim_id"] is not None) is (
            row["prefix_support"] == "reconstructed_total"
        )


def test_no_old_failure_or_request_is_rewritten_or_promoted(inputs, result):
    assert all(
        qual["status"] == "known_failure"
        and qual["qualified"] is False
        and qual["end_to_end_success"] is False
        for qual in inputs["old_qualifications"]
    )
    assert all("public_final_contract" not in row["request"] for row in inputs["ready_states"])
    assert result["old_qualified_count_before"] == result["old_qualified_count_after"] == 0
    assert result["old_registered_denominator"] == 12
    assert result["old_outcomes_unchanged"] and result["original_inputs_and_states_unchanged"]
    assert (
        result["old_sessions_resumed"]
        == result["old_finals_appended"]
        == result["new_model_samples"]
        == 0
    )
    assert result["training_rows_created"] == 0


def test_all_four_families_keep_original_acceptance_and_publication_is_read_only(inputs, result):
    assert result["passed"] and result["all_expected_outcomes"] and result["read_only"]
    assert result["control_count"] == len(result["rows"]) == 156
    assert result["family_count"] == 4 and set(result["family_counts"]) == set(FAMILIES)
    assert result["positive_control_count"] == 24 and result["negative_control_count"] == 132
    assert result["readonly_admission_evaluations"] == 312
    assert result["local_original_strict_verifier_calls"] == 264
    assert result["ready_state_ids"] == [row["id"] for row in inputs["ready_states"]]
    assert result["controls_by_task"] == {"T01": 52, "T02": 52, "T03": 52}
    for row in result["rows"]:
        assert row["original_admission"] == row["published_admission"]
        assert row["acceptance_unchanged"] and row["expected_outcome_observed"]
        assert row["control_evidence"] and not row["generated_model_sample"]
        assert not row["positive_training_candidate"] and not row["old_session_appended"]


def test_receiver_uses_only_public_paths_not_the_adapter_or_source_oracle(inputs, monkeypatch):
    ready = inputs["ready_states"][0]
    request = publish_final_contract(ready["request"])
    adapter = inputs["adapters"][ready["task_group"]]
    monkeypatch.setattr(adapter, "verify_final", forbidden)
    response = public_control_response(request)
    assert set(response["result"]) == {"value", "unit"}
    assert isinstance(response["result"]["value"], str)
    assert len(response["result"]["value"].partition(".")[2]) == 6
    assert response["result"]["unit"] == "percent"
    assert response["state_id"] == request["state"]["id"]
    assert response["answer_claim_id"] in request["final_claim_ids"]


def test_new_publication_changes_only_declared_request_fields(inputs):
    old = inputs["ready_states"][0]["request"]
    before = canonical_json_bytes(old)
    new = publish_final_contract(old)
    assert canonical_json_bytes(old) == before
    assert new["public_final_contract"] == public_final_contract()
    assert new["response_schemas"]["final"] == public_final_schema()
    for key, value in old.items():
        if key not in {"id", "response_schemas"}:
            assert new[key] == value
    assert {key: value for key, value in new["response_schemas"].items() if key != "final"} == {
        key: value for key, value in old["response_schemas"].items() if key != "final"
    }


@pytest.mark.parametrize(
    "case,category",
    [
        ("result_copied_metadata", "result_fields"),
        ("result_missing_unit", "result_fields"),
        ("json_number_not_string", "value_projection"),
        ("unquantized_claim_value", "value_projection"),
        ("wrong_unit_form", "unit"),
    ],
)
def test_result_boundary_negatives_stay_rejected_and_have_precise_public_category(
    result, case, category
):
    rows = [row for row in result["rows"] if row["case"] == case]
    assert len(rows) == 12
    for row in rows:
        assert row["published_admission"]["admitted"] is False
        assert row["published_admission"]["error_code"] == "admission.final_qa"
        assert row["published_admission"]["strict_verifier_calls"] == 1
        assert {
            item["category"] for item in row["feedback"]["public_diagnostic"]["violations"]
        } == {category}


def test_metadata_feedback_lists_all_extra_fields_not_a_repaired_answer(result):
    row = next(row for row in result["rows"] if row["case"] == "result_copied_metadata")
    diagnostic = row["feedback"]["public_diagnostic"]
    violation = diagnostic["violations"][0]
    assert violation["extra_fields"] == ["metric", "period", "subject"]
    assert violation["missing_fields"] == []
    assert not diagnostic["response_rewritten"] and not diagnostic["replacement_answer_supplied"]
    assert set(row["control_response"]["result"]) == {
        "value",
        "unit",
        "metric",
        "period",
        "subject",
    }


def test_support_swap_is_rejected_for_both_seven_disclosed_and_five_reconstructed_prefixes(result):
    rows = [
        row
        for row in result["rows"]
        if row["case"] == "disclosed_reconstructed_support_replacement"
    ]
    assert Counter(row["prefix_support"] for row in rows) == {
        "disclosed_total": 7,
        "reconstructed_total": 5,
    }
    for row in rows:
        violations = row["feedback"]["public_diagnostic"]["violations"]
        assert len(violations) == 1 and violations[0]["category"] == "actual_lineage"
        assert violations[0]["missing_ids"] and violations[0]["extra_ids"]
        assert not row["published_admission"]["admitted"]


def test_citation_duplicate_is_rejected_even_when_the_set_is_correct(result):
    rows = [row for row in result["rows"] if row["case"] == "duplicate_actual_citation"]
    for row in rows:
        violation = row["feedback"]["public_diagnostic"]["violations"][0]
        assert violation["missing_ids"] == violation["extra_ids"] == []
        assert len(violation["duplicate_ids"]) == 1
        assert not row["published_admission"]["admitted"]


@pytest.mark.parametrize(
    "case,code,category",
    [
        ("accepted_intermediate_not_answer", "admission.final_accepted_claim", "accepted_answer"),
        ("previous_state_not_current", "admission.current_state", "current_state"),
    ],
)
def test_current_claim_and_state_gates_do_not_run_or_relabel_final_qa(result, case, code, category):
    for row in (row for row in result["rows"] if row["case"] == case):
        assert row["published_admission"]["error_code"] == code
        assert row["published_admission"]["strict_verifier_calls"] == 0
        assert {
            item["category"] for item in row["feedback"]["public_diagnostic"]["violations"]
        } == {category}


def test_canonical_citation_reordering_is_still_accepted(result):
    rows = [row for row in result["rows"] if row["case"] == "legal_citation_set_order"]
    assert len(rows) == 12
    assert all(row["published_admission"]["admitted"] for row in rows)


def test_nonfinal_control_is_blocked_before_any_action_or_update_admission(inputs):
    ready = inputs["ready_states"][0]
    response = {"kind": "action"}
    with pytest.raises(ProtocolError, match="final_only_no_action_or_update"):
        readonly_final_admission(
            inputs["adapters"][ready["task_group"]], ready["request"], response
        )


def test_feedback_does_not_modify_response_or_call_the_source_verifier(inputs, monkeypatch):
    ready = inputs["ready_states"][0]
    request = publish_final_contract(ready["request"])
    response = public_control_response(request)
    response["result"]["value"] = float(response["result"]["value"])
    before = canonical_json_bytes(response)
    monkeypatch.setattr(BoundShareTaskAdapter, "verify_final", forbidden)
    feedback = rejection_feedback("admission.final_qa", request, response)
    assert canonical_json_bytes(response) == before
    assert feedback["public_diagnostic"]["source_answer_verifier_called"] is False
    assert feedback["public_diagnostic"]["financial_operations_executed"] is False
    assert feedback["public_diagnostic"]["replacement_answer_supplied"] is False


def test_readonly_admission_leaves_state_context_and_source_objects_unchanged(inputs):
    ready = inputs["ready_states"][0]
    adapter = inputs["adapters"][ready["task_group"]]
    request = publish_final_contract(ready["request"])
    response = public_control_response(request)
    before = canonical_json_bytes(
        {
            "request": request,
            "response": response,
            "context": adapter.context,
            "source": adapter.source.binding_record,
        }
    )
    outcome = readonly_final_admission(adapter, request, copy.deepcopy(response))
    assert outcome["admitted"] and not outcome["runtime_constructed"]
    assert (
        canonical_json_bytes(
            {
                "request": request,
                "response": response,
                "context": adapter.context,
                "source": adapter.source.binding_record,
            }
        )
        == before
    )
