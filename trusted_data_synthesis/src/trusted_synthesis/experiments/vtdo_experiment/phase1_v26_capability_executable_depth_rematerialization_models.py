from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.program import ProgramVerification
from trusted_synthesis.core.task.capability_observation import (
    CAPABILITY_FAMILY_ORDER,
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
    ObservationPartition,
)
from trusted_synthesis.core.task.executable_capability_depth import (
    BoundarySelectionAlgorithmContract,
    CapabilityDepthVerifierContract,
    CapabilityDepthWitnessContract,
    CompiledNuisanceMeasurement,
    CompiledTargetLoad,
    DepthPromptBinding,
    ExecutableCapabilityDepthGraph,
    ExecutableCapabilityDepthWitness,
    ExecutableDepthSignature,
    MechanismCounterfactualKind,
    ObservabilityFloorNuisanceEnvelope,
)
from trusted_synthesis.core.trajectory.executable_task import BoundPublicExecutableWitness
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    OperationalTaskRecord,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolEnvironmentManifest

V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION = (
    "finance_v26_capability_executable_depth_rematerialization.v1"
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
        "v26_163_frozen_source",
        "v26_167_frozen_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["89ed58d566df56edc1dc54087cb722dc5a485ee48068a543aa15d79850a10dbb"]
    review_byte_count: Literal[25940] = 25_940
    authorized_stage: Literal[
        "capability_observation_executable_depth_rematerialization_and_static_reaudit_only"
    ]
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_executable_depth_external_audit_authorization:",
        ):
            raise ValueError("v26.168 external authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=4)
    file_count: int = Field(ge=4)
    complete_static_import_closure: Literal[True] = True
    unresolved_trusted_synthesis_import_count: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("transitive source file count is inconsistent")
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("transitive source root is not canonical")
        if any(item.source_kind != "transitive_source" for item in self.files):
            raise ValueError("transitive source root contains another provenance")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_executable_depth_transitive_source_root:",
        ):
            raise ValueError("transitive source root identity is invalid")
        return self


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v26_167_report_id: str = Field(min_length=1)
    transitive_source_root_id: str = Field(min_length=1)
    bindings: tuple[FileBinding, ...] = Field(min_length=20)
    v26_167_historical_artifact_mutation_count: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.168 source replay is not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executable_depth_source_replay:",
        ):
            raise ValueError("v26.168 source replay identity is invalid")
        return self


class V167ExecutableDefectRow(FrozenModel):
    source_task_artifact_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    group_index: int = Field(ge=1, le=4)
    historical_tier: str = Field(min_length=1)
    source_evidence_count: int = Field(ge=1)
    source_program_node_count: int = Field(ge=1)
    variant_count: Literal[4] = 4
    unique_program_hash_count_across_depths: Literal[1] = 1
    unique_tool_set_count_across_depths: Literal[1] = 1
    unique_public_witness_sequence_count_across_depths: Literal[1] = 1
    actual_operational_witness_passed: bool
    actual_failure_reasons: tuple[str, ...]


class V167ExecutableDepthDefectAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v26_167_report_id: str = Field(min_length=1)
    rows: tuple[V167ExecutableDefectRow, ...] = Field(min_length=16, max_length=16)
    variant_count: Literal[64] = 64
    actual_public_witness_pass_count: Literal[48] = 48
    actual_public_witness_failure_count: Literal[16] = 16
    reconciliation_failure_count: Literal[16] = 16
    metadata_ladder_only: Literal[True] = True
    historical_report_rewritten: Literal[False] = False
    stale_development_preflight_authorization_blocked: Literal[True] = True
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V167ExecutableDepthDefectAudit:
        passed = sum(
            item.variant_count for item in self.rows if item.actual_operational_witness_passed
        )
        failed = self.variant_count - passed
        reconciliation = sum(
            item.variant_count
            for item in self.rows
            if item.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
            and not item.actual_operational_witness_passed
        )
        if (
            passed != self.actual_public_witness_pass_count
            or failed != self.actual_public_witness_failure_count
            or reconciliation != self.reconciliation_failure_count
        ):
            raise ValueError("v26.167 executable defect partition is inconsistent")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v167_executable_depth_defect_audit:",
        ):
            raise ValueError("v26.167 executable defect audit identity is invalid")
        return self


class ExecutableDepthSourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    group_index: int = Field(ge=1, le=4)
    partition: ObservationPartition
    source_task_artifact_id: str = Field(min_length=1)
    source_task_id: str = Field(min_length=1)
    historical_tier: Literal["easy_control", "frontier"]
    source_evidence_count: int = Field(ge=2)
    source_program_node_count: int = Field(ge=1)
    selected_core_evidence_ids: tuple[str, str]
    selected_core_evidence_version_ids: tuple[str, str]
    selected_core_source_record_ids: tuple[str, ...] = Field(min_length=1)
    source_core_semantic_signature: str = Field(min_length=1)
    source_mechanism_instance_signature: str = Field(min_length=1)
    selection_rank: str = Field(min_length=64, max_length=64)
    selection_before_outcome_load: Literal[True] = True

    @model_validator(mode="after")
    def validate_binding(self) -> ExecutableDepthSourceBinding:
        if self.selected_core_evidence_ids != tuple(sorted(set(self.selected_core_evidence_ids))):
            raise ValueError("selected core Evidence IDs are not canonical")
        if self.selected_core_evidence_version_ids != tuple(
            sorted(set(self.selected_core_evidence_version_ids))
        ):
            raise ValueError("selected core Evidence Version IDs are not canonical")
        expected_partition = (
            ObservationPartition.DEVELOPMENT
            if self.group_index <= 2
            else ObservationPartition.CONFIRMATION
        )
        expected_tier = (
            "easy_control" if self.partition == ObservationPartition.DEVELOPMENT else "frontier"
        )
        if self.partition != expected_partition or self.historical_tier != expected_tier:
            raise ValueError("source binding violates the low-nuisance partition rule")
        if self.binding_id != identity(
            self,
            "binding_id",
            "finance_v26_executable_depth_source_binding:",
        ):
            raise ValueError("executable depth source binding identity is invalid")
        return self


class ExecutableDepthSourceCapacityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    prior_exposed_population_id: str = Field(min_length=1)
    eligible_count_by_capability: dict[CapabilityFamily, int]
    selected: tuple[ExecutableDepthSourceBinding, ...] = Field(min_length=16, max_length=16)
    selected_group_count: Literal[16] = 16
    development_easy_group_count: Literal[8] = 8
    sealed_confirmation_frontier_group_count: Literal[8] = 8
    selected_core_evidence_count: Literal[32] = 32
    cross_group_overlap_count: Literal[0] = 0
    model_outcomes_used_for_selection: Literal[False] = False
    v26_167_static_exposure_is_model_exposure: Literal[False] = False
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutableDepthSourceCapacityAudit:
        if self.eligible_count_by_capability != {family: 7 for family in CAPABILITY_FAMILY_ORDER}:
            raise ValueError("v26.168 source capacity changed")
        if len({item.binding_id for item in self.selected}) != 16:
            raise ValueError("v26.168 selected source binding repeats")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executable_depth_source_capacity_audit:",
        ):
            raise ValueError("v26.168 source capacity audit identity is invalid")
        return self


class LowNuisanceFinanceCore(FrozenModel):
    core_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    partition: ObservationPartition
    source_task_artifact_id: str = Field(min_length=1)
    source_program_node_id: str = Field(min_length=1)
    operational_record: OperationalTaskRecord
    environment: AgentToolEnvironmentManifest
    operational_witness: BoundPublicExecutableWitness
    independent_task_verification_passed: Literal[True] = True
    evidence_count: Literal[2] = 2
    program_node_count: Literal[1] = 1
    program_edge_count: Literal[0] = 0
    model_behavior_measured: Literal[False] = False
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_core(self) -> LowNuisanceFinanceCore:
        record = self.operational_record
        if (
            record.environment_manifest_id != self.environment.manifest_id
            or self.operational_witness.task_package_id != record.task_package.package_id
            or not self.operational_witness.full_validity_passed
            or len(record.evidence_bundle.evidence) != self.evidence_count
            or len(record.task_package.task.oracle.task_program.nodes) != self.program_node_count
        ):
            raise ValueError("low-nuisance Finance core binding is invalid")
        if self.core_id != identity(
            self,
            "core_id",
            "finance_v26_low_nuisance_finance_core:",
        ):
            raise ValueError("low-nuisance Finance core identity is invalid")
        return self


class ExecutableDepthPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    partition: ObservationPartition
    capability_family: CapabilityFamily
    depth: ObservationDepth
    source_binding_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    graph: ExecutableCapabilityDepthGraph
    witness_contract: CapabilityDepthWitnessContract
    verifier_contract: CapabilityDepthVerifierContract
    variant_operational_witness: BoundPublicExecutableWitness
    variant_program_verification: ProgramVerification
    depth_witness: ExecutableCapabilityDepthWitness
    target_load: CompiledTargetLoad
    nuisance: CompiledNuisanceMeasurement
    prompt_binding: DepthPromptBinding
    signature: ExecutableDepthSignature
    operational_witness_compiler_invocation_count: Literal[1] = 1
    task_program_verifier_invocation_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    runner_preflighted: Literal[False] = False
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> ExecutableDepthPackage:
        expected_id = canonical_hash(
            {
                "group_id": self.group_id,
                "partition": self.partition.value,
                "capability_family": self.capability_family.value,
                "depth": self.depth.value,
                "source_binding_id": self.source_binding_id,
                "finance_core_id": self.finance_core_id,
                "schema_version": self.schema_version,
            },
            prefix="finance_v26_executable_depth_package:",
        )
        if self.package_id != expected_id or self.graph.package_id != self.package_id:
            raise ValueError("executable depth Package identity is invalid")
        if (
            self.graph.capability_family != self.capability_family
            or self.graph.depth != self.depth
            or self.graph.finance_core_id != self.finance_core_id
            or self.witness_contract.graph_id != self.graph.graph_id
            or self.verifier_contract.witness_contract_id != self.witness_contract.contract_id
            or self.variant_operational_witness.task_package_id
            != self.graph.base_operational_task_package_id
            or not self.variant_operational_witness.full_validity_passed
            or not self.variant_program_verification.passed
            or self.variant_program_verification.independently_computed_output is None
            or self.signature.variant_operational_witness_id
            != self.variant_operational_witness.witness_id
            or self.signature.variant_program_verification_hash
            != canonical_hash(
                self.variant_program_verification.model_dump(mode="json"),
                prefix="variant_task_program_verification:",
            )
            or self.depth_witness.graph_id != self.graph.graph_id
            or self.target_load.graph_id != self.graph.graph_id
            or self.target_load.witness_id != self.depth_witness.witness_id
            or self.nuisance.finance_core_id != self.finance_core_id
            or self.prompt_binding.graph_id != self.graph.graph_id
            or self.signature.package_id != self.package_id
            or self.signature.graph_id != self.graph.graph_id
        ):
            raise ValueError("executable depth Package parent bindings are inconsistent")
        return self


class ExecutableDepthGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    group_index: int = Field(ge=1, le=4)
    partition: ObservationPartition
    capability_family: CapabilityFamily
    source_binding_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    packages: tuple[ExecutableDepthPackage, ...] = Field(min_length=4, max_length=4)
    exposure_unit_is_whole_group: Literal[True] = True
    partial_regeneration_allowed: Literal[False] = False
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> ExecutableDepthGroup:
        if tuple(item.depth for item in self.packages) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("executable depth Group does not contain D0-D3")
        if any(
            item.group_id != self.group_id
            or item.partition != self.partition
            or item.capability_family != self.capability_family
            or item.source_binding_id != self.source_binding_id
            or item.finance_core_id != self.finance_core_id
            for item in self.packages
        ):
            raise ValueError("executable depth Group Package binding changed")
        totals = tuple(item.target_load.total for item in self.packages)
        if any(left >= right for left, right in zip(totals, totals[1:], strict=False)):
            raise ValueError("computed executable target load is not strictly increasing")
        if len({item.graph.graph_id for item in self.packages}) != 4:
            raise ValueError("executable depth Group repeats a Runtime graph")
        if len({item.nuisance.measurement_id for item in self.packages}) != 1:
            raise ValueError("executable depth Group changes computed nuisance")
        if len({item.prompt_binding.rendered_prompt_bytes for item in self.packages}) != 1:
            raise ValueError("executable depth Group changes Prompt byte burden")
        expected_id = canonical_hash(
            {
                "group_index": self.group_index,
                "partition": self.partition.value,
                "capability_family": self.capability_family.value,
                "source_binding_id": self.source_binding_id,
                "finance_core_id": self.finance_core_id,
                "schema_version": self.schema_version,
            },
            prefix="finance_v26_executable_depth_group:",
        )
        if self.group_id != expected_id:
            raise ValueError("executable depth Group identity is invalid")
        return self


class ExecutableDepthCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    partition: ObservationPartition
    finance_cores: tuple[LowNuisanceFinanceCore, ...] = Field(min_length=8, max_length=8)
    groups: tuple[ExecutableDepthGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    package_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> ExecutableDepthCatalog:
        if any(item.partition != self.partition for item in self.groups):
            raise ValueError("executable depth Catalog crosses partitions")
        if {item.core_id for item in self.finance_cores} != {
            item.finance_core_id for item in self.groups
        }:
            raise ValueError("executable depth Catalog core set is incomplete")
        if sum(len(item.packages) for item in self.groups) != self.package_count:
            raise ValueError("executable depth Catalog Package count changed")
        cores = {item.core_id: item for item in self.finance_cores}
        for group in self.groups:
            core = cores[group.finance_core_id]
            program_id = core.operational_record.task_package.task.oracle.task_program.program_id
            task_package_id = core.operational_record.task_package.package_id
            if any(
                package.graph.base_operational_task_package_id != task_package_id
                or package.variant_program_verification.program_id != program_id
                or package.signature.base_operational_record_id != core.operational_record.record_id
                for package in group.packages
            ):
                raise ValueError("executable depth Catalog variant replay is misbound")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            f"finance_v26_{self.partition.value}_executable_depth_catalog:",
        ):
            raise ValueError("executable depth Catalog identity is invalid")
        return self


class SealedConfirmationReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    sealed_catalog_id: str = Field(min_length=1)
    sealed_content_root_sha256: str = Field(min_length=64, max_length=64)
    sealed_file_count: Literal[1] = 1
    sealed_byte_count: int = Field(ge=1)
    payload_path_disclosed_to_development: Literal[False] = False
    payload_embedded_in_development_root: Literal[False] = False
    development_payload_access_count: Literal[0] = 0
    host_static_construction_only: Literal[True] = True
    sealed_until_development_postrun_audit: Literal[True] = True
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> SealedConfirmationReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "finance_v26_sealed_confirmation_executable_depth_receipt:",
        ):
            raise ValueError("sealed Confirmation receipt identity is invalid")
        return self


class FixedDevelopmentGenerationCondition(FrozenModel):
    condition_id: str = Field(min_length=1)
    name: Literal["fixed_development_generation_condition"] = (
        "fixed_development_generation_condition"
    )
    path_strategy: Literal["structured_direct"] = "structured_direct"
    capability_cue_injected: Literal[False] = False
    static_reference_path_exposed: Literal[False] = False
    capability_neutral_label_claimed: Literal[False] = False
    runner_prompt_noninterference_preflighted: Literal[False] = False
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_condition(self) -> FixedDevelopmentGenerationCondition:
        if self.condition_id != identity(
            self,
            "condition_id",
            "fixed_development_generation_condition:",
        ):
            raise ValueError("fixed Development condition identity is invalid")
        return self


class TargetCapabilityNoninterferenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    condition_id: str = Field(min_length=1)
    development_package_count: Literal[32] = 32
    candidate_set_match_count: Literal[32] = 32
    transition_graph_match_count: Literal[32] = 32
    capability_cue_injection_count: Literal[0] = 0
    static_reference_path_exposure_count: Literal[0] = 0
    runner_prompt_noninterference_unmeasured: Literal[True] = True
    capability_neutral_term_deferred: Literal[True] = True
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TargetCapabilityNoninterferenceAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_target_capability_noninterference_audit:",
        ):
            raise ValueError("target-capability noninterference audit identity is invalid")
        return self


class BoundaryAlgorithmTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    boolean_pattern_count: Literal[256] = 256
    development_pattern_count: Literal[256] = 256
    confirmation_pattern_count: Literal[256] = 256
    uniquely_classified_pattern_count: Literal[512] = 512
    threshold_denominator_pair_count: Literal[2] = 2
    threshold_edge_case_count: Literal[8] = 8
    threshold_edge_case_pass_count: Literal[8] = 8
    artificial_interpretation_branch_count: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BoundaryAlgorithmTotalityAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_boundary_algorithm_totality_audit:",
        ):
            raise ValueError("Boundary Algorithm totality audit identity is invalid")
        return self


class MechanismCounterfactualReplay(FrozenModel):
    replay_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    baseline_witness_id: str = Field(min_length=1)
    counterfactual_kind: MechanismCounterfactualKind
    mutation_target_candidate_id: str = Field(min_length=1)
    production_graph_or_runtime_mutated: Literal[True] = True
    target_event_requirement_preserved: Literal[True] = True
    observed_failure_code: str = Field(min_length=1)
    full_validity_passed: Literal[False] = False
    target_mechanism_necessary: Literal[True] = True
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_replay(self) -> MechanismCounterfactualReplay:
        if self.replay_id != identity(
            self,
            "replay_id",
            "finance_v26_executable_depth_counterfactual_replay:",
        ):
            raise ValueError("executable depth counterfactual Replay identity is invalid")
        return self


class MechanismNecessityCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    replays: tuple[MechanismCounterfactualReplay, ...] = Field(min_length=128, max_length=128)
    package_count: Literal[64] = 64
    counterfactuals_per_package: Literal[2] = 2
    failed_counterfactual_count: Literal[128] = 128
    necessity_pass_count: Literal[64] = 64
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> MechanismNecessityCatalog:
        if len({item.package_id for item in self.replays}) != self.package_count:
            raise ValueError("Necessity Catalog Package denominator changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_executable_depth_mechanism_necessity_catalog:",
        ):
            raise ValueError("Necessity Catalog identity is invalid")
        return self


class NuisanceRecomputationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    envelope_contract_id: str = Field(min_length=1)
    package_count: Literal[64] = 64
    computed_measurement_count: Literal[64] = 64
    within_group_exact_match_count: Literal[64] = 64
    development_floor_envelope_pass_count: Literal[32] = 32
    declared_zero_delta_used_as_oracle: Literal[False] = False
    source_hard_development_group_count: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NuisanceRecomputationAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executable_depth_nuisance_recomputation_audit:",
        ):
            raise ValueError("nuisance recomputation audit identity is invalid")
        return self


StaticGateName = Literal[
    "boundary_algorithm_totality",
    "computed_nuisance_stability",
    "computed_target_load_monotonicity",
    "confirmation_access_isolation",
    "d0_real_mechanism",
    "development_floor_envelope",
    "executable_candidate_delta",
    "executable_graph_delta",
    "executable_transition_delta",
    "fixed_condition_noninterference",
    "historical_v167_freeze",
    "low_nuisance_operational_witness",
    "mechanism_event_multiplicity",
    "mechanism_necessity",
    "provider_zero",
    "public_witness",
    "reconciliation_reference_consumption",
    "source_capacity_and_freshness",
    "stale_preflight_block",
    "task_verifier",
    "transitive_source_closure",
    "typed_runtime_terminal_policy",
]


class StaticGateResult(FrozenModel):
    gate_name: StaticGateName
    passed: Literal[True] = True
    denominator: int = Field(ge=1)
    numerator: int = Field(ge=1)
    evidence_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_gate(self) -> StaticGateResult:
        if self.numerator != self.denominator:
            raise ValueError("noncompensatory executable-depth Gate did not pass")
        return self


class ExecutableDepthStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGateResult, ...] = Field(min_length=22, max_length=22)
    gate_count: Literal[22] = 22
    passed_gate_count: Literal[22] = 22
    group_count: Literal[16] = 16
    package_count: Literal[64] = 64
    public_witness_pass_count: Literal[64] = 64
    task_verifier_pass_count: Literal[64] = 64
    mechanism_necessity_pass_count: Literal[64] = 64
    reconciliation_consumption_pass_count: Literal[16] = 16
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExecutableDepthStaticAudit:
        if tuple(item.gate_name for item in self.gates) != tuple(
            sorted(item.gate_name for item in self.gates)
        ):
            raise ValueError("executable-depth Gates are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executable_depth_static_audit:",
        ):
            raise ValueError("executable-depth static audit identity is invalid")
        return self


ProductionMutationTarget = Literal[
    "boundary_contract",
    "development_catalog",
    "depth_witness",
    "executable_graph",
    "finance_core",
    "nuisance_measurement",
    "operational_task_package",
    "operational_witness",
    "prompt_binding",
    "runtime_observation",
    "runtime_trace",
    "sealed_receipt",
    "source_root",
    "task_program",
    "task_verifier_binding",
    "verifier_contract",
]


class ProductionMutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    target_object_kind: ProductionMutationTarget
    production_validator_invoked: Literal[True] = True
    detected: Literal[True] = True
    failure_code: str = Field(min_length=1)


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[ProductionMutationResult, ...] = Field(min_length=30, max_length=30)
    mutation_count: Literal[30] = 30
    detected_count: Literal[30] = 30
    abstract_summary_dictionary_mutation_count: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if tuple(item.mutation_name for item in self.mutations) != tuple(
            sorted(item.mutation_name for item in self.mutations)
        ):
            raise ValueError("production destructive mutations are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_executable_depth_production_destructive_audit:",
        ):
            raise ValueError("production destructive audit identity is invalid")
        return self


class TransitionContract(FrozenModel):
    transition_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    sealed_confirmation_receipt_id: str = Field(min_length=1)
    boundary_algorithm_contract_id: str = Field(min_length=1)
    next_stage: Literal["capability_observation_executable_depth_development_runner_preflight_only"]
    future_development_job_count: Literal[192] = 192
    provider_execution_authorized: Literal[False] = False
    confirmation_payload_loading_authorized: Literal[False] = False
    mapper_or_vtdo_authorized: Literal[False] = False
    forbidden_operations: tuple[str, ...] = Field(min_length=10)
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> TransitionContract:
        required = {
            "confirmation_payload_loading",
            "provider_execution",
            "source_reselection",
            "threshold_tuning",
            "v26_167_historical_rewrite",
            "vtdo_or_contribution_estimation",
        }
        if self.forbidden_operations != tuple(sorted(set(self.forbidden_operations))):
            raise ValueError("v26.168 transition prohibitions are not canonical")
        if not required <= set(self.forbidden_operations):
            raise ValueError("v26.168 transition omits a required prohibition")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_executable_depth_transition:",
        ):
            raise ValueError("v26.168 transition identity is invalid")
        return self


class DetailFile(FrozenModel):
    filename: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class ExecutableDepthRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    transitive_source_root_id: str = Field(min_length=1)
    v26_167_defect_audit_id: str = Field(min_length=1)
    source_capacity_audit_id: str = Field(min_length=1)
    nuisance_envelope_contract_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    sealed_confirmation_receipt_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    noninterference_audit_id: str = Field(min_length=1)
    boundary_algorithm_contract_id: str = Field(min_length=1)
    boundary_totality_audit_id: str = Field(min_length=1)
    necessity_catalog_id: str = Field(min_length=1)
    nuisance_recomputation_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=10)
    group_count: Literal[16] = 16
    package_count: Literal[64] = 64
    development_package_count: Literal[32] = 32
    sealed_confirmation_package_count: Literal[32] = 32
    public_witness_pass_count: Literal[64] = 64
    mechanism_necessity_pass_count: Literal[64] = 64
    production_mutation_detected_count: Literal[30] = 30
    development_confirmation_payload_access_count: Literal[0] = 0
    historical_artifact_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    development_jobs: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    model_behavior_measured: Literal[False] = False
    runner_preflighted: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_stage: Literal["capability_observation_executable_depth_development_runner_preflight_only"]
    schema_version: str = V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> ExecutableDepthRematerializationReport:
        names = tuple(item.filename for item in self.detail_files)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.168 detail files are not canonical")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_executable_depth_rematerialization_report:",
        ):
            raise ValueError("v26.168 report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    transitive_source_root: TransitiveSourceRoot
    source_replay: SourceReplayAudit
    v167_defect: V167ExecutableDepthDefectAudit
    source_capacity: ExecutableDepthSourceCapacityAudit
    nuisance_envelope: ObservabilityFloorNuisanceEnvelope
    fixed_condition: FixedDevelopmentGenerationCondition
    noninterference: TargetCapabilityNoninterferenceAudit
    boundary_contract: BoundarySelectionAlgorithmContract
    boundary_totality: BoundaryAlgorithmTotalityAudit
    development_catalog: ExecutableDepthCatalog
    confirmation_receipt: SealedConfirmationReceipt
    necessity: MechanismNecessityCatalog
    nuisance_audit: NuisanceRecomputationAudit
    static_audit: ExecutableDepthStaticAudit
    destructive_audit: ProductionDestructiveAudit
    transition: TransitionContract
    report: ExecutableDepthRematerializationReport


def model_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value
