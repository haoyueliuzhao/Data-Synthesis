from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    ValidOnlyStateMapperContractV2,
    make_qualified_verifier_input_binding_v2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    PublicTrajectoryActionV2,
    make_empirical_route_signature_v2,
    make_experimental_condition_v2,
    make_public_trajectory_action_v2,
    make_public_trajectory_projection_v2,
    map_independently_valid_public_trajectory_to_state_v2,
)
from trusted_synthesis.core.trajectory.reference_empirical_state_mapping_v2 import (
    reference_map_public_trajectory_v2,
)
from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class GoldStatePairResult(FrozenModel):
    fixture_name: str = Field(min_length=1)
    expected_relation: Literal["merge", "split"]
    left_state_id: str = Field(min_length=1)
    right_state_id: str = Field(min_length=1)
    production_relation_passed: Literal[True] = True
    independent_reference_match_count: Literal[2] = 2


class MapperV2GoldFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    fixture_count: Literal[5] = 5
    merge_fixture_count: Literal[2] = 2
    split_fixture_count: Literal[3] = 3
    production_pass_count: Literal[5] = 5
    independent_reference_state_match_count: Literal[10] = 10
    fixtures: tuple[GoldStatePairResult, ...] = Field(min_length=5, max_length=5)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> MapperV2GoldFixtureAudit:
        names = tuple(item.fixture_name for item in self.fixtures)
        if (
            names != tuple(sorted(set(names)))
            or sum(item.expected_relation == "merge" for item in self.fixtures) != 2
            or sum(item.expected_relation == "split" for item in self.fixtures) != 3
        ):
            raise ValueError("Mapper v2 Gold fixture partition changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_mapper_v2_gold_fixture_audit:",
        ):
            raise ValueError("Mapper v2 Gold fixture identity changed")
        return self


def _report(trajectory_id: str, verifier_contract_id: str) -> QualifiedTrajectoryValidityReport:
    values: dict[str, Any] = {
        "verifier_contract_id": verifier_contract_id,
        "trajectory_id": trajectory_id,
        "eligibility_id": f"{trajectory_id}:eligibility",
        "base_report_id": f"{trajectory_id}:base",
        "mechanism_report_id": f"{trajectory_id}:mechanism",
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


def _action(
    policy: EmpiricalStateSemanticPolicyV2,
    *,
    index: int,
    decision: str,
    tool: str | None,
    arguments: Mapping[str, Any] | None = None,
    status: str | None = None,
    error_code: str | None = None,
    result: Mapping[str, Any] | None = None,
    evidence_ids: Sequence[str] = (),
) -> PublicTrajectoryActionV2:
    return make_public_trajectory_action_v2(
        action_index=index,
        decision_kind=decision,
        action_kind="emit_final" if tool is None else "call_tool",
        tool_id=tool,
        arguments=arguments,
        observation_status=status,
        error_code=error_code,
        observation_result=result,
        evidence_ids=evidence_ids,
        reference_policy=policy.typed_reference_policy,
    )


def _acquisition(
    policy: EmpiricalStateSemanticPolicyV2,
    index: int,
    subject: str,
    *,
    failed: bool = False,
) -> PublicTrajectoryActionV2:
    evidence = f"evidence:{subject}"
    return _action(
        policy,
        index=index,
        decision="acquire_public_input",
        tool="query_structured_fact",
        arguments={"subject_alias": subject},
        status="failed" if failed else "succeeded",
        error_code="typed_selector_requires_refinement" if failed else None,
        result=(
            {"retry_contract": "refine"}
            if failed
            else {"evidence_ids": [evidence], "facts": [{"evidence_id": evidence}]}
        ),
        evidence_ids=() if failed else (evidence,),
    )


def _verification(
    policy: EmpiricalStateSemanticPolicyV2,
    index: int,
) -> PublicTrajectoryActionV2:
    return _action(
        policy,
        index=index,
        decision="verify_terminal_operation",
        tool="cross_check_evidence",
        arguments={"claim_or_result": {}, "evidence_ids": ["evidence:A"]},
        status="succeeded",
        result={"support": ["evidence:A"], "conflicts": [], "verified": True},
        evidence_ids=("evidence:A",),
    )


def _final(policy: EmpiricalStateSemanticPolicyV2, index: int) -> PublicTrajectoryActionV2:
    return _action(
        policy,
        index=index,
        decision="emit_final_answer",
        tool=None,
    )


def _reindex(actions: Sequence[PublicTrajectoryActionV2]) -> tuple[PublicTrajectoryActionV2, ...]:
    return tuple(
        item.model_copy(update={"action_index": index}) for index, item in enumerate(actions)
    )


def _map_fixture(
    *,
    fixture_id: str,
    actions: Sequence[PublicTrajectoryActionV2],
    raw_result: Mapping[str, Any],
    canonical_result: Mapping[str, Any],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
) -> tuple[str, str]:
    trajectory = make_public_trajectory_projection_v2(
        trajectory_id=fixture_id,
        terminal_disposition="completed_model_endpoint",
        actions=_reindex(actions),
        raw_final_result=raw_result,
        canonical_result=canonical_result,
        answer_semantic_schema_id="gold-answer-schema",
        reference_projection_policy_id=semantic_policy.reference_projection_policy_id,
        final_citations=("evidence:A",),
    )
    report = _report(fixture_id, mapper_contract.qualified_verifier_contract_id)
    raw_hash = strict_canonical_hash(trajectory, prefix="gold-raw:")
    binding = make_qualified_verifier_input_binding_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        raw_execution_artifact_hash=raw_hash,
        qualified_verifier_input_hash=strict_canonical_hash(
            {
                "trajectory": trajectory.trajectory_bound_artifact_hash,
                "canonical_result": trajectory.canonical_result_semantics_hash,
            },
            prefix="gold-verifier-input:",
        ),
    )
    condition = make_experimental_condition_v2(
        sampling_mode="reachability_unconditional",
        public_condition_id=None,
        requested_path_id=None,
        requested_path_strategy=None,
        static_path_catalog_id="gold-path-catalog",
    )
    assignment = map_independently_valid_public_trajectory_to_state_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        verifier_input_binding=binding,
        mapper_contract=mapper_contract,
        omega_task_context_id="gold-omega-context",
        experimental_condition=condition,
        empirical_route_signature=make_empirical_route_signature_v2(trajectory),
        runtime_operation_aliases={},
        semantic_policy=semantic_policy,
        raw_execution_artifact_hash=raw_hash,
    )
    reference = reference_map_public_trajectory_v2(
        trajectory=trajectory,
        omega_task_context_id="gold-omega-context",
        runtime_operation_aliases={},
        semantic_policy=semantic_policy,
    )
    if reference.structural_state != assignment.structural_state:
        raise ValueError(f"Gold fixture Reference Mapper mismatch: {fixture_id}")
    return assignment.structural_state_id, reference.structural_state.state_id


def build_mapper_v2_gold_fixture_audit(
    *,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
) -> MapperV2GoldFixtureAudit:
    acquisition_a = _acquisition(semantic_policy, 0, "A")
    acquisition_b = _acquisition(semantic_policy, 1, "B")
    failure = _acquisition(semantic_policy, 0, "A", failed=True)
    verification = _verification(semantic_policy, 0)
    final = _final(semantic_policy, 0)
    pairs: tuple[
        tuple[
            str,
            Literal["merge", "split"],
            Sequence[PublicTrajectoryActionV2],
            Sequence[PublicTrajectoryActionV2],
            Mapping[str, Any],
            Mapping[str, Any],
        ],
        ...,
    ] = (
        (
            "merge_independent_acquisition_order",
            "merge",
            (acquisition_a, acquisition_b, final),
            (acquisition_b, acquisition_a, final),
            {"value": "1"},
            {"value": "1"},
        ),
        (
            "merge_verifier_canonical_numeric_representation",
            "merge",
            (acquisition_a, final),
            (acquisition_a, final),
            {"value": "1.0"},
            {"value": 1.0},
        ),
        (
            "split_failure_revision_order",
            "split",
            (failure, acquisition_a, final),
            (acquisition_a, failure, final),
            {"value": "1"},
            {"value": "1"},
        ),
        (
            "split_verification_relative_order",
            "split",
            (verification, acquisition_a, final),
            (acquisition_a, verification, final),
            {"value": "1"},
            {"value": "1"},
        ),
        (
            "split_stopping_relative_order",
            "split",
            (final, acquisition_a),
            (acquisition_a, final),
            {"value": "1"},
            {"value": "1"},
        ),
    )
    results: list[GoldStatePairResult] = []
    reference_matches = 0
    for name, relation, left_actions, right_actions, left_raw, right_raw in pairs:
        canonical = {"value": "1"}
        left_state, left_reference = _map_fixture(
            fixture_id=f"gold:{name}:left",
            actions=left_actions,
            raw_result=left_raw,
            canonical_result=canonical,
            semantic_policy=semantic_policy,
            mapper_contract=mapper_contract,
        )
        right_state, right_reference = _map_fixture(
            fixture_id=f"gold:{name}:right",
            actions=right_actions,
            raw_result=right_raw,
            canonical_result=canonical,
            semantic_policy=semantic_policy,
            mapper_contract=mapper_contract,
        )
        reference_matches += int(left_state == left_reference) + int(right_state == right_reference)
        passed = left_state == right_state if relation == "merge" else left_state != right_state
        if not passed:
            raise ValueError(f"Mapper v2 Gold fixture failed: {name}")
        results.append(
            GoldStatePairResult(
                fixture_name=name,
                expected_relation=relation,
                left_state_id=left_state,
                right_state_id=right_state,
            )
        )
    ordered = tuple(sorted(results, key=lambda item: item.fixture_name))
    values = {"fixtures": ordered}
    provisional = MapperV2GoldFixtureAudit.model_construct(audit_id="pending", **values)
    if reference_matches != 10:
        raise ValueError("Mapper v2 Gold fixture Reference denominator changed")
    return MapperV2GoldFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_mapper_v2_gold_fixture_audit:",
        ),
        **values,
    )
