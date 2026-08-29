from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    BaselineTraceBinding,
    CandidateLegalityProjection,
    DynamicReplicaTrace,
    SemanticMechanismQualification,
)
from trusted_synthesis.hashing import canonical_hash

V26_DYNAMIC_DEPTH_HARDENING_VERSION = "finance_v26.172_dynamic_depth_hardening.v1"


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
        "capability_observation_legend_deleak_mechanism_semantics_and_dynamic_depth_hardening_only"
    ]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_dynamic_depth_external_audit_authorization:",
        ):
            raise ValueError("v26.172 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=3)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.172 source Root count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.172 source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_dynamic_depth_transitive_source_root:",
        ):
            raise ValueError("v26.172 source Root identity is invalid")
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=23, max_length=23)
    file_count: Literal[23] = 23
    independent_rebuild_match_count: Literal[23] = 23
    predecessor_mutation_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        if len(self.files) != self.file_count:
            raise ValueError("v26.171 predecessor file denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v171_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.171 predecessor Freeze identity is invalid")
        return self


class V171DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    replica_prompt_count: Literal[480] = 480
    reference_first_legend_state_count: Literal[80] = 80
    legend_first_reference_recovery_count: Literal[480] = 480
    unique_reference_semantic_length_state_count: Literal[32] = 32
    declared_dependency_link_count: Literal[80] = 80
    dependency_bearing_component_count: Literal[48] = 48
    predecessor_conditioned_prompt_count: Literal[0] = 0
    reverse_topological_stopping_link_count: Literal[12] = 12
    base_true_canonical_mechanism_false_count: Literal[26] = 26
    recovery_wrong_current_rule_runtime_legal_count: Literal[20] = 20
    fully_rehashed_baseline_trace_mutation_accepted_count: Literal[1] = 1
    stale_runner_preflight_blocked: Literal[True] = True
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V171DefectReproductionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v171_dynamic_depth_defect_reproduction:",
        ):
            raise ValueError("v26.171 defect reproduction identity is invalid")
        return self


class JointLegendPresentationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    replica_count: Literal[6] = 6
    legend_and_candidate_joint_balance_required: Literal[True] = True
    display_handle_rank_balance_required: Literal[True] = True
    state_shared_semantic_catalog_required: Literal[True] = True
    fixed_width_semantic_index_rows_required: Literal[True] = True
    visible_padding_allowed: Literal[False] = False
    registered_shortcut_selectors: tuple[
        Literal[
            "legend_first",
            "legend_last",
            "legend_index",
            "semantic_payload_length",
            "lexical_shape",
            "choice_handle_order",
        ],
        ...,
    ] = Field(min_length=6, max_length=6)
    preoutcome_salt_sha256: str = Field(min_length=64, max_length=64)
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> JointLegendPresentationContract:
        if len(set(self.registered_shortcut_selectors)) != 6:
            raise ValueError("Legend Contract does not register all six shortcut selectors")
        if self.contract_id != identity(
            self,
            "contract_id",
            "joint_legend_candidate_presentation_contract:",
        ):
            raise ValueError("Legend Presentation Contract identity is invalid")
        return self


class MechanismSemanticsContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    reference_path_match_is_diagnostic_only: Literal[True] = True
    mechanism_semantically_qualified_is_primary: Literal[True] = True
    recovery_requires_typed_failure_changed_selector_success_and_task_close: Literal[True] = True
    context_requires_real_applied_decision_and_task_close: Literal[True] = True
    reconciliation_requires_emit_then_consume_and_task_close: Literal[True] = True
    stopping_requires_dynamic_readiness_verified_stop_and_no_later_call: Literal[True] = True
    exact_selector_or_record_order_required: Literal[False] = False
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> MechanismSemanticsContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "capability_mechanism_semantics_contract:",
        ):
            raise ValueError("Mechanism Semantics Contract identity is invalid")
        return self


class DynamicDepthRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    topological_component_order_required: Literal[True] = True
    reached_current_state_required: Literal[True] = True
    predecessor_observation_receipt_required: Literal[True] = True
    next_prompt_rebuild_from_receipt_required: Literal[True] = True
    per_step_model_ownership_required: Literal[True] = True
    precommitted_choice_vector_allowed: Literal[False] = False
    future_prompt_access_allowed: Literal[False] = False
    complete_prompt_tuple_materialization_allowed: Literal[False] = False
    depth_interpretation: Literal[
        "bounded_sequential_target_decision_depth_not_latent_ability_boundary"
    ] = "bounded_sequential_target_decision_depth_not_latent_ability_boundary"
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> DynamicDepthRunnerContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "dynamic_depth_runner_contract:",
        ):
            raise ValueError("Dynamic Depth Runner Contract identity is invalid")
        return self


class CandidateLegalityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    layers: tuple[
        Literal[
            "publicly_grounded",
            "publicly_executable",
            "state_precondition_valid",
            "mechanism_relevant",
            "task_semantically_valid",
        ],
        ...,
    ] = Field(min_length=5, max_length=5)
    executable_distractor_may_fail_state_precondition: Literal[True] = True
    runtime_legal_alias_for_all_layers_forbidden: Literal[True] = True
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CandidateLegalityContract:
        if len(set(self.layers)) != 5:
            raise ValueError("Candidate Legality Contract does not separate five layers")
        if self.contract_id != identity(
            self,
            "contract_id",
            "layered_candidate_legality_contract:",
        ):
            raise ValueError("Candidate Legality Contract identity is invalid")
        return self


class BaselineTraceBindingContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    replayed_fields: tuple[str, ...] = Field(min_length=6)
    exact_canonical_result_match_required: Literal[True] = True
    fully_rehashed_trace_mutation_must_fail_closed: Literal[True] = True
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BaselineTraceBindingContract:
        expected = {
            "chosen_choice_handles",
            "runtime_event_ids",
            "runtime_event_order",
            "task_validity_report",
            "mechanism_qualification_report",
            "qualified_validity_report",
        }
        if set(self.replayed_fields) != expected:
            raise ValueError("Baseline Trace Contract replay surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "baseline_trace_parent_binding_contract:",
        ):
            raise ValueError("Baseline Trace Binding Contract identity is invalid")
        return self


class DynamicHardeningPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    reference_path_hash: str = Field(min_length=1)
    baseline_trace_binding: BaselineTraceBinding
    baseline_semantic_mechanism: SemanticMechanismQualification
    replica_traces: tuple[DynamicReplicaTrace, ...] = Field(min_length=6, max_length=6)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> DynamicHardeningPackage:
        if tuple(item.replica_index for item in self.replica_traces) != tuple(range(6)):
            raise ValueError("Dynamic Package does not contain six ordered Replicas")
        if any(
            item.package_id != self.package_id
            or tuple(step.component_key for step in item.steps) != self.topological_component_keys
            or item.terminal_result_id != self.baseline_trace_binding.replay_result_id
            for item in self.replica_traces
        ):
            raise ValueError("Dynamic Package Trace parents are inconsistent")
        if (
            self.baseline_trace_binding.package_id != self.source_package_id
            or self.baseline_semantic_mechanism.package_id != self.source_package_id
            or not self.baseline_semantic_mechanism.reference_path_match
            or not self.baseline_semantic_mechanism.mechanism_semantically_qualified
        ):
            raise ValueError("Dynamic Package baseline parents are inconsistent")
        for component_index in range(len(self.topological_component_keys)):
            steps = tuple(item.steps[component_index] for item in self.replica_traces)
            choice_count = len(steps[0].prompt.state.choice_legend)
            expected = 6 // choice_count
            legend_positions = [
                next(
                    index
                    for index, item in enumerate(step.prompt.state.choice_legend)
                    if item.choice_handle == step.displayed_choice_handle
                )
                for step in steps
            ]
            candidate_positions = [
                next(
                    index
                    for index, item in enumerate(step.prompt.candidates)
                    if item.choice_handle == step.displayed_choice_handle
                )
                for step in steps
            ]
            handle_ranks = [
                sorted(item.choice_handle for item in step.prompt.state.choice_legend).index(
                    step.displayed_choice_handle
                )
                for step in steps
            ]
            for positions in (legend_positions, candidate_positions, handle_ranks):
                if any(positions.count(index) != expected for index in range(choice_count)):
                    raise ValueError("Dynamic Package reference presentation is not balanced")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_dynamic_depth_package_artifact:",
        ):
            raise ValueError("Dynamic Package artifact identity is invalid")
        return self


class DynamicHardeningGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    packages: tuple[DynamicHardeningPackage, ...] = Field(min_length=4, max_length=4)
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> DynamicHardeningGroup:
        if tuple(item.depth for item in self.packages) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("Dynamic Group does not contain D0-D3")
        if any(
            item.source_group_id != self.source_group_id
            or item.finance_core_id != self.finance_core_id
            or item.capability_family != self.capability_family
            for item in self.packages
        ):
            raise ValueError("Dynamic Group crosses a source parent")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_dynamic_depth_group:",
        ):
            raise ValueError("Dynamic Group identity is invalid")
        return self


class DynamicHardeningCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_catalog_id: str = Field(min_length=1)
    legend_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    legality_contract_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    groups: tuple[DynamicHardeningGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    replica_trace_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> DynamicHardeningCatalog:
        packages = tuple(package for group in self.groups for package in group.packages)
        if len(self.groups) != self.group_count or len(packages) != self.package_count:
            raise ValueError("Dynamic Catalog denominator changed")
        if sum(len(item.replica_traces) for item in packages) != self.replica_trace_count:
            raise ValueError("Dynamic Catalog Replica denominator changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_dynamic_depth_development_catalog:",
        ):
            raise ValueError("Dynamic Development Catalog identity is invalid")
        return self


class DynamicRunnerInputPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    legend_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    legality_contract_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    reference_trace_payload_accessible: Literal[False] = False
    precommitted_choice_vector_allowed: Literal[False] = False
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> DynamicRunnerInputPackage:
        forbidden = {
            "baseline_prompts",
            "future_prompts",
            "observations",
            "prompts",
            "reference_traces",
            "replica_traces",
            "steps",
        }
        if set(type(self).model_fields) & forbidden:
            raise ValueError("Runner Input Package contains a future Prompt or Trace field")
        if self.package_id != identity(
            self,
            "package_id",
            "finance_v26_dynamic_depth_runner_input_package:",
        ):
            raise ValueError("Dynamic Runner Input Package identity is invalid")
        return self


class DynamicRunnerInputCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    packages: tuple[DynamicRunnerInputPackage, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    materialized_prompt_count: Literal[0] = 0
    materialized_observation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> DynamicRunnerInputCatalog:
        if len(self.packages) != self.package_count:
            raise ValueError("Dynamic Runner Input denominator changed")
        if len({item.source_package_artifact_id for item in self.packages}) != self.package_count:
            raise ValueError("Dynamic Runner Input repeats a source Package")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_dynamic_depth_runner_input_catalog:",
        ):
            raise ValueError("Dynamic Runner Input Catalog identity is invalid")
        return self


class LegendShortcutAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    presentation_count: Literal[480] = 480
    displayed_candidate_count: Literal[1356] = 1356
    unequal_legend_row_width_count: Literal[0] = 0
    legend_position_imbalance_count: Literal[0] = 0
    candidate_position_imbalance_count: Literal[0] = 0
    display_handle_rank_imbalance_count: Literal[0] = 0
    shortcut_success_counts: dict[str, int] = Field(min_length=6, max_length=6)
    stable_full_recovery_selector_count: Literal[0] = 0
    visible_padding_field_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> LegendShortcutAudit:
        if set(self.shortcut_success_counts) != {
            "legend_first",
            "legend_last",
            "legend_index",
            "semantic_payload_length",
            "lexical_shape",
            "choice_handle_order",
        }:
            raise ValueError("Legend shortcut selector surface changed")
        if any(value >= self.presentation_count for value in self.shortcut_success_counts.values()):
            raise ValueError("a registered Legend shortcut fully recovers the reference")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_legend_shortcut_audit:",
        ):
            raise ValueError("Legend Shortcut Audit identity is invalid")
        return self


class MechanismSemanticsAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_count: Literal[178] = 178
    baseline_count: Literal[32] = 32
    legal_nonreference_count: Literal[146] = 146
    reference_path_match_count: Literal[32] = 32
    semantic_mechanism_qualified_count: int = Field(ge=32, le=178)
    base_true_old_canonical_false_count: Literal[26] = 26
    base_true_old_canonical_false_semantic_true_count: Literal[26] = 26
    context_recovered_semantic_count: Literal[6] = 6
    recovery_recovered_semantic_count: Literal[20] = 20
    base_semantic_matrix: dict[str, int] = Field(min_length=4, max_length=4)
    reference_path_and_semantic_fields_separate: Literal[True] = True
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MechanismSemanticsAudit:
        if sum(self.base_semantic_matrix.values()) != self.execution_count:
            raise ValueError("Mechanism semantic matrix denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_mechanism_semantics_audit:",
        ):
            raise ValueError("Mechanism Semantics Audit identity is invalid")
        return self


class DynamicDepthAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    replica_trace_count: Literal[192] = 192
    reached_prompt_count: Literal[480] = 480
    reached_observation_count: Literal[480] = 480
    topological_component_graph_count: Literal[32] = 32
    declared_dependency_link_count: Literal[80] = 80
    predecessor_conditioned_prompt_count: Literal[288] = 288
    bound_predecessor_receipt_link_count: Literal[480] = 480
    reverse_topological_link_count: Literal[0] = 0
    precommitted_vector_rejection_count: Literal[1] = 1
    future_prompt_access_rejection_count: Literal[1] = 1
    complete_prompt_tuple_field_count: Literal[0] = 0
    depth_claim_is_sequential_burden_not_latent_boundary: Literal[True] = True
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicDepthAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_dynamic_depth_interaction_audit:",
        ):
            raise ValueError("Dynamic Depth Audit identity is invalid")
        return self


class CandidateLegalityCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    projections: tuple[CandidateLegalityProjection, ...] = Field(min_length=226, max_length=226)
    candidate_count: Literal[226] = 226
    publicly_grounded_count: int = Field(ge=1)
    publicly_executable_count: int = Field(ge=1)
    state_precondition_valid_count: int = Field(ge=1)
    mechanism_relevant_count: int = Field(ge=1)
    task_semantically_valid_count: int = Field(ge=1)
    recovery_wrong_current_rule_executable_count: Literal[20] = 20
    recovery_wrong_current_rule_state_valid_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> CandidateLegalityCatalog:
        if len(self.projections) != self.candidate_count:
            raise ValueError("Candidate Legality denominator changed")
        counts = (
            sum(item.publicly_grounded for item in self.projections),
            sum(item.publicly_executable for item in self.projections),
            sum(item.state_precondition_valid for item in self.projections),
            sum(item.mechanism_relevant for item in self.projections),
            sum(item.task_semantically_valid for item in self.projections),
        )
        if counts != (
            self.publicly_grounded_count,
            self.publicly_executable_count,
            self.state_precondition_valid_count,
            self.mechanism_relevant_count,
            self.task_semantically_valid_count,
        ):
            raise ValueError("Candidate Legality layer counts are stale")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_layered_candidate_legality_catalog:",
        ):
            raise ValueError("Candidate Legality Catalog identity is invalid")
        return self


class BaselineTraceParentAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    canonical_result_match_count: Literal[32] = 32
    chosen_handle_match_count: Literal[32] = 32
    event_id_match_count: Literal[32] = 32
    event_order_match_count: Literal[32] = 32
    task_report_match_count: Literal[32] = 32
    mechanism_report_match_count: Literal[32] = 32
    qualified_report_match_count: Literal[32] = 32
    fully_rehashed_trace_mutation_count: int = Field(ge=2)
    fully_rehashed_trace_rejection_count: int = Field(ge=2)
    accepted_mutation_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BaselineTraceParentAudit:
        if self.fully_rehashed_trace_mutation_count != self.fully_rehashed_trace_rejection_count:
            raise ValueError("Baseline trace mutation did not fail closed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_baseline_trace_parent_audit:",
        ):
            raise ValueError("Baseline Trace Parent Audit identity is invalid")
        return self


class ComputedEvidenceScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    registered_selector_count: Literal[6] = 6
    registered_selector_full_recovery_count: Literal[0] = 0
    source_oracle_key_scan_finding_count: Literal[0] = 0
    public_only_selector_failure_count: Literal[0] = 0
    literal_default_evidence_field_count: Literal[0] = 0
    claim_scope: Literal[
        "registered_scans_and_selectors_only_not_complete_model_visible_noninterference"
    ] = "registered_scans_and_selectors_only_not_complete_model_visible_noninterference"
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ComputedEvidenceScopeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_computed_evidence_scope_audit:",
        ):
            raise ValueError("Computed Evidence Scope Audit identity is invalid")
        return self


class DestructiveMutation(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    error_code: str = Field(min_length=1)


class DynamicHardeningDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=12)
    mutation_count: int = Field(ge=12)
    rejection_count: int = Field(ge=12)
    acceptance_count: Literal[0] = 0
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicHardeningDestructiveAudit:
        if self.mutation_count != len(self.mutations) or self.rejection_count != len(
            self.mutations
        ):
            raise ValueError("Dynamic destructive denominator changed")
        if len({item.mutation for item in self.mutations}) != len(self.mutations):
            raise ValueError("Dynamic destructive Audit repeats a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_dynamic_depth_destructive_audit:",
        ):
            raise ValueError("Dynamic Destructive Audit identity is invalid")
        return self


StaticGateName = Literal[
    "baseline_trace_parent_replay",
    "candidate_legality_layers",
    "computed_evidence_scope",
    "confirmation_access_zero",
    "dynamic_depth_interaction",
    "historical_v171_freeze",
    "joint_legend_balance",
    "legend_shortcut_rejection",
    "mechanism_semantic_separation",
    "production_destructive",
    "provider_and_job_zero",
    "source_closure",
]


class StaticGate(FrozenModel):
    gate: StaticGateName
    passed: Literal[True] = True
    evidence_count: int = Field(ge=1)


class DynamicHardeningStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=12, max_length=12)
    gate_count: Literal[12] = 12
    passed_gate_count: Literal[12] = 12
    scientific_claim: Literal[
        "legend_deleak_semantic_mechanism_and_dynamic_interaction_static_preflight_passed"
    ] = "legend_deleak_semantic_mechanism_and_dynamic_interaction_static_preflight_passed"
    empirical_model_behavior_measured: Literal[False] = False
    latent_ability_boundary_claimed: Literal[False] = False
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicHardeningStaticAudit:
        if len({item.gate for item in self.gates}) != self.gate_count:
            raise ValueError("Dynamic Static Gate surface changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_dynamic_depth_static_audit:",
        ):
            raise ValueError("Dynamic Static Audit identity is invalid")
        return self


class DynamicHardeningTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    blocked_predecessor_stage: Literal[
        "capability_observation_validity_separated_causal_deleaked_"
        "development_runner_preflight_only"
    ]
    next_stage: Literal["capability_observation_dynamic_depth_development_runner_preflight_only"]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_loading_authorized: Literal[False] = False
    source_core_change_authorized: Literal[False] = False
    mapper_or_vtdo_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> DynamicHardeningTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_dynamic_depth_transition:",
        ):
            raise ValueError("Dynamic Hardening Transition identity is invalid")
        return self


class DynamicHardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_audit_id: str = Field(min_length=1)
    defect_audit_id: str = Field(min_length=1)
    legend_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    legality_contract_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    legend_audit_id: str = Field(min_length=1)
    mechanism_audit_id: str = Field(min_length=1)
    dynamic_depth_audit_id: str = Field(min_length=1)
    legality_catalog_id: str = Field(min_length=1)
    trace_audit_id: str = Field(min_length=1)
    computed_evidence_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=18)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    next_stage: Literal["capability_observation_dynamic_depth_development_runner_preflight_only"]
    schema_version: str = V26_DYNAMIC_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> DynamicHardeningReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_dynamic_depth_hardening_report:",
        ):
            raise ValueError("Dynamic Hardening Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorFreezeAudit
    defect: V171DefectReproductionAudit
    legend_contract: JointLegendPresentationContract
    mechanism_contract: MechanismSemanticsContract
    runner_contract: DynamicDepthRunnerContract
    legality_contract: CandidateLegalityContract
    trace_contract: BaselineTraceBindingContract
    development_catalog: DynamicHardeningCatalog
    runner_input_catalog: DynamicRunnerInputCatalog
    legend_audit: LegendShortcutAudit
    mechanism_audit: MechanismSemanticsAudit
    dynamic_depth_audit: DynamicDepthAudit
    legality_catalog: CandidateLegalityCatalog
    trace_audit: BaselineTraceParentAudit
    computed_evidence: ComputedEvidenceScopeAudit
    destructive: DynamicHardeningDestructiveAudit
    static: DynamicHardeningStaticAudit
    transition: DynamicHardeningTransition
    report: DynamicHardeningReport


def make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    return cast(
        Any,
        make_identity_model(model_type, values, field=field, prefix=prefix),
    )
