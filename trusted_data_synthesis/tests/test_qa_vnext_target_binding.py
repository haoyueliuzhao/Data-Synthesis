"""New pure controls only; never reload, grade, or generate historical models."""

from copy import deepcopy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_target_binding.cases import validate_evidence
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    CASE_KEYS,
    OUTPUT,
    TASKS,
    ZeroModelGuard,
    read_phase,
    record,
    seal,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.failure_structure import (
    DIMENSIONS,
    summarize,
    vector,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.ledger import (
    SPECS,
    source_leaves,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.policy import (
    policy,
    source_claim,
    target_binding,
)


def binding(**overrides):
    values = {
        "local_relation": "PASS",
        "alignment": "ALIGNED",
        "public_scope_match": "PASS",
        "registered_scope_match": "PASS",
        "final_chain_completes_public_target": "PASS",
    }
    return target_binding(**{**values, **overrides})


def old_row():
    fields = (
        "formula_applicability",
        "variable_correspondence",
        "unit_handling",
        "publication_alignment",
        "final_answer_consistency",
    )
    return {
        "id": "row:fixture",
        "review_id": "fixture",
        "task_key": "SYNTHETIC",
        "phase": "dev",
        "variant": "pi0_11",
        "group": "fixture",
        "actual_calculations": 1,
        "model_requests": 2,
        "tool_calls": 1,
        "semantic_review": {k: {"status": "PASS"} for k in fields},
        "qualification": {
            "id": "qualification:fixture",
            "task_answer_status": "PASS",
            "delivery_status": "FINAL_DELIVERED",
            "complete_verifiable_trajectory": True,
            "trace_status": "PASS",
            "original_calculation_quantity": {"call_id": "tool:1"},
            "actual_Final_amount_consistency": {"status": "PASS"},
            "trace_checks": {
                "first_three_have_pre_or_same_call_evidence": True,
                "calculation_quantity_interpretation_established": True,
                "selected_tool_result_matches_publication": True,
                "explicit_Final_result_reference_consistent": True,
            },
        },
    }


def packet():
    return {
        "all_generated_public_responses": [
            {"response_index": 0, "content": '{"message":"Example only"}'}
        ],
        "recorded_public_system": "A nested value and source association is a declaration.",
        "public_document": {
            "question": "Which period?",
            "segments": {"p0": {"text": "Public source text."}},
        },
    }


def test_exact_bounded_inputs():
    assert set(SPECS) == set(TASKS)
    assert len(TASKS) == 36 and len(CASE_KEYS) == len(set(CASE_KEYS)) == 18
    assert {key[0] for key in CASE_KEYS} == {"C04", "C08", "C09"}
    assert {key[1] for key in CASE_KEYS} == {"pi0", "minus_D"}


def test_local_relation_does_not_override_requested_period():
    result = binding(public_scope_match="FAIL", registered_scope_match="FAIL")
    assert result["local_relation_validity"] == "PASS"
    assert result["public_task_applicability"] == "FAIL"


@pytest.mark.parametrize("alignment", ["PUBLIC_UNDERSPECIFIED", "NEED_SOURCE_CHECK"])
@pytest.mark.parametrize("private_status", ["PASS", "FAIL", "UNDETERMINED"])
def test_private_target_cannot_resolve_public_ambiguity(alignment, private_status):
    result = binding(alignment=alignment, registered_scope_match=private_status)
    assert result["public_task_applicability"] == "UNDETERMINED"
    assert not result["registered_reference_eligible_for_prospective_primary_score"]


def test_direct_public_mismatch_is_not_a_private_reference_repair():
    result = binding(alignment="PRIVATE_MISMATCH", registered_scope_match="FAIL")
    assert result["public_task_applicability"] == "PASS"
    assert not result["registered_reference_eligible_for_prospective_primary_score"]


def test_wrong_object_can_fail_even_with_another_ambiguous_axis():
    assert (
        binding(alignment="PUBLIC_UNDERSPECIFIED", public_scope_match="FAIL")[
            "public_task_applicability"
        ]
        == "FAIL"
    )


def test_correct_intermediate_then_completed_target_is_allowed():
    # This flag represents an evidenced completed chain; no intermediate-equals-target gate exists.
    assert (
        binding(final_chain_completes_public_target="PASS")["public_task_applicability"] == "PASS"
    )
    assert (
        binding(final_chain_completes_public_target="FAIL")["public_task_applicability"] == "FAIL"
    )


@pytest.mark.parametrize(
    "field", ["local_relation", "public_scope_match", "final_chain_completes_public_target"]
)
def test_unknown_binding_stays_unknown(field):
    assert binding(**{field: "UNDETERMINED"})["public_task_applicability"] == "UNDETERMINED"


@pytest.mark.parametrize("consumed", [False, True])
def test_actual_direct_false_claim_not_erased_by_nonconsumption(consumed):
    result = source_claim(
        role="DIRECT_SOURCE_VALUE", current=True, source_value_equal=False, consumed=consumed
    )
    assert result["status"] == "FAIL"


def test_derived_source_does_not_require_equal_source_number():
    result = source_claim(
        role="DERIVED_FROM_SOURCES",
        current=True,
        source_value_equal=False,
        derivation_supported=True,
    )
    assert result["status"] == "PASS"


def test_general_reference_is_not_a_direct_value_assertion():
    result = source_claim(
        role="GENERAL_REFERENCE", current=True, source_value_equal=False, reference_relevant=True
    )
    assert result["status"] == "PASS"


def test_flat_ambiguous_fields_do_not_choose_a_role():
    result = source_claim(role="UNRESOLVED", current=True, source_value_equal=False, consumed=False)
    assert result["status"] == "UNDETERMINED"


def test_claim_withdrawal_needs_support():
    with pytest.raises(ValueError, match="withdrawal"):
        source_claim(role="DIRECT_SOURCE_VALUE", current=False, source_value_equal=False)
    assert (
        source_claim(
            role="DIRECT_SOURCE_VALUE",
            current=False,
            source_value_equal=False,
            withdrawal_supported=True,
        )["status"]
        == "NOT_CURRENT"
    )


@pytest.mark.parametrize(
    "role", ["DIRECT_SOURCE_VALUE", "DERIVED_FROM_SOURCES", "GENERAL_REFERENCE"]
)
def test_unestablished_claim_support_is_unknown(role):
    assert source_claim(role=role, current=True)["status"] == "UNDETERMINED"


def test_invalid_role_is_not_silently_general_reference():
    with pytest.raises(ValueError):
        source_claim(role="ADJACENT_FIELDS_THEREFORE_DIRECT", current=True)


def test_saved_vector_does_not_mutate_old_grade():
    row = old_row()
    original = deepcopy(row)
    result = vector(row)
    assert row == original and list(result["conditions"]) == list(DIMENSIONS)
    assert result["original_complete_trajectory_PASS"]
    assert result["new_semantic_judgments"] == 0


def test_saved_single_failure_and_joint_unknown_partition():
    one = old_row()
    one["semantic_review"]["variable_correspondence"]["status"] = "FAIL"
    one["qualification"].update(complete_verifiable_trajectory=False, trace_status="FAIL")
    unknown = deepcopy(one)
    unknown["qualification"]["task_answer_status"] = "UNDETERMINED"
    first, second = vector(one), vector(unknown)
    assert first["exclusive_category"] == "ONLY_ONE_FAIL"
    assert first["nonPASS_conditions"] == ["source"]
    assert second["exclusive_category"] == "INFORMATION_INSUFFICIENT"
    assert second["failed_conditions"] == ["source"]
    assert second["unknown_conditions"] == ["quantity"]
    summary = summarize([first, second])
    assert summary["information_insufficient_with_known_FAIL"] == 1
    assert summary["pairwise_nonPASS_intersections_not_causal"]["quantity+source"] == 1


def test_multiple_known_failure_category():
    row = old_row()
    for field in ("formula_applicability", "variable_correspondence"):
        row["semantic_review"][field]["status"] = "FAIL"
    row["qualification"].update(complete_verifiable_trajectory=False, trace_status="FAIL")
    assert vector(row)["exclusive_category"] == "MULTIPLE_FAIL"


def test_remaining_temporal_gate_is_not_lost_in_seven_vector():
    row = old_row()
    row["qualification"]["trace_checks"]["first_three_have_pre_or_same_call_evidence"] = False
    row["qualification"].update(
        complete_verifiable_trajectory=False, trace_status="NOT_ESTABLISHED"
    )
    result = vector(row)
    assert result["exclusive_category"] == "ALL_SEVEN_PASS"
    assert summarize([result])["all_seven_PASS_but_remaining_gate_not_PASS"] == 1


def test_corrupt_saved_grade_projection_stops():
    row = old_row()
    row["qualification"]["complete_verifiable_trajectory"] = False
    with pytest.raises(ValueError, match="projection"):
        vector(row)


def test_no_Final_does_not_become_PASS():
    row = old_row()
    row["qualification"].update(
        delivery_status="NO_FINAL",
        complete_verifiable_trajectory=False,
        trace_status="NOT_ESTABLISHED",
    )
    result = vector(row)
    assert result["conditions"]["Final"] == "NOT_ESTABLISHED"
    assert result["original_Final_consistency_status"] == "PASS"


@pytest.mark.parametrize(
    "evidence",
    [
        {"kind": "response", "response_index": 0, "quote": "Example only"},
        {"kind": "source", "segment_id": "p0", "quote": "Public source"},
        {"kind": "question", "quote": "Which period?"},
        {"kind": "contract", "quote": "nested value and source"},
    ],
)
def test_evidence_matches_original_kind(evidence):
    validate_evidence(packet(), [evidence])


def test_reference_or_proposed_question_cannot_fill_public_evidence():
    for evidence in (
        {"kind": "private_reference", "quote": "Example only"},
        {"kind": "question", "quote": "A clarified future period"},
        {"kind": "response", "response_index": 1, "quote": "Example only"},
    ):
        with pytest.raises(ValueError):
            validate_evidence(packet(), [evidence])


def test_phase_is_exclusive_and_byte_bound(tmp_path):
    payload = record("test_fixture", x=1)
    seal(tmp_path, "fixture", {"report.json": payload})
    assert read_phase(tmp_path, "fixture")[0] == payload
    with pytest.raises(ValueError, match="write_once"):
        seal(tmp_path, "fixture", {"report.json": payload})
    (tmp_path / OUTPUT / "fixture/report.json").write_text("{}")
    with pytest.raises(ValueError, match="unchanged"):
        read_phase(tmp_path, "fixture")


def test_source_leaves_only_collects_registered_references():
    value = {
        "op": "add",
        "args": ["source:t1c1n0", {"op": "divide", "args": ["source:t2c1n0", "constant:100"]}],
    }
    assert source_leaves(value) == ["source:t1c1n0", "source:t2c1n0"]


@pytest.mark.parametrize(
    "event,args",
    [
        ("import", ("torch", None, None, None, None)),
        ("socket.connect", (None, ("example.invalid", 443))),
        ("subprocess.Popen", ("unused", [], None, None)),
        ("open", ("/tmp/not-this-audit-output.txt", "w", 0)),
        ("open", ("/tmp/.env", "r", 0)),
        ("os.mkdir", ("/tmp/not-this-audit-output", 0, -1)),
    ],
)
def test_guard_controls_are_event_simulations_not_real_model_or_network_calls(event, args):
    guard = ZeroModelGuard(Path("/tmp/audit-guard-fixture"))
    guard.active = True
    try:
        with pytest.raises(PermissionError):
            guard._event(event, args)
    finally:
        guard.active = False


def test_policy_preserves_old_primary_and_exposed_confirmation():
    result = policy()
    assert result["historical_scores_unchanged"]
    assert result["local_cases_cannot_be_spliced_into_a_new_252_session_primary_score"]
    assert result["previous_confirmation_tasks_are_now_known_historical_material"]
    assert result["new_model_budget"] == 0
    assert result["E_X2_DR_study_status"] == "PROPOSED_NOT_ACCEPTED_OR_FROZEN"
