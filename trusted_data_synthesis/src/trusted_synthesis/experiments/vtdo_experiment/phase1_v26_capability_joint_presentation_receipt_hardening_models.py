from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import StepRuntimeResult
from trusted_synthesis.hashing import canonical_hash

V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION = (
    "finance_v26.174_joint_presentation_receipt_hardening.v1"
)
AUTHORIZED_STAGE = (
    "capability_observation_joint_presentation_mechanism_semantics_"
    "receipt_and_runner_parent_hardening_only"
)
NEXT_STAGE = (
    "capability_observation_joint_neutral_state_bound_step_runtime_"
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
        "capability_observation_joint_presentation_mechanism_semantics_"
        "receipt_and_runner_parent_hardening_only"
    ]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_joint_presentation_receipt_external_authorization:",
        ):
            raise ValueError("v26.174 external Authorization identity is invalid")
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
            raise ValueError("v26.174 source Root count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.174 source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_joint_presentation_receipt_transitive_source_root:",
        ):
            raise ValueError("v26.174 source Root identity is invalid")
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_runner_input_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=21, max_length=21)
    file_count: Literal[21] = 21
    independent_rebuild_match_count: Literal[21] = 21
    predecessor_mutation_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        if len(self.files) != self.file_count:
            raise ValueError("v26.173 predecessor file denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v173_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.173 predecessor Freeze identity is invalid")
        return self


class V173DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    presentation_count: Literal[480] = 480
    three_choice_state_count: Literal[66] = 66
    two_choice_state_count: Literal[14] = 14
    three_choice_presentation_count: Literal[396] = 396
    action_rank_candidate_position_recovery_count: Literal[396] = 396
    display_rank_legend_position_recovery_count: Literal[396] = 396
    legal_nonreference_execution_count: Literal[146] = 146
    rejected_base_false_mechanism_false_count: Literal[20] = 20
    accepted_base_false_mechanism_false_count: Literal[102] = 102
    accepted_base_true_mechanism_false_count: Literal[24] = 24
    nonreference_mechanism_qualified_count: Literal[0] = 0
    context_base_true_mechanism_false_count: Literal[6] = 6
    reconciliation_base_true_mechanism_false_count: Literal[4] = 4
    recovery_base_true_mechanism_false_count: Literal[14] = 14
    stopping_base_true_mechanism_false_count: Literal[0] = 0
    same_rule_noncanonical_recovery_count: Literal[20] = 20
    same_rule_retry_success_count: Literal[14] = 14
    same_rule_base_valid_count: Literal[14] = 14
    same_rule_mechanism_qualified_count: Literal[0] = 0
    recovery_prompt_count: Literal[120] = 120
    prompt_receipt_rule_bound_count: Literal[0] = 0
    prompt_runtime_receipt_identity_match_count: Literal[0] = 0
    runtime_internal_receipt_lineage_count: Literal[120] = 120
    receipt_mutation_reference_count: Literal[20] = 20
    receipt_delete_accepted_count: Literal[20] = 20
    receipt_hash_change_accepted_count: Literal[20] = 20
    receipt_error_change_accepted_count: Literal[20] = 20
    explicit_wrong_rule_accepted_count: Literal[0] = 0
    accepted_development_parent_rehash_count: Literal[6] = 6
    accepted_runner_parent_rehash_count: Literal[7] = 7
    duplicate_drop_runner_denominator_accepted: Literal[True] = True
    stale_runner_preflight_blocked: Literal[True] = True
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V173DefectReproductionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v173_joint_receipt_parent_defect_reproduction:",
        ):
            raise ValueError("v26.173 defect reproduction identity is invalid")
        return self


class JointPresentationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    replica_count: Literal[6] = 6
    catalog_scope: Literal["package_component_replica_field"] = "package_component_replica_field"
    one_alias_per_choice_and_field_required: Literal[True] = True
    replica_local_opaque_value_handles_required: Literal[True] = True
    independently_phased_visible_rank_channels: tuple[str, ...] = Field(
        min_length=7,
        max_length=7,
    )
    registered_rule_families: tuple[str, ...] = Field(min_length=6, max_length=6)
    exact_six_replica_stratum_required: Literal[True] = True
    structural_baseline_formula: Literal["replica_count_divided_by_choice_count"] = (
        "replica_count_divided_by_choice_count"
    )
    every_registered_rule_at_or_below_baseline_required: Literal[True] = True
    encoded_operation_reconstruction_required: Literal[True] = True
    decoded_runtime_operation_reconstruction_required: Literal[True] = True
    visible_padding_allowed: Literal[False] = False
    stratum_key: tuple[
        Literal["capability", "depth", "decision_kind", "choice_count", "group"],
        ...,
    ] = ("capability", "depth", "decision_kind", "choice_count", "group")
    preoutcome_salt_sha256: str = Field(min_length=64, max_length=64)
    claim_scope: Literal[
        "registered_univariate_and_pairwise_low_order_rules_not_universal_noninterference"
    ] = "registered_univariate_and_pairwise_low_order_rules_not_universal_noninterference"
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> JointPresentationContract:
        expected_channels = {
            "action_id_rank",
            "candidate_position",
            "display_handle_rank",
            "legend_position",
            "value_handle_rank_0",
            "value_handle_rank_1",
            "value_handle_rank_2_plus",
        }
        expected_families = {
            "univariate_rank_constant",
            "pairwise_affine_mod_choice_count",
            "pairwise_order_relation",
            "rank_position_cross",
            "value_vector_min_max_median",
            "visible_cross_order",
        }
        if set(self.independently_phased_visible_rank_channels) != expected_channels:
            raise ValueError("Joint Presentation rank-channel surface changed")
        if set(self.registered_rule_families) != expected_families:
            raise ValueError("Joint Presentation rule-family surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "joint_presentation_contract:",
        ):
            raise ValueError("Joint Presentation Contract identity is invalid")
        return self


class MechanismSemanticsContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    action_acceptance_is_hard_mechanism_precondition: Literal[True] = True
    selected_rule_equals_current_failed_rule: Literal[True] = True
    failure_revision_retry_share_rule: Literal[True] = True
    failure_revision_retry_share_receipt: Literal[True] = True
    selected_rule_consumed_by_runtime: Literal[True] = True
    context_requires_real_state_decision_and_task_closure: Literal[True] = True
    reconciliation_requires_real_reference_emission_consumption_and_task_closure: Literal[True] = (
        True
    )
    recovery_requires_changed_selector_successful_retry_and_task_closure: Literal[True] = True
    stopping_requires_runtime_readiness_verified_stop_and_no_postcompletion: Literal[True] = True
    exact_reference_selector_required_for_mechanism: Literal[False] = False
    reference_path_match_is_diagnostic_only: Literal[True] = True
    invalid_precondition_may_be_qualified: Literal[False] = False
    task_validity_remains_independent: Literal[True] = True
    row_level_legality_mechanism_qualified_binding_required: Literal[True] = True
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> MechanismSemanticsContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "family_specific_mechanism_semantics_contract:",
        ):
            raise ValueError("Mechanism Semantics Contract identity is invalid")
        return self


class ExactFailureReceiptContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    receipt_fields: tuple[str, ...] = Field(min_length=6, max_length=6)
    real_failure_before_prompt_required: Literal[True] = True
    prompt_and_retry_same_receipt_identity_required: Literal[True] = True
    current_rule_and_failed_selector_binding_required: Literal[True] = True
    exact_error_and_source_tool_binding_required: Literal[True] = True
    missing_field_defaulting_allowed: Literal[False] = False
    retry_after_receipt_mismatch_allowed: Literal[False] = False
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ExactFailureReceiptContract:
        expected = {
            "error_code",
            "failed_selector_hash",
            "failure_event_id",
            "receipt_id",
            "rule_handle",
            "source_tool_id",
        }
        if set(self.receipt_fields) != expected:
            raise ValueError("Exact Failure Receipt field surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "exact_failure_receipt_lifecycle_contract:",
        ):
            raise ValueError("Exact Failure Receipt Contract identity is invalid")
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
    recovery_failure_materialized_before_prompt_required: Literal[True] = True
    recovery_retry_consumes_prompt_receipt_required: Literal[True] = True
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


class ContractDenominatorParentContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    reconstructed_parents: tuple[str, ...] = Field(min_length=15, max_length=15)
    exact_source_object_reconstruction_required: Literal[True] = True
    exact_authoritative_contract_ids_required: Literal[True] = True
    package_id_recomputation_required: Literal[True] = True
    public_task_id_reconstruction_required: Literal[True] = True
    runner_source_set_equality_required: Literal[True] = True
    runner_row_count: Literal[32] = 32
    runner_unique_package_count: Literal[32] = 32
    runner_unique_source_count: Literal[32] = 32
    runner_missing_duplicate_extra_tolerance: Literal[0] = 0
    saved_hash_as_outcome_oracle_allowed: Literal[False] = False
    fully_rehashed_cross_parent_mutation_must_fail: Literal[True] = True
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ContractDenominatorParentContract:
        expected = {
            "authoritative_contract_ids",
            "display_source_handle_mapping",
            "exact_failure_receipt",
            "mechanism_report",
            "observation_public_effects",
            "package_identity",
            "prompt_state_token",
            "public_task_identity",
            "receipt_parent",
            "reference_operation",
            "reference_path_hash",
            "runner_exact_source_set",
            "runner_source_development_catalog",
            "runner_input_topology",
            "source_package_identity",
        }
        if set(self.reconstructed_parents) != expected:
            raise ValueError("Semantic Parent Contract surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "contract_denominator_parent_closure_contract:",
        ):
            raise ValueError("Contract Denominator Parent Contract identity is invalid")
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
    joint_presentation_contract_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_closure_contract_id: str = Field(min_length=1)
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
            "finance_v26_joint_presentation_receipt_package_artifact:",
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
            "finance_v26_joint_presentation_receipt_group:",
        ):
            raise ValueError("Hardened Group identity is invalid")
        return self


class HardenedDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_v173_catalog_id: str = Field(min_length=1)
    source_v171_catalog_id: str = Field(min_length=1)
    joint_presentation_contract_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_closure_contract_id: str = Field(min_length=1)
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
        for field in (
            "artifact_id",
            "package_id",
            "source_v173_package_artifact_id",
            "source_v171_package_artifact_id",
            "source_package_id",
        ):
            values = tuple(getattr(item, field) for item in packages)
            if len(values) != len(set(values)):
                raise ValueError(f"Hardened Catalog repeats Package parent:{field}")
        expected_contracts = {
            "joint_presentation_contract_id": self.joint_presentation_contract_id,
            "mechanism_semantics_contract_id": self.mechanism_semantics_contract_id,
            "failure_receipt_contract_id": self.failure_receipt_contract_id,
            "step_runtime_contract_id": self.step_runtime_contract_id,
            "parent_closure_contract_id": self.parent_closure_contract_id,
            "sequential_estimand_contract_id": self.sequential_estimand_contract_id,
        }
        if any(
            getattr(package, field) != expected
            for package in packages
            for field, expected in expected_contracts.items()
        ):
            raise ValueError("Hardened Catalog Package crosses an authoritative Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_joint_presentation_receipt_development_catalog:",
        ):
            raise ValueError("Hardened Development Catalog identity is invalid")
        return self


class HardenedRunnerInputPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    public_task_id: str = Field(min_length=1)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    joint_presentation_contract_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_closure_contract_id: str = Field(min_length=1)
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
            "finance_v26_joint_presentation_receipt_runner_input_package:",
        ):
            raise ValueError("Hardened Runner Input Package identity is invalid")
        return self


class HardenedRunnerInputCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    joint_presentation_contract_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_closure_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    expected_source_package_artifact_ids: tuple[str, ...] = Field(
        min_length=32,
        max_length=32,
    )
    expected_source_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
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
        runner_ids = tuple(item.package_id for item in self.packages)
        source_artifacts = tuple(item.source_package_artifact_id for item in self.packages)
        source_ids = tuple(item.source_package_id for item in self.packages)
        if len(set(runner_ids)) != 32:
            raise ValueError("Hardened Runner Input does not have 32 unique Package rows")
        if len(set(source_artifacts)) != 32 or len(set(source_ids)) != 32:
            raise ValueError("Hardened Runner Input does not have 32 unique source Packages")
        if set(source_artifacts) != set(self.expected_source_package_artifact_ids):
            raise ValueError("Hardened Runner Input source-artifact denominator changed")
        if set(source_ids) != set(self.expected_source_package_ids):
            raise ValueError("Hardened Runner Input source-Package denominator changed")
        expected_contracts = {
            "joint_presentation_contract_id": self.joint_presentation_contract_id,
            "mechanism_semantics_contract_id": self.mechanism_semantics_contract_id,
            "failure_receipt_contract_id": self.failure_receipt_contract_id,
            "step_runtime_contract_id": self.step_runtime_contract_id,
            "parent_closure_contract_id": self.parent_closure_contract_id,
            "sequential_estimand_contract_id": self.sequential_estimand_contract_id,
        }
        if any(
            getattr(package, field) != expected
            for package in self.packages
            for field, expected in expected_contracts.items()
        ):
            raise ValueError("Hardened Runner Input crosses an authoritative Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_joint_presentation_receipt_runner_input_catalog:",
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
    selector_success_counts: dict[str, int] = Field(min_length=1)
    univariate_rule_count: int = Field(ge=1)
    pairwise_rule_count: int = Field(ge=1)
    vector_combination_rule_count: int = Field(ge=1)
    evaluated_rule_count: int = Field(ge=1)
    maximum_reference_recovery_count: int = Field(ge=0, le=3)
    excess_selector_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_stratum(self) -> ShortcutStratum:
        if self.structural_baseline_success_count != 6 // self.choice_count:
            raise ValueError("Shortcut Stratum structural baseline is stale")
        if self.evaluated_rule_count != len(self.selector_success_counts):
            raise ValueError("Shortcut Stratum rule denominator changed")
        if self.evaluated_rule_count != (
            self.univariate_rule_count
            + self.pairwise_rule_count
            + self.vector_combination_rule_count
        ):
            raise ValueError("Shortcut Stratum rule-family partition changed")
        if self.maximum_reference_recovery_count != max(self.selector_success_counts.values()):
            raise ValueError("Shortcut Stratum maximum is not computed from its rules")
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


class JointShortcutAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    strata: tuple[ShortcutStratum, ...] = Field(min_length=80, max_length=80)
    stratum_count: Literal[80] = 80
    target_state_count: Literal[80] = 80
    presentation_count: Literal[480] = 480
    displayed_candidate_count: Literal[1356] = 1356
    evaluated_rule_count: int = Field(ge=1)
    univariate_rule_evaluation_count: int = Field(ge=1)
    pairwise_rule_evaluation_count: int = Field(ge=1)
    vector_combination_rule_evaluation_count: int = Field(ge=1)
    excess_stratum_count: Literal[0] = 0
    stable_cross_replica_value_vector_count: Literal[0] = 0
    unique_encoded_operation_length_presentation_count: Literal[0] = 0
    legend_position_imbalance_count: Literal[0] = 0
    candidate_position_imbalance_count: Literal[0] = 0
    display_handle_rank_imbalance_count: Literal[0] = 0
    action_id_rank_imbalance_count: Literal[0] = 0
    value_handle_rank_imbalance_count: Literal[0] = 0
    visible_padding_field_count: Literal[0] = 0
    predecessor_action_rank_candidate_position_recovery_count: Literal[396] = 396
    predecessor_display_rank_legend_position_recovery_count: Literal[396] = 396
    current_action_rank_candidate_position_recovery_count: int = Field(ge=0, le=132)
    current_display_rank_legend_position_recovery_count: int = Field(ge=0, le=132)
    claim_scope: Literal[
        "registered_stratified_univariate_and_pairwise_low_order_rules_"
        "not_universal_noninterference"
    ] = (
        "registered_stratified_univariate_and_pairwise_low_order_rules_"
        "not_universal_noninterference"
    )
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> JointShortcutAudit:
        if len(self.strata) != self.stratum_count:
            raise ValueError("Joint Shortcut denominator changed")
        if self.evaluated_rule_count != sum(item.evaluated_rule_count for item in self.strata):
            raise ValueError("Joint Shortcut total rule denominator changed")
        if self.univariate_rule_evaluation_count != sum(
            item.univariate_rule_count for item in self.strata
        ):
            raise ValueError("Joint Shortcut univariate denominator changed")
        if self.pairwise_rule_evaluation_count != sum(
            item.pairwise_rule_count for item in self.strata
        ):
            raise ValueError("Joint Shortcut pairwise denominator changed")
        if self.vector_combination_rule_evaluation_count != sum(
            item.vector_combination_rule_count for item in self.strata
        ):
            raise ValueError("Joint Shortcut vector denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_joint_presentation_shortcut_audit:",
        ):
            raise ValueError("Joint Shortcut Audit identity is invalid")
        return self


class MechanismSemanticsAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    legal_nonreference_execution_count: Literal[146] = 146
    wrong_current_rule_candidate_count: Literal[20] = 20
    wrong_current_rule_rejection_count: Literal[20] = 20
    accepted_nonreference_count: Literal[126] = 126
    base_valid_nonreference_count: Literal[24] = 24
    mechanism_qualified_nonreference_count: int = Field(ge=24, le=126)
    qualified_valid_nonreference_count: Literal[24] = 24
    base_valid_mechanism_false_count: Literal[0] = 0
    context_noncanonical_base_and_mechanism_valid_count: Literal[6] = 6
    reconciliation_noncanonical_base_and_mechanism_valid_count: Literal[4] = 4
    same_rule_noncanonical_recovery_count: Literal[20] = 20
    same_rule_retry_success_count: Literal[14] = 14
    same_rule_base_valid_count: Literal[14] = 14
    same_rule_mechanism_qualified_count: Literal[14] = 14
    same_rule_qualified_valid_count: Literal[14] = 14
    exact_reference_selector_required_count: Literal[0] = 0
    reference_path_diagnostic_only_count: Literal[146] = 146
    reference_baseline_count: Literal[192] = 192
    reference_baseline_qualified_count: Literal[192] = 192
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> MechanismSemanticsAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_family_specific_mechanism_semantics_audit:",
        ):
            raise ValueError("Mechanism Semantics Audit identity is invalid")
        return self


class ExactFailureReceiptAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    recovery_prompt_count: Literal[120] = 120
    real_failure_before_prompt_count: Literal[120] = 120
    prompt_receipt_complete_count: Literal[120] = 120
    prompt_runtime_receipt_identity_match_count: Literal[120] = 120
    failure_retry_receipt_identity_match_count: Literal[120] = 120
    rule_binding_match_count: Literal[120] = 120
    failed_selector_hash_match_count: Literal[120] = 120
    error_code_match_count: Literal[120] = 120
    source_tool_match_count: Literal[120] = 120
    missing_receipt_rejection_count: Literal[20] = 20
    changed_receipt_id_rejection_count: Literal[20] = 20
    changed_error_rejection_count: Literal[20] = 20
    changed_selector_hash_rejection_count: Literal[20] = 20
    changed_source_tool_rejection_count: Literal[20] = 20
    changed_rule_rejection_count: Literal[20] = 20
    retry_after_receipt_rejection_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExactFailureReceiptAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_exact_failure_receipt_lifecycle_audit:",
        ):
            raise ValueError("Exact Failure Receipt Audit identity is invalid")
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
    preprompt_failure_event_count: Literal[120] = 120
    retry_consuming_exact_receipt_count: Literal[120] = 120
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


class ParentClosureAudit(FrozenModel):
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
    authoritative_contract_binding_match_count: Literal[192] = 192
    package_identity_recomputation_match_count: Literal[32] = 32
    public_task_identity_match_count: Literal[32] = 32
    runner_unique_package_count: Literal[32] = 32
    runner_unique_source_artifact_count: Literal[32] = 32
    runner_unique_source_package_count: Literal[32] = 32
    runner_missing_count: Literal[0] = 0
    runner_duplicate_count: Literal[0] = 0
    runner_extra_count: Literal[0] = 0
    fully_rehashed_mutation_count: Literal[16] = 16
    fully_rehashed_rejection_count: Literal[16] = 16
    accepted_mutation_count: Literal[0] = 0
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentClosureAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_contract_denominator_parent_closure_audit:",
        ):
            raise ValueError("Parent Closure Audit identity is invalid")
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
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=28)
    mutation_count: int = Field(ge=28)
    rejection_count: int = Field(ge=28)
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
    "authoritative_contract_binding",
    "confirmation_access_zero",
    "exact_failure_receipt_lifecycle",
    "historical_v173_freeze",
    "joint_pairwise_shortcut_rejection",
    "joint_presentation_phase_balance",
    "mechanism_semantics_restoration",
    "package_identity_recomputation",
    "parent_closure",
    "preprompt_failure_materialization",
    "production_destructive",
    "provider_and_job_zero",
    "runner_exact_denominator",
    "runner_input_zero_prompt",
    "sequential_estimand_registration",
    "source_closure",
    "state_bound_qualified_validity",
    "true_step_runtime",
    "wrong_current_rule_rejection",
]


class StaticGate(FrozenModel):
    gate: StaticGateName
    passed: Literal[True] = True
    evidence_count: int = Field(ge=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=18, max_length=18)
    gate_count: Literal[18] = 18
    passed_gate_count: Literal[18] = 18
    scientific_claim: Literal[
        "joint_presentation_mechanism_receipt_runtime_and_parent_hardening_static_passed"
    ] = "joint_presentation_mechanism_receipt_runtime_and_parent_hardening_static_passed"
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
            "finance_v26_joint_presentation_receipt_static_audit:",
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
        "capability_observation_state_bound_step_runtime_development_runner_preflight_only"
    ]
    next_stage: Literal[
        "capability_observation_joint_neutral_state_bound_step_runtime_"
        "development_runner_preflight_only"
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
            "finance_v26_joint_presentation_receipt_transition:",
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
    joint_presentation_contract_id: str = Field(min_length=1)
    mechanism_semantics_contract_id: str = Field(min_length=1)
    failure_receipt_contract_id: str = Field(min_length=1)
    step_runtime_contract_id: str = Field(min_length=1)
    parent_closure_contract_id: str = Field(min_length=1)
    sequential_estimand_contract_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    runner_input_catalog_id: str = Field(min_length=1)
    joint_shortcut_audit_id: str = Field(min_length=1)
    mechanism_semantics_audit_id: str = Field(min_length=1)
    failure_receipt_audit_id: str = Field(min_length=1)
    step_runtime_audit_id: str = Field(min_length=1)
    parent_closure_audit_id: str = Field(min_length=1)
    sequential_estimand_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=20)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    next_stage: Literal[
        "capability_observation_joint_neutral_state_bound_step_runtime_"
        "development_runner_preflight_only"
    ]
    schema_version: str = V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> HardeningReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_joint_presentation_receipt_hardening_report:",
        ):
            raise ValueError("Hardening Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorFreezeAudit
    defect: V173DefectReproductionAudit
    joint_presentation_contract: JointPresentationContract
    mechanism_semantics_contract: MechanismSemanticsContract
    failure_receipt_contract: ExactFailureReceiptContract
    step_runtime_contract: StepRuntimeContract
    parent_closure_contract: ContractDenominatorParentContract
    sequential_estimand_contract: SequentialEstimandContract
    development_catalog: HardenedDevelopmentCatalog
    runner_input_catalog: HardenedRunnerInputCatalog
    joint_shortcut_audit: JointShortcutAudit
    mechanism_semantics_audit: MechanismSemanticsAudit
    failure_receipt_audit: ExactFailureReceiptAudit
    step_runtime_audit: StepRuntimeAudit
    parent_closure_audit: ParentClosureAudit
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
