from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.program import ProgramVerification
from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalPublicPrompt,
    CausalSemanticExecutionResult,
    CausalTargetComponent,
    ValiditySeparatedPublicTask,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.hashing import canonical_hash

V26_VALIDITY_CAUSAL_REAUDIT_VERSION = (
    "finance_v26_validity_separation_presentation_deleak_causal_reaudit.v1"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "external_audit_input",
        "formal_output",
        "implementation",
        "transitive_source",
        "v26_170_frozen_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["0a9e048bf1d83540185af60c64bb138a503a880689e8aeecf32efb5bec40f5b8"]
    review_byte_count: Literal[26048] = 26_048
    authorized_stage: Literal[
        "capability_observation_validity_separation_presentation_deleak_and_causal_component_reaudit_only"
    ]
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_validity_causal_external_audit_authorization:",
        ):
            raise ValueError("v26.171 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=4)
    file_count: int = Field(ge=4)
    complete_static_import_closure: Literal[True] = True
    unresolved_trusted_synthesis_import_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.171 transitive source count changed")
        if len({item.relative_path for item in self.files}) != len(self.files):
            raise ValueError("v26.171 transitive source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_validity_causal_transitive_source_root:",
        ):
            raise ValueError("v26.171 transitive source Root identity is invalid")
        return self


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    bindings: tuple[FileBinding, ...] = Field(min_length=18, max_length=18)
    matched_file_count: Literal[18] = 18
    predecessor_mutation_count: Literal[0] = 0
    stale_runner_preflight_transition_blocked: Literal[True] = True
    sealed_confirmation_payload_loaded: Literal[False] = False
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        if len(self.bindings) != self.matched_file_count:
            raise ValueError("v26.170 predecessor binding count changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v170_predecessor_integrity:",
        ):
            raise ValueError("v26.170 predecessor integrity identity is invalid")
        return self


class V170DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    nonreference_choice_count: Literal[160] = 160
    nonreference_program_valid_count: Literal[100] = 100
    nonreference_program_answer_postcompletion_valid_count: Literal[76] = 76
    depth_increment_counterfactual_count: Literal[48] = 48
    depth_increment_program_valid_count: Literal[28] = 28
    depth_increment_task_semantic_valid_count: Literal[24] = 24
    unique_reference_padding_length_state_count: Literal[34] = 34
    unique_reference_padding_length_presentation_count: Literal[204] = 204
    compare_core_internal_reference_output_count: Literal[6] = 6
    visible_padding_field_count: int = Field(ge=1)
    base_reference_equality_coupling_reproduced: Literal[True] = True
    historical_artifact_rewritten: Literal[False] = False
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V170DefectReproductionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v170_validity_padding_defect_reproduction:",
        ):
            raise ValueError("v26.170 defect reproduction identity is invalid")
        return self


class ValiditySeparationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    base_inputs: tuple[str, ...] = Field(min_length=9, max_length=9)
    mechanism_input: Literal["capability_family_specific_causal_trace"] = (
        "capability_family_specific_causal_trace"
    )
    qualified_formula: Literal["base_valid and mechanism_qualified"] = (
        "base_valid and mechanism_qualified"
    )
    host_reference_allowed_in_base: Literal[False] = False
    base_true_mechanism_false_required: Literal[True] = True
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ValiditySeparationContract:
        expected = (
            "local_program_contract_valid",
            "operation_lineage_complete",
            "answer_projection_complete",
            "answer_schema_valid",
            "public_answer_semantically_valid",
            "reference_identity_valid",
            "citation_complete",
            "terminal_verification_complete",
            "postcompletion_control_passed",
        )
        if self.base_inputs != expected:
            raise ValueError("Base validity input language changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "validity_separation_contract:",
        ):
            raise ValueError("Validity Separation Contract identity is invalid")
        return self


class CausalComponentContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    allowed_decisions_by_family: dict[CapabilityFamily, tuple[str, ...]]
    real_program_effect_required: Literal[True] = True
    recovery_failure_must_be_observed: Literal[True] = True
    normalization_reference_must_be_consumed: Literal[True] = True
    readiness_receipt_must_be_runtime_derived: Literal[True] = True
    reconciliation_operator_target_forbidden: Literal[True] = True
    dynamic_dependency_receipt_required: Literal[True] = True
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CausalComponentContract:
        if set(self.allowed_decisions_by_family) != set(CapabilityFamily):
            raise ValueError("Causal Component Contract omits a capability family")
        if self.contract_id != identity(
            self,
            "contract_id",
            "causal_component_contract:",
        ):
            raise ValueError("Causal Component Contract identity is invalid")
        return self


class DeleakedPresentationPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    replica_count: Literal[6] = 6
    fixed_width_choice_handle: Literal[True] = True
    visible_padding_allowed: Literal[False] = False
    candidate_byte_length_must_be_equal: Literal[True] = True
    candidate_field_count_must_be_equal: Literal[True] = True
    candidate_argument_count_cue_forbidden: Literal[True] = True
    semantic_payload_lives_in_public_state_legend: Literal[True] = True
    preoutcome_fixed_salt_sha256: str = Field(min_length=64, max_length=64)
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> DeleakedPresentationPolicy:
        if self.policy_id != identity(
            self,
            "policy_id",
            "deleaked_public_candidate_presentation_policy:",
        ):
            raise ValueError("Deleaked Presentation Policy identity is invalid")
        return self


class SemanticParentBindingContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    recomputed_fields: tuple[str, ...] = Field(min_length=6)
    whole_graph_rehash_must_fail_closed: Literal[True] = True
    depth_increment_five_parent_binding_required: Literal[True] = True
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> SemanticParentBindingContract:
        expected = {
            "reference_choice_handle",
            "source_program_verification_hash",
            "source_public_task_hash",
            "source_public_evidence_semantic_hash",
            "projected_public_task_id",
            "source_finance_core_id",
        }
        if set(self.recomputed_fields) != expected:
            raise ValueError("Semantic parent recomputation surface changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "semantic_parent_binding_contract:",
        ):
            raise ValueError("Semantic Parent Binding Contract identity is invalid")
        return self


class SourceSemanticParentBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    source_finance_core_id: str = Field(min_length=1)
    source_v170_package_artifact_id: str = Field(min_length=1)
    source_v168_package_id: str = Field(min_length=1)
    source_program_verification: ProgramVerification
    source_program_verification_hash: str = Field(min_length=1)
    source_public_task_hash: str = Field(min_length=1)
    source_public_evidence_semantic_hash: str = Field(min_length=1)
    projected_public_task_id: str = Field(min_length=1)
    parent_binding_contract_id: str = Field(min_length=1)
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> SourceSemanticParentBinding:
        expected = canonical_hash(
            self.source_program_verification.model_dump(mode="json"),
            prefix="source_program_verification:",
        )
        if self.source_program_verification_hash != expected:
            raise ValueError("source Program Verification hash is stale")
        if not self.source_program_verification.passed:
            raise ValueError("source Program Verification did not pass")
        if self.binding_id != identity(
            self,
            "binding_id",
            "causal_semantic_source_parent_binding:",
        ):
            raise ValueError("Source Semantic Parent Binding identity is invalid")
        return self


class ReplicaPresentation(FrozenModel):
    presentation_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    prompt: CausalPublicPrompt
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_presentation(self) -> ReplicaPresentation:
        if self.presentation_id != identity(
            self,
            "presentation_id",
            "causal_deleaked_replica_presentation:",
        ):
            raise ValueError("Replica Presentation identity is invalid")
        return self


class CausalPromptBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    public_task_id: str = Field(min_length=1)
    component_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    baseline_prompts: tuple[CausalPublicPrompt, ...] = Field(min_length=1, max_length=4)
    prompt_count: int = Field(ge=1, le=4)
    dynamic_predecessor_receipts_required: bool
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> CausalPromptBinding:
        if self.prompt_count != len(self.baseline_prompts):
            raise ValueError("Causal Prompt Binding count changed")
        if any(item.task.task_id != self.public_task_id for item in self.baseline_prompts):
            raise ValueError("Causal Prompt Binding crosses a public Task")
        if self.binding_id != identity(
            self,
            "binding_id",
            "causal_public_prompt_binding:",
        ):
            raise ValueError("Causal Prompt Binding identity is invalid")
        return self


class CausalTargetLoad(FrozenModel):
    load_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    target_component_count: int = Field(ge=1, le=4)
    family_validator_passed_count: int = Field(ge=1, le=4)
    nuisance_model_choice_count: Literal[0] = 0
    deterministic_nuisance_execution: Literal[True] = True
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_load(self) -> CausalTargetLoad:
        expected = OBSERVATION_DEPTH_ORDER.index(self.depth) + 1
        if (
            self.target_component_count != expected
            or self.family_validator_passed_count != expected
        ):
            raise ValueError("Causal target Load does not match D0-D3")
        if self.load_id != identity(
            self,
            "load_id",
            "causal_family_validated_target_load:",
        ):
            raise ValueError("Causal target Load identity is invalid")
        return self


class ValiditySeparatedCausalPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_v170_package_artifact_id: str = Field(min_length=1)
    source_v170_group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    finance_core_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    validity_contract_id: str = Field(min_length=1)
    component_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    parent_binding_contract_id: str = Field(min_length=1)
    public_task: ValiditySeparatedPublicTask
    source_parent_binding: SourceSemanticParentBinding
    components: tuple[CausalTargetComponent, ...] = Field(min_length=1, max_length=4)
    prompt_binding: CausalPromptBinding
    replica_presentations: tuple[ReplicaPresentation, ...] = Field(
        min_length=6,
        max_length=24,
    )
    target_load: CausalTargetLoad
    baseline_execution: CausalSemanticExecutionResult
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    runner_preflighted: Literal[False] = False
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> ValiditySeparatedCausalPackage:
        expected_id = canonical_hash(
            {
                "source_v170_package_artifact_id": self.source_v170_package_artifact_id,
                "capability_family": self.capability_family.value,
                "depth": self.depth.value,
                "finance_core_id": self.finance_core_id,
                "fixed_generation_condition_id": self.fixed_generation_condition_id,
                "validity_contract_id": self.validity_contract_id,
                "component_contract_id": self.component_contract_id,
                "presentation_policy_id": self.presentation_policy_id,
                "parent_binding_contract_id": self.parent_binding_contract_id,
                "public_task_id": self.public_task.task_id,
                "component_keys": [item.component_key for item in self.components],
                "schema_version": self.schema_version,
            },
            prefix="finance_v26_validity_causal_package:",
        )
        if self.package_id != expected_id:
            raise ValueError("Validity-separated causal Package identity is invalid")
        if (
            self.source_parent_binding.source_finance_core_id != self.finance_core_id
            or self.source_parent_binding.source_v170_package_artifact_id
            != self.source_v170_package_artifact_id
            or self.source_parent_binding.projected_public_task_id != self.public_task.task_id
            or self.source_parent_binding.parent_binding_contract_id
            != self.parent_binding_contract_id
            or self.prompt_binding.package_id != self.package_id
            or self.prompt_binding.public_task_id != self.public_task.task_id
            or self.prompt_binding.component_contract_id != self.component_contract_id
            or self.prompt_binding.presentation_policy_id != self.presentation_policy_id
            or self.target_load.package_id != self.package_id
            or self.target_load.capability_family != self.capability_family
            or self.target_load.depth != self.depth
            or self.target_load.target_component_count != len(self.components)
            or self.baseline_execution.package_id != self.package_id
            or not self.baseline_execution.qualified_validity.qualified_valid
        ):
            raise ValueError("Validity-separated causal Package parent binding is inconsistent")
        if any(
            item.capability_family != self.capability_family or item.depth != self.depth
            for item in self.components
        ):
            raise ValueError("Validity-separated Package crosses a target family or depth")
        expected_rows = {
            (component.component_id, replica)
            for component in self.components
            for replica in range(6)
        }
        observed_rows = {
            (item.component_id, item.replica_index) for item in self.replica_presentations
        }
        if expected_rows != observed_rows:
            raise ValueError("Validity-separated Package Replica surface is incomplete")
        component_by_id = {item.component_id: item for item in self.components}
        for row in self.replica_presentations:
            component = component_by_id[row.component_id]
            if (
                row.package_id != self.package_id
                or row.prompt.task != self.public_task
                or row.prompt.state != component.public_state
            ):
                raise ValueError("Replica Presentation crosses a Package parent")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_validity_causal_package_artifact:",
        ):
            raise ValueError("Validity-separated Package artifact identity is invalid")
        return self


class ValiditySeparatedCausalGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    source_v170_group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    finance_core_id: str = Field(min_length=1)
    packages: tuple[ValiditySeparatedCausalPackage, ...] = Field(
        min_length=4,
        max_length=4,
    )
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> ValiditySeparatedCausalGroup:
        if tuple(item.depth for item in self.packages) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("Validity-separated Group does not contain D0-D3")
        if any(
            item.source_v170_group_id != self.source_v170_group_id
            or item.capability_family != self.capability_family
            or item.finance_core_id != self.finance_core_id
            for item in self.packages
        ):
            raise ValueError("Validity-separated Group contains a crossed Package")
        component_sets = [
            set(item.component_key for item in package.components) for package in self.packages
        ]
        for source, target in zip(component_sets, component_sets[1:], strict=False):
            if not source < target or len(target - source) != 1:
                raise ValueError("Validity-separated depth does not add one Component")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_validity_causal_group:",
        ):
            raise ValueError("Validity-separated Group identity is invalid")
        return self


class ValiditySeparatedDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    source_v170_catalog_id: str = Field(min_length=1)
    source_v170_report_id: str = Field(min_length=1)
    sealed_confirmation_receipt_id: str = Field(min_length=1)
    validity_contract_id: str = Field(min_length=1)
    component_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    parent_binding_contract_id: str = Field(min_length=1)
    finance_cores: tuple[v168_models.LowNuisanceFinanceCore, ...] = Field(
        min_length=8,
        max_length=8,
    )
    groups: tuple[ValiditySeparatedCausalGroup, ...] = Field(min_length=8, max_length=8)
    finance_core_count: Literal[8] = 8
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    confirmation_payload_access_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> ValiditySeparatedDevelopmentCatalog:
        cores = {item.core_id: item for item in self.finance_cores}
        if len(cores) != self.finance_core_count or len(self.groups) != self.group_count:
            raise ValueError("Validity-separated Catalog denominator changed")
        if sum(len(item.packages) for item in self.groups) != self.package_count:
            raise ValueError("Validity-separated Catalog Package count changed")
        if len({item.source_v170_group_id for item in self.groups}) != self.group_count:
            raise ValueError("Validity-separated Catalog repeats a source Group")
        if any(item.finance_core_id not in cores for item in self.groups):
            raise ValueError("Validity-separated Catalog references an absent Finance Core")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_validity_separated_development_catalog:",
        ):
            raise ValueError("Validity-separated Development Catalog identity is invalid")
        return self


class PublicAnswerProjectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    finance_core_count: Literal[8] = 8
    package_count: Literal[32] = 32
    compare_core_count: Literal[6] = 6
    compare_package_count: Literal[24] = 24
    raw_internal_reference_package_count: Literal[24] = 24
    public_reference_projection_complete_count: Literal[24] = 24
    exact_answer_schema_pass_count: Literal[32] = 32
    canonical_semantic_match_count: Literal[32] = 32
    citation_complete_count: Literal[32] = 32
    baseline_base_valid_count: Literal[32] = 32
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicAnswerProjectionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_answer_projection_audit:",
        ):
            raise ValueError("Public Answer Projection Audit identity is invalid")
        return self


class ValiditySeparationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    baseline_count: Literal[32] = 32
    baseline_base_valid_count: Literal[32] = 32
    baseline_mechanism_qualified_count: Literal[32] = 32
    baseline_qualified_valid_count: Literal[32] = 32
    nonreference_counterfactual_count: int = Field(ge=1)
    base_true_mechanism_true_count: int = Field(ge=0)
    base_true_mechanism_false_count: int = Field(ge=1)
    base_false_mechanism_true_count: int = Field(ge=0)
    base_false_mechanism_false_count: int = Field(ge=1)
    base_reference_metadata_input_count: Literal[0] = 0
    shared_base_mechanism_report_id_count: Literal[0] = 0
    qualified_conjunction_match_count: int = Field(ge=1)
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ValiditySeparationAudit:
        matrix_total = sum(
            (
                self.base_true_mechanism_true_count,
                self.base_true_mechanism_false_count,
                self.base_false_mechanism_true_count,
                self.base_false_mechanism_false_count,
            )
        )
        if matrix_total != self.nonreference_counterfactual_count:
            raise ValueError("Validity Separation matrix denominator changed")
        if self.qualified_conjunction_match_count != self.nonreference_counterfactual_count:
            raise ValueError("Qualified validity conjunction does not close")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_validity_separation_audit:",
        ):
            raise ValueError("Validity Separation Audit identity is invalid")
        return self


class CausalComponentAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    target_component_count: Literal[80] = 80
    component_causal_effect_count: Literal[80] = 80
    real_task_program_executor_call_count: int = Field(ge=32)
    real_task_program_verifier_call_count: Literal[32] = 32
    normalization_runtime_call_count: int = Field(ge=1)
    normalized_reference_emitted_count: int = Field(ge=1)
    normalized_reference_consumed_count: int = Field(ge=1)
    typed_failure_observation_count: int = Field(ge=1)
    successful_recovery_count: int = Field(ge=1)
    dynamic_readiness_receipt_count: int = Field(ge=1)
    wrong_readiness_changes_terminal_count: int = Field(ge=1)
    postcompletion_control_count: int = Field(ge=1)
    synthetic_set_result_effect_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CausalComponentAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_causal_component_execution_audit:",
        ):
            raise ValueError("Causal Component Audit identity is invalid")
        return self


class ComponentFamilyAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_component_count: Literal[80] = 80
    family_validator_pass_count: Literal[80] = 80
    family_validator_failure_count: Literal[0] = 0
    reconciliation_operator_target_count: Literal[0] = 0
    non_target_model_choice_count: Literal[0] = 0
    dynamic_dependency_link_count: int = Field(ge=1)
    dependency_order_failure_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ComponentFamilyAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_component_family_validator_audit:",
        ):
            raise ValueError("Component Family Audit identity is invalid")
        return self


class CandidateLegalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    semantic_candidate_count: int = Field(ge=160)
    publicly_grounded_candidate_count: int = Field(ge=160)
    runtime_legal_candidate_count: int = Field(ge=160)
    publicly_grounded_distractor_count: int = Field(ge=1)
    illegal_operator_candidate_count: Literal[0] = 0
    ungrounded_candidate_count: Literal[0] = 0
    legal_action_claim_matches_count: int = Field(ge=160)
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CandidateLegalityAudit:
        if not (
            self.semantic_candidate_count
            == self.publicly_grounded_candidate_count
            == self.runtime_legal_candidate_count
            == self.legal_action_claim_matches_count
        ):
            raise ValueError("Candidate legality denominator does not close")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_candidate_legality_audit:",
        ):
            raise ValueError("Candidate Legality Audit identity is invalid")
        return self


class PresentationDeleakAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    replica_count: Literal[6] = 6
    presentation_count: Literal[480] = 480
    displayed_candidate_count: int = Field(ge=960)
    visible_padding_field_count: Literal[0] = 0
    padding_only_unique_selector_count: Literal[0] = 0
    candidate_byte_length_unique_selector_count: Literal[0] = 0
    argument_count_unique_selector_count: Literal[0] = 0
    field_count_unique_selector_count: Literal[0] = 0
    per_state_position_imbalance_count: Literal[0] = 0
    semantic_choice_set_mismatch_count: Literal[0] = 0
    action_id_collision_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PresentationDeleakAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_presentation_deleak_audit:",
        ):
            raise ValueError("Presentation Deleak Audit identity is invalid")
        return self


class DepthIncrementCausalArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    target_package_id: str = Field(min_length=1)
    new_component_id: str = Field(min_length=1)
    source_depth: ObservationDepth
    target_depth: ObservationDepth
    alternative_choice_handle: str = Field(min_length=1)
    baseline_result_id: str = Field(min_length=1)
    counterfactual_result_id: str = Field(min_length=1)
    counterfactual_result: CausalSemanticExecutionResult
    task_level_necessary: bool
    mechanism_necessary: bool
    qualified_necessary: bool
    classification: Literal[
        "task_and_mechanism_necessary",
        "mechanism_only_necessary",
        "task_only_necessary",
        "neither_necessary",
    ]
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> DepthIncrementCausalArtifact:
        if self.counterfactual_result_id != self.counterfactual_result.result_id:
            raise ValueError("Depth Increment counterfactual Result parent is stale")
        expected = {
            (True, True): "task_and_mechanism_necessary",
            (False, True): "mechanism_only_necessary",
            (True, False): "task_only_necessary",
            (False, False): "neither_necessary",
        }[(self.task_level_necessary, self.mechanism_necessary)]
        if self.classification != expected:
            raise ValueError("Depth Increment necessity classification is inconsistent")
        if self.qualified_necessary != (
            not self.counterfactual_result.qualified_validity.qualified_valid
        ):
            raise ValueError("Depth Increment Qualified necessity is inconsistent")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "depth_increment_causal_artifact:",
        ):
            raise ValueError("Depth Increment Causal Artifact identity is invalid")
        return self


class DepthIncrementCausalCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    artifacts: tuple[DepthIncrementCausalArtifact, ...] = Field(
        min_length=1,
        max_length=48,
    )
    group_count: Literal[8] = 8
    adjacent_increment_count: Literal[24] = 24
    artifact_count: int = Field(ge=24, le=48)
    task_level_necessary_count: int = Field(ge=0)
    mechanism_necessary_count: int = Field(ge=1)
    qualified_necessary_count: int = Field(ge=1)
    base_true_mechanism_false_count: int = Field(ge=1)
    five_parent_binding_match_count: int = Field(ge=1)
    task_level_necessity_claim_is_count_limited: Literal[True] = True
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> DepthIncrementCausalCatalog:
        if self.artifact_count != len(self.artifacts):
            raise ValueError("Depth Increment Causal denominator changed")
        if self.five_parent_binding_match_count != self.artifact_count:
            raise ValueError("Depth Increment five-parent binding does not close")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "depth_increment_causal_catalog:",
        ):
            raise ValueError("Depth Increment Causal Catalog identity is invalid")
        return self


class SemanticParentBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    reference_recomputation_match_count: Literal[80] = 80
    source_program_verification_recomputation_match_count: Literal[32] = 32
    source_public_task_recomputation_match_count: Literal[32] = 32
    source_evidence_semantic_recomputation_match_count: Literal[32] = 32
    projected_public_task_recomputation_match_count: Literal[32] = 32
    depth_increment_parent_match_count: int = Field(ge=1)
    whole_graph_rehash_mutation_count: int = Field(ge=4)
    whole_graph_rehash_rejection_count: int = Field(ge=4)
    crossed_parent_acceptance_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticParentBindingAudit:
        if self.whole_graph_rehash_mutation_count != self.whole_graph_rehash_rejection_count:
            raise ValueError("Semantic parent mutation did not fail closed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_semantic_parent_binding_audit:",
        ):
            raise ValueError("Semantic Parent Binding Audit identity is invalid")
        return self


class ComputedEvidenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    prompt_count: Literal[480] = 480
    source_oracle_dependency_count: int = Field(ge=0)
    opaque_hash_guess_state_count: int = Field(ge=0)
    host_preclassified_alternative_count: int = Field(ge=0)
    computed_zero_count: int = Field(ge=0)
    literal_default_evidence_field_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ComputedEvidenceAudit:
        values = (
            self.source_oracle_dependency_count,
            self.opaque_hash_guess_state_count,
            self.host_preclassified_alternative_count,
        )
        if self.computed_zero_count != sum(value == 0 for value in values):
            raise ValueError("Computed Evidence zero count is inconsistent")
        if any(values):
            raise ValueError("Computed Evidence audit found a forbidden dependency")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_computed_evidence_audit:",
        ):
            raise ValueError("Computed Evidence Audit identity is invalid")
        return self


class DestructiveMutationResult(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True
    error_code: str = Field(min_length=1)


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutationResult, ...] = Field(min_length=12)
    mutation_count: int = Field(ge=12)
    rejected_count: int = Field(ge=12)
    accepted_count: Literal[0] = 0
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if self.mutation_count != len(self.mutations) or self.rejected_count != len(self.mutations):
            raise ValueError("Production destructive denominator changed")
        if len({item.mutation for item in self.mutations}) != len(self.mutations):
            raise ValueError("Production destructive Audit repeats a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_validity_causal_destructive_audit:",
        ):
            raise ValueError("Production Destructive Audit identity is invalid")
        return self


StaticGateName = Literal[
    "answer_projection_complete",
    "candidate_legality",
    "causal_component_execution",
    "component_family_validation",
    "computed_evidence",
    "confirmation_access_zero",
    "depth_increment_honesty",
    "historical_v170_freeze",
    "parent_binding_reconstruction",
    "presentation_deleak",
    "production_destructive",
    "provider_zero",
    "public_only_constructibility",
    "source_closure",
    "validity_separation",
]


class StaticGateResult(FrozenModel):
    gate: StaticGateName
    passed: Literal[True] = True
    evidence_count: int = Field(ge=1)


class ValidityCausalStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGateResult, ...] = Field(min_length=15, max_length=15)
    gate_count: Literal[15] = 15
    passed_gate_count: Literal[15] = 15
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ValidityCausalStaticAudit:
        if len({item.gate for item in self.gates}) != self.gate_count:
            raise ValueError("Validity-causal Static Gate surface changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_validity_causal_static_audit:",
        ):
            raise ValueError("Validity-causal Static Audit identity is invalid")
        return self


class ValidityCausalTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    validity_contract_id: str = Field(min_length=1)
    component_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    parent_binding_contract_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    blocked_predecessor_stage: Literal[
        "capability_observation_public_semantic_execution_development_runner_preflight_only"
    ]
    next_stage: Literal[
        "capability_observation_validity_separated_causal_deleaked_development_runner_preflight_only"
    ]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_loading_authorized: Literal[False] = False
    source_or_task_change_authorized: Literal[False] = False
    threshold_change_authorized: Literal[False] = False
    mapper_or_vtdo_authorized: Literal[False] = False
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ValidityCausalTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_validity_causal_transition:",
        ):
            raise ValueError("Validity-causal Transition identity is invalid")
        return self


class ValidityCausalReauditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    transitive_source_root_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    defect_reproduction_audit_id: str = Field(min_length=1)
    validity_contract_id: str = Field(min_length=1)
    component_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    parent_binding_contract_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    answer_projection_audit_id: str = Field(min_length=1)
    validity_separation_audit_id: str = Field(min_length=1)
    causal_component_audit_id: str = Field(min_length=1)
    component_family_audit_id: str = Field(min_length=1)
    candidate_legality_audit_id: str = Field(min_length=1)
    presentation_deleak_audit_id: str = Field(min_length=1)
    depth_increment_catalog_id: str = Field(min_length=1)
    parent_binding_audit_id: str = Field(min_length=1)
    computed_evidence_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    finance_core_count: Literal[8] = 8
    development_package_count: Literal[32] = 32
    target_state_count: Literal[80] = 80
    baseline_qualified_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    model_behavior_measured: Literal[False] = False
    runner_preflighted: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_stage: Literal[
        "capability_observation_validity_separated_causal_deleaked_development_runner_preflight_only"
    ]
    schema_version: str = V26_VALIDITY_CAUSAL_REAUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ValidityCausalReauditReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_validity_causal_reaudit_report:",
        ):
            raise ValueError("Validity-causal Reaudit Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorIntegrityAudit
    defect: V170DefectReproductionAudit
    validity_contract: ValiditySeparationContract
    component_contract: CausalComponentContract
    presentation_policy: DeleakedPresentationPolicy
    parent_binding_contract: SemanticParentBindingContract
    development_catalog: ValiditySeparatedDevelopmentCatalog
    answer_projection: PublicAnswerProjectionAudit
    validity_separation: ValiditySeparationAudit
    causal_component: CausalComponentAudit
    component_family: ComponentFamilyAudit
    candidate_legality: CandidateLegalityAudit
    presentation_deleak: PresentationDeleakAudit
    increments: DepthIncrementCausalCatalog
    parent_binding: SemanticParentBindingAudit
    computed_evidence: ComputedEvidenceAudit
    destructive: ProductionDestructiveAudit
    static: ValidityCausalStaticAudit
    transition: ValidityCausalTransition
    report: ValidityCausalReauditReport
