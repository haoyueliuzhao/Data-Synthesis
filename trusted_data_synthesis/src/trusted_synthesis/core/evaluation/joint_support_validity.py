from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseTrajectoryValidityReport,
    BaseValidityChecks,
    MechanismId,
    MechanismQualificationReport,
    NoninterferenceArtifactBinding,
    QualifiedTrajectoryValidityReport,
    ValidityEligibility,
    make_base_validity_report,
    make_mechanism_qualification_report,
    make_qualified_validity_report,
    make_validity_eligibility,
)
from trusted_synthesis.core.measurement.support import MeasurementSupportDecision
from trusted_synthesis.hashing import canonical_hash

EndpointDisposition = Literal[
    "measurement_support_exit",
    "model_endpoint_unobserved",
    "instrument_failure",
    "privacy_rejection",
    "model_qualified_trajectory",
    "model_unqualified_trajectory",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class JointSupportValidityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    measurement_support_contract_id: str = Field(min_length=1)
    verifier_vnext_contract_id: str = Field(min_length=1)
    required_event_ids_by_mechanism: dict[MechanismId, tuple[str, ...]]
    state_machine_order: tuple[str, ...] = (
        "public_state",
        "model_action",
        "stage_two_commit",
        "public_observation",
        "measurement_support",
        "model_endpoint",
        "validity_eligibility",
        "base_validity",
        "mechanism_qualification",
        "qualified_validity",
    )
    support_exit_invokes_task_verifier: Literal[False] = False
    missing_endpoint_invokes_task_verifier: Literal[False] = False
    instrument_failure_invokes_task_verifier: Literal[False] = False
    privacy_rejection_invokes_task_verifier: Literal[False] = False
    eligible_endpoint_task_verifier_invocation_count: Literal[1] = 1
    support_exit_is_model_invalid: Literal[False] = False
    instrument_failure_is_model_invalid: Literal[False] = False
    privacy_rejection_infers_answer: Literal[False] = False
    stage_two_provider_calls: Literal[0] = 0
    schema_version: str = "prospective_joint_support_validity_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> JointSupportValidityContract:
        expected = {
            key: tuple(sorted(set(value)))
            for key, value in self.required_event_ids_by_mechanism.items()
        }
        if self.required_event_ids_by_mechanism != expected or set(expected) != {
            "context_conditioned_action",
            "semantic_reconciliation",
            "failure_recovery",
            "state_dependent_stopping",
        }:
            raise ValueError("joint support-validity Mechanism Contract changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "prospective_joint_support_validity_contract:",
        ):
            raise ValueError("joint support-validity Contract identity changed")
        return self


class JointSupportValidityResult(FrozenModel):
    result_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    support_decision_id: str = Field(min_length=1)
    support_status: Literal["available", "not_required", "unavailable"]
    endpoint_disposition: EndpointDisposition
    eligibility: ValidityEligibility
    base_report: BaseTrajectoryValidityReport
    mechanism_report: MechanismQualificationReport
    qualified_report: QualifiedTrajectoryValidityReport
    task_verifier_invocation_count: Literal[0, 1]
    model_outcome: bool
    model_qualified: bool | None
    state_mapping_eligible: bool
    host_answer_or_mechanism_inserted: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: str = "prospective_joint_support_validity_result.v1"

    @model_validator(mode="after")
    def validate_result(self) -> JointSupportValidityResult:
        evaluable = self.eligibility.evaluable
        if self.task_verifier_invocation_count != int(evaluable):
            raise ValueError("joint task-Verifier invocation count changed")
        if not evaluable and (
            self.base_report.valid is not None
            or self.mechanism_report.success is not None
            or self.qualified_report.valid is not None
            or self.model_outcome
            or self.model_qualified is not None
            or self.state_mapping_eligible
        ):
            raise ValueError("ineligible joint result inferred model validity")
        if evaluable and (
            not self.model_outcome
            or self.model_qualified != self.qualified_report.valid
            or self.state_mapping_eligible != self.qualified_report.state_mapping_eligible
        ):
            raise ValueError("eligible joint result changed")
        expected_disposition = _endpoint_disposition(
            support_status=self.support_status,
            model_endpoint_observed=self.eligibility.model_endpoint_observed,
            instrument_integrity=self.eligibility.instrument_integrity,
            privacy_compliant=self.eligibility.privacy_compliant,
            qualified_valid=self.qualified_report.valid,
        )
        if self.endpoint_disposition != expected_disposition:
            raise ValueError("joint endpoint disposition changed")
        if self.result_id != _identity(
            self,
            "result_id",
            "prospective_joint_support_validity_result:",
        ):
            raise ValueError("joint support-validity result identity changed")
        return self


def make_joint_support_validity_contract(
    *,
    measurement_support_contract_id: str,
    verifier_vnext_contract_id: str,
    required_event_ids_by_mechanism: Mapping[MechanismId, Sequence[str]],
) -> JointSupportValidityContract:
    values = {
        "measurement_support_contract_id": measurement_support_contract_id,
        "verifier_vnext_contract_id": verifier_vnext_contract_id,
        "required_event_ids_by_mechanism": {
            key: tuple(sorted(set(value)))
            for key, value in sorted(required_event_ids_by_mechanism.items())
        },
    }
    provisional = JointSupportValidityContract.model_construct(contract_id="pending", **values)
    return JointSupportValidityContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "prospective_joint_support_validity_contract:",
        ),
        **values,
    )


def evaluate_joint_support_validity(
    *,
    contract: JointSupportValidityContract,
    support_decision: MeasurementSupportDecision,
    trajectory_id: str,
    task_package_id: str,
    model_endpoint_observed: bool,
    instrument_integrity: bool,
    privacy_compliant: bool,
    mechanism_id: MechanismId,
    base_checks: BaseValidityChecks | None = None,
    noninterference_binding: NoninterferenceArtifactBinding | None = None,
    observed_mechanism_event_ids: Sequence[str] = (),
) -> JointSupportValidityResult:
    support_available = support_decision.status != "unavailable"
    if not support_available and model_endpoint_observed:
        raise ValueError("measurement-support exit cannot carry a completed model endpoint")
    eligibility = make_validity_eligibility(
        measurement_support_available=support_available,
        model_endpoint_observed=model_endpoint_observed,
        instrument_integrity=instrument_integrity,
        privacy_compliant=privacy_compliant,
    )
    required_events = contract.required_event_ids_by_mechanism[mechanism_id]
    if eligibility.evaluable:
        if base_checks is None or noninterference_binding is None:
            raise ValueError("evaluable joint result requires exact Verifier inputs")
        if noninterference_binding.task_package_id != task_package_id:
            raise ValueError("noninterference Artifact is detached from the TaskPackage")
        observed_events = tuple(observed_mechanism_event_ids)
    else:
        if (
            base_checks is not None
            or noninterference_binding is not None
            or observed_mechanism_event_ids
        ):
            raise ValueError("ineligible joint result may not invoke or prime the task Verifier")
        observed_events = ()
    base = make_base_validity_report(
        verifier_contract_id=contract.verifier_vnext_contract_id,
        trajectory_id=trajectory_id,
        eligibility=eligibility,
        checks=base_checks,
        noninterference_binding=noninterference_binding,
    )
    mechanism = make_mechanism_qualification_report(
        verifier_contract_id=contract.verifier_vnext_contract_id,
        trajectory_id=trajectory_id,
        eligibility=eligibility,
        mechanism_id=mechanism_id,
        required_event_ids=required_events,
        observed_event_ids=observed_events,
        causal_failure_group_id=(
            f"{trajectory_id}:state_dependent_stopping"
            if mechanism_id == "state_dependent_stopping" and eligibility.evaluable
            else None
        ),
    )
    qualified = make_qualified_validity_report(
        verifier_contract_id=contract.verifier_vnext_contract_id,
        trajectory_id=trajectory_id,
        eligibility=eligibility,
        base=base,
        mechanism=mechanism,
    )
    disposition = _endpoint_disposition(
        support_status=support_decision.status,
        model_endpoint_observed=model_endpoint_observed,
        instrument_integrity=instrument_integrity,
        privacy_compliant=privacy_compliant,
        qualified_valid=qualified.valid,
    )
    values = {
        "contract_id": contract.contract_id,
        "trajectory_id": trajectory_id,
        "task_package_id": task_package_id,
        "support_decision_id": support_decision.decision_id,
        "support_status": support_decision.status,
        "endpoint_disposition": disposition,
        "eligibility": eligibility,
        "base_report": base,
        "mechanism_report": mechanism,
        "qualified_report": qualified,
        "task_verifier_invocation_count": int(eligibility.evaluable),
        "model_outcome": eligibility.evaluable,
        "model_qualified": qualified.valid,
        "state_mapping_eligible": qualified.state_mapping_eligible,
    }
    provisional = JointSupportValidityResult.model_construct(result_id="pending", **values)
    return JointSupportValidityResult(
        result_id=_identity(
            provisional,
            "result_id",
            "prospective_joint_support_validity_result:",
        ),
        **values,
    )


def _endpoint_disposition(
    *,
    support_status: str,
    model_endpoint_observed: bool,
    instrument_integrity: bool,
    privacy_compliant: bool,
    qualified_valid: bool | None,
) -> EndpointDisposition:
    if support_status == "unavailable":
        return "measurement_support_exit"
    if not model_endpoint_observed:
        return "model_endpoint_unobserved"
    if not instrument_integrity:
        return "instrument_failure"
    if not privacy_compliant:
        return "privacy_rejection"
    return "model_qualified_trajectory" if qualified_valid else "model_unqualified_trajectory"


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)
