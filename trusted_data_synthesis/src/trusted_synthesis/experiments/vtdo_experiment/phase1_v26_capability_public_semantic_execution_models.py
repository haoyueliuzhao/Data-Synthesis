from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PublicSemanticPrompt,
    PublicSemanticTask,
    SemanticExecutionResult,
    TargetComponent,
    canonical_bytes,
    project_public_semantic_task,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.hashing import canonical_hash

V26_PUBLIC_SEMANTIC_EXECUTION_VERSION = (
    "finance_v26_public_semantic_sufficiency_task_execution_hardening.v3"
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
        "implementation",
        "transitive_source",
        "v26_169_frozen_output",
        "formal_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["1dd7e35803ce73bfd7d9be3517399c6e416d6aa4f7504276fdad38ceb6131d85"]
    review_byte_count: Literal[25632] = 25_632
    authorized_stage: Literal[
        "capability_observation_public_semantic_sufficiency_and_task_execution_hardening_only"
    ]
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_public_semantic_external_audit_authorization:",
        ):
            raise ValueError("v26.170 external audit Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=4)
    file_count: int = Field(ge=4)
    complete_static_import_closure: Literal[True] = True
    unresolved_trusted_synthesis_import_count: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.170 transitive source count is inconsistent")
        if len({item.relative_path for item in self.files}) != len(self.files):
            raise ValueError("v26.170 transitive source Root repeats a file")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_public_semantic_transitive_source_root:",
        ):
            raise ValueError("v26.170 transitive source Root identity is invalid")
        return self


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    bindings: tuple[FileBinding, ...] = Field(min_length=17, max_length=17)
    matched_file_count: Literal[17] = 17
    predecessor_mutation_count: Literal[0] = 0
    stale_runner_preflight_transition_blocked: Literal[True] = True
    sealed_confirmation_payload_loaded: Literal[False] = False
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        if len(self.bindings) != self.matched_file_count:
            raise ValueError("v26.170 predecessor binding count changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_semantic_predecessor_integrity:",
        ):
            raise ValueError("v26.170 predecessor integrity identity is invalid")
        return self


class V169SemanticDefectAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    finance_core_count: Literal[8] = 8
    original_public_instruction_exact_count: Literal[0] = 0
    registered_alias_value_retained_count: Literal[0] = 0
    registered_alias_value_count: Literal[23] = 23
    registered_period_value_retained_count: Literal[0] = 0
    registered_period_value_count: Literal[14] = 14
    resolution_rule_value_retained_count: Literal[0] = 0
    resolution_rule_value_count: Literal[101] = 101
    unique_public_task_projection_hash_count: Literal[5] = 5
    action_state_count: Literal[210] = 210
    reference_parameter_externally_bound_state_count: Literal[8] = 8
    no_candidate_parameter_externally_bound_state_count: Literal[202] = 202
    indexed_token_state_count: Literal[68] = 68
    reference_index_minimum_state_count: Literal[68] = 68
    set_expected_result_effect_count: Literal[32] = 32
    nonreference_alternative_count: Literal[420] = 420
    task_invalid_alternative_count: Literal[420] = 420
    terminate_invalid_alternative_count: Literal[404] = 404
    set_alternate_result_effect_count: Literal[404] = 404
    d0_target_state_count_by_family: dict[CapabilityFamily, int]
    d0_non_target_state_count_by_family: dict[CapabilityFamily, int]
    rehashed_public_task_parent_mutation_accepted: Literal[True] = True
    future_six_replica_order_varies: Literal[False] = False
    historical_artifact_rewritten: Literal[False] = False
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V169SemanticDefectAudit:
        expected_target = {
            CapabilityFamily.CONTEXT_CONDITIONED_ACTION: 1,
            CapabilityFamily.SEMANTIC_RECONCILIATION: 3,
            CapabilityFamily.FAILURE_RECOVERY: 2,
            CapabilityFamily.STATE_DEPENDENT_STOPPING: 1,
        }
        expected_non_target = {
            CapabilityFamily.CONTEXT_CONDITIONED_ACTION: 3,
            CapabilityFamily.SEMANTIC_RECONCILIATION: 3,
            CapabilityFamily.FAILURE_RECOVERY: 3,
            CapabilityFamily.STATE_DEPENDENT_STOPPING: 4,
        }
        if (
            self.d0_target_state_count_by_family != expected_target
            or self.d0_non_target_state_count_by_family != expected_non_target
        ):
            raise ValueError("v26.169 D0 target/non-target defect partition changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v169_public_semantic_execution_defect_audit:",
        ):
            raise ValueError("v26.169 semantic defect Audit identity is invalid")
        return self


class PublicSemanticProjectionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    exact_public_instruction_retained: Literal[True] = True
    aliases_and_periods_retained: Literal[True] = True
    resolution_rules_retained: Literal[True] = True
    operation_input_output_semantics_retained: Literal[True] = True
    public_record_values_retained: Literal[True] = True
    gold_evidence_identity_exposed: Literal[False] = False
    source_oracle_program_inputs_exposed: Literal[False] = False
    expected_result_exposed: Literal[False] = False
    reference_choice_exposed: Literal[False] = False
    capability_or_depth_exposed: Literal[False] = False
    current_state_only: Literal[True] = True
    public_task_reconstructible_from_finance_core: Literal[True] = True
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicSemanticProjectionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "public_semantic_projection_contract:",
        ):
            raise ValueError("Public Semantic Projection Contract identity is invalid")
        return self


class ReplicaPresentationPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    replica_count: Literal[6] = 6
    candidate_count_per_state: Literal[3] = 3
    position_count_per_semantic_choice: Literal[2] = 2
    permutation_key: Literal["variant_x_replica_x_state"] = "variant_x_replica_x_state"
    preoutcome_fixed_salt_sha256: str = Field(min_length=64, max_length=64)
    semantic_payload_invariant_across_replicas: Literal[True] = True
    action_id_and_order_are_presentation_only: Literal[True] = True
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> ReplicaPresentationPolicy:
        if self.policy_id != identity(
            self,
            "policy_id",
            "public_semantic_replica_presentation_policy:",
        ):
            raise ValueError("Replica Presentation Policy identity is invalid")
        return self


class PublicTaskParentBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    source_public_task_hash: str = Field(min_length=1)
    source_public_evidence_semantic_hash: str = Field(min_length=1)
    projected_public_task_hash: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> PublicTaskParentBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "public_semantic_task_parent_binding:",
        ):
            raise ValueError("Public Task parent Binding identity is invalid")
        return self


class ReplicaPresentation(FrozenModel):
    presentation_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    prompt: PublicSemanticPrompt
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_presentation(self) -> ReplicaPresentation:
        if self.presentation_id != identity(
            self,
            "presentation_id",
            "public_semantic_replica_presentation:",
        ):
            raise ValueError("Replica Presentation identity is invalid")
        return self


class HardenedPromptBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    public_task_hash: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    prompts: tuple[PublicSemanticPrompt, ...] = Field(min_length=1, max_length=4)
    prompt_count: int = Field(ge=1, le=4)
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> HardenedPromptBinding:
        if self.prompt_count != len(self.prompts):
            raise ValueError("Hardened Prompt binding count changed")
        if any(item.task.semantic_hash != self.public_task_hash for item in self.prompts):
            raise ValueError("Hardened Prompt task payload crosses its Task parent")
        task_bytes = {canonical_bytes(item.task) for item in self.prompts}
        if len(task_bytes) != 1:
            raise ValueError("Hardened Prompt projections do not share exact Task bytes")
        if self.binding_id != identity(
            self,
            "binding_id",
            "public_semantic_prompt_binding:",
        ):
            raise ValueError("Hardened Prompt Binding identity is invalid")
        return self


class IsolatedTargetLoad(FrozenModel):
    load_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    target_component_count: int = Field(ge=1, le=4)
    non_target_choice_state_count: Literal[0] = 0
    deterministic_non_target_execution: Literal[True] = True
    total: int = Field(ge=1, le=4)
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_load(self) -> IsolatedTargetLoad:
        if self.total != self.target_component_count:
            raise ValueError("Isolated target Load includes non-target burden")
        if self.load_id != identity(
            self,
            "load_id",
            "isolated_capability_target_load:",
        ):
            raise ValueError("Isolated target Load identity is invalid")
        return self


class HardenedSemanticPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    predecessor_package_id: str = Field(min_length=1)
    predecessor_group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    finance_core_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    public_task: PublicSemanticTask
    task_parent_binding: PublicTaskParentBinding
    components: tuple[TargetComponent, ...] = Field(min_length=1, max_length=4)
    prompt_binding: HardenedPromptBinding
    replica_presentations: tuple[ReplicaPresentation, ...] = Field(min_length=6, max_length=24)
    target_load: IsolatedTargetLoad
    baseline_execution: SemanticExecutionResult
    source_program_verification_hash: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    runner_preflighted: Literal[False] = False
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> HardenedSemanticPackage:
        expected_package = canonical_hash(
            {
                "predecessor_package_id": self.predecessor_package_id,
                "capability_family": self.capability_family.value,
                "depth": self.depth.value,
                "finance_core_id": self.finance_core_id,
                "fixed_generation_condition_id": self.fixed_generation_condition_id,
                "projection_contract_id": self.projection_contract_id,
                "presentation_policy_id": self.presentation_policy_id,
                "public_task_hash": self.public_task.semantic_hash,
                "component_keys": [item.component_key for item in self.components],
                "schema_version": self.schema_version,
            },
            prefix="finance_v26_public_semantic_package:",
        )
        if self.package_id != expected_package:
            raise ValueError("Hardened semantic Package identity is invalid")
        component_by_id = {item.component_id: item for item in self.components}
        if len(component_by_id) != len(self.components):
            raise ValueError("Hardened semantic Package repeats a Component")
        if (
            self.task_parent_binding.finance_core_id != self.finance_core_id
            or self.task_parent_binding.projected_public_task_hash != self.public_task.semantic_hash
            or self.task_parent_binding.projection_contract_id != self.projection_contract_id
            or self.prompt_binding.package_id != self.package_id
            or self.prompt_binding.public_task_hash != self.public_task.semantic_hash
            or self.prompt_binding.projection_contract_id != self.projection_contract_id
            or self.target_load.package_id != self.package_id
            or self.target_load.capability_family != self.capability_family
            or self.target_load.depth != self.depth
            or self.target_load.target_component_count != len(self.components)
            or not self.baseline_execution.qualified_valid
            or tuple(self.baseline_execution.chosen_semantic_keys)
            != tuple(item.reference_semantic_key for item in self.components)
        ):
            raise ValueError("Hardened semantic Package parent binding is inconsistent")
        prompt_states = {item.state.state_token for item in self.prompt_binding.prompts}
        if prompt_states != {item.public_state.state_token for item in self.components}:
            raise ValueError("Hardened semantic Package Prompt State set is incomplete")
        expected_rows = {
            (component.component_id, replica)
            for component in self.components
            for replica in range(6)
        }
        observed_rows = {
            (item.component_id, item.replica_index) for item in self.replica_presentations
        }
        if expected_rows != observed_rows:
            raise ValueError("Hardened semantic Package Replica surface is incomplete")
        for presentation in self.replica_presentations:
            component = component_by_id[presentation.component_id]
            if presentation.package_id != self.package_id:
                raise ValueError("Replica Presentation crosses a Package")
            if presentation.prompt.task != self.public_task:
                raise ValueError("Replica Presentation crosses a public Task")
            if presentation.prompt.state != component.public_state:
                raise ValueError("Replica Presentation crosses a target State")
            if {item.operation.semantic_key for item in presentation.prompt.candidates} != {
                item.semantic_key for item in component.choices
            }:
                raise ValueError("Replica Presentation changes Candidate semantics")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_public_semantic_package_artifact:",
        ):
            raise ValueError("Hardened semantic Package artifact identity is invalid")
        return self


class HardenedSemanticGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    predecessor_group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    finance_core_id: str = Field(min_length=1)
    packages: tuple[HardenedSemanticPackage, ...] = Field(min_length=4, max_length=4)
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> HardenedSemanticGroup:
        if tuple(item.depth for item in self.packages) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("Hardened semantic Group does not contain D0-D3")
        if any(
            item.predecessor_group_id != self.predecessor_group_id
            or item.capability_family != self.capability_family
            or item.finance_core_id != self.finance_core_id
            for item in self.packages
        ):
            raise ValueError("Hardened semantic Group contains a crossed Package")
        component_sets = [
            set(item.component_key for item in package.components) for package in self.packages
        ]
        for previous, current in zip(component_sets, component_sets[1:], strict=False):
            if not previous < current or len(current - previous) != 1:
                raise ValueError(
                    "Hardened semantic depth does not add exactly one target component"
                )
        if tuple(item.target_load.total for item in self.packages) != (1, 2, 3, 4):
            raise ValueError("Hardened semantic target Load is not isolated D0-D3")
        if len({item.public_task.semantic_hash for item in self.packages}) != 1:
            raise ValueError("Hardened semantic Group changes its public Task across depth")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_public_semantic_group:",
        ):
            raise ValueError("Hardened semantic Group identity is invalid")
        return self


def validate_public_task_reconstruction(
    *,
    core: v168_models.LowNuisanceFinanceCore,
    package: HardenedSemanticPackage,
) -> None:
    task = core.operational_record.task_package.task
    reconstructed = project_public_semantic_task(
        task.public.model_dump(mode="json"),
        core.operational_record.evidence_bundle.evidence,
    )
    if canonical_bytes(package.public_task) != canonical_bytes(reconstructed):
        raise ValueError("Public Task cannot be reconstructed from exact Finance Core")


class HardenedSemanticDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    v168_finance_core_catalog_id: str = Field(min_length=1)
    sealed_confirmation_receipt_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    finance_cores: tuple[v168_models.LowNuisanceFinanceCore, ...] = Field(
        min_length=8,
        max_length=8,
    )
    groups: tuple[HardenedSemanticGroup, ...] = Field(min_length=8, max_length=8)
    finance_core_count: Literal[8] = 8
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    confirmation_payload_access_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> HardenedSemanticDevelopmentCatalog:
        cores = {item.core_id: item for item in self.finance_cores}
        if len(cores) != self.finance_core_count or len(self.groups) != self.group_count:
            raise ValueError("Hardened semantic Catalog denominator changed")
        if sum(len(item.packages) for item in self.groups) != self.package_count:
            raise ValueError("Hardened semantic Catalog Package count changed")
        if len({item.predecessor_group_id for item in self.groups}) != self.group_count:
            raise ValueError("Hardened semantic Catalog repeats a predecessor Group")
        for group in self.groups:
            if group.finance_core_id not in cores:
                raise ValueError("Hardened semantic Group references an absent Finance Core")
            core = cores[group.finance_core_id]
            for package in group.packages:
                validate_public_task_reconstruction(core=core, package=package)
                if (
                    package.projection_contract_id != self.projection_contract_id
                    or package.presentation_policy_id != self.presentation_policy_id
                    or package.fixed_generation_condition_id != self.fixed_generation_condition_id
                ):
                    raise ValueError("Hardened semantic Package crosses a shared Contract")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_public_semantic_development_catalog:",
        ):
            raise ValueError("Hardened semantic Development Catalog identity is invalid")
        return self


class PublicSemanticSufficiencyAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    finance_core_count: Literal[8] = 8
    exact_instruction_retained_count: Literal[8] = 8
    alias_value_retained_count: Literal[23] = 23
    period_value_retained_count: Literal[14] = 14
    resolution_rule_value_retained_count: Literal[101] = 101
    unique_public_task_hash_count: Literal[8] = 8
    target_state_count: Literal[80] = 80
    production_public_only_unique_choice_count: Literal[80] = 80
    independent_public_only_unique_choice_count: Literal[80] = 80
    replica_public_only_choice_match_count: Literal[480] = 480
    action_id_or_ordinal_dependency_count: Literal[0] = 0
    source_oracle_dependency_count: Literal[0] = 0
    opaque_hash_guess_state_count: Literal[0] = 0
    model_visible_host_leak_count: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicSemanticSufficiencyAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_semantic_sufficiency_audit:",
        ):
            raise ValueError("Public Semantic Sufficiency Audit identity is invalid")
        return self


class CandidateGroundingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    semantic_candidate_count: Literal[240] = 240
    publicly_grounded_candidate_count: Literal[240] = 240
    ungrounded_candidate_count: Literal[0] = 0
    indexed_shortcut_candidate_count: Literal[0] = 0
    random_peer_hash_candidate_count: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CandidateGroundingAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_candidate_grounding_audit:",
        ):
            raise ValueError("Candidate Grounding Audit identity is invalid")
        return self


class RealProgramExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    task_program_executor_invocation_count: Literal[32] = 32
    task_program_oracle_verifier_invocation_count: Literal[32] = 32
    baseline_program_valid_count: Literal[32] = 32
    baseline_base_valid_count: Literal[32] = 32
    baseline_mechanism_qualified_count: Literal[32] = 32
    baseline_qualified_valid_count: Literal[32] = 32
    predecessor_output_match_count: Literal[32] = 32
    set_expected_result_effect_count: Literal[0] = 0
    set_alternate_result_effect_count: Literal[0] = 0
    host_preclassified_alternative_count: Literal[0] = 0
    host_result_assignment_count: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RealProgramExecutionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_real_program_execution_audit:",
        ):
            raise ValueError("Real Program Execution Audit identity is invalid")
        return self


class TargetIsolationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    target_choice_state_count: Literal[80] = 80
    non_target_choice_state_count: Literal[0] = 0
    deterministic_non_target_execution_count: Literal[32] = 32
    target_state_count_by_depth: dict[ObservationDepth, int]
    d0_target_states_per_package_by_family: dict[CapabilityFamily, int]
    d0_non_target_choice_states_by_family: dict[CapabilityFamily, int]
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TargetIsolationAudit:
        if self.target_state_count_by_depth != {
            ObservationDepth.D0_OBSERVABILITY_ANCHOR: 8,
            ObservationDepth.D1_BASIC: 16,
            ObservationDepth.D2_COMPOSITIONAL: 24,
            ObservationDepth.D3_STRESS: 32,
        }:
            raise ValueError("target State depth partition changed")
        if self.d0_target_states_per_package_by_family != {
            family: 1 for family in CapabilityFamily
        }:
            raise ValueError("D0 does not isolate one target decision per Package")
        if self.d0_non_target_choice_states_by_family != {family: 0 for family in CapabilityFamily}:
            raise ValueError("D0 retains a non-target choice State")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_target_isolation_audit:",
        ):
            raise ValueError("Target Isolation Audit identity is invalid")
        return self


class DepthIncrementNecessityArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    source_depth: ObservationDepth
    target_depth: ObservationDepth
    new_component_key: str = Field(min_length=1)
    alternative_semantic_key: str = Field(min_length=1)
    runtime_result: SemanticExecutionResult
    task_level_validity_changed: Literal[True] = True
    mechanism_qualification_changed: Literal[True] = True
    qualified_validity_changed: Literal[True] = True
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> DepthIncrementNecessityArtifact:
        if (
            self.runtime_result.base_valid
            or self.runtime_result.mechanism_qualified
            or self.runtime_result.qualified_valid
        ):
            raise ValueError("Depth increment alternative retained task validity")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "depth_increment_necessity_artifact:",
        ):
            raise ValueError("Depth Increment Necessity Artifact identity is invalid")
        return self


class DepthIncrementNecessityCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    artifacts: tuple[DepthIncrementNecessityArtifact, ...] = Field(
        min_length=48,
        max_length=48,
    )
    group_count: Literal[8] = 8
    adjacent_increment_count: Literal[24] = 24
    alternatives_per_increment: Literal[2] = 2
    artifact_count: Literal[48] = 48
    task_invalid_count: Literal[48] = 48
    mechanism_unqualified_count: Literal[48] = 48
    qualified_invalid_count: Literal[48] = 48
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> DepthIncrementNecessityCatalog:
        if len(self.artifacts) != self.artifact_count:
            raise ValueError("Depth Increment Necessity denominator changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "depth_increment_necessity_catalog:",
        ):
            raise ValueError("Depth Increment Necessity Catalog identity is invalid")
        return self


class PromptParentBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    semantic_task_mutation_count: Literal[32] = 32
    child_identity_recomputed_count: Literal[32] = 32
    package_identity_recomputed_count: Literal[32] = 32
    group_identity_recomputed_count: Literal[32] = 32
    catalog_identity_recomputed_count: Literal[32] = 32
    reconstruction_rejection_count: Literal[32] = 32
    accepted_crossed_public_task_count: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PromptParentBindingAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_task_parent_binding_audit:",
        ):
            raise ValueError("Prompt parent Binding Audit identity is invalid")
        return self


class ReplicaPresentationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    target_state_count: Literal[80] = 80
    replica_count: Literal[6] = 6
    presentation_count: Literal[480] = 480
    displayed_candidate_count: Literal[1440] = 1440
    semantic_choice_position_count: Literal[2] = 2
    per_state_position_imbalance_count: Literal[0] = 0
    semantic_payload_mismatch_count: Literal[0] = 0
    action_id_collision_count: Literal[0] = 0
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ReplicaPresentationAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_replica_presentation_audit:",
        ):
            raise ValueError("Replica Presentation Audit identity is invalid")
        return self


StaticGateName = Literal[
    "candidate_grounding",
    "confirmation_access_zero",
    "depth_increment_necessity",
    "deterministic_non_target_execution",
    "exact_public_instruction",
    "historical_v169_freeze",
    "model_visible_leakage_zero",
    "prompt_parent_reconstruction",
    "provider_zero",
    "public_only_constructibility",
    "public_record_semantics",
    "real_program_execution",
    "replica_presentation_balance",
    "resolution_rule_retention",
    "target_burden_isolation",
    "task_program_oracle_verification",
    "transitive_source_closure",
    "unique_public_task_identity",
]


class StaticGateResult(FrozenModel):
    gate: StaticGateName
    passed: Literal[True] = True
    evidence_count: int = Field(ge=1)


class PublicSemanticStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGateResult, ...] = Field(min_length=18, max_length=18)
    gate_count: Literal[18] = 18
    passed_gate_count: Literal[18] = 18
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicSemanticStaticAudit:
        if len(self.gates) != self.gate_count or len({item.gate for item in self.gates}) != 18:
            raise ValueError("Public semantic static Gate surface changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_semantic_static_audit:",
        ):
            raise ValueError("Public semantic Static Audit identity is invalid")
        return self


class PublicSemanticTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    blocked_predecessor_stage: Literal[
        "capability_observation_executable_depth_development_runner_preflight_only"
    ]
    next_stage: Literal[
        "capability_observation_public_semantic_execution_development_runner_preflight_only"
    ]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_loading_authorized: Literal[False] = False
    source_or_public_semantic_change_authorized: Literal[False] = False
    threshold_change_authorized: Literal[False] = False
    mapper_or_vtdo_authorized: Literal[False] = False
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> PublicSemanticTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_public_semantic_transition:",
        ):
            raise ValueError("Public semantic Transition identity is invalid")
        return self


class PublicSemanticHardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    transitive_source_root_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    defect_audit_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    sufficiency_audit_id: str = Field(min_length=1)
    grounding_audit_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    isolation_audit_id: str = Field(min_length=1)
    increment_catalog_id: str = Field(min_length=1)
    parent_binding_audit_id: str = Field(min_length=1)
    replica_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    finance_core_count: Literal[8] = 8
    development_package_count: Literal[32] = 32
    target_state_count: Literal[80] = 80
    semantic_candidate_count: Literal[240] = 240
    baseline_qualified_count: Literal[32] = 32
    depth_increment_counterfactual_count: Literal[48] = 48
    replica_presentation_count: Literal[480] = 480
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    model_behavior_measured: Literal[False] = False
    runner_preflighted: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_stage: Literal[
        "capability_observation_public_semantic_execution_development_runner_preflight_only"
    ]
    schema_version: str = V26_PUBLIC_SEMANTIC_EXECUTION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PublicSemanticHardeningReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_public_semantic_hardening_report:",
        ):
            raise ValueError("Public semantic Hardening Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: PredecessorIntegrityAudit
    defect: V169SemanticDefectAudit
    projection_contract: PublicSemanticProjectionContract
    presentation_policy: ReplicaPresentationPolicy
    development_catalog: HardenedSemanticDevelopmentCatalog
    sufficiency: PublicSemanticSufficiencyAudit
    grounding: CandidateGroundingAudit
    execution: RealProgramExecutionAudit
    isolation: TargetIsolationAudit
    increments: DepthIncrementNecessityCatalog
    parent_binding: PromptParentBindingAudit
    replica: ReplicaPresentationAudit
    static: PublicSemanticStaticAudit
    transition: PublicSemanticTransition
    report: PublicSemanticHardeningReport
