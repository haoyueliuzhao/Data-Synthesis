from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    make_qualified_verifier_input_binding_v2,
    make_valid_only_state_mapper_contract_v2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    PublicTrajectoryActionV2,
    make_empirical_route_signature_v2,
    make_empirical_state_semantic_policy_v2,
    make_experimental_condition_v2,
    make_public_trajectory_action_v2,
    make_public_trajectory_projection_v2,
    make_state_contrast_v2,
    map_independently_valid_public_trajectory_to_state_v2,
)
from trusted_synthesis.hashing import canonical_hash


def _policy() -> EmpiricalStateSemanticPolicyV2:
    return make_empirical_state_semantic_policy_v2(
        answer_semantics_contract_id="answer-semantics-contract",
        reference_projection_policy_id="reference-projection-policy",
        decimal_canonicalization_policy_id="decimal-canonicalization-policy",
    )


def _action(
    policy: EmpiricalStateSemanticPolicyV2,
    *,
    action_index: int,
    decision_kind: str,
    tool_id: str | None,
    arguments: Mapping[str, Any] | None = None,
    status: str | None = None,
    error_code: str | None = None,
    result: Mapping[str, Any] | None = None,
    evidence_ids: Sequence[str] = (),
    provenance_hashes: Sequence[str] = (),
) -> PublicTrajectoryActionV2:
    return make_public_trajectory_action_v2(
        action_index=action_index,
        decision_kind=decision_kind,
        action_kind="emit_final" if tool_id is None else "call_tool",
        tool_id=tool_id,
        arguments=arguments,
        observation_status=status,
        error_code=error_code,
        observation_result=result,
        evidence_ids=evidence_ids,
        provenance_hashes=provenance_hashes,
        reference_policy=policy.typed_reference_policy,
    )


def _acquisition(
    policy: EmpiricalStateSemanticPolicyV2,
    index: int,
    subject: str,
    evidence_id: str,
    *,
    status: str = "succeeded",
    error_code: str | None = None,
) -> PublicTrajectoryActionV2:
    result: dict[str, Any]
    if status == "succeeded":
        result = {
            "evidence_ids": [evidence_id],
            "facts": [{"evidence_id": evidence_id, "provenance_hash": f"p:{subject}"}],
        }
    else:
        result = {"retry_contract": "refine"}
    return _action(
        policy,
        action_index=index,
        decision_kind="acquire_public_input",
        tool_id="query_structured_fact",
        arguments={"subject_alias": subject},
        status=status,
        error_code=error_code,
        result=result,
        evidence_ids=(evidence_id,) if status == "succeeded" else (),
        provenance_hashes=(f"p:{subject}",) if status == "succeeded" else (),
    )


def _reindex(actions: Sequence[PublicTrajectoryActionV2]) -> tuple[PublicTrajectoryActionV2, ...]:
    return tuple(
        item.model_copy(update={"action_index": index}) for index, item in enumerate(actions)
    )


def _base_actions(
    policy: EmpiricalStateSemanticPolicyV2,
    *,
    reverse_acquisitions: bool = False,
    evidence_order: tuple[str, str] = ("evidence:a", "evidence:b"),
) -> tuple[PublicTrajectoryActionV2, ...]:
    acquisitions = [
        _acquisition(policy, 0, "A", "evidence:a"),
        _acquisition(policy, 1, "B", "evidence:b"),
    ]
    if reverse_acquisitions:
        acquisitions.reverse()
    calculator = _action(
        policy,
        action_index=2,
        decision_kind="execute_public_operation",
        tool_id="calculator",
        arguments={
            "operands": [
                {"evidence_id": "evidence:a"},
                {"evidence_id": "evidence:b"},
            ],
            "operator": "subtract",
            "parameters": {},
        },
        status="succeeded",
        result={"operation_hash": "hash", "result": {"operation_ref": "runtime:result"}},
        evidence_ids=evidence_order,
    )
    verification = _action(
        policy,
        action_index=3,
        decision_kind="verify_terminal_operation",
        tool_id="cross_check_evidence",
        arguments={
            "claim_or_result": {"operation_ref": "runtime:result"},
            "evidence_ids": list(evidence_order),
        },
        status="succeeded",
        result={"support": list(reversed(evidence_order)), "conflicts": [], "verified": True},
        evidence_ids=evidence_order,
    )
    final = _action(
        policy,
        action_index=4,
        decision_kind="emit_final_answer",
        tool_id=None,
    )
    return _reindex((*acquisitions, calculator, verification, final))


def _qualified_report(trajectory_id: str) -> QualifiedTrajectoryValidityReport:
    values: dict[str, Any] = {
        "verifier_contract_id": "verifier-contract",
        "trajectory_id": trajectory_id,
        "eligibility_id": "eligibility-1",
        "base_report_id": "base-report-1",
        "mechanism_report_id": "mechanism-report-1",
        "valid": True,
        "state_mapping_eligible": True,
    }
    provisional = QualifiedTrajectoryValidityReport.model_construct(
        report_id="pending",
        **values,
    )
    return QualifiedTrajectoryValidityReport(
        report_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"report_id"}),
            prefix="prospective_qualified_trajectory_validity_report:",
        ),
        **values,
    )


def _map(
    *,
    actions: Sequence[PublicTrajectoryActionV2],
    raw_final_result: Mapping[str, Any],
    canonical_result: Mapping[str, Any],
    trajectory_id: str = "trajectory-1",
    final_citations: Sequence[str] = ("evidence:a", "evidence:b"),
):
    policy = _policy()
    trajectory = make_public_trajectory_projection_v2(
        trajectory_id=trajectory_id,
        terminal_disposition="completed_model_endpoint",
        actions=_reindex(actions),
        raw_final_result=raw_final_result,
        canonical_result=canonical_result,
        answer_semantic_schema_id="answer-schema",
        reference_projection_policy_id=policy.reference_projection_policy_id,
        final_citations=final_citations,
    )
    report = _qualified_report(trajectory_id)
    raw_hash = f"raw-sha256:{trajectory_id}"
    verifier_input_hash = strict_canonical_hash(
        {
            "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
            "canonical_result": trajectory.canonical_result,
            "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
        },
        prefix="qualified-verifier-input:",
    )
    binding = make_qualified_verifier_input_binding_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        raw_execution_artifact_hash=raw_hash,
        qualified_verifier_input_hash=verifier_input_hash,
    )
    contract = make_valid_only_state_mapper_contract_v2(
        qualified_verifier_contract_id="verifier-contract",
        mapper_implementation_id="mapper-v2",
        semantic_policy_id=policy.policy_id,
    )
    condition = make_experimental_condition_v2(
        sampling_mode="reachability_unconditional",
        public_condition_id=None,
        requested_path_id=None,
        requested_path_strategy=None,
        static_path_catalog_id="path-catalog",
    )
    route = make_empirical_route_signature_v2(trajectory)
    assignment = map_independently_valid_public_trajectory_to_state_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        verifier_input_binding=binding,
        mapper_contract=contract,
        omega_task_context_id="omega-context",
        experimental_condition=condition,
        empirical_route_signature=route,
        runtime_operation_aliases={"runtime:result": "operation:result"},
        semantic_policy=policy,
        raw_execution_artifact_hash=raw_hash,
    )
    return trajectory, assignment


def test_verifier_canonical_result_controls_state_while_raw_payload_remains_auditable() -> None:
    policy = _policy()
    actions = _base_actions(policy)
    left_trajectory, left = _map(
        actions=actions,
        raw_final_result={"difference": "0.224"},
        canonical_result={"difference": "0.224"},
        trajectory_id="trajectory-left",
    )
    right_trajectory, right = _map(
        actions=actions,
        raw_final_result={"difference": 0.224},
        canonical_result={"difference": "0.224"},
        trajectory_id="trajectory-right",
    )

    assert left_trajectory.raw_final_payload_hash != right_trajectory.raw_final_payload_hash
    assert (
        left_trajectory.trajectory_semantic_content_hash
        != right_trajectory.trajectory_semantic_content_hash
    )
    assert left.structural_state_id == right.structural_state_id
    assert left.canonical_result_semantics_hash == right.canonical_result_semantics_hash


def test_set_like_fields_and_independent_acquisition_order_do_not_split_state() -> None:
    policy = _policy()
    _, baseline = _map(
        actions=_base_actions(policy),
        raw_final_result={"value": "1"},
        canonical_result={"value": "1"},
    )
    _, reordered = _map(
        actions=_base_actions(
            policy,
            reverse_acquisitions=True,
            evidence_order=("evidence:b", "evidence:a"),
        ),
        raw_final_result={"value": "1"},
        canonical_result={"value": "1"},
        trajectory_id="trajectory-reordered",
    )

    assert baseline.structural_state_id == reordered.structural_state_id
    assert baseline.experimental_condition_id == reordered.experimental_condition_id
    assert baseline.empirical_route_signature_id != reordered.empirical_route_signature_id


def test_failure_verification_and_final_relative_order_split_states() -> None:
    policy = _policy()
    success = _acquisition(policy, 0, "A", "evidence:a")
    failure = _acquisition(
        policy,
        1,
        "A",
        "evidence:a",
        status="failed",
        error_code="typed_selector_requires_refinement",
    )
    verification = _action(
        policy,
        action_index=2,
        decision_kind="verify_terminal_operation",
        tool_id="cross_check_evidence",
        arguments={"claim_or_result": {}, "evidence_ids": ["evidence:a"]},
        status="succeeded",
        result={"support": ["evidence:a"], "conflicts": [], "verified": True},
        evidence_ids=("evidence:a",),
    )
    final = _action(
        policy,
        action_index=3,
        decision_kind="emit_final_answer",
        tool_id=None,
    )

    sequences = (
        (failure, success, verification, final),
        (success, failure, verification, final),
        (failure, verification, success, final),
        (failure, success, final, verification),
    )
    states = {
        _map(
            actions=sequence,
            raw_final_result={"value": "1"},
            canonical_result={"value": "1"},
            trajectory_id=f"trajectory-temporal-{index}",
            final_citations=("evidence:a",),
        )[1].structural_state_id
        for index, sequence in enumerate(sequences)
    }

    assert len(states) == len(sequences)


def test_typed_reference_schema_ignores_string_heuristics_and_unknown_tools_fail_closed() -> None:
    policy = _policy()
    action = _action(
        policy,
        action_index=0,
        decision_kind="acquire_public_input",
        tool_id="query_structured_fact",
        arguments={"evidence_id_hint": "evidence:not-a-schema-reference"},
        status="succeeded",
        result={"query_hash": "operation:not-a-reference"},
    )
    assert action.typed_references.consumed_evidence_refs == ()
    assert action.typed_references.produced_operation_refs == ()

    with pytest.raises(ValueError, match="no schema"):
        _action(
            policy,
            action_index=0,
            decision_kind="acquire_public_input",
            tool_id="unregistered_tool",
        )


def test_typed_lineage_namespaces_and_state_contrast_explain_differences() -> None:
    policy = _policy()
    evidence_action = _acquisition(policy, 0, "A", "same")
    final = _action(
        policy,
        action_index=1,
        decision_kind="emit_final_answer",
        tool_id=None,
    )
    _, with_citation = _map(
        actions=(evidence_action, final),
        raw_final_result={"value": "1"},
        canonical_result={"value": "1"},
        trajectory_id="trajectory-with-citation",
        final_citations=("same",),
    )
    _, without_citation = _map(
        actions=(evidence_action, final),
        raw_final_result={"value": "1"},
        canonical_result={"value": "1"},
        trajectory_id="trajectory-without-citation",
        final_citations=(),
    )

    entries = {
        (item.lineage_kind, item.value) for item in with_citation.structural_state.typed_lineage
    }
    assert ("citation", "same") in entries
    assert ("evidence", "same") in entries
    contrast = make_state_contrast_v2(
        with_citation.structural_state,
        without_citation.structural_state,
    )
    assert "typed_evidence_lineage" in contrast.differing_dimensions
    assert contrast.minimal_difference_witness["typed_evidence_lineage"]
