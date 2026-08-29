from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.semantic_table_trace_hardening import StepRuntimeResult
from trusted_synthesis.hashing import canonical_hash

V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION = "finance_v26.173_semantic_table_trace_hardening.v1"
AUTHORIZED_STAGE = (
    "capability_observation_semantic_table_deleak_"
    "state_precondition_and_trace_parent_hardening_only"
)
NEXT_STAGE = "capability_observation_state_bound_step_runtime_development_runner_preflight_only"


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
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "external_audit_input",
        "predecessor_artifact",
        "implementation",
        "formal_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(min_length=64, max_length=64)
    review_byte_count: int = Field(ge=1)
    authorized_stage: Literal[
        "capability_observation_semantic_table_deleak_"
        "state_precondition_and_trace_parent_hardening_only"
    ]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_semantic_table_trace_external_authorization:",
        ):
            raise ValueError("v26.173 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.173 source Root count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.173 source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_semantic_table_trace_transitive_source_root:",
        ):
            raise ValueError("v26.173 source Root identity is invalid")
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_runner_input_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=22, max_length=22)
    file_count: Literal[22] = 22
    independent_rebuild_match_count: Literal[22] = 22
    predecessor_mutation_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        if len(self.files) != self.file_count:
            raise ValueError("v26.172 predecessor file denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v172_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.172 predecessor Freeze identity is invalid")
        return self


class V172DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    presentation_count: Literal[480] = 480
    stable_index_rule_state_count: Literal[40] = 40
    stable_index_rule_recovery_count: Literal[240] = 240
    unique_decoded_operation_length_state_count: Literal[32] = 32
    decoded_operation_length_recovery_count: Literal[192] = 192
    external_reported_action_id_rank_imbalanced_state_count: Literal[56] = 56
    direct_recomputed_action_id_rank_imbalanced_state_count: Literal[64] = 64
    minimum_action_id_recovery_count: Literal[197] = 197
    recovery_wrong_current_rule_candidate_count: Literal[20] = 20
    recovery_contract_conflict_count: Literal[6] = 6
    baseline_projection_trace_count: Literal[192] = 192
    accepted_fully_rehashed_parent_mutation_count: Literal[4] = 4
    stale_runner_preflight_blocked: Literal[True] = True
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V172DefectReproductionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v172_semantic_trace_defect_reproduction:",
        ):
            raise ValueError("v26.172 defect reproduction identity is invalid")
        return self


ShortcutSelector = Literal[
    "action_id_order",
    "argument_field_order",
    "candidate_position",
    "catalog_lexical_order",
    "choice_handle_order",
    "encoded_operation_length",
    "fixed_value_handle_vector",
    "legend_position",
    "maximum_value_handle_vector",
    "minimum_value_handle_vector",
]


class SemanticTablePresentationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    replica_count: Literal[6] = 6
    catalog_scope: Literal["package_component_replica_field"] = "package_component_replica_field"
    replica_local_opaque_value_handles_required: Literal[True] = True
    value_handle_lexical_rank_balance_required: Literal[True] = True
    legend_position_balance_required: Literal[True] = True
    candidate_position_balance_required: Literal[True] = True
    display_handle_rank_balance_required: Literal[True] = True
    action_id_rank_balance_required: Literal[True] = True
    encoded_operation_reconstruction_required: Literal[True] = True
    decoded_runtime_operation_reconstruction_required: Literal[True] = True
    visible_padding_allowed: Literal[False] = False
    registered_shortcut_selectors: tuple[ShortcutSelector, ...] = Field(
        min_length=10,
        max_length=10,
    )
    stratum_key: tuple[
        Literal["capability", "depth", "decision_kind", "choice_count", "group"],
        ...,
    ] = ("capability", "depth", "decision_kind", "choice_count", "group")
    preoutcome_salt_sha256: str = Field(min_length=64, max_length=64)
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticTablePresentationContract:
        if len(set(self.registered_shortcut_selectors)) != 10:
            raise ValueError("Semantic Table Contract selector surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "semantic_table_presentation_contract:",
        ):
            raise ValueError("Semantic Table Presentation Contract identity is invalid")
        return self


class StatePreconditionMechanismContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    action_acceptance_is_hard_mechanism_precondition: Literal[True] = True
    selected_rule_equals_current_failed_rule: Literal[True] = True
    failure_revision_retry_share_rule: Literal[True] = True
    failure_revision_retry_share_receipt: Literal[True] = True
    selected_rule_consumed_by_runtime: Literal[True] = True
    invalid_precondition_may_be_qualified: Literal[False] = False
    task_validity_remains_independent: Literal[True] = True
    row_level_legality_mechanism_qualified_binding_required: Literal[True] = True
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> StatePreconditionMechanismContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "state_precondition_mechanism_contract:",
        ):
            raise ValueError("State Precondition Contract identity is invalid")
        return self


class StepRuntimeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    api: tuple[
        Literal["initialize", "render_next_prompt", "step", "finalize"],
        ...,
    ] = ("initialize", "render_next_prompt", "step", "finalize")
    complete_baseline_result_loading_allowed: Literal[False] = False
    static_reference_trace_loading_allowed: Literal[False] = False
    baseline_event_filtering_allowed: Literal[False] = False
    one_current_action_per_step_required: Literal[True] = True
    actual_runtime_event_before_observation_required: Literal[True] = True
    next_prompt_from_reached_receipts_required: Literal[True] = True
    precommitted_choice_vector_allowed: Literal[False] = False
    future_prompt_access_allowed: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> StepRuntimeContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "production_step_runtime_contract:",
        ):
            raise ValueError("Step Runtime Contract identity is invalid")
        return self


class SemanticParentReconstructionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    reconstructed_parents: tuple[str, ...] = Field(min_length=8)
    exact_source_object_reconstruction_required: Literal[True] = True
    saved_hash_as_outcome_oracle_allowed: Literal[False] = False
    fully_rehashed_cross_parent_mutation_must_fail: Literal[True] = True
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticParentReconstructionContract:
        expected = {
            "display_source_handle_mapping",
            "mechanism_report",
            "observation_public_effects",
            "prompt_state_token",
            "receipt_parent",
            "reference_operation",
            "reference_path_hash",
            "runner_input_topology",
        }
        if set(self.reconstructed_parents) != expected:
            raise ValueError("Semantic Parent Contract surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "semantic_parent_reconstruction_contract:",
        ):
            raise ValueError("Semantic Parent Contract identity is invalid")
        return self


class SequentialEstimandContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    registered_future_fields: tuple[str, ...] = Field(min_length=5, max_length=5)
    depth_interpretation: Literal[
        "bounded_sequential_target_decision_depth_not_latent_ability_boundary"
    ] = "bounded_sequential_target_decision_depth_not_latent_ability_boundary"
    final_qualified_only_boundary_forbidden: Literal[True] = True
    empirical_value_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> SequentialEstimandContract:
        expected = {
            "component_specific_hazard",
            "first_failed_component",
            "full_package_success",
            "per_step_conditional_success",
            "task_base_and_mechanism_qualification",
        }
        if set(self.registered_future_fields) != expected:
            raise ValueError("Sequential Estimand field surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "sequential_depth_estimand_contract:",
        ):
            raise ValueError("Sequential Estimand Contract identity is invalid")
        return self


class HardenedDevelopmentPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_v172_package_artifact_id: str = Field(min_length=1)
    source_v171_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    reference_path_hash: str = Field(min_length=1)
    semantic_table_contract_id: str = Field(min_length=1)
    state_precondition_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_reconstruction_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    replica_results: tuple[StepRuntimeResult, ...] = Field(min_length=6, max_length=6)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> HardenedDevelopmentPackage:
        if tuple(item.replica_index for item in self.replica_results) != tuple(range(6)):
            raise ValueError("Hardened Package does not contain six ordered Replicas")
        if any(
            item.package_id != self.package_id
            or item.source_package_id != self.source_package_id
            or tuple(step.component_key for step in item.steps) != self.topological_component_keys
            or item.reference_path_hash != self.reference_path_hash
            or not item.qualified_validity.qualified_valid
            for item in self.replica_results
        ):
            raise ValueError("Hardened Package baseline Result parents are inconsistent")
        for component_index in range(len(self.topological_component_keys)):
            steps = tuple(item.steps[component_index] for item in self.replica_results)
            choice_count = len(steps[0].prompt.candidates)
            expected = 6 // choice_count
            positions = {
                "legend": [
                    next(
                        index
                        for index, item in enumerate(step.prompt.state.choice_legend)
                        if item.choice_handle == step.displayed_choice_handle
                    )
                    for step in steps
                ],
                "candidate": [
                    next(
                        index
                        for index, item in enumerate(step.prompt.candidates)
                        if item.choice_handle == step.displayed_choice_handle
                    )
                    for step in steps
                ],
                "display_rank": [
                    sorted(item.choice_handle for item in step.prompt.candidates).index(
                        step.displayed_choice_handle
                    )
                    for step in steps
                ],
                "action_rank": [
                    sorted(item.action_id for item in step.prompt.candidates).index(
                        step.selected_action_id
                    )
                    for step in steps
                ],
            }
            for name, values in positions.items():
                if any(values.count(index) != expected for index in range(choice_count)):
                    raise ValueError(f"Hardened Package reference {name} is not balanced")
            for field in steps[0].prompt.state.argument_fields:
                value_ranks: list[int] = []
                value_count = len(steps[0].prompt.state.argument_value_catalogs[field])
                for step in steps:
                    encoded = next(
                        item
                        for item in step.prompt.state.choice_legend
                        if item.choice_handle == step.displayed_choice_handle
                    )
                    field_index = step.prompt.state.argument_fields.index(field)
                    selected_handle = encoded.value_handles[field_index]
                    value_ranks.append(
                        sorted(
                            item.value_handle
                            for item in step.prompt.state.argument_value_catalogs[field]
                        ).index(selected_handle)
                    )
                if value_count > 1 and any(
                    value_ranks.count(index) != 6 // value_count for index in range(value_count)
                ):
                    raise ValueError("Hardened Package reference value-handle rank is not balanced")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_semantic_table_trace_package_artifact:",
        ):
            raise ValueError("Hardened Package artifact identity is invalid")
        return self


class HardenedDevelopmentGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    packages: tuple[HardenedDevelopmentPackage, ...] = Field(min_length=4, max_length=4)
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> HardenedDevelopmentGroup:
        if tuple(item.depth for item in self.packages) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("Hardened Group does not contain D0-D3")
        if any(
            item.source_group_id != self.source_group_id
            or item.finance_core_id != self.finance_core_id
            or item.capability_family != self.capability_family
            for item in self.packages
        ):
            raise ValueError("Hardened Group crosses a source parent")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_semantic_table_trace_group:",
        ):
            raise ValueError("Hardened Group identity is invalid")
        return self


class HardenedDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_v172_catalog_id: str = Field(min_length=1)
    source_v171_catalog_id: str = Field(min_length=1)
    semantic_table_contract_id: str = Field(min_length=1)
    state_precondition_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_reconstruction_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    groups: tuple[HardenedDevelopmentGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    replica_result_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> HardenedDevelopmentCatalog:
        packages = tuple(item for group in self.groups for item in group.packages)
        if len(packages) != self.package_count:
            raise ValueError("Hardened Catalog Package denominator changed")
        if sum(len(item.replica_results) for item in packages) != self.replica_result_count:
            raise ValueError("Hardened Catalog Replica denominator changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_semantic_table_trace_development_catalog:",
        ):
            raise ValueError("Hardened Development Catalog identity is invalid")
        return self


class HardenedRunnerInputPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    semantic_table_contract_id: str = Field(min_length=1)
    state_precondition_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_reconstruction_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    reference_trace_payload_accessible: Literal[False] = False
    precommitted_choice_vector_allowed: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> HardenedRunnerInputPackage:
        forbidden = {"prompts", "observations", "replica_results", "steps", "reference_traces"}
        if set(type(self).model_fields) & forbidden:
            raise ValueError("Hardened Runner Input exposes a dynamic payload")
        if self.package_id != identity(
            self,
            "package_id",
            "finance_v26_semantic_table_trace_runner_input_package:",
        ):
            raise ValueError("Hardened Runner Input Package identity is invalid")
        return self


class HardenedRunnerInputCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    packages: tuple[HardenedRunnerInputPackage, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> HardenedRunnerInputCatalog:
        if len(self.packages) != self.package_count:
            raise ValueError("Hardened Runner Input denominator changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_semantic_table_trace_runner_input_catalog:",
        ):
            raise ValueError("Hardened Runner Input Catalog identity is invalid")
        return self


class ShortcutStratum(FrozenModel):
    stratum_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    decision_kind: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    choice_count: int = Field(ge=2, le=3)
    presentation_count: Literal[6] = 6
    structural_baseline_success_count: int = Field(ge=2, le=3)
    selector_success_counts: dict[ShortcutSelector, int] = Field(min_length=10, max_length=10)
    excess_selector_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_stratum(self) -> ShortcutStratum:
        if len(self.selector_success_counts) != 10:
            raise ValueError("Shortcut Stratum selector surface changed")
        if self.structural_baseline_success_count != 6 // self.choice_count:
            raise ValueError("Shortcut Stratum structural baseline is stale")
        if any(
            value > self.structural_baseline_success_count
            for value in self.selector_success_counts.values()
        ):
            raise ValueError("Shortcut Stratum contains systematic reference recovery")
        if self.stratum_id != identity(
            self,
            "stratum_id",
            "semantic_table_shortcut_stratum:",
        ):
            raise ValueError("Shortcut Stratum identity is invalid")
        return self


class StratifiedShortcutAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    strata: tuple[ShortcutStratum, ...] = Field(min_length=80, max_length=80)
    stratum_count: Literal[80] = 80
    target_state_count: Literal[80] = 80
    presentation_count: Literal[480] = 480
    displayed_candidate_count: Literal[1356] = 1356
    selector_count: Literal[10] = 10
    excess_stratum_count: Literal[0] = 0
    stable_cross_replica_value_vector_count: Literal[0] = 0
    unique_encoded_operation_length_presentation_count: Literal[0] = 0
    legend_position_imbalance_count: Literal[0] = 0
    candidate_position_imbalance_count: Literal[0] = 0
    display_handle_rank_imbalance_count: Literal[0] = 0
    action_id_rank_imbalance_count: Literal[0] = 0
    value_handle_rank_imbalance_count: Literal[0] = 0
    visible_padding_field_count: Literal[0] = 0
    claim_scope: Literal[
        "registered_stratified_structural_shortcuts_not_universal_noninterference"
    ] = "registered_stratified_structural_shortcuts_not_universal_noninterference"
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StratifiedShortcutAudit:
        if len(self.strata) != self.stratum_count:
            raise ValueError("Stratified Shortcut denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_stratified_semantic_table_shortcut_audit:",
        ):
            raise ValueError("Stratified Shortcut Audit identity is invalid")
        return self


class RecoveryStateConsistencyAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    wrong_current_rule_candidate_count: Literal[20] = 20
    state_precondition_invalid_count: Literal[20] = 20
    action_acceptance_count: Literal[0] = 0
    mechanism_semantically_qualified_count: Literal[0] = 0
    qualified_valid_count: Literal[0] = 0
    typed_target_mismatch_count: Literal[20] = 20
    retry_after_target_mismatch_count: Literal[0] = 0
    base_valid_count: int = Field(ge=0, le=20)
    reference_recovery_execution_count: Literal[20] = 20
    reference_rule_receipt_lineage_pass_count: Literal[20] = 20
    reference_qualified_count: Literal[20] = 20
    row_level_parent_binding_count: Literal[40] = 40
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RecoveryStateConsistencyAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_recovery_state_consistency_audit:",
        ):
            raise ValueError("Recovery State Consistency Audit identity is invalid")
        return self


class StepRuntimeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    replica_execution_count: Literal[192] = 192
    initialize_count: Literal[192] = 192
    render_current_prompt_count: Literal[480] = 480
    step_count: Literal[480] = 480
    finalize_count: Literal[192] = 192
    reached_observation_count: Literal[480] = 480
    actual_runtime_event_count: int = Field(ge=480)
    predecessor_conditioned_prompt_count: Literal[288] = 288
    bound_predecessor_receipt_link_count: Literal[480] = 480
    complete_baseline_result_load_count: Literal[0] = 0
    baseline_event_filter_count: Literal[0] = 0
    static_reference_trace_input_count: Literal[0] = 0
    reference_qualified_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StepRuntimeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_true_step_runtime_audit:",
        ):
            raise ValueError("Step Runtime Audit identity is invalid")
        return self


class SemanticParentReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_reconstruction_match_count: Literal[32] = 32
    prompt_reconstruction_match_count: Literal[480] = 480
    display_source_mapping_match_count: Literal[480] = 480
    reference_operation_match_count: Literal[480] = 480
    observation_effect_match_count: Literal[480] = 480
    receipt_parent_match_count: Literal[480] = 480
    mechanism_report_match_count: Literal[192] = 192
    reference_path_match_count: Literal[32] = 32
    runner_input_topology_match_count: Literal[32] = 32
    fully_rehashed_mutation_count: Literal[4] = 4
    fully_rehashed_rejection_count: Literal[4] = 4
    accepted_mutation_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticParentReconstructionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_semantic_parent_reconstruction_audit:",
        ):
            raise ValueError("Semantic Parent Reconstruction Audit identity is invalid")
        return self


class SequentialEstimandAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    registered_future_field_count: Literal[5] = 5
    empirical_row_count: Literal[0] = 0
    package_success_estimate_count: Literal[0] = 0
    conditional_step_estimate_count: Literal[0] = 0
    component_hazard_estimate_count: Literal[0] = 0
    latent_ability_boundary_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SequentialEstimandAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_sequential_estimand_registration_audit:",
        ):
            raise ValueError("Sequential Estimand Audit identity is invalid")
        return self


class DestructiveMutation(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    error_code: str = Field(min_length=1)


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=18)
    mutation_count: int = Field(ge=18)
    rejection_count: int = Field(ge=18)
    acceptance_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if self.mutation_count != len(self.mutations) or self.rejection_count != len(
            self.mutations
        ):
            raise ValueError("Production Destructive denominator changed")
        if len({item.mutation for item in self.mutations}) != len(self.mutations):
            raise ValueError("Production Destructive Audit repeats a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_semantic_table_trace_destructive_audit:",
        ):
            raise ValueError("Production Destructive Audit identity is invalid")
        return self


StaticGateName = Literal[
    "action_id_rank_balance",
    "confirmation_access_zero",
    "historical_v172_freeze",
    "parent_reconstruction",
    "production_destructive",
    "provider_and_job_zero",
    "recovery_state_consistency",
    "replica_local_semantic_table",
    "runner_input_zero_prompt",
    "sequential_estimand_registration",
    "source_closure",
    "state_bound_qualified_validity",
    "stratified_shortcut_rejection",
    "true_step_runtime",
    "value_handle_rank_balance",
]


class StaticGate(FrozenModel):
    gate: StaticGateName
    passed: Literal[True] = True
    evidence_count: int = Field(ge=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=15, max_length=15)
    gate_count: Literal[15] = 15
    passed_gate_count: Literal[15] = 15
    scientific_claim: Literal[
        "semantic_table_state_precondition_step_runtime_and_parent_hardening_static_passed"
    ] = "semantic_table_state_precondition_step_runtime_and_parent_hardening_static_passed"
    empirical_model_behavior_measured: Literal[False] = False
    latent_ability_boundary_claimed: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if len({item.gate for item in self.gates}) != self.gate_count:
            raise ValueError("Static Gate surface changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_semantic_table_trace_static_audit:",
        ):
            raise ValueError("Static Audit identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    blocked_predecessor_stage: Literal[
        "capability_observation_dynamic_depth_development_runner_preflight_only"
    ]
    next_stage: Literal[
        "capability_observation_state_bound_step_runtime_development_runner_preflight_only"
    ]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_loading_authorized: Literal[False] = False
    source_task_or_component_change_authorized: Literal[False] = False
    threshold_tuning_authorized: Literal[False] = False
    mapper_state_frequency_or_vtdo_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_semantic_table_trace_transition:",
        ):
            raise ValueError("Prospective Transition identity is invalid")
        return self


class HardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_audit_id: str = Field(min_length=1)
    defect_audit_id: str = Field(min_length=1)
    semantic_table_contract_id: str = Field(min_length=1)
    state_precondition_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_reconstruction_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    shortcut_audit_id: str = Field(min_length=1)
    recovery_audit_id: str = Field(min_length=1)
    step_runtime_audit_id: str = Field(min_length=1)
    parent_reconstruction_audit_id: str = Field(min_length=1)
    sequential_estimand_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=20)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    next_stage: Literal[
        "capability_observation_state_bound_step_runtime_development_runner_preflight_only"
    ]
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> HardeningReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_semantic_table_trace_hardening_report:",
        ):
            raise ValueError("Hardening Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorFreezeAudit
    defect: V172DefectReproductionAudit
    semantic_table_contract: SemanticTablePresentationContract
    state_precondition_contract: StatePreconditionMechanismContract
    step_runtime_contract: StepRuntimeContract
    parent_reconstruction_contract: SemanticParentReconstructionContract
    sequential_estimand_contract: SequentialEstimandContract
    development_catalog: HardenedDevelopmentCatalog
    runner_input_catalog: HardenedRunnerInputCatalog
    shortcut_audit: StratifiedShortcutAudit
    recovery_audit: RecoveryStateConsistencyAudit
    step_runtime_audit: StepRuntimeAudit
    parent_reconstruction_audit: SemanticParentReconstructionAudit
    sequential_estimand_audit: SequentialEstimandAudit
    destructive: ProductionDestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: HardeningReport


def make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    return cast(Any, make_identity_model(model_type, values, field=field, prefix=prefix))
