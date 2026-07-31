from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts.runtime import QualityContractRuntime
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.trajectory.attributes import (
    TrajectoryAttributes,
    extract_trajectory_attributes,
)
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateVerificationReport,
    CandidateWorkflowVerifier,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.hashing import canonical_hash

TRAJECTORY_VALIDITY_SCHEMA_VERSION = "trajectory_validity.v1"

_CHECK_COMPONENTS = {
    "task_identity": "identity_and_interface",
    "candidate_workflow_kind": "identity_and_interface",
    "public_only_generation": "identity_and_interface",
    "allowed_tool_compliance": "identity_and_interface",
    "required_actions_present": "identity_and_interface",
    "step_statuses_succeeded": "identity_and_interface",
    "action_sequence_valid": "identity_and_interface",
    "retrieved_evidence_known": "evidence",
    "retrieved_evidence_validity": "evidence",
    "selected_evidence_was_retrieved": "evidence",
    "selected_evidence_validity": "evidence",
    "source_grounding": "evidence",
    "evidence_recall": "evidence",
    "evidence_precision": "evidence",
    "proof_graph_binding": "proof_graph",
    "execution_coverage": "program_execution",
    "operation_grounding": "program_execution",
    "tool_necessity": "program_execution",
    "program_node_alignment": "program_execution",
    "all_calculations_correct": "program_execution",
    "verification_step_binding": "program_execution",
    "operation_correctness": "program_execution",
    "answer_schema_validity": "answer_and_claim",
    "answer_correctness": "answer_and_claim",
    "unsupported_claim_detection": "answer_and_claim",
    "domain_claim_verification": "answer_and_claim",
    "citation_binding": "citation",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TrajectoryValidityReport(FrozenModel):
    """A fail-closed evaluation of V(trajectory, Omega_x)."""

    report_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_hash: str = Field(min_length=1)
    valid: bool
    validity_score: float = Field(ge=0, le=1)
    component_validity: dict[str, float] = Field(min_length=1)
    attributes: TrajectoryAttributes
    failed_check_ids: tuple[str, ...] = ()
    failed_clause_ids: tuple[str, ...] = ()
    failure_types: tuple[str, ...] = ()
    failure_locations: tuple[str, ...] = ()
    workflow_report_hash: str | None = None
    contract_assessment_hash: str | None = None
    verifier_failures: tuple[str, ...] = ()
    schema_version: str = TRAJECTORY_VALIDITY_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity_and_status(self) -> TrajectoryValidityReport:
        if self.valid and (
            self.failed_check_ids
            or self.failed_clause_ids
            or self.failure_types
            or self.verifier_failures
        ):
            raise ValueError("a valid trajectory cannot retain verifier failures")
        if self.valid and not all(value == 1.0 for value in self.component_validity.values()):
            raise ValueError("a valid trajectory requires every component to pass")
        expected_score = sum(self.component_validity.values()) / len(
            self.component_validity
        )
        if abs(self.validity_score - expected_score) > 1e-12:
            raise ValueError("trajectory validity score must be the component mean")
        if self.report_id != trajectory_validity_report_id(self):
            raise ValueError("trajectory validity report identity is invalid")
        return self


class TrajectoryValidityEvaluator:
    """Reuse independent workflow and executable Quality Contract verification."""

    def __init__(
        self,
        workflow_verifier: CandidateWorkflowVerifier,
        *,
        contract_runtime: QualityContractRuntime | None = None,
    ) -> None:
        self._workflow_verifier = workflow_verifier
        self._contract_runtime = contract_runtime or QualityContractRuntime(
            workflow_verifier
        )

    def evaluate(
        self,
        context: TrajectoryVerificationContext,
        trajectory: Trajectory,
    ) -> TrajectoryValidityReport:
        attributes = extract_trajectory_attributes(
            trajectory,
            context.task.oracle.task_program,
        )
        workflow_report: CandidateVerificationReport | None = None
        contract_assessment = None
        verifier_failures: list[str] = []
        try:
            workflow_report = self._workflow_verifier.verify(
                context.task,
                context.public_corpus,
                context.proof_graph,
                trajectory,
            )
        except Exception as exc:  # fail closed at the verification boundary
            verifier_failures.append(f"workflow:{type(exc).__name__}:{exc}")
        try:
            contract_assessment = self._contract_runtime.evaluate(
                context.quality_contract,
                context.task,
                context.public_corpus,
                context.proof_graph,
                trajectory,
            )
        except Exception as exc:  # fail closed at the verification boundary
            verifier_failures.append(f"quality_contract:{type(exc).__name__}:{exc}")

        component_values = _component_validity(workflow_report)
        component_values["quality_contract"] = float(
            contract_assessment is not None
            and contract_assessment.decision == ReleaseDecision.ACCEPTED
        )
        failed_checks = tuple(
            check.check_id
            for check in workflow_report.checks
            if not check.passed
        ) if workflow_report is not None else ("workflow_verifier_unavailable",)
        failed_clauses = (
            contract_assessment.failed_clause_ids
            if contract_assessment is not None
            else ("quality_contract_runtime_unavailable",)
        )
        failure_types = set(failed_checks)
        failure_types.update(item.split(":", 1)[0] for item in verifier_failures)
        failure_locations = {f"check:{item}" for item in failed_checks}
        if contract_assessment is not None:
            failure_types.update(
                item.failure_code
                for item in contract_assessment.clause_results
                if not item.passed and item.failure_code is not None
            )
            failure_locations.update(
                f"{item.location_type}:{item.location_ref}"
                for item in contract_assessment.clause_results
                if not item.passed
                and item.location_type is not None
                and item.location_ref is not None
            )
        valid = bool(
            workflow_report is not None
            and workflow_report.passed
            and contract_assessment is not None
            and contract_assessment.decision == ReleaseDecision.ACCEPTED
            and not verifier_failures
        )
        values = {
            "context_id": context.context_id,
            "trajectory_id": trajectory.trajectory_id,
            "trajectory_hash": trajectory.trajectory_hash,
            "valid": valid,
            "validity_score": sum(component_values.values()) / len(component_values),
            "component_validity": dict(sorted(component_values.items())),
            "attributes": attributes,
            "failed_check_ids": tuple(sorted(failed_checks)),
            "failed_clause_ids": tuple(sorted(failed_clauses)),
            "failure_types": tuple(sorted(failure_types)),
            "failure_locations": tuple(sorted(failure_locations)),
            "workflow_report_hash": (
                canonical_hash(workflow_report, prefix="candidate_workflow_report:")
                if workflow_report is not None
                else None
            ),
            "contract_assessment_hash": (
                canonical_hash(contract_assessment, prefix="contract_assessment_result:")
                if contract_assessment is not None
                else None
            ),
            "verifier_failures": tuple(verifier_failures),
            "schema_version": TRAJECTORY_VALIDITY_SCHEMA_VERSION,
        }
        provisional = TrajectoryValidityReport.model_construct(report_id="pending", **values)
        return TrajectoryValidityReport(
            report_id=trajectory_validity_report_id(provisional),
            **values,
        )


def trajectory_validity_report_id(value: TrajectoryValidityReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="trajectory_validity_report:",
    )


def _component_validity(
    report: CandidateVerificationReport | None,
) -> dict[str, float]:
    component_checks: dict[str, list[bool]] = defaultdict(list)
    for component in sorted(set(_CHECK_COMPONENTS.values())):
        component_checks[component] = []
    if report is None:
        return {component: 0.0 for component in sorted(component_checks)}
    for check in report.checks:
        component = _CHECK_COMPONENTS.get(check.check_id, "identity_and_interface")
        component_checks[component].append(check.passed)
    return {
        component: (
            sum(values) / len(values)
            if values
            else 0.0
        )
        for component, values in sorted(component_checks.items())
    }
