from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    StateLocalRankSchedule,
    StepRuntimeResult,
)
from trusted_synthesis.hashing import canonical_hash

V26_STATE_LOCAL_PRESENTATION_VERSION = "state_local_presentation_parent_hardening.v1"
AUTHORIZED_STAGE: Final[
    Literal[
        "capability_observation_state_local_higher_order_presentation_"
        "and_source_catalog_parent_hardening_only"
    ]
] = (
    "capability_observation_state_local_higher_order_presentation_"
    "and_source_catalog_parent_hardening_only"
)
NEXT_STAGE: Final[
    Literal[
        "capability_observation_state_local_higher_order_state_bound_step_runtime_"
        "development_runner_preflight_only"
    ]
] = (
    "capability_observation_state_local_higher_order_state_bound_step_runtime_"
    "development_runner_preflight_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "external_audit_input",
        "implementation",
        "predecessor_artifact",
        "formal_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_byte_count: int = Field(ge=1)
    authorized_stage: Literal[
        "capability_observation_state_local_higher_order_presentation_"
        "and_source_catalog_parent_hardening_only"
    ] = AUTHORIZED_STAGE
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_access_authorized: Literal[False] = False
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_state_local_presentation_external_authorization:",
        ):
            raise ValueError("v26.175 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.175 source Root file count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.175 source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_state_local_presentation_transitive_source_root:",
        ):
            raise ValueError("v26.175 source Root identity is invalid")
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_runner_input_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=23, max_length=23)
    predecessor_file_count: Literal[23] = 23
    independent_rebuild_match_count: Literal[23] = 23
    predecessor_mutation_count: Literal[0] = 0
    stale_runner_transition_blocked: Literal[True] = True
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.174 predecessor Freeze denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v174_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.174 predecessor Freeze identity is invalid")
        return self


class V174DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    three_choice_state_count: Literal[66] = 66
    three_choice_presentation_count: Literal[396] = 396
    registered_univariate_pairwise_rule_evaluation_count: Literal[23918] = 23918
    registered_univariate_pairwise_excess_stratum_count: Literal[0] = 0
    triple_rank_attack_recovery_count: Literal[396] = 396
    triple_rank_attack_structural_baseline_total: Literal[132] = 132
    legal_single_choice_nonreference_execution_count: Literal[146] = 146
    full_multicomponent_combination_audited: Literal[False] = False
    accepted_rehashed_source_v173_catalog_parent_attack_count: Literal[1] = 1
    accepted_rehashed_source_v171_catalog_parent_attack_count: Literal[1] = 1
    classifier_only_receipt_mutation_count: Literal[120] = 120
    production_step_receipt_mutation_count: Literal[0] = 0
    stale_runner_transition_blocked: Literal[True] = True
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V174DefectReproductionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v174_higher_order_parent_defect_reproduction:",
        ):
            raise ValueError("v26.174 defect reproduction identity is invalid")
        return self


class StateLocalPresentationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    schedule_scope: Literal["source_package_x_component"] = "source_package_x_component"
    source_order_policy: Literal[
        "canonical_public_operation_then_choice_handle_not_reference_first"
    ] = "canonical_public_operation_then_choice_handle_not_reference_first"
    six_replica_marginal_balance_required: Literal[True] = True
    state_local_codebook_uniqueness_required: Literal[True] = True
    latent_rank_factorization_required: Literal[True] = True
    schedule_frozen_before_model_outcome: Literal[True] = True
    schedule_identity_is_package_parent: Literal[True] = True
    triple_affine_coefficients: tuple[int, ...] = (-3, -2, -1, 1, 2, 3)
    triple_affine_moduli: tuple[int, ...] = (2, 3, 4, 5, 6)
    triple_selection_rules: tuple[str, ...] = ("equality", "maximum", "minimum")
    explicit_counterexample_coefficients: tuple[int, int, int] = (-2, 2, -3)
    explicit_counterexample_modulus: Literal[6] = 6
    provider_calls: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> StateLocalPresentationContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "state_local_higher_order_presentation_contract:",
        ):
            raise ValueError("State-local Presentation Contract identity is invalid")
        return self


class InteractionParentReceiptContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    trajectory_surface: Literal["complete_declared_choice_cartesian_product_per_package"] = (
        "complete_declared_choice_cartesian_product_per_package"
    )
    accepted_trajectory_fields: tuple[str, ...] = (
        "action_acceptance",
        "base_validity",
        "dependency_and_receipt_consistency",
        "first_failed_component",
        "mechanism_semantic_qualification",
        "qualified_validity",
    )
    exact_source_catalog_parents_required: tuple[str, ...] = (
        "source_v174_catalog_id",
        "source_v173_catalog_id",
        "source_v171_catalog_id",
    )
    receipt_mutations_must_execute_production_step: Literal[True] = True
    typed_rejection_must_not_advance_component: Literal[True] = True
    typed_rejection_retry_delta_required: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> InteractionParentReceiptContract:
        if len(set(self.accepted_trajectory_fields)) != len(self.accepted_trajectory_fields):
            raise ValueError("Interaction Contract repeats a projected field")
        if self.contract_id != identity(
            self,
            "contract_id",
            "interaction_parent_receipt_hardening_contract:",
        ):
            raise ValueError("Interaction/Parent/Receipt Contract identity is invalid")
        return self


class StateLocalScheduleCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    schedules: tuple[StateLocalRankSchedule, ...] = Field(min_length=80, max_length=80)
    schedule_count: Literal[80] = 80
    unique_schedule_id_count: Literal[80] = 80
    unique_codebook_count: Literal[80] = 80
    reused_codebook_count: Literal[0] = 0
    reference_first_normalization_count: Literal[0] = 0
    model_outcome_input_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> StateLocalScheduleCatalog:
        if len(self.schedules) != self.schedule_count:
            raise ValueError("State-local Schedule denominator changed")
        if len({item.schedule_id for item in self.schedules}) != self.unique_schedule_id_count:
            raise ValueError("State-local Schedule identity is reused")
        if any(
            item.schedule_contract_id != self.presentation_contract_id for item in self.schedules
        ):
            raise ValueError("State-local Schedule crosses its Presentation Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_state_local_schedule_catalog:",
        ):
            raise ValueError("State-local Schedule Catalog identity is invalid")
        return self


class StateLocalDevelopmentPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_v174_package_artifact_id: str = Field(min_length=1)
    source_v173_package_artifact_id: str = Field(min_length=1)
    source_v171_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    reference_path_hash: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    replica_results: tuple[StepRuntimeResult, ...] = Field(min_length=6, max_length=6)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> StateLocalDevelopmentPackage:
        if len(self.schedule_ids) != len(self.topological_component_keys):
            raise ValueError("State-local Package Schedule denominator changed")
        if len(set(self.schedule_ids)) != len(self.schedule_ids):
            raise ValueError("State-local Package repeats a Component Schedule")
        if tuple(item.replica_index for item in self.replica_results) != tuple(range(6)):
            raise ValueError("State-local Package does not contain six ordered Replicas")
        if any(
            item.package_id != self.package_id
            or item.source_package_id != self.source_package_id
            or tuple(step.component_key for step in item.steps) != self.topological_component_keys
            or item.reference_path_hash != self.reference_path_hash
            or not item.qualified_validity.qualified_valid
            for item in self.replica_results
        ):
            raise ValueError("State-local Package baseline Result parents are inconsistent")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_state_local_presentation_package_artifact:",
        ):
            raise ValueError("State-local Package artifact identity is invalid")
        return self


class StateLocalDevelopmentGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    packages: tuple[StateLocalDevelopmentPackage, ...] = Field(min_length=4, max_length=4)
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> StateLocalDevelopmentGroup:
        expected_depths = tuple(ObservationDepth)
        if tuple(item.depth for item in self.packages) != expected_depths:
            raise ValueError("State-local Group does not contain ordered D0-D3")
        if any(
            item.source_group_id != self.source_group_id
            or item.finance_core_id != self.finance_core_id
            or item.capability_family != self.capability_family
            for item in self.packages
        ):
            raise ValueError("State-local Group crosses a source parent")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_state_local_presentation_group:",
        ):
            raise ValueError("State-local Group identity is invalid")
        return self


class StateLocalDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_v174_catalog_id: str = Field(min_length=1)
    source_v173_catalog_id: str = Field(min_length=1)
    source_v171_catalog_id: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    groups: tuple[StateLocalDevelopmentGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    replica_result_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> StateLocalDevelopmentCatalog:
        packages = tuple(item for group in self.groups for item in group.packages)
        if len(packages) != self.package_count:
            raise ValueError("State-local Development Package denominator changed")
        if sum(len(item.replica_results) for item in packages) != self.replica_result_count:
            raise ValueError("State-local Development Replica denominator changed")
        for field in (
            "artifact_id",
            "package_id",
            "source_v174_package_artifact_id",
            "source_v173_package_artifact_id",
            "source_v171_package_artifact_id",
            "source_package_id",
        ):
            values = tuple(getattr(item, field) for item in packages)
            if len(values) != len(set(values)):
                raise ValueError(f"State-local Development repeats a Package parent:{field}")
        expected = {
            "presentation_contract_id": self.presentation_contract_id,
            "interaction_parent_receipt_contract_id": self.interaction_parent_receipt_contract_id,
            "schedule_catalog_id": self.schedule_catalog_id,
            "mechanism_semantics_contract_id": self.mechanism_semantics_contract_id,
            "failure_receipt_contract_id": self.failure_receipt_contract_id,
            "step_runtime_contract_id": self.step_runtime_contract_id,
            "sequential_estimand_contract_id": self.sequential_estimand_contract_id,
        }
        if any(
            getattr(package, field) != contract_id
            for package in packages
            for field, contract_id in expected.items()
        ):
            raise ValueError("State-local Development Package crosses a Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_state_local_presentation_development_catalog:",
        ):
            raise ValueError("State-local Development Catalog identity is invalid")
        return self


class StateLocalRunnerInputPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_development_package_artifact_id: str = Field(min_length=1)
    source_v174_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    reference_trace_payload_accessible: Literal[False] = False
    precommitted_choice_vector_allowed: Literal[False] = False
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> StateLocalRunnerInputPackage:
        forbidden = {"prompts", "observations", "replica_results", "steps", "reference_traces"}
        if set(type(self).model_fields) & forbidden:
            raise ValueError("State-local Runner Input exposes a dynamic payload")
        if len(self.schedule_ids) != len(self.topological_component_keys):
            raise ValueError("State-local Runner Input Schedule denominator changed")
        if self.package_id != identity(
            self,
            "package_id",
            "finance_v26_state_local_presentation_runner_input_package:",
        ):
            raise ValueError("State-local Runner Input Package identity is invalid")
        return self


class StateLocalRunnerInputCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    expected_source_artifact_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    expected_source_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    packages: tuple[StateLocalRunnerInputPackage, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    future_job_count: Literal[192] = 192
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> StateLocalRunnerInputCatalog:
        if len(self.packages) != self.package_count:
            raise ValueError("State-local Runner Input denominator changed")
        runner_ids = tuple(item.package_id for item in self.packages)
        source_artifacts = tuple(
            item.source_development_package_artifact_id for item in self.packages
        )
        source_ids = tuple(item.source_package_id for item in self.packages)
        if len(set(runner_ids)) != 32:
            raise ValueError("State-local Runner Input repeats a Runner Package")
        if len(set(source_artifacts)) != 32 or len(set(source_ids)) != 32:
            raise ValueError("State-local Runner Input repeats a source Package")
        if set(source_artifacts) != set(self.expected_source_artifact_ids):
            raise ValueError("State-local Runner Input source artifact set changed")
        if set(source_ids) != set(self.expected_source_package_ids):
            raise ValueError("State-local Runner Input source Package set changed")
        if any(
            item.presentation_contract_id != self.presentation_contract_id
            or item.interaction_parent_receipt_contract_id
            != self.interaction_parent_receipt_contract_id
            or item.schedule_catalog_id != self.schedule_catalog_id
            for item in self.packages
        ):
            raise ValueError("State-local Runner Input crosses a current Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_state_local_presentation_runner_input_catalog:",
        ):
            raise ValueError("State-local Runner Input Catalog identity is invalid")
        return self


class HigherOrderShortcutStratum(FrozenModel):
    stratum_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    component_key: str = Field(min_length=1)
    choice_count: int = Field(ge=2, le=3)
    visible_rank_channel_count: int = Field(ge=5, le=8)
    presentation_count: Literal[6] = 6
    structural_baseline_success_count: int = Field(ge=2, le=3)
    registered_univariate_pairwise_rule_count: int = Field(ge=1)
    registered_triple_affine_rule_count: int = Field(ge=1)
    explicit_counterexample_success_count: int = Field(ge=0, le=3)
    maximum_triple_rule_success_count: int = Field(ge=0, le=3)
    triple_rule_excess_count: Literal[0] = 0
    latent_rank_factorization_passed: Literal[True] = True
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_stratum(self) -> HigherOrderShortcutStratum:
        if self.structural_baseline_success_count != 6 // self.choice_count:
            raise ValueError("Higher-order Shortcut baseline changed")
        if self.maximum_triple_rule_success_count > self.structural_baseline_success_count:
            raise ValueError("Higher-order Shortcut exceeds its exact-stratum baseline")
        if self.explicit_counterexample_success_count > self.structural_baseline_success_count:
            raise ValueError("Known three-rank attack survives the state-local Schedule")
        if self.stratum_id != identity(
            self,
            "stratum_id",
            "higher_order_shortcut_stratum:",
        ):
            raise ValueError("Higher-order Shortcut Stratum identity is invalid")
        return self


class HigherOrderPresentationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    strata: tuple[HigherOrderShortcutStratum, ...] = Field(min_length=80, max_length=80)
    stratum_count: Literal[80] = 80
    presentation_count: Literal[480] = 480
    three_choice_state_count: Literal[66] = 66
    three_choice_presentation_count: Literal[396] = 396
    predecessor_explicit_attack_recovery_count: Literal[396] = 396
    current_explicit_attack_recovery_count: int = Field(ge=0, le=132)
    current_structural_baseline_total: Literal[132] = 132
    registered_univariate_pairwise_rule_evaluation_count: int = Field(ge=1)
    registered_triple_affine_rule_evaluation_count: int = Field(ge=1)
    maximum_exact_stratum_recovery_count: int = Field(ge=0, le=3)
    excess_stratum_count: Literal[0] = 0
    unique_state_local_codebook_count: Literal[80] = 80
    reused_state_local_codebook_count: Literal[0] = 0
    reference_first_source_normalization_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> HigherOrderPresentationAudit:
        if len(self.strata) != self.stratum_count:
            raise ValueError("Higher-order Presentation stratum denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_higher_order_presentation_audit:",
        ):
            raise ValueError("Higher-order Presentation Audit identity is invalid")
        return self


class TrajectoryCombinationRow(FrozenModel):
    row_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    selected_source_choice_handles: tuple[str, ...] = Field(min_length=1, max_length=4)
    nonreference_choice_count: int = Field(ge=0, le=4)
    target_component_count: int = Field(ge=1, le=4)
    attempted_component_count: int = Field(ge=1, le=4)
    committed_component_count: int = Field(ge=0, le=4)
    action_acceptance: tuple[bool, ...] = Field(min_length=1, max_length=4)
    all_actions_accepted: bool
    typed_rejection: bool
    first_failed_component_key: str | None = None
    dependency_receipt_consistent: bool
    exact_failure_receipt_consistent: bool
    base_valid: bool | None = None
    mechanism_semantically_qualified: bool | None = None
    qualified_valid: bool | None = None
    reference_path_match: bool | None = None
    task_report_id: str | None = None
    mechanism_report_id: str | None = None
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> TrajectoryCombinationRow:
        if len(self.selected_source_choice_handles) != self.target_component_count:
            raise ValueError("Trajectory combination Choice vector is incomplete")
        if len(self.action_acceptance) != self.attempted_component_count:
            raise ValueError("Trajectory combination acceptance vector is inconsistent")
        if self.committed_component_count != sum(self.action_acceptance):
            raise ValueError("Trajectory combination committed count is inconsistent")
        result_fields = (
            self.base_valid,
            self.mechanism_semantically_qualified,
            self.qualified_valid,
            self.reference_path_match,
            self.task_report_id,
            self.mechanism_report_id,
        )
        if self.all_actions_accepted:
            if (
                not all(self.action_acceptance)
                or self.attempted_component_count != self.target_component_count
                or self.committed_component_count != self.target_component_count
                or any(item is None for item in result_fields)
                or self.typed_rejection
            ):
                raise ValueError("Accepted trajectory combination is incomplete")
            if self.qualified_valid != (self.base_valid and self.mechanism_semantically_qualified):
                raise ValueError("Trajectory combination Qualified validity is not conjunctive")
        elif (
            self.first_failed_component_key is None
            or not self.typed_rejection
            or any(item is not None for item in result_fields)
        ):
            raise ValueError("Rejected trajectory combination boundary is inconsistent")
        if self.row_id != identity(
            self,
            "row_id",
            "full_trajectory_combination_row:",
        ):
            raise ValueError("Trajectory combination Row identity is invalid")
        return self


class ExhaustiveTrajectoryInteractionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[TrajectoryCombinationRow, ...] = Field(min_length=32)
    package_count: Literal[32] = 32
    declared_combination_count: int = Field(ge=32)
    maximum_package_combination_count: int = Field(ge=2, le=81)
    fully_accepted_combination_count: int = Field(ge=32)
    typed_rejected_combination_count: int = Field(ge=1)
    reference_combination_count: Literal[32] = 32
    reference_qualified_count: Literal[32] = 32
    legal_single_choice_nonreference_combination_count: Literal[146] = 146
    multi_nonreference_combination_count: int = Field(ge=1)
    multi_nonreference_fully_accepted_count: int = Field(ge=1)
    base_valid_count: int = Field(ge=1)
    mechanism_semantically_qualified_count: int = Field(ge=1)
    qualified_valid_count: int = Field(ge=1)
    qualified_conjunction_mismatch_count: Literal[0] = 0
    dependency_receipt_failure_count: Literal[0] = 0
    exact_failure_receipt_failure_count: Literal[0] = 0
    runtime_exception_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExhaustiveTrajectoryInteractionAudit:
        if len(self.rows) != self.declared_combination_count:
            raise ValueError("Exhaustive trajectory denominator changed")
        if self.fully_accepted_combination_count + self.typed_rejected_combination_count != len(
            self.rows
        ):
            raise ValueError("Exhaustive trajectory terminal partition changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_exhaustive_trajectory_interaction_audit:",
        ):
            raise ValueError("Exhaustive Trajectory Audit identity is invalid")
        return self


class SourceCatalogParentAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_v174_catalog_match: Literal[True] = True
    source_v173_catalog_match: Literal[True] = True
    source_v171_catalog_match: Literal[True] = True
    package_source_parent_match_count: Literal[32] = 32
    fully_rehashed_top_level_attack_count: Literal[3] = 3
    fully_rehashed_top_level_rejection_count: Literal[3] = 3
    accepted_top_level_attack_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceCatalogParentAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_source_catalog_parent_audit:",
        ):
            raise ValueError("Source Catalog Parent Audit identity is invalid")
        return self


class ReceiptMutationExecution(FrozenModel):
    execution_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    mutation: Literal["error", "missing", "receipt_id", "rule", "selector", "tool"]
    typed_rejected: Literal[True] = True
    action_committed: Literal[False] = False
    retry_invocation_delta: Literal[0] = 0
    recovery_success_event_delta: Literal[0] = 0
    local_tool_invocation_delta: Literal[0] = 0
    target_component_advanced: Literal[False] = False
    next_target_component_advanced: Literal[False] = False
    exact_failure_event_retained: Literal[True] = True
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_execution(self) -> ReceiptMutationExecution:
        if self.execution_id != identity(
            self,
            "execution_id",
            "receipt_mutation_step_execution:",
        ):
            raise ValueError("Receipt mutation execution identity is invalid")
        return self


class RuntimeReceiptMutationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    executions: tuple[ReceiptMutationExecution, ...] = Field(min_length=120, max_length=120)
    recovery_component_count: Literal[20] = 20
    mutation_kind_count: Literal[6] = 6
    production_step_execution_count: Literal[120] = 120
    typed_rejection_count: Literal[120] = 120
    retry_invocation_count: Literal[0] = 0
    recovery_success_event_count: Literal[0] = 0
    local_tool_invocation_count: Literal[0] = 0
    target_component_advance_count: Literal[0] = 0
    next_target_component_advance_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RuntimeReceiptMutationAudit:
        if len(self.executions) != self.production_step_execution_count:
            raise ValueError("Receipt mutation execution denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_runtime_receipt_mutation_audit:",
        ):
            raise ValueError("Runtime Receipt Mutation Audit identity is invalid")
        return self


class ParentClosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_package_reconstruction_match_count: Literal[32] = 32
    schedule_reconstruction_match_count: Literal[80] = 80
    source_catalog_parent_match_count: Literal[3] = 3
    runner_package_reconstruction_match_count: Literal[32] = 32
    runner_unique_source_count: Literal[32] = 32
    runner_missing_count: Literal[0] = 0
    runner_duplicate_count: Literal[0] = 0
    runner_extra_count: Literal[0] = 0
    fully_rehashed_mutation_count: int = Field(ge=8)
    fully_rehashed_rejection_count: int = Field(ge=8)
    accepted_mutation_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentClosureAudit:
        if self.fully_rehashed_mutation_count != self.fully_rehashed_rejection_count:
            raise ValueError("Parent Closure accepted a fully rehashed mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_state_local_parent_closure_audit:",
        ):
            raise ValueError("Parent Closure Audit identity is invalid")
        return self


class DestructiveMutation(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    error_code: str = Field(min_length=1)


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=20)
    mutation_count: int = Field(ge=20)
    rejection_count: int = Field(ge=20)
    acceptance_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if self.mutation_count != len(self.mutations):
            raise ValueError("Production destructive denominator changed")
        if self.rejection_count != self.mutation_count:
            raise ValueError("Production destructive mutation was accepted")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_state_local_production_destructive_audit:",
        ):
            raise ValueError("Production Destructive Audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    gate: str = Field(min_length=1)
    passed: Literal[True] = True
    observed: int | bool | str
    required: int | bool | str


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=15)
    gate_count: int = Field(ge=15)
    passed_gate_count: int = Field(ge=15)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates) or self.passed_gate_count != self.gate_count:
            raise ValueError("Static Gate denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_state_local_presentation_static_audit:",
        ):
            raise ValueError("Static Audit identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    blocked_predecessor_stage: str = Field(min_length=1)
    consumed_stage: Literal[
        "capability_observation_state_local_higher_order_presentation_"
        "and_source_catalog_parent_hardening_only"
    ] = AUTHORIZED_STAGE
    next_stage: Literal[
        "capability_observation_state_local_higher_order_state_bound_step_runtime_"
        "development_runner_preflight_only"
    ] = NEXT_STAGE
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.blocked_predecessor_stage == self.next_stage:
            raise ValueError("v26.175 did not block the stale v26.174 transition")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_state_local_presentation_transition:",
        ):
            raise ValueError("v26.175 Transition identity is invalid")
        return self


class HardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_audit_id: str = Field(min_length=1)
    defect_audit_id: str = Field(min_length=1)
    presentation_contract_id: str = Field(min_length=1)
    interaction_parent_receipt_contract_id: str = Field(min_length=1)
    schedule_catalog_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    higher_order_presentation_audit_id: str = Field(min_length=1)
    exhaustive_trajectory_audit_id: str = Field(min_length=1)
    source_catalog_parent_audit_id: str = Field(min_length=1)
    runtime_receipt_mutation_audit_id: str = Field(min_length=1)
    parent_closure_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    detail_file_count: int = Field(ge=1)
    provider_calls: Literal[0] = 0
    stage2_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    state_assignment_count: Literal[0] = 0
    frequency_row_count: Literal[0] = 0
    contribution_row_count: Literal[0] = 0
    vtdo_row_count: Literal[0] = 0
    next_stage: str = Field(min_length=1)
    schema_version: str = V26_STATE_LOCAL_PRESENTATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> HardeningReport:
        if len(self.detail_files) != self.detail_file_count:
            raise ValueError("v26.175 report detail denominator changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_state_local_presentation_parent_hardening_report:",
        ):
            raise ValueError("v26.175 report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorFreezeAudit
    defect: V174DefectReproductionAudit
    presentation_contract: StateLocalPresentationContract
    interaction_parent_receipt_contract: InteractionParentReceiptContract
    schedule_catalog: StateLocalScheduleCatalog
    development_catalog: StateLocalDevelopmentCatalog
    runner_input_catalog: StateLocalRunnerInputCatalog
    higher_order_presentation_audit: HigherOrderPresentationAudit
    exhaustive_trajectory_audit: ExhaustiveTrajectoryInteractionAudit
    source_catalog_parent_audit: SourceCatalogParentAudit
    runtime_receipt_mutation_audit: RuntimeReceiptMutationAudit
    parent_closure_audit: ParentClosureAudit
    destructive: ProductionDestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: HardeningReport
