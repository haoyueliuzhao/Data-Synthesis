from __future__ import annotations

from typing import Any

import pytest

from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping import (
    ValidOnlyStateMapperContract,
    authorize_independently_valid_trajectory_mapping,
    make_valid_only_state_mapper_contract,
    map_independently_valid_trajectory_to_state,
)
from trusted_synthesis.hashing import canonical_hash


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


def _contract() -> ValidOnlyStateMapperContract:
    return make_valid_only_state_mapper_contract(
        qualified_verifier_contract_id="verifier-contract",
        mapper_implementation_id="mapper-implementation",
        mapper_version="mapper.v1",
    )


def test_valid_only_mapper_invokes_the_mapper_once_after_authorization() -> None:
    calls: list[str] = []

    def mapper(authorization: object) -> dict[str, str]:
        calls.append(type(authorization).__name__)
        return {"state_id": "state-1"}

    result = map_independently_valid_trajectory_to_state(
        trajectory_id="trajectory-1",
        qualified_validity_report=_qualified_report(),
        mapper_contract=_contract(),
        omega_task_context_id="omega-1",
        raw_observation_prefix_hash="prefix-1",
        mapper=mapper,
    )

    assert calls == ["ValidOnlyMappingAuthorization"]
    assert result.mapper_invocation_count == 1
    assert result.mapped_state == {"state_id": "state-1"}
    assert result.authorization.qualified_validity is True
    assert result.authorization.state_mapping_eligible is True


@pytest.mark.parametrize("valid", [False, None])
def test_valid_only_mapper_rejects_nonqualified_reports_before_callback(
    valid: bool | None,
) -> None:
    calls = 0

    def mapper(_: object) -> str:
        nonlocal calls
        calls += 1
        return "state"

    with pytest.raises(ValueError, match="non-Qualified trajectory"):
        map_independently_valid_trajectory_to_state(
            trajectory_id="trajectory-1",
            qualified_validity_report=_qualified_report(valid=valid),
            mapper_contract=_contract(),
            omega_task_context_id="omega-1",
            raw_observation_prefix_hash="prefix-1",
            mapper=mapper,
        )
    assert calls == 0


def test_valid_only_mapper_rejects_crossed_trajectory_and_verifier_contract() -> None:
    report = _qualified_report()
    with pytest.raises(ValueError, match="another trajectory"):
        authorize_independently_valid_trajectory_mapping(
            trajectory_id="trajectory-2",
            qualified_validity_report=report,
            mapper_contract=_contract(),
            omega_task_context_id="omega-1",
            raw_observation_prefix_hash="prefix-1",
        )

    other = make_valid_only_state_mapper_contract(
        qualified_verifier_contract_id="other-verifier",
        mapper_implementation_id="mapper-implementation",
        mapper_version="mapper.v1",
    )
    with pytest.raises(ValueError, match="Verifier Contracts"):
        authorize_independently_valid_trajectory_mapping(
            trajectory_id="trajectory-1",
            qualified_validity_report=report,
            mapper_contract=other,
            omega_task_context_id="omega-1",
            raw_observation_prefix_hash="prefix-1",
        )


def test_valid_only_mapper_contract_rejects_missing_assignment_binding() -> None:
    contract = _contract()
    payload = contract.model_dump(mode="python")
    payload["required_assignment_bindings"] = contract.required_assignment_bindings[:-1]
    provisional = ValidOnlyStateMapperContract.model_construct(**payload)
    payload["contract_id"] = canonical_hash(
        provisional.model_dump(mode="json", exclude={"contract_id"}),
        prefix="valid_only_state_mapper_contract:",
    )
    with pytest.raises(ValueError, match="bindings are incomplete"):
        ValidOnlyStateMapperContract.model_validate(payload)
