from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    make_qualified_verifier_input_binding_v2,
    make_valid_only_state_mapper_contract_v2,
    map_independently_valid_trajectory_to_state_v2,
)
from trusted_synthesis.hashing import canonical_hash


class Trajectory(BaseModel):
    model_config = ConfigDict(frozen=True)

    trajectory_id: str
    trajectory_semantic_content_hash: str
    trajectory_bound_artifact_hash: str
    raw_observation_prefix_hash: str
    final_result: dict[str, Any]


def _trajectory(result: str) -> Trajectory:
    semantic = strict_canonical_hash(
        {"final_result": {"value": result}},
        prefix="trajectory-semantic:",
    )
    return Trajectory(
        trajectory_id="trajectory-1",
        trajectory_semantic_content_hash=semantic,
        trajectory_bound_artifact_hash=strict_canonical_hash(
            {"trajectory_id": "trajectory-1", "semantic": semantic},
            prefix="trajectory-bound:",
        ),
        raw_observation_prefix_hash="prefix-1",
        final_result={"value": result},
    )


def _qualified_report(*, valid: bool | None = True) -> QualifiedTrajectoryValidityReport:
    values: dict[str, Any] = {
        "verifier_contract_id": "verifier-contract",
        "trajectory_id": "trajectory-1",
        "eligibility_id": "eligibility-1",
        "base_report_id": "base-report-1",
        "mechanism_report_id": "mechanism-report-1",
        "valid": valid,
        "state_mapping_eligible": valid is True,
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


def _contract():
    return make_valid_only_state_mapper_contract_v2(
        qualified_verifier_contract_id="verifier-contract",
        mapper_implementation_id="mapper-v2",
        semantic_policy_id="semantic-policy-v2",
    )


def test_v2_core_passes_the_exact_bound_trajectory_to_mapper() -> None:
    trajectory = _trajectory("1")
    report = _qualified_report()
    binding = make_qualified_verifier_input_binding_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        raw_execution_artifact_hash="raw-sha256",
        qualified_verifier_input_hash="verifier-input-hash",
    )
    seen: list[Trajectory] = []

    result = map_independently_valid_trajectory_to_state_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        verifier_input_binding=binding,
        mapper_contract=_contract(),
        omega_task_context_id="omega-1",
        raw_execution_artifact_hash="raw-sha256",
        mapper=lambda _authorization, bound: seen.append(bound) or {"state_id": "state-1"},
    )

    assert seen == [trajectory]
    assert result.trajectory_passed_to_mapper_by_core is True
    assert result.authorization.trajectory_semantic_content_hash == (
        trajectory.trajectory_semantic_content_hash
    )


def test_v2_core_rejects_same_id_with_different_content_before_callback() -> None:
    original = _trajectory("1")
    changed = _trajectory("2")
    report = _qualified_report()
    binding = make_qualified_verifier_input_binding_v2(
        trajectory=original,
        qualified_validity_report=report,
        raw_execution_artifact_hash="raw-sha256",
        qualified_verifier_input_hash="verifier-input-hash",
    )
    calls = 0

    def mapper(_authorization: object, _trajectory: object) -> str:
        nonlocal calls
        calls += 1
        return "state"

    with pytest.raises(ValueError, match="content binding"):
        map_independently_valid_trajectory_to_state_v2(
            trajectory=changed,
            qualified_validity_report=report,
            verifier_input_binding=binding,
            mapper_contract=_contract(),
            omega_task_context_id="omega-1",
            raw_execution_artifact_hash="raw-sha256",
            mapper=mapper,
        )
    assert calls == 0


def test_v2_core_rejects_raw_hash_or_nonqualified_report_before_callback() -> None:
    trajectory = _trajectory("1")
    report = _qualified_report()
    binding = make_qualified_verifier_input_binding_v2(
        trajectory=trajectory,
        qualified_validity_report=report,
        raw_execution_artifact_hash="raw-sha256",
        qualified_verifier_input_hash="verifier-input-hash",
    )
    with pytest.raises(ValueError, match="content binding"):
        map_independently_valid_trajectory_to_state_v2(
            trajectory=trajectory,
            qualified_validity_report=report,
            verifier_input_binding=binding,
            mapper_contract=_contract(),
            omega_task_context_id="omega-1",
            raw_execution_artifact_hash="other-raw",
            mapper=lambda _authorization, _trajectory: "state",
        )

    invalid = _qualified_report(valid=False)
    invalid_binding = make_qualified_verifier_input_binding_v2(
        trajectory=trajectory,
        qualified_validity_report=invalid,
        raw_execution_artifact_hash="raw-sha256",
        qualified_verifier_input_hash="verifier-input-hash",
    )
    with pytest.raises(ValueError, match="non-Qualified"):
        map_independently_valid_trajectory_to_state_v2(
            trajectory=trajectory,
            qualified_validity_report=invalid,
            verifier_input_binding=invalid_binding,
            mapper_contract=_contract(),
            omega_task_context_id="omega-1",
            raw_execution_artifact_hash="raw-sha256",
            mapper=lambda _authorization, _trajectory: "state",
        )
