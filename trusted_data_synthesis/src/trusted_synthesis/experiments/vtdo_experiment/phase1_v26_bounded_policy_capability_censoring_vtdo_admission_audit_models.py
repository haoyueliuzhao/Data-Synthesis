from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyEndpointProjection,
)

OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_166_bounded_policy_capability_censoring_vtdo_admission_audit_v1_20260828"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit.py"
)
MODEL_IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit_models.py"
)
AUDIT_DECISION: Final = "bounded_policy_capability_censoring_and_vtdo_admission_audit_only"
NEXT_STAGE: Final = "fresh_vtdo_admission_confirmation_preflight_only"
EXTERNAL_REVIEW_SHA256: Final = "00363f92c449225c0f19cb34a510baf4c97b1857dd77f81ba240d7e53481fb0b"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 17_949

MechanismId = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
]
Tier = Literal["easy_control", "frontier", "hard_control"]
CellCondition = Literal[
    "unconditional",
    "structured_direct",
    "search_then_structured",
    "search_then_open",
]
SupportStratum = Literal[
    "valid_support_absent",
    "single_valid_observation",
    "observed_single_state_support",
    "observed_multistate_support",
]
GateStage = Literal[
    "action_entry",
    "program_closure",
    "operation_lineage",
    "evidence_support",
    "terminal_verification",
    "final_abi",
    "answer_semantics",
    "reference_identity",
    "citation",
    "mechanism_qualification",
    "policy_horizon",
]
FirstAuthorizedBlocker = Literal[
    "action_entry",
    "program_closure",
    "operation_lineage",
    "evidence_support",
    "terminal_verification",
    "final_abi",
    "answer_semantics",
    "reference_identity",
    "citation",
    "mechanism_qualification",
    "policy_horizon",
    "none_qualified_survivor",
]

GATE_DAG: Final[tuple[GateStage, ...]] = (
    "action_entry",
    "program_closure",
    "operation_lineage",
    "evidence_support",
    "terminal_verification",
    "final_abi",
    "answer_semantics",
    "reference_identity",
    "citation",
    "mechanism_qualification",
    "policy_horizon",
)

ABSENT_CELL_SIGNATURES: Final[tuple[str, ...]] = (
    "context_conditioned_action|hard_control|search_then_open",
    "context_conditioned_action|hard_control|search_then_structured",
    "context_conditioned_action|hard_control|structured_direct",
    "context_conditioned_action|hard_control|unconditional",
    "failure_recovery|hard_control|structured_direct",
    "semantic_reconciliation|hard_control|search_then_open",
    "semantic_reconciliation|hard_control|search_then_structured",
    "semantic_reconciliation|hard_control|structured_direct",
    "semantic_reconciliation|hard_control|unconditional",
    "state_dependent_stopping|hard_control|structured_direct",
)

SINGLE_STATE_CELL_SIGNATURES: Final[tuple[str, ...]] = (
    "context_conditioned_action|frontier|structured_direct",
    "state_dependent_stopping|easy_control|structured_direct",
    "state_dependent_stopping|easy_control|unconditional",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


def json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_payload(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    source_sha256: Literal["00363f92c449225c0f19cb34a510baf4c97b1857dd77f81ba240d7e53481fb0b"] = (
        EXTERNAL_REVIEW_SHA256
    )
    source_byte_count: Literal[17949] = EXTERNAL_REVIEW_BYTE_COUNT
    authorized_decision: Literal[
        "bounded_policy_capability_censoring_and_vtdo_admission_audit_only"
    ] = AUDIT_DECISION
    required_outputs: tuple[str, ...] = (
        "capability_survival_profile",
        "cell_support_strata",
        "coverage_gap_registry",
        "fresh_confirmation_protocol",
        "terminal_endpoint_schema_matrix",
        "typed_semantic_rejection_boundary",
        "vtdo_admission_tiers",
    )
    historical_artifact_mutation_allowed: Literal[False] = False
    provider_execution_allowed: Literal[False] = False
    vtdo_execution_allowed: Literal[False] = False
    compiler_intervention_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.required_outputs != tuple(sorted(set(self.required_outputs))):
            raise ValueError("v26.166 external audit requirements changed")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_bounded_policy_capability_censoring_authorization:",
        ):
            raise ValueError("v26.166 external audit authorization identity changed")
        return self


class SourceBinding(FrozenModel):
    stage: Literal["v26.163", "v26.164", "v26.165", "v26.166"]
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    artifact_bindings: tuple[SourceBinding, ...] = Field(min_length=25, max_length=25)
    implementation_bindings: tuple[SourceBinding, ...] = Field(min_length=2, max_length=2)
    v26_163_binding_count: Literal[4] = 4
    v26_164_binding_count: Literal[13] = 13
    v26_165_binding_count: Literal[8] = 8
    v26_166_implementation_count: Literal[2] = 2
    complete_endpoint_parent_count: Literal[360] = 360
    qualified_assignment_parent_count: Literal[106] = 106
    frozen_cell_report_parent_count: Literal[48] = 48
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    historical_artifact_write_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        artifact_keys = tuple((item.stage, item.relative_path) for item in self.artifact_bindings)
        implementation_paths = tuple(item.relative_path for item in self.implementation_bindings)
        if (
            artifact_keys != tuple(sorted(set(artifact_keys)))
            or implementation_paths != tuple(sorted(set(implementation_paths)))
            or sum(item.stage == "v26.163" for item in self.artifact_bindings) != 4
            or sum(item.stage == "v26.164" for item in self.artifact_bindings) != 13
            or sum(item.stage == "v26.165" for item in self.artifact_bindings) != 8
            or any(item.stage != "v26.166" for item in self.implementation_bindings)
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_censoring_source_replay:",
            )
        ):
            raise ValueError("v26.166 source replay changed")
        return self


class CellSupportStratumRow(FrozenModel):
    row_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Tier
    condition: CellCondition
    expected_endpoint_count: Literal[6, 12]
    bounded_policy_endpoint_count: Literal[6, 12]
    qualified_count: int = Field(ge=0, le=12)
    observed_state_count: int = Field(ge=0, le=12)
    observed_state_ids: tuple[str, ...]
    q_hat: str = Field(min_length=1)
    stratum: SupportStratum
    pi_instantiated: bool
    pi_one_is_population_degeneracy_claim: Literal[False] = False
    zero_state_imputed: Literal[False] = False
    stable_population_probability_claimed: Literal[False] = False

    @property
    def signature(self) -> str:
        return f"{self.mechanism_id}|{self.tier}|{self.condition}"

    @model_validator(mode="after")
    def validate_row(self) -> CellSupportStratumRow:
        if self.observed_state_ids != tuple(sorted(set(self.observed_state_ids))):
            raise ValueError("v26.166 observed State set changed")
        if self.observed_state_count != len(self.observed_state_ids):
            raise ValueError("v26.166 observed State count changed")
        expected = _support_stratum(self.qualified_count, self.observed_state_count)
        if (
            self.stratum != expected
            or self.pi_instantiated != (self.qualified_count > 0)
            or self.bounded_policy_endpoint_count != self.expected_endpoint_count
            or self.row_id
            != identity(
                self,
                "row_id",
                "finance_v26_bounded_policy_cell_support_stratum_row:",
            )
        ):
            raise ValueError("v26.166 Cell support stratum changed")
        return self


def _support_stratum(qualified_count: int, state_count: int) -> SupportStratum:
    if qualified_count == 0:
        if state_count != 0:
            raise ValueError("zero Qualified Cell cannot contain an imputed State")
        return "valid_support_absent"
    if qualified_count == 1:
        if state_count != 1:
            raise ValueError("single Qualified observation must bind its one observed State")
        return "single_valid_observation"
    if state_count == 1:
        return "observed_single_state_support"
    if state_count >= 2:
        return "observed_multistate_support"
    raise ValueError("positive Qualified support cannot have zero observed States")


class CellSupportStratumCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    rows: tuple[CellSupportStratumRow, ...] = Field(min_length=48, max_length=48)
    valid_support_absent_count: Literal[10] = 10
    single_valid_observation_count: Literal[8] = 8
    observed_single_state_support_count: Literal[3] = 3
    observed_multistate_support_count: Literal[27] = 27
    hard_tier_absent_count: Literal[10] = 10
    absent_cell_signatures: tuple[str, ...] = ABSENT_CELL_SIGNATURES
    single_state_cell_signatures: tuple[str, ...] = SINGLE_STATE_CELL_SIGNATURES
    qualified_count_sum: Literal[106] = 106
    zero_state_imputation_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> CellSupportStratumCatalog:
        ids = tuple(item.row_id for item in self.rows)
        counts = {
            key: sum(item.stratum == key for item in self.rows)
            for key in (
                "valid_support_absent",
                "single_valid_observation",
                "observed_single_state_support",
                "observed_multistate_support",
            )
        }
        absent = tuple(sorted(item.signature for item in self.rows if item.qualified_count == 0))
        single_state = tuple(
            sorted(
                item.signature
                for item in self.rows
                if item.stratum == "observed_single_state_support"
            )
        )
        if (
            ids != tuple(sorted(set(ids)))
            or counts
            != {
                "valid_support_absent": 10,
                "single_valid_observation": 8,
                "observed_single_state_support": 3,
                "observed_multistate_support": 27,
            }
            or absent != self.absent_cell_signatures
            or absent != ABSENT_CELL_SIGNATURES
            or single_state != self.single_state_cell_signatures
            or single_state != SINGLE_STATE_CELL_SIGNATURES
            or any(item.tier != "hard_control" for item in self.rows if item.qualified_count == 0)
            or sum(item.qualified_count for item in self.rows) != 106
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_bounded_policy_cell_support_stratum_catalog:",
            )
        ):
            raise ValueError("v26.166 Cell support stratum Catalog changed")
        return self


class CapabilityGateDAGChecks(FrozenModel):
    action_entry: bool | None
    program_closure: bool | None
    operation_lineage: bool | None
    evidence_support: bool | None
    terminal_verification: bool | None
    final_abi: bool | None
    answer_semantics: bool | None
    reference_identity: bool | None
    citation: bool | None
    mechanism_qualification: bool | None
    policy_horizon: bool | None
    noninterference_artifact_bound: bool | None


class CapabilitySurvivalRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    endpoint_projection_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Tier
    condition: CellCondition
    terminal_class: str = Field(min_length=1)
    gate_dag: tuple[GateStage, ...] = GATE_DAG
    checks: CapabilityGateDAGChecks
    base_failed_check_ids: tuple[str, ...]
    mechanism_missing_event_ids: tuple[str, ...]
    first_authorized_blocker: FirstAuthorizedBlocker
    qualified_survivor: bool
    mechanism_endpoint_qualification: bool
    mechanism_event_evaluable: bool
    task_verifier_invoked: bool
    policy_censored: bool
    typed_semantic_rejection: bool
    historical_mapping_eligible: bool
    invalid_trajectory_mapped_to_vtdo_state: Literal[False] = False
    historical_reclassification: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> CapabilitySurvivalRow:
        first = _first_blocker(self.checks)
        if (
            self.gate_dag != GATE_DAG
            or self.first_authorized_blocker != first
            or self.qualified_survivor != (first == "none_qualified_survivor")
            or self.historical_mapping_eligible != self.qualified_survivor
            or self.mechanism_event_evaluable != self.task_verifier_invoked
            or self.row_id
            != identity(
                self,
                "row_id",
                "finance_v26_bounded_policy_capability_survival_row:",
            )
        ):
            raise ValueError("v26.166 Capability Survival row changed")
        if self.typed_semantic_rejection and (
            self.mechanism_endpoint_qualification
            or self.mechanism_event_evaluable
            or self.task_verifier_invoked
        ):
            raise ValueError("typed rejection inferred a Mechanism Verifier result")
        if self.policy_censored and (
            self.first_authorized_blocker != "policy_horizon" or self.task_verifier_invoked
        ):
            raise ValueError("policy Horizon was converted into a capability failure")
        return self


def _first_blocker(checks: CapabilityGateDAGChecks) -> FirstAuthorizedBlocker:
    values = checks.model_dump(mode="python")
    for stage in GATE_DAG:
        if values[stage] is False:
            return stage
    if all(values[stage] is True for stage in GATE_DAG):
        return "none_qualified_survivor"
    raise ValueError("Capability Survival row has an unresolved Gate-DAG suffix")


class CapabilitySurvivalProfileCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    rows: tuple[CapabilitySurvivalRow, ...] = Field(min_length=360, max_length=360)
    endpoint_count: Literal[360] = 360
    qualified_survivor_count: Literal[106] = 106
    blocked_or_censored_count: Literal[254] = 254
    typed_semantic_rejection_count: Literal[2] = 2
    policy_horizon_count: Literal[1] = 1
    mechanism_event_evaluable_count: Literal[357] = 357
    task_verifier_invoked_count: Literal[357] = 357
    first_authorized_blocker_counts: dict[str, int]
    invalid_trajectory_vtdo_mapping_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> CapabilitySurvivalProfileCatalog:
        ids = tuple(item.row_id for item in self.rows)
        counts: dict[str, int] = {}
        for item in self.rows:
            counts[item.first_authorized_blocker] = counts.get(item.first_authorized_blocker, 0) + 1
        if (
            ids != tuple(sorted(set(ids)))
            or counts != self.first_authorized_blocker_counts
            or sum(counts.values()) != 360
            or counts.get("none_qualified_survivor") != 106
            or sum(item.typed_semantic_rejection for item in self.rows) != 2
            or sum(item.policy_censored for item in self.rows) != 1
            or sum(item.mechanism_event_evaluable for item in self.rows) != 357
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_bounded_policy_capability_survival_profile:",
            )
        ):
            raise ValueError("v26.166 Capability Survival Profile changed")
        return self


class TerminalEndpointSchemaCase(FrozenModel):
    case_id: str = Field(min_length=1)
    case_name: str = Field(min_length=1)
    endpoint: BoundedPolicyEndpointProjection
    expected_task_completion: bool | None
    expected_base_validity: bool | None
    expected_mechanism_qualification: bool | None
    expected_qualified_validity: bool | None
    expected_mapping_eligible: bool
    expected_task_verifier_invocation_count: Literal[0, 1]

    @model_validator(mode="after")
    def validate_case(self) -> TerminalEndpointSchemaCase:
        if (
            self.endpoint.task_completion != self.expected_task_completion
            or self.endpoint.base_validity != self.expected_base_validity
            or self.endpoint.mechanism_qualification != self.expected_mechanism_qualification
            or self.endpoint.qualified_validity != self.expected_qualified_validity
            or self.endpoint.state_mapping_eligible != self.expected_mapping_eligible
            or self.endpoint.task_verifier_invocation_count
            != self.expected_task_verifier_invocation_count
            or self.case_id
            != identity(
                self,
                "case_id",
                "finance_v26_terminal_endpoint_schema_case:",
            )
        ):
            raise ValueError("v26.166 terminal Endpoint schema case changed")
        return self


class TerminalEndpointSchemaAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    cases: tuple[TerminalEndpointSchemaCase, ...] = Field(min_length=8, max_length=8)
    completed_endpoint_case_count: Literal[1] = 1
    model_result_failure_case_count: Literal[1] = 1
    typed_semantic_rejection_case_count: Literal[1] = 1
    policy_horizon_case_count: Literal[1] = 1
    support_instrument_privacy_transport_case_count: Literal[4] = 4
    exact_null_policy_match_count: Literal[8] = 8
    future_runner_preflight_matrix_required: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalEndpointSchemaAudit:
        names = tuple(item.case_name for item in self.cases)
        if names != tuple(sorted(set(names))) or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_terminal_endpoint_schema_audit:",
        ):
            raise ValueError("v26.166 terminal Endpoint schema audit changed")
        return self


class TypedSemanticRejectionBoundaryRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    endpoint_projection_id: str = Field(min_length=1)
    mechanism_endpoint_qualification: Literal[False] = False
    mechanism_event_evaluable: Literal[False] = False
    task_verifier_invoked: Literal[False] = False
    legacy_mechanism_report_success: None = None
    mechanism_nonoccurrence_claimed: Literal[False] = False
    endpoint_failure_is_route_b_rule: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> TypedSemanticRejectionBoundaryRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_typed_semantic_rejection_boundary_row:",
        ):
            raise ValueError("v26.166 typed rejection boundary row changed")
        return self


class TypedSemanticRejectionBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[TypedSemanticRejectionBoundaryRow, ...] = Field(min_length=2, max_length=2)
    endpoint_false_count: Literal[2] = 2
    mechanism_event_evaluable_count: Literal[0] = 0
    task_verifier_invocation_count: Literal[0] = 0
    historical_mechanism_qualified_count: Literal[226] = 226
    unconditional_mechanism_occurrence_rate_claimed: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> TypedSemanticRejectionBoundaryAudit:
        ids = tuple(item.row_id for item in self.rows)
        if ids != tuple(sorted(set(ids))) or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_typed_semantic_rejection_boundary_audit:",
        ):
            raise ValueError("v26.166 typed rejection boundary audit changed")
        return self


class VTDOAdmissionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    support_stratum: SupportStratum
    state_support_existence: bool
    frequency_estimability: Literal[False] = False
    contribution_estimability: Literal[False] = False
    materialization_feasibility: Literal[False] = False
    student_visibility: Literal[False] = False
    highest_passed_tier: Literal["none", "state_support_existence"]
    selected_for_vtdo: Literal[False] = False
    current_development_denominator_reused_for_confirmation: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> VTDOAdmissionRow:
        existence = self.support_stratum == "observed_multistate_support"
        if (
            self.state_support_existence != existence
            or self.highest_passed_tier != ("state_support_existence" if existence else "none")
            or self.row_id
            != identity(
                self,
                "row_id",
                "finance_v26_vtdo_admission_row:",
            )
        ):
            raise ValueError("v26.166 VTDO admission row changed")
        return self


class VTDOAdmissionCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    rows: tuple[VTDOAdmissionRow, ...] = Field(min_length=48, max_length=48)
    state_support_existence_count: Literal[27] = 27
    frequency_estimability_count: Literal[0] = 0
    contribution_estimability_count: Literal[0] = 0
    materialization_feasibility_count: Literal[0] = 0
    student_visibility_count: Literal[0] = 0
    selected_for_vtdo_count: Literal[0] = 0
    post_outcome_cell_selection_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> VTDOAdmissionCatalog:
        ids = tuple(item.row_id for item in self.rows)
        if (
            ids != tuple(sorted(set(ids)))
            or sum(item.state_support_existence for item in self.rows) != 27
            or any(
                any(
                    (
                        item.frequency_estimability,
                        item.contribution_estimability,
                        item.materialization_feasibility,
                        item.student_visibility,
                        item.selected_for_vtdo,
                    )
                )
                for item in self.rows
            )
            or self.catalog_id
            != identity(
                self,
                "catalog_id",
                "finance_v26_vtdo_admission_catalog:",
            )
        ):
            raise ValueError("v26.166 VTDO admission Catalog changed")
        return self


class CoverageGapRow(FrozenModel):
    row_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    mechanism_id: MechanismId
    tier: Tier
    condition: CellCondition
    support_stratum: Literal[
        "valid_support_absent",
        "single_valid_observation",
        "observed_single_state_support",
    ]
    current_vtdo_coverage_available: Literal[False] = False
    shared_coverage_anchor_required_for_joint_future_design: Literal[True] = True
    compiler_assisted_capability_coverage_research_candidate: Literal[True] = True
    compiler_intervention_applied: Literal[False] = False
    current_frequency_or_state_imputed: Literal[False] = False

    @model_validator(mode="after")
    def validate_row(self) -> CoverageGapRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_coverage_gap_row:",
        ):
            raise ValueError("v26.166 Coverage Gap row changed")
        return self


class CoverageGapRegistry(FrozenModel):
    registry_id: str = Field(min_length=1)
    rows: tuple[CoverageGapRow, ...] = Field(min_length=21, max_length=21)
    valid_support_absent_count: Literal[10] = 10
    weak_support_count: Literal[11] = 11
    single_valid_observation_count: Literal[8] = 8
    observed_single_state_support_count: Literal[3] = 3
    compiler_intervention_count: Literal[0] = 0
    current_vtdo_coverage_count: Literal[0] = 0
    fresh_population_materialized_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_registry(self) -> CoverageGapRegistry:
        ids = tuple(item.row_id for item in self.rows)
        counts = {
            key: sum(item.support_stratum == key for item in self.rows)
            for key in (
                "valid_support_absent",
                "single_valid_observation",
                "observed_single_state_support",
            )
        }
        if (
            ids != tuple(sorted(set(ids)))
            or counts
            != {
                "valid_support_absent": 10,
                "single_valid_observation": 8,
                "observed_single_state_support": 3,
            }
            or self.registry_id
            != identity(
                self,
                "registry_id",
                "finance_v26_coverage_gap_registry:",
            )
        ):
            raise ValueError("v26.166 Coverage Gap Registry changed")
        return self


class EngineeringTokenDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    provider_total_tokens: Literal[28539733] = 28_539_733
    qualified_trajectory_count: Literal[106] = 106
    tokens_per_qualified_trajectory: Literal["269242.76415094339622641509433962264150943396226415"]
    preregistered_estimand: Literal[False] = False
    cell_budget_allocation_authorized: Literal[False] = False
    cross_heterogeneous_cell_bookkeeping_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_diagnostic(self) -> EngineeringTokenDiagnostic:
        if self.diagnostic_id != identity(
            self,
            "diagnostic_id",
            "finance_v26_cross_cell_token_per_qualified_diagnostic:",
        ):
            raise ValueError("v26.166 engineering token diagnostic changed")
        return self


class FreshConfirmationProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    selection_strata: tuple[str, str, str] = (
        "mechanism",
        "tier",
        "generation_condition",
    )
    admission_rules_frozen_before_outcome_loading: Literal[True] = True
    fresh_model_unexposed_tasks_required: Literal[True] = True
    independent_confirmation_denominator_required: Literal[True] = True
    current_27_multistate_cells_may_define_selection_frame: Literal[False] = False
    current_development_rows_may_establish_vtdo_effect: Literal[False] = False
    current_population_reused: Literal[False] = False
    current_job_reused: Literal[False] = False
    fresh_population_materialized: Literal[False] = False
    fresh_task_package_materialized: Literal[False] = False
    fresh_manifest_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    next_stage: Literal["fresh_vtdo_admission_confirmation_preflight_only"] = NEXT_STAGE

    @model_validator(mode="after")
    def validate_protocol(self) -> FreshConfirmationProtocol:
        if self.protocol_id != identity(
            self,
            "protocol_id",
            "finance_v26_fresh_vtdo_admission_confirmation_protocol:",
        ):
            raise ValueError("v26.166 fresh confirmation protocol changed")
        return self


class TransitionContract(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    fresh_confirmation_protocol_id: str = Field(min_length=1)
    next_stage: Literal["fresh_vtdo_admission_confirmation_preflight_only"] = NEXT_STAGE
    allowed_operations: tuple[str, ...] = (
        "credential_free_fresh_confirmation_population_design",
        "credential_free_fresh_confirmation_runner_preflight",
        "pre_outcome_mechanism_tier_generation_condition_stratification",
    )
    forbidden_operations: tuple[str, ...] = (
        "compiler_intervention",
        "current_27_cell_outcome_selection",
        "current_denominator_reuse",
        "historical_artifact_mutation",
        "provider_execution",
        "state_probability_claim",
        "student_training_visibility_claim",
        "training_release_or_production",
        "vtdo_contribution_estimation",
        "vtdo_execution",
    )
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> TransitionContract:
        if (
            self.allowed_operations != tuple(sorted(set(self.allowed_operations)))
            or self.forbidden_operations != tuple(sorted(set(self.forbidden_operations)))
            or self.transition_id
            != identity(
                self,
                "transition_id",
                "finance_v26_bounded_policy_censoring_transition:",
            )
        ):
            raise ValueError("v26.166 transition Contract changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class CapabilityCensoringAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    cell_support_stratum_catalog_id: str = Field(min_length=1)
    capability_survival_profile_catalog_id: str = Field(min_length=1)
    terminal_endpoint_schema_audit_id: str = Field(min_length=1)
    typed_semantic_rejection_boundary_audit_id: str = Field(min_length=1)
    vtdo_admission_catalog_id: str = Field(min_length=1)
    coverage_gap_registry_id: str = Field(min_length=1)
    engineering_token_diagnostic_id: str = Field(min_length=1)
    fresh_confirmation_protocol_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    endpoint_count: Literal[360] = 360
    qualified_survivor_count: Literal[106] = 106
    valid_support_absent_cell_count: Literal[10] = 10
    weak_support_cell_count: Literal[11] = 11
    observed_multistate_candidate_cell_count: Literal[27] = 27
    current_vtdo_admitted_cell_count: Literal[0] = 0
    terminal_schema_case_count: Literal[8] = 8
    typed_semantic_rejection_count: Literal[2] = 2
    mechanism_qualified_count_is_unconditional_rate: Literal[False] = False
    rho_materialization_authorized: Literal[False] = False
    state_probability_authorized: Literal[False] = False
    contribution_estimation_authorized: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    compiler_intervention_applied: Literal[False] = False
    historical_reclassification_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    detail_files: tuple[DetailFile, ...]
    next_stage: Literal["fresh_vtdo_admission_confirmation_preflight_only"] = NEXT_STAGE
    status: Literal["bounded_policy_capability_censoring_and_vtdo_admission_audit_complete"] = (
        "bounded_policy_capability_censoring_and_vtdo_admission_audit_complete"
    )

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityCensoringAuditReport:
        names = tuple(item.relative_path for item in self.detail_files)
        if names != tuple(sorted(set(names))) or self.report_id != identity(
            self,
            "report_id",
            "finance_v26_bounded_policy_capability_censoring_audit_report:",
        ):
            raise ValueError("v26.166 audit report changed")
        return self
