from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.causal_capability_depth import (
    CausalCounterfactualKind,
    CausalDepthVerifierContract,
    CausalDepthWitness,
    CausalDepthWitnessContract,
    CausalFinanceBinding,
    CausalMechanismValidityReport,
    CausalQualifiedValidityReport,
    CausalRuntimeObservation,
    CausalTaskValidityReport,
    DepthPromptProjectionContract,
    HostExecutableDepthGraph,
    PublicPromptProjection,
)
from trusted_synthesis.hashing import canonical_hash

V26_CAUSAL_DEPTH_HARDENING_VERSION = (
    "finance_v26_public_projection_causal_depth_runtime_hardening.v2"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "external_audit_input",
        "implementation",
        "transitive_source",
        "v26_168_frozen_output",
        "formal_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["6105461d1c58f507ee5227f3b8f6867e020dedec828b7687befe1eddb108bb4e"]
    review_byte_count: Literal[27021] = 27_021
    authorized_stage: Literal[
        "capability_observation_public_projection_and_causal_depth_runtime_hardening_only"
    ]
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_causal_depth_external_audit_authorization:",
        ):
            raise ValueError("v26.169 external authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=4)
    file_count: int = Field(ge=4)
    complete_static_import_closure: Literal[True] = True
    unresolved_trusted_synthesis_import_count: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        paths = tuple(item.relative_path for item in self.files)
        if self.file_count != len(self.files) or paths != tuple(sorted(set(paths))):
            raise ValueError("v26.169 transitive source root is not canonical")
        if any(item.source_kind != "transitive_source" for item in self.files):
            raise ValueError("v26.169 transitive source root contains another provenance")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_causal_depth_transitive_source_root:",
        ):
            raise ValueError("v26.169 transitive source root identity is invalid")
        return self


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v26_168_report_id: str = Field(min_length=1)
    v26_168_development_catalog_id: str = Field(min_length=1)
    v26_168_sealed_receipt_id: str = Field(min_length=1)
    v26_168_transition_id: str = Field(min_length=1)
    bindings: tuple[FileBinding, ...] = Field(min_length=19, max_length=19)
    matched_file_count: Literal[19] = 19
    predecessor_mutation_count: Literal[0] = 0
    sealed_confirmation_payload_loaded: Literal[False] = False
    old_runner_preflight_transition_blocked: Literal[True] = True
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        paths = tuple(item.relative_path for item in self.bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.168 predecessor bindings are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_causal_depth_predecessor_integrity:",
        ):
            raise ValueError("v26.168 predecessor integrity identity is invalid")
        return self


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    transitive_source_root_id: str = Field(min_length=1)
    bindings: tuple[FileBinding, ...] = Field(min_length=20)
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.169 source replay is not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_causal_depth_source_replay:",
        ):
            raise ValueError("v26.169 source replay identity is invalid")
        return self


class V168DefectReproductionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_development_catalog_id: str = Field(min_length=1)
    development_package_count: Literal[32] = 32
    nonterminal_state_count: Literal[142] = 142
    all_candidates_same_successor_count: Literal[142] = 142
    reference_candidate_field_count: Literal[142] = 142
    reference_action_true_count: Literal[142] = 142
    target_capability_action_true_count: Literal[244] = 244
    target_bypass_candidate_count: Literal[108] = 108
    tempting_continuation_candidate_count: Literal[34] = 34
    public_capability_family_field_count: Literal[174] = 174
    public_depth_field_count: Literal[174] = 174
    required_event_key_count: Literal[92] = 92
    impossible_family_trace_count: Literal[4] = 4
    old_noninterference_gate_rejected: Literal[True] = True
    v26_168_artifacts_rewritten: Literal[False] = False
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V168DefectReproductionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v168_public_projection_runtime_defect_audit:",
        ):
            raise ValueError("v26.168 defect reproduction identity is invalid")
        return self


class CandidatePresentationPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    permutation_salt_sha256: str = Field(min_length=64, max_length=64)
    opaque_action_id_hex_length: Literal[24] = 24
    neutral_description: Literal["Apply the displayed operation payload."] = (
        "Apply the displayed operation payload."
    )
    deterministic_preoutcome_permutation: Literal[True] = True
    reference_position_rotation_balanced: Literal[True] = True
    equal_candidate_encoding_per_state: Literal[True] = True
    semantic_selection_independent_of_action_id: Literal[True] = True
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> CandidatePresentationPolicy:
        if self.policy_id != identity(
            self,
            "policy_id",
            "causal_depth_candidate_presentation_policy:",
        ):
            raise ValueError("Candidate presentation Policy identity is invalid")
        return self


class CausalCompiledTargetLoad(FrozenModel):
    load_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    witness_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    dimensions: dict[str, int] = Field(min_length=1)
    total: int = Field(gt=0)
    computed_from_host_graph_and_runtime: Literal[True] = True
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_load(self) -> CausalCompiledTargetLoad:
        if any(value < 0 for value in self.dimensions.values()):
            raise ValueError("causal target load has a negative dimension")
        if self.total != sum(self.dimensions.values()):
            raise ValueError("causal target load total is inconsistent")
        if self.load_id != identity(
            self,
            "load_id",
            "compiled_causal_capability_target_load:",
        ):
            raise ValueError("causal target load identity is invalid")
        return self


class CausalNuisanceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    predecessor_measurement_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    base_operational_task_package_id: str = Field(min_length=1)
    evidence_count: Literal[2] = 2
    source_program_node_count: Literal[1] = 1
    source_program_edge_count: Literal[0] = 0
    resource_token_ceiling: Literal[1120000] = 1_120_000
    predecessor_nuisance_preserved: Literal[True] = True
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> CausalNuisanceBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "causal_depth_nuisance_binding:",
        ):
            raise ValueError("causal nuisance binding identity is invalid")
        return self


class CausalPromptBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    public_task_projection_hash: str = Field(min_length=1)
    projections: tuple[PublicPromptProjection, ...] = Field(min_length=1)
    prompt_projection_count: int = Field(ge=1)
    host_graph_serialization_count: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> CausalPromptBinding:
        if self.prompt_projection_count != len(self.projections):
            raise ValueError("Prompt binding projection count is inconsistent")
        if any(
            item.package_id != self.package_id
            or item.graph_id != self.graph_id
            or item.contract_id != self.projection_contract_id
            or item.fixed_generation_condition_id != self.fixed_generation_condition_id
            for item in self.projections
        ):
            raise ValueError("Prompt binding contains a crossed projection")
        if self.binding_id != identity(
            self,
            "binding_id",
            "causal_depth_prompt_binding:",
        ):
            raise ValueError("causal Prompt binding identity is invalid")
        return self


class CausalDepthSignature(FrozenModel):
    signature_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    predecessor_package_id: str = Field(min_length=1)
    group_key: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    finance_binding_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    witness_contract_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    baseline_witness_id: str = Field(min_length=1)
    target_load_id: str = Field(min_length=1)
    nuisance_binding_id: str = Field(min_length=1)
    prompt_binding_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    host_graph_hash: str = Field(min_length=1)
    public_projection_hash: str = Field(min_length=1)
    task_validity_report_id: str = Field(min_length=1)
    mechanism_validity_report_id: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_signature(self) -> CausalDepthSignature:
        if self.signature_id != identity(
            self,
            "signature_id",
            "causal_depth_package_signature:",
        ):
            raise ValueError("causal Package Signature identity is invalid")
        return self


class CausalDepthPackage(FrozenModel):
    artifact_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    predecessor_package_id: str = Field(min_length=1)
    predecessor_group_id: str = Field(min_length=1)
    group_key: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    finance_core_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    finance_binding: CausalFinanceBinding
    graph: HostExecutableDepthGraph
    witness_contract: CausalDepthWitnessContract
    verifier_contract: CausalDepthVerifierContract
    baseline_witness: CausalDepthWitness
    target_load: CausalCompiledTargetLoad
    nuisance_binding: CausalNuisanceBinding
    prompt_binding: CausalPromptBinding
    signature: CausalDepthSignature
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    runner_preflighted: Literal[False] = False
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> CausalDepthPackage:
        expected_package_id = canonical_hash(
            {
                "predecessor_package_id": self.predecessor_package_id,
                "group_key": self.group_key,
                "capability_family": self.capability_family.value,
                "depth": self.depth.value,
                "finance_core_id": self.finance_core_id,
                "fixed_generation_condition_id": self.fixed_generation_condition_id,
                "schema_version": self.schema_version,
            },
            prefix="finance_v26_causal_depth_package:",
        )
        if self.package_id != expected_package_id:
            raise ValueError("causal Package semantic identity is invalid")
        graph = self.graph
        binding = self.finance_binding
        witness = self.baseline_witness
        signature = self.signature
        if (
            graph.package_id != self.package_id
            or graph.predecessor_package_id != self.predecessor_package_id
            or graph.finance_core_id != self.finance_core_id
            or graph.base_operational_task_package_id != binding.base_operational_task_package_id
            or graph.finance_binding_id != binding.binding_id
            or graph.capability_family != self.capability_family
            or graph.depth != self.depth
            or binding.finance_core_id != self.finance_core_id
            or self.witness_contract.graph_id != graph.graph_id
            or self.witness_contract.finance_binding_id != binding.binding_id
            or self.witness_contract.capability_family != self.capability_family
            or self.witness_contract.depth != self.depth
            or self.witness_contract.required_event_multiplicities
            != graph.required_event_multiplicities
            or self.verifier_contract.witness_contract_id != self.witness_contract.contract_id
            or self.verifier_contract.finance_binding_id != binding.binding_id
            or self.verifier_contract.task_program_id != binding.task_program_id
            or self.verifier_contract.task_verifier_binding_id != binding.task_verifier_binding_id
            or witness.package_id != self.package_id
            or witness.graph_id != graph.graph_id
            or witness.witness_contract_id != self.witness_contract.contract_id
            or witness.verifier_contract_id != self.verifier_contract.contract_id
            or self.target_load.package_id != self.package_id
            or self.target_load.graph_id != graph.graph_id
            or self.target_load.witness_id != witness.witness_id
            or self.target_load.capability_family != self.capability_family
            or self.target_load.depth != self.depth
            or self.nuisance_binding.finance_core_id != self.finance_core_id
            or self.nuisance_binding.base_operational_task_package_id
            != binding.base_operational_task_package_id
            or self.prompt_binding.package_id != self.package_id
            or self.prompt_binding.graph_id != graph.graph_id
            or self.prompt_binding.fixed_generation_condition_id
            != self.fixed_generation_condition_id
            or {item.host_state_id for item in self.prompt_binding.projections}
            != {item.state_id for item in graph.states if item.terminal_kind.value == "none"}
            or signature.package_id != self.package_id
            or signature.predecessor_package_id != self.predecessor_package_id
            or signature.group_key != self.group_key
            or signature.finance_core_id != self.finance_core_id
            or signature.finance_binding_id != binding.binding_id
            or signature.graph_id != graph.graph_id
            or signature.witness_contract_id != self.witness_contract.contract_id
            or signature.verifier_contract_id != self.verifier_contract.contract_id
            or signature.baseline_witness_id != witness.witness_id
            or signature.target_load_id != self.target_load.load_id
            or signature.nuisance_binding_id != self.nuisance_binding.binding_id
            or signature.prompt_binding_id != self.prompt_binding.binding_id
            or signature.projection_contract_id != self.prompt_binding.projection_contract_id
            or signature.presentation_policy_id != self.prompt_binding.presentation_policy_id
            or signature.task_validity_report_id != witness.task_validity.report_id
            or signature.mechanism_validity_report_id != witness.mechanism_validity.report_id
            or signature.qualified_validity_report_id != witness.qualified_validity.report_id
            or signature.host_graph_hash
            != canonical_hash(graph.model_dump(mode="json"), prefix="causal_host_graph_bytes:")
            or signature.public_projection_hash
            != canonical_hash(
                tuple(item.projection_id for item in self.prompt_binding.projections),
                prefix="causal_public_projection_set:",
            )
        ):
            raise ValueError("causal Package cross-parent binding is inconsistent")
        if self.artifact_id != identity(
            self,
            "artifact_id",
            "finance_v26_causal_depth_package_artifact:",
        ):
            raise ValueError("causal Package artifact identity is invalid")
        return self


class CausalDepthGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    group_key: str = Field(min_length=1)
    predecessor_group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    finance_core_id: str = Field(min_length=1)
    packages: tuple[CausalDepthPackage, ...] = Field(min_length=4, max_length=4)
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> CausalDepthGroup:
        expected_key = canonical_hash(
            {
                "predecessor_group_id": self.predecessor_group_id,
                "capability_family": self.capability_family.value,
                "finance_core_id": self.finance_core_id,
                "schema_version": self.schema_version,
            },
            prefix="finance_v26_causal_depth_group_key:",
        )
        if self.group_key != expected_key:
            raise ValueError("causal Group key is invalid")
        if tuple(item.depth for item in self.packages) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("causal Group does not contain D0-D3")
        if any(
            item.group_key != self.group_key
            or item.predecessor_group_id != self.predecessor_group_id
            or item.capability_family != self.capability_family
            or item.finance_core_id != self.finance_core_id
            for item in self.packages
        ):
            raise ValueError("causal Group contains a crossed Package")
        loads = tuple(item.target_load.total for item in self.packages)
        if any(left >= right for left, right in zip(loads, loads[1:], strict=False)):
            raise ValueError("causal Group target load is not strictly increasing")
        if self.group_id != identity(
            self,
            "group_id",
            "finance_v26_causal_depth_group:",
        ):
            raise ValueError("causal Group identity is invalid")
        return self


class CausalDevelopmentCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    predecessor_catalog_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    sealed_confirmation_receipt_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    groups: tuple[CausalDepthGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    confirmation_payload_access_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> CausalDevelopmentCatalog:
        if len({item.predecessor_group_id for item in self.groups}) != self.group_count:
            raise ValueError("causal Catalog repeats a predecessor Group")
        if sum(len(item.packages) for item in self.groups) != self.package_count:
            raise ValueError("causal Catalog Package denominator changed")
        if any(
            package.prompt_binding.projection_contract_id != self.projection_contract_id
            or package.prompt_binding.presentation_policy_id != self.presentation_policy_id
            or package.fixed_generation_condition_id != self.fixed_generation_condition_id
            for group in self.groups
            for package in group.packages
        ):
            raise ValueError("causal Catalog crosses a shared Contract parent")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_causal_development_catalog:",
        ):
            raise ValueError("causal Development Catalog identity is invalid")
        return self


class CausalCounterfactualReplay(FrozenModel):
    replay_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    baseline_witness_id: str = Field(min_length=1)
    counterfactual_kind: CausalCounterfactualKind
    intervention_candidate_id: str = Field(min_length=1)
    graph_remained_structurally_valid: Literal[True] = True
    runtime_completed_typed_terminal: Literal[True] = True
    task_verifier_invoked: Literal[True] = True
    mechanism_verifier_invoked: Literal[True] = True
    observations: tuple[CausalRuntimeObservation, ...] = Field(min_length=1)
    task_validity: CausalTaskValidityReport
    mechanism_validity: CausalMechanismValidityReport
    qualified_validity: CausalQualifiedValidityReport
    counterfactual_base_valid: bool
    counterfactual_mechanism_qualified: bool
    counterfactual_qualified_valid: bool
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_replay(self) -> CausalCounterfactualReplay:
        if (
            self.counterfactual_base_valid != self.task_validity.base_valid
            or self.counterfactual_mechanism_qualified
            != self.mechanism_validity.mechanism_qualified
            or self.counterfactual_qualified_valid != self.qualified_validity.qualified_valid
            or self.qualified_validity.task_report_id != self.task_validity.report_id
            or self.qualified_validity.mechanism_report_id != self.mechanism_validity.report_id
        ):
            raise ValueError("causal Counterfactual result is not computed from Verifiers")
        if self.replay_id != identity(
            self,
            "replay_id",
            "finance_v26_causal_depth_counterfactual_replay:",
        ):
            raise ValueError("causal Counterfactual identity is invalid")
        return self


class CausalCounterfactualCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    replays: tuple[CausalCounterfactualReplay, ...] = Field(min_length=64, max_length=64)
    package_count: Literal[32] = 32
    counterfactuals_per_package: Literal[2] = 2
    task_verifier_invocation_count: Literal[64] = 64
    mechanism_verifier_invocation_count: Literal[64] = 64
    base_invalid_count: Literal[64] = 64
    mechanism_unqualified_count: Literal[64] = 64
    qualified_invalid_count: Literal[64] = 64
    malformed_graph_rejection_used_as_necessity_evidence: Literal[False] = False
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> CausalCounterfactualCatalog:
        if len({item.package_id for item in self.replays}) != self.package_count:
            raise ValueError("causal Counterfactual Package denominator changed")
        if any(
            item.counterfactual_base_valid
            or item.counterfactual_mechanism_qualified
            or item.counterfactual_qualified_valid
            for item in self.replays
        ):
            raise ValueError("causal Counterfactual unexpectedly retained validity")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_causal_depth_counterfactual_catalog:",
        ):
            raise ValueError("causal Counterfactual Catalog identity is invalid")
        return self


class PublicProjectionLeakageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    prompt_projection_count: int = Field(ge=32)
    public_candidate_count: int = Field(ge=64)
    recursive_host_key_leak_count: Literal[0] = 0
    recursive_answer_cue_count: Literal[0] = 0
    full_future_graph_exposure_count: Literal[0] = 0
    reference_path_exposure_count: Literal[0] = 0
    capability_label_exposure_count: Literal[0] = 0
    depth_label_exposure_count: Literal[0] = 0
    nonopaque_action_id_count: Literal[0] = 0
    unequal_candidate_encoding_state_count: Literal[0] = 0
    nonisomorphic_candidate_schema_state_count: Literal[0] = 0
    candidate_argument_shape_mismatch_state_count: Literal[0] = 0
    synthetic_alternative_cue_count: Literal[0] = 0
    unbalanced_reference_position_cell_count: Literal[0] = 0
    id_free_semantic_choice_failure_count: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicProjectionLeakageAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_public_projection_leakage_audit:",
        ):
            raise ValueError("Public Projection Leakage Audit identity is invalid")
        return self


class CausalRuntimeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    baseline_task_valid_count: Literal[32] = 32
    baseline_mechanism_qualified_count: Literal[32] = 32
    baseline_qualified_valid_count: Literal[32] = 32
    nonterminal_state_count: int = Field(ge=32)
    branch_divergent_state_count: int = Field(ge=32)
    all_candidates_same_successor_count: Literal[0] = 0
    finance_program_coupled_package_count: Literal[32] = 32
    context_dependent_candidate_set_pass_count: Literal[8] = 8
    reconciliation_unproduced_consumption_rejection_count: Literal[8] = 8
    recovery_without_failure_rejection_count: Literal[8] = 8
    stopping_before_verification_rejection_count: Literal[8] = 8
    postcompletion_violation_terminal_count: Literal[8] = 8
    impossible_trace_acceptance_count: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CausalRuntimeAudit:
        if self.branch_divergent_state_count != self.nonterminal_state_count:
            raise ValueError("not every causal Runtime State branches")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_causal_runtime_audit:",
        ):
            raise ValueError("causal Runtime Audit identity is invalid")
        return self


class ParentBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    mutation_kind_count: Literal[10] = 10
    crossed_parent_mutation_count: Literal[320] = 320
    crossed_parent_rejection_count: Literal[320] = 320
    child_identity_recomputed_count: Literal[320] = 320
    package_identity_recomputed_count: Literal[320] = 320
    group_identity_recomputed_count: Literal[320] = 320
    catalog_identity_recomputed_count: Literal[320] = 320
    stale_hash_only_mutation_count: Literal[0] = 0
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentBindingAudit:
        if self.crossed_parent_rejection_count != self.crossed_parent_mutation_count:
            raise ValueError("not every recomputed crossed parent failed closed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_causal_depth_parent_binding_audit:",
        ):
            raise ValueError("Parent Binding Audit identity is invalid")
        return self


class OperationalWitnessInterpretation(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_package_count: Literal[32] = 32
    unique_finance_core_count: Literal[8] = 8
    unique_operational_witness_count: Literal[8] = 8
    operational_witness_package_replay_count: Literal[32] = 32
    unique_causal_depth_witness_count: Literal[32] = 32
    independent_finance_witness_surface_claim_count: Literal[8] = 8
    independent_depth_runtime_surface_claim_count: Literal[32] = 32
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OperationalWitnessInterpretation:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_operational_witness_interpretation:",
        ):
            raise ValueError("Operational Witness Interpretation identity is invalid")
        return self


StaticGateName = Literal[
    "candidate_encoding_equality",
    "candidate_position_balance",
    "causal_counterfactual_validity",
    "causal_finance_binding",
    "causal_runtime_branching",
    "confirmation_access_zero",
    "context_dependency",
    "development_catalog_closure",
    "finance_program_verifier",
    "historical_v168_freeze",
    "host_public_separation",
    "id_free_semantic_selection",
    "operational_witness_interpretation",
    "parent_binding_fail_closed",
    "prompt_recursive_leakage_zero",
    "provider_zero",
    "reconciliation_preconditions",
    "recovery_preconditions",
    "source_transitive_closure",
    "stopping_preconditions",
    "target_load_monotonicity",
    "task_level_necessity",
]


class StaticGateResult(FrozenModel):
    gate: StaticGateName
    passed: Literal[True] = True
    evidence_count: int = Field(ge=1)


class CausalDepthStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGateResult, ...] = Field(min_length=22, max_length=22)
    gate_count: Literal[22] = 22
    passed_gate_count: Literal[22] = 22
    provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    model_behavior_measured: Literal[False] = False
    runner_preflighted: Literal[False] = False
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> CausalDepthStaticAudit:
        names = tuple(item.gate for item in self.gates)
        if names != tuple(sorted(set(names))):
            raise ValueError("causal Static Gates are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_causal_depth_static_audit:",
        ):
            raise ValueError("causal Static Audit identity is invalid")
        return self


class CausalDepthTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    next_stage: Literal["capability_observation_executable_depth_development_runner_preflight_only"]
    provider_calls_authorized: Literal[False] = False
    development_jobs_authorized: Literal[False] = False
    confirmation_payload_loading_authorized: Literal[False] = False
    source_or_graph_change_authorized: Literal[False] = False
    mapper_or_vtdo_authorized: Literal[False] = False
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> CausalDepthTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_causal_depth_transition:",
        ):
            raise ValueError("causal depth Transition identity is invalid")
        return self


class CausalDepthHardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    transitive_source_root_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    defect_reproduction_audit_id: str = Field(min_length=1)
    projection_contract_id: str = Field(min_length=1)
    presentation_policy_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    leakage_audit_id: str = Field(min_length=1)
    runtime_audit_id: str = Field(min_length=1)
    counterfactual_catalog_id: str = Field(min_length=1)
    parent_binding_audit_id: str = Field(min_length=1)
    operational_witness_interpretation_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...]
    development_package_count: Literal[32] = 32
    baseline_qualified_count: Literal[32] = 32
    task_level_counterfactual_count: Literal[64] = 64
    recursive_prompt_leak_count: Literal[0] = 0
    impossible_trace_acceptance_count: Literal[0] = 0
    crossed_parent_acceptance_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    development_jobs: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    model_behavior_measured: Literal[False] = False
    runner_preflighted: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_stage: Literal["capability_observation_executable_depth_development_runner_preflight_only"]
    schema_version: str = V26_CAUSAL_DEPTH_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CausalDepthHardeningReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_causal_depth_hardening_report:",
        ):
            raise ValueError("causal depth Hardening Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    transitive_source_root: TransitiveSourceRoot
    source_replay: SourceReplayAudit
    predecessor_integrity: PredecessorIntegrityAudit
    defect_reproduction: V168DefectReproductionAudit
    projection_contract: DepthPromptProjectionContract
    presentation_policy: CandidatePresentationPolicy
    development_catalog: CausalDevelopmentCatalog
    leakage_audit: PublicProjectionLeakageAudit
    runtime_audit: CausalRuntimeAudit
    counterfactual_catalog: CausalCounterfactualCatalog
    parent_binding_audit: ParentBindingAudit
    operational_witness_interpretation: OperationalWitnessInterpretation
    static_audit: CausalDepthStaticAudit
    transition: CausalDepthTransition
    report: CausalDepthHardeningReport
