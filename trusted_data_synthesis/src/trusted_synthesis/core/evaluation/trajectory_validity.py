from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

MechanismId = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ValidityEligibility(FrozenModel):
    eligibility_id: str = Field(min_length=1)
    measurement_support_available: bool
    model_endpoint_observed: bool
    instrument_integrity: bool
    privacy_compliant: bool
    evaluable: bool
    ineligible_reason_ids: tuple[str, ...]
    schema_version: str = "prospective_validity_eligibility.v1"

    @model_validator(mode="after")
    def validate_eligibility(self) -> ValidityEligibility:
        values = {
            "measurement_support_unavailable": self.measurement_support_available,
            "model_endpoint_unobserved": self.model_endpoint_observed,
            "instrument_integrity_failed": self.instrument_integrity,
            "privacy_noncompliant": self.privacy_compliant,
        }
        expected_reasons = tuple(sorted(key for key, passed in values.items() if not passed))
        if self.evaluable != all(values.values()) or self.ineligible_reason_ids != expected_reasons:
            raise ValueError("prospective Validity eligibility changed")
        if self.eligibility_id != _identity(
            self,
            "eligibility_id",
            "prospective_validity_eligibility:",
        ):
            raise ValueError("prospective Validity eligibility identity changed")
        return self


class NoninterferenceArtifactBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    noninterference_contract_id: str = Field(min_length=1)
    noninterference_audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    audit_passed: Literal[True] = True
    hardcoded_pass_forbidden: Literal[True] = True
    schema_version: str = "prospective_noninterference_artifact_binding.v1"

    @model_validator(mode="after")
    def validate_binding(self) -> NoninterferenceArtifactBinding:
        if self.binding_id != _identity(
            self,
            "binding_id",
            "prospective_noninterference_artifact_binding:",
        ):
            raise ValueError("prospective noninterference binding identity changed")
        return self


class BaseValidityChecks(FrozenModel):
    action_abi_complete: bool
    program_closed: bool
    operation_lineage_complete: bool
    required_evidence_support_complete: bool
    runtime_selected_support_complete: bool
    model_citation_complete: bool
    terminal_verification_complete: bool
    final_abi_complete: bool
    answer_schema_complete: bool
    answer_canonical_semantic_match: bool
    reference_identity_match: bool
    verification_support_complete: bool
    no_postcompletion_violation: bool
    noninterference_artifact_bound: bool

    def all_passed(self) -> bool:
        return all(self.model_dump(mode="python").values())


class BaseTrajectoryValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    eligibility_id: str = Field(min_length=1)
    noninterference_binding_id: str | None = None
    checks: BaseValidityChecks | None = None
    valid: bool | None = None
    failed_check_ids: tuple[str, ...]
    schema_version: str = "prospective_base_trajectory_validity_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> BaseTrajectoryValidityReport:
        if self.checks is None:
            if self.valid is not None or self.failed_check_ids or self.noninterference_binding_id:
                raise ValueError("ineligible Base report inferred task validity")
        else:
            failures = tuple(
                sorted(
                    key for key, value in self.checks.model_dump(mode="python").items() if not value
                )
            )
            if (
                self.noninterference_binding_id is None
                or self.valid != self.checks.all_passed()
                or self.failed_check_ids != failures
            ):
                raise ValueError("prospective Base report changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "prospective_base_trajectory_validity_report:",
        ):
            raise ValueError("prospective Base report identity changed")
        return self


class MechanismQualificationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    eligibility_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    required_event_ids: tuple[str, ...]
    observed_event_ids: tuple[str, ...]
    missing_event_ids: tuple[str, ...]
    success: bool | None
    causal_failure_group_id: str | None = None
    schema_version: str = "prospective_mechanism_qualification_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> MechanismQualificationReport:
        required = set(self.required_event_ids)
        observed = set(self.observed_event_ids)
        missing = tuple(sorted(required - observed))
        if (
            self.required_event_ids != tuple(sorted(required))
            or self.observed_event_ids != tuple(sorted(observed))
            or self.missing_event_ids != missing
        ):
            raise ValueError("prospective Mechanism event partition changed")
        if self.success is not None and self.success != (not missing):
            raise ValueError("prospective Mechanism success changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "prospective_mechanism_qualification_report:",
        ):
            raise ValueError("prospective Mechanism report identity changed")
        return self


class QualifiedTrajectoryValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    eligibility_id: str = Field(min_length=1)
    base_report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    valid: bool | None
    state_mapping_eligible: bool
    schema_version: str = "prospective_qualified_trajectory_validity_report.v1"

    @model_validator(mode="after")
    def validate_report(self) -> QualifiedTrajectoryValidityReport:
        if self.state_mapping_eligible != (self.valid is True):
            raise ValueError("prospective State Mapping eligibility changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "prospective_qualified_trajectory_validity_report:",
        ):
            raise ValueError("prospective Qualified report identity changed")
        return self


class ContextMechanismEvidence(FrozenModel):
    frozen_context_pair_id: str = Field(min_length=1)
    baseline_action_id: str = Field(min_length=1)
    conditioned_action_id: str = Field(min_length=1)
    target_action_change_required: Literal[True] = True


class ReconciliationMechanismEvidence(FrozenModel):
    target_evidence_ids: tuple[str, ...] = Field(min_length=1)
    normalized_target_evidence_ids: tuple[str, ...]
    consumed_normalization_evidence_ids: tuple[str, ...]
    extra_legal_normalized_evidence_ids: tuple[str, ...] = ()
    extra_legal_normalization_forbidden: Literal[False] = False


class RecoveryMechanismEvidence(FrozenModel):
    typed_failure_observation_index: int | None = Field(default=None, ge=0)
    revised_action_observation_index: int | None = Field(default=None, ge=0)
    later_success_observation_index: int | None = Field(default=None, ge=0)
    failed_action_signature: str | None = None
    revised_action_signature: str | None = None


class StoppingMechanismEvidence(FrozenModel):
    completion_verified: bool
    stopped_after_completion: bool
    postcompletion_violation: bool
    stopping_failure_causal_group_id: str = Field(min_length=1)


def make_validity_eligibility(
    *,
    measurement_support_available: bool,
    model_endpoint_observed: bool,
    instrument_integrity: bool,
    privacy_compliant: bool,
) -> ValidityEligibility:
    passed = {
        "measurement_support_unavailable": measurement_support_available,
        "model_endpoint_unobserved": model_endpoint_observed,
        "instrument_integrity_failed": instrument_integrity,
        "privacy_noncompliant": privacy_compliant,
    }
    values = {
        "measurement_support_available": measurement_support_available,
        "model_endpoint_observed": model_endpoint_observed,
        "instrument_integrity": instrument_integrity,
        "privacy_compliant": privacy_compliant,
        "evaluable": all(passed.values()),
        "ineligible_reason_ids": tuple(sorted(key for key, value in passed.items() if not value)),
    }
    provisional = ValidityEligibility.model_construct(eligibility_id="pending", **values)
    return ValidityEligibility(
        eligibility_id=_identity(
            provisional,
            "eligibility_id",
            "prospective_validity_eligibility:",
        ),
        **values,
    )


def make_noninterference_artifact_binding(
    *,
    noninterference_contract_id: str,
    noninterference_audit_id: str,
    task_package_id: str,
) -> NoninterferenceArtifactBinding:
    values = {
        "noninterference_contract_id": noninterference_contract_id,
        "noninterference_audit_id": noninterference_audit_id,
        "task_package_id": task_package_id,
    }
    provisional = NoninterferenceArtifactBinding.model_construct(binding_id="pending", **values)
    return NoninterferenceArtifactBinding(
        binding_id=_identity(
            provisional,
            "binding_id",
            "prospective_noninterference_artifact_binding:",
        ),
        **values,
    )


def make_base_validity_report(
    *,
    verifier_contract_id: str,
    trajectory_id: str,
    eligibility: ValidityEligibility,
    checks: BaseValidityChecks | None,
    noninterference_binding: NoninterferenceArtifactBinding | None,
) -> BaseTrajectoryValidityReport:
    if eligibility.evaluable:
        if checks is None or noninterference_binding is None:
            raise ValueError("evaluable Base report requires checks and noninterference Artifact")
        if not checks.noninterference_artifact_bound:
            raise ValueError("Base report lacks a passing noninterference Artifact binding")
        failures = tuple(
            sorted(key for key, value in checks.model_dump(mode="python").items() if not value)
        )
        valid: bool | None = checks.all_passed()
        binding_id: str | None = noninterference_binding.binding_id
    else:
        if checks is not None or noninterference_binding is not None:
            raise ValueError("ineligible Base report may not invoke task verification")
        failures = ()
        valid = None
        binding_id = None
    values = {
        "verifier_contract_id": verifier_contract_id,
        "trajectory_id": trajectory_id,
        "eligibility_id": eligibility.eligibility_id,
        "noninterference_binding_id": binding_id,
        "checks": checks,
        "valid": valid,
        "failed_check_ids": failures,
    }
    provisional = BaseTrajectoryValidityReport.model_construct(report_id="pending", **values)
    return BaseTrajectoryValidityReport(
        report_id=_identity(
            provisional,
            "report_id",
            "prospective_base_trajectory_validity_report:",
        ),
        **values,
    )


def make_mechanism_qualification_report(
    *,
    verifier_contract_id: str,
    trajectory_id: str,
    eligibility: ValidityEligibility,
    mechanism_id: MechanismId,
    required_event_ids: Sequence[str],
    observed_event_ids: Sequence[str] = (),
    causal_failure_group_id: str | None = None,
) -> MechanismQualificationReport:
    required = tuple(sorted(set(required_event_ids)))
    observed = tuple(sorted(set(observed_event_ids))) if eligibility.evaluable else ()
    missing = tuple(sorted(set(required) - set(observed))) if eligibility.evaluable else required
    success = not missing if eligibility.evaluable else None
    values = {
        "verifier_contract_id": verifier_contract_id,
        "trajectory_id": trajectory_id,
        "eligibility_id": eligibility.eligibility_id,
        "mechanism_id": mechanism_id,
        "required_event_ids": required,
        "observed_event_ids": observed,
        "missing_event_ids": missing,
        "success": success,
        "causal_failure_group_id": causal_failure_group_id,
    }
    provisional = MechanismQualificationReport.model_construct(report_id="pending", **values)
    return MechanismQualificationReport(
        report_id=_identity(
            provisional,
            "report_id",
            "prospective_mechanism_qualification_report:",
        ),
        **values,
    )


def make_qualified_validity_report(
    *,
    verifier_contract_id: str,
    trajectory_id: str,
    eligibility: ValidityEligibility,
    base: BaseTrajectoryValidityReport,
    mechanism: MechanismQualificationReport,
) -> QualifiedTrajectoryValidityReport:
    if (
        base.verifier_contract_id != verifier_contract_id
        or mechanism.verifier_contract_id != verifier_contract_id
        or base.trajectory_id != trajectory_id
        or mechanism.trajectory_id != trajectory_id
        or base.eligibility_id != eligibility.eligibility_id
        or mechanism.eligibility_id != eligibility.eligibility_id
    ):
        raise ValueError("Qualified report parents are not jointly bound")
    valid = bool(base.valid and mechanism.success) if eligibility.evaluable else None
    values = {
        "verifier_contract_id": verifier_contract_id,
        "trajectory_id": trajectory_id,
        "eligibility_id": eligibility.eligibility_id,
        "base_report_id": base.report_id,
        "mechanism_report_id": mechanism.report_id,
        "valid": valid,
        "state_mapping_eligible": valid is True,
    }
    provisional = QualifiedTrajectoryValidityReport.model_construct(report_id="pending", **values)
    return QualifiedTrajectoryValidityReport(
        report_id=_identity(
            provisional,
            "report_id",
            "prospective_qualified_trajectory_validity_report:",
        ),
        **values,
    )


def qualify_context_mechanism(
    evidence: ContextMechanismEvidence,
) -> tuple[str, ...]:
    events = {"frozen_context_difference_bound"}
    if evidence.baseline_action_id != evidence.conditioned_action_id:
        events.add("target_context_action_changed")
    return tuple(sorted(events))


def qualify_reconciliation_mechanism(
    evidence: ReconciliationMechanismEvidence,
) -> tuple[str, ...]:
    target = set(evidence.target_evidence_ids)
    normalized = set(evidence.normalized_target_evidence_ids)
    consumed = set(evidence.consumed_normalization_evidence_ids)
    events: set[str] = set()
    if normalized == target:
        events.add("all_target_evidence_normalized")
    if target <= consumed:
        events.add("all_target_normalization_references_consumed")
    if evidence.extra_legal_normalized_evidence_ids:
        events.add("extra_legal_normalization_observed")
    return tuple(sorted(events))


def qualify_recovery_mechanism(evidence: RecoveryMechanismEvidence) -> tuple[str, ...]:
    events: set[str] = set()
    failure = evidence.typed_failure_observation_index
    revised = evidence.revised_action_observation_index
    success = evidence.later_success_observation_index
    if failure is not None:
        events.add("typed_failure_observed")
    revised_action = bool(
        failure is not None
        and revised is not None
        and revised > failure
        and evidence.failed_action_signature
        and evidence.revised_action_signature
        and evidence.failed_action_signature != evidence.revised_action_signature
    )
    if revised_action:
        events.add("selector_or_action_revised")
    if revised_action and revised is not None and success is not None and success > revised:
        events.add("later_recovery_observation_succeeded")
    return tuple(sorted(events))


def qualify_stopping_mechanism(evidence: StoppingMechanismEvidence) -> tuple[str, ...]:
    events: set[str] = set()
    if evidence.completion_verified:
        events.add("completion_verified")
    if evidence.stopped_after_completion:
        events.add("stopped_after_completion")
    if evidence.postcompletion_violation:
        events.add("postcompletion_violation")
    else:
        events.add("no_postcompletion_violation")
    return tuple(sorted(events))


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)
